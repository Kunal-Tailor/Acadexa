"""Tests for synthetic coursework generation (task 4.6)."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from datetime import timedelta

import numpy as np
import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    generate_academic_records,
    generate_coursework,
    generate_students,
)
from acadexa.validation import COURSEWORK_SCHEMA, validate_records

_ASSIGNMENT_PREFIX = "A"
_QUIZ_PREFIX = "Q"


@pytest.fixture(scope="module")
def dataset() -> tuple[GeneratorRun, list[dict], list[dict], list[dict]]:
    """Full-scale generation, computed once for this module."""
    run = GeneratorRun(validate_project_config())
    students = generate_students(run)
    records = generate_academic_records(run, students)
    coursework = generate_coursework(run, students, records)
    return run, students, records, coursework


@pytest.fixture(scope="module")
def term_stats(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> dict:
    """One pass over coursework: status counts and term-level aggregates."""
    run, students, records, coursework = dataset
    status_counts: Counter[str] = Counter()
    stats: dict[tuple[str, str], list[float]] = {}
    for row in coursework:
        status_counts[row["status"]] += 1
        key = (row["student_id"], row["course_id"])
        entry = stats.get(key)
        if entry is None:
            entry = [0.0, 0.0, 0.0, 0.0]
            stats[key] = entry
        if row["item_type"] == "ASSIGNMENT":
            entry[0] += 1
            if row["status"] == "LATE":
                entry[1] += 1
        if row["score"] is not None:
            entry[2] += row["score"] / row["max_score"]
            entry[3] += 1

    name_to_school = {
        spec["name"]: school_id
        for school_id, spec in run.configs["hierarchy"]["schools"].items()
    }
    student_school = {
        student["student_id"]: name_to_school[student["school"]]
        for student in students
    }
    late_rates: list[float] = []
    marks_values: list[float] = []
    schools: list[str] = []
    score_pcts: list[float] = []
    score_marks: list[float] = []
    for record in records:
        entry = stats[(record["student_id"], record["course_id"])]
        marks = (
            record["internal_marks"]
            + record["midterm_marks"]
            + record["endterm_marks"]
        ) / 3
        late_rates.append(entry[1] / entry[0])
        marks_values.append(marks)
        schools.append(student_school[record["student_id"]])
        if entry[3]:
            score_pcts.append(entry[2] / entry[3])
            score_marks.append(marks)
    return {
        "status_counts": status_counts,
        "assign_total": int(sum(entry[0] for entry in stats.values())),
        "late_rates": np.array(late_rates),
        "marks": np.array(marks_values),
        "schools": schools,
        "score_pcts": np.array(score_pcts),
        "score_marks": np.array(score_marks),
    }


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


def _expected_quiz_count(configs: dict, course_id: str) -> int:
    """Quiz items per course from its school quiz_activity profile."""
    department = configs["courses"]["courses"][course_id]["department"]
    school_id = configs["hierarchy"]["departments"][department]["school"]
    base = configs["generator"]["behavior"]["coursework"][
        "quizzes_per_course_per_semester"
    ]
    profile = configs["generator"]["school_profiles"][school_id]
    return max(1, round(base * profile["quiz_activity"]))


def _expected_rows(configs: dict, records: list[dict]) -> int:
    """Rows implied by enrollment × per-course item counts."""
    assignments = configs["generator"]["behavior"]["coursework"][
        "assignments_per_course_per_semester"
    ]
    return sum(
        assignments + _expected_quiz_count(configs, record["course_id"])
        for record in records
    )


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


def test_coursework_count_matches_documented_scale(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
    term_stats: dict,
) -> None:
    run, students, records, coursework = dataset
    params = run.configs["generator"]["behavior"]["coursework"]
    assert len(students) == 12_000
    assert len(records) == 288_000
    assert term_stats["assign_total"] == 288_000 * params[
        "assignments_per_course_per_semester"
    ] == 2_304_000
    # docs promise ~3.5M coursework rows; calibrated to 3,338,810
    assert 3_200_000 <= len(coursework) <= 3_600_000


def test_status_rates_within_calibrated_bands(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
    term_stats: dict,
) -> None:
    _, _, _, coursework = dataset
    counts = term_stats["status_counts"]
    assert set(counts) == {"ON_TIME", "LATE", "MISSING"}
    total = sum(counts.values())
    assert total == len(coursework)
    assert 0.030 <= counts["MISSING"] / total <= 0.050
    assert 0.06 <= counts["LATE"] / total <= 0.16


def test_full_scale_invariants_and_shared_schedules(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, records, coursework = dataset
    params = run.configs["generator"]["behavior"]["coursework"]
    semesters = run.configs["academic_periods"]["semesters"]
    semester_of = {
        (record["student_id"], record["course_id"]): record["semester_id"]
        for record in records
    }
    schedules: dict[tuple[str, str, str], tuple] = {}

    for row in coursework:
        status = row["status"]
        assert status in ("ON_TIME", "LATE", "MISSING")
        is_quiz = row["item_type"] == "QUIZ"
        assert row["item_id"][0] == (_QUIZ_PREFIX if is_quiz else _ASSIGNMENT_PREFIX)
        assert row["assigned_date"] <= row["due_date"]
        window = (
            params["quiz_window_days"] if is_quiz else params["assignment_window_days"]
        )
        assert (row["due_date"] - row["assigned_date"]).days == window
        expected_max = (
            params["quiz_max_score"] if is_quiz else params["assignment_max_score"]
        )
        assert row["max_score"] == expected_max

        semester = semesters[semester_of[(row["student_id"], row["course_id"])]]
        assert semester["start_date"] <= row["assigned_date"]
        assert row["due_date"] <= semester["end_date"]

        schedule_key = (
            semester_of[(row["student_id"], row["course_id"])],
            row["course_id"],
            row["item_id"],
        )
        schedule = (row["assigned_date"], row["due_date"], row["item_type"])
        known = schedules.get(schedule_key)
        if known is None:
            schedules[schedule_key] = schedule
        else:
            assert known == schedule, f"shared schedule diverged: {schedule_key}"

        if status == "MISSING":
            assert row["submitted_at"] is None
            assert row["score"] is None
            assert row["attempts"] == 0
            continue

        assert row["submitted_at"] is not None
        assert row["score"] is not None
        assert 0 <= row["score"] <= row["max_score"]
        submitted_day = row["submitted_at"].date()
        hour = row["submitted_at"].hour
        if status == "LATE":
            assert row["due_date"] < submitted_day
            assert submitted_day <= row["due_date"] + timedelta(
                days=params["max_late_days"]
            )
            assert 17 <= hour <= 23
            assert row["attempts"] >= 1
        else:
            assert row["assigned_date"] <= submitted_day <= row["due_date"]
            assert 8 <= hour <= 22
            assert row["attempts"] >= 1
        if is_quiz:
            assert 1 <= row["attempts"] <= params["max_quiz_attempts"]
        else:
            assert row["attempts"] == 1

    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for (semester_id, course_id, item_id), (_, _, item_type) in schedules.items():
        grouped[(semester_id, course_id)][item_type] += 1
    for (semester_id, course_id), counts in grouped.items():
        assert counts["ASSIGNMENT"] == params["assignments_per_course_per_semester"]
        assert counts["QUIZ"] == _expected_quiz_count(run.configs, course_id)


# ── Planted behavior (F-B09) ────────────────────────────


def test_late_submissions_correlate_negatively_with_marks(
    term_stats: dict,
) -> None:
    rho = _spearman(term_stats["marks"], term_stats["late_rates"])
    assert -0.45 <= rho <= -0.12, f"late↔marks Spearman {rho:.3f} outside band"


def test_scores_correlate_positively_with_marks(term_stats: dict) -> None:
    rho = _spearman(term_stats["score_marks"], term_stats["score_pcts"])
    assert rho >= 0.70, f"score↔marks Spearman {rho:.3f} too weak"


def test_school_profiles_shift_late_submissions(term_stats: dict) -> None:
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for late_rate, school in zip(term_stats["late_rates"], term_stats["schools"]):
        totals[school][0] += float(late_rate)
        totals[school][1] += 1
    means = {school: total / count for school, (total, count) in totals.items()}
    assert means["lad"] == max(means.values())
    assert means["sci"] == min(means.values())
    assert means["lad"] - means["sci"] >= 0.01


# ── Sample schema check ─────────────────────────────────


def test_full_scale_sample_conforms_to_schema(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, coursework = dataset
    validate_records(coursework[:50_000], COURSEWORK_SCHEMA)


# ── Small-scale schema & reproducibility ────────────────


def test_small_dataset_conforms_to_schema_and_counts(
    small_configs: dict,
) -> None:
    run = GeneratorRun(small_configs)
    students = generate_students(run)
    records = generate_academic_records(run, students)
    coursework = generate_coursework(run, students, records)
    assert len(coursework) == _expected_rows(small_configs, records)
    validate_records(coursework, COURSEWORK_SCHEMA)


def test_coursework_is_reproducible(small_configs: dict) -> None:
    first = generate_coursework(GeneratorRun(small_configs))
    second = generate_coursework(GeneratorRun(small_configs))
    assert first == second


def test_different_seed_changes_coursework(small_configs: dict) -> None:
    other_configs = copy.deepcopy(small_configs)
    other_configs["generator"]["generator"]["seed"] += 1
    baseline = generate_coursework(GeneratorRun(small_configs))
    other = generate_coursework(GeneratorRun(other_configs))
    assert other != baseline


def test_accepts_precomputed_students_and_records(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    coursework = generate_coursework(run, students, records)
    assert len(coursework) == _expected_rows(run.configs, records)


# ── Initialization failures ─────────────────────────────


def test_missing_coursework_config_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["coursework"]
    with pytest.raises(GeneratorError, match="behavior.coursework"):
        generate_coursework(GeneratorRun(broken))


def test_missing_late_probability_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["coursework"]["late_probability"]
    with pytest.raises(GeneratorError, match="late_probability"):
        generate_coursework(GeneratorRun(broken))


def test_non_positive_window_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    broken["generator"]["behavior"]["coursework"]["assignment_window_days"] = 0
    with pytest.raises(GeneratorError, match="assignment_window_days"):
        generate_coursework(GeneratorRun(broken))


def test_out_of_range_probability_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    broken["generator"]["behavior"]["coursework"]["late_probability"] = 1.5
    with pytest.raises(GeneratorError, match="late_probability"):
        generate_coursework(GeneratorRun(broken))


def test_window_outside_semester_calendar_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    broken = copy.deepcopy(run.configs)
    broken["generator"]["behavior"]["coursework"]["assignment_window_days"] = 60
    with pytest.raises(GeneratorError, match="outside the semester calendar"):
        generate_coursework(GeneratorRun(broken), students, records)


def test_retake_across_semesters_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    retake = dict(records[0])
    retake["semester_id"] = "S2" if retake["semester_id"] != "S2" else "S1"
    with pytest.raises(GeneratorError, match="at most one semester"):
        generate_coursework(run, students, records + [retake])


def test_record_with_unknown_student_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, _, records = small_chain
    with pytest.raises(GeneratorError, match="unknown student"):
        generate_coursework(run, students=[], records=records)


def test_record_with_unknown_course_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    unknown = dict(records[0])
    unknown["course_id"] = "C9999"
    with pytest.raises(GeneratorError, match="unknown course"):
        generate_coursework(run, students, [unknown])
