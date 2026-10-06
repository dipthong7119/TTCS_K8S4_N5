"""
Unit tests for SCRUM-183 (Thu thập và đối chiếu kWh hệ thống vs simulator).
Phụ trách: Hoàng Văn Đức (Backend / SCRUM-183)
"""

import json
from pathlib import Path

import pytest

from app.services.kwh_reconciliation import (
    calculate_session_kwh,
    export_markdown_table,
    reconcile_datasets,
    reconcile_single_session,
)


def test_calculate_session_kwh():
    """Kiểm tra hàm tính kWh thuần từ hai mốc Wh theo S-18 / SCRUM-187."""
    assert calculate_session_kwh(0, 15000) == 15.0
    assert calculate_session_kwh(12500, 28700) == 16.2
    assert calculate_session_kwh(5000, 5000) == 0.0
    # Ca số đo lùi: trả None thay vì số âm
    assert calculate_session_kwh(5000, 4000) is None


def test_reconcile_single_session_match():
    """Ca khớp hoàn toàn giữa hệ thống và simulator."""
    sys_rec = {
        "session_id": 101,
        "charge_point_code": "CP01",
        "connector_id": 1,
        "meter_start_wh": 1000,
        "meter_stop_wh": 6000,
        "system_kwh": 5.0,
    }
    sim_rec = {
        "session_id": 101,
        "charge_point_code": "CP01",
        "connector_id": 1,
        "meter_start_wh": 1000,
        "meter_stop_wh": 6000,
        "simulator_kwh": 5.0,
        "disconnect_count": 2,
    }
    item = reconcile_single_session(sys_rec, sim_rec)
    assert item.status == "MATCH"
    assert item.difference_kwh == 0.0
    assert item.disconnect_count == 2


def test_reconcile_single_session_mismatch():
    """Ca lệch kWh vượt ngưỡng cho phép."""
    sys_rec = {
        "session_id": 102,
        "charge_point_code": "CP02",
        "connector_id": 1,
        "meter_start_wh": 1000,
        "meter_stop_wh": 6000,
        "system_kwh": 5.0,
    }
    sim_rec = {
        "session_id": 102,
        "charge_point_code": "CP02",
        "connector_id": 1,
        "meter_start_wh": 1000,
        "meter_stop_wh": 7500,
        "simulator_kwh": 6.5,
        "disconnect_count": 1,
    }
    item = reconcile_single_session(sys_rec, sim_rec, tolerance=0.001)
    assert item.status == "MISMATCH"
    assert item.difference_kwh == 1.5


def test_reconcile_single_session_missing():
    """Ca thiếu phiên ở một trong hai phía."""
    # Thiếu trên CSMS
    item1 = reconcile_single_session(None, {"session_id": 103, "simulator_kwh": 10.0})
    assert item1.status == "MISSING_IN_SYSTEM"

    # Thiếu trên Simulator
    item2 = reconcile_single_session({"session_id": 104, "system_kwh": 12.0}, None)
    assert item2.status == "MISSING_IN_SIMULATOR"


def test_reconcile_datasets_20_sessions_sample():
    """Kiểm tra đối chiếu tập dữ liệu 20 phiên mẫu từ ketqua/kwh_reconciliation_sample.json."""
    sample_file = Path(__file__).resolve().parents[4] / "ketqua" / "kwh_reconciliation_sample.json"
    assert sample_file.exists(), f"Không tìm thấy file {sample_file}"

    with open(sample_file, encoding="utf-8") as f:
        data = json.load(f)

    # Tách thành hai danh sách đại diện hệ thống và simulator
    sys_sessions = []
    sim_sessions = []
    for s in data["sessions"]:
        sys_sessions.append({
            "session_id": s["session_id"],
            "charge_point_code": s["charge_point_code"],
            "connector_id": s["connector_id"],
            "meter_start_wh": s["meter_start_wh"],
            "meter_stop_wh": s["meter_stop_wh"],
            "system_kwh": s["system_kwh"],
        })
        sim_sessions.append({
            "session_id": s["session_id"],
            "charge_point_code": s["charge_point_code"],
            "connector_id": s["connector_id"],
            "meter_start_wh": s["meter_start_wh"],
            "meter_stop_wh": s["meter_stop_wh"],
            "simulator_kwh": s["simulator_kwh"],
            "disconnect_count": s["disconnect_count"],
            "notes": s.get("notes", ""),
        })

    result = reconcile_datasets(sys_sessions, sim_sessions)
    summary = result["summary"]

    assert summary["total_sessions"] == 20
    assert summary["matched_sessions"] == 20
    assert summary["mismatched_sessions"] == 0
    assert summary["match_percentage"] == 100.0
    assert summary["total_difference_kwh"] == 0.0
    assert summary["verdict"] == "PASSED"


def test_export_markdown_table():
    """Kiểm tra hàm xuất bảng đối chiếu Markdown cho Tuấn (SCRUM-184)."""
    dataset = {
        "summary": {
            "total_sessions": 2,
            "matched_sessions": 2,
            "mismatched_sessions": 0,
            "match_percentage": 100.0,
            "total_system_kwh": 30.0,
            "total_simulator_kwh": 30.0,
            "total_difference_kwh": 0.0,
            "verdict": "PASSED",
        },
        "sessions": [
            {
                "session_id": 1,
                "charge_point_code": "CP01",
                "connector_id": 1,
                "meter_start_wh": 0,
                "meter_stop_wh": 10000,
                "disconnect_count": 1,
                "system_kwh": 10.0,
                "simulator_kwh": 10.0,
                "difference_kwh": 0.0,
                "status": "MATCH",
                "notes": "OK",
            },
            {
                "session_id": 2,
                "charge_point_code": "CP02",
                "connector_id": 1,
                "meter_start_wh": 10000,
                "meter_stop_wh": 30000,
                "disconnect_count": 2,
                "system_kwh": 20.0,
                "simulator_kwh": 20.0,
                "difference_kwh": 0.0,
                "status": "MATCH",
                "notes": "OK",
            },
        ],
    }
    md = export_markdown_table(dataset)
    assert "# BẢNG ĐỐI CHIẾU NĂNG LƯỢNG KWH" in md
    assert "CP01" in md
    assert "CP02" in md
    assert "100.0%" in md
