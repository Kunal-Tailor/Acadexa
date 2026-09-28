"""Unit tests for Spark integrated student feature table construction - J3 (tasks 8.1 & 8.2, rules.md §17, §18)."""

from __future__ import annotations

import ast
from datetime import date, datetime
import inspect
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

from acadexa.analytics.metrics import (
    calculate_academic_score,
    calculate_attendance_percentage,
    calculate_attendance_rate,
    calculate_late_submission_rate,
    calculate_missing_rate,
    calculate_quiz_retry_ratio,
    calculate_score_percentage,
)
import acadexa.analytics.metrics as metrics_module
from acadexa.processing.jobs.feature_table import (
    J3Config,
    J3Result,
    aggregate_attendance_features,
    aggregate_coursework_features,
    aggregate_lms_features,
    build_integrated_student_features,
    build_student_semester_features,
    derive_semester_id_from_date,
    run_j3_feature_table,
)
import acadexa.processing.jobs.feature_table as j3_module
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for J3 feature table tests."""
    cfg = SparkRuntimeConfig(app_name="TestFeatureTable", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def test_j3_config_defaults() -> None:
    """Verify default parameters of J3Config."""
    cfg = J3Config()
    assert cfg.academic_records_path == Path("data/processed/academic_records")
    assert cfg.attendance_path == Path("data/processed/attendance")
    assert cfg.coursework_path == Path("data/processed/coursework")
    assert cfg.lms_path == Path("data/processed/lms_weekly_engagement")
    assert cfg.output_path == Path("data/processed/student_features")
    assert cfg.save_parquet is True
    assert cfg.partition_by == ("semester_id",)
    assert cfg.join_mode == "outer"


def test_metrics_column_expressions(spark_session: SparkSession) -> None:
    """Verify individual analytical metric Column expressions including division by zero safety."""
    data = [
        # attended, conducted, late, total_sub, miss, total_cw, score, max_sc, attempts, quizzes, int, mid, end
        (30, 40, 2, 10, 1, 10, 85.0, 100.0, 6, 3, 30, 25, 35),
        # 0 denominator row
        (0, 0, 0, 0, 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0),
    ]
    cols = [
        "classes_attended",
        "classes_conducted",
        "late_submissions",
        "total_submissions",
        "missing_submissions",
        "total_coursework",
        "total_score",
        "max_score",
        "total_quiz_attempts",
        "total_quizzes",
        "internal_marks",
        "midterm_marks",
        "endterm_marks",
    ]
    df = spark_session.createDataFrame(data, cols)

    res_df = df.select(
        calculate_attendance_rate("classes_attended", "classes_conducted").alias("att_rate"),
        calculate_attendance_percentage("classes_attended", "classes_conducted").alias("att_pct"),
        calculate_late_submission_rate("late_submissions", "total_submissions").alias("late_rate"),
        calculate_missing_rate("missing_submissions", "total_coursework").alias("miss_rate"),
        calculate_score_percentage("total_score", "max_score").alias("score_pct"),
        calculate_quiz_retry_ratio("total_quiz_attempts", "total_quizzes").alias("retry_ratio"),
        calculate_academic_score("internal_marks", "midterm_marks", "endterm_marks").alias("acad_score"),
    )

    rows = res_df.collect()
    row0 = rows[0]
    assert row0["att_rate"] == pytest.approx(0.75)
    assert row0["att_pct"] == pytest.approx(75.0)
    assert row0["late_rate"] == pytest.approx(0.20)
    assert row0["miss_rate"] == pytest.approx(0.10)
    assert row0["score_pct"] == pytest.approx(85.0)
    assert row0["retry_ratio"] == pytest.approx(2.0)
    assert row0["acad_score"] == pytest.approx(30.0)

    # 0 denominator row must safely evaluate to 0.0 without errors
    row1 = rows[1]
    assert row1["att_rate"] == 0.0
    assert row1["att_pct"] == 0.0
    assert row1["late_rate"] == 0.0
    assert row1["miss_rate"] == 0.0
    assert row1["score_pct"] == 0.0
    assert row1["retry_ratio"] == 0.0
    assert row1["acad_score"] == 0.0


def test_derive_semester_id_from_date(spark_session: SparkSession) -> None:
    """Verify semester mapping from calendar dates."""
    dates = [
        ("2024-07-20", "S1"),
        ("2025-02-10", "S2"),
        ("2025-08-15", "S3"),
        ("2026-03-01", "S4"),
        ("2023-01-01", "UNKNOWN"),
    ]
    df = spark_session.createDataFrame([(d[0],) for d in dates], ["due_date"])
    res = df.withColumn("semester_id", derive_semester_id_from_date("due_date"))

    rows = res.collect()
    for row, (_, expected_sem) in zip(rows, dates):
        assert row["semester_id"] == expected_sem


def test_aggregate_attendance_features(spark_session: SparkSession) -> None:
    """Verify weekly attendance aggregation to student x course x semester grain."""
    data = [
        ("STU001", "CS101", "S1", "2024-07-15", 4, 3),
        ("STU001", "CS101", "S1", "2024-07-22", 4, 4),
        ("STU001", "CS101", "S1", "2024-07-29", 2, 1),
        ("STU001", "MATH101", "S1", "2024-07-15", 3, 3),
    ]
    cols = [
        "student_id",
        "course_id",
        "semester_id",
        "week_start",
        "classes_conducted",
        "classes_attended",
    ]
    df = spark_session.createDataFrame(data, cols)

    agg = aggregate_attendance_features(df)
    rows = agg.collect()
    assert len(rows) == 2

    cs101_row = next(r for r in rows if r["course_id"] == "CS101")
    assert cs101_row["classes_conducted"] == 10
    assert cs101_row["classes_attended"] == 8
    assert cs101_row["classes_missed"] == 2
    assert cs101_row["attendance_weeks"] == 3
    assert cs101_row["attendance_rate"] == pytest.approx(0.80)
    assert cs101_row["attendance_percentage"] == pytest.approx(80.0)

    math_row = next(r for r in rows if r["course_id"] == "MATH101")
    assert math_row["classes_conducted"] == 3
    assert math_row["classes_attended"] == 3
    assert math_row["attendance_percentage"] == pytest.approx(100.0)


def test_aggregate_coursework_features(spark_session: SparkSession) -> None:
    """Verify coursework aggregation and derived metrics."""
    data = [
        # student_id, course_id, item_id, item_type, due_date, status, score, max_score, attempts
        ("STU001", "CS101", "A01", "ASSIGNMENT", "2024-07-29", "ON_TIME", 18.0, 20.0, 1),
        ("STU001", "CS101", "A02", "ASSIGNMENT", "2024-08-12", "LATE", 14.0, 20.0, 1),
        ("STU001", "CS101", "A03", "ASSIGNMENT", "2024-08-26", "MISSING", None, 20.0, 0),
        ("STU001", "CS101", "Q01", "QUIZ", "2024-08-05", "ON_TIME", 9.0, 10.0, 2),
        ("STU001", "CS101", "Q02", "QUIZ", "2024-08-19", "ON_TIME", 8.0, 10.0, 3),
    ]
    cols = [
        "student_id",
        "course_id",
        "item_id",
        "item_type",
        "due_date",
        "status",
        "score",
        "max_score",
        "attempts",
    ]
    df = spark_session.createDataFrame(data, cols)

    agg = aggregate_coursework_features(df)
    rows = agg.collect()
    assert len(rows) == 1
    r = rows[0]

    assert r["student_id"] == "STU001"
    assert r["course_id"] == "CS101"
    assert r["semester_id"] == "S1"
    assert r["total_coursework"] == 5
    assert r["total_assignments"] == 3
    assert r["total_quizzes"] == 2
    assert r["total_submissions"] == 4
    assert r["submitted_assignments"] == 2
    assert r["submitted_quizzes"] == 2
    assert r["late_submissions"] == 1
    assert r["late_assignments"] == 1
    assert r["missing_submissions"] == 1
    assert r["missing_assignments"] == 1
    assert r["missing_quizzes"] == 0
    assert r["late_submission_rate"] == pytest.approx(0.25)  # 1 late / 4 submissions
    assert r["late_assignment_rate"] == pytest.approx(1.0 / 3.0)  # 1 late / 3 assignments
    assert r["missing_coursework_rate"] == pytest.approx(0.20)  # 1 missing / 5 items
    assert r["coursework_total_score"] == pytest.approx(49.0)  # 18 + 14 + 0 + 9 + 8
    assert r["coursework_max_score"] == pytest.approx(80.0)  # 20 + 20 + 20 + 10 + 10
    assert r["coursework_score_pct"] == pytest.approx(49.0 / 80.0 * 100.0)
    assert r["total_quiz_attempts"] == 5  # 2 + 3
    assert r["quiz_retry_ratio"] == pytest.approx(2.5)  # 5 attempts / 2 quizzes


def test_aggregate_lms_features(spark_session: SparkSession) -> None:
    """Verify weekly LMS engagement aggregation to student x course x semester."""
    data = [
        # student_id, course_id, semester_id, week_start, total_events, total_dur, active_days, content, assess, part, access, vid, quiz, aview, asub, forum, login
        ("STU001", "CS101", "S1", "2024-07-15", 25, 3600, 4, 15, 5, 2, 3, 10, 2, 2, 1, 2, 3),
        ("STU001", "CS101", "S1", "2024-07-22", 35, 5400, 5, 20, 8, 3, 4, 12, 4, 2, 2, 3, 4),
    ]
    cols = [
        "student_id",
        "course_id",
        "semester_id",
        "week_start",
        "total_events",
        "total_duration_sec",
        "active_days",
        "content_views",
        "assessment_events",
        "participation_events",
        "access_events",
        "video_views",
        "quiz_attempts",
        "assignment_views",
        "assignment_submissions",
        "forum_posts",
        "logins",
    ]
    df = spark_session.createDataFrame(data, cols)

    agg = aggregate_lms_features(df)
    rows = agg.collect()
    assert len(rows) == 1
    r = rows[0]

    assert r["student_id"] == "STU001"
    assert r["course_id"] == "CS101"
    assert r["semester_id"] == "S1"
    assert r["lms_total_events"] == 60
    assert r["lms_total_duration_sec"] == 9000
    assert r["lms_total_duration_hours"] == pytest.approx(2.5)
    assert r["lms_active_days_total"] == 9
    assert r["lms_active_weeks"] == 2
    assert r["lms_active_days_per_week_avg"] == pytest.approx(4.5)
    assert r["lms_events_per_active_day"] == pytest.approx(60.0 / 9.0)
    assert r["lms_content_views"] == 35
    assert r["lms_assessment_events"] == 13
    assert r["lms_participation_events"] == 5
    assert r["lms_access_events"] == 7
    assert r["lms_video_views"] == 22
    assert r["lms_quiz_attempts"] == 6


def test_build_integrated_student_features_end_to_end(
    spark_session: SparkSession,
) -> None:
    """Verify integrated student feature table creation with metadata and derived metrics."""
    # Academic records
    acad_data = [
        ("STU001", "CS101", "S1", 28, 22, 35, "A"),
        ("STU001", "MATH101", "S1", 20, 18, 26, "B"),
    ]
    acad_df = spark_session.createDataFrame(
        acad_data,
        ["student_id", "course_id", "semester_id", "internal_marks", "midterm_marks", "endterm_marks", "final_grade"],
    )

    # Attendance
    att_data = [
        ("STU001", "CS101", "S1", "2024-07-15", 4, 3),
        ("STU001", "MATH101", "S1", "2024-07-15", 4, 4),
    ]
    att_df = spark_session.createDataFrame(
        att_data,
        ["student_id", "course_id", "semester_id", "week_start", "classes_conducted", "classes_attended"],
    )

    # Coursework
    cw_data = [
        ("STU001", "CS101", "A01", "ASSIGNMENT", "2024-07-29", "ON_TIME", 18.0, 20.0, 1),
        ("STU001", "MATH101", "A01", "ASSIGNMENT", "2024-07-29", "LATE", 15.0, 20.0, 1),
    ]
    cw_df = spark_session.createDataFrame(
        cw_data,
        ["student_id", "course_id", "item_id", "item_type", "due_date", "status", "score", "max_score", "attempts"],
    )

    # LMS
    lms_data = [
        ("STU001", "CS101", "S1", "2024-07-15", 30, 3600, 3, 20, 5, 2, 3, 10, 2, 2, 1, 2, 3),
        ("STU001", "MATH101", "S1", "2024-07-15", 15, 1800, 2, 10, 2, 1, 2, 5, 1, 1, 0, 1, 2),
    ]
    lms_cols = [
        "student_id", "course_id", "semester_id", "week_start", "total_events",
        "total_duration_sec", "active_days", "content_views", "assessment_events",
        "participation_events", "access_events", "video_views", "quiz_attempts",
        "assignment_views", "assignment_submissions", "forum_posts", "logins",
    ]
    lms_df = spark_session.createDataFrame(lms_data, lms_cols)

    # Courses metadata
    courses_data = [
        ("CS101", "Intro to CS", "SCET", "Computer Science", 0.45, "medium"),
        ("MATH101", "Calculus I", "SOS", "Mathematics", 0.60, "hard"),
    ]
    courses_df = spark_session.createDataFrame(
        courses_data,
        ["course_id", "title", "school", "department", "difficulty", "difficulty_level"],
    )

    # Students metadata
    students_data = [
        ("STU001", "SCET", "Computer Science", "B.Tech CS", 2024, 1),
    ]
    students_df = spark_session.createDataFrame(
        students_data,
        ["student_id", "school", "department", "program", "batch", "semester"],
    )

    # Build integrated feature table
    feat_df = build_integrated_student_features(
        academic_records_df=acad_df,
        attendance_df=att_df,
        coursework_df=cw_df,
        lms_weekly_df=lms_df,
        courses_df=courses_df,
        students_df=students_df,
    )

    rows = feat_df.collect()
    assert len(rows) == 2

    cs_row = next(r for r in rows if r["course_id"] == "CS101")
    assert cs_row["student_id"] == "STU001"
    assert cs_row["semester_id"] == "S1"
    assert cs_row["total_marks"] == 85
    assert cs_row["academic_score"] == pytest.approx(85.0 / 3.0)
    assert cs_row["exam_marks_trend"] == 7  # 35 - 28
    assert cs_row["attendance_percentage"] == pytest.approx(75.0)
    assert cs_row["late_submission_rate"] == 0.0
    assert cs_row["coursework_score_pct"] == pytest.approx(90.0)
    assert cs_row["lms_total_events"] == 30
    assert cs_row["course_difficulty"] == pytest.approx(0.45)
    assert cs_row["course_title"] == "Intro to CS"
    assert cs_row["school"] == "SCET"

    math_row = next(r for r in rows if r["course_id"] == "MATH101")
    assert math_row["late_submission_rate"] == 1.0
    assert math_row["attendance_percentage"] == pytest.approx(100.0)
    assert math_row["course_difficulty"] == pytest.approx(0.60)


def test_build_student_semester_features(spark_session: SparkSession) -> None:
    """Verify student-semester roll-up conforming to student_features gold collection schema."""
    feature_data = [
        ("STU001", "CS101", "S1", 80.0, 40, 1, 4, 5, 28.0, "SCET", "CS"),
        ("STU001", "MATH101", "S1", 90.0, 60, 0, 4, -3, 24.0, "SCET", "CS"),
    ]
    cols = [
        "student_id",
        "course_id",
        "semester_id",
        "attendance_percentage",
        "lms_total_events",
        "late_submissions",
        "total_submissions",
        "exam_marks_trend",
        "academic_score",
        "student_school",
        "student_department",
    ]
    df = spark_session.createDataFrame(feature_data, cols)

    rollup = build_student_semester_features(df)
    rows = rollup.collect()
    assert len(rows) == 1
    r = rows[0]

    assert r["student_id"] == "STU001"
    assert r["semester_id"] == "S1"
    assert r["attendance_mean"] == pytest.approx(85.0)  # avg(80, 90)
    assert r["engagement_count"] == 100  # 40 + 60
    assert r["late_submission_rate"] == pytest.approx(0.125)  # 1 / 8
    assert r["score_trend"] == pytest.approx(1.0)  # avg(5, -3)
    assert r["enrolled_courses_count"] == 2
    assert r["avg_academic_score"] == pytest.approx(26.0)


def test_run_j3_feature_table_end_to_end(
    tmp_path: Path,
    spark_session: SparkSession,
) -> None:
    """Verify run_j3_feature_table execution with Parquet inputs and output."""
    in_dir = tmp_path / "processed"
    out_dir = tmp_path / "student_features"
    rollup_dir = tmp_path / "student_features_summary"

    # Write mock domain parquets
    # 1. Academic records
    acad_df = spark_session.createDataFrame(
        [("STU001", "CS101", "S1", 25, 25, 30, "A")],
        ["student_id", "course_id", "semester_id", "internal_marks", "midterm_marks", "endterm_marks", "final_grade"],
    )
    acad_path = in_dir / "academic_records"
    acad_df.write.parquet(str(acad_path))

    # 2. Attendance
    att_df = spark_session.createDataFrame(
        [("STU001", "CS101", "S1", "2024-07-15", 4, 4)],
        ["student_id", "course_id", "semester_id", "week_start", "classes_conducted", "classes_attended"],
    )
    att_path = in_dir / "attendance"
    att_df.write.parquet(str(att_path))

    # 3. Coursework
    cw_df = spark_session.createDataFrame(
        [("STU001", "CS101", "A01", "ASSIGNMENT", "2024-07-29", "ON_TIME", 18.0, 20.0, 1)],
        ["student_id", "course_id", "item_id", "item_type", "due_date", "status", "score", "max_score", "attempts"],
    )
    cw_path = in_dir / "coursework"
    cw_df.write.parquet(str(cw_path))

    # 4. LMS weekly engagement
    lms_df = spark_session.createDataFrame(
        [("STU001", "CS101", "S1", "2024-07-15", 20, 1800, 3, 10, 5, 2, 3, 5, 2, 2, 1, 2, 3)],
        [
            "student_id", "course_id", "semester_id", "week_start", "total_events",
            "total_duration_sec", "active_days", "content_views", "assessment_events",
            "participation_events", "access_events", "video_views", "quiz_attempts",
            "assignment_views", "assignment_submissions", "forum_posts", "logins",
        ],
    )
    lms_path = in_dir / "lms_weekly_engagement"
    lms_df.write.parquet(str(lms_path))

    # 5. Courses metadata
    courses_df = spark_session.createDataFrame(
        [("CS101", "CS 101", "SCET", "CS", 0.40, "medium")],
        ["course_id", "title", "school", "department", "difficulty", "difficulty_level"],
    )
    courses_path = in_dir / "courses"
    courses_df.write.parquet(str(courses_path))

    # 6. Students metadata
    students_df = spark_session.createDataFrame(
        [("STU001", "SCET", "CS", "B.Tech", 2024, 1)],
        ["student_id", "school", "department", "program", "batch", "semester"],
    )
    students_path = in_dir / "students"
    students_df.write.parquet(str(students_path))

    cfg = J3Config(
        academic_records_path=acad_path,
        attendance_path=att_path,
        coursework_path=cw_path,
        lms_path=lms_path,
        courses_path=courses_path,
        students_path=students_path,
        output_path=out_dir,
        student_rollup_path=rollup_dir,
        save_parquet=True,
    )

    res = run_j3_feature_table(spark_session, cfg)
    assert res.total_features_rows == 1
    assert res.total_students == 1
    assert res.output_path == out_dir
    assert out_dir.exists()
    assert rollup_dir.exists()

    # Read back saved parquet
    saved_df = spark_session.read.parquet(str(out_dir))
    assert saved_df.count() == 1
    first_row = saved_df.first()
    assert first_row["student_id"] == "STU001"
    assert first_row["course_id"] == "CS101"
    assert first_row["semester_id"] == "S1"
    assert first_row["total_marks"] == 80
    assert first_row["attendance_percentage"] == pytest.approx(100.0)


def test_no_large_collect_or_driver_iteration_in_j3_and_metrics() -> None:
    """Explicitly verify no large collect() or driver iteration exists in J3 or metrics (rules.md §17.3)."""
    for mod in (j3_module, metrics_module):
        source_file = Path(inspect.getfile(mod))
        tree = ast.parse(source_file.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                called_method = node.func.attr
                assert called_method not in (
                    "collect",
                    "toPandas",
                    "toArray",
                ), f"Forbidden driver-side collect/toPandas call '{called_method}' found on line {node.lineno} in {source_file.name}"
