"""Course view (Task 12.3, docs/design.md §17, features.md F-E05).

Per-course analytics from actual gold and serving data: course metadata,
enrollment, average marks, attendance, coursework performance, LMS
engagement, late submissions, trend and relevant association information.
Cross-factor comparisons are presented as observed association only —
never as causation (rules.md §20).

Structure mirrors the earlier pages:

- :func:`fetch_course_data` — bounded, scope-aware reads (gold metrics,
  catalogue metadata, coursework items, enrollment records; student
  feature/risk rows joined in Python via enrollment).
- :func:`compute_course_summary` — pure aggregation over record lists.
- :func:`render_course_page` — Streamlit rendering with shared components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from acadexa.dashboard import components, layout
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.permissions import Scope, build_mongo_scope_filter

COURSE_PICKER_SESSION_KEY: str = "acadexa_course_picker"


@dataclass(frozen=True)
class CourseworkSummary:
    """Observed coursework behavior for one course."""

    items: int
    submitted: int
    late: int
    late_rate_pct: float | None
    avg_score_pct: float | None
    quizzes: int
    assignments: int


@dataclass(frozen=True)
class CourseTrendSummary:
    """Observed score-trend mix of enrolled students (points)."""

    student_count: int
    mean_score_trend: float | None
    declining: int
    improving: int
    stable: int


@dataclass(frozen=True)
class CourseSummary:
    """Aggregated Course view content (None = data unavailable)."""

    course_id: str
    course_title: str | None
    school: str | None
    department: str | None
    difficulty_level: str | None
    enrollment: int | None
    avg_performance: float | None
    avg_attendance: float | None
    engagement_count: int | None
    difficulty_adjusted_performance: float | None
    school_avg_performance: float | None
    school_avg_attendance: float | None
    coursework: CourseworkSummary | None
    trend: CourseTrendSummary | None
    students_with_signals: int | None
    students_assessed: int | None


def available_courses(course_metrics: list[dict[str, Any]]) -> list[str]:
    """Sorted course IDs present in ``course_metrics`` rows."""
    return sorted({str(d["course_id"]) for d in course_metrics if d.get("course_id")})


def resolve_selected_course(
    available: list[str], requested: str | None
) -> str | None:
    """Validate a course picker selection (None when nothing is available)."""
    if not available:
        return None
    if requested in available:
        return requested
    return available[0]


def _mean(values: list[float]) -> float | None:
    """Rounded mean of ``values`` (None when empty)."""
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _summarize_coursework(coursework: list[dict[str, Any]]) -> CourseworkSummary | None:
    """Aggregate coursework items (None when no items)."""
    if not coursework:
        return None
    submitted = [d for d in coursework if d.get("submitted_at") is not None]
    late = [d for d in submitted if d.get("status") == "LATE"]
    scored = [
        float(d["score"]) / float(d["max_score"]) * 100.0
        for d in coursework
        if d.get("score") is not None
        and d.get("max_score") not in (None, 0)
    ]
    return CourseworkSummary(
        items=len(coursework),
        submitted=len(submitted),
        late=len(late),
        late_rate_pct=round(len(late) / len(submitted) * 100, 1) if submitted else None,
        avg_score_pct=round(sum(scored) / len(scored), 1) if scored else None,
        quizzes=sum(1 for d in coursework if d.get("item_type") == "QUIZ"),
        assignments=sum(1 for d in coursework if d.get("item_type") == "ASSIGNMENT"),
    )


def _summarize_course_trend(student_features: list[dict[str, Any]]) -> CourseTrendSummary | None:
    """Summarize enrolled students' observed score trends (None when absent)."""
    trends = [float(d["score_trend"]) for d in student_features if d.get("score_trend") is not None]
    if not trends:
        return None
    return CourseTrendSummary(
        student_count=len(trends),
        mean_score_trend=_mean(trends),
        declining=sum(1 for v in trends if v < 0),
        improving=sum(1 for v in trends if v > 0),
        stable=sum(1 for v in trends if v == 0),
    )


