"""Validation for project configuration files loaded in tasks 2.1–2.5.

Checks required fields, valid ranges and incompatible cross-file values.
Raises :class:`ConfigurationError` with a specific message on the first
failure. Does not generate or modify data.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from acadexa.config.loader import config_path, load_config_file

RISK_SIGNAL_NAMES = frozenset(
    {
        "low_attendance",
        "lms_decline",
        "late_submissions",
        "marks_decline",
        "low_quiz_activity",
    }
)

HIERARCHY_REQUIRED = ("id", "name")
DEPARTMENT_REQUIRED = ("school", "code", "name")
PROGRAM_REQUIRED = ("department", "degree", "name")
COURSE_REQUIRED = ("title", "department")
SEMESTER_REQUIRED = (
    "academic_year",
    "semester_index",
    "position_in_year",
    "term",
    "start_date",
    "end_date",
    "teaching_weeks",
)
SCHOOL_PROFILE_MULTIPLIERS = ("lms_activity", "attendance", "quiz_activity", "late_submission")
INJECTION_RATE_KEYS = (
    "duplicate_lms_events",
    "nulls_non_key",
    "timestamp_inconsistencies",
    "course_id_formatting",
    "orphan_records",
    "out_of_range_values",
)


class ConfigurationError(ValueError):
    """Raised when project configuration fails validation."""


def _check(condition: bool, message: str) -> None:
    """Raise ConfigurationError with ``message`` when ``condition`` is false."""
    if not condition:
        raise ConfigurationError(message)


def _require_keys(mapping: dict[str, Any], required: tuple[str, ...], context: str) -> None:
    for key in required:
        _check(key in mapping, f"{context}: missing required field '{key}'")


def validate_hierarchy(config: dict[str, Any]) -> None:
    """Validate university metadata, schools, departments and programs."""
    _require_keys(config, ("university", "schools", "departments", "programs"), "hierarchy")
    _require_keys(config["university"], HIERARCHY_REQUIRED, "hierarchy.university")

    schools = config["schools"]
    departments = config["departments"]
    programs = config["programs"]
    _check(len(schools) > 0, "hierarchy: at least one school is required")
    _check(len(departments) > 0, "hierarchy: at least one department is required")
    _check(len(programs) > 0, "hierarchy: at least one program is required")

    for sid, school in schools.items():
        _require_keys(school, ("code", "name"), f"hierarchy.schools.{sid}")

    for did, dept in departments.items():
        _require_keys(dept, DEPARTMENT_REQUIRED, f"hierarchy.departments.{did}")
        _check(
            dept["school"] in schools,
            f"hierarchy.departments.{did}: unknown school '{dept['school']}'",
        )

    for pid, program in programs.items():
        _require_keys(program, PROGRAM_REQUIRED, f"hierarchy.programs.{pid}")
        _check(
            program["department"] in departments,
            f"hierarchy.programs.{pid}: unknown department '{program['department']}'",
        )


def validate_courses(config: dict[str, Any], hierarchy: dict[str, Any]) -> None:
    """Validate the course catalog against the hierarchy."""
    _require_keys(config, ("courses",), "courses")
    courses = config["courses"]
    departments = hierarchy["departments"]
    _check(len(courses) > 0, "courses: catalog must not be empty")
    for cid, course in courses.items():
        _require_keys(course, COURSE_REQUIRED, f"courses.{cid}")
        _check(
            course["department"] in departments,
            f"courses.{cid}: unknown department '{course['department']}'",
        )


def validate_academic_periods(config: dict[str, Any]) -> None:
    """Validate academic years and semester periods for range and compatibility."""
    _require_keys(config, ("academic_years", "semesters"), "academic_periods")
    years = config["academic_years"]
    semesters = config["semesters"]
    _check(len(years) > 0, "academic_periods: at least one academic year is required")
    _check(len(semesters) > 0, "academic_periods: at least one semester is required")

    seen_indices: set[int] = set()
    for sid, sem in semesters.items():
        context = f"academic_periods.semesters.{sid}"
        _require_keys(sem, SEMESTER_REQUIRED, context)
        _check(
            sem["academic_year"] in years,
            f"{context}: unknown academic_year '{sem['academic_year']}'",
        )
        _check(sem["term"] in ("odd", "even"), f"{context}: term must be 'odd' or 'even'")
        _check(
            sem["position_in_year"] in (1, 2),
            f"{context}: position_in_year must be 1 or 2",
        )
        _check(
            isinstance(sem["start_date"], date) and isinstance(sem["end_date"], date),
            f"{context}: start_date and end_date must be dates",
        )
        _check(
            sem["start_date"] < sem["end_date"],
            f"{context}: start_date must be before end_date",
        )
        _check(
            isinstance(sem["teaching_weeks"], int) and sem["teaching_weeks"] > 0,
            f"{context}: teaching_weeks must be a positive integer",
        )
        span_days = (sem["end_date"] - sem["start_date"]).days + 1
        _check(
            span_days == sem["teaching_weeks"] * 7,
            f"{context}: date span ({span_days} days) does not equal "
            f"teaching_weeks * 7 ({sem['teaching_weeks'] * 7} days)",
        )
        index = sem["semester_index"]
        _check(
            isinstance(index, int) and index > 0,
            f"{context}: semester_index must be a positive integer",
        )
        _check(index not in seen_indices, f"{context}: duplicate semester_index {index}")
        seen_indices.add(index)

    ordered = sorted(semesters.values(), key=lambda s: s["start_date"])
    for earlier, later in zip(ordered, ordered[1:]):
        _check(
            later["start_date"] > earlier["end_date"],
            "academic_periods: semesters overlap "
            f"({earlier['start_date']}..{earlier['end_date']} vs "
            f"{later['start_date']}..{later['end_date']})",
        )


def validate_generator(config: dict[str, Any], hierarchy: dict[str, Any]) -> None:
    """Validate generator seed, scale, behavior, difficulty and injection rates."""
    _require_keys(config, ("generator", "scale", "behavior", "course_difficulty",
                           "data_quality_injection"), "generator")
    _require_keys(config["generator"], ("seed",), "generator.generator")
    _check(
        isinstance(config["generator"]["seed"], int),
        "generator.generator: seed must be an integer",
    )

    scale = config["scale"]
    _require_keys(
        scale,
        ("target_students", "target_courses", "target_lms_events",
         "lms_events_per_student_per_day"),
        "generator.scale",
    )
    for key in ("target_students", "target_courses", "target_lms_events",
                "lms_events_per_student_per_day"):
        _check(
            isinstance(scale[key], int) and scale[key] > 0,
            f"generator.scale.{key}: must be a positive integer",
        )

    schools = hierarchy["schools"]
    population = scale.get("school_population", {})
    _check(len(population) > 0, "generator.scale: school_population must not be empty")
    for sid, count in population.items():
        _check(
            sid in schools,
            f"generator.scale.school_population: unknown school '{sid}'",
        )
        _check(
            isinstance(count, int) and count >= 0,
            f"generator.scale.school_population.{sid}: must be a non-negative integer",
        )
    total = sum(population.values())
    _check(
        total == scale["target_students"],
        f"generator.scale.school_population sums to {total}, "
        f"but target_students is {scale['target_students']}",
    )

    behavior = config["behavior"]
    _require_keys(behavior, ("student_traits", "decliners", "rhythms"), "generator.behavior")
    for trait in ("ability", "diligence", "engagement"):
        _check(trait in behavior["student_traits"], f"generator.behavior.student_traits: missing '{trait}'")
        params = behavior["student_traits"][trait]
        _require_keys(params, ("mean", "std"), f"generator.behavior.student_traits.{trait}")
        _check(
            0.0 <= params["mean"] <= 1.0,
            f"generator.behavior.student_traits.{trait}.mean must be in [0, 1]",
        )
        _check(
            0.0 < params["std"] <= 1.0,
            f"generator.behavior.student_traits.{trait}.std must be in (0, 1]",
        )

    traits = behavior["student_traits"]
    _check(
        "observation_noise_std" in traits,
        "generator.behavior.student_traits: missing 'observation_noise_std'",
    )
    _check(
        isinstance(traits["observation_noise_std"], (int, float))
        and not isinstance(traits["observation_noise_std"], bool)
        and traits["observation_noise_std"] >= 0.0,
        "generator.behavior.student_traits.observation_noise_std must be >= 0",
    )
    for weight_name in (
        "ability_marks_weight",
        "diligence_attendance_weight",
        "engagement_attendance_weight",
        "diligence_late_weight",
    ):
        _check(
            weight_name in traits,
            f"generator.behavior.student_traits: missing '{weight_name}'",
        )
        _check(
            isinstance(traits[weight_name], (int, float))
            and not isinstance(traits[weight_name], bool)
            and traits[weight_name] >= 0.0,
            f"generator.behavior.student_traits.{weight_name} must be >= 0",
        )

    decliners = behavior["decliners"]
    _require_keys(decliners, ("rate",), "generator.behavior.decliners")
    _check(
        0.0 <= decliners["rate"] <= 1.0,
        "generator.behavior.decliners.rate must be in [0, 1]",
    )
    if "start_week" in decliners:
        _check(
            decliners["start_week"] >= 1,
            "generator.behavior.decliners.start_week must be >= 1",
        )
    if "marks_decline_lag_weeks" in decliners:
        _check(
            decliners["marks_decline_lag_weeks"] >= 1,
            "generator.behavior.decliners.marks_decline_lag_weeks must be >= 1",
        )

    for factor_name, factor in behavior["rhythms"].items():
        _check(
            isinstance(factor, (int, float)) and factor > 0,
            f"generator.behavior.rhythms.{factor_name}: must be > 0",
        )

    for sid, profile in config.get("school_profiles", {}).items():
        _check(
            sid in schools,
            f"generator.school_profiles: unknown school '{sid}'",
        )
        for name in SCHOOL_PROFILE_MULTIPLIERS:
            _check(
                name in profile,
                f"generator.school_profiles.{sid}: missing '{name}'",
            )
            _check(
                0.0 < profile[name] <= 3.0,
                f"generator.school_profiles.{sid}.{name} must be in (0, 3]",
            )

    difficulty = config["course_difficulty"]
    _require_keys(
        difficulty,
        ("easy_share", "medium_share", "hard_share"),
        "generator.course_difficulty",
    )
    for name in ("easy_share", "medium_share", "hard_share"):
        _check(
            0.0 <= difficulty[name] <= 1.0,
            f"generator.course_difficulty.{name} must be in [0, 1]",
        )
    share_sum = difficulty["easy_share"] + difficulty["medium_share"] + difficulty["hard_share"]
    _check(
        abs(share_sum - 1.0) < 1e-9,
        f"generator.course_difficulty: shares sum to {share_sum}, expected 1.0",
    )

    injection = config["data_quality_injection"]
    _require_keys(injection, INJECTION_RATE_KEYS, "generator.data_quality_injection")
    for name in INJECTION_RATE_KEYS:
        _check(
            0.0 <= injection[name] <= 1.0,
            f"generator.data_quality_injection.{name} must be in [0, 1]",
        )
    _check(
        injection.get("null_key_fields_allowed") is False,
        "generator.data_quality_injection: null_key_fields_allowed must be false "
        "(rules.md §10.1: key identifiers must not be intentionally nulled)",
    )


def validate_risk(config: dict[str, Any]) -> None:
    """Validate the risk configuration contains exactly the five approved signals."""
    _require_keys(config, ("risk", "signals"), "risk")
    _check(
        config["risk"].get("max_signal_count") == 5,
        "risk.risk: max_signal_count must be 5",
    )
    _check(
        config["risk"].get("points_per_signal") == 1,
        "risk.risk: points_per_signal must be 1",
    )

    signals = config["signals"]
    names = set(signals)
    _check(
        names == set(RISK_SIGNAL_NAMES),
        f"risk.signals: expected exactly {sorted(RISK_SIGNAL_NAMES)}, got {sorted(names)}",
    )

    attendance = signals["low_attendance"]
    _check(
        0.0 <= attendance.get("threshold_percent", -1) <= 100.0,
        "risk.signals.low_attendance.threshold_percent must be in [0, 100]",
    )

    lms = signals["lms_decline"]
    _check(
        isinstance(lms.get("window_weeks"), int) and lms["window_weeks"] > 0,
        "risk.signals.lms_decline.window_weeks must be a positive integer",
    )
    _check(
        0.0 <= lms.get("comparison_ratio", -1) <= 1.0,
        "risk.signals.lms_decline.comparison_ratio must be in [0, 1]",
    )

    late = signals["late_submissions"]
    _check(
        0.0 <= late.get("late_rate_threshold", -1) <= 1.0,
        "risk.signals.late_submissions.late_rate_threshold must be in [0, 1]",
    )

    marks = signals["marks_decline"]
    _check(
        isinstance(marks.get("recent_items"), int) and marks["recent_items"] >= 1,
        "risk.signals.marks_decline.recent_items must be an integer >= 1",
    )
    _check(
        marks.get("point_drop_threshold", -1) >= 0,
        "risk.signals.marks_decline.point_drop_threshold must be >= 0",
    )

    quiz = signals["low_quiz_activity"]
    _check(
        0.0 <= quiz.get("percentile_threshold", -1) <= 1.0,
        "risk.signals.low_quiz_activity.percentile_threshold must be in [0, 1]",
    )


def validate_project_config() -> dict[str, dict[str, Any]]:
    """Load and validate every project configuration file.

    Returns:
        The loaded configurations keyed by file stem.

    Raises:
        ConfigurationError: if any file is missing, unreadable or invalid.
    """
    hierarchy = load_config_file(config_path("university", "hierarchy.toml"))
    courses = load_config_file(config_path("university", "courses.toml"))
    academic_periods = load_config_file(config_path("university", "academic_periods.toml"))
    generator = load_config_file(config_path("generator", "generator.toml"))
    risk = load_config_file(config_path("risk", "risk_signals.toml"))

    validate_hierarchy(hierarchy)
    validate_courses(courses, hierarchy)
    validate_academic_periods(academic_periods)
    validate_generator(generator, hierarchy)
    validate_risk(risk)

    return {
        "hierarchy": hierarchy,
        "courses": courses,
        "academic_periods": academic_periods,
        "generator": generator,
        "risk": risk,
    }
