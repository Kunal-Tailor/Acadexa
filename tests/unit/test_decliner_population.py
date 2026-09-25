"""Tests for the synthetic decliner population (task 4.8)."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    generate_academic_records,
    generate_attendance,
    generate_coursework,
    generate_decliner_flags,
    generate_students,
)


def _scaled_configs(target: int) -> dict:
    """Deep copy of the real configuration scaled to ``target`` students."""
    configs = copy.deepcopy(validate_project_config())
    scale = configs["generator"]["scale"]
    scale["target_students"] = target
    per_school = target // len(scale["school_population"])
    scale["school_population"] = {
        school_id: per_school for school_id in scale["school_population"]
    }
    return configs


@pytest.fixture(scope="module")
def full_flags() -> tuple[GeneratorRun, list[dict], dict[str, bool]]:
    """Full-scale (12000 students) decliner flags for population tests."""
    run = GeneratorRun(validate_project_config())
    students = generate_students(run)
    flags = generate_decliner_flags(run, students)
    return run, students, flags


@pytest.fixture(scope="module")
def mid_chain() -> tuple[
    GeneratorRun,
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    dict[str, bool],
]:
    """Mid-scale (600 students) generation chain for decline tests."""
    run = GeneratorRun(_scaled_configs(600))
    students = generate_students(run)
    records = generate_academic_records(run, students)
    attendance = generate_attendance(run, students, records)
    coursework = generate_coursework(run, students, records)
    flags = generate_decliner_flags(run, students)
    return run, students, records, attendance, coursework, flags


def _attendance_rates(
    rows: list[dict], semesters: dict, start_week: int
) -> dict[str, tuple[float, float]]:
    """Per-student (early, late) attendance rates; middle weeks ignored."""
    buckets: dict[str, dict[str, list[int]]] = {}
    for row in rows:
        spec = semesters[row["semester_id"]]
        week = (row["week_start"] - spec["start_date"]).days // 7 + 1
        if week < start_week:
            phase = "early"
        elif week >= start_week + 7:
            phase = "late"
        else:
            continue
        bucket = buckets.setdefault(
            row["student_id"], {"early": [0, 0], "late": [0, 0]}
        )
        bucket[phase][0] += row["classes_attended"]
        bucket[phase][1] += row["classes_conducted"]
    return {
        student_id: (early[0] / early[1], late[0] / late[1])
        for student_id, phases in buckets.items()
        if (early := phases["early"])[1] and (late := phases["late"])[1]
    }


def _component_means(
    records: list[dict], flags: dict[str, bool]
) -> tuple[np.ndarray, int, np.ndarray, int]:
    """(decliner means, count, non-decliner means, count) for the three components."""
    decliner_sum = np.zeros(3)
    decliner_count = 0
    other_sum = np.zeros(3)
    other_count = 0
    for record in records:
        values = np.array(
            [
                record["internal_marks"],
                record["midterm_marks"],
                record["endterm_marks"],
            ],
            dtype=float,
        )
        if flags[record["student_id"]]:
            decliner_sum += values
            decliner_count += 1
        else:
            other_sum += values
            other_count += 1
    return (
        decliner_sum / decliner_count,
        decliner_count,
        other_sum / other_count,
        other_count,
    )


def _score_quality_split(
    coursework: list[dict],
    semesters: dict,
    flags: dict[str, bool],
    score_start_week: int,
) -> dict[str, np.ndarray]:
    """Score quality split by decliner group and early/late due weeks."""
    buckets: dict[str, list[float]] = {"de": [], "dl": [], "ne": [], "nl": []}
    for row in coursework:
        if row["score"] is None:
            continue
        due = row["due_date"]
        spec = next(
            semester
            for semester in semesters.values()
            if semester["start_date"] <= due <= semester["end_date"]
        )
        week = (due - spec["start_date"]).days // 7 + 1
        if week < score_start_week:
            phase = "e"
        elif week >= score_start_week + 4:
            phase = "l"
        else:
            continue
        group = "d" if flags[row["student_id"]] else "n"
        buckets[group + phase].append(row["score"] / row["max_score"])
    return {key: np.array(values) for key, values in buckets.items()}


# ── Population ──────────────────────────────────────────


def test_decliner_rate_near_configured_share(
    full_flags: tuple[GeneratorRun, list[dict], dict[str, bool]],
) -> None:
    _, students, flags = full_flags
    share = sum(flags.values()) / len(students)
    assert 0.06 <= share <= 0.10, f"decliner share {share:.4f} outside band"


def test_flags_cover_every_student(
    full_flags: tuple[GeneratorRun, list[dict], dict[str, bool]],
) -> None:
    _, students, flags = full_flags
    assert set(flags) == {student["student_id"] for student in students}
    assert len(flags) == 12000
    assert all(isinstance(flag, bool) for flag in flags.values())


def test_decliner_flag_hidden_from_student_documents(
    full_flags: tuple[GeneratorRun, list[dict], dict[str, bool]],
) -> None:
    _, students, _ = full_flags
    for student in students:
        assert not any("declin" in key for key in student)


def test_flags_are_reproducible(
    full_flags: tuple[GeneratorRun, list[dict], dict[str, bool]],
) -> None:
    run, students, flags = full_flags
    assert generate_decliner_flags(run, students) == flags
    assert generate_decliner_flags(GeneratorRun(validate_project_config())) == flags


def test_different_seed_changes_flags() -> None:
    configs = _scaled_configs(600)
    other = _scaled_configs(600)
    other["generator"]["generator"]["seed"] = (
        configs["generator"]["generator"]["seed"] + 1
    )
    first = generate_decliner_flags(GeneratorRun(configs))
    second = generate_decliner_flags(GeneratorRun(other))
    assert first != second


def test_rate_zero_selects_nobody() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["rate"] = 0.0
    flags = generate_decliner_flags(GeneratorRun(configs))
    assert not any(flags.values())


def test_rate_one_selects_everyone() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["rate"] = 1.0
    flags = generate_decliner_flags(GeneratorRun(configs))
    assert all(flags.values())


# ── Decline behavior (mid scale) ────────────────────────


def test_decliner_attendance_fades_over_semester(
    mid_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, bool],
    ],
) -> None:
    run, _, _, attendance, _, flags = mid_chain
    semesters = run.configs["academic_periods"]["semesters"]
    start_week = run.configs["generator"]["behavior"]["decliners"]["start_week"]
    rates = _attendance_rates(attendance, semesters, start_week)
    decliner_early = [early for sid, (early, _) in rates.items() if flags[sid]]
    decliner_late = [late for sid, (_, late) in rates.items() if flags[sid]]
    other_early = [early for sid, (early, _) in rates.items() if not flags[sid]]
    other_late = [late for sid, (_, late) in rates.items() if not flags[sid]]
    assert len(decliner_early) >= 30
    assert np.mean(decliner_late) <= np.mean(decliner_early) - 0.20
    assert abs(np.mean(other_late) - np.mean(other_early)) <= 0.05


def test_decliner_marks_decline_within_semester(
    mid_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, bool],
    ],
) -> None:
    _, _, records, _, _, flags = mid_chain
    decliner_means, decliner_count, other_means, other_count = _component_means(
        records, flags
    )
    assert decliner_count >= 30
    assert other_count >= 300
    assert decliner_means[0] - decliner_means[2] >= 8
    assert abs(other_means[0] - other_means[2]) <= 3


def test_decliner_aggregate_below_non_decliner(
    mid_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, bool],
    ],
) -> None:
    _, _, records, _, _, flags = mid_chain
    decliner_means, _, other_means, _ = _component_means(records, flags)
    assert other_means.mean() - decliner_means.mean() >= 3


def test_decliner_coursework_scores_decline(
    mid_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, bool],
    ],
) -> None:
    run, _, _, _, coursework, flags = mid_chain
    semesters = run.configs["academic_periods"]["semesters"]
    decliner_params = run.configs["generator"]["behavior"]["decliners"]
    score_start = (
        decliner_params["start_week"] + decliner_params["marks_decline_lag_weeks"]
    )
    split = _score_quality_split(coursework, semesters, flags, score_start)
    assert len(split["de"]) >= 500
    assert np.mean(split["dl"]) <= np.mean(split["de"]) - 0.07
    assert abs(np.mean(split["nl"]) - np.mean(split["ne"])) <= 0.03


def test_non_decliner_rows_unchanged_at_zero_rate(
    mid_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, bool],
    ],
) -> None:
    run, _, records, attendance, coursework, flags = mid_chain
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["rate"] = 0.0
    other_run = GeneratorRun(configs)
    other_students = generate_students(other_run)
    other_records = generate_academic_records(other_run, other_students)
    other_attendance = generate_attendance(other_run, other_students, other_records)
    other_coursework = generate_coursework(other_run, other_students, other_records)

    decliner_ids = {student_id for student_id, flag in flags.items() if flag}
    non_decliner_ids = set(flags) - decliner_ids
    assert not any(generate_decliner_flags(other_run, other_students).values())

    changed_decliner_rows = 0
    for left, right in zip(records, other_records):
        if left["student_id"] in non_decliner_ids:
            assert left == right
        elif left != right:
            changed_decliner_rows += 1
    assert changed_decliner_rows > 0

    for left, right in zip(attendance, other_attendance):
        if left["student_id"] in non_decliner_ids:
            assert left == right
    for left, right in zip(coursework, other_coursework):
        if left["student_id"] in non_decliner_ids:
            assert left == right


# ── Error paths ─────────────────────────────────────────


def test_missing_decliners_section_raises() -> None:
    configs = _scaled_configs(600)
    del configs["generator"]["behavior"]["decliners"]
    with pytest.raises(GeneratorError, match="behavior.decliners"):
        generate_decliner_flags(GeneratorRun(configs))


def test_missing_rate_raises() -> None:
    configs = _scaled_configs(600)
    del configs["generator"]["behavior"]["decliners"]["rate"]
    with pytest.raises(GeneratorError, match="missing 'rate'"):
        generate_decliner_flags(GeneratorRun(configs))


def test_rate_out_of_range_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["rate"] = 1.5
    with pytest.raises(GeneratorError, match="rate must be in"):
        generate_decliner_flags(GeneratorRun(configs))


def test_start_week_out_of_range_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["start_week"] = 0
    with pytest.raises(GeneratorError, match="start_week must be"):
        generate_decliner_flags(GeneratorRun(configs))


def test_engagement_decay_out_of_range_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["weekly_engagement_decay"] = 1.2
    with pytest.raises(GeneratorError, match="weekly_engagement_decay"):
        generate_decliner_flags(GeneratorRun(configs))


def test_marks_lag_out_of_range_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["marks_decline_lag_weeks"] = 0
    with pytest.raises(GeneratorError, match="marks_decline_lag_weeks"):
        generate_decliner_flags(GeneratorRun(configs))


def test_missing_component_weeks_raises() -> None:
    configs = _scaled_configs(600)
    del configs["generator"]["behavior"]["decliners"]["component_weeks"]
    with pytest.raises(GeneratorError, match="component_weeks"):
        generate_decliner_flags(GeneratorRun(configs))


def test_unordered_component_weeks_raise() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["component_weeks"]["endterm"] = 2
    with pytest.raises(GeneratorError, match="internal < midterm < endterm"):
        generate_decliner_flags(GeneratorRun(configs))


def test_negative_marks_weekly_decline_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["marks_weekly_decline"] = -1.0
    with pytest.raises(GeneratorError, match="marks_weekly_decline must be"):
        generate_decliner_flags(GeneratorRun(configs))


def test_score_weekly_decay_out_of_range_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["decliners"]["score_weekly_decay"] = 1.0
    with pytest.raises(GeneratorError, match="score_weekly_decay"):
        generate_decliner_flags(GeneratorRun(configs))


def test_consumer_fails_fast_without_decliners_section() -> None:
    configs = _scaled_configs(36)
    del configs["generator"]["behavior"]["decliners"]
    with pytest.raises(GeneratorError, match="behavior.decliners"):
        generate_academic_records(GeneratorRun(configs))
