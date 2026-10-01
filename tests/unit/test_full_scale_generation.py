"""Unit tests for full-scale core generation records (Tasks 14.3 & 14.4).

Validates the committed stage manifests produced by the frozen-config
full run (12,000 students, seed 42): exact population/record counts,
four-semester coverage, school split, grain uniqueness and storage
usage. Fast: reads only small committed JSON, never the generated data.
"""

from __future__ import annotations

import json
from pathlib import Path

from acadexa.config.loader import PROJECT_ROOT

STUDENTS_MANIFEST = PROJECT_ROOT / "data" / "manifests" / "full_scale_students.json"
ATTENDANCE_MANIFEST = PROJECT_ROOT / "data" / "manifests" / "full_scale_attendance_coursework.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_full_scale_students_record() -> None:
    """14.3 record: 12,000 students and 288,000 records across S1–S4."""
    manifest = _load(STUDENTS_MANIFEST)
    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["task"] == "14.3"
    assert manifest["seed"] == 42
    assert manifest["target_counts"] == {"students": 12000, "academic_records": 288000}

    actual = manifest["actual_counts"]
    assert actual["students"] == 12000
    assert actual["courses"] == 72
    assert actual["academic_records"] == 288000
    assert actual["records_by_semester"] == {
        "S1": 72000,
        "S2": 72000,
        "S3": 72000,
        "S4": 72000,
    }
    assert sum(actual["records_by_semester"].values()) == actual["academic_records"]
    assert actual["distinct_student_course_semester"] == 288000


def test_full_scale_school_split_matches_frozen_population() -> None:
    """School split matches the frozen six-school population exactly."""
    manifest = _load(STUDENTS_MANIFEST)
    by_school = manifest["students_by_school"]
    assert sorted(by_school.values()) == [800, 1000, 2200, 2400, 2600, 3000]
    assert sum(by_school.values()) == 12000


def test_full_scale_attendance_coursework_record() -> None:
    """14.4 record: 4.6M attendance and 3.3M coursework rows plus storage."""
    manifest = _load(ATTENDANCE_MANIFEST)
    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["task"] == "14.4"
    assert manifest["seed"] == 42

    actual = manifest["actual_counts"]
    assert actual["attendance"] == 4608000
    assert actual["attendance_by_semester"] == {
        "S1": 1152000,
        "S2": 1152000,
        "S3": 1152000,
        "S4": 1152000,
    }
    assert sum(actual["attendance_by_semester"].values()) == actual["attendance"]
    assert actual["coursework"] == 3338810
    assert actual["coursework_distinct_items"] > 0
    assert set(actual["attendance_weeks_per_record_values"]) <= set(range(1, 17))
    assert 16 in actual["attendance_weeks_per_record_values"]

    disk = manifest["disk_usage_bytes"]
    assert disk["attendance"] > 500_000_000
    assert disk["coursework"] > 500_000_000
    assert disk["attendance"] + disk["coursework"] > 1_000_000_000
