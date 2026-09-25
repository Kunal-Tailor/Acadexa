"""Tests for the synthetic behavioral model (task 4.7)."""

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
    generate_behavioral_traits,
    generate_coursework,
    generate_students,
)

_TRAIT_KEYS = ("ability", "diligence", "engagement")


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
def full_traits() -> tuple[GeneratorRun, list[dict], dict[str, dict[str, float]]]:
    """Full-scale (12000 students) traits for distribution tests."""
    run = GeneratorRun(validate_project_config())
    students = generate_students(run)
    traits = generate_behavioral_traits(run, students)
    return run, students, traits


@pytest.fixture(scope="module")
def influence_chain() -> tuple[
    GeneratorRun,
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    dict[str, dict[str, float]],
]:
    """Mid-scale (600 students) generation chain for influence tests."""
    run = GeneratorRun(_scaled_configs(600))
    students = generate_students(run)
    records = generate_academic_records(run, students)
    attendance = generate_attendance(run, students, records)
    coursework = generate_coursework(run, students, records)
    traits = generate_behavioral_traits(run, students)
    return run, students, records, attendance, coursework, traits


def _mean_marks_by_student(records: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for record in records:
        buckets.setdefault(record["student_id"], []).append(
            (record["internal_marks"] + record["midterm_marks"] + record["endterm_marks"])
            / 3
        )
    return {student_id: float(np.mean(values)) for student_id, values in buckets.items()}


def _attendance_rate_by_student(attendance: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[int]] = {}
    for row in attendance:
        bucket = buckets.setdefault(row["student_id"], [0, 0])
        bucket[0] += row["classes_attended"]
        bucket[1] += row["classes_conducted"]
    return {student_id: a / b for student_id, (a, b) in buckets.items()}


def _late_rate_by_student(coursework: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[int]] = {}
    for row in coursework:
        bucket = buckets.setdefault(row["student_id"], [0, 0])
        bucket[1] += 1
        if row["status"] == "LATE":
            bucket[0] += 1
    return {student_id: a / b for student_id, (a, b) in buckets.items()}


# ── Trait distribution & coverage (full scale) ──────────


def test_every_student_receives_all_three_traits(
    full_traits: tuple[GeneratorRun, list[dict], dict[str, dict[str, float]]],
) -> None:
    _, students, traits = full_traits
    assert set(traits) == {student["student_id"] for student in students}
    assert len(traits) == 12000
    for values in traits.values():
        assert set(values) == set(_TRAIT_KEYS)
        for value in values.values():
            assert isinstance(value, float)


def test_traits_stay_hidden_from_student_documents(
    full_traits: tuple[GeneratorRun, list[dict], dict[str, dict[str, float]]],
) -> None:
    _, students, _ = full_traits
    for student in students:
        for trait in _TRAIT_KEYS:
            assert trait not in student


def test_trait_values_lie_in_unit_interval(
    full_traits: tuple[GeneratorRun, list[dict], dict[str, dict[str, float]]],
) -> None:
    _, _, traits = full_traits
    for values in traits.values():
        for value in values.values():
            assert 0.0 <= value <= 1.0


def test_trait_distributions_follow_configuration(
    full_traits: tuple[GeneratorRun, list[dict], dict[str, dict[str, float]]],
) -> None:
    run, _, traits = full_traits
    traits_config = run.configs["generator"]["behavior"]["student_traits"]
    noise = traits_config["observation_noise_std"]
    for trait in _TRAIT_KEYS:
        samples = np.array([values[trait] for values in traits.values()])
        mean = traits_config[trait]["mean"]
        std = traits_config[trait]["std"]
        assert abs(float(samples.mean()) - mean) <= 0.02
        theoretical = float(np.hypot(std, noise))
        assert abs(float(samples.std()) - theoretical) <= 0.03


def test_most_trait_values_are_strictly_interior(
    full_traits: tuple[GeneratorRun, list[dict], dict[str, dict[str, float]]],
) -> None:
    _, _, traits = full_traits
    interior = sum(
        1
        for values in traits.values()
        for value in values.values()
        if 0.0 < value < 1.0
    )
    assert interior / (len(traits) * len(_TRAIT_KEYS)) >= 0.9


# ── Reproducibility & seeds ─────────────────────────────


def test_traits_are_reproducible_for_same_run() -> None:
    configs = _scaled_configs(600)
    run = GeneratorRun(configs)
    students = generate_students(run)
    first = generate_behavioral_traits(run, students)
    second = generate_behavioral_traits(run, students)
    assert first == second


def test_fresh_run_with_same_seed_gives_identical_traits() -> None:
    first = generate_behavioral_traits(GeneratorRun(_scaled_configs(600)))
    second = generate_behavioral_traits(GeneratorRun(_scaled_configs(600)))
    assert first == second


def test_different_seed_changes_traits() -> None:
    configs = _scaled_configs(600)
    other = _scaled_configs(600)
    other["generator"]["generator"]["seed"] = configs["generator"]["generator"]["seed"] + 1
    first = generate_behavioral_traits(GeneratorRun(configs))
    second = generate_behavioral_traits(GeneratorRun(other))
    assert first != second


# ── Configuration knobs ─────────────────────────────────


def test_observation_noise_zero_matches_latent_std() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["student_traits"]["observation_noise_std"] = 0.0
    traits = generate_behavioral_traits(GeneratorRun(configs))
    ability = np.array([values["ability"] for values in traits.values()])
    assert abs(float(ability.std()) - 0.15) <= 0.03


def test_observation_noise_widens_trait_dispersion() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["student_traits"]["observation_noise_std"] = 0.25
    traits = generate_behavioral_traits(GeneratorRun(configs))
    ability = np.array([values["ability"] for values in traits.values()])
    # Clipping at the unit bounds keeps the observed spread below the
    # unclipped N(0.65, hypot(0.15, 0.25)) theory (≈0.29).
    assert 0.20 <= float(ability.std()) <= 0.30


def test_trait_mean_knob_shifts_distribution() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["student_traits"]["ability"]["mean"] = 0.85
    traits = generate_behavioral_traits(GeneratorRun(configs))
    ability = np.array([values["ability"] for values in traits.values()])
    assert 0.74 <= float(ability.mean()) <= 0.90


# ── Influence on generated behavior (mid scale) ─────────


def test_ability_influences_generated_marks(
    influence_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, dict[str, float]],
    ],
) -> None:
    _, students, records, _, _, traits = influence_chain
    mean_marks = _mean_marks_by_student(records)
    ids = sorted(mean_marks)
    marks = np.array([mean_marks[student_id] for student_id in ids])
    ability = np.array([traits[student_id]["ability"] for student_id in ids])
    assert len(students) == 600
    assert _spearman(ability, marks) >= 0.5


