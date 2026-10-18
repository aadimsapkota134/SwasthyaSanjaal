# 04 — Data, Lexicon & Demo Assets Specification

> **Companion to [`docs/00-MASTER-DOCUMENTATION.md`](00-MASTER-DOCUMENTATION.md) (§9) and [`data/DATASHEET.md`](../data/DATASHEET.md).**

---

## 1. The Nepali Clinical Lexicon (`data/nepali_clinical_lexicon.json`)

### 1.1 Why It Exists
Every prior Nepali NLP resource is news-domain (NepBERTa, IRIISNepal corpus, NepaliGPT, NepaliBERT, Nep-gLUE, NPVec1). **No medical or clinical terminology dataset existed for Nepali.** `nepali_clinical_lexicon.json` is the first open, machine-readable clinical vocabulary for Nepali, released under **CC-BY-4.0**.

### 1.2 Authoritative Schema
Each of the **300 concepts** (`NCL-0001` through `NCL-0300`) adheres to the following schema:

```json
{
  "concept_id": "NCL-0058",
  "canonical_en": "Typhoid fever",
  "canonical_np": "टाइफाइड ज्वरो",
  "preferred_register": "colloquial",
  "devanagari_aliases": ["मियादी जोरो", "मियादी ज्वरो", "टाइफाइड", "टाइफाइड ज्वरो"],
  "romanized_aliases": ["miyadi joro", "typhoid", "miyadi jworo"],
  "latin_aliases": [],
  "code_mixed_patterns": ["typhoid cha", "मियादी joro"],
  "concept_type": "condition",
  "generic_of": null,
  "icd11_code": "1A07",
  "icd10_code": "A01.0",
  "negation_sensitive": true,
  "duration_days": null,
  "frequency_per_day": null,
  "negation_scope": null,
  "source": "authored for ArogyaKhata v0.1; not extracted from a published register",
  "verify_against": "WHO ICD-11 MMS",
  "review_status": "unreviewed",
  "license": "CC-BY-4.0"
}
```

### 1.3 Field Semantics & Honesty Rules

| Field | Semantics |
|---|---|
| `concept_id` | Stable `NCL-####` identifier. Never reused. |
| `preferred_register` | `colloquial` \| `literary` \| `clinical`. Records the canonicalization decision. |
| `devanagari_aliases` | Strictly Devanagari surface forms seen in prescriptions, lab slips, and patient notes. |
| `romanized_aliases` | Phonetic Latin transliterations typed on mobile keyboards without Devanagari input. |
| `latin_aliases` | International clinical abbreviations (`CBC`, `HbA1c`, `SpO2`, `Widal`). |
| `code_mixed_patterns` | Multi-token Nepali–English clinical phrases (`"fever cha"`, `"tab cetamol"`). |
| `concept_type` | `drug_brand` (65) \| `symptom` (63) \| `condition` (37) \| `investigation` (37) \| `drug_generic` (28) \| `body_site` (25) \| `duration` (20) \| `severity` (15) \| `negation` (10). |
| `generic_of` | On `drug_brand` concepts, points to the parent `drug_generic` `concept_id`. |
| `negation_sensitive` | Whether directional negation markers (`छैन`, `बिना`) flip `negated=True` on this concept. |
| `negation_scope` | On `negation` concepts, specifies `"post"` / `"backward"` (Nepali post-positional) or `"pre"` / `"forward"` (pre-positional). |
| `source` | Honest authorship statement. Never claims extraction from an external register that wasn't directly ingested. |
| `verify_against` | Names the external clinical authority that settles the row (`WHO ICD-11 MMS`, `NLEM 2021`, `Nepal DDA`, `clinician review`). |
| `review_status` | Currently `"unreviewed"` across all 300 rows until a named clinician signs off. |

---

## 2. Why Commercial Brand Names Are High-Value

Real prescriptions in Nepal are written predominantly in commercial brand names (`सिटामोल` / `Cetamol` / `Niko` rather than Paracetamol; `Glycomet` rather than Metformin; `Ecosprin` rather than Aspirin; `Taxim-O` rather than Cefixime). A clinical NLP pipeline that only recognizes WHO generic INN names fails on the first real prescription it encounters.

Mapping `drug_brand` $\rightarrow$ `generic_of` $\rightarrow$ `drug_generic` provides:
- Deterministic entity linking without LLM hallucination
- Duplicate-therapy awareness (e.g., recognizing two different brands of Paracetamol)
- Clean downstream HL7 FHIR R4 `MedicationRequest` coding

---

## 3. Devanagari Preprocessing Rules (`backend/nlp/devanagari.py`)

Before any Tier 1 or Tier 2 lookup runs, `prepare()` applies four deterministic transformations:

1. **Unicode NFC Normalization (`unicodedata.normalize("NFC", text)`)**: Visually identical Devanagari strings can differ in byte representation (composed vs. decomposed nukta/vowel sequences). NFC normalization is mandatory.
2. **Zero-Width Character Stripping**: Removes `\u200b` (ZWSP), `\u200c` (ZWNJ), `\u200d` (ZWJ), and `\ufeff` (BOM), which frequently appear in mobile Devanagari keyboards and PDF text layers.
3. **Devanagari Numeral Folding (`५८९` $\rightarrow$ `589`)**: Normalizes `०`–`९` (`\u0966`–`\u096f`) to ASCII digits `0`–`9` so dosages (`५०० एमजी` $\rightarrow$ `500 एमजी`) and durations (`३ दिन` $\rightarrow$ `3 दिन`) parse uniformly.
4. **Danda Punctuation Separation**: Normalizes `।` and `॥` into clause boundaries so directional negation windows never leak across sentences.

---

## 4. Synthetic Encounter & Demo Assets (`data/`)

- **`data/seed_patients.json`**: Three synthetic patient profiles (`patient_ram`, `patient_sita`, `patient_maya`) carrying both `sanjaal_id` (`SS-NP-####`) and `sanchai_id` (`SANCHAI-####`), allergies, and chronic conditions.
- **`data/seed_entries.json`**: Four synthetic longitudinal encounters demonstrating prescription OCR, lab report extraction, and voice/speech negation (`"ज्वरो छैन"`).
- **`data/demo_assets/`**:
  - `lab_report_01.pdf` — Born-digital PDF laboratory report exercising the `< 10 ms` PyMuPDF extraction fast-path.
  - `prescription_01_sample.txt` & `prescription_02_sample.txt` — Bilingual Devanagari + English prescription samples.
  - `bill_01_sample.txt` — Hospital billing receipt sample exercising document classification (`CLASS_BILL`).
