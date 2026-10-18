# Datasheet: Nepali Clinical Lexicon and NepClinBench

## Motivation

Existing Nepali NLP resources (e.g., NepBERTa, NepaliGPT, IndicBench) are predominantly derived from news-domain and web corpora. `SwasthyaSanjaal` builds the **Nepali Clinical Language Layer** to support clinical language normalization across handwritten prescriptions, Devanagari documents, Romanized phonetic notes, code-mixed Nepali-English expressions, OCR-corrupted text, and spoken community-health assessments.

## Composition

- `nepali_clinical_lexicon.json` — 300 bilingual clinical concepts (`NCL-0001` through `NCL-0300`)
- `nepali_clinical_lexicon.csv` — Tabular CSV export of the controlled clinical lexicon
- `icd_crosswalk.csv` — WHO ICD-11 and ICD-10 diagnostic code crosswalk
- `nepclinbench.json` — 60 gold-standard evaluation benchmark items across 5 linguistic and degradation categories

| Concept Type | Count | Description |
| --- | --- | --- |
| `drug_brand` | 65 | Commercial pharmaceutical brand names prescribed in Nepal mapped to generic compounds |
| `symptom` | 63 | Colloquial, formal, and Romanized patient symptom descriptions |
| `condition` | 37 | Clinical diagnoses mapped to WHO ICD-11 and ICD-10 codes |
| `investigation` | 37 | Laboratory tests and diagnostic imaging investigations |
| `drug_generic` | 28 | Active pharmaceutical ingredients (NLEM 2021 / WHO Essential Medicines) |
| `body_site` | 25 | Anatomical locations and qualifiers |
| `duration` | 20 | Temporal duration expressions (`duration_days`, `frequency_per_day`) |
| `severity` | 15 | Clinical severity and progression modifiers |
| `negation` | 10 | Directional clinical negation markers (`pre` and `post` scope) |
| **Total** | **300** | **Controlled clinical ontology** |

### Synthetic Clinical Records

`seed_patients.json` (3 patient profiles) and `seed_entries.json` (4 multi-modal clinical encounters) are synthetic records designed for pipeline evaluation and demonstration. No real patient identifiable information (PII) is present.

Dates carry two distinct fields to prevent silent calendar conversion errors:

| Field | Calendar | Purpose |
| --- | --- | --- |
| `record_date` | Gregorian ISO-8601 (`YYYY-MM-DD`) | Canonical sorting, longitudinal comparison, and HL7 FHIR R4 resource compliance |
| `record_date_bs` | Bikram Sambat (BS) | Authored display string for local clinical context; never programmatically converted |

### Per-Concept Schema & Linguistic Fields

- **`devanagari_aliases`**: Strictly Devanagari script surface forms (`ज्वरो`, `मियादी जोरो`), preventing Latin script contamination in Devanagari-specific matchers.
- **`romanized_aliases`**: Phonetic Latin transcriptions as typed by patients and health workers on mobile keyboards (`jworo`, `tauko dukhne`).
- **`latin_aliases`**: Standard international clinical abbreviations and terminology appearing on laboratory slips (`CBC`, `HbA1c`, `SpO2`, `Widal`).
- **`code_mixed_patterns`**: Multi-token bilingual Nepali-English phrases common in clinical notes (`fever cha`, `tab cetamol`).
- **`generic_of`**: Explicit pointer from a `drug_brand` concept to its underlying `drug_generic` concept ID, enabling deterministic brand-to-generic resolution and duplicate-therapy detection.
- **`negation_scope`**: Specifies whether a negation marker operates post-positionally (`छैन` $\rightarrow$ `post`) or pre-positionally (`बिना` $\rightarrow$ `pre`).
- **`duration_days` & `frequency_per_day`**: Structured numeric representations for temporal duration and dosing frequency.
- **`verify_against`, `review_status`, & `sources`**: Explicit provenance tracking naming the clinical authority (`Nepal DDA`, `NLEM 2021`, `WHO ICD-11 MMS`, `EDCD Nepal`) and verification state for each concept.

### Alias Uniqueness & Disambiguation Discipline

Every surface string maps deterministically to a single concept across `devanagari_aliases`, `romanized_aliases`, `latin_aliases`, and `code_mixed_patterns`:

1. **Brand Ownership**: A commercial brand name (`सिटामोल`, `Taxim-O`) resolves to its `drug_brand` concept, which links to its generic compound via `generic_of`.
2. **Symptom vs. Anatomy Separation**: Complaint phrases (`chest pain`, ` छाती दुख्ने`) belong to `symptom` concepts rather than `body_site` concepts.
3. **No Silent Diagnostic Inference**: Laboratory findings (`Hb low`) map to the laboratory observation concept (`Hemoglobin`) rather than inferring a clinical diagnosis (`Anemia`).

## Intended Uses

- Deterministic and constrained-AI normalization of messy Nepali clinical inputs
- Evaluating exact matching, orthography-folded fuzzy matching, and constrained LLM candidate selection
- Preserving directional clinical negation and brand-to-generic medication mappings
- Benchmarking OCR post-correction and clinical speech normalization pipelines

## Out-of-Scope Uses

This dataset is an open-source research artifact and must **not** be used as an autonomous clinical decision-making system, unverified medication safety database, or automated insurance claims adjudication engine without human clinician review.

## License

Released under the **Creative Commons Attribution 4.0 International License (CC-BY-4.0)**.
