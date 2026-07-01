"""LlmScorer: LLM-based relevance judging for topics that need semantic
filtering (ai_health, quant_factor — see ADR-003/ADR-009), not just keyword
hits.

Reuses the same OpenAI-compatible provider as the digest layer (env vars
DIGEST_API_KEY/DIGEST_BASE_URL/DIGEST_MODEL) — one key does both jobs, no
second GitHub secret. When unconfigured (no client injected), this scorer is
identical to KeywordScorer, matching the old stub's behavior exactly.

KeywordScorer's score is always computed first as the baseline: it stands for
items outside the per-run budget and for any item where the LLM call or
response parsing fails, so a missing/broken key never breaks a topic's output.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from radar.models import Item, TopicSpec
from radar.scorers.keyword import KeywordScorer

DEFAULT_BUDGET = 200  # per-run cap on real LLM judgments (shared across topics)

RELEVANCE_SYSTEM_PROMPT = (
    "你是资讯相关性判定助手。给定一个主题的关键词和一条资讯的标题+摘要，判断这条资讯"
    "与该主题的相关程度。\n"
    '只输出一个 JSON 对象，形如 {"score": 0到1之间的数字, "reason": "一句话中文理由"}；'
    "不要任何额外文字、解释或代码块标记。"
)


def _request_text(topic: TopicSpec, item: Item) -> str:
    keywords = ", ".join(topic.keywords) or "(未提供关键词，凭标题摘要判断领域相关性)"
    body = item.title if not item.summary else f"{item.title}\n\n{item.summary}"
    return f"主题关键词: {keywords}\n\n资讯:\n{body}"


def parse_relevance_json(raw: str | None) -> tuple[float, str] | None:
    """Tolerant extraction of {score, reason} from an LLM reply.

    Returns None on any malformed/out-of-range result (caller keeps the
    keyword-fallback score for that item).
    """

    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except ValueError:
        return None
    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        return None
    if not (0.0 <= score <= 1.0):
        return None
    reason = str(data.get("reason") or "").strip() or "llm judged"
    return round(score, 4), reason


class RelevanceCache:
    """Persistent {item_id: (score, reason)} cache, mirrors digest.cache.DigestCache."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._store: dict[str, tuple[float, str]] = {}

    def load(self) -> "RelevanceCache":
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            raw = {}
        for item_id, val in (raw or {}).items():
            if isinstance(val, dict) and "score" in val:
                try:
                    self._store[item_id] = (float(val["score"]), str(val.get("reason", "")))
                except (TypeError, ValueError):
                    continue
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: {"score": v[0], "reason": v[1]} for k, v in self._store.items()}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, item_id: str) -> tuple[float, str] | None:
        return self._store.get(item_id)

    def put(self, item_id: str, score: float, reason: str) -> None:
        self._store[item_id] = (score, reason)


def build_relevance_client():
    """Return an OpenAI-compatible (client, model) pair from env, or None if unconfigured."""

    api_key = os.environ.get("DIGEST_API_KEY")
    base_url = os.environ.get("DIGEST_BASE_URL")
    model = os.environ.get("DIGEST_MODEL")
    if not (api_key and base_url and model):
        return None
    from openai import OpenAI  # lazy

    return OpenAI(api_key=api_key, base_url=base_url), model


class LlmScorer:
    """Judges relevance via LLM when configured; keyword score is always the
    baseline and the fallback for budget-exceeded / failed items."""

    def __init__(
        self,
        client=None,
        model: str | None = None,
        cache: RelevanceCache | None = None,
        budget: int = DEFAULT_BUDGET,
    ) -> None:
        self._fallback = KeywordScorer()
        self._client = client
        self._model = model
        self._cache = cache
        self._budget = budget  # decremented across calls; shared budget for a whole run

    def score(self, items: list[Item], topic: TopicSpec) -> list[Item]:
        self._fallback.score(items, topic)
        if self._client is None:
            return items
        for item in items:
            cached = self._cache.get(item.id) if self._cache else None
            if cached is not None:
                item.score, item.score_reason = cached
                continue
            if self._budget <= 0:
                continue  # keep keyword fallback score already set
            self._budget -= 1
            judged = self._judge_one(item, topic)
            if judged is None:
                continue  # keep keyword fallback score already set
            score, reason = judged
            item.score, item.score_reason = score, reason
            if self._cache:
                self._cache.put(item.id, score, reason)
        return items

    def _judge_one(self, item: Item, topic: TopicSpec) -> tuple[float, str] | None:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                max_tokens=200,
                messages=[
                    {"role": "system", "content": RELEVANCE_SYSTEM_PROMPT},
                    {"role": "user", "content": _request_text(topic, item)},
                ],
            )
            return parse_relevance_json(resp.choices[0].message.content)
        except Exception:
            return None  # per-item failure -> keyword fallback stands
