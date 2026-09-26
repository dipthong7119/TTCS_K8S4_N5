"""
services/ownership.py -- Ham loc theo quyen so huu, dung chung (T-07)
Tham chieu: SPRINT_1.md T-07, 02_CODING_STANDARDS.md, SSD-1
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.models.station import Station

logger = logging.getLogger("csms.ownership")


def filter_by_owner(query, user_id: int, role_names: list[str]):
    """
    Them dieu kien owner_id vao truy van neu user KHONG phai admin.
    Chi mot ham — khong chep tay vao tung query (T-07 NFR).

    Su dung:
        query = filter_by_owner(query, current_user.id, ["admin", ...])
    """
    if "admin" not in role_names:
        query = query.filter(Station.owner_id == user_id)
    return query


def check_station_access(station: Station, current_user) -> None:
    """
    Kiem tra quyen so huu sau khi fetch ban ghi don (GET/PUT/DELETE).
    - Admin: bo qua kiem tra, return ngay.
    - Khong phai admin + station.owner_id != current_user.id:
        ghi 1 dong log WARNING (khong PII) roi raise HTTPException 403.

    Dung chung cho ca 3 route: get_station, update_station, delete_station.
    """
    role_names = [r.name for r in current_user.roles]
    if "admin" in role_names:
        return

    if station.owner_id != current_user.id:
        logger.warning(
            "ACCESS_DENIED user_id=%s station_id=%s at=%s",
            current_user.id,
            station.id,
            datetime.now(timezone.utc).isoformat(),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Khong co quyen truy cap tram nay",
        )