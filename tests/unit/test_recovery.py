"""Unit tests for ground-truth recovery comparison (Task 10.2, rules.md §9, §31).

Verifies that planted relationships, the decoy relationship and missing
observations are distinguished as planted / recovered / not recovered /
decoy without modifying the registry after observing analytics. Uses small
fixtures only; the single Spark test collects just the tiny J4 result
(5 rows), never large datasets.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from acadexa.analytics.correlation import evaluate_planted_and_decoy_correlations
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)
from acadexa.validation.recovery import (
    DECOY_NULL_THRESHOLD,
    RECOVERY_NEGATIVE_THRESHOLD,
    RECOVERY_POSITIVE_THRESHOLD,
    RecoveryReport,
    classify_recovery,
    compare_ground_truth_recovery,
    evaluate_recovery_from_paths,
    select_primary_observation,
)


def _fixture_ground_truth() -> dict:
    """Minimal registry-shaped fixture (read, never modified)."""
    return {
        "seed": 42,
        "planted_relationships": [
            {
                "id": "attendance_marks",
                "relationship_type": "planted",
                "expected_direction": "positive",
                "expected_strength": "moderate",
            },
            {
                "id": "late_submissions_marks",
                "relationship_type": "planted",
                "expected_direction": "negative",
                "expected_strength": "moderate",
            },
        ],
        "decoy_relationship": {
            "id": "decoy_forum_marks",
            "relationship_type": "decoy",
            "expected_direction": "none",
            "expected_strength": "none",
        },
    }


def _observed(
    relationship_id: str, raw: float | None, normalized: float | None = None
) -> dict:
    """Build one J4-shaped observed row."""
    return {
        "relationship_id": relationship_id,
        "scope": "overall",
        "spearman_raw": raw,
        "spearman_normalized": normalized if normalized is not None else raw,
        "sample_size": 12,
    }


def test_recovery_thresholds_are_predefined_and_documented() -> None:
    """Thresholds are fixed constants aligned with the ±0.10 association boundary."""
    assert RECOVERY_POSITIVE_THRESHOLD == 0.10
    assert RECOVERY_NEGATIVE_THRESHOLD == -0.10
    assert DECOY_NULL_THRESHOLD == 0.10


def test_select_primary_observation_prefers_normalized() -> None:
    """Within-course normalized coefficient is primary; raw is fallback."""
    assert (
        select_primary_observation(
            {"spearman_raw": 0.05, "spearman_normalized": 0.42}
        )
        == 0.42
    )
    assert (
        select_primary_observation({"spearman_raw": 0.31, "spearman_normalized": None})
        == 0.31
    )
    assert (
        select_primary_observation({"spearman_raw": None, "spearman_normalized": None})
        is None
    )


def test_planted_positive_recovered_and_not_recovered() -> None:
    """Positive planted expectation recovers at/above +0.10 only."""
    assert classify_recovery("positive", "planted", 0.45) == "recovered"
    assert classify_recovery("positive", "planted", 0.10) == "recovered"
    assert classify_recovery("positive", "planted", 0.02) == "not_recovered"
    assert classify_recovery("positive", "planted", -0.30) == "not_recovered"


def test_planted_negative_recovered_and_not_recovered() -> None:
    """Negative planted expectation recovers at/below -0.10 only."""
    assert classify_recovery("negative", "planted", -0.45) == "recovered"
    assert classify_recovery("negative", "planted", -0.10) == "recovered"
    assert classify_recovery("negative", "planted", 0.03) == "not_recovered"
    assert classify_recovery("negative", "planted", 0.50) == "not_recovered"


def test_decoy_negative_control_classification() -> None:
    """Decoy shows no association below |0.10, else spurious association."""
    assert classify_recovery("none", "decoy", 0.02) == "correctly_no_association"
    assert classify_recovery("none", "decoy", -0.09) == "correctly_no_association"
    assert classify_recovery("none", "decoy", 0.35) == "spurious_association"
    assert classify_recovery("none", "decoy", -0.25) == "spurious_association"
    assert classify_recovery("positive", "planted", None) == "not_evaluated"


def test_compare_distinguishes_planted_recovered_and_decoy() -> None:
    """Full comparison reports planted/recovered/not-recovered/decoy separately."""
    ground_truth = _fixture_ground_truth()
    snapshot = json.loads(json.dumps(ground_truth))
    observed = [
        _observed("attendance_marks", 0.55),
        _observed("late_submissions_marks", 0.04),
        _observed("decoy_forum_marks", 0.02),
    ]

    report = compare_ground_truth_recovery(ground_truth, observed, scope="overall")

    # Registry must not be modified by the comparison.
    assert ground_truth == snapshot
    assert report.seed == 42
    by_id = {e.relationship_id: e for e in report.entries}
    assert by_id["attendance_marks"].status == "recovered"
    assert by_id["late_submissions_marks"].status == "not_recovered"
    assert by_id["decoy_forum_marks"].status == "correctly_no_association"
    assert report.summary["planted"] == 2
    assert report.summary["recovered"] == 1
    assert report.summary["not_recovered"] == 1
    assert report.summary["decoy"] == 1
    assert report.summary["decoy_clean"] == 1
    assert report.summary["decoy_spurious"] == 0
    # Non-causal language only.
    for entry in report.entries:
        assert "caus" not in entry.interpretation.lower()


def test_compare_marks_missing_observation_not_evaluated() -> None:
    """Planted relationships without analytics output are not_evaluated."""
    ground_truth = _fixture_ground_truth()
    observed = [_observed("attendance_marks", 0.60)]

    report = compare_ground_truth_recovery(ground_truth, observed)
    by_id = {e.relationship_id: e for e in report.entries}
    assert by_id["attendance_marks"].status == "recovered"
    assert by_id["late_submissions_marks"].status == "not_evaluated"
    assert by_id["late_submissions_marks"].observed_corr is None
    assert by_id["decoy_forum_marks"].status == "not_evaluated"
    assert report.summary["not_evaluated"] == 2


def test_recovery_report_save_and_load_roundtrip(tmp_path: Path) -> None:
    """Report serializes to JSON and loads back with identical content."""
    report = compare_ground_truth_recovery(
        _fixture_ground_truth(),
        [
            _observed("attendance_marks", 0.50),
            _observed("late_submissions_marks", -0.40),
            _observed("decoy_forum_marks", 0.55),
        ],
    )
    target = tmp_path / "recovery" / "ground_truth_recovery.json"
    saved = report.save(target)
    assert saved.exists()

    loaded = RecoveryReport.load(target)
    assert loaded.seed == report.seed
    assert loaded.summary == report.summary
    assert [e.status for e in loaded.entries] == [
        e.status for e in report.entries
    ]
    assert loaded.entries[2].status == "spurious_association"


def test_evaluate_recovery_from_json_files(tmp_path: Path) -> None:
    """File-based evaluation reads registry + correlation JSON and writes a report."""
    gt_path = tmp_path / "ground_truth_registry.json"
    gt_path.write_text(json.dumps(_fixture_ground_truth()), encoding="utf-8")
    corr_path = tmp_path / "correlations.json"
    corr_path.write_text(
        json.dumps(
            [
                _observed("attendance_marks", 0.33),
                _observed("late_submissions_marks", -0.28),
                _observed("decoy_forum_marks", 0.01),
            ]
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "reports" / "ground_truth_recovery.json"

    report = evaluate_recovery_from_paths(gt_path, corr_path, out_path)

    assert out_path.exists()
    assert report.summary["recovered"] == 2
    assert report.summary["decoy_clean"] == 1


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession for the small recovery integration check."""
    cfg = SparkRuntimeConfig(app_name="TestGroundTruthRecovery", shuffle_partitions=2)
    spark = get_or_create_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def test_spark_correlation_recovery_marks_planted(spark_session: SparkSession) -> None:
    """J4 output on a perfectly associated fixture recovers planted signals."""
    data = [
        (70.0, -1.0, 60.0, -1.0, 100, -1.0, 0.4, 1.0, 2, -1.0, 10, 0.2, "SCET"),
        (80.0, 0.0, 75.0, 0.0, 200, 0.0, 0.2, 0.0, 4, 0.0, 12, -0.3, "SCET"),
        (90.0, 1.0, 90.0, 1.0, 300, 1.0, 0.0, -1.0, 6, 1.0, 8, 0.1, "SCET"),
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
    # Tiny J4 result (one row per relationship); bounded driver read is intentional.
    observed_rows = [row.asDict() for row in corr_df.collect()]

    ground_truth = _fixture_ground_truth()
    report = compare_ground_truth_recovery(ground_truth, observed_rows)
    by_id = {e.relationship_id: e for e in report.entries}

    assert by_id["attendance_marks"].status == "recovered"
    assert by_id["late_submissions_marks"].status == "recovered"
    # Decoy entry must exist with a valid negative-control status.
    assert by_id["decoy_forum_marks"].status in (
        "correctly_no_association",
        "spurious_association",
    )
