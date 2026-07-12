"""ArxivAuthorFetcher: anchor on an arXiv author identifier to avoid name clashes.

Uses the author's atom feed (https://arxiv.org/a/<author_id>.atom) so results are
tied to a unique author id, not a name (e.g. 姚顺宇 vs 姚顺雨 / Shunyu Yao).
"""

from __future__ import annotations

from datetime import datetime

import requests

from radar.fetchers.feed import FeedFetcher
from radar.models import Item, SourceHealth, SourceSpec, TopicSpec


class ArxivAuthorFetcher:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._feed = FeedFetcher(session=session)

    def fetch(
        self, source: SourceSpec, topic: TopicSpec, now: datetime
    ) -> tuple[list[Item], SourceHealth]:
        author_id = (source.author_id or "").strip()
        if not author_id or author_id == "TODO":
            return [], SourceHealth(
                source_name=source.name, type=source.type, status="failed",
                error="missing author_id",
            )
        url = f"https://arxiv.org/a/{author_id}.atom"
        return self._feed.fetch_url(url, source, topic, now)
