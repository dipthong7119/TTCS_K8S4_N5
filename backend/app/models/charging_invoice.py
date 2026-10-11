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
        CheckConstraint(
            "tariff_id IS NOT NULL OR subscription_id IS NOT NULL",
            name="ck_charging_invoice_has_pricing_source",
        ),
        Index("ix_charging_invoices_tariff", "tariff_id"),
        Index("ix_charging_invoices_subscription", "subscription_id"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(
        Integer,
        ForeignKey("charging_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    tariff_id = Column(
        Integer, ForeignKey("station_tariffs.id", ondelete="RESTRICT"), nullable=True
    )
    subscription_id = Column(
        Integer,
        ForeignKey(
            "driver_subscriptions.id",
            ondelete="RESTRICT",
            name="fk_charging_invoices_subscription",
        ),
        nullable=True,
    )
    package_name = Column(String(120), nullable=True)
    total_vnd = Column(Integer, nullable=False)
    segments = Column(JSON, nullable=False, default=list)
    rounding_rule = Column(
        String(150),
        nullable=False,
        default="Làm tròn HALF_UP đến đồng trên từng khung giá; phí chiếm trụ tính mỗi phút bắt đầu.",
        server_default="Làm tròn HALF_UP đến đồng trên từng khung giá; phí chiếm trụ tính mỗi phút bắt đầu.",
    )
    calculation_version = Column(String(30), nullable=False, default="time-band-v1")
    is_demo = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    session = relationship("ChargingSession", back_populates="invoice")
    tariff = relationship("StationTariff")
