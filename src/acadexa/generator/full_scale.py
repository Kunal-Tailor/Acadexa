"""Full-scale generation targets and freeze validation (Tasks 14.1 & 14.2).

Task 14.1 freezes the generator configuration for the full target run
WITHOUT changing schema or architecture: the frozen constants below lock
every documented full-scale value (docs/prd.md §7, docs/memory.md,
rules.md §14), and :func:`validate_full_scale_config` reports any drift
so configuration changes require explicit review instead of slipping in
silently.

Task 14.2 records actual full-hierarchy counts via
:func:`record_hierarchy_counts` (six-school target, no scaled-down
development overrides).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from acadexa.config import validate_project_config

MANIFEST_VERSION: str = "1.0.0"
HIERARCHY_MANIFEST_TYPE: str = "full_scale_hierarchy"

# ── Frozen full-scale targets (docs/prd.md §7, docs/memory.md) ──────
# Engineering targets, not measured results. Any change here must be an
# explicit reviewed decision; validate_full_scale_config() enforces that.

FROZEN_SEED: int = 42

FROZEN_TARGET_STUDENTS: int = 12000
FROZEN_SCHOOL_POPULATION: dict[str, int] = {
    "cet": 2600,
    "set": 3000,
    "som": 2400,
    "lad": 2200,
    "sci": 1000,
    "sol": 800,
}
FROZEN_TARGET_COURSES: int = 250
FROZEN_COURSES_PER_STUDENT_PER_SEMESTER: int = 6
FROZEN_TARGET_LMS_EVENTS: int = 70_000_000
FROZEN_LMS_EVENTS_PER_STUDENT_PER_DAY: int = 15
FROZEN_TEACHING_DAYS_PER_YEAR: int = 200

FROZEN_SCHOOL_IDS: tuple[str, ...] = ("cet", "set", "som", "lad", "sci", "sol")
FROZEN_DEPARTMENT_COUNT: int = 18
FROZEN_PROGRAM_COUNT: int = 40

FROZEN_SEMESTER_IDS: tuple[str, ...] = ("S1", "S2", "S3", "S4")
FROZEN_ACADEMIC_YEARS: int = 2
FROZEN_TEACHING_WEEKS_PER_SEMESTER: int = 16

FROZEN_DECLINER_RATE: float = 0.08

FROZEN_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "LOGIN",
        "LOGOUT",
        "VIDEO_VIEW",
        "VIDEO_COMPLETE",
        "PDF_VIEW",
        "RESOURCE_DOWNLOAD",
        "QUIZ_ATTEMPT",
        "ASSIGNMENT_VIEW",
        "ASSIGNMENT_SUBMISSION",
        "COURSE_PAGE_VIEW",
        "FORUM_POST",
    }
)

# Approximate injection rates (docs/memory.md §12); exact injected counts
# go to the injection manifest per run (rules.md §10.2).
FROZEN_INJECTION_RATES: dict[str, float] = {
    "duplicate_lms_events": 0.01,
    "nulls_non_key": 0.015,
    "timestamp_inconsistencies": 0.01,
    "course_id_formatting": 0.005,
    "orphan_records": 0.001,
    "out_of_range_values": 0.001,
}


@dataclass(frozen=True)
class FullScaleMismatch:
    """One frozen-target deviation found during validation."""

    field: str
    expected: Any
    actual: Any


@dataclass
class FullScaleConfigReport:
    """Outcome of validating live configuration against frozen targets."""

    is_frozen: bool
    mismatches: list[FullScaleMismatch] = field(default_factory=list)
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to a JSON-serializable dictionary."""
        return {
            "manifest_version": MANIFEST_VERSION,
            "is_frozen": self.is_frozen,
            "seed": self.seed,
            "mismatches": [
                {"field": m.field, "expected": m.expected, "actual": m.actual}
                for m in self.mismatches
            ],
        }


def _check(
    mismatches: list[FullScaleMismatch], field: str, expected: Any, actual: Any
) -> None:
    """Record a mismatch when ``actual`` differs from the frozen ``expected``."""
    if actual != expected:
        mismatches.append(FullScaleMismatch(field, expected, actual))


