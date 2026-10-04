"""
Script kiểm thử tự động toàn diện SCRUM-130 (T-31).
Kiểm chứng cơ chế dọn dẹp tin nhắn OCPP cũ và kiểm tra tính Idempotency khi gửi lặp lại 5 lần:
- TC-130-01: Bản ghi cũ hơn 7 ngày bị xóa
- TC-130-02: Bản ghi trong vòng 7 ngày KHÔNG bị xóa
- TC-130-03: Kiểm tra biên (đúng ngưỡng 7 ngày)
- TC-130-04: Lần chạy tiếp theo là no-op khi không còn bản ghi cũ
- TC-130-05: Xóa hàng loạt nhiều bản ghi (bulk deletion 50 bản ghi)
- TC-130-06: Coroutine async chạy theo chu kỳ và không crash
- Idempotency: Gửi lại cùng một CALL 5 lần với cùng msg_id và charge_point_code
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.models.charge_point import ChargePoint
from app.models.ocpp_message import OcppMessage
from app.models.station import Station
from app.services.jobs import cleanup_old_ocpp_messages, cleanup_old_ocpp_messages_once
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call


def cleanup_test_messages(db):
    """Xóa tất cả message thử nghiệm có prefix test-scrum130-."""
    db.query(OcppMessage).filter(OcppMessage.msg_id.like("test-scrum130-%")).delete(synchronize_session=False)
    db.commit()


def setup_test_station_and_cp(db):
    """Đảm bảo có trạm và trụ sạc cho test idempotency."""
    station = db.query(Station).filter_by(id=998).first()
    if not station:
        station = Station(id=998, name="Trạm Test 130", address="Hà Nội", owner_id=1, status="active")
        db.add(station)
        db.commit()

    cp = db.query(ChargePoint).filter_by(code="CP-130-TEST").first()
    if not cp:
        cp = ChargePoint(code="CP-130-TEST", station_id=998, status="online")
        db.add(cp)
        db.commit()
    return cp


def test_tc_130_01_older_than_retention_deleted(db):
    """TC-130-01: Bản ghi cũ hơn 7 ngày bị xóa."""
    print("\n--- Chạy TC-130-01: Bản ghi cũ hơn 7 ngày bị xóa ---")
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    old_time = now_utc - timedelta(days=settings.OCPP_MESSAGE_RETENTION_DAYS + 1)  # 8 ngày trước

    msg = OcppMessage(
        msg_id="test-scrum130-old-001",
        charge_point_code="CP-130-TEST",
        action="BootNotification",
        request_payload={"chargePointModel": "ModelX"},
        response_payload={"status": "Accepted", "currentTime": now_utc.isoformat(), "interval": 300},
        request_hash="hash-old-001",
        created_at=old_time,
    )
    db.add(msg)
    db.commit()

    # Kiểm tra bản ghi đã được thêm
    assert db.query(OcppMessage).filter_by(msg_id="test-scrum130-old-001").count() == 1

    # Chạy cleanup
    deleted = cleanup_old_ocpp_messages_once(db)
    print(f"Số bản ghi đã xóa: {deleted}")
    assert deleted >= 1, f"Mong đợi xóa ít nhất 1 bản ghi, thực tế xóa: {deleted}"

    # Kiểm tra bản ghi không còn trong DB
    remaining = db.query(OcppMessage).filter_by(msg_id="test-scrum130-old-001").count()
    assert remaining == 0, "Bản ghi cũ vẫn còn trong database sau cleanup!"
    print("TC-130-01 PASSED: Bản ghi cũ hơn 7 ngày đã bị xóa thành công.")


def test_tc_130_02_newer_than_retention_kept(db):
    """TC-130-02: Bản ghi trong vòng 7 ngày KHÔNG bị xóa."""
    print("\n--- Chạy TC-130-02: Bản ghi trong vòng 7 ngày KHÔNG bị xóa ---")
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    recent_time = now_utc - timedelta(days=3)  # 3 ngày trước

    msg = OcppMessage(
        msg_id="test-scrum130-new-001",
        charge_point_code="CP-130-TEST",
        action="Heartbeat",
        request_payload={},
        response_payload={"currentTime": now_utc.isoformat()},
        request_hash="hash-new-001",
        created_at=recent_time,
    )
    db.add(msg)
    db.commit()

    deleted = cleanup_old_ocpp_messages_once(db)
    print(f"Số bản ghi đã xóa trong lần này: {deleted}")

    # Kiểm tra bản ghi vẫn còn
    record = db.query(OcppMessage).filter_by(msg_id="test-scrum130-new-001").first()
    assert record is not None, "Bản ghi mới (3 ngày) bị xóa nhầm!"
    print("TC-130-02 PASSED: Bản ghi trong 7 ngày được giữ nguyên an toàn.")


def test_tc_130_03_boundary_retention(db):
    """TC-130-03: Kiểm tra biên chính xác tại ngưỡng 7 ngày."""
    print("\n--- Chạy TC-130-03: Kiểm tra biên (đúng 7 ngày) ---")
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    retention_days = settings.OCPP_MESSAGE_RETENTION_DAYS

    # Bản ghi 1: 7 ngày + 1 giờ (cũ hơn ngưỡng -> phải bị xóa)
    msg_past = OcppMessage(
        msg_id="test-scrum130-edge-past",
        charge_point_code="CP-130-TEST",
        action="StatusNotification",
        request_payload={"status": "Available"},
        response_payload={},
        request_hash="hash-edge-past",
        created_at=now_utc - timedelta(days=retention_days, hours=1),
    )
    # Bản ghi 2: 7 ngày - 1 giờ (trong ngưỡng -> phải được giữ)
    msg_future = OcppMessage(
        msg_id="test-scrum130-edge-future",
        charge_point_code="CP-130-TEST",
        action="StatusNotification",
        request_payload={"status": "Available"},
        response_payload={},
        request_hash="hash-edge-future",
        created_at=now_utc - timedelta(days=retention_days) + timedelta(hours=1),
    )
    db.add_all([msg_past, msg_future])
    db.commit()

    deleted = cleanup_old_ocpp_messages_once(db)
    print(f"Số bản ghi đã xóa: {deleted}")

    assert db.query(OcppMessage).filter_by(msg_id="test-scrum130-edge-past").count() == 0, (
        "Bản ghi > 7 ngày không bị xóa!"
    )
    assert db.query(OcppMessage).filter_by(msg_id="test-scrum130-edge-future").count() == 1, (
        "Bản ghi < 7 ngày bị xóa nhầm!"
    )
    print("TC-130-03 PASSED: Hành vi biên chính xác (< cutoff bị xóa, >= cutoff được giữ).")


def test_tc_130_04_idempotent_no_op(db):
    """TC-130-04: Lần chạy lặp lại là no-op khi không còn bản ghi cũ."""
    print("\n--- Chạy TC-130-04: Lần chạy lặp lại là no-op ---")
    deleted = cleanup_old_ocpp_messages_once(db)
    print(f"Số bản ghi đã xóa lần 2: {deleted}")
    assert deleted == 0, f"Mong đợi return 0 khi không còn bản ghi cũ, nhận: {deleted}"
    print("TC-130-04 PASSED: Cleanup chạy lại an toàn, trả về 0, không exception.")


def test_tc_130_05_bulk_deletion(db):
    """TC-130-05: Xóa nhiều bản ghi cùng lúc (bulk delete 50 bản ghi cũ)."""
    print("\n--- Chạy TC-130-05: Xóa hàng loạt (50 bản ghi cũ) ---")
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    bulk_msgs = [
        OcppMessage(
            msg_id=f"test-scrum130-bulk-{i}",
            charge_point_code="CP-130-TEST",
            action="Heartbeat",
            request_payload={},
            response_payload={"currentTime": now_utc.isoformat()},
            request_hash=f"hash-bulk-{i}",
            created_at=now_utc - timedelta(days=10),
        )
        for i in range(50)
    ]
    db.add_all(bulk_msgs)
    db.commit()

    count_before = db.query(OcppMessage).filter(OcppMessage.msg_id.like("test-scrum130-bulk-%")).count()
    assert count_before == 50, f"Thêm bản ghi bulk thất bại: {count_before}"

    deleted = cleanup_old_ocpp_messages_once(db)
    print(f"Số bản ghi đã xóa hàng loạt: {deleted}")
    assert deleted == 50, f"Mong đợi xóa 50 bản ghi, nhận: {deleted}"

    count_after = db.query(OcppMessage).filter(OcppMessage.msg_id.like("test-scrum130-bulk-%")).count()
    assert count_after == 0, f"Vẫn còn {count_after} bản ghi bulk trong DB!"
    print("TC-130-05 PASSED: Toàn bộ 50 bản ghi cũ bị xóa sạch hoàn toàn.")


def test_tc_130_06_async_job_execution():
    """TC-130-06: Coroutine async chạy theo chu kỳ và không crash."""
    print("\n--- Chạy TC-130-06: Async job chu kỳ không crash ---")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    import app.services.jobs
    original_sleep = asyncio.sleep

    called = False

    async def mock_sleep(seconds):
        nonlocal called
        called = True
        raise asyncio.CancelledError()

    app.services.jobs.asyncio.sleep = mock_sleep

    try:
        loop.run_until_complete(cleanup_old_ocpp_messages())
    except asyncio.CancelledError:
        pass
    finally:
        app.services.jobs.asyncio.sleep = original_sleep
        loop.close()

    assert called, "Job không gọi asyncio.sleep!"
    print("TC-130-06 PASSED: Coroutine async cleanup chạy chu kỳ bình thường, xử lý CancelledError mượt mà.")


def test_idempotency_5_repeated_calls(db):
    """Kiểm tra AC Idempotency: Gửi lại cùng một CALL 5 lần với cùng msg_id."""
    print("\n--- Chạy Test Idempotency: Gửi lại cùng CALL 5 lần ---")
    setup_test_station_and_cp(db)

    idem_msg_id = "test-scrum130-idem-repeat-5x"
    raw_call = pack_call(idem_msg_id, "Heartbeat", {})

    # Lần gửi thứ 1
    resp_1 = handle_ocpp_message(db, "CP-130-TEST", raw_call)
    assert resp_1 is not None, "Lần 1 không nhận được response!"

    # Gửi lặp lại 5 lần tiếp theo
    responses = [resp_1]
    for i in range(1, 6):
        resp = handle_ocpp_message(db, "CP-130-TEST", raw_call)
        assert resp == resp_1, f"Lần {i+1} nhận response khác lần 1!"
        responses.append(resp)

    # Kiểm tra trong DB: chỉ tồn tại DUY NHẤT 1 bản ghi
    record_count = db.query(OcppMessage).filter_by(msg_id=idem_msg_id, charge_point_code="CP-130-TEST").count()
    assert record_count == 1, f"Mong đợi đúng 1 bản ghi trong ocpp_messages, thực tế có {record_count} bản ghi!"

    print("Đã gửi tổng cộng 6 lần (1 lần gốc + 5 lần lặp lại).")
    print(f"Tất cả {len(responses)} phản hồi hoàn toàn trùng khớp:")
    print(f"Phản hồi mẫu: {resp_1}")
    print(f"Số lượng bản ghi trong ocpp_messages: {record_count}")
    print("Idempotency 5x PASSED: Chống trùng hoàn hảo, trả về cached response và không chèn bản ghi trùng.")


def main():
    print("=" * 60)
    print("BẮT ĐẦU KIỂM THỬ NGHIỆM THU SCRUM-130 (T-31)")
    print("Dọn dẹp OCPP Messages > 7 ngày & Kiểm tra Idempotency lặp 5 lần")
    print("=" * 60)

    with SessionLocal() as db:
        try:
            cleanup_test_messages(db)

            test_tc_130_01_older_than_retention_deleted(db)
            test_tc_130_02_newer_than_retention_kept(db)
            test_tc_130_03_boundary_retention(db)
            test_tc_130_04_idempotent_no_op(db)
            test_tc_130_05_bulk_deletion(db)
            test_tc_130_06_async_job_execution()
            test_idempotency_5_repeated_calls(db)

            print("\n" + "=" * 60)
            print("TẤT CẢ TEST CASES CỦA SCRUM-130 (T-31) ĐỀU ĐÃ ĐẠT (PASS 100%)!")
            print("=" * 60)
        finally:
            cleanup_test_messages(db)
            # Dọn dẹp station và cp test nếu có
            cp = db.query(ChargePoint).filter_by(code="CP-130-TEST").first()
            if cp:
                db.delete(cp)
            st = db.query(Station).filter_by(id=998).first()
            if st:
                db.delete(st)
            db.commit()


if __name__ == "__main__":
    main()
