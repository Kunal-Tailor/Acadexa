"""Unit tests for the Student view (Task 12.4).

Covers student selection, scoped fetching with enrollment checks, pure
aggregation (profile, academic, attendance, coursework, LMS, trend,
five-rule breakdown) and headless rendering. Small fixtures only;
live-Mongo AppTest checks use the development data without asserting
exact values except stable seeded markers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard.config import DashboardConfig
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.pages.student import (
    STUDENT_PICKER_SESSION_KEY,
    available_students,
    compute_student_summary,
    fetch_student_data,
    resolve_selected_student,
)
from acadexa.dashboard.permissions import Scope

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"


def _student_features() -> list[dict]:
    """Two semesters of features for STU01."""
    return [
        {
            "student_id": "STU01",
            "semester_id": "S2",
            "attendance_mean": 80.0,
            "engagement_count": 200,
            "late_submission_rate": 0.5,
            "score_trend": -4.0,
            "avg_academic_score": 70.0,
            "student_school": "School of Technology",
            "student_department": "Computer Science",
        },
        {
            "student_id": "STU01",
            "semester_id": "S1",
            "attendance_mean": 90.0,
            "engagement_count": 300,
            "late_submission_rate": 0.0,
            "score_trend": 6.0,
            "avg_academic_score": 85.0,
            "student_school": "School of Technology",
            "student_department": "Computer Science",
        },
    ]


def _academic_records() -> list[dict]:
    """Two course records for STU01."""
    return [
        {"student_id": "STU01", "course_id": "CSA101", "semester_id": "S1",
         "internal_marks": 30, "midterm_marks": 25, "endterm_marks": 60,
         "final_grade": "B"},
        {"student_id": "STU01", "course_id": "CSA102", "semester_id": "S1",
         "internal_marks": 35, "midterm_marks": 28, "endterm_marks": 70,
         "final_grade": "A"},
    ]


def _enrollment_records() -> list[dict]:
    """STU01 enrolled in CSA101/CSA102 (S1)."""
    return [
        {"student_id": "STU01", "course_id": "CSA101", "semester_id": "S1"},
        {"student_id": "STU01", "course_id": "CSA102", "semester_id": "S1"},
    ]


def _academic_rows() -> list[dict]:
    """Two graded course records for STU01."""
    return [
        {"student_id": "STU01", "course_id": "CSA101", "semester_id": "S1",
         "internal_marks": 30, "midterm_marks": 25, "endterm_marks": 60,
         "final_grade": "B"},
        {"student_id": "STU01", "course_id": "CSA102", "semester_id": "S1",
         "internal_marks": 35, "midterm_marks": 28, "endterm_marks": 70,
         "final_grade": "A"},
    ]


def _attendance() -> list[dict]:
    """Three weekly observations (one zero-conducted guard row)."""
    return [
        {"student_id": "STU01", "course_id": "CSA101", "semester_id": "S1",
         "week_start": "2025-09-08", "classes_conducted": 4, "classes_attended": 3},
        {"student_id": "STU01", "course_id": "CSA101", "semester_id": "S1",
         "week_start": "2025-09-01", "classes_conducted": 4, "classes_attended": 4},
        {"student_id": "STU01", "course_id": "CSA102", "semester_id": "S1",
         "week_start": "2025-09-01", "classes_conducted": 0, "classes_attended": 0},
    ]


def _coursework() -> list[dict]:
    """Two submitted items (one late) plus one missing unscored item."""
    return [
        {"student_id": "STU01", "course_id": "CSA101", "item_id": "A01",
         "item_type": "ASSIGNMENT", "submitted_at": "2025-09-01T10:00:00",
         "score": 16, "max_score": 20, "attempts": 1, "status": "ON_TIME"},
        {"student_id": "STU01", "course_id": "CSA101", "item_id": "A02",
         "item_type": "ASSIGNMENT", "submitted_at": "2025-09-10T10:00:00",
         "score": 10, "max_score": 20, "attempts": 2, "status": "LATE"},
        {"student_id": "STU01", "course_id": "CSA102", "item_id": "Q01",
         "item_type": "QUIZ", "submitted_at": None,
         "score": None, "max_score": 10, "attempts": 0, "status": "MISSING"},
    ]


def _lms_events() -> list[dict]:
    """Three events across two activity types."""
    return [
        {"timestamp": "2025-09-01T10:00:00",
         "meta": {"student_id": "STU01", "course_id": "CSA101"},
         "activity_type": "VIDEO_VIEW"},
        {"timestamp": "2025-09-02T10:00:00",
         "meta": {"student_id": "STU01", "course_id": "CSA101"},
         "activity_type": "VIDEO_VIEW"},
        {"timestamp": "2025-09-03T10:00:00",
         "meta": {"student_id": "STU01", "course_id": "CSA102"},
         "activity_type": "QUIZ_ATTEMPT"},
    ]


def _risk_indicators() -> list[dict]:
    """Two assessments; the later week wins."""
    return [
        {"student_id": "STU01", "week_start": "2025-09-01", "signal_count": 1,
         "low_attendance": False, "lms_decline": False, "late_submissions": True,
         "marks_decline": False, "low_quiz_activity": False,
         "explanations": {"low_attendance": "old"}},
        {"student_id": "STU01", "week_start": "2025-09-08", "signal_count": 3,
         "low_attendance": True, "lms_decline": True, "late_submissions": False,
         "marks_decline": True, "low_quiz_activity": False,
         "explanations": {"low_attendance": "68.0% < 75% threshold"}},
    ]


# ── Student selection ──────────────────────────────────────────────


def test_available_students_sorted_unique() -> None:
    """Picker options derive from real feature rows, sorted."""
    assert available_students(_student_features()) == ["STU01"]
    assert available_students([]) == []
    assert available_students([{"semester_id": "S1"}]) == []


def test_resolve_selected_student() -> None:
    """Stored selections validate; unknown/empty falls back deterministically."""
    assert resolve_selected_student(["S1", "S2"], "S2") == "S2"
    assert resolve_selected_student(["S1", "S2"], "Nope") == "S1"
    assert resolve_selected_student(["S1", "S2"], None) == "S1"
    assert resolve_selected_student([], "S1") is None


# ── Pure aggregation ───────────────────────────────────────────────


def test_compute_student_summary() -> None:
    """Integrated summary aggregates exactly across all six domains."""
    summary = compute_student_summary(
        "STU01", _student_features(), _academic_rows(), _attendance(),
        _coursework(), _lms_events(), _risk_indicators(),
    )
    assert summary.student_id == "STU01"
    assert summary.school == "School of Technology"
    assert summary.department == "Computer Science"
    assert summary.semesters == ("S1", "S2")
    assert summary.avg_academic_score == 77.5
    assert summary.avg_attendance == 85.0
    assert summary.attendance_rate == 87.5
    assert summary.classes_attended == 7
    assert summary.classes_conducted == 8
    assert summary.lms_events == 3
    assert summary.lms_by_activity == {"VIDEO_VIEW": 2, "QUIZ_ATTEMPT": 1}
    assert summary.late_submission_rate == 0.2
    assert [(r.course_id, r.final_grade) for r in summary.academic_rows] == [
        ("CSA101", "B"), ("CSA102", "A"),
    ]
    assert [(p.week_start, p.attendance_rate) for p in summary.attendance_series] == [
        ("2025-09-01", 100.0), ("2025-09-01", None), ("2025-09-08", 75.0),
    ]
    assert len(summary.coursework_items) == 3
    assert summary.coursework_items[0].score_pct == 80.0
    assert summary.coursework_items[2].score_pct is None
    assert summary.coursework_submitted == 2
    assert summary.coursework_late == 1
    # Latest semester (S2) trend wins over list order.
    assert summary.score_trend == -4.0
    # Latest week assessment wins.
    assert summary.risk_count == 3
    assert summary.risk_triggered["low_attendance"] is True
    assert summary.risk_triggered["late_submissions"] is False
    assert summary.risk_explanations["low_attendance"] == "68.0% < 75% threshold"


def test_compute_empty_inputs_yield_unavailable() -> None:
    """Empty records yield unavailable KPIs, never fabricated zeros."""
    summary = compute_student_summary("STU01", [], [], [], [], [], [])
    assert summary.student_id == "STU01"
    assert summary.school is None
    assert summary.avg_academic_score is None
    assert summary.attendance_rate is None
    assert summary.classes_conducted == 0
    assert summary.lms_events is None
    assert summary.lms_by_activity == {}
    assert summary.academic_rows == ()
    assert summary.attendance_series == ()
    assert summary.coursework_items == ()
    assert summary.score_trend is None
    assert summary.risk_count is None
    assert summary.risk_triggered == {}


# ── Scope-aware fetching ───────────────────────────────────────────


class _RecordingCursor(list):
    """Cursor double supporting ``limit``."""

    def limit(self, n: int) -> list:
        return list(self)[:n]


def _lookup(doc: dict, dotted: str):
    """Resolve a dotted MongoDB path inside nested dicts."""
    current: object = doc
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _matches(doc: dict, query: dict) -> bool:
    """Naive matcher supporting equality, $in and match-nothing."""
    for key, expected in query.items():
        actual = _lookup(doc, key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
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


def _recording_access() -> tuple[DashboardDataAccess, _RecordingDB]:
    db: _RecordingDB = _RecordingDB(
        {
            "student_features": _RecordingCollection(_student_features()),
            "academic_records": _RecordingCollection(_enrollment_records()),
            "attendance": _RecordingCollection(_attendance()),
            "coursework": _RecordingCollection(_coursework()),
            "lms_events": _RecordingCollection(_lms_events()),
            "risk_indicators": _RecordingCollection(_risk_indicators()),
        }
    )
    return DashboardDataAccess(DashboardConfig(), db=db), db


def test_fetch_applies_student_semester_and_dotted_lms() -> None:
    """Semester narrows semester grain; LMS uses the meta student path."""
    access, db = _recording_access()
    records, error = fetch_student_data(
        access, Scope(level="university"), "S1", "STU01"
    )
    assert error is None
    assert db["student_features"].queries == [{"student_id": "STU01", "semester_id": "S1"}]
    assert db["academic_records"].queries == [{"student_id": "STU01", "semester_id": "S1"}]
    assert db["attendance"].queries == [{"student_id": "STU01", "semester_id": "S1"}]
    assert db["coursework"].queries == [{"student_id": "STU01"}]
    assert db["lms_events"].queries == [{"meta.student_id": "STU01"}]
    assert db["risk_indicators"].queries == [{"student_id": "STU01"}]
    assert len(records["lms_events"]) == 3
    assert len(records["risk_indicators"]) == 2


def test_fetch_school_scope_rejects_out_of_scope_student() -> None:
    """Picker values cannot escape school scopes."""
    access, _ = _recording_access()
    records, error = fetch_student_data(
        access, Scope(level="school", school="Somewhere Else"), None, "STU01"
    )
    assert records == {}
    assert error is not None and "outside the allowed scope" in error


def test_fetch_faculty_scope_checks_enrollment_and_restricts() -> None:
    """Faculty see enrolled students only, with coursework/LMS course-filtered."""
    mixed_lms = _lms_events() + [
        {"timestamp": "2025-09-04T10:00:00",
         "meta": {"student_id": "STU01", "course_id": "OTHER"},
         "activity_type": "LOGIN"},
    ]

    db: _RecordingDB = _RecordingDB(
        {
            "student_features": _RecordingCollection(_student_features()),
            "academic_records": _RecordingCollection(_academic_records()),
            "attendance": _RecordingCollection(_attendance()),
            "coursework": _RecordingCollection(
                _coursework()
                + [{"student_id": "STU01", "course_id": "OTHER", "item_id": "X01",
                    "item_type": "QUIZ", "submitted_at": "2025-09-01T10:00:00",
                    "score": 5, "max_score": 10, "attempts": 1, "status": "ON_TIME"}]
            ),
            "lms_events": _RecordingCollection(mixed_lms),
            "risk_indicators": _RecordingCollection(_risk_indicators()),
        }
    )
    faculty_access = DashboardDataAccess(DashboardConfig(), db=db)
    records, error = fetch_student_data(
        faculty_access, Scope(level="courses", courses=("CSA101", "CSA102")), None, "STU01"
    )
    assert error is None
    assert {d["course_id"] for d in records["coursework"]} == {"CSA101", "CSA102"}
    assert {(d.get("meta") or {}).get("course_id") for d in records["lms_events"]} <= {
        "CSA101",
        "CSA102",
    }

    records, error = fetch_student_data(
        faculty_access, Scope(level="courses", courses=("OTHER101",)), None, "STU01"
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
        records, error = fetch_student_data(
            access, Scope(level="university"), None, "STU01"
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


def _goto_students(at) -> None:
    at.sidebar.radio[0].set_value("Students").run()
    assert not at.exception


def test_students_page_renders_integrated_sections() -> None:
    """Admin Students page shows picker, KPIs and all six domains."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_students(at)

    assert at.header[0].value == "Students"
    assert at.selectbox(key=STUDENT_PICKER_SESSION_KEY).value == "STU010482"
    assert any("Student: STU010482" in s.value for s in at.subheader)
    labels = [m.label for m in at.metric]
    for expected in (
        "Average Score",
        "Attendance Rate",
        "LMS Events",
        "Late Submission Rate",
        "Score Trend",
        "Risk Signals",
    ):
        assert expected in labels
    subheaders = [s.value for s in at.subheader]
    for expected in (
        "Student KPIs",
        "Academic summary",
        "Attendance",
        "Coursework",
        "LMS engagement",
        "Recent trend",
        "Risk signals",
    ):
        assert expected in subheaders
    assert any("## 3 / 5" in m.value for m in at.markdown)
    captions = [c.value for c in at.caption]
    assert any("not a failure prediction" in text for text in captions)


