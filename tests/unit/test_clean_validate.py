"""Unit tests for Spark clean and validate job - J1 (tasks 7.3 & 7.4, rules.md §10, §18)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from acadexa.processing.jobs.clean_validate import (
    DatasetQualityMetrics,
    IssueMetric,
    J1Config,
    J1QualityReport,
    build_j1_quality_report,
    clean_academic_records,
    clean_attendance,
    clean_courses,
    clean_coursework,
    clean_lms_events,
    clean_students,
    load_injection_manifest_counts,
)
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for J1 tests."""
    cfg = SparkRuntimeConfig(app_name="TestCleanValidate", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def test_j1_config_defaults() -> None:
    """Verify default configuration attributes of J1Config."""
    cfg = J1Config()
    assert cfg.input_format == "file"
    assert cfg.raw_data_dir == Path("data")
    assert cfg.output_dir == Path("data/processed")
    assert cfg.report_path == Path("reports/quality/j1_quality_report.json")
    assert cfg.manifest_path == Path("data/manifests/injection_manifest.json")
    assert cfg.impute_null_durations is True
    assert cfg.impute_null_scores is True
    assert cfg.impute_null_marks is True
    assert cfg.save_parquet is True
    assert cfg.save_report is True


def test_clean_students(spark_session: SparkSession) -> None:
    """Verify students identifier normalization and deduplication."""
    data = [
        ("stu001 ", "Engineering", "Alice"),
        ("STU001", "Engineering", "Alice"),  # duplicate
        (" stu002", "Science", "Bob"),
    ]
    schema = StructType(
        [
            StructField("student_id", StringType(), False),
            StructField("school", StringType(), False),
            StructField("name", StringType(), False),
        ]
    )
    df = spark_session.createDataFrame(data, schema)
    cleaned_df, metrics = clean_students(df)

    rows = cleaned_df.collect()
    assert len(rows) == 2
    student_ids = {r["student_id"] for r in rows}
    assert student_ids == {"STU001", "STU002"}
    assert metrics.input_rows == 3
    assert metrics.output_rows == 2
    assert metrics.issues["duplicates"].detected == 1


def test_clean_courses(spark_session: SparkSession) -> None:
    """Verify course identifier normalization and deduplication."""
    data = [
        (" cs101 ", "Intro CS", "Engineering"),
        ("CS101", "Intro CS", "Engineering"),  # duplicate
        ("math201", "Linear Algebra", "Science"),
    ]
    schema = StructType(
        [
            StructField("course_id", StringType(), False),
            StructField("course_name", StringType(), False),
            StructField("school", StringType(), False),
        ]
    )
    df = spark_session.createDataFrame(data, schema)
    cleaned_df, metrics = clean_courses(df)

    rows = cleaned_df.collect()
    assert len(rows) == 2
    course_ids = {r["course_id"] for r in rows}
    assert course_ids == {"CS101", "MATH201"}
    assert metrics.input_rows == 3
    assert metrics.output_rows == 2


def test_clean_attendance(spark_session: SparkSession) -> None:
    """Verify attendance orphan filtering, course formatting, and range clamping."""
    students = spark_session.createDataFrame(
        [("STU001",), ("STU002",)], ["student_id"]
    )
    att_data = [
        ("STU001", "cs101 ", "S1", 1, 10, 8, 0.8),  # format issue
        ("STU001", "CS101", "S1", 2, 10, 14, 1.4),  # out of range (attended > conducted)
        ("STU001", "CS101", "S1", 3, 10, -2, -0.2),  # out of range (attended < 0)
        ("STU999", "CS101", "S1", 1, 10, 8, 0.8),  # orphan record
    ]
    att_schema = StructType(
        [
            StructField("student_id", StringType(), False),
            StructField("course_id", StringType(), False),
            StructField("semester_id", StringType(), False),
            StructField("week_number", IntegerType(), False),
            StructField("classes_conducted", IntegerType(), False),
            StructField("classes_attended", IntegerType(), False),
            StructField("attendance_rate", DoubleType(), False),
        ]
    )
    att_df = spark_session.createDataFrame(att_data, att_schema)
    cleaned_df, metrics = clean_attendance(
        attendance_df=att_df,
        valid_students_df=students,
        injected_counts={"course_id_formatting": 1, "orphan_records": 1, "out_of_range_values": 2},
    )

    rows = cleaned_df.orderBy("week_number").collect()
    assert len(rows) == 3
    # Verify orphan STU999 dropped
    assert all(r["student_id"] == "STU001" for r in rows)
    # Verify course_id normalized
    assert all(r["course_id"] == "CS101" for r in rows)
    # Verify clamped attendance
    week2 = next(r for r in rows if r["week_number"] == 2)
    assert week2["classes_attended"] == 10
    assert week2["attendance_rate"] == 1.0
    week3 = next(r for r in rows if r["week_number"] == 3)
    assert week3["classes_attended"] == 0
    assert week3["attendance_rate"] == 0.0

    # Verify metrics
    assert metrics.issues["course_id_formatting"].detected == 1
    assert metrics.issues["course_id_formatting"].corrected == 1
    assert metrics.issues["orphan_records"].detected == 1
    assert metrics.issues["orphan_records"].dropped == 1
    assert metrics.issues["out_of_range_values"].detected == 2
    assert metrics.issues["out_of_range_values"].corrected == 2


def test_clean_academic_records(spark_session: SparkSession) -> None:
    """Verify academic records orphan filtering, marks clamping, and null imputation."""
    students = spark_session.createDataFrame(
        [("STU001",)], ["student_id"]
    )
    acad_data = [
        ("STU001", "cs101 ", "S1", 120, 80, -10, "B"),  # format + out of range
        ("STU001", "CS101", "S2", None, 75, 85, None),  # null marks and null grade
        ("STU999", "CS101", "S1", 80, 80, 80, "A"),  # orphan
    ]
    acad_schema = StructType(
        [
            StructField("student_id", StringType(), False),
            StructField("course_id", StringType(), False),
            StructField("semester_id", StringType(), False),
            StructField("internal_marks", IntegerType(), True),
            StructField("midterm_marks", IntegerType(), True),
            StructField("endterm_marks", IntegerType(), True),
            StructField("final_grade", StringType(), True),
        ]
    )
    acad_df = spark_session.createDataFrame(acad_data, acad_schema)
    cleaned_df, metrics = clean_academic_records(
        academic_df=acad_df,
        valid_students_df=students,
        injected_counts={"course_id_formatting": 1, "orphan_records": 1, "out_of_range_values": 1, "nulls_non_key": 1},
        impute_null_marks=True,
    )

    rows = cleaned_df.orderBy("semester_id").collect()
    assert len(rows) == 2
    # Row 1: clamped 120 -> 100, -10 -> 0
    row1 = next(r for r in rows if r["semester_id"] == "S1")
    assert row1["internal_marks"] == 100
    assert row1["endterm_marks"] == 0
    assert row1["course_id"] == "CS101"

    # Row 2: imputed internal_marks None -> 0, final_grade None -> computed
    row2 = next(r for r in rows if r["semester_id"] == "S2")
    assert row2["internal_marks"] == 0
    assert row2["final_grade"] is not None

    assert metrics.issues["orphan_records"].dropped == 1
    assert metrics.issues["out_of_range_values"].corrected == 1
    assert metrics.issues["nulls_non_key"].corrected == 1


def test_clean_coursework(spark_session: SparkSession) -> None:
    """Verify coursework timestamp parsing, score clamping, null score imputation."""
    students = spark_session.createDataFrame(
        [("STU001",)], ["student_id"]
    )
    cw_data = [
        ("ITM01", "STU001", "cs101", "S1", "Assign 1", "ASSIGNMENT", 100.0, 115.0, "SUBMITTED", "2026-09-01", "2026-09-10", "2026/09/08 14:30:00"),
        ("ITM02", "STU001", "CS101", "S1", "Assign 2", "ASSIGNMENT", 100.0, None, "SUBMITTED", "2026-09-10", "2026-09-20", "2026-09-18T10:00:00"),
        ("ITM03", "STU999", "CS101", "S1", "Assign 3", "ASSIGNMENT", 100.0, 80.0, "SUBMITTED", "2026-09-10", "2026-09-20", "2026-09-18T10:00:00"),
    ]
    cw_schema = StructType(
        [
            StructField("item_id", StringType(), False),
            StructField("student_id", StringType(), False),
            StructField("course_id", StringType(), False),
            StructField("semester_id", StringType(), False),
            StructField("title", StringType(), False),
            StructField("component_type", StringType(), False),
            StructField("max_score", DoubleType(), False),
            StructField("score", DoubleType(), True),
            StructField("status", StringType(), False),
            StructField("assigned_date", StringType(), False),
            StructField("due_date", StringType(), False),
            StructField("submitted_at", StringType(), True),
        ]
    )
    cw_df = spark_session.createDataFrame(cw_data, cw_schema)
    cleaned_df, metrics = clean_coursework(
        cw_df=cw_df,
        valid_students_df=students,
        injected_counts={"course_id_formatting": 1, "orphan_records": 1, "out_of_range_values": 1, "timestamp_inconsistencies": 1, "nulls_non_key": 1},
        impute_null_scores=True,
    )

    rows = cleaned_df.orderBy("item_id").collect()
    assert len(rows) == 2

    # ITM01: clamped 115.0 -> 100.0, timestamp parsed
    itm1 = next(r for r in rows if r["item_id"] == "ITM01")
    assert itm1["score"] == 100.0
    assert itm1["submitted_at"] is not None
    assert itm1["course_id"] == "CS101"

    # ITM02: null score imputed to 0.0
    itm2 = next(r for r in rows if r["item_id"] == "ITM02")
    assert itm2["score"] == 0.0

    assert metrics.issues["timestamp_inconsistencies"].detected == 1
    assert metrics.issues["timestamp_inconsistencies"].corrected == 1
    assert metrics.issues["orphan_records"].dropped == 1
    assert metrics.issues["out_of_range_values"].corrected == 1
    assert metrics.issues["nulls_non_key"].corrected == 1


def test_clean_lms_events(spark_session: SparkSession) -> None:
    """Verify LMS events deduplication, orphan filtering, duration clamping, and null imputation."""
    students = spark_session.createDataFrame(
        [("STU001",)], ["student_id"]
    )

    # Use dict records converted via JSON to test struct schema properly
    records = [
        {"timestamp": "2026-09-01T10:00:00", "meta": {"student_id": "stu001", "course_id": "cs101 ", "school": "ENG"}, "activity_type": "VIDEO_VIEW", "duration_sec": 300, "session_id": "S1"},
        {"timestamp": "2026-09-01T10:00:00", "meta": {"student_id": "stu001", "course_id": "cs101 ", "school": "ENG"}, "activity_type": "VIDEO_VIEW", "duration_sec": 300, "session_id": "S1"},  # duplicate
        {"timestamp": "2026-09-01T11:00:00", "meta": {"student_id": "STU001", "course_id": "CS101", "school": "ENG"}, "activity_type": "VIDEO_VIEW", "duration_sec": -120, "session_id": "S2"},  # negative
        {"timestamp": "2026-09-01T12:00:00", "meta": {"student_id": "STU001", "course_id": "CS101", "school": "ENG"}, "activity_type": "PDF_VIEW", "duration_sec": None, "session_id": "S3"},  # null
        {"timestamp": "2026-09-01T13:00:00", "meta": {"student_id": "STU999", "course_id": "CS101", "school": "ENG"}, "activity_type": "LOGIN", "duration_sec": None, "session_id": "S4"},  # orphan
    ]
    rdd = spark_session.sparkContext.parallelize([json.dumps(r) for r in records])
    lms_df = spark_session.read.json(rdd)

    cleaned_df, metrics = clean_lms_events(
        lms_df=lms_df,
        valid_students_df=students,
        injected_counts={"duplicate_lms_events": 1, "orphan_records": 1, "out_of_range_values": 1, "nulls_non_key": 1, "course_id_formatting": 1},
        impute_null_durations=True,
    )

    rows = cleaned_df.orderBy("session_id").collect()
    assert len(rows) == 3  # S1, S2, S3 (S1 duplicate dropped, S4 orphan dropped)

    s1 = next(r for r in rows if r["session_id"] == "S1")
    assert s1["meta"]["student_id"] == "STU001"
    assert s1["meta"]["course_id"] == "CS101"

    s2 = next(r for r in rows if r["session_id"] == "S2")
    assert s2["duration_sec"] == 0  # negative clamped to 0

    s3 = next(r for r in rows if r["session_id"] == "S3")
    assert s3["duration_sec"] == 0  # null imputed to 0

    assert metrics.issues["duplicate_lms_events"].dropped == 1
    assert metrics.issues["orphan_records"].dropped == 1
    assert metrics.issues["out_of_range_values"].corrected == 1
    assert metrics.issues["nulls_non_key"].corrected == 1


def test_quality_report_serialization(tmp_path: Path) -> None:
    """Verify building and serializing J1QualityReport to JSON."""
    ds_metrics = {
        "attendance": DatasetQualityMetrics(
            dataset_name="attendance",
            input_rows=100,
            output_rows=90,
            issues={
                "orphan_records": IssueMetric(injected=10, detected=10, dropped=10),
            },
        ),
    }
    report = build_j1_quality_report(
        dataset_metrics=ds_metrics,
        manifest_category_totals={"orphan_records": 10},
        manifest_grand_total=10,
    )

    assert report.total_injected == 10
    assert report.total_detected == 10
    assert report.total_dropped == 10
    assert report.total_remaining == 0
    assert report.validation_status == "PASSED"

    target_json = tmp_path / "test_report.json"
    report.save(target_json)
    assert target_json.exists()

    with open(target_json, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["job_name"] == "J1_clean_and_validate"
    assert loaded["total_injected"] == 10
    assert loaded["total_dropped"] == 10
    assert "attendance" in loaded["datasets"]


def test_no_large_collect_or_driver_iteration_in_j1() -> None:
    """Explicitly verify no large collect() or driver iteration exists in J1 (task 7.6, rules.md §17.3)."""
    import ast
    import inspect
    import acadexa.processing.jobs.clean_validate as j1_mod

    source_file = Path(inspect.getfile(j1_mod))
    tree = ast.parse(source_file.read_text(encoding="utf-8"))

    # Verify no forbidden DataFrame collect or conversion methods on large datasets
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called_method = node.func.attr
            assert called_method not in (
                "collect",
                "toPandas",
                "toArray",
            ), f"Forbidden driver-side collect/toPandas call '{called_method}' found on line {node.lineno} in {source_file.name}"

