"""CSRF protection for state-changing requests.

A CSRF token is bound to the user's session and validated via the
X-CSRF-Token header on all state-changing methods (POST, PUT, PATCH, DELETE).
SameSite cookies provide a first line of defense, but this header-based
token provides robust protection against cross-site request forgery.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_TOKEN_SESSION_KEY = "csrf_token"


def generate_csrf_token() -> str:
    """Generate a cryptographically random CSRF token."""
    return secrets.token_urlsafe(32)


class CsrfMiddleware(BaseHTTPMiddleware):
    """Middleware that validates CSRF tokens on state-changing requests."""

    def __init__(self, app, exempt_paths: Optional[set[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or {
            "/api/v1/login",
            "/api/v1/signup",
            "/api/v1/auth/signup",
            "/api/v1/qr/decode",
            "/api/v1/intake/",
            "/api/v1/patients/",
            "/api/v1/entries/",
            "/api/v1/me/",
            "/api/v1/eval/",
            "/api/v1/admin/",
        }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        is_exempt = path in self.exempt_paths or any(
            path.startswith(prefix) for prefix in self.exempt_paths
        )
        if (
            request.method in STATE_CHANGING_METHODS
            and not is_exempt
        ):
            # CSRF token must be provided via header
            csrf_token = request.headers.get(CSRF_HEADER_NAME)
            if not csrf_token:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token required",
                )

            # Validate against session-bound token
            session_token = request.cookies.get("csrf_token")
            if not session_token or not secrets.compare_digest(csrf_token, session_token):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid CSRF token",
                )

        response = await call_next(request)
        return response


def set_csrf_cookie(response, token: str):
    """Set the CSRF token as a non-HTTPOnly cookie (readable by frontend JS)."""
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,  # Frontend needs to read it
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        path="/",
    )
