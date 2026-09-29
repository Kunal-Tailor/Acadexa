"""Risk-signal boundary validation (Task 10.3, rules.md §22, §28).

Validates positive / negative / boundary behavior for the five approved
rule-based signals using thresholds loaded from configuration
(not hard-coded in the assertions):

- Attendance: below 75% triggers (74.99 True / 75.0 False / 75.01 False).
- LMS decline: current 4-week engagement <= 50% of prior 4 weeks triggers.
- Late submissions: more than 30% late triggers (0.30 False / above True).
- Marks decline: drop >= 10 points triggers (9.99 False / 10.0 True).
- Quiz activity: bottom quartile within course triggers
  (percent_rank < 0.25; exactly 0.25 does not trigger).

Each triggered signal contributes one point (observed signal count 0–5);
no failure prediction is implied.
"""

from __future__ import annotations

import pytest
from pyspark.sql import SparkSession

from acadexa.analytics.risk import (
    RiskSignalThresholds,
    evaluate_student_course_risk_signals,
)
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession for risk boundary tests."""
    cfg = SparkRuntimeConfig(app_name="TestRiskBoundaries", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


@pytest.fixture(scope="module")
def thresholds() -> RiskSignalThresholds:
    """Thresholds loaded from configuration (single source of truth)."""
    th = RiskSignalThresholds.from_config()
    assert th.attendance_threshold == 75.0
    assert th.lms_comparison_ratio == 0.50
    assert th.late_rate_threshold == 0.30
    assert th.marks_drop_threshold == 10.0
    assert th.quiz_percentile_threshold == 0.25
    return th


def _neutral_row(
    student_id: str,
    thresholds: RiskSignalThresholds,
    *,
    attendance: float = 90.0,
    lms_ratio: float = 1.0,
    late_rate: float = 0.0,
    marks_drop: float = 0.0,
    quiz_attempts: int = 5,
) -> tuple:
    """Build one input row with all signals neutral except overridden fields."""
    return (
        student_id,
        "CS101",
        "S1",
        attendance,
        False,
        lms_ratio,
        100,
        late_rate,
        False,
        marks_drop,
        quiz_attempts,
    )


_NEUTRAL_COLS = [
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


def test_attendance_boundary_75_percent(
    spark_session: SparkSession, thresholds: RiskSignalThresholds
) -> None:
    """Attendance below (not at) the threshold triggers the signal."""
    th = thresholds.attendance_threshold
    rows = [
        _neutral_row("STU_BELOW", thresholds, attendance=th - 0.01, quiz_attempts=5),
        _neutral_row("STU_AT", thresholds, attendance=th, quiz_attempts=5),
        _neutral_row("STU_ABOVE", thresholds, attendance=th + 0.01, quiz_attempts=5),
    ]
    df = spark_session.createDataFrame(rows, _NEUTRAL_COLS)
    result = {r["student_id"]: r for r in evaluate_student_course_risk_signals(df).collect()}

    assert result["STU_BELOW"]["low_attendance"] is True
    assert result["STU_AT"]["low_attendance"] is False
    assert result["STU_ABOVE"]["low_attendance"] is False


def test_lms_decline_boundary_50_percent(
    spark_session: SparkSession, thresholds: RiskSignalThresholds
) -> None:
    """LMS ratio at or below the comparison ratio triggers the signal."""
    ratio = thresholds.lms_comparison_ratio
    rows = [
        _neutral_row("STU_BELOW", thresholds, lms_ratio=ratio - 0.01),
        _neutral_row("STU_AT", thresholds, lms_ratio=ratio),
        _neutral_row("STU_ABOVE", thresholds, lms_ratio=ratio + 0.01),
    ]
    df = spark_session.createDataFrame(rows, _NEUTRAL_COLS)
    result = {r["student_id"]: r for r in evaluate_student_course_risk_signals(df).collect()}

    assert result["STU_BELOW"]["lms_decline"] is True
    assert result["STU_AT"]["lms_decline"] is True
    assert result["STU_ABOVE"]["lms_decline"] is False


def test_lms_decline_requires_prior_activity(
    spark_session: SparkSession, thresholds: RiskSignalThresholds
) -> None:
    """Zero prior-period activity guards against an invalid denominator."""
    ratio = thresholds.lms_comparison_ratio
    rows = [
        (
            "STU_ZERO_PREV",
            "CS101",
            "S1",
            90.0,
            False,
            ratio - 0.10,
            0,
            0.0,
            False,
            0.0,
            5,
        ),
    ]
    df = spark_session.createDataFrame(rows, _NEUTRAL_COLS)
    result = {r["student_id"]: r for r in evaluate_student_course_risk_signals(df).collect()}

    assert result["STU_ZERO_PREV"]["lms_decline"] is False


def test_late_submissions_boundary_30_percent(
    spark_session: SparkSession, thresholds: RiskSignalThresholds
) -> None:
    """Late rate strictly above the threshold triggers the signal."""
    th = thresholds.late_rate_threshold
    rows = [
        _neutral_row("STU_BELOW", thresholds, late_rate=th - 0.01),
        _neutral_row("STU_AT", thresholds, late_rate=th),
        _neutral_row("STU_ABOVE", thresholds, late_rate=th + 0.01),
    ]
    df = spark_session.createDataFrame(rows, _NEUTRAL_COLS)
    result = {r["student_id"]: r for r in evaluate_student_course_risk_signals(df).collect()}

    assert result["STU_BELOW"]["late_submissions"] is False
    assert result["STU_AT"]["late_submissions"] is False
    assert result["STU_ABOVE"]["late_submissions"] is True


def test_marks_decline_boundary_10_points(
    spark_session: SparkSession, thresholds: RiskSignalThresholds
) -> None:
    """Marks drop at or above the point threshold triggers the signal."""
    th = thresholds.marks_drop_threshold
    rows = [
        _neutral_row("STU_BELOW", thresholds, marks_drop=th - 0.01),
        _neutral_row("STU_AT", thresholds, marks_drop=th),
        _neutral_row("STU_ABOVE", thresholds, marks_drop=th + 0.01),
    ]
    df = spark_session.createDataFrame(rows, _NEUTRAL_COLS)
    result = {r["student_id"]: r for r in evaluate_student_course_risk_signals(df).collect()}

    assert result["STU_BELOW"]["marks_decline"] is False
    assert result["STU_AT"]["marks_decline"] is True
    assert result["STU_ABOVE"]["marks_decline"] is True


def test_quiz_bottom_quartile_boundary(
    spark_session: SparkSession, thresholds: RiskSignalThresholds
) -> None:
    """Quiz rank strictly below the quartile threshold triggers the signal."""
    assert thresholds.quiz_percentile_threshold == 0.25
    # Five students, distinct attempts 0..4 in one course offering:
    # percent_rank values are 0.0, 0.25, 0.5, 0.75, 1.0.
    rows = [_neutral_row(f"STU_Q{i}", thresholds, quiz_attempts=i) for i in range(5)]
    df = spark_session.createDataFrame(rows, _NEUTRAL_COLS)
    result = {r["student_id"]: r for r in evaluate_student_course_risk_signals(df).collect()}

    assert result["STU_Q0"]["low_quiz_activity"] is True
    # Exactly at the 25th percentile does not trigger (strict < comparison).
    assert result["STU_Q1"]["low_quiz_activity"] is False
    assert result["STU_Q4"]["low_quiz_activity"] is False
