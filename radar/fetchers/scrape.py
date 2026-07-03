"""ScrapeFetcher: config-driven HTML scraping via CSS selectors (BeautifulSoup).

No per-site Python file. `item_selector` must match a self-contained card that
either is an <a href> or contains exactly one; `title_selector`/`date_selector`
are optional selectors scoped within each matched card. This keeps adding a new
scrape source a topics.yaml-only change, consistent with the rest of the engine.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from radar.fetchers.base import parse_published
from radar.models import Item, SourceHealth, SourceSpec, TopicSpec, make_item_id

DEFAULT_TIMEOUT = 20  # seconds
# Real browser UA + HTML Accept: scraped news pages are often behind the same
# "block non-browser clients" rule as the feed hosts (see feed.py).
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
}


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    return session


class ScrapeFetcher:
    """Fetches an HTML page, extracts cards via CSS selectors, maps to Items.

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
        item_sel = source.item_selector or ""
        if not url or not item_sel:
            return [], SourceHealth(
                source_name=source.name, type=source.type, status="failed",
                error="missing url or item_selector",
            )
        try:
            resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:  # network / HTTP error -> failed, never raise
            return [], SourceHealth(
                source_name=source.name, type=source.type, status="failed",
                error=str(exc),
            )

        soup = BeautifulSoup(resp.content, "html.parser")
        items: list[Item] = []
        for node in soup.select(item_sel):
            item = self._node_to_item(node, source, topic, now, url)
            if item is not None:
                items.append(item)

        if not items:
            return [], SourceHealth(
                source_name=source.name, type=source.type, status="failed",
                error=f"item_selector {item_sel!r} matched no usable cards "
                "(page structure likely changed)",
            )

        return items, SourceHealth(
            source_name=source.name, type=source.type, status="ok",
            fetched=len(items),
        )

    def _node_to_item(
        self, node, source: SourceSpec, topic: TopicSpec, now: datetime, page_url: str,
    ) -> Item | None:
        href = node.get("href") if node.name == "a" else None
        if not href:
            link = node.select_one("a[href]")
            href = link.get("href") if link else None
        if not href:
            return None
        url = urljoin(page_url, href.strip())

        title = None
        if source.title_selector:
            title_node = node.select_one(source.title_selector)
            title = title_node.get_text(" ", strip=True) if title_node else None
        title = (title or "").strip()
        if not title:
            return None

        published = None
        if source.date_selector:
            date_node = node.select_one(source.date_selector)
            raw_date = date_node.get_text(strip=True) if date_node else None
            if raw_date:
                published = parse_published({"published": raw_date}, now)

        return Item(
            id=make_item_id(source.name, title, url),
            title=title,
            url=url,
            source_name=source.name,
            tier=source.tier,
            topic_id=topic.id,
            published=published,
            sub_label=source.sub_label,
        )
