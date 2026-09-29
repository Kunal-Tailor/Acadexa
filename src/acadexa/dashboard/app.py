"""Acadexa Streamlit application entry point (Tasks 11.1, 11.4).

Run with::

    streamlit run src/acadexa/dashboard/app.py

Shows the dummy login screen when logged out and the shared-layout
authenticated shell (sidebar navigation, page header, breadcrumbs, global
filters, serving-layer status, logout) when logged in. All permission
decisions go through :mod:`acadexa.dashboard.permissions`; analytical page
content lives under :mod:`acadexa.dashboard.pages` (University Overview
first, remaining views in later Phase 12 tasks).
"""

from __future__ import annotations

import streamlit as st

from acadexa.dashboard import auth, components, layout, permissions, session
from acadexa.dashboard.auth import AuthConfigError, User
from acadexa.dashboard.config import DashboardConfig
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.pages import university as university_page


@st.cache_resource
def get_dashboard_config() -> DashboardConfig:
    """Cached dashboard configuration (MongoDB settings from environment)."""
    return DashboardConfig.from_env()


@st.cache_resource
def get_dummy_users() -> dict[str, User]:
    """Cached configured dummy users keyed by username."""
    return auth.load_dummy_users(get_dashboard_config().dummy_users_path)


def render_login(users: dict[str, User]) -> None:
    """Render the demonstration login screen (rules.md §24)."""
    st.title("Acadexa — Academic Intelligence")
    st.caption("RAS University · synthetic-data demonstration")
    st.subheader("Demo login")
    st.info(
        "Demonstration login only — selecting a configured user establishes "
        "a demo session. Not production security."
    )
    ordered = sorted(users.values(), key=lambda u: u.username)
    labels = [f"{u.display_name} ({u.role})" for u in ordered]
    choice = st.selectbox("User", labels, key="acadexa_login_choice")
    if st.button("Log in", key="acadexa_login_button"):
        selected = next((u for u in ordered if f"{u.display_name} ({u.role})" == choice), None)
        if selected is None:
            st.error("Unknown user — please select a configured demo user.")
        else:
            session.login(st.session_state, selected)
            st.rerun()


def render_shell(user: User, data: DashboardDataAccess) -> None:
    """Render the shared-layout shell: nav, header, filters, data status."""
    scope = permissions.resolve_scope(user)
    page_key = layout.render_sidebar_nav(user)
    with st.sidebar:
        if st.button("Log out", key="acadexa_logout_button"):
            session.logout(st.session_state)
            st.rerun()

    page_title = layout.nav_title(page_key)
    selections = layout.read_filter_selections(scope)
    context = layout.academic_context_label(selections)
    layout.render_header(page_title, user, context)
    layout.render_breadcrumbs(layout.build_breadcrumbs(page_title, scope))
    selections = layout.render_global_filters(scope)

    st.subheader("Serving-layer status")
    status = data.gold_status()
    failures = {name: info["error"] for name, info in status.items() if info["error"]}
    if failures:
        components.status_badge(
            "warning",
            "Dashboard data is unavailable — showing a controlled error state. "
            "No fallback values are displayed.",
        )
        for name, error in failures.items():
            st.caption(f"{name}: {error}")
    else:
        components.status_badge("ok", "Gold collections reachable.")
        for name, info in status.items():
            st.caption(f"{name}: {info['count']} documents")

    if page_key == "overview":
        university_page.render_university_page(scope, selections, data)
    else:
        components.empty_state(
            f"{page_title} analytics arrive in Phase 12 "
            f"(current scope: {permissions.describe_scope(scope)})."
        )


def main() -> None:
    """Streamlit entry point: login screen or authenticated shell."""
    config = get_dashboard_config()
    st.set_page_config(page_title=config.app_title, layout="wide")
    try:
        users = get_dummy_users()
    except (AuthConfigError, FileNotFoundError, ValueError) as exc:
        st.error(f"Dashboard user configuration is unavailable: {exc}")
        return

    user = session.get_current_user(st.session_state)
    if user is None:
        render_login(users)
        return

    data = DashboardDataAccess(config)
    try:
        render_shell(user, data)
    finally:
        data.close()


if __name__ == "__main__":
    main()
