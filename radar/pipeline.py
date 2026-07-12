"""Single-topic pipeline: fetch -> prefilter -> window -> dedup -> score -> rank."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from radar.dedup import dedupe
from radar.fetchers import DEFERRED_TYPES, get_fetcher
from radar.fetchers.base import skipped_health
from radar.models import Item, SourceHealth, SourceSpec, TopicResult, TopicSpec
from radar.scorers import get_scorer
from radar.scorers.base import Scorer

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MAX_FETCH_WORKERS = 8  # per-topic concurrency for network fetches


def _should_skip(source: SourceSpec) -> str | None:
    """Return a skip reason if this source must not be fetched, else None."""

    if source.type in DEFERRED_TYPES:
        return f"deferred type: {source.type}"
    if not source.enabled:
        return "disabled"
    if source.type == "arxiv_author" and (not source.author_id or source.author_id == "TODO"):
        return "author_id not set"
    return None


def _prefilter(items: list[Item], keywords: list[str]) -> list[Item]:
    if not keywords:
        return items
    lowered = [k.lower() for k in keywords]
    out = []
    for item in items:
        text = f"{item.title} {item.summary or ''}".lower()
        if any(kw in text for kw in lowered):
            out.append(item)
    return out


def _within_window(item: Item, now: datetime, window_hours: float) -> bool:
    if item.published is None:
        return True  # keep undated items; they sort last later
    return item.published >= now - timedelta(hours=window_hours)


def _rank_and_gate(items: list[Item], topic: TopicSpec) -> list[Item]:
    if topic.mode == "entity":
        return sorted(items, key=lambda i: i.published or _EPOCH, reverse=True)
    # topic mode: drop below gate, sort by score desc (undated/None score last)
    gated = [i for i in items if (i.score or 0.0) >= topic.score_gate]
    return sorted(gated, key=lambda i: (i.score if i.score is not None else -1.0), reverse=True)


def run_topic(
    topic: TopicSpec,
    now: datetime,
    *,
    max_feeds: int | None = None,
    scorer_overrides: dict[str, Scorer] | None = None,
) -> TopicResult:
    """Run the full pipeline for one topic and return its TopicResult.

    `scorer_overrides` lets the caller inject a runtime-configured scorer (e.g.
    an LlmScorer wired to a cache + budget in runner.run_all()) for a given
    topic.scorer name, taking priority over the stateless registry default.
    """

    # Decide skip-vs-fetch in source order first: this keeps max_feeds semantics
    # ("first N runnable sources") and the health record order deterministic,
    # independent of which network fetch finishes first below.
    plans: list[tuple[SourceSpec, bool, str | None]] = []  # (source, do_fetch, skip_reason)
    runnable = 0
    for source in topic.sources:
        skip_reason = _should_skip(source)
        if skip_reason:
            plans.append((source, False, skip_reason))
        elif max_feeds is not None and runnable >= max_feeds:
            plans.append((source, False, "max_feeds limit"))
        else:
            runnable += 1
            plans.append((source, True, None))

    fetch_sources = [src for src, do_fetch, _ in plans if do_fetch]
    fetched: dict[int, tuple[list[Item], SourceHealth]] = {}
    if fetch_sources:
        def _do(src: SourceSpec) -> tuple[list[Item], SourceHealth]:
            return get_fetcher(src.type).fetch(src, topic, now)  # fetchers never raise

        with ThreadPoolExecutor(max_workers=min(MAX_FETCH_WORKERS, len(fetch_sources))) as pool_ex:
            for src, res in zip(fetch_sources, pool_ex.map(_do, fetch_sources)):
                fetched[id(src)] = res

    pool: list[Item] = []
    health: list[SourceHealth] = []
    fetched_total = 0
    for source, do_fetch, skip_reason in plans:
        if not do_fetch:
            health.append(skipped_health(source, skip_reason))
            continue
        items, src_health = fetched[id(source)]
        health.append(src_health)
        fetched_total += src_health.fetched
        if source.prefilter:
            items = _prefilter(items, topic.prefilter_keywords)
        pool.extend(items)

    after_prefilter = len(pool)
    pool = [i for i in pool if _within_window(i, now, topic.window_hours)]
    after_window = len(pool)
    pool = dedupe(pool)
    after_dedup = len(pool)

    scorer = (scorer_overrides or {}).get(topic.scorer) or get_scorer(topic.scorer)
    scored = scorer.score(pool, topic)
    final = _rank_and_gate(scored, topic)

    stats = {
        "fetched_total": fetched_total,
        "after_prefilter": after_prefilter,
        "after_window": after_window,
        "after_dedup": after_dedup,
        "final": len(final),
    }
    # Optional: scorers (e.g. LlmScorer) may report their own run stats, prefixed
    # to avoid colliding with the digest layer's own llm_calls/from_cache keys.
    scorer_stats = getattr(scorer, "last_stats", None)
    if scorer_stats:
        stats.update({f"scoring_{k}": v for k, v in scorer_stats.items()})

    return TopicResult(
        topic_id=topic.id,
        name=topic.name,
        mode=topic.mode,
        window_hours=topic.window_hours,
        generated_at=now.astimezone(timezone.utc).isoformat(),
        items=final,
        source_health=health,
        stats=stats,
    )
