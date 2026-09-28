"""Unit tests for rule-based risk signals and explainability (Tasks 8.7 & 8.8, rules.md §8, §17, §18, §22)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from acadexa.analytics.risk import (
    RiskSignalThresholds,
    build_student_risk_indicators,
    evaluate_student_course_risk_signals,
)
import acadexa.analytics.risk as risk_analytics_module
from acadexa.processing.jobs.risk_signals import (
    J6Config,
    J6Result,
    run_j6_risk_signals,
)
import acadexa.processing.jobs.risk_signals as j6_job_module
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)
from acadexa.validation import RISK_INDICATORS_SCHEMA, validate_record


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for risk signal tests."""
    cfg = SparkRuntimeConfig(app_name="TestRiskSignals", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def test_risk_signal_thresholds_from_config() -> None:
    """Verify RiskSignalThresholds loads values correctly from config/risk/risk_signals.toml."""
    th = RiskSignalThresholds.from_config()
    assert th.attendance_threshold == 75.0
    assert th.lms_comparison_ratio == 0.50
    assert th.late_rate_threshold == 0.30
    assert th.marks_drop_threshold == 10.0
    assert th.quiz_percentile_threshold == 0.25


def test_evaluate_individual_signals_and_explanations(spark_session: SparkSession) -> None:
    """Verify evaluation of all five individual signals and explainability strings (Tasks 8.7 & 8.8)."""
    # 5 students with distinct signal patterns
    data = [
        # STU01: All 5 signals triggered
        ("STU01", "CS101", "S1", 60.0, True, 0.40, 100, 0.50, True, 15.0, 0),
        # STU02: None triggered
        ("STU02", "CS101", "S1", 90.0, False, 0.90, 100, 0.10, False, 0.0, 10),
        # STU03: Low attendance only
        ("STU03", "CS101", "S1", 70.0, False, 1.00, 100, 0.10, False, 2.0, 8),
        # STU04: LMS decline + late submissions
        ("STU04", "CS101", "S1", 85.0, True, 0.35, 100, 0.40, False, 5.0, 7),
        # STU05: Marks decline only
        ("STU05", "CS101", "S1", 80.0, False, 0.80, 100, 0.15, True, 12.0, 9),
    ]
    cols = [
        "student_id",
        "course_id",
        "semester_id",
        "attendance_percentage",
        "lms_decline_detected",
        "lms_recent_vs_prior_ratio",
        "lms_prev_4w_events",
        "late_assignment_rate",
        "marks_decline_detected",
        "marks_drop_points",
        "total_quiz_attempts",
    ]
    df = spark_session.createDataFrame(data, cols)

    evaluated = evaluate_student_course_risk_signals(df)

    rows = {r["student_id"]: r for r in evaluated.collect()}

    # STU01: All signals true, signal_count = 5
    s1 = rows["STU01"]
    assert s1["low_attendance"] is True
    assert s1["lms_decline"] is True
    assert s1["late_submissions"] is True
    assert s1["marks_decline"] is True
    assert s1["low_quiz_activity"] is True
    assert s1["signal_count"] == 5

    # Check explainability strings for STU01
    exp1 = s1["explanations"]
    assert "60.0% < 75" in exp1["low_attendance"]
    assert "40.0% of previous 4 weeks (<= 50" in exp1["lms_decline"]
    assert "50.0% > 30" in exp1["late_submissions"]
    assert "15.0 pts (>= 10" in exp1["marks_decline"]
    assert "bottom quartile" in exp1["low_quiz_activity"]

    # STU02: All signals false, signal_count = 0
    s2 = rows["STU02"]
    assert s2["low_attendance"] is False
    assert s2["lms_decline"] is False
    assert s2["late_submissions"] is False
    assert s2["marks_decline"] is False
    assert s2["low_quiz_activity"] is False
    assert s2["signal_count"] == 0

    exp2 = s2["explanations"]
    assert "90.0% >= 75" in exp2["low_attendance"]
    assert "stable" in exp2["lms_decline"]
    assert "10.0% <= 30" in exp2["late_submissions"]
    assert "stable" in exp2["marks_decline"]
    assert "not in bottom quartile" in exp2["low_quiz_activity"]

    # STU03: Low attendance only
    s3 = rows["STU03"]
    assert s3["low_attendance"] is True
    assert s3["lms_decline"] is False
    assert s3["late_submissions"] is False
    assert s3["marks_decline"] is False
    assert s3["signal_count"] >= 1

    # STU04: LMS decline + late submissions
    s4 = rows["STU04"]
    assert s4["low_attendance"] is False
    assert s4["lms_decline"] is True
    assert s4["late_submissions"] is True

    # STU05: Marks decline only
    s5 = rows["STU05"]
    assert s5["marks_decline"] is True


def test_build_student_risk_indicators_schema_conformance(spark_session: SparkSession) -> None:
    """Verify build_student_risk_indicators outputs match RISK_INDICATORS_SCHEMA (task 8.7)."""
    data = [
        ("STU010482", "CS101", "S1", 68.0, True, 0.42, 120, 0.20, True, 12.0, 6),
        ("STU010482", "CS102", "S1", 72.0, False, 0.85, 150, 0.10, False, 2.0, 7),
        ("STU020001", "CS101", "S1", 92.0, False, 0.95, 200, 0.05, False, 0.0, 12),
    ]
    cols = [
        "student_id",
        "course_id",
        "semester_id",
        "attendance_percentage",
        "lms_decline_detected",
        "lms_recent_vs_prior_ratio",
        "lms_prev_4w_events",
        "late_assignment_rate",
        "marks_decline_detected",
        "marks_drop_points",
        "total_quiz_attempts",
    ]
    df = spark_session.createDataFrame(data, cols)

    course_risk = evaluate_student_course_risk_signals(df)
    student_risk = build_student_risk_indicators(course_risk, evaluation_week_start="2025-11-03")

    # Assert schema columns exactly match RISK_INDICATORS_SCHEMA fields
    expected_cols = {
        "student_id",
        "week_start",
        "signal_count",
        "low_attendance",
        "lms_decline",
        "late_submissions",
        "marks_decline",
        "low_quiz_activity",
        "explanations",
        "computed_at",
    }
    assert set(student_risk.columns) == expected_cols

    # Collect rows and validate each against RISK_INDICATORS_SCHEMA with Phase 3 validator
    records = student_risk.toPandas().to_dict(orient="records")
    assert len(records) == 2

    for rec in records:
        validate_record(rec, RISK_INDICATORS_SCHEMA)

    # Specific check for STU010482
    stu1 = next(r for r in records if r["student_id"] == "STU010482")
    assert stu1["low_attendance"] is True
    assert stu1["lms_decline"] is True
    assert stu1["marks_decline"] is True
    assert stu1["signal_count"] >= 3
    assert isinstance(stu1["explanations"], dict)
    assert "low_attendance" in stu1["explanations"]
    assert "lms_decline" in stu1["explanations"]
    assert "late_submissions" in stu1["explanations"]
    assert "marks_decline" in stu1["explanations"]
    assert "low_quiz_activity" in stu1["explanations"]


def test_j6_risk_signals_end_to_end_job(spark_session: SparkSession, tmp_path: Path) -> None:
    """Verify run_j6_risk_signals end-to-end execution, parquet persistence, and result metrics."""
    in_dir = tmp_path / "processed"
    out_dir = tmp_path / "risk_indicators"
    course_out_dir = tmp_path / "course_risk"

    feat_path = in_dir / "student_features"
    trend_path = in_dir / "trend_indicators"

    feat_data = [
        ("STU01", "CS101", "S1", 65.0, 0.40, 1),
        ("STU02", "CS101", "S1", 85.0, 0.10, 8),
        ("STU03", "CS101", "S1", 50.0, 0.50, 0),
    ]
    spark_session.createDataFrame(
        feat_data,
        ["student_id", "course_id", "semester_id", "attendance_percentage", "late_assignment_rate", "total_quiz_attempts"],
    ).write.parquet(str(feat_path))

    trend_data = [
        ("STU01", "CS101", "S1", True, 0.30, 100, True, 12.0),
        ("STU02", "CS101", "S1", False, 0.90, 100, False, 2.0),
        ("STU03", "CS101", "S1", True, 0.40, 100, True, 15.0),
    ]
    spark_session.createDataFrame(
        trend_data,
        ["student_id", "course_id", "semester_id", "lms_decline_detected", "lms_recent_vs_prior_ratio", "lms_prev_4w_events", "marks_decline_detected", "marks_drop_points"],
    ).write.parquet(str(trend_path))

    cfg = J6Config(
        student_features_path=feat_path,
        trend_indicators_path=trend_path,
        output_path=out_dir,
        course_level_output_path=course_out_dir,
        save_parquet=True,
    )

    res = run_j6_risk_signals(spark_session, cfg)

    assert res.total_students == 3
    assert res.output_path == out_dir
    assert out_dir.exists()
    assert course_out_dir.exists()

    # Read saved parquet
    saved_df = spark_session.read.parquet(str(out_dir))
    assert saved_df.count() == 3
    assert "signal_count" in saved_df.columns
    assert "explanations" in saved_df.columns

    # Verify breakdown
    assert sum(res.signal_counts_breakdown.values()) == 3
    assert res.flagged_students_count >= 2


def test_no_large_collect_or_driver_iteration_in_j6() -> None:
    """Explicitly verify no driver-side collect/toPandas exists in J6 job or risk analytics (rules.md §17.3)."""
    for mod in (j6_job_module, risk_analytics_module):
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
