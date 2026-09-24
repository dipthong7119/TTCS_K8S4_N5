"""
Model: stations
Task T-08 — Sprint 1
Schema: khoá ngoại tới users (chủ sở hữu), trạng thái hoạt động, toạ độ số thực.
NFR: chỉ mục trên owner_id vì mọi truy vấn của chủ trạm lọc theo cột này.
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Station(Base):
    """Trạm sạc — do một chủ trạm sở hữu (owner_id → users.id)."""

    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String, nullable=True)

    # Toạ độ địa lý — kiểu số thực (FLOAT ~ DOUBLE PRECISION trên PostgreSQL)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Trạng thái hoạt động: active | inactive | maintenance
    status = Column(String(20), nullable=False, default="active")

    # Khoá ngoại tới chủ sở hữu; RESTRICT để chặn xoá user còn trạm
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Quan hệ
    owner = relationship("User", back_populates="stations")
    charge_points = relationship(
        "ChargePoint", back_populates="station", cascade="all, delete-orphan"
    )

    # Chỉ mục trên owner_id — NFR T-08: mọi truy vấn của chủ trạm lọc theo cột này
    __table_args__ = (Index("ix_stations_owner_id", "owner_id"),)
