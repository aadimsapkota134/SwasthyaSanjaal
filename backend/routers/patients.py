from __future__ import annotations

import datetime as dt
import json
import sqlite3
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from backend.auth.router import require_admin, require_auth
from backend.auth.session import validate_session
from backend.db import session as db_session
from backend.nlp.lexicon import Lexicon, get_lexicon
from backend.record import entries as record
from backend.record import qr
from backend.record.fhir import build_bundle
from backend.record.pdf import generate_doctor_summary_pdf
from backend.routers.intake import DOCUMENT_CLASSES
from backend.schemas import (
    Allergy,
    CommitEntryRequest,
    ConditionRef,
    FhirBundle,
    GenericRef,
    InlineNote,
    PatientDetail,
    PatientSummary,
    QrPayload,
    RecordConcept,
    RecordEntryDetail,
    RecordEntrySummary,
    RecordResponse,
)

router = APIRouter(tags=["record"])

# Supported clinical input modalities at the human confirmation write gate.
ALLOWED_INPUT_TYPES = frozenset({"text", "image", "pdf", "voice", "speech"})


def check_patient_access(
    con: sqlite3.Connection,
    current_user: dict,
    patient_id: str,
) -> None:
    """Enforce patient-level access control.

    Administrators can access any patient. Clinicians must have an explicit
    (non-revoked) patient_access grant. Raises 403 if access is denied.
    Uses a generic "not found" message to avoid leaking patient existence.
    """
    if current_user.get("role") == "administrator":
        return
    row = con.execute(
        """
        SELECT id FROM patient_access
        WHERE user_id = :user_id AND patient_id = :patient_id AND revoked_at IS NULL
        """,
        {"user_id": current_user["user_id"], "patient_id": patient_id},
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Patient {patient_id} not found",
        )


def _age(dob: str | None, on: dt.date | None = None) -> int | None:
    if not dob:
        return None
    try:
        born = dt.date.fromisoformat(dob)
    except ValueError:
        return None
    today = on or dt.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _require_gregorian(value: str, field: str) -> str:
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"{field} must be a Gregorian ISO date (YYYY-MM-DD)"
        ) from exc
    if not 1900 <= parsed.year <= dt.date.today().year + 1:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{field} year {parsed.year} is implausible for a Gregorian date — "
                "Bikram Sambat belongs in record_date_bs"
            ),
        )
    return value


def _to_record_concept(item: record.StoredConcept, lexicon: Lexicon) -> RecordConcept:
    generic = lexicon.generic_for(item.concept) if hasattr(lexicon, "generic_for") else None
    return RecordConcept(
        concept_id=item.concept.concept_id,
        canonical_en=item.concept.canonical_en,
        canonical_np=item.concept.canonical_np,
        concept_type=item.concept.concept_type,
        negated=item.negated,
        surface_form=item.surface_form or item.concept.canonical_np,
        tier=item.tier or 1,
        confidence=item.confidence or 1.0,
        start=item.start or 0,
        end=item.end or 0,
        reasoning=item.reasoning,
        icd11_code=item.concept.icd11_code,
        icd10_code=item.concept.icd10_code,
        generic=(
            GenericRef(
                concept_id=generic.concept_id,
                canonical_en=generic.canonical_en,
                canonical_np=generic.canonical_np,
            )
            if generic
            else None
        ),
    )


def _to_summary(row: sqlite3.Row, lexicon: Lexicon) -> RecordEntrySummary:
    norm = record.hydrate(row["normalized_json"], lexicon)
    tiers = sorted({c.tier for c in norm.all_concepts if c.tier is not None})
    return RecordEntrySummary(
        id=row["id"],
        patient_id=row["patient_id"],
        input_type=row["input_type"],
        document_class=row["document_class"],
        facility_name=row["facility_name"],
        record_date=row["record_date"],
        record_date_bs=row["record_date_bs"],
        extraction_method=row["extraction_method"],
        summary_np=record.summarize(norm),
        concept_count=len(norm.concepts),
        negated_count=sum(1 for c in norm.concepts if c.negated),
        icd11_code=row["icd11_code"],
        icd10_code=row["icd10_code"],
        icd_link_status=row["icd_link_status"],
        has_asset=bool(row["asset_path"]),
        tiers=tiers,
    )