def compute_course_summary(
    course_id: str,
    course_metrics: list[dict[str, Any]],
    catalogue: list[dict[str, Any]],
    school_summary: list[dict[str, Any]],
    coursework: list[dict[str, Any]],
    student_features: list[dict[str, Any]],
    risk_indicators: list[dict[str, Any]],
) -> CourseSummary:
    """Aggregate course records into Course view content (pure).

    ``course_metrics`` may hold one row per semester; metric KPIs use the
    mean across the selected semesters. Empty inputs yield None KPIs and
    empty sections so the page renders explicit unavailable/empty states.
    """
    rows = [d for d in course_metrics if str(d.get("course_id")) == course_id]
    meta = next((d for d in catalogue if str(d.get("course_id")) == course_id), {})
    school = meta.get("school") or next(
        (d.get("school") for d in rows if d.get("school")), None
    )
    school_rows = [d for d in school_summary if school and d.get("school") == school]

    perfs = [float(d["avg_performance"]) for d in rows if d.get("avg_performance") is not None]
    atts = [float(d["avg_attendance"]) for d in rows if d.get("avg_attendance") is not None]
    engs = [int(d["engagement_count"]) for d in rows if d.get("engagement_count") is not None]
    enrolled_counts = [int(d["enrolled_students_count"]) for d in rows if d.get("enrolled_students_count") is not None]
    adj = [float(d["difficulty_adjusted_performance"]) for d in rows if d.get("difficulty_adjusted_performance") is not None]

    assessed = {str(d.get("student_id")) for d in risk_indicators if d.get("student_id")}
    flagged = sum(1 for d in risk_indicators if int(d.get("signal_count") or 0) >= 1)

    return CourseSummary(
        course_id=course_id,
        course_title=meta.get("title") or next(
            (d.get("course_title") for d in rows if d.get("course_title")), None
        ),
        school=str(school) if school else None,
        department=str(meta.get("department")) if meta.get("department") else next(
            (str(d.get("department")) for d in rows if d.get("department")), None
        ),
        difficulty_level=str(meta["difficulty_level"]) if meta.get("difficulty_level") else None,
        enrollment=max(enrolled_counts) if enrolled_counts else None,
        avg_performance=_mean(perfs),
        avg_attendance=_mean(atts),
        engagement_count=sum(engs) if engs else None,
        difficulty_adjusted_performance=_mean(adj),
        school_avg_performance=_mean(
            [float(d["avg_performance"]) for d in school_rows if d.get("avg_performance") is not None]
        ),
        school_avg_attendance=_mean(
            [float(d["avg_attendance"]) for d in school_rows if d.get("avg_attendance") is not None]
        ),
        coursework=_summarize_coursework(coursework),
        trend=_summarize_course_trend(student_features),
        students_with_signals=flagged if assessed else None,
        students_assessed=len(assessed) if assessed else None,
    )


