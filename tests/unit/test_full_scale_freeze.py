"""Unit tests for the full-scale configuration freeze (Task 14.1).

The freeze locks documented full-target values without changing schema
or architecture: any configuration drift must fail here for explicit
review instead of slipping silently into full-scale generation.
"""

from __future__ import annotations

import copy

from acadexa.config import validate_project_config
from acadexa.generator.full_scale import (
    FROZEN_SCHOOL_IDS,
    FROZEN_SEED,
    FROZEN_TARGET_LMS_EVENTS,
    FROZEN_TARGET_STUDENTS,
    validate_full_scale_config,
)


def test_live_config_matches_frozen_targets() -> None:
    """Validated project configuration satisfies every frozen target."""
    report = validate_full_scale_config()
    assert report.is_frozen is True
    assert report.mismatches == []
    assert report.seed == FROZEN_SEED == 42


def test_frozen_scale_values() -> None:
    """Scale block matches the documented full target (no silent edits)."""
    configs = validate_project_config()
    scale = configs["generator"]["scale"]
    assert scale["target_students"] == FROZEN_TARGET_STUDENTS == 12000
    assert sum(scale["school_population"].values()) == 12000
    assert scale["target_lms_events"] == FROZEN_TARGET_LMS_EVENTS == 70_000_000
    assert sorted(scale["school_population"]) == sorted(FROZEN_SCHOOL_IDS)


def test_seed_drift_is_reported() -> None:
    """A changed seed breaks the freeze with a named mismatch."""
    configs = copy.deepcopy(validate_project_config())
    configs["generator"]["generator"]["seed"] = 999
    report = validate_full_scale_config(configs)
    assert report.is_frozen is False
    assert [m.field for m in report.mismatches] == ["seed"]
    assert report.mismatches[0].expected == 42
    assert report.mismatches[0].actual == 999


def test_population_drift_is_reported() -> None:
    """Population edits break both the table and the sum check."""
    configs = copy.deepcopy(validate_project_config())
    configs["generator"]["scale"]["school_population"]["cet"] += 1
    report = validate_full_scale_config(configs)
    assert report.is_frozen is False
    fields = [m.field for m in report.mismatches]
    assert "scale.school_population" in fields
    assert "scale.school_population_sum" in fields


def test_injection_rate_drift_is_reported() -> None:
    """Quality-injection edits break the freeze as one named mismatch."""
    configs = copy.deepcopy(validate_project_config())
    configs["generator"]["data_quality_injection"]["orphan_records"] = 0.5
    report = validate_full_scale_config(configs)
    assert report.is_frozen is False
    assert [m.field for m in report.mismatches] == [
        "generator.data_quality_injection"
    ]


def test_report_serializes() -> None:
    """Freeze reports serialize for review tooling."""
    report = validate_full_scale_config()
    assert report.to_dict() == {
        "manifest_version": "1.0.0",
        "is_frozen": True,
        "seed": 42,
        "mismatches": [],
    }
