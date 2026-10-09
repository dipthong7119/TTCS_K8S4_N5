"""Đổi, đọc và lưu cấu hình OCPP của trụ sạc."""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models.charge_point import ChargePoint
from app.models.charge_point_configuration import ChargePointConfiguration
from app.ocpp.config_keys import CONFIGURATION_KEYS, validate_change
from app.services.connection_manager import manager
from app.services.ocpp_parser import OCPPError

logger = logging.getLogger(__name__)


class ConfigurationOperationError(Exception):
    """Lỗi nghiệp vụ có mã HTTP dùng bởi router."""

    def __init__(
        self,
        http_status: int,
        code: str,
        message: str,
        *,
        last_saved: dict[str, dict[str, Any]] | None = None,
        ocpp_error_code: str | None = None,
    ):
        self.http_status = http_status
        self.code = code
        self.message = message
        self.last_saved = last_saved
        self.ocpp_error_code = ocpp_error_code
        super().__init__(message)

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.ocpp_error_code is not None:
            payload["ocpp_error_code"] = self.ocpp_error_code
        if self.last_saved:
            payload["last_saved"] = self.last_saved
        return payload


_configuration_locks: dict[tuple[str, str], asyncio.Lock] = {}
_configuration_locks_guard = asyncio.Lock()


@dataclass(frozen=True)
class ChargePointSnapshot:
    id: int
    status: str


@asynccontextmanager
async def _lock_keys(charge_point_code: str, keys: list[str]) -> AsyncIterator[None]:
    """Tuần tự hóa lệnh theo từng trụ và khóa cấu hình."""
    locks: list[asyncio.Lock] = []
    async with _configuration_locks_guard:
        for key in sorted(set(keys)):
            lock_key = (charge_point_code, key)
            locks.append(_configuration_locks.setdefault(lock_key, asyncio.Lock()))
    acquired: list[asyncio.Lock] = []
    try:
        for lock in locks:
            await lock.acquire()
            acquired.append(lock)
        yield
    finally:
        for lock in reversed(acquired):
            lock.release()


def _now_utc_naive() -> datetime:
    """Dùng UTC không timezone để tương thích DateTime hiện có."""
    return datetime.now(UTC).replace(tzinfo=None)


def _charge_point_and_saved(
    db: Session,
    charge_point_code: str,
    keys: list[str],
) -> tuple[ChargePointSnapshot, dict[str, dict[str, Any]]]:
    point = db.query(ChargePoint).filter_by(code=charge_point_code).first()
    if point is None:
        db.rollback()
        raise ConfigurationOperationError(404, "charge_point_not_found", "Không tìm thấy trụ sạc")
    point_snapshot = ChargePointSnapshot(id=point.id, status=point.status)

    rows = db.execute(
        select(ChargePointConfiguration).where(
            ChargePointConfiguration.charge_point_id == point.id,
            ChargePointConfiguration.key.in_(keys),
        )
    ).scalars().all()
    saved = {
        row.key: {
            "value": row.value,
            "status": row.status,
            "confirmed_at": row.confirmed_at.isoformat() + "Z",
        }
        for row in rows
    }
    db.rollback()
    return point_snapshot, saved


def _ensure_live_connection(point: ChargePointSnapshot, charge_point_code: str) -> None:
    if point.status != "online" or charge_point_code not in manager.active_connections:
        raise ConfigurationOperationError(
            409,
            "charge_point_offline",
            "Trụ sạc đang ngoại tuyến, không thể đổi cấu hình.",
        )


def _upsert_configuration(
    db: Session,
    *,
    charge_point_id: int,
    key: str,
    value: str,
    status: str,
) -> None:
    """Ghi một câu upsert trên SQLite hoặc PostgreSQL."""
    dialect = db.get_bind().dialect.name
    insert = sqlite_insert if dialect == "sqlite" else postgresql_insert
    table = ChargePointConfiguration.__table__
    statement = insert(table).values(
        charge_point_id=charge_point_id,
        key=key,
        value=value,
        status=status,
        confirmed_at=_now_utc_naive(),
    )
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.charge_point_id, table.c.key],
        set_={
            "value": statement.excluded.value,
            "status": statement.excluded.status,
            "confirmed_at": statement.excluded.confirmed_at,
        },
    )
    db.execute(statement)


