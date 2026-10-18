from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

from backend.record.entries import StoredNormalization
from backend.schemas import FhirBundle

logger = logging.getLogger("swasthyasanjaal.backend.fhir")

SYSTEM_ICD11 = "http://id.who.int/icd/release/11/mms"
SYSTEM_ICD10 = "http://hl7.org/fhir/sid/icd-10"
SYSTEM_LEXICON = "urn:swasthyasanjaal:nepali-clinical-lexicon"
SYSTEM_FHIR_EVENT = "http://terminology.hl7.org/CodeSystem/v3-ActCode"

RESOURCE_FOR_TYPE = {
    "condition": "Condition",
    "symptom": "Condition",
    "investigation": "Observation",
    "drug_generic": "MedicationRequest",
    "drug_brand": "MedicationRequest",
}


def _fhir_safe_id(internal_id: str) -> str:
    """Convert an internal database ID to a FHIR R4-compliant resource ID.

    FHIR R4 requires resource IDs to match ``^[A-Za-z0-9\\-.]+$``. Internal
    database IDs use underscores (e.g. ``patient_ram``) which are invalid, so
    underscores are replaced with hyphens.
    """
    return internal_id.replace("_", "-")


def _codeable(concept: Any) -> dict[str, Any]:
    codings: list[dict[str, str]] = [
        {
            "system": SYSTEM_LEXICON,
            "code": concept.concept_id,
            "display": concept.canonical_en,
        }
    ]
    if concept.icd11_code:
        codings.append(
            {"system": SYSTEM_ICD11, "code": concept.icd11_code, "display": concept.canonical_en}
        )
    if concept.icd10_code:
        codings.append(
            {"system": SYSTEM_ICD10, "code": concept.icd10_code, "display": concept.canonical_en}
        )
    return {"coding": codings, "text": concept.canonical_np}


def _patient_resource(patient: Any) -> dict[str, Any]:
    sanjaal_id = (
        (patient["sanjaal_id"] if "sanjaal_id" in patient.keys() else None)
        or (patient["sanchai_id"].replace("SANCHAI-", "SANJAAL-") if patient["sanchai_id"] else None)
        or f"SANJAAL-{patient['id']}"
    )
    sanchai_id = patient["sanchai_id"] or patient["arogya_id"] or f"SANCHAI-{patient['id']}"
    identifiers = [
        {
            "system": "urn:swasthyasanjaal:patient-id",
            "value": sanjaal_id,
        },
        {
            "system": "urn:sanchai:patient-id",
            "value": sanchai_id,
        },
    ]
    if patient["arogya_id"]:
        identifiers.append(
            {
                "system": "urn:swasthyasanjaal:legacy-arogya-id",
                "value": patient["arogya_id"],
            }
        )

    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": _fhir_safe_id(patient["id"]),
        "identifier": identifiers,
        "name": [{"text": patient["name_np"] or patient["name"]}],
    }
    if patient["gender"]:
        resource["gender"] = patient["gender"]
    if patient["dob"]:
        resource["birthDate"] = patient["dob"]
    return resource


def _allergy_resources(patient_id: str, allergies: Sequence[Any]) -> list[dict[str, Any]]:
    fhir_patient_id = _fhir_safe_id(patient_id)
    return [
        {
            "resourceType": "AllergyIntolerance",
            "id": _fhir_safe_id(row["id"]),
            "patient": {"reference": f"Patient/{fhir_patient_id}"},
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        "code": "active",
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification-status",
                        "code": "confirmed",
                    }
                ]
            },
            "code": {
                "coding": [
                    {
                        "display": row["substance_en"],
                    }
                ],
                "text": f"{row['substance_en']} ({row['substance_np']})" if row["substance_np"] else row["substance_en"],
            },
            **({"criticality": "high"} if row["severity"] == "severe" else {}),
        }
        for row in allergies
    ]


def _clinical_resources(
    patient_id: str, row: Any, normalization: StoredNormalization
) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    fhir_patient_ref = f"Patient/{_fhir_safe_id(patient_id)}"

    for index, item in enumerate(normalization.concepts):
        # Strict clinical safety rule: negated findings are never emitted as condition resources!
        if item.negated:
            continue

        resource_type = RESOURCE_FOR_TYPE.get(item.concept.concept_type)
        if resource_type is None:
            continue

        entry_id = _fhir_safe_id(f"{row['id']}-{index}")
        codeable = _codeable(item.concept)

        if resource_type == "Condition":
            base: dict[str, Any] = {
                "resourceType": "Condition",
                "id": entry_id,
                "subject": {"reference": fhir_patient_ref},
                "code": codeable,
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            "code": "unconfirmed",
                        }
                    ]
                },
                "recordedDate": row["record_date"],
            }
        elif resource_type == "Observation":
            base = {
                "resourceType": "Observation",
                "id": entry_id,
                "subject": {"reference": fhir_patient_ref},
                "code": codeable,
                "status": "final",
                "effectiveDateTime": row["record_date"],
            }
        else:
            base = {
                "resourceType": "MedicationRequest",
                "id": entry_id,
                "subject": {"reference": fhir_patient_ref},
                "medication": {"concept": codeable},
                "status": "active",
                "intent": "order",
                "authoredOn": row["record_date"],
            }
            if normalization.duration_days or normalization.frequency_per_day:
                timing: dict[str, Any] = {}
                if normalization.frequency_per_day:
                    timing["frequency"] = normalization.frequency_per_day
                    timing["period"] = 1
                    timing["periodUnit"] = "d"
                if normalization.duration_days:
                    timing["duration"] = normalization.duration_days
                    timing["durationUnit"] = "d"
                base["dosageInstruction"] = [{"timing": {"repeat": timing}}]

        resources.append(base)

    return resources


def validate_bundle(bundle_dict: dict[str, Any]) -> None:
    """Validate the FHIR R4 bundle against the ``fhir.resources`` R4 model.

    Raises ``ValidationError`` if any resource in the bundle is structurally
    invalid. This is a development-time safety net: if validation fails it
    indicates a bug in ``_patient_resource`` / ``_clinical_resources`` /
    ``_allergy_resources``.
    """
    from fhir.resources.bundle import Bundle
    from pydantic import ValidationError

    try:
        Bundle(**bundle_dict)
    except ValidationError:
        logger.error("FHIR bundle validation failed; see ValidationError below")
        raise


def build_bundle(
    patient: Any,
    allergies: Sequence[Any],
    entries: Iterable[tuple[Any, StoredNormalization]],
) -> FhirBundle:
    """Assemble HL7 FHIR R4 Collection Bundle strictly excluding negated concepts.

    Every generated resource is structurally validated against the installed
    ``fhir.resources`` R4 model before the bundle is returned, ensuring
    resource IDs, required fields, and reference targets comply with the spec.
    """
    resources: list[dict[str, Any]] = [_patient_resource(patient)]
    resources.extend(_allergy_resources(patient["id"], allergies))

    excluded = 0
    for row, normalization in entries:
        excluded += sum(1 for item in normalization.concepts if item.negated)
        resources.extend(_clinical_resources(patient["id"], row, normalization))

    bundle_dict = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }

    validate_bundle(bundle_dict)

    return FhirBundle(
        resourceType="Bundle",
        type="collection",
        entry=bundle_dict["entry"],
        negated_excluded=excluded,
        synthetic=True,
    )