def test_students_picker_switches_student_content() -> None:
    """Switching the picker re-scopes the profile header and risk card."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_students(at)

    at.selectbox(key=STUDENT_PICKER_SESSION_KEY).set_value("STU020001").run()
    assert not at.exception
    assert any("Student: STU020001" in s.value for s in at.subheader)
    assert not any("Student: STU010482" in s.value for s in at.subheader)
    assert any("## 0 / 5" in m.value for m in at.markdown)


def test_students_empty_scope_shows_explicit_states() -> None:
    """A scope with no gold data renders unavailable/empty states, no zeros."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "CET School Admin", "School / Department Admin")
    _goto_students(at)

    assert not at.exception
    assert any(
        "No student data is available for this selection." in i.value
        for i in at.info
    )


def test_students_error_state_without_traceback(tmp_path: Path) -> None:
    """Unreachable data renders the controlled error state in-page."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_student_error.py"
    script.write_text(
        "from acadexa.dashboard.config import DashboardConfig\n"
        "from acadexa.dashboard.data_access import DashboardDataAccess\n"
        "from acadexa.dashboard.pages.student import render_student_page\n"
        "from acadexa.dashboard.permissions import Scope\n"
        "from acadexa.database import MongoDBConfig\n"
        "bad = MongoDBConfig(uri='mongodb://localhost:29999', "
        "database='test_student_unreachable', server_selection_timeout_ms=50, "
        "connect_timeout_ms=50)\n"
        "access = DashboardDataAccess(DashboardConfig(database=bad))\n"
        "render_student_page(Scope(level='university'), {}, access)\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception
    assert any("Unable to load student view" in e.value for e in at.error)
    assert all("Traceback" not in e.value for e in at.error)
