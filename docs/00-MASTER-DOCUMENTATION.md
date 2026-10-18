# SwasthyaSanjaal · स्वास्थ्य सञ्जाल
## Master Documentation — Nepali Clinical Language Layer

> **Status · 18 October 2026 — Authoritative Specification.**
>
> This is the single source of truth for the project: what we're building, why, how, what ships when, and what we will *not* claim. It merges the project direction, the technical specification, the two-surface design, the evaluation plan, the Frogtoberfest execution plan, and the research-paper trajectory into one file.
>
> **It supersedes:** `01-MASTER-DOCUMENTATION.md` (the one-day ArogyaKhata hackathon plan) and serves as the comprehensive companion to `README.md` (the public-facing summary of §1–§5 below).
>
> **It is not:** a pitch deck, a product roadmap beyond month one, or a claim that unverified clinical review has occurred. Where a number is prior-prototype or current deterministic benchmark evidence, it is labelled explicitly with its derivation and caveats.
>
> **One rule above all.** If a decision is not written here, it is not decided. If a feature does not pass §4.1, it does not ship. If a claim cannot be backed by a number, a citation, or a datum, it does not go in the paper or pitch.

**Event** · Frogtoberfest 2026 · Leapfrog Technology · October 2026
**Format** · Month-long open-source contribution challenge — weekly mergeable PRs, issue-driven, code review after the event
**Follow-on** · Research paper (target: arXiv preprint January 2027; venue submission thereafter)
**Team** · 2 core builders + open-source contributors
**Scope** · The Nepali clinical language layer. Two demonstration surfaces. Written path complete, spoken path staged.

---

## Document Map

| Part | Section | What it covers |
|---|---|---|
| **I** | §1–§6 | Direction: problem, solution, scope filter, names, why now |
| **II** | §7–§19 | The layer: architecture, lexicon, matching, extraction, uncertainty, confirmation, data model, API, stack |
| **III** | §20–§21 | Input paths: written (OCR) and spoken (ASR) |
| **IV** | §22–§24 | Surfaces: patient, FCHV, what ships vs. what's designed |
| **V** | §25–§29 | Evaluation, benchmark, metrics, error analysis, research questions, paper plan |
| **VI** | §30–§34 | Execution: Frogtoberfest plan, team, risks, deliverables, success criteria |
| **VII** | §35–§37 | Context: Nepal health systems, competitive landscape, references |
| **App.** | A–F | Naming, decision log, glossary, datasheet template, provenance codes, positioning |

---

# PART I · DIRECTION

## 1. The product in one sentence

**SwasthyaSanjaal builds the Nepali clinical language layer — a lexicon-grounded pipeline that turns messy real-world Nepali, spoken or written, into structured clinical fields with per-field uncertainty, and asks instead of guessing.**

The order of that sentence is the strategy. **The language layer is the product.** The two surfaces — a patient-owned record and an FCHV assessment — are demonstrations of what the layer enables. Pitch it the other way round and you have drifted into building an app.

## 2. The problem

Nepal does not have a shortage of health records. It has a problem with what those records contain and how they move.

Health information commonly begins as:

- handwritten prescriptions
- scanned or photographed reports
- Devanagari PDFs
- paper notes
- Romanized Nepali
- code-mixed Nepali–English
- spoken assessments

These formats may contain clinically useful information, but the information is rarely structured enough to be searched, connected to previous visits, validated, or reused across systems.

The difficult part begins **before** an electronic health record exists.

A sentence such as:

> `हिजोबाट तातो छ जस्तो छ, आज झन् बढेको।`

may need to become:

```json
{ "symptom": "fever", "duration": "2 days", "severity": "increasing" }
```

The same concept appears through many forms:

```text
ज्वरो · ज्वरो छ · मियादी जोरो · miyadi joro · typhoid · ज्वरो छैन · Glycomet
```

These are not merely spelling differences. A system must recognize colloquial language, Romanized text, negation, medicine brands, OCR errors, and conversational descriptions — while preserving the original meaning. **A single missed negation or incorrectly normalized medicine can produce a structurally valid record containing the wrong clinical concept.**

