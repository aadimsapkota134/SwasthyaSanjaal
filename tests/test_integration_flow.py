import fitz
import pytest
from fastapi.testclient import TestClient
from backend.main import app

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_full_end_to_end_backend_clinical_flow(clinician_client):
    # Step 1: Health Probe Check
    health_resp = clinician_client.get("/api/v1/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["service"] == "swasthyasanjaal-api"
    assert health_data["status"] == "ok"

    # Step 2: Patient Discovery
    patients_resp = clinician_client.get("/api/v1/patients")
    assert patients_resp.status_code == 200
    patients = patients_resp.json()
    assert len(patients) >= 1
    target_patient_id = "patient_ram"

    initial_timeline = clinician_client.get(f"/api/v1/patients/{target_patient_id}/record").json()
    initial_entry_count = len(initial_timeline["entries"])

    # Step 3: Document Intake via Digital PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        fitz.Point(50, 72),
        "Dhulikhel Hospital\nRx: Tab Metformin 500mg od. Tab Paracetamol 500mg sos.\nCough present. Fever chaina.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    ocr_resp = clinician_client.post(
        "/api/v1/intake/ocr",
        files={"file": ("dhulikhel_rx.pdf", pdf_bytes, "application/pdf")},
        data={"use_model": "false", "correct": "true", "document_class": "prescription"},
    )
    assert ocr_resp.status_code == 200
    intake_data = ocr_resp.json()
    assert intake_data["extraction_method"] == "pymupdf"
    assert intake_data["document_class"] == "prescription"
    assert intake_data["normalized"] is not None
    concepts = intake_data["normalized"]["concepts"]
    assert len(concepts) >= 1

    # Verify Approval-Before-Write safety guarantee: intake MUST NOT have altered patient timeline!
    timeline_after_intake = clinician_client.get(f"/api/v1/patients/{target_patient_id}/record").json()
    assert len(timeline_after_intake["entries"]) == initial_entry_count

    # Step 4: Clinician Approval-Before-Write Gate
    commit_payload = {
        "input_type": "pdf",
        "record_date": "2026-10-09",
        "record_date_bs": "२०८३ असोज २३",
        "facility_name": "धुलिखेल अस्पताल",
        "document_class": "prescription",
        "raw_transcript": intake_data["raw_transcript"],
        "corrected_text": intake_data["corrected_text"],
        "extraction_method": intake_data["extraction_method"],
        "asset_path": intake_data["asset_path"],
        "meaning_np": "मधुमेह र खोकी नियन्त्रणका लागि सिफारिस गरिएको औषधि।",
        "normalized": intake_data["normalized"],
        "notes": intake_data["notes"],
    }
    commit_resp = clinician_client.post(
        f"/api/v1/patients/{target_patient_id}/entries",
        json=commit_payload,
    )
    assert commit_resp.status_code == 201
    created_entry = commit_resp.json()
    assert created_entry["patient_id"] == target_patient_id
    assert created_entry["facility_name"] == "धुलिखेल अस्पताल"

    # Step 5: Timeline & Entry Detail Verification
    updated_timeline = clinician_client.get(f"/api/v1/patients/{target_patient_id}/record").json()
    assert len(updated_timeline["entries"]) == initial_entry_count + 1
    assert updated_timeline["entries"][0]["id"] == created_entry["id"]

    entry_detail_resp = clinician_client.get(
        f"/api/v1/patients/{target_patient_id}/entries/{created_entry['id']}"
    )
    assert entry_detail_resp.status_code == 200
    assert entry_detail_resp.json()["id"] == created_entry["id"]

    # Step 6: Standards Interoperability (Segno QR Code)
    qr_resp = clinician_client.get(f"/api/v1/patients/{target_patient_id}/qr")
    assert qr_resp.status_code == 200
    qr_data = qr_resp.json()
    assert qr_data["qr_token"]
    assert qr_data["qr_png"].startswith("data:image/png;base64,")

    qr_image_resp = clinician_client.get(f"/api/v1/patients/{target_patient_id}/qr.png")
    assert qr_image_resp.status_code == 200
    assert qr_image_resp.headers["content-type"] == "image/png"
    assert qr_image_resp.content.startswith(PNG_MAGIC)

    # Step 7: Standards Interoperability (HL7 FHIR R4 Bundle)
    fhir_resp = clinician_client.get(f"/api/v1/patients/{target_patient_id}/fhir")
    assert fhir_resp.status_code == 200
    fhir_bundle = fhir_resp.json()
    assert fhir_bundle["resourceType"] == "Bundle"
    assert fhir_bundle["type"] == "collection"
    assert fhir_bundle["synthetic"] is True

    # Strict Clinical Safety: No Condition resource in FHIR bundle is negated
    for entry in fhir_bundle["entry"]:
        res = entry["resource"]
        if res["resourceType"] == "Condition":
            for coding in res.get("code", {}).get("coding", []):
                assert not coding.get("display", "").lower().startswith("no ")
