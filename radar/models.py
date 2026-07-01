"""Unified data structures for the radar engine.

These are the contract every layer (fetchers, scorers, pipeline, writer) speaks.
Pure data + a stable id helper; no business logic, no third-party imports.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ConfigError(Exception):
    """Raised when topics.yaml is invalid (missing field / unknown enum)."""


@dataclass(frozen=True)
class SourceSpec:
    """One source within a topic, as declared in topics.yaml."""

    name: str
    type: str  # rss | arxiv | arxiv_author | podcast | youtube | scrape | (deferred: x_account)
    tier: str  # official | media | aggregator | self_media | entity
    url: str | None = None  # arxiv_author may have no url (built from author_id)
    sub_label: str | None = None
    prefilter: bool = False  # apply topic.prefilter_keywords to this source
    author_id: str | None = None  # arxiv_author anchoring
    host: str | None = None  # podcast host (passthrough)
    enabled: bool = True
    status: str | None = None  # yaml's ok/verify/todo, metadata passthrough
    item_selector: str | None = None  # scrape: CSS selector for each card (must be or contain an <a href>)
    title_selector: str | None = None  # scrape: CSS selector for title, scoped within item_selector
    date_selector: str | None = None  # scrape: CSS selector for a date string, scoped within item_selector


@dataclass(frozen=True)
class TopicSpec:
    """One topic: its mode, window, scorer, and sources."""

    id: str
    name: str
    mode: str  # topic | entity
    window_hours: float  # "72h"/"1w"/"2w" parsed to hours
    scorer: str  # keyword | none | llm | keyword_prefilter+llm
    sources: list[SourceSpec]
    keywords: list[str] = field(default_factory=list)  # relevance scoring (KeywordScorer)
    sub_labels: list[str] = field(default_factory=list)
    prefilter_keywords: list[str] = field(default_factory=list)  # high-frequency prefilter
    score_gate: float = 0.0  # topic-mode gate threshold (0 = no filtering)


@dataclass
class Item:
    """A normalized story/item produced by a fetcher."""

    id: str  # stable hash of source_name + title + url
    title: str
    url: str
    source_name: str
    tier: str
    topic_id: str
    summary: str | None = None  # feed summary/description; scoring uses title + summary
    audio_url: str | None = None  # podcast audio enclosure (reliable "listen" link)
    title_zh: str | None = None  # LLM Chinese title (translated if source is English)
    summary_zh: str | None = None  # LLM 2-3 sentence Chinese summary
    published: datetime | None = None
    sub_label: str | None = None
    score: float | None = None  # left None by none/entity scorer
    score_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceHealth:
    """Outcome of fetching one source."""

    source_name: str
    type: str
    status: str  # ok | failed | skipped
    fetched: int = 0  # items fetched (before prefilter/window)
    error: str | None = None  # failure reason / skip reason


@dataclass
class TopicResult:
    """Everything produced for one topic in one run."""

    topic_id: str
    name: str
    mode: str
    window_hours: float
    generated_at: str  # ISO8601 UTC
    items: list[Item]
    source_health: list[SourceHealth]
    stats: dict[str, int] = field(default_factory=dict)
    topic_error: str | None = None  # set on topic-level hard error; items == []


def make_item_id(source_name: str, title: str, url: str) -> str:
    """Stable short id for an item, independent of run time."""

    digest = hashlib.sha1(f"{source_name}|{title}|{url}".encode("utf-8")).hexdigest()
    return digest[:16]
