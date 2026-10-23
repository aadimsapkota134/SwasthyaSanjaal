"""In-memory rate limiter for login attempts.

Tracks failed login attempts per (ip_address, email) pair. After
``max_failed_login_attempts`` failures, further attempts are rejected with
HTTP 429 for ``failed_login_lockout_seconds``.

This is a single-process in-memory store. For multi-node deployments, replace
with a distributed store (e.g. Redis).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from backend.config import settings


@dataclass
class _AttemptRecord:
    count: int = 0
    first_failure: Optional[float] = None
    locked_until: Optional[float] = None


class RateLimiter:
    """Tracks failed login attempts and enforces lockout."""

    def __init__(self) -> None:
        self._attempts: dict[tuple[str, str], _AttemptRecord] = defaultdict(
            _AttemptRecord
        )

    def _key(self, ip_address: str, email: str) -> tuple[str, str]:
        # Normalize email (lowercase) to avoid case-sensitivity bypass
        return (ip_address, email.lower().strip())

    def is_rate_limited(
        self, ip_address: str, email: str
    ) -> tuple[bool, Optional[float]]:
        """Return (is_limited, retry_after_seconds) for the given key."""
        key = self._key(ip_address, email)
        record = self._attempts[key]
        now = time.monotonic()

        if record.locked_until is not None and now < record.locked_until:
            return True, record.locked_until - now

        # Lockout has expired; reset the record
        if record.locked_until is not None:
            record.count = 0
            record.first_failure = None
            record.locked_until = None

        return False, None

    def record_failure(self, ip_address: str, email: str) -> None:
        """Record a failed login attempt. May trigger lockout."""
        key = self._key(ip_address, email)
        record = self._attempts[key]
        now = time.monotonic()

        if record.locked_until is not None and now < record.locked_until:
            # Already locked out; don't increment further
            return

        if record.first_failure is None:
            record.first_failure = now

        record.count += 1

        if record.count >= settings.max_failed_login_attempts:
            record.locked_until = now + settings.failed_login_lockout_seconds

    def record_success(self, ip_address: str, email: str) -> None:
        """Clear failure history on successful login."""
        key = self._key(ip_address, email)
        if key in self._attempts:
            del self._attempts[key]


# Module-level singleton. In production with multiple workers, replace with
# a distributed store such as Redis.
rate_limiter = RateLimiter()
