# 05 — AI Engine, Multimodal Serving & Versioned Clinical Prompts

> **Companion to [`docs/00-MASTER-DOCUMENTATION.md`](00-MASTER-DOCUMENTATION.md) (§10, §20–§21) and `backend/ai/`.**

---

## 1. Dual-Tier Gemma 4 Serving Architecture (`backend/config.py`, `backend/ai/engine.py`)

**SwasthyaSanjaal** uses a single open-source model family (**Google Gemma 4**) resolved across two backends at startup:

| Property | Cloud Backend | Local / Edge Backend |
|---|---|---|
| **Base URL** | `https://ollama.com` | `http://localhost:11434` |
| **Default Model Tag** | `gemma4:31b-cloud` | `gemma4:e2b-it-qat` (4.3 GB QAT) |
| **Auth Header** | `Authorization: Bearer <OLLAMA_API_KEY>` | `{}` (Never sent to localhost) |
| **Selected When** | `OLLAMA_API_KEY` is set in `.env` | `MODEL_BACKEND=local` or no cloud key set |
| **Automatic Fallback** | Falls back to `localhost:11434` (`gemma4:e2b-it-qat`) on timeout/offline | Deterministic Tiers 1 & 2 continue offline |

### Security Invariants
- `settings.model_headers` returns `{}` unless `resolved_backend == "cloud"`. The cloud API key is never transmitted to `localhost`.
- If both cloud and local model endpoints are unreachable, the deterministic language layer (Tier 1 `LEXICON` + Tier 2 `FUZZY_MATCH` + PyMuPDF digital PDF extraction) continues operating at `100%` availability.

---

## 2. Fail-Closed Audio Safety Gate (`AUDIO_INPUT_SUPPORTED = False`)

While the Gemma 4 model architecture natively supports audio, standard Ollama HTTP endpoints (`/api/generate` and `/api/chat`) do **not** accept an audio waveform field. Sending a speech transcription prompt without an attached waveform causes an LLM to hallucinate fluent, plausible, completely ungrounded Nepali clinical complaints.

To prevent fabricated speech from ever entering a health record:
- `AUDIO_INPUT_SUPPORTED = False` in `backend/ai/engine.py`.
- `GemmaEngine.transcribe_audio()` returns `None` immediately without issuing an HTTP request.
- Raw audio uploads (`POST /api/v1/intake/voice`) fail closed with `extraction_status = "engine_unavailable"`, `confirmation_required = True`, and a bilingual warning note.
- Spoken assessments enter via the **Nepali Speech Pipeline** (`POST /api/v1/intake/speech`), which accepts ASR transcripts along with `asr_confidence` (`0.0`–`1.0`) and propagates acoustic uncertainty to every extracted field.

---

## 3. Versioned Production Prompts (`backend/prompts/`)

All prompts live in versioned `.txt` files under `backend/prompts/` and are loaded via `backend/ai/prompts.py`.

### 3.1 Vision OCR Transcription (`backend/prompts/ocr_extract.txt`)
Extracts raw Devanagari and English text from photographed prescriptions and scanned laboratory reports at `temperature = 0.0`.
- **Key Guardrail**: Instructs the VLM to preserve original script, never translate or guess diagnoses, and mark any illegible handwriting or smudged dosage as `[?]`. Any `[?]` token automatically triggers a clinical warning note and sets `confirmation_required = True`.

### 3.2 Tier 3 Shortlist-Constrained Matcher (`backend/prompts/tier3_disambiguate.txt`)
Invoked by `GemmaTier3Matcher` (`backend/nlp/tier3.py`) only on residual 1–3 token spans that were not resolved by Tier 1 (`LEXICON`) or Tier 2 (`FUZZY_MATCH`).
- **Key Guardrail**: Receives the top-12 lexicon candidates ranked by `rapidfuzz.fuzz.WRatio`. Must return a JSON object whose `concept_id` is either in the candidate shortlist or `"UNKNOWN"`. `GemmaTier3Matcher` validates the returned ID against `allowed_ids` in Python—any out-of-shortlist ID is discarded.

### 3.3 Spoken Nepali ASR Prompt (`backend/prompts/asr_transcribe.txt`)
Prompt template for multimodal endpoints that support native audio input (`input_audio`), emphasizing strict preservation of Nepali negation markers (`छैन`, `होइन`, `बिना`, `दुख्दैन`), spoken numbers, and durations.

### 3.4 Unconstrained Ablation Baseline (`backend/prompts/baseline_extract.txt`)
Used exclusively by `backend/eval/baseline.py` (`python -m backend.eval --compare`) to measure how raw, unconstrained Gemma 4 performs without the Nepali Clinical Lexicon.

### 3.5 Plain-Nepali Patient Explanation (`backend/prompts/meaning_np.txt`)
Generates a compassionate, source-grounded plain-Nepali explanation of the confirmed clinical concepts without adding unstated diagnoses or medical advice.
