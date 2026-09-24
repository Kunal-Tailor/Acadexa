"""Tests for weekly attendance generation (task 4.5)."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from datetime import date

import numpy as np
import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    assign_course_difficulty,
    generate_academic_records,
    generate_attendance,
    generate_students,
)
from acadexa.validation import ATTENDANCE_SCHEMA, validate_records


@pytest.fixture(scope="module")
def dataset() -> tuple[GeneratorRun, list[dict], list[dict], list[dict]]:
    """Full-scale generation, computed once for this module."""
    run = GeneratorRun(validate_project_config())
    students = generate_students(run)
    records = generate_academic_records(run, students)
    attendance = generate_attendance(run, students, records)
    return run, students, records, attendance


@pytest.fixture(scope="module")
def term_entries(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> list[tuple[float, float, str, str]]:
    """One pass over attendance: term-level (rate, marks, school, level)."""
    run, students, records, attendance = dataset
    sums: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in attendance:
        key = (row["student_id"], row["course_id"], row["semester_id"])
        bucket = sums[key]
        bucket[0] += row["classes_attended"]
        bucket[1] += row["classes_conducted"]

    difficulties = assign_course_difficulty(
        run,
        [{"course_id": course_id} for course_id in run.configs["courses"]["courses"]],
    )
    name_to_school = {
        spec["name"]: school_id
        for school_id, spec in run.configs["hierarchy"]["schools"].items()
    }
    student_school = {
        student["student_id"]: name_to_school[student["school"]]
        for student in students
    }

    entries: list[tuple[float, float, str, str]] = []
    for record in records:
        key = (record["student_id"], record["course_id"], record["semester_id"])
        attended, conducted = sums[key]
        rate = attended / conducted
        marks = (
            record["internal_marks"]
            + record["midterm_marks"]
            + record["endterm_marks"]
        ) / 3
        entries.append(
            (
                rate,
                marks,
                student_school[record["student_id"]],
                difficulties[record["course_id"]]["difficulty_level"],
            )
        )
    return entries


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


def _rankdata(values: np.ndarray) -> np.ndarray:
    """Average ranks (1-based groups) with ties handled."""
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    ranks = np.empty(len(values))
    index = 0
    size = len(values)
    while index < size:
        end = index
        while end + 1 < size and sorted_values[end + 1] == sorted_values[index]:
            end += 1
        ranks[order[index : end + 1]] = (index + end) / 2.0 + 1.0
        index = end + 1
    return ranks


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.corrcoef(_rankdata(x), _rankdata(y))[0, 1])


# ── Full-scale structure ────────────────────────────────


def test_attendance_count_matches_documented_scale(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, students, records, attendance = dataset
    teaching_weeks = {
        spec["teaching_weeks"]
        for spec in run.configs["academic_periods"]["semesters"].values()
    }
    assert teaching_weeks == {16}
    assert len(records) == 288_000
    assert len(attendance) == len(records) * 16 == 4_608_000
    assert len(students) == 12_000


def test_full_scale_counts_weeks_and_invariants(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, records, attendance = dataset
    classes_conducted = run.configs["generator"]["behavior"]["weekly_attendance"][
        "classes_conducted"
    ]
    semester_ids = set(run.configs["academic_periods"]["semesters"])
    weeks_per_pair: Counter[tuple[str, str]] = Counter()
    for row in attendance:
        assert row["classes_conducted"] == classes_conducted
        assert 0 <= row["classes_attended"] <= row["classes_conducted"]
        assert row["week_start"].weekday() == 0
        assert row["semester_id"] in semester_ids
        assert "percentage" not in row
        weeks_per_pair[(row["student_id"], row["course_id"])] += 1
    assert set(weeks_per_pair) == {
        (record["student_id"], record["course_id"]) for record in records
    }
    assert set(weeks_per_pair.values()) == {16}


# ── Planted behavior (F-B09) ────────────────────────────


def test_attendance_correlates_moderately_with_marks(
    term_entries: list[tuple[float, float, str, str]],
) -> None:
    rates = np.array([entry[0] for entry in term_entries])
    marks = np.array([entry[1] for entry in term_entries])
    rho = _spearman(rates, marks)
    assert 0.40 <= rho <= 0.75, f"attendance↔marks Spearman {rho:.3f} outside band"


def test_course_difficulty_lowers_attendance(
    term_entries: list[tuple[float, float, str, str]],
) -> None:
    totals: dict[str, list[float]] = {
        level: [0.0, 0.0] for level in ("easy", "medium", "hard")
    }
    for rate, _, _, level in term_entries:
        totals[level][0] += rate
        totals[level][1] += 1
    means = {level: total / count for level, (total, count) in totals.items()}
    assert means["hard"] < means["medium"] < means["easy"]


def test_school_profiles_shift_attendance(
    term_entries: list[tuple[float, float, str, str]],
) -> None:
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for rate, _, school, _ in term_entries:
        totals[school][0] += rate
        totals[school][1] += 1
    means = {school: total / count for school, (total, count) in totals.items()}
    assert means["som"] > means["cet"] > means["lad"]
    assert means["sci"] > means["lad"]


# ── Small-scale schema & reproducibility ────────────────


def test_small_dataset_conforms_to_schema_and_calendar(
    small_configs: dict,
) -> None:
    attendance = generate_attendance(GeneratorRun(small_configs))
    assert len(attendance) == 36 * 24 * 16
    validate_records(attendance, ATTENDANCE_SCHEMA)
    assert all(row["week_start"].weekday() == 0 for row in attendance)


def test_attendance_is_reproducible(small_configs: dict) -> None:
    first = generate_attendance(GeneratorRun(small_configs))
    second = generate_attendance(GeneratorRun(small_configs))
    assert first == second


def test_different_seed_changes_attendance(small_configs: dict) -> None:
    other_configs = copy.deepcopy(small_configs)
    other_configs["generator"]["generator"]["seed"] += 1
    baseline = generate_attendance(GeneratorRun(small_configs))
    other = generate_attendance(GeneratorRun(other_configs))
    assert other != baseline


def test_accepts_precomputed_students_and_records(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    attendance = generate_attendance(run, students, records)
    assert len(attendance) == len(records) * 16


# ── Initialization failures ─────────────────────────────


def test_missing_weekly_attendance_config_raises(
    small_configs: dict,
) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["weekly_attendance"]
    with pytest.raises(GeneratorError, match="weekly_attendance"):
        generate_attendance(GeneratorRun(broken))


def test_missing_classes_conducted_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["weekly_attendance"]["classes_conducted"]
    with pytest.raises(GeneratorError, match="classes_conducted"):
        generate_attendance(GeneratorRun(broken))


def test_missing_attendance_drag_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["course_difficulty"]["attendance_drag"]
    with pytest.raises(GeneratorError, match="attendance_drag"):
        generate_attendance(GeneratorRun(broken))


def test_non_monday_semester_start_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    broken["academic_periods"]["semesters"]["S1"]["start_date"] = date(2024, 7, 16)
    with pytest.raises(GeneratorError, match="Monday"):
        generate_attendance(GeneratorRun(broken))


def test_teaching_weeks_past_end_date_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    broken["academic_periods"]["semesters"]["S1"]["teaching_weeks"] = 60
    with pytest.raises(GeneratorError, match="teaching_weeks"):
        generate_attendance(GeneratorRun(broken))


def test_retake_across_semesters_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    retake = dict(records[0])
    retake["semester_id"] = "S2" if retake["semester_id"] != "S2" else "S1"
    with pytest.raises(GeneratorError, match="at most one semester"):
        generate_attendance(run, students, records + [retake])


def test_record_with_unknown_student_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, _, records = small_chain
    with pytest.raises(GeneratorError, match="unknown student"):
        generate_attendance(run, students=[], records=records)
