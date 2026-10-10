"""Create an immutable tariff snapshot and wallet debit for a completed session."""

import logging

from sqlalchemy.orm import Session

from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.driver_subscription import DriverSubscription
from app.models.station import Station
from app.models.station_tariff import StationTariff
from app.models.subscription_usage import SubscriptionUsage
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.pricing import CALCULATION_VERSION, calculate_session_price

logger = logging.getLogger(__name__)


def finalize_session_billing(
    db: Session, session: ChargingSession, meter_readings: list[dict]
) -> ChargingInvoice | None:
    """Snapshot the effective tariff and charge once inside the OCPP transaction."""
    existing = (
        db.query(ChargingInvoice).filter(ChargingInvoice.session_id == session.id).first()
    )
    if existing is not None:
        return existing
    if (
        session.status != "completed"
        or session.ended_at is None
        or session.meter_stop_wh is None
        or session.station_id is None
    ):
        return None

    tariff = (
        db.query(StationTariff)
        .filter(
            StationTariff.station_id == session.station_id,
            StationTariff.effective_from <= session.started_at,
        )
        .order_by(StationTariff.effective_from.desc(), StationTariff.id.desc())
        .first()
    )
    subscription = None
    if session.user_id is not None:
        subscription = (
            db.query(DriverSubscription)
            .filter(
                DriverSubscription.user_id == session.user_id,
                DriverSubscription.starts_at <= session.started_at,
                DriverSubscription.expires_at > session.started_at,
            )
            .order_by(DriverSubscription.starts_at.desc(), DriverSubscription.id.desc())
            .first()
        )
    if tariff is None and subscription is None:
        return None

    timezone_name = tariff.timezone_name if tariff is not None else "Asia/Ho_Chi_Minh"
    if subscription is not None:
        bands = [
            {
                "label": f"Gói {subscription.plan_name}",
                "start_minute": 0,
                "end_minute": 1440,
                "price_vnd_per_kwh": subscription.price_vnd_per_kwh,
            }
        ]
    else:
        assert tariff is not None
        bands = tariff.bands

    try:
        breakdown = calculate_session_price(
            started_at=session.started_at,
            ended_at=session.ended_at,
            meter_start_wh=session.meter_start_wh,
            meter_stop_wh=session.meter_stop_wh,
            meter_readings=meter_readings,
            bands=bands,
            timezone_name=timezone_name,
            occupancy_started_at=session.occupancy_started_at,
            occupancy_fee_vnd_per_minute=(tariff.occupancy_fee_vnd_per_minute if tariff else 0),
            grace_period_minutes=tariff.grace_period_minutes if tariff else 0,
        )
    except ValueError:
        # Do not turn a completed OCPP transaction into a failed transaction if
        # billing inputs are incomplete. It remains visible without an invoice.
        logger.warning("Could not calculate billing for session %s", session.id)
        return None

    invoice = ChargingInvoice(
        session_id=session.id,
        tariff_id=tariff.id if tariff else None,
        subscription_id=subscription.id if subscription else None,
        package_name=subscription.plan_name if subscription else None,
        total_vnd=breakdown["total_vnd"],
        segments=breakdown["segments"],
        rounding_rule=breakdown["rounding_rule"],
        calculation_version=("subscription-v1" if subscription else CALCULATION_VERSION),
        is_demo=tariff.is_demo if tariff else session.is_demo,
    )
    db.add(invoice)
    db.flush()

    if subscription is not None:
        station_owner_id = (
            db.query(Station.owner_id).filter(Station.id == session.station_id).scalar()
        )
        if station_owner_id is not None:
            db.add(
                SubscriptionUsage(
                    subscription_id=subscription.id,
                    charging_session_id=session.id,
                    station_id=session.station_id,
                    station_owner_id=station_owner_id,
                    energy_wh=max(session.meter_stop_wh - session.meter_start_wh, 0),
                    created_at=session.ended_at,
                )
            )
            db.flush()

    if session.user_id and invoice.total_vnd > 0:
        idempotency_key = f"session-charge:{session.id}"
        exists = (
            db.query(WalletLedgerEntry.id)
            .filter(WalletLedgerEntry.idempotency_key == idempotency_key)
            .first()
        )
        if exists is None:
            db.add(
                WalletLedgerEntry(
                    user_id=session.user_id,
                    entry_type="session_charge",
                    amount_vnd=-invoice.total_vnd,
                    idempotency_key=idempotency_key,
                    reference_type="session",
                    reference_id=session.id,
                    description=f"Thanh toán phiên sạc tại {session.station_name}",
                    created_at=session.ended_at,
                )
            )
    return invoice
