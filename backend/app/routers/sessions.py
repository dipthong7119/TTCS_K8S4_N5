"""Session history, anomaly review, and remote-stop APIs."""

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.models.station import Station
from app.models.user import User
from app.services.audit import ghi_nhat_ky
from app.services.connection_manager import manager
from app.services.ocpp_parser import OCPPError
from app.services.ocpp_status import is_charge_point_stale

router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(deny_unannotated_route)],
)

GLOBAL_SESSION_ROLES = ("admin", "operator", "accountant")
SESSION_VIEW_ROLES = (*GLOBAL_SESSION_ROLES, "station_owner", "driver")


def _role_names(user: User) -> set[str]:
    return {role.name for role in user.roles}


def _session_query(db: Session):
    return db.query(ChargingSession)


def _calculate_live_kwh(item: ChargingSession, reading: MeterValue | None) -> float | None:
    if reading is None:
        return None
    value = float(reading.value)
    if (reading.unit or "Wh").lower() == "kwh":
        value -= item.meter_start_wh / 1000
    else:
        value = (value - item.meter_start_wh) / 1000
    return value if value >= 0 else None


def _serialize_session(
    db: Session,
    item: ChargingSession,
    *,
    load_latest_meter: bool = True,
    latest_meter: MeterValue | None = None,
) -> dict:
    now = datetime.now(UTC).replace(tzinfo=None)
    ended = item.ended_at
    duration = int(((ended or now) - item.started_at).total_seconds())
    live_kwh = None
    if ended is None and load_latest_meter:
        latest_energy = (
            db.query(MeterValue)
            .filter(
                MeterValue.session_id == item.id,
                MeterValue.measurand == "Energy.Active.Import.Register",
            )
            .order_by(MeterValue.measured_at.desc(), MeterValue.id.desc())
            .first()
        )
        live_kwh = _calculate_live_kwh(item, latest_energy)
    elif ended is None:
        live_kwh = _calculate_live_kwh(item, latest_meter)
    return {
        "id": item.id,
        "charge_point_code": item.charge_point_code,
        "station_name": item.station_name,
        "connector_number": item.connector_number,
        "driver_id": item.user_id,
        "driver_name": item.driver_name,
        "started_at": item.started_at.isoformat() + "Z",
        "ended_at": ended.isoformat() + "Z" if ended else None,
        "duration_seconds": max(duration, 0),
        "meter_start_wh": item.meter_start_wh,
        "meter_stop_wh": item.meter_stop_wh,
        "kwh": float(item.energy_kwh) if item.energy_kwh is not None else None,
        "live_kwh": live_kwh,
        "cost_vnd": item.invoice.total_vnd if item.invoice else None,
        "invoice_segments": item.invoice.segments if item.invoice else None,
        "invoice_rounding_rule": item.invoice.rounding_rule if item.invoice else None,
        "invoice_subscription_id": item.invoice.subscription_id if item.invoice else None,
        "invoice_package_name": item.invoice.package_name if item.invoice else None,
        "status": item.status,
        "stop_reason": item.stop_reason,
        "remote_stop_requested_at": item.remote_stop_requested_at.isoformat() + "Z"
        if item.remote_stop_requested_at
        else None,
        "anomaly_reason": item.anomaly_reason,
        "is_demo": item.is_demo,
    }


def _apply_visibility(query, user: User):
    roles = _role_names(user)
    if roles.intersection(GLOBAL_SESSION_ROLES):
        return query
    if "station_owner" in roles:
        return query.join(Station, ChargingSession.station_id == Station.id).filter(
            Station.owner_id == user.id
        )
    return query.filter(ChargingSession.user_id == user.id)


