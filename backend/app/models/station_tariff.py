"""Versioned station tariff plans and their daily time bands."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StationTariff(Base):
    __tablename__ = "station_tariffs"

    id = Column(Integer, primary_key=True)
    station_id = Column(
        Integer, ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False
    )
    name = Column(String(120), nullable=False)
    timezone_name = Column(String(80), nullable=False, default="Asia/Ho_Chi_Minh")
    effective_from = Column(DateTime, nullable=False)
    is_demo = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    bands = relationship(
        "TariffBand",
        back_populates="tariff",
        order_by="TariffBand.start_minute",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "station_id", "effective_from", name="uq_station_tariff_effective"
        ),
        Index("ix_station_tariffs_station_effective", "station_id", "effective_from"),
    )


class TariffBand(Base):
    __tablename__ = "tariff_bands"

    id = Column(Integer, primary_key=True)
    tariff_id = Column(
        Integer, ForeignKey("station_tariffs.id", ondelete="RESTRICT"), nullable=False
    )
    label = Column(String(80), nullable=False)
    start_minute = Column(Integer, nullable=False)
    end_minute = Column(Integer, nullable=False)
    price_vnd_per_kwh = Column(Integer, nullable=False)

    tariff = relationship("StationTariff", back_populates="bands")

    __table_args__ = (
        CheckConstraint(
            "start_minute >= 0 AND start_minute < 1440 AND "
            "end_minute > start_minute AND end_minute <= 1440",
            name="ck_tariff_band_minutes",
        ),
        CheckConstraint(
            "price_vnd_per_kwh >= 0", name="ck_tariff_band_price_nonnegative"
        ),
        UniqueConstraint("tariff_id", "start_minute", name="uq_tariff_band_start"),
        Index(
            "ix_tariff_bands_tariff_minutes", "tariff_id", "start_minute", "end_minute"
        ),
    )
