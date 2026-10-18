"""Monthly driver subscriptions, wallet collection, and station revenue shares."""

from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.driver_subscription import DriverSubscription
from app.models.station import Station
from app.models.subscription_plan import SubscriptionPlan
from app.models.subscription_usage import SubscriptionUsage
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.wallet import wallet_totals

PLATFORM_SHARE_PERCENT = 40
STATION_OWNER_SHARE_PERCENT = 60


class SubscriptionConflict(ValueError):
    """The requested subscription cannot be purchased in the current state."""


class InsufficientSubscriptionBalance(ValueError):
    """The driver's wallet cannot cover the monthly subscription fee."""


def utc_now_naive() -> datetime:
    """Return the UTC-naive timestamp convention used by this project's models."""
    return datetime.now(UTC).replace(tzinfo=None)


def add_one_calendar_month(value: datetime) -> datetime:
    """Advance one calendar month, clamping dates such as January 31 to month end."""
    month_index = value.month
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def list_active_plans(db: Session) -> list[SubscriptionPlan]:
    return (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.monthly_fee_vnd, SubscriptionPlan.id)
        .all()
    )


def get_current_subscription(
    db: Session, user_id: int, *, at: datetime | None = None
) -> DriverSubscription | None:
    now = at or utc_now_naive()
    return (
        db.query(DriverSubscription)
        .filter(
            DriverSubscription.user_id == user_id,
            DriverSubscription.starts_at <= now,
            DriverSubscription.expires_at > now,
        )
        .order_by(DriverSubscription.starts_at.desc(), DriverSubscription.id.desc())
        .first()
    )


def list_user_subscriptions(db: Session, user_id: int) -> list[DriverSubscription]:
    return (
        db.query(DriverSubscription)
        .filter(DriverSubscription.user_id == user_id)
        .order_by(DriverSubscription.starts_at.desc(), DriverSubscription.id.desc())
        .all()
    )


def purchase_subscription(
    db: Session,
    user_id: int,
    plan_id: int,
    *,
    at: datetime | None = None,
) -> DriverSubscription:
    """Charge the monthly fee once and snapshot the plan and expiry on purchase."""
    # Locking the driver row serializes concurrent attempts to buy overlapping plans
    # on PostgreSQL; the unique ledger key remains the final idempotency guard.
    driver = db.query(User).filter(User.id == user_id).with_for_update().first()
    if driver is None or not driver.is_active:
        raise SubscriptionConflict("Tài khoản tài xế không còn hoạt động")

    now = at or utc_now_naive()
    current = get_current_subscription(db, user_id, at=now)
    if current is not None:
        raise SubscriptionConflict("Gói hiện tại còn hạn; vui lòng đăng ký lại sau khi hết hạn")

    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.id == plan_id, SubscriptionPlan.is_active.is_(True))
        .first()
    )
    if plan is None:
        raise SubscriptionConflict("Gói thuê bao không tồn tại hoặc đã ngừng bán")

    balance = wallet_totals(db, user_id)["balance_vnd"]
    if balance < plan.monthly_fee_vnd:
        raise InsufficientSubscriptionBalance(
            f"Ví không đủ số dư; cần {plan.monthly_fee_vnd} đồng"
        )

    subscription = DriverSubscription(
        user_id=user_id,
        plan_id=plan.id,
        plan_name=plan.name,
        monthly_fee_vnd=plan.monthly_fee_vnd,
        price_vnd_per_kwh=plan.price_vnd_per_kwh,
        starts_at=now,
        expires_at=add_one_calendar_month(now),
    )
    db.add(subscription)
    db.flush()

    db.add(
        WalletLedgerEntry(
            user_id=user_id,
            entry_type="subscription_charge",
            amount_vnd=-plan.monthly_fee_vnd,
            idempotency_key=f"subscription-charge:{subscription.id}",
            reference_type="driver_subscription",
            reference_id=subscription.id,
            description=f"Phí gói tháng {subscription.plan_name}",
            created_at=now,
        )
    )
    db.flush()
    return subscription


