"""Tests for radar.config: loading + validation of topics.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from radar.config import load_topics, parse_window
from radar.models import ConfigError

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "topics.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _topic(**over) -> dict:
    base = {
        "id": "t1",
        "name": "T1",
        "mode": "topic",
        "window": "72h",
        "scorer": "keyword",
        "sources": [{"name": "S", "type": "rss", "tier": "media", "url": "https://x/feed"}],
    }
    base.update(over)
    return base


def test_parse_window():
    assert parse_window("72h") == 72
    assert parse_window("1w") == 168
    assert parse_window("2w") == 336
    assert parse_window("3d") == 72
    assert parse_window("24") == 24


def test_current_topics_yaml_loads_all_seven():
    topics = load_topics(REPO_ROOT / "topics.yaml")
    assert len(topics) == 7
    ids = {t.id for t in topics}
    assert {"frontier", "entity_radar", "ai_health"} <= ids


def test_deferred_and_disabled_sources_do_not_fail(tmp_path):
    data = {"version": 1, "topics": [_topic(sources=[
        {"name": "scrapeme", "type": "scrape", "tier": "official"},          # no url, deferred
        {"name": "todoauthor", "type": "arxiv_author", "tier": "entity", "author_id": "TODO"},
        {"name": "off", "type": "rss", "tier": "media", "enabled": False},   # disabled, no url
        {"name": "ok", "type": "rss", "tier": "media", "url": "https://x/feed"},
    ])]}
    topics = load_topics(_write(tmp_path, data))
    assert len(topics[0].sources) == 4  # all parsed, none dropped


def test_unknown_type_raises(tmp_path):
    data = {"topics": [_topic(sources=[{"name": "S", "type": "frobnicate", "tier": "media", "url": "u"}])]}
    with pytest.raises(ConfigError):
        load_topics(_write(tmp_path, data))


def test_runnable_arxiv_author_without_id_raises(tmp_path):
    data = {"topics": [_topic(sources=[{"name": "A", "type": "arxiv_author", "tier": "entity"}])]}
    with pytest.raises(ConfigError):
        load_topics(_write(tmp_path, data))


def test_runnable_rss_without_url_raises(tmp_path):
    data = {"topics": [_topic(sources=[{"name": "S", "type": "rss", "tier": "media"}])]}
    with pytest.raises(ConfigError):
        load_topics(_write(tmp_path, data))


def test_entity_mode_requires_none_scorer(tmp_path):
    data = {"topics": [_topic(mode="entity", scorer="keyword")]}
    with pytest.raises(ConfigError):
        load_topics(_write(tmp_path, data))


def test_missing_window_raises(tmp_path):
    t = _topic()
    del t["window"]
    with pytest.raises(ConfigError):
        load_topics(_write(tmp_path, {"topics": [t]}))
