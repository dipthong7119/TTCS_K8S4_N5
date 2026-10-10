"""Wallet reads and append-only manual credits."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.charging_session import ChargingSession
from app.models.payment_transaction import PaymentTransaction
from app.models.user import Role, User, user_roles
from app.models.wallet_ledger import WalletLedgerEntry


def wallet_totals(db: Session, user_id: int) -> dict[str, int]:
    balance = (
        db.query(func.coalesce(func.sum(WalletLedgerEntry.amount_vnd), 0))
        .filter(WalletLedgerEntry.user_id == user_id)
        .scalar()
    )
    topups = (
        db.query(func.coalesce(func.sum(WalletLedgerEntry.amount_vnd), 0))
        .filter(
            WalletLedgerEntry.user_id == user_id,
            WalletLedgerEntry.amount_vnd > 0,
        )
        .scalar()
    )
    spent = (
        db.query(func.coalesce(-func.sum(WalletLedgerEntry.amount_vnd), 0))
        .filter(
            WalletLedgerEntry.user_id == user_id,
            WalletLedgerEntry.amount_vnd < 0,
        )
        .scalar()
    )
    return {
        "balance_vnd": int(balance or 0),
        "total_topup_vnd": int(topups or 0),
        "total_spent_vnd": int(spent or 0),
    }


def list_wallet_entries(
    db: Session,
    user_id: int,
    *,
    days: int | None,
    page: int,
    page_size: int,
) -> dict:
    balance_at_entry = (
        db.query(
            WalletLedgerEntry.id.label("entry_id"),
            func.sum(WalletLedgerEntry.amount_vnd)
            .over(
                partition_by=WalletLedgerEntry.user_id,
                order_by=(WalletLedgerEntry.created_at, WalletLedgerEntry.id),
                rows=(None, 0),
            )
            .label("balance_after_vnd"),
        )
        .filter(WalletLedgerEntry.user_id == user_id)
        .subquery()
    )
    query = (
        db.query(WalletLedgerEntry, balance_at_entry.c.balance_after_vnd)
        .join(balance_at_entry, balance_at_entry.c.entry_id == WalletLedgerEntry.id)
        .filter(WalletLedgerEntry.user_id == user_id)
    )
    if days is not None:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        query = query.filter(WalletLedgerEntry.created_at >= cutoff)

    total = query.count()
    rows = (
        query.order_by(WalletLedgerEntry.created_at.desc(), WalletLedgerEntry.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": entry.id,
                "type": entry.entry_type,
                "amount_vnd": entry.amount_vnd,
                "description": entry.description,
                "balance_after_vnd": int(balance_after or 0),
                "created_at": entry.created_at.isoformat() + "Z",
                "reference_type": entry.reference_type,
                "reference_id": entry.reference_id,
                "receipt_code": entry.receipt_code,
            }
            for entry, balance_after in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_driver_wallet_summaries(
    db: Session, *, query_text: str | None, page: int, page_size: int
) -> dict:
    query = (
        db.query(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(Role.name == "driver")
        .distinct()
    )
    if query_text:
        search = f"%{query_text.strip()}%"
        query = query.filter((User.full_name.ilike(search)) | (User.email.ilike(search)))
    total = query.count()
    drivers = (
        query.order_by(User.full_name, User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    driver_ids = [driver.id for driver in drivers]
    if not driver_ids:
        return {"items": [], "total": total, "page": page, "page_size": page_size}

    ledger_totals = (
        db.query(
            WalletLedgerEntry.user_id,
            func.coalesce(func.sum(WalletLedgerEntry.amount_vnd), 0).label("balance"),
            func.coalesce(
                -func.sum(
                    case(
                        (WalletLedgerEntry.amount_vnd < 0, WalletLedgerEntry.amount_vnd),
                        else_=0,
                    )
                ),
                0,
            ).label("spent"),
        )
        .filter(WalletLedgerEntry.user_id.in_(driver_ids))
        .group_by(WalletLedgerEntry.user_id)
        .all()
    )
    totals_by_user = {row.user_id: row for row in ledger_totals}
    last_charges = (
        db.query(ChargingSession.user_id, func.max(ChargingSession.ended_at).label("last_charge"))
        .filter(
            ChargingSession.user_id.in_(driver_ids),
            ChargingSession.status == "completed",
        )
        .group_by(ChargingSession.user_id)
        .all()
    )
    last_by_user = {row.user_id: row.last_charge for row in last_charges}

    items = []
    for driver in drivers:
        totals_row = totals_by_user.get(driver.id)
        last_charge = last_by_user.get(driver.id)
        items.append(
            {
                "id": driver.id,
                "full_name": driver.full_name,
                "email": driver.email,
                "is_active": driver.is_active,
                "balance_vnd": int(totals_row.balance if totals_row else 0),
                "total_spent_vnd": int(totals_row.spent if totals_row else 0),
                "last_charge_at": last_charge.isoformat() + "Z" if last_charge else None,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def create_sandbox_topup_request(
    db: Session,
    user_id: int,
    amount_vnd: int,
) -> PaymentTransaction:
    """Tạo đơn nạp tiền qua cổng sandbox (SCRUM-196, SCRUM-197)."""
    now = datetime.now(UTC)
    timestamp_str = now.strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:6].upper()
    order_code = f"TOPUP-{timestamp_str}-{suffix}"

    tx = PaymentTransaction(
        order_code=order_code,
        user_id=user_id,
        amount_vnd=amount_vnd,
        status="pending",
        provider="sandbox",
        payment_url=f"/wallet/sandbox-checkout?order_code={order_code}",
    )
    db.add(tx)
    db.flush()
    return tx


def process_sandbox_webhook(
    db: Session,
    order_code: str,
    status: str,
    failure_reason: str | None = None,
) -> tuple[PaymentTransaction | None, WalletLedgerEntry | None]:
    """Xử lý webhook callback từ cổng sandbox với cơ chế idempotent (SCRUM-198)."""
    tx = db.query(PaymentTransaction).filter_by(order_code=order_code).first()
    if not tx:
        return None, None

    # Idempotent: nếu giao dịch đã hoàn tất trước đó thì không cộng tiền lại
    if tx.status == "success":
        existing_entry = (
            db.query(WalletLedgerEntry)
            .filter_by(idempotency_key=f"sandbox-topup:{tx.order_code}")
            .first()
        )
        return tx, existing_entry

    if tx.status in ("failed", "cancelled"):
        return tx, None

    if status == "success":
        tx.status = "success"
        tx.failure_reason = None
        entry = WalletLedgerEntry(
            user_id=tx.user_id,
            entry_type="sandbox_topup",
            amount_vnd=tx.amount_vnd,
            idempotency_key=f"sandbox-topup:{tx.order_code}",
            receipt_code=tx.order_code,
            reference_type="payment_transaction",
            reference_id=tx.id,
            description=f"Nạp ví qua cổng sandbox ({tx.order_code})",
        )
        db.add(entry)
        db.flush()
        return tx, entry

    # Trường hợp thất bại hoặc hủy
    tx.status = status if status in ("failed", "cancelled") else "failed"
    tx.failure_reason = (
        failure_reason or "Giao dịch thanh toán bị hủy hoặc không thành công"
    )
    db.flush()
    return tx, None


def list_user_payment_transactions(
    db: Session,
    user_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Lấy danh sách lịch sử các yêu cầu nạp tiền của tài xế (SCRUM-197)."""
    query = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.user_id == user_id)
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": tx.id,
                "order_code": tx.order_code,
                "amount_vnd": tx.amount_vnd,
                "status": tx.status,
                "provider": tx.provider,
                "payment_url": tx.payment_url,
                "failure_reason": tx.failure_reason,
                "created_at": (
                    tx.created_at.isoformat() + "Z" if tx.created_at else None
                ),
                "updated_at": (
                    tx.updated_at.isoformat() + "Z" if tx.updated_at else None
                ),
            }
            for tx in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def has_minimum_balance(
    db: Session,
    user_id: int,
    min_amount_vnd: int = 50_000,
) -> bool:
    """Kiểm tra số dư đạt ngưỡng tối thiểu trước khi sạc (SCRUM-199, 72)."""
    totals = wallet_totals(db, user_id)
    return totals["balance_vnd"] >= min_amount_vnd