### 2.1 Two problems with the same root

**Patients do not have records they own.** A prescription is a handwritten slip. A lab report is a Devanagari PDF. A bill is a piece of paper. India solved this with ABDM — patient-owned health accounts, FHIR-based, scan-and-share QR. Nepal has the EHR pilots (NepalEHR, NIC Nepal, NEMRS planning) but not the interoperability or the language layer.

**The frontline cannot feed data upward.** Nepal has more than 51,000 Female Community Health Volunteers. They assess children, decide who needs referral, and record what they find. Most of that happens in conversation, in Nepali. That conversation has to become something a health system can use, and right now it mostly doesn't.

**The root is the same: there is no resource for Nepali clinical language.** Every Nepali NLP corpus is news text — NepBERTa, the IRIISNepal corpus, NepaliGPT, all trained on journalism. Nothing clinical. No lexicon of medical terms in Devanagari with Romanized variants. No negation handling. No uncertainty estimation. No way to know whether the system understood what was said or made something up.

### 2.2 What it costs

Data that is wrong in a way that looks right.

- A child who should have been referred.
- A record that cannot be exchanged because it was never structured.
- A patient who cannot check their own record because they cannot read it.
- EHR pilots that don't talk to each other, because the layer underneath them was never built.

## 3. What this project does

This project provides a **Nepali Clinical Language Layer** between unstructured health inputs and structured clinical records.

```text
                 REAL-WORLD INPUT
                        │
       ┌────────────────┼────────────────┐
       │                │                │
   Photograph        Document          Speech
       │                │                │
       └────────────────┼────────────────┘
                        ▼
                  AI / NLP LAYER
                        │
              Transcription / ASR
                        │
                 Clinical Lexicon
                        │
          Exact → Fuzzy → AI Matching
                        │
              Clinical Extraction
                        │
              Field-level Uncertainty
                        │
                  Confirmation
                        │
               Structured Record
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
     Patient                   Community
   Health Record               Health Use
```

The core transformation:

> **messy Nepali clinical language in → structured, reviewable health information out**

## 4. What we are building — and what we are not

### 4.1 The scope filter

One test, applied to every feature, forever:

> **Does this demonstrate the Nepali clinical language layer — or does it merely happen to be medical?**

Passes → build it. Fails → cut it, however good a product idea it is.

### 4.2 In scope

| Component | Why it's in |
|---|---|
| Nepali Clinical Lexicon (300 concepts) | The foundation. First of its kind. |
| Three-tier normalizer with tier logging | The method. Auditable. |
| Field extraction with per-field confidence | The output. |
| Per-field uncertainty estimation | The differentiator. |
| Human confirmation loop | The safety mechanism and the product surface. |
| Written path end-to-end (document → structured fields) | The complete, demonstrable product. |
| Speech pipeline: ASR evaluation + fine-tune | The research track. |
| Speech path end-to-end | Conditional on ASR quality. Stated honestly. |
| NepClinBench (60–100 items) | The evaluation. |
| Patient surface (intake → record → explanation → read-aloud) | Demonstration of the layer. |
| FCHV surface (confirmation loop for narrow scenario) | Demonstration of the layer. |
| Open-source release (CC-BY-4.0) | The contribution. |
| Research paper draft | The follow-on. |

### 4.3 Out of scope — cut, with reasoning

| Cut | Why |
|---|---|
| Full patient-record application | Months of work. The layer is the contribution. The record is a demonstration. |
| Full FCHV protocol engine | Deterministic protocol is easy; full workflow is not. Design it, don't build it in month one. |
| Benefit-package parsing | Separate from the core layer. Roadmap. |
| Symptom triage / diagnosis | Not a language feature. Fails §4.1. |
| Medication interaction engine | Needs a vetted DB. Not responsible in month one. |
| General health advice / open-ended chatbot | Unguarded model improvising clinical advice in Nepali. The only genuine downside risk in the build. |
| Bilingual UI chrome | Product surface, not language layer. |
| WebGPU / in-browser inference | Elegant, but the risk lands on the demo. Roadmap. |

