"""Unit tests for the Analysis view (Task 12.5).

Covers pure rank-correlation statistics, interpretation boundaries,
scoped fetching, recovery comparison and headless rendering of
correlations, trends, engagement, recovery and methodology sections.
Small fixtures only; live-Mongo AppTest checks use the development data
without asserting exact values except stable seeded markers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard.config import DashboardConfig
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.pages.analysis import (
    compute_analysis_summary,
    compute_correlations,
    compute_recovery,
    fetch_analysis_data,
    interpret_association,
    load_ground_truth_registry,
    spearman_rank_correlation,
)
from acadexa.dashboard.permissions import Scope

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"


def _features() -> list[dict]:
    """Five students with monotonic attendance/score and noisy engagement."""
    return [
        {"student_id": f"S{i}", "semester_id": "S1",
         "attendance_mean": 60.0 + i * 5.0,
         "engagement_count": [120, 400, 200, 350, 150][i],
         "late_submission_rate": 0.5 - i * 0.1,
         "score_trend": [-8.0, 2.0, 0.0, 5.0, -1.0][i],
         "avg_academic_score": 60.0 + i * 5.0,
         "student_school": "School of Technology"}
        for i in range(5)
    ]


def _risk() -> list[dict]:
    """Two assessments with one of each decline flag set."""
    return [
        {"student_id": "S0", "signal_count": 2, "lms_decline": True,
         "marks_decline": False},
        {"student_id": "S1", "signal_count": 1, "lms_decline": False,
         "marks_decline": True},
    ]


def _registry() -> dict:
    """Minimal registry-shaped fixture (read, never modified)."""
    return {
        "seed": 42,
        "planted_relationships": [
            {"id": "attendance_marks", "relationship_type": "planted",
             "expected_direction": "positive", "expected_strength": "moderate"},
            {"id": "late_submissions_marks", "relationship_type": "planted",
             "expected_direction": "negative", "expected_strength": "moderate"},
        ],
        "decoy_relationship": {
            "id": "decoy_forum_marks", "relationship_type": "decoy",
            "expected_direction": "none", "expected_strength": "none"},
    }


# ── Pure statistics ────────────────────────────────────────────────


def test_spearman_perfect_and_degenerate_cases() -> None:
    """Rank correlation is exact on monotonic data, None when degenerate."""
    assert spearman_rank_correlation([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) == 1.0
    assert spearman_rank_correlation([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]) == -1.0
    # Tied ranks still correlate perfectly when order agrees.
    assert spearman_rank_correlation([1.0, 1.0, 2.0, 3.0], [5.0, 5.0, 6.0, 7.0]) == 1.0
    assert spearman_rank_correlation([1.0, 2.0], [1.0, 2.0]) is None
    assert spearman_rank_correlation([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]) is None
    assert spearman_rank_correlation([], []) is None


def test_interpretation_matches_canonical_boundaries() -> None:
    """Local interpretation tracks analytics.correlation exactly."""
    from acadexa.analytics.correlation import (
        interpret_spearman_association as canonical,
    )

    for value in [None, 0.9, 0.5, 0.25, 0.1, 0.05, 0.0, -0.05, -0.1,
                  -0.2, -0.3, -0.5, -0.9]:
        assert interpret_association(value) == canonical(value)


def test_compute_correlations_known_directions() -> None:
    """Planted directions surface with the designed signs on fixtures."""
    results = {c.relationship_id: c for c in compute_correlations(_features())}
    assert results["attendance_marks"].spearman_rho == 1.0
    assert results["attendance_marks"].sample_size == 5
    assert results["late_submissions_marks"].spearman_rho == -1.0
    assert results["lms_engagement_marks"].sample_size == 5
    assert all(c.interpretation for c in results.values())


def test_compute_correlations_empty_inputs() -> None:
    """No rows yield uncomputable correlations, never zeros."""
    results = compute_correlations([])
    assert all(c.spearman_rho is None and c.sample_size == 0 for c in results)
    assert all(c.interpretation == "Insufficient variation to determine association"
               for c in results)


# ── Recovery comparison ────────────────────────────────────────────


def test_compute_recovery_statuses() -> None:
    """Planted/decoy expectations classify via the shared recovery logic."""
    correlations = compute_correlations(_features())
    entries, summary = compute_recovery(_registry(), correlations, "overall")
    by_id = {e["relationship_id"]: e for e in entries}
    assert by_id["attendance_marks"]["status"] == "recovered"
    assert by_id["late_submissions_marks"]["status"] == "recovered"
    assert by_id["decoy_forum_marks"]["status"] == "not_evaluated"
    assert summary["recovered"] == 2
    assert summary["not_evaluated"] == 1
    assert all("caus" not in e["interpretation"].lower() for e in entries)


def test_compute_recovery_without_registry() -> None:
    """Missing registry yields empty recovery, never fabricated entries."""
    assert compute_recovery(None, compute_correlations(_features()), "overall") == ((), {})


def test_load_ground_truth_registry_tracked_file() -> None:
    """The tracked registry loads with planted and decoy relationships."""
    registry, error = load_ground_truth_registry()
    assert error is None
    assert registry is not None
    assert registry["seed"] == 42
    assert {r["id"] for r in registry["planted_relationships"]} >= {
        "attendance_marks", "lms_engagement_marks", "late_submissions_marks",
    }
    assert registry["decoy_relationship"]["id"] == "decoy_forum_marks"


def test_load_ground_truth_registry_missing_file(tmp_path: Path) -> None:
    """Missing registry surfaces a controlled message, never an exception."""
    registry, error = load_ground_truth_registry(tmp_path / "nope.json")
    assert registry is None
    assert error is not None and "not found" in error


# ── Summary aggregation ────────────────────────────────────────────


def test_compute_analysis_summary() -> None:
    """Trend, decline-rate and engagement stats aggregate exactly."""
    summary = compute_analysis_summary(_features(), _risk(), _registry(), "overall")
    assert summary.student_count == 5
    assert len(summary.correlations) == 3
    assert summary.mean_score_trend == -0.4
    assert (summary.declining, summary.improving, summary.stable) == (2, 2, 1)
    assert summary.lms_decline_rate == 50.0
    assert summary.marks_decline_rate == 50.0
    assert summary.mean_engagement == 244.0
    assert summary.total_engagement == 1220
    assert summary.recovery_summary["recovered"] == 2


def test_compute_analysis_summary_empty() -> None:
    """Empty inputs yield zero students and unavailable stats."""
    summary = compute_analysis_summary([], [], None, "overall")
    assert summary.student_count == 0
    assert summary.mean_score_trend is None
    assert summary.lms_decline_rate is None
    assert summary.total_engagement is None
    assert summary.recovery_entries == ()
    assert summary.recovery_summary == {}


# ── Scope-aware fetching ───────────────────────────────────────────


class _RecordingCursor(list):
    """Cursor double supporting ``limit``."""

    def limit(self, n: int) -> list:
        return list(self)[:n]


def _matches(doc: dict, query: dict) -> bool:
    """Naive matcher supporting equality, $in and match-nothing."""
    for key, expected in query.items():
        actual = doc.get(key)
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
            "student_features": _RecordingCollection(_features()),
            "risk_indicators": _RecordingCollection(_risk()),
            "academic_records": _RecordingCollection(
                [{"student_id": "S0", "course_id": "CSA101", "semester_id": "S1"}]
            ),
        }
    )
    return DashboardDataAccess(DashboardConfig(), db=db), db


def test_fetch_applies_scope_and_semester() -> None:
    """School/semester filters narrow feature reads; risk joins in Python."""
    access, db = _recording_access()
    records, error = fetch_analysis_data(
        access, Scope(level="school", school="School of Technology"), "S1"
    )
    assert error is None
    assert db["student_features"].queries == [
        {"student_school": "School of Technology", "semester_id": "S1"}
    ]
    assert len(records["student_features"]) == 5
    assert len(records["risk_indicators"]) == 2


def test_fetch_faculty_scope_resolves_enrollment() -> None:
    """Course-scoped users analyse enrolled students only."""
    access, _ = _recording_access()
    records, error = fetch_analysis_data(
        access, Scope(level="courses", courses=("CSA101",)), None
    )
    assert error is None
    assert [d["student_id"] for d in records["student_features"]] == ["S0"]
    assert [d["student_id"] for d in records["risk_indicators"]] == ["S0"]


def test_fetch_faculty_scope_empty_enrollment() -> None:
    """No enrolled students yields empty sections, not an error."""
    access, _ = _recording_access()
    records, error = fetch_analysis_data(
        access, Scope(level="courses", courses=("NOPE101",)), None
    )
    assert error is None
    assert records == {"student_features": [], "risk_indicators": []}


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
        records, error = fetch_analysis_data(
            access, Scope(level="university"), None
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


def _goto_analysis(at) -> None:
    at.sidebar.radio[0].set_value("Analysis").run()
    assert not at.exception


def test_analysis_page_renders_gold_backed_sections() -> None:
    """Admin Analysis page shows correlations, trends, recovery, methodology."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_analysis(at)

    assert at.header[0].value == "Analysis"
    subheaders = [s.value for s in at.subheader]
    for expected in (
        "Analysis overview",
        "Factor relationships",
        "Trend detection",
        "Engagement analysis",
        "Ground-truth recovery",
        "Methodology",
    ):
        assert expected in subheaders
    tables = [str(frame.value) for frame in at.dataframe]
    assert any("attendance_marks" in table for table in tables)
    assert any("recovered" in table for table in tables)
    captions = [c.value for c in at.caption]
    assert any("association, not causation" in text for text in captions)
    assert any("fully synthetic" in text for text in captions)


