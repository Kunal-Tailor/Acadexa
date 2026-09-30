"""Unit tests for the PySpark feature-table join benchmark (Task 13.5, F-F03).

Verifies the timed J3 workload on tiny Parquet data and the failure
path. Uses a module-scoped local Spark session shared across tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from acadexa.benchmarks.runner import ENGINE_PYSPARK
from acadexa.benchmarks.spark.feature_join import (
    WORKLOAD_ID,
    run_feature_table_join_spark,
)
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for join benchmark tests."""
    cfg = SparkRuntimeConfig(app_name="TestBenchmarkJoinSpark", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def _write_domain_parquet(spark_session: SparkSession, base: Path) -> None:
    """Write tiny cleaned-shaped domain datasets for the join."""
    spark_session.createDataFrame(
        [
            ("S1", "C1", "S1", 30, 30, 40, "B"),
            ("S2", "C2", "S1", 10, 10, 10, "C"),
        ],
        ["student_id", "course_id", "semester_id", "internal_marks",
         "midterm_marks", "endterm_marks", "final_grade"],
    ).write.mode("overwrite").parquet(str(base / "academic_records"))
    spark_session.createDataFrame(
        [
            ("S1", "C1", "S1", "2024-07-15", 4, 3),
            ("S1", "C1", "S1", "2024-07-22", 2, 2),
            ("S2", "C2", "S1", "2024-07-15", 4, 4),
        ],
        ["student_id", "course_id", "semester_id", "week_start",
         "classes_conducted", "classes_attended"],
    ).write.mode("overwrite").parquet(str(base / "attendance"))
    spark_session.createDataFrame(
        [
            ("S1", "C1", "S1", "A01", "ASSIGNMENT", "2024-08-01", "ON_TIME", 16.0, 20.0, 1),
            ("S1", "C1", "S1", "A02", "ASSIGNMENT", "2024-08-01", "LATE", 10.0, 20.0, 2),
            ("S2", "C2", "S1", "A01", "ASSIGNMENT", "2024-08-01", "ON_TIME", 9.0, 10.0, 1),
        ],
        ["student_id", "course_id", "semester_id", "item_id", "item_type",
         "due_date", "status", "score", "max_score", "attempts"],
    ).write.mode("overwrite").parquet(str(base / "coursework"))
    spark_session.createDataFrame(
        [
            ("S1", "C1", "S1", "2024-07-15", 10, 600, 2, 5, 3, 0, 2, 4, 1, 1, 1, 0, 2),
            ("S2", "C2", "S1", "2024-07-15", 20, 900, 3, 8, 4, 1, 3, 2, 0, 1, 1, 1, 3),
        ],
        ["student_id", "course_id", "semester_id", "week_start", "total_events",
         "total_duration_sec", "active_days", "content_views", "assessment_events",
         "participation_events", "access_events", "video_views", "quiz_attempts",
         "assignment_views", "assignment_submissions", "forum_posts", "logins"],
    ).write.mode("overwrite").parquet(str(base / "lms_weekly_engagement"))


def test_run_feature_table_join_spark_end_to_end(
    spark_session: SparkSession, tmp_path: Path
) -> None:
    """Timed J3 join workload on tiny Parquet data records measured results."""
    base = tmp_path / "processed"
    output_path = tmp_path / "student_features"
    _write_domain_parquet(spark_session, base)

    result = run_feature_table_join_spark(
        base, output_path, spark=spark_session
    )
    assert result.workload_id == WORKLOAD_ID
    assert result.engine == ENGINE_PYSPARK
    assert result.success is True
    assert result.error is None
    assert result.input_rows == 2 + 3 + 3 + 2
    assert result.output_rows == 2
    assert result.duration_sec >= 0.0
    assert result.peak_memory_mb is None  # JVM execution: not measurable here
    assert result.extra["join_semantics"] == "outer"
    assert output_path.exists()


def test_run_feature_table_join_spark_missing_input(
    spark_session: SparkSession, tmp_path: Path
) -> None:
    """Missing input records failure without raising."""
    result = run_feature_table_join_spark(
        tmp_path / "does_not_exist",
        tmp_path / "out",
        spark=spark_session,
    )
    assert result.success is False
    assert result.input_rows == 0
    assert result.error is not None