> **If asked why no symptom checker or diet advice:** *"We built the language layer. Clinical advice needs clinical validation we don't have yet — shipping it untested would be the irresponsible version of this project."*

## 5. Why now

Three things converge.

1. **The models are good enough.** Open-source vision-language models now transcribe handwritten Devanagari at usable quality. Open-source ASR for Nepali exists and can be fine-tuned. The bottleneck is no longer the model — it is the missing resource.
2. **The comparison is live.** ABDM's nine hundred million patient-owned accounts prove the model works at national scale. Nepal has the EHR pilots but not the interoperability or the language layer.
3. **The research gap is real.** Clinical uncertainty estimation exists for English EHRs. Nepali clinical NLP is almost entirely unstudied. The contribution is clear and the baseline is low.

## 6. Names

| Layer | Name | Role |
|---|---|---|
| **Initiative / repository** | **SwasthyaSanjaal** (स्वास्थ्य सञ्जाल) | The mission, the umbrella. Warm, Nepali, recognises the network aspect. |
| **Open-source layer** | **Bodh** (बोध — understanding) | The package, the paper, the importable artifact. Short, distinctive, works in English and Nepali. |

**Rationale for two names.** SwasthyaSanjaal describes the mission; Bodh describes the artifact. The package name needs to be short and memorable for `pip install bodh`. The initiative name needs to be warm and recognisable for the README and the banner.

---

# PART II · THE LAYER

## 7. Architecture

```text
INPUT                ROUTING                NORMALIZATION              EXTRACTION              OUTPUT
─────                ───────                ─────────────              ──────────              ──────
text          ──┐
photo         ──┼──► is_image? ──► OCR ──┐
pdf           ──┘                          │
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
                              (JSON export)    inputs          explanation
```

Every step logs. Every field carries its provenance (which tier, which model, which threshold). This is what makes the system auditable.

## 8. Architectural principles

These are the rules the code follows. They are not aspirations.

### 8.1 Precision over recall

A clinical tool must be short on recall rather than wrong. Producing an extra hallucinated disease is clinically dangerous; missing a term is merely an omission. **Precision targets 1.000.** The evaluation reports recall honestly, and the uncertainty layer handles the trade-off by asking instead of guessing.

### 8.2 Approval before write

Ingesting an image or a voice note **never** writes to the database automatically. What the user reviews and confirms on screen is what is committed. Every entry carries a timestamp on commit.

### 8.3 Deterministic core, constrained models

Use the lexicon and deterministic code for what is known. Use open-source models for **perception** (OCR, ASR, semantic synthesis) and **constrained matching** (pick from a candidate list or return `UNKNOWN`). Never use a model for **open-ended clinical generation**.

### 8.4 Negation safety

Negated findings (`"ज्वरो छैन"`, `"chest pain denied"`) are flagged in the output and **strictly excluded** from downstream record exports. A missed negation is the single most dangerous failure mode in this system, and it is tested explicitly.

### 8.5 `UNKNOWN` is valid

When the system cannot resolve a term safely, it returns `UNKNOWN` rather than forcing a prediction. `UNKNOWN` triggers confirmation. It is not an error state.

### 8.6 Source preservation

Original text and normalized concepts are stored separately. The raw transcript is never edited.

```text
Original:    "मियादी जोरो"
Normalized:  concept_id → NCL-0058 (Typhoid fever)
             resolution_method → LEXICON
```

### 8.7 No fabricated authority

`source` says what is true. `verify_against` names who settles the row. `review_status` makes completion countable. **Do not claim clinician review that did not happen.** That is exactly the fabricated authority this project argues against.

### 8.8 No date fabrication

All internal dates are ISO-8601 Gregorian. Bikram Sambat (BS) is an authored display string only. Zero programmatic AD↔BS conversion, to prevent month-boundary inaccuracies.

## 9. The Nepali Clinical Lexicon

### 9.1 Purpose

The lexicon (`data/nepali_clinical_lexicon.json` and `.csv`) is the resource that makes the rest of the layer work. It is the first curated terminology resource for Nepali clinical language. It is released openly (CC-BY-4.0) with a datasheet (`data/DATASHEET.md`).

