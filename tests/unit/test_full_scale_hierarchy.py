"""Unit tests for full university hierarchy generation (Task 14.2).

Runs hierarchy generation at the full six-school target (no scaled-down
development overrides) and records actual counts: level totals, school
identifiers, per-school breakdowns and the configured catalog size
against the 250-course full target.
"""

from __future__ import annotations

import json
from pathlib import Path

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorRun,
    build_hierarchy_counts,
    generate_university_hierarchy,
    record_hierarchy_counts,
)


def _full_hierarchy():
    """Full-target hierarchy from validated configuration (no overrides)."""
    configs = validate_project_config()
    return generate_university_hierarchy(configs), configs


def test_full_hierarchy_level_counts() -> None:
    """Six schools, eighteen departments, forty programs at full target."""
    hierarchy, _ = _full_hierarchy()
    counts = build_hierarchy_counts(hierarchy)
    assert counts["schools"] == 6
    assert counts["departments"] == 18
    assert counts["programs"] == 40
    assert counts["school_ids"] == ["cet", "lad", "sci", "set", "sol", "som"]


def test_full_hierarchy_per_school_breakdown() -> None:
    """Per-school breakdowns reconcile with level totals."""
    hierarchy, _ = _full_hierarchy()
    counts = build_hierarchy_counts(hierarchy)
    by_school = counts["by_school"]
    assert len(by_school) == 6
    assert sum(s["departments"] for s in by_school) == 18
    assert sum(s["programs"] for s in by_school) == 40
    assert sum(s["courses"] for s in by_school) == counts["courses"]
    cet = next(s for s in by_school if s["id"] == "cet")
    assert cet["code"] == "CET"
    assert cet["name"] == "School of Computer Engineering & Technology"
    assert cet["departments"] > 0 and cet["courses"] > 0


def test_full_hierarchy_records_catalog_against_target() -> None:
    """Configured catalog size is recorded alongside the 250-course target."""
    hierarchy, configs = _full_hierarchy()
    counts = build_hierarchy_counts(hierarchy)
    assert counts["courses"] == len(configs["courses"]["courses"]) == 72
    assert counts["catalog_target_courses"] == 250


def test_full_hierarchy_is_deterministic() -> None:
    """Repeated full-target runs produce identical counts."""
    first, _ = _full_hierarchy()
    second, _ = _full_hierarchy()
    assert build_hierarchy_counts(first) == build_hierarchy_counts(second)


def test_record_hierarchy_manifest(tmp_path: Path) -> None:
    """Manifest file carries type, seed, timestamp and actual counts."""
    hierarchy, _ = _full_hierarchy()
    run = GeneratorRun(validate_project_config())
    target = record_hierarchy_counts(
        hierarchy, seed=run.seed, output_path=tmp_path / "full_scale_hierarchy.json"
    )
    assert target.exists()
    manifest = json.loads(target.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["manifest_type"] == "full_scale_hierarchy"
    assert manifest["seed"] == 42
    assert manifest["generated_at"]
    assert manifest["actual_counts"]["schools"] == 6
    assert manifest["actual_counts"]["departments"] == 18
    assert manifest["actual_counts"]["programs"] == 40
    assert len(manifest["actual_counts"]["by_school"]) == 6
