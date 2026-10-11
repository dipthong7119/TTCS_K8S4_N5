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


def record_remote_command(
    db,
    *,
    action: str,
    command: str,
    object_type: str,
    object_id: int | str,
    actor,
    charge_point_code: str,
    outcome: str,
    details: dict | None = None,
) -> AuditLog:
    """Record a remote control command with its actor, target, and outcome."""
    return append_audit(
        db,
        action=action,
        object_type=object_type,
        object_id=object_id,
        actor_id=actor.id,
        actor_email=actor.email,
        actor_name=actor.full_name,
        charge_point_code=charge_point_code,
        details={**(details or {}), "command": command, "outcome": outcome},
    )
