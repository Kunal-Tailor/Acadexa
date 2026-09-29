"""Centralized role and scope resolution (Task 11.3, rules.md §25).

The single canonical place where an authenticated user becomes an allowed
analytical scope and a capability set:

```text
authenticated user
        ↓
role
        ↓
scope
        ↓
allowed capabilities
```

Dashboard pages must call :func:`can` / :func:`resolve_scope` /
:func:`build_mongo_scope_filter` instead of duplicating permission
conditions. Streamlit-free so the logic is unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from acadexa.dashboard.auth import (
    APPROVED_ROLES,
    ROLE_ANALYST,
    ROLE_FACULTY,
    ROLE_SCHOOL_ADMIN,
    ROLE_UNIVERSITY_ADMIN,
    User,
)

# Dashboard capabilities (features.md §20: Feature-to-User Mapping).
CAP_VIEW_UNIVERSITY: str = "view_university"
CAP_VIEW_SCHOOL: str = "view_school"
CAP_VIEW_DEPARTMENT: str = "view_department"
CAP_VIEW_COURSE: str = "view_course"
CAP_VIEW_STUDENT: str = "view_student"
CAP_VIEW_ANALYSIS: str = "view_analysis"
CAP_VIEW_QUALITY: str = "view_quality"
CAP_VIEW_BENCHMARKS: str = "view_benchmarks"

ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    ROLE_UNIVERSITY_ADMIN: frozenset(
        {
            CAP_VIEW_UNIVERSITY,
            CAP_VIEW_SCHOOL,
            CAP_VIEW_DEPARTMENT,
            CAP_VIEW_COURSE,
            CAP_VIEW_STUDENT,
            CAP_VIEW_ANALYSIS,
            CAP_VIEW_QUALITY,
            CAP_VIEW_BENCHMARKS,
        }
    ),
    ROLE_SCHOOL_ADMIN: frozenset(
        {
            CAP_VIEW_SCHOOL,
            CAP_VIEW_DEPARTMENT,
            CAP_VIEW_COURSE,
            CAP_VIEW_STUDENT,
            CAP_VIEW_ANALYSIS,
            CAP_VIEW_QUALITY,
        }
    ),
    ROLE_FACULTY: frozenset(
        {
            CAP_VIEW_COURSE,
            CAP_VIEW_STUDENT,
            CAP_VIEW_ANALYSIS,
        }
    ),
    ROLE_ANALYST: frozenset(
        {
            CAP_VIEW_UNIVERSITY,
            CAP_VIEW_SCHOOL,
            CAP_VIEW_ANALYSIS,
            CAP_VIEW_QUALITY,
            CAP_VIEW_BENCHMARKS,
        }
    ),
}


@dataclass(frozen=True)
class Scope:
    """Allowed analytical scope resolved from an authenticated user."""

    level: str  # "university" | "school" | "department" | "courses"
    school: str | None = None
    department: str | None = None
    courses: tuple[str, ...] = ()


def resolve_scope(user: User) -> Scope:
    """Resolve the analytical scope for ``user`` from role + assignments.

    - University Admin / Academic Analyst → university-wide scope.
    - School / Department Admin → their school (and department when set).
    - Faculty → their assigned courses.
    """
    if user.role in (ROLE_UNIVERSITY_ADMIN, ROLE_ANALYST):
        return Scope(level="university")
    if user.role == ROLE_SCHOOL_ADMIN:
        if user.department:
            return Scope(
                level="department", school=user.school, department=user.department
            )
        return Scope(level="school", school=user.school)
    if user.role == ROLE_FACULTY:
        return Scope(
            level="courses",
            school=user.school,
            department=user.department,
            courses=tuple(user.courses),
        )
    raise ValueError(f"Cannot resolve scope for unapproved role {user.role!r}")


def capabilities_for(role: str) -> frozenset[str]:
    """Return the capability set for ``role`` (empty when unapproved)."""
    return ROLE_CAPABILITIES.get(role, frozenset())


def can(user: User, capability: str) -> bool:
    """Return True when ``user`` is allowed ``capability``."""
    return capability in capabilities_for(user.role)


def build_mongo_scope_filter(
    scope: Scope,
    *,
    school_field: str = "school",
    course_field: str = "course_id",
) -> dict[str, Any]:
    """Build a MongoDB query filter expressing ``scope``.

    University scope matches everything (``{}``); school/department scopes
    match their hierarchy fields; course scopes match the assigned courses.
    """
    if scope.level == "university":
        return {}
    if scope.level == "school":
        return {school_field: scope.school} if scope.school else {}
    if scope.level == "department":
        filt: dict[str, Any] = {}
        if scope.school:
            filt[school_field] = scope.school
        if scope.department:
            filt["department"] = scope.department
        return filt
    if scope.level == "courses":
        if not scope.courses:
            # No assigned courses: match nothing rather than everything.
            return {"_id": None}
        return {course_field: {"$in": list(scope.courses)}}
    raise ValueError(f"Unknown scope level {scope.level!r}")


def describe_scope(scope: Scope) -> str:
    """Human-readable scope summary for the dashboard sidebar/header."""
    if scope.level == "university":
        return "RAS University (all schools)"
    if scope.level == "school":
        return f"School: {scope.school or 'unassigned'}"
    if scope.level == "department":
        return f"Department: {scope.department or 'unassigned'} ({scope.school or 'unassigned'})"
    if scope.level == "courses":
        if not scope.courses:
            return "Courses: none assigned"
        return f"Courses: {', '.join(scope.courses)}"
    return "Unknown scope"


__all__ = [
    "APPROVED_ROLES",
    "CAP_VIEW_ANALYSIS",
    "CAP_VIEW_BENCHMARKS",
    "CAP_VIEW_COURSE",
    "CAP_VIEW_DEPARTMENT",
    "CAP_VIEW_QUALITY",
    "CAP_VIEW_SCHOOL",
    "CAP_VIEW_STUDENT",
    "CAP_VIEW_UNIVERSITY",
    "ROLE_CAPABILITIES",
    "Scope",
    "build_mongo_scope_filter",
    "can",
    "capabilities_for",
    "describe_scope",
    "resolve_scope",
]
