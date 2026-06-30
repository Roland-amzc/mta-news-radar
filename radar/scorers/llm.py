"""LlmScorer: STUB for this phase.

Delegates to KeywordScorer so frontier/health/quant still get sensible scores.
Makes NO network calls. TODO: replace with real LLM relevance judging in a later
spec (provider choice, API key, token budget, cost gate).
"""

from __future__ import annotations

from radar.models import Item, TopicSpec
from radar.scorers.keyword import KeywordScorer


class LlmScorer:
    def __init__(self) -> None:
        self._fallback = KeywordScorer()

    def score(self, items: list[Item], topic: TopicSpec) -> list[Item]:
        # TODO(llm): batch-judge relevance via LLM. For now, keyword fallback.
        return self._fallback.score(items, topic)
