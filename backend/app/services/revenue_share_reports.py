"""Partner revenue-share reports for charging-subscription usage."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.models.driver_subscription import DriverSubscription
from app.models.station import Station
from app.models.subscription_usage import SubscriptionUsage
from app.models.user import User
from app.services.revenue_share_allocation import _allocate_by_contract


def _rounded_ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return int(
        (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


def list_owner_revenue_share(db: Session, owner_id: int) -> dict:
    """Return an owner's contract share across all package usage."""
    subscription_ids = [
        row[0]
        for row in db.query(SubscriptionUsage.subscription_id)
        .filter(SubscriptionUsage.station_owner_id == owner_id)
        .distinct()
        .all()
    ]
    if not subscription_ids:
        return {"items": [], "total_owner_share_vnd": 0}
    usages = (
        db.query(SubscriptionUsage)
        .filter(SubscriptionUsage.subscription_id.in_(subscription_ids))
        .order_by(SubscriptionUsage.subscription_id, SubscriptionUsage.id)
        .all()
    )
    by_subscription: dict[int, list[SubscriptionUsage]] = {}
    for usage in usages:
        by_subscription.setdefault(usage.subscription_id, []).append(usage)
    subscriptions = db.query(DriverSubscription).filter(
        DriverSubscription.id.in_(subscription_ids)
    ).all()
    subscription_by_id = {item.id: item for item in subscriptions}
    now = datetime.now(UTC).replace(tzinfo=None)
    items = []
    total_share = 0
    for subscription_id, rows in by_subscription.items():
        subscription = subscription_by_id.get(subscription_id)
        if subscription is None:
            continue
        groups = _allocate_by_contract(db, rows, subscription.monthly_fee_vnd)
        package_energy = sum(int(row.energy_wh) for row in rows)
        for (group_owner, _contract_id), group in groups.items():
            if group_owner != owner_id:
                continue
            shared = group["shared_amount_vnd"]
            total_share += shared
            items.append(
                {
                    "subscription_id": subscription.id,
                    "plan_name": subscription.plan_name,
                    "starts_at": subscription.starts_at.isoformat() + "Z",
                    "expires_at": subscription.expires_at.isoformat() + "Z",
                    "allocation_status": "accruing"
                    if subscription.expires_at > now
                    else "finalized",
                    "monthly_fee_vnd": subscription.monthly_fee_vnd,
                    "contract_id": group["contract_id"],
                    "partner_share_percent": group["partner_share_percent"],
                    "platform_share_percent": group["platform_share_percent"],
                    "platform_share_vnd": group["base_revenue_vnd"] - shared,
                    "station_owner_pool_vnd": shared,
                    "owner_energy_wh": group["energy_wh"],
                    "package_energy_wh": package_energy,
                    "owner_share_vnd": shared,
                }
            )
    return {"items": items, "total_owner_share_vnd": total_share}


def list_revenue_share_report(
    db: Session,
    date_from: date,
    date_to: date,
    *,
    station_owner_id: int | None = None,
) -> dict:
    """Report contract-based splits for package energy in a local-date interval."""
    zone = ZoneInfo(settings.STATION_TIMEZONE)
    start_at = datetime.combine(date_from, time.min, tzinfo=zone).astimezone(UTC).replace(tzinfo=None)
    end_at = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC).replace(tzinfo=None)
    period_rows = (
        db.query(SubscriptionUsage)
        .filter(SubscriptionUsage.created_at >= start_at, SubscriptionUsage.created_at < end_at)
        .order_by(SubscriptionUsage.subscription_id, SubscriptionUsage.id)
        .all()
    )
    period_by_sub: dict[int, list[SubscriptionUsage]] = {}
    for row in period_rows:
        period_by_sub.setdefault(row.subscription_id, []).append(row)
    sub_ids = list(period_by_sub)
    subscriptions = (
        db.query(DriverSubscription).filter(DriverSubscription.id.in_(sub_ids)).all()
        if sub_ids else []
    )
    subscription_by_id = {item.id: item for item in subscriptions}
    all_rows = (
        db.query(SubscriptionUsage)
        .filter(SubscriptionUsage.subscription_id.in_(sub_ids))
        .order_by(SubscriptionUsage.subscription_id, SubscriptionUsage.id)
        .all()
        if sub_ids else []
    )
    all_by_sub: dict[int, list[SubscriptionUsage]] = {}
    for row in all_rows:
        all_by_sub.setdefault(row.subscription_id, []).append(row)

    totals: dict[tuple[int, int | None], dict] = {}
    for sub_id, selected in period_by_sub.items():
        subscription = subscription_by_id.get(sub_id)
        lifetime_wh = sum(int(row.energy_wh) for row in all_by_sub.get(sub_id, []))
        selected_wh = sum(int(row.energy_wh) for row in selected)
        if subscription is None or lifetime_wh <= 0 or selected_wh <= 0:
            continue
        base_vnd = _rounded_ratio(subscription.monthly_fee_vnd * selected_wh, lifetime_wh)
        for key, group in _allocate_by_contract(db, selected, base_vnd).items():
            target = totals.setdefault(
                key,
                {**group, "energy_wh": 0, "base_revenue_vnd": 0, "shared_amount_vnd": 0},
            )
            for field in ("energy_wh", "base_revenue_vnd", "shared_amount_vnd"):
                target[field] += group[field]

    partners = (
        db.query(User)
        .join(Station, Station.owner_id == User.id)
        .distinct()
        .order_by(User.full_name, User.id)
        .all()
    )
    partner_by_id = {item.id: item for item in partners}
    old_owner_ids = {owner for owner, _ in totals} - set(partner_by_id)
    if old_owner_ids:
        partner_by_id.update(
            {item.id: item for item in db.query(User).filter(User.id.in_(old_owner_ids)).all()}
        )
    items = []
    for (owner_id, contract_id), total in sorted(
        totals.items(),
        key=lambda pair: (
            partner_by_id[pair[0][0]].full_name if pair[0][0] in partner_by_id else "",
            pair[0][0], pair[0][1] or 0,
        ),
    ):
        if station_owner_id is not None and owner_id != station_owner_id:
            continue
        partner = partner_by_id.get(owner_id)
        if partner is None:
            continue
        items.append(
            {
                "station_owner_id": owner_id,
                "partner_name": partner.full_name,
                "partner_email": partner.email,
                "contract_id": contract_id,
                "policy_label": f"Hợp đồng #{contract_id}" if contract_id else "Chưa có hợp đồng",
                "share_percent": float(total["partner_share_percent"]),
                "platform_share_percent": float(total["platform_share_percent"]),
                "effective_from": total["effective_from"].isoformat() + "Z" if total["effective_from"] else None,
                "effective_to": total["effective_to"].isoformat() + "Z" if total["effective_to"] else None,
                "energy_kwh": total["energy_wh"] / 1000,
                "base_revenue_vnd": total["base_revenue_vnd"],
                "shared_amount_vnd": total["shared_amount_vnd"],
            }
        )
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "partners": [
            {"id": item.id, "name": item.full_name, "email": item.email}
            for item in sorted(partner_by_id.values(), key=lambda value: (value.full_name, value.id))
        ],
        "items": items,
        "totals": {
            "base_revenue_vnd": sum(item["base_revenue_vnd"] for item in items),
            "shared_amount_vnd": sum(item["shared_amount_vnd"] for item in items),
        },
    }
