"""Versioned production prompt loader for SwasthyaSanjaal AI engine."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load prompt file from backend/prompts directory."""
    path = PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


# Cached prompt templates
OCR_TRANSCRIBE_PROMPT = load_prompt("ocr_transcribe.txt")
ASR_TRANSCRIBE_PROMPT = load_prompt("asr_transcribe.txt")
TIER3_MATCH_PROMPT = load_prompt("tier3_match.txt")
ASSISTANT_SYSTEM_PROMPT = load_prompt("assistant_system.txt")
SUMMARY_NARRATIVE_PROMPT = load_prompt("summary_narrative.txt")
MEANING_NP_PROMPT = load_prompt("meaning_np.txt")