def _log_change(
    *,
    actor_id: int,
    charge_point_code: str,
    key: str,
    old_value: str | None,
    new_value: str,
    outcome: str,
) -> None:
    """Điểm thay thế sau này bằng hàm audit T-57."""
    logger.info(
        "Charge point configuration change: actor_id=%s cp=%s key=%s old=%s new=%s result=%s",
        actor_id,
        charge_point_code,
        key,
        old_value,
        new_value,
        outcome,
    )


async def change_configuration(
    db: Session,
    charge_point_code: str,
    key: str,
    raw_value: object,
    actor_id: int,
) -> dict[str, Any]:
    """Đổi đúng một khóa rồi chỉ lưu khi trụ xác nhận."""
    value_int = validate_change(key, raw_value)
    value = str(value_int)
    async with _lock_keys(charge_point_code, [key]):
        point, saved = _charge_point_and_saved(db, charge_point_code, [key])
        old_value = saved.get(key, {}).get("value")
        try:
            _ensure_live_connection(point, charge_point_code)
            result = await manager.send_call(
                charge_point_code,
                "ChangeConfiguration",
                {"key": key, "value": value},
                timeout=settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS,
            )
        except ConfigurationOperationError as exc:
            _log_change(
                actor_id=actor_id,
                charge_point_code=charge_point_code,
                key=key,
                old_value=old_value,
                new_value=value,
                outcome=exc.code,
            )
            raise
        except asyncio.TimeoutError as exc:
            _log_change(
                actor_id=actor_id,
                charge_point_code=charge_point_code,
                key=key,
                old_value=old_value,
                new_value=value,
                outcome="timeout",
            )
            raise ConfigurationOperationError(
                504, "configuration_timeout", "Trụ không phản hồi trong thời gian chờ."
            ) from exc
        except ConnectionError as exc:
            _log_change(
                actor_id=actor_id,
                charge_point_code=charge_point_code,
                key=key,
                old_value=old_value,
                new_value=value,
                outcome="disconnected",
            )
            raise ConfigurationOperationError(
                409, "charge_point_offline", "Trụ đã ngắt kết nối trước khi trả lời."
            ) from exc
        except OCPPError as exc:
            _log_change(
                actor_id=actor_id,
                charge_point_code=charge_point_code,
                key=key,
                old_value=old_value,
                new_value=value,
                outcome="call_error",
            )
            raise ConfigurationOperationError(
                502,
                "ocpp_call_error",
                "Trụ trả về CALLERROR khi đổi cấu hình.",
                ocpp_error_code=exc.error_code,
            ) from exc

        status_value = result.get("status") if isinstance(result, dict) else None
        if not isinstance(status_value, str) or status_value not in {
            "Accepted",
            "RebootRequired",
        }:
            outcomes = {
                "Rejected": (502, "configuration_rejected", "Trụ từ chối cấu hình."),
                "NotSupported": (
                    501,
                    "configuration_not_supported",
                    "Trụ không hỗ trợ khóa cấu hình này.",
                ),
            }
            http_status, code, message = outcomes.get(
                status_value if isinstance(status_value, str) else None,
                (502, "invalid_charge_point_response", "Trụ trả phản hồi cấu hình không hợp lệ."),
            )
            _log_change(
                actor_id=actor_id,
                charge_point_code=charge_point_code,
                key=key,
                old_value=old_value,
                new_value=value,
                outcome=str(status_value or "invalid_response"),
            )
            raise ConfigurationOperationError(http_status, code, message)

        stored_status = "applied" if status_value == "Accepted" else "reboot_required"
        _upsert_configuration(
            db,
            charge_point_id=point.id,
            key=key,
            value=value,
            status=stored_status,
        )
        db.commit()
        _log_change(
            actor_id=actor_id,
            charge_point_code=charge_point_code,
            key=key,
            old_value=old_value,
            new_value=value,
            outcome=stored_status,
        )
        return {
            "status": stored_status,
            "value": value_int,
            "reboot_required": stored_status == "reboot_required",
            "verified": None,
        }


