"""PyMuPDF digital text extractor conforming to OcrEngine interface."""

from __future__ import annotations

from typing import Optional
from backend.intake.documents import extract_pdf_text
from backend.ocr.base import OcrEngine, OcrResult


class PyMuPdfEngine(OcrEngine):
    """Zero-model, high-fidelity digital PDF text extraction."""

    def is_available(self) -> bool:
        try:
            import fitz
            return True
        except ImportError:
            return False

    def extract_text(self, pdf_bytes: bytes, lang: Optional[str] = None) -> Optional[OcrResult]:
        if not self.is_available():
            return None
        try:
            pdf = extract_pdf_text(pdf_bytes)
            if pdf.is_digital and pdf.text.strip():
                return OcrResult(
                    text=pdf.text.strip(),
                    confidence=0.99,
                    engine_name="pymupdf",
                    language="mul",
                )
        except Exception:
            pass
        return None
