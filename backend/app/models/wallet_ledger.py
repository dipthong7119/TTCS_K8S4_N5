"""Append-only integer VND wallet transactions."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class WalletLedgerEntry(Base):
    __tablename__ = "wallet_ledger"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    entry_type = Column(String(30), nullable=False)
    amount_vnd = Column(Integer, nullable=False)
    idempotency_key = Column(String(120), nullable=False)
    reference_type = Column(String(30), nullable=True)
    reference_id = Column(Integer, nullable=True)
    receipt_code = Column(String(80), nullable=True, unique=True)
    description = Column(String(255), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type = 'session_charge' AND amount_vnd < 0)",
            name="ck_wallet_ledger_amount_sign",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="uq_wallet_user_idempotency"),
        Index("ix_wallet_ledger_user_created", "user_id", "created_at", "id"),
        Index("ix_wallet_ledger_reference", "reference_type", "reference_id"),
    )
