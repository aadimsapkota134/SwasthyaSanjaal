from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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
"""

TABLES = (
    "patients",
    "allergies",
    "record_entries",
    "lexicon_entries",
    "eval_results",
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


def init_db(db_path: str | None = None) -> list[str]:
    with session(db_path) as con:
        con.executescript(SCHEMA)
        return apply_additive_migrations(con)
