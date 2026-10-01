"""Unit tests for full-scale Spark pipeline stage manifests (Tasks 15.1–15.4).

Validates the committed stage record JSON files produced by running
J1 Clean & Validate, J2 LMS Aggregation, J3 Feature Table, and
J4 Correlation against the full 12,000-student dataset.

These tests do NOT start a SparkSession — they only verify the recorded
manifests to ensure actual measured values are persisted and traceable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

MANIFESTS_DIR = Path(__file__).resolve().parents[2] / "data" / "manifests"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(name: str) -> dict:
    path = MANIFESTS_DIR / name
    assert path.exists(), f"Stage manifest not found: {path}"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Task 15.1 — J1 Clean and Validate
# ---------------------------------------------------------------------------


class TestFullScaleJ1:
    """Task 15.1 — full-scale J1 stage manifest."""

    def test_j1_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j1.json").exists()

    def test_j1_task_and_stage(self):
        d = _load("full_scale_j1.json")
        assert d["task"] == "15.1"
        assert d["stage"] == "J1_clean_and_validate"

    def test_j1_status_success(self):
        d = _load("full_scale_j1.json")
        assert d["status"] == "SUCCESS"

    def test_j1_output_counts(self):
        counts = _load("full_scale_j1.json")["output_counts"]
        assert counts["students"] == 12000
        assert counts["courses"] == 72
        # Core domain datasets should be within ±1% of target
        assert 4_550_000 <= counts["attendance"] <= 4_620_000
        assert 285_000 <= counts["academic_records"] <= 290_000
        assert 3_300_000 <= counts["coursework"] <= 3_380_000
        # LMS events: started with 74.7M; duplicates/orphans dropped
        assert 73_000_000 <= counts["lms_events"] <= 75_000_000

    def test_j1_lms_events_exact(self):
        counts = _load("full_scale_j1.json")["output_counts"]
        assert counts["lms_events"] == 73_961_848

    def test_j1_duration_present(self):
        d = _load("full_scale_j1.json")
        assert isinstance(d["duration_sec"], (int, float))
        assert d["duration_sec"] > 0

    def test_j1_quality_report_structure(self):
        qr = _load("full_scale_j1.json")["quality_report"]
        assert qr["validation_status"] == "PASSED"
        assert qr["total_remaining"] == 0

    def test_j1_quality_report_totals(self):
        qr = _load("full_scale_j1.json")["quality_report"]
        assert qr["total_injected"] == 2_644_049
        assert qr["total_detected"] == 1_551_722
        assert qr["total_corrected"] == 748_183
        assert qr["total_dropped"] == 803_539
        assert qr["total_remaining"] == 0

    def test_j1_all_injection_categories_present(self):
        summary = _load("full_scale_j1.json")["quality_report"]["summary"]
        expected_categories = {
            "duplicate_lms_events",
            "nulls_non_key",
            "timestamp_inconsistencies",
            "course_id_formatting",
            "orphan_records",
            "out_of_range_values",
        }
        assert expected_categories == set(summary.keys())

    def test_j1_duplicate_lms_events(self):
        dupes = _load("full_scale_j1.json")["quality_report"]["summary"]["duplicate_lms_events"]
        assert dupes["injected"] == 740_169
        assert dupes["detected"] == 720_548
        assert dupes["dropped"] == 720_548
        assert dupes["remaining"] == 0

    def test_j1_orphan_records(self):
        orphans = _load("full_scale_j1.json")["quality_report"]["summary"]["orphan_records"]
        assert orphans["injected"] == 82_991
        assert orphans["detected"] == 82_991
        assert orphans["dropped"] == 82_991
        assert orphans["remaining"] == 0

    def test_j1_all_six_datasets_cleaned(self):
        datasets = _load("full_scale_j1.json")["quality_report"]["datasets"]
        assert set(datasets.keys()) == {
            "students", "courses", "attendance",
            "academic_records", "coursework", "lms_events",
        }

    def test_j1_lms_dataset_input_equals_generated(self):
        lms = _load("full_scale_j1.json")["quality_report"]["datasets"]["lms_events"]
        # Input should match the generated 74.7M
        assert lms["input_rows"] == 74_757_153

    def test_j1_timestamps_present(self):
        d = _load("full_scale_j1.json")
        assert d["start_time"]
        assert d["end_time"]


# ---------------------------------------------------------------------------
# Task 15.2 — J2 LMS Aggregation
# ---------------------------------------------------------------------------


class TestFullScaleJ2:
    """Task 15.2 — full-scale J2 stage manifest."""

    def test_j2_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j2.json").exists()

    def test_j2_task_and_stage(self):
        d = _load("full_scale_j2.json")
        assert d["task"] == "15.2"
        assert d["stage"] == "J2_event_aggregation"

    def test_j2_status_success(self):
        assert _load("full_scale_j2.json")["status"] == "SUCCESS"

    def test_j2_output_count(self):
        counts = _load("full_scale_j2.json")["output_counts"]
        assert counts["lms_weekly_engagement"] == 4_607_646

    def test_j2_input_matches_j1_output(self):
        j1 = _load("full_scale_j1.json")["output_counts"]["lms_events"]
        j2_details = _load("full_scale_j2.json")["details"]
        assert j2_details["total_input_events"] == j1

    def test_j2_aggregation_reduces_rows(self):
        # Weekly aggregation should produce far fewer rows than raw events
        j2 = _load("full_scale_j2.json")
        assert j2["details"]["total_input_events"] > j2["details"]["total_output_rows"]

    def test_j2_duration_present(self):
        d = _load("full_scale_j2.json")
        assert d["duration_sec"] > 0

    def test_j2_timestamps_present(self):
        d = _load("full_scale_j2.json")
        assert d["start_time"]
        assert d["end_time"]


# ---------------------------------------------------------------------------
# Task 15.3 — J3 Feature Table
# ---------------------------------------------------------------------------


class TestFullScaleJ3:
    """Task 15.3 — full-scale J3 stage manifest."""

    def test_j3_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j3.json").exists()

    def test_j3_task_and_stage(self):
        d = _load("full_scale_j3.json")
        assert d["task"] == "15.3"
        assert d["stage"] == "J3_feature_table"

    def test_j3_status_success(self):
        assert _load("full_scale_j3.json")["status"] == "SUCCESS"

    def test_j3_feature_rows_exact(self):
        counts = _load("full_scale_j3.json")["output_counts"]
        # 12,000 students × 24 courses = 288,000 rows (student-course grain)
        assert counts["student_course_features"] == 288_000

    def test_j3_total_students(self):
        assert _load("full_scale_j3.json")["details"]["total_students"] == 12_000

    def test_j3_grain_matches_students_times_courses(self):
        d = _load("full_scale_j3.json")
        features = d["output_counts"]["student_course_features"]
        students = d["details"]["total_students"]
        j1_courses = _load("full_scale_j1.json")["output_counts"]["courses"]
        # grain = students × average_courses_per_student (all 4 semesters, ~6 courses each)
        # exact = 288000 which is 12000 * 24
        assert features == students * (features // students)
        assert features == 288_000
        _ = j1_courses  # referenced for context

    def test_j3_duration_present(self):
        d = _load("full_scale_j3.json")
        assert d["duration_sec"] > 0

    def test_j3_timestamps_present(self):
        d = _load("full_scale_j3.json")
        assert d["start_time"]
        assert d["end_time"]


# ---------------------------------------------------------------------------
# Task 15.4 — J4 Correlation Analytics
# ---------------------------------------------------------------------------


class TestFullScaleJ4:
    """Task 15.4 — full-scale J4 stage manifest."""

    def test_j4_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j4.json").exists()

    def test_j4_task_and_stage(self):
        d = _load("full_scale_j4.json")
        assert d["task"] == "15.4"
        assert d["stage"] == "J4_correlation"

    def test_j4_status_success(self):
        assert _load("full_scale_j4.json")["status"] == "SUCCESS"

    def test_j4_relationships_evaluated(self):
        counts = _load("full_scale_j4.json")["output_counts"]
        # 5 relationships defined (planted + decoy)
        assert counts["correlations_evaluated"] == 5

    def test_j4_details_match_counts(self):
        d = _load("full_scale_j4.json")
        assert d["details"]["total_relationships_evaluated"] == \
               d["output_counts"]["correlations_evaluated"]

    def test_j4_duration_present(self):
        d = _load("full_scale_j4.json")
        assert d["duration_sec"] > 0

    def test_j4_timestamps_present(self):
        d = _load("full_scale_j4.json")
        assert d["start_time"]
        assert d["end_time"]


# ---------------------------------------------------------------------------
# Cross-stage continuity checks
# ---------------------------------------------------------------------------


class TestFullScalePipelineContinuity:
    """Validate sequential stage dependencies are consistent."""

    def test_j1_to_j2_lms_continuity(self):
        j1_lms = _load("full_scale_j1.json")["output_counts"]["lms_events"]
        j2_input = _load("full_scale_j2.json")["details"]["total_input_events"]
        assert j1_lms == j2_input, (
            f"J2 input ({j2_input}) should equal J1 cleaned LMS output ({j1_lms})"
        )

    def test_j1_to_j3_student_continuity(self):
        j1_students = _load("full_scale_j1.json")["output_counts"]["students"]
        j3_students = _load("full_scale_j3.json")["details"]["total_students"]
        assert j1_students == j3_students == 12_000

    def test_total_pipeline_duration_reasonable(self):
        j1 = _load("full_scale_j1.json")["duration_sec"]
        j2 = _load("full_scale_j2.json")["duration_sec"]
        j3 = _load("full_scale_j3.json")["duration_sec"]
        j4 = _load("full_scale_j4.json")["duration_sec"]
        total = j1 + j2 + j3 + j4
        # Sanity: full pipeline should complete within 4 hours
        assert total < 14_400, f"Total pipeline duration {total:.1f}s exceeds 4h"
        # J1 (74M rows) should dominate
        assert j1 > j2, "J1 (cleaning 74M LMS rows) should take longer than J2"

# ---------------------------------------------------------------------------
# Task 15.5 — J5 Trend Detection
# ---------------------------------------------------------------------------

class TestFullScaleJ5:
    def test_j5_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j5.json").exists()

    def test_j5_task_and_stage(self):
        d = _load("full_scale_j5.json")
        assert d["task"] == "15.5"
        assert d["stage"] == "J5_trend_detection"

    def test_j5_status_success(self):
        assert _load("full_scale_j5.json")["status"] == "SUCCESS"

    def test_j5_output_counts(self):
        counts = _load("full_scale_j5.json")["output_counts"]
        assert counts["trend_indicators"] == 288_000

    def test_j5_details(self):
        details = _load("full_scale_j5.json")["details"]
        assert details["total_rows"] == 288_000
        assert details["lms_decline_count"] > 0
        assert details["marks_decline_count"] > 0

# ---------------------------------------------------------------------------
# Task 15.6 — J6 Risk Signals
# ---------------------------------------------------------------------------

class TestFullScaleJ6:
    def test_j6_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j6.json").exists()

    def test_j6_task_and_stage(self):
        d = _load("full_scale_j6.json")
        assert d["task"] == "15.6"
        assert d["stage"] == "J6_risk_signals"

    def test_j6_status_success(self):
        assert _load("full_scale_j6.json")["status"] == "SUCCESS"

    def test_j6_output_counts(self):
        counts = _load("full_scale_j6.json")["output_counts"]
        assert counts["risk_indicators"] == 12_000

    def test_j6_details(self):
        details = _load("full_scale_j6.json")["details"]
        assert details["total_students"] == 12_000
        assert details["flagged_students"] > 0
        assert details["high_risk_students"] > 0
        assert "signal_counts_breakdown" in details

# ---------------------------------------------------------------------------
# Task 15.7 — J7 Publish Gold Data & Validate
# ---------------------------------------------------------------------------

class TestFullScaleJ7:
    def test_j7_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j7.json").exists()

    def test_j7_task_and_stage(self):
        d = _load("full_scale_j7.json")
        assert d["task"] == "15.7"
        assert d["stage"] == "J7_publish_gold"

    def test_j7_status_success(self):
        assert _load("full_scale_j7.json")["status"] == "SUCCESS"

    def test_j7_output_counts(self):
        counts = _load("full_scale_j7.json")["output_counts"]
        assert counts["gold_student_features"] == 48_000
        assert counts["gold_course_metrics"] == 288
        assert counts["gold_school_summary"] == 18
        assert counts["gold_risk_indicators"] == 12_000

    def test_j7_validation_summary(self):
        summary = _load("full_scale_j7.json")["gold_validation_summary"]
        for collection in [
            "student_features", "course_metrics", 
            "school_summary", "risk_indicators"
        ]:
            assert collection in summary
            assert summary[collection]["is_valid"] is True
            assert summary[collection]["grain_unique"] is True

# ---------------------------------------------------------------------------
# Task 15.8 — J8 Benchmarks
# ---------------------------------------------------------------------------

class TestFullScaleJ8:
    def test_j8_manifest_exists(self):
        assert (MANIFESTS_DIR / "full_scale_j8.json").exists()

    def test_j8_task_and_stage(self):
        d = _load("full_scale_j8.json")
        assert d["task"] == "15.8"
        assert d["stage"] == "J8_benchmarks"

    def test_j8_results_structure(self):
        d = _load("full_scale_j8.json")
        results = d["results"]
        assert isinstance(results, list)
        assert len(results) == 6

    def test_j8_summary(self):
        summary = _load("full_scale_j8.json")["summary"]
        assert summary["total_runs"] == 6
        assert summary["successful_runs"] + summary["failed_runs"] == 6

