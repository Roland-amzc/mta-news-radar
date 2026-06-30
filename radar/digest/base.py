"""Digest layer contracts: turn items into concise Chinese title + summary.

The Digester protocol is the seam: ClaudeDigester (real) and NoopDigester
(degraded) implement it; tests inject a fake. No business logic here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DigestRequest:
    """One item to digest, identified by its stable Item.id."""

    id: str
    title: str
    summary: str | None = None


@dataclass(frozen=True)
class DigestOutput:
    """Chinese key points produced for one item."""

    title_zh: str
    summary_zh: str


@dataclass(frozen=True)
class DigestConfig:
    top_n: int = 24  # digest the first N items per topic (after ranking)
    max_items_per_run: int = 200  # budget gate: cap new LLM calls per run
    model: str = "claude-haiku-4-5"
    max_concurrency: int = 6


class Digester(Protocol):
    """Maps requests -> {id: DigestOutput}. A missing id means that item failed
    and is skipped (never raises for per-item failures)."""

    def digest(self, requests: list[DigestRequest]) -> dict[str, DigestOutput]: ...


# Shared, provider-agnostic prompt + parsing (Claude and OpenAI-compatible both use these).
DIGEST_SYSTEM_PROMPT = (
    "你是中文科技/资讯编辑。读给定条目,产出:\n"
    "- title_zh: 一个中文标题,不超过 30 字(原文是英文则翻译成自然的中文)\n"
    "- summary_zh: 2-3 句中文摘要,讲清「是什么、为什么值得看」\n"
    "要求:忠实原文、不编造、不加个人评论。\n"
    '只输出一个 JSON 对象,形如 {"title_zh":"...","summary_zh":"..."};不要任何额外文字、解释或代码块标记。'
)


def request_text(req: DigestRequest) -> str:
    return req.title if not req.summary else f"{req.title}\n\n{req.summary}"


def parse_digest_json(raw: str | None) -> DigestOutput | None:
    """Tolerant extraction of {title_zh, summary_zh} from an LLM reply.

    Handles code fences and surrounding prose by slicing the first {...} span.
    Returns None on any malformed / empty result (caller skips that item).
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
    title_zh = str(data.get("title_zh") or "").strip()
    summary_zh = str(data.get("summary_zh") or "").strip()
    if not title_zh or not summary_zh:
        return None
    return DigestOutput(title_zh, summary_zh)