def allocate_station_owner_pool(
    station_pool_vnd: int, energy_wh_by_owner: dict[int, int]
) -> dict[int, int]:
    """Split VND proportionally by Wh with largest-remainder rounding."""
    weights = {owner_id: weight for owner_id, weight in energy_wh_by_owner.items() if weight > 0}
    total_energy_wh = sum(weights.values())
    if station_pool_vnd <= 0 or total_energy_wh <= 0:
        return {owner_id: 0 for owner_id in energy_wh_by_owner}

    amounts = {
        owner_id: station_pool_vnd * weight // total_energy_wh
        for owner_id, weight in weights.items()
    }
    remainders = {
        owner_id: station_pool_vnd * weight % total_energy_wh
        for owner_id, weight in weights.items()
    }
    remaining = station_pool_vnd - sum(amounts.values())
    for owner_id in sorted(weights, key=lambda key: (-remainders[key], key))[:remaining]:
        amounts[owner_id] += 1
    return {owner_id: amounts.get(owner_id, 0) for owner_id in energy_wh_by_owner}


def _station_owner_pool(monthly_fee_vnd: int) -> int:
    """Round the 60% owner pool HALF_UP to a dong; platform receives the remainder."""
    return (monthly_fee_vnd * STATION_OWNER_SHARE_PERCENT + 50) // 100


def list_owner_revenue_share(db: Session, owner_id: int) -> dict:
    """Calculate this owner's 60% package share from immutable package usage."""
    subscriptions = (
        db.query(DriverSubscription)
        .join(SubscriptionUsage, SubscriptionUsage.subscription_id == DriverSubscription.id)
        .filter(SubscriptionUsage.station_owner_id == owner_id)
        .distinct()
        .order_by(DriverSubscription.expires_at.desc(), DriverSubscription.id.desc())
        .all()
    )
    if not subscriptions:
        return {"items": [], "total_owner_share_vnd": 0}

    subscription_ids = [item.id for item in subscriptions]
    grouped_usage = (
        db.query(
            SubscriptionUsage.subscription_id,
            SubscriptionUsage.station_owner_id,
            func.sum(SubscriptionUsage.energy_wh).label("energy_wh"),
        )
        .filter(SubscriptionUsage.subscription_id.in_(subscription_ids))
        .group_by(SubscriptionUsage.subscription_id, SubscriptionUsage.station_owner_id)
        .all()
    )
    usage_by_subscription: dict[int, dict[int, int]] = {}
    for row in grouped_usage:
        usage_by_subscription.setdefault(row.subscription_id, {})[row.station_owner_id] = int(
            row.energy_wh or 0
        )

    now = utc_now_naive()
    items = []
    total_owner_share = 0
    for subscription in subscriptions:
        usage_by_owner = usage_by_subscription[subscription.id]
        pool_vnd = _station_owner_pool(subscription.monthly_fee_vnd)
        allocations = allocate_station_owner_pool(pool_vnd, usage_by_owner)
        owner_share_vnd = allocations.get(owner_id, 0)
        total_wh = sum(usage_by_owner.values())
        if owner_share_vnd == 0 and usage_by_owner.get(owner_id, 0) == 0:
            continue
        total_owner_share += owner_share_vnd
        items.append(
            {
                "subscription_id": subscription.id,
                "plan_name": subscription.plan_name,
                "starts_at": subscription.starts_at.isoformat() + "Z",
                "expires_at": subscription.expires_at.isoformat() + "Z",
                "allocation_status": "accruing" if subscription.expires_at > now else "finalized",
                "monthly_fee_vnd": subscription.monthly_fee_vnd,
                "platform_share_vnd": subscription.monthly_fee_vnd - pool_vnd,
                "station_owner_pool_vnd": pool_vnd,
                "owner_energy_wh": usage_by_owner.get(owner_id, 0),
                "package_energy_wh": total_wh,
                "owner_share_vnd": owner_share_vnd,
            }
        )
    return {"items": items, "total_owner_share_vnd": total_owner_share}


