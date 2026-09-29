"""Unit tests for the Course view (Task 12.3).

Covers course selection, scoped fetching with enrollment joins, pure
aggregation (metadata, enrollment, marks, attendance, coursework, LMS
engagement, trends, associations) and headless rendering. Small fixtures
only; live-Mongo AppTest checks use the development data without asserting
exact values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard.config import DashboardConfig
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.pages.course import (
    COURSE_PICKER_SESSION_KEY,
    available_courses,
    compute_course_summary,
    fetch_course_data,
    resolve_selected_course,
)
from acadexa.dashboard.permissions import Scope

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"


def _course_metrics() -> list[dict]:
    """Two semesters of CSA101 plus one row of another course."""
    return [
        {
            "course_id": "CSA101",
            "semester_id": "S1",
            "avg_performance": 78.5,
            "avg_attendance": 85.0,
            "engagement_count": 450,
            "enrolled_students_count": 2,
            "course_title": "Intro CS",
            "school": "School of Technology",
            "department": "Computer Science",
            "course_difficulty": 0.4,
            "difficulty_adjusted_performance": 0.81,
        },
        {
            "course_id": "CSA101",
            "semester_id": "S2",
            "avg_performance": 80.5,
            "avg_attendance": 87.0,
            "engagement_count": 550,
            "enrolled_students_count": 3,
            "course_title": "Intro CS",
            "school": "School of Technology",
            "department": "Computer Science",
            "course_difficulty": 0.4,
            "difficulty_adjusted_performance": 0.91,
        },
        {
            "course_id": "MGT101",
            "semester_id": "S1",
            "avg_performance": 76.5,
            "avg_attendance": 83.5,
            "engagement_count": 380,
            "enrolled_students_count": 1,
            "course_title": "Prin Mgmt",
            "school": "School of Business",
            "department": "Management",
            "course_difficulty": 0.3,
            "difficulty_adjusted_performance": 0.68,
        },
    ]


def _catalogue() -> list[dict]:
    """Catalogue metadata for CSA101 only (MGT101 falls back to metrics)."""
    return [
        {
            "course_id": "CSA101",
            "title": "Programming Fundamentals",
            "school": "School of Technology",
            "department": "Computer Science and Applications",
            "difficulty_level": "medium",
            "difficulty": 0.65,
        }
    ]


def _school_summary() -> list[dict]:
    """School roll-ups for Technology and Business."""
    return [
        {
            "school": "School of Technology",
            "department": "Computer Science",
            "student_count": 2,
            "course_count": 1,
            "avg_performance": 75.8,
            "avg_attendance": 82.3,
            "engagement_count": 712,
        },
        {
            "school": "School of Technology",
            "department": "Information Technology",
            "student_count": 1,
            "course_count": 1,
            "avg_performance": 65.0,
            "avg_attendance": 70.0,
            "engagement_count": 100,
        },
        {
            "school": "School of Business",
            "department": "Management",
            "student_count": 1,
            "course_count": 1,
            "avg_performance": 76.5,
            "avg_attendance": 83.5,
            "engagement_count": 380,
        },
    ]


def _coursework() -> list[dict]:
    """Four items: two on-time, one late, one missing, one quiz."""
    return [
        {"student_id": "S1", "course_id": "CSA101", "item_id": "A01",
         "item_type": "ASSIGNMENT", "submitted_at": "2025-09-01T10:00:00",
         "score": 16, "max_score": 20, "attempts": 1, "status": "ON_TIME"},
        {"student_id": "S1", "course_id": "CSA101", "item_id": "A02",
         "item_type": "ASSIGNMENT", "submitted_at": "2025-09-10T10:00:00",
         "score": 10, "max_score": 20, "attempts": 2, "status": "LATE"},
        {"student_id": "S2", "course_id": "CSA101", "item_id": "Q01",
         "item_type": "QUIZ", "submitted_at": "2025-09-05T10:00:00",
         "score": 9, "max_score": 10, "attempts": 1, "status": "ON_TIME"},
        {"student_id": "S2", "course_id": "CSA101", "item_id": "A03",
         "item_type": "ASSIGNMENT", "submitted_at": None,
         "score": None, "max_score": 20, "attempts": 0, "status": "MISSING"},
    ]


def _student_features() -> list[dict]:
    """Two enrolled students with opposing trends."""
    return [
        {"student_id": "S1", "semester_id": "S1", "attendance_mean": 80.0,
         "engagement_count": 200, "late_submission_rate": 0.5,
         "score_trend": -4.0, "avg_academic_score": 70.0,
         "student_school": "School of Technology"},
        {"student_id": "S2", "semester_id": "S1", "attendance_mean": 90.0,
         "engagement_count": 300, "late_submission_rate": 0.0,
         "score_trend": 6.0, "avg_academic_score": 85.0,
         "student_school": "School of Technology"},
    ]


def _risk_indicators() -> list[dict]:
    """One flagged enrolled student plus one orphan row."""
    return [
        {"student_id": "S1", "signal_count": 2, "low_attendance": True,
         "lms_decline": False, "late_submissions": True,
         "marks_decline": False, "low_quiz_activity": False},
        {"student_id": "GHOST", "signal_count": 5, "low_attendance": True,
         "lms_decline": True, "late_submissions": True,
         "marks_decline": True, "low_quiz_activity": True},
    ]


# ── Course selection ───────────────────────────────────────────────


def test_available_courses_sorted_unique() -> None:
    """Picker options derive from real metric rows, sorted."""
    assert available_courses(_course_metrics()) == ["CSA101", "MGT101"]
    assert available_courses([]) == []
    assert available_courses([{"semester_id": "S1"}]) == []


def test_resolve_selected_course() -> None:
    """Stored selections validate; unknown/empty falls back deterministically."""
    assert resolve_selected_course(["CSA101", "MGT101"], "MGT101") == "MGT101"
    assert resolve_selected_course(["CSA101", "MGT101"], "Nope") == "CSA101"
    assert resolve_selected_course(["CSA101", "MGT101"], None) == "CSA101"
    assert resolve_selected_course([], "CSA101") is None


# ── Pure aggregation ───────────────────────────────────────────────


def test_compute_course_summary_kpis() -> None:
    """KPIs aggregate exactly: means across semesters, max enrollment."""
    summary = compute_course_summary(
        "CSA101", _course_metrics(), _catalogue(), _school_summary(),
        _coursework(), _student_features(), _risk_indicators(),
    )
    assert summary.course_id == "CSA101"
    assert summary.course_title == "Programming Fundamentals"
    assert summary.school == "School of Technology"
    assert summary.department == "Computer Science and Applications"
    assert summary.difficulty_level == "medium"
    assert summary.enrollment == 3
    assert summary.avg_performance == 79.5
    assert summary.avg_attendance == 86.0
    assert summary.engagement_count == 1000
    assert summary.difficulty_adjusted_performance == 0.9
    assert summary.school_avg_performance == 70.4
    assert summary.school_avg_attendance == 76.2
    assert summary.students_with_signals == 2
    assert summary.students_assessed == 2


def test_compute_metadata_falls_back_to_metrics() -> None:
    """Missing catalogue rows fall back to metric fields, not blanks."""
    summary = compute_course_summary(
        "MGT101", _course_metrics(), _catalogue(), _school_summary(),
        [], [], [],
    )
    assert summary.course_title == "Prin Mgmt"
    assert summary.school == "School of Business"
    assert summary.department == "Management"
    assert summary.difficulty_level is None
    assert summary.enrollment == 1


def test_compute_coursework_summary() -> None:
    """Coursework math: submitted/late rates, score mix, item mix."""
    summary = compute_course_summary(
        "CSA101", _course_metrics(), _catalogue(), _school_summary(),
        _coursework(), _student_features(), _risk_indicators(),
    )
    assert summary.coursework is not None
    assert summary.coursework.items == 4
    assert summary.coursework.submitted == 3
    assert summary.coursework.late == 1
    assert summary.coursework.late_rate_pct == 33.3
    assert summary.coursework.avg_score_pct == 73.3
    assert summary.coursework.quizzes == 1
    assert summary.coursework.assignments == 3


def test_compute_coursework_empty_and_unsubmitted() -> None:
    """No items yield None; submissions missing yield no late rate."""
    summary = compute_course_summary(
        "CSA101", _course_metrics(), _catalogue(), _school_summary(),
        [], _student_features(), _risk_indicators(),
    )
    assert summary.coursework is None

    missing_only = [dict(_coursework()[3])]
    summary = compute_course_summary(
        "CSA101", _course_metrics(), _catalogue(), _school_summary(),
        missing_only, _student_features(), _risk_indicators(),
    )
    assert summary.coursework is not None
    assert summary.coursework.submitted == 0
    assert summary.coursework.late_rate_pct is None
    assert summary.coursework.avg_score_pct is None


def test_compute_course_trend_mix() -> None:
    """Trend mix splits declining/improving with a rounded mean."""
    summary = compute_course_summary(
        "CSA101", _course_metrics(), _catalogue(), _school_summary(),
        _coursework(), _student_features(), _risk_indicators(),
    )
    assert summary.trend is not None
    assert summary.trend.student_count == 2
    assert summary.trend.mean_score_trend == 1.0
    assert summary.trend.declining == 1
    assert summary.trend.improving == 1
    assert summary.trend.stable == 0


def test_compute_empty_inputs_yield_unavailable() -> None:
    """Empty gold data yields unavailable KPIs, never fabricated zeros."""
    summary = compute_course_summary("CSA101", [], [], [], [], [], [])
    assert summary.course_id == "CSA101"
    assert summary.course_title is None
    assert summary.enrollment is None
    assert summary.avg_performance is None
    assert summary.coursework is None
    assert summary.trend is None
    assert summary.students_with_signals is None


# ── Scope-aware fetching ───────────────────────────────────────────


class _RecordingCursor(list):
    """Cursor double supporting ``limit``."""

    def limit(self, n: int) -> list:
        return list(self)[:n]


def _matches(doc: dict, query: dict) -> bool:
    """Naive matcher supporting equality, $in and match-nothing."""
    for key, expected in query.items():
        if isinstance(expected, dict) and "$in" in expected:
            if doc.get(key) not in expected["$in"]:
                return False
        elif doc.get(key) != expected:
            return False
    return True


class _RecordingCollection:
    """Collection double recording queries."""

    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs
        self.queries: list[dict] = []

    def find(self, query: dict) -> _RecordingCursor:
        self.queries.append(dict(query))
        if query == {"_id": None}:
            return _RecordingCursor([])
        return _RecordingCursor([d for d in self._docs if _matches(d, query)])

    def count_documents(self, query: dict) -> int:
        return len(self.find(query))


class _RecordingDB(dict):
    """Database double supporting ``db[name]`` access."""

    def __getitem__(self, name: str):  # type: ignore[override]
        return super().__getitem__(name)


def _academic_records() -> list[dict]:
    return [
        {"student_id": "S1", "course_id": "CSA101", "semester_id": "S1"},
        {"student_id": "S2", "course_id": "CSA101", "semester_id": "S1"},
    ]


def _recording_access() -> tuple[DashboardDataAccess, _RecordingDB]:
    db: _RecordingDB = _RecordingDB(
        {
            "course_metrics": _RecordingCollection(_course_metrics()),
            "courses": _RecordingCollection(_catalogue()),
            "school_summary": _RecordingCollection(_school_summary()),
            "coursework": _RecordingCollection(_coursework()),
            "academic_records": _RecordingCollection(_academic_records()),
            "student_features": _RecordingCollection(_student_features()),
            "risk_indicators": _RecordingCollection(_risk_indicators()),
        }
    )
    return DashboardDataAccess(DashboardConfig(), db=db), db


def test_fetch_applies_course_semester_and_enrollment_join() -> None:
    """Course/semester filters narrow grain reads; students/risk join by enrollment."""
    access, db = _recording_access()
    records, error = fetch_course_data(
        access, Scope(level="university"), "S1", "CSA101"
    )
    assert error is None
    assert db["course_metrics"].queries == [{"course_id": "CSA101", "semester_id": "S1"}]
    assert db["courses"].queries == [{"course_id": "CSA101"}]
    assert db["coursework"].queries == [{"course_id": "CSA101"}]
    assert db["academic_records"].queries == [{"course_id": "CSA101", "semester_id": "S1"}]
    assert {d["student_id"] for d in records["student_features"]} == {"S1", "S2"}
    assert {d["student_id"] for d in records["risk_indicators"]} == {"S1"}


def test_fetch_school_scope_rejects_out_of_scope_course() -> None:
    """Picker values cannot escape school scopes."""
    access, _ = _recording_access()
    records, error = fetch_course_data(
        access, Scope(level="school", school="School of Technology"), None, "MGT101"
    )
    assert records == {}
    assert error is not None and "outside the allowed scope" in error


def test_fetch_faculty_scope_honors_assignments() -> None:
    """Faculty see assigned courses only."""
    access, _ = _recording_access()
    records, error = fetch_course_data(
        access, Scope(level="courses", courses=("CSA101",)), None, "CSA101"
    )
    assert error is None
    assert records["course_metrics"]

    records, error = fetch_course_data(
        access, Scope(level="courses", courses=("CSA101",)), None, "MGT101"
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
        records, error = fetch_course_data(
            access, Scope(level="university"), None, "CSA101"
        )
        assert records == {}
        assert error is not None and "course_metrics" in error
    finally:
        access.close()


# ── Headless rendering ─────────────────────────────────────────────


def _login_as(at, display_name: str, role: str) -> None:
    at.selectbox(key="acadexa_login_choice").set_value(
        f"{display_name} ({role})"
    ).run()
    at.button(key="acadexa_login_button").click().run()
    assert not at.exception


def _goto_courses(at) -> None:
    at.sidebar.radio[0].set_value("Courses").run()
    assert not at.exception


def test_courses_page_renders_gold_backed_sections() -> None:
    """Admin Courses page shows picker, KPIs, coursework, trends and risk."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_courses(at)

    assert at.header[0].value == "Courses"
    assert at.selectbox(key=COURSE_PICKER_SESSION_KEY).value == "CSA101"
    assert any("Course: CSA101" in s.value for s in at.subheader)
    labels = [m.label for m in at.metric]
    for expected in (
        "Enrollment",
        "Average Marks",
        "Average Attendance",
        "LMS Events",
        "Late Submission Rate",
        "Students With Risk Signals",
    ):
        assert expected in labels
    subheaders = [s.value for s in at.subheader]
    for expected in (
        "Course KPIs",
        "Coursework behavior",
        "Performance, attendance and engagement",
        "Trend",
        "Risk signals",
    ):
        assert expected in subheaders
    captions = [c.value for c in at.caption]
    assert any("Items, submissions, late rate" in text for text in captions)


