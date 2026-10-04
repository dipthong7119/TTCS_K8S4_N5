"""Wallet reads and append-only manual credits."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.charging_session import ChargingSession
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
        query = query.filter(
            (User.full_name.ilike(search)) | (User.email.ilike(search))
        )
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
                        (
                            WalletLedgerEntry.amount_vnd < 0,
                            WalletLedgerEntry.amount_vnd,
                        ),
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
        db.query(
            ChargingSession.user_id,
            func.max(ChargingSession.ended_at).label("last_charge"),
        )
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
                "last_charge_at": last_charge.isoformat() + "Z"
                if last_charge
                else None,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}
