"""Yêu cầu tài xế bắt đầu phiên từ xa (S-24 / T-51)."""

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
from sqlalchemy.sql import func

from app.database import Base


class RemoteStartStatus(str, Enum):
    """Vòng đời yêu cầu RemoteStartTransaction."""

    SENDING = "sending"
    WAITING_START = "waiting_start"
    STARTED = "started"
    REJECTED = "rejected"
    NO_REPLY = "no_reply"
    CHARGER_ERROR = "charger_error"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class RemoteStartRequest(Base):
    """Yêu cầu gắn với một tài xế, đầu nối và thẻ ảo."""

    __tablename__ = "remote_start_requests"

    id = Column(Integer, primary_key=True)
    driver_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    connector_id = Column(Integer, ForeignKey("connectors.id", ondelete="RESTRICT"), nullable=False)
    id_tag_id = Column(Integer, ForeignKey("id_tags.id", ondelete="RESTRICT"), nullable=False)
    status = Column(
        SAEnum(
            RemoteStartStatus,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            native_enum=False,
            length=20,
            name="remote_start_status",
        ),
        nullable=False,
        default=RemoteStartStatus.SENDING,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    accepted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    session_id = Column(Integer, ForeignKey("charging_sessions.id", ondelete="SET NULL"), nullable=True)
    detail = Column(String(80), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('sending', 'waiting_start', 'started', 'rejected', "
            "'no_reply', 'charger_error', 'expired', 'superseded')",
            name="ck_remote_start_request_status",
        ),
        Index(
            "uq_remote_start_active_connector",
            "connector_id",
            unique=True,
            sqlite_where=text("status IN ('sending', 'waiting_start')"),
            postgresql_where=text("status IN ('sending', 'waiting_start')"),
        ),
        Index("ix_remote_start_driver_created", "driver_user_id", "created_at"),
        Index("ix_remote_start_connector_created", "connector_id", "created_at"),
    )

