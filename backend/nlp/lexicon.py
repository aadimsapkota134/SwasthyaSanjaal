"""In-memory indexed clinical lexicon of 300 Nepali medical concepts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from backend.config import settings
from backend.nlp.devanagari import fold, fold_orthography, prepare, tokenize

ASSERTION_TYPES = frozenset(
    {"symptom", "condition", "investigation", "drug_generic", "drug_brand", "severity"}
)

NEGATION_TYPE = "negation"
DURATION_TYPE = "duration"


@dataclass(frozen=True, slots=True)
class Concept:
    concept_id: str
    canonical_en: str
    canonical_np: str
    concept_type: str
    preferred_register: str | None = None
    devanagari_aliases: tuple[str, ...] = ()
    romanized_aliases: tuple[str, ...] = ()
    latin_aliases: tuple[str, ...] = ()
    code_mixed_patterns: tuple[str, ...] = ()
    generic_of: str | None = None
    icd11_code: str | None = None
    icd10_code: str | None = None
    negation_sensitive: bool = False
    duration_days: int | None = None
    frequency_per_day: int | None = None
    negation_scope: str | None = None

    @property
    def is_assertion(self) -> bool:
        return self.concept_type in ASSERTION_TYPES


@dataclass(frozen=True, slots=True)
class Surface:
    """One indexed alias: folded key, token count, and parent concept id."""
    key: str
    tokens: int
    concept_id: str


@dataclass
class Lexicon:
    concepts: dict[str, Concept]
    exact: dict[str, str] = field(default_factory=dict)
    folded: dict[str, str] = field(default_factory=dict)
    spellings: dict[str, str] = field(default_factory=dict)
    surfaces: list[Surface] = field(default_factory=list)
    max_tokens: int = 1

    def get(self, concept_id: str) -> Concept | None:
        return self.concepts.get(concept_id)

    def generic_for(self, concept: Concept) -> Concept | None:
        """Resolves brand drug name to its underlying generic compound."""
        return self.concepts.get(concept.generic_of) if concept.generic_of else None

    def negation_markers(self) -> list[Concept]:
        return [c for c in self.concepts.values() if c.concept_type == NEGATION_TYPE]


def _dict_to_concept(data: dict[str, object]) -> Concept:
    def as_tuple(key: str) -> tuple[str, ...]:
        val = data.get(key)
        if isinstance(val, (list, tuple)):
            return tuple(str(x) for x in val)
        if isinstance(val, str) and val.startswith("["):
            try:
                return tuple(json.loads(val))
            except Exception:
                pass
        return ()

    return Concept(
        concept_id=str(data["concept_id"]),
        canonical_en=str(data["canonical_en"]),
        canonical_np=str(data["canonical_np"]),
        concept_type=str(data["concept_type"]),
        preferred_register=str(data["preferred_register"]) if data.get("preferred_register") else None,
        devanagari_aliases=as_tuple("devanagari_aliases"),
        romanized_aliases=as_tuple("romanized_aliases"),
        latin_aliases=as_tuple("latin_aliases"),
        code_mixed_patterns=as_tuple("code_mixed_patterns"),
        generic_of=str(data["generic_of"]) if data.get("generic_of") else None,
        icd11_code=str(data["icd11_code"]) if data.get("icd11_code") else None,
        icd10_code=str(data["icd10_code"]) if data.get("icd10_code") else None,
        negation_sensitive=bool(data.get("negation_sensitive", False)),
        duration_days=int(data["duration_days"]) if data.get("duration_days") is not None else None,
        frequency_per_day=int(data["frequency_per_day"]) if data.get("frequency_per_day") is not None else None,
        negation_scope=str(data["negation_scope"]) if data.get("negation_scope") else None,
    )


def index_key(text: str) -> tuple[str, int]:
    tokens = [token.text for token in tokenize(prepare(text))]
    return fold(" ".join(tokens)), len(tokens)


def build_lexicon(concepts: list[Concept]) -> Lexicon:
    lexicon = Lexicon(concepts={c.concept_id: c for c in concepts})
    ordered = sorted(concepts, key=lambda c: c.concept_id)

    def add(concept: Concept, alias: str) -> None:
        key, count = index_key(alias)
        if not key:
            return
        lexicon.exact.setdefault(key, concept.concept_id)
        lexicon.folded.setdefault(fold_orthography(key), concept.concept_id)
        lexicon.spellings.setdefault(fold_orthography(key), key)
        lexicon.surfaces.append(Surface(key, count, concept.concept_id))
        lexicon.max_tokens = max(lexicon.max_tokens, count)

    # Pass 1: Curated aliases
    for concept in ordered:
        aliases = [
            *concept.devanagari_aliases,
            *concept.romanized_aliases,
            *concept.latin_aliases,
        ]
        if concept.concept_type != NEGATION_TYPE:
            aliases.extend(concept.code_mixed_patterns)
        for alias in aliases:
            add(concept, alias)

    # Pass 2: Canonical names
    for concept in ordered:
        add(concept, concept.canonical_np)
        add(concept, concept.canonical_en)

    return lexicon


def load_lexicon_from_file(path_str: str | None = None) -> Lexicon:
    """Loads concepts from JSON file."""
    candidate_paths = [
        Path(path_str) if path_str else None,
        Path(settings.lexicon_path),
        Path(__file__).resolve().parent.parent.parent / "data" / "nepali_clinical_lexicon.json",
        Path("data/nepali_clinical_lexicon.json"),
    ]

    for p in candidate_paths:
        if p and p.is_file():
            raw_data = json.loads(p.read_text(encoding="utf-8"))
            items = raw_data if isinstance(raw_data, list) else raw_data.get("concepts", [])
            concepts = [_dict_to_concept(item) for item in items]
            return build_lexicon(concepts)

    raise FileNotFoundError("Could not locate nepali_clinical_lexicon.json")


@lru_cache(maxsize=1)
def get_lexicon() -> Lexicon:
    """Process-wide cached Lexicon instance."""
    return load_lexicon_from_file()


def reset_lexicon_cache() -> None:
    get_lexicon.cache_clear()
