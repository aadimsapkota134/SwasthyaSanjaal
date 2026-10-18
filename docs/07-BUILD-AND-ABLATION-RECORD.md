# 07 — Engineering Build & Ablation Record

> **Adapted from the empirical engineering log (`12-BUILD-RECORD.md`) and updated for SwasthyaSanjaal.**

Nothing in this document is aspirational. Every number and architectural invariant below traces to an executable command and test in this repository.

---

## 1. Key Engineering Findings & Decisions

### 1.1 Why Constrained Lexicon Matching Beats Unconstrained LLM Extraction
To answer the question *"Why not let Gemma 4 extract clinical concepts directly without a lexicon?"*, `backend/eval/baseline.py` runs an unconstrained extraction prompt (`backend/prompts/baseline_extract.txt`) on the exact same 60 `NepClinBench` items and maps the LLM's free-text predictions back to the lexicon using a generous `0.80` fuzzy threshold (looser than our own Tier 2 `0.85` threshold):

| Configuration | Exact Match | Micro Precision | Micro Recall | Micro F1 |
|---|---|---|---|---|
| **SwasthyaSanjaal (Tiers 1 + 2 Deterministic)** | **58 / 60 (96.7%)** | **1.0000** | **0.9818** | **0.9908** |
| **Raw Gemma 4 (Unconstrained, No Lexicon)** | 42 / 60 (70.0%) | 0.7810 | 0.7310 | 0.7550 |
| **SwasthyaSanjaal Full System (Tiers 1 + 2 + 3)** | **58 / 60 (96.7%)** | **1.0000** | **0.9818** | **0.9908** |

**Why the unconstrained LLM loses 22 points of precision:**
1. **Vocabulary Drift into Unmapped Jargon**: When given colloquial Nepali complaints, an unconstrained LLM frequently emits varying English medical terms (*dyspnea*, *dysuria*, *hematochezia*, *hyperglycemia*) or inconsistent paraphrases that cannot be deterministically linked to a controlled concept ID.
2. **Nepali Brand Blindness**: Without the lexicon's `generic_of` table, raw LLM inference misses or misidentifies local Nepal pharmaceutical brands (`सिटामोल`, `Niko`, `एमलोवास्क`).
3. **Clause-Bounded Negation Inversion**: On compound Nepali sentences (`"खोकी छ तर छाती दुख्ने छैन"`), unconstrained prompts occasionally drop or invert the negation flag on the second clause.

Reproduce the comparison anytime via:
```bash
python -m backend.eval --compare
```

---

### 1.2 Fairness Rules in `backend/eval/baseline.py`
To ensure the ablation is scientifically fair and never rigged against the baseline:
1. **Generous Fuzzy Threshold (`0.80` vs. `0.85`)**: The baseline's free-form concept names are matched back to lexicon surface forms at `0.80` similarity.
2. **Prose-Wrapped JSON Parsing**: Regex extraction (`\{.*\}`) parses JSON objects even when the LLM wraps its response in markdown fences or commentary.
3. **Whole-Token Phrase Matching (`_contains_phrase`)**: Prevents substring false positives (such as matching *"subacute"* onto the severity modifier *"acute"*).
4. **Network Disconnection Tracking (`unanswered`)**: If the model endpoint is offline, items are counted in `unanswered` rather than silently scored as empty predictions.

---

### 1.3 Fail-Closed Raw Audio vs. Nepali Speech Transcript Pipeline
Live verification against standard Ollama endpoints (`/api/generate` and `/api/chat`) proved that standard Ollama HTTP payloads silently discard audio waveform arrays and evaluate only the text prompt tokens—causing the LLM to invent a fictional Nepali patient monologue.

In **SwasthyaSanjaal**:
- Raw audio uploads (`POST /api/v1/intake/voice`) fail closed (`AUDIO_INPUT_SUPPORTED = False`), returning `extraction_status = "engine_unavailable"`, zero fabricated tokens, and `confirmation_required = True`.
- Spoken assessments enter via `POST /api/v1/intake/speech` (`run_speech_intake`), which processes ASR transcripts together with `asr_confidence` (`0.0`–`1.0`), scales concept and field confidences by acoustic certainty, and generates Nepali confirmation prompts (`confirmation_prompt_np`) whenever certainty falls below `0.85`.

---

## 2. Verification Commands & Test Coverage

| Verification Check | Result | Command |
|---|---|---|
| **Automated Pytest Suite** | **51 / 51 passing** | `pytest -q` |
| **Nepali Clinical Lexicon** | **300 concepts** across 9 types | `python scripts/expand_lexicon.py` |
| **NepClinBench Evaluation** | **58 / 60 (96.7%)**, Precision **1.0000** | `python -m backend.eval` |
| **Negation Accuracy** | **10 / 10 (100.0%)** | `python -m backend.eval` |
| **HL7 FHIR R4 Validation** | Validated via `fhir.resources` R4 `Bundle` | `pytest tests/test_fhir.py -q` |

---

## 3. Documented Limitations & Honest Caveats

1. **Clinician Review Pending (`review_status: "unreviewed"`)**: All 300 lexicon entries currently carry `"review_status": "unreviewed"`. No entry is marked `"clinician-reviewed"` until a named clinician signs off.
2. **Tier 3 Coverage on NepClinBench**: Because Tiers 1 and 2 resolve 58 of the 60 benchmark items deterministically, Tier 3 (`GemmaTier3Matcher`) is exercised via dedicated unit and integration tests rather than dominating the benchmark score.
3. **Synthetic OCR Perturbations**: The 12 `ocr_corrupted` items in `nepclinbench.json` carry explicit `derivation` metadata (`authored` vs. `synthetic_perturbation`), reported automatically in `caveats()` by the benchmark runner.
