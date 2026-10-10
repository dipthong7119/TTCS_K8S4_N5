"""Immutable monthly plan and price snapshots purchased by drivers."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.sql import func

from app.database import Base


class DriverSubscription(Base):
    __tablename__ = "driver_subscriptions"
    __table_args__ = (
        CheckConstraint("monthly_fee_vnd > 0", name="ck_driver_subscription_fee_positive"),
        CheckConstraint("price_vnd_per_kwh >= 0", name="ck_driver_subscription_rate_nonnegative"),
        CheckConstraint("expires_at > starts_at", name="ck_driver_subscription_period_valid"),
        Index("ix_driver_subscriptions_user_period", "user_id", "starts_at", "expires_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    plan_id = Column(
        Integer, ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False
    )
    plan_name = Column(String(120), nullable=False)
    monthly_fee_vnd = Column(Integer, nullable=False)
    price_vnd_per_kwh = Column(Integer, nullable=False)
    starts_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
