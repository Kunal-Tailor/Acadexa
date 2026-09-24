"""Tests for seeded student generation (task 4.3)."""

from __future__ import annotations

import copy
import re
from collections import Counter

import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    generate_students,
    generate_university_hierarchy,
)
from acadexa.validation import STUDENT_ID_PATTERN, STUDENTS_SCHEMA, validate_records


@pytest.fixture()
def run() -> GeneratorRun:
    return GeneratorRun(validate_project_config())


@pytest.fixture()
def students(run: GeneratorRun) -> list[dict]:
    return generate_students(run)


# ── Population & identifiers ────────────────────────────


def test_generates_target_student_count(run: GeneratorRun, students: list[dict]) -> None:
    assert len(students) == run.configs["generator"]["scale"]["target_students"] == 12000


def test_student_ids_are_stable_unique_and_well_formed(students: list[dict]) -> None:
    ids = [student["student_id"] for student in students]
    assert len(set(ids)) == len(ids)
    assert all(re.match(STUDENT_ID_PATTERN, student_id) for student_id in ids)
    assert ids[0] == "STU000001"
    assert ids[-1] == "STU012000"


def test_school_counts_match_configuration_exactly(
    run: GeneratorRun, students: list[dict]
) -> None:
    hierarchy = generate_university_hierarchy(run.configs)
    school_names = {school["id"]: school["name"] for school in hierarchy.schools}
    expected = Counter(
        {
            school_names[school_id]: count
            for school_id, count in run.configs["generator"]["scale"][
                "school_population"
            ].items()
        }
    )
    assert Counter(student["school"] for student in students) == expected


# ── Reproducibility (F-B02) ─────────────────────────────


def test_generation_is_reproducible(run: GeneratorRun, students: list[dict]) -> None:
    second = GeneratorRun(validate_project_config())
    assert generate_students(second) == students


def test_same_run_regenerates_identically(run: GeneratorRun, students: list[dict]) -> None:
    assert generate_students(run) == students


def test_different_seed_changes_assignments(run: GeneratorRun) -> None:
    other_configs = copy.deepcopy(run.configs)
    other_configs["generator"]["generator"]["seed"] = run.seed + 1
    other_students = generate_students(GeneratorRun(other_configs))
    baseline = generate_students(run)
    assert other_students != baseline


# ── Valid hierarchy assignments ─────────────────────────


def test_hierarchy_assignments_are_valid(
    run: GeneratorRun, students: list[dict]
) -> None:
    hierarchy = generate_university_hierarchy(run.configs)
    schools = {school["id"]: school["name"] for school in hierarchy.schools}
    departments = {department["id"]: department for department in hierarchy.departments}
    programs = {program["name"]: program for program in hierarchy.programs}
    for student in students:
        program = programs[student["program"]]
        department = departments[program["department_id"]]
        assert student["department"] == department["name"]
        assert student["school"] == schools[department["school_id"]]


def test_generated_students_conform_to_schema(students: list[dict]) -> None:
    validate_records(students, STUDENTS_SCHEMA)


# ── Batch & semester from the academic calendar ─────────


def test_batch_is_earliest_semester_start_year(
    run: GeneratorRun, students: list[dict]
) -> None:
    semesters = run.configs["academic_periods"]["semesters"].values()
    expected_batch = min(spec["start_date"] for spec in semesters).year
    assert expected_batch == 2024
    assert {student["batch"] for student in students} == {expected_batch}


def test_semester_values_come_from_configured_indexes(
    run: GeneratorRun, students: list[dict]
) -> None:
    configured = {
        int(spec["semester_index"])
        for spec in run.configs["academic_periods"]["semesters"].values()
    }
    used = {student["semester"] for student in students}
    assert used == configured == {1, 2, 3, 4}


# ── Initialization failures ─────────────────────────────


def test_missing_academic_periods_raises(run: GeneratorRun) -> None:
    broken = GeneratorRun(copy.deepcopy({k: v for k, v in run.configs.items()
                                         if k != "academic_periods"}))
    with pytest.raises(GeneratorError, match="academic_periods"):
        generate_students(broken)


def test_unknown_school_population_raises(run: GeneratorRun) -> None:
    broken_configs = copy.deepcopy(run.configs)
    population = broken_configs["generator"]["scale"]["school_population"]
    total = sum(population.values())
    population["ghost"] = 10
    population["cet"] -= 10
    assert sum(population.values()) == total
    with pytest.raises(GeneratorError, match="unknown school 'ghost'"):
        generate_students(GeneratorRun(broken_configs))


def test_population_sum_mismatch_raises(run: GeneratorRun) -> None:
    broken_configs = copy.deepcopy(run.configs)
    broken_configs["generator"]["scale"]["target_students"] += 1
    with pytest.raises(GeneratorError, match="sums to"):
        generate_students(GeneratorRun(broken_configs))
