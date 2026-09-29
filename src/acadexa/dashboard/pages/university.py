"""University Overview page (Task 12.1, docs/design.md §14, features.md F-E01).

Primary landing page for broad-scope users, built only from actual gold
data: university KPIs, school comparison, academic/attendance/LMS
overview, trend summary and risk summary.

Structure mirrors the aggregation in three layers so each is testable:

- :func:`fetch_university_data` — bounded, scope-aware MongoDB reads
  (semester filter applies only to semester-grained collections).
- :func:`compute_university_summary` — pure aggregation over record lists.
- :func:`render_university_page` — Streamlit rendering with shared
  components (requires a UI runtime).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import streamlit as st

from acadexa.dashboard import components, layout
from acadexa.dashboard.permissions import Scope, build_mongo_scope_filter
from acadexa.dashboard.data_access import DashboardDataAccess

OVERVIEW_COLLECTIONS: tuple[str, ...] = (
    "student_features",
    "course_metrics",
    "school_summary",
    "risk_indicators",
)


@dataclass(frozen=True)
class SchoolRow:
    """One aggregated school comparison row (mean of department roll-ups)."""

    school: str
    student_count: int
    course_count: int
    avg_performance: float | None
    avg_attendance: float | None
    engagement_count: int


@dataclass(frozen=True)
class TrendSummary:
    """Observed score-trend summary (recent-minus-earlier points)."""

    student_count: int
    mean_score_trend: float | None
    declining: int
    improving: int
    stable: int


@dataclass(frozen=True)
class RiskSummary:
    """Observed risk-signal summary (counts, never predictions)."""

    assessed: int
    flagged: int
    distribution: dict[int, int] = field(default_factory=dict)
    signal_triggers: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class UniversitySummary:
    """Aggregated University Overview content (None = data unavailable)."""

    student_count: int | None
    course_count: int | None
    avg_attendance: float | None
    avg_performance: float | None
    avg_engagement: float | None
    total_lms_events: int | None
    students_with_signals: int | None
    schools: tuple[SchoolRow, ...] = ()
    trend: TrendSummary | None = None
    risk: RiskSummary | None = None


def _mean(values: list[float]) -> float | None:
    """Rounded mean of ``values`` (None when empty)."""
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def compute_university_summary(
    student_features: list[dict[str, Any]],
    course_metrics: list[dict[str, Any]],
    school_summary: list[dict[str, Any]],
    risk_indicators: list[dict[str, Any]],
) -> UniversitySummary:
    """Aggregate gold records into University Overview content (pure).

    Empty inputs yield None KPIs and empty sections so the page renders
    explicit "Data unavailable" / empty states instead of zeros.
    """
    students = {str(d.get("student_id")) for d in student_features if d.get("student_id")}
    courses = {str(d.get("course_id")) for d in course_metrics if d.get("course_id")}

    attendance = [float(d["attendance_mean"]) for d in student_features if d.get("attendance_mean") is not None]
    performance = [float(d["avg_academic_score"]) for d in student_features if d.get("avg_academic_score") is not None]
    engagement = [int(d["engagement_count"]) for d in student_features if d.get("engagement_count") is not None]

    schools = _aggregate_schools(school_summary)
    trend = _summarize_trends(student_features)
    risk = _summarize_risk(risk_indicators)

    return UniversitySummary(
        student_count=len(students) if student_features else None,
        course_count=len(courses) if course_metrics else None,
        avg_attendance=_mean(attendance),
        avg_performance=_mean(performance),
        avg_engagement=_mean([float(v) for v in engagement]),
        total_lms_events=sum(engagement) if engagement else None,
        students_with_signals=risk.flagged if risk is not None else None,
        schools=schools,
        trend=trend,
        risk=risk,
    )


def _aggregate_schools(school_summary: list[dict[str, Any]]) -> tuple[SchoolRow, ...]:
    """Roll department grain up to one row per school."""
    by_school: dict[str, dict[str, Any]] = {}
    for doc in school_summary:
        school = doc.get("school")
        if not school:
            continue
        bucket = by_school.setdefault(
            str(school),
            {"students": 0, "courses": 0, "perf": [], "att": [], "eng": 0},
        )
        bucket["students"] += int(doc.get("student_count") or 0)
        bucket["courses"] += int(doc.get("course_count") or 0)
        if doc.get("avg_performance") is not None:
            bucket["perf"].append(float(doc["avg_performance"]))
        if doc.get("avg_attendance") is not None:
            bucket["att"].append(float(doc["avg_attendance"]))
        bucket["eng"] += int(doc.get("engagement_count") or 0)
    return tuple(
        SchoolRow(
            school=name,
            student_count=bucket["students"],
            course_count=bucket["courses"],
            avg_performance=_mean(bucket["perf"]),
            avg_attendance=_mean(bucket["att"]),
            engagement_count=bucket["eng"],
        )
        for name, bucket in sorted(by_school.items())
    )


def _summarize_trends(student_features: list[dict[str, Any]]) -> TrendSummary | None:
    """Summarize observed score trends (None when no trend data)."""
    trends = [float(d["score_trend"]) for d in student_features if d.get("score_trend") is not None]
    if not trends:
        return None
    return TrendSummary(
        student_count=len(trends),
        mean_score_trend=_mean(trends),
        declining=sum(1 for v in trends if v < 0),
        improving=sum(1 for v in trends if v > 0),
        stable=sum(1 for v in trends if v == 0),
    )


def _summarize_risk(risk_indicators: list[dict[str, Any]]) -> RiskSummary | None:
    """Summarize observed risk signals (None when nothing assessed)."""
    if not risk_indicators:
        return None
    distribution = {n: 0 for n in range(6)}
    triggers = {
        "low_attendance": 0,
        "lms_decline": 0,
        "late_submissions": 0,
        "marks_decline": 0,
        "low_quiz_activity": 0,
    }
    for doc in risk_indicators:
        count = int(doc.get("signal_count") or 0)
        distribution[count] = distribution.get(count, 0) + 1
        for key in triggers:
            if doc.get(key) is True:
                triggers[key] += 1
    return RiskSummary(
        assessed=len(risk_indicators),
        flagged=sum(1 for d in risk_indicators if int(d.get("signal_count") or 0) >= 1),
        distribution=distribution,
        signal_triggers=triggers,
    )


def fetch_university_data(
    access: DashboardDataAccess,
    scope: Scope,
    semester: str | None,
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    """Fetch scoped gold records for the overview page.

    The semester filter applies only to semester-grained collections
    (``student_features``, ``course_metrics``); school/risk summaries
    aggregate the selected scope across semesters. ``risk_indicators``
    carry no hierarchy fields, so they are restricted in Python to the
    scoped students. Returns ``(records, error)`` following the
    data-access failure contract: any failure yields a controlled error
    and no fabricated values.
    """
    student_filter = build_mongo_scope_filter(
        scope, school_field="student_school", department_field="student_department"
    )
    course_filter = build_mongo_scope_filter(scope, school_field="school")
    school_filter = build_mongo_scope_filter(scope, school_field="school")
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


def _kpi_row(summary: UniversitySummary, context: str) -> None:
    """Render the six F-E01 university KPI cards."""
    columns = st.columns(6)
    kpis = (
        ("Active Students", summary.student_count, "students"),
        ("Average Attendance", summary.avg_attendance, "percent"),
        ("Average Performance", summary.avg_performance, "/ 100"),
        ("Average Engagement", summary.avg_engagement, "events"),
        ("Total LMS Events", summary.total_lms_events, "events"),
        ("Students With Risk Signals", summary.students_with_signals, "students"),
    )
    for column, (label, value, unit) in zip(columns, kpis):
        with column:
            components.kpi_card(label, value, unit=unit, context=context)


def _school_comparison(schools: tuple[SchoolRow, ...]) -> None:
    """Render school comparison without any composite best-school score."""
    def _body() -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [
                {"School": row.school, "Avg performance": row.avg_performance}
                for row in schools
                if row.avg_performance is not None
            ]
        )
        if not frame.empty:
            st.bar_chart(frame, x="School", y="Avg performance")
        st.dataframe(
            [
                {
                    "School": row.school,
                    "Students": row.student_count,
                    "Courses": row.course_count,
                    "Avg performance": row.avg_performance,
                    "Avg attendance": row.avg_attendance,
                    "LMS events": row.engagement_count,
                }
                for row in schools
            ]
        )

    if not schools:
        components.empty_state("No school data is available for this selection.")
        return
    components.analytical_card(
        "School comparison",
        "Department roll-ups aggregated per school. No composite best-school score is shown.",
        method="Mean of department roll-ups per school",
        render_body=_body,
    )


def _academic_engagement(course_metrics: list[dict[str, Any]]) -> None:
    """Render course performance vs LMS engagement (association, not causation)."""
    points = [
        {
            "Course": str(d.get("course_id")),
            "Avg performance": d.get("avg_performance"),
            "LMS events": d.get("engagement_count"),
        }
        for d in course_metrics
        if d.get("avg_performance") is not None and d.get("engagement_count") is not None
    ]
    if not points:
        components.empty_state("No course data is available for this selection.")
        return

    def _body() -> None:
        import pandas as pd

        st.scatter_chart(pd.DataFrame(points), x="LMS events", y="Avg performance")

    components.analytical_card(
        "Academic vs engagement overview",
        "Course performance plotted against LMS engagement. Observed association only.",
        method="Course × semester gold metrics; association, not causation",
        render_body=_body,
    )


def _trend_section(trend: TrendSummary | None) -> None:
    """Render the observed score-trend summary."""
    if trend is None:
        components.empty_state("No trend data is available for this selection.")
        return

    def _body() -> None:
        st.caption(
            f"{trend.declining} declining · {trend.improving} improving · "
            f"{trend.stable} stable (recent-minus-earlier graded-item average, points)"
        )

    components.analytical_card(
        "Trend summary",
        f"Mean score trend {components.format_value(trend.mean_score_trend, 'pts')} "
        f"across {trend.student_count} students.",
        method="Recent-minus-earlier graded-item average; association, not causation",
        render_body=_body,
    )


def _risk_section(risk: RiskSummary | None) -> None:
    """Render the observed risk-signal summary (counts, never predictions)."""
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


def render_university_page(
    scope: Scope,
    filters: Mapping[str, str | None],
    access: DashboardDataAccess,
) -> None:
    """Render the University Overview page from actual gold data."""
    records, error = fetch_university_data(access, scope, (filters or {}).get("semester"))
    if error is not None:
        components.error_state(
            "Unable to load university overview.",
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
        context += " (school and risk summaries aggregate all semesters in scope)"

    st.subheader("University KPIs")
    _kpi_row(summary, context)

    st.subheader("School comparison")
    _school_comparison(summary.schools)

    st.subheader("Academic vs engagement overview")
    _academic_engagement(records["course_metrics"])

    st.subheader("Trend summary")
    _trend_section(summary.trend)

    st.subheader("Risk summary")
    _risk_section(summary.risk)
