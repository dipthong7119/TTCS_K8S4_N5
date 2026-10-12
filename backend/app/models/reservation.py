"""
Models: reservations (SCRUM-76 / S-48: Tài xế đặt chỗ trụ sạc).
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Reservation(Base):
    """
    Bản ghi đặt chỗ trụ sạc trước thời gian sạc (OCPP ReserveNow).
    """

    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    charge_point_id = Column(
        Integer,
        ForeignKey("charge_points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_id = Column(Integer, nullable=False)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_tag = Column(String(50), nullable=False)
    start_time = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    # Status: 'pending', 'accepted', 'rejected', 'cancelled', 'expired', 'completed'
    status = Column(String(20), default="pending", nullable=False)
    reject_reason = Column(String(100), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    charge_point = relationship("ChargePoint")
    user = relationship("User")

    __table_args__ = (
        Index(
            "ix_reservations_cp_conn_status",
            "charge_point_id",
            "connector_id",
            "status",
        ),
    )
