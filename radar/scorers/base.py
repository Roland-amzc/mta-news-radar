"""Scorer protocol: assign item.score in place, return the list."""

from __future__ import annotations

from typing import Protocol

from radar.models import Item, TopicSpec


class Scorer(Protocol):
    def score(self, items: list[Item], topic: TopicSpec) -> list[Item]: ...
