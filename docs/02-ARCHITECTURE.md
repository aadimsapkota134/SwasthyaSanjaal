# 02 — System Architecture & Clinical Pipelines

## 1. Core Architectural Principle

> **Language models read and propose candidates; deterministic clinical code decides.**

Every concept match, provenance label (`LEXICON`, `FUZZY_MATCH`, `LLM`), negation scope flag, brand-to-generic drug link, and HL7 FHIR R4 resource in **SwasthyaSanjaal** traces to a deterministic rule or a closed-vocabulary constraint. Unconfirmed extractions never enter the longitudinal health record without passing the **Human Confirmation Gate**.

---

## 2. End-to-End Pipeline Architecture

```
MULTIMODAL INPUTS          EXTRACTION & ROUTING           LANGUAGE LAYER (NCL)            HUMAN GATE & INTEROP
─────────────────          ────────────────────           ────────────────────            ────────────────────
Digital PDF       ───►     PyMuPDF (fitz) fast-path  ─┐
Scanned PDF / Img ───►     Gemma 4 VLM OCR + [?]     ─┼─► Lexicon-Constrained
FCHV / Patient    ───►     Nepali Speech Pipeline    ─┤   Spell Correction
ASR Transcript             + Acoustic Confidence     ─┤          │
Direct Text       ───►     Unicode NFC + Devanagari  ─┘          ▼
                           Digit Folding                  3-TIER NORMALIZATION
                                                          • Tier 1: Exact (1.00)
                                                          • Tier 2: Folded/Fuzzy (≥0.85)
                                                          • Tier 3: Constrained LLM (0.70)
                                                                 │
                                                                 ▼
                                                          CLINICAL ENRICHMENT
                                                          • Directional Negation Scope
                                                          • Duration / Frequency / Severity
                                                          • Brand → Generic Resolution
                                                          • Field-Level Uncertainty
                                                                 │
                                                                 ▼
                                                       HUMAN CONFIRMATION GATE
                                                    (POST /api/v1/patients/{id}/entries)
                                                                 │
                                           ┌─────────────────────┼─────────────────────┐
                                           ▼                     ▼                     ▼
                                     SQLite Ledger        HL7 FHIR R4 Bundle     Emergency QR &
                                   (Hydrated on Read)   (Negated Excluded Out)   A4 Summary PDF
```

---

## 3. Layer-by-Layer Design

### 3.1 Layer 1: Nepali Clinical Lexicon (`data/nepali_clinical_lexicon.json`)
- **300 curated concepts** (`NCL-0001` to `NCL-0300`) spanning 9 clinical types:
  - `symptom` (72), `condition` (64), `drug_generic` (43), `drug_brand` (44), `investigation` (38), `procedure` (12), `duration` (10), `severity` (9), and `negation` (8).
- Dual WHO coding (`icd11_code` and `icd10_code`) with a standalone crosswalk (`data/icd_crosswalk.csv`).
- Loaded into an in-memory multi-index (`backend/nlp/lexicon.py`) with exact, orthography-folded, and token-level inverted indexes.

### 3.2 Layer 2: Devanagari Normalization & Spell Correction (`backend/nlp/`)
- **`devanagari.py`**: Strips zero-width joiners (`\u200b`–`\u200d`, `\ufeff`), converts Devanagari digits (`०`–`९`) to ASCII (`0`–`9`), normalizes danda punctuation (`।`, `॥`), and folds common Nepali orthographic variants (`ँ` $\rightarrow$ `ं`, `ई` $\rightarrow$ `इ`, `ऊ` $\rightarrow$ `उ`, `ब` $\rightarrow$ `व`, `ष`/`श` $\rightarrow$ `स`).
- **`correct.py`**: Repairs single-token OCR corruptions only when a single lexicon surface form lies within the Levenshtein edit budget ($\le 1$ for 4–6 chars, $\le 2$ for $\ge 7$ chars). Ambiguous ties are left untouched and surfaced in `unverified`.

### 3.3 Layer 3: Three-Tier Clinical Normalizer (`backend/nlp/normalize.py`)
1. **Tier 1 (`LEXICON`, confidence = `1.00`)**: Exact n-gram lookup (up to 6 tokens) against Devanagari, Romanized, Latin, and code-mixed lexicon aliases.
2. **Tier 2 (`FUZZY_MATCH`, confidence = `0.85`–`0.95`)**:
   - Stage 2a: Exact match after Devanagari orthographic folding (`confidence = 0.95`).
   - Stage 2b: RapidFuzz similarity $\ge 0.85$ coupled with a strict Levenshtein edit distance check so short clinical words never cross-match.
3. **Tier 3 (`LLM`, confidence = `0.70`)**: Residual unmatched spans (1–3 tokens) retrieve top-12 lexicon candidates via `fuzz.WRatio` and prompt Gemma 4 (`tier3_disambiguate.txt`) to return either an `EXISTING_CONCEPT_ID` from the shortlist or `UNKNOWN`. Out-of-shortlist IDs are rejected by code (`backend/nlp/tier3.py`).
4. **Weighted Interval Scheduling**: Overlapping candidate spans are resolved globally via dynamic programming maximizing `(end_token - start_token) * TIER_WEIGHT[tier] * confidence`.
5. **Directional Negation Scope**: Negation concepts (`छैन`, `नभएको`, `होइन`, `chaina`, `chhaina`, `no`, `without`, `denies`) apply within a 3-token window respecting `negation_scope` (`backward` for Nepali post-positions, `forward` for English pre-positions) and clause boundaries (`तर`, `र`, `अनि`, `,`).

### 3.4 Layer 4: Field-Level Uncertainty & Nepali Confirmation Prompts
Every extracted assertion and clinical field carries:
- `resolution_method`: `"LEXICON" | "FUZZY_MATCH" | "LLM"`
- `confirmation_required`: `True` whenever `confidence < 0.85`, `tier == 3`, `asr_confidence < 0.85`, or unreadable `[?]` markers exist.
- `confirmation_prompt_np`: Automatically synthesized Nepali verification question (e.g., `"के तपाईंले ३ दिनदेखि ज्वरो र खोकी भन्न खोज्नुभएको हो?"`) for FCHV or patient confirmation.

### 3.5 Layer 5: Human Confirmation Gate & Interoperability (`backend/record/`)
- **Read-Only Intake**: `/api/v1/intake/text`, `/api/v1/intake/ocr`, `/api/v1/intake/speech`, `/api/v1/intake/voice`, and `/api/v1/intake/normalize` are strictly stateless with respect to the patient database.
- **Confirmation Write Gate**: `POST /api/v1/patients/{patient_id}/entries` is the sole endpoint that writes to `record_entries`. Stored records persist slim concept IDs and span metadata (`encode_normalization`) and hydrate against the live lexicon on read (`hydrate`).
- **HL7 FHIR R4 Bundle (`backend/record/fhir.py`)**: Builds structurally validated R4 `Bundle` (`Patient`, `AllergyIntolerance`, `Condition`, `Observation`, `MedicationRequest`) validated at runtime via `fhir.resources`. Negated findings (`negated=True`) are strictly excluded from `Condition` resources and counted in `negated_excluded`.
