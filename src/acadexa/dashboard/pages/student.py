"""Student view (Task 12.4, docs/design.md §18, features.md F-E06).

Integrated per-student analytics from actual gold and serving data:
profile, academic summary, attendance, coursework, LMS engagement, recent
trend and the five-rule signal breakdown (rendered with the shared
:func:`risk_signal_card`, never reimplemented).

Structure mirrors the earlier pages:

- :func:`fetch_student_data` — bounded, scope-aware reads (feature,
  academic, attendance, coursework, LMS and risk rows for one student;
  picker options intersected with scope).
- :func:`compute_student_summary` — pure aggregation over record lists.
- :func:`render_student_page` — Streamlit rendering with shared components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import streamlit as st

from acadexa.dashboard import components, layout
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.permissions import Scope, build_mongo_scope_filter

STUDENT_PICKER_SESSION_KEY: str = "acadexa_student_picker"


@dataclass(frozen=True)
class AcademicRow:
    """One student × course × semester academic record."""

    course_id: str
    semester_id: str | None
    internal_marks: float | None
    midterm_marks: float | None
    endterm_marks: float | None
    final_grade: str | None


@dataclass(frozen=True)
class AttendancePoint:
    """One weekly attendance observation."""

    week_start: str
    course_id: str | None
    attendance_rate: float | None


@dataclass(frozen=True)
class CourseworkItem:
    """One coursework item with submission outcome."""

    item_id: str
    course_id: str | None
    item_type: str | None
    score_pct: float | None
    status: str | None


@dataclass(frozen=True)
class StudentSummary:
    """Aggregated Student view content (None = data unavailable)."""

    student_id: str
    school: str | None
    department: str | None
    semesters: tuple[str, ...] = ()
    avg_academic_score: float | None = None
    avg_attendance: float | None = None
    attendance_rate: float | None = None
    classes_attended: int = 0
    classes_conducted: int = 0
    lms_events: int | None = None
    lms_by_activity: dict[str, int] = field(default_factory=dict)
    late_submission_rate: float | None = None
    academic_rows: tuple[AcademicRow, ...] = ()
    attendance_series: tuple[AttendancePoint, ...] = ()
    coursework_items: tuple[CourseworkItem, ...] = ()
    coursework_submitted: int = 0
    coursework_late: int = 0
    score_trend: float | None = None
    risk_count: int | None = None
    risk_triggered: dict[str, bool] = field(default_factory=dict)
    risk_explanations: dict[str, str] = field(default_factory=dict)


def available_students(student_features: list[dict[str, Any]]) -> list[str]:
    """Sorted student IDs present in ``student_features`` rows."""
    return sorted({str(d["student_id"]) for d in student_features if d.get("student_id")})


def resolve_selected_student(
    available: list[str], requested: str | None
) -> str | None:
    """Validate a student picker selection (None when nothing is available)."""
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


def _latest_risk(risk_indicators: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Most recent risk assessment by week_start (None when absent)."""
    if not risk_indicators:
        return None
    return max(risk_indicators, key=lambda d: str(d.get("week_start") or ""))


