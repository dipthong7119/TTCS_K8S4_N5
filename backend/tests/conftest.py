import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ENERGY_SAMPLE_CASES = json.loads(
    (Path(__file__).parent / "scrum188_sessions.json").read_text(encoding="utf-8")
)


@pytest.fixture(params=ENERGY_SAMPLE_CASES, ids=lambda case: case["case_id"])
def energy_sample_case(request):
    """SCRUM-188: đáp án tính tay dùng chung cho hàm thuần và handler."""
    return request.param


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db(db_session):
    return db_session
