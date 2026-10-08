"""T-53/SCRUM-174: ngưỡng cấu hình, không đóng phiên, job chạy lặp an toàn."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from app.config import settings
from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.user import User
from app.services.jobs import review_stale_sessions_once


@pytest.fixture
def review_setup(db_session, monkeypatch):
    now = datetime(2026, 10, 9, 8, tzinfo=UTC).replace(tzinfo=None)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(tzinfo=UTC) if tz is not None else now

    monkeypatch.setattr("app.services.jobs.datetime", FixedDateTime)
    monkeypatch.setattr(settings, "SESSION_OFFLINE_GRACE_SECONDS", 60)
    monkeypatch.setattr(settings, "REMOTE_STOP_REVIEW_SECONDS", 120)
    notify = Mock()
    monkeypatch.setattr("app.routers.monitoring.notify_session_change", notify)
    owner = User(email="review-owner@example.test", password_hash="test", full_name="Owner")
    db_session.add(owner)
    db_session.flush()
    station = Station(name="Session review", owner_id=owner.id, status="active")
    db_session.add(station)
    db_session.commit()
    return db_session, station, now, notify


def add_session(setup, *, age=61, point_status="offline", session_status="active", never_seen=False):
    db, station, now, _ = setup
    point = ChargePoint(code=f"REVIEW-{db.query(ChargePoint).count() + 1}",
                        station_id=station.id, status=point_status,
                        created_at=now - timedelta(seconds=age),
                        last_seen_at=None if never_seen else now - timedelta(seconds=age))
    db.add(point)
    db.flush()
    session = ChargingSession(charge_point_id=point.id, charge_point_code=point.code,
                              station_id=station.id, station_name=station.name, connector_number=1,
                              meter_start_wh=1000, started_at=now - timedelta(hours=2),
                              status=session_status)
    db.add(session)
    db.commit()
    return session


@pytest.mark.parametrize(("age", "changed"), [(59, False), (60, True), (61, True)])
def test_offline_grace_boundary_and_repeat_have_no_closure_or_duplicate_events(review_setup, age, changed):
    db, station, _, notify = review_setup
    session = add_session(review_setup, age=age)

    assert review_stale_sessions_once(db) == int(changed)
    db.refresh(session)
    assert session.status == ("anomaly" if changed else "active")
    assert session.anomaly_reason == ("offline" if changed else None)
    assert session.ended_at is None
    assert session.meter_stop_wh is None
    assert session.energy_kwh is None
    assert review_stale_sessions_once(db) == 0
    assert notify.call_count == int(changed)
    if changed:
        notify.assert_called_once_with(None, station.owner_id, session.id)


@pytest.mark.parametrize(("age", "changed"), [(30, False), (120, True)])
def test_never_seen_point_uses_creation_time(review_setup, age, changed):
    db, _, _, _ = review_setup
    session = add_session(review_setup, age=age, never_seen=True)
    assert review_stale_sessions_once(db) == int(changed)
    db.refresh(session)
    assert session.status == ("anomaly" if changed else "active")


def test_online_point_is_not_flagged_merely_because_session_is_old(review_setup):
    db, _, _, notify = review_setup
    session = add_session(review_setup, age=86400, point_status="online")
    assert review_stale_sessions_once(db) == 0
    db.refresh(session)
    assert session.status == "active"
    notify.assert_not_called()


@pytest.mark.parametrize("status", ["completed", "needs_review", "anomaly"])
def test_previously_reviewed_and_closed_sessions_keep_their_reason(review_setup, status):
    db, _, now, notify = review_setup
    session = add_session(review_setup, session_status=status)
    session.anomaly_reason = "existing_reason"
    if status == "completed":
        session.ended_at = now - timedelta(minutes=1)
        session.meter_stop_wh = 2500
    db.commit()
    assert review_stale_sessions_once(db) == 0
    db.refresh(session)
    assert session.status == status
    assert session.anomaly_reason == "existing_reason"
    notify.assert_not_called()


@pytest.mark.parametrize(("age", "changed"), [(119, False), (120, True), (121, True)])
def test_remote_stop_deadline_keeps_session_open(review_setup, age, changed):
    db, _, now, _ = review_setup
    session = add_session(review_setup, point_status="online")
    session.remote_stop_requested_at = now - timedelta(seconds=age)
    db.commit()
    assert review_stale_sessions_once(db) == int(changed)
    db.refresh(session)
    assert session.status == ("needs_review" if changed else "active")
    assert session.anomaly_reason == ("remote_stop_timeout" if changed else None)
    assert session.ended_at is None
    assert review_stale_sessions_once(db) == 0


def test_remote_stop_timeout_is_not_overwritten_by_offline_sweep(review_setup):
    """Both criteria match in the same run with autoflush=False (production config)."""
    db, _, now, notify = review_setup
    session = add_session(review_setup)
    session.remote_stop_requested_at = now - timedelta(seconds=121)
    db.commit()
    assert review_stale_sessions_once(db) == 1
    db.refresh(session)
    assert session.status == "needs_review"
    assert session.anomaly_reason == "remote_stop_timeout"
    assert session.ended_at is None
    assert review_stale_sessions_once(db) == 0
    notify.assert_called_once()


def test_deleted_point_does_not_make_an_unrelated_session_offline(review_setup):
    db, _, _, notify = review_setup
    session = add_session(review_setup)
    session.charge_point_id = None
    db.commit()
    assert review_stale_sessions_once(db) == 0
    notify.assert_not_called()
