"""Tests for radar.pipeline.run_topic and radar.runner.run_all (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import radar.pipeline as pipeline_mod
import radar.runner as runner_mod
from radar.models import Item, SourceHealth, SourceSpec, TopicSpec
from radar.pipeline import run_topic
from radar.runner import run_all

NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _src(name, type_="rss", tier="media", enabled=True, prefilter=False):
    return SourceSpec(name=name, type=type_, tier=tier, url="https://x/feed",
                      enabled=enabled, prefilter=prefilter)


def _topic(mode="topic", scorer="keyword", sources=None, keywords=("agent", "LLM"),
           prefilter_keywords=("agent",), score_gate=0.0):
    return TopicSpec(id="t", name="T", mode=mode, window_hours=72, scorer=scorer,
                     sources=sources or [], keywords=list(keywords),
                     prefilter_keywords=list(prefilter_keywords), score_gate=score_gate)


class FakeFetcher:
    """Returns canned items keyed by source name; status ok."""

    def __init__(self, by_source: dict):
        self._by_source = by_source

    def fetch(self, source, topic, now):
        specs = self._by_source.get(source.name, [])
        items = [
            Item(id=f"{source.name}-{i}", title=t, url=f"https://x/{source.name}/{i}",
                 source_name=source.name, tier=source.tier, topic_id=topic.id,
                 summary=None, published=pub)
            for i, (t, pub) in enumerate(specs)
        ]
        return items, SourceHealth(source.name, source.type, "ok", fetched=len(items))


def _install(monkeypatch, by_source):
    monkeypatch.setattr(pipeline_mod, "get_fetcher", lambda _type: FakeFetcher(by_source))


def test_window_filters_old_keeps_undated(monkeypatch):
    recent = ("recent agent item", NOW - timedelta(hours=10))
    old = ("old agent item", NOW - timedelta(days=30))
    undated = ("undated agent item", None)
    _install(monkeypatch, {"S": [recent, old, undated]})
    result = run_topic(_topic(sources=[_src("S")]), NOW)
    titles = {i.title for i in result.items}
    assert "old agent item" not in titles
    assert {"recent agent item", "undated agent item"} <= titles
    assert result.stats["fetched_total"] == 3
    assert result.stats["after_window"] == 2


def test_topic_mode_sorted_by_score_and_gated(monkeypatch):
    items = {"S": [
        ("agent LLM combo", NOW), ("agent only", NOW), ("totally unrelated", NOW),
    ]}
    _install(monkeypatch, items)
    result = run_topic(_topic(sources=[_src("S")], score_gate=0.25), NOW)
    titles = [i.title for i in result.items]
    assert titles[0] == "agent LLM combo"  # most hits -> highest score
    assert "totally unrelated" not in titles  # below gate 0.25
    scores = [i.score for i in result.items]
    assert scores == sorted(scores, reverse=True)


def test_scorer_overrides_take_priority_over_registry(monkeypatch):
    class FixedScorer:
        def score(self, items, topic):
            for item in items:
                item.score, item.score_reason = 0.99, "overridden"
            return items

    _install(monkeypatch, {"S": [("agent LLM combo", NOW), ("totally unrelated", NOW)]})
    result = run_topic(
        _topic(sources=[_src("S")], score_gate=0.0), NOW,
        scorer_overrides={"keyword": FixedScorer()},
    )
    assert all(i.score == 0.99 and i.score_reason == "overridden" for i in result.items)


def test_entity_mode_collects_all_by_time(monkeypatch):
    items = {"S": [
        ("c", NOW - timedelta(hours=1)),
        ("a", NOW - timedelta(hours=3)),
        ("b", NOW - timedelta(hours=2)),
    ]}
    _install(monkeypatch, items)
    result = run_topic(_topic(mode="entity", scorer="none", sources=[_src("S", tier="entity")]), NOW)
    assert [i.title for i in result.items] == ["c", "b", "a"]
    assert all(i.score is None for i in result.items)


def test_skips_deferred_and_disabled(monkeypatch):
    _install(monkeypatch, {"S3": [("agent live", NOW)]})
    sources = [_src("S1", type_="x_account"), _src("S2", enabled=False), _src("S3")]
    result = run_topic(_topic(sources=sources), NOW)
    by_name = {h.source_name: h.status for h in result.source_health}
    assert by_name == {"S1": "skipped", "S2": "skipped", "S3": "ok"}
    assert len(result.items) == 1


def test_empty_topic_all_skipped_is_valid(monkeypatch):
    _install(monkeypatch, {})
    sources = [_src("S1", type_="x_account"), _src("S2", enabled=False)]
    result = run_topic(_topic(sources=sources), NOW)
    assert result.items == []
    assert result.topic_error is None
    assert result.stats["final"] == 0


def test_prefilter_only_affects_prefilter_sources(monkeypatch):
    _install(monkeypatch, {"P": [("agent paper", NOW), ("cooking paper", NOW)]})
    result = run_topic(_topic(sources=[_src("P", prefilter=True)]), NOW)
    assert result.stats["fetched_total"] == 2
    assert result.stats["after_prefilter"] == 1  # "cooking" dropped by prefilter


# ---- runner ----

def _write_cfg(tmp_path, topic_dict) -> Path:
    path = tmp_path / "topics.yaml"
    path.write_text(yaml.safe_dump({"topics": [topic_dict]}, allow_unicode=True), encoding="utf-8")
    return path


def test_runner_writes_topic_and_index(tmp_path):
    cfg = _write_cfg(tmp_path, {
        "id": "demo", "name": "Demo", "mode": "entity", "window": "72h", "scorer": "none",
        "sources": [{"name": "off", "type": "rss", "tier": "media", "enabled": False}],
    })
    out = tmp_path / "data"
    results = run_all(cfg, out, NOW)
    assert len(results) == 1
    topic_file = out / "demo" / "latest.json"
    assert topic_file.exists()
    payload = json.loads(topic_file.read_text(encoding="utf-8"))
    assert payload["topic_id"] == "demo" and payload["items"] == []
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["topics"][0]["id"] == "demo"


def test_runner_topic_error_still_writes(tmp_path, monkeypatch):
    def boom(topic, now, *, max_feeds=None, scorer_overrides=None):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(runner_mod, "run_topic", boom)
    cfg = _write_cfg(tmp_path, {
        "id": "demo", "name": "Demo", "mode": "entity", "window": "72h", "scorer": "none",
        "sources": [{"name": "off", "type": "rss", "tier": "media", "enabled": False}],
    })
    out = tmp_path / "data"
    results = run_all(cfg, out, NOW)
    payload = json.loads((out / "demo" / "latest.json").read_text(encoding="utf-8"))
    assert payload["topic_error"] == "kaboom"
    assert payload["items"] == []
