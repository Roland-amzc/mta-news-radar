#!/usr/bin/env python3
"""CLI entry point for the multi-topic news radar engine.

Examples:
    python run_radar.py                       # all topics -> data/<topic>/latest.json
    python run_radar.py --only frontier       # one topic
    python run_radar.py --only frontier,quant_factor --max-feeds 3
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as dtparser

from radar.models import ConfigError
from radar.runner import run_all


def _parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    dt = dtparser.parse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-topic news radar engine")
    parser.add_argument("--config", default="topics.yaml", help="path to topics.yaml")
    parser.add_argument("--output-dir", default="data", help="output directory")
    parser.add_argument("--only", default=None, help="comma-separated topic ids to run")
    parser.add_argument("--max-feeds", type=int, default=None, help="cap fetched sources per topic")
    parser.add_argument("--now", default=None, help="override 'now' (ISO8601), for testing")
    args = parser.parse_args(argv)

    only = [s.strip() for s in args.only.split(",") if s.strip()] if args.only else None
    now = _parse_now(args.now)

    try:
        results = run_all(
            Path(args.config), Path(args.output_dir), now,
            only=only, max_feeds=args.max_feeds,
        )
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if not results:
        print("no topics matched", file=sys.stderr)
        return 1
    if all(r.topic_error for r in results):
        print("all topics failed", file=sys.stderr)
        return 1

    for r in results:
        flag = "ERROR" if r.topic_error else f"{len(r.items)} items"
        print(f"  {r.topic_id:14} {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