def _list_sessions(
    db: Session,
    user: User,
    *,
    page: int,
    page_size: int,
    days: int | None,
    status_filter: str | None,
):
    query = _apply_visibility(_session_query(db), user)
    if days is not None:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        query = query.filter(ChargingSession.started_at >= cutoff)
    if status_filter:
        query = query.filter(ChargingSession.status == status_filter)

    total = query.count()
    # SQL SUM over nullable energy values returns None when no sessions have kWh.
    aggregate = query.with_entities(func.sum(ChargingSession.energy_kwh)).scalar()
    aggregate_cost = (
        query.outerjoin(ChargingInvoice, ChargingInvoice.session_id == ChargingSession.id)
        .with_entities(func.coalesce(func.sum(ChargingInvoice.total_vnd), 0))
        .scalar()
    )
    rows = (
        query.order_by(ChargingSession.started_at.desc(), ChargingSession.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_serialize_session(db, item) for item in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_kwh": float(aggregate) if aggregate is not None else 0.0,
        "total_cost_vnd": int(aggregate_cost or 0),
    }


@router.get("/mine", dependencies=[Depends(require_role("driver"))])
async def list_my_sessions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    days: int = Query(30, ge=1, le=3650),
    status_filter: str | None = Query(None, alias="status", max_length=20),
):
    return _list_sessions(
        db, current_user, page=page, page_size=page_size, days=days, status_filter=status_filter
    )


@router.get("/current", dependencies=[Depends(require_role("driver"))])
async def get_current_driver_session(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    latest_meter_id = (
        db.query(MeterValue.id)
        .filter(
            MeterValue.session_id == ChargingSession.id,
            MeterValue.measurand == "Energy.Active.Import.Register",
        )
        .order_by(MeterValue.measured_at.desc(), MeterValue.id.desc())
        .limit(1)
        .correlate(ChargingSession)
        .scalar_subquery()
    )
    row = (
        db.query(ChargingSession, MeterValue)
        # The serializer reads item.invoice; eager-load it to keep this API to
        # one SQL query alongside the correlated latest-meter lookup.
        .options(joinedload(ChargingSession.invoice))
        .outerjoin(MeterValue, MeterValue.id == latest_meter_id)
        .filter(ChargingSession.user_id == current_user.id, ChargingSession.ended_at.is_(None))
        .order_by(ChargingSession.started_at.desc(), ChargingSession.id.desc())
        .first()
    )
    if row is None:
        return Response(status_code=204)
    item, latest_meter = row
    return _serialize_session(db, item, load_latest_meter=False, latest_meter=latest_meter)


@router.get("", dependencies=[Depends(require_role(*SESSION_VIEW_ROLES))])
async def list_sessions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    days: int = Query(30, ge=1, le=3650),
    status_filter: str | None = Query(None, alias="status", max_length=20),
):
    return _list_sessions(
        db, current_user, page=page, page_size=page_size, days=days, status_filter=status_filter
    )


