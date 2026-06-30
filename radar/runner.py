"""Top-level orchestration: load config, run each topic (isolated), write output."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from radar.config import load_topics
from radar.models import TopicResult
from radar.pipeline import run_topic
from radar.writer import write_index, write_topic


def run_all(
    config_path: Path,
    output_dir: Path,
    now: datetime,
    *,
    only: list[str] | None = None,
    max_feeds: int | None = None,
) -> list[TopicResult]:
    """Run every topic. ConfigError from load_topics propagates to the caller.

    A topic-level hard error is caught: an empty TopicResult with topic_error is
    still written, so every selected topic produces an output file.
    """

    topics = load_topics(config_path)
    if only:
        wanted = set(only)
        topics = [t for t in topics if t.id in wanted]

    results: list[TopicResult] = []
    for topic in topics:
        try:
            result = run_topic(topic, now, max_feeds=max_feeds)
        except Exception as exc:  # topic-level isolation
            result = TopicResult(
                topic_id=topic.id,
                name=topic.name,
                mode=topic.mode,
                window_hours=topic.window_hours,
                generated_at=now.astimezone(timezone.utc).isoformat(),
                items=[],
                source_health=[],
                stats={},
                topic_error=str(exc),
            )
        write_topic(result, output_dir)
        results.append(result)

    write_index(results, output_dir)
    return results
