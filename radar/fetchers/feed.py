"""FeedFetcher: fetch + parse any RSS/Atom feed (rss/podcast/youtube/arxiv)."""

from __future__ import annotations

from datetime import datetime

import feedparser
import requests

from radar.fetchers.base import entry_to_item
from radar.models import Item, SourceHealth, SourceSpec, TopicSpec

DEFAULT_TIMEOUT = 20  # seconds
USER_AGENT = "Mozilla/5.0 (compatible; mta-news-radar/0.1)"


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


class FeedFetcher:
    """Fetches a feed URL with a timeout, parses it, maps entries to Items.

    A session can be injected for testing; otherwise a default one is created
    lazily on first use.
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = _build_session()
        return self._session

    def fetch(
        self, source: SourceSpec, topic: TopicSpec, now: datetime
    ) -> tuple[list[Item], SourceHealth]:
        url = source.url or ""
        return self.fetch_url(url, source, topic, now)

    def fetch_url(
        self, url: str, source: SourceSpec, topic: TopicSpec, now: datetime
    ) -> tuple[list[Item], SourceHealth]:
        if not url:
            return [], SourceHealth(
                source_name=source.name, type=source.type, status="failed",
                error="no url",
            )
        try:
            resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:  # network / HTTP error -> failed, never raise
            return [], SourceHealth(
                source_name=source.name, type=source.type, status="failed",
                error=str(exc),
            )

        parsed = feedparser.parse(resp.content)
        entries = parsed.get("entries") or []
        # No entries is only OK if it's a recognizable but empty feed. A non-feed
        # (HTML error page) has no feed `version`; bozo also signals trouble.
        if not entries and (parsed.get("bozo") or not parsed.get("version")):
            reason = str(parsed.get("bozo_exception") or "not a recognizable feed")
            return [], SourceHealth(
                source_name=source.name, type=source.type, status="failed",
                error=reason,
            )

        items: list[Item] = []
        for entry in entries:
            item = entry_to_item(entry, source, topic, now)
            if item is not None:
                items.append(item)

        return items, SourceHealth(
            source_name=source.name, type=source.type, status="ok",
            fetched=len(items),
        )
