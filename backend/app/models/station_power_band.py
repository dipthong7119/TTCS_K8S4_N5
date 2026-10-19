"""Daily station power-limit bands (SCRUM-83)."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)

from app.database import Base


class StationPowerBand(Base):
    __tablename__ = "station_power_bands"

    id = Column(Integer, primary_key=True)
    station_id = Column(
        Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False
    )
    start_minute = Column(Integer, nullable=False)
    end_minute = Column(Integer, nullable=False)
    power_limit_kw = Column(Numeric(10, 3), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "start_minute >= 0 AND start_minute < 1440",
            name="ck_station_power_bands_start_minute",
        ),
        CheckConstraint(
            "end_minute >= 0 AND end_minute <= 1440",
            name="ck_station_power_bands_end_minute",
        ),
        CheckConstraint(
            "start_minute <> end_minute",
            name="ck_station_power_bands_nonempty",
        ),
        CheckConstraint(
            "power_limit_kw > 0",
            name="ck_station_power_bands_limit_positive",
        ),
        UniqueConstraint(
            "station_id", "start_minute", name="uq_station_power_band_start"
        ),
        Index(
            "ix_station_power_bands_station_minutes",
            "station_id",
            "start_minute",
            "end_minute",
        ),
    )
