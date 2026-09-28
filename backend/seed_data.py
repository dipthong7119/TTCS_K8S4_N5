"""Idempotent development data for exploring the CSMS interfaces."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.connector_error import ConnectorError
from app.models.id_tag import IdTag
from app.models.station import Station
from app.models.user import User

SIMULATOR_CODES = tuple(f"SIM-{number:02d}" for number in range(1, 21))

STATIONS = (
    {
        "name": "Trạm sạc Vincom Center",
        "address": "72 Lê Thánh Tôn, Bến Nghé, Quận 1, TP.HCM",
        "latitude": 10.7779,
        "longitude": 106.7024,
        "status": "active",
        "charge_points": (
            {"code": "CP_VINCOM_01", "vendor": "VinFast", "model": "VF-AC-11KW", "connectors": 2},
            {"code": "CP_VINCOM_02", "vendor": "ABB", "model": "Terra 54", "connectors": 1},
        ),
    },
    {
        "name": "Trạm sạc AEON Mall",
        "address": "30 Bờ Bao Tân Thắng, Sơn Kỳ, Tân Phú, TP.HCM",
        "latitude": 10.8016,
        "longitude": 106.6179,
        "status": "active",
        "charge_points": (
            {"code": "CP_AEON_01", "vendor": "EVN", "model": "EVN-FAST", "connectors": 3},
            {
                "code": "CP_AEON_FAULT",
                "vendor": "ABB",
                "model": "Terra AC",
                "connectors": 1,
                "fault_connector": 1,
            },
        ),
    },
    {
        "name": "Trạm sạc khu đô thị Thủ Thiêm",
        "address": "Đường Nguyễn Cơ Thạch, An Lợi Đông, TP. Thủ Đức, TP.HCM",
        "latitude": 10.7788,
        "longitude": 106.7317,
        "status": "maintenance",
        "charge_points": (
            {"code": "CP_DEMO_MAINT_01", "vendor": "Schneider", "model": "EVlink", "connectors": 2},
        ),
    },
    {
        "name": "Trạm sạc thử nghiệm OCPP",
        "address": "Khu vực thử nghiệm nội bộ CSMS, TP.HCM",
        "latitude": 10.7769,
        "longitude": 106.7009,
        "status": "active",
        "charge_points": tuple(
            {
                "code": code,
                "vendor": "CSMS Simulator",
                "model": "OCPP 1.6J",
                "connectors": 2,
            }
            for code in SIMULATOR_CODES
        ),
    },
)

# Dữ liệu có ngày khác nhau để các bộ lọc 7/30/90/365 ngày đều có kết quả.
# Bản ghi bất thường cố ý minh họa dữ liệu cần rà soát, không phải giao dịch thật.
SESSION_SAMPLES = (
    {
        "key": "demo-history-vincom-01",
        "code": "CP_VINCOM_01",
        "connector": 1,
        "days_ago": 2,
        "duration_minutes": 42,
        "meter_start_wh": 18340,
        "energy_kwh": 7.420,
        "status": "completed",
        "stop_reason": "Local",
    },
    {
        "key": "demo-history-aeon-01",
        "code": "CP_AEON_01",
        "connector": 2,
        "days_ago": 12,
        "duration_minutes": 58,
        "meter_start_wh": 27110,
        "energy_kwh": 11.860,
        "status": "completed",
        "stop_reason": "EVDisconnected",
    },
    {
        "key": "demo-history-sim-01",
        "code": "SIM-01",
        "connector": 1,
        "days_ago": 42,
        "duration_minutes": 35,
        "meter_start_wh": 40520,
        "energy_kwh": 5.230,
        "status": "completed",
        "stop_reason": "Local",
    },
    {
        "key": "demo-history-sim-02",
        "code": "SIM-02",
        "connector": 2,
        "days_ago": 120,
        "duration_minutes": 73,
        "meter_start_wh": 68200,
        "energy_kwh": 18.340,
        "status": "completed",
        "stop_reason": "EVDisconnected",
    },
    {
        "key": "demo-anomaly-negative-kwh",
        "code": "CP_AEON_01",
        "connector": 1,
        "days_ago": 4,
        "duration_minutes": 9,
        "meter_start_wh": 51200,
        "energy_kwh": -0.120,
        "status": "anomaly",
        "anomaly_reason": "negative_kwh",
        "stop_reason": "Other",
    },
    {
        "key": "demo-anomaly-offline",
        "code": "SIM-03",
        "connector": 1,
        "days_ago": 6,
        "duration_minutes": 18,
        "meter_start_wh": 73900,
        "energy_kwh": 3.100,
        "status": "needs_review",
        "anomaly_reason": "offline",
        "stop_reason": None,
    },
)


def _ensure_station(db: Session, owner: User, spec: dict, counts: dict[str, int]) -> Station:
    station = (
        db.query(Station)
        .filter(Station.owner_id == owner.id, Station.name == spec["name"])
        .first()
    )
    if station is None:
        station = Station(
            name=spec["name"],
            address=spec["address"],
            latitude=spec["latitude"],
            longitude=spec["longitude"],
            status=spec["status"],
            owner_id=owner.id,
        )
        db.add(station)
        db.flush()
        counts["stations"] += 1
    return station


def _ensure_charge_points(
    db: Session, station: Station, specs: tuple[dict, ...], counts: dict[str, int]
) -> dict[str, ChargePoint]:
    points: dict[str, ChargePoint] = {}
    for spec in specs:
        point = db.query(ChargePoint).filter(ChargePoint.code == spec["code"]).first()
        if point is not None and point.station_id != station.id:
            # Never move/reassign an existing device if the demo code was already claimed.
            continue
        if point is None:
            point = ChargePoint(
                code=spec["code"],
                station_id=station.id,
                vendor=spec["vendor"],
                model=spec["model"],
                firmware_version="1.6J-demo",
                status="offline",
            )
            db.add(point)
            db.flush()
            counts["charge_points"] += 1

        fault_connector = spec.get("fault_connector")
        for number in range(1, spec["connectors"] + 1):
            connector = (
                db.query(Connector)
                .filter_by(charge_point_id=point.id, connector_id=number)
                .first()
            )
            if connector is not None:
                continue
            is_fault = number == fault_connector
            connector = Connector(
                charge_point_id=point.id,
                connector_id=number,
                status="lỗi" if is_fault else "unavailable",
                ocpp_status="Faulted" if is_fault else None,
                error_code="GroundFailure" if is_fault else "NoError",
            )
            db.add(connector)
            db.flush()
            counts["connectors"] += 1
            if is_fault:
                _ensure_connector_error(db, connector, counts)

        points[point.code] = point
    return points


def _ensure_connector_error(db: Session, connector: Connector, counts: dict[str, int]) -> None:
    error = (
        db.query(ConnectorError)
        .filter_by(
            connector_id=connector.id,
            error_code="GroundFailure",
            vendor_error_code="DEMO-GND-01",
        )
        .first()
    )
    if error is None:
        db.add(
            ConnectorError(
                connector_id=connector.id,
                error_code="GroundFailure",
                vendor_error_code="DEMO-GND-01",
                info="Bản ghi lỗi giả lập để minh họa trạng thái đầu nối; không phải lỗi thiết bị thật.",
                timestamp=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
            )
        )
        counts["connector_errors"] += 1


def _ensure_driver_tags(db: Session, driver: User, counts: dict[str, int]) -> IdTag:
    now = datetime.now(UTC).replace(tzinfo=None)
    base_tag = f"DEMO-DRIVER-{driver.id:04d}"
    tag_value = base_tag
    suffix = 0
    active_tag = None
    while active_tag is None:
        existing = db.query(IdTag).filter(IdTag.id_tag == tag_value).first()
        if existing is None:
            active_tag = IdTag(id_tag=tag_value, user_id=driver.id, is_blocked=False)
            db.add(active_tag)
            db.flush()
            counts["id_tags"] += 1
            break
        is_valid = (
            existing.user_id == driver.id
            and not existing.is_blocked
            and (existing.expiry_date is None or existing.expiry_date > now)
        )
        if is_valid:
            active_tag = existing
            break
        suffix += 1
        tag_value = f"DEMO-SEED-DRIVER-{driver.id:04d}-{suffix}"

    tag_fixtures = (
        (f"DEMO-BLOCKED-{driver.id:04d}", True, None),
        (
            f"DEMO-EXPIRED-{driver.id:04d}",
            False,
            now - timedelta(days=1),
        ),
    )
    for tag_value, is_blocked, expiry_date in tag_fixtures:
        if db.query(IdTag.id).filter(IdTag.id_tag == tag_value).first():
            continue
        db.add(
            IdTag(
                id_tag=tag_value,
                user_id=driver.id,
                is_blocked=is_blocked,
                expiry_date=expiry_date,
            )
        )
        counts["id_tags"] += 1
    db.flush()
    return active_tag


def _ensure_sessions(
    db: Session,
    driver: User,
    active_tag: IdTag,
    points: dict[str, ChargePoint],
    now: datetime,
    counts: dict[str, int],
) -> list[ChargingSession]:
    sessions: list[ChargingSession] = []
    for spec in SESSION_SAMPLES:
        point = points.get(spec["code"])
        if point is None:
            continue
        item = db.query(ChargingSession).filter_by(demo_key=spec["key"]).first()
        if item is None:
            started_at = now - timedelta(days=spec["days_ago"], hours=2)
            ended_at = started_at + timedelta(minutes=spec["duration_minutes"])
            meter_stop = spec["meter_start_wh"] + round(spec["energy_kwh"] * 1000)
            item = ChargingSession(
                charge_point_id=point.id,
                charge_point_code=point.code,
                station_id=point.station_id,
                station_name=point.station.name,
                connector_number=spec["connector"],
                user_id=driver.id,
                driver_name=driver.full_name,
                id_tag_id=active_tag.id,
                id_tag=active_tag.id_tag,
                meter_start_wh=spec["meter_start_wh"],
                meter_stop_wh=meter_stop,
                energy_kwh=spec["energy_kwh"],
                started_at=started_at,
                ended_at=ended_at,
                status=spec["status"],
                stop_reason=spec["stop_reason"],
                anomaly_reason=spec.get("anomaly_reason"),
                is_demo=True,
                demo_key=spec["key"],
            )
            db.add(item)
            db.flush()
            counts["sessions"] += 1

        sessions.append(item)
    return sessions


def _ensure_audit_samples(
    db: Session, now: datetime, point_codes: set[str], counts: dict[str, int]
) -> None:
    samples = (
        {
            "key": "demo-seed-stations",
            "action": "demo.seed.stations",
            "object_type": "station",
            "object_id": "demo-stations",
            "charge_point_code": None,
            "details": {"note": "Bản ghi mẫu do seed_data.py tạo trong development."},
            "days_ago": 14,
        },
        {
            "key": "demo-seed-remote-reset",
            "action": "charge_point.reset.accepted",
            "object_type": "charge_point",
            "object_id": "demo-reset-sample",
            "charge_point_code": "SIM-01",
            "details": {"reset_type": "Soft", "outcome": "Accepted", "demo": True},
            "days_ago": 2,
        },
        {
            "key": "demo-seed-session-review",
            "action": "session.review.required",
            "object_type": "charging_session",
            "object_id": "demo-anomaly-offline",
            "charge_point_code": "SIM-03",
            "details": {"reason": "offline", "demo": True},
            "days_ago": 6,
        },
    )
    for spec in samples:
        if spec["charge_point_code"] and spec["charge_point_code"] not in point_codes:
            continue
        exists = (
            db.query(AuditLog.id)
            .filter(
                AuditLog.action == spec["action"],
                AuditLog.object_type == spec["object_type"],
                AuditLog.object_id == spec["object_id"],
            )
            .first()
        )
        if exists:
            continue
        db.add(
            AuditLog(
                actor_name="Dữ liệu mẫu CSMS",
                action=spec["action"],
                object_type=spec["object_type"],
                object_id=spec["object_id"],
                charge_point_code=spec["charge_point_code"],
                details=spec["details"],
                created_at=now - timedelta(days=spec["days_ago"]),
            )
        )
        counts["audit_logs"] += 1


def seed_data(db: Session | None = None) -> None:
    """Add missing demo rows only; never replace existing user data."""
    if settings.APP_ENV != "development":
        print("Demo seed skipped: APP_ENV is not development.")
        return

    owns_session = db is None
    db = db or SessionLocal()
    counts = {
        "stations": 0,
        "charge_points": 0,
        "connectors": 0,
        "connector_errors": 0,
        "id_tags": 0,
        "sessions": 0,
        "audit_logs": 0,
    }
    try:
        owner = db.query(User).filter(User.email == "owner@csms.local").first()
        driver = db.query(User).filter(User.email == "driver@csms.local").first()
        if owner is None or driver is None:
            print("Demo seed skipped: required demo owner/driver is not present.")
            return

        now = datetime.now(UTC).replace(tzinfo=None)
        all_points: dict[str, ChargePoint] = {}
        for station_spec in STATIONS:
            station = _ensure_station(db, owner, station_spec, counts)
            all_points.update(
                _ensure_charge_points(db, station, station_spec["charge_points"], counts)
            )

        active_tag = _ensure_driver_tags(db, driver, counts)
        _ensure_sessions(db, driver, active_tag, all_points, now, counts)
        _ensure_audit_samples(db, now, set(all_points), counts)
        db.commit()
        summary = ", ".join(f"{amount} {name}" for name, amount in counts.items() if amount)
        print(f"Development demo seed ready. Newly added: {summary or 'no rows (already seeded)'}.")
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    seed_data()
