"""Owner API for SCRUM-83 station power-capacity bands."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.station import Station
from app.models.station_power_band import StationPowerBand
from app.schemas.power_capacity_band import (
    PowerCapacityBandInput,
    PowerCapacityBandResponse,
)
from app.services.audit import append_audit
from app.services.ownership import get_station_for_user
from app.services.power_capacity_bands import (
    PowerBandOverlapError,
    ensure_no_power_band_overlap,
    station_power_timezone,
)

router = APIRouter(
    prefix="/stations",
    tags=["station power capacity bands"],
    dependencies=[Depends(deny_unannotated_route)],
)
OWNER_ROLES = ["station_owner", "admin"]


def _authorize_station(db: Session, station_id: int, current_user: CurrentUser):
    roles = [role.name for role in current_user.roles]
    station = get_station_for_user(
        db, station_id, current_user.id, roles, "manage_power_capacity_bands"
    )
    return station, roles


def _lock_station(db: Session, station_id: int) -> None:
    db.query(Station.id).filter(Station.id == station_id).with_for_update().first()


def _response(
    db: Session, band: StationPowerBand, timezone_name: str | None = None
) -> dict:
    return {
        "id": band.id,
        "station_id": band.station_id,
        "start_minute": band.start_minute,
        "end_minute": band.end_minute,
        "power_limit_kw": band.power_limit_kw,
        "timezone_name": timezone_name or station_power_timezone(db, band.station_id),
    }


def _write_audit(
    db: Session,
    *,
    action: str,
    band: StationPowerBand,
    current_user: CurrentUser,
) -> None:
    append_audit(
        db,
        action=action,
        object_type="station_power_band",
        object_id=band.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_name=current_user.full_name,
        details={
            "station_id": band.station_id,
            "start_minute": band.start_minute,
            "end_minute": band.end_minute,
            "power_limit_kw": str(band.power_limit_kw),
        },
    )


def _handle_band_conflict(db: Session, exc: Exception) -> HTTPException:
    db.rollback()
    if isinstance(exc, PowerBandOverlapError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(
        status_code=409,
        detail="Khung giờ trùng giờ bắt đầu với một khung công suất khác",
    )


def _schedule_rebalance(station_id: int) -> None:
    from app.services.power_allocation import schedule_station_rebalance

    schedule_station_rebalance(station_id)


@router.get(
    "/{station_id}/power-capacity-bands",
    response_model=list[PowerCapacityBandResponse],
    dependencies=[Depends(require_role(*OWNER_ROLES))],
)
async def list_power_capacity_bands(
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    _authorize_station(db, station_id, current_user)
    bands = (
        db.query(StationPowerBand)
        .filter(StationPowerBand.station_id == station_id)
        .order_by(StationPowerBand.start_minute, StationPowerBand.id)
        .all()
    )
    timezone_name = station_power_timezone(db, station_id)
    return [_response(db, band, timezone_name) for band in bands]


@router.post(
    "/{station_id}/power-capacity-bands",
    response_model=PowerCapacityBandResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(*OWNER_ROLES))],
)
async def create_power_capacity_band(
    station_id: int,
    body: PowerCapacityBandInput,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    station, _roles = _authorize_station(db, station_id, current_user)
    _lock_station(db, station.id)
    try:
        ensure_no_power_band_overlap(
            db, station.id, body.start_minute, body.end_minute
        )
        band = StationPowerBand(
            station_id=station.id,
            start_minute=body.start_minute,
            end_minute=body.end_minute,
            power_limit_kw=body.power_limit_kw,
        )
        db.add(band)
        db.flush()
        _write_audit(
            db,
            action="station.power_capacity_band.created",
            band=band,
            current_user=current_user,
        )
        db.commit()
        db.refresh(band)
    except (PowerBandOverlapError, IntegrityError) as exc:
        raise _handle_band_conflict(db, exc) from None
    _schedule_rebalance(station.id)
    return _response(db, band)


@router.put(
    "/{station_id}/power-capacity-bands/{band_id}",
    response_model=PowerCapacityBandResponse,
    dependencies=[Depends(require_role(*OWNER_ROLES))],
)
async def update_power_capacity_band(
    station_id: int,
    band_id: int,
    body: PowerCapacityBandInput,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    station, _roles = _authorize_station(db, station_id, current_user)
    _lock_station(db, station.id)
    band = (
        db.query(StationPowerBand)
        .filter(
            StationPowerBand.id == band_id,
            StationPowerBand.station_id == station.id,
        )
        .first()
    )
    if band is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khung công suất")
    try:
        ensure_no_power_band_overlap(
            db,
            station.id,
            body.start_minute,
            body.end_minute,
            exclude_band_id=band.id,
        )
        band.start_minute = body.start_minute
        band.end_minute = body.end_minute
        band.power_limit_kw = body.power_limit_kw
        _write_audit(
            db,
            action="station.power_capacity_band.updated",
            band=band,
            current_user=current_user,
        )
        db.commit()
        db.refresh(band)
    except (PowerBandOverlapError, IntegrityError) as exc:
        raise _handle_band_conflict(db, exc) from None
    _schedule_rebalance(station.id)
    return _response(db, band)


@router.delete(
    "/{station_id}/power-capacity-bands/{band_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(*OWNER_ROLES))],
)
async def delete_power_capacity_band(
    station_id: int,
    band_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    station, _roles = _authorize_station(db, station_id, current_user)
    _lock_station(db, station.id)
    band = (
        db.query(StationPowerBand)
        .filter(
            StationPowerBand.id == band_id,
            StationPowerBand.station_id == station.id,
        )
        .first()
    )
    if band is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khung công suất")
    _write_audit(
        db,
        action="station.power_capacity_band.deleted",
        band=band,
        current_user=current_user,
    )
    db.delete(band)
    db.commit()
    _schedule_rebalance(station.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
