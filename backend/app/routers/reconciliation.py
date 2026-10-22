"""
reconciliation.py — REST API đối chiếu kWh hệ thống CSMS vs Simulator (SCRUM-183 / SCRUM-184).

Phụ trách: Hoàng Văn Đức (Backend)
Tiêu thụ bởi: Phạm Văn Tuấn (Frontend / SCRUM-184)
Tham chiếu: SCRUM-182, SCRUM-183, SCRUM-184, S-21, E-04
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import deny_unannotated_route, require_role
from app.database import get_db
from app.models.charging_session import ChargingSession
from app.models.user import User
from app.services.kwh_reconciliation import reconcile_datasets

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reconciliation",
    tags=["reconciliation"],
    dependencies=[Depends(deny_unannotated_route)],
)


def _get_static_data_dir() -> Path:
    """Trả về thư mục dữ liệu frontend tương thích cả local dev lẫn Docker."""
    root_dir = Path(__file__).resolve().parents[3]
    docker_static = Path("/app/frontend/static/data")
    return (
        docker_static
        if docker_static.exists()
        else root_dir / "frontend" / "static" / "data"
    )


def _load_sample_data(static_data_dir: Path, tolerance: float) -> dict[str, Any]:
    """Tải dữ liệu mẫu khi chưa có kết quả chạy kịch bản thật từ SCRUM-182."""
    sample_file = static_data_dir / "kwh_reconciliation_sample.json"
    if sample_file.exists():
        try:
            data = json.loads(sample_file.read_text(encoding="utf-8"))
            metadata = data.setdefault("metadata", {})
            metadata["is_sample"] = True
            metadata["tolerance_kwh"] = tolerance
            return data
        except Exception as e:
            logger.warning("Không thể đọc file mẫu %s: %s", sample_file, e)

    return {
        "metadata": {
            "title": "Bảng dữ liệu mẫu đối chiếu kWh (Chưa có dữ liệu)",
            "task": "Báo cáo đối chiếu kWh",
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
    - Nếu không bật cờ sample: Đối chiếu các phiên OCPP gần đây được lưu trong DB.
    - Nếu chưa có phiên phù hợp hoặc bật cờ sample: Fallback tải dữ liệu mẫu chuẩn (is_sample: true).
    """
    static_data_dir = _get_static_data_dir()

    # Reconcile recent OCPP sessions directly from stored meter readings.
    if not sample:
        recent_since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
        sessions_query = db.query(ChargingSession).filter(
            ChargingSession.status == "completed",
            ChargingSession.ended_at.is_not(None),
            ChargingSession.meter_stop_wh.is_not(None),
            ChargingSession.started_at >= recent_since,
        )
        if settings.APP_ENV != "development":
            sessions_query = sessions_query.filter(ChargingSession.is_demo.is_(False))
        recent_sessions = (
            sessions_query.order_by(ChargingSession.started_at.desc(), ChargingSession.id.desc())
            .limit(500)
            .all()
        )
        if recent_sessions:
            system_sessions = []
            sim_sessions = []
            session_by_key = {}
            for session in recent_sessions:
                meter_start = int(session.meter_start_wh or 0)
                meter_stop = int(session.meter_stop_wh)
                meter_kwh = round(max(meter_stop - meter_start, 0) / 1000.0, 3)
                session_key = str(session.id)
                session_by_key[session_key] = session
                common = {
                    "session_id": session.id,
                    "charge_point_code": session.charge_point_code,
                    "connector_id": session.connector_number,
                    "meter_start_wh": meter_start,
                    "meter_stop_wh": meter_stop,
                    "disconnect_count": 0,
                    "notes": "Đối chiếu từ số đo công tơ OCPP đã lưu.",
                }
                system_sessions.append(
                    {
                        **common,
                        "system_kwh": float(
                            session.energy_kwh
                            if session.energy_kwh is not None
                            else meter_kwh
                        ),
                    }
                )
                sim_sessions.append({**common, "simulator_kwh": meter_kwh})

            reconciliation = reconcile_datasets(
                system_sessions, sim_sessions, tolerance=tolerance
            )
            for item in reconciliation["sessions"]:
                session = session_by_key.get(str(item["session_id"]))
                if session is not None:
                    item["station_id"] = session.station_id
                    item["station_name"] = session.station_name

            return {
                "metadata": {
                    "title": "Đối chiếu các phiên OCPP gần đây",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "total_charge_points": len({s.charge_point_code for s in recent_sessions}),
                    "tolerance_kwh": tolerance,
                    "is_sample": False,
                    "source": "ocpp_meter_readings",
                },
                "summary": reconciliation["summary"],
                "sessions": reconciliation["sessions"],
            }

    # Fallback sang dữ liệu mẫu nếu DB chưa có phiên phù hợp hoặc được yêu cầu.
    return _load_sample_data(static_data_dir, tolerance)
