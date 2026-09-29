"""Unit tests for the University Overview page (Task 12.1).

Covers pure gold aggregation, scope-aware fetching and headless rendering
of university KPIs, school comparison, academic/attendance/LMS overview,
trend summary and risk summary. Small fixtures only; live-Mongo AppTest
checks use the development gold data without asserting exact values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard.config import DashboardConfig
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.pages.university import (
    OVERVIEW_COLLECTIONS,
    compute_university_summary,
    fetch_university_data,
)
from acadexa.dashboard.permissions import Scope

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"


def _student_features() -> list[dict]:
    """Three students across two schools (mirrors live gold shapes)."""
    return [
        {
            "student_id": "STU010482",
            "semester_id": "S1",
            "attendance_mean": 78.5,
            "engagement_count": 412,
            "late_submission_rate": 0.2,
            "score_trend": -12.0,
            "avg_academic_score": 71.2,
            "student_school": "School of Technology",
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
            "student_school": "School of Technology",
            "student_department": "Computer Science",
        },
        {
            "student_id": "STU030001",
            "semester_id": "S2",
            "attendance_mean": 83.5,
            "engagement_count": 380,
            "late_submission_rate": 0.125,
            "score_trend": 0.0,
            "avg_academic_score": 76.5,
            "student_school": "School of Business",
            "student_department": "Management",
        },
    ]


def _course_metrics() -> list[dict]:
    """Four course × semester rows across two schools."""
    return [
        {
            "course_id": "CSA101",
            "semester_id": "S1",
            "avg_performance": 71.2,
            "avg_attendance": 82.4,
            "engagement_count": 500,
            "school": "School of Technology",
        },
        {
            "course_id": "CSA102",
            "semester_id": "S1",
            "avg_performance": 80.0,
            "avg_attendance": 88.0,
            "engagement_count": 212,
            "school": "School of Technology",
        },
        {
            "course_id": "MGT101",
            "semester_id": "S2",
            "avg_performance": 76.5,
            "avg_attendance": 83.5,
            "engagement_count": 380,
            "school": "School of Business",
        },
        {
            "course_id": "MGT102",
            "semester_id": "S2",
            "avg_performance": 70.0,
            "avg_attendance": 79.0,
            "engagement_count": 100,
            "school": "School of Business",
        },
    ]


def _school_summary() -> list[dict]:
    """Three department roll-ups across two schools."""
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
            "avg_performance": 70.0,
            "avg_attendance": 80.0,
            "engagement_count": 100,
        },
        {
            "school": "School of Business",
            "department": "Management",
            "student_count": 1,
            "course_count": 2,
            "avg_performance": 76.5,
            "avg_attendance": 83.5,
            "engagement_count": 380,
        },
    ]


def _risk_indicators() -> list[dict]:
    """Three assessments plus one orphan outside the student set."""
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
            "student_id": "STU030001",
            "signal_count": 1,
            "low_attendance": False,
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


# ── Pure aggregation ───────────────────────────────────────────────


def test_compute_university_kpis() -> None:
    """KPIs aggregate exactly from gold records (no hard-coded values)."""
    summary = compute_university_summary(
        _student_features(), _course_metrics(), _school_summary(), _risk_indicators()
    )
    assert summary.student_count == 3
    assert summary.course_count == 4
    assert summary.avg_attendance == 84.0
    assert summary.avg_performance == 77.6
    assert summary.avg_engagement == 364.0
    assert summary.total_lms_events == 1092
    assert summary.students_with_signals == 3


def test_compute_school_aggregation() -> None:
    """Department roll-ups combine into one row per school."""
    summary = compute_university_summary(
        _student_features(), _course_metrics(), _school_summary(), _risk_indicators()
    )
    assert [row.school for row in summary.schools] == [
        "School of Business",
        "School of Technology",
    ]
    tech = next(r for r in summary.schools if r.school == "School of Technology")
    assert tech.student_count == 3
    assert tech.course_count == 2
    assert tech.avg_performance == 72.9
    assert tech.avg_attendance == 81.2
    assert tech.engagement_count == 812


def test_compute_trend_summary() -> None:
    """Trend counts split declining/improving/stable with a rounded mean."""
    summary = compute_university_summary(
        _student_features(), _course_metrics(), _school_summary(), _risk_indicators()
    )
    assert summary.trend is not None
    assert summary.trend.student_count == 3
    assert summary.trend.mean_score_trend == -2.3
    assert summary.trend.declining == 1
    assert summary.trend.improving == 1
    assert summary.trend.stable == 1


def test_compute_risk_summary() -> None:
    """Risk summary counts assessed/flagged, zero-filled distribution, triggers."""
    summary = compute_university_summary(
        _student_features(), _course_metrics(), _school_summary(), []
    )
    assert summary.students_with_signals is None
    assert summary.risk is None

    summary = compute_university_summary(
        _student_features(), _course_metrics(), _school_summary(), _risk_indicators()
    )
    assert summary.risk is not None
    assert summary.risk.assessed == 4
    assert summary.risk.flagged == 3
    assert summary.risk.distribution == {0: 1, 1: 1, 2: 0, 3: 1, 4: 0, 5: 1}
    assert summary.risk.signal_triggers == {
        "low_attendance": 2,
        "lms_decline": 2,
        "late_submissions": 2,
        "marks_decline": 2,
        "low_quiz_activity": 1,
    }


def test_compute_empty_inputs_yield_unavailable() -> None:
    """Empty gold data yields unavailable KPIs, never fabricated zeros."""
    summary = compute_university_summary([], [], [], [])
    assert summary.student_count is None
    assert summary.course_count is None
    assert summary.avg_attendance is None
    assert summary.avg_performance is None
    assert summary.avg_engagement is None
    assert summary.total_lms_events is None
    assert summary.students_with_signals is None
    assert summary.schools == ()
    assert summary.trend is None
    assert summary.risk is None


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


def test_fetch_university_scope_returns_all_in_scope() -> None:
    """University scope reads everything; orphan risk rows are excluded."""
    access, _ = _recording_access()
    records, error = fetch_university_data(
        access, Scope(level="university"), semester=None
    )
    assert error is None
    assert {d["student_id"] for d in records["student_features"]} == {
        "STU010482",
        "STU020001",
        "STU030001",
    }
    assert len(records["course_metrics"]) == 4
    assert len(records["school_summary"]) == 3
    # STU999999 has no student_features row, so it is out of scope.
    assert {d["student_id"] for d in records["risk_indicators"]} == {
        "STU010482",
        "STU020001",
        "STU030001",
    }


def test_fetch_school_scope_filters_and_joins_risk() -> None:
    """School scope filters hierarchy collections and joins risk in Python."""
    access, db = _recording_access()
    records, error = fetch_university_data(
        access, Scope(level="school", school="School of Technology"), semester=None
    )
    assert error is None
    assert db["student_features"].queries == [
        {"student_school": "School of Technology"}
    ]
    assert db["school_summary"].queries == [{"school": "School of Technology"}]
    assert {d["student_id"] for d in records["student_features"]} == {
        "STU010482",
        "STU020001",
    }
    assert {d["student_id"] for d in records["risk_indicators"]} == {
        "STU010482",
        "STU020001",
    }


def test_fetch_semester_applies_only_to_semester_grain() -> None:
    """Semester filter narrows student/course reads, not school/risk reads."""
    access, db = _recording_access()
    records, error = fetch_university_data(
        access, Scope(level="university"), semester="S1"
    )
    assert error is None
    assert db["student_features"].queries == [{"semester_id": "S1"}]
    assert db["course_metrics"].queries == [{"semester_id": "S1"}]
    assert db["school_summary"].queries == [{}]
    assert {d["student_id"] for d in records["student_features"]} == {
        "STU010482",
        "STU020001",
    }


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
        records, error = fetch_university_data(
            access, Scope(level="university"), semester=None
        )
        assert records == {}
        assert error is not None and "student_features" in error
    finally:
        access.close()


def test_overview_collections_cover_gold_contract() -> None:
    """The page reads exactly the four gold collections."""
    assert set(OVERVIEW_COLLECTIONS) == {
        "student_features",
        "course_metrics",
        "school_summary",
        "risk_indicators",
    }


# ── Headless rendering ─────────────────────────────────────────────


def _login_as(at, display_name: str, role: str) -> None:
    at.selectbox(key="acadexa_login_choice").set_value(
        f"{display_name} ({role})"
    ).run()
    at.button(key="acadexa_login_button").click().run()
    assert not at.exception


def test_overview_renders_gold_backed_sections() -> None:
    """Admin overview shows KPIs, school comparison, trends and risk summary."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")

    labels = [m.label for m in at.metric]
    for expected in (
        "Active Students",
        "Average Attendance",
        "Average Performance",
        "Average Engagement",
        "Total LMS Events",
        "Students With Risk Signals",
    ):
        assert expected in labels
    subheaders = [s.value for s in at.subheader]
    for expected in (
        "University KPIs",
        "School comparison",
        "Academic vs engagement overview",
        "Trend summary",
        "Risk summary",
    ):
        assert expected in subheaders
    captions = [c.value for c in at.caption]
    assert any("not a failure prediction" in text for text in captions)
    assert any("association, not causation" in text for text in captions)
    assert len(at.dataframe) >= 1


