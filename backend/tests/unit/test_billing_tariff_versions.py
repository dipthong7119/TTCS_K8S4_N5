"""SCRUM-67: future tariffs must not rewrite ended-session invoices."""

from datetime import UTC, datetime

from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.station_tariff import StationTariff, TariffBand
from app.models.user import User
from app.services.billing import finalize_session_billing


def _utc_naive(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC).replace(tzinfo=None)


def _tariff(station_id: int, effective_from: datetime, rate: int, name: str):
    return StationTariff(
        station_id=station_id,
        name=name,
        timezone_name="UTC",
        effective_from=effective_from,
        bands=[
            TariffBand(
                label="All day",
                start_minute=0,
                end_minute=1440,
                price_vnd_per_kwh=rate,
            )
        ],
    )


def _completed_session(
    *, session_id: int, station_id: int, started_at: datetime
) -> ChargingSession:
    return ChargingSession(
        id=session_id,
        charge_point_code="CP-TARIFF-VERSION",
        station_id=station_id,
        station_name="Versioned tariff station",
        connector_number=1,
        meter_start_wh=0,
        meter_stop_wh=1000,
        started_at=started_at,
        ended_at=started_at.replace(hour=started_at.hour + 1),
        status="completed",
    )


def test_future_tariff_only_applies_to_sessions_started_after_effective_time(
    db_session,
) -> None:
    owner = User(
        id=1,
        email="tariff-version-owner@example.test",
        password_hash="test-hash",
        full_name="Tariff Owner",
        is_active=True,
    )
    station = Station(id=1, name="Versioned tariff station", owner_id=owner.id)
    old_tariff = _tariff(1, _utc_naive(2026, 10, 1), 1000, "Old rate")
    future_tariff = _tariff(1, _utc_naive(2026, 10, 11), 2000, "Future rate")
    today_session = _completed_session(
        session_id=1,
        station_id=1,
        started_at=_utc_naive(2026, 10, 10, 8),
    )
    tomorrow_session = _completed_session(
        session_id=2,
        station_id=1,
        started_at=_utc_naive(2026, 10, 11, 8),
    )
    db_session.add_all([owner, station, old_tariff, future_tariff, today_session, tomorrow_session])
    db_session.commit()

    today_invoice = finalize_session_billing(db_session, today_session, [])
    assert today_invoice is not None
    assert today_invoice.tariff_id == old_tariff.id
    assert today_invoice.total_vnd == 1000

    # Adding a later version leaves the already saved invoice untouched.
    db_session.add(_tariff(1, _utc_naive(2026, 10, 12), 9000, "Later rate"))
    db_session.flush()
    assert finalize_session_billing(db_session, today_session, []) is today_invoice
    assert today_invoice.tariff_id == old_tariff.id
    assert today_invoice.total_vnd == 1000

    tomorrow_invoice = finalize_session_billing(db_session, tomorrow_session, [])
    assert tomorrow_invoice is not None
    assert tomorrow_invoice.tariff_id == future_tariff.id
    assert tomorrow_invoice.total_vnd == 2000