def test_analysis_faculty_scope_renders_without_error() -> None:
    """Course-scoped analysis renders sections or honest empty states."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "CSA Faculty Member", "Faculty")
    _goto_analysis(at)

    assert not at.exception
    assert at.header[0].value == "Analysis"
    assert any(s.value == "Factor relationships" for s in at.subheader)


def test_analysis_error_state_without_traceback(tmp_path: Path) -> None:
    """Unreachable data renders the controlled error state in-page."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_analysis_error.py"
    script.write_text(
        "from acadexa.dashboard.config import DashboardConfig\n"
        "from acadexa.dashboard.data_access import DashboardDataAccess\n"
        "from acadexa.dashboard.pages.analysis import render_analysis_page\n"
        "from acadexa.dashboard.permissions import Scope\n"
        "from acadexa.database import MongoDBConfig\n"
        "bad = MongoDBConfig(uri='mongodb://localhost:29999', "
        "database='test_analysis_unreachable', server_selection_timeout_ms=50, "
        "connect_timeout_ms=50)\n"
        "access = DashboardDataAccess(DashboardConfig(database=bad))\n"
        "render_analysis_page(Scope(level='university'), {}, access)\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception
    assert any("Unable to load analysis view" in e.value for e in at.error)
    assert all("Traceback" not in e.value for e in at.error)
