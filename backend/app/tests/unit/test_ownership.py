"""
tests/unit/test_ownership.py -- Test hàm lọc theo quyền sở hữu (T-07)
Tham chieu: SPRINT_1.md T-07, SSD-1
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.station import Station
from app.models.user import User
from app.services.ownership import filter_by_owner


def test_filter_by_owner_admin_sees_all(db_session: Session):
    """Admin thấy tất cả trạm"""
    # Tạo 2 user: admin và owner
    admin = User(email="admin@test.com", password_hash="x", full_name="Admin", is_active=True)
    owner = User(email="owner@test.com", password_hash="x", full_name="Owner", is_active=True)
    db_session.add_all([admin, owner])
    db_session.commit()

    # Tạo 2 trạm: mỗi trạm thuộc một owner
    station1 = Station(name="Trạm A", address="Addr A", owner_id=owner.id)
    station2 = Station(name="Trạm B", address="Addr B", owner_id=admin.id)
    db_session.add_all([station1, station2])
    db_session.commit()

    # Admin thấy cả 2 trạm
    stmt = select(Station)
    stmt = filter_by_owner(stmt, admin.id, ["admin"])
    result = db_session.scalars(stmt).all()
    assert len(result) == 2

    # Chỉ owner của mỗi trạm mới thấy trạm của mình
    stmt1 = select(Station).where(Station.name == "Trạm A")
    stmt1 = filter_by_owner(stmt1, owner.id, ["station_owner"])
    result1 = db_session.scalars(stmt1).all()
    assert len(result1) == 1
    assert result1[0].name == "Trạm A"

    stmt2 = select(Station).where(Station.name == "Trạm B")
    stmt2 = filter_by_owner(stmt2, owner.id, ["station_owner"])
    result2 = db_session.scalars(stmt2).all()
    assert len(result2) == 0  # owner không thấy trạm B (của admin)


def test_filter_by_owner_station_owner_sees_only_their_stations(db_session: Session):
    """Chủ trạm chỉ thấy trạm của mình"""
    owner1 = User(email="owner1@test.com", password_hash="x", full_name="Owner 1", is_active=True)
    owner2 = User(email="owner2@test.com", password_hash="x", full_name="Owner 2", is_active=True)
    db_session.add_all([owner1, owner2])
    db_session.commit()

    station1 = Station(name="Trạm 1", address="Addr 1", owner_id=owner1.id)
    station2 = Station(name="Trạm 2", address="Addr 2", owner_id=owner2.id)
    db_session.add_all([station1, station2])
    db_session.commit()

    stmt = select(Station)
    stmt = filter_by_owner(stmt, owner1.id, ["station_owner"])
    result = db_session.scalars(stmt).all()
    assert len(result) == 1
    assert result[0].name == "Trạm 1"


def test_filter_by_owner_driver_sees_nothing(db_session: Session):
    """Tài xế không thấy trạm nào"""
    driver = User(email="driver@test.com", password_hash="x", full_name="Driver", is_active=True)
    owner = User(email="owner@test.com", password_hash="x", full_name="Owner", is_active=True)
    db_session.add_all([driver, owner])
    db_session.commit()

    station = Station(name="Trạm Test", address="Addr Test", owner_id=owner.id)
    db_session.add(station)
    db_session.commit()

    stmt = select(Station)
    stmt = filter_by_owner(stmt, driver.id, ["driver"])
    result = db_session.scalars(stmt).all()
    assert len(result) == 0