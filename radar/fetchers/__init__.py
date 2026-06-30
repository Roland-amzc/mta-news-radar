"""Fetcher registry: source type -> Fetcher implementation."""

from __future__ import annotations

from radar.fetchers.arxiv_author import ArxivAuthorFetcher
from radar.fetchers.base import Fetcher
from radar.fetchers.feed import FeedFetcher

_FEED = FeedFetcher()
_ARXIV_AUTHOR = ArxivAuthorFetcher()

# rss / podcast / youtube / arxiv are all plain feeds -> one implementation.
FETCHERS: dict[str, Fetcher] = {
    "rss": _FEED,
    "podcast": _FEED,
    "youtube": _FEED,
    "arxiv": _FEED,
    "arxiv_author": _ARXIV_AUTHOR,
}

# Known-but-not-yet-implemented types: parsed by config, skipped by pipeline.
DEFERRED_TYPES: set[str] = {"scrape", "x_account"}


def get_fetcher(source_type: str) -> Fetcher:
    """Return the fetcher for a runnable source type, or raise for unknown types."""

    try:
        return FETCHERS[source_type]
    except KeyError:
        raise ValueError(f"unknown source type: {source_type!r}")


__all__ = ["FETCHERS", "DEFERRED_TYPES", "get_fetcher", "Fetcher"]
