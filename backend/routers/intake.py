from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from backend.auth.router import require_auth
from backend.db import session as db_session
from backend.intake.documents import (
    CLASS_BILL,
    CLASS_FCHV_ASSESSMENT,
    CLASS_LAB_REPORT,
    CLASS_NOTE,
    CLASS_PRESCRIPTION,
)
from backend.intake.pipeline import (
    IntakeEvent,
    IntakeResult,
    Upload,
    collect,
    run_intake,
    run_speech_intake,
)
from backend.nlp.lexicon import get_lexicon
from backend.nlp.normalize import normalize
from backend.schemas import (
    IntakeRequest,
    IntakeResponse,
    NormalizeRequest,
    NormalizeResponse,
    SpeechIntakeRequest,
)

router = APIRouter(tags=["intake"])

logger = logging.getLogger("swasthyasanjaal.intake")

DOCUMENT_CLASSES = {
    CLASS_PRESCRIPTION,
    CLASS_LAB_REPORT,
    CLASS_BILL,
    CLASS_NOTE,
    CLASS_FCHV_ASSESSMENT,
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024
SIZE_EXCEEDED_DETAIL = f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
MAX_TEXT_CHARS = 20000


def _validate_hint(hint: str | None) -> str | None:
    if hint is None or hint == "":
        return None
    if hint not in DOCUMENT_CLASSES:
        raise HTTPException(
            status_code=422,
            detail=f"document_class must be one of {sorted(DOCUMENT_CLASSES)}",
        )
    return hint


async def _read_upload(file: UploadFile) -> Upload:
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=SIZE_EXCEEDED_DETAIL)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=SIZE_EXCEEDED_DETAIL)
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    return Upload(
        data=data,
        mime_type=file.content_type or "application/octet-stream",
        filename=file.filename,
    )


def _respond(result: IntakeResult) -> IntakeResponse:
    return result.to_response(get_lexicon())


@router.post("/intake/text", response_model=IntakeResponse)
def intake_text(
    payload: IntakeRequest,
    current_user: dict = Depends(require_auth),
) -> IntakeResponse:
    """Direct clinical text intake with lexicon-constrained correction and 3-tier normalization."""
    return _respond(
        collect(
            run_intake(
                text=payload.text,
                use_model=payload.use_model,
                apply_correction=payload.correct,
            )
        )
    )


@router.post("/intake/speech", response_model=IntakeResponse)
def intake_speech(
    payload: SpeechIntakeRequest,
    current_user: dict = Depends(require_auth),
) -> IntakeResponse:
    """Nepali Speech Pipeline: processes spoken FCHV or patient ASR transcripts with acoustic uncertainty propagation."""
    return _respond(
        run_speech_intake(
            transcript=payload.transcript,
            asr_confidence=payload.asr_confidence,
            speaker_role=payload.speaker_role,
            use_model=payload.use_model,
            apply_correction=payload.correct,
        )
    )


@router.post("/intake/voice", response_model=IntakeResponse)
async def intake_voice(
    file: UploadFile = File(...),
    use_model: bool = Form(default=True),
    correct: bool = Form(default=True),
    current_user: dict = Depends(require_auth),
) -> IntakeResponse:
    """Raw audio upload intake: fails closed with explicit clinical warning when backend lacks audio waveform API."""
    upload = await _read_upload(file)
    return _respond(
        collect(
            run_intake(
                upload=upload,
                use_model=use_model,
                apply_correction=correct,
            )
        )
    )


@router.post("/intake/ocr", response_model=IntakeResponse)
async def intake_ocr(
    file: UploadFile = File(...),
    document_class: str | None = Form(default=None),
    use_model: bool = Form(default=True),
    correct: bool = Form(default=True),
    current_user: dict = Depends(require_auth),
) -> IntakeResponse:
    """Document intake: digital PDFs are extracted via PyMuPDF instantly; images are processed via vision OCR."""
    upload = await _read_upload(file)
    return _respond(
        collect(
            run_intake(
                upload=upload,
                document_class_hint=_validate_hint(document_class),
                use_model=use_model,
                apply_correction=correct,
            )
        )
    )


