"""Model đặt chỗ tối thiểu (S-48/S-49 sẽ thêm logic tạo/huỷ theo tài xế).

Chỉ cung cấp bảng reservations phục vụ job xử lý quá hạn (S-52).
Chú ý:
- reservationId gửi cho trụ chính là cột id (INTEGER PRIMARY KEY).
- cancel_status theo dõi vòng đời CancelReservation độc lập với status.
- Ràng buộc chống 2 chỗ active trên cùng đầu nối sẽ thêm ở S-49.
"""

from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func

from app.database import Base


class ReservationStatus(str, Enum):
    """Vòng đời đặt chỗ."""

    ACTIVE = "active"          # Trụ đã Accepted và đang giữ chỗ
    FULFILLED = "fulfilled"    # Tài xế đã bắt đầu phiên
    EXPIRED = "expired"        # Quá hạn, job đã xử lý
    CANCELLED = "cancelled"    # Tài xế huỷ (S-51, chưa cài)


class CancelStatus(str, Enum):
    """Vòng đời lệnh CancelReservation gửi xuống trụ."""

    NOT_NEEDED = "not_needed"  # Không cần huỷ (đã fulfilled)
    PENDING = "pending"        # Chờ gửi hoặc đang thử lại
    DONE = "done"              # Trụ trả Accepted
    GONE = "gone"              # Trụ trả Rejected (đã tự nhả) — coi như xong
    ABANDONED = "abandoned"    # Hết số lần thử hoặc hết CANCEL_RESERVATION_RETRY_WINDOW


def _status_enum(name: str) -> SAEnum:
    return SAEnum(
        ReservationStatus,
        values_callable=lambda e: [v.value for v in e],
        native_enum=False,
        length=20,
        name=name,
    )


def _cancel_enum(name: str) -> SAEnum:
    return SAEnum(
        CancelStatus,
        values_callable=lambda e: [v.value for v in e],
        native_enum=False,
        length=20,
        name=name,
    )


class Reservation(Base):
    """Bảng đặt chỗ tối thiểu phục vụ job no-show (S-52)."""

    __tablename__ = "reservations"

    # reservationId trong OCPP ReserveNow — trụ dùng số nguyên này
    id = Column(Integer, primary_key=True, autoincrement=True)

    driver_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    connector_id = Column(
        Integer, ForeignKey("connectors.id", ondelete="RESTRICT"), nullable=False
    )
    id_tag_id = Column(
        Integer, ForeignKey("id_tags.id", ondelete="RESTRICT"), nullable=False
    )

    status = Column(
        _status_enum("reservation_status"),
        nullable=False,
        default=ReservationStatus.ACTIVE,
    )

    # Thời điểm hết hạn giữ chỗ (UTC naive), chính là expiryDate gửi cho trụ
    expiry_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # ── fulfilled ──────────────────────────────────────────────────────────
    fulfilled_session_id = Column(
        Integer,
        ForeignKey("charging_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    fulfilled_at = Column(DateTime, nullable=True)

    # ── expired ────────────────────────────────────────────────────────────
    expired_at = Column(DateTime, nullable=True)

    # ── cancelled ──────────────────────────────────────────────────────────
    cancelled_at = Column(DateTime, nullable=True)

    # ── phí không đến ──────────────────────────────────────────────────────
    # Mức phí chốt lúc đặt (đồng VNĐ). NULL → dùng mức hiện tại của trạm khi tính phí.
    no_show_fee_vnd = Column(Integer, nullable=True)
    # id dòng sổ cái đã ghi (tránh tra lại khi hiển thị)
    fee_ledger_entry_id = Column(Integer, nullable=True)
    # Lý do miễn phí (AC8: lần đầu); NULL = không miễn
    fee_waived_reason = Column(String(200), nullable=True)

    # ── trạng thái gửi CancelReservation ──────────────────────────────────
    cancel_status = Column(
        _cancel_enum("reservation_cancel_status"),
        nullable=False,
        default=CancelStatus.PENDING,
    )
    cancel_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_cancel_attempt_at = Column(DateTime, nullable=True)

    __table_args__ = (
        # Chỉ mục chính cho job quét: (status, expiry_at)
        Index("ix_reservations_status_expiry", "status", "expiry_at"),
        # Tìm nhanh đặt chỗ đang giữ trên một đầu nối
        Index("ix_reservations_connector_status", "connector_id", "status"),
        # Lịch sử theo tài xế
        Index("ix_reservations_driver_status", "driver_user_id", "status"),
        # Bảo đảm phí hợp lệ: >= 0 hoặc NULL
        CheckConstraint(
            "no_show_fee_vnd IS NULL OR no_show_fee_vnd >= 0",
            name="ck_reservation_fee_nonneg",
        ),
        # cancel_attempts không âm
        CheckConstraint(
            "cancel_attempts >= 0",
            name="ck_reservation_cancel_attempts",
        ),
    )
