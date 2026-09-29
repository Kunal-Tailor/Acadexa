"""Unit tests for shared dashboard layout and components (Tasks 11.4–11.5).

Covers the navigation model, breadcrumbs, scope-aware global filters
(11.4) and the reusable KPI/analytical/status/risk-signal components
following docs/design.md (11.5). Pure helpers are tested directly;
rendering is verified headlessly via AppTest on the app and on a small
component script. Small fixtures only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard import components, layout
from acadexa.dashboard.auth import User, load_dummy_users
from acadexa.dashboard.components import (
    RISK_SIGNAL_KEYS,
    RISK_SIGNAL_LABELS,
    format_value,
    risk_attention_text,
    risk_summary_text,
)
from acadexa.dashboard.layout import (
    FILTER_FIELDS,
    NAV_ITEMS,
    academic_context_label,
    build_breadcrumbs,
    default_filters,
    default_nav_key,
    filter_options,
    format_breadcrumbs,
    load_academic_periods,
    nav_title,
    visible_filters,
    visible_nav_items,
)
from acadexa.dashboard.permissions import Scope, resolve_scope

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"


@pytest.fixture(scope="module")
def users() -> dict[str, User]:
    """Configured dummy users from the tracked TOML."""
    return load_dummy_users()


def _scope(users: dict[str, User], username: str) -> Scope:
    return resolve_scope(users[username])


# ── 11.4: navigation model ─────────────────────────────────────────


def test_nav_items_follow_design_order() -> None:
    """Primary navigation matches design.md §8 analytical concepts."""
    assert [item.title for item in NAV_ITEMS] == [
        "Overview",
        "Schools",
        "Courses",
        "Students",
        "Analysis",
        "Data Quality",
    ]
    assert all(item.required_capabilities for item in NAV_ITEMS)


def test_visible_nav_items_per_role(users) -> None:
    """Navigation is gated by capability, never hard-coded per page."""
    assert [i.title for i in visible_nav_items(users["admin"])] == [
        "Overview",
        "Schools",
        "Courses",
        "Students",
        "Analysis",
        "Data Quality",
    ]
    assert len(visible_nav_items(users["cet.admin"])) == 6
    assert [i.title for i in visible_nav_items(users["faculty.csa"])] == [
        "Courses",
        "Students",
        "Analysis",
    ]
    assert [i.title for i in visible_nav_items(users["analyst"])] == [
        "Overview",
        "Schools",
        "Analysis",
        "Data Quality",
    ]


def test_visible_nav_items_empty_for_unapproved_role() -> None:
    """Unknown roles see no navigation destinations."""
    assert (
        visible_nav_items(
            User(username="x", display_name="X", role="Superuser")
        )
        == ()
    )


def test_default_nav_key_and_titles(users) -> None:
    """Landing page is the first visible item; unknown keys pass through."""
    assert default_nav_key(users["admin"]) == "overview"
    assert default_nav_key(users["faculty.csa"]) == "courses"
    assert nav_title("data_quality") == "Data Quality"
    assert nav_title("mystery") == "mystery"


# ── 11.4: breadcrumbs ─────────────────────────────────────────────


def test_build_breadcrumbs_hierarchy(users) -> None:
    """Crumbs narrow university › school › department › page."""
    assert build_breadcrumbs("Overview", _scope(users, "admin")) == [
        "RAS University",
        "Overview",
    ]
    assert build_breadcrumbs("Schools", _scope(users, "cet.admin")) == [
        "RAS University",
        "School of Computer Engineering & Technology",
        "Schools",
    ]
    dept_scope = Scope(
        level="department",
        school="School of Business",
        department="Management Studies",
    )
    assert build_breadcrumbs("Students", dept_scope) == [
        "RAS University",
        "School of Business",
        "Management Studies",
        "Students",
    ]
    assert build_breadcrumbs("Courses", _scope(users, "faculty.csa")) == [
        "RAS University",
        "School of Computer Engineering & Technology",
        "Courses: CSA101, CSA102",
        "Courses",
    ]
    assert "none assigned" in build_breadcrumbs(
        "Courses", Scope(level="courses", courses=())
    )[-2]


def test_format_breadcrumbs_separator() -> None:
    """Crumbs render with the design.md §11 separator."""
    assert format_breadcrumbs(["A", "B"]) == "A › B"


# ── 11.4: global filters ───────────────────────────────────────────


def test_load_academic_periods_from_tracked_config() -> None:
    """Year/semester options come from configuration, not hard-coded lists."""
    periods = load_academic_periods()
    assert periods["academic_years"] == ["2024-25", "2025-26"]
    assert periods["semesters"] == ["S1", "S2", "S3", "S4"]


def test_load_academic_periods_missing_file(tmp_path: Path) -> None:
    """Missing configuration fails fast instead of silently emptying filters."""
    with pytest.raises(FileNotFoundError):
        load_academic_periods(tmp_path / "nope.toml")


def test_visible_filters_respect_scope(users) -> None:
    """Scope-fixed dimensions are excluded from user-selectable filters."""
    assert visible_filters(_scope(users, "admin")) == FILTER_FIELDS
    assert visible_filters(_scope(users, "analyst")) == FILTER_FIELDS
    school_filters = visible_filters(_scope(users, "cet.admin"))
    assert "school" not in school_filters
    assert len(school_filters) == len(FILTER_FIELDS) - 1
    dept_filters = visible_filters(
        Scope(level="department", school="S", department="D")
    )
    assert "school" not in dept_filters and "department" not in dept_filters
    assert visible_filters(_scope(users, "faculty.csa")) == (
        "academic_year",
        "semester",
    )


def test_visible_filters_rejects_unknown_scope() -> None:
    """Unknown scope levels fail fast."""
    with pytest.raises(ValueError, match="Unknown scope level"):
        visible_filters(Scope(level="planet"))


def test_default_filters_start_unrestricted(users) -> None:
    """Defaults cover exactly the visible fields, all starting at "All"."""
    scope = _scope(users, "admin")
    defaults = default_filters(scope)
    assert set(defaults) == set(visible_filters(scope))
    assert all(value is None for value in defaults.values())


def test_filter_options_sources(users) -> None:
    """Year/semester options come from config; hierarchy is scope-driven."""
    periods = load_academic_periods()
    admin_scope = _scope(users, "admin")
    assert filter_options("academic_year", admin_scope, periods)[0] == "All"
    assert "2025-26" in filter_options("academic_year", admin_scope, periods)
    assert filter_options("semester", admin_scope, periods) == [
        "All",
        "S1",
        "S2",
        "S3",
        "S4",
    ]
    assert filter_options("school", _scope(users, "cet.admin")) == [
        "School of Computer Engineering & Technology"
    ]
    assert filter_options("course", _scope(users, "faculty.csa")) == [
        "CSA101",
        "CSA102",
    ]
    assert filter_options("course", Scope(level="courses", courses=())) == []
    assert filter_options("program", admin_scope) == ["All"]
    with pytest.raises(ValueError, match="Unknown filter field"):
        filter_options("planet", admin_scope)


def test_academic_context_label() -> None:
    """Header context reads "AY · Semester" with explicit All fallbacks."""
    assert (
        academic_context_label({"academic_year": "2025-26", "semester": "S2"})
        == "2025-26 · S2"
    )
    assert (
        academic_context_label({"academic_year": None, "semester": None})
        == "All years · All semesters"
    )


# ── 11.5: component formatting contracts ───────────────────────────


def test_format_value_units_and_missing() -> None:
    """KPI values carry units; missing data never renders as zero."""
    assert format_value(None) == "Data unavailable"
    assert format_value(81.666, "percent") == "81.7%"
    assert format_value(12000, "students") == "12,000 students"
    assert format_value(72.4, None) == "72.4"
    assert format_value(72.4, "/ 100") == "72.4 / 100"


def test_risk_summary_and_attention_text() -> None:
    """Risk captions use N / 5 counts with non-sensational language."""
    assert risk_summary_text(3) == "3 / 5"
    assert risk_summary_text(0) == "0 / 5"
    assert risk_attention_text(0) == "No observed indicators"
    assert risk_attention_text(1) == "1 observed indicator requires attention"
    assert risk_attention_text(5) == "5 observed indicators require attention"
    for bad in (6, -1, True, "3", None):
        with pytest.raises(ValueError, match="signal_count"):
            risk_summary_text(bad)


def test_risk_signal_labels_cover_five_signals() -> None:
    """Signal labels match exactly the five-signal analytics contract."""
    assert set(RISK_SIGNAL_LABELS) == set(RISK_SIGNAL_KEYS)
    assert RISK_SIGNAL_LABELS["low_attendance"] == "Attendance"


# ── 11.5: component rendering (headless) ────────────────────────────


def _run_component_script(tmp_path: Path, body: str):
    """Run a small component-rendering script headlessly via AppTest."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_components.py"
    script.write_text(
        "from acadexa.dashboard import components as c\n" + body,
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception, f"Component script raised: {at.exception}"
    return at


def test_kpi_and_analytical_cards_render(tmp_path: Path) -> None:
    """KPI/analytical cards show label, value, context and method."""
    at = _run_component_script(
        tmp_path,
        'c.kpi_card("Active Students", 12000, unit="students", '
        'context="Semester 2 · 2025–26", comparison="+2.1% vs S1")\n'
        'c.analytical_card("Attendance vs Marks", "Observed association.", '
        'method="Spearman ρ; association, not causation")\n',
    )
    assert at.metric[0].label == "Active Students"
    assert at.metric[0].value == "12,000 students"
    captions = [c.value for c in at.caption]
    assert any("Semester 2" in text for text in captions)
    assert any("association, not causation" in text for text in captions)


def test_status_badge_levels_render(tmp_path: Path) -> None:
    """Status levels map to the matching Streamlit severity element."""
    at = _run_component_script(
        tmp_path,
        'c.status_badge("ok", "Gold collections reachable.")\n'
        'c.status_badge("error", " boom")\n',
    )
    assert at.success[0].value == "Gold collections reachable."
    assert "boom" in at.error[0].value
    with pytest.raises(ValueError, match="Unknown status level"):
        components._check_status_level("critical")


def test_risk_signal_card_renders_breakdown(tmp_path: Path) -> None:
    """Risk card shows N / 5, per-signal breakdown and methodology note."""
    at = _run_component_script(
        tmp_path,
        "c.risk_signal_card(3, {'low_attendance': True, 'lms_decline': True, "
        "'late_submissions': False, 'marks_decline': True, "
        "'low_quiz_activity': False}, "
        "explanations={'low_attendance': '68.0% < 75% threshold'})\n",
    )
    assert at.markdown[1].value == "## 3 / 5"
    captions = [c.value for c in at.caption]
    assert any("3 observed indicators require attention" in t for t in captions)
    assert any("Attendance — ● Triggered" in t for t in captions)
    assert any("68.0% < 75% threshold" in t for t in captions)
    assert any("Late submissions — ○ Not triggered" in t for t in captions)
    assert any("not a failure prediction" in t for t in captions)


def test_risk_signal_card_rejects_bad_contract(tmp_path: Path) -> None:
    """Out-of-contract counts/keys surface as run errors, not silent cards."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_bad_risk.py"
    script.write_text(
        "from acadexa.dashboard import components as c\n"
        "c.risk_signal_card(2, {'low_attendance': True, 'mind_reading': True})\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert len(at.exception) == 1
    assert "Unknown risk signals" in at.exception[0].message


def test_empty_and_error_states_render(tmp_path: Path) -> None:
    """Empty/error states are explicit and hide technical internals."""
    at = _run_component_script(
        tmp_path,
        'c.empty_state("No course data is available for this selection.")\n'
        'c.error_state("Unable to load course analytics.", '
        '"The analytical data service is currently unavailable.")\n',
    )
    assert "No course data" in at.info[0].value
    assert "Unable to load course analytics" in at.error[0].value
    assert "Traceback" not in at.error[0].value


# ── 11.4: shell wiring (headless) ───────────────────────────────────


def _login_as(at, display_name: str, role: str) -> None:
    at.selectbox(key="acadexa_login_choice").set_value(
        f"{display_name} ({role})"
    ).run()
    at.button(key="acadexa_login_button").click().run()
    assert not at.exception


def test_shell_shows_nav_header_breadcrumbs_filters() -> None:
    """Admin shell exposes nav, header, breadcrumbs and all six filters."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")

    assert [o for o in at.sidebar.radio[0].options] == [
        "Overview",
        "Schools",
        "Courses",
        "Students",
        "Analysis",
        "Data Quality",
    ]
    assert at.header[0].value == "Overview"
    assert any("RAS University" in c.value for c in at.caption)
    filter_labels = [s.label for s in at.selectbox]
    assert filter_labels == [
        "Academic year",
        "Semester",
        "School",
        "Department",
        "Program",
        "Course",
    ]


def test_shell_page_switch_updates_header_and_breadcrumbs() -> None:
    """Navigation changes the header/breadcrumb; content stays Phase-12 honest."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")

    at.sidebar.radio[0].set_value("Data Quality").run()
    assert not at.exception
    assert at.header[0].value == "Data Quality"
    assert any("Data Quality" in c.value and "›" in c.value for c in at.caption)
    assert any("Phase 12" in i.value for i in at.info)


def test_shell_restricts_nav_and_filters_for_faculty() -> None:
    """Faculty see course-scoped nav, fixed courses and year/semester filters."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "CSA Faculty Member", "Faculty")

    assert [o for o in at.sidebar.radio[0].options] == [
        "Courses",
        "Students",
        "Analysis",
    ]
    assert at.header[0].value == "Courses"
    assert [s.label for s in at.selectbox] == ["Academic year", "Semester", "Course"]
    assert any("CSA101" in c.value for c in at.caption)
