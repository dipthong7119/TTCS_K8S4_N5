"""Owner API for station and connector power limits (SCRUM-80)."""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.schemas.power_capacity import (
    ConnectorPowerCapacityResponse,
    StationPowerCapacityResponse,
    StationPowerCapacityUpdate,
)
from app.services.audit import append_audit
from app.services.ownership import get_station_for_user

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/stations",
    tags=["station power capacity"],
    dependencies=[Depends(deny_unannotated_route)],
)


def _capacity_response(db: Session, station: Station) -> dict:
    rows = (
        db.query(ChargePoint.code, Connector.connector_id, Connector.rated_power_kw)
        .join(Connector, Connector.charge_point_id == ChargePoint.id)
        .filter(ChargePoint.station_id == station.id)
        .order_by(ChargePoint.code, Connector.connector_id)
        .all()
    )
    known_ratings = [Decimal(rating) for _code, _number, rating in rows if rating is not None]
    nominal_power = sum(known_ratings, Decimal(0))
    limit = Decimal(station.power_limit_kw) if station.power_limit_kw is not None else None
    return {
        "station_id": station.id,
        "power_limit_kw": limit,
        "nominal_power_kw": nominal_power,
        "over_subscribed": limit is not None and nominal_power > limit,
        "missing_connector_count": len(rows) - len(known_ratings),
        "connectors": [
            ConnectorPowerCapacityResponse(
                charge_point_code=code,
                connector_id=connector_number,
                rated_power_kw=Decimal(rating) if rating is not None else None,
            )
            for code, connector_number, rating in rows
        ],
    }


@router.get(
    "/{station_id}/power-capacity",
    response_model=StationPowerCapacityResponse,
    dependencies=[Depends(require_role("station_owner", "admin"))],
)
async def get_power_capacity(
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    station = get_station_for_user(
        db,
        station_id,
        current_user.id,
        [role.name for role in current_user.roles],
        "view_power_capacity",
    )
    return _capacity_response(db, station)


@router.put(
    "/{station_id}/power-capacity",
    response_model=StationPowerCapacityResponse,
    dependencies=[Depends(require_role("station_owner", "admin"))],
)
async def update_power_capacity(
    station_id: int,
    body: StationPowerCapacityUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    station = get_station_for_user(
        db,
        station_id,
        current_user.id,
        [role.name for role in current_user.roles],
        "update_power_capacity",
    )
    rows = (
        db.query(Connector, ChargePoint.code)
        .join(ChargePoint, ChargePoint.id == Connector.charge_point_id)
        .filter(ChargePoint.station_id == station.id)
        .all()
    )
    actual = {(code, connector.connector_id): connector for connector, code in rows}
    supplied = {}
    for item in body.connectors:
        key = (item.charge_point_code.strip(), item.connector_id)
        if key in supplied:
            raise HTTPException(status_code=422, detail="Đầu nối bị khai báo lặp")
        supplied[key] = item
    if set(supplied) != set(actual):
        raise HTTPException(
            status_code=422,
            detail="Cần khai báo công suất đúng một lần cho từng đầu nối của trạm",
        )

    station.power_limit_kw = body.power_limit_kw
    for key, connector in actual.items():
        connector.rated_power_kw = supplied[key].rated_power_kw
    nominal_power = sum(
        (item.rated_power_kw for item in supplied.values()), Decimal(0)
    )
    over_subscribed = nominal_power > body.power_limit_kw
    append_audit(
        db,
        action="station.power_capacity.updated",
        object_type="station",
        object_id=station.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_name=current_user.full_name,
        details={
            "power_limit_kw": str(body.power_limit_kw),
            "nominal_power_kw": str(nominal_power),
            "over_subscribed": over_subscribed,
            "connector_count": len(rows),
        },
    )
    db.commit()
    if over_subscribed:
        logger.warning(
            "Station is over-subscribed: station_id=%s nominal_power_kw=%s power_limit_kw=%s",
            station.id,
            nominal_power,
            station.power_limit_kw,
        )

    from app.services.power_allocation import schedule_station_rebalance

    schedule_station_rebalance(station.id)
    return _capacity_response(db, station)
