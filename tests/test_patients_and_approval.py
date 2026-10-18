import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_list_patients(client):
    response = client.get("/api/v1/patients")
    assert response.status_code == 200
    patients = response.json()
    assert len(patients) >= 3
    ram = next((p for p in patients if p["id"] == "patient_ram"), None)
    assert ram is not None
    assert ram["name"] == "Ram Bahadur Shrestha"
    assert ram["sanjaal_id"].startswith(("SS-", "SANJAAL-"))
    assert ram["sanchai_id"].startswith("SANCHAI-")
    assert ram["entry_count"] >= 2


def test_get_patient_detail(client):
    response = client.get("/api/v1/patients/patient_ram")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "patient_ram"
    assert data["name"] == "Ram Bahadur Shrestha"
    assert len(data["allergies"]) >= 1
    assert data["allergies"][0]["substance_en"] == "Penicillin"
    assert "conditions" in data


def test_get_patient_record_timeline(client):
    response = client.get("/api/v1/patients/patient_ram/record")
    assert response.status_code == 200
    data = response.json()
    assert "patient" in data
    assert "entries" in data
    entries = data["entries"]
    assert len(entries) >= 2
    dates = [e["record_date"] for e in entries]
    assert dates == sorted(dates, reverse=True)


def test_approval_before_write_gate(client):
    # 1. Normalize intake payload (intake never mutates database)
    intake_resp = client.post(
        "/api/v1/intake/normalize",
        json={"text": "खोकी लागेको छ प्यारासिटामोल ५०० एमजी लिनुभयो", "use_model": False},
    )
    assert intake_resp.status_code == 200
    norm_data = intake_resp.json()

    rec_before = client.get("/api/v1/patients/patient_maya/record").json()
    initial_count = len(rec_before["entries"])

    # 2. Explicit Human-Confirmation commit
    commit_payload = {
        "input_type": "text",
        "record_date": "2026-10-09",
        "record_date_bs": "२०८३ असोज २३",
        "facility_name": "पाटन अस्पताल",
        "document_class": "prescription",
        "raw_transcript": "खोकी लागेको छ प्यारासिटामोल ५०० एमजी लिनुभयो",
        "corrected_text": "खोकी लागेको छ प्यारासिटामोल ५०० एमजी लिनुभयो",
        "extraction_method": "direct",
        "meaning_np": "खोकी र ज्वरो नियन्त्रणका लागि औषधि।",
        "normalized": norm_data,
        "notes": [],
    }

    commit_res = client.post("/api/v1/patients/patient_maya/entries", json=commit_payload)
    assert commit_res.status_code == 201
    entry_detail = commit_res.json()
    assert entry_detail["patient_id"] == "patient_maya"
    assert entry_detail["record_date"] == "2026-10-09"
    assert entry_detail["document_class"] == "prescription"
    assert len(entry_detail["concepts"]) >= 1

    rec_after = client.get("/api/v1/patients/patient_maya/record").json()
    assert len(rec_after["entries"]) == initial_count + 1

    entry_id = entry_detail["id"]
    get_entry_res = client.get(f"/api/v1/patients/patient_maya/entries/{entry_id}")
    assert get_entry_res.status_code == 200
    assert get_entry_res.json()["id"] == entry_id


def test_invalid_patient_or_date(client):
    dummy_payload = {
        "input_type": "text",
        "record_date": "2026-10-09",
        "normalized": {"text": "test", "prepared_text": "test", "concepts": []},
    }
    res_404 = client.post("/api/v1/patients/nonexistent_patient/entries", json=dummy_payload)
    assert res_404.status_code == 404

    invalid_date_payload = {
        **dummy_payload,
        "record_date": "2083-04-12",
    }
    res_422 = client.post("/api/v1/patients/patient_ram/entries", json=invalid_date_payload)
    assert res_422.status_code == 422


def test_commit_rejects_invalid_input_type_and_document_class(client):
    base = {
        "record_date": "2026-10-09",
        "normalized": {"text": "test", "prepared_text": "test", "concepts": []},
    }
    before = len(client.get("/api/v1/patients/patient_maya/record").json()["entries"])

    # Invalid input_type -> 422
    res = client.post(
        "/api/v1/patients/patient_maya/entries",
        json={**base, "input_type": "fax"},
    )
    assert res.status_code == 422
    assert "input_type" in res.json()["detail"]

    # Unknown document_class -> 422
    res = client.post(
        "/api/v1/patients/patient_maya/entries",
        json={**base, "input_type": "text", "document_class": "receipt"},
    )
    assert res.status_code == 422
    assert "document_class" in res.json()["detail"]

    after = len(client.get("/api/v1/patients/patient_maya/record").json()["entries"])
    assert after == before

    # Speech FCHV assessment commits cleanly after human confirmation
    res = client.post(
        "/api/v1/patients/patient_maya/entries",
        json={**base, "input_type": "voice", "document_class": "fchv_assessment"},
    )
    assert res.status_code == 201
    assert res.json()["document_class"] == "fchv_assessment"


def test_get_patient_summary_pdf(client):
    res = client.get("/api/v1/patients/patient_ram/summary.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")
    assert len(res.content) > 1000


def test_get_entry_by_id_and_commit(client):
    entries = client.get("/api/v1/patients/patient_ram/entries").json()
    assert len(entries) >= 1
    entry_id = entries[0]["id"]

    entry_res = client.get(f"/api/v1/entries/{entry_id}")
    assert entry_res.status_code == 200
    assert entry_res.json()["id"] == entry_id

    commit_res = client.post(f"/api/v1/entries/{entry_id}/commit")
    assert commit_res.status_code == 200
    assert commit_res.json()["committed"] is True
    assert commit_res.json()["entry"]["id"] == entry_id


def test_get_emergency_by_token(client):
    patient = client.get("/api/v1/patients/patient_ram").json()
    token = patient["qr_token"]

    res = client.get(f"/api/v1/emergency/{token}")
    assert res.status_code == 200
    data = res.json()
    assert "patient" in data
    assert "qrPayload" in data
    assert "highlights" in data
    assert data["patient"]["id"] == "patient_ram"
    assert data["qrPayload"]["blood_group"] == "B+"


def test_get_dashboard_summary(client):
    res = client.get("/api/v1/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "patient" in data
    assert "entries" in data
    assert "intake" in data
