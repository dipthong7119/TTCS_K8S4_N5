"""Monthly driver subscriptions, wallet collection, and station revenue shares."""

from calendar import monthrange
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.driver_subscription import DriverSubscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.revenue_sharing import (
    allocate_station_owner_pool,
    create_revenue_share_contract,
    list_owner_revenue_share,
    list_revenue_share_contracts,
    list_revenue_share_report,
)
from app.services.wallet import wallet_totals

__all__ = [
    "allocate_station_owner_pool",
    "create_revenue_share_contract",
    "list_owner_revenue_share",
    "list_revenue_share_contracts",
    "list_revenue_share_report",
]


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
