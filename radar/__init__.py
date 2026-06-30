"""MTA News Radar engine: topics.yaml-driven multi-topic news radar.

Pluggable fetchers/scorers, per-topic window, output to data/<topic>/latest.json.
"""

__all__ = ["models", "config", "pipeline", "dedup", "writer", "runner"]
