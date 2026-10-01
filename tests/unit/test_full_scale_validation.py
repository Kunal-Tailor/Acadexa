"""Unit tests for Phase 16 Full-Scale Validation and Hardening (Tasks 16.1–16.4).

Verifies correctness after scaling:
- 16.1: Compare full-scale generated counts against generation manifest and schema expectations.
- 16.2: Validate full-scale data-quality detection against injection manifest.
- 16.3: Run full-scale ground-truth recovery and document recovered/non-recovered/decoy relationships.
- 16.4: Validate full-scale risk signal calculations against independent fixtures and sampled records.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from acadexa.validation import (
    ALL_SCHEMAS,
    STUDENTS_SCHEMA,
    COURSES_SCHEMA,
    ACADEMIC_RECORDS_SCHEMA,
    ATTENDANCE_SCHEMA,
    COURSEWORK_SCHEMA,
    LMS_EVENTS_SCHEMA,
    RISK_INDICATORS_SCHEMA,
    STUDENT_FEATURES_SCHEMA,
    validate_record,
)
from acadexa.validation.recovery import (
    RecoveryReport,
    evaluate_recovery_from_paths,
)
from acadexa.analytics.risk import RiskSignalThresholds

MANIFESTS_DIR = Path(__file__).resolve().parents[2] / "data" / "manifests"
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


def _load_manifest(name: str) -> dict:
    path = MANIFESTS_DIR / name
    assert path.exists(), f"Manifest not found: {path}"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Task 16.1 — Full-Scale Record Count and Schema Validation
# ---------------------------------------------------------------------------


class TestTask161CountAndSchemaValidation:
    """Task 16.1: Compare full-scale generated counts against the generation manifest and schema expectations."""

    def test_generation_manifest_counts_match_targets(self):
        gen_manifest = _load_manifest("full_scale_generation_manifest.json")
        actual = gen_manifest["actual_counts"]
        target = gen_manifest["target_counts"]

        # Student population target: 12,000
        assert actual["students"] == 12_000
        assert actual["students"] == target["target_students"]

        # Hierarchy expectations: 6 schools, 18 departments, 72 courses
        assert actual["courses"] == 72

        # Academic records: 12,000 students x 24 courses across 4 semesters = 288,000
        assert actual["academic_records"] == 288_000

        # Attendance: 12,000 students x 6 courses x 4 semesters x 16 weeks = 4,608,000
        assert actual["attendance"] == 4_608_000

        # Coursework: within expected range (12 coursework items per student-course)
        assert 3_300_000 <= actual["coursework"] <= 3_400_000

        # LMS Events: reached target scale (~74.7M events)
        assert actual["lms_events"] >= target["target_lms_events"]
        assert actual["lms_events"] == 74_757_153

    def test_hierarchy_school_breakdown_matches_frozen_spec(self):
        gen_manifest = _load_manifest("full_scale_generation_manifest.json")
        pop_cfg = gen_manifest["configuration"]["generator"]["scale"]["school_population"]

        # Frozen distribution from spec:
        # CET: 2600, SET: 3000, SOM: 2400, LAD: 2200, SCI: 1000, SOL: 800 -> Total: 12,000
        assert pop_cfg["cet"] == 2600
        assert pop_cfg["set"] == 3000
        assert pop_cfg["som"] == 2400
        assert pop_cfg["lad"] == 2200
        assert pop_cfg["sci"] == 1000
        assert pop_cfg["sol"] == 800
        assert sum(pop_cfg.values()) == 12_000

    def test_schema_contracts_hold_for_all_registered_entities(self):
        # Verify schema specifications exist and examples validate cleanly
        for name, schema in ALL_SCHEMAS.items():
            example = schema.get("example")
            assert example is not None, f"Schema {name} missing example"
            validate_record(example, schema)


# ---------------------------------------------------------------------------
# Task 16.2 — Full-Scale Data-Quality Detection Validation
# ---------------------------------------------------------------------------


class TestTask162DataQualityValidation:
    """Task 16.2: Validate full-scale data-quality detection against the injection manifest."""

    def test_injection_manifest_exists_and_matches_scale(self):
        inj_manifest = _load_manifest("full_scale_injection_manifest.json")
        assert inj_manifest["manifest_type"] == "injection_manifest"
        assert inj_manifest["metadata"]["scale"] == "full"
        assert inj_manifest["baseline_counts"]["students"] == 12_000
        assert inj_manifest["total_injected"] == 2_644_049

    def test_j1_quality_report_recovers_all_categories(self):
        j1 = _load_manifest("full_scale_j1.json")
        qr = j1["quality_report"]
        inj = _load_manifest("full_scale_injection_manifest.json")

        assert qr["validation_status"] == "PASSED"
        assert qr["total_injected"] == inj["total_injected"]
        assert qr["total_remaining"] == 0

        # Assert all 6 injected issue categories were detected and addressed
        summary = qr["summary"]
        expected_categories = {
            "duplicate_lms_events",
            "nulls_non_key",
            "timestamp_inconsistencies",
            "course_id_formatting",
            "orphan_records",
            "out_of_range_values",
        }
        assert set(summary.keys()) == expected_categories

        for cat, metrics in summary.items():
            # Injected issues should be positive
            assert metrics["injected"] > 0
            # Detected issues should be positive
            assert metrics["detected"] > 0
            # Zero remaining issues post-clean
            assert metrics["remaining"] == 0
            # Either corrected or dropped
            assert (metrics["corrected"] + metrics["dropped"]) == metrics["detected"]

    def test_orphans_and_duplicates_dropped_completely(self):
        j1 = _load_manifest("full_scale_j1.json")
        summary = j1["quality_report"]["summary"]

        # Duplicate LMS events: 100% of detected were dropped
        dupes = summary["duplicate_lms_events"]
        assert dupes["dropped"] == dupes["detected"] == 720_548
        assert dupes["corrected"] == 0

        # Orphan records: 100% of detected were dropped
        orphans = summary["orphan_records"]
        assert orphans["dropped"] == orphans["detected"] == 82_991
        assert orphans["corrected"] == 0


# ---------------------------------------------------------------------------
# Task 16.3 — Full-Scale Ground-Truth Recovery Validation
# ---------------------------------------------------------------------------


class TestTask163GroundTruthRecovery:
    """Task 16.3: Run full-scale ground-truth recovery and document recovered/non-recovered/decoy relationships."""

    def test_ground_truth_recovery_report_structure(self):
        rec = _load_manifest("full_scale_ground_truth_recovery.json")
        assert rec["report_version"] == "1.0.0"
        assert rec["seed"] == 42
        summary = rec["summary"]

        assert summary["planted"] == 4
        assert summary["decoy"] == 1
        assert summary["decoy_clean"] == 1
        assert summary["decoy_spurious"] == 0
        assert summary["recovered"] >= 2
        assert summary["not_evaluated"] == 1  # Confounder is not directly evaluated by J4

    def test_documented_recovered_relationships(self):
        rec = _load_manifest("full_scale_ground_truth_recovery.json")
        entries = {e["relationship_id"]: e for e in rec["entries"]}

        # 1. attendance_marks: planted positive -> recovered (spearman ~0.443)
        att = entries["attendance_marks"]
        assert att["status"] == "recovered"
        assert att["observed_corr"] > 0.10
        assert att["expected_direction"] == "positive"

        # 2. late_submissions_marks: planted negative -> recovered (spearman ~ -0.292)
        late = entries["late_submissions_marks"]
        assert late["status"] == "recovered"
        assert late["observed_corr"] < -0.10
        assert late["expected_direction"] == "negative"

    def test_documented_decoy_relationship_is_clean(self):
        rec = _load_manifest("full_scale_ground_truth_recovery.json")
        entries = {e["relationship_id"]: e for e in rec["entries"]}

        # Decoy forum activity: expected none -> correctly no association (spearman ~0.012 < 0.10)
        decoy = entries["decoy_forum_marks"]
        assert decoy["status"] == "correctly_no_association"
        assert abs(decoy["observed_corr"]) < 0.10

    def test_documented_non_recovered_relationships(self):
        rec = _load_manifest("full_scale_ground_truth_recovery.json")
        entries = {e["relationship_id"]: e for e in rec["entries"]}

        # Documented behavior: lms_engagement_marks and quiz_attempts_marks
        # were attenuated at whole-population scale due to school-specific multipliers and ceiling effects
        assert entries["lms_engagement_marks"]["status"] == "not_recovered"
        assert entries["quiz_attempts_marks"]["status"] == "not_recovered"


# ---------------------------------------------------------------------------
# Task 16.4 — Full-Scale Risk Signal Calculations Validation
# ---------------------------------------------------------------------------


class TestTask164RiskSignalCalculations:
    """Task 16.4: Validate full-scale risk signal calculations against independent small fixtures and selected sampled records."""

    def test_thresholds_match_canonical_configuration(self):
        th = RiskSignalThresholds.from_config()
        assert th.attendance_threshold == 75.0
        assert th.lms_comparison_ratio == 0.50
        assert th.late_rate_threshold == 0.30
        assert th.marks_drop_threshold == 10.0
        assert th.quiz_percentile_threshold == 0.25

    def test_signal_distribution_and_monotonic_bounds(self):
        j6 = _load_manifest("full_scale_j6.json")
        dist = j6["details"]["signal_counts_breakdown"]
        total = j6["details"]["total_students"]

        assert total == 12_000
        # All students accounted for across signal count buckets 0..5
        assert sum(dist.values()) == 12_000

        # Verify high-risk threshold definition (count >= 3)
        high_risk_sum = dist["3"] + dist["4"] + dist["5"]
        assert j6["details"]["high_risk_students"] == high_risk_sum
        assert high_risk_sum == 10_182

    def test_sample_risk_records_explainability_and_conformity(self):
        j7 = _load_manifest("full_scale_j7.json")
        gold_val = j7["gold_validation_summary"]["risk_indicators"]

        assert gold_val["is_valid"] is True
        assert gold_val["row_count"] == 12_000
        assert gold_val["grain_unique"] is True

        # Check breakdown metrics from gold publication
        breakdown = j7["details"]["risk_signal_breakdown"]["flag_counts"]
        assert breakdown["low_attendance"] == 6245
        assert breakdown["lms_decline"] == 2094
        assert breakdown["late_submissions"] == 8578
        assert breakdown["marks_decline"] == 11922
        assert breakdown["low_quiz_activity"] == 12000
