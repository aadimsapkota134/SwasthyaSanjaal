# 06 — Codebase Architecture & Module Reference

> **Companion to [`docs/00-MASTER-DOCUMENTATION.md`](00-MASTER-DOCUMENTATION.md) and [`docs/02-ARCHITECTURE.md`](02-ARCHITECTURE.md).**

---

## 1. Repository Layout

```text
SwasthyaSanjaal/
├── README.md                              # Project overview & quickstart
├── CONTRIBUTING.md                        # Frogtoberfest contributor guide & PR rules
├── CITATION.cff                           # Academic citation metadata
├── LICENSE                                # Dual license: MIT (code) + CC-BY-4.0 (data/lexicon)
├── pyproject.toml                         # Python package & pytest configuration
├── .env.example                           # Environment template (model backend & DB paths)
│
├── data/
│   ├── nepali_clinical_lexicon.json       # 300 curated Nepali clinical concepts (CC-BY-4.0)
│   ├── nepali_clinical_lexicon.csv        # Tabular CSV export of the lexicon
│   ├── icd_crosswalk.csv                  # WHO ICD-11 MMS & ICD-10 crosswalk
│   ├── nepclinbench.json                  # 60-item gold evaluation benchmark
│   ├── DATASHEET.md                       # 8-section Datasheet for Datasets
│   ├── seed_patients.json                 # Synthetic patient profiles (zero PII)
│   ├── seed_entries.json                  # Synthetic clinical encounters
│   └── demo_assets/                       # Sample digital PDF lab report, Rx, and bill
│
├── scripts/
│   └── expand_lexicon.py                  # Deterministic lexicon builder & CSV exporter
│
├── backend/
│   ├── __init__.py
│   ├── config.py                          # Pydantic Settings (cloud vs. local Gemma resolution)
│   ├── schemas.py                         # Pydantic v2 contracts (Provenance, FieldUncertainty, FHIR)
│   ├── db.py                              # SQLite schema & additive migrations
│   ├── seed.py                            # Idempotent lexicon & synthetic patient seeding
│   ├── main.py                            # FastAPI app, body-size gate, CORS, /api/v1/health
│   │
│   ├── nlp/                               # Core Nepali Clinical Language Layer
│   │   ├── devanagari.py                  # NFC, ZWJ/ZWNJ strip, numeral folding, orthography folding
│   │   ├── lexicon.py                     # In-memory exact, folded, and token-inverted indexes
│   │   ├── correct.py                     # Lexicon-constrained Levenshtein OCR spell corrector
│   │   ├── tier3.py                       # Shortlist-constrained Gemma Tier-3 matcher (ID or UNKNOWN)
│   │   └── normalize.py                   # 3-tier matcher, interval DP, negation, duration, severity, uncertainty
│   │
│   ├── ai/                                # Constrained Perception & Model Client
│   │   ├── engine.py                      # Dual-tier Gemma 4 client + AUDIO_INPUT_SUPPORTED = False gate
│   │   └── prompts.py                     # Prompt loader
│   │
│   ├── prompts/                           # Versioned prompt templates (.txt)
│   │   ├── ocr_extract.txt
│   │   ├── asr_transcribe.txt
│   │   ├── tier3_disambiguate.txt
│   │   ├── baseline_extract.txt
│   │   ├── meaning_np.txt
│   │   └── summary_doctor.txt
│   │
│   ├── intake/                            # Multimodal Written & Spoken Intake Pipeline
│   │   ├── documents.py                   # PyMuPDF digital PDF extractor & text-derived classifier
│   │   ├── storage.py                     # Content-addressed SHA-256 upload storage
│   │   └── pipeline.py                    # run_intake (text/PDF/image/voice) & run_speech_intake (ASR)
│   │
│   ├── record/                            # Confirmed Clinical Record & Interoperability
│   │   ├── entries.py                     # Slim JSON storage, live lexicon hydration, active_conditions
│   │   ├── fhir.py                        # HL7 FHIR R4 Bundle builder + fhir.resources validation
│   │   ├── qr.py                          # Segno emergency QR generator (opaque token, no leaked PII)
│   │   └── pdf.py                         # ReportLab A4 clinical summary PDF generator
│   │
│   ├── eval/                              # NepClinBench Evaluation & Ablation Suite
│   │   ├── bench.py                       # 60-item benchmark runner, category & tier precision scorer
│   │   ├── baseline.py                    # Unconstrained raw Gemma 4 baseline extractor
│   │   └── __main__.py                    # CLI (`python -m backend.eval [--compare] [--persist]`)
│   │
│   └── routers/                           # FastAPI HTTP & SSE Routers
│       ├── intake.py                      # /intake/text, /ocr, /speech, /voice, /stream, /normalize, /lexicon
│       ├── patients.py                    # /patients, human confirmation gate, /fhir, /qr, /summary.pdf
│       └── eval.py                        # /eval/run, /eval/latest, /eval/runs
│
├── tests/                                 # 51 automated pytest tests
│   ├── conftest.py                        # Per-test isolated SQLite DB & upload directory fixture
│   ├── test_health.py
│   ├── test_db_seed.py
│   ├── test_intake.py                     # Written, PDF, SSE, speech uncertainty, and fail-closed audio tests
│   ├── test_eval.py                       # Verifies 58/60 exact match, 1.000 precision, 10/10 negation
│   ├── test_fhir.py                       # Verifies R4 Bundle validation & strict negation exclusion
│   ├── test_patients_and_approval.py      # Verifies human confirmation gate & timeline hydration
│   ├── test_qr.py                         # Verifies emergency QR payload privacy & negation exclusion
│   └── test_integration_flow.py           # End-to-end clinical flow test
│
└── docs/                                  # Comprehensive Research & Engineering Documentation
    ├── 00-MASTER-DOCUMENTATION.md
    ├── 01-RESEARCH-DOSSIER.md
    ├── 02-ARCHITECTURE.md
    ├── 03-EVALUATION-NEPCLINBENCH.md
    ├── 04-DATA-AND-LEXICON-SPEC.md
    ├── 05-AI-AND-PROMPTS.md
    ├── 06-CODEBASE-REFERENCE.md
    └── 07-BUILD-AND-ABLATION-RECORD.md
```

