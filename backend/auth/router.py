"""Authentication and authorization API routes for Swasthya Sanjaal.

Endpoints:
- POST   /api/v1/auth/login              - Create a session (email + password)
- POST   /api/v1/auth/logout             - Revoke the current session
- GET    /api/v1/auth/me                 - Return the current authenticated user
- POST   /api/v1/admin/users             - Admin: create a user account
- GET    /api/v1/admin/users             - Admin: list user accounts
- PATCH  /api/v1/admin/users/{user_id}   - Admin: deactivate/reactivate a user
- POST   /api/v1/admin/patient-access    - Admin: grant patient access to a user
- DELETE /api/v1/admin/patient-access    - Admin: revoke patient access from a user
- GET    /api/v1/admin/patient-access    - Admin: list patient access grants
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.auth.audit import audit
from backend.auth.csrf import generate_csrf_token, set_csrf_cookie
from backend.auth.password import hash_password, verify_password
from backend.auth.rate_limit import rate_limiter
from backend.auth.session import (
    cleanup_expired_sessions,
    create_session,
    generate_session_token,
    hash_token,
    revoke_all_sessions_for_user,
    revoke_session,
    validate_session,
)
from backend.config import settings
from backend.db import session as db_session

# Common passwords that should be rejected (OWASP top 1000 subset)
_COMMON_PASSWORDS = {
    "password",
    "123456",
    "12345678",
    "123456789",
    "1234567890",
    "qwerty",
    "abc123",
    "monkey",
    "dragon",
    "master",
    "login",
    "welcome",
    "admin",
    "letmein",
    "football",
    "iloveyou",
    "starwars",
    "access",
    "flower",
    "passw0rd",
    "trustno1",
    "sunshine",
    "princess",
    "test",
    "testing",
    "test123",
    "admin123",
    "root",
    "toor",
    "changeit",
    "changeme",
    "default",
    "guest",
    "user",
    "demo",
}


def _validate_password(value: str) -> str:
    """Validate a password: not empty, meets minimum length, not common."""
    if not value or not value.strip():
        raise ValueError("Password must not be empty")
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if value.strip().lower() in _COMMON_PASSWORDS:
        raise ValueError(
            "Password is too common; please choose a less guessable password"
        )
    return value

router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        return _validate_password(v)


class LoginResponse(BaseModel):
    user_id: str
    email: str
    role: str
    expires_at: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    role: str = Field(default="clinician", pattern="^(administrator|clinician)$")

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        return _validate_password(v)


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    role: str | None = Field(default=None, pattern="^(administrator|clinician)$")
    full_name: str | None = None


class PatientAccessRequest(BaseModel):
    user_id: str
    patient_id: str
class PatientAccessResponse(BaseModel):
    id: str
    user_id: str
    patient_id: str
    granted_by: str | None = None
    granted_at: str
    revoked_at: str | None = None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
) -> Optional[dict[str, Any]]:
    """Resolve the current authenticated user from the session cookie.

    Returns None if no valid session exists (used by optional-auth routes).
    """
    from typing import Optional

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None

    with db_session() as con:
        cleanup_expired_sessions(con)
        session_row = validate_session(con, token)
        if session_row is None:
            return None
        return session_row


async def require_auth(
    request: Request,
    current_user: Optional[dict[str, Any]] = Depends(get_current_user),
) -> dict[str, Any]:
    """Require a valid authenticated session. Raises 401 if not authenticated."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def require_admin(
    current_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Require an administrator role. Raises 403 if not an admin."""
    if current_user.get("role") != "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
):
    """Authenticate with email and password, creating a server-side session.

    Returns a session cookie. Generic error messages are used to avoid
    account enumeration.

    Rate-limited by (IP address, email) to prevent brute-force attacks.
    Returns HTTP 429 with Retry-After header when the limit is exceeded.
    """
    ip_address = request.client.host if request.client else "unknown"
    email = payload.email.lower().strip()

    # Check rate limit before doing anything else
    is_limited, retry_after = rate_limiter.is_rate_limited(ip_address, email)
    if is_limited:
        retry_after_int = int(retry_after) if retry_after is not None else 0
        audit(
            None,  # No DB session for rate-limited attempts
            action="login",
            actor_email=email,
            outcome="failure",
            detail="Rate limited",
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after_int)},
        )

    with db_session() as con:
        # Generic delay to mitigate timing attacks
        row = con.execute(
            "SELECT id, email, password_hash, role, is_active FROM users WHERE email = :email",
            {"email": payload.email},
        ).fetchone()

        password_valid = False
        if row is not None and row["is_active"] == 1:
            password_valid = verify_password(payload.password, row["password_hash"])

        if not password_valid:
            # Still create a fake session lookup to keep timing similar
            _ = hash_token("dummy")
            rate_limiter.record_failure(ip_address, email)
            # Re-check lockout after recording failure
            is_limited_now, retry_after_now = rate_limiter.is_rate_limited(
                ip_address, email
            )
            audit(
                con,
                action="login",
                actor_email=payload.email,
                outcome="failure",
                detail="Invalid credentials",
                ip_address=ip_address,
                user_agent=request.headers.get("user-agent"),
            )
            headers: dict[str, str] = {}
            if is_limited_now and retry_after_now is not None:
                headers["Retry-After"] = str(int(retry_after_now))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers=headers,
            )

        user = dict(row)
        # Revoke all existing sessions for this user to prevent session fixation.
        # An attacker could have set a session cookie before login; revoking all
        # prior sessions ensures only the newly created session is valid.
        revoke_all_sessions_for_user(con, user["id"])
        rate_limiter.record_success(ip_address, email)
        audit(
            con,
            action="login",
            actor_id=user["id"],
            actor_email=user["email"],
            outcome="success",
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
        )
        token = create_session(
            con,
            user_id=user["id"],
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
        )

    # Set session cookie (outside the db session context)
    response = JSONResponse(
        content={
            "user_id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "expires_at": (
                datetime.now(timezone.utc).timestamp() + settings.session_ttl_seconds
            ),
        }
    )
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path=settings.session_cookie_path,
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.post("/logout")
def logout(
    request: Request,
    current_user: dict[str, Any] = Depends(require_auth),
):
    """Revoke the current session and clear the session cookie.

    Always clears the session cookie on the client side, even if the server-side
    session no longer exists (e.g. already expired or revoked). This ensures the
    client cannot reuse a stale cookie.
    """
    token = request.cookies.get(settings.session_cookie_name)
    with db_session() as con:
        if token:
            revoke_session(con, token)
            audit(
                con,
                action="logout",
                actor_id=current_user["user_id"],
                actor_email=current_user["email"],
                outcome="success",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )

    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
        domain=settings.session_cookie_domain,
    )
    # Also clear the CSRF cookie on logout
    response.delete_cookie(
        key="csrf_token",
        path="/",
        domain=settings.session_cookie_domain,
    )
    return response


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: dict[str, Any] = Depends(require_auth),
):
    """Return the currently authenticated user's profile."""
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "full_name": None,
        "role": current_user["role"],
        "is_active": bool(current_user["is_active"]),
        "created_at": "",
    }


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.post("/admin/users", response_model=UserResponse, status_code=201)
def create_user(
    payload: CreateUserRequest,
    current_user: dict[str, Any] = Depends(require_admin),
    request: Request = None,
):
    """Create a new user account (administrator only)."""
    with db_session() as con:
        existing = con.execute(
            "SELECT id FROM users WHERE email = :email",
            {"email": payload.email},
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        user_id = secrets.token_urlsafe(16)
        password_hash_val = hash_password(payload.password)
        now = datetime.now(timezone.utc).isoformat()

        con.execute(
            """
            INSERT INTO users (id, email, password_hash, full_name, role, is_active, created_at, updated_at)
            VALUES (:id, :email, :password_hash, :full_name, :role, 1, :created_at, :updated_at)
            """,
            {
                "id": user_id,
                "email": payload.email,
                "password_hash": password_hash_val,
                "full_name": payload.full_name,
                "role": payload.role,
                "created_at": now,
                "updated_at": now,
            },
        )
        con.commit()

        audit(
            con,
            action="user_create",
            actor_id=current_user["user_id"],
            actor_email=current_user["email"],
            resource="user",
            resource_id=user_id,
            outcome="success",
            detail=f"Created user {payload.email} with role {payload.role}",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )

    return {
        "user_id": user_id,
        "email": payload.email,
        "full_name": payload.full_name,
        "role": payload.role,
        "is_active": True,
        "created_at": now,
    }


@router.get("/admin/users", response_model=list[UserResponse])
def list_users(
    current_user: dict[str, Any] = Depends(require_admin),
):
    """List all user accounts (administrator only)."""
    with db_session() as con:
        rows = con.execute(
            "SELECT id, email, full_name, role, is_active, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "user_id": r["id"],
                "email": r["email"],
                "full_name": r["full_name"],
                "role": r["role"],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    current_user: dict[str, Any] = Depends(require_admin),
    request: Request = None,
):
    """Update a user account: deactivate/reactivate, change role or name (admin only)."""
    with db_session() as con:
        row = con.execute(
            "SELECT id, email, full_name, role, is_active FROM users WHERE id = :id",
            {"id": user_id},
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        updates = []
        params: dict[str, Any] = {"id": user_id}
        if payload.is_active is not None:
            updates.append("is_active = :is_active")
            params["is_active"] = 1 if payload.is_active else 0
        if payload.role is not None:
            updates.append("role = :role")
            params["role"] = payload.role
        if payload.full_name is not None:
            updates.append("full_name = :full_name")
            params["full_name"] = payload.full_name

        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

        updates.append("updated_at = :updated_at")
        params["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Revoke all sessions if deactivating
        if payload.is_active is False:
            revoke_all_sessions_for_user(con, user_id)

        con.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = :id",
            params,
        )
        con.commit()

        audit(
            con,
            action="user_update",
            actor_id=current_user["user_id"],
            actor_email=current_user["email"],
            resource="user",
            resource_id=user_id,
            outcome="success",
            detail=f"Updated user {user_id}: fields={list(params.keys())}",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )

        updated = con.execute(
            "SELECT id, email, full_name, role, is_active, created_at FROM users WHERE id = :id",
            {"id": user_id},
        ).fetchone()
        return {
            "user_id": updated["id"],
            "email": updated["email"],
            "full_name": updated["full_name"],
            "role": updated["role"],
            "is_active": bool(updated["is_active"]),
            "created_at": updated["created_at"],
        }


@router.post("/admin/patient-access", response_model=PatientAccessResponse, status_code=201)
def grant_patient_access(
    payload: PatientAccessRequest,
    current_user: dict[str, Any] = Depends(require_admin),
    request: Request = None,
):
    """Grant a user access to a patient record (administrator only)."""
    with db_session() as con:
        # Verify user exists and is active
        user_row = con.execute(
            "SELECT id, is_active FROM users WHERE id = :id", {"id": payload.user_id}
        ).fetchone()
        if user_row is None or not user_row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive",
            )

        # Verify patient exists
        patient_row = con.execute(
            "SELECT id FROM patients WHERE id = :id", {"id": payload.patient_id}
        ).fetchone()
        if patient_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        access_id = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc).isoformat()

        con.execute(
            """
            INSERT OR REPLACE INTO patient_access (id, user_id, patient_id, granted_by, granted_at, revoked_at)
            VALUES (:id, :user_id, :patient_id, :granted_by, :granted_at, NULL)
            """,
            {
                "id": access_id,
                "user_id": payload.user_id,
                "patient_id": payload.patient_id,
                "granted_by": current_user["user_id"],
                "granted_at": now,
            },
        )
        con.commit()

        audit(
            con,
            action="patient_access_grant",
            actor_id=current_user["user_id"],
            actor_email=current_user["email"],
            resource="patient_access",
            resource_id=access_id,
            patient_id=payload.patient_id,
            outcome="success",
            detail=f"Granted user {payload.user_id} access to patient {payload.patient_id}",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )

    return {
        "id": access_id,
        "user_id": payload.user_id,
        "patient_id": payload.patient_id,
        "granted_by": current_user["user_id"],
        "granted_at": now,
        "revoked_at": None,
    }


