"""Within-topic de-duplication: merge same/near-duplicate stories, keep the
most authoritative copy (higher tier, then newer)."""

from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse

from radar.models import Item

TITLE_SIMILARITY_THRESHOLD = 0.92
# A necessary condition for SequenceMatcher.ratio() >= threshold: since
# ratio == 2*M/(la+lb) and M <= min(la, lb), ratio can only reach the threshold
# when min/max length ratio >= threshold/(2-threshold). Titles outside this band
# cannot match, so we skip the expensive ratio() for them.
_LEN_BAND = TITLE_SIMILARITY_THRESHOLD / (2.0 - TITLE_SIMILARITY_THRESHOLD)

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


def _title_matches(a_title: str, b_title: str) -> bool:
    """True if two lowercased titles are near-duplicates (ratio >= threshold).

    Uses difflib's own cheap upper bounds (real_quick_ratio/quick_ratio) plus a
    length-band prefilter to skip the O(n^2) full ratio() in the common
    not-a-match case; the final ratio() gate is identical to the plain form.
    """

    la, lb = len(a_title), len(b_title)
    if not la or not lb:
        return False  # empty titles never reach dedupe (fetchers drop them)
    if min(la, lb) / max(la, lb) < _LEN_BAND:
        return False
    matcher = SequenceMatcher(None, a_title, b_title)
    return (
        matcher.real_quick_ratio() >= TITLE_SIMILARITY_THRESHOLD
        and matcher.quick_ratio() >= TITLE_SIMILARITY_THRESHOLD
        and matcher.ratio() >= TITLE_SIMILARITY_THRESHOLD
    )


def _same_story(a: Item, b: Item) -> bool:
    if normalize_url(a.url) == normalize_url(b.url):
        return True
    return _title_matches(a.title.lower(), b.title.lower())


def dedupe(items: list[Item]) -> list[Item]:
    """Collapse duplicate stories, keeping the most authoritative representative.

    Same semantics as a naive O(n^2) scan (first matching representative in
    insertion order wins; a more-authoritative later copy replaces it), but the
    per-item normalized URL and lowercased title are computed once instead of
    recomputed on every pairwise comparison, and title similarity is gated by a
    length band + difflib's cheap upper bounds.
    """

    kept: list[Item] = []
    kept_url: list[str] = []  # normalized url of each representative
    kept_title: list[str] = []  # lowercased title of each representative
    for item in items:
        norm_url = normalize_url(item.url)
        low_title = item.title.lower()
        match_idx = None
        for idx in range(len(kept)):
            if kept_url[idx] == norm_url or _title_matches(low_title, kept_title[idx]):
                match_idx = idx
                break
        if match_idx is None:
            kept.append(item)
            kept_url.append(norm_url)
            kept_title.append(low_title)
        elif _is_more_authoritative(item, kept[match_idx]):
            kept[match_idx] = item
            kept_url[match_idx] = norm_url
            kept_title[match_idx] = low_title
    return kept