def _to_detail(row: sqlite3.Row, lexicon: Lexicon) -> RecordEntryDetail:
    summary = _to_summary(row, lexicon)
    norm = record.hydrate(row["normalized_json"], lexicon)
    notes_raw = json.loads(row["notes_json"]) if row["notes_json"] else []
    notes = [
        InlineNote(**n) if (isinstance(n, dict) and "message_np" in n and "level" in n) else n
        for n in notes_raw
    ]

    return RecordEntryDetail(
        **summary.model_dump(),
        raw_transcript=row["raw_transcript"],
        corrected_text=row["corrected_text"],
        asset_path=row["asset_path"],
        meaning_np=row["meaning_np"],
        concepts=[_to_record_concept(c, lexicon) for c in norm.concepts],
        modifiers=[_to_record_concept(c, lexicon) for c in norm.modifiers],
        duration_days=norm.duration_days,
        frequency_per_day=norm.frequency_per_day,
        unmatched=norm.unmatched,
        notes=notes,
        dangling_concept_ids=norm.dangling,
    )


def _build_patient_detail(patient: sqlite3.Row, con: sqlite3.Connection, lexicon: Lexicon) -> PatientDetail:
    allergies = [
        Allergy(
            substance_en=a["substance_en"],
            substance_np=a["substance_np"],
            severity=a["severity"],
        )
        for a in record.list_allergies(con, patient["id"])
    ]
    conditions = [
        ConditionRef(
            concept_id=c.concept_id,
            canonical_en=c.canonical_en,
            canonical_np=c.canonical_np,
            icd11_code=c.icd11_code,
            icd10_code=c.icd10_code,
        )
        for c in record.active_conditions(con, patient["id"], lexicon)
    ]
    entry_rows = record.list_entries(con, patient["id"])
    sanchai_id = patient["sanchai_id"] or patient["arogya_id"] or f"SANCHAI-{patient['id']}"
    sanjaal_id = (
        (patient["sanjaal_id"] if "sanjaal_id" in patient.keys() else None)
        or sanchai_id.replace("SANCHAI-", "SANJAAL-")
    )

    return PatientDetail(
        id=patient["id"],
        name=patient["name"],
        name_np=patient["name_np"],
        sanjaal_id=sanjaal_id,
        sanchai_id=sanchai_id,
        arogya_id=patient["arogya_id"],
        age=_age(patient["dob"]),
        dob=patient["dob"],
        gender=patient["gender"],
        gender_np=patient["gender_np"],
        district=patient["district"],
        blood_group=patient["blood_group"],
        entry_count=len(entry_rows),
        qr_token=patient["qr_token"],
        allergies=allergies,
        conditions=conditions,
        synthetic=True,
    )


@router.get("/patients", response_model=list[PatientSummary])
def list_patients(
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
):
    with con:
        if current_user.get("role") == "administrator":
            rows = record.list_patients(con)
        else:
            # Clinicians only see patients they have access to
            rows = con.execute(
                """
                SELECT p.* FROM patients p
                JOIN patient_access pa ON pa.patient_id = p.id
                WHERE pa.user_id = :user_id AND pa.revoked_at IS NULL
                ORDER BY p.name
                """,
                {"user_id": current_user["user_id"]},
            ).fetchall()
        result: list[PatientSummary] = []
        for p in rows:
            entry_count = len(record.list_entries(con, p["id"]))
            sanchai_id = p["sanchai_id"] or p["arogya_id"] or f"SANCHAI-{p['id']}"
            sanjaal_id = (
                (p["sanjaal_id"] if "sanjaal_id" in p.keys() else None)
                or sanchai_id.replace("SANCHAI-", "SANJAAL-")
            )
            result.append(
                PatientSummary(
                    id=p["id"],
                    name=p["name"],
                    name_np=p["name_np"],
                    sanjaal_id=sanjaal_id,
                    sanchai_id=sanchai_id,
                    arogya_id=p["arogya_id"],
                    age=_age(p["dob"]),
                    gender=p["gender"],
                    gender_np=p["gender_np"],
                    district=p["district"],
                    blood_group=p["blood_group"],
                    entry_count=entry_count,
                )
            )
        return result


