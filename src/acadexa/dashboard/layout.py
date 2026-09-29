"""Shared dashboard layout, navigation and global filters (Task 11.4).

Implements docs/design.md §7–§11: a consistent page structure (sidebar
navigation + page header + context/filters + content), role-gated
navigation over analytical concepts (never Spark internals), scope-aware
global academic filters, and hierarchy breadcrumbs.

The navigation model, breadcrumb builder and filter descriptors are pure
(Streamlit-free) so pages share one implementation and unit tests do not
need a UI runtime. Only the ``render_*`` helpers require Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from acadexa.config.loader import config_path, load_config_file
from acadexa.dashboard.auth import User
from acadexa.dashboard.permissions import (
    CAP_VIEW_ANALYSIS,
    CAP_VIEW_COURSE,
    CAP_VIEW_QUALITY,
    CAP_VIEW_SCHOOL,
    CAP_VIEW_STUDENT,
    CAP_VIEW_UNIVERSITY,
    Scope,
    can,
    describe_scope,
    resolve_scope,
)

NAV_SESSION_KEY: str = "acadexa_nav_page"
FILTER_SESSION_PREFIX: str = "acadexa_filter_"

UNIVERSITY_CRUMB: str = "RAS University"

# Global academic filter fields in display order (design.md §10).
FILTER_FIELDS: tuple[str, ...] = (
    "academic_year",
    "semester",
    "school",
    "department",
    "program",
    "course",
)

FILTER_LABELS: dict[str, str] = {
    "academic_year": "Academic year",
    "semester": "Semester",
    "school": "School",
    "department": "Department",
    "program": "Program",
    "course": "Course",
}

DEFAULT_ACADEMIC_PERIODS_PATH: Path = config_path(
    "university", "academic_periods.toml"
)


@dataclass(frozen=True)
class NavItem:
    """One analytical navigation destination (design.md §8)."""

    key: str
    title: str
    required_capabilities: frozenset[str]


# Primary navigation over analytical concepts, in design.md §8 order.
NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("overview", "Overview", frozenset({CAP_VIEW_UNIVERSITY, CAP_VIEW_SCHOOL})),
    NavItem("schools", "Schools", frozenset({CAP_VIEW_SCHOOL})),
    NavItem("courses", "Courses", frozenset({CAP_VIEW_COURSE})),
    NavItem("students", "Students", frozenset({CAP_VIEW_STUDENT})),
    NavItem("analysis", "Analysis", frozenset({CAP_VIEW_ANALYSIS})),
    NavItem("data_quality", "Data Quality", frozenset({CAP_VIEW_QUALITY})),
)


def visible_nav_items(user: User) -> tuple[NavItem, ...]:
    """Return navigation items ``user`` may see (any required capability)."""
    return tuple(
        item
        for item in NAV_ITEMS
        if any(can(user, cap) for cap in item.required_capabilities)
    )


def default_nav_key(user: User) -> str:
    """First visible navigation key, or ``overview`` when nothing is visible."""
    visible = visible_nav_items(user)
    return visible[0].key if visible else "overview"


def nav_title(page_key: str) -> str:
    """Display title for a navigation key (falls back to the raw key)."""
    for item in NAV_ITEMS:
        if item.key == page_key:
            return item.title
    return page_key


def build_breadcrumbs(page_title: str, scope: Scope) -> list[str]:
    """Build hierarchy crumbs: university › school › department › page.

    Course-scoped users see their assigned courses as the finest crumb.
    """
    crumbs = [UNIVERSITY_CRUMB]
    if scope.level in ("school", "department", "courses") and scope.school:
        crumbs.append(scope.school)
    if scope.level == "department" and scope.department:
        crumbs.append(scope.department)
    if scope.level == "courses":
        if scope.courses:
            crumbs.append(f"Courses: {', '.join(scope.courses)}")
        else:
            crumbs.append("Courses: none assigned")
    crumbs.append(page_title)
    return crumbs


def format_breadcrumbs(crumbs: list[str]) -> str:
    """Render crumbs with the design.md §11 separator."""
    return " › ".join(crumbs)


def load_academic_periods(
    path: Path | str | None = None,
) -> dict[str, list[str]]:
    """Load academic-year labels and semester IDs from tracked config.

    Returns ``{"academic_years": [...], "semesters": [...]}``.
    """
    target = Path(path) if path is not None else DEFAULT_ACADEMIC_PERIODS_PATH
    data = load_config_file(target)
    years = data.get("academic_years", {})
    semesters = data.get("semesters", {})
    return {
        "academic_years": [years[k]["label"] for k in sorted(years)],
        "semesters": sorted(semesters),
    }


def visible_filters(scope: Scope) -> tuple[str, ...]:
    """Filter fields applicable to ``scope`` (design.md §10).

    Scope-fixed fields are excluded because the user cannot change them;
    faculty additionally see no course picker (their courses are fixed).
    """
    if scope.level == "university":
        return FILTER_FIELDS
    if scope.level == "school":
        return tuple(f for f in FILTER_FIELDS if f != "school")
    if scope.level == "department":
        return tuple(f for f in FILTER_FIELDS if f not in ("school", "department"))
    if scope.level == "courses":
        return ("academic_year", "semester")
    raise ValueError(f"Unknown scope level {scope.level!r}")


def default_filters(scope: Scope) -> dict[str, str | None]:
    """Default filter values for ``scope`` (None = unrestricted "All").

    Scope-fixed dimensions are not user-selectable, so they never appear
    here. Hierarchy options below school/department (program, course) are
    populated from serving data in Phase 12, so they default to None here.
    """
    return {field: None for field in visible_filters(scope)}


def filter_options(
    field: str,
    scope: Scope,
    academic_periods: Mapping[str, list[str]] | None = None,
) -> list[str]:
    """Selectable options for ``field`` ("All" first when unrestricted).

    Academic year/semester options come from tracked configuration;
    hierarchy options come from serving data in Phase 12 and currently
    offer only "All" (or the single scope-fixed value).
    """
    if field not in FILTER_FIELDS:
        raise ValueError(f"Unknown filter field {field!r}")
    periods = academic_periods or {}
    if field == "academic_year":
        return ["All", *periods.get("academic_years", [])]
    if field == "semester":
        return ["All", *periods.get("semesters", [])]
    if field == "school" and scope.level in ("school", "department") and scope.school:
        return [scope.school]
    if field == "course" and scope.level == "courses":
        return list(scope.courses) if scope.courses else []
    return ["All"]


def academic_context_label(filters: Mapping[str, str | None]) -> str:
    """Compact "AY · Semester" context label for the page header."""
    year = filters.get("academic_year") or "All years"
    semester = filters.get("semester") or "All semesters"
    return f"{year} · {semester}"


# ── Streamlit render helpers ─────────────────────────────────────────


def read_filter_selections(scope: Scope) -> dict[str, str | None]:
    """Read current global-filter values from session state (None = All).

    Used for the page-header context line before the filter widgets render;
    widget changes trigger a rerun that refreshes the header.
    """
    selections: dict[str, str | None] = {}
    for field in visible_filters(scope):
        picked = st.session_state.get(f"{FILTER_SESSION_PREFIX}{field}", "All")
        selections[field] = None if picked in (None, "All") else picked
    return selections


def render_sidebar_nav(user: User) -> str:
    """Render role-gated sidebar navigation; return the selected page key."""
    visible = visible_nav_items(user)
    titles = [item.title for item in visible]
    keys = [item.key for item in visible]
    current = st.session_state.get(NAV_SESSION_KEY, default_nav_key(user))
    if current not in keys:
        current = default_nav_key(user)
    with st.sidebar:
        st.markdown(f"**{user.display_name}**")
        st.caption(user.role)
        st.caption(describe_scope(resolve_scope(user)))
        choice = st.radio("Navigate", titles, index=keys.index(current), key="acadexa_nav_radio")
    selected = keys[titles.index(choice)]
    st.session_state[NAV_SESSION_KEY] = selected
    return selected


def render_header(
    page_title: str,
    user: User,
    academic_context: str,
) -> None:
    """Render the page header: identity, page, academic context (design §9)."""
    st.title("Acadexa — Academic Intelligence")
    st.caption(f"RAS University · {academic_context} · {user.display_name} ({user.role})")
    st.header(page_title)


def render_breadcrumbs(crumbs: list[str]) -> None:
    """Render hierarchy context crumbs (design.md §11)."""
    st.caption(format_breadcrumbs(crumbs))


def render_global_filters(scope: Scope) -> dict[str, str | None]:
    """Render scope-aware global filters; return field → selection (None = All)."""
    try:
        periods = load_academic_periods()
    except (FileNotFoundError, ValueError):
        periods = {"academic_years": [], "semesters": []}
    fields = visible_filters(scope)
    selections: dict[str, str | None] = {}
    if not fields:
        return selections
    columns = st.columns(len(fields))
    for column, field in zip(columns, fields):
        with column:
            options = filter_options(field, scope, periods)
            if not options:
                selections[field] = None
                continue
            session_key = f"{FILTER_SESSION_PREFIX}{field}"
            default = st.session_state.get(session_key, options[0])
            index = options.index(default) if default in options else 0
            picked = st.selectbox(
                FILTER_LABELS[field], options, index=index, key=session_key
            )
            selections[field] = None if picked == "All" else picked
    return selections