def validate_full_scale_config(
    configs: dict[str, Any] | None = None,
) -> FullScaleConfigReport:
    """Validate live project configuration against the frozen full-scale targets.

    Args:
        configs: Validated project configuration. Defaults to
            :func:`validate_project_config` (the actual generation input).

    Returns:
        Report with ``is_frozen`` True only when every frozen target
        matches; otherwise each deviation is listed for explicit review.
    """
    if configs is None:
        configs = validate_project_config()

    mismatches: list[FullScaleMismatch] = []
    generator = configs.get("generator", {})
    scale = generator.get("scale", {})
    behavior = generator.get("behavior", {})

    seed = generator.get("generator", {}).get("seed")
    _check(mismatches, "seed", FROZEN_SEED, seed)

    _check(mismatches, "scale.target_students", FROZEN_TARGET_STUDENTS, scale.get("target_students"))
    _check(mismatches, "scale.school_population", FROZEN_SCHOOL_POPULATION, scale.get("school_population"))
    population = scale.get("school_population", {})
    if isinstance(population, dict):
        _check(
            mismatches,
            "scale.school_population_sum",
            FROZEN_TARGET_STUDENTS,
            sum(population.values()),
        )
    _check(mismatches, "scale.target_courses", FROZEN_TARGET_COURSES, scale.get("target_courses"))
    _check(
        mismatches,
        "scale.courses_per_student_per_semester",
        FROZEN_COURSES_PER_STUDENT_PER_SEMESTER,
        scale.get("courses_per_student_per_semester"),
    )
    _check(mismatches, "scale.target_lms_events", FROZEN_TARGET_LMS_EVENTS, scale.get("target_lms_events"))
    _check(
        mismatches,
        "scale.lms_events_per_student_per_day",
        FROZEN_LMS_EVENTS_PER_STUDENT_PER_DAY,
        scale.get("lms_events_per_student_per_day"),
    )
    _check(
        mismatches,
        "scale.teaching_days_per_academic_year",
        FROZEN_TEACHING_DAYS_PER_YEAR,
        scale.get("teaching_days_per_academic_year"),
    )

    hierarchy = configs.get("hierarchy", {})
    _check(mismatches, "hierarchy.school_ids", sorted(FROZEN_SCHOOL_IDS), sorted(hierarchy.get("schools", {})))
    _check(
        mismatches,
        "hierarchy.department_count",
        FROZEN_DEPARTMENT_COUNT,
        len(hierarchy.get("departments", {})),
    )
    _check(
        mismatches,
        "hierarchy.program_count",
        FROZEN_PROGRAM_COUNT,
        len(hierarchy.get("programs", {})),
    )

    periods = configs.get("academic_periods", {})
    _check(mismatches, "academic_periods.semesters", list(FROZEN_SEMESTER_IDS), sorted(periods.get("semesters", {})))
    _check(
        mismatches,
        "academic_periods.academic_years",
        FROZEN_ACADEMIC_YEARS,
        len(periods.get("academic_years", {})),
    )
    for sem_id in FROZEN_SEMESTER_IDS:
        spec = periods.get("semesters", {}).get(sem_id, {})
        _check(
            mismatches,
            f"academic_periods.{sem_id}.teaching_weeks",
            FROZEN_TEACHING_WEEKS_PER_SEMESTER,
            spec.get("teaching_weeks"),
        )

    _check(
        mismatches,
        "behavior.decliners.rate",
        FROZEN_DECLINER_RATE,
        behavior.get("decliners", {}).get("rate"),
    )
    _check(
        mismatches,
        "generator.data_quality_injection",
        FROZEN_INJECTION_RATES,
        {
            key: generator.get("data_quality_injection", {}).get(key)
            for key in FROZEN_INJECTION_RATES
        },
    )

    return FullScaleConfigReport(
        is_frozen=not mismatches, mismatches=mismatches, seed=seed
    )


def build_hierarchy_counts(hierarchy: Any) -> dict[str, Any]:
    """Compute actual hierarchy counts from a generated hierarchy (pure).

    Args:
        hierarchy: ``UniversityHierarchy`` with ``schools``, ``departments``,
            ``programs`` and ``courses`` record lists.

    Returns:
        Counts plus a per-school breakdown (department/program/course counts
        resolved through hierarchy references).
    """
    departments = list(hierarchy.departments)
    programs = list(hierarchy.programs)
    courses = list(hierarchy.courses)
    dept_school = {d["id"]: d.get("school_id") for d in departments}
    prog_dept = {p["id"]: p.get("department_id") for p in programs}

    dept_names = {d["id"]: d.get("name") for d in departments}
    school_names = {s["id"]: s.get("name") for s in hierarchy.schools}
    course_school_ids: dict[str, str | None] = {}
    for course in courses:
        dept_name = course.get("department")
        dept_id = next(
            (did for did, name in dept_names.items() if name == dept_name), None
        )
        course_school_ids[course.get("course_id")] = (
            dept_school.get(dept_id) if dept_id else None
        )

    schools = []
    for school in hierarchy.schools:
        sid = school.get("id")
        school_depts = [d for d in departments if d.get("school_id") == sid]
        school_dept_ids = {d["id"] for d in school_depts}
        school_progs = [p for p in programs if p.get("department_id") in school_dept_ids]
        school_courses = [
            c for c in courses if course_school_ids.get(c.get("course_id")) == sid
        ]
        schools.append(
            {
                "id": sid,
                "code": school.get("code"),
                "name": school.get("name"),
                "departments": len(school_depts),
                "programs": len(school_progs),
                "courses": len(school_courses),
            }
        )

    return {
        "schools": len(list(hierarchy.schools)),
        "departments": len(departments),
        "programs": len(programs),
        "courses": len(courses),
        "school_ids": sorted(s.get("id") for s in hierarchy.schools),
        "by_school": sorted(schools, key=lambda s: s["id"] or ""),
        "catalog_target_courses": FROZEN_TARGET_COURSES,
        "school_names": school_names,
    }


def record_hierarchy_counts(
    hierarchy: Any,
    *,
    seed: int,
    output_path: str | Path,
) -> Path:
    """Record actual full-hierarchy counts to a manifest JSON file (14.2).

    Args:
        hierarchy: Generated full-target ``UniversityHierarchy``.
        seed: Generator seed used for the run.
        output_path: Destination manifest file path.

    Returns:
        Resolved output path written to.
    """
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "manifest_type": HIERARCHY_MANIFEST_TYPE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "note": (
            "Actual full-target hierarchy counts (Task 14.2). Targets are "
            "engineering values from the frozen configuration (Task 14.1); "
            "the course catalog is the configured initial catalog, smaller "
            "than the 250-course full target."
        ),
        "actual_counts": build_hierarchy_counts(hierarchy),
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target
