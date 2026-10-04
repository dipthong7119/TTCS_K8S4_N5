from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

# Do dùng SQLite nên cần thêm check_same_thread=False
# (để FastAPI có thể sử dụng DB trên nhiều thread)
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enforce_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency để sử dụng trong FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
