"""Role-filtered monitoring tree and Server-Sent Events (T-23–T-25)."""

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload
from sse_starlette.sse import EventSourceResponse

from app.core.deps import deny_unannotated_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.models.user import User
from app.services.ocpp_status import station_status_payload
from app.services.ownership import filter_by_owner

router = APIRouter(dependencies=[Depends(deny_unannotated_route)])
sse_clients: list[dict] = []
SSE_QUEUE_LIMIT = 10


def notify_status_change(station_id: int, charge_points_data: list, owner_id: int | None = None):
    data = json.dumps({"station_id": station_id, "charge_points": charge_points_data})
    event = {"event": "status_update", "data": data}
    for subscriber in tuple(sse_clients):
        if subscriber["global_access"] or subscriber["owner_id"] == owner_id:
            queue = subscriber["queue"]
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # A later tree refresh supplies authoritative state.
                continue


@router.get("/sse", dependencies=[Depends(require_role("admin", "station_owner", "operator"))])
async def monitoring_sse(
    request: Request,
    current_user: User = Depends(require_role("admin", "station_owner", "operator")),
):
    roles = [role.name for role in current_user.roles]
    subscriber = {
        "queue": asyncio.Queue(maxsize=SSE_QUEUE_LIMIT),
        "owner_id": current_user.id,
        "global_access": bool({"admin", "operator"}.intersection(roles)),
    }
    sse_clients.append(subscriber)

    async def event_generator():
        try:
            while not await request.is_disconnected():
                try:
                    yield await asyncio.wait_for(subscriber["queue"].get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "ping"}
        finally:
            if subscriber in sse_clients:
                sse_clients.remove(subscriber)

    return EventSourceResponse(event_generator())


@router.get("/tree")
async def get_monitoring_tree(
    current_user: User = Depends(require_role("admin", "station_owner", "operator")),
    db: Session = Depends(get_db),
):
    query = db.query(Station).options(
        joinedload(Station.charge_points).joinedload(ChargePoint.connectors)
    )
    roles = [role.name for role in current_user.roles]
    stations = filter_by_owner(query, current_user.id, roles).all()
    return [
        station_status_payload(station)
        for station in sorted(stations, key=lambda item: item.id)
    ]
