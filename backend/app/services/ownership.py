"""
services/ownership.py -- Ham loc theo quyen so huu, dung chung (T-07)
Tham chieu: SPRINT_1.md T-07, 02_CODING_STANDARDS.md, SSD-1
"""


from app.models.station import Station


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