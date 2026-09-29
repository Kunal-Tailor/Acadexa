"""Cross-dashboard usability/accessibility/error-state pass (Task 12.8).

One reviewable pass, encoded as tests — no new features:

- every role reaches every visible page without errors (catches duplicate
  widget IDs, unguarded empty data and scope leaks),
- every interactive widget carries a meaningful label (design.md §36),
- breadcrumbs, scope context and the synthetic-data disclosure render on
  every page (design.md §11, §38),
- rendered microcopy never makes causal or predictive claims except in
  negated methodology notes (design.md §37, rules.md §20),
- analysis tables stay Arrow-safe with uniformly typed columns.

Small fixtures only for pure checks; the matrix uses live development
data through AppTest without asserting exact values.
"""

from __future__ import annotations

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard.pages.analysis import (
    correlation_table_rows,
    recovery_table_rows,
)
from acadexa.dashboard.pages.analysis import (
    CorrelationResult,
)

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"

USERS: tuple[tuple[str, str], ...] = (
    ("University Administrator", "University Admin"),
    ("CET School Admin", "School / Department Admin"),
    ("CSA Faculty Member", "Faculty"),
    ("Academic Analyst", "Academic Analyst"),
)


def _login_as(at, display_name: str, role: str) -> None:
    at.selectbox(key="acadexa_login_choice").set_value(
        f"{display_name} ({role})"
    ).run()
    at.button(key="acadexa_login_button").click().run()
    assert not at.exception


def _page_texts(at) -> list[str]:
    """All user-facing text on the current page run."""
    texts: list[str] = []
    for group in (at.caption, at.markdown, at.info, at.error, at.success, at.warning):
        texts.extend(element.value for element in group)
    texts.extend(header.value for header in at.header)
    texts.extend(sub.value for sub in at.subheader)
    return [text for text in texts if isinstance(text, str)]


def _assert_honest_microcopy(texts: list[str], page: str) -> None:
    """Causal/predictive claims may only appear negated in methodology notes."""
    for text in texts:
        lowered = text.lower()
        if "caus" in lowered:
            assert (
                "not caus" in lowered
                or "non-causal" in lowered
                or "never caus" in lowered
            ), f"Unnegated causal language on {page}: {text!r}"
        if "predict" in lowered:
            assert "not " in lowered or "never " in lowered, (
                f"Unnegated predictive language on {page}: {text!r}"
            )
        for banned in ("will fail", "ai predicts", "guarantee"):
            assert banned not in lowered, f"Banned phrase on {page}: {text!r}"


def test_table_rows_use_uniform_column_types() -> None:
    """Analysis table coefficients render as strings (Arrow-safe columns)."""
    correlations = (
        CorrelationResult("a", "A vs B", 0.42, 10, "Moderate positive association"),
        CorrelationResult("b", "C vs D", None, 0, "Insufficient variation to determine association"),
    )
    rows = correlation_table_rows(correlations)
    assert [row["Spearman ρ"] for row in rows] == ["0.420", "—"]
    assert all(isinstance(row["Spearman ρ"], str) for row in rows)

    entries = (
        {"relationship_id": "r1", "expected_direction": "positive",
         "observed_corr": 0.333, "status": "recovered"},
        {"relationship_id": "r2", "expected_direction": "none",
         "observed_corr": None, "status": "not_evaluated"},
    )
    recovery_rows = recovery_table_rows(entries)
    assert [row["Observed ρ"] for row in recovery_rows] == ["0.333", "—"]
    assert all(isinstance(row["Observed ρ"], str) for row in recovery_rows)


def test_matrix_all_roles_all_pages() -> None:
    """Every role reaches every visible page with labels, context and honesty."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    from acadexa.database import check_connection

    from acadexa.dashboard.config import DashboardConfig

    cfg = DashboardConfig.from_env()
    if not check_connection(config=cfg.database):
        pytest.skip("MongoDB is not reachable in current environment")

    for display_name, role in USERS:
        at = st_test.AppTest.from_file(str(APP_PATH))
        at.run()
        _login_as(at, display_name, role)
        pages = [option for option in at.sidebar.radio[0].options]
        assert pages, f"No navigation options for {display_name}"

        for page in pages:
            at.sidebar.radio[0].set_value(page).run()
            assert not at.exception, f"{display_name} / {page} raised: {at.exception}"

            widgets = (
                [(s.label, "selectbox") for s in at.selectbox]
                + [(at.sidebar.radio[0].label, "radio")]
                + [(b.label, "button") for b in at.button]
                + [(b.label, "button") for b in at.sidebar.button]
            )
            assert widgets, f"No widgets on {display_name} / {page}"
            for label, kind in widgets:
                assert label and label.strip(), (
                    f"Unlabeled {kind} widget on {display_name} / {page}"
                )

            texts = _page_texts(at)
            assert any("›" in text for text in texts), (
                f"No breadcrumb on {display_name} / {page}"
            )
            assert any("fully synthetic" in text for text in texts), (
                f"No synthetic-data disclosure on {display_name} / {page}"
            )
            _assert_honest_microcopy(texts, f"{display_name} / {page}")
