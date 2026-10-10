"""Driver wallet APIs and read-only administrator driver balances."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import (
    CurrentUser,
    deny_unannotated_route,
    public_route,
    require_role,
)
from app.database import get_db
from app.services.audit import append_audit
from app.services.wallet import (
    create_sandbox_topup_request,
    list_driver_wallet_summaries,
    list_user_payment_transactions,
    list_wallet_entries,
    manual_topup,
    process_sandbox_webhook,
    wallet_totals,
)

router = APIRouter(
    prefix="/wallet",
    tags=["wallet"],
    dependencies=[Depends(deny_unannotated_route)],
)


class ManualTopUpRequest(BaseModel):
    amount: StrictInt
    receipt_code: str
    note: str = ""


class LegacyManualTopUpRequest(BaseModel):
    amount_vnd: StrictInt
    receipt_code: str


@router.post(
    "/admin/wallets/{driver_user_id}/manual-topups",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def manually_top_up_driver(
    driver_user_id: int,
    body: ManualTopUpRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    try:
        entry = manual_topup(
            db=db,
            admin_user_id=current_user.id,
            driver_user_id=driver_user_id,
            amount_vnd=body.amount,
            receipt_code=body.receipt_code,
            note=body.note,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã phiếu thu đã được sử dụng") from exc

    balance_after = wallet_totals(db, driver_user_id)["balance_vnd"]
    return {
        "ledger_entry_id": entry.id,
        "wallet_id": driver_user_id,  # Theo giả định dùng user_id thay wallet_id
        "amount": entry.amount_vnd,
        "balance_after": balance_after,
        "amount_vnd": entry.amount_vnd,
        "balance_vnd": balance_after,
        "receipt_code": entry.receipt_code,
    }


@router.get(
    "/drivers",
    dependencies=[Depends(require_role("admin", "accountant"))],
)
async def get_driver_wallets(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """List driver balances for the existing administrator screen."""
    return list_driver_wallet_summaries(
        db, query_text=q, page=page, page_size=page_size
    )


@router.post(
    "/drivers/{driver_id}/topups",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def legacy_manually_top_up_driver(
    driver_id: int,
    body: LegacyManualTopUpRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Keep the endpoint and response shape used by the current admin UI."""
    try:
        entry = manual_topup(
            db=db,
            admin_user_id=current_user.id,
            driver_user_id=driver_id,
            amount_vnd=body.amount_vnd,
            receipt_code=body.receipt_code,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã phiếu thu đã được sử dụng") from exc

    return {
        "id": entry.id,
        "driver_id": driver_id,
        "amount_vnd": entry.amount_vnd,
        "receipt_code": entry.receipt_code,
        "balance_vnd": wallet_totals(db, driver_id)["balance_vnd"],
    }


@router.get(
    "/admin/wallets/{driver_user_id}/ledger",
    dependencies=[Depends(require_role("admin"))],
)
async def get_admin_wallet_ledger(
    driver_user_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
):
    return list_wallet_entries(
        db,
        driver_user_id,
        days=None,
        page=1,
        page_size=limit,
    )


class SandboxTopUpRequest(BaseModel):
    amount_vnd: int = Field(ge=10_000, le=10_000_000, description="Số tiền nạp (VNĐ)")


class SandboxWebhookPayload(BaseModel):
    order_code: str = Field(min_length=5, max_length=80)
    status: str = Field(default="success")
    failure_reason: str | None = None
    signature: str | None = None


class SimulatePayRequest(BaseModel):
    order_code: str = Field(min_length=5, max_length=80)
    status: str = Field(default="success")


@router.post(
    "/topups/sandbox",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("driver"))],
)
async def create_sandbox_topup(
    body: SandboxTopUpRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Tài xế khởi tạo yêu cầu nạp tiền qua cổng sandbox (SCRUM-196, SCRUM-197)."""
    tx = create_sandbox_topup_request(db, current_user.id, body.amount_vnd)
    append_audit(
        db,
        action="wallet.sandbox_topup_created",
        object_type="payment_transaction",
        object_id=tx.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_name=current_user.full_name,
        details={"order_code": tx.order_code, "amount_vnd": tx.amount_vnd},
    )
    db.commit()
    return {
        "order_code": tx.order_code,
        "amount_vnd": tx.amount_vnd,
        "status": tx.status,
        "provider": tx.provider,
        "payment_url": tx.payment_url,
        "created_at": tx.created_at.isoformat() + "Z" if tx.created_at else None,
    }


@router.post("/topups/sandbox/webhook")
@public_route
async def sandbox_topup_webhook(
    payload: SandboxWebhookPayload,
    db: Session = Depends(get_db),
):
    """Cổng sandbox gọi callback cập nhật kết quả giao dịch (SCRUM-198)."""
    tx, entry = process_sandbox_webhook(
        db,
        order_code=payload.order_code,
        status=payload.status,
        failure_reason=payload.failure_reason,
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mã giao dịch thanh toán",
        )

    if entry:
        append_audit(
            db,
            action="wallet.sandbox_topup_success",
            object_type="payment_transaction",
            object_id=tx.id,
            actor_id=tx.user_id,
            actor_email=None,
            actor_name=None,
            details={
                "order_code": tx.order_code,
                "amount_vnd": tx.amount_vnd,
                "ledger_entry_id": entry.id,
            },
        )
    db.commit()

    current_totals = wallet_totals(db, tx.user_id)
    return {
        "order_code": tx.order_code,
        "status": tx.status,
        "amount_vnd": tx.amount_vnd,
        "user_id": tx.user_id,
        "balance_vnd": current_totals["balance_vnd"],
    }


@router.post(
    "/topups/sandbox/simulate-pay",
    dependencies=[Depends(require_role("driver"))],
)
async def simulate_sandbox_payment(
    body: SimulatePayRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Giả lập thanh toán nhanh cho tài xế hoặc tester (SCRUM-196, 198)."""
    tx, entry = process_sandbox_webhook(
        db,
        order_code=body.order_code,
        status=body.status,
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mã đơn nạp tiền",
        )
    if tx.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thanh toán đơn nạp của tài khoản khác",
        )

    if entry:
        append_audit(
            db,
            action="wallet.sandbox_simulated_pay",
            object_type="payment_transaction",
            object_id=tx.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            details={"order_code": tx.order_code, "amount_vnd": tx.amount_vnd},
        )
    db.commit()

    return {
        "order_code": tx.order_code,
        "status": tx.status,
        "amount_vnd": tx.amount_vnd,
        "balance_vnd": wallet_totals(db, current_user.id)["balance_vnd"],
    }


