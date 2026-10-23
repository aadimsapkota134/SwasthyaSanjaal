"""Server-side session management for Swasthya Sanjaal.

Sessions are stored in SQLite with a hash of the session token (never the
raw token). Session identifiers are generated using Python's secrets module
for cryptographic randomness, mixed with the configured secret key.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.config import settings
from backend.db import session as db_session


def generate_session_token() -> str:
    """Generate a cryptographically random session token.

    The token is mixed with the configured session secret key via HMAC so
    that the token cannot be forged without knowing the secret.
    """
    random_bytes = secrets.token_bytes(32)
    secret = settings.session_secret_key.encode()
    if secret:
        token = hmac.new(secret, random_bytes, hashlib.sha256).hexdigest()
    else:
        token = random_bytes.hex()
    return token


def hash_token(token: str) -> str:
    """Hash a session token for storage. Never store raw tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(
    con,
    user_id: str,
    ttl_seconds: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """Create a new session for a user.

    Returns the raw session token (only shown once to the caller).
    The token hash is stored in the database.
    """
    if ttl_seconds is None:
        ttl_seconds = settings.session_ttl_seconds

    token = generate_session_token()
    token_hash = hash_token(token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    session_id = secrets.token_urlsafe(16)

    con.execute(
        """
        INSERT INTO sessions (id, user_id, token_hash, expires_at, ip_address, user_agent)
        VALUES (:id, :user_id, :token_hash, :expires_at, :ip_address, :user_agent)
        """,
        {
            "id": session_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
        },
    )
    con.commit()
    return token


def validate_session(con, token: str) -> Optional[dict]:
    """Validate a session token and return the session record if valid.

    Returns None if the token is invalid, expired, or the session is revoked.
    Updates last_used_at on successful validation.
    """
    token_hash = hash_token(token)
    now = datetime.now(timezone.utc).isoformat()

    row = con.execute(
        """
        SELECT s.id, s.user_id, s.expires_at, s.last_used_at, u.email, u.role, u.is_active
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = :token_hash
          AND s.expires_at > :now
          AND u.is_active = 1
        """,
        {"token_hash": token_hash, "now": now},
    ).fetchone()

    if row is None:
        return None

    # Update last_used_at
    con.execute(
        "UPDATE sessions SET last_used_at = :now WHERE id = :id",
        {"now": datetime.now(timezone.utc).isoformat(), "id": row["id"]},
    )
    con.commit()

    return dict(row)


def revoke_session(con, token: str) -> bool:
    """Revoke (delete) a session by token. Returns True if a session was removed."""
    token_hash = hash_token(token)
    cur = con.execute(
        "DELETE FROM sessions WHERE token_hash = :token_hash",
        {"token_hash": token_hash},
    )
    con.commit()
    return cur.rowcount > 0


def revoke_all_sessions_for_user(con, user_id: str) -> int:
    """Revoke all sessions for a user. Returns the number revoked."""
    cur = con.execute(
        "DELETE FROM sessions WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    con.commit()
    return cur.rowcount


def cleanup_expired_sessions(con) -> int:
    """Delete expired sessions. Returns the number removed."""
    now = datetime.now(timezone.utc).isoformat()
    cur = con.execute(
        "DELETE FROM sessions WHERE expires_at <= :now",
        {"now": now},
    )
    con.commit()
    return cur.rowcount
