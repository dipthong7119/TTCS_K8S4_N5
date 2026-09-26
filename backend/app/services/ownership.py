"""
services/ownership.py -- Ham loc theo quyen so huu, dung chung (T-07)
Tham chieu: SPRINT_1.md T-07, 02_CODING_STANDARDS.md, SSD-1
"""


import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.station import Station

logger = logging.getLogger(__name__)


def filter_by_owner(query, user_id: int, role_names: list[str]):
    """
    Them dieu kien owner_id vao truy vấn neu user KHONG phai admin hoac operator.
    Chi mot ham — khong chép tay vào tung query (T-07 NFR).

    Su dung:
        query = filter_by_owner(query, current_user.id, ["admin", ...])
    """
    if "admin" not in role_names and "operator" not in role_names:
        query = query.filter(Station.owner_id == user_id)
    return query


def get_station_for_user(
    db: Session,
    station_id: int,
    user_id: int,
    role_names: list[str],
    action: str = "view",
) -> Station:
    """Fetch through the shared owner filter and log denied cross-owner access."""
    station = filter_by_owner(
        db.query(Station), user_id, role_names
    ).filter(Station.id == station_id).first()
    if station is not None:
        return station

    exists = db.query(Station.id).filter(Station.id == station_id).first()
    if exists:
        logger.warning(
            "station_access_denied user_id=%s station_id=%s action=%s",
            user_id,
            station_id,
            action,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Khong co quyen truy cap tram nay",
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay tram")