def compute_student_summary(
    student_id: str,
    student_features: list[dict[str, Any]],
    academic_records: list[dict[str, Any]],
    attendance: list[dict[str, Any]],
    coursework: list[dict[str, Any]],
    lms_events: list[dict[str, Any]],
    risk_indicators: list[dict[str, Any]],
) -> StudentSummary:
    """Aggregate one student's records into Student view content (pure).

    Empty inputs yield None KPIs and empty sections so the page renders
    explicit unavailable/empty states instead of zeros.
    """
    schools = {str(d["student_school"]) for d in student_features if d.get("student_school")}
    departments = {str(d["student_department"]) for d in student_features if d.get("student_department")}
    semesters = sorted({str(d["semester_id"]) for d in student_features if d.get("semester_id")})

    conducted = sum(int(d.get("classes_conducted") or 0) for d in attendance)
    attended = sum(int(d.get("classes_attended") or 0) for d in attendance)

    series = sorted(
        (
            AttendancePoint(
                week_start=str(d.get("week_start")),
                course_id=str(d.get("course_id")) if d.get("course_id") else None,
                attendance_rate=round(att / cond * 100, 1) if cond else None,
            )
            for d in attendance
            if d.get("week_start") is not None
            for cond in (int(d.get("classes_conducted") or 0),)
            for att in (int(d.get("classes_attended") or 0),)
        ),
        key=lambda p: (p.week_start, p.course_id or ""),
    )

    items = [
        CourseworkItem(
            item_id=str(d.get("item_id")),
            course_id=str(d.get("course_id")) if d.get("course_id") else None,
            item_type=str(d.get("item_type")) if d.get("item_type") else None,
            score_pct=round(float(d["score"]) / float(d["max_score"]) * 100, 1)
            if d.get("score") is not None and d.get("max_score") not in (None, 0)
            else None,
            status=str(d.get("status")) if d.get("status") else None,
        )
        for d in coursework
        if d.get("item_id")
    ]
    submitted_items = [d for d in coursework if d.get("submitted_at") is not None]

    activity: dict[str, int] = {}
    for event in lms_events:
        activity[str(event.get("activity_type") or "UNKNOWN")] = (
            activity.get(str(event.get("activity_type") or "UNKNOWN"), 0) + 1
        )

    by_semester = sorted(
        (str(d.get("semester_id") or ""), float(d["score_trend"]))
        for d in student_features
        if d.get("score_trend") is not None
    )
    trends = [value for _, value in by_semester]
    latest = _latest_risk(risk_indicators)

    return StudentSummary(
        student_id=student_id,
        school=sorted(schools)[0] if schools else None,
        department=sorted(departments)[0] if departments else None,
        semesters=tuple(semesters),
        avg_academic_score=_mean(
            [float(d["avg_academic_score"]) for d in student_features if d.get("avg_academic_score") is not None]
        ),
        avg_attendance=_mean(
            [float(d["attendance_mean"]) for d in student_features if d.get("attendance_mean") is not None]
        ),
        attendance_rate=round(attended / conducted * 100, 1) if conducted else None,
        classes_attended=attended,
        classes_conducted=conducted,
        lms_events=len(lms_events) if lms_events or student_features else None,
        lms_by_activity=activity,
        late_submission_rate=_mean(
            [float(d["late_submission_rate"]) for d in student_features if d.get("late_submission_rate") is not None]
        ),
        academic_rows=tuple(
            sorted(
                (
                    AcademicRow(
                        course_id=str(d.get("course_id")),
                        semester_id=str(d.get("semester_id")) if d.get("semester_id") else None,
                        internal_marks=float(d["internal_marks"]) if d.get("internal_marks") is not None else None,
                        midterm_marks=float(d["midterm_marks"]) if d.get("midterm_marks") is not None else None,
                        endterm_marks=float(d["endterm_marks"]) if d.get("endterm_marks") is not None else None,
                        final_grade=str(d.get("final_grade")) if d.get("final_grade") else None,
                    )
                    for d in academic_records
                    if d.get("course_id")
                ),
                key=lambda r: (r.semester_id or "", r.course_id),
            )
        ),
        attendance_series=tuple(series),
        coursework_items=tuple(items),
        coursework_submitted=len(submitted_items),
        coursework_late=sum(1 for d in submitted_items if d.get("status") == "LATE"),
        score_trend=trends[-1] if trends else None,
        risk_count=int(latest["signal_count"]) if latest and latest.get("signal_count") is not None else None,
        risk_triggered={key: bool(latest.get(key)) for key in components.RISK_SIGNAL_KEYS} if latest else {},
        risk_explanations=dict(latest.get("explanations") or {}) if latest else {},
    )


