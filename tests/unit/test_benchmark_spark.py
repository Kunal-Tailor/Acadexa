"""Unit tests for the PySpark weekly-engagement benchmark (Task 13.4, F-F03).

Verifies the timed J2 workload on tiny Parquet data and the failure
path. Uses a module-scoped local Spark session shared across tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from acadexa.benchmarks.runner import ENGINE_PYSPARK
from acadexa.benchmarks.spark.weekly_engagement import (
    WORKLOAD_ID,
    run_weekly_engagement_spark,
)
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for benchmark tests."""
    cfg = SparkRuntimeConfig(app_name="TestBenchmarkSpark", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def _write_events_parquet(spark_session: SparkSession, path: Path) -> None:
    """Write six hand-built flat events covering two weeks and S1."""
    rows = [
        ("2024-07-15 10:00:00", "STU1", "CS101", "ENG", "VIDEO_VIEW", 300),
        ("2024-07-15 11:00:00", "STU1", "CS101", "ENG", "LOGIN", None),
        ("2024-07-16 10:00:00", "STU1", "CS101", "ENG", "QUIZ_ATTEMPT", -5),
        ("2024-07-22 10:00:00", "STU1", "CS101", "ENG", "FORUM_POST", 60),
        ("2024-07-15 12:00:00", "STU2", "CS101", "ENG", "VIDEO_VIEW", 100),
        ("2023-01-02 10:00:00", "STU1", "CS101", "ENG", "LOGIN", 10),
    ]
    frame = spark_session.createDataFrame(
        rows,
        ["timestamp", "student_id", "course_id", "school", "activity_type", "duration_sec"],
    )
    frame.write.mode("overwrite").parquet(str(path))


def test_run_weekly_engagement_spark_end_to_end(
    spark_session: SparkSession, tmp_path: Path
) -> None:
    """Timed J2 workload on tiny Parquet data records measured results."""
    input_path = tmp_path / "lms_events"
    output_path = tmp_path / "weekly_engagement"
    _write_events_parquet(spark_session, input_path)

    result = run_weekly_engagement_spark(
        input_path, output_path, spark=spark_session
    )
    assert result.workload_id == WORKLOAD_ID
    assert result.engine == ENGINE_PYSPARK
    assert result.success is True
    assert result.error is None
    assert result.input_rows == 6
    assert result.output_rows == 4
    assert result.duration_sec >= 0.0
    assert result.peak_memory_mb is None  # JVM execution: not measurable here
    assert result.extra["spark_driver_memory"] == "2g"
    assert output_path.exists()


def test_run_weekly_engagement_spark_missing_input(
    spark_session: SparkSession, tmp_path: Path
) -> None:
    """Missing input records failure without raising."""
    result = run_weekly_engagement_spark(
        tmp_path / "does_not_exist",
        tmp_path / "out",
        spark=spark_session,
    )
    assert result.success is False
    assert result.input_rows == 0
    assert result.error is not None


def test_run_benchmarks_cli_parses_all_engines(tmp_path: Path) -> None:
    """CLI accepts every engine with per-engine path options."""
    import scripts.run_benchmarks as run_benchmarks_script

    for engine in ("pandas", "mongodb", "pyspark"):
        args = run_benchmarks_script.parse_args(["--engine", engine])
        assert args.engine == engine
    args = run_benchmarks_script.parse_args(
        ["--output-path", str(tmp_path), "--collection", "lms_events"]
    )
    assert args.output_path == str(tmp_path)
    assert args.collection == "lms_events"
