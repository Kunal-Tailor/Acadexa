"""Unit tests for full-scale LMS Parquet dataset and serving slice records (Tasks 14.5 & 14.6).

Validates the committed stage manifests produced by the frozen-config
full run (74.7M LMS Parquet events, 8.95M LMS serving slice in MongoDB):
exact event counts, partition part counts, storage usage, injection counts,
and serving slice specification adherence.
Fast: reads only small committed JSON manifests and tests spec logic.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from acadexa.config.loader import PROJECT_ROOT
from acadexa.database.loader import LMSServingSliceSpec

LMS_MANIFEST = PROJECT_ROOT / "data" / "manifests" / "full_scale_lms.json"
LMS_SLICE_MANIFEST = PROJECT_ROOT / "data" / "manifests" / "full_scale_lms_slice.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_full_scale_lms_parquet_record() -> None:
    """14.5 record: ~74.7M LMS events streamed to Parquet across 13k parts."""
    manifest = _load(LMS_MANIFEST)
    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["task"] == "14.5"
    assert manifest["seed"] == 42
    assert manifest["target_lms_events"] == 70000000

    actual = manifest["actual_counts"]
    assert actual["lms_events"] == 74757153
    assert actual["parquet_part_files"] == 13338

    disk = manifest["disk_usage_bytes"]
    assert disk["lms_events"] == 1384299429
    assert disk["lms_events"] > 1_000_000_000

    injected = manifest["injected_lms_issues"]
    assert set(injected.keys()) == {
        "duplicate_lms_events",
        "nulls_non_key",
        "timestamp_inconsistencies",
        "course_id_formatting",
        "orphan_records",
        "out_of_range_values",
    }
    assert all(cnt > 0 for cnt in injected.values())
    assert injected["duplicate_lms_events"] == 740169
    assert injected["nulls_non_key"] == 590317
    assert injected["timestamp_inconsistencies"] == 779625
    assert injected["course_id_formatting"] == 414959
    assert injected["orphan_records"] == 82991
    assert injected["out_of_range_values"] == 35988

    assert manifest["chunking"]["config_chunk_size"] == 100000


def test_full_scale_lms_serving_slice_record() -> None:
    """14.6 record: S4 + CET/SOM operational slice loaded and verified in MongoDB."""
    manifest = _load(LMS_SLICE_MANIFEST)
    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["task"] == "14.6"

    spec = manifest["spec"]
    assert sorted(spec["schools"]) == ["CET", "SOM"]
    assert spec["semester_id"] == "S4"
    assert spec["start_date"] == "2026-01-05"
    assert spec["end_date"] == "2026-04-26"

    actual = manifest["actual_counts"]
    assert actual["total_scanned"] == 18688887
    assert actual["slice_selected"] == 8958633
    assert actual["inserted_count"] == 8958633
    assert actual["actual_db_count"] == 8958633

    assert actual["total_scanned"] >= actual["slice_selected"]
    assert actual["slice_selected"] == actual["inserted_count"] == actual["actual_db_count"]
    assert manifest["validated"] is True


def test_lms_serving_slice_spec_matching() -> None:
    """Test slice specification matching logic against candidate records."""
    spec = LMSServingSliceSpec.from_config(semester_id="S4", schools=("CET", "SOM"))

    # Valid matching record
    rec_match = {
        "timestamp": datetime(2026, 2, 10, 14, 0, 0),
        "meta": {"student_id": "STU001", "course_id": "CS101", "school": "CET"},
        "activity_type": "LOGIN",
    }
    assert spec.matches(rec_match) is True

    # Matching second school
    rec_som = {
        "timestamp": datetime(2026, 3, 1, 10, 0, 0),
        "meta": {"student_id": "STU002", "course_id": "MGT101", "school": "SOM"},
        "activity_type": "VIDEO_VIEW",
    }
    assert spec.matches(rec_som) is True

    # Non-matching school
    rec_sci = {
        "timestamp": datetime(2026, 2, 10, 14, 0, 0),
        "meta": {"student_id": "STU003", "course_id": "MAT101", "school": "SCI"},
        "activity_type": "LOGIN",
    }
    assert spec.matches(rec_sci) is False

    # Out of semester range (before start date)
    rec_early = {
        "timestamp": datetime(2025, 10, 10, 14, 0, 0),
        "meta": {"student_id": "STU001", "course_id": "CS101", "school": "CET"},
        "activity_type": "LOGIN",
    }
    assert spec.matches(rec_early) is False
