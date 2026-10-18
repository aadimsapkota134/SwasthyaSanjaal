# 01 — Research Dossier: Nepali Clinical Language & Multimodal Health Records

## 1. The Nepali Clinical NLP Gap

### 1.1 Existing Nepali NLP Resources

| Resource | Year | Architecture / Scale | Corpus Domain |
|---|---|---|---|
| **NepBERTa** (AACL 2022) | 2022 | BERT, 0.8B words | 36 news sites |
| **IRIISNEPAL Nepali-Text-Corpus** | 2024 | 6.4M articles, 10.1 GB | 99 news websites |
| **NepaliGPT** | 2025 | GPT-2 arch, 10.75 GB, custom 16k BPE | News |
| **NepaliBERT** | 2023 | Masked LM | News |
| **NPVec1** | 2021 | 25 embedding sets — GloVe, Word2Vec, fastText, BERT | General |
| **Nep-gLUE / NLUE** | 2022– | Benchmarks: sentiment, hate speech, toxicity, QA, NER | General |
| **FLORES-101** | 2021 | MT eval, 101 languages incl. Nepali | General |
| **IndicBench** | 2024 | 11 Indic languages, 13 tasks | General |
| **RoundTripOCR** (arXiv 2412.15248) | 2024 | Post-OCR correction, 2.97M Nepali sentences | General OCR errors |

**Core Finding:** Every existing Nepali NLP corpus and benchmark is news-domain or general-purpose. Prior to **SwasthyaSanjaal**, no open Nepali clinical lexicon or medical normalization benchmark existed to bridge spoken/written Nepali patient expressions (`पेट पोल्ने`, `वाकवाकी`, `रिंगटा लाग्ने`, `pet dukhyo`, `khoki chha tara jwaro chaina`) to WHO ICD-11/ICD-10 and HL7 FHIR R4.

### 1.2 Linguistic Scope & Canonicalization Policy

Nepali (32–40M speakers, Devanagari script) is the official working language of Nepal under Article 7(1) of the Constitution. In clinical encounters across Nepal—from rural Female Community Health Volunteer (FCHV / महिला स्वास्थ्य स्वयंसेविका) assessments to tertiary hospital OPD desks—clinical language exhibits four distinct phenomena:

1. **Register Split (Colloquial vs. Literary/Sanskritized):**
   - A patient says `दम` (*dam*), whereas formal literature writes `श्वासप्रश्वास रोग` (Asthma / COPD).
   - A patient says `उच्च रक्तचाप` or `प्रेसर बढेको`, whereas discharge notes write `HTN`.
   - **Policy:** Both registers are indexed in the **Nepali Clinical Lexicon (NCL)** under a single concept ID (`NCL-xxxx`), with `preferred_register: "colloquial"` or `"literary"` explicitly recorded.
2. **Devanagari Orthographic Drift:**
   - Zero-width joiners (`\u200c`, `\u200d`), nukta variations, चंद्रबिन्दु vs. अनुस्वार (`ँ` $\rightarrow$ `ं`), दीर्घ vs. ह्रस्व vowels (`ई` $\rightarrow$ `इ`, `ऊ` $\rightarrow$ `उ`), and `व`/`ब` or `श`/`ष`/`स` substitutions occur constantly in both human typing and OCR output.
3. **Informal Romanized & Code-Mixed Clinical Shorthand:**
   - Prescriptions and SMS notes routinely mix Devanagari, Romanized Nepali, and English medical abbreviations (`Tab Sitamol 500mg दिनको २ पटक, jwaro chaina`).
4. **Local Pharmaceutical Brand Dominance:**
   - Prescriptions in Nepal are written predominantly by brand name (`सिटामोल` / `Niko` / `Cetamol` for Paracetamol; `ग्लाइकोमेट` for Metformin; `एमलोवास्क` for Amlodipine). Clinical safety and WHO interoperability require resolving every `drug_brand` concept to its canonical `drug_generic` parent (`generic_of`).

---

## 2. Empirical Evidence on Devanagari Clinical OCR

Recent stress-testing of Vision-Language Models on real printed Devanagari scans (*Can OCR-VLMs Read Devanagari?*, arXiv 2606.29213) establishes four engineering constraints that directly shape SwasthyaSanjaal's document pipeline:

1. **Digital PDFs must bypass OCR entirely:** A substantial fraction of laboratory reports and hospital bills are born-digital PDFs. Extracting their text layer via **PyMuPDF (`fitz`)** is instantaneous, deterministic, and immune to VLM hallucination.
2. **Unconstrained OCR post-correction does not transfer:** Generic seq2seq post-correctors overfit to a single OCR engine's error distribution and risk inventing clinical terms. Instead, SwasthyaSanjaal uses a **lexicon-constrained Levenshtein spell corrector** (`backend/nlp/correct.py`) that only repairs tokens within a strict edit-distance budget ($\le 1$ for tokens of length 4–6, $\le 2$ for length $\ge 7$) when a unique lexicon entry wins.
3. **Illegible spans must be marked `[?]`, never guessed:** Vision OCR prompts (`backend/prompts/ocr_extract.txt`) instruct Gemma 4 to emit `[?]` for any illegible handwriting or smudged dosage rather than guessing a medication name or strength.
4. **Document classification must be text-derived:** Document class (`prescription`, `lab_report`, `bill`, `note`, `fchv_assessment`) is inferred deterministically from extracted cue patterns (`backend/intake/documents.py`).

---

## 3. Speech Pipeline & Acoustic Uncertainty in Community Health

In Nepal's primary care ecosystem, over 52,000 Female Community Health Volunteers (FCHVs) conduct maternal, neonatal, and community health visits. Spoken symptom reporting introduces two safety hazards:

1. **Acoustic Ambiguity:** Low-SNR audio or dialect variation can cause ASR systems to misrecognize durations, severities, or drug names. SwasthyaSanjaal's **Nepali Speech Pipeline** (`POST /api/v1/intake/speech`) propagates `asr_confidence` directly into concept and modifier confidence scores, emitting structured `FieldUncertainty` records and forcing `confirmation_required = True` whenever confidence falls below `0.85`.
2. **Fail-Closed Raw Audio Gate:** When running against an inference backend whose HTTP API lacks an audio waveform channel (such as standard Ollama `/api/generate`), sending a text-only transcription prompt would cause the LLM to invent a plausible Nepali clinical monologue. SwasthyaSanjaal enforces a strict fail-closed gate (`AUDIO_INPUT_SUPPORTED = False` in `backend/ai/engine.py`) so raw audio uploads return `extraction_status = "engine_unavailable"` with `confirmation_required = True` and zero fabricated transcript tokens.
