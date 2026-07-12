"""Persistent digest cache keyed by Item.id, so processed items aren't re-paid."""

from __future__ import annotations

from typing import Any

from radar.digest.base import DigestOutput
from radar.jsoncache import JsonKVCache


class DigestCache(JsonKVCache[DigestOutput]):
    def _serialize(self, value: DigestOutput) -> dict[str, Any]:
        return {"title_zh": value.title_zh, "summary_zh": value.summary_zh}

    def _deserialize(self, raw: dict[str, Any]) -> DigestOutput | None:
        if "title_zh" not in raw or "summary_zh" not in raw:
            return None
        return DigestOutput(raw["title_zh"], raw["summary_zh"])
