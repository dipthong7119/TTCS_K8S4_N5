"""
Model: charge_points, connectors
Task T-10 — Sprint 1
Quan hệ: stations → charge_points → connectors (cha-con hai tầng).
NFR: charge_points.code UNIQUE toàn hệ thống + chỉ mục (mọi kết nối OCPP tra cứu theo cột này).
     connectors.connector_id bắt đầu từ 1, khớp với connectorId trong tin nhắn OCPP.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ChargePoint(Base):
    """Trụ sạc — thuộc một trạm (station_id). Mã trụ (code) duy nhất toàn hệ thống."""

    __tablename__ = "charge_points"

    id = Column(Integer, primary_key=True, index=True)

    # Mã trụ — tra cứu bởi mọi kết nối OCPP → UNIQUE + chỉ mục rõ tường minh
    code = Column(String(50), unique=True, nullable=False, index=True)

    station_id = Column(
        Integer,
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
    )

    vendor = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    firmware_version = Column(String(100), nullable=True)

    # Trạng thái kết nối OCPP: online | offline
    status = Column(String(20), nullable=False, default="offline")

    # Thời điểm nhận tin nhắn cuối (Heartbeat / StatusNotification)
    # — job nền T-26 dùng để phát hiện trụ mất kết nối
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Quan hệ
    station = relationship("Station", back_populates="charge_points")
    connectors = relationship(
        "Connector", back_populates="charge_point", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_charge_points_station_id", "station_id"),)


class Connector(Base):
    """Đầu nối — thuộc một trụ sạc.
    connector_id bắt đầu từ 1, khớp với connectorId trong tin nhắn OCPP 1.6J.
    Ràng buộc UNIQUE (charge_point_id, connector_id) để không trùng đầu nối trong cùng trụ.
    """

    __tablename__ = "connectors"

    id = Column(Integer, primary_key=True, index=True)

    charge_point_id = Column(
        Integer,
        ForeignKey("charge_points.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Số thứ tự đầu nối theo OCPP — bắt đầu từ 1
    connector_id = Column(Integer, nullable=False)

    # Trạng thái đầu nối: Available, Preparing, Charging, SuspendedEV,
    # SuspendedEVSE, Finishing, Reserved, Unavailable, Faulted
    status = Column(String(20), nullable=False, default="Unavailable")
    error_code = Column(String(50), nullable=False, default="NoError")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Quan hệ
    charge_point = relationship("ChargePoint", back_populates="connectors")

    __table_args__ = (
        # Ràng buộc: một trụ không thể có hai đầu nối cùng connector_id
        UniqueConstraint("charge_point_id", "connector_id", name="uq_connectors_cp_connector"),
        Index("ix_connectors_charge_point_id", "charge_point_id"),
    )
