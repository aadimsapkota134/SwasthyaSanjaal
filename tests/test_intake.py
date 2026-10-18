import fitz
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_intake_text_direct(client):
    payload = {
        "text": "टाइफाइड ज्वरोको लागि प्यारासिटामोल ५०० एमजी दिनको दुई पटक",
        "use_model": False,
        "correct": True,
    }
    response = client.post("/api/v1/intake/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "text"
    assert data["extraction_method"] == "direct"
    assert data["extraction_status"] == "ok"
    assert data["raw_transcript"] == payload["text"]
    assert data["normalized"] is not None
    concepts = data["normalized"]["concepts"]
    assert len(concepts) >= 2
    concept_ids = {c["concept_id"] for c in concepts}
    assert "NCL-0088" in concept_ids or "NCL-0001" in concept_ids or "NCL-0058" in concept_ids
    for c in concepts:
        assert c["resolution_method"] in {"LEXICON", "FUZZY_MATCH", "LLM"}


def test_intake_speech_pipeline_and_uncertainty(client):
    """Nepali Speech Pipeline: spoken FCHV assessment with low ASR confidence propagates uncertainty."""
    payload = {
        "transcript": "३ दिनदेखि ज्वरो र खोकी छ, सिटामोल ५०० एमजी दिनुभएको छ",
        "asr_confidence": 0.65,
        "speaker_role": "fchv",
        "use_model": False,
        "correct": True,
    }
    response = client.post("/api/v1/intake/speech", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "voice"
    assert data["extraction_method"] == "asr_transcript"
    assert data["extraction_status"] == "ok"
    assert data["document_class"] == "fchv_assessment"
    assert data["asr_confidence"] == 0.65
    assert data["confirmation_required"] is True
    assert len(data["field_uncertainties"]) >= 1
    assert any(u["confirmation_required"] for u in data["field_uncertainties"])


def test_intake_voice_raw_audio_fails_closed(client):
    """Uploading raw audio waveform fails closed when backend lacks audio waveform API."""
    files = {"file": ("recording.wav", b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/wav")}
    response = client.post("/api/v1/intake/voice", files=files, data={"use_model": "false"})
    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "voice"
    assert data["extraction_status"] in {"engine_unavailable", "unsupported"}
    assert data["confirmation_required"] is True
    assert any(n["level"] == "warning" for n in data["notes"])


def test_lexicon_inspection_endpoint(client):
    response = client.get("/api/v1/lexicon?concept_type=drug_brand&q=सिटामोल")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(c["generic_of"] == "NCL-0088" for c in data["concepts"])


def test_intake_normalize_direct(client):
    payload = {
        "text": "खोकी छ तर ज्वरो छैन",
        "use_model": False,
    }
    response = client.post("/api/v1/intake/normalize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "concepts" in data
    fever = next((c for c in data["concepts"] if c["concept_id"] == "NCL-0001"), None)
    if fever:
        assert fever["negated"] is True


def test_intake_pdf_digital(client):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        fitz.Point(50, 72),
        "Rx: Tab Paracetamol 500mg bd. Patient reports high fever and cough. Follow up in 3 days.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    files = {"file": ("prescription_test.pdf", pdf_bytes, "application/pdf")}
    data = {"use_model": "false", "correct": "true"}

    response = client.post("/api/v1/intake/ocr", files=files, data=data)
    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data["input_type"] == "pdf"
    assert resp_data["extraction_method"] == "pymupdf"
    assert resp_data["extraction_status"] == "ok"
    assert resp_data["document_class"] == "prescription"
    assert resp_data["normalized"] is not None
    assert len(resp_data["normalized"]["concepts"]) >= 1


def test_intake_malformed_pdf_reports_unsupported(client):
    """Corrupted PDF bytes must report 'unsupported', not falsely claim the AI engine is down."""
    garbage = b"%PDF-1.4 " + b"\x00garbage-bytes" * 200

    response = client.post(
        "/api/v1/intake/ocr",
        files={"file": ("corrupt.pdf", garbage, "application/pdf")},
        data={"use_model": "false", "correct": "true"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "pdf"
    assert data["extraction_status"] == "unsupported"
    assert data["extraction_method"] == "unavailable"
    assert data["raw_transcript"] == ""
    assert data["normalized"] is None
    assert any(n["level"] == "error" for n in data["notes"])


def test_upload_too_large_returns_413(client, monkeypatch):
    monkeypatch.setattr("backend.routers.intake.MAX_UPLOAD_BYTES", 1024)
    payload = b"%PDF-1.4 " + b"A" * 4096

    response = client.post(
        "/api/v1/intake/ocr",
        files={"file": ("big.pdf", payload, "application/pdf")},
        data={"use_model": "false"},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]


def test_empty_upload_returns_422(client):
    response = client.post(
        "/api/v1/intake/ocr",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"use_model": "false"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Uploaded file is empty."


def test_oversized_content_length_rejected_before_parsing(client, monkeypatch):
    monkeypatch.setattr("backend.main.REQUEST_BODY_LIMIT_BYTES", 10)

    response = client.post(
        "/api/v1/intake/text",
        json={"text": "ज्वरो आएको छ", "use_model": False},
        headers={"origin": "http://localhost:3000"},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]
    assert response.headers.get("access-control-allow-origin") in {
        "http://localhost:3000",
        "*",
    }


def test_intake_stream_rejects_oversized_text(client):
    response = client.post(
        "/api/v1/intake/stream",
        data={"text": "ज्वरो " * 5000, "use_model": "false"},
    )
    assert response.status_code == 422
    assert "20000" in response.json()["detail"]


def test_intake_image_offline_resilience(client):
    dummy_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
        b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("rx_test.png", dummy_png, "image/png")}
    data = {"use_model": "true", "correct": "true"}

    response = client.post("/api/v1/intake/ocr", files=files, data=data)
    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data["input_type"] == "image"
    assert resp_data["extraction_status"] in {"ok", "engine_unavailable"}
    if resp_data["extraction_status"] == "engine_unavailable":
        assert len(resp_data["notes"]) >= 1


def test_intake_stream(client):
    form_data = {
        "text": "ज्वरो आएको छ",
        "use_model": "false",
        "correct": "true",
    }
    response = client.post("/api/v1/intake/stream", data=form_data)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    content = response.text
    assert "event: routing" in content
    assert "event: done" in content


def test_sse_closes_upstream_on_consumer_close():
    from backend.routers.intake import _sse
    from backend.intake.pipeline import IntakeEvent

    closed: list[bool] = []

    def upstream():
        try:
            yield IntakeEvent("routing", {"input_type": "text"})
            yield IntakeEvent("extracting", {"stage": "extracting", "input_type": "text"})
        finally:
            closed.append(True)

    stream = _sse(upstream())
    first = next(stream)
    assert "event: routing" in first
    stream.close()
    assert closed == [True]


def test_sse_emits_error_event_when_upstream_raises():
    from backend.routers.intake import _sse
    from backend.intake.pipeline import IntakeEvent

    def upstream():
        yield IntakeEvent("routing", {"input_type": "text"})
        raise RuntimeError("pipeline exploded")

    frames = list(_sse(upstream()))
    assert len(frames) == 2
    assert "event: routing" in frames[0]
    assert "event: error" in frames[1]
    assert "pipeline exploded" in frames[1]
    assert "event: done" not in "".join(frames)


def test_intake_stream_emits_error_event_on_storage_failure(client, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("simulated storage failure")

    monkeypatch.setattr("backend.intake.pipeline.save_upload", boom)

    dummy_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
        b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response = client.post(
        "/api/v1/intake/stream",
        files={"file": ("rx_test.png", dummy_png, "image/png")},
        data={"use_model": "false", "correct": "true"},
    )
    assert response.status_code == 200
    content = response.text
    assert "event: routing" in content
    assert "event: error" in content
    assert "simulated storage failure" in content
    assert "event: done" not in content
