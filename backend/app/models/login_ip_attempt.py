"""Per-IP failed-login counters used by the Sprint 1 lockout policy."""

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class LoginIPAttempt(Base):
    __tablename__ = "login_ip_attempts"

    id = Column(Integer, primary_key=True)
    ip_address = Column(String(45), nullable=False)
    failed_login_count = Column(Integer, default=0, server_default="0", nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ip_address", name="uq_login_ip_attempts_ip_address"),
    )
