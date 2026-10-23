"""Argon2id password hashing for Swasthya Sanjaal user accounts.

Uses the argon2-cffi reference implementation, which is the recommended
choice for new applications. Argon2id provides resistance to both GPU and
side-channel attacks.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyError, InvalidHashError


_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Returns an encoded hash string suitable for storage. The encoded string
    includes the algorithm parameters, salt, and hash.
    """
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Returns True if the password matches, False otherwise. Never raises
    exceptions for invalid passwords (caller should treat all failures
    identically to avoid account enumeration).
    """
    try:
        _hasher.verify(hashed_password, plain_password)
        return True
    except (VerifyError, InvalidHashError):
        return False
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if a stored hash was created with older parameters.

    Callers can use this to transparently rehash passwords on successful
    login when parameters have been upgraded.
    """
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except Exception:
        return False
