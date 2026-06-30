"""Digest layer: produce Chinese title + summary for top-N items per topic."""

from __future__ import annotations

import os

from radar.digest.base import DigestConfig, Digester, DigestOutput, DigestRequest
from radar.digest.noop import NoopDigester


def build_digester(config: DigestConfig) -> Digester:
    """ClaudeDigester when a key is present and digest is enabled, else Noop."""

    if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("DIGEST_ENABLED", "1") != "0":
        from radar.digest.claude import ClaudeDigester  # lazy: avoids importing anthropic otherwise

        return ClaudeDigester(config)
    print("[digest] no ANTHROPIC_API_KEY (or DIGEST_ENABLED=0) -> skipping digest")
    return NoopDigester()


__all__ = [
    "DigestConfig",
    "Digester",
    "DigestOutput",
    "DigestRequest",
    "NoopDigester",
    "build_digester",
]