### 9.2 Schema

```json
{
  "concept_id": "NCL-0001",
  "canonical_en": "Fever",
  "canonical_np": "ज्वरो",
  "preferred_register": "colloquial",
  "devanagari_aliases": ["ज्वरो", "जोरो", "ताप"],
  "romanized_aliases": ["jworo", "joro", "fever", "taap"],
  "code_mixed_patterns": ["fever cha", "ज्वरो cha"],
  "concept_type": "symptom",
  "generic_of": null,
  "negation_sensitive": true,
  "negation_scope": null,
  "icd11_code": null,
  "source": "authored for SwasthyaSanjaal v0.1; not extracted from a published register",
  "verify_against": "clinician review — Nepali clinical usage",
  "review_status": "unreviewed",
  "license": "CC-BY-4.0"
}
```

**Honesty rule.** `review_status` currently reads `unreviewed` on every row. It flips to `clinician-reviewed` only when a named clinician signs off. The datasheet states this explicitly.

### 9.3 Coverage — 300 entries

| Category | Count | Examples |
|---|---|---|
| Drug brand names (`drug_brand`) | 65 | Glycomet → Metformin; Ecosprin → Aspirin; Cetamol → Paracetamol; Flexon → Ibuprofen+Paracetamol |
| Symptoms (`symptom`) | 63 | ज्वरो, झाडापखाला, रुघाखोकी, पेट दुख्ने, सास फेर्न गाह्रो, टाउको दुख्ने, रिंगटा लाग्ने |
| Conditions (`condition`) | 37 | मधुमेह, उच्च रक्तचाप, क्षयरोग, निमोनिया, टाइफाइड |
| Investigations (`investigation`) | 37 | CBC, X-ray, urine routine, blood sugar |
| Generic medications (`drug_generic`) | 28 | Paracetamol, Metformin, Amlodipine, Amoxicillin, ORS |
| Body sites (`body_site`) | 25 | छाती, पेट, टाउको, खुट्टा, मिर्गौला |
| Duration / frequency (`duration`) | 20 | दिन, हप्ता, महिना, पटक, देखि |
| Severity (`severity`) | 15 | धेरै, अलिकति, बढ्दै, कडा |
| Negation markers (`negation`) | 10 | छैन, भएन, नभएको, हुँदैन, बिना |

### 9.4 Canonicalization policy

Nepali has no standard medical vocabulary. **Policy: canonicalize to the register a patient actually uses, not the Sanskritized formal term.** Record the choice in `preferred_register`. Understanding matters more than vocabulary purity.

### 9.5 The lexicon as a safety boundary

The lexicon is not just a lookup table. It is the boundary that constrains the model. Models can select an approved concept or return `UNKNOWN`. They cannot silently invent new clinical terminology.

## 10. Multi-stage concept matching

Implemented in `backend/nlp/normalize.py` and `backend/nlp/tier3.py`:

| Tier | Provenance Code | Confidence | Meaning |
|---|---|---|---|
| **1** | `LEXICON` | `1.00` | Exact match against canonical or alias |
| **2** | `FUZZY_MATCH` | `0.85`–`0.95` | Devanagari orthographic folding (`0.95`) or RapidFuzz within Levenshtein edit budget ($\ge 0.85$) |
| **3** | `LLM` | `0.70` | Shortlist-constrained candidate selection; reasoning logged and confirmation required |
| **UNKNOWN** | `UNKNOWN` | `0.00` | System refuses to guess; triggers human confirmation |

## 11. Clinical information extraction

Implemented across `backend/nlp/normalize.py`, `backend/intake/pipeline.py`, and `backend/schemas.py`:

| Field | Example input | Output |
|---|---|---|
| `symptom` | ज्वरो | `{value: "fever", concept_id: "NCL-0001", negated: false}` |
| `duration` | ३ दिनदेखि | `{value: "3 days", duration_days: 3}` |
| `severity` | धेरै बढेको | `{value: "Increasing"}` |
| `body_site` | छाती दुख्ने | `{value: "Chest", concept_id: "NCL-..."}` |
| `negation` | ज्वरो छैन | `negated: true` on target concept |
| `medication` | सिटामोल / Glycomet | `{value: "Paracetamol", generic_of: "NCL-0088"}` |
| `lab_test` | CBC | `{value: "Complete blood count", concept_id: "NCL-0181"}` |

