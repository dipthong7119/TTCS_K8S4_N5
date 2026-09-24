"""
Model: users, roles, user_roles
Task T-04 — Sprint 1
Schema theo mẫu đặt tên từ T-01: snake_case, PK = id, thời gian = created_at/updated_at.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Role(Base):
    """Bảng vai trò — seed sẵn 5 vai trò: driver, station_owner, operator, accountant, admin."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Quan hệ ngược
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class User(Base):
    """Bảng người dùng — mọi vai trò đăng nhập qua bảng này."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(512), nullable=False)          # argon2id — đủ dài cho hash
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Chống brute-force — lưu ở DB, không lưu biến tiến trình (SSD-1 ràng buộc)
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_failed_ip = Column(String(45), nullable=True)           # IPv4/IPv6

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Quan hệ
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    stations = relationship("Station", back_populates="owner")


class UserRole(Base):
    """Bảng nối nhiều-nhiều users ↔ roles."""

    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

    # Quan hệ
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles"),)
