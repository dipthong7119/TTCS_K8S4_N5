"""Immutable snapshots created each time a reconciliation period is closed."""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class ReconciliationPeriodSnapshot(Base):
    __tablename__ = "reconciliation_period_snapshots"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_recon_period_snapshot_revision"),
        UniqueConstraint(
            "period_lock_id", "revision", name="uq_recon_period_snapshot_revision"
        ),
    )

    id = Column(Integer, primary_key=True)
    period_lock_id = Column(
        Integer,
        ForeignKey("reconciliation_period_locks.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    locked_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    locked_at = Column(DateTime, nullable=False, server_default=func.now())
