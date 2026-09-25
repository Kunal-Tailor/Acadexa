"""Tests for controlled data-quality injection (task 5.6).

Verifies:
- All six approved quality-issue categories:
  1. Duplicate LMS events (~1%).
  2. Nulls in selected non-key fields (~1.5%) with key identifiers strictly protected.
  3. Timestamp format inconsistencies (~1%).
  4. Course ID formatting (casing and whitespace) (~0.5%).
  5. Orphan records (~0.1%).
  6. Out-of-range values (~0.1%).
- Accurate recording of exact injected counts (rules.md §10.2).
- Non-destructive execution on record copies.
- Seeded reproducibility using child RNG sub-stream.
- Multi-collection dataset injection and InjectionReport serialization.
"""

from __future__ import annotations

import copy
from datetime import date, datetime
import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    DEFAULT_INJECTION_RATES,
    INJECTION_RATE_KEYS,
    GeneratorError,
    GeneratorRun,
    InjectionReport,
    get_injection_rates,
    inject_course_id_formatting,
    inject_data_quality,
    inject_duplicate_lms_events,
    inject_nulls_non_key,
    inject_orphan_records,
    inject_out_of_range_values,
    inject_quality_issues_academic_records,
    inject_quality_issues_attendance,
    inject_quality_issues_coursework,
    inject_quality_issues_lms_events,
    inject_timestamp_inconsistencies,
)
from acadexa.generator.quality_injection import FORBIDDEN_NULL_KEYS


def _make_sample_lms_events(count: int = 50) -> list[dict]:
    """Create sample valid LMS events for testing."""
    events = []
    for i in range(count):
        events.append(
            {
                "timestamp": datetime(2025, 9, (i % 25) + 1, 10, i % 60),
                "meta": {
                    "student_id": f"STU{100000 + i:06d}",
                    "course_id": "CSE101",
                    "school": "CET",
                },
                "activity_type": "VIDEO_VIEW",
                "resource_id": f"R{100 + i}",
                "duration_sec": 300 + i * 10,
                "session_id": f"SES{2000000 + i:07d}",
            }
        )
    return events


def _make_sample_academic_records(count: int = 50) -> list[dict]:
    """Create sample academic records for testing."""
    records = []
    for i in range(count):
        records.append(
            {
                "student_id": f"STU{100000 + i:06d}",
                "course_id": "CSE101",
                "semester_id": "S1",
                "internal_marks": 35,
                "midterm_marks": 20,
                "endterm_marks": 38,
                "final_grade": "A",
            }
        )
    return records


def _make_sample_attendance(count: int = 50) -> list[dict]:
    """Create sample attendance rows for testing."""
    attendance = []
    for i in range(count):
        attendance.append(
            {
                "student_id": f"STU{100000 + i:06d}",
                "course_id": "CSE101",
                "semester_id": "S1",
                "week_start": date(2025, 9, 8),
                "classes_conducted": 4,
                "classes_attended": 3,
            }
        )
    return attendance


def _make_sample_coursework(count: int = 50) -> list[dict]:
    """Create sample coursework rows for testing."""
    coursework = []
    for i in range(count):
        coursework.append(
            {
                "student_id": f"STU{100000 + i:06d}",
                "course_id": "CSE101",
                "item_id": f"A{i:02d}",
                "item_type": "ASSIGNMENT",
                "assigned_date": date(2025, 9, 1),
                "due_date": date(2025, 9, 15),
                "submitted_at": datetime(2025, 9, 14, 18, 30),
                "score": 18,
                "max_score": 20,
                "attempts": 1,
                "status": "ON_TIME",
            }
        )
    return coursework


def test_get_injection_rates() -> None:
    """Verify injection rates are extracted properly from config and defaults."""
    rates = get_injection_rates()
    for key in INJECTION_RATE_KEYS:
        assert key in rates
        assert 0.0 <= rates[key] <= 1.0

    configs = validate_project_config()
    loaded_rates = get_injection_rates(configs)
    assert loaded_rates["duplicate_lms_events"] == 0.01
    assert loaded_rates["nulls_non_key"] == 0.015
    assert loaded_rates["timestamp_inconsistencies"] == 0.01
    assert loaded_rates["course_id_formatting"] == 0.005
    assert loaded_rates["orphan_records"] == 0.001
    assert loaded_rates["out_of_range_values"] == 0.001


