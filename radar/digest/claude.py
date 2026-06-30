"""ClaudeDigester: produce Chinese title + summary via Claude Haiku 4.5.

`anthropic` is imported lazily so `import radar.digest.claude` works without the
SDK installed and without a key — the client is built only on construction.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from radar.digest.base import DigestConfig, DigestOutput, DigestRequest

SYSTEM_PROMPT = (
    "你是中文科技/资讯编辑。把给定条目压缩成:一个中文标题(不超过 30 字)和 "
    "2-3 句中文摘要,讲清「是什么、为什么值得看」。要求:忠实原文、不编造、不加个人评论;"
    "若原文是英文,翻译成自然的中文。只输出要求的字段。"
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "title_zh": {"type": "string"},
        "summary_zh": {"type": "string"},
    },
    "required": ["title_zh", "summary_zh"],
    "additionalProperties": False,
}


class ClaudeDigester:
    def __init__(self, config: DigestConfig, client=None) -> None:
        self.config = config
        if client is None:
            import anthropic  # lazy: only needed when actually digesting

            client = anthropic.Anthropic()
        self._client = client

    def _digest_one(self, req: DigestRequest) -> tuple[str, DigestOutput] | None:
        text = req.title if not req.summary else f"{req.title}\n\n{req.summary}"
        try:
            resp = self._client.messages.create(
                model=self.config.model,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
                output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            )
            raw = next(b.text for b in resp.content if b.type == "text")
            data = json.loads(raw)
            title_zh = str(data["title_zh"]).strip()
            summary_zh = str(data["summary_zh"]).strip()
            if not title_zh or not summary_zh:
                return None
            return req.id, DigestOutput(title_zh, summary_zh)
        except Exception:
            return None  # per-item failure is skipped, never raised

    def digest(self, requests: list[DigestRequest]) -> dict[str, DigestOutput]:
        if not requests:
            return {}
        out: dict[str, DigestOutput] = {}
        workers = max(1, min(self.config.max_concurrency, len(requests)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(self._digest_one, requests):
                if result is not None:
                    out[result[0]] = result[1]
        return out
