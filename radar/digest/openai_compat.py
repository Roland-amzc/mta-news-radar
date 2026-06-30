"""OpenAICompatibleDigester: one adapter for any OpenAI-compatible API.

Configured entirely by (api_key, base_url, model) so the same code works with
DeepSeek / 通义 Qwen / Kimi / 智谱 GLM / Gemini(OpenAI 端点) / OpenAI — no key to
the Anthropic API required. `openai` is imported lazily.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from radar.digest.base import (
    DIGEST_SYSTEM_PROMPT,
    DigestConfig,
    DigestOutput,
    DigestRequest,
    parse_digest_json,
    request_text,
)


class OpenAICompatibleDigester:
    def __init__(
        self,
        config: DigestConfig,
        api_key: str,
        base_url: str,
        model: str,
        client=None,
    ) -> None:
        self.config = config
        self.model = model
        if client is None:
            from openai import OpenAI  # lazy

            client = OpenAI(api_key=api_key, base_url=base_url)
        self._client = client

    def _digest_one(self, req: DigestRequest) -> tuple[str, DigestOutput] | None:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
                    {"role": "user", "content": request_text(req)},
                ],
            )
            raw = resp.choices[0].message.content
            out = parse_digest_json(raw)
            return (req.id, out) if out else None
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
