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
    # Default (unconfigured) instance: identical to keyword. runner.run_all()
    # injects a real, budget/cache-backed LlmScorer via scorer_overrides when
    # DIGEST_API_KEY/BASE_URL/MODEL are set (see radar.scorers.llm).
    "llm": _LLM,
    # frontier: keyword scoring is sufficient (arXiv volume already trimmed by
    # the per-source prefilter upstream in pipeline.py); real LLM judging is
    # reserved for ai_health/quant_factor, which ADR-003 flagged as weak.
    "keyword_prefilter+llm": _KEYWORD,
}


def get_scorer(name: str) -> Scorer:
    try:
        return SCORERS[name]
    except KeyError:
        raise ValueError(f"unknown scorer: {name!r}")


__all__ = ["SCORERS", "get_scorer", "Scorer"]
