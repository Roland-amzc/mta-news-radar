"""Fetcher protocol and shared feed-entry mapping helpers."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from dateutil import parser as dtparser

from radar.models import Item, SourceHealth, SourceSpec, TopicSpec, make_item_id


class Fetcher(Protocol):
    """A source fetcher: turns one source into items + a health record.

    Implementations must never raise for network/parse errors; they return a
    SourceHealth with status="failed" instead.
    """

    def fetch(
        self, source: SourceSpec, topic: TopicSpec, now: datetime
    ) -> tuple[list[Item], SourceHealth]: ...


def parse_published(entry: dict[str, Any], now: datetime) -> datetime | None:
    """Best-effort parse of a feed entry's publish time to aware UTC.

    Prefers feedparser's pre-parsed struct_time; falls back to dateutil on the
    raw string. Returns None when unparseable or absurdly far in the future.
    """

    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    dt: datetime | None = None
    if struct is not None:
        try:
            dt = datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
        except (ValueError, OverflowError, TypeError):
            dt = None
    if dt is None:
        raw = entry.get("published") or entry.get("updated") or entry.get("pubDate")
        if raw:
            try:
                dt = dtparser.parse(str(raw))
            except (ValueError, OverflowError, TypeError):
                dt = None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Guard against garbage future timestamps.
    if dt > now + timedelta(days=2):
        return None
    return dt


def entry_to_item(
    entry: dict[str, Any], source: SourceSpec, topic: TopicSpec, now: datetime
) -> Item | None:
    """Map a feedparser entry to a unified Item; None if it lacks title+link."""

    title = (entry.get("title") or "").strip()
    url = (entry.get("link") or "").strip()
    if not title or not url:
        return None
    summary = entry.get("summary") or entry.get("description") or None
    if summary:
        summary = str(summary).strip() or None
    audio_url = None
    for enc in entry.get("enclosures") or []:
        href = enc.get("href") or enc.get("url")
        enc_type = (enc.get("type") or "").lower()
        if href and (enc_type.startswith("audio") or not enc_type):
            audio_url = href
            break
    return Item(
        id=make_item_id(source.name, title, url),
        title=title,
        url=url,
        source_name=source.name,
        tier=source.tier,
        topic_id=topic.id,
        summary=summary,
        audio_url=audio_url,
        published=parse_published(entry, now),
        sub_label=source.sub_label,
    )


def skipped_health(source: SourceSpec, reason: str) -> SourceHealth:
    return SourceHealth(
        source_name=source.name, type=source.type, status="skipped", error=reason
    )
