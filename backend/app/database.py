"""
database.py — SQLAlchemy engine, session factory, và Base.
Dùng engine đồng bộ (synchronous) để tương thích với Alembic và code hiện tại.
Chỉ file này tạo engine — không tạo engine ở nơi khác.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class cho tất cả SQLAlchemy models."""
    pass


# Engine PostgreSQL (synchronous) — chuỗi kết nối đọc từ config.py, không hardcode
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # phát hiện connection chết trước khi dùng
    echo=False,           # không log SQL ra stdout (tránh rò rỉ thông tin nhạy cảm)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI Dependency — inject DB session vào router/service."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
