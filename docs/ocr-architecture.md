# OCR Pipeline Architecture & Engine Selection

**Project:** Swasthya Sanjaal (स्वास्थ्य सञ्जाल)  
**Scope:** Document Understanding, Printed & Handwritten Devanagari/Latin Ingestion

---

## 1. Architectural Strategy & Decision Matrix

Swasthya Sanjaal employs a **multi-tiered local fallback pipeline** for extracting clinical text from medical documents (prescriptions, lab reports, doctor notes, and pharmacy slips):

| Tier | Engine / Technology | Modality / Target | Latency | Dependency / Weights | Accuracy (Clinical) |
|---|---|---|---|---|---|
| **Tier 1 (Instant)** | **PyMuPDF (`fitz`)** | Digital PDFs (direct text layer) | < 15ms | In-repo dependency, 0 weights | 99%+ lossless extraction |
| **Tier 2 (Local OCR)** | **Tesseract 5 LSTM** (`eng`, `nep`) | Printed Latin & Devanagari documents | ~200–600ms | Free local binary (`brew install tesseract`), no cloud API | High on printed clinic slips |
| **Tier 3 (Vision LLM)** | **Gemma 4 VLM** (`gemma4:31b` / `e2b-it-qat`) | Handwritten doctor notes & complex layouts | 2–5s | Optional local Ollama or cloud backend | High on handwriting |

---

## 2. Evaluation of Alternatives

### Tesseract 5 vs. PaddleOCR vs. Qwen-VL

1. **Tesseract 5 (Selected for local tier):**
   - **Pros:** Completely open-source, installed locally with zero cloud dependencies or ongoing API charges. High performance on standard printed fonts and Devanagari script (`nep` / Devanagari traineddata). Lightweight, instant startup, and requires no GPU.
   - **Cons:** Struggles on cursive/messy handwritten doctor handwriting. Handled cleanly by escalating unreadable areas `[?]` to the human confirmation gate.

2. **PaddleOCR:**
   - **Evaluation:** High accuracy on Asian character sets, but carries substantial weight dependencies (PaddlePaddle wheel ~500MB+), complex C++ compilation on macOS ARM, and lack of pre-bundled Nepali clinical models without extensive fine-tuning.

3. **Qwen-VL / Gemma 4 VLM:**
   - **Evaluation:** Excellent document layout analysis and handwritten prescription transcription. Implemented as an **optional, non-blocking fallback tier** via Ollama. If model weights are not present or Ollama is offline, the pipeline degrades gracefully to Tesseract or signals `engine_unavailable` without crashing the application.

---

## 3. Human-Confirmation Gate & Safety Guarantees

In accordance with Swasthya Sanjaal's clinical safety principles:
- **Approval-Before-Write:** Neither OCR nor Vision extraction ever mutates the database directly. All extracted text is staged into an approval buffer (`intake -> normalize -> human confirmation -> commit`).
- **Uncertainty Propagation:** Unreadable regions in physical slips are tagged with `[?]`, forcing clinician or patient review prior to inclusion in the health timeline.
- **Fail-Closed on Audio:** Voice intake strictly rejects ungrounded transcription if an audio waveform pipeline is unavailable.
