import asyncio

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload
from sse_starlette.sse import EventSourceResponse

from app.core.deps import deny_unannotated_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.models.user import User
from app.services.ownership import filter_by_owner

router = APIRouter(dependencies=[Depends(deny_unannotated_route)])

# T-25: Kênh đẩy trạng thái xuống trình duyệt
# Chúng ta sẽ giữ một danh sách các kết nối chờ
sse_clients = []

def notify_status_change(station_id: int, charge_points_data: list, owner_id: int | None = None):
    """
    Hàm này dùng để đẩy sự kiện xuống các client khi trạng thái thay đổi.
    charge_points_data là dữ liệu charge_points đã được cập nhật.
    """
    import json
    data = json.dumps({
        "station_id": station_id,
        "charge_points": charge_points_data
    })
    for subscriber in sse_clients:
        if subscriber["global_access"] or subscriber["owner_id"] == owner_id:
            subscriber["queue"].put_nowait({"event": "status_update", "data": data})

@router.get("/sse", dependencies=[Depends(require_role("admin", "station_owner", "operator"))])
async def monitoring_sse(
    request: Request,
    current_user: User = Depends(require_role("admin", "station_owner", "operator")),
):
    """T-25: SSE endpoint"""
    q = asyncio.Queue()
    roles = [role.name for role in current_user.roles]
    subscriber = {
        "queue": q,
        "owner_id": current_user.id,
        "global_access": bool({"admin", "operator"}.intersection(roles)),
    }
    sse_clients.append(subscriber)
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Wait for message with a timeout to send ping
                    message = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield message
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "ping"}
        finally:
            if subscriber in sse_clients:
                sse_clients.remove(subscriber)
                
    return EventSourceResponse(event_generator())

@router.get("/tree")
async def get_monitoring_tree(
    current_user: User = Depends(require_role("admin", "station_owner", "operator")),
    db: Session = Depends(get_db)
):
    """
    T-23: Truy vấn một lần trả về cây trạm–trụ–đầu nối đã lọc theo quyền.
    """
    query = db.query(Station).options(
        joinedload(Station.charge_points).joinedload(ChargePoint.connectors)
    )

    roles = [r.name for r in current_user.roles]
    query = filter_by_owner(query, current_user.id, roles)
    
    stations = query.all()
    
    result = []
    for st in stations:
        cp_list = []
        for cp in st.charge_points:
            conn_list = []
            for cn in cp.connectors:
                conn_list.append({
                    "id": cn.id,
                    "connector_id": cn.connector_id,
                    "status": cn.status,
                    "error_code": cn.error_code,
                    "updated_at": cn.updated_at.isoformat()
                })
            cp_list.append({
                "id": cp.id,
                "code": cp.code,
                "status": cp.status,
                "vendor": cp.vendor,
                "model": cp.model,
                "firmware_version": cp.firmware_version,
                "last_seen_at": cp.last_seen_at.isoformat() if cp.last_seen_at else None,
                "connectors": conn_list
            })
        result.append({
            "id": st.id,
            "name": st.name,
            "address": st.address,
            "latitude": st.latitude,
            "longitude": st.longitude,
            "status": st.status,
            "charge_points": cp_list
        })
        
    return result
