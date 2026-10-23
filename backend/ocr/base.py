"""Base contract and registry for OCR engines in Swasthya Sanjaal."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    confidence: float
    engine_name: str
    language: str
    is_fallback: bool = False


class OcrEngine(ABC):
    """Abstract interface for local OCR engines."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if system dependencies (binaries, libraries) are present."""
        ...

    @abstractmethod
    def extract_text(self, image_bytes: bytes, lang: Optional[str] = None) -> Optional[OcrResult]:
        """Extract plain text from image bytes. Return None if unable or empty."""
        ...
