#!/usr/bin/env python3
"""Post-run source-health check: surface silently-broken sources.

Reads the engine's output (`data/index.json` + each topic's `latest.json`) and
reports every source that came back `status=failed` — i.e. an *enabled* source
the engine tried to fetch and could not. Intentional non-fetches (`skipped` /
`disabled`) and healthy-but-empty sources (`ok` with 0 items, normal for
low-frequency scrape/blog feeds inside a short window) are NOT alerts.

Output targets, in order of usefulness:
  * GitHub Actions `::warning::` annotations (show inline + in the run summary)
  * a Markdown table appended to `$GITHUB_STEP_SUMMARY` (the run's summary page)
  * plain stdout (local runs / logs)

Exit code is always 0: a transient feed failure must never block the daily
Pages deploy. The signal is meant to be *seen*, not to break the build. Pass
`--fail-over N` to exit 1 when the failed-source count is at least N (opt-in,
for anyone who wants CI to go red on systemic breakage).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _load_json(path: Path) -> dict | None:
    """Return parsed JSON, or None if the file is missing/unreadable."""
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def collect_failures(data_dir: Path) -> list[dict[str, str]]:
    """Return one record per failed source across all topics.

    Each record: {topic, source, type, error}. Reads topic files via the
    `data_url` list in index.json; falls back to scanning `<data_dir>/*/latest.json`
    if index.json is absent.
    """
    failures: list[dict[str, str]] = []
    index = _load_json(data_dir / "index.json")

    topic_files: list[Path] = []
    if index and isinstance(index.get("topics"), list):
        for topic in index["topics"]:
            data_url = topic.get("data_url")
            if data_url:
                topic_files.append(data_dir / Path(data_url).relative_to("data")
                                    if str(data_url).startswith("data/")
                                    else data_dir / data_url)
    if not topic_files:
        topic_files = sorted(data_dir.glob("*/latest.json"))

    for topic_file in topic_files:
        topic_data = _load_json(topic_file)
        if not topic_data:
            continue
        topic_name = topic_data.get("name") or topic_file.parent.name
        for health in topic_data.get("source_health", []) or []:
            if health.get("status") == "failed":
                failures.append({
                    "topic": str(topic_name),
                    "source": str(health.get("source_name", "?")),
                    "type": str(health.get("type", "?")),
                    "error": str(health.get("error", "")).strip(),
                })
    return failures


def _emit_github_annotations(failures: list[dict[str, str]]) -> None:
    """Print `::warning::` lines the Actions runner turns into annotations."""
    for f in failures:
        msg = f"[{f['topic']}] source '{f['source']}' ({f['type']}) failed: {f['error']}"
        # Newlines break the annotation format; collapse them.
        print(f"::warning title=Source failed::{msg.replace(chr(10), ' ')}")


def _write_step_summary(failures: list[dict[str, str]], summary_path: Path) -> None:
    """Append a Markdown table to the GitHub Actions step summary."""
    lines = ["", "### 📡 信息源健康检查", ""]
    if not failures:
        lines.append("✅ 所有 enabled 源均正常（无 `status=failed`）。")
    else:
        lines.append(f"⚠️ **{len(failures)} 个源抓取失败**（`skipped`/`disabled` 不计）：")
        lines.append("")
        lines.append("| 主题 | 源 | 类型 | 错误 |")
        lines.append("| --- | --- | --- | --- |")
        for f in failures:
            err = f["error"].replace("|", "\\|")[:160]
            lines.append(f"| {f['topic']} | {f['source']} | {f['type']} | {err} |")
    lines.append("")
    with summary_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report failed (silently-broken) sources")
    parser.add_argument("--data-dir", default="data", help="engine output dir")
    parser.add_argument(
        "--fail-over", type=int, default=0,
        help="exit 1 if failed-source count >= N (0 = never fail, default)",
    )
    args = parser.parse_args(argv)

    failures = collect_failures(Path(args.data_dir))

    if failures:
        print(f"⚠️  {len(failures)} source(s) failed:")
        for f in failures:
            print(f"   [{f['topic']}] {f['source']} ({f['type']}): {f['error']}")
    else:
        print("✅ No failed sources.")

    if os.environ.get("GITHUB_ACTIONS") == "true":
        _emit_github_annotations(failures)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            _write_step_summary(failures, Path(summary))

    if args.fail_over and len(failures) >= args.fail_over:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
