"""School/Department views (Task 12.2, docs/design.md §15–§16, features.md F-E02/F-E03).

Scoped analytics for one school at a time: scoped KPIs (population,
marks, attendance, engagement, coursework behavior), department
breakdown, course breakdown, trends and risk distribution. Selecting a
department narrows every section to department level (design.md §16).

Built only from actual gold data. Aggregation math is reused from the
University Overview (:func:`compute_university_summary`) so scoped KPIs,
trends and risk distribution share one canonical implementation; this
module adds school selection, department narrowing and the
department/course breakdowns.

Structure mirrors the University Overview page:

- :func:`fetch_school_data` — bounded, scope-aware MongoDB reads.
- :func:`available_schools` / :func:`resolve_selected_school` — pure
  school-picker model over real summary rows.
- :func:`render_school_page` — Streamlit rendering with shared components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from acadexa.dashboard import components, layout
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.pages.university import (
    UniversitySummary,
    compute_university_summary,
)
from acadexa.dashboard.permissions import Scope, build_mongo_scope_filter

SCHOOL_PICKER_SESSION_KEY: str = "acadexa_school_picker"


@dataclass(frozen=True)
class DepartmentRow:
    """One department breakdown row at school grain."""

    department: str
    student_count: int
    course_count: int
    avg_performance: float | None
    avg_attendance: float | None
    engagement_count: int


@dataclass(frozen=True)
class CourseRow:
    """One course breakdown row at school/department grain."""

    course_id: str
    course_title: str | None
    avg_performance: float | None
    avg_attendance: float | None
    engagement_count: int | None
    enrolled_students_count: int | None
    difficulty_adjusted_performance: float | None


def available_schools(school_summary: list[dict[str, Any]]) -> list[str]:
    """Sorted school names present in ``school_summary`` rows."""
    return sorted({str(d["school"]) for d in school_summary if d.get("school")})


def resolve_selected_school(
    available: list[str], requested: str | None
) -> str | None:
    """Validate a school picker selection (None when nothing is available)."""
    if not available:
        return None
    if requested in available:
        return requested
    return available[0]


def _department_rows(school_summary: list[dict[str, Any]]) -> tuple[DepartmentRow, ...]:
    """Pass department-grain summary rows through in sorted order."""
    rows = [
        DepartmentRow(
            department=str(d.get("department")),
            student_count=int(d.get("student_count") or 0),
            course_count=int(d.get("course_count") or 0),
            avg_performance=float(d["avg_performance"])
            if d.get("avg_performance") is not None
            else None,
            avg_attendance=float(d["avg_attendance"])
            if d.get("avg_attendance") is not None
            else None,
            engagement_count=int(d.get("engagement_count") or 0),
        )
        for d in school_summary
        if d.get("department")
    ]
    return tuple(sorted(rows, key=lambda r: r.department))


def _course_rows(course_metrics: list[dict[str, Any]]) -> tuple[CourseRow, ...]:
    """Pass course-grain metric rows through in sorted order."""
    rows = [
        CourseRow(
            course_id=str(d.get("course_id")),
            course_title=d.get("course_title"),
            avg_performance=float(d["avg_performance"])
            if d.get("avg_performance") is not None
            else None,
            avg_attendance=float(d["avg_attendance"])
            if d.get("avg_attendance") is not None
            else None,
            engagement_count=int(d["engagement_count"])
            if d.get("engagement_count") is not None
            else None,
            enrolled_students_count=int(d["enrolled_students_count"])
            if d.get("enrolled_students_count") is not None
            else None,
            difficulty_adjusted_performance=float(d["difficulty_adjusted_performance"])
            if d.get("difficulty_adjusted_performance") is not None
            else None,
        )
        for d in course_metrics
        if d.get("course_id")
    ]
    return tuple(sorted(rows, key=lambda r: r.course_id))


def fetch_school_data(
    access: DashboardDataAccess,
    scope: Scope,
    semester: str | None,
    school: str,
    department: str | None,
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    """Fetch school-scoped gold records for the Schools page.

    ``school`` is intersected with ``scope`` so the page can never escape
    the user's allowed scope; ``department`` narrows every section to
    department level when set. The semester filter applies only to
    semester-grained collections. ``risk_indicators`` carry no hierarchy
    fields, so they are restricted in Python to the scoped students.
    Returns ``(records, error)`` following the data-access failure
    contract: any failure yields a controlled error and no fabricated
    values.
    """
    if scope.level == "university":
        pass
    elif scope.level in ("school", "department") and scope.school == school:
        if (
            scope.level == "department"
            and scope.department
            and department
            and department != scope.department
        ):
            return {}, (
                f"Department {department!r} is outside the allowed scope "
                f"({scope.department!r})."
            )
        if scope.level == "department" and scope.department:
            department = scope.department
    elif scope.level in ("school", "department"):
        return {}, f"School {school!r} is outside the allowed scope."
    else:
        return {}, "This view is unavailable for the current scope."
    base = Scope(level="school", school=school)

    student_filter = build_mongo_scope_filter(
        base, school_field="student_school", department_field="student_department"
    )
    course_filter = build_mongo_scope_filter(base, school_field="school")
    school_filter = build_mongo_scope_filter(base, school_field="school")
    if department:
        student_filter = {**student_filter, "student_department": department}
        course_filter = {**course_filter, "department": department}
        school_filter = {**school_filter, "department": department}
    if semester:
        student_filter = {**student_filter, "semester_id": semester}
        course_filter = {**course_filter, "semester_id": semester}

    records: dict[str, list[dict[str, Any]]] = {}
    for collection, query in (
        ("student_features", student_filter),
        ("course_metrics", course_filter),
        ("school_summary", school_filter),
    ):
        docs, error = access.fetch(collection, query)
        if error is not None:
            return {}, error
        records[collection] = docs

    risk_docs, error = access.fetch("risk_indicators", {})
    if error is not None:
        return {}, error
    scoped_students = {str(d.get("student_id")) for d in records["student_features"]}
    records["risk_indicators"] = [
        d for d in risk_docs if str(d.get("student_id")) in scoped_students
    ]
    return records, None


def _scoped_kpi_row(summary: UniversitySummary, context: str) -> None:
    """Render the scoped KPI cards (population, marks, attendance, engagement)."""
    columns = st.columns(6)
    kpis = (
        ("Students", summary.student_count, "students"),
        ("Courses", summary.course_count, "courses"),
        ("Average Attendance", summary.avg_attendance, "percent"),
        ("Average Performance", summary.avg_performance, "/ 100"),
        ("Average Engagement", summary.avg_engagement, "events"),
        ("Students With Risk Signals", summary.students_with_signals, "students"),
    )
    for column, (label, value, unit) in zip(columns, kpis):
        with column:
            components.kpi_card(label, value, unit=unit, context=context)


def _department_breakdown(departments: tuple[DepartmentRow, ...]) -> None:
    """Render the department comparison table (no best-department score)."""
    if not departments:
        components.empty_state("No department data is available for this selection.")
        return

    def _body() -> None:
        st.dataframe(
            [
                {
                    "Department": row.department,
                    "Students": row.student_count,
                    "Courses": row.course_count,
                    "Avg performance": row.avg_performance,
                    "Avg attendance": row.avg_attendance,
                    "LMS events": row.engagement_count,
                }
                for row in departments
            ]
        )

    components.analytical_card(
        "Department breakdown",
        "Department roll-ups within the selected school. No composite ranking is shown.",
        method="School × department gold roll-ups",
        render_body=_body,
    )


def _course_breakdown(courses: tuple[CourseRow, ...]) -> None:
    """Render course comparisons with difficulty-adjusted performance."""
    if not courses:
        components.empty_state("No course data is available for this selection.")
        return

    def _body() -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [
                {"Course": row.course_id, "Avg performance": row.avg_performance}
                for row in courses
                if row.avg_performance is not None
            ]
        )
        if not frame.empty:
            st.bar_chart(frame, x="Course", y="Avg performance")
        st.dataframe(
            [
                {
                    "Course": row.course_id,
                    "Title": row.course_title or "—",
                    "Avg performance": row.avg_performance,
                    "Avg attendance": row.avg_attendance,
                    "LMS events": row.engagement_count,
                    "Enrolled": row.enrolled_students_count,
                    "Difficulty-adj. perf.": row.difficulty_adjusted_performance,
                }
                for row in courses
            ]
        )

    components.analytical_card(
        "Course breakdown",
        "Course performance, attendance, engagement and difficulty-adjusted "
        "performance. Observed association only.",
        method="Course × semester gold metrics; association, not causation",
        render_body=_body,
    )


def _coursework_section(student_features: list[dict[str, Any]]) -> None:
    """Render coursework behavior from late-submission rates in gold data."""
    rates = [
        float(d["late_submission_rate"])
        for d in student_features
        if d.get("late_submission_rate") is not None
    ]
    if not rates:
        components.empty_state("No coursework data is available for this selection.")
        return
    mean_rate = round(sum(rates) / len(rates) * 100, 1)

    def _body() -> None:
        st.caption(
            f"Mean late-submission rate {mean_rate}% across {len(rates)} students "
            f"(fraction of assignments submitted late)."
        )

    components.analytical_card(
        "Coursework behavior",
        "Late-submission behavior observed in gold feature data.",
        method="Mean of per-student late-submission rates",
        render_body=_body,
    )


def _trend_section(summary: UniversitySummary) -> None:
    """Render the scoped observed score-trend summary."""
    trend = summary.trend
    if trend is None:
        components.empty_state("No trend data is available for this selection.")
        return

    def _body() -> None:
        st.caption(
            f"{trend.declining} declining · {trend.improving} improving · "
            f"{trend.stable} stable (recent-minus-earlier graded-item average, points)"
        )

    components.analytical_card(
        "Trend indicators",
        f"Mean score trend {components.format_value(trend.mean_score_trend, 'pts')} "
        f"across {trend.student_count} students.",
        method="Recent-minus-earlier graded-item average; association, not causation",
        render_body=_body,
    )


def _risk_section(summary: UniversitySummary) -> None:
    """Render the scoped risk-signal distribution (counts, never predictions)."""
    risk = summary.risk
    if risk is None or risk.assessed == 0:
        components.empty_state("No risk signals were detected for the selected scope.")
        return
    st.markdown(f"**{risk.flagged} of {risk.assessed} students show observed signals**")
    st.bar_chart(
        {"Signal count": list(risk.distribution.keys()), "Students": list(risk.distribution.values())},
        x="Signal count",
        y="Students",
    )
    for key in components.RISK_SIGNAL_KEYS:
        st.caption(
            f"{components.RISK_SIGNAL_LABELS[key]} — triggered for "
            f"{risk.signal_triggers.get(key, 0)} students"
        )
    st.caption(
        "Risk indicator = count of five predefined observed signals. "
        "It is not a failure prediction model."
    )


def _resolve_picker_school(scope: Scope, access: DashboardDataAccess) -> tuple[str | None, str | None]:
    """Return ``(school, error)`` for the Schools page picker.

    University scope offers every school in gold data; school/department
    scopes fix the school without a picker.
    """
    if scope.level in ("school", "department"):
        if not scope.school:
            return None, "No school is assigned to the current scope."
        return scope.school, None
    rows, error = access.fetch("school_summary", {})
    if error is not None:
        return None, error
    options = available_schools(rows)
    if not options:
        return None, None
    stored = st.session_state.get(SCHOOL_PICKER_SESSION_KEY, options[0])
    selected = resolve_selected_school(options, stored if isinstance(stored, str) else None)
    assert selected is not None
    choice = st.selectbox("School", options, index=options.index(selected), key=SCHOOL_PICKER_SESSION_KEY)
    return choice, None


def render_school_page(
    scope: Scope,
    filters: Mapping[str, str | None],
    access: DashboardDataAccess,
) -> None:
    """Render the School/Department views from actual gold data."""
    school, error = _resolve_picker_school(scope, access)
    if error is not None:
        components.error_state(
            "Unable to load school view.",
            "The analytical data service is currently unavailable. "
            "Please check the database connection and try again.",
        )
        return
    if school is None:
        components.empty_state("No school data is available for this selection.")
        return

    department = (filters or {}).get("department")
    records, error = fetch_school_data(
        access, scope, (filters or {}).get("semester"), school, department
    )
    if error is not None:
        if "outside the allowed scope" in error or "unavailable for the current scope" in error:
            components.error_state("Selection outside allowed scope.", error)
        else:
            components.error_state(
                "Unable to load school view.",
                "The analytical data service is currently unavailable. "
                "Please check the database connection and try again.",
            )
        return

    summary = compute_university_summary(
        records["student_features"],
        records["course_metrics"],
        records["school_summary"],
        records["risk_indicators"],
    )
    context = layout.academic_context_label(filters or {})
    if (filters or {}).get("semester"):
        context += " (department and risk summaries aggregate all semesters in scope)"
    if department:
        st.subheader(f"Department: {department}")
    else:
        st.subheader(f"School: {school}")

    st.subheader("Scoped KPIs")
    _scoped_kpi_row(summary, context)

    st.subheader("Coursework behavior")
    _coursework_section(records["student_features"])

    if not department:
        st.subheader("Department breakdown")
        _department_breakdown(_department_rows(records["school_summary"]))

    st.subheader("Course breakdown")
    _course_breakdown(_course_rows(records["course_metrics"]))

    st.subheader("Trend indicators")
    _trend_section(summary)

    st.subheader("Risk distribution")
    _risk_section(summary)
