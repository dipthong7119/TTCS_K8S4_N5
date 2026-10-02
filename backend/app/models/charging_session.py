"""Persisted OCPP charging transactions and their driver/station snapshots."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    false,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    # This ID is also the transactionId returned to the charge point.
    id = Column(Integer, primary_key=True)
    charge_point_id = Column(Integer, ForeignKey("charge_points.id", ondelete="SET NULL"), nullable=True)
    charge_point_code = Column(String(50), nullable=False)
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="SET NULL"), nullable=True)
    station_name = Column(String(255), nullable=False)
    connector_number = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    driver_name = Column(String(255), nullable=True)
    id_tag_id = Column(Integer, ForeignKey("id_tags.id", ondelete="SET NULL"), nullable=True)
    id_tag = Column(String(50), nullable=True)
    meter_start_wh = Column(Integer, nullable=False)
    meter_stop_wh = Column(Integer, nullable=True)
    energy_kwh = Column(Numeric(12, 3), nullable=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    remote_stop_requested_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="active", server_default="active")
    stop_reason = Column(String(50), nullable=True)
    anomaly_reason = Column(String(50), nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False, server_default=false())
    demo_key = Column(String(80), nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    invoice = relationship("ChargingInvoice", back_populates="session", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'anomaly', 'needs_review')",
            name="ck_charging_sessions_status",
        ),
        Index("ix_charging_sessions_user_started", "user_id", "started_at"),
        Index("ix_charging_sessions_cp_started", "charge_point_code", "started_at"),
        Index("ix_charging_sessions_status_started", "status", "started_at"),
        Index(
            "uq_active_session_per_connector",
            "charge_point_id",
            "connector_number",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
            postgresql_where=text("ended_at IS NULL"),
        ),
    )
