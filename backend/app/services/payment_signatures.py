"""HMAC helpers for sandbox payment callbacks."""

import hashlib
import hmac
import json


def sandbox_webhook_signature(
    *,
    order_code: str,
    status: str,
    failure_reason: str | None,
    secret: str,
) -> str:
    """Return the hex HMAC-SHA256 for the canonical callback fields."""
    message = json.dumps(
        {
            "failure_reason": failure_reason,
            "order_code": order_code,
            "status": status,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_sandbox_webhook_signature(
    *,
    order_code: str,
    status: str,
    failure_reason: str | None,
    signature: str | None,
    secret: str,
) -> bool:
    if not secret or not signature:
        return False
    expected = sandbox_webhook_signature(
        order_code=order_code,
        status=status,
        failure_reason=failure_reason,
        secret=secret,
    )
    return hmac.compare_digest(expected.encode("ascii"), signature.encode("utf-8"))
