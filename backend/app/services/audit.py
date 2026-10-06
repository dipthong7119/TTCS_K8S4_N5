"""Shared append-only audit writer. Callers commit with their business transaction."""

from app.models.audit_log import AuditLog


def ghi_nhat_ky(
    db,
    *,
    action: str,
    object_type: str,
    object_id: int | str | None = None,
    actor_id: int | None = None,
    actor_email: str | None = None,
    actor_name: str | None = None,
    charge_point_code: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        actor_email=actor_email,
        actor_name=actor_name,
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id is not None else None,
        charge_point_code=charge_point_code,
        details=details or {},
    )
    db.add(entry)
    return entry


# Preserve the existing name for callers while standardizing on the T-57 API.
append_audit = ghi_nhat_ky
