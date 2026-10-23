import re

import pytest
from fastapi.testclient import TestClient

from backend.main import app

FHIR_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-\.]+$")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_get_patient_fhir_bundle(clinician_client):
    response = clinician_client.get("/api/v1/patients/patient_ram/fhir")
    assert response.status_code == 200
    data = response.json()

    assert data["resourceType"] == "Bundle"
    assert data["type"] == "collection"
    assert data["synthetic"] is True
    assert isinstance(data["entry"], list)
    assert len(data["entry"]) >= 3

    resource_types = [e["resource"]["resourceType"] for e in data["entry"]]
    assert "Patient" in resource_types
    assert "AllergyIntolerance" in resource_types

    for entry in data["entry"]:
        assert FHIR_ID_PATTERN.match(entry["resource"]["id"]), (
            f"FHIR resource id '{entry['resource']['id']}' violates R4 ID pattern"
        )

    patient_res = next(
        e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "Patient"
    )
    assert patient_res["id"] == "patient-ram"
    identifiers = [ident["value"] for ident in patient_res["identifier"]]
    assert any("SANJAAL-" in v or "SANCHAI-" in v or "AK-" in v for v in identifiers)

    allergy_res = next(
        e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "AllergyIntolerance"
    )
    assert "Penicillin" in allergy_res["code"]["text"]


def test_fhir_validates_against_model(clinician_client):
    """Every resource in the bundle must pass fhir.resources R4 validation."""
    from fhir.resources.bundle import Bundle

    response = clinician_client.get("/api/v1/patients/patient_ram/fhir")
    assert response.status_code == 200
    data = response.json()

    bundle_dict = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": data["entry"],
    }

    bundle = Bundle(**bundle_dict)
    assert bundle.type == "collection"
    assert len(bundle.entry) >= 3


def test_fhir_resource_structure(clinician_client):
    """Verify FHIR resource fields are structurally correct."""
    response = clinician_client.get("/api/v1/patients/patient_ram/fhir")
    assert response.status_code == 200
    data = response.json()

    for entry in data["entry"]:
        res = entry["resource"]
        if res["resourceType"] == "Condition":
            assert "clinicalStatus" in res
            coding = res["clinicalStatus"]["coding"][0]
            assert coding["code"] == "active"
        elif res["resourceType"] == "MedicationRequest":
            assert "medication" in res
            assert "medicationCodeableConcept" not in res
            assert res["medication"]["concept"]["coding"][0]["code"]
            assert res["status"] == "active"
            assert res["intent"] == "order"
        elif res["resourceType"] == "Observation":
            assert res["status"] == "final"

    patient_res = next(
        e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "Patient"
    )
    for entry in data["entry"]:
        res = entry["resource"]
        ref_field = "patient" if res.get("resourceType") == "AllergyIntolerance" else "subject"
        if ref_field in res:
            ref = res[ref_field]["reference"]
            assert ref == f"Patient/{patient_res['id']}"


def test_fhir_strictly_excludes_negated_findings(clinician_client):
    response = clinician_client.get("/api/v1/patients/patient_ram/fhir")
    assert response.status_code == 200
    data = response.json()

    assert data["negated_excluded"] >= 1

    for entry in data["entry"]:
        res = entry["resource"]
        if res["resourceType"] == "Condition":
            codings = res.get("code", {}).get("coding", [])
            for c in codings:
                assert not c.get("display", "").lower().startswith("no ")


def test_fhir_not_found(clinician_client):
    res = clinician_client.get("/api/v1/patients/nonexistent_patient/fhir")
    assert res.status_code == 404


def test_validate_bundle_rejects_invalid_resources():
    """Prove the validator is not vacuous: structurally invalid bundles must raise."""
    from pydantic import ValidationError
    from backend.record.fhir import validate_bundle

    with pytest.raises(ValidationError):
        validate_bundle(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [
                    {"resource": {"resourceType": "Patient", "id": "patient_bad"}}
                ],
            }
        )

    with pytest.raises(ValidationError):
        validate_bundle(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "cond-1",
                            "subject": {"reference": "Patient/patient-ram"},
                            "code": {"text": "Fever"},
                        }
                    }
                ],
            }
        )


def test_fhir_patient_references_point_to_bundle_resources(clinician_client):
    """Every Patient/... reference must resolve to the Patient resource in the bundle."""
    response = clinician_client.get("/api/v1/patients/patient_ram/fhir")
    assert response.status_code == 200
    data = response.json()

    patient_ids = {
        e["resource"]["id"]
        for e in data["entry"]
        if e["resource"]["resourceType"] == "Patient"
    }
    assert len(patient_ids) == 1

    ref_pattern = re.compile(r"^Patient/([A-Za-z0-9\-.]+)$")
    for entry in data["entry"]:
        res = entry["resource"]
        for field_name in ("subject", "patient"):
            if field_name in res:
                match = ref_pattern.match(res[field_name]["reference"])
                assert match, f"malformed reference: {res[field_name]['reference']}"
                assert match.group(1) in patient_ids, (
                    f"dangling reference: {res[field_name]['reference']}"
                )