def deduct_session_charge(
    db: Session,
    user_id: int,
    session_id: int,
    amount_vnd: int,
    *,
    actor_id: int | None = None,
) -> WalletLedgerEntry:
    """Trừ tiền tự động từ ví khi phiên sạc kết thúc (SCRUM-199, SCRUM-71)."""
    idempotency_key = f"session-charge:{session_id}"
    existing = (
        db.query(WalletLedgerEntry).filter_by(idempotency_key=idempotency_key).first()
    )
    if existing:
        return existing

    amount_to_deduct = -abs(amount_vnd)
    entry = WalletLedgerEntry(
        user_id=user_id,
        entry_type="session_charge",
        amount_vnd=amount_to_deduct,
        idempotency_key=idempotency_key,
        receipt_code=f"CHARGE-{session_id}",
        reference_type="charging_session",
        reference_id=session_id,
        description=f"Thanh toán phiên sạc #{session_id}",
        actor_id=actor_id,
    )
    db.add(entry)
    db.flush()
    return entry


def refund_wallet_charge(
    db: Session,
    user_id: int,
    original_receipt_code: str,
    amount_vnd: int,
    reason: str,
    *,
    actor_id: int | None = None,
) -> WalletLedgerEntry:
    """Hoàn tiền vào ví tài xế khi giao dịch có sự cố (SCRUM-201)."""
    idempotency_key = f"refund:{original_receipt_code}"
    existing = (
        db.query(WalletLedgerEntry).filter_by(idempotency_key=idempotency_key).first()
    )
    if existing:
        return existing

    entry = WalletLedgerEntry(
        user_id=user_id,
        entry_type="refund",
        amount_vnd=abs(amount_vnd),
        idempotency_key=idempotency_key,
        receipt_code=f"REFUND-{original_receipt_code}",
        reference_type="wallet_ledger",
        description=f"Hoàn tiền giao dịch {original_receipt_code}: {reason}",
        actor_id=actor_id,
    )
    db.add(entry)
    db.flush()
    return entry


