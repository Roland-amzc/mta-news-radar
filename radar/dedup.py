"""Within-topic de-duplication: merge same/near-duplicate stories, keep the
most authoritative copy (higher tier, then newer)."""

from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse

from radar.models import Item

TITLE_SIMILARITY_THRESHOLD = 0.92

# Lower rank = more authoritative.
TIER_RANK: dict[str, int] = {
    "official": 0,
    "media": 1,
    "aggregator": 2,
    "self_media": 3,
    "entity": 4,
}
DEFAULT_TIER_RANK = 5

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def normalize_url(url: str) -> str:
    """Drop query/fragment, lowercase host, strip trailing slash."""

    try:
        parts = urlparse(url.strip())
    except ValueError:
        return url.strip().lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunparse((parts.scheme.lower(), netloc, path, "", "", ""))


def _published_key(item: Item) -> datetime:
    return item.published or _EPOCH


def _is_more_authoritative(candidate: Item, current: Item) -> bool:
    """True if candidate should replace current (higher tier, then newer)."""

    cand_rank = TIER_RANK.get(candidate.tier, DEFAULT_TIER_RANK)
    cur_rank = TIER_RANK.get(current.tier, DEFAULT_TIER_RANK)
    if cand_rank != cur_rank:
        return cand_rank < cur_rank
    return _published_key(candidate) > _published_key(current)


def _same_story(a: Item, b: Item) -> bool:
    if normalize_url(a.url) == normalize_url(b.url):
        return True
    ratio = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
    return ratio >= TITLE_SIMILARITY_THRESHOLD


def dedupe(items: list[Item]) -> list[Item]:
    """Collapse duplicate stories, keeping the most authoritative representative."""

    kept: list[Item] = []
    for item in items:
        match_idx = None
        for idx, rep in enumerate(kept):
            if _same_story(item, rep):
                match_idx = idx
                break
        if match_idx is None:
            kept.append(item)
        elif _is_more_authoritative(item, kept[match_idx]):
            kept[match_idx] = item
    return kept
