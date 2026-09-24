"""Tests for academic-record generation and course difficulty (task 4.4)."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict

import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    assign_course_difficulty,
    generate_academic_records,
    generate_students,
    generate_university_hierarchy,
)
from acadexa.validation import ACADEMIC_RECORDS_SCHEMA, validate_records


@pytest.fixture(scope="module")
def dataset() -> tuple[GeneratorRun, list[dict], list[dict]]:
    """Full-scale generation, computed once for this module."""
    run = GeneratorRun(validate_project_config())
    students = generate_students(run)
    records = generate_academic_records(run, students)
    return run, students, records


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


# ── Full-scale structure ────────────────────────────────


def test_record_count_matches_documented_scale(
    dataset: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = dataset
    scale = run.configs["generator"]["scale"]
    semester_count = len(run.configs["academic_periods"]["semesters"])
    expected = (
        len(students)
        * semester_count
        * scale["courses_per_student_per_semester"]
    )
    assert len(records) == expected == 12000 * 4 * 6 == 288_000


def test_each_student_takes_configured_courses_per_semester(
    dataset: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, _, records = dataset
    per_semester = run.configs["generator"]["scale"][
        "courses_per_student_per_semester"
    ]
    counts = Counter(
        (record["student_id"], record["semester_id"]) for record in records
    )
    assert counts and set(counts.values()) == {per_semester}


def test_records_conform_to_schema(
    dataset: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    _, _, records = dataset
    validate_records(records, ACADEMIC_RECORDS_SCHEMA)


def test_references_resolve_to_existing_entities(
    dataset: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = dataset
    hierarchy = generate_university_hierarchy(run.configs)
    assert {record["student_id"] for record in records} == {
        student["student_id"] for student in students
    }
    assert {record["course_id"] for record in records} == {
        course["course_id"] for course in hierarchy.courses
    }
    assert {record["semester_id"] for record in records} == set(
        run.configs["academic_periods"]["semesters"]
    )


def test_enrollment_covers_school_catalogue_and_distinct_electives(
    dataset: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = dataset
    hierarchy = generate_university_hierarchy(run.configs)
    school_of = {
        course["course_id"]: course["school"] for course in hierarchy.courses
    }
    enrolled_by_student: dict[str, list[str]] = defaultdict(list)
    for record in records:
        enrolled_by_student[record["student_id"]].append(record["course_id"])

    for student in students:
        enrolled = enrolled_by_student[student["student_id"]]
        assert len(enrolled) == 24
        assert len(set(enrolled)) == 24
        school_courses = {
            course_id
            for course_id, school in school_of.items()
            if school == student["school"]
        }
        own = [
            course_id
            for course_id in enrolled
            if school_of[course_id] == student["school"]
        ]
        electives = [
            course_id
            for course_id in enrolled
            if school_of[course_id] != student["school"]
        ]
        assert set(own) == school_courses
        assert len(electives) == 12


# ── Marks & grades ──────────────────────────────────────


def test_final_grade_matches_configured_scale(
    dataset: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, _, records = dataset
    grade_scale = run.configs["generator"]["behavior"]["grade_scale"]
    bands = sorted(grade_scale.items(), key=lambda item: item[1], reverse=True)
    seen: set[str] = set()
    for record in records:
        aggregate = (
            record["internal_marks"]
            + record["midterm_marks"]
            + record["endterm_marks"]
        ) / 3
        expected = "F"
        for letter, threshold in bands:
            if aggregate >= threshold:
                expected = letter
                break
        assert record["final_grade"] == expected
        seen.add(expected)
    assert seen == {"A", "B", "C", "D", "F"}


def test_course_difficulty_lowers_expected_marks(
    dataset: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, _, records = dataset
    hierarchy = generate_university_hierarchy(run.configs)
    difficulties = assign_course_difficulty(run, hierarchy.courses)
    totals: dict[str, list[float]] = {
        level: [0.0, 0.0] for level in ("easy", "medium", "hard")
    }
    for record in records:
        level = difficulties[record["course_id"]]["difficulty_level"]
        aggregate = (
            record["internal_marks"]
            + record["midterm_marks"]
            + record["endterm_marks"]
        ) / 3
        totals[level][0] += aggregate
        totals[level][1] += 1
    means = {level: total / count for level, (total, count) in totals.items()}
    assert means["hard"] < means["medium"] < means["easy"]


# ── Course difficulty assignment ────────────────────────


def test_difficulty_counts_follow_configured_shares() -> None:
    run = GeneratorRun(validate_project_config())
    hierarchy = generate_university_hierarchy(run.configs)
    assignments = assign_course_difficulty(run, hierarchy.courses)
    assert len(assignments) == len(hierarchy.courses)
    counts = Counter(
        assignment["difficulty_level"] for assignment in assignments.values()
    )
    assert counts == {"easy": 22, "medium": 32, "hard": 18}


def test_difficulty_values_sit_inside_their_bucket() -> None:
    run = GeneratorRun(validate_project_config())
    hierarchy = generate_university_hierarchy(run.configs)
    ranges = {"easy": (0.0, 0.4), "medium": (0.4, 0.7), "hard": (0.7, 1.0)}
    assignments = assign_course_difficulty(run, hierarchy.courses)
    for assignment in assignments.values():
        low, high = ranges[assignment["difficulty_level"]]
        assert low <= assignment["difficulty"] < high


def test_course_difficulty_assignment_is_reproducible() -> None:
    first = GeneratorRun(validate_project_config())
    second = GeneratorRun(validate_project_config())
    hierarchy = generate_university_hierarchy(first.configs)
    assert assign_course_difficulty(first, hierarchy.courses) == (
        assign_course_difficulty(second, hierarchy.courses)
    )


def test_course_difficulty_assignment_changes_with_seed() -> None:
    configs = copy.deepcopy(validate_project_config())
    hierarchy = generate_university_hierarchy(configs)
    baseline = assign_course_difficulty(GeneratorRun(configs), hierarchy.courses)
    configs["generator"]["generator"]["seed"] += 1
    other = assign_course_difficulty(GeneratorRun(configs), hierarchy.courses)
    assert other != baseline


def test_assign_course_difficulty_requires_courses() -> None:
    run = GeneratorRun(validate_project_config())
    with pytest.raises(GeneratorError, match="must not be empty"):
        assign_course_difficulty(run, [])


# ── Reproducibility & seed behavior (small scale) ───────


def test_records_are_reproducible(small_configs: dict) -> None:
    first = generate_academic_records(GeneratorRun(small_configs))
    second = generate_academic_records(GeneratorRun(small_configs))
    assert first == second
    assert len(first) == 36 * 4 * 6


def test_different_seed_changes_records(small_configs: dict) -> None:
    other_configs = copy.deepcopy(small_configs)
    other_configs["generator"]["generator"]["seed"] += 1
    baseline = generate_academic_records(GeneratorRun(small_configs))
    other = generate_academic_records(GeneratorRun(other_configs))
    assert other != baseline


# ── Initialization failures ─────────────────────────────


def test_missing_course_difficulty_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["course_difficulty"]
    with pytest.raises(GeneratorError, match="course_difficulty"):
        generate_academic_records(GeneratorRun(broken))


def test_missing_academic_performance_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["academic_performance"]
    with pytest.raises(GeneratorError, match="academic_performance"):
        generate_academic_records(GeneratorRun(broken))


def test_missing_grade_scale_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["grade_scale"]
    with pytest.raises(GeneratorError, match="grade_scale"):
        generate_academic_records(GeneratorRun(broken))


def test_missing_academic_periods_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["academic_periods"]
    with pytest.raises(GeneratorError, match="academic_periods"):
        generate_academic_records(GeneratorRun(broken))


def test_elective_count_exceeding_total_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    scale = broken["generator"]["scale"]
    scale["elective_courses_per_semester"] = (
        scale["courses_per_student_per_semester"] + 1
    )
    with pytest.raises(GeneratorError, match="elective_courses_per_semester"):
        generate_academic_records(GeneratorRun(broken))
