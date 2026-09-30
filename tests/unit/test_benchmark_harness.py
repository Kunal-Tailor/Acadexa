"""Unit tests for the J8 benchmark harness (Task 13.1, rules.md §30).

Covers workload registration/lookup, environment capture, timed
execution with optional memory measurement, success/failure result
recording and run-manifest save/load round-trips. Fast and hermetic:
no Spark session, no MongoDB, no generated data required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.benchmarks.runner import (
    DEFAULT_BENCHMARK_MANIFEST_PATH,
    ENGINE_PANDAS,
    WORKLOADS,
    BenchmarkResult,
    BenchmarkRun,
    capture_environment,
    get_workload,
    new_run_id,
    run_benchmark,
    run_timed,
)


def test_workload_registry_defines_weekly_engagement() -> None:
    """The repeatable workload definition names grain, input and metrics."""
    assert "weekly_lms_engagement" in WORKLOADS
    workload = get_workload("weekly_lms_engagement")
    assert workload.title == "Weekly LMS engagement aggregation"
    assert "student_id" in workload.output_grain
    assert "week_start" in workload.output_grain
    assert "total_events" in workload.metrics
    assert "active_days" in workload.metrics


def test_get_workload_rejects_unknown_id() -> None:
    """Unknown workload ids fail fast instead of running the wrong task."""
    with pytest.raises(KeyError, match="Unknown benchmark workload"):
        get_workload("nonexistent_workload")


def test_capture_environment_records_interpretable_context() -> None:
    """Environment capture includes interpreter, platform and package versions."""
    env = capture_environment({"workload": "weekly_lms_engagement"})
    for key in ("python_version", "platform", "cpu_count", "pandas_version"):
        assert key in env
    assert env["workload"] == "weekly_lms_engagement"
    assert isinstance(env["python_version"], str) and env["python_version"]


def test_run_timed_measures_duration_and_memory() -> None:
    """Timed execution reports wall time and Python-allocator peak."""
    def _work() -> str:
        return "done"

    value, duration, peak_mb = run_timed(_work)
    assert value == "done"
    assert duration >= 0.0
    assert peak_mb is not None and peak_mb >= 0.0

    _, _, disabled = run_timed(_work, measure_memory=False)
    assert disabled is None


def test_run_benchmark_records_success() -> None:
    """Successful engine runs record rows, timing and metadata."""
    def _engine() -> tuple[int, int]:
        return 100, 10

    result = run_benchmark(
        "weekly_lms_engagement", ENGINE_PANDAS, _engine, extra={"note": "test"}
    )
    assert isinstance(result, BenchmarkResult)
    assert result.success is True
    assert result.error is None
    assert (result.input_rows, result.output_rows) == (100, 10)
    assert result.duration_sec >= 0.0
    assert result.extra["note"] == "test"
    assert result.to_dict()["workload_id"] == "weekly_lms_engagement"


def test_run_benchmark_records_failure_without_raising() -> None:
    """Engine failures are observations, not test crashes."""
    def _broken() -> tuple[int, int]:
        raise RuntimeError("engine exploded")

    result = run_benchmark("weekly_lms_engagement", ENGINE_PANDAS, _broken)
    assert result.success is False
    assert result.input_rows == 0
    assert result.output_rows == 0
    assert "RuntimeError" in (result.error or "")
    assert result.peak_memory_mb is None


def test_run_benchmark_rejects_unknown_workload() -> None:
    """Unknown workloads fail fast before executing anything."""
    with pytest.raises(KeyError, match="Unknown benchmark workload"):
        run_benchmark("nope", ENGINE_PANDAS, lambda: (0, 0))


def test_benchmark_run_manifest_roundtrip(tmp_path: Path) -> None:
    """Run manifests save and load with environment and results intact."""
    run = BenchmarkRun(
        run_id=new_run_id(),
        started_at="2026-01-01T00:00:00+00:00",
        environment={"python_version": "3.11.9"},
        results=[
            BenchmarkResult(
                workload_id="weekly_lms_engagement",
                engine=ENGINE_PANDAS,
                duration_sec=1.234,
                input_rows=100,
                output_rows=10,
                peak_memory_mb=12.5,
            )
        ],
    )
    assert run.run_id.startswith("bench_")
    target = run.save(tmp_path / "manifests" / "benchmark_run_manifest.json")
    assert target.exists()

    loaded = BenchmarkRun.load(target)
    assert loaded.run_id == run.run_id
    assert loaded.environment["python_version"] == "3.11.9"
    assert len(loaded.results) == 1
    assert loaded.results[0].engine == ENGINE_PANDAS
    assert loaded.results[0].input_rows == 100


def test_default_manifest_path_targets_benchmark_reports() -> None:
    """Raw run manifests default under reports/benchmarks/."""
    assert DEFAULT_BENCHMARK_MANIFEST_PATH == Path(
        "reports/benchmarks/benchmark_run_manifest.json"
    )