def test_courses_picker_switches_course_content() -> None:
    """Switching the picker re-scopes the course header and tables."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_courses(at)

    at.selectbox(key=COURSE_PICKER_SESSION_KEY).set_value("MGT101").run()
    assert not at.exception
    assert any("Course: MGT101" in s.value for s in at.subheader)
    assert not any("Course: CSA101" in s.value for s in at.subheader)


def test_courses_faculty_scope_restricts_picker() -> None:
    """Faculty see assigned courses only, landing on course content."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "CSA Faculty Member", "Faculty")

    assert at.header[0].value == "Courses"
    assert at.selectbox(key=COURSE_PICKER_SESSION_KEY).options == [
        "CSA101",
        "CSA102",
    ]
    assert any("Course: CSA101" in s.value for s in at.subheader)


def test_courses_full_render_with_consistent_stub(tmp_path: Path) -> None:
    """Deterministic stub data exercises every section incl. methodology notes."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_course_full.py"
    script.write_text(
        "from acadexa.dashboard.config import DashboardConfig\n"
        "from acadexa.dashboard.data_access import DashboardDataAccess\n"
        "from acadexa.dashboard.pages.course import render_course_page\n"
        "from acadexa.dashboard.permissions import Scope\n"
        "\n"
        "class _Cursor(list):\n"
        "    def limit(self, n):\n"
        "        return list(self)[:n]\n"
        "\n"
        "def _matches(doc, query):\n"
        "    for k, v in query.items():\n"
        "        if isinstance(v, dict) and '$in' in v:\n"
        "            if doc.get(k) not in v['$in']:\n"
        "                return False\n"
        "        elif doc.get(k) != v:\n"
        "            return False\n"
        "    return True\n"
        "\n"
        "class _Collection:\n"
        "    def __init__(self, docs):\n"
        "        self._docs = docs\n"
        "    def find(self, query):\n"
        "        if query == {'_id': None}:\n"
        "            return _Cursor([])\n"
        "        return _Cursor([d for d in self._docs if _matches(d, query)])\n"
        "    def count_documents(self, query):\n"
        "        return len(self.find(query))\n"
        "\n"
        "class _DB(dict):\n"
        "    def __getitem__(self, name):\n"
        "        return super().__getitem__(name)\n"
        "\n"
        "db = _DB({\n"
        "    'course_metrics': _Collection([{'course_id': 'C1', 'semester_id': 'S1',"
        " 'avg_performance': 80.0, 'avg_attendance': 85.0, 'engagement_count': 100,"
        " 'enrolled_students_count': 2, 'course_title': 'T', 'school': 'S',"
        " 'department': 'D', 'course_difficulty': 0.5,"
        " 'difficulty_adjusted_performance': 0.2}]),\n"
        "    'courses': _Collection([{'course_id': 'C1', 'title': 'T',"
        " 'school': 'S', 'department': 'D', 'difficulty_level': 'medium'}]),\n"
        "    'school_summary': _Collection([{'school': 'S', 'department': 'D',"
        " 'student_count': 2, 'course_count': 1, 'avg_performance': 75.0,"
        " 'avg_attendance': 80.0, 'engagement_count': 100}]),\n"
        "    'coursework': _Collection([{'student_id': 'U1', 'course_id': 'C1',"
        " 'item_id': 'A1', 'item_type': 'ASSIGNMENT',"
        " 'submitted_at': '2025-09-01T10:00:00', 'score': 8, 'max_score': 10,"
        " 'attempts': 1, 'status': 'ON_TIME'}]),\n"
        "    'academic_records': _Collection([{'student_id': 'U1', 'course_id': 'C1',"
        " 'semester_id': 'S1'}, {'student_id': 'U2', 'course_id': 'C1',"
        " 'semester_id': 'S1'}]),\n"
        "    'student_features': _Collection([{'student_id': 'U1', 'semester_id': 'S1',"
        " 'attendance_mean': 80.0, 'engagement_count': 50,"
        " 'late_submission_rate': 0.0, 'score_trend': -2.0,"
        " 'avg_academic_score': 78.0, 'student_school': 'S'},"
        " {'student_id': 'U2', 'semester_id': 'S1', 'attendance_mean': 90.0,"
        " 'engagement_count': 60, 'late_submission_rate': 0.0, 'score_trend': 3.0,"
        " 'avg_academic_score': 82.0, 'student_school': 'S'}]),\n"
        "    'risk_indicators': _Collection([{'student_id': 'U1', 'signal_count': 1,"
        " 'low_attendance': False, 'lms_decline': False, 'late_submissions': True,"
        " 'marks_decline': False, 'low_quiz_activity': False}]),\n"
        "})\n"
        "access = DashboardDataAccess(DashboardConfig(), db=db)\n"
        "render_course_page(Scope(level='university'), {}, access)\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception, f"Course stub render raised: {at.exception}"
    assert any("Course: C1" in s.value for s in at.subheader)
    captions = [c.value for c in at.caption]
    assert any("association, not causation" in text for text in captions)
    assert any("not a failure prediction" in text for text in captions)
    assert any("1 declining" in text for text in captions)
    markdowns = [m.value for m in at.markdown]
    assert any("1 of 1" in text and "observed signals" in text for text in markdowns)


def test_courses_error_state_without_traceback(tmp_path: Path) -> None:
    """Unreachable data renders the controlled error state in-page."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_course_error.py"
    script.write_text(
        "from acadexa.dashboard.config import DashboardConfig\n"
        "from acadexa.dashboard.data_access import DashboardDataAccess\n"
        "from acadexa.dashboard.pages.course import render_course_page\n"
        "from acadexa.dashboard.permissions import Scope\n"
        "from acadexa.database import MongoDBConfig\n"
        "bad = MongoDBConfig(uri='mongodb://localhost:29999', "
        "database='test_course_unreachable', server_selection_timeout_ms=50, "
        "connect_timeout_ms=50)\n"
        "access = DashboardDataAccess(DashboardConfig(database=bad))\n"
        "render_course_page(Scope(level='university'), {}, access)\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception
    assert any("Unable to load course view" in e.value for e in at.error)
    assert all("Traceback" not in e.value for e in at.error)
