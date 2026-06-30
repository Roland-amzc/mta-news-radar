"""Digest layer: produce Chinese title + summary for top-N items per topic.

Provider selection (in priority order), all via environment variables:

1. OpenAI-compatible (recommended for non-Anthropic / Coding-Plan-only setups):
   set DIGEST_API_KEY + DIGEST_BASE_URL + DIGEST_MODEL. One adapter covers
   DeepSeek / 通义 Qwen / Kimi / 智谱 GLM / Gemini(OpenAI endpoint) / OpenAI.
   Presets in PROVIDER_PRESETS below.
2. Anthropic API: set ANTHROPIC_API_KEY (NOT the Claude Code subscription —
   that's a different auth and does not grant Messages API access).
3. Neither set (or DIGEST_ENABLED=0): NoopDigester — engine runs, no zh fields.
"""

from __future__ import annotations

import os

from radar.digest.base import DigestConfig, Digester, DigestOutput, DigestRequest
from radar.digest.noop import NoopDigester

# base_url / model presets for common OpenAI-compatible providers (reference).
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-2.0-flash"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
}


def build_digester(config: DigestConfig) -> Digester:
    """Pick a Digester from env. OpenAI-compatible first, then Anthropic, else Noop."""

    if os.environ.get("DIGEST_ENABLED", "1") == "0":
        print("[digest] DIGEST_ENABLED=0 -> skipping digest")
        return NoopDigester()

    api_key = os.environ.get("DIGEST_API_KEY")
    base_url = os.environ.get("DIGEST_BASE_URL")
    model = os.environ.get("DIGEST_MODEL")
    if api_key and base_url and model:
        from radar.digest.openai_compat import OpenAICompatibleDigester  # lazy

        print(f"[digest] OpenAI-compatible provider: {base_url} ({model})")
        return OpenAICompatibleDigester(config, api_key=api_key, base_url=base_url, model=model)

    if os.environ.get("ANTHROPIC_API_KEY"):
        from radar.digest.claude import ClaudeDigester  # lazy

        print(f"[digest] Anthropic API: {config.model}")
        return ClaudeDigester(config)

    print(
        "[digest] no provider configured -> skipping digest "
        "(set DIGEST_API_KEY/DIGEST_BASE_URL/DIGEST_MODEL, or ANTHROPIC_API_KEY)"
    )
    return NoopDigester()


__all__ = [
    "DigestConfig",
    "Digester",
    "DigestOutput",
    "DigestRequest",
    "NoopDigester",
    "PROVIDER_PRESETS",
    "build_digester",
]
