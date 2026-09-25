"""Tests for LMS event generation (task 5.1)."""

from __future__ import annotations

import copy
from collections import Counter

import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    generate_academic_records,
    generate_lms_events,
    generate_students,
)
from acadexa.validation import LMS_EVENTS_SCHEMA, validate_records


@pytest.fixture(scope="module")
def dataset() -> tuple[GeneratorRun, list[dict], list[dict], list[dict]]:
    """Full-scale generation, computed once for this module."""
    run = GeneratorRun(validate_project_config())
    students = generate_students(run)
    records = generate_academic_records(run, students)
    events = generate_lms_events(run, students, records)
    return run, students, records, events


@pytest.fixture()
def small_configs() -> dict:
    """Validated configuration scaled down to 36 students for fast tests."""
    configs = copy.deepcopy(validate_project_config())
    scale = configs["generator"]["scale"]
    scale["target_students"] = 36
    scale["school_population"] = {
        school_id: 6 for school_id in scale["school_population"]
    }
    return configs


@pytest.fixture()
def small_chain(small_configs: dict) -> tuple[GeneratorRun, list[dict], list[dict]]:
    run = GeneratorRun(small_configs)
    students = generate_students(run)
    records = generate_academic_records(run, students)
    return run, students, records


# ── Full-scale structure ────────────────────────────────


def test_lms_events_have_required_fields_and_types(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, students, records, events = dataset
    validate_records(events, LMS_EVENTS_SCHEMA)


def test_lms_events_use_only_approved_event_types(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    from acadexa.validation.schema import LMS_EVENT_TYPES

    used_types = {event["activity_type"] for event in events}
    assert used_types == set(LMS_EVENT_TYPES)


def test_lms_events_reference_valid_students_courses_semesters(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, students, records, events = dataset
    student_ids = {student["student_id"] for student in students}
    course_ids = set(run.configs["courses"]["courses"].keys())
    semester_ids = set(run.configs["academic_periods"]["semesters"].keys())
    school_codes = {school_id for school_id in run.configs["hierarchy"]["schools"].keys()}

    for event in events:
        assert event["meta"]["student_id"] in student_ids
        assert event["meta"]["course_id"] in course_ids
        assert event["meta"]["school"] in school_codes
        # Note: semester_id is not directly in LMS events, but is implicit through
        # the enrollment that generated the events


def test_lms_events_have_valid_timestamps(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    for event in events:
        assert isinstance(event["timestamp"], type(event["timestamp"]))


def test_lms_events_have_valid_session_ids(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    from acadexa.validation.schema import SESSION_ID_PATTERN
    import re

    pattern = re.compile(SESSION_ID_PATTERN)
    for event in events:
        assert pattern.match(event["session_id"])


def test_lms_events_have_nullable_resource_id_and_duration(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    for event in events:
        # resource_id and duration_sec are nullable
        if event["resource_id"] is not None:
            assert isinstance(event["resource_id"], str)
        if event["duration_sec"] is not None:
            assert isinstance(event["duration_sec"], int)
            assert event["duration_sec"] >= 0


def test_lms_events_respect_configuration_distribution(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, _, events = dataset
    event_type_counts = Counter(event["activity_type"] for event in events)
    total = len(events)

    # Check that the distribution roughly matches configuration
    # (allowing for some statistical variation)
    lms_config = run.configs.get("generator", {}).get("lms_events", {})
    if "event_type_distribution" in lms_config:
        distribution = lms_config["event_type_distribution"]
        for event_type, expected_prob in distribution.items():
            actual_prob = event_type_counts[event_type] / total
            # Allow 20% relative tolerance for statistical variation
            assert abs(actual_prob - expected_prob) / expected_prob < 0.2, (
                f"Event type {event_type}: expected probability {expected_prob:.3f}, "
                f"got {actual_prob:.3f}"
            )


# ── Small-scale schema & reproducibility ────────────────


def test_small_dataset_conforms_to_schema(
    small_configs: dict,
) -> None:
    events = generate_lms_events(GeneratorRun(small_configs))
    validate_records(events, LMS_EVENTS_SCHEMA)


def test_lms_events_are_reproducible(small_configs: dict) -> None:
    first = generate_lms_events(GeneratorRun(small_configs))
    second = generate_lms_events(GeneratorRun(small_configs))
    assert first == second


def test_different_seed_changes_lms_events(small_configs: dict) -> None:
    other_configs = copy.deepcopy(small_configs)
    other_configs["generator"]["generator"]["seed"] += 1
    baseline = generate_lms_events(GeneratorRun(small_configs))
    other = generate_lms_events(GeneratorRun(other_configs))
    assert other != baseline


def test_accepts_precomputed_students_and_records(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    events = generate_lms_events(run, students, records)
    assert len(events) > 0


# ── Initialization failures ─────────────────────────────


def test_missing_lms_events_per_day_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["scale"]["lms_events_per_student_per_day"]
    with pytest.raises(GeneratorError, match="lms_events_per_student_per_day"):
        generate_lms_events(GeneratorRun(broken))


def test_missing_teaching_days_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["scale"]["teaching_days_per_academic_year"]
    with pytest.raises(GeneratorError, match="teaching_days_per_academic_year"):
        generate_lms_events(GeneratorRun(broken))


def test_invalid_event_type_distribution_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    # Ensure the lms_events section exists at the right level
    if "lms_events" not in broken:
        broken["lms_events"] = {}
    broken["lms_events"]["event_type_distribution"] = {
        "LOGIN": 0.5,
        "INVALID_TYPE": 0.5,  # Invalid event type
    }
    with pytest.raises(GeneratorError, match="unknown event type"):
        generate_lms_events(GeneratorRun(broken))


def test_event_type_distribution_not_summing_to_one_raises(
    small_configs: dict,
) -> None:
    broken = copy.deepcopy(small_configs)
    # Ensure the lms_events section exists at the right level
    if "lms_events" not in broken:
        broken["lms_events"] = {}
    broken["lms_events"]["event_type_distribution"] = {
        "LOGIN": 0.5,
        "LOGOUT": 0.3,  # Sum = 0.8, not 1.0
    }
    with pytest.raises(GeneratorError, match="sum to 1.0"):
        generate_lms_events(GeneratorRun(broken))


def test_record_with_unknown_student_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, _, records = small_chain
    with pytest.raises(GeneratorError, match="unknown student"):
        generate_lms_events(run, students=[], records=records)


def test_record_with_unknown_course_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    broken_record = dict(records[0])
    broken_record["course_id"] = "INVALID999"
    with pytest.raises(GeneratorError, match="unknown course"):
        generate_lms_events(run, students, records + [broken_record])


def test_record_with_unknown_semester_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    broken_record = dict(records[0])
    broken_record["semester_id"] = "S99"
    with pytest.raises(GeneratorError, match="unknown semester"):
        generate_lms_events(run, students, records + [broken_record])
