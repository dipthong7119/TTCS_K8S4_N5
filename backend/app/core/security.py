"""
security.py -- hash/verify mat khau bang argon2id, tao/doc session cookie
Tham chieu: SPRINT_1.md T-05, 02_CODING_STANDARDS.md
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
)


def hash_password(plain: str) -> str:
    """Tra ve argon2id hash cua mat khau."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Tra ve True neu mat khau khop, False neu sai.
    Khong tiet lo ly do cu the (SSD-1 rang buoc: thong bao sai phai giong het nhau).
    """
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
