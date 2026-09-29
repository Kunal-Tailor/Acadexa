"""Unit tests for the Streamlit dashboard foundation (Tasks 11.1–11.3).

Covers shared configuration/data-access (11.1), dummy login + session
state with the four approved roles (11.2) and centralized role/scope
resolution (11.3), plus an AppTest run proving the app starts and the
login → authenticated-shell flow works. Small fixtures only; MongoDB live
checks skip when unreachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.dashboard import auth, permissions, session
from acadexa.dashboard.auth import (
    APPROVED_ROLES,
    AuthConfigError,
    User,
    authenticate,
    load_dummy_users,
)
from acadexa.dashboard.config import (
    APP_TITLE,
    DashboardConfig,
    DEFAULT_DUMMY_USERS_PATH,
)
from acadexa.dashboard.data_access import DashboardDataAccess, DataAccessError
from acadexa.dashboard.permissions import (
    CAP_VIEW_ANALYSIS,
    CAP_VIEW_BENCHMARKS,
    CAP_VIEW_COURSE,
    CAP_VIEW_QUALITY,
    CAP_VIEW_STUDENT,
    CAP_VIEW_UNIVERSITY,
    Scope,
    build_mongo_scope_filter,
    can,
    capabilities_for,
    describe_scope,
    resolve_scope,
)
from acadexa.config.loader import PROJECT_ROOT
from acadexa.database import MongoDBConfig, check_connection

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"


@pytest.fixture(scope="module")
def users() -> dict[str, User]:
    """Configured dummy users from the tracked TOML."""
    return load_dummy_users()


# ── 11.2: dummy login ──────────────────────────────────────────────


def test_dummy_users_cover_exactly_the_four_approved_roles(users) -> None:
    """Configured users span exactly the four approved roles."""
    assert set(users) == {"admin", "cet.admin", "faculty.csa", "analyst"}
    assert {u.role for u in users.values()} == set(APPROVED_ROLES)
    assert users["admin"].role == "University Admin"
    assert users["cet.admin"].role == "School / Department Admin"
    assert users["faculty.csa"].role == "Faculty"
    assert users["analyst"].role == "Academic Analyst"


def test_authenticate_known_and_unknown_users(users) -> None:
    """Known usernames resolve; unknown/empty usernames do not."""
    user = authenticate("admin", users)
    assert isinstance(user, User)
    assert user.username == "admin"
    assert authenticate("ghost", users) is None
    assert authenticate("", users) is None
    assert authenticate(None, users) is None


def test_load_dummy_users_rejects_unapproved_role(tmp_path: Path) -> None:
    """Unapproved roles fail fast instead of entering the session."""
    bad = tmp_path / "dummy_users.toml"
    bad.write_text(
        '[[users]]\nusername = "x"\ndisplay_name = "X"\nrole = "Superuser"\n',
        encoding="utf-8",
    )
    with pytest.raises(AuthConfigError, match="unapproved role"):
        load_dummy_users(bad)


def test_load_dummy_users_rejects_duplicates(tmp_path: Path) -> None:
    """Duplicate usernames fail fast."""
    dup = tmp_path / "dummy_users.toml"
    dup.write_text(
        '[[users]]\nusername = "a"\nrole = "Faculty"\n'
        '[[users]]\nusername = "a"\nrole = "Faculty"\n',
        encoding="utf-8",
    )
    with pytest.raises(AuthConfigError, match="Duplicate"):
        load_dummy_users(dup)


def test_user_dict_roundtrip(users) -> None:
    """Session-safe serialization preserves role and scope fields."""
    original = users["faculty.csa"]
    restored = User.from_dict(original.to_dict())
    assert restored == original
    assert restored.courses == ("CSA101", "CSA102")


# ── 11.2: session state ────────────────────────────────────────────


def test_session_login_logout_cycle(users) -> None:
    """Login establishes the session; logout clears it (plain-dict state)."""
    state: dict = {}
    assert session.is_authenticated(state) is False
    assert session.get_current_user(state) is None

    session.login(state, users["admin"])
    assert session.is_authenticated(state) is True
    current = session.get_current_user(state)
    assert current is not None
    assert current.username == "admin"
    assert current.role == "University Admin"
    # Stored value must be a plain dict (Streamlit-serializable).
    assert isinstance(state[session.SESSION_USER_KEY], dict)

    session.logout(state)
    assert session.is_authenticated(state) is False
    assert session.get_current_user(state) is None


# ── 11.3: centralized role/scope resolution ────────────────────────


def test_resolve_scope_per_role(users) -> None:
    """Each role resolves to its documented analytical scope."""
    assert resolve_scope(users["admin"]) == permissions.Scope(level="university")
    assert resolve_scope(users["analyst"]) == permissions.Scope(level="university")

    school_scope = resolve_scope(users["cet.admin"])
    assert school_scope.level == "school"
    assert school_scope.school == "School of Computer Engineering & Technology"

    faculty_scope = resolve_scope(users["faculty.csa"])
    assert faculty_scope.level == "courses"
    assert faculty_scope.courses == ("CSA101", "CSA102")


def test_capabilities_follow_feature_mapping(users) -> None:
    """Capability sets match docs/features.md §20 (single source of truth)."""
    admin_caps = capabilities_for("University Admin")
    assert {
        CAP_VIEW_UNIVERSITY,
        CAP_VIEW_COURSE,
        CAP_VIEW_STUDENT,
        CAP_VIEW_ANALYSIS,
        CAP_VIEW_QUALITY,
        CAP_VIEW_BENCHMARKS,
    } <= admin_caps

    assert can(users["admin"], CAP_VIEW_BENCHMARKS) is True
    assert can(users["faculty.csa"], CAP_VIEW_COURSE) is True
    assert can(users["faculty.csa"], CAP_VIEW_UNIVERSITY) is False
    assert can(users["faculty.csa"], CAP_VIEW_BENCHMARKS) is False
    assert can(users["analyst"], CAP_VIEW_ANALYSIS) is True
    assert can(users["analyst"], CAP_VIEW_COURSE) is False
    assert can(users["analyst"], CAP_VIEW_STUDENT) is False
    assert can(users["cet.admin"], CAP_VIEW_QUALITY) is True
    assert can(users["cet.admin"], CAP_VIEW_UNIVERSITY) is False
    assert capabilities_for("Superuser") == frozenset()


def test_build_mongo_scope_filter_shapes(users) -> None:
    """Scope filters express university/school/course boundaries for queries."""
    assert build_mongo_scope_filter(resolve_scope(users["admin"])) == {}
    assert build_mongo_scope_filter(resolve_scope(users["analyst"])) == {}
    assert build_mongo_scope_filter(resolve_scope(users["cet.admin"])) == {
        "school": "School of Computer Engineering & Technology"
    }
    assert build_mongo_scope_filter(resolve_scope(users["faculty.csa"])) == {
        "course_id": {"$in": ["CSA101", "CSA102"]}
    }
    assert build_mongo_scope_filter(Scope(level="courses", courses=())) == {
        "_id": None
    }
    dept = Scope(
        level="department",
        school="School of Business",
        department="Management Studies",
    )
    assert build_mongo_scope_filter(dept) == {
        "school": "School of Business",
        "department": "Management Studies",
    }


def test_describe_scope_is_human_readable(users) -> None:
    """Sidebar/header scope summaries name the resolved scope."""
    assert "all schools" in describe_scope(resolve_scope(users["admin"]))
    assert "Computer Engineering" in describe_scope(
        resolve_scope(users["cet.admin"])
    )
    assert "CSA101" in describe_scope(resolve_scope(users["faculty.csa"]))


def test_resolve_scope_rejects_unapproved_role() -> None:
    """Unapproved roles cannot reach page permission checks."""
    with pytest.raises(ValueError, match="unapproved role"):
        resolve_scope(
            User(username="x", display_name="X", role="Superuser")
        )


# ── 11.1: shared configuration ─────────────────────────────────────


def test_dashboard_config_defaults() -> None:
    """Dashboard defaults reference gold collections and the tracked TOML."""
    cfg = DashboardConfig()
    assert cfg.app_title == APP_TITLE
    assert "RAS University" in cfg.app_subtitle
    assert set(cfg.gold_collections) == {
        "student_features",
        "course_metrics",
        "school_summary",
        "risk_indicators",
    }
    assert cfg.dummy_users_path == DEFAULT_DUMMY_USERS_PATH
    assert cfg.dummy_users_path.is_file()
    assert cfg.default_query_limit > 0


def test_dashboard_config_from_env_uses_environment(monkeypatch) -> None:
    """MongoDB settings come from the environment, never hard-coded secrets."""
    monkeypatch.setenv("MONGODB_DATABASE", "test_acadexa_dashboard_cfg")
    cfg = DashboardConfig.from_env()
    assert cfg.database.database == "test_acadexa_dashboard_cfg"


# ── 11.1: shared data-access layer ─────────────────────────────────


class _StubCursor(list):
    """Minimal cursor double supporting ``limit``."""

    def limit(self, n: int) -> list:
        return list(self)[:n]


class _StubCollection:
    """Minimal collection double with naive equality filtering."""

    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def find(self, query: dict) -> _StubCursor:
        return _StubCursor(
            [d for d in self._docs if all(d.get(k) == v for k, v in query.items())]
        )

    def count_documents(self, query: dict) -> int:
        return len(self.find(query))


class _StubDB(dict):
    """Minimal database double supporting ``db[name]`` access."""

    def __getitem__(self, name: str) -> _StubCollection:  # type: ignore[override]
        return super().__getitem__(name)


def _stub_access() -> DashboardDataAccess:
    db: _StubDB = _StubDB(
        {
            "student_features": _StubCollection(
                [
                    {"student_id": "STU01", "school": "CET"},
                    {"student_id": "STU02", "school": "SOM"},
                ]
            ),
            "course_metrics": _StubCollection([]),
            "school_summary": _StubCollection([]),
            "risk_indicators": _StubCollection([]),
        }
    )
    return DashboardDataAccess(DashboardConfig(), db=db)


def test_fetch_applies_scope_filter_and_limit() -> None:
    """Bounded reads honor scope filters without touching MongoDB."""
    data = _stub_access()
    records, error = data.fetch("student_features", {"school": "CET"}, limit=10)
    assert error is None
    assert [r["student_id"] for r in records] == ["STU01"]

    records, error = data.fetch("student_features", {}, limit=1)
    assert error is None
    assert len(records) == 1


def test_fetch_rejects_unknown_collection() -> None:
    """Programmer errors fail fast instead of querying arbitrary collections."""
    with pytest.raises(DataAccessError, match="Unknown dashboard collection"):
        _stub_access().fetch("enrollments")


def test_unreachable_mongo_returns_controlled_error() -> None:
    """Database failures yield ([], error) — never fabricated values."""
    bad_db = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_acadexa_dashboard_unreachable",
        server_selection_timeout_ms=50,
        connect_timeout_ms=50,
    )
    data = DashboardDataAccess(DashboardConfig(database=bad_db))
    try:
        records, error = data.fetch("student_features", {}, limit=5)
        assert records == []
        assert error is not None and "student_features" in error

        count, count_error = data.collection_count("student_features")
        assert count == 0
        assert count_error is not None

        status = data.gold_status()
        assert set(status) == set(DashboardConfig().gold_collections)
        assert all(info["count"] == 0 and info["error"] for info in status.values())
    finally:
        data.close()


def test_gold_status_live_shape() -> None:
    """Live serving-layer status reports per-collection counts or errors."""
    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")
    data = DashboardDataAccess(cfg)
    try:
        status = data.gold_status()
        assert set(status) == set(cfg.gold_collections)
        for info in status.values():
            assert info["count"] >= 0
            assert ("error" in info) and (info["error"] is None or info["count"] == 0)
    finally:
        data.close()


# ── 11.1: application entry point starts ───────────────────────────


def test_app_starts_with_login_screen() -> None:
    """The Streamlit app starts unauthenticated showing the demo login."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    assert not at.exception, f"App raised on start: {at.exception}"
    assert at.title[0].value == "Acadexa — Academic Intelligence"
    assert at.selectbox(key="acadexa_login_choice").label == "User"
    assert at.button(key="acadexa_login_button").label == "Log in"


def test_app_login_flow_reaches_authenticated_shell() -> None:
    """Demo login transitions to the shell; logout returns to login."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    assert not at.exception

    admin_label = "University Administrator (University Admin)"
    at.selectbox(key="acadexa_login_choice").set_value(admin_label).run()
    at.button(key="acadexa_login_button").click().run()
    assert not at.exception, f"App raised after login: {at.exception}"
    assert at.subheader[0].value == "Serving-layer status"
    assert at.button(key="acadexa_logout_button").label == "Log out"

    at.button(key="acadexa_logout_button").click().run()
    assert not at.exception, f"App raised after logout: {at.exception}"
    assert at.button(key="acadexa_login_button").label == "Log in"
