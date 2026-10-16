"""
Model: alerts
Tham chiếu: S-46 (SCRUM-90) — Cảnh báo khi trụ ngoại tuyến quá lâu hoặc báo lỗi liên tục.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Alert(Base):
    """Bảng lưu các cảnh báo giám sát vận hành."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    charge_point_id = Column(
        Integer, ForeignKey("charge_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connector_id = Column(
        Integer, ForeignKey("connectors.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # offline | connector_error
    alert_type = Column(String(50), nullable=False)
    # warning | critical
    severity = Column(String(20), default="warning", nullable=False)
    # active | resolved
    status = Column(String(20), default="active", nullable=False)
    message = Column(String(500), nullable=False)
    error_count = Column(Integer, nullable=True)

    triggered_at = Column(DateTime, server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    charge_point = relationship("ChargePoint")
    connector = relationship("Connector")
    resolved_by = relationship("User")

    __table_args__ = (
        Index("ix_alerts_cp_status_type", "charge_point_id", "status", "alert_type"),
        Index("ix_alerts_status", "status"),
    )
