"""Synthetic student generation (F-B02).

Generates students with stable identifiers and valid hierarchy
assignments from the validated configuration and a seeded
:class:`GeneratorRun` (rules.md §8.2: deterministic seed).

- Student IDs are stable sequential identifiers ``STU000001``…
  for a given target population.
- Per-school headcounts match ``scale.school_population`` exactly.
- Each student's program is drawn from the assigned school's
  programs, so school → department → program assignments are always
  consistent with the hierarchy.
- The cohort batch is the start year of the earliest configured
  semester; the current-semester value is drawn from the configured
  semester indexes.
- Hidden behavioral traits (ability, diligence, engagement) are
  produced by the behavioral model (task 4.7), not here.
"""

from __future__ import annotations

from typing import Any

from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.university import generate_university_hierarchy


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def generate_students(run: GeneratorRun) -> list[dict[str, Any]]:
    """Generate the synthetic student population for a seeded run.

    Args:
        run: A seeded generator run whose ``configs`` contain the
            validated generator scale, academic periods and
            university hierarchy configuration.

    Returns:
        One dict per student, conforming to the ``students``
        schema contract.

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
        "school_population" in scale,
        "generator scale missing school_population",
    )
    _check(
        "target_students" in scale,
        "generator scale missing target_students",
    )
    _check(
        "academic_periods" in configs
        and "semesters" in configs.get("academic_periods", {}),
        "configs missing academic_periods semesters",
    )
    semesters = configs["academic_periods"]["semesters"]
    _check(bool(semesters), "academic_periods must contain at least one semester")

    ordered_semesters = sorted(semesters.values(), key=lambda spec: spec["start_date"])
    batch = ordered_semesters[0]["start_date"].year
    semester_indexes = sorted({int(spec["semester_index"]) for spec in ordered_semesters})

    hierarchy = generate_university_hierarchy(configs)
    school_names = {school["id"]: school["name"] for school in hierarchy.schools}
    department_names = {
        department["id"]: department["name"] for department in hierarchy.departments
    }
    department_school = {
        department["id"]: department["school_id"] for department in hierarchy.departments
    }
    programs_by_school: dict[str, list[dict[str, Any]]] = {
        school["id"]: [] for school in hierarchy.schools
    }
    for program in hierarchy.programs:
        programs_by_school[department_school[program["department_id"]]].append(program)

    population = scale["school_population"]
    _check(
        isinstance(population, dict) and population,
        "generator scale school_population must not be empty",
    )
    for school_id, count in population.items():
        _check(
            school_id in programs_by_school,
            f"school_population: unknown school '{school_id}'",
        )
        _check(
            bool(programs_by_school[school_id]),
            f"school_population: school '{school_id}' has no programs",
        )
        _check(
            isinstance(count, int) and count >= 0,
            f"school_population: count for '{school_id}' must be a non-negative integer",
        )
    target = scale["target_students"]
    total = sum(population.values())
    _check(
        total == target,
        f"school_population sums to {total}, but target_students is {target}",
    )
    _check(
        target <= 999_999,
        f"target_students {target} exceeds the STU###### identifier space",
    )

    school_slots: list[str] = []
    for school_id, count in population.items():
        school_slots.extend([school_id] * count)

    rng = run.child_rng("students")
    order = rng.permutation(len(school_slots))

    students: list[dict[str, Any]] = []
    for position, slot_index in enumerate(order, start=1):
        school_id = school_slots[int(slot_index)]
        programs = programs_by_school[school_id]
        program = programs[int(rng.integers(len(programs)))]
        students.append(
            {
                "student_id": f"STU{position:06d}",
                "school": school_names[school_id],
                "department": department_names[program["department_id"]],
                "program": program["name"],
                "batch": batch,
                "semester": semester_indexes[
                    int(rng.integers(len(semester_indexes)))
                ],
            }
        )
    return students