## 12. Negation handling

A directional window (default 3 tokens) detects post-positional Nepali negation markers (`छैन`, `थिएन`, `नभएको`, `chaina`) and pre-positional markers (`बिना`, `no`, `without`, `denies`) while respecting clause boundaries (`तर`, `र`, `,`). Negated findings carry `negated: true` and are strictly excluded from active condition summaries and FHIR R4 `Condition` exports.

## 13. Medicine normalization

Controlled brand-to-generic mappings link commercial Nepal brands (`drug_brand`) to their active pharmaceutical ingredient (`drug_generic`) via `generic_of`.

## 14. Field-level uncertainty estimation

Per-field uncertainty separates what the pipeline is certain about from what requires verification:

1. **Lexical & matching confidence** — derived from the normalizer tier (`1.00` for Tier 1 `LEXICON`, `0.85`–`0.95` for Tier 2 `FUZZY_MATCH`, `0.70` for Tier 3 `LLM`).
2. **Modality / acoustic confidence** — propagated from OCR (`[?]` unverified markers) or speech (`asr_confidence` on `/api/v1/intake/speech`).

Fields below the uncertainty threshold trigger `confirmation_required: true` alongside a Nepali confirmation prompt (`confirmation_prompt_np`).

## 15. Human confirmation layer

When a field is uncertain, the pipeline surfaces a structured Nepali confirmation prompt:

```text
System:   के तपाईंले "ज्वरो" भन्न खोज्नुभएको हो?
          (Did you mean "Fever"?)
```

Only after explicit human confirmation via `POST /api/v1/patients/{patient_id}/entries` is an extraction committed to the longitudinal record.

## 16. Provenance and audit trail

Every normalized concept and field records its provenance code (`resolution_method`):
- `LEXICON` — exact match
- `FUZZY_MATCH` — orthography-folded or Levenshtein fuzzy match
- `LLM` — model-constrained candidate selection
- `OCR` / `VLM` — vision-language document transcription
- `ASR` — speech transcription
- `HUMAN_CONFIRMED` — confirmed or corrected by a human at the write gate
- `UNKNOWN` — unresolved, triggers confirmation

## 17. Data model (SQLite)

Implemented in `backend/db.py` (`patients`, `allergies`, `record_entries`, `lexicon_entries`, `eval_results`) with additive migrations and foreign-key integrity.

## 18. API contract

Implemented in `backend/main.py` and `backend/routers/`:

```text
POST /api/v1/intake/text                 direct clinical text → corrected + normalized + uncertainty
POST /api/v1/intake/ocr                  image/PDF → PyMuPDF or VLM OCR → corrected + normalized
POST /api/v1/intake/speech               ASR transcript + confidence → normalized + uncertainty propagation
POST /api/v1/intake/voice                raw audio upload (fail-closed when backend lacks audio channel)
POST /api/v1/intake/stream               SSE streaming intake across routing, extraction, correction, normalization
POST /api/v1/intake/normalize            direct 3-tier normalization + field uncertainty
GET  /api/v1/lexicon                     query the 300-concept Nepali Clinical Lexicon
POST /api/v1/patients/{id}/entries       human confirmation gate (writes confirmed record)
GET  /api/v1/patients/{id}/record        longitudinal patient record hydrated against lexicon
GET  /api/v1/patients/{id}/fhir          HL7 FHIR R4 Bundle (negated findings strictly excluded)
POST /api/v1/eval/run                    run 60-item NepClinBench benchmark
GET  /api/v1/eval/latest                 retrieve benchmark summary and category breakdown
GET  /api/v1/health                      service and model backend status
```

## 19. Technology stack

