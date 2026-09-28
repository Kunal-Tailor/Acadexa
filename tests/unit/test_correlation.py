"""Unit tests for within-course normalization and Spearman correlation analytics (Tasks 8.3 & 8.4, rules.md §8, §17, §18)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from scipy.stats import spearmanr

from acadexa.analytics.correlation import (
    APPROVED_CORRELATION_RELATIONSHIPS,
    assign_fractional_ranks,
    compute_spearman_correlation,
    evaluate_planted_and_decoy_correlations,
    interpret_spearman_association,
)
import acadexa.analytics.correlation as corr_analytics_module
from acadexa.analytics.normalization import (
    DEFAULT_NORMALIZATION_METRICS,
    normalize_within_course,
)
import acadexa.analytics.normalization as norm_module
from acadexa.processing.jobs.correlation import (
    J4Config,
    J4Result,
    run_j4_correlation,
)
import acadexa.processing.jobs.correlation as j4_module
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for correlation and normalization tests."""
    cfg = SparkRuntimeConfig(app_name="TestCorrelationAnalytics", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def test_normalize_within_course(spark_session: SparkSession) -> None:
    """Verify within-course z-scoring standardizes metrics per course offering."""
    data = [
        # student_id, course_id, semester_id, academic_score, attendance_percentage
        ("STU01", "CS101", "S1", 60.0, 70.0),
        ("STU02", "CS101", "S1", 80.0, 90.0),
        ("STU03", "CS101", "S1", 100.0, 80.0),
        # Single-student course section (zero variance)
        ("STU04", "MATH201", "S1", 75.0, 85.0),
    ]
    df = spark_session.createDataFrame(
        data,
        ["student_id", "course_id", "semester_id", "academic_score", "attendance_percentage"],
    )

    norm_df = normalize_within_course(
        df,
        metric_cols=["academic_score", "attendance_percentage"],
        partition_cols=["course_id", "semester_id"],
    )

    rows = norm_df.collect()
    assert len(rows) == 4

    cs_rows = [r for r in rows if r["course_id"] == "CS101"]
    # CS101 academic scores: 60, 80, 100 -> mean 80, std 20 -> z: -1.0, 0.0, 1.0
    cs_scores = {r["student_id"]: r["z_academic_score"] for r in cs_rows}
    assert cs_scores["STU01"] == pytest.approx(-1.0)
    assert cs_scores["STU02"] == pytest.approx(0.0)
    assert cs_scores["STU03"] == pytest.approx(1.0)

    # Check difficulty_adjusted_performance alias
    for r in cs_rows:
        assert r["difficulty_adjusted_performance"] == r["z_academic_score"]

    # Single-student section: std is null -> z evaluates safely to 0.0
    math_row = next(r for r in rows if r["course_id"] == "MATH201")
    assert math_row["z_academic_score"] == 0.0
    assert math_row["z_attendance_percentage"] == 0.0


def test_assign_fractional_ranks(spark_session: SparkSession) -> None:
    """Verify fractional ranking assigns the exact average rank for tied values."""
    # Values: 10, 20, 20, 30 -> Ranks: 1.0, 2.5, 2.5, 4.0
    data = [(10.0,), (20.0,), (20.0,), (30.0,)]
    df = spark_session.createDataFrame(data, ["score"])

    ranked_df = assign_fractional_ranks(df, "score", "rank_score")
    ranks = [r["rank_score"] for r in ranked_df.orderBy("score").collect()]

    assert ranks == [1.0, 2.5, 2.5, 4.0]


def test_compute_spearman_correlation_mathematical_precision(
    spark_session: SparkSession,
) -> None:
    """Verify compute_spearman_correlation matches scipy.stats.spearmanr exactly."""
    data = [
        (12.0, 45.0),
        (25.0, 55.0),
        (32.0, 50.0),
        (45.0, 75.0),
        (55.0, 70.0),
        (68.0, 88.0),
        (80.0, 92.0),
    ]
    df = spark_session.createDataFrame(data, ["x", "y"])

    res_df = compute_spearman_correlation(df, "x", "y")
    spark_corr = res_df.first()["spearman_corr"]

    xs = [d[0] for d in data]
    ys = [d[1] for d in data]
    scipy_corr = spearmanr(xs, ys).statistic

    assert spark_corr == pytest.approx(scipy_corr, abs=1e-6)
    assert res_df.first()["sample_size"] == len(data)


def test_compute_spearman_correlation_stratified_by_school(
    spark_session: SparkSession,
) -> None:
    """Verify compute_spearman_correlation when grouped by school."""
    data = [
        # Perfect positive in SCET
        ("SCET", 10.0, 100.0),
        ("SCET", 20.0, 200.0),
        ("SCET", 30.0, 300.0),
        # Perfect negative in SOM
        ("SOM", 10.0, 300.0),
        ("SOM", 20.0, 200.0),
        ("SOM", 30.0, 100.0),
    ]
    df = spark_session.createDataFrame(data, ["school", "x", "y"])

    res_df = compute_spearman_correlation(df, "x", "y", group_by_col="school")
    rows = res_df.collect()
    assert len(rows) == 2

    scet_row = next(r for r in rows if r["school"] == "SCET")
    assert scet_row["spearman_corr"] == pytest.approx(1.0)
    assert scet_row["sample_size"] == 3

    som_row = next(r for r in rows if r["school"] == "SOM")
    assert som_row["spearman_corr"] == pytest.approx(-1.0)
    assert som_row["sample_size"] == 3


def test_interpret_spearman_association() -> None:
    """Verify standardized non-causal descriptions of association."""
    assert interpret_spearman_association(0.65) == "Strong positive association"
    assert interpret_spearman_association(0.35) == "Moderate positive association"
    assert interpret_spearman_association(0.15) == "Weak positive association"
    assert interpret_spearman_association(0.02) == "No observed monotonic association"
    assert interpret_spearman_association(-0.15) == "Weak negative association"
    assert interpret_spearman_association(-0.35) == "Moderate negative association"
    assert interpret_spearman_association(-0.65) == "Strong negative association"
    assert interpret_spearman_association(None) == "Insufficient variation to determine association"


def test_evaluate_planted_and_decoy_correlations(
    spark_session: SparkSession,
) -> None:
    """Verify evaluation of planted relationships and decoy relationship."""
    data = [
        # attendance_percentage, z_attendance_percentage, academic_score, z_academic_score, lms_total_events, z_lms_total_events, late_submission_rate, z_late_submission_rate, total_quiz_attempts, z_total_quiz_attempts, lms_forum_posts, z_lms_forum_posts, school
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

    corr_df = evaluate_planted_and_decoy_correlations(df)
    rows = corr_df.collect()
    assert len(rows) == len(APPROVED_CORRELATION_RELATIONSHIPS)

    rel_map = {r["relationship_id"]: r for r in rows}

    # Planted positive relationships
    att_rel = rel_map["attendance_marks"]
    assert att_rel["relationship_type"] == "planted"
    assert att_rel["spearman_raw"] == pytest.approx(1.0)
    assert att_rel["spearman_normalized"] == pytest.approx(1.0)
    assert att_rel["scope"] == "overall"

    lms_rel = rel_map["lms_engagement_marks"]
    assert lms_rel["spearman_raw"] == pytest.approx(1.0)

    # Planted negative relationship
    late_rel = rel_map["late_submissions_marks"]
    assert late_rel["spearman_raw"] == pytest.approx(-1.0)

    # Decoy relationship
    decoy_rel = rel_map["decoy_forum_marks"]
    assert decoy_rel["relationship_type"] == "decoy"


def test_run_j4_correlation_end_to_end(
    tmp_path: Path,
    spark_session: SparkSession,
) -> None:
    """Verify run_j4_correlation execution with Parquet inputs and output."""
    in_dir = tmp_path / "student_features"
    out_dir = tmp_path / "correlations"

    data = [
        ("STU01", "CS101", "S1", 60.0, 70.0, 150, 0.3, 2, 5, "SCET"),
        ("STU02", "CS101", "S1", 80.0, 85.0, 250, 0.1, 4, 6, "SCET"),
        ("STU03", "CS101", "S1", 95.0, 95.0, 350, 0.0, 6, 4, "SCET"),
    ]
    cols = [
        "student_id",
        "course_id",
        "semester_id",
        "academic_score",
        "attendance_percentage",
        "lms_total_events",
        "late_submission_rate",
        "total_quiz_attempts",
        "lms_forum_posts",
        "school",
    ]
    df = spark_session.createDataFrame(data, cols)
    df.write.parquet(str(in_dir))

    cfg = J4Config(
        input_path=in_dir,
        output_path=out_dir,
        save_parquet=True,
        group_by_col="school",
    )

    res = run_j4_correlation(spark_session, cfg)
    assert res.total_relationships_evaluated == len(APPROVED_CORRELATION_RELATIONSHIPS)
    assert res.output_path == out_dir
    assert (out_dir / "overall").exists()
    assert (out_dir / "by_school").exists()

    # Read back saved overall parquet
    saved_overall = spark_session.read.parquet(str(out_dir / "overall"))
    assert saved_overall.count() == len(APPROVED_CORRELATION_RELATIONSHIPS)


def test_no_large_collect_or_driver_iteration_in_j4_and_analytics() -> None:
    """Explicitly verify no large collect() or driver iteration exists in J4 or analytics (rules.md §17.3)."""
    for mod in (j4_module, corr_analytics_module, norm_module):
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
