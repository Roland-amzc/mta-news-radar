"""Tests for scripts.check_source_health: which sources count as alerts."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.check_source_health import collect_failures, main


def _write_topic(data_dir: Path, topic_id: str, name: str, health: list[dict]) -> None:
    topic_dir = data_dir / topic_id
    topic_dir.mkdir(parents=True, exist_ok=True)
    (topic_dir / "latest.json").write_text(
        json.dumps({"name": name, "source_health": health}), encoding="utf-8"
    )


def _write_index(data_dir: Path, topic_ids: list[str]) -> None:
    topics = [{"id": t, "data_url": f"data/{t}/latest.json"} for t in topic_ids]
    (data_dir / "index.json").write_text(json.dumps({"topics": topics}), encoding="utf-8")


def test_only_failed_status_is_an_alert(tmp_path: Path) -> None:
    # failed -> alert; ok / skipped are not, even ok-with-zero-items.
    _write_topic(tmp_path, "t1", "Topic One", [
        {"source_name": "Good", "type": "rss", "status": "ok", "fetched": 5},
        {"source_name": "Empty", "type": "scrape", "status": "ok", "fetched": 0},
        {"source_name": "Disabled", "type": "rss", "status": "skipped", "error": "disabled"},
        {"source_name": "Broken", "type": "rss", "status": "failed", "error": "403 Forbidden"},
    ])
    _write_index(tmp_path, ["t1"])

    failures = collect_failures(tmp_path)
    assert [f["source"] for f in failures] == ["Broken"]
    assert failures[0]["topic"] == "Topic One"
    assert "403" in failures[0]["error"]


def test_no_failures_returns_empty(tmp_path: Path) -> None:
    _write_topic(tmp_path, "t1", "Topic One", [
        {"source_name": "Good", "type": "rss", "status": "ok", "fetched": 5},
        {"source_name": "Skip", "type": "x_account", "status": "skipped", "error": "deferred"},
    ])
    _write_index(tmp_path, ["t1"])
    assert collect_failures(tmp_path) == []


def test_works_without_index_via_glob(tmp_path: Path) -> None:
    # No index.json -> fall back to scanning */latest.json.
    _write_topic(tmp_path, "t2", "Topic Two", [
        {"source_name": "Broken", "type": "podcast", "status": "failed", "error": "timeout"},
    ])
    failures = collect_failures(tmp_path)
    assert len(failures) == 1
    assert failures[0]["source"] == "Broken"


def test_exit_code_never_fails_by_default(tmp_path: Path) -> None:
    _write_topic(tmp_path, "t1", "T", [
        {"source_name": "Broken", "type": "rss", "status": "failed", "error": "boom"},
    ])
    _write_index(tmp_path, ["t1"])
    assert main(["--data-dir", str(tmp_path)]) == 0
    assert main(["--data-dir", str(tmp_path), "--fail-over", "1"]) == 1
    assert main(["--data-dir", str(tmp_path), "--fail-over", "2"]) == 0


def test_missing_data_dir_is_safe(tmp_path: Path) -> None:
    assert collect_failures(tmp_path / "nope") == []
    assert main(["--data-dir", str(tmp_path / "nope")]) == 0
