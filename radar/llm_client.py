"""Shared OpenAI-compatible provider wiring from env.

Both the digest layer (build_digester) and the LLM relevance scorer
(build_relevance_client) read the same DIGEST_API_KEY/DIGEST_BASE_URL/
DIGEST_MODEL trio — one key, two jobs (see ADR-007/ADR-009). This module is the
single place that reads those env vars and builds the client, so the two callers
no longer duplicate the logic.
"""

from __future__ import annotations

import os


def read_openai_env() -> tuple[str, str, str] | None:
    """Return (api_key, base_url, model) if all three DIGEST_* vars are set, else None."""

    api_key = os.environ.get("DIGEST_API_KEY")
    base_url = os.environ.get("DIGEST_BASE_URL")
    model = os.environ.get("DIGEST_MODEL")
    if api_key and base_url and model:
        return api_key, base_url, model
    return None


def build_openai_client(api_key: str, base_url: str):
    """Construct an OpenAI-compatible client. `openai` is imported lazily."""

    from openai import OpenAI  # lazy: only needed when a provider is configured

    return OpenAI(api_key=api_key, base_url=base_url)
