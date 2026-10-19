"""Immutable financial reconciliation snapshots for locked station periods."""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from app.database import Base


class ReconciliationPeriodLock(Base):
    __tablename__ = "reconciliation_period_locks"
    __table_args__ = (
        CheckConstraint("to_date >= from_date", name="ck_recon_lock_date_range"),
        CheckConstraint("status = 'locked'", name="ck_recon_lock_status_locked"),
        UniqueConstraint(
            "station_id", "from_date", "to_date", name="uq_recon_lock_station_period"
        ),
    )

    id = Column(Integer, primary_key=True)
    station_id = Column(
        Integer, ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False
    )
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    status = Column(String(10), nullable=False, server_default=text("'locked'"))
    snapshot = Column(JSON, nullable=False)
    locked_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    locked_at = Column(DateTime, nullable=False, server_default=func.now())