---

## 2. Critical Algorithmic Safeguards

### 2.1 The Dosage-Unit Levenshtein Edit Budget (`backend/nlp/normalize.py`)
On real Nepali prescriptions, `एजी` (the commercial antibiotic brand *Azee* / Azithromycin) sits one inserted character away from `एमजी` (*mg* / milligrams), yielding a normalized `fuzz.ratio` of `0.857` (above the `0.85` threshold). Relying on a normalized ratio alone caused early prototypes to falsely hallucinate an antibiotic on every milligram dosage string (`५०० एमजी`).

`backend/nlp/normalize.py` enforces two hard guards in `_tier2_matches`:
1. `MIN_FUZZY_SHORTER = 5`: Both the input span and the candidate lexicon key must be at least 5 characters long before general fuzzy matching is attempted.
2. `FUZZY_EDIT_BUDGET = ((8, 1), (10**6, 2))`: Spans of length 5–8 are permitted at most **1** Levenshtein edit (`Levenshtein.distance(span, key) <= 1`); longer spans are permitted at most **2** edits.

### 2.2 Weighted Interval Scheduling for Span Overlap Resolution (`_resolve_overlaps`)
When multiple n-gram spans overlap (e.g., `"प्यारासिटामोल"` inside `"प्यारासिटामोल ५००"` or `"ज्वरो"` inside `"टाइफाइड ज्वरो"`), `_resolve_overlaps` solves the weighted interval scheduling problem via bottom-up dynamic programming:
- Weight of a candidate match: `(end_token - start_token) * TIER_WEIGHT[tier] * confidence`
- Longer, higher-tier clinical phrases deterministically win over fragmented sub-spans.

### 2.3 Slim Storage & Live Lexicon Hydration (`backend/record/entries.py`)
When a confirmed entry is written to `record_entries`, `encode_normalization()` stores only the `concept_id`, `surface_form`, `tier`, `confidence`, `negated` flag, and character offsets. When the record is read back (`hydrate()`), each `concept_id` is resolved against the live in-memory `Lexicon`. Consequently, updating a Nepali display label or ICD code in `nepali_clinical_lexicon.json` automatically reflects across all historical patient records without requiring database data migrations.
