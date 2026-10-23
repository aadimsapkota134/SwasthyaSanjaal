from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.db import init_db, session as db_session
from backend.main import app
from backend.seed import seed_all


@pytest.fixture(autouse=True)
def setup_portal_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_portal_auth.db"
    monkeypatch.setattr(settings, "db_path", str(test_db))
    init_db()
    with db_session() as con:
        seed_all(con)
    return test_db


def test_individual_cannot_access_patient_directory():
    """Individuals must receive 403 Forbidden when trying to list all clinic patients."""
    client = TestClient(app)
    signup_resp = client.post(
        "/api/v1/signup",
        json={
            "email": "individual.portal@example.com",
            "password": "StrongPassword123!",
            "full_name": "Portal Individual",
            "role": "individual",
        },
    )
    assert signup_resp.status_code == 201

    resp = client.get("/api/v1/patients", cookies=signup_resp.cookies)
    assert resp.status_code == 403
    assert "Healthcare provider access required" in resp.json()["detail"]


def test_individual_sees_own_patient_and_reports_only():
    """Individuals access /me/patient and /me/reports and cannot manipulate target patient_id."""
    client = TestClient(app)
    signup_resp = client.post(
        "/api/v1/signup",
        json={
            "email": "individual.reports@example.com",
            "password": "StrongPassword123!",
            "full_name": "Aasha Shrestha",
            "role": "individual",
        },
    )
    assert signup_resp.status_code == 201

    # 1. Fetch own patient profile
    pat_resp = client.get("/api/v1/me/patient", cookies=signup_resp.cookies)
    assert pat_resp.status_code == 200
    pat_data = pat_resp.json()
    assert pat_data["name"] == "Aasha Shrestha"
    pat_id = pat_data["id"]

    # 2. Initially empty reports
    reports_resp = client.get("/api/v1/me/reports", cookies=signup_resp.cookies)
    assert reports_resp.status_code == 200
    assert reports_resp.json() == []

    # 3. Normalize a clinical text snippet to get valid NormalizeResponse
    norm_resp = client.post(
        "/api/v1/intake/normalize",
        json={"text": "सिटामोल 500 एमजी लिनुहोस्", "use_model": False},
    )
    assert norm_resp.status_code == 200
    norm_data = norm_resp.json()

    # 4. Upload report via /me/reports (patient_id derived server-side)
    entry_payload = {
        "input_type": "text",
        "document_class": "prescription",
        "facility_name": "Bir Hospital",
        "record_date": "2026-03-15",
        "raw_transcript": "सिटामोल 500 एमजी लिनुहोस्",
        "corrected_text": "सिटामोल 500 एमजी लिनुहोस्",
        "extraction_method": "direct",
        "normalized": norm_data,
        "meaning_np": "ज्वरो र दुखाइ कम गर्न",
        "notes": [],
    }

    upload_resp = client.post("/api/v1/me/reports", json=entry_payload, cookies=signup_resp.cookies)
    assert upload_resp.status_code == 200
    uploaded_entry = upload_resp.json()
    assert uploaded_entry["patient_id"] == pat_id

    # 4. Now /me/reports returns this entry
    reports_after = client.get("/api/v1/me/reports", cookies=signup_resp.cookies)
    assert reports_after.status_code == 200
    reports_list = reports_after.json()
    assert len(reports_list) == 1
    assert reports_list[0]["id"] == uploaded_entry["id"]


def test_clinician_can_list_assigned_patients():
    """Clinicians retain provider access to patients directory."""
    client = TestClient(app)
    signup_resp = client.post(
        "/api/v1/signup",
        json={
            "email": "doctor.clinician@clinic.np",
            "password": "DoctorPass12345!",
            "full_name": "Dr. Aarav",
            "role": "clinician",
        },
    )
    assert signup_resp.status_code == 201

    resp = client.get("/api/v1/patients", cookies=signup_resp.cookies)
    assert resp.status_code == 200
    patients = resp.json()
    assert len(patients) >= 3