def get_effective_heartbeat_interval(db: Session, charge_point: ChargePoint) -> int:
    """Ưu tiên nhịp tim đã áp dụng; nếu chưa có thì dùng giá trị chung."""
    row = db.query(ChargePointConfiguration.value).filter_by(
        charge_point_id=charge_point.id,
        key="HeartbeatInterval",
        status="applied",
    ).first()
    if row is None:
        return settings.OCPP_HEARTBEAT_INTERVAL_SECONDS
    try:
        return validate_change("HeartbeatInterval", row.value)
    except ValueError:
        logger.warning("Invalid stored HeartbeatInterval: cp=%s", charge_point.code)
        return settings.OCPP_HEARTBEAT_INTERVAL_SECONDS


def activate_reboot_required_configurations(db: Session, charge_point_id: int) -> None:
    """BootNotification Accepted xác nhận cấu hình chờ khởi động lại đã có hiệu lực."""
    db.execute(
        update(ChargePointConfiguration)
        .where(
            ChargePointConfiguration.charge_point_id == charge_point_id,
            ChargePointConfiguration.status == "reboot_required",
        )
        .values(status="applied")
    )


async def read_configuration(
    db: Session,
    charge_point_code: str,
    keys: list[str] | None = None,
) -> dict[str, Any]:
    """Đọc cấu hình thật, chỉ để lộ các khóa trong allowlist."""
    requested = list(CONFIGURATION_KEYS) if keys is None else list(dict.fromkeys(keys))
    invalid = [key for key in requested if key not in CONFIGURATION_KEYS]
    if invalid:
        raise ConfigurationOperationError(
            422,
            "unknown_key",
            "Chỉ được đọc các khóa cấu hình nằm trong danh sách cho phép.",
        )
    if not requested:
        requested = list(CONFIGURATION_KEYS)

    async with _lock_keys(charge_point_code, requested):
        point, saved = _charge_point_and_saved(db, charge_point_code, requested)
        try:
            _ensure_live_connection(point, charge_point_code)
        except ConfigurationOperationError as exc:
            exc.last_saved = saved
            raise

        try:
            result = await manager.send_call(
                charge_point_code,
                "GetConfiguration",
                {"key": requested},
                timeout=settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise ConfigurationOperationError(
                504,
                "configuration_timeout",
                "Trụ không phản hồi trong thời gian chờ.",
                last_saved=saved,
            ) from exc
        except ConnectionError as exc:
            raise ConfigurationOperationError(
                409,
                "charge_point_offline",
                "Trụ đã ngắt kết nối trước khi trả lời.",
                last_saved=saved,
            ) from exc
        except OCPPError as exc:
            raise ConfigurationOperationError(
                502,
                "ocpp_call_error",
                "Trụ trả về CALLERROR khi đọc cấu hình.",
                last_saved=saved,
                ocpp_error_code=exc.error_code,
            ) from exc

        entries = result.get("configurationKey") if isinstance(result, dict) else None
        if not isinstance(entries, list):
            raise ConfigurationOperationError(
                502,
                "invalid_charge_point_response",
                "Trụ trả phản hồi GetConfiguration không hợp lệ.",
                last_saved=saved,
            )

        safe_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            if key not in requested:
                continue
            value = entry.get("value")
            readonly = entry.get("readonly")
            if not isinstance(value, str) or not isinstance(readonly, bool):
                continue

            saved_value = saved.get(key, {}).get("value")
            verified: bool | None = None
            if saved_value is not None:
                try:
                    verified = validate_change(key, value) == int(saved_value)
                except (ValueError, TypeError):
                    verified = False
                if not verified:
                    logger.warning(
                        "Charge point configuration mismatch: cp=%s key=%s",
                        charge_point_code,
                        key,
                    )
            safe_entries.append(
                {
                    "key": key,
                    "readonly": readonly,
                    "value": value,
                    "requested_value": saved_value,
                    "verified": verified,
                }
            )

        raw_unknown = result.get("unknownKey", [])
        allowed_requested = set(requested)
        unknown_keys = (
            sorted({key for key in raw_unknown if isinstance(key, str) and key in allowed_requested})
            if isinstance(raw_unknown, list)
            else []
        )
        return {
            "charge_point": charge_point_code,
            "configurationKey": safe_entries,
            "unknownKey": unknown_keys,
            "last_saved": saved,
        }
