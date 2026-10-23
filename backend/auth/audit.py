"""Audit logging for security-relevant events in Swasthya Sanjaal.

Audit records capture actor, action, resource, patient reference, outcome,
timestamp, and request context. Passwords, session tokens, and authorization
headers are never recorded.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from backend.db import session as db_session


def audit(
    con: sqlite3.Connection,
    *,
    action: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    outcome: str = "success",
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Write an audit log entry.

    All parameters are optional except action and outcome. The entry is
    inserted immediately (not part of a larger transaction) so that audit
    records are preserved even if the calling transaction rolls back.
    """
    import secrets as _secrets

    audit_id = _secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc).isoformat()

    con.execute(
        """
        INSERT INTO audit_log (
            id, actor_id, actor_email, action, resource, resource_id,
            patient_id, outcome, detail, ip_address, user_agent, created_at
        )
        VALUES (
            :id, :actor_id, :actor_email, :action, :resource, :resource_id,
            :patient_id, :outcome, :detail, :ip_address, :user_agent, :created_at
        )
        """,
        {
            "id": audit_id,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "patient_id": patient_id,
            "outcome": outcome,
            "detail": detail,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": now,
        },
    )
    con.commit()
