"""Unit tests for the School/Department views (Task 12.2).

Covers school selection, scoped fetching with department narrowing,
scoped KPIs/coursework/trends/risk via the shared aggregation, and
headless rendering of department breakdown, course breakdown and risk
distribution. Small fixtures only; live-Mongo AppTest checks use the
development gold data without asserting exact values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard.config import DashboardConfig
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.pages.school import (
    SCHOOL_PICKER_SESSION_KEY,
    available_schools,
    fetch_school_data,
    resolve_selected_school,
)
from acadexa.dashboard.pages.university import compute_university_summary
from acadexa.dashboard.permissions import Scope

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"

TECH = "School of Technology"
BUSINESS = "School of Business"


def _student_features() -> list[dict]:
    """Four students across two schools and three departments."""
    return [
        {
            "student_id": "STU010482",
            "semester_id": "S1",
            "attendance_mean": 78.5,
            "engagement_count": 412,
            "late_submission_rate": 0.2,
            "score_trend": -12.0,
            "avg_academic_score": 71.2,
            "student_school": TECH,
            "student_department": "Computer Science",
        },
        {
            "student_id": "STU020001",
            "semester_id": "S1",
            "attendance_mean": 90.0,
            "engagement_count": 300,
            "late_submission_rate": 0.0,
            "score_trend": 5.0,
            "avg_academic_score": 85.0,
            "student_school": TECH,
            "student_department": "Computer Science",
        },
        {
            "student_id": "STU020002",
            "semester_id": "S1",
            "attendance_mean": 70.0,
            "engagement_count": 100,
            "late_submission_rate": 0.5,
            "score_trend": -3.0,
            "avg_academic_score": 65.0,
            "student_school": TECH,
            "student_department": "Information Technology",
        },
        {
            "student_id": "STU030001",
            "semester_id": "S1",
            "attendance_mean": 83.5,
            "engagement_count": 380,
            "late_submission_rate": 0.125,
            "score_trend": 1.0,
            "avg_academic_score": 76.5,
            "student_school": BUSINESS,
            "student_department": "Management",
        },
    ]


def _course_metrics() -> list[dict]:
    """Four courses across two schools."""
    return [
        {
            "course_id": "CSA101",
            "semester_id": "S1",
            "avg_performance": 78.5,
            "avg_attendance": 85.0,
            "engagement_count": 450,
            "enrolled_students_count": 2,
            "course_title": "Intro CS",
            "school": TECH,
            "department": "Computer Science",
            "course_difficulty": 0.4,
            "difficulty_adjusted_performance": 0.81,
        },
        {
            "course_id": "CSA102",
            "semester_id": "S1",
            "avg_performance": 70.4,
            "avg_attendance": 77.0,
            "engagement_count": 262,
            "enrolled_students_count": 1,
            "course_title": "Data Struct",
            "school": TECH,
            "department": "Computer Science",
            "course_difficulty": 0.6,
            "difficulty_adjusted_performance": -1.36,
        },
        {
            "course_id": "ITX101",
            "semester_id": "S1",
            "avg_performance": 65.0,
            "avg_attendance": 70.0,
            "engagement_count": 100,
            "enrolled_students_count": 1,
            "course_title": "Networks",
            "school": TECH,
            "department": "Information Technology",
            "course_difficulty": 0.5,
            "difficulty_adjusted_performance": -0.2,
        },
        {
            "course_id": "MGT101",
            "semester_id": "S1",
            "avg_performance": 76.5,
            "avg_attendance": 83.5,
            "engagement_count": 380,
            "enrolled_students_count": 1,
            "course_title": "Prin Mgmt",
            "school": BUSINESS,
            "department": "Management",
            "course_difficulty": 0.3,
            "difficulty_adjusted_performance": 0.68,
        },
    ]


def _school_summary() -> list[dict]:
    """Three department roll-ups across two schools."""
    return [
        {
            "school": TECH,
            "department": "Computer Science",
            "student_count": 2,
            "course_count": 2,
            "avg_performance": 75.8,
            "avg_attendance": 82.3,
            "engagement_count": 712,
        },
        {
            "school": TECH,
            "department": "Information Technology",
            "student_count": 1,
            "course_count": 1,
            "avg_performance": 65.0,
            "avg_attendance": 70.0,
            "engagement_count": 100,
        },
        {
            "school": BUSINESS,
            "department": "Management",
            "student_count": 1,
            "course_count": 1,
            "avg_performance": 76.5,
            "avg_attendance": 83.5,
            "engagement_count": 380,
        },
    ]


def _risk_indicators() -> list[dict]:
    """Assessments for the Technology students plus one orphan row."""
    return [
        {
            "student_id": "STU010482",
            "signal_count": 3,
            "low_attendance": True,
            "lms_decline": True,
            "late_submissions": False,
            "marks_decline": True,
            "low_quiz_activity": False,
        },
        {
            "student_id": "STU020001",
            "signal_count": 0,
            "low_attendance": False,
            "lms_decline": False,
            "late_submissions": False,
            "marks_decline": False,
            "low_quiz_activity": False,
        },
        {
            "student_id": "STU020002",
            "signal_count": 2,
            "low_attendance": True,
            "lms_decline": False,
            "late_submissions": True,
            "marks_decline": False,
            "low_quiz_activity": False,
        },
        {
            "student_id": "STU999999",
            "signal_count": 5,
            "low_attendance": True,
            "lms_decline": True,
            "late_submissions": True,
            "marks_decline": True,
            "low_quiz_activity": True,
        },
    ]


# ── School selection ───────────────────────────────────────────────


def test_available_schools_sorted_unique() -> None:
    """Picker options derive from real summary rows, sorted."""
    assert available_schools(_school_summary()) == [BUSINESS, TECH]
    assert available_schools([]) == []
    assert available_schools([{"department": "X"}]) == []


def test_resolve_selected_school() -> None:
    """Stored selections validate; unknown/empty falls back deterministically."""
    assert resolve_selected_school([BUSINESS, TECH], TECH) == TECH
    assert resolve_selected_school([BUSINESS, TECH], "Nope") == BUSINESS
    assert resolve_selected_school([BUSINESS, TECH], None) == BUSINESS
    assert resolve_selected_school([], TECH) is None


# ── Scoped aggregation (shared math, school-scoped records) ────────


def _tech_records() -> tuple[list, list, list, list]:
    """Fixture records narrowed to the Technology school."""
    students = [d for d in _student_features() if d["student_school"] == TECH]
    courses = [d for d in _course_metrics() if d["school"] == TECH]
    summary = [d for d in _school_summary() if d["school"] == TECH]
    risk = [d for d in _risk_indicators() if d["student_id"] != "STU999999"][:3]
    return students, courses, summary, risk


def test_scoped_kpis_use_shared_aggregation() -> None:
    """School-scoped KPIs reuse the canonical aggregation exactly."""
    students, courses, summary, risk = _tech_records()
    result = compute_university_summary(students, courses, summary, risk)
    assert result.student_count == 3
    assert result.course_count == 3
    assert result.avg_attendance == 79.5
    assert result.avg_performance == 73.7
    assert result.total_lms_events == 812
    assert result.students_with_signals == 2
    assert [row.school for row in result.schools] == [TECH]


def test_department_narrowing_changes_kpis() -> None:
    """Department narrowing restricts every KPI to the department slice."""
    students = [d for d in _student_features() if d["student_department"] == "Computer Science"]
    courses = [d for d in _course_metrics() if d["department"] == "Computer Science"]
    summary = [d for d in _school_summary() if d["department"] == "Computer Science"]
    risk = [d for d in _risk_indicators() if d["student_id"] in {"STU010482", "STU020001"}]
    result = compute_university_summary(students, courses, summary, risk)
    assert result.student_count == 2
    assert result.course_count == 2
    assert result.avg_attendance == 84.2
    assert result.total_lms_events == 712
    assert result.students_with_signals == 1


# ── Scope-aware fetching ───────────────────────────────────────────


class _RecordingCursor(list):
    """Cursor double supporting ``limit``."""

    def limit(self, n: int) -> list:
        return list(self)[:n]


class _RecordingCollection:
    """Collection double recording queries with naive equality filtering."""

    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs
        self.queries: list[dict] = []

    def find(self, query: dict) -> _RecordingCursor:
        self.queries.append(dict(query))
        return _RecordingCursor(
            [d for d in self._docs if all(d.get(k) == v for k, v in query.items())]
        )

    def count_documents(self, query: dict) -> int:
        return len(self.find(query))


class _RecordingDB(dict):
    """Database double supporting ``db[name]`` access."""

    def __getitem__(self, name: str):  # type: ignore[override]
        return super().__getitem__(name)


def _recording_access() -> tuple[DashboardDataAccess, _RecordingDB]:
    db: _RecordingDB = _RecordingDB(
        {
            "student_features": _RecordingCollection(_student_features()),
            "course_metrics": _RecordingCollection(_course_metrics()),
            "school_summary": _RecordingCollection(_school_summary()),
            "risk_indicators": _RecordingCollection(_risk_indicators()),
        }
    )
    return DashboardDataAccess(DashboardConfig(), db=db), db


def test_fetch_forces_school_and_joins_risk() -> None:
    """University scope plus picker school filters hierarchy reads and risk."""
    access, db = _recording_access()
    records, error = fetch_school_data(
        access, Scope(level="university"), None, TECH, None
    )
    assert error is None
    assert db["student_features"].queries == [{"student_school": TECH}]
    assert db["course_metrics"].queries == [{"school": TECH}]
    assert db["school_summary"].queries == [{"school": TECH}]
    assert {d["student_id"] for d in records["student_features"]} == {
        "STU010482",
        "STU020001",
        "STU020002",
    }
    assert {d["student_id"] for d in records["risk_indicators"]} == {
        "STU010482",
        "STU020001",
        "STU020002",
    }


def test_fetch_applies_department_and_semester() -> None:
    """Department narrows every grain; semester only semester-grained reads."""
    access, db = _recording_access()
    records, error = fetch_school_data(
        access, Scope(level="university"), "S1", TECH, "Computer Science"
    )
    assert error is None
    assert db["student_features"].queries == [
        {"student_school": TECH, "student_department": "Computer Science", "semester_id": "S1"}
    ]
    assert db["course_metrics"].queries == [
        {"school": TECH, "department": "Computer Science", "semester_id": "S1"}
    ]
    assert db["school_summary"].queries == [
        {"school": TECH, "department": "Computer Science"}
    ]
    assert {d["student_id"] for d in records["student_features"]} == {
        "STU010482",
        "STU020001",
    }
    assert {d["course_id"] for d in records["course_metrics"]} == {"CSA101", "CSA102"}


def test_fetch_rejects_out_of_scope_school() -> None:
    """Picker values cannot escape school/department scopes."""
    access, _ = _recording_access()
    records, error = fetch_school_data(
        access, Scope(level="school", school=TECH), None, BUSINESS, None
    )
    assert records == {}
    assert error is not None and "outside the allowed scope" in error

    records, error = fetch_school_data(
        access,
        Scope(level="department", school=TECH, department="Computer Science"),
        None,
        TECH,
        "Information Technology",
    )
    assert records == {}
    assert error is not None and "outside the allowed scope" in error


def test_fetch_reports_controlled_error() -> None:
    """Database failures surface as controlled errors, never partial data."""

    class _FailingCollection:
        def find(self, query: dict):
            raise ConnectionError("boom")

        def count_documents(self, query: dict) -> int:
            raise ConnectionError("boom")

    class _FailingDB(dict):
        def __getitem__(self, name: str):  # type: ignore[override]
            return _FailingCollection()

    access = DashboardDataAccess(DashboardConfig(), db=_FailingDB())
    try:
        records, error = fetch_school_data(
            access, Scope(level="university"), None, TECH, None
        )
        assert records == {}
        assert error is not None and "student_features" in error
    finally:
        access.close()


# ── Headless rendering ─────────────────────────────────────────────


def _login_as(at, display_name: str, role: str) -> None:
    at.selectbox(key="acadexa_login_choice").set_value(
        f"{display_name} ({role})"
    ).run()
    at.button(key="acadexa_login_button").click().run()
    assert not at.exception


def _goto_schools(at) -> None:
    at.sidebar.radio[0].set_value("Schools").run()
    assert not at.exception


def test_schools_page_renders_scoped_sections() -> None:
    """Admin Schools page shows picker, KPIs, breakdowns, trends and risk."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_schools(at)

    assert at.header[0].value == "Schools"
    assert at.selectbox(key=SCHOOL_PICKER_SESSION_KEY).value == "School of Business"
    labels = [m.label for m in at.metric]
    for expected in (
        "Students",
        "Courses",
        "Average Attendance",
        "Average Performance",
        "Average Engagement",
        "Students With Risk Signals",
    ):
        assert expected in labels
    subheaders = [s.value for s in at.subheader]
    for expected in (
        "Scoped KPIs",
        "Coursework behavior",
        "Department breakdown",
        "Course breakdown",
        "Trend indicators",
        "Risk distribution",
    ):
        assert expected in subheaders
    assert any("MGT101" in str(frame.value) for frame in at.dataframe)
    captions = [c.value for c in at.caption]
    assert any("not a failure prediction" in text for text in captions)


