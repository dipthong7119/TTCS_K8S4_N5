"""SCRUM-68: monthly subscriptions, package billing, and owner revenue share."""

from datetime import UTC, datetime

import pytest

from app.models.charging_session import ChargingSession
from app.models.driver_subscription import DriverSubscription
from app.models.station import Station
from app.models.subscription_plan import SubscriptionPlan
from app.models.subscription_usage import SubscriptionUsage
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.billing import finalize_session_billing
from app.services.subscriptions import (
    InsufficientSubscriptionBalance,
    SubscriptionConflict,
    add_one_calendar_month,
    allocate_station_owner_pool,
    list_owner_revenue_share,
    purchase_subscription,
)


def _utc_naive(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC).replace(tzinfo=None)


def _user(user_id: int, email: str) -> User:
    return User(
        id=user_id,
        email=email,
        password_hash="test-hash",
        full_name=f"User {user_id}",
        is_active=True,
    )


def test_purchase_charges_once_and_expires_after_one_calendar_month(db_session) -> None:
    driver = _user(1, "subscription-driver@example.test")
    plan = SubscriptionPlan(
        id=1,
        name="Monthly",
        monthly_fee_vnd=25_000,
        price_vnd_per_kwh=2_000,
        is_active=True,
    )
    db_session.add_all(
        [
            driver,
            plan,
            WalletLedgerEntry(
                user_id=driver.id,
                entry_type="demo_topup",
                amount_vnd=50_000,
                idempotency_key="subscription-test-topup",
                description="Test top-up",
            ),
        ]
    )
    db_session.commit()
    starts_at = _utc_naive(2026, 1, 31, 9)

    subscription = purchase_subscription(db_session, driver.id, plan.id, at=starts_at)
    assert subscription.expires_at == _utc_naive(2026, 2, 28, 9)
    charge = (
        db_session.query(WalletLedgerEntry)
        .filter_by(reference_type="driver_subscription", reference_id=subscription.id)
        .one()
    )
    assert charge.entry_type == "subscription_charge"
    assert charge.amount_vnd == -25_000

    with pytest.raises(SubscriptionConflict):
        purchase_subscription(db_session, driver.id, plan.id, at=starts_at)

    renewed = purchase_subscription(
        db_session, driver.id, plan.id, at=subscription.expires_at
    )
    assert renewed.starts_at == subscription.expires_at
    assert renewed.expires_at == _utc_naive(2026, 3, 28, 9)
    assert (
        db_session.query(WalletLedgerEntry)
        .filter_by(reference_type="driver_subscription")
        .count()
        == 2
    )


def test_purchase_rejects_insufficient_wallet_balance(db_session) -> None:
    driver = _user(1, "poor-driver@example.test")
    plan = SubscriptionPlan(
        id=1,
        name="Monthly",
        monthly_fee_vnd=25_000,
        price_vnd_per_kwh=2_000,
        is_active=True,
    )
    db_session.add_all([driver, plan])
    db_session.commit()

    with pytest.raises(InsufficientSubscriptionBalance):
        purchase_subscription(db_session, driver.id, plan.id, at=_utc_naive(2026, 10, 10))
    assert db_session.query(DriverSubscription).count() == 0


def test_package_billing_snapshots_plan_usage_and_owner_share(db_session) -> None:
    owner = _user(1, "subscription-owner@example.test")
    driver = _user(2, "package-driver@example.test")
    station = Station(id=1, name="Any station", owner_id=owner.id)
    plan = SubscriptionPlan(
        id=1,
        name="Frequent driver",
        monthly_fee_vnd=10_001,
        price_vnd_per_kwh=2_000,
        is_active=True,
    )
    starts_at = _utc_naive(2026, 9, 9, 10)
    subscription = DriverSubscription(
        id=1,
        user_id=driver.id,
        plan_id=plan.id,
        plan_name=plan.name,
        monthly_fee_vnd=plan.monthly_fee_vnd,
        price_vnd_per_kwh=plan.price_vnd_per_kwh,
        starts_at=starts_at,
        expires_at=_utc_naive(2026, 10, 9, 10),
    )
    # This session ends after expiry; the plan is chosen by its start time.
    session = ChargingSession(
        id=1,
        charge_point_code="CP-PACKAGE",
        station_id=station.id,
        station_name=station.name,
        connector_number=1,
        user_id=driver.id,
        meter_start_wh=0,
        meter_stop_wh=2_500,
        started_at=_utc_naive(2026, 10, 9, 9),
        ended_at=_utc_naive(2026, 10, 9, 11),
        status="completed",
    )
    db_session.add_all([owner, driver, station, plan, subscription, session])
    db_session.commit()

    invoice = finalize_session_billing(db_session, session, [])
    assert invoice is not None
    assert invoice.tariff_id is None
    assert invoice.subscription_id == subscription.id
    assert invoice.package_name == "Frequent driver"
    assert invoice.total_vnd == 5_000
    assert invoice.segments[0]["price_vnd_per_kwh"] == 2_000

    usage = db_session.query(SubscriptionUsage).filter_by(charging_session_id=session.id).one()
    assert usage.subscription_id == subscription.id
    assert usage.station_owner_id == owner.id
    assert usage.energy_wh == 2_500

    share = list_owner_revenue_share(db_session, owner.id)
    assert share["total_owner_share_vnd"] == 6_001
    assert share["items"][0]["platform_share_vnd"] == 4_000
    assert share["items"][0]["station_owner_pool_vnd"] == 6_001
    assert share["items"][0]["allocation_status"] == "finalized"


def test_owner_revenue_pool_uses_largest_remainder_without_losing_dong() -> None:
    assert allocate_station_owner_pool(6_001, {10: 1_000, 20: 1_000}) == {
        10: 3_001,
        20: 3_000,
    }
    assert add_one_calendar_month(_utc_naive(2024, 1, 31)) == _utc_naive(2024, 2, 29)
