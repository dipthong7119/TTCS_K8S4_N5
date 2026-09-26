from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database import Base

class IdTag(Base):
    """
    T-32: Bảng id_tags gắn thẻ với tài xế
    """
    __tablename__ = "id_tags"

    id = Column(Integer, primary_key=True)
    id_tag = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    is_blocked = Column(Boolean, default=False, nullable=False)
    expiry_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
