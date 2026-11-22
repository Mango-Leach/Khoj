"""Decides whether a learner's own words support a skill. A rule, not a model.

An AI may propose skills, but a skill is kept only when a keyword for it appears in what the
learner actually said (CLAUDE.md: "AI proposes, rules or people decide"). The tiles a learner
ticked are interest, never evidence.

Matching is by whole word, because plain substrings misfire in English: "been" is not a bee,
"when" is not a hen, "them" is not a hem. Latin keywords may carry a common ending
(paint, paints, painting, painted, painter). Devanagari keywords inflect too much for that,
so they match from the start of a word onward, which also covers endings such as शिवते and शिवतो.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

_ENDINGS = "s|es|ed|d|er|ers|ing|ings"
_DEVANAGARI = "ऀ-ॿ"
_SEPARATORS = re.compile(r"[-_/.,;:!?()\[\]\"'`]+")
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase, and turn punctuation and hyphens into spaces so "two-wheeler" matches "two wheeler".
    The answer separator and the "+" of a pair keyword are kept."""
    return _SPACES.sub(" ", _SEPARATORS.sub(" ", text.lower())).strip()


@lru_cache(maxsize=2048)
def _pattern(keyword: str) -> re.Pattern[str]:
    kw = normalise(keyword)
    if not kw.isascii():
        return re.compile(rf"(?<![{_DEVANAGARI}]){re.escape(kw)}")
    alternatives = [re.escape(kw) + rf"(?:{_ENDINGS})?"]
    if kw.endswith("e"):  # bake -> baking, solare -> n/a
        alternatives.append(re.escape(kw[:-1]) + r"(?:ing|er|ers)")
    return re.compile(rf"(?<![a-z])(?:{'|'.join(alternatives)})(?![a-z])")


SEGMENT = "|"  # separates answers, so a pair keyword cannot be satisfied by two different answers


def _matches(keyword: str, segments: list[str]) -> bool:
    """A plain keyword matches anywhere. "fix+phone" needs both words in the same answer, in any order."""
    parts = keyword.split("+")
    return any(all(_pattern(p).search(seg) for p in parts) for seg in segments)


def keyword_hits(skill: dict[str, Any], text: str) -> int:
    """How many of the skill's keywords appear in `text` (already normalised, answers joined by SEGMENT)."""
    segments = text.split(SEGMENT)
    return sum(1 for kw in skill["keywords"] if _matches(kw, segments))


def has_evidence(skill: dict[str, Any], text: str) -> bool:
    """`text` may hold several answers separated by SEGMENT."""
    return keyword_hits(skill, SEGMENT.join(normalise(part) for part in text.split(SEGMENT))) > 0