def test_schools_picker_switches_school_content() -> None:
    """Switching the picker re-scopes KPIs, courses and departments."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_schools(at)

    at.selectbox(key=SCHOOL_PICKER_SESSION_KEY).set_value(TECH).run()
    assert not at.exception
    assert any("CSA101" in str(frame.value) for frame in at.dataframe)
    assert not any("MGT101" in str(frame.value) for frame in at.dataframe)


def test_schools_empty_scope_shows_explicit_states() -> None:
    """A scope with no gold data renders unavailable/empty states, no zeros."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "CET School Admin", "School / Department Admin")
    _goto_schools(at)

    assert not at.exception
    assert any(m.value == "Data unavailable" for m in at.metric)
    assert any(
        "No department data is available for this selection." in i.value
        for i in at.info
    )


def test_schools_error_state_without_traceback(tmp_path: Path) -> None:
    """Unreachable data renders the controlled error state in-page."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_school_error.py"
    script.write_text(
        "from acadexa.dashboard.config import DashboardConfig\n"
        "from acadexa.dashboard.data_access import DashboardDataAccess\n"
        "from acadexa.dashboard.pages.school import render_school_page\n"
        "from acadexa.dashboard.permissions import Scope\n"
        "from acadexa.database import MongoDBConfig\n"
        "bad = MongoDBConfig(uri='mongodb://localhost:29999', "
        "database='test_school_unreachable', server_selection_timeout_ms=50, "
        "connect_timeout_ms=50)\n"
        "access = DashboardDataAccess(DashboardConfig(database=bad))\n"
        "render_school_page(Scope(level='university'), {}, access)\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception
    assert any("Unable to load school view" in e.value for e in at.error)
    assert all("Traceback" not in e.value for e in at.error)
