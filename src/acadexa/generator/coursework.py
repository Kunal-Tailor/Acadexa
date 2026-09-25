"""Synthetic coursework generation (F-B06).

Generates assignment and quiz rows at the student × course × item
grain (rules.md §12). Items are defined per course-semester from
configuration and shared by every enrolled student; enrollment comes
from academic records, so coursework never references a
non-enrolled pair. Every (student, course) pair must occur in at
 most one semester — the frozen schema grain does not model retakes.

Item schedule (deterministic, derived from the academic calendar):

- due dates are spread across the semester's teaching weeks;
  ``assigned_date = due_date − window`` (7 days for assignments,
  matching the documented example; 3 for quizzes).
- ``item_id`` values are ``A01``… / ``Q01``…, unique within a course.
- Quiz item counts scale with the course's school
  ``quiz_activity`` profile (CET courses get more quizzes, LAD fewer).

Outcome model (parameters in configuration, none hard-coded):

- ``missing_probability`` → status ``MISSING``: null ``submitted_at``
  and ``score``, ``attempts`` 0.
- Late: ``late_probability × student-school late_submission profile``
  multiplier, aligned against term marks — high marks lower the late
  chance, planting the documented negative late ↔ marks relationship
  (F-B09) at the student × course × semester grain — and scaled by
  ``1 − diligence_late_weight × (diligence − configured mean)`` from
  the hidden behavioral traits (task 4.7): diligent students submit
  late less often.
- Otherwise ``ON_TIME`` with a submission inside the item window.
- ``score`` = quality × ``max_score`` where quality = aggregate
  marks / 100 plus Gaussian noise (score ↔ performance).
- ``attempts``: submitted assignments 1; submitted quizzes retry with
  ``quiz_retry_probability``, capped at ``max_quiz_attempts``.

Decliner behavior (4.8) and deadline rhythms (5.2) are not applied
here.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import numpy as np

from acadexa.generator.academic_records import generate_academic_records
from acadexa.generator.behavioral_model import generate_behavioral_traits
from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students

_COURSEWORK_PARAM_KEYS = (
    "assignments_per_course_per_semester",
    "quizzes_per_course_per_semester",
    "assignment_window_days",
    "quiz_window_days",
    "max_late_days",
    "missing_probability",
    "late_probability",
    "late_marks_alignment",
    "quiz_retry_probability",
    "max_quiz_attempts",
    "assignment_max_score",
    "quiz_max_score",
    "score_noise_std",
)
_PROBABILITY_KEYS = (
    "missing_probability",
    "late_probability",
    "late_marks_alignment",
    "quiz_retry_probability",
)


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _due_week(teaching_weeks: int, position: int, count: int) -> int:
    """Spread ``count`` due dates over the teaching weeks (1-based)."""
    span = teaching_weeks - 1
    return -(-(span * position) // (count + 1))


def _build_course_items(
    configs: dict[str, Any],
    params: dict[str, Any],
    course_id: str,
    semester_id: str,
) -> list[dict[str, Any]]:
    """Build the shared item schedule for one course-semester."""
    semester = configs["academic_periods"]["semesters"][semester_id]
    start: date = semester["start_date"]
    end: date = semester["end_date"]
    teaching_weeks = semester["teaching_weeks"]

    department = configs["courses"]["courses"][course_id]["department"]
    school_id = configs["hierarchy"]["departments"][department]["school"]
    profile = configs["generator"].get("school_profiles", {}).get(school_id, {})
    quiz_multiplier = float(profile.get("quiz_activity", 1.0))

    assignment_count = params["assignments_per_course_per_semester"]
    quiz_base = params["quizzes_per_course_per_semester"]
    quiz_count = (
        0
        if quiz_base == 0
        else max(1, int(round(quiz_base * quiz_multiplier)))
    )

    items: list[dict[str, Any]] = []
    for position in range(1, assignment_count + 1):
        due = start + timedelta(
            weeks=_due_week(teaching_weeks, position, assignment_count)
        )
        assigned = due - timedelta(days=params["assignment_window_days"])
        _check(
            assigned >= start and due <= end,
            f"course '{course_id}' semester '{semester_id}': assignment "
            f"schedule outside the semester calendar (check window_days)",
        )
        items.append(
            {
                "item_id": f"A{position:02d}",
                "item_type": "ASSIGNMENT",
                "assigned_date": assigned,
                "due_date": due,
                "assigned_ord": assigned.toordinal(),
                "due_ord": due.toordinal(),
                "max_score": params["assignment_max_score"],
            }
        )
    for position in range(1, quiz_count + 1):
        due = start + timedelta(
            weeks=_due_week(teaching_weeks, position, quiz_count)
        )
        assigned = due - timedelta(days=params["quiz_window_days"])
        _check(
            assigned >= start and due <= end,
            f"course '{course_id}' semester '{semester_id}': quiz schedule "
            f"outside the semester calendar (check window_days)",
        )
        items.append(
            {
                "item_id": f"Q{position:02d}",
                "item_type": "QUIZ",
                "assigned_date": assigned,
                "due_date": due,
                "assigned_ord": assigned.toordinal(),
                "due_ord": due.toordinal(),
                "max_score": params["quiz_max_score"],
            }
        )
    return items


def generate_coursework(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
    records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate assignment and quiz rows for every enrollment (F-B06).

    Args:
        run: Seeded generator run providing coursework, school-profile,
            hierarchy and academic-period configuration.
        students: Previously generated student documents (needed for
            the school late-submission profile). When omitted, they
            are generated for this run.
        records: Previously generated academic records, which define
            enrollment. When omitted, they are generated for this run.

    Returns:
        One dict per student × course × item, conforming to the
        ``coursework`` schema contract.

    Raises:
        GeneratorError: if required configuration is missing or
            inconsistent, or if enrollment breaks the coursework
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
        "coursework" in behavior,
        "configs missing generator behavior.coursework",
    )
    params = behavior["coursework"]
    for key in _COURSEWORK_PARAM_KEYS:
        _check(key in params, f"generator behavior.coursework missing '{key}'")
    for key in (
        "assignments_per_course_per_semester",
        "quiz_window_days",
        "assignment_window_days",
        "max_late_days",
        "max_quiz_attempts",
        "assignment_max_score",
        "quiz_max_score",
    ):
        value = params[key]
        _check(
            isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"generator behavior.coursework.{key} must be a positive integer",
        )
    _check(
        isinstance(params["quizzes_per_course_per_semester"], int)
        and not isinstance(params["quizzes_per_course_per_semester"], bool)
        and params["quizzes_per_course_per_semester"] >= 0,
        "generator behavior.coursework.quizzes_per_course_per_semester "
        "must be a non-negative integer",
    )
    for key in _PROBABILITY_KEYS:
        value = params[key]
        _check(
            _is_number(value) and 0.0 <= value <= 1.0,
            f"generator behavior.coursework.{key} must be in [0, 1]",
        )
    _check(
        _is_number(params["score_noise_std"]) and params["score_noise_std"] >= 0,
        "generator behavior.coursework.score_noise_std must be >= 0",
    )

    _check(
        "student_traits" in behavior,
        "configs missing generator behavior.student_traits",
    )
    traits_config = behavior["student_traits"]
    _check(
        "diligence_late_weight" in traits_config,
        "generator behavior.student_traits missing 'diligence_late_weight'",
    )
    late_weight = traits_config["diligence_late_weight"]
    _check(
        _is_number(late_weight) and late_weight >= 0,
        "generator behavior.student_traits.diligence_late_weight "
        "must be a non-negative number",
    )

    _check(
        "academic_periods" in configs
        and "semesters" in configs.get("academic_periods", {}),
        "configs missing academic_periods semesters",
    )
    semesters = configs["academic_periods"]["semesters"]
    _check(bool(semesters), "academic_periods must contain at least one semester")
    for semester_id, spec in semesters.items():
        for key in ("start_date", "end_date", "teaching_weeks"):
            _check(
                key in spec,
                f"academic_periods.semesters.{semester_id} missing '{key}'",
            )
        _check(
            isinstance(spec["teaching_weeks"], int)
            and not isinstance(spec["teaching_weeks"], bool)
            and spec["teaching_weeks"] > 0,
            f"academic_periods.semesters.{semester_id}: teaching_weeks "
            "must be a positive integer",
        )
        _check(
            spec["start_date"] <= spec["end_date"],
            f"academic_periods.semesters.{semester_id}: start_date after end_date",
        )

    _check(
        "hierarchy" in configs and "departments" in configs.get("hierarchy", {}),
        "configs missing hierarchy departments configuration",
    )
    name_to_school = {
        spec["name"]: school_id
        for school_id, spec in configs.get("hierarchy", {}).get("schools", {}).items()
    }
    school_profiles = configs["generator"].get("school_profiles", {})
    _check(
        "courses" in configs and "courses" in configs.get("courses", {}),
        "configs missing courses configuration",
    )
    course_catalog = configs["courses"]["courses"]
    departments = configs["hierarchy"]["departments"]
    for course_id, spec in course_catalog.items():
        _check(
            spec["department"] in departments,
            f"courses.{course_id}: unknown department '{spec['department']}'",
        )

    if students is None:
        students = generate_students(run)
    if records is None:
        records = generate_academic_records(run, students)

    traits = generate_behavioral_traits(run, students)
    diligence_mean = traits_config["diligence"]["mean"]

    student_school: dict[str, str] = {}
    for student in students:
        school_name = student["school"]
        _check(
            school_name in name_to_school,
            f"student '{student['student_id']}': unknown school '{school_name}'",
        )
        student_school[student["student_id"]] = name_to_school[school_name]

    rng = run.child_rng("coursework")
    items_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    coursework: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    missing_probability = float(params["missing_probability"])
    late_probability = float(params["late_probability"])
    late_alignment = float(params["late_marks_alignment"])
    retry_probability = float(params["quiz_retry_probability"])
    max_quiz_attempts = params["max_quiz_attempts"]
    score_noise_std = float(params["score_noise_std"])
    max_late_days = params["max_late_days"]
    assignment_window = params["assignment_window_days"]
    quiz_window = params["quiz_window_days"]

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
            f"coursework grain requires at most one semester per student-course "
            f"pair, got '{student_id}' in '{course_id}' twice",
        )
        seen_pairs.add(pair)
        _check(
            course_id in course_catalog,
            f"record references unknown course '{course_id}'",
        )
        _check(
            semester_id in semesters,
            f"record references unknown semester '{semester_id}'",
        )

        cache_key = (course_id, semester_id)
        items = items_cache.get(cache_key)
        if items is None:
            items = _build_course_items(configs, params, course_id, semester_id)
            items_cache[cache_key] = items

        aggregate = (
            record["internal_marks"]
            + record["midterm_marks"]
            + record["endterm_marks"]
        ) / 3
        profile = school_profiles.get(student_school[student_id], {})
        late_multiplier = float(profile.get("late_submission", 1.0))
        diligence_shift = 1.0 - late_weight * (
            traits[student_id]["diligence"] - diligence_mean
        )
        late_probability_adj = min(
            1.0,
            max(
                0.0,
                late_probability
                * late_multiplier
                * (1.0 + late_alignment * (50.0 - aggregate) / 50.0)
                * diligence_shift,
            ),
        )

        # One uniform per item decides MISSING / LATE / ON_TIME; the
        # segment draws below are batched per record so the generator
        # makes a handful of vectorized RNG calls instead of one call
        # per row.
        categories = rng.random(len(items)).tolist()
        late_slots: list[int] = []
        on_time_slots: list[int] = []
        submitted_slots: list[int] = []
        for slot, category in enumerate(categories):
            if category < missing_probability:
                continue
            submitted_slots.append(slot)
            if category < missing_probability + late_probability_adj:
                late_slots.append(slot)
            else:
                on_time_slots.append(slot)

        if late_slots:
            delays = rng.integers(
                1, max_late_days + 1, size=len(late_slots)
            ).tolist()
            late_seconds = rng.integers(
                17 * 3600, 24 * 3600, size=len(late_slots)
            ).tolist()
        else:
            delays = []
            late_seconds = []
        if on_time_slots:
            windows = np.fromiter(
                (
                    assignment_window
                    if items[step]["item_type"] == "ASSIGNMENT"
                    else quiz_window
                    for step in on_time_slots
                ),
                dtype=np.int64,
                count=len(on_time_slots),
            )
            offsets = rng.integers(0, windows + 1).tolist()
            on_time_seconds = rng.integers(
                8 * 3600, 23 * 3600, size=len(on_time_slots)
            ).tolist()
        else:
            offsets = []
            on_time_seconds = []

        quiz_slots = [
            step
            for step in submitted_slots
            if items[step]["item_type"] == "QUIZ"
        ]
        if quiz_slots:
            quiz_retries = rng.binomial(
                max_quiz_attempts - 1, retry_probability, size=len(quiz_slots)
            ).tolist()
        else:
            quiz_retries = []
        if submitted_slots:
            noises = rng.normal(
                0.0, score_noise_std, size=len(submitted_slots)
            ).tolist()
        else:
            noises = []

        late_index = 0
        on_time_index = 0
        quiz_index = 0
        noise_index = 0
        for slot, item in enumerate(items):
            category = categories[slot]
            if category < missing_probability:
                status = "MISSING"
                submitted_at = None
                score = None
                attempts = 0
            elif category < missing_probability + late_probability_adj:
                status = "LATE"
                ordinal = item["due_ord"] + delays[late_index]
                seconds = late_seconds[late_index]
                late_index += 1
            else:
                status = "ON_TIME"
                ordinal = item["assigned_ord"] + offsets[on_time_index]
                seconds = on_time_seconds[on_time_index]
                on_time_index += 1

            if status != "MISSING":
                if item["item_type"] == "QUIZ":
                    attempts = 1 + quiz_retries[quiz_index]
                    quiz_index += 1
                else:
                    attempts = 1
                quality = aggregate / 100.0 + noises[noise_index]
                noise_index += 1
                if quality < 0.0:
                    quality = 0.0
                elif quality > 1.0:
                    quality = 1.0
                score = int(round(quality * item["max_score"]))
                submitted_at = datetime.combine(
                    date.fromordinal(ordinal),
                    time(seconds // 3600, (seconds // 60) % 60, seconds % 60),
                )

            coursework.append(
                {
                    "student_id": student_id,
                    "course_id": course_id,
                    "item_id": item["item_id"],
                    "item_type": item["item_type"],
                    "assigned_date": item["assigned_date"],
                    "due_date": item["due_date"],
                    "submitted_at": submitted_at,
                    "score": score,
                    "max_score": item["max_score"],
                    "attempts": attempts,
                    "status": status,
                }
            )
    return coursework
