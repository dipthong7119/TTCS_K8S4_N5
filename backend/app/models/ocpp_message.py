from sqlalchemy import JSON, Column, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class OcppMessage(Base):
    """
    T-30: Bảng lưu tin nhắn OCPP đã xử lý để chống trùng (idempotency).
    Lưu msg_id để khi trụ gửi lại, hệ thống trả về đúng response cũ.
    """
    __tablename__ = "ocpp_messages"

    id = Column(Integer, primary_key=True)
    msg_id = Column(String(50), nullable=False)
    charge_point_code = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    response_payload = Column(JSON, nullable=False)
    request_hash = Column(String(64), nullable=False, default="")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("uq_ocpp_message_per_charge_point", "charge_point_code", "msg_id", unique=True),
    )