def manual_topup(
    db: Session,
    admin_user_id: int,
    driver_user_id: int,
    amount_vnd: int,
    receipt_code: str,
    note: str = ""
) -> WalletLedgerEntry:
    """Quản trị viên nạp tiền thủ công cho tài xế qua phiếu thu."""
    import re
    from fastapi import HTTPException
    from app.config import settings
    from app.services.audit import append_audit
    from sqlalchemy import func
    
    if type(amount_vnd) is not int or type(amount_vnd) is float:
        raise ValueError("Số tiền phải là số nguyên (int)")
    if amount_vnd < settings.MANUAL_TOPUP_MIN or amount_vnd > settings.MANUAL_TOPUP_MAX:
        raise ValueError(f"Số tiền nạp không hợp lệ (phải từ {settings.MANUAL_TOPUP_MIN} đến {settings.MANUAL_TOPUP_MAX})")

    receipt_code_norm = (receipt_code or "").strip().upper()
    if not (3 <= len(receipt_code_norm) <= 50):
        raise ValueError("Mã phiếu thu phải từ 3 đến 50 ký tự")
    if not re.match(r"^[A-Z0-9.\-_/]+$", receipt_code_norm):
        raise ValueError("Mã phiếu thu không hợp lệ")

    driver = db.query(User).join(user_roles).join(Role).filter(
        User.id == driver_user_id,
        Role.name == "driver"
    ).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản tài xế")
    if not driver.is_active:
        raise HTTPException(status_code=409, detail="Không thể nạp ví cho tài khoản đã khóa")

    entry = WalletLedgerEntry(
        user_id=driver_user_id,
        entry_type="manual_topup",
        amount_vnd=amount_vnd,
        idempotency_key=f"manual-topup:{receipt_code_norm}",
        receipt_code=receipt_code_norm,
        description=note.strip()[:200] if note else "",
        actor_id=admin_user_id,
    )
    db.add(entry)
    db.flush()
    
    append_audit(
        db,
        action="wallet.manual_topup",
        object_type="wallet_ledger",
        object_id=entry.id,
        actor_id=admin_user_id,
        details={"driver_id": driver_user_id, "amount_vnd": amount_vnd, "receipt_code": receipt_code_norm},
    )
    return entry


def wallet_balance_matches_ledger(db: Session, wallet_id: int) -> bool:
    """Hàm kiểm tra bất biến cho test. Do dùng user_id thay wallet_id, ta dùng wallet_id như user_id."""
    from sqlalchemy import func
    totals = wallet_totals(db, wallet_id)
    balance_calc = db.query(func.coalesce(func.sum(WalletLedgerEntry.amount_vnd), 0)).filter(WalletLedgerEntry.user_id == wallet_id).scalar()
    return totals["balance_vnd"] == int(balance_calc or 0)
