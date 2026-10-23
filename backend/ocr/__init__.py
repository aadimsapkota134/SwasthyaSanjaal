"""OCR package exports."""

from backend.ocr.base import OcrEngine, OcrResult
from backend.ocr.pymupdf_engine import PyMuPdfEngine
from backend.ocr.router import OcrRouter
from backend.ocr.tesseract_engine import TesseractEngine

__all__ = [
    "OcrEngine",
    "OcrResult",
    "PyMuPdfEngine",
    "TesseractEngine",
    "OcrRouter",
]
