from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload
from typing import List
from sse_starlette.sse import EventSourceResponse
import asyncio

from app.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.station import Station
from app.models.charge_point import ChargePoint, Connector
from app.services.ownership import filter_by_owner

router = APIRouter()

# T-25: Kênh đẩy trạng thái xuống trình duyệt
# Chúng ta sẽ giữ một danh sách các kết nối chờ
import queue
sse_clients = []

def notify_status_change(station_id: int, charge_points_data: list):
    """
    Hàm này dùng để đẩy sự kiện xuống các client khi trạng thái thay đổi.
    charge_points_data là dữ liệu charge_points đã được cập nhật.
    """
    import json
    data = json.dumps({
        "station_id": station_id,
        "charge_points": charge_points_data
    })
    for q in sse_clients:
        try:
            q.put_nowait({"event": "status_update", "data": data})
        except Exception:
            pass

@router.get("/sse")
async def monitoring_sse(request: Request):
    """T-25: SSE endpoint"""
    q = asyncio.Queue()
    sse_clients.append(q)
    
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
            if q in sse_clients:
                sse_clients.remove(q)
                
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

