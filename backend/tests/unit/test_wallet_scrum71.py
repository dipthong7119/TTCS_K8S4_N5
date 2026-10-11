"""Unit tests for SCRUM-71 (S-37): Tự động trừ tiền ví khi phiên sạc kết thúc."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.station_tariff import StationTariff, TariffBand
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.ocpp.handlers.stop_transaction import handle_stop_transaction
from app.services.billing import finalize_session_billing
from app.services.wallet import (
    deduct_session_charge,
    has_minimum_balance,
    wallet_totals,
)


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """Tạo datetime chuẩn UTC stripped để tương thích SQLite datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC).replace(tzinfo=None)


@pytest.fixture()
def db():
    """Tạo database in-memory cho test SCRUM-71."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Tạo User Driver
    driver_role = Role(id=1, name="driver")
    driver = User(
        id=1,
        email="driver@test.com",
        password_hash="hashed_secret",
        full_name="Nguyễn Văn Tài Xế",
        is_active=True,
    )
    driver.roles = [driver_role]
    session.add_all([driver_role, driver])

    # Tạo Trạm sạc và Cổng sạc
    station = Station(
        id=1,
        name="Trạm Sạc Vincom Bà Triệu",
        address="191 Bà Triệu, Hà Nội",
        latitude=21.011,
        longitude=105.849,
        owner_id=1,
        status="active",
    )
    point = ChargePoint(
        id=1,
        code="CP-01",
        station_id=1,
        status="online",
    )
    connector = Connector(
        id=1,
        charge_point_id=1,
        connector_id=1,
        status="charging",
    )
    session.add_all([station, point, connector])

    # Biểu giá trạm: 3,000 VND/kWh
    now = _dt(2026, 10, 10, 8, 0)
    tariff = StationTariff(
        id=1,
        station_id=1,
        name="Biểu giá tiêu chuẩn",
        timezone_name="UTC",
        effective_from=now - timedelta(days=1),
        bands=[
            TariffBand(
                label="Cả ngày",
                start_minute=0,
                end_minute=1440,
                price_vnd_per_kwh=3000,
            )
        ],
    )
    session.add(tariff)
    session.commit()

    yield session
    session.close()


def _topup_wallet(db, user_id: int, amount_vnd: int) -> WalletLedgerEntry:
    """Nạp tiền giả định vào ví để phục vụ test."""
    entry = WalletLedgerEntry(
        user_id=user_id,
        entry_type="manual_topup",
        amount_vnd=amount_vnd,
        idempotency_key=f"topup-test-{user_id}-{datetime.now(UTC).timestamp()}",
        description="Nạp tiền ban đầu",
    )
    db.add(entry)
    db.commit()
    return entry


# ---------------------------------------------------------------------------
# AC1: Phiên kết thúc và hoá đơn đã lập -> ví bị trừ đúng tổng hoá đơn
# ---------------------------------------------------------------------------
def test_ac1_session_charge_deducted_and_referenced_in_ledger(db):
    """AC1: Ví bị trừ đúng tổng hoá đơn và sổ cái có dòng tham chiếu tới phiên."""
    _topup_wallet(db, user_id=1, amount_vnd=100_000)
    assert wallet_totals(db, 1)["balance_vnd"] == 100_000

    start_time = _dt(2026, 10, 10, 8, 0)
    end_time = _dt(2026, 10, 10, 9, 0)
    charging_session = ChargingSession(
        id=101,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        id_tag="TAG001",
        user_id=1,
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=0,
        meter_stop_wh=10_000,  # 10 kWh -> 10 * 3000 = 30,000 VND
        energy_kwh=Decimal("10.000"),
    )
    db.add(charging_session)
    db.commit()

    # Lập hoá đơn và trừ tiền
    invoice = finalize_session_billing(db, charging_session, meter_readings=[])
    db.commit()

    assert invoice is not None
    assert invoice.total_vnd == 30_000

    # Kiểm tra dòng sổ cái
    ledger_entry = (
        db.query(WalletLedgerEntry)
        .filter_by(
            user_id=1,
            entry_type="session_charge",
            reference_id=101,
        )
        .first()
    )
    assert ledger_entry is not None
    assert ledger_entry.amount_vnd == -30_000
    assert ledger_entry.idempotency_key == "session-charge:101"
    assert ledger_entry.receipt_code == "CHARGE-101"
    assert ledger_entry.reference_type == "session"
    assert "Trạm Sạc Vincom Bà Triệu" in ledger_entry.description

    # Kiểm tra số dư ví cuối: 100k - 30k = 70k
    totals = wallet_totals(db, 1)
    assert totals["balance_vnd"] == 70_000
    assert totals["total_spent_vnd"] == 30_000


# ---------------------------------------------------------------------------
# AC2: Hai phiên của cùng tài xế kết thúc cùng lúc
# ---------------------------------------------------------------------------
def test_ac2_two_sessions_same_driver_end_concurrently(db):
    """AC2: Hai phiên của cùng tài xế đều được trừ và số dư cuối bằng số dư đầu trừ tổng hai hoá đơn."""
    _topup_wallet(db, user_id=1, amount_vnd=200_000)
    assert wallet_totals(db, 1)["balance_vnd"] == 200_000

    start_time = _dt(2026, 10, 10, 8, 0)
    end_time = _dt(2026, 10, 10, 9, 0)

    # Phiên 1: 5 kWh * 3000 = 15,000 VND
    session_1 = ChargingSession(
        id=201,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=1,
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=0,
        meter_stop_wh=5_000,
        energy_kwh=Decimal("5.000"),
    )
    # Phiên 2: 8 kWh * 3000 = 24,000 VND
    session_2 = ChargingSession(
        id=202,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=1,
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=5_000,
        meter_stop_wh=13_000,
        energy_kwh=Decimal("8.000"),
    )
    db.add_all([session_1, session_2])
    db.commit()

    inv1 = finalize_session_billing(db, session_1, meter_readings=[])
    inv2 = finalize_session_billing(db, session_2, meter_readings=[])
    db.commit()

    assert inv1.total_vnd == 15_000
    assert inv2.total_vnd == 24_000

    # Cả hai đều có bản ghi sổ cái riêng biệt
    entries = (
        db.query(WalletLedgerEntry)
        .filter(
            WalletLedgerEntry.user_id == 1,
            WalletLedgerEntry.entry_type == "session_charge",
        )
        .order_by(WalletLedgerEntry.id)
        .all()
    )
    assert len(entries) == 2
    assert entries[0].idempotency_key == "session-charge:201"
    assert entries[0].amount_vnd == -15_000
    assert entries[1].idempotency_key == "session-charge:202"
    assert entries[1].amount_vnd == -24_000

    # Số dư cuối: 200,000 - (15,000 + 24,000) = 161,000 VND
    assert wallet_totals(db, 1)["balance_vnd"] == 161_000


# ---------------------------------------------------------------------------
# AC3: Ví không đủ tiền vẫn trừ để số dư âm (tài khoản nợ)
# ---------------------------------------------------------------------------
def test_ac3_overdraft_negative_balance_allowed(db):
    """AC3: Ví không đủ tiền vẫn trừ để số dư âm và đánh dấu nợ."""
    # Nạp 10,000 VND ban đầu
    _topup_wallet(db, user_id=1, amount_vnd=10_000)
    assert wallet_totals(db, 1)["balance_vnd"] == 10_000

    start_time = _dt(2026, 10, 10, 8, 0)
    end_time = _dt(2026, 10, 10, 9, 0)
    charging_session = ChargingSession(
        id=301,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=1,
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=0,
        meter_stop_wh=10_000,  # 10 kWh * 3000 = 30,000 VND (vượt quá 10k)
        energy_kwh=Decimal("10.000"),
    )
    db.add(charging_session)
    db.commit()

    # Vẫn trừ thành công, không văng exception
    invoice = finalize_session_billing(db, charging_session, meter_readings=[])
    db.commit()

    assert invoice is not None
    assert invoice.total_vnd == 30_000

    # Số dư trở thành âm: 10,000 - 30,000 = -20,000 VND
    totals = wallet_totals(db, 1)
    assert totals["balance_vnd"] == -20_000

    # Kiểm tra tài khoản bị đánh dấu không đủ ngưỡng tối thiểu (SCRUM-72)
    assert has_minimum_balance(db, user_id=1, min_amount_vnd=50_000) is False
    assert has_minimum_balance(db, user_id=1, min_amount_vnd=0) is False


# ---------------------------------------------------------------------------
# NFR: Idempotency - Một phiên không bao giờ bị trừ 2 lần
# ---------------------------------------------------------------------------
def test_nfr_idempotency_no_duplicate_charge(db):
    """NFR: Gọi tính tiền nhiều lần cho cùng 1 phiên không làm trừ tiền 2 lần."""
    _topup_wallet(db, user_id=1, amount_vnd=100_000)

    start_time = _dt(2026, 10, 10, 8, 0)
    end_time = _dt(2026, 10, 10, 9, 0)
    charging_session = ChargingSession(
        id=401,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=1,
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=0,
        meter_stop_wh=10_000,
        energy_kwh=Decimal("10.000"),
    )
    db.add(charging_session)
    db.commit()

    # Lần 1
    inv1 = finalize_session_billing(db, charging_session, meter_readings=[])
    db.commit()
    assert inv1.total_vnd == 30_000
    assert wallet_totals(db, 1)["balance_vnd"] == 70_000

    # Lần 2 (mô phỏng gọi lại)
    inv2 = finalize_session_billing(db, charging_session, meter_readings=[])
    db.commit()
    assert inv2.id == inv1.id

    # Số bản ghi ledger cho session 401 vẫn chỉ là 1
    count = (
        db.query(WalletLedgerEntry)
        .filter_by(
            user_id=1,
            idempotency_key="session-charge:401",
        )
        .count()
    )
    assert count == 1
    # Số dư vẫn là 70,000 VND
    assert wallet_totals(db, 1)["balance_vnd"] == 70_000


# ---------------------------------------------------------------------------
# NFR: Atomicity - Hóa đơn và trừ ví trong cùng 1 Transaction
# ---------------------------------------------------------------------------
def test_nfr_atomicity_rollback_preserves_consistency(db):
    """NFR: Nếu transaction rollback thì cả hóa đơn và trừ ví đều không được lưu."""
    _topup_wallet(db, user_id=1, amount_vnd=50_000)

    start_time = _dt(2026, 10, 10, 8, 0)
    end_time = _dt(2026, 10, 10, 9, 0)
    charging_session = ChargingSession(
        id=501,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=1,
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=0,
        meter_stop_wh=5_000,
        energy_kwh=Decimal("5.000"),
    )
    db.add(charging_session)
    db.commit()

    # Gọi finalize nhưng rollback thay vì commit
    finalize_session_billing(db, charging_session, meter_readings=[])
    db.rollback()

    # Cả invoice và ledger entry đều không được lưu
    assert db.query(ChargingInvoice).filter_by(session_id=501).first() is None
    assert (
        db.query(WalletLedgerEntry)
        .filter_by(idempotency_key="session-charge:501")
        .first()
        is None
    )
    assert wallet_totals(db, 1)["balance_vnd"] == 50_000


# ---------------------------------------------------------------------------
# Edge Cases: Phiên 0 đồng và phiên không có user_id
# ---------------------------------------------------------------------------
def test_edge_case_zero_amount_session_does_not_create_negative_ledger(db):
    """Edge case: Phiên tiêu thụ 0 kWh (0 VND) không tạo bản ghi trừ ví."""
    start_time = _dt(2026, 10, 10, 8, 0)
    end_time = _dt(2026, 10, 10, 8, 10)
    charging_session = ChargingSession(
        id=601,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=1,
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=1000,
        meter_stop_wh=1000,  # 0 Wh
        energy_kwh=Decimal("0.000"),
    )
    db.add(charging_session)
    db.commit()

    invoice = finalize_session_billing(db, charging_session, meter_readings=[])
    db.commit()

    assert invoice is not None
    assert invoice.total_vnd == 0
    # Không tạo dòng trừ ví
    assert (
        db.query(WalletLedgerEntry)
        .filter_by(idempotency_key="session-charge:601")
        .first()
        is None
    )


def test_edge_case_anonymous_session_without_user_id(db):
    """Edge case: Phiên vãng lai không có user_id vẫn lập hóa đơn nhưng không trừ ví."""
    start_time = _dt(2026, 10, 10, 8, 0)
    end_time = _dt(2026, 10, 10, 9, 0)
    charging_session = ChargingSession(
        id=701,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=None,  # Không có user
        status="completed",
        started_at=start_time,
        ended_at=end_time,
        meter_start_wh=0,
        meter_stop_wh=5_000,
        energy_kwh=Decimal("5.000"),
    )
    db.add(charging_session)
    db.commit()

    invoice = finalize_session_billing(db, charging_session, meter_readings=[])
    db.commit()

    assert invoice is not None
    assert invoice.total_vnd == 15_000
    assert (
        db.query(WalletLedgerEntry)
        .filter_by(idempotency_key="session-charge:701")
        .first()
        is None
    )


def test_validation_deduct_session_charge_rejects_non_positive_amount(db):
    """Hàm deduct_session_charge từ chối số tiền <= 0 đồng."""
    with pytest.raises(ValueError, match="lớn hơn 0"):
        deduct_session_charge(db, user_id=1, session_id=801, amount_vnd=0)

    with pytest.raises(ValueError, match="lớn hơn 0"):
        deduct_session_charge(db, user_id=1, session_id=802, amount_vnd=-5000)


# ---------------------------------------------------------------------------
# E2E StopTransaction OCPP handler integration
# ---------------------------------------------------------------------------
def test_e2e_stop_transaction_handler_deducts_wallet(db):
    """Tích hợp luồng StopTransaction OCPP: xử lý kết thúc phiên và tự động trừ ví."""
    _topup_wallet(db, user_id=1, amount_vnd=100_000)

    start_time = _dt(2026, 10, 10, 8, 0)
    session = ChargingSession(
        id=901,
        charge_point_id=1,
        charge_point_code="CP-01",
        station_id=1,
        station_name="Trạm Sạc Vincom Bà Triệu",
        connector_number=1,
        user_id=1,
        status="active",
        started_at=start_time,
        meter_start_wh=1000,
    )
    point = db.get(ChargePoint, 1)
    db.add(session)
    db.commit()

    # Gửi bản tin StopTransaction với meterStop=6000 (5 kWh -> 15,000 VND)
    payload = {
        "transactionId": 901,
        "meterStop": 6000,
        "timestamp": "2026-10-10T09:00:00Z",
        "reason": "EVDisconnected",
        "transactionData": [],
    }
    raw_response = handle_stop_transaction(db, point, "msg-scrum71-001", payload)
    db.commit()

    assert "Accepted" in raw_response

    # Kiểm tra session
    db.refresh(session)
    assert session.status == "completed"
    assert session.energy_kwh == Decimal("5.000")

    # Kiểm tra invoice
    invoice = db.query(ChargingInvoice).filter_by(session_id=901).one()
    assert invoice.total_vnd == 15_000

    # Kiểm tra ví bị trừ 15,000 VND
    ledger = (
        db.query(WalletLedgerEntry)
        .filter_by(
            user_id=1,
            reference_id=901,
            entry_type="session_charge",
        )
        .one()
    )
    assert ledger.amount_vnd == -15_000
    assert ledger.idempotency_key == "session-charge:901"
    assert wallet_totals(db, 1)["balance_vnd"] == 85_000
