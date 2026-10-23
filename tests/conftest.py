"""Pytest configuration and shared fixtures for SwasthyaSanjaal backend tests.

Provides test isolation by overriding the database path and upload directory
to per-test temporary locations. Includes authentication fixtures for testing
protected routes.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.auth.password import hash_password
from backend.auth.session import create_session, hash_token
from backend.config import settings
from backend.db import session as db_session, init_db
from backend.seed import seed_all, bootstrap_admin


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Route database and uploads to per-test temp locations."""
    test_db = str(tmp_path / "test_swasthyasanjaal.db")
    test_uploads = str(tmp_path / "uploads")

    monkeypatch.setattr(settings, "db_path", test_db)
    monkeypatch.setattr(settings, "upload_dir", test_uploads)

    yield tmp_path


@pytest.fixture
def client():
    """Standard FastAPI TestClient with an isolated database."""
    from backend.main import app

    init_db()
    with db_session() as con:
        seed_all(con)
        # Bootstrap an admin user
        bootstrap_admin(
            con,
            email="admin@swasthya.example",
            password="AdminPass123!",
            full_name="System Administrator",
        )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_client(client):
    """Authenticated TestClient as administrator."""
    # Log in as admin
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@swasthya.example", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return client  # cookies are preserved by TestClient


@pytest.fixture
def clinician_client(client, tmp_path):
    """Authenticated TestClient as a clinician with access to patient_ram."""
    from backend.db import session as db_session

    with db_session() as con:
        # Create a clinician user
        clinician_id = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc).isoformat()
        con.execute(
            """
            INSERT INTO users (id, email, password_hash, full_name, role, is_active, created_at, updated_at)
            VALUES (:id, :email, :password_hash, :full_name, 'clinician', 1, :created_at, :updated_at)
            """,
            {
                "id": clinician_id,
                "email": "clinician@swasthya.example",
                "password_hash": hash_password("ClinicianPass123!"),
                "full_name": "Test Clinician",
                "role": "clinician",
                "created_at": now,
                "updated_at": now,
            },
        )
        # Grant access to patient_ram
        access_id = secrets.token_urlsafe(16)
        con.execute(
            """
            INSERT INTO patient_access (id, user_id, patient_id, granted_by, granted_at, revoked_at)
            VALUES (:id, :user_id, :patient_id, :granted_by, :granted_at, NULL)
            """,
            {
                "id": access_id,
                "user_id": clinician_id,
                "patient_id": "patient_ram",
                "granted_by": clinician_id,
                "granted_at": now,
            },
        )
        con.commit()

    # Log in as clinician
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "clinician@swasthya.example", "password": "ClinicianPass123!"},
    )
    assert resp.status_code == 200, f"Clinician login failed: {resp.text}"
    return client


@pytest.fixture
def unassigned_clinician_client(client, tmp_path):
    """Authenticated TestClient as a clinician with NO patient access."""
    from backend.db import session as db_session

    with db_session() as con:
        clinician_id = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc).isoformat()
        con.execute(
            """
            INSERT INTO users (id, email, password_hash, full_name, role, is_active, created_at, updated_at)
            VALUES (:id, :email, :password_hash, :full_name, 'clinician', 1, :created_at, :updated_at)
            """,
            {
                "id": clinician_id,
                "email": "unassigned@swasthya.example",
                "password_hash": hash_password("UnassignedPass123!"),
                "full_name": "Unassigned Clinician",
                "role": "clinician",
                "created_at": now,
                "updated_at": now,
            },
        )
        con.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "unassigned@swasthya.example", "password": "UnassignedPass123!"},
    )
    assert resp.status_code == 200, f"Unassigned login failed: {resp.text}"
    return client
