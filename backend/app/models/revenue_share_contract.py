"""Versioned partner/platform revenue split agreements."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class RevenueShareContract(Base):
    __tablename__ = "revenue_share_contracts"
    __table_args__ = (
        CheckConstraint(
            "partner_share_percent >= 0 AND partner_share_percent <= 100",
            name="ck_revenue_share_contract_partner_percent",
        ),
        CheckConstraint(
            "platform_share_percent >= 0 AND platform_share_percent <= 100",
            name="ck_revenue_share_contract_platform_percent",
        ),
        CheckConstraint(
            "partner_share_percent + platform_share_percent = 100",
            name="ck_revenue_share_contract_total_percent",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_revenue_share_contract_effective_range",
        ),
        UniqueConstraint(
            "station_owner_id", "effective_from", name="uq_revenue_share_owner_effective"
        ),
        Index(
            "ix_revenue_share_owner_effective",
            "station_owner_id",
            "effective_from",
            "effective_to",
        ),
    )

    id = Column(Integer, primary_key=True)
    station_owner_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    partner_share_percent = Column(Numeric(5, 2), nullable=False)
    platform_share_percent = Column(Numeric(5, 2), nullable=False)
    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
