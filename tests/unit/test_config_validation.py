"""Validation tests for the project configuration (tasks 2.1–2.5)."""

from __future__ import annotations

import copy
from datetime import timedelta

import pytest

from acadexa.config import (
    ConfigurationError,
    config_path,
    load_config_file,
    validate_academic_periods,
    validate_generator,
    validate_hierarchy,
    validate_project_config,
    validate_risk,
)


def _load_all() -> dict:
    return {
        "hierarchy": load_config_file(config_path("university", "hierarchy.toml")),
        "academic_periods": load_config_file(
            config_path("university", "academic_periods.toml")
        ),
        "generator": load_config_file(config_path("generator", "generator.toml")),
        "risk": load_config_file(config_path("risk", "risk_signals.toml")),
    }


# ── Valid project configuration ─────────────────────────


def test_project_config_is_valid() -> None:
    configs = validate_project_config()
    assert set(configs) == {"hierarchy", "courses", "academic_periods", "generator", "risk"}


# ── Hierarchy: required fields & references ─────────────


def test_hierarchy_missing_university_field_raises() -> None:
    hierarchy = _load_all()["hierarchy"]
    del hierarchy["university"]["id"]
    with pytest.raises(ConfigurationError, match="missing required field 'id'"):
        validate_hierarchy(hierarchy)


def test_hierarchy_department_unknown_school_raises() -> None:
    hierarchy = _load_all()["hierarchy"]
    hierarchy["departments"]["csa"]["school"] = "no_such_school"
    with pytest.raises(ConfigurationError, match="unknown school"):
        validate_hierarchy(hierarchy)


def test_hierarchy_program_unknown_department_raises() -> None:
    hierarchy = _load_all()["hierarchy"]
    hierarchy["programs"]["btech_cse_ai_ds"]["department"] = "no_such_dept"
    with pytest.raises(ConfigurationError, match="unknown department"):
        validate_hierarchy(hierarchy)


def test_hierarchy_empty_schools_raises() -> None:
    hierarchy = _load_all()["hierarchy"]
    hierarchy["schools"] = {}
    hierarchy["departments"] = {}
    hierarchy["programs"] = {}
    with pytest.raises(ConfigurationError, match="at least one school"):
        validate_hierarchy(hierarchy)


# ── Academic periods: ranges & incompatible values ──────


def test_semester_span_incompatible_with_teaching_weeks_raises() -> None:
    periods = _load_all()["academic_periods"]
    periods["semesters"]["S1"]["teaching_weeks"] = 10
    with pytest.raises(ConfigurationError, match="does not equal"):
        validate_academic_periods(periods)


def test_overlapping_semesters_raise() -> None:
    periods = _load_all()["academic_periods"]
    s1_end = periods["semesters"]["S1"]["end_date"]
    periods["semesters"]["S2"]["start_date"] = s1_end
    periods["semesters"]["S2"]["end_date"] = s1_end + timedelta(
        days=periods["semesters"]["S2"]["teaching_weeks"] * 7 - 1
    )
    with pytest.raises(ConfigurationError, match="overlap"):
        validate_academic_periods(periods)


def test_semester_bad_term_raises() -> None:
    periods = _load_all()["academic_periods"]
    periods["semesters"]["S1"]["term"] = "summer"
    with pytest.raises(ConfigurationError, match="term must be"):
        validate_academic_periods(periods)


def test_semester_unknown_year_raises() -> None:
    periods = _load_all()["academic_periods"]
    periods["semesters"]["S1"]["academic_year"] = "AY9"
    with pytest.raises(ConfigurationError, match="unknown academic_year"):
        validate_academic_periods(periods)


def test_duplicate_semester_index_raises() -> None:
    periods = _load_all()["academic_periods"]
    periods["semesters"]["S2"]["semester_index"] = 1
    with pytest.raises(ConfigurationError, match="duplicate semester_index"):
        validate_academic_periods(periods)


# ── Generator: ranges & incompatible values ─────────────