def test_zero_ability_weight_removes_marks_influence() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["student_traits"]["ability_marks_weight"] = 0.0
    run = GeneratorRun(configs)
    students = generate_students(run)
    records = generate_academic_records(run, students)
    traits = generate_behavioral_traits(run, students)
    mean_marks = _mean_marks_by_student(records)
    ids = sorted(mean_marks)
    marks = np.array([mean_marks[student_id] for student_id in ids])
    ability = np.array([traits[student_id]["ability"] for student_id in ids])
    assert abs(_spearman(ability, marks)) <= 0.15


def test_diligence_influences_attendance_rate(
    influence_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, dict[str, float]],
    ],
) -> None:
    _, _, _, attendance, _, traits = influence_chain
    rates = _attendance_rate_by_student(attendance)
    ids = sorted(rates)
    attendance_rate = np.array([rates[student_id] for student_id in ids])
    diligence = np.array([traits[student_id]["diligence"] for student_id in ids])
    assert _spearman(diligence, attendance_rate) >= 0.15


def test_engagement_influences_attendance_rate(
    influence_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, dict[str, float]],
    ],
) -> None:
    _, _, _, attendance, _, traits = influence_chain
    rates = _attendance_rate_by_student(attendance)
    ids = sorted(rates)
    attendance_rate = np.array([rates[student_id] for student_id in ids])
    engagement = np.array([traits[student_id]["engagement"] for student_id in ids])
    assert _spearman(engagement, attendance_rate) >= 0.1


def test_diligence_reduces_late_submissions(
    influence_chain: tuple[
        GeneratorRun,
        list[dict],
        list[dict],
        list[dict],
        list[dict],
        dict[str, dict[str, float]],
    ],
) -> None:
    _, _, _, _, coursework, traits = influence_chain
    late_rates = _late_rate_by_student(coursework)
    ids = sorted(late_rates)
    late_rate = np.array([late_rates[student_id] for student_id in ids])
    diligence = np.array([traits[student_id]["diligence"] for student_id in ids])
    assert _spearman(diligence, late_rate) <= -0.12


# ── Error paths ─────────────────────────────────────────


def test_missing_student_traits_raises() -> None:
    configs = _scaled_configs(600)
    del configs["generator"]["behavior"]["student_traits"]
    with pytest.raises(GeneratorError, match="behavior.student_traits"):
        generate_behavioral_traits(GeneratorRun(configs))


def test_missing_trait_distribution_raises() -> None:
    configs = _scaled_configs(600)
    del configs["generator"]["behavior"]["student_traits"]["diligence"]
    with pytest.raises(GeneratorError, match="missing 'diligence'"):
        generate_behavioral_traits(GeneratorRun(configs))


def test_trait_mean_out_of_range_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["student_traits"]["ability"]["mean"] = 1.5
    with pytest.raises(GeneratorError, match="mean must be in"):
        generate_behavioral_traits(GeneratorRun(configs))


def test_trait_std_out_of_range_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["student_traits"]["engagement"]["std"] = 0.0
    with pytest.raises(GeneratorError, match="std must be in"):
        generate_behavioral_traits(GeneratorRun(configs))


def test_missing_observation_noise_raises() -> None:
    configs = _scaled_configs(600)
    del configs["generator"]["behavior"]["student_traits"]["observation_noise_std"]
    with pytest.raises(GeneratorError, match="observation_noise_std"):
        generate_behavioral_traits(GeneratorRun(configs))


def test_negative_observation_noise_raises() -> None:
    configs = _scaled_configs(600)
    configs["generator"]["behavior"]["student_traits"]["observation_noise_std"] = -0.1
    with pytest.raises(GeneratorError, match="observation_noise_std must be"):
        generate_behavioral_traits(GeneratorRun(configs))


def test_records_missing_ability_weight_raises() -> None:
    configs = _scaled_configs(36)
    del configs["generator"]["behavior"]["student_traits"]["ability_marks_weight"]
    with pytest.raises(GeneratorError, match="ability_marks_weight"):
        generate_academic_records(GeneratorRun(configs))


def test_attendance_missing_weight_raises() -> None:
    configs = _scaled_configs(36)
    del configs["generator"]["behavior"]["student_traits"][
        "engagement_attendance_weight"
    ]
    with pytest.raises(GeneratorError, match="engagement_attendance_weight"):
        generate_attendance(GeneratorRun(configs))


def test_coursework_negative_weight_raises() -> None:
    configs = _scaled_configs(36)
    configs["generator"]["behavior"]["student_traits"]["diligence_late_weight"] = -1.0
    with pytest.raises(GeneratorError, match="diligence_late_weight"):
        generate_coursework(GeneratorRun(configs))
