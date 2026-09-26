import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.models.charge_point import ChargePoint
from app.services.connection_manager import manager
from app.services.ocpp_handlers import handle_ocpp_message

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ocpp/{charge_point_code}")
async def ocpp_websocket_endpoint(
    websocket: WebSocket,
    charge_point_code: str
):
    requested_protocols = websocket.headers.get("sec-websocket-protocol", "").split(",")
    requested_protocols = [p.strip() for p in requested_protocols]

    if "ocpp1.6" not in requested_protocols:
        logger.warning(f"Từ chối kết nối từ {websocket.client.host}: Giao thức không được hỗ trợ {requested_protocols}")
        await websocket.close(code=1002, reason="Unsupported protocol")
        return

    await websocket.accept(subprotocol="ocpp1.6")

    with SessionLocal() as db:
        charge_point = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()

        if not charge_point:
            logger.warning(f"Mã trụ lạ kết nối: {charge_point_code}, IP: {websocket.client.host}")
            await websocket.close(code=1008, reason="Charge point not found")
            return

    await manager.connect(charge_point_code, websocket)
    logger.info(f"Trụ {charge_point_code} đã kết nối WebSocket.")

    try:
        while True:
            raw_msg = await websocket.receive_text()
            logger.debug(f"Nhận từ {charge_point_code}: {raw_msg}")

            with SessionLocal() as db:
                response = handle_ocpp_message(db, charge_point_code, raw_msg)

            if response:
                await websocket.send_text(response)
                logger.debug(f"Gửi tới {charge_point_code}: {response}")

    except WebSocketDisconnect:
        logger.info(f"Trụ {charge_point_code} ngắt kết nối.")
        manager.disconnect(charge_point_code, websocket)
    except Exception as e:
        logger.error(f"Lỗi kết nối trụ {charge_point_code}: {e}")
        manager.disconnect(charge_point_code, websocket)
        await websocket.close(code=1011)
