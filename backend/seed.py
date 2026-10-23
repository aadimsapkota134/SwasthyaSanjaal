from __future__ import annotations

import getpass
import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.auth.password import hash_password
from backend.config import settings
from backend.db import session as db_session

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


def bootstrap_admin(con: sqlite3.Connection, email: str, password: str, full_name: str | None = None) -> dict[str, Any]:
    """Bootstrap the first administrator account.

    Refuses to overwrite an existing administrator. Prompts for credentials
    securely (no echo). Never logs or prints the password.
    """
    # Check if any administrator already exists
    existing_admin = con.execute(
        "SELECT id FROM users WHERE role = 'administrator' LIMIT 1"
    ).fetchone()
    if existing_admin is not None:
        raise ValueError("An administrator account already exists")

    # Check if any user with this email already exists
    existing = con.execute(
        "SELECT id FROM users WHERE email = :email", {"email": email}
    ).fetchone()
    if existing is not None:
        raise ValueError("An account with this email already exists")

    # Validate password strength
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    user_id = secrets.token_urlsafe(16)
    password_hash_val = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    con.execute(
        """
        INSERT INTO users (id, email, password_hash, full_name, role, is_active, created_at, updated_at)
        VALUES (:id, :email, :password_hash, :full_name, 'administrator', 1, :created_at, :updated_at)
        """,
        {
            "id": user_id,
            "email": email,
            "password_hash": password_hash_val,
            "full_name": full_name,
            "created_at": now,
            "updated_at": now,
        },
    )
    con.commit()

    return {
        "user_id": user_id,
        "email": email,
        "full_name": full_name,
        "role": "administrator",
        "created_at": now,
    }


if __name__ == "__main__":
    import sys
    from datetime import datetime, timezone

    from backend.db import init_db

    if len(sys.argv) > 1 and sys.argv[1] == "bootstrap-admin":
        init_db()
        email = input("Admin email: ").strip()
        if not email:
            print("Email is required", file=sys.stderr)
            sys.exit(1)
        password = getpass.getpass("Admin password: ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Passwords do not match", file=sys.stderr)
            sys.exit(1)
        full_name = input("Full name (optional): ").strip() or None

        try:
            with db_session() as connection:
                result = bootstrap_admin(connection, email, password, full_name)
            print(f"Administrator created: {result['email']} ({result['user_id']})")
        except ValueError as exc:
            print(f"Bootstrap failed: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        init_db()
        with db_session() as connection:
            print(json.dumps(seed_all(connection), indent=2))
