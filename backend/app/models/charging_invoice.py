"""Immutable cost breakdown captured when a charging session ends."""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    false,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ChargingInvoice(Base):
    __tablename__ = "charging_invoices"
    __table_args__ = (
        CheckConstraint("total_vnd >= 0", name="ck_charging_invoice_total_nonnegative"),
        Index("ix_charging_invoices_tariff", "tariff_id"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(
        Integer,
        ForeignKey("charging_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    tariff_id = Column(
        Integer, ForeignKey("station_tariffs.id", ondelete="RESTRICT"), nullable=False
    )
    total_vnd = Column(Integer, nullable=False)
    segments = Column(JSON, nullable=False, default=list)
    calculation_version = Column(String(30), nullable=False, default="time-band-v1")
    is_demo = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    session = relationship("ChargingSession", back_populates="invoice")
    tariff = relationship("StationTariff")
