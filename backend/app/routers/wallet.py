"""Driver wallet APIs and read-only administrator driver balances."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.user import Role, User, user_roles
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.audit import append_audit
from app.services.wallet import list_driver_wallet_summaries, list_wallet_entries, wallet_totals

router = APIRouter(
    prefix="/wallet",
    tags=["wallet"],
    dependencies=[Depends(deny_unannotated_route)],
)


class ManualTopUpRequest(BaseModel):
    amount_vnd: int = Field(ge=10_000, le=10_000_000)
    receipt_code: str = Field(min_length=3, max_length=80)

    @field_validator("receipt_code")
    @classmethod
    def normalize_receipt_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,79}", normalized):
            raise ValueError("Mã phiếu chỉ gồm chữ, số, gạch ngang hoặc gạch dưới")
        return normalized


@router.get("", dependencies=[Depends(require_role("driver"))])
async def get_my_wallet(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    return {
        "account_id": f"CSMS-{current_user.id:06d}",
        **wallet_totals(db, current_user.id),
    }


@router.get("/ledger", dependencies=[Depends(require_role("driver"))])
async def get_my_wallet_ledger(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    days: str = Query("30", max_length=10),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=50),
):
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


@router.get("/drivers", dependencies=[Depends(require_role("admin", "accountant"))])
async def get_driver_wallets(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return list_driver_wallet_summaries(
        db, query_text=q, page=page, page_size=page_size
    )


@router.post(
    "/drivers/{driver_id}/topups",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def manually_top_up_driver(
    driver_id: int,
    body: ManualTopUpRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    driver = (
        db.query(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(User.id == driver_id, Role.name == "driver")
        .first()
    )
    if driver is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản tài xế")
    if not driver.is_active:
        raise HTTPException(status_code=409, detail="Không thể nạp ví cho tài khoản đã khóa")
    if db.query(WalletLedgerEntry.id).filter_by(receipt_code=body.receipt_code).first():
        raise HTTPException(status_code=409, detail="Mã phiếu thu đã được sử dụng")

    entry = WalletLedgerEntry(
        user_id=driver.id,
        entry_type="manual_topup",
        amount_vnd=body.amount_vnd,
        idempotency_key=f"manual-topup:{body.receipt_code}",
        receipt_code=body.receipt_code,
        description="Nạp thủ công theo phiếu thu",
        actor_id=current_user.id,
    )
    db.add(entry)
    try:
        db.flush()
        append_audit(
            db,
            action="wallet.manual_topup",
            object_type="wallet_ledger",
            object_id=entry.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            details={"driver_id": driver.id, "amount_vnd": body.amount_vnd, "receipt_code": body.receipt_code},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã phiếu thu đã được sử dụng") from exc

    return {
        "id": entry.id,
        "driver_id": driver.id,
        "amount_vnd": entry.amount_vnd,
        "receipt_code": entry.receipt_code,
        "balance_vnd": wallet_totals(db, driver.id)["balance_vnd"],
    }
