"""Tests for radar.fetchers: feed parsing without network (injected session)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests

from radar.fetchers.arxiv_author import ArxivAuthorFetcher
from radar.fetchers.feed import FeedFetcher
from radar.models import SourceSpec, TopicSpec

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "radar"
NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, content: bytes, raise_exc: Exception | None = None):
        self.content = content
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise is not None:
            raise self._raise


class FakeSession:
    def __init__(self, response: FakeResponse):
        self._response = response
        self.headers = {}

    def get(self, url, timeout=None):
        return self._response


def _topic() -> TopicSpec:
    return TopicSpec(id="frontier", name="F", mode="topic", window_hours=72,
                     scorer="keyword", sources=[])


def _source() -> SourceSpec:
    return SourceSpec(name="Sample", type="rss", tier="media",
                      url="https://x/feed", sub_label="model_release")


def test_feed_parses_items_with_summary_and_time():
    content = (FIXTURES / "sample_rss.xml").read_bytes()
    fetcher = FeedFetcher(session=FakeSession(FakeResponse(content)))
    items, health = fetcher.fetch(_source(), _topic(), NOW)
    assert health.status == "ok"
    assert health.fetched == 2
    first = items[0]
    assert first.title.startswith("OpenAI")
    assert first.url == "https://example.com/a"
    assert first.summary and "agent" in first.summary.lower()
    assert first.published is not None and first.published.tzinfo is not None
    assert first.tier == "media" and first.sub_label == "model_release"
    assert first.topic_id == "frontier"
    assert first.audio_url == "https://cdn.example.com/ep1.mp3"  # enclosure captured
    assert items[1].audio_url is None  # no enclosure -> None


def test_http_error_marks_failed():
    resp = FakeResponse(b"", raise_exc=requests.HTTPError("403 Forbidden"))
    fetcher = FeedFetcher(session=FakeSession(resp))
    items, health = fetcher.fetch(_source(), _topic(), NOW)
    assert items == []
    assert health.status == "failed"
    assert "403" in (health.error or "")


def test_non_feed_content_marks_failed():
    fetcher = FeedFetcher(session=FakeSession(FakeResponse(b"<html>nope</html>")))
    items, health = fetcher.fetch(_source(), _topic(), NOW)
    assert items == []
    assert health.status == "failed"


def test_arxiv_author_missing_id_fails_fast():
    fetcher = ArxivAuthorFetcher(session=FakeSession(FakeResponse(b"")))
    src = SourceSpec(name="Yao", type="arxiv_author", tier="entity", author_id="TODO")
    items, health = fetcher.fetch(src, _topic(), NOW)
    assert items == []
    assert health.status == "failed"
