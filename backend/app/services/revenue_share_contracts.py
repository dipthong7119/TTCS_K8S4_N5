"""Versioned revenue-share agreement management."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.revenue_share_contract import RevenueShareContract
from app.models.station import Station
from app.models.user import User


def _utc_naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def list_revenue_share_contracts(db: Session, station_owner_id: int | None = None) -> dict:
    partners_query = (
        db.query(User)
        .join(Station, Station.owner_id == User.id)
        .distinct()
        .order_by(User.full_name, User.id)
    )
    if station_owner_id is not None:
        partners_query = partners_query.filter(User.id == station_owner_id)
    partners = partners_query.all()
    partner_by_id = {partner.id: partner for partner in partners}
    query = db.query(RevenueShareContract)
    if station_owner_id is not None:
        query = query.filter(RevenueShareContract.station_owner_id == station_owner_id)
    contracts = query.order_by(
        RevenueShareContract.station_owner_id,
        RevenueShareContract.effective_from.desc(),
        RevenueShareContract.id.desc(),
    ).all()
    return {
        "partners": [
            {"id": partner.id, "name": partner.full_name, "email": partner.email}
            for partner in partners
        ],
        "items": [
            {
                "id": contract.id,
                "station_owner_id": contract.station_owner_id,
                "partner_name": partner_by_id[contract.station_owner_id].full_name,
                "partner_email": partner_by_id[contract.station_owner_id].email,
                "partner_share_percent": contract.partner_share_percent,
                "platform_share_percent": contract.platform_share_percent,
                "effective_from": contract.effective_from.isoformat() + "Z",
                "effective_to": contract.effective_to.isoformat() + "Z"
                if contract.effective_to
                else None,
            }
            for contract in contracts
            if contract.station_owner_id in partner_by_id
        ],
    }


def create_revenue_share_contract(
    db: Session,
    *,
    station_owner_id: int,
    partner_share_percent: Decimal,
    platform_share_percent: Decimal,
    effective_from: datetime,
    created_by: int,
) -> RevenueShareContract:
    """Add a new version and close the prior version at its effective time."""
    if partner_share_percent + platform_share_percent != Decimal(100):
        raise ValueError("Tổng tỉ lệ đối tác và nền tảng phải bằng 100%")
    if not db.query(Station.id).filter(Station.owner_id == station_owner_id).first():
        raise LookupError("Không tìm thấy đối tác đang sở hữu trạm")
    effective_from = _utc_naive(effective_from)
    if effective_from <= datetime.now(UTC).replace(tzinfo=None):
        raise ValueError("Ngày hiệu lực hợp đồng phải ở tương lai để giữ nguyên các kỳ đã phát sinh")
    latest = (
        db.query(RevenueShareContract)
        .filter(RevenueShareContract.station_owner_id == station_owner_id)
        .order_by(RevenueShareContract.effective_from.desc(), RevenueShareContract.id.desc())
        .with_for_update()
        .first()
    )
    if latest is not None and effective_from <= latest.effective_from:
        raise ValueError("Ngày hiệu lực hợp đồng mới phải sau phiên bản hiện tại")
    if latest is not None and latest.effective_to is not None:
        raise ValueError("Hợp đồng mới không thể nối tiếp sau một khoảng đã kết thúc")
    if latest is not None:
        latest.effective_to = effective_from
    contract = RevenueShareContract(
        station_owner_id=station_owner_id,
        partner_share_percent=partner_share_percent,
        platform_share_percent=platform_share_percent,
        effective_from=effective_from,
        created_by=created_by,
    )
    db.add(contract)
    db.flush()
    return contract


def _effective_contracts(
    db: Session, owner_ids: set[int]
) -> dict[int, list[RevenueShareContract]]:
    if not owner_ids:
        return {}
    rows = (
        db.query(RevenueShareContract)
        .filter(RevenueShareContract.station_owner_id.in_(owner_ids))
        .order_by(
            RevenueShareContract.station_owner_id,
            RevenueShareContract.effective_from,
            RevenueShareContract.id,
        )
        .all()
    )
    by_owner: dict[int, list[RevenueShareContract]] = {}
    for row in rows:
        by_owner.setdefault(row.station_owner_id, []).append(row)
    return by_owner


def _contract_at(
    contracts: list[RevenueShareContract], at: datetime
) -> RevenueShareContract | None:
    for contract in reversed(contracts):
        if contract.effective_from <= at and (
            contract.effective_to is None or at < contract.effective_to
        ):
            return contract
    return None
