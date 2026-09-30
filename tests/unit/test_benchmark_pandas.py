"""Unit tests for the pandas weekly-engagement benchmark (Task 13.2, F-F03).

Verifies J2-equivalent aggregation semantics on hand-built fixtures
(weekly grain, Monday weeks, semester mapping, category roll-ups,
positive-only durations, active days, identifier normalization) plus the
end-to-end timed workload on tiny Parquet data and the CLI wiring. Fast
and hermetic: no Spark session, no MongoDB required.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from acadexa.benchmarks.pandas.weekly_engagement import (
    WORKLOAD_ID,
    aggregate_weekly_engagement,
    load_lms_events_frame,
    run_weekly_engagement_pandas,
)
from acadexa.benchmarks.runner import ENGINE_PANDAS
import scripts.run_benchmarks as run_benchmarks_script


def _meta_events() -> pd.DataFrame:
    """Hand-built events with dict metadata, mixed case and null duration."""
    return pd.DataFrame(
        [
            {
                "timestamp": "2024-07-15T10:00:00",
                "meta": {"student_id": " stu1 ", "course_id": " cs101 ", "school": "ENG"},
                "activity_type": "VIDEO_VIEW",
                "duration_sec": 300,
            },
            {
                "timestamp": "2024-07-15T11:00:00",
                "meta": {"student_id": "STU1", "course_id": "CS101", "school": "ENG"},
                "activity_type": "LOGIN",
                "duration_sec": None,
            },
            {
                "timestamp": "2024-07-16T10:00:00",
                "meta": {"student_id": "STU1", "course_id": "CS101", "school": "ENG"},
                "activity_type": "QUIZ_ATTEMPT",
                "duration_sec": -5,
            },
            {
                "timestamp": "2024-07-22T10:00:00",
                "meta": {"student_id": "STU1", "course_id": "CS101", "school": "ENG"},
                "activity_type": "FORUM_POST",
                "duration_sec": 60,
            },
            {
                "timestamp": "2024-07-15T12:00:00",
                "meta": {"student_id": "STU2", "course_id": "CS101", "school": "ENG"},
                "activity_type": "VIDEO_VIEW",
                "duration_sec": 100,
            },
            {
                "timestamp": "2023-01-02T10:00:00",
                "meta": {"student_id": "STU1", "course_id": "CS101", "school": "ENG"},
                "activity_type": "LOGIN",
                "duration_sec": 10,
            },
        ]
    )


def _row(frame: pd.DataFrame, student: str, week: str) -> pd.Series:
    """Select one weekly group row by student and ISO week_start."""
    matches = frame[
        (frame["student_id"] == student)
        & (frame["week_start"].astype(str) == week)
    ]
    assert len(matches) == 1
    return matches.iloc[0]


def test_aggregate_weekly_grain_and_normalization() -> None:
    """Aggregation groups Monday weeks with normalized identifiers."""
    summary = aggregate_weekly_engagement(_meta_events())
    assert len(summary) == 4
    assert list(summary.columns)[:6] == [
        "student_id",
        "course_id",
        "school",
        "semester_id",
        "week_start",
        "week_number",
    ]
    assert set(summary["student_id"]) == {"STU1", "STU2"}
    assert (summary["week_number"] == 1).sum() == 3  # S1 week + UNKNOWN week
    assert (
        summary.loc[summary["week_start"].astype(str) == "2024-07-22", "week_number"]
        == 2
    ).all()


def test_aggregate_metrics_match_j2_semantics() -> None:
    """Counts, positive-only durations, active days and categories match J2."""
    summary = aggregate_weekly_engagement(_meta_events())
    first = _row(summary, "STU1", "2024-07-15")
    assert first["total_events"] == 3
    assert first["total_duration_sec"] == 300.0  # null and negative contribute 0
    assert first["active_days"] == 2
    assert first["content_views"] == 1
    assert first["assessment_events"] == 1
    assert first["access_events"] == 1
    assert first["participation_events"] == 0
    assert first["video_views"] == 1
    assert first["quiz_attempts"] == 1
    assert first["logins"] == 1
    assert first["semester_id"] == "S1"

    second = _row(summary, "STU1", "2024-07-22")
    assert (second["total_events"], second["forum_posts"]) == (1, 1)
    assert second["participation_events"] == 1

    unknown = _row(summary, "STU1", "2023-01-02")
    assert unknown["semester_id"] == "UNKNOWN"
    assert unknown["week_number"] == 1


def test_aggregate_flat_columns_variant() -> None:
    """Events without a meta struct aggregate identically."""
    flat = pd.DataFrame(
        [
            {
                "timestamp": "2024-07-15T10:00:00",
                "student_id": "STU1",
                "course_id": "CS101",
                "school": "ENG",
                "activity_type": "VIDEO_VIEW",
                "duration_sec": 300,
            },
            {
                "timestamp": "2024-07-15T11:00:00",
                "student_id": "STU1",
                "course_id": "CS101",
                "school": "ENG",
                "activity_type": "LOGIN",
                "duration_sec": None,
            },
        ]
    )
    summary = aggregate_weekly_engagement(flat)
    assert len(summary) == 1
    assert summary.iloc[0]["total_events"] == 2
    assert summary.iloc[0]["total_duration_sec"] == 300.0
    assert summary.iloc[0]["active_days"] == 1


def test_aggregate_empty_frame() -> None:
    """Empty input yields an empty summary without errors."""
    summary = aggregate_weekly_engagement(
        pd.DataFrame(
            columns=["timestamp", "meta", "activity_type", "duration_sec"]
        )
    )
    assert len(summary) == 0


def test_load_missing_path_raises() -> None:
    """Missing input paths fail fast instead of benchmarking nothing."""
    with pytest.raises(FileNotFoundError, match="not found"):
        load_lms_events_frame("data/does_not_exist")


def test_run_weekly_engagement_pandas_end_to_end(tmp_path: Path) -> None:
    """Timed workload on tiny Parquet data records measured results."""
    input_path = tmp_path / "lms_events"
    _meta_events().to_parquet(input_path)

    result = run_weekly_engagement_pandas(input_path)
    assert result.workload_id == WORKLOAD_ID
    assert result.engine == ENGINE_PANDAS
    assert result.success is True
    assert result.error is None
    assert result.input_rows == 6
    assert result.output_rows == 4
    assert result.duration_sec >= 0.0
    assert result.peak_memory_mb is not None and result.peak_memory_mb >= 0.0


def test_run_benchmarks_cli_wires_pandas_workload(tmp_path: Path) -> None:
    """CLI parses args, runs pandas and saves the raw run manifest."""
    args = run_benchmarks_script.parse_args(
        ["--workload", "weekly_lms_engagement", "--engine", "pandas"]
    )
    assert args.workload == "weekly_lms_engagement"
    assert args.engine == "pandas"

    input_path = tmp_path / "lms_events"
    _meta_events().to_parquet(input_path)
    manifest_path = tmp_path / "benchmark_run_manifest.json"
    exit_code = run_benchmarks_script.main(
        [
            "--workload",
            "weekly_lms_engagement",
            "--engine",
            "pandas",
            "--input-path",
            str(input_path),
            "--manifest-path",
            str(manifest_path),
            "--quiet",
        ]
    )
    assert exit_code == 0
    assert manifest_path.exists()

    from acadexa.benchmarks.runner import BenchmarkRun

    run = BenchmarkRun.load(manifest_path)
    assert len(run.results) == 1
    assert run.results[0].engine == ENGINE_PANDAS
    assert run.results[0].input_rows == 6
    assert "pandas_version" in run.environment
