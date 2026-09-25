"""Synthetic weekly attendance generation (F-B05).

Generates student × course × week attendance rows with raw
``classes_conducted`` / ``classes_attended`` counts (rules.md §13:
percentage is derived, never stored). Weeks follow each semester's
configured calendar (Monday-start, ``teaching_weeks`` rows).

Weekly probability model (parameters in configuration, none
hard-coded):

- ``base_probability × school profile attendance multiplier`` —
  school profiles shift generated behavior (original_idea §5.2).
- minus ``difficulty × course_difficulty.attendance_drag`` — course
  difficulty is the documented confounder shifting attendance and
  marks together (memory.md §7).
- plus ``alignment_weight × (aggregate marks − 50) / 50`` — plants
  the attendance ↔ marks relationship (F-B09) at the student ×
  course × semester grain analytics will join on.
- plus the configured diligence/engagement attendance weights ×
  (trait − configured mean) — hidden student traits shift weekly
  attendance (prd.md §13.1, task 4.7).
- plus weekly Gaussian noise, clipped to floor/ceiling;
  ``classes_attended ~ Binomial(classes_conducted, p)``.

Enrollment comes from academic records, so attendance never
references a non-enrolled student/course/semester. Every
(student, course) pair must occur in at most one semester — the
frozen schema grain (student × course × week) does not model retakes.

Decliner decline (4.8) and LMS rhythms (5.2) are not applied here.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from acadexa.generator.academic_records import generate_academic_records
from acadexa.generator.behavioral_model import generate_behavioral_traits
from acadexa.generator.courses import assign_course_difficulty
from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students

_WEEKLY_PARAM_KEYS = (
    "classes_conducted",
    "base_probability",
    "alignment_weight",
    "weekly_noise_std",
    "probability_floor",
    "probability_ceiling",
)


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def generate_attendance(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
    records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate weekly attendance rows for every enrollment (F-B05).

    Args:
        run: Seeded generator run providing weekly-attendance,
            course-difficulty, school-profile, hierarchy and
            academic-period configuration.
        students: Previously generated student documents (needed for
            school profile lookup). When omitted, they are generated
            for this run.
        records: Previously generated academic records, which define
            enrollment. When omitted, they are generated for this run.

    Returns:
        One dict per student × course × week, conforming to the
        ``attendance`` schema contract.

    Raises:
        GeneratorError: if required configuration is missing or
            inconsistent, or if enrollment breaks the attendance
            grain (a student enrolled in one course across two
            semesters).
    """
    configs = run.configs
    _check(
        "generator" in configs and "behavior" in configs.get("generator", {}),
        "configs missing generator behavior configuration",
    )
    behavior = configs["generator"]["behavior"]
    _check(
        "weekly_attendance" in behavior,
        "configs missing generator behavior.weekly_attendance",
    )
    params = behavior["weekly_attendance"]
    for key in _WEEKLY_PARAM_KEYS:
        _check(
            key in params,
            f"generator behavior.weekly_attendance missing '{key}'",
        )
    classes_conducted = params["classes_conducted"]
    _check(
        isinstance(classes_conducted, int)
        and not isinstance(classes_conducted, bool)
        and classes_conducted > 0,
        "generator behavior.weekly_attendance.classes_conducted must be a positive integer",
    )
    base_probability = params["base_probability"]
    _check(
        _is_number(base_probability) and 0.0 <= base_probability <= 1.0,
        "generator behavior.weekly_attendance.base_probability must be in [0, 1]",
    )
    alignment_weight = params["alignment_weight"]
    _check(
        _is_number(alignment_weight) and 0.0 <= alignment_weight <= 1.0,
        "generator behavior.weekly_attendance.alignment_weight must be in [0, 1]",
    )
    weekly_noise_std = params["weekly_noise_std"]
    _check(
        _is_number(weekly_noise_std) and weekly_noise_std >= 0,
        "generator behavior.weekly_attendance.weekly_noise_std must be >= 0",
    )
    floor = params["probability_floor"]
    ceiling = params["probability_ceiling"]
    _check(
        _is_number(floor)
        and _is_number(ceiling)
        and 0.0 <= floor < ceiling <= 1.0,
        "generator behavior.weekly_attendance probability_floor/probability_ceiling "
        "must satisfy 0 <= floor < ceiling <= 1",
    )

    _check(
        "student_traits" in behavior,
        "configs missing generator behavior.student_traits",
    )
    traits_config = behavior["student_traits"]
    attendance_weights: dict[str, float] = {}
    for key in ("diligence_attendance_weight", "engagement_attendance_weight"):
        _check(
            key in traits_config,
            f"generator behavior.student_traits missing '{key}'",
        )
        weight = traits_config[key]
        _check(
            _is_number(weight) and weight >= 0,
            f"generator behavior.student_traits.{key} must be a non-negative number",
        )
        attendance_weights[key] = float(weight)

    _check(
        "generator" in configs
        and "course_difficulty" in configs.get("generator", {}),
        "configs missing generator course_difficulty configuration",
    )
    difficulty_config = configs["generator"]["course_difficulty"]
    _check(
        "attendance_drag" in difficulty_config,
        "generator course_difficulty missing 'attendance_drag'",
    )
    attendance_drag = difficulty_config["attendance_drag"]
    _check(
        _is_number(attendance_drag) and attendance_drag >= 0,
        "generator course_difficulty.attendance_drag must be a non-negative number",
    )

    _check(
        "academic_periods" in configs
        and "semesters" in configs.get("academic_periods", {}),
        "configs missing academic_periods semesters",
    )
    semesters = configs["academic_periods"]["semesters"]
    _check(bool(semesters), "academic_periods must contain at least one semester")
    semester_weeks: dict[str, list[date]] = {}
    for semester_id, spec in semesters.items():
        for key in ("start_date", "end_date", "teaching_weeks"):
            _check(
                key in spec,
                f"academic_periods.semesters.{semester_id} missing '{key}'",
            )
        start = spec["start_date"]
        end = spec["end_date"]
        teaching_weeks = spec["teaching_weeks"]
        _check(
            isinstance(teaching_weeks, int)
            and not isinstance(teaching_weeks, bool)
            and teaching_weeks > 0,
            f"academic_periods.semesters.{semester_id}: teaching_weeks "
            "must be a positive integer",
        )
        _check(
            start.weekday() == 0,
            f"academic_periods.semesters.{semester_id}: start_date must be a Monday",
        )
        _check(
            start + timedelta(weeks=teaching_weeks - 1, days=6) <= end,
            f"academic_periods.semesters.{semester_id}: teaching_weeks {teaching_weeks} "
            "extend past end_date",
        )
        semester_weeks[semester_id] = [
            start + timedelta(weeks=offset) for offset in range(teaching_weeks)
        ]

    _check(
        "hierarchy" in configs and "schools" in configs.get("hierarchy", {}),
        "configs missing hierarchy schools configuration",
    )
    name_to_school = {
        spec["name"]: school_id
        for school_id, spec in configs["hierarchy"]["schools"].items()
    }
    school_profiles = configs["generator"].get("school_profiles", {})

    _check(
        "courses" in configs and "courses" in configs.get("courses", {}),
        "configs missing courses configuration",
    )
    course_ids = list(configs["courses"]["courses"])
    difficulties = assign_course_difficulty(
        run, [{"course_id": course_id} for course_id in course_ids]
    )

    if students is None:
        students = generate_students(run)
    if records is None:
        records = generate_academic_records(run, students)

    traits = generate_behavioral_traits(run, students)
    diligence_mean = traits_config["diligence"]["mean"]
    engagement_mean = traits_config["engagement"]["mean"]

    student_school: dict[str, str] = {}
    for student in students:
        school_name = student["school"]
        _check(
            school_name in name_to_school,
            f"student '{student['student_id']}': unknown school '{school_name}'",
        )
        student_school[student["student_id"]] = name_to_school[school_name]

    rng = run.child_rng("attendance")
    attendance: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for record in records:
        student_id = record["student_id"]
        course_id = record["course_id"]
        semester_id = record["semester_id"]
        _check(
            student_id in student_school,
            f"record references unknown student '{student_id}'",
        )
        pair = (student_id, course_id)
        _check(
            pair not in seen_pairs,
            f"attendance grain requires at most one semester per student-course "
            f"pair, got '{student_id}' in '{course_id}' twice",
        )
        seen_pairs.add(pair)
        _check(
            course_id in difficulties,
            f"record references unknown course '{course_id}'",
        )
        _check(
            semester_id in semester_weeks,
            f"record references unknown semester '{semester_id}'",
        )
        weeks = semester_weeks[semester_id]

        profile = school_profiles.get(student_school[student_id], {})
        multiplier = float(profile.get("attendance", 1.0))
        difficulty = difficulties[course_id]["difficulty"]
        aggregate = (
            record["internal_marks"]
            + record["midterm_marks"]
            + record["endterm_marks"]
        ) / 3
        student_traits = traits[student_id]
        trait_shift = (
            attendance_weights["diligence_attendance_weight"]
            * (student_traits["diligence"] - diligence_mean)
            + attendance_weights["engagement_attendance_weight"]
            * (student_traits["engagement"] - engagement_mean)
        )
        probability = (
            base_probability * multiplier
            - difficulty * attendance_drag
            + alignment_weight * (aggregate - 50.0) / 50.0
            + trait_shift
        )
        noise = rng.normal(0.0, weekly_noise_std, size=len(weeks))
        probabilities = np.clip(
            probability + noise, float(floor), float(ceiling)
        )
        attended = rng.binomial(classes_conducted, probabilities)
        for index, week_start in enumerate(weeks):
            attendance.append(
                {
                    "student_id": student_id,
                    "course_id": course_id,
                    "semester_id": semester_id,
                    "week_start": week_start,
                    "classes_conducted": classes_conducted,
                    "classes_attended": int(attended[index]),
                }
            )
    return attendance
