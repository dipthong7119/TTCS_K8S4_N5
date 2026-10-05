"""
Script kiểm thử tự động 8 Test Case của SCRUM-126 (T-27).
Chạy trực tiếp với DB và services của CSMS để kiểm chứng hành vi:
- TC-126-01: Trụ online -> dừng -> trạng thái chuyển offline
- TC-126-02: Connector chuyển về unknown khi trụ stale
- TC-126-03: Bật lại trụ -> trạng thái trở về online
- TC-126-04: Connector trở về trạng thái sau khi trụ online lại (StatusNotification)
- TC-126-05: Job không đánh dấu sai trụ vẫn đang online
- TC-126-06: Lần chạy job lặp lại là no-op (idempotent)
- TC-126-07: SSE event được phát khi trụ chuyển offline
- TC-126-08: Bật/dừng nhiều trụ cùng lúc
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.config import settings
from app.database import SessionLocal
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.services.jobs import expire_stale_charge_points_once
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


def setup_test_data(db):
    """Khởi tạo trạm và các trụ phục vụ test."""
    station = db.query(Station).filter_by(id=999).first()
    if not station:
        station = Station(id=999, name="Trạm Test E2E 126", address="Khu CNC", owner_id=1, status="active")
        db.add(station)
        db.commit()

    codes = ["CP-001", "CP-002", "CP-003"]
    for code in codes:
        cp = db.query(ChargePoint).filter_by(code=code).first()
        if not cp:
            cp = ChargePoint(code=code, station_id=999, status="offline")
            db.add(cp)
            db.commit()
            conn1 = Connector(charge_point_id=cp.id, connector_id=1, status="unknown")
            conn2 = Connector(charge_point_id=cp.id, connector_id=2, status="unknown")
            db.add_all([conn1, conn2])
            db.commit()

    return station


def cleanup_test_data(db):
    """Dọn dẹp dữ liệu test."""
    from app.models.ocpp_message import OcppMessage
    codes = ["CP-001", "CP-002", "CP-003"]
    db.query(OcppMessage).filter(OcppMessage.charge_point_code.in_(codes)).delete(synchronize_session=False)
    for code in codes:
        cp = db.query(ChargePoint).filter_by(code=code).first()
        if cp:
            db.delete(cp)
    st = db.query(Station).filter_by(id=999).first()
    if st:
        db.delete(st)
    db.commit()


def run_all_tests():
    results = {}
    db = SessionLocal()
    try:
        setup_test_data(db)

        # -------------------------------------------------------------
        # TC-126-01: Trụ online -> dừng -> trạng thái chuyển offline
        # -------------------------------------------------------------
        cp1 = db.query(ChargePoint).filter_by(code="CP-001").one()
        timeout = settings.OCPP_HEARTBEAT_INTERVAL_SECONDS * settings.OCPP_HEARTBEAT_MULTIPLIER
        stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=timeout + 30)
        cp1.status = "online"
        cp1.last_seen_at = stale_time
        db.commit()

        expire_stale_charge_points_once(db)
        db.refresh(cp1)
        assert cp1.status == "offline", f"CP-001 status should be offline, got {cp1.status}"
        assert cp1.last_seen_at == stale_time, "last_seen_at không được đổi sau khi stale"
        results["TC-126-01"] = {
            "status": "PASS",
            "detail": f"Trụ CP-001 tự động chuyển sang offline khi last_seen_at quá {timeout}s. last_seen_at được giữ nguyên.",
        }

        # -------------------------------------------------------------
        # TC-126-02: Connector chuyển về `unknown` khi trụ stale
        # -------------------------------------------------------------
        cp1.status = "online"
        cp1.last_seen_at = stale_time
        for conn in cp1.connectors:
            conn.status = "bận"
        db.commit()

        expire_stale_charge_points_once(db)
        db.refresh(cp1)
        for conn in cp1.connectors:
            assert conn.status == "unknown", f"Connector status should be unknown, got {conn.status}"
        results["TC-126-02"] = {
            "status": "PASS",
            "detail": "Tất cả các connector của CP-001 đều chuyển về trạng thái 'unknown' sau khi trụ bị đánh dấu offline.",
        }

        # -------------------------------------------------------------
        # TC-126-03: Bật lại trụ -> trạng thái trở về online
        # -------------------------------------------------------------
        old_seen = cp1.last_seen_at
        hb_call = pack_call(f"hb-{time.time_ns()}", "Heartbeat", {})
        resp = handle_ocpp_message(db, "CP-001", hb_call)
        parsed = parse_message(resp)
        assert parsed[0] == 3, f"Phản hồi Heartbeat phải là CALLRESULT (3), nhận {parsed[0]}"

        db.refresh(cp1)
        assert cp1.status == "online", f"CP-001 phải trở về online sau Heartbeat, nhận {cp1.status}"
        assert cp1.last_seen_at > old_seen, "last_seen_at phải được cập nhật thời điểm mới"
        results["TC-126-03"] = {
            "status": "PASS",
            "detail": f"Trụ CP-001 nhận Heartbeat -> status hồi phục về 'online', last_seen_at={cp1.last_seen_at}.",
        }

        # -------------------------------------------------------------
        # TC-126-04: Connector trở về trạng thái sau khi nhận StatusNotification
        # -------------------------------------------------------------
        status_call = pack_call(f"sn-{time.time_ns()}", "StatusNotification", {
            "connectorId": 1,
            "errorCode": "NoError",
            "status": "Available",
        })
        resp = handle_ocpp_message(db, "CP-001", status_call)
        parsed = parse_message(resp)
        assert parsed[0] == 3, "Phản hồi StatusNotification phải là CALLRESULT"

        db.expire_all()
        conn1 = db.query(Connector).filter_by(charge_point_id=cp1.id, connector_id=1).one()
        assert conn1.status == "rảnh", f"Connector 1 phải chuyển về 'rảnh', nhận {conn1.status}"
        results["TC-126-04"] = {
            "status": "PASS",
            "detail": f"Connector 1 cập nhật thành công từ 'unknown' sang '{conn1.status}' (rảnh/Available) sau StatusNotification.",
        }

        # -------------------------------------------------------------
        # TC-126-05: Job không đánh dấu sai trụ vẫn đang online
        # -------------------------------------------------------------
        cp2 = db.query(ChargePoint).filter_by(code="CP-002").one()
        now_time = datetime.now(timezone.utc).replace(tzinfo=None)
        cp1.status = "online"
        cp1.last_seen_at = now_time - timedelta(seconds=timeout + 50)
        cp2.status = "online"
        cp2.last_seen_at = now_time - timedelta(seconds=1)
        db.commit()

        expire_stale_charge_points_once(db)
        db.refresh(cp1)
        db.refresh(cp2)
        assert cp1.status == "offline", "CP-001 phải offline do quá hạn"
        assert cp2.status == "online", "CP-002 phải giữ online do vẫn heartbeat đều đặn"
        results["TC-126-05"] = {
            "status": "PASS",
            "detail": "CP-001 stale chuyển offline, CP-002 có heartbeat gần nhất vẫn giữ nguyên status 'online'.",
        }

        # -------------------------------------------------------------
        # TC-126-06: Lần chạy job lặp lại là no-op (idempotent)
        # -------------------------------------------------------------
        second_run_count = expire_stale_charge_points_once(db)
        assert second_run_count == 0, f"Lần chạy thứ 2 phải quét được 0 bản ghi, nhận {second_run_count}"
        db.refresh(cp1)
        assert cp1.status == "offline"
        results["TC-126-06"] = {
            "status": "PASS",
            "detail": "Lần chạy thứ 2 trả về 0 bản ghi thay đổi, không gây tác dụng phụ, tính idempotent được đảm bảo.",
        }

        # -------------------------------------------------------------
        # TC-126-07: SSE event được phát khi trụ chuyển offline
        # -------------------------------------------------------------
        cp1.status = "online"
        cp1.last_seen_at = now_time - timedelta(seconds=timeout + 60)
        db.commit()

        with patch("app.routers.monitoring.notify_status_change") as mock_notify:
            expire_stale_charge_points_once(db)
            assert mock_notify.called, "notify_status_change phải được gọi khi có trụ chuyển offline"
            call_args = mock_notify.call_args[0]
            assert call_args[0] == 999, f"Station ID phát SSE phải là 999, nhận {call_args[0]}"
        results["TC-126-07"] = {
            "status": "PASS",
            "detail": "SSE event notify_status_change được kích hoạt thành công cho station_id=999 khi trụ offline.",
        }

        # -------------------------------------------------------------
        # TC-126-08: Bật/dừng nhiều trụ cùng lúc
        # -------------------------------------------------------------
        cp3 = db.query(ChargePoint).filter_by(code="CP-003").one()
        cp1.status = "online"
        cp1.last_seen_at = now_time - timedelta(seconds=timeout + 100)
        cp2.status = "online"
        cp2.last_seen_at = now_time - timedelta(seconds=timeout + 100)
        cp3.status = "online"
        cp3.last_seen_at = now_time - timedelta(seconds=1)
        db.commit()

        expire_stale_charge_points_once(db)
        db.refresh(cp1)
        db.refresh(cp2)
        db.refresh(cp3)
        assert cp1.status == "offline", "CP-001 phải offline"
        assert cp2.status == "offline", "CP-002 phải offline"
        assert cp3.status == "online", "CP-003 phải online"
        results["TC-126-08"] = {
            "status": "PASS",
            "detail": "CP-001 và CP-002 đồng thời chuyển offline, CP-003 vẫn online chính xác, không nhầm lẫn.",
        }

    finally:
        cleanup_test_data(db)
        db.close()

    return results


if __name__ == "__main__":
    print("=== BẮT ĐẦU CHẠY KIỂM THỬ SCRUM-126 ===")
    res = run_all_tests()
    all_passed = True
    for tc_id, data in sorted(res.items()):
        print(f"[{data['status']}] {tc_id}: {data['detail']}")
        if data["status"] != "PASS":
            all_passed = False
    print("========================================")
    if all_passed:
        print("TẤT CẢ 8/8 TEST CASE CỦA SCRUM-126 ĐÃ PASS THÀNH CÔNG! 🎉")
    else:
        print("CÓ TEST CASE BỊ THẤT BẠI!")
