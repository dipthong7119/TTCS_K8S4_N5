"""Financial reconciliation for completed, non-demo charging sessions."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session, joinedload

from app.models.charge_point import ChargePoint
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.driver_subscription import DriverSubscription
from app.models.meter_value import MeterValue
from app.models.station import Station
from app.models.station_tariff import StationTariff
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.financial_reconciliation_pricing import (
    calculate_expected_session_amount,
    station_timezone,
)


def _report_summary(rows: list[dict]) -> dict:
    return {
        "total_kwh": round(sum(row["energy_kwh"] for row in rows), 3),
        "total_expected_vnd": sum(row["expected_vnd"] or 0 for row in rows),
        "total_invoiced_vnd": sum(row["invoiced_vnd"] or 0 for row in rows),
        "total_collected_vnd": sum(row["collected_vnd"] for row in rows),
        "total_difference_vnd": sum(abs(row["difference_vnd"] or 0) for row in rows),
        "total_invoice_difference_vnd": sum(
            abs(row["invoice_difference_vnd"] or 0) for row in rows
        ),
        "review_count": sum(bool(row["issues"]) for row in rows),
    }


def filter_financial_reconciliation_report(
    report: dict,
    status: str,
    charge_point_code: str | None = None,
) -> dict:
    """Filter a live report or a saved snapshot with the same summary rules."""
    rows = report["rows"]
    if status == "review":
        rows = [row for row in rows if row["issues"]]
    elif status != "all":
        rows = [row for row in rows if status in row["issues"]]
    if charge_point_code:
        rows = [row for row in rows if row["charge_point_code"] == charge_point_code]
    return {**report, "rows": rows, "summary": _report_summary(rows)}


def get_financial_reconciliation_report(
    db: Session,
    *,
    from_date: date,
    to_date: date,
    station_id: int | None = None,
    station_owner_id: int | None = None,
    charge_point_code: str | None = None,
    status: str = "all",
) -> dict:
    """Reconcile tariff amount, immutable invoice, and wallet debit by local end date."""
    if from_date > to_date:
        raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")

    # Include all UTC instants that can map to the requested local dates, then
    # apply each station's exact timezone in Python.
    utc_start = datetime.combine(from_date, time.min) - timedelta(hours=14)
    utc_end = datetime.combine(to_date + timedelta(days=1), time.min) + timedelta(hours=12)
    query = (
        db.query(ChargingSession, ChargingInvoice)
        .outerjoin(ChargingInvoice, ChargingInvoice.session_id == ChargingSession.id)
        .filter(
            ChargingSession.status == "completed",
            ChargingSession.ended_at.is_not(None),
            ChargingSession.ended_at >= utc_start,
            ChargingSession.ended_at < utc_end,
            ChargingSession.is_demo.is_(False),
        )
    )
    if station_owner_id is not None:
        query = query.join(Station, ChargingSession.station_id == Station.id).filter(
            Station.owner_id == station_owner_id
        )
    if station_id is not None:
        query = query.filter(ChargingSession.station_id == station_id)
    if charge_point_code:
        query = query.filter(ChargingSession.charge_point_code == charge_point_code)
    candidates = query.order_by(ChargingSession.ended_at, ChargingSession.id).all()

    station_ids = {session.station_id for session, _ in candidates if session.station_id}
    session_ids = {session.id for session, _ in candidates}
    user_ids = {session.user_id for session, _ in candidates if session.user_id}
    tariffs_by_station: dict[int, list[StationTariff]] = defaultdict(list)
    for tariff in (
        db.query(StationTariff)
        .options(joinedload(StationTariff.bands))
        .filter(StationTariff.station_id.in_(station_ids))
        .order_by(StationTariff.station_id, StationTariff.effective_from, StationTariff.id)
        .all()
        if station_ids else []
    ):
        tariffs_by_station[tariff.station_id].append(tariff)

    subscriptions = (
        db.query(DriverSubscription)
        .filter(DriverSubscription.user_id.in_(user_ids))
        .order_by(DriverSubscription.user_id, DriverSubscription.starts_at, DriverSubscription.id)
        .all()
        if user_ids else []
    )
    subscriptions_by_user: dict[int, list[DriverSubscription]] = defaultdict(list)
    subscriptions_by_id = {}
    for subscription in subscriptions:
        subscriptions_by_user[subscription.user_id].append(subscription)
        subscriptions_by_id[subscription.id] = subscription

    readings_by_session: dict[int, list[MeterValue]] = defaultdict(list)
    for reading in (
        db.query(MeterValue)
        .filter(MeterValue.session_id.in_(session_ids))
        .order_by(MeterValue.session_id, MeterValue.measured_at, MeterValue.id)
        .all()
        if session_ids else []
    ):
        readings_by_session[reading.session_id].append(reading)

    collected_by_session: dict[int, int] = defaultdict(int)
    ledger_count: dict[int, int] = defaultdict(int)
    for entry in (
        db.query(WalletLedgerEntry)
        .filter(
            WalletLedgerEntry.entry_type == "session_charge",
            WalletLedgerEntry.reference_type == "session",
            WalletLedgerEntry.reference_id.in_(session_ids),
        )
        .all()
        if session_ids else []
    ):
        collected_by_session[entry.reference_id] += -entry.amount_vnd
        ledger_count[entry.reference_id] += 1

    stations_query = db.query(Station)
    charge_points_query = db.query(ChargePoint)
    if station_owner_id is not None:
        stations_query = stations_query.filter(Station.owner_id == station_owner_id)
        charge_points_query = charge_points_query.join(
            Station, ChargePoint.station_id == Station.id
        ).filter(Station.owner_id == station_owner_id)
    stations = stations_query.order_by(Station.name, Station.id).all()
    station_by_id = {item.id: item for item in stations}
    rows = []
    for session, invoice in candidates:
        if session.station_id is None:
            continue
        station = station_by_id.get(session.station_id)
        if station is None:
            continue
        station_tariffs = tariffs_by_station[session.station_id]
        timezone_name = station_timezone(station_tariffs, session.started_at)
        try:
            local_end = session.ended_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(
                ZoneInfo(timezone_name)
            )
        except (ValueError, ZoneInfoNotFoundError):
            local_end = session.ended_at
        if not from_date <= local_end.date() <= to_date:
            continue

        relevant_subscriptions = subscriptions_by_user.get(session.user_id, [])
        if invoice and invoice.subscription_id:
            used_subscription = subscriptions_by_id.get(invoice.subscription_id)
            relevant_subscriptions = [used_subscription] if used_subscription else []
        expected = calculate_expected_session_amount(
            session,
            invoice,
            station_tariffs,
            relevant_subscriptions,
            readings_by_session[session.id],
        )
        collected = collected_by_session[session.id]
        energy = session.energy_kwh
        if energy is None and session.meter_stop_wh is not None:
            energy = Decimal(session.meter_stop_wh - session.meter_start_wh) / Decimal(1000)
        energy_kwh = float(energy or 0)
        invoice_amount = int(invoice.total_vnd) if invoice else None
        difference = expected - collected if expected is not None else None
        invoice_difference = (
            invoice_amount - expected
            if invoice_amount is not None and expected is not None
            else None
        )
        issues = []
        if expected is None:
            issues.append("missing_pricing")
        if energy_kwh > 0 and invoice is None:
            issues.append("missing_invoice")
        if invoice is not None and expected is not None and invoice_amount != expected:
            issues.append("amount_mismatch")
        if invoice_amount is not None and invoice_amount > 0 and ledger_count[session.id] == 0:
            issues.append("missing_ledger")
        if ledger_count[session.id] > 0 and invoice_amount != collected:
            issues.append("collection_mismatch")
        rows.append({
            "session_id": session.id,
            "date": local_end.date().isoformat(),
            "station_id": session.station_id,
            "station_name": station.name,
            "charge_point_code": session.charge_point_code,
            "energy_kwh": energy_kwh,
            "expected_vnd": expected,
            "invoiced_vnd": invoice_amount,
            "collected_vnd": collected,
            "difference_vnd": difference,
            "invoice_difference_vnd": invoice_difference,
            "issues": issues,
        })

    report = {
        "period": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "station_id": station_id,
        },
        "period_state": "open",
        "locked_at": None,
        "locked_by": None,
        "filters": {
            "stations": [{"id": item.id, "name": item.name} for item in stations],
            "charge_points": [
                {"code": item.code, "station_id": item.station_id}
                for item in charge_points_query.order_by(ChargePoint.code).all()
            ],
        },
        "rows": rows,
    }
    return filter_financial_reconciliation_report(report, status)
