"""Unit tests for the Data Quality view (Task 12.6).

Covers status classification, pure aggregation over the J1 cleaning
report, tracked-report loading and headless rendering of pipeline-wide
totals, issue categories, dataset outcomes and methodology. Small
fixtures only; live AppTest checks assert structure and labels rather
than exact regenerable values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard.pages.data_quality import (
    CATEGORY_LABELS,
    METRIC_KEYS,
    category_label,
    category_status,
    compute_quality_summary,
    load_quality_report,
)
from acadexa.dashboard.permissions import Scope

APP_PATH = PROJECT_ROOT / "src" / "acadexa" / "dashboard" / "app.py"


def _report() -> dict:
    """Small J1-shaped fixture exercising every status branch."""
    return {
        "validation_status": "PASSED",
        "total_injected": 100,
        "total_detected": 90,
        "total_corrected": 70,
        "total_dropped": 20,
        "total_remaining": 10,
        "summary": {
            "duplicate_lms_events": {
                "injected": 50, "detected": 50, "corrected": 0,
                "dropped": 50, "remaining": 0,
            },
            "orphan_records": {
                "injected": 30, "detected": 30, "corrected": 0,
                "dropped": 20, "remaining": 10,
            },
            "nulls_non_key": {
                "injected": 20, "detected": 10, "corrected": 10,
                "dropped": 0, "remaining": 10,
            },
            "mystery_problems": {
                "injected": 0, "detected": 0, "corrected": 0,
                "dropped": 0, "remaining": 0,
            },
        },
        "datasets": {
            "students": {"input_rows": 36, "output_rows": 36, "issues": {}},
            "attendance": {"input_rows": 100, "output_rows": 90, "issues": {}},
        },
    }


# ── Status classification ──────────────────────────────────────────


def test_category_status_branches() -> None:
    """Healthy/Attention/Issue follow remaining-vs-detected logic with notes."""
    status, detail = category_status(
        {"injected": 50, "detected": 50, "remaining": 0}
    )
    assert status == "Healthy"
    assert "50" in detail

    status, detail = category_status(
        {"injected": 30, "detected": 30, "remaining": 10}
    )
    assert status == "Attention"
    assert "10 of 30" in detail and "detected" in detail

    status, detail = category_status(
        {"injected": 20, "detected": 0, "remaining": 20}
    )
    assert status == "Issue"
    assert "undetected" in detail

    status, detail = category_status(
        {"injected": 0, "detected": 0, "remaining": 0}
    )
    assert status == "Healthy"
    assert "No issues injected" in detail


def test_category_label_known_and_fallback() -> None:
    """Known categories use design labels; unknown keys prettify safely."""
    assert category_label("duplicate_lms_events") == "Duplicates"
    assert category_label("orphan_records") == "Orphan records"
    assert set(CATEGORY_LABELS) >= {
        "duplicate_lms_events", "nulls_non_key", "timestamp_inconsistencies",
        "course_id_formatting", "orphan_records", "out_of_range_values",
    }
    assert category_label("mystery_problems") == "Mystery Problems"


# ── Pure aggregation ───────────────────────────────────────────────


def test_compute_quality_summary() -> None:
    """Totals pass through; rows sort with statuses and dropped deltas."""
    summary = compute_quality_summary(_report())
    assert summary.validation_status == "PASSED"
    assert summary.total_injected == 100
    assert summary.total_remaining == 10
    assert [row.category for row in summary.categories] == [
        "Duplicates", "Mystery Problems", "Nulls", "Orphan records",
    ]
    by_name = {row.category: row for row in summary.categories}
    assert by_name["Duplicates"].status == "Healthy"
    assert by_name["Orphan records"].status == "Attention"
    assert by_name["Nulls"].status == "Attention"
    assert by_name["Nulls"].remaining == 10
    assert [(r.dataset, r.dropped_rows) for r in summary.datasets] == [
        ("attendance", 10), ("students", 0),
    ]


def test_compute_quality_summary_missing_report() -> None:
    """Missing report yields unavailable totals, never fabricated zeros."""
    summary = compute_quality_summary(None)
    assert summary.total_injected is None
    assert summary.validation_status is None
    assert summary.categories == ()
    assert summary.datasets == ()


# ── Tracked report loading ─────────────────────────────────────────


def test_load_tracked_quality_report_is_internally_consistent() -> None:
    """The committed J1 report loads with consistent measured totals."""
    report, error = load_quality_report()
    assert error is None
    assert report is not None
    assert report["job_name"] == "J1_clean_and_validate"
    for key in METRIC_KEYS:
        assert isinstance(report[f"total_{key}"], int)
        assert report[f"total_{key}"] >= 0
    assert report["total_injected"] == sum(
        values["injected"] for values in report["summary"].values()
    )
    assert report["total_remaining"] == sum(
        values["remaining"] for values in report["summary"].values()
    )
    assert report["datasets"]["students"]["input_rows"] > 0


def test_load_quality_report_missing_file(tmp_path: Path) -> None:
    """Missing report surfaces pipeline guidance, never an exception."""
    report, error = load_quality_report(tmp_path / "nope.json")
    assert report is None
    assert error is not None and "run_pipeline" in error


# ── Headless rendering ─────────────────────────────────────────────


def _login_as(at, display_name: str, role: str) -> None:
    at.selectbox(key="acadexa_login_choice").set_value(
        f"{display_name} ({role})"
    ).run()
    at.button(key="acadexa_login_button").click().run()
    assert not at.exception


def _goto_data_quality(at) -> None:
    at.sidebar.radio[0].set_value("Data Quality").run()
    assert not at.exception


def test_data_quality_page_renders_pipeline_output() -> None:
    """Admin Data Quality page shows totals, categories, datasets, method."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "University Administrator", "University Admin")
    _goto_data_quality(at)

    assert at.header[0].value == "Data Quality"
    subheaders = [s.value for s in at.subheader]
    for expected in (
        "Quality overview",
        "Issue categories",
        "Dataset outcomes",
        "Methodology",
    ):
        assert expected in subheaders
    labels = [m.label for m in at.metric]
    for expected in (
        "Issues Injected",
        "Issues Detected",
        "Issues Corrected",
        "Issues Dropped",
        "Issues Remaining",
    ):
        assert expected in labels
    tables = [str(frame.value) for frame in at.dataframe]
    assert any("Duplicates" in table for table in tables)
    assert any("Orphan records" in table for table in tables)
    assert any("Healthy" in table or "Attention" in table for table in tables)
    captions = [c.value for c in at.caption]
    assert any("J1 detection" in text or "J1 input/output" in text for text in captions)


def test_data_quality_page_notes_pipeline_wide_scope() -> None:
    """Scoped roles see the same pipeline-wide figures with an explicit note."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    at = st_test.AppTest.from_file(str(APP_PATH))
    at.run()
    _login_as(at, "CET School Admin", "School / Department Admin")
    _goto_data_quality(at)

    assert not at.exception
    assert at.header[0].value == "Data Quality"
    assert any("not scope-filtered" in c.value for c in at.caption)


def test_data_quality_missing_report_empty_state(tmp_path: Path) -> None:
    """Missing report file renders guidance, not an error or zeros."""
    st_test = pytest.importorskip("streamlit.testing.v1")
    script = tmp_path / "render_quality_missing.py"
    script.write_text(
        "from acadexa.dashboard.pages.data_quality import render_data_quality_page\n"
        "from acadexa.dashboard.permissions import Scope\n"
        "render_data_quality_page(Scope(level='university'), "
        f"'{(tmp_path / 'nope.json').as_posix()}')\n",
        encoding="utf-8",
    )
    at = st_test.AppTest.from_file(str(script))
    at.run()
    assert not at.exception
    assert any("not available yet" in i.value for i in at.info)
