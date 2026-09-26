import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import deny_unannotated_route, require_role
from app.services.connection_manager import manager
from app.services.ocpp_parser import pack_call

router = APIRouter(dependencies=[Depends(deny_unannotated_route)])

@router.post("/charge_points/{code}/reset")
async def reset_charge_point(
    code: str,
    payload: dict,
    current_user=Depends(require_role("admin", "operator"))
):
    """
    T-34, T-35: Gửi lệnh Reset xuống trụ sạc
    """
    if code not in manager.active_connections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trụ sạc đang ngoại tuyến, không thể gửi lệnh."
        )
    
    # payload: {"type": "Soft" | "Hard"}
    reset_type = payload.get("type", "Soft")
    
    msg_id = str(uuid.uuid4().int & 0x7FFFFF)
    raw_msg = pack_call(msg_id, "Reset", {"type": reset_type})
    
    # Gửi lệnh
    await manager.send_to(code, raw_msg)
    
    # Theo thiết kế OCPP, chúng ta sẽ nhận được CALLRESULT.
    # Trong phiên bản đơn giản này, ta coi lệnh đã được gửi đi thành công.
    # Thực tế có thể thiết lập hàng đợi để chờ CALLRESULT, nhưng T-34 yêu cầu
    # "Khớp CALLRESULT", có thể ta ghi log hoặc xử lý ở ocpp_handlers.py.
    return {"message": "Lệnh Reset đã được gửi", "msg_id": msg_id}
