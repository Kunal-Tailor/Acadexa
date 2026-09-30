"""Benchmark result publication (Task 13.6, rules.md §30, architecture.md §20).

Builds measured benchmark output — dataset size, execution time, memory
observations where practical and environment information — from a J8 run
manifest, as structured JSON and Markdown. Per benchmark rules the output
records measurements only: it states comparability caveats (different
input sources and join scopes per engine) and draws no technology
conclusions. Interpretation is left to the reader.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from acadexa.benchmarks.runner import (
    BENCHMARK_MANIFEST_VERSION,
    WORKLOADS,
    BenchmarkRun,
)

logger = logging.getLogger(__name__)

REPORT_VERSION: str = "1.0.0"


def _format_memory(value: float | None) -> str:
    """Render peak memory observably (explicit n/a when not measured)."""
    return f"{value} MB" if value is not None else "n/a"


def _format_status(result: dict[str, Any]) -> str:
    """Render success or the recorded failure reason."""
    if result.get("success"):
        return "SUCCESS"
    error = result.get("error") or "unknown error"
    return f"FAILED: {error}"


def build_benchmark_report(run: BenchmarkRun) -> dict[str, Any]:
    """Build the structured report document from a benchmark run."""
    workloads = []
    for workload_id in sorted({r.workload_id for r in run.results}):
        definition = WORKLOADS.get(workload_id)
        rows = [
            {
                "engine": r.engine,
                "duration_sec": r.duration_sec,
                "input_rows": r.input_rows,
                "output_rows": r.output_rows,
                "peak_memory_mb": r.peak_memory_mb,
                "status": _format_status(r.to_dict()),
                "extra": dict(r.extra),
            }
            for r in run.results
            if r.workload_id == workload_id
        ]
        workloads.append(
            {
                "workload_id": workload_id,
                "title": definition.title if definition else workload_id,
                "description": definition.description if definition else "",
                "output_grain": definition.output_grain if definition else "",
                "results": rows,
            }
        )
    return {
        "report_version": REPORT_VERSION,
        "manifest_version": BENCHMARK_MANIFEST_VERSION,
        "run_id": run.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": dict(run.environment),
        "workloads": workloads,
        "notes": [
            "Measured results from the local project environment; "
            "no technology conclusions are drawn.",
            "Each engine includes its own read path: pandas/Spark read "
            "Parquet datasets, MongoDB aggregates its serving collections.",
            "Feature-table join scopes differ by engine holdings: "
            "pandas/Spark join four domains including LMS weekly "
            "aggregates, MongoDB joins the three operational collections.",
            "Memory figures are Python-allocator peaks where measured; "
            "JVM execution memory is not captured (driver memory recorded).",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report document as Markdown."""
    lines = [
        "# Acadexa Benchmark Report",
        "",
        f"Run ID: `{report['run_id']}`",
        f"Generated: {report['generated_at']}",
        "",
        "## Environment",
        "",
    ]
    for key, value in report["environment"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    for workload in report["workloads"]:
        lines.extend(
            [
                f"## {workload['title']} (`{workload['workload_id']}`)",
                "",
                workload["description"],
                "",
                f"Output grain: `{workload['output_grain']}`",
                "",
                "| Engine | Duration (s) | Input rows | Output rows | Peak memory | Status |",
                "| --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for row in workload["results"]:
            lines.append(
                f"| {row['engine']} | {row['duration_sec']} | {row['input_rows']} | "
                f"{row['output_rows']} | {_format_memory(row['peak_memory_mb'])} | "
                f"{row['status']} |"
            )
        lines.append("")
    lines.extend(["## Notes", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    lines.append("")
    return "\n".join(lines)


def save_report(report: dict[str, Any], base_path: str | Path) -> tuple[Path, Path]:
    """Save the report as JSON and Markdown next to ``base_path`` stem."""
    base = Path(base_path)
    json_path = base.with_name(f"{base.stem}_report.json")
    md_path = base.with_name(f"{base.stem}_report.md")
    for target, content in (
        (json_path, json.dumps(report, indent=2)),
        (md_path, render_markdown(report)),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    logger.info("Saved benchmark report to %s and %s", json_path, md_path)
    return json_path, md_path
