from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    false,
    text,
)
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
    is_virtual = Column(Boolean, default=False, server_default=false(), nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    expiry_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "uq_virtual_id_tag_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("is_virtual = 1"),
            postgresql_where=text("is_virtual"),
        ),
    )
