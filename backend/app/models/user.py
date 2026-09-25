"""
Models: users, roles, user_roles
Tham chieu: SPRINT_1.md T-04, 02_CODING_STANDARDS.md muc 2.2
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

# -- Bang noi nhieu-nhieu user <-> role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    """Vai tro: driver | station_owner | operator | accountant | admin"""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    """Nguoi dung he thong -- mat khau luu duoi dang hash argon2id."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(512), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Chong brute-force -- luu o DB, khong o bien tien trinh (SSD-1)
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_failed_ip = Column(String(45), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    roles = relationship("Role", secondary=user_roles, back_populates="users")
    stations = relationship("Station", back_populates="owner")
