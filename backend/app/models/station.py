"""
Models: stations
Tham chieu: SPRINT_1.md T-08, 02_CODING_STANDARDS.md muc 2.2
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Station(Base):
    """Tram sac -- co khoa ngoai toi users lam chu so huu."""

    __tablename__ = "stations"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    power_limit_kw = Column(Numeric(10, 3), nullable=True)
    # active | inactive | maintenance | locked (administrative OCPP boot block)
    status = Column(String(20), default="inactive", server_default="inactive", nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Phí không đến (VNĐ, mặc định 0). snapshot_no_show_fee() chốt giá trị này vào reservation khi đặt chỗ.
    no_show_fee_vnd = Column(Integer, nullable=False, default=0, server_default="0")

    # Chi muc tren owner_id -- moi truy van cua chu tram loc theo cot nay (T-08 NFR)
    __table_args__ = (
        CheckConstraint(
            "power_limit_kw IS NULL OR power_limit_kw > 0",
            name="ck_stations_power_limit_positive",
        ),
        CheckConstraint(
            "no_show_fee_vnd >= 0",
            name="ck_stations_no_show_fee_nonneg",
        ),
        Index("ix_stations_owner_id", "owner_id"),
    )

    owner = relationship("User", back_populates="stations")
    charge_points = relationship(
        "ChargePoint", back_populates="station", cascade="all, delete-orphan"
    )