@router.get(
    "/topups",
    dependencies=[Depends(require_role("driver"))],
)
async def get_my_topup_history(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """Xem lịch sử các lần yêu cầu nạp tiền của tài xế (SCRUM-197)."""
    return list_user_payment_transactions(
        db, current_user.id, page=page, page_size=page_size
    )


@router.get(
    "/check-balance",
    dependencies=[Depends(require_role("driver", "operator", "admin"))],
)
async def check_wallet_balance(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    user_id: int | None = Query(None, description="User ID cần kiểm tra"),
    min_amount_vnd: int = Query(50_000, ge=0),
):
    """Kiểm tra số dư tối thiểu trước khi kích hoạt phiên sạc (SCRUM-199 / SCRUM-72)."""
    target_user_id = current_user.id
    roles = [r.name for r in current_user.roles]
    if user_id is not None and user_id != current_user.id:
        if not {"admin", "operator"}.intersection(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ admin hoặc operator mới có thể tra cứu số dư người khác",
            )
        target_user_id = user_id

    balance = wallet_totals(db, target_user_id)["balance_vnd"]
    return {
        "user_id": target_user_id,
        "balance_vnd": balance,
        "minimum_required_vnd": min_amount_vnd,
        "has_minimum_balance": balance >= min_amount_vnd,
    }



wallets_router = APIRouter(
    prefix="/wallets",
    tags=["wallets"],
    dependencies=[Depends(deny_unannotated_route)],
)

class WalletTotalsResponse(BaseModel):
    account_id: str
    balance_vnd: int
    total_topup_vnd: int
    total_spent_vnd: int
    as_of: datetime

class LedgerItem(BaseModel):
    entry_id: int
    created_at: datetime
    type: str
    entry_type: str
    amount_vnd: int
    balance_after_vnd: int
    description: str
    session_id: int | None
    reference_code: str | None

class LedgerResponse(BaseModel):
    items: list[LedgerItem]
    total: int
    page: int
    page_size: int

def _check_driver_ownership(current_user: CurrentUser, target_user_id: int):
    # Dùng chung cho các route kiểm tra quyền sở hữu
    if current_user.id != target_user_id:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập ví của người khác")

@router.get("", response_model=WalletTotalsResponse, dependencies=[Depends(require_role("driver"))])
async def get_my_wallet(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    totals = wallet_totals(db, current_user.id)
    return {
        "account_id": f"W-{current_user.id:06d}",
        **totals,
        "as_of": datetime.now(UTC),
    }

@wallets_router.get("/{driver_user_id}", response_model=WalletTotalsResponse, dependencies=[Depends(require_role("driver"))])
async def get_driver_wallet(
    driver_user_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    _check_driver_ownership(current_user, driver_user_id)
    totals = wallet_totals(db, driver_user_id)
    return {
        "account_id": f"W-{driver_user_id:06d}",
        **totals,
        "as_of": datetime.now(UTC),
    }

@router.get("/ledger", response_model=LedgerResponse, dependencies=[Depends(require_role("driver"))])
async def get_my_wallet_ledger(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    days: str = Query("all", max_length=10),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
):
    page_size = min(page_size, 50) # Giới hạn tối đa 50 dòng theo yêu cầu
        
    day_count = None
    if days != "all":
        try:
            day_count = int(days)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="days phải là số ngày hoặc all") from exc
        if not 1 <= day_count <= 3650:
            raise HTTPException(status_code=422, detail="days nằm ngoài khoảng cho phép")
            
    return list_wallet_entries(
        db,
        current_user.id,
        days=day_count,
        page=page,
        page_size=page_size,
    )

@wallets_router.get("/{driver_user_id}/ledger", response_model=LedgerResponse, dependencies=[Depends(require_role("driver"))])
async def get_driver_wallet_ledger(
    driver_user_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    days: str = Query("all", max_length=10),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
):
    _check_driver_ownership(current_user, driver_user_id)
    
    page_size = min(page_size, 50)
        
    day_count = None
    if days != "all":
        try:
            day_count = int(days)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="days phải là số ngày hoặc all") from exc
        if not 1 <= day_count <= 3650:
            raise HTTPException(status_code=422, detail="days nằm ngoài khoảng cho phép")
            
    return list_wallet_entries(
        db,
        driver_user_id,
        days=day_count,
        page=page,
        page_size=page_size,
    )

