from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.meter_value import MeterValue


def get_latest_meter_value(db: Session, session_id: int, measurand: str) -> MeterValue | None:
    """
    Lấy số đo mới nhất của một phiên sạc và một đại lượng đo (measurand) cụ thể.
    Dùng ORDER BY measured_at DESC LIMIT 1.
    Chỉ mục ix_meter_values_session_id_measured_at sẽ hỗ trợ truy vấn này tốt,
    kết hợp với bộ lọc bổ sung trên measurand ở mức dữ liệu hẹp của một session.
    """
    stmt = (
        select(MeterValue)
        .where(MeterValue.session_id == session_id, MeterValue.measurand == measurand)
        .order_by(MeterValue.measured_at.desc())
        .limit(1)
    )
    result = db.execute(stmt).scalars().first()
    return result
