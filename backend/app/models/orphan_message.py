"""Sanitized OCPP records that could not be matched to a charging session."""

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class OrphanMessage(Base):
    __tablename__ = "orphan_messages"

    id = Column(Integer, primary_key=True)
    charge_point_code = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    transaction_id = Column(Integer, nullable=True)
    connector_number = Column(Integer, nullable=True)
    reason = Column(String(80), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    received_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_orphan_messages_cp_received", "charge_point_code", "received_at"),
        Index("ix_orphan_messages_transaction", "transaction_id", "received_at"),
    )
