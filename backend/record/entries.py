from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.nlp.lexicon import Concept, Lexicon

SHAPE_SEEDED = "seeded"
SHAPE_NORMALIZED = "normalized"
PROVENANCE_SEED = "seed"


@dataclass(slots=True)
class StoredConcept:
    """A concept hydrated against the active clinical lexicon."""
    concept: Concept
    negated: bool = False
    surface_form: str | None = None
    tier: int | None = None
    confidence: float | None = None
    start: int | None = None
    end: int | None = None
    reasoning: str | None = None


@dataclass(slots=True)
class StoredNormalization:
    shape: str
    concepts: list[StoredConcept] = field(default_factory=list)
    modifiers: list[StoredConcept] = field(default_factory=list)
    duration_days: int | None = None
    frequency_per_day: int | None = None
    unmatched: list[str] = field(default_factory=list)
    prepared_text: str | None = None
    dangling: list[str] = field(default_factory=list)

    @property
    def all_concepts(self) -> list[StoredConcept]:
        return [*self.concepts, *self.modifiers]


def hydrate(normalized_json: str, lexicon: Lexicon) -> StoredNormalization:
    """Reconstruct concepts and metadata from stored JSON against active lexicon."""
    payload: dict[str, Any] = json.loads(normalized_json) if normalized_json else {}
    dangling: list[str] = []

    def resolve(concept_id: str) -> Concept | None:
        concept = lexicon.get(concept_id)
        if concept is None:
            dangling.append(concept_id)
        return concept

    if "concept_ids" in payload:
        negated_ids = set(payload.get("negated_concept_ids") or [])
        stored: list[StoredConcept] = []
        for concept_id in [*payload["concept_ids"], *negated_ids]:
            concept = resolve(concept_id)
            if concept is not None:
                stored.append(StoredConcept(concept=concept, negated=concept_id in negated_ids))
        return StoredNormalization(
            shape=SHAPE_SEEDED,
            concepts=[s for s in stored if s.concept.is_assertion],
            modifiers=[s for s in stored if not s.concept.is_assertion],
            dangling=dangling,
        )

    def build(items: list[dict[str, Any]]) -> list[StoredConcept]:
        out: list[StoredConcept] = []
        for item in items:
            concept = resolve(str(item.get("concept_id", "")))
            if concept is None:
                continue
            out.append(
                StoredConcept(
                    concept=concept,
                    negated=bool(item.get("negated")),
                    surface_form=item.get("surface_form"),
                    tier=item.get("tier"),
                    confidence=item.get("confidence"),
                    start=item.get("start"),
                    end=item.get("end"),
                    reasoning=item.get("reasoning"),
                )
            )
        return out

    return StoredNormalization(
        shape=SHAPE_NORMALIZED,
        concepts=build(payload.get("concepts") or []),
        modifiers=build(payload.get("modifiers") or []),
        duration_days=payload.get("duration_days"),
        frequency_per_day=payload.get("frequency_per_day"),
        unmatched=list(payload.get("unmatched") or []),
        prepared_text=payload.get("prepared_text"),
        dangling=dangling,
    )


def encode_normalization(payload: dict[str, Any]) -> str:
    """Serialize minimal match metadata so lexicon corrections auto-reflect on read."""
    def slim(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "concept_id": item["concept_id"],
                "surface_form": item.get("surface_form"),
                "tier": item.get("tier"),
                "confidence": item.get("confidence"),
                "negated": bool(item.get("negated")),
                "start": item.get("start"),
                "end": item.get("end"),
                "reasoning": item.get("reasoning"),
            }
            for item in items
        ]

    return json.dumps(
        {
            "prepared_text": payload.get("prepared_text"),
            "concepts": slim(payload.get("concepts") or []),
            "modifiers": slim(payload.get("modifiers") or []),
            "duration_days": payload.get("duration_days"),
            "frequency_per_day": payload.get("frequency_per_day"),
            "unmatched": list(payload.get("unmatched") or []),
        },
        ensure_ascii=False,
    )