| Layer | Choice | Why |
|---|---|---|
| Package | Python 3.11+ | ML/NLP ecosystem |
| API | FastAPI + Uvicorn | Async, typed, auto-docs |
| Validation | Pydantic v2 | Schema enforcement |
| Fuzzy / Edit Distance | RapidFuzz | Fast Levenshtein and token ratio calculation |
| HTTP | httpx | Model backend calls with automatic fallback |
| DB | SQLite (`sqlite3`) | Single-file, zero external container dependency |
| PDF extraction | PyMuPDF (`fitz`) | Free, instant, exact for born-digital PDFs |
| VLM / LLM | Open-source Gemma 4 family | Perception (OCR) and constrained Tier-3 matching |

---

# PART III · INPUT PATHS

## 20. Written path

1. **Digital PDF fast-path (`backend/intake/documents.py`)**: PyMuPDF checks for embedded text ($\ge 50$ non-whitespace characters). If present, extracts in $< 10\text{ ms}$ without invoking any VLM.
2. **Visual OCR (`backend/prompts/ocr_extract.txt`)**: Images and scanned PDFs use temperature `0.0` and explicitly mark illegible regions as `[?]` rather than guessing.
3. **Lexicon snapping (`backend/nlp/correct.py`)**: Conservative Levenshtein spell correction within a strict edit-distance budget against the lexicon.

## 21. Speech pipeline

Staged delivery:
1. **Stage 1 — ASR Evaluation & Domain Gap**: Evaluate general-domain Nepali ASR (OpenSLR / FLEURS / Whisper Nepali) on clinical utterances to measure domain degradation.
2. **Stage 2 — ASR Fine-Tune**: Domain-adaptive LoRA fine-tuning on noisy/colloquial clinical Nepali.
3. **Stage 3 — Spoken Path End-to-End (`/api/v1/intake/speech`)**: Accepts FCHV or patient ASR transcripts + `asr_confidence`, propagates acoustic uncertainty to extracted fields, and triggers Nepali confirmation prompts when confidence falls below threshold. Raw audio uploads (`/api/v1/intake/voice`) fail closed when the active LLM endpoint lacks a native audio waveform channel.

---

# PART IV · SURFACES

## 22. Patient path

Demonstrates `Document / Text → Document Understanding → Clinical Normalization → Structured Fields → Confirmation → Portable Health Record`.

## 23. FCHV path

Demonstrates `Spoken Assessment → ASR Transcript (+ Confidence) → Clinical Normalization → Uncertainty Detection → Nepali Confirmation Prompt → Confirmed Assessment`.

## 24. What ships vs. what's designed

| Artifact | Status | Notes |
|---|---|---|
| Nepali Clinical Lexicon (300 entries, CC-BY-4.0) | **Shipped** | `data/nepali_clinical_lexicon.json` + `.csv` + `DATASHEET.md` |
| Three-tier normalizer | **Shipped** | `backend/nlp/normalize.py` (`LEXICON`, `FUZZY_MATCH`, `LLM`) |
| Field extraction & uncertainty estimation | **Shipped** | `FieldUncertainty`, `confirmation_required`, `confirmation_prompt_np` |
| Human confirmation gate | **Shipped** | `POST /api/v1/patients/{id}/entries` |
| Provenance / audit trail | **Shipped** | Recorded per concept and field |
| Written path end-to-end | **Shipped** | PyMuPDF + VLM OCR + spell correction + 3-tier normalization |
| Spoken transcript + uncertainty path | **Shipped** | `POST /api/v1/intake/speech` + fail-closed `/api/v1/intake/voice` |
| NepClinBench (60 items) + harness | **Shipped** | `data/nepclinbench.json` + `python -m backend.eval` |
| ASR acoustic fine-tune & speech corpus | **Research Track** | Staged per §21.2 |

---

# PART V · EVALUATION & RESEARCH

## 25. NepClinBench

60 gold-annotated items (`data/nepclinbench.json`) across five categories: `clean_devanagari` (12), `romanized` (12), `code_mixed` (12), `negation` (12), and `ocr_corrupted` (12).

### Reproducible Baseline Measurement

