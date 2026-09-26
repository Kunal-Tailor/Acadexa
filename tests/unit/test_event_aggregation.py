"""Unit tests for Spark LMS event aggregation job - J2 (tasks 7.5 & 7.6, rules.md §17, §18)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from acadexa.processing.jobs.event_aggregation import (
    APPROVED_ACTIVITY_CATEGORIES,
    J2Config,
    J2Result,
    aggregate_weekly_lms_events,
    build_semester_expressions,
    run_j2_event_aggregation,
)
import acadexa.processing.jobs.event_aggregation as j2_module
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for J2 aggregation tests."""
    cfg = SparkRuntimeConfig(app_name="TestEventAggregation", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def test_j2_config_defaults() -> None:
    """Verify default parameters of J2Config."""
    cfg = J2Config()
    assert cfg.input_path == Path("data/processed/lms_events")
    assert cfg.raw_fallback_path == Path("data/raw/lms_events")
    assert cfg.output_path == Path("data/processed/lms_weekly_engagement")
    assert cfg.save_parquet is True
    assert cfg.partition_by == ("semester_id",)


def test_build_semester_expressions(spark_session: SparkSession) -> None:
    """Verify mapping of calendar week_start to semester_id and week_number."""
    dates = [
        ("2024-07-15", "S1", 1),
        ("2024-08-05", "S1", 4),
        ("2025-01-06", "S2", 1),
        ("2025-07-14", "S3", 1),
        ("2026-01-05", "S4", 1),
        ("2026-04-20", "S4", 16),
    ]
    df = spark_session.createDataFrame([(d[0],) for d in dates], ["week_start"])
    df = df.withColumn("week_start", F.to_date("week_start"))

    sem_col, week_num_col = build_semester_expressions()
    res = df.withColumn("semester_id", sem_col).withColumn("week_number", week_num_col)

    rows = res.collect()
    for row, (_, exp_sem, exp_wk) in zip(rows, dates):
        assert row["semester_id"] == exp_sem
        assert row["week_number"] == exp_wk


def test_aggregate_weekly_lms_events_multi_day_active_days(
    spark_session: SparkSession,
) -> None:
    """Verify active_days calculation correctly counts distinct event dates in week."""
    # 5 events across 3 distinct days in the week starting 2024-07-15 (Monday)
    data = [
        # Monday (2 events)
        ("2024-07-15 09:00:00", "STU001", "CS101", "ENG", "LOGIN", 0),
        ("2024-07-15 09:30:00", "STU001", "CS101", "ENG", "VIDEO_VIEW", 1200),
        # Wednesday (1 event)
        ("2024-07-17 14:00:00", "STU001", "CS101", "ENG", "PDF_VIEW", 600),
        # Friday (2 events)
        ("2024-07-19 16:00:00", "STU001", "CS101", "ENG", "QUIZ_ATTEMPT", 0),
        ("2024-07-19 16:30:00", "STU001", "CS101", "ENG", "LOGOUT", 0),
    ]
    schema = StructType(
        [
            StructField("timestamp", StringType(), False),
            StructField("student_id", StringType(), False),
            StructField("course_id", StringType(), False),
            StructField("school", StringType(), False),
            StructField("activity_type", StringType(), False),
            StructField("duration_sec", LongType(), False),
        ]
    )
    df = spark_session.createDataFrame(data, schema).withColumn(
        "timestamp", F.to_timestamp("timestamp")
    )

    agg_df = aggregate_weekly_lms_events(df)
    rows = agg_df.collect()

    assert len(rows) == 1
    row = rows[0]
    assert row["student_id"] == "STU001"
    assert row["course_id"] == "CS101"
    assert str(row["week_start"]) == "2024-07-15"
    assert row["semester_id"] == "S1"
    assert row["week_number"] == 1
    assert row["total_events"] == 5
    assert row["active_days"] == 3  # Mon, Wed, Fri
    assert row["total_duration_sec"] == 1800  # 1200 + 600


def test_aggregate_weekly_lms_events_categories_and_breakdown(
    spark_session: SparkSession,
) -> None:
    """Verify approved activity categories and specific event breakdowns."""
    data = [
        # Content views: VIDEO_VIEW, PDF_VIEW, RESOURCE_DOWNLOAD
        ("2024-07-15 10:00:00", "STU001", "CS101", "ENG", "VIDEO_VIEW", 1000),
        ("2024-07-15 11:00:00", "STU001", "CS101", "ENG", "PDF_VIEW", 500),
        ("2024-07-15 12:00:00", "STU001", "CS101", "ENG", "RESOURCE_DOWNLOAD", 0),
        # Assessment: QUIZ_ATTEMPT, ASSIGNMENT_SUBMISSION
        ("2024-07-16 10:00:00", "STU001", "CS101", "ENG", "QUIZ_ATTEMPT", 0),
        ("2024-07-16 11:00:00", "STU001", "CS101", "ENG", "ASSIGNMENT_SUBMISSION", 0),
        # Participation: FORUM_POST
        ("2024-07-17 10:00:00", "STU001", "CS101", "ENG", "FORUM_POST", 0),
        # Access: LOGIN, LOGOUT
        ("2024-07-17 09:00:00", "STU001", "CS101", "ENG", "LOGIN", 0),
        ("2024-07-17 12:00:00", "STU001", "CS101", "ENG", "LOGOUT", 0),
    ]
    schema = StructType(
        [
            StructField("timestamp", StringType(), False),
            StructField("student_id", StringType(), False),
            StructField("course_id", StringType(), False),
            StructField("school", StringType(), False),
            StructField("activity_type", StringType(), False),
            StructField("duration_sec", LongType(), False),
        ]
    )
    df = spark_session.createDataFrame(data, schema).withColumn(
        "timestamp", F.to_timestamp("timestamp")
    )

    agg_df = aggregate_weekly_lms_events(df)
    row = agg_df.first()

    assert row["total_events"] == 8
    # Approved category roll-ups
    assert row["content_views"] == 3
    assert row["assessment_events"] == 2
    assert row["participation_events"] == 1
    assert row["access_events"] == 2
    # Specific breakdowns
    assert row["video_views"] == 1
    assert row["quiz_attempts"] == 1
    assert row["assignment_submissions"] == 1
    assert row["forum_posts"] == 1
    assert row["logins"] == 1


def test_aggregate_weekly_lms_events_multi_course_and_week(
    spark_session: SparkSession,
) -> None:
    """Verify distinct grouping across courses and distinct semester weeks."""
    data = [
        # Student 1, Course 1, Week 1
        ("2024-07-15 10:00:00", "STU001", "CS101", "ENG", "LOGIN", 0),
        # Student 1, Course 2, Week 1
        ("2024-07-16 10:00:00", "STU001", "MATH101", "SCI", "VIDEO_VIEW", 600),
        # Student 1, Course 1, Week 2
        ("2024-07-22 10:00:00", "STU001", "CS101", "ENG", "QUIZ_ATTEMPT", 0),
    ]
    schema = StructType(
        [
            StructField("timestamp", StringType(), False),
            StructField("student_id", StringType(), False),
            StructField("course_id", StringType(), False),
            StructField("school", StringType(), False),
            StructField("activity_type", StringType(), False),
            StructField("duration_sec", LongType(), False),
        ]
    )
    df = spark_session.createDataFrame(data, schema).withColumn(
        "timestamp", F.to_timestamp("timestamp")
    )

    agg_df = aggregate_weekly_lms_events(df)
    rows = agg_df.collect()

    assert len(rows) == 3
    keys = {(r["student_id"], r["course_id"], str(r["week_start"])) for r in rows}
    assert ("STU001", "CS101", "2024-07-15") in keys
    assert ("STU001", "MATH101", "2024-07-15") in keys
    assert ("STU001", "CS101", "2024-07-22") in keys


def test_run_j2_event_aggregation_end_to_end(
    tmp_path: Path,
    spark_session: SparkSession,
) -> None:
    """Verify end-to-end execution of run_j2_event_aggregation with Parquet I/O."""
    input_dir = tmp_path / "raw_events"
    output_dir = tmp_path / "weekly_engagement"

    # Write small mock raw parquet dataset
    raw_data = [
        ("2024-07-15 10:00:00", "STU001", "CS101", "ENG", "LOGIN", 0),
        ("2024-07-15 11:00:00", "STU001", "CS101", "ENG", "VIDEO_VIEW", 1000),
    ]
    schema = StructType(
        [
            StructField("timestamp", StringType(), False),
            StructField("student_id", StringType(), False),
            StructField("course_id", StringType(), False),
            StructField("school", StringType(), False),
            StructField("activity_type", StringType(), False),
            StructField("duration_sec", LongType(), False),
        ]
    )
    df = spark_session.createDataFrame(raw_data, schema).withColumn(
        "timestamp", F.to_timestamp("timestamp")
    )
    df.write.parquet(str(input_dir))

    cfg = J2Config(
        input_path=input_dir,
        output_path=output_dir,
        save_parquet=True,
        partition_by=("semester_id",),
    )

    res = run_j2_event_aggregation(spark_session, cfg)
    assert res.total_input_events == 2
    assert res.total_output_rows == 1
    assert res.output_path == output_dir
    assert output_dir.exists()

    # Read back saved parquet
    saved_df = spark_session.read.parquet(str(output_dir))
    assert saved_df.count() == 1
    saved_row = saved_df.first()
    assert saved_row["total_events"] == 2
    assert saved_row["semester_id"] == "S1"


def test_no_large_collect_or_driver_iteration_in_j2() -> None:
    """Explicitly verify no large collect() or driver-side iteration exists in J2 (task 7.6, rules.md §17.3)."""
    source_file = Path(inspect.getfile(j2_module))
    tree = ast.parse(source_file.read_text(encoding="utf-8"))

    # Inspect all Call nodes in J2 module
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check attribute calls like df.collect() or df.toPandas()
            if isinstance(node.func, ast.Attribute):
                called_method = node.func.attr
                assert called_method not in (
                    "collect",
                    "toPandas",
                    "toArray",
                ), f"Forbidden driver-side collect/toPandas call '{called_method}' found on line {node.lineno} in {source_file.name}"