def test_get_injection_rates_invalid() -> None:
    """Out-of-range rates raise GeneratorError."""
    bad_config = {"generator": {"data_quality_injection": {"duplicate_lms_events": 1.5}}}
    with pytest.raises(GeneratorError, match="must be a float in"):
        get_injection_rates(bad_config)


def test_inject_duplicate_lms_events() -> None:
    """Verify duplicate injection appends duplicate rows and reports exact count."""
    events = _make_sample_lms_events(40)
    original_len = len(events)

    # 1. High rate to ensure duplicates are created
    perturbed, count = inject_duplicate_lms_events(events, rate=0.20)
    assert count == 8  # 40 * 0.20
    assert len(perturbed) == original_len + 8

    # Verify duplicated elements are identical to existing events
    for dup in perturbed[original_len:]:
        assert dup in events

    # 2. Zero rate returns 0 added
    clean, zero_count = inject_duplicate_lms_events(events, rate=0.0)
    assert zero_count == 0
    assert len(clean) == original_len


def test_inject_nulls_non_key_and_protect_key_identifiers() -> None:
    """Verify non-key fields receive nulls while key identifiers are NEVER nulled."""
    events = _make_sample_lms_events(50)
    perturbed, count = inject_nulls_non_key(events, "lms_events", rate=0.40)

    assert count > 0
    assert len(perturbed) == len(events)

    # Confirm key identifiers are strictly not None
    for row in perturbed:
        assert row["meta"]["student_id"] is not None
        assert row["meta"]["course_id"] is not None
        assert row["meta"]["school"] is not None
        assert row["timestamp"] is not None
        assert row["session_id"] is not None
        assert row["activity_type"] is not None

    # Confirm non-key fields (duration_sec or resource_id) were nulled on some records
    null_duration_or_res = sum(
        1 for r in perturbed if r["duration_sec"] is None or r["resource_id"] is None
    )
    assert null_duration_or_res >= count

    # Test coursework score nulling
    cw = _make_sample_coursework(30)
    cw_pert, cw_count = inject_nulls_non_key(cw, "coursework", rate=0.30)
    assert cw_count > 0
    for r in cw_pert:
        assert r["student_id"] is not None
        assert r["course_id"] is not None
        assert r["item_id"] is not None


def test_inject_timestamp_inconsistencies() -> None:
    """Verify datetimes are converted to inconsistent format strings."""
    events = _make_sample_lms_events(40)
    perturbed, count = inject_timestamp_inconsistencies(events, "lms_events", rate=0.25)

    assert count == 10  # 40 * 0.25
    string_ts_count = sum(1 for r in perturbed if isinstance(r["timestamp"], str))
    assert string_ts_count == 10

    # Ensure unperturbed rows retain datetime
    datetime_ts_count = sum(1 for r in perturbed if isinstance(r["timestamp"], datetime))
    assert datetime_ts_count == 30


def test_inject_course_id_formatting() -> None:
    """Verify course_id casing and whitespace anomalies are introduced."""
    records = _make_sample_academic_records(40)
    perturbed, count = inject_course_id_formatting(records, "academic_records", rate=0.25)

    assert count == 10
    anomalous_cids = [r["course_id"] for r in perturbed if r["course_id"] != "CSE101"]
    assert len(anomalous_cids) == 10

    # Test nested course_id in lms_events
    events = _make_sample_lms_events(40)
    lms_pert, lms_count = inject_course_id_formatting(events, "lms_events", rate=0.25)
    assert lms_count == 10
    lms_anomalous = [r["meta"]["course_id"] for r in lms_pert if r["meta"]["course_id"] != "CSE101"]
    assert len(lms_anomalous) == 10


def test_inject_orphan_records() -> None:
    """Verify student_id is replaced with non-existent orphan identifiers."""
    attendance = _make_sample_attendance(40)
    perturbed, count = inject_orphan_records(attendance, "attendance", rate=0.25)

    assert count == 10
    orphans = [r["student_id"] for r in perturbed if r["student_id"].startswith("STU999")]
    assert len(orphans) == 10

    # Test nested student_id in lms_events
    events = _make_sample_lms_events(40)
    lms_pert, lms_count = inject_orphan_records(events, "lms_events", rate=0.25)
    assert lms_count == 10
    lms_orphans = [
        r["meta"]["student_id"]
        for r in lms_pert
        if r["meta"]["student_id"].startswith("STU999")
    ]
    assert len(lms_orphans) == 10