def _sse(events: Iterator[IntakeEvent]) -> Iterator[str]:
    """Serialize intake events as SSE frames."""
    try:
        lexicon = get_lexicon()
        for event in events:
            if isinstance(event.data, IntakeResult):
                body = event.data.to_response(lexicon).model_dump()
            else:
                body = event.data
            yield f"event: {event.name}\ndata: {json.dumps({'event': event.name, 'data': body}, ensure_ascii=False)}\n\n"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Intake stream aborted by pipeline error")
        error_body = {"event": "error", "data": {"error": type(exc).__name__, "detail": str(exc)}}
        yield f"event: error\ndata: {json.dumps(error_body, ensure_ascii=False)}\n\n"
    finally:
        closer = getattr(events, "close", None)
        if callable(closer):
            closer()


@router.post("/intake/stream")
async def intake_stream(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    document_class: str | None = Form(default=None),
    use_model: bool = Form(default=True),
    correct: bool = Form(default=True),
    current_user: dict = Depends(require_auth),
) -> StreamingResponse:
    """Streamed intake returning Server-Sent Events (SSE) across extraction, correction, and normalization."""
    if file is None and not (text or "").strip():
        raise HTTPException(status_code=422, detail="Provide either an uploaded file or text.")
    if text is not None and len(text) > MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"text must be at most {MAX_TEXT_CHARS} characters",
        )

    upload = await _read_upload(file) if file is not None else None
    events = run_intake(
        upload=upload,
        text=text,
        document_class_hint=_validate_hint(document_class),
        use_model=use_model,
        apply_correction=correct,
    )
    return StreamingResponse(
        _sse(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/intake/normalize", response_model=NormalizeResponse)
def direct_normalize(
    payload: NormalizeRequest,
    current_user: dict = Depends(require_auth),
) -> NormalizeResponse:
    """Direct 3-tier normalization endpoint."""
    from backend.nlp.tier3 import GemmaTier3Matcher
    tier3_matcher = GemmaTier3Matcher() if payload.use_model else None
    result = normalize(payload.text, tier3=tier3_matcher)
    return NormalizeResponse.from_result(result, get_lexicon())


@router.get("/lexicon")
def list_lexicon_concepts(
    current_user: dict = Depends(require_auth),
    concept_type: str | None = Query(default=None, description="Filter by concept_type"),
    q: str | None = Query(default=None, description="Search query across Devanagari, Romanized, or English"),
) -> dict[str, Any]:
    """Inspect the 300-concept Nepali Clinical Lexicon (NCL)."""
    lexicon = get_lexicon()
    concepts = list(lexicon.concepts.values())
    if concept_type:
        concepts = [c for c in concepts if c.concept_type == concept_type]
    if q:
        needle = q.strip().casefold()
        concepts = [
            c
            for c in concepts
            if needle in c.concept_id.casefold()
            or needle in c.canonical_en.casefold()
            or needle in c.canonical_np.casefold()
            or any(needle in a.casefold() for a in c.devanagari_aliases)
            or any(needle in a.casefold() for a in c.romanized_aliases)
        ]
    return {
        "total": len(concepts),
        "concepts": [
            {
                "concept_id": c.concept_id,
                "canonical_en": c.canonical_en,
                "canonical_np": c.canonical_np,
                "concept_type": c.concept_type,
                "devanagari_aliases": list(c.devanagari_aliases),
                "romanized_aliases": list(c.romanized_aliases),
                "generic_of": c.generic_of,
                "icd11_code": c.icd11_code,
                "icd10_code": c.icd10_code,
                "negation_sensitive": c.negation_sensitive,
            }
            for c in concepts
        ],
    }
