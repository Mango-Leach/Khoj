"""Keeps personal identifiers out of stored transcripts and out of every LLM request.

The spec's rule (CLAUDE.md, "Guardrails"): no name, phone number or exact location is sent
to any provider. A person's name cannot be found reliably by a pattern, so the intake
questions never ask for one and the prompts tell the model to ignore names. What can be
caught by pattern, phone-like numbers, emails and links, is removed here.
"""
from __future__ import annotations

import re

_DIGIT = r"[0-9०-९]"  # Latin and Devanagari digits
_NUMBER = re.compile(rf"(?<!{_DIGIT})\+?{_DIGIT}(?:[\s\-]?{_DIGIT}){{6,}}")  # 7 or more digits in a row
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_SPACES = re.compile(r"\s+")

REMOVED = "[removed]"
MAX_TRANSCRIPT = 800


def scrub_text(text: str, limit: int = MAX_TRANSCRIPT) -> str:
    """Remove phone-like numbers (7 or more digits), emails and links; tidy spaces; cap length."""
    out = _EMAIL.sub(REMOVED, text)
    out = _URL.sub(REMOVED, out)
    out = _NUMBER.sub(REMOVED, out)
    out = _SPACES.sub(" ", out).strip()
    return out[:limit]