@router.get("/anomalies", dependencies=[Depends(require_role("admin", "operator"))])
async def list_anomalies(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    days: str = Query("30", max_length=10),
    reason: str | None = Query(None, max_length=30),
):
    base_query = _session_query(db).outerjoin(
        ChargePoint, ChargingSession.charge_point_id == ChargePoint.id
    ).filter(
        ChargingSession.status.in_(("anomaly", "needs_review"))
    )
    if days != "all":
        try:
            day_count = int(days)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="days phải là số ngày hoặc all") from exc
        if not 1 <= day_count <= 3650:
            raise HTTPException(status_code=422, detail="days nằm ngoài khoảng cho phép")
        base_query = base_query.filter(
            ChargingSession.started_at >= datetime.now(UTC).replace(tzinfo=None) - timedelta(days=day_count)
        )

    query = base_query

    if reason == "negative_kwh":
        query = query.filter(ChargingSession.anomaly_reason == "negative_kwh")
    elif reason == "offline":
        query = query.filter(ChargingSession.anomaly_reason == "offline")
    elif reason:
        # no_stop/orphan are not generated until their corresponding event rules exist.
        query = query.filter(ChargingSession.anomaly_reason == reason)

    total = query.count()
    negative_kwh_count = base_query.filter(
        ChargingSession.anomaly_reason == "negative_kwh"
    ).count()
    offline_count = base_query.filter(ChargingSession.anomaly_reason == "offline").count()
    rows = (
        query.add_columns(ChargePoint.status)
        .order_by(ChargingSession.started_at.desc(), ChargingSession.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    page_rows = []
    for item, point_status in rows:
        value = _serialize_session(db, item)
        value["anomaly_reason"] = item.anomaly_reason or (
            "offline" if item.ended_at is None else "needs_review"
        )
        value["charge_point_status"] = point_status
        page_rows.append(value)
    return {
        "items": page_rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "offline_count": offline_count,
        "negative_kwh_count": negative_kwh_count,
    }


@router.get("/{session_id}", dependencies=[Depends(require_role(*SESSION_VIEW_ROLES))])
async def get_session(
    session_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    item = _session_query(db).filter(ChargingSession.id == session_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên sạc")
    roles = _role_names(current_user)
    if roles.intersection(GLOBAL_SESSION_ROLES):
        return _serialize_session(db, item)
    if "station_owner" in roles:
        station = db.query(Station).filter(Station.id == item.station_id).first()
        if station is None or station.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Không có quyền xem phiên sạc này")
    elif item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền xem phiên sạc này")
    return _serialize_session(db, item)


@router.post(
    "/{session_id}/remote-stop",
    dependencies=[Depends(require_role("admin", "operator"))],
)
async def remote_stop_session(
    session_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    item = _session_query(db).filter(ChargingSession.id == session_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên sạc")
    if item.ended_at is not None:
        raise HTTPException(status_code=409, detail="Phiên sạc đã kết thúc, không thể dừng từ xa")

    point = db.query(ChargePoint).filter(ChargePoint.id == item.charge_point_id).first()
    if (
        point is None
        or point.code not in manager.active_connections
        or point.status != "online"
        or is_charge_point_stale(point.last_seen_at)
    ):
        raise HTTPException(
            status_code=409, detail="Trụ sạc đang ngoại tuyến, không thể gửi lệnh dừng."
        )

    try:
        result = await manager.send_call(
            point.code,
            "RemoteStopTransaction",
            {"transactionId": item.id},
            timeout=settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        ghi_nhat_ky(
            db,
            action="remote_stop.failed",
            object_type="charging_session",
            object_id=item.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            charge_point_code=point.code,
            details={"outcome": "timeout"},
        )
        db.commit()
        raise HTTPException(
            status_code=504,
            detail="Trụ không phản hồi lệnh dừng từ xa trong thời gian chờ.",
        ) from exc
    except ConnectionError as exc:
        ghi_nhat_ky(
            db,
            action="remote_stop.failed",
            object_type="charging_session",
            object_id=item.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            charge_point_code=point.code,
            details={"outcome": "disconnected"},
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Trụ sạc đã ngắt kết nối trước khi nhận lệnh dừng.",
        ) from exc
    except OCPPError as exc:
        ghi_nhat_ky(
            db,
            action="remote_stop.failed",
            object_type="charging_session",
            object_id=item.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            charge_point_code=point.code,
            details={"outcome": "call_error"},
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="Không gửi được lệnh dừng tới trụ.",
        ) from exc

    accepted = result.get("status") == "Accepted"
    if accepted:
        db.refresh(item)
        if item.ended_at is None:
            item.remote_stop_requested_at = datetime.now(UTC).replace(tzinfo=None)
    ghi_nhat_ky(
        db,
        action="remote_stop.accepted" if accepted else "remote_stop.rejected",
        object_type="charging_session",
        object_id=item.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_name=current_user.full_name,
        charge_point_code=point.code,
        details={"outcome": result.get("status", "unknown")},
    )
    db.commit()
    if not accepted:
        raise HTTPException(
            status_code=502,
            detail="Trụ không chấp nhận lệnh dừng từ xa (Rejected).",
        )
    if item.ended_at is None:
        station = db.query(Station).filter(Station.id == item.station_id).first()
        from app.routers.monitoring import notify_session_change

        notify_session_change(item.user_id, station.owner_id if station else None, item.id)
    return {"status": "Accepted", "message": "Đã gửi lệnh; phiên sẽ đóng khi trụ báo StopTransaction."}
