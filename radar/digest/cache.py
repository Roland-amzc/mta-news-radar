"""Persistent digest cache keyed by Item.id, so processed items aren't re-paid."""

from __future__ import annotations

import json
from pathlib import Path

from radar.digest.base import DigestOutput


class DigestCache:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._store: dict[str, DigestOutput] = {}

    def load(self) -> "DigestCache":
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            raw = {}
        for item_id, val in (raw or {}).items():
            if isinstance(val, dict) and "title_zh" in val and "summary_zh" in val:
                self._store[item_id] = DigestOutput(val["title_zh"], val["summary_zh"])
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            k: {"title_zh": v.title_zh, "summary_zh": v.summary_zh}
            for k, v in self._store.items()
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, item_id: str) -> DigestOutput | None:
        return self._store.get(item_id)

    def put(self, item_id: str, output: DigestOutput) -> None:
        self._store[item_id] = output
