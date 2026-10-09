"""Model for payment transactions and wallet top-up requests."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True)
    order_code = Column(String(80), nullable=False, unique=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_vnd = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    provider = Column(String(30), nullable=False, default="sandbox")
    payment_url = Column(Text, nullable=True)
    failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_payment_transactions_user_status", "user_id", "status"),
        Index("ix_payment_transactions_created", "created_at"),
    )
