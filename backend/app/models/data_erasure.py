"""
Models: data_erasure_requests
Tham chiếu: SCRUM-92 / S-57 — Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển (Nghị định 13/2023/NĐ-CP).
"""

from sqlalchemy import (
    CheckConstraint,
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


class DataErasureRequest(Base):
    """
    Yêu cầu xóa/ẩn danh hóa dữ liệu cá nhân của tài xế theo Nghị định 13/2023/NĐ-CP.
    """

    __tablename__ = "data_erasure_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status = Column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    request_reason = Column(String(500), nullable=True)
    request_reason_label = Column(String(255), nullable=True)
    request_reason_detail = Column(String(2000), nullable=True)
    resolution_action = Column(String(32), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    requested_at = Column(DateTime, nullable=False, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", foreign_keys=[user_id])
    processor = relationship("User", foreign_keys=[processed_by])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_data_erasure_requests_status",
        ),
        CheckConstraint(
            "resolution_action IS NULL OR resolution_action IN ('delete_personal_data', 'hide_account')",
            name="ck_data_erasure_requests_resolution_action",
        ),
        Index("ix_data_erasure_requests_user_status", "user_id", "status"),
    )