def test_inject_out_of_range_values() -> None:
    """Verify out-of-range numerical domain perturbations across collections."""
    # 1. LMS negative duration
    events = _make_sample_lms_events(40)
    lms_pert, lms_count = inject_out_of_range_values(events, "lms_events", rate=0.25)
    assert lms_count == 10
    neg_durations = [r["duration_sec"] for r in lms_pert if r["duration_sec"] < 0]
    assert len(neg_durations) == 10

    # 2. Attendance > 100% (attended > conducted)
    att = _make_sample_attendance(40)
    att_pert, att_count = inject_out_of_range_values(att, "attendance", rate=0.25)
    assert att_count == 10
    over_attended = [
        r for r in att_pert if r["classes_attended"] > r["classes_conducted"]
    ]
    assert len(over_attended) == 10

    # 3. Coursework score > max_score
    cw = _make_sample_coursework(40)
    cw_pert, cw_count = inject_out_of_range_values(cw, "coursework", rate=0.25)
    assert cw_count == 10
    over_score = [r for r in cw_pert if r["score"] > r["max_score"]]
    assert len(over_score) == 10


def test_inject_quality_issues_lms_events() -> None:
    """Verify comprehensive LMS event injection helper tracks all 6 categories."""
    events = _make_sample_lms_events(100)
    rates = {
        "duplicate_lms_events": 0.05,
        "nulls_non_key": 0.05,
        "timestamp_inconsistencies": 0.05,
        "course_id_formatting": 0.05,
        "orphan_records": 0.05,
        "out_of_range_values": 0.05,
    }
    perturbed, counts = inject_quality_issues_lms_events(events, rates=rates)

    assert set(counts.keys()) == set(INJECTION_RATE_KEYS)
    for k, count in counts.items():
        assert count > 0, f"Expected {k} count > 0, got {count}"


def test_inject_data_quality_dataset_wide() -> None:
    """Test full multi-collection injection orchestrator and InjectionReport."""
    configs = validate_project_config()
    run = GeneratorRun(configs)

    events = _make_sample_lms_events(60)
    records = _make_sample_academic_records(60)
    att = _make_sample_attendance(60)
    cw = _make_sample_coursework(60)

    # Use slightly elevated rates to guarantee hits on small sample size
    test_rates = {
        "duplicate_lms_events": 0.05,
        "nulls_non_key": 0.05,
        "timestamp_inconsistencies": 0.05,
        "course_id_formatting": 0.05,
        "orphan_records": 0.05,
        "out_of_range_values": 0.05,
    }

    datasets, report = inject_data_quality(
        run,
        lms_events=events,
        academic_records=records,
        attendance=att,
        coursework=cw,
        rates=test_rates,
    )

    assert isinstance(report, InjectionReport)
    assert report.seed == run.seed
    assert set(report.issue_counts.keys()) == set(INJECTION_RATE_KEYS)
    assert set(report.collection_counts.keys()) == {
        "lms_events",
        "academic_records",
        "attendance",
        "coursework",
    }
    assert report.total_injected == sum(report.issue_counts.values())
    assert report.total_injected > 0

    # Serialization check
    rep_dict = report.to_dict()
    assert rep_dict["seed"] == run.seed
    assert rep_dict["total_injected"] == report.total_injected
    assert "timestamp" in rep_dict


def test_injection_reproducibility() -> None:
    """Two identical runs produce byte-identical injection outcomes and counts."""
    configs1 = validate_project_config()
    configs2 = validate_project_config()
    run1 = GeneratorRun(configs1)
    run2 = GeneratorRun(configs2)

    events1 = _make_sample_lms_events(50)
    events2 = _make_sample_lms_events(50)

    rates = {"duplicate_lms_events": 0.08, "nulls_non_key": 0.08, "timestamp_inconsistencies": 0.08,
             "course_id_formatting": 0.08, "orphan_records": 0.08, "out_of_range_values": 0.08}

    p1, c1 = inject_quality_issues_lms_events(events1, run=run1, rates=rates)
    p2, c2 = inject_quality_issues_lms_events(events2, run=run2, rates=rates)

    assert c1 == c2
    assert p1 == p2


def test_non_destructive_input_guarantee() -> None:
    """Inject functions must not mutate input records in place."""
    events = _make_sample_lms_events(30)
    events_backup = copy.deepcopy(events)

    inject_quality_issues_lms_events(events, rates={"out_of_range_values": 0.5})
    assert events == events_backup
