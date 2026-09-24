"""University hierarchy generation from configuration (F-B01).

Builds schools, departments, programs and the course catalogue from
the validated project configuration. Generation is configuration-
driven per rules.md §8.3: adding a school, department, program or
course to the configuration appears in the output without code
changes.

The step is deterministic — it applies no randomness — so identical
configuration always yields identical output.

Course records carry the hierarchy-resolvable COURSES_SCHEMA fields
(``course_id``, ``title``, ``school``, ``department``).
``semester_applicability`` and ``difficulty`` metadata are produced
by later tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from acadexa.config import validate_project_config
from acadexa.generator.foundation import GeneratorError


@dataclass(frozen=True)
class UniversityHierarchy:
    """Generated hierarchy: university, schools, departments, programs, courses."""

    university: dict[str, Any]
    schools: tuple[dict[str, Any], ...]
    departments: tuple[dict[str, Any], ...]
    programs: tuple[dict[str, Any], ...]
    courses: tuple[dict[str, Any], ...]


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def generate_university_hierarchy(
    configs: dict[str, Any] | None = None,
) -> UniversityHierarchy:
    """Generate the university hierarchy and course catalogue from configuration.

    Args:
        configs: Project configuration mapping containing at least
            ``hierarchy`` and ``courses`` (the result of
            :func:`validate_project_config`). When omitted, the
            project configuration is loaded and validated.

    Raises:
        GeneratorError: if required configuration sections are
            missing or a reference points to an unknown entity.
    """
    if configs is None:
        configs = validate_project_config()
    _check(
        isinstance(configs, dict),
        "configs must be a mapping from validate_project_config()",
    )
    _check("hierarchy" in configs, "configs missing 'hierarchy' configuration")
    _check("courses" in configs, "configs missing 'courses' configuration")

    hierarchy = configs["hierarchy"]
    for key in ("university", "schools", "departments", "programs"):
        _check(key in hierarchy, f"hierarchy configuration missing '{key}'")

    schools = tuple(
        {"id": school_id, "code": spec["code"], "name": spec["name"]}
        for school_id, spec in hierarchy["schools"].items()
    )
    school_names = {school["id"]: school["name"] for school in schools}

    departments: list[dict[str, Any]] = []
    department_names: dict[str, str] = {}
    department_school: dict[str, str] = {}
    for department_id, spec in hierarchy["departments"].items():
        _check(
            spec["school"] in school_names,
            f"department '{department_id}': unknown school '{spec['school']}'",
        )
        record = {
            "id": department_id,
            "code": spec["code"],
            "name": spec["name"],
            "school_id": spec["school"],
        }
        departments.append(record)
        department_names[department_id] = record["name"]
        department_school[department_id] = record["school_id"]

    programs: list[dict[str, Any]] = []
    for program_id, spec in hierarchy["programs"].items():
        _check(
            spec["department"] in department_names,
            f"program '{program_id}': unknown department '{spec['department']}'",
        )
        programs.append(
            {
                "id": program_id,
                "degree": spec["degree"],
                "name": spec["name"],
                "department_id": spec["department"],
            }
        )

    courses: list[dict[str, Any]] = []
    for course_id, spec in configs["courses"]["courses"].items():
        department_id = spec["department"]
        _check(
            department_id in department_names,
            f"course '{course_id}': unknown department '{department_id}'",
        )
        courses.append(
            {
                "course_id": course_id,
                "title": spec["title"],
                "school": school_names[department_school[department_id]],
                "department": department_names[department_id],
            }
        )

    return UniversityHierarchy(
        university=dict(hierarchy["university"]),
        schools=schools,
        departments=tuple(departments),
        programs=tuple(programs),
        courses=tuple(courses),
    )
