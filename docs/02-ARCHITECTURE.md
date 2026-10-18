# 02 — System Architecture & Clinical Pipelines

> **Companion to [`docs/00-MASTER-DOCUMENTATION.md`](00-MASTER-DOCUMENTATION.md) (§7–§19).**

## 1. Eight Architectural Principles (§8)

These are the rules the codebase enforces:

1. **Precision over recall (§8.1)**: A clinical language layer must be short on recall rather than wrong. Producing a hallucinated diagnosis is clinically dangerous; missing a term is an omission handled by the confirmation loop. **Precision targets `1.000`.**
2. **Approval before write (§8.2)**: Ingesting an image, PDF, text, or voice transcript **never** mutates the database automatically. Only explicit human confirmation (`POST /api/v1/patients/{id}/entries`) commits to the longitudinal record.
3. **Deterministic core, constrained models (§8.3)**: Use the lexicon and deterministic code for what is known. Use open-source models strictly for **perception** (OCR, ASR) and **constrained matching** (pick from a shortlist or return `UNKNOWN`). Never use a model for open-ended clinical generation.
4. **Negation safety (§8.4)**: Negated findings (`"ज्वरो छैन"`, `"chest pain denied"`) carry `negated: true` and are **strictly excluded** from active conditions and downstream FHIR `Condition` exports.
5. **`UNKNOWN` is valid (§8.5)**: When the pipeline cannot resolve a term safely, Tier 3 returns `UNKNOWN` rather than forcing a prediction. `UNKNOWN` triggers human confirmation.
6. **Source preservation (§8.6)**: `raw_transcript` and normalized concepts are stored separately. The raw input is never overwritten.
7. **No fabricated authority (§8.7)**: `source` states how a lexicon concept was authored; `verify_against` names the clinical authority; `review_status` (`"unreviewed"`) makes clinician sign-off countable without claiming review that has not occurred.
8. **No date fabrication (§8.8)**: All internal dates (`record_date`) are ISO-8601 Gregorian (`YYYY-MM-DD`). Bikram Sambat (`record_date_bs`) is stored as an authored display string with zero programmatic AD↔BS conversion.

---

## 2. End-to-End Pipeline Architecture

```text
INPUT                ROUTING                NORMALIZATION              EXTRACTION              OUTPUT
─────                ───────                ─────────────              ──────────              ──────
text          ──┐
photo         ──┼──► is_image? ──► OCR ──┐
pdf           ──┘    is_pdf?   ──► fitz ─┤
speech (ASR)  ──────► transcript ────────┘
                                            ▼
                              ┌────────────────────────────┐
                              │  3-TIER NORMALIZATION      │
                              │  T1 exact · T2 fuzzy       │
                              │  T3 model-constrained      │
                              │  + negation + brand→generic│
                              └────────────┬───────────────┘
                                           ▼
                              ┌────────────────────────────┐
                              │  FIELD EXTRACTION          │
                              │  schema-constrained        │
                              │  per-field confidence      │
                              └────────────┬───────────────┘
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                    confidence        confidence       confidence
                    > threshold       < threshold      < threshold
                          │                │                │
                          ▼                ▼                ▼
                    structured        confirmation      confirmation
                    fields (pass)     (T3 match)        (extraction)
                                           │                │
                                           └────────┬───────┘
                                                    ▼
                                          human confirms
                                                    │
                                                    ▼
                                          confirmed fields
                                                    │
                                    ┌───────────────┼───────────────┐
                                    ▼               ▼               ▼
                              patient record   FCHV protocol   plain-Nepali
                              (JSON / FHIR)    inputs          explanation
```

---

## 3. Provenance Codes (Appendix D)

Every normalized concept and extracted field records how it was obtained:

| Code | Meaning |
|---|---|
| `LEXICON` | Exact match against the Nepali Clinical Lexicon (Tier 1, confidence `1.00`) |
| `FUZZY_MATCH` | Devanagari orthographic folding (`0.95`) or Levenshtein fuzzy match above threshold (`0.85`) |
| `LLM` | Model-constrained selection from candidate shortlist (Tier 3, confidence `0.70`) |
| `OCR` / `VLM` | Transcribed by the vision-language model (`gemma4_vlm`) |
| `ASR` | Transcribed from speech (`asr_transcript`) |
| `HUMAN_CONFIRMED` | Confirmed or corrected by a human at the write gate |
| `UNKNOWN` | Unresolved; triggers human confirmation |

---

## 4. Layer-by-Layer Implementation

### 4.1 Nepali Clinical Lexicon (`data/nepali_clinical_lexicon.json`, `backend/nlp/lexicon.py`)
- **300 concepts** (`NCL-0001` to `NCL-0300`) across 9 clinical categories (`drug_brand`, `symptom`, `condition`, `investigation`, `drug_generic`, `body_site`, `duration`, `severity`, `negation`).
- Indexed in memory across exact, orthography-folded, and token-inverted tables.

### 4.2 Devanagari Folding & Lexicon-Constrained Correction (`backend/nlp/devanagari.py`, `backend/nlp/correct.py`)
- Normalizes Unicode NFC, strips zero-width joiners (`\u200b`–`\u200d`), converts Devanagari numerals (`५८९` $\rightarrow$ `589`), and folds common Nepali orthographic variations.
- `correct.py` repairs single-token OCR corruptions only when a unique lexicon entry falls within the Levenshtein edit budget ($\le 1$ for length 4–6, $\le 2$ for length $\ge 7$).

### 4.3 Multi-Stage Concept Matching & Extraction (`backend/nlp/normalize.py`, `backend/nlp/tier3.py`)
- Resolves overlapping candidate spans via weighted interval scheduling dynamic programming.
- Extracts 7 clinical field categories (`symptom`, `duration`, `severity`, `body_site`, `negation`, `medication`, `lab_test`).
- Computes per-field uncertainty (`FieldUncertainty`) and synthesizes Nepali confirmation prompts (`confirmation_prompt_np`) whenever confidence is below threshold (`0.85`).
