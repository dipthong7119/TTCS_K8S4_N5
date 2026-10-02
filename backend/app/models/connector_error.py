from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ConnectorError(Base):
    """Bảng lưu lịch sử lỗi của đầu nối (append-only) - SCRUM-120."""
    __tablename__ = "connector_errors"

    id = Column(Integer, primary_key=True)
    connector_id = Column(Integer, ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False)
    error_code = Column(String(50), nullable=False)
    vendor_error_code = Column(String(50), nullable=True)
    
    # Thời điểm xảy ra lỗi (từ trường timestamp của tin nhắn hoặc giờ server)
    occurred_at = Column(DateTime, nullable=False)
    
    # Thời điểm server nhận và ghi nhận log
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_connector_errors_connector_occurred", "connector_id", "occurred_at"),
    )

    connector = relationship("Connector", back_populates="errors")
