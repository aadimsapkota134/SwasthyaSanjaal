"""Tier 3 — Constrained AI concept matching against clinical lexicon candidates."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from backend.config import settings
from backend.nlp.lexicon import Concept

UNKNOWN = "UNKNOWN"
TIER3_CONFIDENCE = 0.70
REQUEST_TIMEOUT_SECONDS = 30.0

_CONCEPT_ID = re.compile(r"NCL-\d{4}")
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "tier3_match.txt"

_DEFAULT_TIER3_PROMPT = """Match this Nepali clinical term to ONE concept from the candidate list.

TERM:
{term}

CANDIDATES (concept_id, Nepali, English, type):
{candidates}

Rules:
- Return a `concept_id` from the candidate list, or `UNKNOWN`.
- Never invent a concept ID.
- If the term is ambiguous, prefer the patient-register concept.
- Keep reasoning brief and factual.

Return JSON only:
{"concept_id":"NCL-#### or UNKNOWN","confidence":0.0,"reasoning":"..."}"""


def _load_tier3_prompt() -> str:
    if _PROMPT_PATH.is_file():
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    return _DEFAULT_TIER3_PROMPT


@dataclass(frozen=True, slots=True)
class Tier3Decision:
    concept_id: str
    confidence: float
    reasoning: str | None = None


class Tier3Matcher(Protocol):
    def match(self, span: str, candidates: list[Concept]) -> Tier3Decision | None: ...


def render_prompt(span: str, candidates: list[Concept]) -> str:
    """Renders versioned tier3_match prompt with phrase and candidate concepts."""
    candidate_list = [
        {
            "concept_id": c.concept_id,
            "canonical_np": c.canonical_np,
            "canonical_en": c.canonical_en,
            "concept_type": c.concept_type,
        }
        for c in candidates
    ]
    candidate_json = json.dumps(candidate_list, ensure_ascii=False, indent=2)
    template = _load_tier3_prompt()
    return (
        template
        .replace("{phrase}", span)
        .replace("{term}", span)
        .replace("{candidate_json_list}", candidate_json)
        .replace("{candidates}", candidate_json)
    )


def parse_response(raw: str, candidates: list[Concept]) -> Tier3Decision | None:
    """Parses model response strictly ensuring returned concept is in candidate list."""
    text = raw.strip()
    if not text:
        return None

    allowed_ids = {c.concept_id for c in candidates}
    reasoning: str | None = None
    concept_id: str | None = None

    fenced = re.search(r"\{.*\}", text, re.DOTALL)
    if fenced:
        try:
            payload = json.loads(fenced.group())
            if isinstance(payload, dict):
                value = str(payload.get("concept_id", "")).strip()
                reasoning = payload.get("reasoning")
                if value == UNKNOWN:
                    return None
                if value in allowed_ids:
                    concept_id = value
        except Exception:
            pass

    if concept_id is None:
        if UNKNOWN in text and not _CONCEPT_ID.search(text):
            return None
        found = _CONCEPT_ID.findall(text)
        for cand in found:
            if cand in allowed_ids:
                concept_id = cand
                break

    if concept_id:
        return Tier3Decision(concept_id=concept_id, confidence=TIER3_CONFIDENCE, reasoning=reasoning)
    return None


class GemmaTier3Matcher:
    """Tier 3 matcher backed by Gemma 4 with local and cloud fallback support."""

    def __init__(self, client: httpx.Client | None = None, model: str | None = None) -> None:
        self._client = client
        self._model = model or settings.active_model_name

    def match(self, span: str, candidates: list[Concept]) -> Tier3Decision | None:
        if not candidates:
            return None
        prompt = render_prompt(span, candidates)

        url = f"{settings.model_base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0},
        }

        try:
            if self._client:
                res = self._client.post(url, json=payload, headers=settings.model_headers, timeout=REQUEST_TIMEOUT_SECONDS)
                if res.status_code == 200:
                    data = res.json()
                    return parse_response(data.get("response", ""), candidates)
            else:
                with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    res = client.post(url, json=payload, headers=settings.model_headers)
                    if res.status_code == 200:
                        data = res.json()
                        return parse_response(data.get("response", ""), candidates)
        except Exception:
            pass

        # Edge fallback: Try local Ollama with gemma4:e2b-it-qat if cloud was primary and failed
        if settings.resolved_backend == "cloud":
            try:
                local_url = f"{settings.ollama_url.rstrip('/')}/api/generate"
                local_payload = {
                    "model": settings.fallback_model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0},
                }
                with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    res = client.post(local_url, json=local_payload)
                    if res.status_code == 200:
                        data = res.json()
                        return parse_response(data.get("response", ""), candidates)
            except Exception:
                pass

        return None
