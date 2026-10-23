from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.db import init_db, session as db_session
from backend.main import app
from backend.seed import seed_all


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_signup.db"
    monkeypatch.setattr(settings, "db_path", str(test_db))
    init_db()
    with db_session() as con:
        seed_all(con)
    return test_db


def test_signup_individual_success():
    client = TestClient(app)
    response = client.post(
        "/api/v1/signup",
        json={
            "email": "individual.user@example.com",
            "password": "StrongPassword123!",
            "full_name": "Sita Thapa",
            "role": "individual",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "individual.user@example.com"
    assert data["role"] == "individual"
    assert "user_id" in data
    assert settings.session_cookie_name in response.cookies

    # Individual is blocked from provider patient directory (403 Forbidden)
    patients_resp = client.get("/api/v1/patients", cookies=response.cookies)
    assert patients_resp.status_code == 403

    # But individual can access their own personal record via /me/patient
    my_patient_resp = client.get("/api/v1/me/patient", cookies=response.cookies)
    assert my_patient_resp.status_code == 200
    my_patient = my_patient_resp.json()
    assert my_patient["name"] == "Sita Thapa"
    assert "sanjaal_id" in my_patient


def test_signup_clinician_success():
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "dr.karki@clinic.np",
            "password": "DoctorSecretKey456!",
            "full_name": "Dr. Rajesh Karki",
            "role": "clinician",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "dr.karki@clinic.np"
    assert data["role"] == "clinician"


def test_signup_duplicate_email_conflict():
    client = TestClient(app)
    payload = {
        "email": "repeat.user@example.com",
        "password": "PasswordLongEnough789!",
        "full_name": "First Register",
        "role": "individual",
    }
    first_resp = client.post("/api/v1/signup", json=payload)
    assert first_resp.status_code == 201

    second_resp = client.post("/api/v1/signup", json=payload)
    assert second_resp.status_code == 409
    assert "already exists" in second_resp.json()["detail"]


def test_signup_weak_or_common_password():
    client = TestClient(app)
    # Too short
    resp_short = client.post(
        "/api/v1/signup",
        json={
            "email": "weak@example.com",
            "password": "123",
            "role": "individual",
        },
    )
    assert resp_short.status_code == 422

    # Common password
    resp_common = client.post(
        "/api/v1/signup",
        json={
            "email": "common@example.com",
            "password": "password123",
            "role": "individual",
        },
    )
    assert resp_common.status_code in {400, 422}
