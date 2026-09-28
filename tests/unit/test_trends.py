"""Unit tests for temporal trend detection and optional Pearson correlation (Tasks 8.5 & 8.6, rules.md §8, §17, §18)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from scipy.stats import pearsonr

from acadexa.analytics.correlation import (
    APPROVED_CORRELATION_RELATIONSHIPS,
    compute_pearson_correlation,
    evaluate_planted_and_decoy_correlations,
)
from acadexa.analytics.trends import (
    compute_coursework_marks_trends,
    compute_lms_four_week_trends,
    integrate_temporal_trends,
)
import acadexa.analytics.trends as trends_analytics_module
from acadexa.processing.jobs.trend_detection import (
    J5Config,
    J5Result,
    run_j5_trend_detection,
)
import acadexa.processing.jobs.trend_detection as j5_job_module
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for trend detection and Pearson correlation tests."""
    cfg = SparkRuntimeConfig(app_name="TestTrendsAnalytics", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def test_compute_pearson_correlation_precision(spark_session: SparkSession) -> None:
    """Verify compute_pearson_correlation matches scipy.stats.pearsonr exactly (Task 8.5)."""
    data = [
        (10.0, 25.0),
        (20.0, 30.0),
        (30.0, 45.0),
        (40.0, 60.0),
        (50.0, 58.0),
        (60.0, 75.0),
    ]
    df = spark_session.createDataFrame(data, ["x", "y"])

    res_df = compute_pearson_correlation(df, "x", "y")
    spark_p = res_df.first()["pearson_corr"]

    xs = [d[0] for d in data]
    ys = [d[1] for d in data]
    scipy_p = pearsonr(xs, ys).statistic

    assert spark_p == pytest.approx(scipy_p, abs=1e-6)
    assert res_df.first()["sample_size"] == len(data)


def test_evaluate_planted_and_decoy_correlations_with_pearson(
    spark_session: SparkSession,
) -> None:
    """Verify evaluate_planted_and_decoy_correlations includes Pearson columns alongside Spearman (Task 8.5)."""
    data = [
        (70.0, -1.0, 60.0, -1.0, 100, -1.0, 0.4, 1.0, 2, -1.0, 10, -0.5, "SCET"),
        (80.0, 0.0, 75.0, 0.0, 200, 0.0, 0.2, 0.0, 4, 0.0, 12, 0.5, "SCET"),
        (90.0, 1.0, 90.0, 1.0, 300, 1.0, 0.0, -1.0, 6, 1.0, 8, -1.0, "SCET"),
    ]
    cols = [
        "attendance_percentage",
        "z_attendance_percentage",
        "academic_score",
        "z_academic_score",
        "lms_total_events",
        "z_lms_total_events",
        "late_submission_rate",
        "z_late_submission_rate",
        "total_quiz_attempts",
        "z_total_quiz_attempts",
        "lms_forum_posts",
        "z_lms_forum_posts",
        "school",
    ]
    df = spark_session.createDataFrame(data, cols)

    corr_df = evaluate_planted_and_decoy_correlations(df, include_pearson=True)
    rows = corr_df.collect()

    assert "pearson_raw" in corr_df.columns
    assert "pearson_normalized" in corr_df.columns
    assert "spearman_raw" in corr_df.columns
    assert "spearman_normalized" in corr_df.columns

    rel_map = {r["relationship_id"]: r for r in rows}
    att_rel = rel_map["attendance_marks"]
    assert att_rel["spearman_raw"] == pytest.approx(1.0)
    assert att_rel["pearson_raw"] == pytest.approx(1.0)


def test_compute_lms_four_week_trends(spark_session: SparkSession) -> None:
    """Verify rolling 4-week LMS trend detection for stable and declining students (Task 8.6)."""
    # 16 teaching weeks for 2 students
    rows = []
    # STU_STABLE: 20 events every week (no decline)
    for w in range(1, 17):
        rows.append(("STU_STABLE", "CS101", "S1", w, 20))

    # STU_DECLINE: 30 events in weeks 1..10, then drops to 5 events in weeks 11..16 (<= 50% drop)
    for w in range(1, 17):
        events = 30 if w <= 10 else 5
        rows.append(("STU_DECLINE", "CS101", "S1", w, events))

    cols = ["student_id", "course_id", "semester_id", "week_number", "total_events"]
    df = spark_session.createDataFrame(rows, cols)

    trends_df = compute_lms_four_week_trends(df, window_weeks=4, comparison_ratio=0.50)
    results = {r["student_id"]: r for r in trends_df.collect()}

    stable = results["STU_STABLE"]
    assert stable["lms_decline_detected"] is False
    assert stable["lms_decline_start_week"] is None
    assert stable["lms_current_4w_events"] == 80  # 4 * 20
    assert stable["lms_prev_4w_events"] == 80  # 4 * 20
    assert stable["lms_recent_vs_prior_ratio"] == pytest.approx(1.0)
    assert stable["lms_weekly_slope"] == pytest.approx(0.0)

    decline = results["STU_DECLINE"]
    assert decline["lms_decline_detected"] is True
    # Rolling decline triggered when current 4w (weeks 8..11, 30+30+30+5=95 or weeks 9..12, 30+30+5+5=70 vs 120, etc.)
    # At week 14: current 4w (weeks 11..14 = 20) vs prev 4w (weeks 7..10 = 120), ratio = 0.167 <= 0.50
    assert decline["lms_decline_start_week"] is not None
    assert decline["lms_current_4w_events"] == 20  # weeks 13..16: 4 * 5
    assert decline["lms_prev_4w_events"] == 70  # weeks 9..10: 2 * 30 + weeks 11..12: 2 * 5 = 70
    assert decline["lms_recent_vs_prior_ratio"] <= 0.50
    assert decline["lms_weekly_slope"] < 0.0  # negative slope


def test_compute_coursework_marks_trends(spark_session: SparkSession) -> None:
    """Verify coursework marks trend detection comparing latest 3 items against earlier items (Task 8.6)."""
    data = [
        # STU_STABLE: 6 items with consistent 80-85% scores
        ("STU_STABLE", "CS101", "S1", "A01", "2024-07-29", 16.0, 20.0),  # 80%
        ("STU_STABLE", "CS101", "S1", "A02", "2024-08-12", 17.0, 20.0),  # 85%
        ("STU_STABLE", "CS101", "S1", "A03", "2024-08-26", 16.0, 20.0),  # 80%
        ("STU_STABLE", "CS101", "S1", "A04", "2024-09-09", 17.0, 20.0),  # 85%
        ("STU_STABLE", "CS101", "S1", "A05", "2024-09-23", 16.0, 20.0),  # 80%
        ("STU_STABLE", "CS101", "S1", "A06", "2024-10-07", 17.0, 20.0),  # 85%
        # STU_DECLINE: early items 90%, latest 3 items drop to 65% (drop 25 pts >= 10 pts)
        ("STU_DECLINE", "CS101", "S1", "A01", "2024-07-29", 18.0, 20.0),  # 90%
        ("STU_DECLINE", "CS101", "S1", "A02", "2024-08-12", 18.0, 20.0),  # 90%
        ("STU_DECLINE", "CS101", "S1", "A03", "2024-08-26", 18.0, 20.0),  # 90%
        ("STU_DECLINE", "CS101", "S1", "A04", "2024-09-09", 13.0, 20.0),  # 65%
        ("STU_DECLINE", "CS101", "S1", "A05", "2024-09-23", 13.0, 20.0),  # 65%
        ("STU_DECLINE", "CS101", "S1", "A06", "2024-10-07", 13.0, 20.0),  # 65%
    ]
    cols = ["student_id", "course_id", "semester_id", "item_id", "due_date", "score", "max_score"]
    df = spark_session.createDataFrame(data, cols)

    marks_trends = compute_coursework_marks_trends(df, recent_items=3, drop_threshold=10.0)
    results = {r["student_id"]: r for r in marks_trends.collect()}

    stable = results["STU_STABLE"]
    assert stable["marks_decline_detected"] is False
    assert stable["marks_drop_points"] <= 5.0

    decline = results["STU_DECLINE"]
    assert decline["marks_decline_detected"] is True
    assert decline["earlier_coursework_avg"] == pytest.approx(90.0)
    assert decline["recent_coursework_avg"] == pytest.approx(65.0)
    assert decline["marks_drop_points"] == pytest.approx(25.0)


def test_integrate_temporal_trends(spark_session: SparkSession) -> None:
    """Verify integration of LMS and marks temporal indicators."""
    lms_data = [("STU01", "CS101", "S1", True, 9, 0.40, 20, 50, 200, -2.5)]
    lms_cols = [
        "student_id", "course_id", "semester_id", "lms_decline_detected",
        "lms_decline_start_week", "lms_recent_vs_prior_ratio", "lms_current_4w_events",
        "lms_prev_4w_events", "lms_early_events_w1_8", "lms_weekly_slope",
    ]
    lms_df = spark_session.createDataFrame(lms_data, lms_cols)

    marks_data = [("STU01", "CS101", "S1", 6, 65.0, 85.0, 20.0, True)]
    marks_cols = [
        "student_id", "course_id", "semester_id", "total_graded_items",
        "recent_coursework_avg", "earlier_coursework_avg", "marks_drop_points",
        "marks_decline_detected",
    ]
    marks_df = spark_session.createDataFrame(marks_data, marks_cols)

    acad_data = [("STU01", "CS101", "S1", 30, 25, 18)]
    acad_cols = ["student_id", "course_id", "semester_id", "internal_marks", "midterm_marks", "endterm_marks"]
    acad_df = spark_session.createDataFrame(acad_data, acad_cols)

    integrated = integrate_temporal_trends(lms_df, marks_df, acad_df)
    rows = integrated.collect()
    assert len(rows) == 1
    r = rows[0]

    assert r["student_id"] == "STU01"
    assert r["lms_decline_detected"] is True
    assert r["marks_decline_detected"] is True
    assert r["lms_decline_start_week"] == 9
    assert r["marks_drop_points"] == pytest.approx(20.0)
    assert r["exam_marks_trend"] == -12  # 18 - 30


def test_run_j5_trend_detection_end_to_end(
    tmp_path: Path,
    spark_session: SparkSession,
) -> None:
    """Verify run_j5_trend_detection execution with Parquet inputs and output."""
    in_dir = tmp_path / "processed"
    out_dir = tmp_path / "trend_indicators"

    # 1. LMS weekly
    lms_rows = [("STU01", "CS101", "S1", w, 20) for w in range(1, 17)]
    lms_cols = ["student_id", "course_id", "semester_id", "week_number", "total_events"]
    lms_path = in_dir / "lms_weekly_engagement"
    spark_session.createDataFrame(lms_rows, lms_cols).write.parquet(str(lms_path))

    # 2. Coursework
    cw_rows = [("STU01", "CS101", "S1", f"A0{i}", f"2024-0{i+6}-01", 16.0, 20.0) for i in range(1, 5)]
    cw_cols = ["student_id", "course_id", "semester_id", "item_id", "due_date", "score", "max_score"]
    cw_path = in_dir / "coursework"
    spark_session.createDataFrame(cw_rows, cw_cols).write.parquet(str(cw_path))

    # 3. Academic records
    acad_path = in_dir / "academic_records"
    spark_session.createDataFrame(
        [("STU01", "CS101", "S1", 25, 25, 25)],
        ["student_id", "course_id", "semester_id", "internal_marks", "midterm_marks", "endterm_marks"],
    ).write.parquet(str(acad_path))

    cfg = J5Config(
        lms_weekly_path=lms_path,
        coursework_path=cw_path,
        academic_records_path=acad_path,
        output_path=out_dir,
        save_parquet=True,
    )

    res = run_j5_trend_detection(spark_session, cfg)
    assert res.total_rows == 1
    assert res.output_path == out_dir
    assert out_dir.exists()

    saved_df = spark_session.read.parquet(str(out_dir))
    assert saved_df.count() == 1
    assert "lms_decline_detected" in saved_df.columns
    assert "marks_decline_detected" in saved_df.columns


def test_no_large_collect_or_driver_iteration_in_j5() -> None:
    """Explicitly verify no large collect() or driver iteration exists in J5 or trends analytics (rules.md §17.3)."""
    for mod in (j5_job_module, trends_analytics_module):
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