Running `python -m backend.eval` on the current deterministic 3-tier pipeline yields:
- **Exact Set Match**: `58 / 60 (96.7%)`
- **Micro Precision**: `1.0000` (zero hallucinated clinical concepts)
- **Micro Recall**: `0.9818`
- **Negation Accuracy**: `10 / 10 (100.0%)` on the negation subset
- **Contested Items**: `#39` and `#40` (documented code-mixed edge cases where the normalizer refuses to guess).

## 26. Metrics

- **Per-field & micro**: precision, recall, F1
- **Per-tier**: match count and precision for Tier 1, Tier 2, and Tier 3
- **Per-category**: exact match accuracy across the 5 linguistic/degradation classes
- **Calibration & safety**: false-acceptance rate, `UNKNOWN` rate, confirmation rate

## 27. Error analysis

Tracked directly in `backend/eval/bench.py` (`missed`, `spurious`, and `caveats`).

## 28. Research questions

1. **RQ1**: How accurately can Nepali clinical expressions be normalized into a controlled clinical vocabulary?
2. **RQ2**: How much do exact matching, fuzzy matching, and constrained model matching contribute individually?
3. **RQ3**: How reliably can the system preserve clinical negation across post-positional Devanagari and Romanized phrasing?
4. **RQ4**: How accurately can commercial medicine brands in Nepal be mapped to generic concepts?
5. **RQ5**: How well can an open-source vision-language model transcribe handwritten or scanned Nepali clinical documents without introducing unsupported text?
6. **RQ6**: How well does Nepali clinical speech recognition perform compared with general-domain Nepali ASR?
7. **RQ7**: Does field-level uncertainty and human confirmation reduce downstream extraction errors?
8. **RQ8**: How does performance change across Devanagari, Romanized Nepali, code-mixed Nepali–English, and OCR-corrupted inputs?

## 29. Paper plan

- **Working Title**: *Bodh: Uncertainty-Aware Structured Extraction from Nepali Clinical Language*
- **Four Core Contributions**:
  1. **The Nepali Clinical Lexicon** (Resource)
  2. **Lexicon-grounded 3-tier extraction pipeline with per-field uncertainty** (Method)
  3. **NepClinBench** (Evaluation)
  4. **Empirical & ablation analysis across written and spoken paths** (Analysis)

---

# PART VI · EXECUTION

## 30. Frogtoberfest structure

| Week | Focus | Output | Contributor Tasks |
|---|---|---|---|
| **1** | Lexicon (300 entries) + 3-tier normalizer + unit tests | Working normalizer, lexicon JSON/CSV | Add aliases, Romanized variants, edge-case tests |
| **2** | Field extraction + uncertainty estimation + confirmation loop | Extraction API, confirmation prompts | Refine uncertainty thresholds, add field tests |
| **3** | Written path end-to-end (OCR → normalize → extract → confirm) + NepClinBench | Working pipeline, 60-item benchmark | Add benchmark items, error analysis |
| **4** | Speech pipeline + ASR evaluation + paper draft + documentation | Full documentation, evaluation report | ASR domain-gap evaluation, examples |

## 31–34. Team, Risks, Deliverables, and Success Criteria

See `CONTRIBUTING.md` for contributor onboarding, issue labels (`good-first-issue`, `help-wanted`, `research`, `bug`, `enhancement`), and PR verification steps.

---

# PART VII · CONTEXT

## 35. Nepal context

- **Fragmented EHR Pilots**: NepalEHR (Possible / Nyaya Health Nepal), NIC Nepal (Dhulikhel, Chitwan, Trishuli), NEMRS planning. None share a Nepali clinical language normalization layer.
- **Comparison**: India's ABDM (900M+ ABHA accounts, FHIR-based Scan and Share QR).
- **Frontline**: 51,000+ Female Community Health Volunteers (FCHVs) operating in spoken and colloquial Nepali.

## 36. Competitive landscape

While generic medical chatbots are common, **no open-source Nepali clinical lexicon, benchmark, and per-field uncertainty pipeline existed prior to SwasthyaSanjaal**.

## 37. References

