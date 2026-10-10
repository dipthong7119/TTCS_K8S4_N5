"""Package energy usage snapshots used to allocate station-owner revenue."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class SubscriptionUsage(Base):
    __tablename__ = "subscription_usage"
    __table_args__ = (
        CheckConstraint("energy_wh >= 0", name="ck_subscription_usage_energy_nonnegative"),
        UniqueConstraint("charging_session_id", name="uq_subscription_usage_session"),
        Index("ix_subscription_usage_subscription_owner", "subscription_id", "station_owner_id"),
    )

    id = Column(Integer, primary_key=True)
    subscription_id = Column(
        Integer, ForeignKey("driver_subscriptions.id", ondelete="RESTRICT"), nullable=False
    )
    charging_session_id = Column(
        Integer, ForeignKey("charging_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False)
    station_owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    energy_wh = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
