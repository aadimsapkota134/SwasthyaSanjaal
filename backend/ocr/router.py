"""OCR Router coordinating multi-engine fallback for printed and handwritten clinical records.

Hierarchy:
1. PyMuPDF: Digital PDF text layer (instant, lossless, 0 model weights)
2. Tesseract 5: Printed Latin/Devanagari document OCR (free local binary, zero cloud dependency)
3. Gemma4 VLM: Complex visual layout / handwritten prescriptions (Ollama edge or cloud, optional)
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.ocr.base import OcrResult
from backend.ocr.pymupdf_engine import PyMuPdfEngine
from backend.ocr.tesseract_engine import TesseractEngine

logger = logging.getLogger("swasthyasanjaal.ocr.router")


class OcrRouter:
    """Dispatches document extraction across available local engines."""

    def __init__(self) -> None:
        self.pymupdf = PyMuPdfEngine()
        self.tesseract = TesseractEngine()

    def extract_image(self, image_bytes: bytes, lang: Optional[str] = None) -> Optional[OcrResult]:
        """Attempt OCR on an image raster using local engines."""
        # Tier 1 for images: Tesseract
        if self.tesseract.is_available():
            res = self.tesseract.extract_text(image_bytes, lang=lang)
            if res and res.text:
                return res
        return None

    def extract_pdf(self, pdf_bytes: bytes) -> Optional[OcrResult]:
        """Attempt extraction on a PDF using digital layer."""
        if self.pymupdf.is_available():
            res = self.pymupdf.extract_text(pdf_bytes)
            if res and res.text:
                return res
        return None