def test_generator_missing_seed_raises() -> None:
    configs = _load_all()
    del configs["generator"]["generator"]["seed"]
    with pytest.raises(ConfigurationError, match="missing required field 'seed'"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_population_sum_mismatch_raises() -> None:
    configs = _load_all()
    configs["generator"]["scale"]["school_population"]["cet"] += 1
    with pytest.raises(ConfigurationError, match="sums to"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_unknown_school_in_population_raises() -> None:
    configs = _load_all()
    pop = configs["generator"]["scale"]["school_population"]
    pop["ghost_school"] = pop.pop("cet")
    with pytest.raises(ConfigurationError, match="unknown school"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_trait_mean_out_of_range_raises() -> None:
    configs = _load_all()
    configs["generator"]["behavior"]["student_traits"]["ability"]["mean"] = 1.5
    with pytest.raises(ConfigurationError, match="mean must be in"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_observation_noise_out_of_range_raises() -> None:
    configs = _load_all()
    configs["generator"]["behavior"]["student_traits"]["observation_noise_std"] = -0.1
    with pytest.raises(ConfigurationError, match="observation_noise_std"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_missing_trait_weight_raises() -> None:
    configs = _load_all()
    del configs["generator"]["behavior"]["student_traits"]["ability_marks_weight"]
    with pytest.raises(ConfigurationError, match="ability_marks_weight"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_negative_trait_weight_raises() -> None:
    configs = _load_all()
    configs["generator"]["behavior"]["student_traits"]["diligence_late_weight"] = -1.0
    with pytest.raises(ConfigurationError, match="diligence_late_weight"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_decliner_rate_out_of_range_raises() -> None:
    configs = _load_all()
    configs["generator"]["behavior"]["decliners"]["rate"] = 1.5
    with pytest.raises(ConfigurationError, match="rate must be in"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_missing_decliner_key_raises() -> None:
    configs = _load_all()
    del configs["generator"]["behavior"]["decliners"]["score_weekly_decay"]
    with pytest.raises(ConfigurationError, match="score_weekly_decay"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_decliner_engagement_decay_out_of_range_raises() -> None:
    configs = _load_all()
    configs["generator"]["behavior"]["decliners"]["weekly_engagement_decay"] = 1.0
    with pytest.raises(ConfigurationError, match="weekly_engagement_decay"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_decliner_component_weeks_unordered_raises() -> None:
    configs = _load_all()
    configs["generator"]["behavior"]["decliners"]["component_weeks"]["endterm"] = 4
    with pytest.raises(ConfigurationError, match="component_weeks"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_decliner_negative_marks_weekly_decline_raises() -> None:
    configs = _load_all()
    configs["generator"]["behavior"]["decliners"]["marks_weekly_decline"] = -2.0
    with pytest.raises(ConfigurationError, match="marks_weekly_decline"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_difficulty_shares_must_sum_to_one_raises() -> None:
    configs = _load_all()
    configs["generator"]["course_difficulty"]["easy_share"] = 0.50
    with pytest.raises(ConfigurationError, match="shares sum to"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_injection_rate_out_of_range_raises() -> None:
    configs = _load_all()
    configs["generator"]["data_quality_injection"]["duplicate_lms_events"] = 1.5
    with pytest.raises(ConfigurationError, match="duplicate_lms_events"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_key_field_nulling_rejected() -> None:
    configs = _load_all()
    configs["generator"]["data_quality_injection"]["null_key_fields_allowed"] = True
    with pytest.raises(ConfigurationError, match="null_key_fields_allowed"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_negative_target_raises() -> None:
    configs = _load_all()
    configs["generator"]["scale"]["target_students"] = -5
    with pytest.raises(ConfigurationError, match="target_students"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_unknown_school_profile_raises() -> None:
    configs = _load_all()
    configs["generator"]["school_profiles"]["ghost"] = copy.deepcopy(
        configs["generator"]["school_profiles"]["cet"]
    )
    with pytest.raises(ConfigurationError, match="school_profiles"):
        validate_generator(configs["generator"], configs["hierarchy"])


def test_generator_invalid_lms_chunk_size_raises() -> None:
    configs = _load_all()
    configs["generator"]["lms_events"]["chunk_size"] = -50
    with pytest.raises(ConfigurationError, match="chunk_size must be a positive integer"):
        validate_generator(configs["generator"], configs["hierarchy"])


# ── Risk: exactly five approved signals ─────────────────


def test_risk_extra_signal_rejected() -> None:
    risk = _load_all()["risk"]
    risk["signals"]["extra_signal"] = {"threshold_percent": 50}
    with pytest.raises(ConfigurationError, match="expected exactly"):
        validate_risk(risk)


def test_risk_missing_signal_rejected() -> None:
    risk = _load_all()["risk"]
    del risk["signals"]["marks_decline"]
    with pytest.raises(ConfigurationError, match="expected exactly"):
        validate_risk(risk)


def test_risk_attendance_threshold_out_of_range_raises() -> None:
    risk = _load_all()["risk"]
    risk["signals"]["low_attendance"]["threshold_percent"] = 175.0
    with pytest.raises(ConfigurationError, match="threshold_percent"):
        validate_risk(risk)


def test_risk_max_signal_count_must_be_five_raises() -> None:
    risk = _load_all()["risk"]
    risk["risk"]["max_signal_count"] = 10
    with pytest.raises(ConfigurationError, match="max_signal_count"):
        validate_risk(risk)


def test_risk_lms_ratio_out_of_range_raises() -> None:
    risk = _load_all()["risk"]
    risk["signals"]["lms_decline"]["comparison_ratio"] = 2.0
    with pytest.raises(ConfigurationError, match="comparison_ratio"):
        validate_risk(risk)
