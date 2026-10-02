"""Remote charge point commands (S-16, T-34, T-35)."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint
from app.schemas.remote import ResetRequest
from app.services.audit import append_audit
from app.services.connection_manager import manager
from app.services.ocpp_handlers import publish_charge_point_status
from app.services.ocpp_parser import OCPPError
from app.services.ocpp_status import is_charge_point_stale

router = APIRouter(dependencies=[Depends(deny_unannotated_route)])
logger = logging.getLogger(__name__)


@router.post(
    "/charge_points/{code}/reset",
    dependencies=[Depends(require_role("admin", "operator"))],
)
async def reset_charge_point(
    code: str,
    payload: ResetRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    point = db.query(ChargePoint).filter(ChargePoint.code == code).first()
    if point is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy trụ sạc")
    if (
        code not in manager.active_connections
        or point.status != "online"
        or is_charge_point_stale(point.last_seen_at)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trụ sạc đang ngoại tuyến, không thể gửi lệnh.",
        )

    logger.info(
        "Operator requested charge point reset: actor_id=%s charge_point=%s reset_type=%s",
        current_user.id,
        code,
        payload.type,
    )

    def record_reset_outcome(action: str, outcome: str) -> None:
        append_audit(
            db,
            action=action,
            object_type="charge_point",
            object_id=point.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            charge_point_code=point.code,
            details={"reset_type": payload.type, "outcome": outcome},
        )
        db.commit()

    try:
        result = await manager.send_call(
            code,
            "Reset",
            {"type": payload.type},
            timeout=settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        record_reset_outcome("charge_point.reset.failed", "timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Trụ không phản hồi lệnh Reset trong thời gian chờ.",
        ) from exc
    except ConnectionError as exc:
        record_reset_outcome("charge_point.reset.failed", "disconnected")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trụ sạc đã ngắt kết nối trước khi nhận lệnh.",
        ) from exc
    except OCPPError as exc:
        record_reset_outcome("charge_point.reset.rejected", "call_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Trụ từ chối lệnh Reset.",
        ) from exc

    if result.get("status") != "Accepted":
        record_reset_outcome("charge_point.reset.rejected", result.get("status", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Trụ không chấp nhận lệnh Reset.",
        )
    point.status = "offline"
    for connector in point.connectors:
        connector.status = "unknown"
    append_audit(
        db,
        action="charge_point.reset.accepted",
        object_type="charge_point",
        object_id=point.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_name=current_user.full_name,
        charge_point_code=point.code,
        details={"reset_type": payload.type, "outcome": "Accepted"},
    )
    db.commit()
    publish_charge_point_status(db, point.id)
    return {"status": "Accepted", "message": "Trụ đã chấp nhận lệnh Reset."}
