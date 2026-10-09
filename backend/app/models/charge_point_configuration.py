"""Cấu hình OCPP gần nhất đã được trụ xác nhận."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class ChargePointConfiguration(Base):
    __tablename__ = "charge_point_configuration"

    id = Column(Integer, primary_key=True)
    charge_point_id = Column(
        Integer,
        ForeignKey("charge_points.id", ondelete="CASCADE"),
        nullable=False,
    )
    key = Column(String(100), nullable=False)
    value = Column(String(32), nullable=False)
    status = Column(String(20), nullable=False)
    confirmed_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "charge_point_id",
            "key",
            name="uq_charge_point_configuration_key",
        ),
        CheckConstraint(
            "status IN ('applied', 'reboot_required')",
            name="ck_charge_point_configuration_status",
        ),
    )
