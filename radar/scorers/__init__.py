"""Scorer registry: scorer name -> Scorer implementation."""

from __future__ import annotations

from radar.scorers.base import Scorer
from radar.scorers.keyword import KeywordScorer
from radar.scorers.llm import LlmScorer
from radar.scorers.none_ import NoneScorer

_KEYWORD = KeywordScorer()
_NONE = NoneScorer()
_LLM = LlmScorer()

SCORERS: dict[str, Scorer] = {
    "keyword": _KEYWORD,
    "none": _NONE,
    "llm": _LLM,  # stub, delegates to keyword
    "keyword_prefilter+llm": _LLM,  # prefilter happens in pipeline; scoring stubbed
}


def get_scorer(name: str) -> Scorer:
    try:
        return SCORERS[name]
    except KeyError:
        raise ValueError(f"unknown scorer: {name!r}")


__all__ = ["SCORERS", "get_scorer", "Scorer"]
