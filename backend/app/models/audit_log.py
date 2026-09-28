"""Append-only audit trail for operator and OCPP events."""

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, nullable=True)
    actor_email = Column(String(255), nullable=True)
    actor_name = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    object_type = Column(String(80), nullable=False)
    object_id = Column(String(80), nullable=True)
    charge_point_code = Column(String(50), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_audit_logs_created_id", "created_at", "id"),
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
        Index("ix_audit_logs_cp_created", "charge_point_code", "created_at"),
    )
