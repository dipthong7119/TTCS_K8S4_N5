import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.charge_point import ChargePoint

logger = logging.getLogger(__name__)

async def check_offline_charge_points():
    """T-26: Job nền quét last_seen_at quá hai chu kỳ (ví dụ: > 10 phút) và đổi trạng thái"""
    while True:
        try:
            with SessionLocal() as db:
                # Ngưỡng: last_seen_at cách đây hơn 10 phút (2 chu kỳ của 300s)
                threshold = datetime.now(timezone.utc) - timedelta(minutes=10)
                offline_cps = db.query(ChargePoint).filter(
                    ChargePoint.status == "online",
                    (ChargePoint.last_seen_at == None) | (ChargePoint.last_seen_at < threshold)
                ).all()

                if offline_cps:
                    for cp in offline_cps:
                        cp.status = "offline"
                        logger.info(f"Đánh dấu trụ {cp.code} là ngoại tuyến do quá hạn nhịp tim.")

                    db.commit()

                    from app.routers.monitoring import notify_status_change
                    for cp in offline_cps:
                        db.refresh(cp)
                        station = cp.station
                        if station:
                            cp_data = []
                            for p in station.charge_points:
                                conn_list = []
                                for cn in p.connectors:
                                    conn_list.append({
                                        "id": cn.id,
                                        "connector_id": cn.connector_id,
                                        "status": cn.status,
                                        "error_code": cn.error_code,
                                        "updated_at": cn.updated_at.isoformat()
                                    })
                                cp_data.append({
                                    "id": p.id,
                                    "code": p.code,
                                    "status": p.status,
                                    "vendor": p.vendor,
                                    "model": p.model,
                                    "firmware_version": p.firmware_version,
                                    "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
                                    "connectors": conn_list
                                })
                            notify_status_change(station.id, cp_data, station.owner_id)

        except Exception as e:
            logger.error(f"Lỗi job check_offline_charge_points: {e}")

        await asyncio.sleep(60)

async def cleanup_old_ocpp_messages():
    """T-31: Job dọn bản ghi cũ hơn 7 ngày"""
    while True:
        try:
            from app.models.ocpp_message import OcppMessage
            with SessionLocal() as db:
                threshold = datetime.now(timezone.utc) - timedelta(days=7)
                deleted = db.query(OcppMessage).filter(OcppMessage.created_at < threshold).delete()
                db.commit()
                if deleted > 0:
                    logger.info(f"Đã xoá {deleted} bản ghi ocpp_messages cũ hơn 7 ngày.")
        except Exception as e:
            logger.error(f"Lỗi job cleanup_old_ocpp_messages: {e}")

        # Chạy mỗi giờ
        await asyncio.sleep(3600)
