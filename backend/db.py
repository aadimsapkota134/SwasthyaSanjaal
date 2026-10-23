from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
  id                  TEXT PRIMARY KEY,
  name                TEXT NOT NULL,
  name_np             TEXT,
  dob                 DATE,
  gender              TEXT,
  gender_np           TEXT,
  district            TEXT,
  blood_group         TEXT,
  sanjaal_id          TEXT UNIQUE,
  sanchai_id          TEXT UNIQUE,
  arogya_id           TEXT UNIQUE,
  qr_token            TEXT UNIQUE,
  chronic_conditions  TEXT,
  lang_pref           TEXT DEFAULT 'ne'
);

CREATE TABLE IF NOT EXISTS allergies (
  id            TEXT PRIMARY KEY,
  patient_id    TEXT REFERENCES patients(id),
  substance_en  TEXT NOT NULL,
  substance_np  TEXT,
  severity      TEXT
);

CREATE TABLE IF NOT EXISTS record_entries (
  id                TEXT PRIMARY KEY,
  patient_id        TEXT REFERENCES patients(id),
  input_type        TEXT NOT NULL,
  document_class    TEXT,
  facility_name     TEXT,
  record_date       DATE NOT NULL,
  record_date_bs    TEXT,
  asset_path        TEXT,
  raw_transcript    TEXT,
  corrected_text    TEXT,
  extraction_method TEXT,
  normalized_json   TEXT NOT NULL,
  meaning_np        TEXT,
  icd11_code        TEXT,
  icd10_code        TEXT,
  icd_link_status   TEXT,
  fhir_json         TEXT,
  notes_json        TEXT,
  created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entries_patient_date
  ON record_entries(patient_id, record_date DESC);

CREATE TABLE IF NOT EXISTS lexicon_entries (
  concept_id          TEXT PRIMARY KEY,
  canonical_en        TEXT NOT NULL,
  canonical_np        TEXT NOT NULL,
  preferred_register  TEXT,
  devanagari_aliases  TEXT NOT NULL,
  romanized_aliases   TEXT,
  latin_aliases       TEXT,
  code_mixed_patterns TEXT,
  concept_type        TEXT,
  generic_of          TEXT REFERENCES lexicon_entries(concept_id),
  icd11_code          TEXT,
  icd10_code          TEXT,
  negation_sensitive  INTEGER DEFAULT 0,
  duration_days       INTEGER,
  frequency_per_day   INTEGER,
  negation_scope      TEXT,
  source              TEXT,
  license             TEXT
);

CREATE INDEX IF NOT EXISTS idx_lexicon_type ON lexicon_entries(concept_type);

CREATE TABLE IF NOT EXISTS eval_results (
  run_id     TEXT,
  item_id    TEXT,
  category   TEXT,
  tier_fired INTEGER,
  correct    INTEGER,
  predicted  TEXT,
  gold       TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id                TEXT PRIMARY KEY,
  email             TEXT UNIQUE NOT NULL,
  password_hash     TEXT NOT NULL,
  full_name         TEXT,
  role              TEXT NOT NULL DEFAULT 'clinician',
  is_active         INTEGER NOT NULL DEFAULT 1,
  created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
  id                TEXT PRIMARY KEY,
  user_id           TEXT NOT NULL REFERENCES users(id),
  token_hash        TEXT UNIQUE NOT NULL,
  expires_at        TIMESTAMP NOT NULL,
  created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ip_address        TEXT,
  user_agent        TEXT
);

CREATE TABLE IF NOT EXISTS patient_access (
  id                TEXT PRIMARY KEY,
  user_id           TEXT NOT NULL REFERENCES users(id),
  patient_id        TEXT NOT NULL REFERENCES patients(id),
  granted_by        TEXT REFERENCES users(id),
  granted_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  revoked_at        TIMESTAMP,
  UNIQUE(user_id, patient_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id                TEXT PRIMARY KEY,
  actor_id          TEXT REFERENCES users(id),
  actor_email       TEXT,
  action            TEXT NOT NULL,
  resource          TEXT,
  resource_id       TEXT,
  patient_id        TEXT,
  outcome           TEXT NOT NULL,
  detail            TEXT,
  ip_address        TEXT,
  user_agent        TEXT,
  created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_patient_access_user_id ON patient_access(user_id);
CREATE INDEX IF NOT EXISTS idx_patient_access_patient_id ON patient_access(patient_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor_id ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_patient_id ON audit_log(patient_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
"""

TABLES = (
    "patients",
    "allergies",
    "record_entries",
    "lexicon_entries",
    "eval_results",
    "users",
    "sessions",
    "patient_access",
    "audit_log",
)


def connect(db_path: str | None = None) -> sqlite3.Connection:
    target = db_path or settings.db_path
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(target)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def session(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    con = connect(db_path)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("patients", "gender_np", "TEXT"),
    ("patients", "district", "TEXT"),
    ("patients", "sanjaal_id", "TEXT"),
    ("patients", "sanchai_id", "TEXT"),
    ("patients", "chronic_conditions", "TEXT"),
    ("record_entries", "record_date_bs", "TEXT"),
)


def apply_additive_migrations(con: sqlite3.Connection) -> list[str]:
    applied: list[str] = []
    for table, column, declaration in ADDED_COLUMNS:
        present = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
        if not present:
            continue
        if column not in present:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
            applied.append(f"{table}.{column}")
    return applied


def _migrate_individual_patients(con: sqlite3.Connection) -> None:
    """Ensure any individual account has a dedicated patient profile linked by name."""
    import secrets

    individuals = con.execute("SELECT * FROM users WHERE role = 'individual'").fetchall()
    for u in individuals:
        own = con.execute(
            """
            SELECT pa.id FROM patient_access pa
            WHERE pa.user_id = :user_id AND pa.granted_by = :user_id AND pa.revoked_at IS NULL
            """,
            {"user_id": u["id"]},
        ).fetchone()
        if not own:
            pat_id = f"pat_{secrets.token_urlsafe(12)}"
            name = u["full_name"] or u["email"].split("@")[0].capitalize()
            sanjaal_id = f"SANJAAL-{secrets.token_hex(4).upper()}"
            sanchai_id = f"SANCHAI-{secrets.token_hex(4).upper()}"
            qr_token = secrets.token_urlsafe(16)
            con.execute(
                """
                INSERT INTO patients (id, name, sanjaal_id, sanchai_id, qr_token, lang_pref)
                VALUES (:id, :name, :sanjaal_id, :sanchai_id, :qr_token, 'ne')
                """,
                {
                    "id": pat_id,
                    "name": name,
                    "sanjaal_id": sanjaal_id,
                    "sanchai_id": sanchai_id,
                    "qr_token": qr_token,
                },
            )
            # Remove old blanket demo grants for this individual
            con.execute("DELETE FROM patient_access WHERE user_id = :user_id", {"user_id": u["id"]})
            # Link to their newly created patient profile
            access_id = secrets.token_urlsafe(16)
            con.execute(
                """
                INSERT INTO patient_access (id, user_id, patient_id, granted_by, granted_at)
                VALUES (:id, :user_id, :patient_id, :user_id, datetime('now'))
                """,
                {
                    "id": access_id,
                    "user_id": u["id"],
                    "patient_id": pat_id,
                },
            )


def init_db(db_path: str | None = None) -> list[str]:
    with session(db_path) as con:
        con.executescript(SCHEMA)
        migrated = apply_additive_migrations(con)
        _migrate_individual_patients(con)
        return migrated



@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI-compatible dependency that yields a database connection."""
    with session() as con:
        yield con
