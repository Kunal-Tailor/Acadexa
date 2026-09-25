"""Synthetic academic-record generation (F-B04).

Generates student × course × semester term summaries (internal,
midterm and endterm marks plus final letter grade) from a seeded
:class:`GeneratorRun` (rules.md §8.2, §12 grain).

Enrollment (engineering decisions — not fixed by the documents):

- Every student is enrolled in every configured semester (single
  cohort, consistent with tasks 4.3/14.3 and the documented ~290k
  ``academic_records`` target: students × 4 semesters × 6 courses).
- Each semester draws ``elective_courses_per_semester`` courses from
  other schools and the remaining ``courses_per_student_per_semester
  − elective_courses_per_semester`` from the student's own school
  catalogue, without replacement within a semester. In-school courses
  are taken without replacement across semesters until the school
  catalogue is exhausted (the default 3+3×4 consumes all 12 in-school
  courses exactly once); only if a configured draw exceeds catalogue
  size does a semester repeat an earlier course.
- All catalogue courses are treated as offered in every semester;
  ``semester_applicability`` metadata is not produced here.

Performance behavior (engineering model; parameters live in
configuration, none hard-coded):

- Course difficulty (from :func:`assign_course_difficulty`) shifts
  expected marks down by ``difficulty × max_score_drag`` points —
  the documented confounder (F-B03, memory.md §7).
- A record-level latent score is drawn from ``baseline_mean`` with
  ``record_std`` noise, plus ``ability_marks_weight × (ability −
  configured mean)`` from the hidden behavioral traits (task 4.7),
  minus the difficulty drag; each marks component adds
  ``component_std`` noise and is clipped to 0–100.
- ``final_grade`` is the letter band of the unweighted mean of the
  three components, from ``behavior.grade_scale`` (below the lowest
  band: ``F``).

Decliner behavior and school-profile marks shifts are not applied
here (school profiles model LMS/attendance/quiz/late behavior);
course documents do not receive ``difficulty``/
``semester_applicability`` fields.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from acadexa.generator.behavioral_model import generate_behavioral_traits
from acadexa.generator.courses import assign_course_difficulty
from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students
from acadexa.generator.university import generate_university_hierarchy


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _letter_grade(aggregate: float, grade_scale: dict[str, Any]) -> str:
    """Return the letter band for ``aggregate`` from configured thresholds."""
    bands = sorted(grade_scale.items(), key=lambda item: item[1], reverse=True)
    for letter, threshold in bands:
        if aggregate >= threshold:
            return str(letter)
    return "F"


def _take_courses(
    remaining: list[str],
    full_pool: list[str],
    size: int,
    rng: np.random.Generator,
) -> list[str]:
    """Draw ``size`` distinct courses, refilling from ``full_pool`` when exhausted."""
    if size == 0:
        return []
    if len(remaining) < size:
        remaining[:] = [full_pool[int(i)] for i in rng.permutation(len(full_pool))]
    picked = [int(i) for i in rng.permutation(len(remaining))[:size]]
    chosen = [remaining[index] for index in picked]
    for index in sorted(picked, reverse=True):
        remaining.pop(index)
    return chosen


def generate_academic_records(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate academic records for every student and semester (F-B04).

    Args:
        run: Seeded generator run providing scale, behavior,
            course-difficulty, academic-period and hierarchy
            configuration.
        students: Previously generated student documents. When
            omitted, :func:`generate_students` is called for this run.

    Returns:
        One dict per student × course × semester, conforming to the
        ``academic_records`` schema contract.

    Raises:
        GeneratorError: if required configuration is missing or
            inconsistent.
    """
    configs = run.configs
    _check(
        "generator" in configs and "scale" in configs.get("generator", {}),
        "configs missing generator scale configuration",
    )
    scale = configs["generator"]["scale"]
    _check(
        "courses_per_student_per_semester" in scale,
        "generator scale missing courses_per_student_per_semester",
    )
    per_semester = scale["courses_per_student_per_semester"]
    _check(
        isinstance(per_semester, int)
        and not isinstance(per_semester, bool)
        and per_semester > 0,
        "generator scale courses_per_student_per_semester must be a positive integer",
    )
    _check(
        "elective_courses_per_semester" in scale,
        "generator scale missing elective_courses_per_semester",
    )
    elective_per_semester = scale["elective_courses_per_semester"]
    _check(
        isinstance(elective_per_semester, int)
        and not isinstance(elective_per_semester, bool)
        and 0 <= elective_per_semester <= per_semester,
        "generator scale elective_courses_per_semester must be between "
        "0 and courses_per_student_per_semester",
    )
    in_school_per_semester = per_semester - elective_per_semester

    _check(
        "generator" in configs
        and "course_difficulty" in configs.get("generator", {}),
        "configs missing generator course_difficulty configuration",
    )
    difficulty_config = configs["generator"]["course_difficulty"]
    _check(
        "max_score_drag" in difficulty_config,
        "generator course_difficulty missing max_score_drag",
    )
    max_score_drag = difficulty_config["max_score_drag"]
    _check(
        isinstance(max_score_drag, (int, float))
        and not isinstance(max_score_drag, bool)
        and max_score_drag >= 0,
        "generator course_difficulty.max_score_drag must be a non-negative number",
    )

    behavior = configs.get("generator", {}).get("behavior", {})
    _check(
        "academic_performance" in behavior,
        "configs missing generator behavior.academic_performance",
    )
    performance = behavior["academic_performance"]
    for key in ("baseline_mean", "record_std", "component_std"):
        _check(
            key in performance,
            f"generator behavior.academic_performance missing '{key}'",
        )
    baseline_mean = performance["baseline_mean"]
    _check(
        isinstance(baseline_mean, (int, float))
        and not isinstance(baseline_mean, bool)
        and 0 <= baseline_mean <= 100,
        "generator behavior.academic_performance.baseline_mean must be in [0, 100]",
    )
    for key in ("record_std", "component_std"):
        value = performance[key]
        _check(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > 0,
            f"generator behavior.academic_performance.{key} must be > 0",
        )

    _check(
        "grade_scale" in behavior,
        "configs missing generator behavior.grade_scale",
    )
    grade_scale = behavior["grade_scale"]
    _check(
        isinstance(grade_scale, dict) and grade_scale,
        "generator behavior.grade_scale must not be empty",
    )
    for letter, threshold in grade_scale.items():
        _check(
            isinstance(threshold, (int, float))
            and not isinstance(threshold, bool)
            and 0 <= threshold <= 100,
            f"generator behavior.grade_scale.{letter} must be a number in [0, 100]",
        )

    _check(
        "student_traits" in behavior,
        "configs missing generator behavior.student_traits",
    )
    traits_config = behavior["student_traits"]
    _check(
        "ability_marks_weight" in traits_config,
        "generator behavior.student_traits missing 'ability_marks_weight'",
    )
    ability_weight = traits_config["ability_marks_weight"]
    _check(
        isinstance(ability_weight, (int, float))
        and not isinstance(ability_weight, bool)
        and ability_weight >= 0,
        "generator behavior.student_traits.ability_marks_weight "
        "must be a non-negative number",
    )

    _check(
        "academic_periods" in configs
        and "semesters" in configs.get("academic_periods", {}),
        "configs missing academic_periods semesters",
    )
    semesters = configs["academic_periods"]["semesters"]
    _check(bool(semesters), "academic_periods must contain at least one semester")
    semester_ids = [
        semester_id
        for semester_id, _ in sorted(
            semesters.items(), key=lambda item: item[1]["start_date"]
        )
    ]

    hierarchy = generate_university_hierarchy(configs)
    courses = list(hierarchy.courses)
    _check(bool(courses), "configs contain no courses")
    difficulties = assign_course_difficulty(run, courses)

    if students is None:
        students = generate_students(run)

    traits = generate_behavioral_traits(run, students)
    ability_mean = traits_config["ability"]["mean"]

    school_names = {student["school"] for student in students} | {
        course["school"] for course in courses
    }
    pools: dict[str, tuple[list[str], list[str]]] = {}
    for school_name in sorted(school_names):
        own_pool = [
            course["course_id"] for course in courses if course["school"] == school_name
        ]
        elective_pool = [
            course["course_id"] for course in courses if course["school"] != school_name
        ]
        if in_school_per_semester > 0:
            _check(
                len(own_pool) >= in_school_per_semester,
                f"school '{school_name}' has {len(own_pool)} courses but "
                f"{in_school_per_semester} in-school courses per semester are required",
            )
        if elective_per_semester > 0:
            _check(
                len(elective_pool) >= elective_per_semester,
                f"only {len(elective_pool)} elective courses available but "
                f"{elective_per_semester} per semester are required",
            )
        pools[school_name] = (own_pool, elective_pool)

    rng = run.child_rng("academic_records")
    baseline = float(baseline_mean)
    record_std = float(performance["record_std"])
    component_std = float(performance["component_std"])

    records: list[dict[str, Any]] = []
    for student in students:
        school_name = student["school"]
        _check(
            school_name in pools,
            f"student '{student['student_id']}': unknown school '{school_name}'",
        )
        own_pool, elective_pool = pools[school_name]
        student_traits = traits[student["student_id"]]
        ability_shift = ability_weight * (
            student_traits["ability"] - ability_mean
        )
        own_remaining = [own_pool[int(i)] for i in rng.permutation(len(own_pool))]
        elective_remaining = [
            elective_pool[int(i)] for i in rng.permutation(len(elective_pool))
        ]

        for semester_id in semester_ids:
            enrolled = _take_courses(
                own_remaining, own_pool, in_school_per_semester, rng
            )
            enrolled += _take_courses(
                elective_remaining, elective_pool, elective_per_semester, rng
            )
            drag = np.array(
                [
                    difficulties[course_id]["difficulty"] * max_score_drag
                    for course_id in enrolled
                ],
                dtype=float,
            )
            latent = rng.normal(baseline - drag + ability_shift, record_std)
            components = latent[:, None] + rng.normal(
                0.0, component_std, size=(len(enrolled), 3)
            )
            marks = np.clip(np.rint(components), 0, 100).astype(int)
            for index, course_id in enumerate(enrolled):
                internal_marks, midterm_marks, endterm_marks = (
                    int(value) for value in marks[index]
                )
                aggregate = (internal_marks + midterm_marks + endterm_marks) / 3
                records.append(
                    {
                        "student_id": student["student_id"],
                        "course_id": course_id,
                        "semester_id": semester_id,
                        "internal_marks": internal_marks,
                        "midterm_marks": midterm_marks,
                        "endterm_marks": endterm_marks,
                        "final_grade": _letter_grade(aggregate, grade_scale),
                    }
                )
    return records
