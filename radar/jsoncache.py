"""Shared persistent JSON key-value cache, keyed by Item.id.

Subclasses define how one value serializes to / from a JSON dict via
`_serialize` / `_deserialize`; the tolerant load, pretty-printed save, and
get/put plumbing are shared. Used by the digest layer (DigestCache) and the LLM
relevance scorer (RelevanceCache) — previously two near-identical copies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Generic, TypeVar

V = TypeVar("V")


class JsonKVCache(Generic[V]):
    """A `{item_id: value}` cache persisted as a JSON object on disk."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._store: dict[str, V] = {}

    # --- subclass hooks ---
    def _serialize(self, value: V) -> dict[str, Any]:
        raise NotImplementedError

    def _deserialize(self, raw: dict[str, Any]) -> V | None:
        """Return the value, or None to drop a malformed/incomplete entry."""
        raise NotImplementedError

    # --- shared plumbing ---
    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            raw = {}
        for item_id, val in (raw or {}).items():
            if isinstance(val, dict):
                parsed = self._deserialize(val)
                if parsed is not None:
                    self._store[item_id] = parsed
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: self._serialize(v) for k, v in self._store.items()}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, item_id: str) -> V | None:
        return self._store.get(item_id)

    def put(self, item_id: str, value: V) -> None:
        self._store[item_id] = value
