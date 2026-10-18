# Datasheet: Nepali Clinical Lexicon (NCL) and NepClinBench

Following the *Datasheets for Datasets* (Gebru et al., 2021) standard and **Appendix C** of [`docs/00-MASTER-DOCUMENTATION.md`](../docs/00-MASTER-DOCUMENTATION.md), this document records the motivation, composition, collection process, preprocessing, intended uses, distribution, maintenance, and known gaps of the **SwasthyaSanjaal** clinical language resources.

---

## 1. Motivation

Existing Nepali NLP corpora and models (e.g., NepBERTa, IRIISNepal Nepali-Text-Corpus, NepaliGPT, IndicBench) are built almost entirely from news journalism and general web text. None cover clinical terminology, colloquial symptom expressions, Romanized clinic shorthand, or commercial pharmaceutical brand names prescribed in Nepal.

**SwasthyaSanjaal** (open-source layer **Bodh · बोध**) introduces the **Nepali Clinical Lexicon (NCL)** and **NepClinBench** to ground clinical extraction in a curated, auditable vocabulary where every match carries explicit provenance (`LEXICON`, `FUZZY_MATCH`, `LLM`) and per-field uncertainty.

---

## 2. Composition

- **`data/nepali_clinical_lexicon.json` & `.csv`** — 300 bilingual clinical concepts (`NCL-0001` through `NCL-0300`).
- **`data/icd_crosswalk.csv`** — Crosswalk mapping clinical conditions and symptoms to WHO ICD-11 MMS and ICD-10 codes.
- **`data/nepclinbench.json`** — 60 gold-annotated evaluation items across 5 input categories (`clean_devanagari`, `romanized`, `code_mixed`, `negation`, `ocr_corrupted`).
- **`data/seed_patients.json` & `data/seed_entries.json`** — Synthetic clinical records for pipeline testing (zero real patient PII).

| Concept Type | Count | Description |
|---|---|---|
| `drug_brand` | 65 | Commercial pharmaceutical brand names prescribed in Nepal linked to generic compounds via `generic_of` |
| `symptom` | 63 | Colloquial, formal, and Romanized patient symptom descriptions (`ज्वरो`, `पेट पोल्ने`, `रिंगटा लाग्ने`) |
| `condition` | 37 | Clinical diagnoses mapped to WHO ICD-11 and ICD-10 codes (`मधुमेह`, `उच्च रक्तचाप`, `टाइफाइड`) |
| `investigation` | 37 | Laboratory tests and diagnostic imaging investigations (`CBC`, `HbA1c`, `Widal`) |
| `drug_generic` | 28 | Active pharmaceutical ingredients (NLEM 2021 / WHO Essential Medicines) |
| `body_site` | 25 | Anatomical locations and qualifiers (`छाती`, `पेट`, `टाउको`) |
| `duration` | 20 | Temporal duration and dosing frequency expressions (`duration_days`, `frequency_per_day`) |
| `severity` | 15 | Clinical severity and progression modifiers (`धेरै`, `अलिकति`, `बढ्दै`) |
| `negation` | 10 | Directional clinical negation markers (`छैन`, `भएन`, `नभएको`, `बिना`) |
| **Total** | **300** | **Controlled Nepali clinical vocabulary** |

---

## 3. Collection Process & Canonicalization Policy

- **Authorship**: Entries were authored for SwasthyaSanjaal v0.1 by cross-referencing standard Nepali OPD/FCHV expressions, Nepal's National List of Essential Medicines (NLEM 2021), Department of Drug Administration (DDA) registered brands, and WHO ICD-11 MMS concepts.
- **Canonicalization Policy**: Nepali has no single standardized medical register. SwasthyaSanjaal canonicalizes to the register a patient or frontline health worker actually uses (e.g., `दम` and `उच्च रक्तचाप`) rather than artificial Sanskritized neologisms, recording the register in `preferred_register` (`colloquial` vs. `literary`).
- **Provenance & Verification Fields**:
  - `source`: States how the row was created (`"authored for ArogyaKhata/SwasthyaSanjaal v0.1; not extracted from a published register"`).
  - `verify_against`: Names the external authority that settles the row (`WHO ICD-11 MMS`, `NLEM 2021`, `Nepal DDA`, or `clinician review — Nepali clinical usage`).
  - `review_status`: Explicitly tracks clinician sign-off (`"unreviewed"` on all 300 rows in v0.1).

---

## 4. Preprocessing & Indexing

- **Script Separation**: `devanagari_aliases` contains strictly Devanagari surface forms; `romanized_aliases` contains phonetic Latin transliterations (`jworo`, `khoki`); `latin_aliases` contains clinical abbreviations (`CBC`, `SpO2`); `code_mixed_patterns` contains multi-token bilingual phrases (`fever cha`).
- **Alias Uniqueness**: Every surface form maps deterministically to a single concept ID so Tier 1 lookup is $O(1)$ and ambiguity-free.
- **No Calendar Fabrication**: Internal encounter dates (`record_date`) use ISO-8601 Gregorian (`YYYY-MM-DD`). Bikram Sambat (`record_date_bs`) is stored as an authored display string and is never programmatically converted.

---

## 5. Intended Uses

- Grounding 3-tier Nepali clinical concept normalization (`LEXICON` $\rightarrow$ `FUZZY_MATCH` $\rightarrow$ constrained `LLM`)
- Lexicon-constrained post-OCR spell correction
- Preserving directional clinical negation (`negation_scope`) and brand-to-generic medication linking (`generic_of`)
- Evaluating extraction and uncertainty calibration on `NepClinBench`

### Out-of-Scope Uses

This dataset must **not** be used for autonomous clinical diagnosis, unverified drug-interaction checking, or automated medical advice generation without human clinician oversight.

---

## 6. Distribution

Released openly under the **Creative Commons Attribution 4.0 International License (CC-BY-4.0)** in both JSON (`data/nepali_clinical_lexicon.json`) and CSV (`data/nepali_clinical_lexicon.csv`) formats.

---

## 7. Maintenance & Contribution

Maintained in the `SwasthyaSanjaal` repository. Contributors can add aliases, Romanized variants, and new concepts via pull requests following [`CONTRIBUTING.md`](../CONTRIBUTING.md) and running `pytest` + `python -m backend.eval` to verify zero alias collisions and zero precision regressions.

---

## 8. Known Gaps & Honesty Statement

1. **Clinician Review Status (`review_status: "unreviewed"`)**: Every row in `nepali_clinical_lexicon.json` currently carries `"review_status": "unreviewed"`. We do **not** claim clinician sign-off that has not yet occurred; rows transition to `"clinician-reviewed"` only when verified by a named clinician.
2. **Regional Dialect Variation**: Current aliases focus on standard and central hill/valley colloquial Nepali; far-western (*Doteli/Khas*) and Terai code-mixed clinical expressions are underrepresented and targeted for community contribution.
3. **Contested Code-Mixed Benchmark Items**: Items `#39` and `#40` in `nepclinbench.json` represent contested code-mixed shorthand where the deterministic normalizer abstains (`precision = 1.000`, `58/60` exact match) rather than guessing.
