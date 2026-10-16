"""Reservation persistence shared by the booking and no-show workflows."""

from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.sql import func

from app.database import Base


class ReservationStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "accepted"
    REJECTED = "rejected"
    FULFILLED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CancelStatus(str, Enum):
    NOT_NEEDED = "not_needed"
    PENDING = "pending"
    DONE = "done"
    GONE = "gone"
    ABANDONED = "abandoned"


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class Reservation(Base):
    """A charge-point reservation with shared booking and expiry state."""

    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    charge_point_id = Column(
        Integer,
        ForeignKey("charge_points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # OCPP connector number (not the connectors table primary key).
    connector_id = Column(Integer, nullable=False)
    # Internal connector PK used by expiry/cancellation OCPP workflows.
    connector_db_id = Column(
        Integer,
        ForeignKey("connectors.id", ondelete="RESTRICT"),
        nullable=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Keep both forms: ReserveNow uses the raw idTag; S-52 uses its DB row.
    id_tag = Column(String(50), nullable=False)
    id_tag_id = Column(
        Integer,
        ForeignKey("id_tags.id", ondelete="RESTRICT"),
        nullable=True,
    )
    start_time = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    status = Column(
        SAEnum(
            ReservationStatus,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=False,
            length=20,
            name="reservation_status",
        ),
        nullable=False,
        default=ReservationStatus.PENDING,
        server_default=ReservationStatus.PENDING.value,
    )
    reject_reason = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    fulfilled_session_id = Column(
        Integer,
        ForeignKey("charging_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    fulfilled_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    no_show_fee_vnd = Column(Integer, nullable=True)
    fee_ledger_entry_id = Column(Integer, nullable=True)
    fee_waived_reason = Column(String(200), nullable=True)
    cancel_status = Column(
        SAEnum(
            CancelStatus,
            values_callable=_enum_values,
            native_enum=False,
            create_constraint=False,
            length=20,
            name="reservation_cancel_status",
        ),
        nullable=False,
        default=CancelStatus.NOT_NEEDED,
        server_default=CancelStatus.NOT_NEEDED.value,
    )
    cancel_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_cancel_attempt_at = Column(DateTime, nullable=True)

    charge_point = relationship("ChargePoint")
    user = relationship("User")

    # Compatibility names used by the no-show workflow.
    driver_user_id = synonym("user_id")
    expiry_at = synonym("expiry_date")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'expired', 'cancelled', 'completed')",
            name="ck_reservation_status",
        ),
        CheckConstraint(
            "cancel_status IN ('not_needed', 'pending', 'done', 'gone', 'abandoned')",
            name="ck_reservation_cancel_status",
        ),
        CheckConstraint(
            "no_show_fee_vnd IS NULL OR no_show_fee_vnd >= 0",
            name="ck_reservation_fee_nonneg",
        ),
        CheckConstraint(
            "cancel_attempts >= 0",
            name="ck_reservation_cancel_attempts",
        ),
        Index(
            "ix_reservations_cp_conn_status",
            "charge_point_id",
            "connector_id",
            "status",
        ),
        Index(
            "uq_reservations_active_connector",
            "charge_point_id",
            "connector_id",
            unique=True,
            sqlite_where=text("status IN ('accepted', 'pending')"),
            postgresql_where=text("status IN ('accepted', 'pending')"),
        ),
        Index("ix_reservations_status_expiry", "status", "expiry_date"),
        Index("ix_reservations_connector_status", "connector_db_id", "status"),
        Index("ix_reservations_driver_status", "user_id", "status"),
    )