def fetch_course_data(
    access: DashboardDataAccess,
    scope: Scope,
    semester: str | None,
    course_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    """Fetch course-scoped records for the Course view.

    ``course_id`` is intersected with ``scope`` so the page can never
    escape the allowed scope (faculty see only assigned courses). The
    semester filter applies to semester-grained collections
    (``course_metrics``, ``academic_records``); coursework items carry no
    semester field and aggregate all semesters in scope. Student feature
    and risk rows are restricted in Python to enrolled students resolved
    via ``academic_records``. Returns ``(records, error)`` following the
    data-access failure contract.
    """
    allowed: set[str] = set()
    if scope.level == "university":
        pass
    elif scope.level in ("school", "department"):
        course_filter = build_mongo_scope_filter(scope, school_field="school")
        metrics, error = access.fetch("course_metrics", course_filter)
        if error is not None:
            return {}, error
        allowed = {str(d.get("course_id")) for d in metrics if d.get("course_id")}
        if course_id not in allowed:
            return {}, f"Course {course_id!r} is outside the allowed scope."
    elif scope.level == "courses":
        if not scope.courses or course_id not in scope.courses:
            return {}, f"Course {course_id!r} is outside the allowed scope."
    else:
        return {}, "This view is unavailable for the current scope."

    metric_filter: dict[str, Any] = {"course_id": course_id}
    record_filter: dict[str, Any] = {"course_id": course_id}
    if semester:
        metric_filter = {**metric_filter, "semester_id": semester}
        record_filter = {**record_filter, "semester_id": semester}

    records: dict[str, list[dict[str, Any]]] = {}
    for collection, query in (
        ("course_metrics", metric_filter),
        ("courses", {"course_id": course_id}),
        ("school_summary", build_mongo_scope_filter(scope, school_field="school")),
        ("coursework", {"course_id": course_id}),
        ("academic_records", record_filter),
    ):
        docs, error = access.fetch(collection, query)
        if error is not None:
            return {}, error
        records[collection] = docs

    # academic_records carry no school field, but course_id was already
    # validated against the in-scope course list above, so these IDs are
    # inherently in scope.
    enrolled = {str(d.get("student_id")) for d in records["academic_records"] if d.get("student_id")}
    features, error = access.fetch(
        "student_features",
        {"student_id": {"$in": sorted(enrolled)}} if enrolled else {"_id": None},
    )
    if error is not None:
        return {}, error
    records["student_features"] = [d for d in features if str(d.get("student_id")) in enrolled]

    risk_docs, error = access.fetch("risk_indicators", {})
    if error is not None:
        return {}, error
    records["risk_indicators"] = [
        d for d in risk_docs if str(d.get("student_id")) in enrolled
    ]
    return records, None


def _course_kpi_row(summary: CourseSummary, context: str) -> None:
    """Render the six course KPI cards."""
    columns = st.columns(6)
    kpis = (
        ("Enrollment", summary.enrollment, "students"),
        ("Average Marks", summary.avg_performance, "/ 100"),
        ("Average Attendance", summary.avg_attendance, "percent"),
        ("LMS Events", summary.engagement_count, "events"),
        (
            "Late Submission Rate",
            summary.coursework.late_rate_pct if summary.coursework else None,
            "percent",
        ),
        ("Students With Risk Signals", summary.students_with_signals, "students"),
    )
    for column, (label, value, unit) in zip(columns, kpis):
        with column:
            components.kpi_card(label, value, unit=unit, context=context)


def _coursework_section(coursework: CourseworkSummary | None) -> None:
    """Render coursework performance, late submissions and item mix."""
    if coursework is None:
        components.empty_state("No coursework data is available for this selection.")
        return

    def _body() -> None:
        st.caption(
            f"{coursework.items} items ({coursework.assignments} assignments, "
            f"{coursework.quizzes} quizzes) · {coursework.submitted} submitted · "
            f"late rate {components.format_value(coursework.late_rate_pct, 'percent')} · "
            f"average score {components.format_value(coursework.avg_score_pct, 'percent')}"
        )

    components.analytical_card(
        "Coursework behavior",
        "Items, submissions, late rate and average score observed for this course.",
        method="Serving coursework records; observed counts only",
        render_body=_body,
    )


def _association_section(summary: CourseSummary) -> None:
    """Render performance/attendance/engagement comparison vs school average."""
    if summary.avg_performance is None or summary.school_avg_performance is None:
        components.empty_state("No association data is available for this selection.")
        return

    def _body() -> None:
        import pandas as pd

        st.bar_chart(
            pd.DataFrame(
                [
                    {"Metric": "Avg performance", "Course": summary.avg_performance,
                     "School average": summary.school_avg_performance},
                    {"Metric": "Avg attendance", "Course": summary.avg_attendance,
                     "School average": summary.school_avg_attendance},
                ]
            ).set_index("Metric"),
        )
        st.caption(
            "Difficulty-adjusted performance "
            f"{components.format_value(summary.difficulty_adjusted_performance, 'std')} "
            "(within-course normalized; positive = above course-adjusted mean)."
        )

    components.analytical_card(
        "Performance, attendance and engagement",
        "Course metrics beside the school average. Observed comparison only.",
        method="Gold course/school metrics; association, not causation",
        render_body=_body,
    )


def _trend_section(summary: CourseSummary) -> None:
    """Render the enrolled students' observed score-trend mix."""
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
        "Trend",
        f"Mean score trend {components.format_value(trend.mean_score_trend, 'pts')} "
        f"across {trend.student_count} enrolled students.",
        method="Recent-minus-earlier graded-item average; association, not causation",
        render_body=_body,
    )