def new_entry_id() -> str:
    return f"entry_{uuid.uuid4().hex[:12]}"


def summarize(normalization: StoredNormalization, *, limit: int = 4) -> str:
    """Timeline summary line with negated findings explicitly flagged with ✕."""
    parts = [
        f"{item.concept.canonical_np} ✕" if item.negated else item.concept.canonical_np
        for item in normalization.concepts[:limit]
    ]
    remainder = len(normalization.concepts) - len(parts)
    if remainder > 0:
        parts.append(f"+{remainder}")
    return " · ".join(parts)


def insert_entry(con: sqlite3.Connection, row: dict[str, Any]) -> str:
    con.execute(
        """
        INSERT INTO record_entries (
          id, patient_id, input_type, document_class, facility_name, record_date,
          record_date_bs, asset_path, raw_transcript, corrected_text, extraction_method,
          normalized_json, meaning_np, icd11_code, icd10_code, icd_link_status, notes_json
        ) VALUES (
          :id, :patient_id, :input_type, :document_class, :facility_name, :record_date,
          :record_date_bs, :asset_path, :raw_transcript, :corrected_text, :extraction_method,
          :normalized_json, :meaning_np, :icd11_code, :icd10_code, :icd_link_status, :notes_json
        )
        """,
        row,
    )
    return str(row["id"])


def list_entries(
    con: sqlite3.Connection,
    patient_id: str,
    *,
    document_class: str | None = None,
    query: str | None = None,
) -> list[sqlite3.Row]:
    """Retrieve patient timeline chronologically (newest first)."""
    sql = ["SELECT * FROM record_entries WHERE patient_id = :patient_id"]
    params: dict[str, Any] = {"patient_id": patient_id}

    if document_class:
        sql.append("AND document_class = :document_class")
        params["document_class"] = document_class
    if query:
        sql.append(
            "AND (COALESCE(raw_transcript, '') LIKE :needle"
            " OR COALESCE(corrected_text, '') LIKE :needle"
            " OR COALESCE(facility_name, '') LIKE :needle)"
        )
        params["needle"] = f"%{query}%"

    sql.append("ORDER BY record_date DESC, created_at DESC")
    return con.execute(" ".join(sql), params).fetchall()


def get_entry(con: sqlite3.Connection, entry_id: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM record_entries WHERE id = :id", {"id": entry_id}
    ).fetchone()


def get_patient(con: sqlite3.Connection, patient_id: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM patients WHERE id = :id", {"id": patient_id}
    ).fetchone()


def list_patients(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM patients ORDER BY name").fetchall()


def list_allergies(con: sqlite3.Connection, patient_id: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM allergies WHERE patient_id = :id ORDER BY substance_en",
        {"id": patient_id},
    ).fetchall()


def active_conditions(
    con: sqlite3.Connection, patient_id: str, lexicon: Lexicon
) -> list[Concept]:
    """Active conditions for clinical safety strip. Negated findings excluded outright."""
    asserted: dict[str, Concept] = {}
    denied: set[str] = set()

    # Include chronic conditions from patient profile
    patient = get_patient(con, patient_id)
    if patient and patient["chronic_conditions"]:
        try:
            chronic_ids = json.loads(patient["chronic_conditions"])
            for cid in chronic_ids:
                c = lexicon.get(cid)
                if c:
                    asserted.setdefault(c.concept_id, c)
        except Exception:
            pass

    for row in list_entries(con, patient_id):
        for item in hydrate(row["normalized_json"], lexicon).concepts:
            if item.concept.concept_type != "condition":
                continue
            if item.negated:
                denied.add(item.concept.concept_id)
            else:
                asserted.setdefault(item.concept.concept_id, item.concept)

    return [concept for cid, concept in asserted.items() if cid not in denied]
