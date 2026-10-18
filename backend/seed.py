from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.config import settings

SEED_PATIENTS_PATH = "./data/seed_patients.json"
SEED_ENTRIES_PATH = "./data/seed_entries.json"


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def qr_token_for(identifier: str) -> str:
    """Derive a stable share token from patient identifier.

    Deterministic so demo clients produce matching tokens across devices.
    """
    return hashlib.sha256(f"swasthyasanjaal:{identifier}".encode()).hexdigest()[:16]


def sync_lexicon(con: sqlite3.Connection, concepts: list[dict[str, Any]] | None = None) -> int:
    """Mirror the clinical lexicon into `lexicon_entries`. Idempotent."""
    if concepts is None:
        concepts = _load(settings.lexicon_path)

    # Brand drugs reference their generic via generic_of; generics must land first.
    ordered = sorted(concepts, key=lambda c: c.get("generic_of") is not None)

    con.executemany(
        """
        INSERT OR REPLACE INTO lexicon_entries (
          concept_id, canonical_en, canonical_np, preferred_register,
          devanagari_aliases, romanized_aliases, latin_aliases, code_mixed_patterns,
          concept_type, generic_of, icd11_code, icd10_code, negation_sensitive,
          duration_days, frequency_per_day, negation_scope, source, license
        ) VALUES (
          :concept_id, :canonical_en, :canonical_np, :preferred_register,
          :devanagari_aliases, :romanized_aliases, :latin_aliases, :code_mixed_patterns,
          :concept_type, :generic_of, :icd11_code, :icd10_code, :negation_sensitive,
          :duration_days, :frequency_per_day, :negation_scope, :source, :license
        )
        """,
        [
            {
                **concept,
                "devanagari_aliases": json.dumps(concept.get("devanagari_aliases", []), ensure_ascii=False),
                "romanized_aliases": json.dumps(concept.get("romanized_aliases", []), ensure_ascii=False),
                "latin_aliases": json.dumps(concept.get("latin_aliases", []), ensure_ascii=False),
                "code_mixed_patterns": json.dumps(concept.get("code_mixed_patterns", []), ensure_ascii=False),
                "negation_sensitive": int(bool(concept.get("negation_sensitive"))),
            }
            for concept in ordered
        ],
    )
    return len(ordered)


def seed_demo_records(con: sqlite3.Connection) -> dict[str, int]:
    """Insert synthetic demo patients, allergies, and entries."""
    patients = _load(SEED_PATIENTS_PATH)
    entries = _load(SEED_ENTRIES_PATH)

    con.executemany(
        """
        INSERT OR REPLACE INTO patients (
          id, name, name_np, dob, gender, gender_np, district, blood_group,
          sanjaal_id, sanchai_id, arogya_id, qr_token, chronic_conditions, lang_pref
        ) VALUES (
          :id, :name, :name_np, :dob, :gender, :gender_np, :district, :blood_group,
          :sanjaal_id, :sanchai_id, :arogya_id, :qr_token, :chronic_conditions, 'ne'
        )
        """,
        [
            {
                "id": p["id"],
                "name": p["name"],
                "name_np": p.get("name_np"),
                "dob": p.get("dob"),
                "gender": p.get("gender"),
                "gender_np": p.get("gender_np"),
                "district": p.get("district"),
                "blood_group": p.get("blood_group"),
                "sanjaal_id": (
                    sanjaal_id := p.get("sanjaal_id")
                    or (p.get("sanchai_id", "").replace("SANCHAI-", "SANJAAL-") if p.get("sanchai_id") else f"SANJAAL-{p['id']}")
                ),
                "sanchai_id": (
                    sid := p.get("sanchai_id")
                    or (p.get("arogya_id", "").replace("AK-", "SANCHAI-") if p.get("arogya_id") else f"SANCHAI-{p['id']}")
                ),
                "arogya_id": p.get("arogya_id"),
                "qr_token": qr_token_for(sid),
                "chronic_conditions": json.dumps(p.get("chronic_conditions", []), ensure_ascii=False),
            }
            for p in patients
        ],
    )

    allergies = [
        {
            "id": f"alg_{p['id']}_{index}",
            "patient_id": p["id"],
            "substance_en": allergy["substance_en"],
            "substance_np": allergy.get("substance_np"),
            "severity": allergy.get("severity"),
        }
        for p in patients
        for index, allergy in enumerate(p.get("allergies", []), start=1)
    ]
    con.executemany(
        """
        INSERT OR REPLACE INTO allergies (id, patient_id, substance_en, substance_np, severity)
        VALUES (:id, :patient_id, :substance_en, :substance_np, :severity)
        """,
        allergies,
    )

    con.executemany(
        """
        INSERT OR REPLACE INTO record_entries (
          id, patient_id, input_type, document_class, facility_name, record_date,
          record_date_bs, asset_path, raw_transcript, corrected_text, extraction_method,
          normalized_json, meaning_np, icd11_code, icd10_code, icd_link_status
        ) VALUES (
          :id, :patient_id, :input_type, :document_class, :facility_name, :record_date,
          :record_date_bs, :asset_path, :raw_transcript, :corrected_text, :extraction_method,
          :normalized_json, :meaning_np, :icd11_code, :icd10_code, :icd_link_status
        )
        """,
        [
            {
                "id": e["id"],
                "patient_id": e["patient_id"],
                "input_type": e["input_type"],
                "document_class": e.get("document_class"),
                "facility_name": e.get("facility_name"),
                "record_date": e["record_date"],
                "record_date_bs": e.get("record_date_bs"),
                "asset_path": e.get("asset_path"),
                "raw_transcript": e.get("raw_transcript"),
                "corrected_text": None,
                "extraction_method": "seed",
                "normalized_json": json.dumps(
                    {
                        "concept_ids": e.get("concepts", []),
                        "negated_concept_ids": e.get("negated_concepts", []),
                    },
                    ensure_ascii=False,
                ),
                "meaning_np": e.get("meaning_np"),
                "icd11_code": e.get("icd11_code"),
                "icd10_code": e.get("icd10_code"),
                "icd_link_status": e.get("icd_link_status"),
            }
            for e in entries
        ],
    )

    return {"patients": len(patients), "allergies": len(allergies), "entries": len(entries)}


def seed_all(con: sqlite3.Connection) -> dict[str, int]:
    """Re-sync the whole generated package. Safe and idempotent on startup."""
    return {
        "lexicon": sync_lexicon(con),
        **seed_demo_records(con),
    }


if __name__ == "__main__":
    from backend.db import init_db, session

    init_db()
    with session() as connection:
        print(json.dumps(seed_all(connection), indent=2))
