"""Serialize TopicResult to data/<topic>/latest.json and a top-level index."""

from __future__ import annotations

import json
from pathlib import Path

from radar.models import Item, SourceHealth, TopicResult


def _item_to_dict(item: Item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "source_name": item.source_name,
        "tier": item.tier,
        "topic_id": item.topic_id,
        "summary": item.summary,
        "published": item.published.isoformat() if item.published else None,
        "sub_label": item.sub_label,
        "score": item.score,
        "score_reason": item.score_reason,
    }


def _health_to_dict(health: SourceHealth) -> dict:
    return {
        "source_name": health.source_name,
        "type": health.type,
        "status": health.status,
        "fetched": health.fetched,
        "error": health.error,
    }


def write_topic(result: TopicResult, output_dir: Path) -> Path:
    out_dir = Path(output_dir) / result.topic_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "topic_id": result.topic_id,
        "name": result.name,
        "mode": result.mode,
        "window_hours": result.window_hours,
        "generated_at": result.generated_at,
        "topic_error": result.topic_error,
        "stats": result.stats,
        "source_health": [_health_to_dict(h) for h in result.source_health],
        "items": [_item_to_dict(i) for i in result.items],
    }
    path = out_dir / "latest.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def write_index(results: list[TopicResult], output_dir: Path) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "topics": [
            {
                "id": r.topic_id,
                "name": r.name,
                "mode": r.mode,
                "window_hours": r.window_hours,
                "count": len(r.items),
                "stats": r.stats,
                "topic_error": r.topic_error,
                "generated_at": r.generated_at,
                "data_url": f"data/{r.topic_id}/latest.json",
            }
            for r in results
        ],
    }
    path = out_dir / "index.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
