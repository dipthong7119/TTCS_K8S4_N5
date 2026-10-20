"""Recalculate session prices from their effective tariff or subscription rate."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.driver_subscription import DriverSubscription
from app.models.meter_value import MeterValue
from app.models.station_tariff import StationTariff
from app.services.pricing import calculate_session_price

DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"


def station_timezone(tariffs: list[StationTariff], at: datetime) -> str:
    effective = [tariff for tariff in tariffs if tariff.effective_from <= at]
    timezone_name = effective[-1].timezone_name if effective else DEFAULT_TIMEZONE
    try:
        ZoneInfo(timezone_name)
        return timezone_name
    except (ZoneInfoNotFoundError, ValueError):
        return DEFAULT_TIMEZONE


def calculate_expected_session_amount(
    session: ChargingSession,
    invoice: ChargingInvoice | None,
    tariffs: list[StationTariff],
    subscriptions: list[DriverSubscription],
    readings: list[MeterValue],
) -> int | None:
    """Use the same pricing engine and historical inputs as session billing."""
    if session.ended_at is None or session.meter_stop_wh is None:
        return None
    tariff_versions = [item for item in tariffs if item.effective_from <= session.ended_at]
    base_tariff = next(
        (item for item in reversed(tariff_versions) if item.effective_from <= session.started_at),
        None,
    )
    subscription_id = invoice.subscription_id if invoice else None
    if subscription_id is not None:
        subscription = next((item for item in subscriptions if item.id == subscription_id), None)
    else:
        subscription = next(
            (
                item for item in reversed(subscriptions)
                if item.user_id == session.user_id
                and item.starts_at <= session.started_at < item.expires_at
            ),
            None,
        )
    if base_tariff is None and subscription is None:
        return None

    timezone_name = base_tariff.timezone_name if base_tariff else DEFAULT_TIMEZONE
    if subscription is not None:
        bands = [{
            "label": f"Gói {subscription.plan_name}",
            "start_minute": 0,
            "end_minute": 1440,
            "price_vnd_per_kwh": subscription.price_vnd_per_kwh,
        }]
        tariff_payload = None
        occupancy_fee = 0
        grace = 0
    else:
        assert base_tariff is not None
        bands = base_tariff.bands
        tariff_payload = [
            {
                "tariff_id": item.id,
                "name": item.name,
                "effective_from": item.effective_from,
                "bands": item.bands,
                "occupancy_fee_vnd_per_minute": item.occupancy_fee_vnd_per_minute,
                "grace_period_minutes": item.grace_period_minutes,
            }
            for item in tariff_versions
        ]
        occupancy_fee = base_tariff.occupancy_fee_vnd_per_minute
        grace = base_tariff.grace_period_minutes

    try:
        result = calculate_session_price(
            started_at=session.started_at,
            ended_at=session.ended_at,
            meter_start_wh=session.meter_start_wh,
            meter_stop_wh=session.meter_stop_wh,
            meter_readings=[
                {
                    "measurand": item.measurand,
                    "measured_at": item.measured_at,
                    "value": item.value,
                    "unit": item.unit,
                }
                for item in readings
            ],
            bands=bands,
            timezone_name=timezone_name,
            tariff_versions=tariff_payload,
            occupancy_started_at=session.occupancy_started_at,
            occupancy_fee_vnd_per_minute=occupancy_fee,
            grace_period_minutes=grace,
        )
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return None
    return int(result["total_vnd"])
