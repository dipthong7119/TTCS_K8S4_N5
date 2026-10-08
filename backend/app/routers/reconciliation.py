"""
reconciliation.py — REST API đối chiếu kWh hệ thống CSMS vs Simulator (SCRUM-183 / SCRUM-184).

Phụ trách: Hoàng Văn Đức (Backend)
Tiêu thụ bởi: Phạm Văn Tuấn (Frontend / SCRUM-184)
Tham chiếu: SCRUM-182, SCRUM-183, SCRUM-184, S-21, E-04
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.deps import deny_unannotated_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.user import User
from app.services.kwh_reconciliation import reconcile_datasets

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reconciliation",
    tags=["reconciliation"],
    dependencies=[Depends(deny_unannotated_route)],
)


def _get_project_paths() -> tuple[Path, Path]:
    """Trả về (ketqua_dir, static_data_dir) tương thích cả local dev lẫn Docker."""
    root_dir = Path(__file__).resolve().parents[3]

    docker_ketqua = Path("/app/ketqua")
    ketqua_dir = docker_ketqua if docker_ketqua.exists() else root_dir / "ketqua"

    docker_static = Path("/app/frontend/static/data")
    static_data_dir = (
        docker_static if docker_static.exists() else root_dir / "frontend" / "static" / "data"
    )

    return ketqua_dir, static_data_dir


def _load_sample_data(static_data_dir: Path, ketqua_dir: Path, tolerance: float) -> dict[str, Any]:
    """Tải dữ liệu mẫu khi chưa có kết quả chạy kịch bản thật từ SCRUM-182."""
    candidates = [
        static_data_dir / "kwh_reconciliation_sample.json",
        ketqua_dir / "kwh_reconciliation_sample.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                metadata = data.setdefault("metadata", {})
                metadata["is_sample"] = True
                metadata["tolerance_kwh"] = tolerance
                return data
            except Exception as e:
                logger.warning("Không thể đọc file mẫu %s: %s", p, e)

    return {
        "metadata": {
            "title": "Bảng dữ liệu mẫu đối chiếu kWh (Chưa có dữ liệu)",
            "task": "SCRUM-183 (Đức) & SCRUM-184 (Tuấn) & SCRUM-182 (Tú)",
            "generated_at": datetime.now(UTC).isoformat(),
            "total_charge_points": 0,
            "tolerance_kwh": tolerance,
            "is_sample": True,
        },
        "summary": {
            "total_sessions": 0,
            "matched_sessions": 0,
            "mismatched_sessions": 0,
            "match_percentage": 0.0,
            "total_system_kwh": 0.0,
            "total_simulator_kwh": 0.0,
            "total_difference_kwh": 0.0,
            "verdict": "PASSED",
        },
        "sessions": [],
    }


@router.get(
    "/kwh",
    dependencies=[Depends(require_role("admin", "operator"))],
)
def get_kwh_reconciliation(
    current_user: User = Depends(require_role("admin", "operator")),
    db: Session = Depends(get_db),
    tolerance: float = Query(0.001, ge=0.0, description="Ngưỡng sai số kWh cho phép"),
    sample: bool = Query(False, description="Bắt buộc sử dụng dữ liệu mẫu nếu True"),
) -> dict[str, Any]:
    """
    API đối chiếu số liệu kWh giữa hệ thống CSMS và thiết bị giả lập (Simulator).
    - Phục vụ báo cáo nghiệm thu S-21 / E-04 và hiển thị bảng đối chiếu SCRUM-184.
    - Nếu đã có kết quả chạy thật từ SCRUM-182 (scrum182_kwh_result.json) và không bật cờ sample:
      Đối chiếu dữ liệu phiên sạc thực tế giữa DB và Simulator.
    - Nếu chưa có kết quả chạy kịch bản thật: Fallback tải dữ liệu mẫu chuẩn (is_sample: true).
    """
    ketqua_dir, static_data_dir = _get_project_paths()
    scrum182_file = ketqua_dir / "scrum182_kwh_result.json"

    # Trường hợp 1: Có dữ liệu chạy thật từ SCRUM-182 và không yêu cầu sample
    if not sample and scrum182_file.exists():
        try:
            scrum_data = json.loads(scrum182_file.read_text(encoding="utf-8"))
            items = scrum_data.get("items", [])
            if items:
                sim_sessions = [
                    {
                        "session_id": item.get("transaction_id") or f"SIM-{idx}",
                        "charge_point_code": item.get("code", "UNKNOWN"),
                        "connector_id": 1,
                        "meter_start_wh": item.get("meter_start_wh", 0),
                        "meter_stop_wh": item.get("meter_stop_wh", 0),
                        "simulator_kwh": item.get("expected_kwh", 0.0),
                        "disconnect_count": item.get("disconnect_count", 0),
                        "notes": "; ".join(item.get("errors", [])) if item.get("errors") else "",
                    }
                    for idx, item in enumerate(items, 1)
                ]

                tids = [item["transaction_id"] for item in items if item.get("transaction_id")]
                db_sessions = (
                    db.query(ChargingSession).filter(ChargingSession.id.in_(tids)).all()
                    if tids
                    else []
                )
                db_map = {s.id: s for s in db_sessions}

                system_sessions = []
                for item in items:
                    tid = item.get("transaction_id")
                    s = db_map.get(tid)
                    if s:
                        system_sessions.append(
                            {
                                "session_id": s.id,
                                "charge_point_code": s.charge_point_code,
                                "connector_id": s.connector_number,
                                "meter_start_wh": s.meter_start_wh,
                                "meter_stop_wh": (
                                    s.meter_stop_wh if s.meter_stop_wh is not None else s.meter_start_wh
                                ),
                                "system_kwh": float(s.energy_kwh or 0.0),
                                "station_id": s.station_id,
                                "station_name": s.station_name,
                                "status": s.status,
                                "notes": s.anomaly_reason or s.review_reason or "",
                            }
                        )
                    else:
                        system_sessions.append(
                            {
                                "session_id": tid or "N/A",
                                "charge_point_code": item.get("code", "UNKNOWN"),
                                "connector_id": 1,
                                "meter_start_wh": item.get("meter_start_wh", 0),
                                "meter_stop_wh": item.get("meter_stop_wh", 0),
                                "system_kwh": float(item.get("db_kwh") or 0.0),
                                "status": item.get("db_status") or "completed",
                                "notes": "; ".join(item.get("errors", [])) if item.get("errors") else "",
                            }
                        )

                reconciliation = reconcile_datasets(
                    system_sessions, sim_sessions, tolerance=tolerance
                )

                # Bổ sung thông tin trạm sạc nếu còn thiếu
                all_codes = {s["charge_point_code"] for s in reconciliation["sessions"]}
                if all_codes:
                    cps = (
                        db.query(ChargePoint)
                        .options(joinedload(ChargePoint.station))
                        .filter(ChargePoint.code.in_(all_codes))
                        .all()
                    )
                    cp_map = {
                        cp.code: (cp.station_id, cp.station.name if cp.station else "")
                        for cp in cps
                    }
                    for sess in reconciliation["sessions"]:
                        code = sess.get("charge_point_code")
                        if code in cp_map:
                            st_id, st_name = cp_map[code]
                            if not sess.get("station_id"):
                                sess["station_id"] = st_id
                            if not sess.get("station_name"):
                                sess["station_name"] = st_name

                return {
                    "metadata": {
                        "title": "Bảng đối chiếu kWh hệ thống CSMS vs Simulator (SCRUM-182)",
                        "task": "SCRUM-183 (Đức) & SCRUM-184 (Tuấn) & SCRUM-182 (Tú)",
                        "epic": "E-04 / S-21 / T-46",
                        "generated_at": scrum_data.get(
                            "generated_at", datetime.now(UTC).isoformat()
                        ),
                        "total_charge_points": len(
                            {s["charge_point_code"] for s in reconciliation["sessions"]}
                        ),
                        "tolerance_kwh": tolerance,
                        "is_sample": False,
                    },
                    "summary": reconciliation["summary"],
                    "sessions": reconciliation["sessions"],
                }
        except Exception as e:
            logger.exception("Lỗi khi xử lý dữ liệu SCRUM-182: %s", e)

    # Trường hợp 2: Fallback sang dữ liệu mẫu
    return _load_sample_data(static_data_dir, ketqua_dir, tolerance)
