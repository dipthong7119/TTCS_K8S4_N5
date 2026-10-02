from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ConnectorError(Base):
    __tablename__ = "connector_errors"

    id = Column(Integer, primary_key=True)
    connector_id = Column(Integer, ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False)
    error_code = Column(String(50), nullable=False)
    vendor_error_code = Column(String(50), nullable=True)
    info = Column(String(500), nullable=True)
    timestamp = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_connector_errors_connector_timestamp", "connector_id", "timestamp"),)

    connector = relationship("Connector", back_populates="errors")
