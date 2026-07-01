"""Load and validate topics.yaml into TopicSpec/SourceSpec.

Validation philosophy: fail loud on typos/illegal enums, but *parse-but-keep*
sources that are merely deferred (scrape/x_account), disabled, or author_id=TODO
— the pipeline marks those skipped. Only truly unknown types raise ConfigError.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from radar.fetchers import DEFERRED_TYPES, FETCHERS
from radar.models import ConfigError, SourceSpec, TopicSpec
from radar.scorers import SCORERS

VALID_MODES = {"topic", "entity"}
KNOWN_TYPES = set(FETCHERS) | DEFERRED_TYPES
_WINDOW_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([hdw]?)\s*$", re.IGNORECASE)
_WINDOW_UNIT_HOURS = {"h": 1.0, "d": 24.0, "w": 168.0, "": 1.0}


def parse_window(text: Any) -> float:
    """'72h' -> 72, '1w' -> 168, '2w' -> 336, '3d' -> 72, '24' -> 24 (hours)."""

    match = _WINDOW_RE.match(str(text))
    if not match:
        raise ConfigError(f"invalid window: {text!r} (expected like 72h / 1w / 2w)")
    value, unit = match.group(1), match.group(2).lower()
    return float(value) * _WINDOW_UNIT_HOURS[unit]


def _is_skipped(type_: str, enabled: bool, author_id: str | None) -> bool:
    """A source the pipeline will skip (not fetched); config does not validate it."""

    if type_ in DEFERRED_TYPES:
        return True
    if not enabled:
        return True
    # Explicit placeholder = "not ready, skip". A *missing* author_id on an
    # enabled source is a mistake and should fail validation instead.
    if type_ == "arxiv_author" and author_id == "TODO":
        return True
    return False


def _build_source(raw: dict[str, Any], topic_id: str) -> SourceSpec:
    name = raw.get("name")
    type_ = raw.get("type")
    if not name:
        raise ConfigError(f"[{topic_id}] a source is missing 'name'")
    if not type_:
        raise ConfigError(f"[{topic_id}] source {name!r} is missing 'type'")
    if type_ not in KNOWN_TYPES:
        raise ConfigError(
            f"[{topic_id}] source {name!r} has unknown type {type_!r} "
            f"(known: {sorted(KNOWN_TYPES)})"
        )

    enabled = bool(raw.get("enabled", True))
    author_id = raw.get("author_id")
    url = raw.get("url")

    item_selector = raw.get("item_selector")
    title_selector = raw.get("title_selector")

    # Validate field completeness only for sources we will actually run.
    if not _is_skipped(type_, enabled, author_id):
        if type_ == "arxiv_author":
            if not author_id or author_id == "TODO":
                raise ConfigError(
                    f"[{topic_id}] arxiv_author source {name!r} needs a valid author_id"
                )
        elif type_ == "scrape":
            if not url:
                raise ConfigError(f"[{topic_id}] scrape source {name!r} needs a 'url'")
            if not item_selector:
                raise ConfigError(
                    f"[{topic_id}] scrape source {name!r} needs 'item_selector'"
                )
            if not title_selector:
                raise ConfigError(
                    f"[{topic_id}] scrape source {name!r} needs 'title_selector'"
                )
        elif not url:
            raise ConfigError(f"[{topic_id}] source {name!r} needs a 'url'")

    return SourceSpec(
        name=str(name),
        type=str(type_),
        tier=str(raw.get("tier", "other")),
        url=str(url) if url else None,
        sub_label=raw.get("sub_label"),
        prefilter=bool(raw.get("prefilter", False)),
        author_id=str(author_id) if author_id else None,
        host=raw.get("host"),
        enabled=enabled,
        status=raw.get("status"),
        item_selector=str(item_selector) if item_selector else None,
        title_selector=str(title_selector) if title_selector else None,
        date_selector=str(raw.get("date_selector")) if raw.get("date_selector") else None,
    )


def _build_topic(raw: dict[str, Any]) -> TopicSpec:
    topic_id = raw.get("id")
    if not topic_id:
        raise ConfigError("a topic is missing 'id'")
    name = str(raw.get("name") or topic_id)
    mode = raw.get("mode")
    if mode not in VALID_MODES:
        raise ConfigError(f"[{topic_id}] invalid mode {mode!r} (expected topic/entity)")
    scorer = raw.get("scorer")
    if scorer not in SCORERS:
        raise ConfigError(
            f"[{topic_id}] unknown scorer {scorer!r} (known: {sorted(SCORERS)})"
        )
    if mode == "entity" and scorer != "none":
        raise ConfigError(f"[{topic_id}] entity mode requires scorer 'none', got {scorer!r}")
    if "window" not in raw:
        raise ConfigError(f"[{topic_id}] missing 'window'")
    window_hours = parse_window(raw["window"])

    raw_sources = raw.get("sources") or []
    if not isinstance(raw_sources, list):
        raise ConfigError(f"[{topic_id}] 'sources' must be a list")
    sources = [_build_source(s, str(topic_id)) for s in raw_sources]

    return TopicSpec(
        id=str(topic_id),
        name=name,
        mode=str(mode),
        window_hours=window_hours,
        scorer=str(scorer),
        sources=sources,
        keywords=list(raw.get("keywords") or []),
        sub_labels=list(raw.get("sub_labels") or []),
        prefilter_keywords=list(raw.get("prefilter_keywords") or []),
        score_gate=float(raw.get("score_gate", 0.0)),
    )


def load_topics(path: Path) -> list[TopicSpec]:
    """Parse and validate topics.yaml. Raises ConfigError on invalid config."""

    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict) or "topics" not in data:
        raise ConfigError("config must be a mapping with a 'topics' list")
    raw_topics = data.get("topics") or []
    if not isinstance(raw_topics, list) or not raw_topics:
        raise ConfigError("'topics' must be a non-empty list")

    topics = [_build_topic(t) for t in raw_topics]
    ids = [t.id for t in topics]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ConfigError(f"duplicate topic ids: {sorted(dupes)}")
    return topics