def test_overview_empty_scope_shows_explicit_states() -> None:
    """A scope with no gold data renders unavailable/empty states, no zeros."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "CET School Admin", "School / Department Admin")

    assert not at.exception
    assert any(m.value == "Data unavailable" for m in at.metric)
    assert any(
        "No school data is available for this selection." in i.value for i in at.info
    )


def test_overview_error_state_without_traceback(tmp_path: Path) -> None:
    """Unreachable data renders the controlled error state in-page."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_overview_error.py"
    script.write_text(
        "from acadexa.dashboard.config import DashboardConfig\n"
        "from acadexa.dashboard.data_access import DashboardDataAccess\n"
        "from acadexa.dashboard.pages.university import render_university_page\n"
        "from acadexa.dashboard.permissions import Scope\n"
        "from acadexa.database import MongoDBConfig\n"
        "bad = MongoDBConfig(uri='mongodb://localhost:29999', "
        "database='test_overview_unreachable', server_selection_timeout_ms=50, "
        "connect_timeout_ms=50)\n"
        "access = DashboardDataAccess(DashboardConfig(database=bad))\n"
        "render_university_page(Scope(level='university'), {}, access)\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception
    assert any("Unable to load university overview" in e.value for e in at.error)
    assert all("Traceback" not in e.value for e in at.error)
