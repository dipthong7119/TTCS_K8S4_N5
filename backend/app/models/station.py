"""
Models: stations
Tham chieu: SPRINT_1.md T-08, 02_CODING_STANDARDS.md muc 2.2
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String
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
    # active | inactive | maintenance
    status = Column(String(20), default="active", nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Chi muc tren owner_id -- moi truy van cua chu tram loc theo cot nay (T-08 NFR)
    __table_args__ = (Index("ix_stations_owner_id", "owner_id"),)

    owner = relationship("User", back_populates="stations")
    charge_points = relationship("ChargePoint", back_populates="station")