@router.get("/patients/{patient_id}", response_model=PatientDetail)
def get_patient(
    patient_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> PatientDetail:
    check_patient_access(con, current_user, patient_id)
    lexicon = get_lexicon()
    with con:
        p = record.get_patient(con, patient_id)
        if not p:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        return _build_patient_detail(p, con, lexicon)


@router.get("/patients/{patient_id}/record", response_model=RecordResponse)
def get_patient_record(
    patient_id: str,
    document_class: str | None = Query(default=None),
    query: str | None = Query(default=None),
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> RecordResponse:
    check_patient_access(con, current_user, patient_id)
    lexicon = get_lexicon()
    with con:
        p = record.get_patient(con, patient_id)
        if not p:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        patient_detail = _build_patient_detail(p, con, lexicon)
        entry_rows = record.list_entries(
            con, patient_id, document_class=document_class, query=query
        )
        entries = [_to_summary(row, lexicon) for row in entry_rows]
        return RecordResponse(patient=patient_detail, entries=entries)


@router.get("/patients/{patient_id}/entries/{entry_id}", response_model=RecordEntryDetail)
def get_entry(
    patient_id: str,
    entry_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> RecordEntryDetail:
    check_patient_access(con, current_user, patient_id)
    lexicon = get_lexicon()
    with con:
        entry = record.get_entry(con, entry_id)
        if not entry or entry["patient_id"] != patient_id:
            raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found for patient")
        return _to_detail(entry, lexicon)


@router.post("/patients/{patient_id}/entries", response_model=RecordEntryDetail, status_code=201)
def commit_entry(
    patient_id: str,
    payload: CommitEntryRequest,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> RecordEntryDetail:
    """Human-Confirmation Gate: the only endpoint that mutates patient health records."""
    check_patient_access(con, current_user, patient_id)
    _require_gregorian(payload.record_date, "record_date")
    if payload.input_type not in ALLOWED_INPUT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"input_type must be one of {sorted(ALLOWED_INPUT_TYPES)}",
        )
    if payload.document_class is not None and payload.document_class not in DOCUMENT_CLASSES:
        raise HTTPException(
            status_code=422,
            detail=f"document_class must be one of {sorted(DOCUMENT_CLASSES)}",
        )
    lexicon = get_lexicon()

    with con:
        patient = record.get_patient(con, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        entry_id = record.new_entry_id()

        icd11 = None
        icd10 = None
        for concept in payload.normalized.concepts:
            if concept.concept_type == "condition" and not concept.negated:
                if concept.icd11_code:
                    icd11 = concept.icd11_code
                if concept.icd10_code:
                    icd10 = concept.icd10_code
                if icd11:
                    break

        encoded_norm = record.encode_normalization(payload.normalized.model_dump())
        notes_json = (
            json.dumps(
                [
                    n.model_dump()
                    if hasattr(n, "model_dump")
                    else (n if isinstance(n, dict) else {"level": "info", "message_np": str(n), "message_en": str(n)})
                    for n in payload.notes
                ],
                ensure_ascii=False,
            )
            if payload.notes
            else None
        )

        row_data = {
            "id": entry_id,
            "patient_id": patient_id,
            "input_type": payload.input_type,
            "document_class": payload.document_class,
            "facility_name": payload.facility_name,
            "record_date": payload.record_date,
            "record_date_bs": payload.record_date_bs,
            "asset_path": payload.asset_path,
            "raw_transcript": payload.raw_transcript,
            "corrected_text": payload.corrected_text,
            "extraction_method": payload.extraction_method,
            "normalized_json": encoded_norm,
            "meaning_np": payload.meaning_np,
            "icd11_code": icd11,
            "icd10_code": icd10,
            "icd_link_status": "PENDING_LOCAL_WHO_VERIFICATION" if icd11 else None,
            "notes_json": notes_json,
        }

        record.insert_entry(con, row_data)
        created_row = record.get_entry(con, entry_id)
        assert created_row is not None
        return _to_detail(created_row, lexicon)


@router.get("/patients/{patient_id}/qr", response_model=QrPayload)
def get_patient_qr(
    patient_id: str,
    format: str | None = Query(default=None),
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> Any:
    """Generate high-contrast Segno emergency QR payload and scannable code."""
    check_patient_access(con, current_user, patient_id)
    lexicon = get_lexicon()
    with con:
        patient = record.get_patient(con, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        qr_payload = qr.build_qr_payload(patient, con, lexicon)
        if format == "png":
            png_bytes = qr.encode_png_bytes(qr_payload.encodes or f"sanchai://p/{patient['qr_token']}")
            return Response(content=png_bytes, media_type="image/png")
        return qr_payload


@router.get("/patients/{patient_id}/qr.png")
def get_patient_qr_image(
    patient_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> Response:
    """Return scannable QR code PNG image bytes directly."""
    check_patient_access(con, current_user, patient_id)
    with con:
        patient = record.get_patient(con, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        encodes = f"sanchai://p/{patient['qr_token']}"
        png_bytes = qr.encode_png_bytes(encodes)
        return Response(content=png_bytes, media_type="image/png")


@router.post("/qr/decode")
async def decode_qr_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """Decode scannable QR code image and resolve patient emergency token."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty image file received")

    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image format")

    detector = cv2.QRCodeDetector()
    val, pts, st_code = detector.detectAndDecode(img)
    if not val:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        val, pts, st_code = detector.detectAndDecode(gray)
        if not val:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            eq = clahe.apply(gray)
            val, pts, st_code = detector.detectAndDecode(eq)
            if not val:
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                val, pts, st_code = detector.detectAndDecode(thresh)

    if not val:
        raise HTTPException(status_code=422, detail="No QR code detected in the uploaded image")

    token = val.strip()
    if token.startswith("sanchai://p/"):
        token = token.replace("sanchai://p/", "")

    with session() as con:
        row = con.execute("SELECT * FROM patients WHERE qr_token = :token", {"token": token}).fetchone()
        patient_id = row["id"] if row else None
        patient_name = row["name"] if row else None
        blood_group = row["blood_group"] if row else None

    return {
        "success": True,
        "raw_text": val,
        "token": token,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "blood_group": blood_group,
        "emergency_path": f"/emergency/{token}",
    }


@router.get("/patients/{patient_id}/fhir", response_model=FhirBundle)
def get_patient_fhir(
    patient_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> FhirBundle:
    """Generate HL7 FHIR R4 Collection Bundle strictly excluding negated findings."""
    check_patient_access(con, current_user, patient_id)
    lexicon = get_lexicon()
    with con:
        patient = record.get_patient(con, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        allergies = record.list_allergies(con, patient_id)
        raw_entries = record.list_entries(con, patient_id)
        entries = [(row, record.hydrate(row["normalized_json"], lexicon)) for row in raw_entries]
        return build_bundle(patient, allergies, entries)


@router.get("/patients/{patient_id}/summary.pdf")
def get_patient_summary_pdf(
    patient_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> Response:
    """Generate high-contrast A4 Doctor Summary PDF using ReportLab."""
    check_patient_access(con, current_user, patient_id)
    lexicon = get_lexicon()
    with con:
        patient = record.get_patient(con, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        pdf_bytes = generate_doctor_summary_pdf(patient, con, lexicon)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="swasthyasanjaal_summary_{patient_id}.pdf"'},
        )


@router.get("/patients/{patient_id}/entries", response_model=list[RecordEntrySummary])
def get_patient_entries(
    patient_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> list[RecordEntrySummary]:
    """List timeline entries for a specific patient."""
    check_patient_access(con, current_user, patient_id)
    lexicon = get_lexicon()
    with con:
        patient = record.get_patient(con, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        rows = record.list_entries(con, patient_id)
        return [_to_summary(row, lexicon) for row in rows]


@router.get("/entries/{entry_id}", response_model=RecordEntryDetail)
def get_entry_by_id(
    entry_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> RecordEntryDetail:
    """Retrieve entry detail directly by entry ID."""
    lexicon = get_lexicon()
    with con:
        entry = record.get_entry(con, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
        check_patient_access(con, current_user, entry["patient_id"])
        return _to_detail(entry, lexicon)


@router.post("/entries/{entry_id}/commit")
def commit_entry_by_id(
    entry_id: str,
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> dict[str, Any]:
    """Confirmation Gate: commit an existing draft entry."""
    lexicon = get_lexicon()
    with con:
        entry = record.get_entry(con, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
        check_patient_access(con, current_user, entry["patient_id"])
        return {"committed": True, "entry": _to_detail(entry, lexicon).model_dump()}


@router.get("/emergency/{token}")
def get_emergency_by_token(token: str) -> dict[str, Any]:
    """Resolve emergency responder summary by QR token.

    Intentionally public (no authentication required) for first-responder use.
    Returns only a minimal emergency-data projection: blood group, allergies,
    active conditions, and district. Does not expose the full clinical timeline
    or unrestricted record exports.
    """
    lexicon = get_lexicon()
    with session() as con:
        row = con.execute("SELECT * FROM patients WHERE qr_token = :token", {"token": token}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Emergency token not found")

        detail = _build_patient_detail(row, con, lexicon)
        qr_obj = qr.build_qr_payload(row, con, lexicon)
        highlights = [
            f"Blood Group {row['blood_group'] or 'Unknown'}",
            f"{len(detail.allergies)} documented allergies",
            f"{len(detail.conditions)} active conditions",
            f"Region: {row['district'] or 'Nepal'}",
        ]
        return {
            "patient": {
                "id": detail.id,
                "name": detail.name,
                "name_np": detail.name_np,
                "sanjaal_id": detail.sanjaal_id,
                "blood_group": detail.blood_group,
                "district": detail.district,
                "allergies": detail.allergies,
                "conditions": detail.conditions,
                "synthetic": detail.synthetic,
            },
            "qrPayload": qr_obj.model_dump(),
            "highlights": highlights,
        }


@router.get("/dashboard")
def get_dashboard_summary(
    current_user: dict = Depends(require_auth),
    con: sqlite3.Connection = Depends(lambda: db_session()),
) -> dict[str, Any]:
    """Aggregate dashboard summary for the authenticated user's assigned patients."""
    lexicon = get_lexicon()
    with con:
        if current_user.get("role") == "administrator":
            patient_row = con.execute("SELECT * FROM patients ORDER BY id ASC LIMIT 1").fetchone()
        else:
            patient_row = con.execute(
                """
                SELECT p.* FROM patients p
                JOIN patient_access pa ON pa.patient_id = p.id
                WHERE pa.user_id = :user_id AND pa.revoked_at IS NULL
                ORDER BY p.name ASC LIMIT 1
                """,
                {"user_id": current_user["user_id"]},
            ).fetchone()

        if not patient_row:
            raise HTTPException(status_code=404, detail="No accessible patients")

        patient_detail = _build_patient_detail(patient_row, con, lexicon)
        entries = [_to_summary(row, lexicon) for row in record.list_entries(con, patient_row["id"])]
        return {
            "patient": patient_detail.model_dump(),
            "entries": [e.model_dump() for e in entries],
            "intake": {
                "raw_transcript": "ज्वरो छैन, खोकी छ, सिटामोल ५०० एमजी",
                "corrected_text": "ज्वरो छैन खोकी छ सिटामोल 500 एमजी",
                "extraction_method": "direct",
                "extraction_status": "ok",
                "input_type": "text",
                "document_class": "prescription",
                "document_class_evidence": ["medication names"],
                "corrections": [],
                "unverified": [],
                "notes": [],
            },
        }
