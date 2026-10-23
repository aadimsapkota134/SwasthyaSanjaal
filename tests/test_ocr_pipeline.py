from __future__ import annotations

import io
from PIL import Image, ImageDraw
import pytest

from backend.intake.pipeline import (
    METHOD_DIRECT,
    METHOD_PYMUPDF,
    METHOD_TESSERACT,
    METHOD_UNAVAILABLE,
    STATUS_ENGINE_UNAVAILABLE,
    STATUS_OK,
    Upload,
    collect,
    run_intake,
)
from backend.ocr.router import OcrRouter
from backend.ocr.tesseract_engine import TesseractEngine


def _make_sample_image(text: str = "Paracetamol 500mg") -> bytes:
    """Generate a clean test image with rendered text."""
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 35), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_tesseract_engine_availability():
    engine = TesseractEngine()
    # If tesseract is installed in local environment, it should report True
    avail = engine.is_available()
    assert isinstance(avail, bool)


def test_tesseract_extracts_printed_image():
    engine = TesseractEngine()
    if not engine.is_available():
        pytest.skip("Tesseract binary not installed on machine")

    image_bytes = _make_sample_image("Paracetamol 500mg")
    res = engine.extract_text(image_bytes)
    assert res is not None
    assert "paracetamol" in res.text.lower() or "500" in res.text
    assert res.engine_name == "tesseract"


def test_pipeline_uses_tesseract_for_image_upload():
    image_bytes = _make_sample_image("Paracetamol 500mg")
    upload = Upload(data=image_bytes, mime_type="image/png", filename="rx.png")

    events = list(run_intake(upload=upload, use_model=False))
    result = collect(iter(events))

    engine = TesseractEngine()
    if engine.is_available():
        assert result.extraction_method == METHOD_TESSERACT
        assert result.extraction_status == STATUS_OK
    else:
        assert result.extraction_method == METHOD_UNAVAILABLE
        assert result.extraction_status == STATUS_ENGINE_UNAVAILABLE


def test_pipeline_graceful_degradation_without_models():
    """Verify system does not crash or stall when no models are downloaded."""
    # Blank/unreadable image without AI model
    blank_img = Image.new("RGB", (10, 10), color=(255, 255, 255))
    buf = io.BytesIO()
    blank_img.save(buf, format="PNG")

    upload = Upload(data=buf.getvalue(), mime_type="image/png", filename="blank.png")
    events = list(run_intake(upload=upload, use_model=False))
    result = collect(iter(events))
    assert result.extraction_status in {STATUS_OK, STATUS_ENGINE_UNAVAILABLE}