@router.delete("/admin/patient-access", status_code=204)
def revoke_patient_access(
    payload: PatientAccessRequest,
    current_user: dict[str, Any] = Depends(require_admin),
    request: Request = None,
):
    """Revoke a user's access to a patient (administrator only)."""
    with db_session() as con:
        con.execute(
            """
            UPDATE patient_access
            SET revoked_at = :revoked_at
            WHERE user_id = :user_id AND patient_id = :patient_id AND revoked_at IS NULL
            """,
            {
                "revoked_at": datetime.now(timezone.utc).isoformat(),
                "user_id": payload.user_id,
                "patient_id": payload.patient_id,
            },
        )
        con.commit()

        audit(
            con,
            action="patient_access_revoke",
            actor_id=current_user["user_id"],
            actor_email=current_user["email"],
            resource="patient_access",
            patient_id=payload.patient_id,
            outcome="success",
            detail=f"Revoked user {payload.user_id} access to patient {payload.patient_id}",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )

    return JSONResponse(status_code=204, content=None)


@router.get("/admin/patient-access", response_model=list[PatientAccessResponse])
def list_patient_access(
    current_user: dict[str, Any] = Depends(require_admin),
):
    """List all patient access grants (administrator only)."""
    with db_session() as con:
        rows = con.execute(
            """
            SELECT id, user_id, patient_id, granted_by, granted_at, revoked_at
            FROM patient_access ORDER BY granted_at DESC
            """
        ).fetchall()
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "patient_id": r["patient_id"],
                "granted_by": r["granted_by"],
                "granted_at": r["granted_at"],
                "revoked_at": r["revoked_at"],
            }
            for r in rows
        ]