- **Nepali NLP**: NepBERTa (AACL 2022), IRIISNepal Nepali-Text-Corpus (2024), NepaliGPT (2025), RoundTripOCR (arXiv:2412.15248)
- **Devanagari OCR**: *Can OCR-VLMs Read Devanagari? A Stress-Test Benchmark and Post-Correction Study* (arXiv:2606.29213)
- **ASR**: OpenSLR Nepali ASR corpus, Whisper Nepali fine-tunes, NepFinSpeech-403
- **Clinical Uncertainty**: CeRTS, calibration metrics (Brier score, AUROC)

---

# APPENDICES

## Appendix A · Naming and decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-18 | Focus on the language layer, not standalone chatbot/UI | Layer is the novel scientific & engineering contribution. |
| 2026-10-18 | Written path complete, spoken path staged with fail-closed raw audio | Written path is deterministically testable; raw audio fails closed when backend lacks audio channel. |
| 2026-10-18 | Do not train OCR from scratch | PyMuPDF fast-path + VLM transcription + lexicon-constrained correction is superior. |
| 2026-10-18 | Per-field uncertainty, not sequence-level | Per-field confidence drives targeted Nepali confirmation prompts. |
| 2026-10-18 | Constrained model matching, not open generation | Cannot hallucinate a diagnosis if restricted to `EXISTING_CONCEPT_ID` or `UNKNOWN`. |
| 2026-10-18 | No claim of clinician review | `review_status: "unreviewed"` on all 300 rows until a named clinician signs off. |

## Appendix B · Glossary

| Term | Meaning |
|---|---|
| **Clinical language layer** | Pipeline turning messy Nepali clinical language into structured fields with per-field uncertainty |
| **Lexicon (NCL)** | Curated list of 300 clinical concepts with Devanagari, Romanized, Latin, and code-mixed aliases |
| **Tier 1 / 2 / 3** | Exact (`LEXICON`) / Fuzzy (`FUZZY_MATCH`) / Model-constrained (`LLM`) matching |
| **Per-field uncertainty** | Confidence score and `confirmation_required` flag for each extracted field |
| **Confirmation** | Human-in-the-loop verification step before writing to the health record |
| **NepClinBench** | 60-item benchmark evaluating extraction across 5 realistic Nepali clinical input classes |

## Appendix C · Datasheet compliance

Implemented in [`data/DATASHEET.md`](../data/DATASHEET.md), covering Motivation, Composition, Collection Process, Preprocessing, Uses, Distribution, Maintenance, and Known Gaps (`review_status: unreviewed`).

## Appendix D · Provenance codes

| Code | Meaning |
|---|---|
| `LEXICON` | Exact match against the Nepali Clinical Lexicon (Tier 1) |
| `FUZZY_MATCH` | Orthography-folded or Levenshtein fuzzy match above threshold (Tier 2) |
| `LLM` | Model-constrained selection from candidate shortlist (Tier 3) |
| `OCR` / `VLM` | Transcribed by the vision-language model |
| `ASR` | Transcribed from speech |
| `HUMAN_CONFIRMED` | Confirmed or corrected by a human at the write gate |
| `UNKNOWN` | Unresolved; triggers human confirmation |

## Appendix E · Positioning

- **For Frogtoberfest**: Issue-driven open-source project releasing the first Nepali clinical lexicon (CC-BY-4.0), a 3-tier uncertainty-aware normalization pipeline, and NepClinBench.
- **For Research**: *Bodh: Uncertainty-Aware Structured Extraction from Nepali Clinical Language* — resource, method, benchmark, and empirical ablation.

## Appendix F · The one-paragraph summary

> **SwasthyaSanjaal** builds the Nepali clinical language layer — a lexicon-grounded pipeline that turns messy real-world Nepali, spoken or written, into structured clinical fields with per-field uncertainty, and asks instead of guessing. It ships with a curated 300-concept Nepali Clinical Lexicon, a three-tier normalizer, a field-level uncertainty estimator, a human confirmation loop, and the 60-item NepClinBench benchmark for evaluating extraction under realistic low-resource conditions. The goal is not to replace clinical judgment, but to make the language layer reliable enough that downstream systems — patient records, FCHV protocols, referral tools — can trust what they receive, and know when to ask a human instead of guessing.