def _risk_section(summary: CourseSummary) -> None:
    """Render observed risk signals among enrolled students (never predictions)."""
    if summary.students_assessed is None or summary.students_assessed == 0:
        components.empty_state("No risk signals were detected for the selected scope.")
        return
    st.markdown(
        f"**{summary.students_with_signals} of {summary.students_assessed} "
        "enrolled students show observed signals**"
    )
    st.caption(
        "Risk indicator = count of five predefined observed signals. "
        "It is not a failure prediction model. Per-student breakdowns "
        "arrive in the Student view."
    )


def _resolve_picker_course(scope: Scope, access: DashboardDataAccess) -> tuple[str | None, str | None]:
    """Return ``(course_id, error)`` for the Course view picker.

    Courses are intersected with ``scope`` (faculty see only assigned
    courses); an empty course list yields an explicit empty state.
    """
    if scope.level == "courses":
        options = [c for c in scope.courses if c]
    else:
        rows, error = access.fetch(
            "course_metrics", build_mongo_scope_filter(scope, school_field="school")
        )
        if error is not None:
            return None, error
        options = available_courses(rows)
    if not options:
        return None, None
    stored = st.session_state.get(COURSE_PICKER_SESSION_KEY, options[0])
    selected = resolve_selected_course(options, stored if isinstance(stored, str) else None)
    assert selected is not None
    choice = st.selectbox("Course", options, index=options.index(selected), key=COURSE_PICKER_SESSION_KEY)
    return choice, None


def render_course_page(
    scope: Scope,
    filters: Mapping[str, str | None],
    access: DashboardDataAccess,
) -> None:
    """Render the Course view from actual gold and serving data."""
    course_id, error = _resolve_picker_course(scope, access)
    if error is not None:
        components.error_state(
            "Unable to load course view.",
            "The analytical data service is currently unavailable. "
            "Please check the database connection and try again.",
        )
        return
    if course_id is None:
        components.empty_state("No course data is available for this selection.")
        return

    records, error = fetch_course_data(access, scope, (filters or {}).get("semester"), course_id)
    if error is not None:
        if "outside the allowed scope" in error or "unavailable for the current scope" in error:
            components.error_state("Selection outside allowed scope.", error)
        else:
            components.error_state(
                "Unable to load course view.",
                "The analytical data service is currently unavailable. "
                "Please check the database connection and try again.",
            )
        return

    summary = compute_course_summary(
        course_id,
        records["course_metrics"],
        records["courses"],
        records["school_summary"],
        records["coursework"],
        records["student_features"],
        records["risk_indicators"],
    )
    context = layout.academic_context_label(filters or {})
    if (filters or {}).get("semester"):
        context += " (coursework aggregates all semesters in scope)"
    meta_line = " · ".join(
        part for part in (summary.course_title, summary.school, summary.department) if part
    )
    st.subheader(f"Course: {summary.course_id}" + (f" — {meta_line}" if meta_line else ""))
    if summary.difficulty_level:
        st.caption(f"Difficulty level: {summary.difficulty_level}")

    st.subheader("Course KPIs")
    _course_kpi_row(summary, context)

    st.subheader("Coursework behavior")
    _coursework_section(summary.coursework)

    st.subheader("Performance, attendance and engagement")
    _association_section(summary)

    st.subheader("Trend")
    _trend_section(summary)

    st.subheader("Risk signals")
    _risk_section(summary)
