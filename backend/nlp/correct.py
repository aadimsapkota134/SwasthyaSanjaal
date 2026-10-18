"""Lexicon-constrained OCR and transcription spell-correction.

Snaps misread tokens to known clinical vocabulary conservatively,
without altering word initials or inventing diagnoses.
"""

from __future__ import annotations

from dataclasses import dataclass
from rapidfuzz import fuzz, process

from backend.nlp.devanagari import (
    Token,
    fold,
    fold_orthography,
    prepare_layout,
    tokenize,
)
from backend.nlp.lexicon import Lexicon, get_lexicon

CORRECTION_THRESHOLD = 0.90
MIN_CORRECTION_LENGTH = 4
ORTHOGRAPHY_CONFIDENCE = 0.95

REASON_ORTHOGRAPHY = "orthography"
REASON_FUZZY = "fuzzy"


@dataclass(frozen=True, slots=True)
class Correction:
    """An individual verified substitution."""
    original: str
    replacement: str
    start: int
    end: int
    reason: str
    confidence: float


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    text: str
    corrections: tuple[Correction, ...] = ()
    unverified: tuple[str, ...] = ()


def _is_word(token: Token) -> bool:
    """Only word-like tokens with alphabetic characters are candidates for correction."""
    return any(c.isalpha() for c in token.text)


def _single_token_keys(lexicon: Lexicon) -> list[str]:
    seen: dict[str, None] = {}
    for surface in lexicon.surfaces:
        if surface.tokens == 1:
            seen.setdefault(surface.key, None)
    return list(seen)


def _match_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _same_initial(left: str, right: str) -> bool:
    """Preserves first character: never change first letter to avoid changing semantic word."""
    return bool(left) and bool(right) and left[0] == right[0]


def correct(
    raw: str,
    *,
    lexicon: Lexicon | None = None,
    threshold: float = CORRECTION_THRESHOLD,
) -> CorrectionResult:
    """Conservatively snaps OCR errors to known clinical lexicon terms."""
    lexicon = lexicon or get_lexicon()
    text = prepare_layout(raw)
    tokens = tokenize(text)
    if not tokens:
        return CorrectionResult(text=text)

    keys = _single_token_keys(lexicon)
    corrections: list[Correction] = []
    unverified: list[str] = []

    for token in tokens:
        if not _is_word(token):
            continue

        key = fold(token.text)
        if key in lexicon.exact:
            continue

        spelling = lexicon.spellings.get(fold_orthography(key))
        if spelling and spelling != key:
            corrections.append(
                Correction(
                    original=token.text,
                    replacement=_match_case(token.text, spelling),
                    start=token.start,
                    end=token.end,
                    reason=REASON_ORTHOGRAPHY,
                    confidence=ORTHOGRAPHY_CONFIDENCE,
                )
            )
            continue

        if len(key) < MIN_CORRECTION_LENGTH:
            continue

        hit = process.extractOne(key, keys, scorer=fuzz.ratio, score_cutoff=threshold * 100)
        if hit is not None and _same_initial(key, hit[0]):
            corrections.append(
                Correction(
                    original=token.text,
                    replacement=_match_case(token.text, hit[0]),
                    start=token.start,
                    end=token.end,
                    reason=REASON_FUZZY,
                    confidence=round(hit[1] / 100, 4),
                )
            )
            continue

        unverified.append(token.text)

    return CorrectionResult(
        text=_splice(text, corrections),
        corrections=tuple(corrections),
        unverified=tuple(dict.fromkeys(unverified)),
    )


def _splice(text: str, corrections: list[Correction]) -> str:
    if not corrections:
        return text
    out: list[str] = []
    cursor = 0
    for c in corrections:
        out.append(text[cursor : c.start])
        out.append(c.replacement)
        cursor = c.end
    out.append(text[cursor:])
    return "".join(out)
