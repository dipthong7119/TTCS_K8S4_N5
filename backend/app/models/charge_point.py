"""
Models: charge_points, connectors
Tham chieu: SPRINT_1.md T-10, 02_CODING_STANDARDS.md muc 2.2
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ChargePoint(Base):
    """Tru sac -- code unique toan he thong, co chi muc vi moi ket noi OCPP tra cuu theo day."""

    __tablename__ = "charge_points"

    id = Column(Integer, primary_key=True)
    # UNIQUE + INDEX: moi ket noi WebSocket OCPP tra cuu theo cot nay (T-10 NFR)
    code = Column(String(50), unique=True, nullable=False, index=True)
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    vendor = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    firmware_version = Column(String(100), nullable=True)
    # online | offline
    status = Column(String(20), default="offline", nullable=False)
    last_seen_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    station = relationship("Station", back_populates="charge_points")
    connectors = relationship("Connector", back_populates="charge_point")


class Connector(Base):
    """Dau noi cua tru sac -- connector_id khop voi connectorId trong giao thuc OCPP (bat dau tu 1)."""

    __tablename__ = "connectors"

    id = Column(Integer, primary_key=True)
    charge_point_id = Column(Integer, ForeignKey("charge_points.id", ondelete="CASCADE"), nullable=False)
    # Khop voi connectorId trong tin nhan OCPP, bat dau tu 1 (T-10 NFR)
    connector_id = Column(Integer, nullable=False)
    # unavailable | available | charging | faulted
    status = Column(String(20), default="unavailable", nullable=False)
    error_code = Column(String(50), default="NoError", nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        # Moi cap (tru, dau noi) phai duy nhat -- DB tu choi neu chon trung (T-10 AC)
        UniqueConstraint("charge_point_id", "connector_id", name="uq_connector_per_charge_point"),
    )

    charge_point = relationship("ChargePoint", back_populates="connectors")
    errors = relationship("ConnectorError", back_populates="connector", cascade="all, delete-orphan")
