"""Create an immutable tariff snapshot and wallet debit for a completed session."""

import logging

from sqlalchemy.orm import Session

from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.station_tariff import StationTariff
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.pricing import CALCULATION_VERSION, calculate_session_price

logger = logging.getLogger(__name__)


def finalize_session_billing(
    db: Session, session: ChargingSession, meter_readings: list[dict]
) -> ChargingInvoice | None:
    """Snapshot the effective tariff and charge once inside the OCPP transaction."""
    existing = (
        db.query(ChargingInvoice)
        .filter(ChargingInvoice.session_id == session.id)
        .first()
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
    if tariff is None:
        return None

    try:
        breakdown = calculate_session_price(
            started_at=session.started_at,
            ended_at=session.ended_at,
            meter_start_wh=session.meter_start_wh,
            meter_stop_wh=session.meter_stop_wh,
            meter_readings=meter_readings,
            bands=tariff.bands,
            timezone_name=tariff.timezone_name,
        )
    except ValueError:
        # Do not turn a completed OCPP transaction into a failed transaction if
        # billing inputs are incomplete. It remains visible without an invoice.
        logger.warning("Could not calculate billing for session %s", session.id)
        return None

    invoice = ChargingInvoice(
        session_id=session.id,
        tariff_id=tariff.id,
        total_vnd=breakdown["total_vnd"],
        segments=breakdown["segments"],
        calculation_version=CALCULATION_VERSION,
        is_demo=tariff.is_demo,
    )
    db.add(invoice)
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
