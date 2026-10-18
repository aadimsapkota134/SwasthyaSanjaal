"""Devanagari Unicode text preparation, tokenization, and orthography folding.

Everything downstream — exact dictionary lookup, fuzzy edit distance,
and negation scope resolution — relies on deterministic `prepare()`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

ZERO_WIDTH = dict.fromkeys(
    [
        0x200B,  # zero-width space
        0x200C,  # ZWNJ (Zero Width Non-Joiner)
        0x200D,  # ZWJ (Zero Width Joiner)
        0xFEFF,  # BOM
        0x00AD,  # soft hyphen
    ]
)

# Devanagari digits ० through ९ and extended forms
NEPALI_DIGITS = {chr(0x0966 + n): str(n) for n in range(10)}
NEPALI_DIGITS.update({chr(0xA8D0 + n): str(n) for n in range(10)})

CONJUNCT_TEST = "क्ष त्र ज्ञ श्र द्य ट्ट ङ्ग द्ध क्त ह्म"
DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")

# Tokenizer matching non-separators to preserve Devanagari combining marks
_WORD = re.compile(r"[^\s,;:!?()\[\]{}\"'/\\।॥–—\-‘’“”]+")

# Split boundary between digits and letters, preserving decimals like 98.6
_DIGIT_BOUNDARY = re.compile(r"(?<=\d)(?=[^\d.])|(?<=[^\d.])(?=\d)")


@dataclass(frozen=True, slots=True)
class Token:
    """A word token with source character offsets in prepared text."""
    text: str
    start: int
    end: int


def strip_zero_width(text: str) -> str:
    """Removes non-rendering zero-width marks."""
    return text.translate(ZERO_WIDTH)


def to_ascii_digits(text: str) -> str:
    """Converts Nepali Devanagari numerals (०-९) to ASCII (0-9)."""
    return text.translate(str.maketrans(NEPALI_DIGITS))


def prepare_layout(text: str) -> str:
    """NFC normalization, zero-width stripping, digit translation preserving newlines."""
    text = unicodedata.normalize("NFC", text)
    text = strip_zero_width(text)
    return to_ascii_digits(text)


def prepare(text: str) -> str:
    """Full preparation: NFC, zero-width stripping, digit translation, collapsed whitespace."""
    return re.sub(r"\s+", " ", prepare_layout(text)).strip()


def tokenize(text: str) -> list[Token]:
    """Tokenize Devanagari and Latin clinical text preserving precise character offsets."""
    tokens: list[Token] = []
    for word in _WORD.finditer(text):
        chunk = word.group()
        cuts = sorted({0, len(chunk)} | {m.start() for m in _DIGIT_BOUNDARY.finditer(chunk)})
        for begin, end in zip(cuts, cuts[1:]):
            piece = chunk[begin:end]
            lead = len(piece) - len(piece.lstrip("."))
            trimmed = piece.strip(".")
            if not trimmed:
                continue
            start = word.start() + begin + lead
            tokens.append(Token(trimmed, start, start + len(trimmed)))
    return tokens


# Orthographic variation folding in Nepali clinical handwriting & phonetics:
# interchangeable matras (ि/ी, ु/ू, ो/ौ, े/ै)
_MATRA_FOLD = str.maketrans(
    {
        "ी": "ि", "ू": "ु", "ौ": "ो", "ै": "े",
        "ः": "", "ँ": "ं",
        "ॢ": "लृ", "ऱ": "र", "ऴ": "ळ",
        "ई": "इ", "ऊ": "उ", "औ": "ओ", "ऐ": "ए",
    }
)

_NUKTA = "़"


def fold_orthography(text: str) -> str:
    """Collapses Devanagari spelling variants that do not change clinical semantics."""
    decomposed = unicodedata.normalize("NFD", text).replace(_NUKTA, "")
    return unicodedata.normalize("NFC", decomposed).translate(_MATRA_FOLD)


def is_devanagari(text: str) -> bool:
    """Returns True if string contains Devanagari characters."""
    return bool(DEVANAGARI_RANGE.search(text))


def fold(text: str) -> str:
    """Case-folds Latin surfaces for uniform indexing."""
    return text.casefold()
