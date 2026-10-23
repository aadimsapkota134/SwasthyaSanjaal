import pytest
from fastapi.testclient import TestClient
from backend.main import app

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_get_patient_qr_json(clinician_client):
    response = clinician_client.get("/api/v1/patients/patient_ram/qr")
    assert response.status_code == 200
    data = response.json()
    assert data["sanjaal_id"].startswith(("SS-", "SANJAAL-"))
    assert data["sanchai_id"].startswith("SANCHAI-")
    assert data["qr_token"]
    assert data["encodes"] == f"sanchai://p/{data['qr_token']}"
    assert data["qr_png"].startswith("data:image/png;base64,")
    assert any("Penicillin" in a for a in data["allergies"])


def test_get_patient_qr_png_param(clinician_client):
    response = clinician_client.get("/api/v1/patients/patient_ram/qr?format=png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(PNG_MAGIC)


def test_get_patient_qr_image_route(clinician_client):
    response = clinician_client.get("/api/v1/patients/patient_ram/qr.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(PNG_MAGIC)


def test_get_qr_not_found(clinician_client):
    res = clinician_client.get("/api/v1/patients/nonexistent_patient/qr")
    assert res.status_code == 404


def test_qr_payload_only_exposes_emergency_fields(clinician_client):
    """The emergency payload must never carry internal IDs, demographic
    detail beyond the emergency set, or full record contents."""
    res = clinician_client.get("/api/v1/patients/patient_ram/qr")
    assert res.status_code == 200
    data = res.json()

    allowed = {
        "sanjaal_id", "sanchai_id", "arogya_id", "qr_token", "name", "name_np",
        "blood_group", "allergies", "conditions", "synthetic",
        "encodes", "qr_png",
    }
    assert set(data.keys()) <= allowed

    assert "id" not in data
    assert "dob" not in data
    assert "district" not in data
    assert "entries" not in data
    assert data["encodes"] == f"sanchai://p/{data['qr_token']}"


def test_qr_conditions_exclude_negated_findings(clinician_client):
    """Patient Ram's record contains a negated 'Fever' (ज्वरो छैन); the
    emergency payload must not surface it as an active condition."""
    res = clinician_client.get("/api/v1/patients/patient_ram/qr")
    assert res.status_code == 200
    condition_names = [c.split(" (")[0] for c in res.json()["conditions"]]
    assert "Fever" not in condition_names
    assert "Typhoid fever" in condition_names
