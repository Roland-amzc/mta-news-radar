"""NoneScorer: entity mode — collect all, no scoring (score stays None)."""

from __future__ import annotations

from radar.models import Item, TopicSpec


class NoneScorer:
    def score(self, items: list[Item], topic: TopicSpec) -> list[Item]:
        return items
