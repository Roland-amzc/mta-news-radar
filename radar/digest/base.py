"""Digest layer contracts: turn items into concise Chinese title + summary.

The Digester protocol is the seam: ClaudeDigester (real) and NoopDigester
(degraded) implement it; tests inject a fake. No business logic here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DigestRequest:
    """One item to digest, identified by its stable Item.id."""

    id: str
    title: str
    summary: str | None = None


@dataclass(frozen=True)
class DigestOutput:
    """Chinese key points produced for one item."""

    title_zh: str
    summary_zh: str


@dataclass(frozen=True)
class DigestConfig:
    top_n: int = 24  # digest the first N items per topic (after ranking)
    max_items_per_run: int = 200  # budget gate: cap new LLM calls per run
    model: str = "claude-haiku-4-5"
    max_concurrency: int = 6


class Digester(Protocol):
    """Maps requests -> {id: DigestOutput}. A missing id means that item failed
    and is skipped (never raises for per-item failures)."""

    def digest(self, requests: list[DigestRequest]) -> dict[str, DigestOutput]: ...