def fetch_student_data(
    access: DashboardDataAccess,
    scope: Scope,
    semester: str | None,
    student_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    """Fetch one student's scoped records for the Student view.

    ``student_id`` is verified against ``scope`` (school/department via
    feature rows, courses via enrollment in assigned courses) so the page
    can never escape the allowed scope. The semester filter applies to
    semester-grained collections; coursework, LMS and risk rows aggregate
    all semesters in scope. Returns ``(records, error)`` following the
    data-access failure contract.
    """
    if scope.level in ("school", "department"):
        check, error = access.fetch(
            "student_features",
            {"student_id": student_id, **build_mongo_scope_filter(
                scope, school_field="student_school", department_field="student_department"
            )},
        )
        if error is not None:
            return {}, error
        if not check:
            return {}, f"Student {student_id!r} is outside the allowed scope."
    elif scope.level == "courses":
        if not scope.courses:
            return {}, "This view is unavailable for the current scope."
        enrolled, error = access.fetch(
            "academic_records",
            {"student_id": student_id, "course_id": {"$in": list(scope.courses)}},
        )
        if error is not None:
            return {}, error
        if not enrolled:
            return {}, f"Student {student_id!r} is outside the allowed scope."
    elif scope.level != "university":
        return {}, "This view is unavailable for the current scope."

    student_filter: dict[str, Any] = {"student_id": student_id}
    semester_filter: dict[str, Any] = (
        {"student_id": student_id, "semester_id": semester} if semester else {"student_id": student_id}
    )
    records: dict[str, list[dict[str, Any]]] = {}
    for collection, query in (
        ("student_features", semester_filter),
        ("academic_records", semester_filter),
        ("attendance", semester_filter),
        ("coursework", student_filter),
        ("lms_events", {"meta.student_id": student_id}),
        ("risk_indicators", student_filter),
    ):
        docs, error = access.fetch(collection, query)
        if error is not None:
            return {}, error
        records[collection] = docs
    if scope.level == "courses":
        allowed = set(scope.courses)
        records["coursework"] = [d for d in records["coursework"] if d.get("course_id") in allowed]
        records["lms_events"] = [
            d for d in records["lms_events"] if (d.get("meta") or {}).get("course_id") in allowed
        ]
    return records, None


def _student_kpi_row(summary: StudentSummary, context: str) -> None:
    """Render the integrated student KPI cards."""
    columns = st.columns(6)
    kpis = (
        ("Average Score", summary.avg_academic_score, "/ 100"),
        ("Attendance Rate", summary.attendance_rate, "percent"),
        ("LMS Events", summary.lms_events, "events"),
        ("Late Submission Rate", round(summary.late_submission_rate * 100, 1) if summary.late_submission_rate is not None else None, "percent"),
        ("Score Trend", summary.score_trend, "pts"),
        ("Risk Signals", summary.risk_count, "/ 5"),
    )
    for column, (label, value, unit) in zip(columns, kpis):
        with column:
            components.kpi_card(label, value, unit=unit, context=context)


def _academic_section(rows: tuple[AcademicRow, ...]) -> None:
    """Render per-course academic records."""
    if not rows:
        components.empty_state("No academic records are available for this selection.")
        return

    def _body() -> None:
        st.dataframe(
            [
                {
                    "Course": r.course_id,
                    "Semester": r.semester_id or "—",
                    "Internal": r.internal_marks,
                    "Midterm": r.midterm_marks,
                    "Endterm": r.endterm_marks,
                    "Grade": r.final_grade or "—",
                }
                for r in rows
            ]
        )

    components.analytical_card(
        "Academic summary",
        "Internal, midterm and endterm marks with final grades per course.",
        method="Serving academic records; observed values only",
        render_body=_body,
    )


def _attendance_section(summary: StudentSummary) -> None:
    """Render derived attendance rate with the weekly series."""
    if summary.classes_conducted == 0:
        components.empty_state("No attendance data is available for this selection.")
        return

    def _body() -> None:
        import pandas as pd

        points = [p for p in summary.attendance_series if p.attendance_rate is not None]
        if points:
            st.bar_chart(
                pd.DataFrame(
                    [{"Week": p.week_start, "Attendance %": p.attendance_rate} for p in points]
                ),
                x="Week",
                y="Attendance %",
            )
        st.caption(
            f"{summary.classes_attended} of {summary.classes_conducted} classes attended "
            "(percentage derived from raw counts)."
        )

    components.analytical_card(
        "Attendance",
        "Weekly attendance derived from attended/conducted counts.",
        method="Derived rate; raw counts are authoritative",
        render_body=_body,
    )


def _coursework_section(summary: StudentSummary) -> None:
    """Render coursework items, submission timing and scores."""
    if not summary.coursework_items:
        components.empty_state("No coursework data is available for this selection.")
        return

    def _body() -> None:
        st.caption(
            f"{len(summary.coursework_items)} items · {summary.coursework_submitted} submitted · "
            f"{summary.coursework_late} late"
        )
        st.dataframe(
            [
                {
                    "Item": i.item_id,
                    "Course": i.course_id or "—",
                    "Type": i.item_type or "—",
                    "Score %": i.score_pct,
                    "Status": i.status or "—",
                }
                for i in summary.coursework_items
            ]
        )

    components.analytical_card(
        "Coursework",
        "Assignment and quiz items with submission timing and scores.",
        method="Serving coursework records; observed values only",
        render_body=_body,
    )


def _lms_section(summary: StudentSummary) -> None:
    """Render LMS engagement by activity type (association, not causation)."""
    if not summary.lms_by_activity:
        components.empty_state("No LMS activity is available for this selection.")
        return

    def _body() -> None:
        import pandas as pd

        st.bar_chart(
            pd.DataFrame(
                [{"Activity": k, "Events": v} for k, v in sorted(summary.lms_by_activity.items())]
            ),
            x="Activity",
            y="Events",
        )

    components.analytical_card(
        "LMS engagement",
        "Event counts by activity type. Observed engagement only.",
        method="Serving LMS event slice; association, not causation",
        render_body=_body,
    )


def _trend_section(summary: StudentSummary) -> None:
    """Render the recent score trend."""
    if summary.score_trend is None:
        components.empty_state("No trend data is available for this selection.")
        return
    direction = (
        "declining" if summary.score_trend < 0 else "improving" if summary.score_trend > 0 else "stable"
    )
    components.analytical_card(
        "Recent trend",
        f"Score trend {components.format_value(summary.score_trend, 'pts')} "
        f"({direction}; recent-minus-earlier graded-item average).",
        method="Gold feature trend; association, not causation",
    )


def _risk_section(summary: StudentSummary) -> None:
    """Render the five-rule signal breakdown via the shared risk card."""
    if summary.risk_count is None:
        components.empty_state("No risk signals were detected for the selected scope.")
        return
    components.risk_signal_card(
        summary.risk_count, summary.risk_triggered, explanations=summary.risk_explanations or None
    )


def _resolve_picker_student(scope: Scope, access: DashboardDataAccess) -> tuple[str | None, str | None]:
    """Return ``(student_id, error)`` for the Student view picker.

    Options are intersected with ``scope`` (faculty see students enrolled
    in assigned courses); an empty list yields an explicit empty state.
    """
    if scope.level == "courses":
        if not scope.courses:
            return None, None
        rows, error = access.fetch("academic_records", {"course_id": {"$in": list(scope.courses)}})
        if error is not None:
            return None, error
        options = sorted({str(d["student_id"]) for d in rows if d.get("student_id")})
    else:
        rows, error = access.fetch(
            "student_features", build_mongo_scope_filter(
                scope, school_field="student_school", department_field="student_department"
            )
        )
        if error is not None:
            return None, error
        options = available_students(rows)
    if not options:
        return None, None
    stored = st.session_state.get(STUDENT_PICKER_SESSION_KEY, options[0])
    selected = resolve_selected_student(options, stored if isinstance(stored, str) else None)
    assert selected is not None
    choice = st.selectbox("Student", options, index=options.index(selected), key=STUDENT_PICKER_SESSION_KEY)
    return choice, None


def render_student_page(
    scope: Scope,
    filters: Mapping[str, str | None],
    access: DashboardDataAccess,
) -> None:
    """Render the integrated Student view from actual gold and serving data."""
    student_id, error = _resolve_picker_student(scope, access)
    if error is not None:
        components.error_state(
            "Unable to load student view.",
            "The analytical data service is currently unavailable. "
            "Please check the database connection and try again.",
        )
        return
    if student_id is None:
        components.empty_state("No student data is available for this selection.")
        return

    records, error = fetch_student_data(access, scope, (filters or {}).get("semester"), student_id)
    if error is not None:
        if "outside the allowed scope" in error or "unavailable for the current scope" in error:
            components.error_state("Selection outside allowed scope.", error)
        else:
            components.error_state(
                "Unable to load student view.",
                "The analytical data service is currently unavailable. "
                "Please check the database connection and try again.",
            )
        return

    summary = compute_student_summary(
        student_id,
        records["student_features"],
        records["academic_records"],
        records["attendance"],
        records["coursework"],
        records["lms_events"],
        records["risk_indicators"],
    )
    context = layout.academic_context_label(filters or {})
    if (filters or {}).get("semester"):
        context += " (coursework, LMS and risk aggregate all semesters in scope)"
    profile = " · ".join(part for part in (summary.school, summary.department) if part)
    st.subheader(f"Student: {summary.student_id}" + (f" — {profile}" if profile else ""))

    st.subheader("Student KPIs")
    _student_kpi_row(summary, context)

    st.subheader("Academic summary")
    _academic_section(summary.academic_rows)

    st.subheader("Attendance")
    _attendance_section(summary)

    st.subheader("Coursework")
    _coursework_section(summary)

    st.subheader("LMS engagement")
    _lms_section(summary)

    st.subheader("Recent trend")
    _trend_section(summary)

    st.subheader("Risk signals")
    _risk_section(summary)
