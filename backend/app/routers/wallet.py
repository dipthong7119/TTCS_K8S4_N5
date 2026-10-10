"""Driver wallet APIs and read-only administrator driver balances."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import (
    CurrentUser,
    deny_unannotated_route,
    public_route,
    require_role,
)
from app.database import get_db
from app.models.user import Role, User, user_roles
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.audit import append_audit
from app.services.wallet import (
    create_sandbox_topup_request,
    list_driver_wallet_summaries,
    list_user_payment_transactions,
    list_wallet_entries,
    process_sandbox_webhook,
    wallet_totals,
)

router = APIRouter(
    prefix="/wallet",
    tags=["wallet"],
    dependencies=[Depends(deny_unannotated_route)],
)


from app.config import settings
from app.services.wallet import manual_topup

class ManualTopUpRequest(BaseModel):
    amount: int
    receipt_code: str
    note: str = ""


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
        raise HTTPException(status_code=422, detail=str(e))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã phiếu thu đã được sử dụng") from exc

    return {
        "ledger_entry_id": entry.id,
        "wallet_id": driver_user_id,  # Theo giả định dùng user_id thay wallet_id
        "amount": entry.amount_vnd,
        "balance_after": wallet_totals(db, driver_user_id)["balance_vnd"],
        "receipt_code": entry.receipt_code,
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

