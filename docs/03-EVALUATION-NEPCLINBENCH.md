# 03 — NepClinBench Evaluation, Research Questions & Paper Plan

> **Companion to [`docs/00-MASTER-DOCUMENTATION.md`](00-MASTER-DOCUMENTATION.md) (§25–§29).**

## 1. NepClinBench Specification (`data/nepclinbench.json`)

**NepClinBench** is a 60-item gold-annotated benchmark evaluating clinical normalization and extraction across five realistic Nepali input classes (12 items per category):

| Category | Count | Example Input | Target Phenomenon |
|---|---|---|---|
| `clean_devanagari` | 12 | `"ज्वरो, ३ दिन देखि"` | Colloquial & formal Devanagari symptoms, durations, and chronic conditions |
| `romanized` | 12 | `"malai 3 din dekhi jwaro ra khoki chha"` | Informal phonetic Latin transliteration used in SMS and mobile notes |
| `code_mixed` | 12 | `"Tab Sitamol 500mg दिनको २ पटक"` | Bilingual Nepali–English prescriptions and brand-to-generic linking |
| `negation` | 12 | `"खोकी छ तर छाती दुख्ने छैन"` | Post-positional Nepali negation (`छैन`, `नभएको`) and clause boundaries |
| `ocr_corrupted` | 12 | `"ज्वरो र खोकि छ"` | Matra, conjunct, and sibilant corruptions typical of Devanagari OCR |

---

## 2. Reproducible Benchmark Results

Execute the evaluation suite via:

```bash
python -m backend.eval
```

| Metric | Score | Notes |
|---|---|---|
| **Exact Set Match** | **58 / 60 (96.7%)** | Both `predicted_present == gold_present` and `predicted_negated == gold_negated` |
| **Micro Precision** | **1.0000** | Zero hallucinated or spurious clinical concepts across all 60 items |
| **Micro Recall** | **0.9818** | 108 / 110 gold concepts recovered |
| **Micro F1 Score** | **0.9908** | Harmonic mean of micro precision and recall |
| **Negation Accuracy** | **10 / 10 (100.0%)** | Zero false-positive conditions from negated assertions |
| **Duration Extraction** | **2 / 2 (100.0%)** | Exact integer day extraction across Devanagari and Romanized numerals |
| **Brand $\rightarrow$ Generic** | **100.0%** | Every matched `drug_brand` resolves to its canonical `drug_generic` parent |

### Error Analysis & Contested Items (`#39` and `#40`)

In accordance with §26–§27 of the Master Documentation (*"Report like a paper, not a pitch. Include the bad numbers."*):
- All matches in the deterministic run (`use_model=False`) come from Tiers 1 and 2 (`model_share = 0.0%`).
- The two non-exact items (`#39` and `#40` in `code_mixed`) are contested shorthand labels where the normalizer abstains (`missed`, zero `spurious`), preserving `1.0000` precision and routing unmatched spans to the uncertainty/confirmation layer rather than guessing.

---

## 3. Research Questions (§28)

1. **RQ1 (Vocabulary Normalization)**: How accurately can messy Nepali clinical expressions be normalized into a controlled clinical vocabulary (`NCL`)?
2. **RQ2 (Tier Ablation)**: How much do Tier 1 exact matching (`LEXICON`), Tier 2 orthography/fuzzy matching (`FUZZY_MATCH`), and Tier 3 constrained model matching (`LLM`) contribute individually?
3. **RQ3 (Negation Preservation)**: How reliably does directional windowing preserve clinical negation across post-positional Nepali (`छैन`, `नभएको`) and pre-positional English (`no`, `without`)?
4. **RQ4 (Brand-to-Generic Linking)**: How accurately can commercial pharmaceutical brands in Nepal (`सिटामोल`, `Glycomet`, `Ecosprin`) be resolved to generic compounds?
5. **RQ5 (Devanagari Clinical OCR)**: How well do open-source vision-language models + lexicon-constrained correction transcribe handwritten or scanned Nepali clinical documents without inventing text?
6. **RQ6 (Clinical ASR Domain Shift)**: How much does general-domain Nepali ASR degrade on spoken clinical assessments (FCHV / patient speech), and how does domain-adaptive fine-tuning affect WER/CER?
7. **RQ7 (Per-Field Uncertainty & Confirmation)**: Does field-level uncertainty estimation (`FieldUncertainty`) catch downstream extraction errors and reduce false-acceptance rates via human confirmation?
8. **RQ8 (Cross-Script Robustness)**: How does extraction performance vary across clean Devanagari, Romanized Nepali, code-mixed Nepali–English, OCR-corrupted text, and speech transcripts?

---

## 4. Paper Plan (§29)

- **Working Title**: *Bodh: Uncertainty-Aware Structured Extraction from Nepali Clinical Language*
- **Contributions**:
  1. **The Nepali Clinical Lexicon (NCL)** — 300-concept open resource (CC-BY-4.0) with Devanagari, Romanized, code-mixed, and Nepal brand-name coverage.
  2. **Lexicon-Grounded Extraction with Per-Field Uncertainty** — 3-tier constrained normalization, provenance logging, and Nepali confirmation prompts.
  3. **NepClinBench** — Multi-category evaluation benchmark and ablation harness (`python -m backend.eval --compare`).
  4. **Empirical Analysis** — Error analysis across orthographic drift, code-mixing, OCR degradation, and ASR confidence propagation.
