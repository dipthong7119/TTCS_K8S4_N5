"""Known OCPP meter samples associated with a persisted charging session."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.sql import func

from app.database import Base


class MeterValue(Base):
    __tablename__ = "meter_values"

    id = Column(Integer, primary_key=True)
    session_id = Column(
        Integer,
        ForeignKey("charging_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    measured_at = Column(DateTime, nullable=False)
    measurand = Column(String(80), nullable=False)
    value = Column(Numeric(18, 6), nullable=False)
    unit = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_meter_values_session_measured", "session_id", "measured_at"),
    )
