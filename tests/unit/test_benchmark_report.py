"""Unit tests for benchmark result publication (Task 13.6, rules.md §30).

Covers structured report building, Markdown rendering with dataset
size/timing/memory/environment context, report saving and the
report-only CLI mode. Uses fabricated run metadata (no engines run
here); live CLI workload tests live with their engine test files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.benchmarks.report import (
    REPORT_VERSION,
    build_benchmark_report,
    render_markdown,
    save_report,
)
from acadexa.benchmarks.runner import (
    BenchmarkResult,
    BenchmarkRun,
)


def _run() -> BenchmarkRun:
    """Fabricated two-workload run with mixed success and memory coverage."""
    return BenchmarkRun(
        run_id="bench_20260101_000000",
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:05:00+00:00",
        duration_sec=300.0,
        environment={"python_version": "3.11.9", "platform": "test-os"},
        results=[
            BenchmarkResult(
                workload_id="weekly_lms_engagement",
                engine="pandas",
                duration_sec=45.144,
                input_rows=227662,
                output_rows=14048,
                peak_memory_mb=103.465,
            ),
            BenchmarkResult(
                workload_id="weekly_lms_engagement",
                engine="mongodb",
                duration_sec=0.849,
                input_rows=22357,
                output_rows=1170,
                peak_memory_mb=3.045,
            ),
            BenchmarkResult(
                workload_id="feature_table_join",
                engine="pyspark",
                duration_sec=60.0,
                input_rows=1000,
                output_rows=100,
                peak_memory_mb=None,
            ),
            BenchmarkResult(
                workload_id="feature_table_join",
                engine="mongodb",
                duration_sec=1.0,
                input_rows=0,
                output_rows=0,
                success=False,
                error="MongoConnectionError: down",
            ),
        ],
    )


def test_build_benchmark_report_structure() -> None:
    """Report groups per-engine results under workload definitions."""
    report = build_benchmark_report(_run())
    assert report["report_version"] == REPORT_VERSION
    assert report["run_id"] == "bench_20260101_000000"
    assert report["environment"]["python_version"] == "3.11.9"
    assert [w["workload_id"] for w in report["workloads"]] == [
        "feature_table_join",
        "weekly_lms_engagement",
    ]
    weekly = next(w for w in report["workloads"] if w["workload_id"] == "weekly_lms_engagement")
    assert weekly["title"] == "Weekly LMS engagement aggregation"
    assert [r["engine"] for r in weekly["results"]] == ["pandas", "mongodb"]
    pandas_row = weekly["results"][0]
    assert (pandas_row["input_rows"], pandas_row["output_rows"]) == (227662, 14048)
    assert pandas_row["status"] == "SUCCESS"
    join = next(w for w in report["workloads"] if w["workload_id"] == "feature_table_join")
    failed = next(r for r in join["results"] if r["engine"] == "mongodb")
    assert failed["status"] == "FAILED: MongoConnectionError: down"
    assert "no technology conclusions are drawn" in " ".join(report["notes"])


def test_render_markdown_tables_and_context() -> None:
    """Markdown carries tables, environment and caveats without conclusions."""
    text = render_markdown(build_benchmark_report(_run()))
    assert text.startswith("# Acadexa Benchmark Report")
    assert "bench_20260101_000000" in text
    assert "python_version: 3.11.9" in text
    assert "| pandas | 45.144 | 227662 | 14048 | 103.465 MB | SUCCESS |" in text
    assert "| pyspark | 60.0 | 1000 | 100 | n/a | SUCCESS |" in text
    assert "FAILED: MongoConnectionError: down" in text
    assert "no technology conclusions are drawn" in text
    for banned in ("winner", "fastest engine", "recommend", "should use"):
        assert banned not in text.lower()


def test_save_report_writes_json_and_markdown(tmp_path: Path) -> None:
    """Report saving writes sibling JSON and Markdown files."""
    manifest_path = tmp_path / "benchmark_run_manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    json_path, md_path = save_report(build_benchmark_report(_run()), manifest_path)
    assert json_path == tmp_path / "benchmark_run_manifest_report.json"
    assert md_path == tmp_path / "benchmark_run_manifest_report.md"
    assert json_path.exists() and md_path.exists()

    import json as json_module

    saved = json_module.loads(json_path.read_text(encoding="utf-8"))
    assert saved["run_id"] == "bench_20260101_000000"
    assert "| pandas | 45.144 | 227662 | 14048 | 103.465 MB | SUCCESS |" in md_path.read_text(
        encoding="utf-8"
    )


def test_run_benchmarks_report_only_regenerates(tmp_path: Path) -> None:
    """--report-only rebuilds report files from a manifest without running."""
    import scripts.run_benchmarks as run_benchmarks_script

    manifest_path = tmp_path / "benchmark_run_manifest.json"
    run = _run()
    run.save(manifest_path)

    exit_code = run_benchmarks_script.main(
        [
            "--report-only",
            "--manifest-path",
            str(manifest_path),
            "--quiet",
        ]
    )
    assert exit_code == 0
    assert (tmp_path / "benchmark_run_manifest_report.json").exists()
    assert (tmp_path / "benchmark_run_manifest_report.md").exists()


def test_run_benchmarks_cli_feature_join_mongodb(tmp_path: Path) -> None:
    """CLI runs the MongoDB join engine against live data and reports."""
    from acadexa.database import MongoDBConfig, check_connection
    import scripts.run_benchmarks as run_benchmarks_script

    if not check_connection(config=MongoDBConfig.from_env()):
        pytest.skip("MongoDB is not reachable in current environment")

    manifest_path = tmp_path / "benchmark_run_manifest.json"
    exit_code = run_benchmarks_script.main(
        [
            "--workload",
            "feature_table_join",
            "--engine",
            "mongodb",
            "--manifest-path",
            str(manifest_path),
            "--quiet",
        ]
    )
    assert exit_code == 0
    run = BenchmarkRun.load(manifest_path)
    assert run.results[0].engine == "mongodb"
    assert run.results[0].input_rows > 0
    assert (tmp_path / "benchmark_run_manifest_report.json").exists()
    assert (tmp_path / "benchmark_run_manifest_report.md").exists()
