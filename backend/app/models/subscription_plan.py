"""Platform-wide monthly charging packages and their prices."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    true,
)
from sqlalchemy.sql import func

from app.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        CheckConstraint("monthly_fee_vnd > 0", name="ck_subscription_plan_fee_positive"),
        CheckConstraint("price_vnd_per_kwh >= 0", name="ck_subscription_plan_rate_nonnegative"),
        Index("ix_subscription_plans_active_name", "is_active", "name"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    monthly_fee_vnd = Column(Integer, nullable=False)
    price_vnd_per_kwh = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
