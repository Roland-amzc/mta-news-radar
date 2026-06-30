"""NoopDigester: the degraded path (no API key / digest disabled)."""

from __future__ import annotations

from radar.digest.base import DigestOutput, DigestRequest


class NoopDigester:
    def digest(self, requests: list[DigestRequest]) -> dict[str, DigestOutput]:
        return {}
