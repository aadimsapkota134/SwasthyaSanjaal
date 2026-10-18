"""Three-tier normalization of Nepali clinical text with field-level uncertainty and provenance.

Tier 1 (LEXICON): Exact dictionary lookup (confidence = 1.00)
Tier 2 (FUZZY_MATCH): Orthography-folded & RapidFuzz similarity with edit-distance budget
Tier 3 (LLM): Shortlist-constrained Gemma classification (confidence = 0.70, requires confirmation)

Features:
- Dynamic programming overlap resolution (weighted interval scheduling)
- Directional negation resolution (Nepali post-positional "छैन" and pre-positional markers)
- Duration, daily frequency, and severity modifier extraction
- Field-level uncertainty (`confirmation_required`) and provenance (`resolution_method`)
- Nepali confirmation prompt generation (`confirmation_prompt_np`)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

from backend.nlp.devanagari import Token, fold_orthography, prepare, tokenize
from backend.nlp.lexicon import (
    DURATION_TYPE,
    NEGATION_TYPE,
    Concept,
    Lexicon,
    get_lexicon,
)
from backend.nlp.tier3 import Tier3Matcher

FUZZY_THRESHOLD = 0.85
UNCERTAINTY_THRESHOLD = 0.85
NEGATION_WINDOW = 3

TIER_WEIGHT = {1: 1.0, 2: 0.7, 3: 0.5}
TIER3_MAX_SPAN_TOKENS = 3
TIER3_CANDIDATES = 12

PROVENANCE_FOR_TIER = {
    1: "LEXICON",
    2: "FUZZY_MATCH",
    3: "LLM",
}

NEPALI_NUMBER_WORDS = {
    "एक": 1, "दुई": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पाच": 5,
    "छ": 6, "सात": 7, "आठ": 8, "नौ": 9, "दश": 10, "दस": 10, "पन्ध्र": 15,
    "ek": 1, "dui": 2, "tin": 3, "teen": 3, "char": 4, "panch": 5,
    "chha": 6, "saat": 7, "sat": 7, "aath": 8, "nau": 9, "das": 10,
}

MIN_FUZZY_LENGTH = 3
FOLDED_CONFIDENCE = 0.95
FUZZY_CANDIDATES = 5
MIN_FUZZY_SHORTER = 5
FUZZY_EDIT_BUDGET = ((8, 1), (10**6, 2))


@dataclass(slots=True)
class Match:
    concept: Concept
    surface_form: str
    start_token: int
    end_token: int  # inclusive
    start_char: int
    end_char: int
    tier: int
    confidence: float
    negated: bool = False
    reasoning: str | None = None

    @property
    def token_span(self) -> int:
        return self.end_token - self.start_token + 1

    @property
    def resolution_method(self) -> str:
        """Provenance label for how this clinical concept was resolved."""
        return PROVENANCE_FOR_TIER.get(self.tier, "LEXICON")

    @property
    def confirmation_required(self) -> bool:
        """True if resolved via LLM (Tier 3) or below the deterministic confidence threshold."""
        return self.tier == 3 or self.confidence < UNCERTAINTY_THRESHOLD

    @property
    def confirmation_prompt_np(self) -> str | None:
        """Generates a human-in-the-loop Nepali confirmation question when uncertain."""
        if not self.confirmation_required:
            return None
        if self.negated:
            return f"मैले '{self.surface_form}' बाट '{self.concept.canonical_np}' छैन भनेर बुझेँ। हो?"
        return f"मैले '{self.surface_form}' लाई '{self.concept.canonical_np}' ({self.concept.canonical_en}) भनेर बुझेँ। हो?"


@dataclass(slots=True)
class NormalizationResult:
    text: str
    prepared_text: str
    matches: list[Match] = field(default_factory=list)
    duration_days: int | None = None
    frequency_per_day: int | None = None
    severity: str | None = None
    unmatched: list[str] = field(default_factory=list)

    @property
    def assertions(self) -> list[Match]:
        """Concepts that represent clinical assertions (symptoms, conditions, medications, labs, severity)."""
        return [m for m in self.matches if m.concept.is_assertion]

    @property
    def requires_confirmation(self) -> bool:
        """True if any extracted clinical assertion requires human confirmation."""
        return any(m.confirmation_required for m in self.assertions)

    def tier_counts(self) -> dict[int, int]:
        counts = {1: 0, 2: 0, 3: 0}
        for match in self.matches:
            counts[match.tier] += 1
        return counts


def _spans(tokens: list[Token], max_tokens: int) -> list[tuple[int, int, str]]:
    """Yields candidate spans (start_idx, end_idx, folded_text), longest spans first."""
    out: list[tuple[int, int, str]] = []
    for start in range(len(tokens)):
        for length in range(min(max_tokens, len(tokens) - start), 0, -1):
            end = start + length - 1
            span_text = " ".join(t.text for t in tokens[start : end + 1]).casefold()
            out.append((start, end, span_text))
    return out


def _within_edit_budget(span: str, alias: str) -> bool:
    """Absolute edit-distance budget guard against false positives like Azee vs mg."""
    shorter = min(len(span), len(alias))
    if shorter < MIN_FUZZY_SHORTER:
        return False
    edits = Levenshtein.distance(span, alias)
    for limit, budget in FUZZY_EDIT_BUDGET:
        if shorter <= limit:
            return edits <= budget
    return False


def _is_negation_marker(lexicon: Lexicon, text: str) -> bool:
    concept_id = lexicon.exact.get(text.casefold())
    return (
        concept_id is not None
        and lexicon.concepts[concept_id].concept_type == NEGATION_TYPE
    )


def _exact_and_fuzzy(
    tokens: list[Token], lexicon: Lexicon, *, fuzzy_threshold: float
) -> list[Match]:
    candidates: list[Match] = []
    keys = [surface.key for surface in lexicon.surfaces]

    marker_tokens = {
        index for index, token in enumerate(tokens) if _is_negation_marker(lexicon, token.text)
    }

    for start, end, text in _spans(tokens, lexicon.max_tokens + 1):
        concept_id = lexicon.exact.get(text)
        if concept_id:
            candidates.append(
                _make_match(tokens, start, end, lexicon.concepts[concept_id], 1, 1.0)
            )
            continue

        if end > start and marker_tokens & set(range(start, end + 1)):
            continue
        if len(text) < MIN_FUZZY_LENGTH:
            continue

        folded = lexicon.folded.get(fold_orthography(text))
        if folded:
            candidates.append(
                _make_match(
                    tokens, start, end, lexicon.concepts[folded], 2, FOLDED_CONFIDENCE
                )
            )
            continue

        for _, score, position in process.extract(
            text, keys, scorer=fuzz.ratio, score_cutoff=fuzzy_threshold * 100,
            limit=FUZZY_CANDIDATES,
        ):
            if not _within_edit_budget(text, keys[position]):
                continue
            candidates.append(
                _make_match(
                    tokens,
                    start,
                    end,
                    lexicon.concepts[lexicon.surfaces[position].concept_id],
                    2,
                    round(score / 100, 4),
                )
            )
            break

    return candidates


def _make_match(
    tokens: list[Token], start: int, end: int, concept: Concept, tier: int, confidence: float
) -> Match:
    return Match(
        concept=concept,
        surface_form=" ".join(t.text for t in tokens[start : end + 1]),
        start_token=start,
        end_token=end,
        start_char=tokens[start].start,
        end_char=tokens[end].end,
        tier=tier,
        confidence=confidence,
    )


def _resolve_overlaps(candidates: list[Match]) -> list[Match]:
    """Resolves overlapping matches using dynamic programming weighted interval scheduling."""
    if not candidates:
        return []

    length = max(m.end_token for m in candidates) + 1
    ending: dict[int, list[Match]] = {}
    for match in candidates:
        ending.setdefault(match.end_token + 1, []).append(match)
    for bucket in ending.values():
        bucket.sort(key=lambda m: (m.tier, -m.token_span, -m.confidence, m.concept.concept_id))

    best = [0.0] * (length + 1)
    chosen: list[Match | None] = [None] * (length + 1)
    for position in range(1, length + 1):
        best[position] = best[position - 1]
        for match in ending.get(position, []):
            score = best[match.start_token] + match.token_span * TIER_WEIGHT[match.tier]
            if score > best[position]:
                best[position] = score
                chosen[position] = match

    kept: list[Match] = []
    position = length
    while position > 0:
        match = chosen[position]
        if match is None:
            position -= 1
            continue
        kept.append(match)
        position = match.start_token

    return sorted(kept, key=lambda m: m.start_token)


def _apply_negation(matches: list[Match], window: int = NEGATION_WINDOW) -> None:
    """Detects directional negation and flags denied findings."""
    markers = [m for m in matches if m.concept.concept_type == NEGATION_TYPE]
    targets = [m for m in matches if m.concept.is_assertion]

    for marker in markers:
        scope = marker.concept.negation_scope or "post"
        backward = [
            t for t in targets if t.end_token < marker.start_token
            and marker.start_token - t.end_token <= window
        ]
        forward = [
            t for t in targets if t.start_token > marker.end_token
            and t.start_token - marker.end_token <= window
        ]

        if scope == "pre":
            chosen = forward[0] if forward else None
        else:
            chosen = backward[-1] if backward else (forward[0] if forward else None)

        if chosen is not None:
            chosen.negated = True


def _read_duration(tokens: list[Token], matches: list[Match]) -> tuple[int | None, int | None]:
    """Extracts duration (days) and frequency (times per day)."""
    days: int | None = None
    frequency: int | None = None

    for match in matches:
        if match.concept.concept_type != DURATION_TYPE:
            continue
        if match.concept.frequency_per_day is not None:
            frequency = match.concept.frequency_per_day
        unit_days = match.concept.duration_days
        if unit_days is None:
            continue

        quantity = 1
        if match.start_token > 0:
            previous = tokens[match.start_token - 1].text.casefold()
            if previous.isdigit():
                quantity = int(previous)
            elif previous in NEPALI_NUMBER_WORDS:
                quantity = NEPALI_NUMBER_WORDS[previous]
        days = max(days or 0, unit_days * quantity)

    return days, frequency


def _read_severity(matches: list[Match]) -> str | None:
    """Extracts primary clinical severity modifier if present."""
    for match in matches:
        if match.concept.concept_type == "severity" and not match.negated:
            return match.concept.canonical_en.lower()
    return None


def _unmatched_spans(tokens: list[Token], matches: list[Match]) -> list[tuple[int, int]]:
    covered = {i for m in matches for i in range(m.start_token, m.end_token + 1)}
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index in range(len(tokens)):
        if index in covered:
            if start is not None:
                runs.append((start, index - 1))
                start = None
        elif start is None:
            start = index
    if start is not None:
        runs.append((start, len(tokens) - 1))
    return runs


def _run_tier3(
    tokens: list[Token],
    leftovers: list[tuple[int, int]],
    lexicon: Lexicon,
    tier3: Tier3Matcher,
) -> list[Match]:
    keys = [surface.key for surface in lexicon.surfaces]
    matches: list[Match] = []

    for start, end in leftovers:
        if end - start + 1 > TIER3_MAX_SPAN_TOKENS:
            continue
        span = " ".join(t.text for t in tokens[start : end + 1])
        top = process.extract(span.casefold(), keys, limit=TIER3_CANDIDATES)
        candidates = [lexicon.concepts[lexicon.surfaces[pos].concept_id] for _, _, pos in top]

        decision = tier3.match(span, candidates)
        if decision is not None and decision.concept_id in lexicon.concepts:
            concept = lexicon.concepts[decision.concept_id]
            match = _make_match(tokens, start, end, concept, 3, decision.confidence)
            match.reasoning = decision.reasoning
            matches.append(match)

    return matches


def normalize(
    text: str,
    *,
    lexicon: Lexicon | None = None,
    tier3: Tier3Matcher | None = None,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> NormalizationResult:
    """Normalizes clinical text into 3-tier concepts, negation, duration, and uncertainty."""
    lexicon = lexicon or get_lexicon()
    prepared = prepare(text)
    tokens = tokenize(prepared)
    if not tokens:
        return NormalizationResult(text=text, prepared_text=prepared)

    matches = _resolve_overlaps(_exact_and_fuzzy(tokens, lexicon, fuzzy_threshold=fuzzy_threshold))

    leftovers = _unmatched_spans(tokens, matches)
    if tier3 is not None and leftovers:
        matches = _resolve_overlaps(
            matches + _run_tier3(tokens, leftovers, lexicon, tier3)
        )

    _apply_negation(matches)
    days, frequency = _read_duration(tokens, matches)
    severity = _read_severity(matches)

    return NormalizationResult(
        text=text,
        prepared_text=prepared,
        matches=matches,
        duration_days=days,
        frequency_per_day=frequency,
        severity=severity,
        unmatched=[
            " ".join(t.text for t in tokens[s : e + 1])
            for s, e in _unmatched_spans(tokens, matches)
        ],
    )
