"""DigestService: orchestrate per-topic digesting (top-N, cache, budget, stats)."""

from __future__ import annotations

import logging

from radar.digest.base import Digester, DigestConfig, DigestRequest
from radar.digest.cache import DigestCache
from radar.models import TopicResult, TopicSpec

logger = logging.getLogger(__name__)


class DigestService:
    def __init__(self, digester: Digester, cache: DigestCache, config: DigestConfig) -> None:
        self._digester = digester
        self._cache = cache
        self._config = config
        self._budget = config.max_items_per_run  # shared across topics this run

    def budget_left(self) -> int:
        return self._budget

    def process(self, result: TopicResult, topic: TopicSpec) -> None:
        """Backfill title_zh/summary_zh on the topic's top-N items, in place.

        Never raises: a digest failure must not break the topic's output.
        """
        targets = result.items[: self._config.top_n]
        from_cache = 0
        llm_calls = 0
        try:
            missing = []
            for item in targets:
                cached = self._cache.get(item.id)
                if cached is not None:
                    item.title_zh, item.summary_zh = cached.title_zh, cached.summary_zh
                    from_cache += 1
                else:
                    missing.append(item)

            to_call = missing[: max(0, self._budget)]
            if to_call:
                requests = [DigestRequest(i.id, i.title, i.summary) for i in to_call]
                outputs = self._digester.digest(requests)
                self._budget -= len(to_call)  # budget tracks attempts (cost bound)
                llm_calls = len(outputs)  # stat reports items actually digested
                by_id = {i.id: i for i in to_call}
                for item_id, out in outputs.items():
                    self._cache.put(item_id, out)
                    item = by_id.get(item_id)
                    if item is not None:
                        item.title_zh, item.summary_zh = out.title_zh, out.summary_zh
        except Exception as exc:  # digest is best-effort; never break the topic
            result.stats["digest_error"] = 1
            logger.warning("%s digest error: %s", result.topic_id, exc)

        result.stats["digest_targets"] = len(targets)
        result.stats["from_cache"] = from_cache
        result.stats["llm_calls"] = llm_calls
