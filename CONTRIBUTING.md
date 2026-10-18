# Contributing to SwasthyaSanjaal (स्वास्थ्य सञ्जाल)

Thank you for contributing to **SwasthyaSanjaal** (and its open-source clinical language layer, **Bodh · बोध**)!

This project is built as an open-source research and engineering initiative for **Frogtoberfest 2026** and our follow-on research paper (*Bodh: Uncertainty-Aware Structured Extraction from Nepali Clinical Language*).

---

## 1. The Scope Filter (Read First)

Every pull request and feature proposal is evaluated against a single rule (see [`docs/00-MASTER-DOCUMENTATION.md §4.1`](docs/00-MASTER-DOCUMENTATION.md)):

> **Does this demonstrate the Nepali clinical language layer — or does it merely happen to be medical?**

- **In Scope**: Nepali Clinical Lexicon entries, Devanagari/Romanized/code-mixed aliases, 3-tier normalization improvements, directional negation rules, brand-to-generic drug mappings, OCR post-correction, ASR evaluation & uncertainty calibration, `NepClinBench` test items, and human confirmation workflows.
- **Out of Scope**: Open-ended AI health advice chatbots, unverified symptom triage/diagnosis, or ungrounded clinical generation.

---

## 2. Where You Can Contribute

We organize issues using five standard labels:

- `good-first-issue` — Add Romanized aliases, Devanagari spelling variants, or brand-to-generic mappings in `data/nepali_clinical_lexicon.json`; fix typos; add unit tests.
- `help-wanted` — Expand `NepClinBench` test cases (`data/nepclinbench.json`), improve duration/frequency/severity modifier extraction, or enhance documentation.
- `research` — Per-field uncertainty calibration (Brier score, AUROC), Nepali clinical ASR domain-gap evaluation, and error analysis on OCR/ASR corruptions.
- `bug` — Reproducible issues in normalization, negation scope, or PDF/OCR routing.
- `enhancement` — Pipeline and API improvements aligned with the Master Documentation.

---

## 3. Local Development Setup

### Prerequisites
- Python 3.11+
- Git

### Installation

```bash
git clone https://github.com/aadimsapkota134/SwasthyaSanjaal.git
cd SwasthyaSanjaal
pip install -r backend/requirements.txt
```

### Running the Evaluation Benchmark (`NepClinBench`)

```bash
python -m backend.eval
```

Expected deterministic baseline output:
- **Exact Set Match**: `58/60 (96.7%)`
- **Micro Precision**: `1.0000` (Zero Hallucinations)
- **Negation Accuracy**: `10/10 (100.0%)`

### Running the Automated Test Suite

```bash
pytest -q
```

### Running the API Server Locally

```bash
uvicorn backend.main:app --reload --port 8000
```

---

## 4. Guidelines for Lexicon & Benchmark Contributions

1. **Honesty Rule (`review_status`)**:
   - New lexicon entries must set `"review_status": "unreviewed"` and specify `"source"` and `"verify_against"`. Never set `"review_status": "clinician-reviewed"` unless a named clinician has reviewed and signed off on the entry.
2. **Script Discipline**:
   - `devanagari_aliases` must contain Devanagari script only.
   - `romanized_aliases` must contain lowercase Latin transliterations (`jworo`, `pet polne`).
   - `code_mixed_patterns` holds multi-token Nepali–English phrases (`fever cha`, `bp high छ`).
3. **Precision Target (`1.000`)**:
   - Never add an ambiguous alias that collides with an unrelated clinical concept. Always run `pytest` and `python -m backend.eval` before opening a PR.

---

## 5. Pull Request Workflow

1. Link the relevant issue in your PR description.
2. Keep PRs focused and small so they can be reviewed and merged within 48 hours.
3. Include unit tests (`tests/`) or benchmark items (`data/nepclinbench.json`) for any new normalization or extraction behavior.
4. Ensure `pytest -q` passes with zero failures.
