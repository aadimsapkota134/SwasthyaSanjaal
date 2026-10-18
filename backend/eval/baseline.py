"""The ablation: Raw Gemma doing extraction without the clinical lexicon.

Used by `python -m backend.eval --compare` to prove the advantage of the
curated lexicon over raw unconstrained LLM inference.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx
from rapidfuzz import fuzz

from backend.config import settings
from backend.nlp.devanagari import fold_orthography, prepare
from backend.nlp.lexicon import Concept, Lexicon, get_lexicon
from backend.nlp.normalize import Match, NormalizationResult

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "baseline_extract.txt"
REQUEST_TIMEOUT_SECONDS = 90.0
BASELINE_FUZZY_THRESHOLD = 0.80
OOV_PREFIX = "OOV:"
BASELINE_TIER = 3
BASELINE_CONFIDENCE = 0.5


@dataclass(slots=True)
class BaselinePrediction:
    present: set[str] = field(default_factory=set)
    negated: set[str] = field(default_factory=set)
    out_of_vocabulary: list[str] = field(default_factory=list)
    answered: bool = True


class BaselineExtractor(Protocol):
    def extract(self, text: str) -> BaselinePrediction: ...


def _keys(concept: Concept) -> list[str]:
    parts = [concept.canonical_en, concept.canonical_np]
    parts.extend(concept.devanagari_aliases)
    parts.extend(concept.romanized_aliases)
    parts.extend(getattr(concept, "latin_aliases", ()) or ())
    return [p for p in parts if p]


def _key(text: str) -> str:
    return fold_orthography(prepare(text).casefold()).strip()


def _surface_table(lexicon: Lexicon) -> list[tuple[str, tuple[str, ...], str]]:
    table: list[tuple[str, tuple[str, ...], str]] = []
    for concept_id in lexicon.concepts:
        concept = lexicon.get(concept_id)
        if concept is None:
            continue
        for surface in _keys(concept):
            k = _key(surface)
            if k:
                table.append((k, tuple(k.split()), concept_id))
    return table


def _contains_phrase(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1)
    )


def resolve(name: str, lexicon: Lexicon) -> str | None:
    needle = _key(name)
    if not needle:
        return None
    needle_tokens = tuple(needle.split())
    table = _surface_table(lexicon)

    for key, _tokens, concept_id in table:
        if key == needle:
            return concept_id

    for _key_text, tokens, concept_id in table:
        if _contains_phrase(needle_tokens, tokens) or _contains_phrase(tokens, needle_tokens):
            return concept_id

    best_id: str | None = None
    best_score = 0.0
    for key, _tokens, concept_id in table:
        score = fuzz.ratio(needle, key) / 100.0
        if score > best_score:
            best_score, best_id = score, concept_id
    return best_id if best_score >= BASELINE_FUZZY_THRESHOLD else None


def parse_response(raw: str, lexicon: Lexicon) -> BaselinePrediction:
    found = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if not found:
        return BaselinePrediction(answered=False)
    try:
        payload = json.loads(found.group())
    except json.JSONDecodeError:
        return BaselinePrediction(answered=False)

    entries = payload.get("concepts") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return BaselinePrediction(answered=False)

    prediction = BaselinePrediction()
    for entry in entries:
        if isinstance(entry, str):
            name, negated = entry, False
        elif isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            negated = bool(entry.get("negated", False))
        else:
            continue
        if not name:
            continue

        concept_id = resolve(name, lexicon)
        if concept_id is None:
            prediction.out_of_vocabulary.append(name)
            concept_id = f"{OOV_PREFIX}{name.casefold()}"
        (prediction.negated if negated else prediction.present).add(concept_id)

    prediction.negated -= prediction.present
    return prediction


class GemmaBaselineExtractor:
    """Free-form baseline extraction backed by Ollama Cloud or local Gemma."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        model: str | None = None,
        lexicon: Lexicon | None = None,
    ) -> None:
        self._client = client
        self._model = model or settings.active_model_name
        self._lexicon = lexicon

    def extract(self, text: str) -> BaselinePrediction:
        lexicon = self._lexicon or get_lexicon()
        prompt = PROMPT_PATH.read_text(encoding="utf-8").replace("{text}", text)
        url = f"{settings.model_base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0},
        }

        try:
            if self._client:
                res = self._client.post(
                    url, json=payload, headers=settings.model_headers, timeout=REQUEST_TIMEOUT_SECONDS
                )
                if res.status_code == 200:
                    return parse_response(res.json().get("response", ""), lexicon)
            else:
                with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    res = client.post(url, json=payload, headers=settings.model_headers)
                    if res.status_code == 200:
                        return parse_response(res.json().get("response", ""), lexicon)
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
                        return parse_response(res.json().get("response", ""), lexicon)
            except Exception:
                pass

        return BaselinePrediction(answered=False)


def as_result(text: str, prediction: BaselinePrediction, lexicon: Lexicon) -> NormalizationResult:
    """Adapts a baseline prediction into a NormalizationResult for uniform scoring."""
    matches: list[Match] = []
    for concept_id, negated in [
        *((cid, False) for cid in sorted(prediction.present)),
        *((cid, True) for cid in sorted(prediction.negated)),
    ]:
        if concept_id.startswith(OOV_PREFIX):
            raw_name = concept_id[len(OOV_PREFIX):]
            concept = Concept(
                concept_id=concept_id,
                canonical_en=raw_name,
                canonical_np=raw_name,
                concept_type="symptom",
            )
        else:
            concept = lexicon.get(concept_id)
            if concept is None:
                continue

        matches.append(
            Match(
                concept=concept,
                surface_form=concept.canonical_en,
                start_token=0,
                end_token=0,
                start_char=0,
                end_char=0,
                tier=BASELINE_TIER,
                confidence=BASELINE_CONFIDENCE,
                negated=negated,
            )
        )

    return NormalizationResult(text=text, prepared_text=text, matches=matches)
