"""Tesseract OCR engine wrapper supporting Devanagari and English."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from backend.ocr.base import OcrEngine, OcrResult

logger = logging.getLogger("swasthyasanjaal.ocr.tesseract")


class TesseractEngine(OcrEngine):
    """Local Tesseract 5 engine wrapper executing via subprocess without python wrapper dependencies.

    Gracefully detects availability, checks available language packs (e.g. 'nep', 'eng'),
    and handles printed Nepali (Devanagari) and English text.
    """

    def __init__(self, tesseract_cmd: str = "tesseract") -> None:
        self.cmd = tesseract_cmd
        self._available: Optional[bool] = None
        self._languages: set[str] = set()

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        found = shutil.which(self.cmd) is not None
        if not found:
            self._available = False
            return False

        try:
            res = subprocess.run(
                [self.cmd, "--list-langs"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                langs = set()
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if clean and not clean.startswith("List of") and not clean.endswith(":"):
                        langs.add(clean)
                self._languages = langs
                self._available = True
                return True
        except Exception as exc:
            logger.warning("Tesseract discovery failed: %s", exc)

        self._available = False
        return False

    def available_languages(self) -> set[str]:
        if self._available is None:
            self.is_available()
        return self._languages

    def extract_text(self, image_bytes: bytes, lang: Optional[str] = None) -> Optional[OcrResult]:
        if not self.is_available():
            return None

        # Choose best available language
        selected_lang = "eng"
        if lang and lang in self._languages:
            selected_lang = lang
        elif "nep" in self._languages and "eng" in self._languages:
            selected_lang = "nep+eng"
        elif "nep" in self._languages:
            selected_lang = "nep"
        elif "eng" in self._languages:
            selected_lang = "eng"

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_file = Path(tmp_dir) / "input_doc.png"
            output_base = Path(tmp_dir) / "output"
            input_file.write_bytes(image_bytes)

            try:
                cmd = [
                    self.cmd,
                    str(input_file),
                    str(output_base),
                    "-l",
                    selected_lang,
                    "--oem",
                    "1",  # LSTM engine
                    "--psm",
                    "3",  # Fully automatic page segmentation
                ]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                txt_path = Path(f"{output_base}.txt")
                if txt_path.exists():
                    extracted = txt_path.read_text(encoding="utf-8").strip()
                    if extracted:
                        return OcrResult(
                            text=extracted,
                            confidence=0.88 if selected_lang == "eng" else 0.82,
                            engine_name="tesseract",
                            language=selected_lang,
                        )
            except Exception as exc:
                logger.error("Tesseract execution error: %s", exc)

        return None
