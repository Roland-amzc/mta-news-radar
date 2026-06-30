"""Tests for radar.dedup: within-topic de-duplication."""

from __future__ import annotations

from datetime import datetime, timezone

from radar.dedup import dedupe, normalize_url
from radar.models import Item


def _item(title, url, tier="media", published=None):
    return Item(id=url, title=title, url=url, source_name=tier, tier=tier,
                topic_id="t", published=published)


def test_normalize_url_strips_query_and_trailing_slash():
    assert normalize_url("https://Example.com/a/?utm=1#x") == "https://example.com/a"


def test_same_url_keeps_higher_tier():
    official = _item("Story", "https://example.com/x", tier="official")
    selfmed = _item("Story alt", "https://example.com/x?ref=1", tier="self_media")
    out = dedupe([selfmed, official])
    assert len(out) == 1
    assert out[0].tier == "official"


def test_similar_titles_merged():
    a = _item("OpenAI launches new model today", "https://a.com/1", tier="media")
    b = _item("OpenAI launches new model today!", "https://b.com/2", tier="self_media")
    out = dedupe([a, b])
    assert len(out) == 1
    assert out[0].tier == "media"  # higher tier kept


def test_distinct_items_kept():
    a = _item("Totally different one", "https://a.com/1")
    b = _item("Another unrelated thing", "https://b.com/2")
    assert len(dedupe([a, b])) == 2


def test_same_tier_keeps_newer():
    older = _item("Story", "https://example.com/x", tier="media",
                  published=datetime(2026, 6, 1, tzinfo=timezone.utc))
    newer = _item("Story", "https://example.com/x", tier="media",
                  published=datetime(2026, 6, 30, tzinfo=timezone.utc))
    out = dedupe([older, newer])
    assert len(out) == 1
    assert out[0].published.day == 30
