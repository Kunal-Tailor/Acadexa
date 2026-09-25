"""Tests for the synthetic ground-truth registry (task 5.5).

Verifies:
- Definition and structure of planted relationships and decoy relationship.
- Deterministic capture of decliner population, parameters, and flags.
- Integrity of serialization (to_dict/save) and deserialization (from_dict/load).
- Query methods (is_decliner, get_relationship, decliner_student_ids).
- Reproducibility across seeded generator runs.
- Error handling on invalid/missing input data.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    DECOY_RELATIONSHIP,
    DEFAULT_GROUND_TRUTH_PATH,
    PLANTED_RELATIONSHIPS,
    GeneratorError,
    GeneratorRun,
    GroundTruthRegistry,
    generate_decliner_flags,
    generate_ground_truth_registry,
    generate_students,
    load_ground_truth_registry,
)


def _scaled_configs(target: int = 36) -> dict:
    """Create a deep copy of validated project config scaled to ``target`` students."""
    configs = copy.deepcopy(validate_project_config())
    scale = configs["generator"]["scale"]
    scale["target_students"] = target
    per_school = max(1, target // len(scale["school_population"]))
    scale["school_population"] = {s: per_school for s in scale["school_population"]}
    scale["target_students"] = per_school * len(scale["school_population"])
    return configs


@pytest.fixture()
def small_run() -> tuple[GeneratorRun, list[dict]]:
    """Seeded GeneratorRun with a small student cohort."""
    configs = _scaled_configs(36)
    run = GeneratorRun(configs)
    students = generate_students(run)
    return run, students


def test_planted_relationships_constant_structure() -> None:
    """Check standard PLANTED_RELATIONSHIPS definitions and fields."""
    required_keys = {
        "id",
        "name",
        "independent_variable",
        "dependent_variable",
        "relationship_type",
        "expected_direction",
        "expected_strength",
        "description",
        "mechanism",
    }
    assert len(PLANTED_RELATIONSHIPS) >= 4
    ids = [rel["id"] for rel in PLANTED_RELATIONSHIPS]
    assert "attendance_marks" in ids
    assert "lms_engagement_marks" in ids
    assert "late_submissions_marks" in ids
    assert "course_difficulty_confounder" in ids

    for rel in PLANTED_RELATIONSHIPS:
        assert required_keys.issubset(rel.keys())
        assert rel["relationship_type"] in ("planted", "confounder")
        assert rel["expected_direction"] in ("positive", "negative", "confounder")


def test_decoy_relationship_constant_structure() -> None:
    """Check standard DECOY_RELATIONSHIP definition and fields."""
    required_keys = {
        "id",
        "name",
        "independent_variable",
        "dependent_variable",
        "relationship_type",
        "expected_direction",
        "expected_strength",
        "description",
        "mechanism",
    }
    assert required_keys.issubset(DECOY_RELATIONSHIP.keys())
    assert DECOY_RELATIONSHIP["id"] == "decoy_forum_marks"
    assert DECOY_RELATIONSHIP["relationship_type"] == "decoy"
    assert DECOY_RELATIONSHIP["expected_direction"] == "none"
    assert DECOY_RELATIONSHIP["expected_strength"] == "none"


def test_generate_ground_truth_registry(small_run: tuple[GeneratorRun, list[dict]]) -> None:
    """Generate ground-truth registry and verify all components."""
    run, students = small_run
    registry = generate_ground_truth_registry(run, students)

    assert isinstance(registry, GroundTruthRegistry)
    assert registry.seed == run.seed
    assert len(registry.planted_relationships) == len(PLANTED_RELATIONSHIPS)
    assert registry.decoy_relationship["id"] == "decoy_forum_marks"

    # Decliner behavior checks
    decliner_info = registry.decliner_behavior
    assert decliner_info["total_students"] == len(students)
    assert decliner_info["configured_rate"] == 0.08
    assert decliner_info["start_week"] == 5
    assert decliner_info["marks_decline_lag_weeks"] == 3
    assert decliner_info["decliners_count"] == len(decliner_info["decliner_student_ids"])

    # Decliner flags checks
    assert len(registry.decliner_flags) == len(students)
    for student in students:
        sid = student["student_id"]
        assert sid in registry.decliner_flags
        is_dec = registry.decliner_flags[sid]
        assert registry.is_decliner(sid) is is_dec
        if is_dec:
            assert sid in registry.decliner_student_ids
        else:
            assert sid not in registry.decliner_student_ids

    # Metadata checks
    assert registry.metadata["planted_count"] == len(PLANTED_RELATIONSHIPS)
    assert registry.metadata["decoy_count"] == 1
    assert "association" in registry.metadata["analytical_interpretation"].lower()


def test_generate_ground_truth_without_explicit_students() -> None:
    """Calling generate_ground_truth_registry without students auto-generates students."""
    configs = _scaled_configs(18)
    run = GeneratorRun(configs)
    registry = generate_ground_truth_registry(run)

    assert registry.decliner_behavior["total_students"] == 18
    assert len(registry.decliner_flags) == 18


def test_generate_ground_truth_with_precomputed_flags(
    small_run: tuple[GeneratorRun, list[dict]],
) -> None:
    """Ground truth registry preserves precomputed decliner flags."""
    run, students = small_run
    flags = generate_decliner_flags(run, students)
    registry = generate_ground_truth_registry(run, students, decliner_flags=flags)

    assert registry.decliner_flags == flags
    expected_decliners = sorted(sid for sid, flag in flags.items() if flag)
    assert registry.decliner_student_ids == expected_decliners


def test_ground_truth_registry_reproducibility() -> None:
    """Two GeneratorRuns with the same seed produce identical ground truth."""
    configs1 = _scaled_configs(36)
    configs2 = _scaled_configs(36)
    run1 = GeneratorRun(configs1)
    run2 = GeneratorRun(configs2)

    students1 = generate_students(run1)
    students2 = generate_students(run2)

    reg1 = generate_ground_truth_registry(run1, students1)
    reg2 = generate_ground_truth_registry(run2, students2)

    assert reg1.seed == reg2.seed
    assert reg1.decliner_student_ids == reg2.decliner_student_ids
    assert reg1.decliner_flags == reg2.decliner_flags
    assert reg1.planted_relationships == reg2.planted_relationships
    assert reg1.decoy_relationship == reg2.decoy_relationship


def test_ground_truth_registry_seed_diversity() -> None:
    """Different seeds produce different decliner sets."""
    configs1 = _scaled_configs(120)
    configs2 = _scaled_configs(120)
    configs2["generator"]["generator"]["seed"] = 999

    run1 = GeneratorRun(configs1)
    run2 = GeneratorRun(configs2)

    students1 = generate_students(run1)
    students2 = generate_students(run2)

    reg1 = generate_ground_truth_registry(run1, students1)
    reg2 = generate_ground_truth_registry(run2, students2)

    assert reg1.seed != reg2.seed
    assert reg1.decliner_student_ids != reg2.decliner_student_ids


def test_ground_truth_registry_lookup_methods(
    small_run: tuple[GeneratorRun, list[dict]],
) -> None:
    """Test get_relationship and property lookups."""
    run, students = small_run
    registry = generate_ground_truth_registry(run, students)

    # Planted lookup
    rel = registry.get_relationship("attendance_marks")
    assert rel is not None
    assert rel["name"] == "Attendance to Marks"
    assert rel["expected_direction"] == "positive"

    # Decoy lookup
    decoy = registry.get_relationship("decoy_forum_marks")
    assert decoy is not None
    assert decoy["relationship_type"] == "decoy"
    assert decoy["expected_direction"] == "none"

    # Nonexistent lookup
    assert registry.get_relationship("nonexistent_id") is None

    # Planted IDs property
    assert "attendance_marks" in registry.planted_relationship_ids
    assert "lms_engagement_marks" in registry.planted_relationship_ids


def test_ground_truth_registry_save_and_load(
    tmp_path: Path, small_run: tuple[GeneratorRun, list[dict]]
) -> None:
    """Save to JSON and load back; assert complete structural equality."""
    run, students = small_run
    registry = generate_ground_truth_registry(run, students)

    out_file = tmp_path / "manifests" / "ground_truth_registry.json"
    saved_path = registry.save(out_file)
    assert saved_path == out_file
    assert out_file.is_file()

    # Load back using load_ground_truth_registry
    loaded = load_ground_truth_registry(out_file)
    assert loaded.seed == registry.seed
    assert loaded.planted_relationships == registry.planted_relationships
    assert loaded.decoy_relationship == registry.decoy_relationship
    assert loaded.decliner_behavior == registry.decliner_behavior
    assert loaded.decliner_flags == registry.decliner_flags
    assert loaded.decliner_student_ids == registry.decliner_student_ids
    assert loaded.metadata == registry.metadata


def test_ground_truth_registry_missing_file_error(tmp_path: Path) -> None:
    """Loading a non-existent JSON file raises FileNotFoundError."""
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match="Ground-truth file not found"):
        load_ground_truth_registry(missing)


def test_ground_truth_registry_from_dict_validation() -> None:
    """Reconstructing from an invalid dict raises GeneratorError."""
    with pytest.raises(GeneratorError, match="data must be a dictionary"):
        GroundTruthRegistry.from_dict("not a dict")  # type: ignore

    incomplete = {"seed": 42}
    with pytest.raises(GeneratorError, match="missing 'generation_timestamp'"):
        GroundTruthRegistry.from_dict(incomplete)
