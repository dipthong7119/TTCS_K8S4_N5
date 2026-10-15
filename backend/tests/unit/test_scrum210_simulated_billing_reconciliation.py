"""SCRUM-210: reconcile a simulated OCPP charging session to hand billing."""

import json
from datetime import UTC, datetime

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.id_tag import IdTag
from app.models.meter_value import MeterValue
from app.models.station import Station
from app.models.station_tariff import StationTariff, TariffBand
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import parse_message


def _utc_naive(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC).replace(tzinfo=None)


def _simulator_call(message_id: str, action: str, payload: dict) -> str:
    return json.dumps([2, message_id, action, payload])


def test_simulated_ocpp_session_invoice_matches_manual_midnight_reconciliation(
    db_session,
):
    """4 kWh × 3,000 before midnight + 4 kWh × 6,000 after = 36,000 VND."""
    role = Role(name="driver")
    driver = User(
        id=1,
        email="scrum210-driver@example.test",
        password_hash="test-hash",
        full_name="Simulator Driver",
        is_active=True,
        roles=[role],
    )
    station = Station(
        id=1,
        name="Simulator tariff station",
        owner_id=driver.id,
        status="active",
    )
    point = ChargePoint(
        id=1,
        code="CP-SCRUM-210",
        station_id=station.id,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    connector = Connector(
        id=1,
        charge_point_id=point.id,
        connector_id=1,
        status="available",
        ocpp_status="Available",
    )
    tag = IdTag(id=1, id_tag="SIMULATOR-DRIVER", user_id=driver.id, is_blocked=False)
    old_tariff = StationTariff(
        id=1,
        station_id=station.id,
        name="October 9 tariff",
        timezone_name="Asia/Ho_Chi_Minh",
        effective_from=_utc_naive(2026, 10, 8, 17),
        bands=[
            TariffBand(
                label="Low",
                start_minute=0,
                end_minute=360,
                price_vnd_per_kwh=3_000,
            ),
            TariffBand(
                label="Other",
                start_minute=360,
                end_minute=1320,
                price_vnd_per_kwh=4_000,
            ),
            TariffBand(
                label="Low",
                start_minute=1320,
                end_minute=1440,
                price_vnd_per_kwh=3_000,
            ),
        ],
    )
    next_day_tariff = StationTariff(
        id=2,
        station_id=station.id,
        name="October 10 tariff",
        timezone_name="Asia/Ho_Chi_Minh",
        effective_from=_utc_naive(2026, 10, 9, 17),
        bands=[
            TariffBand(
                label="Next day",
                start_minute=0,
                end_minute=1440,
                price_vnd_per_kwh=6_000,
            )
        ],
    )
    opening_balance = WalletLedgerEntry(
        id=1,
        user_id=driver.id,
        entry_type="manual_topup",
        amount_vnd=50_000,
        idempotency_key="scrum210-opening-balance",
        description="Simulator test opening balance",
    )
    db_session.add_all(
        [
            driver,
            station,
            point,
            connector,
            tag,
            old_tariff,
            next_day_tariff,
            opening_balance,
        ]
    )
    db_session.commit()

    start_response = handle_ocpp_message(
        db_session,
        point.code,
        _simulator_call(
            "scrum210-start",
            "StartTransaction",
            {
                "connectorId": 1,
                "meterStart": 10_000,
                "idTag": tag.id_tag,
                "timestamp": "2026-10-09T23:00:00+07:00",
            },
        ),
    )
    transaction_id = parse_message(start_response)[3]["transactionId"]

    meter_response = handle_ocpp_message(
        db_session,
        point.code,
        _simulator_call(
            "scrum210-midnight-meter",
            "MeterValues",
            {
                "connectorId": 1,
                "transactionId": transaction_id,
                "meterValue": [
                    {
                        "timestamp": "2026-10-10T00:00:00+07:00",
                        "sampledValue": [
                            {
                                "value": "14000",
                                "measurand": "Energy.Active.Import.Register",
                                "unit": "Wh",
                            }
                        ],
                    }
                ],
            },
        ),
    )
    assert parse_message(meter_response)[0] == 3

    stop_response = handle_ocpp_message(
        db_session,
        point.code,
        _simulator_call(
            "scrum210-stop",
            "StopTransaction",
            {
                "transactionId": transaction_id,
                "meterStop": 18_000,
                "timestamp": "2026-10-10T01:00:00+07:00",
                "reason": "EVDisconnected",
            },
        ),
    )
    assert parse_message(stop_response)[0] == 3

    session = db_session.get(ChargingSession, transaction_id)
    invoice = db_session.query(ChargingInvoice).filter_by(session_id=transaction_id).one()
    readings = (
        db_session.query(MeterValue)
        .filter_by(session_id=transaction_id)
        .order_by(MeterValue.measured_at)
        .all()
    )
    charges = (
        db_session.query(WalletLedgerEntry)
        .filter_by(user_id=driver.id, entry_type="session_charge")
        .all()
    )

    assert session is not None and session.status == "completed"
    assert (session.meter_start_wh, session.meter_stop_wh) == (10_000, 18_000)
    assert len(readings) == 1 and readings[0].value == 14_000
    assert invoice.total_vnd == 36_000
    assert [
        (
            segment["service_date"],
            segment["energy_kwh"],
            segment["price_vnd_per_kwh"],
            segment["amount_vnd"],
            segment["tariff_id"],
        )
        for segment in invoice.segments
    ] == [
        ("2026-10-09", "4.000000", 3_000, 12_000, old_tariff.id),
        ("2026-10-10", "4.000000", 6_000, 24_000, next_day_tariff.id),
    ]
    assert len(charges) == 1 and charges[0].amount_vnd == -36_000