def list_revenue_share_report(
    db: Session,
    date_from: date,
    date_to: date,
    *,
    station_owner_id: int | None = None,
) -> dict:
    """Summarize the existing 60% subscription fee pool by owner and usage period."""
    station_zone = ZoneInfo(settings.STATION_TIMEZONE)
    start_at = (
        datetime.combine(date_from, time.min, tzinfo=station_zone)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    end_at = (
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=station_zone)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )

    partners = (
        db.query(User)
        .outerjoin(Station, Station.owner_id == User.id)
        .outerjoin(SubscriptionUsage, SubscriptionUsage.station_owner_id == User.id)
        .filter(or_(Station.id.is_not(None), SubscriptionUsage.id.is_not(None)))
        .distinct()
        .order_by(User.full_name, User.id)
        .all()
    )
    partner_by_id = {partner.id: partner for partner in partners}

    period_rows = (
        db.query(
            SubscriptionUsage.subscription_id,
            SubscriptionUsage.station_owner_id,
            func.sum(SubscriptionUsage.energy_wh).label("energy_wh"),
        )
        .filter(
            SubscriptionUsage.created_at >= start_at,
            SubscriptionUsage.created_at < end_at,
        )
        .group_by(SubscriptionUsage.subscription_id, SubscriptionUsage.station_owner_id)
        .all()
    )
    period_by_subscription: dict[int, dict[int, int]] = {}
    for row in period_rows:
        period_by_subscription.setdefault(row.subscription_id, {})[row.station_owner_id] = int(
            row.energy_wh or 0
        )

    subscription_ids = list(period_by_subscription)
    if subscription_ids:
        subscriptions = (
            db.query(DriverSubscription)
            .filter(DriverSubscription.id.in_(subscription_ids))
            .all()
        )
        all_rows = (
            db.query(
                SubscriptionUsage.subscription_id,
                SubscriptionUsage.station_owner_id,
                func.sum(SubscriptionUsage.energy_wh).label("energy_wh"),
            )
            .filter(SubscriptionUsage.subscription_id.in_(subscription_ids))
            .group_by(SubscriptionUsage.subscription_id, SubscriptionUsage.station_owner_id)
            .all()
        )
    else:
        subscriptions = []
        all_rows = []

    all_by_subscription: dict[int, dict[int, int]] = {}
    for row in all_rows:
        all_by_subscription.setdefault(row.subscription_id, {})[row.station_owner_id] = int(
            row.energy_wh or 0
        )

    totals: dict[int, dict[str, int]] = {}
    for subscription in subscriptions:
        full_weights = all_by_subscription.get(subscription.id, {})
        period_weights = period_by_subscription.get(subscription.id, {})
        full_wh = sum(full_weights.values())
        period_wh = sum(period_weights.values())
        if full_wh <= 0 or period_wh <= 0:
            continue

        # Prorate the fee pool by this interval's kWh, then split across owners.
        base_vnd = (subscription.monthly_fee_vnd * period_wh + full_wh // 2) // full_wh
        owner_pool = _station_owner_pool(subscription.monthly_fee_vnd)
        shared_vnd = (owner_pool * period_wh + full_wh // 2) // full_wh
        base_by_owner = allocate_station_owner_pool(base_vnd, period_weights)
        shared_by_owner = allocate_station_owner_pool(shared_vnd, period_weights)

        for owner_id, energy_wh in period_weights.items():
            owner_total = totals.setdefault(
                owner_id,
                {"energy_wh": 0, "base_revenue_vnd": 0, "shared_amount_vnd": 0},
            )
            owner_total["energy_wh"] += energy_wh
            owner_total["base_revenue_vnd"] += base_by_owner.get(owner_id, 0)
            owner_total["shared_amount_vnd"] += shared_by_owner.get(owner_id, 0)

    items = []
    for owner_id in sorted(
        totals,
        key=lambda key: (
            partner_by_id[key].full_name if key in partner_by_id else "",
            key,
        ),
    ):
        if station_owner_id is not None and owner_id != station_owner_id:
            continue
        partner = partner_by_id.get(owner_id)
        if partner is None:
            continue
        total = totals[owner_id]
        items.append(
            {
                "station_owner_id": owner_id,
                "partner_name": partner.full_name,
                "partner_email": partner.email,
                "policy_label": "Quy tắc mặc định 60%",
                "share_percent": STATION_OWNER_SHARE_PERCENT,
                "energy_kwh": total["energy_wh"] / 1000,
                "base_revenue_vnd": total["base_revenue_vnd"],
                "shared_amount_vnd": total["shared_amount_vnd"],
            }
        )

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "partners": [
            {"id": partner.id, "name": partner.full_name, "email": partner.email}
            for partner in partners
        ],
        "items": items,
        "totals": {
            "base_revenue_vnd": sum(item["base_revenue_vnd"] for item in items),
            "shared_amount_vnd": sum(item["shared_amount_vnd"] for item in items),
        },
    }


def create_plan(db: Session, values: dict) -> SubscriptionPlan:
    plan = SubscriptionPlan(**values)
    db.add(plan)
    db.flush()
    return plan


def update_plan(db: Session, plan: SubscriptionPlan, values: dict) -> SubscriptionPlan:
    for key, value in values.items():
        setattr(plan, key, value)
    db.flush()
    return plan
