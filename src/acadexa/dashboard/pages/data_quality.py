"""Data Quality view (Task 12.6, docs/design.md §25–§26).

Shows injected/detected/corrected/dropped/remaining issues from actual
pipeline output: the tracked J1 cleaning report
(``data/manifests/data_quality_report.json``). Veracity is one of
Acadexa's Big Data dimensions, so this page reports measured pipeline
output only — never estimates.

The quality report is pipeline-global (per-category and per-dataset
grain, not per-school), so scoped roles see the same pipeline-wide
numbers with an explicit caption saying so.

Structure mirrors the earlier pages:

- :func:`load_quality_report` — read the tracked J1 report file.
- :func:`compute_quality_summary` — pure aggregation into display rows.
- :func:`render_data_quality_page` — Streamlit rendering with shared
  components (requires a UI runtime).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard import components
from acadexa.dashboard.permissions import Scope

DEFAULT_QUALITY_REPORT_PATH: Path = (
    PROJECT_ROOT / "data" / "manifests" / "data_quality_report.json"
)

# Display labels for the injected issue categories (design.md §25).
CATEGORY_LABELS: dict[str, str] = {
    "duplicate_lms_events": "Duplicates",
    "nulls_non_key": "Nulls",
    "timestamp_inconsistencies": "Timestamp inconsistencies",
    "course_id_formatting": "Course-ID formatting",
    "orphan_records": "Orphan records",
    "out_of_range_values": "Out-of-range values",
}

METRIC_KEYS: tuple[str, ...] = (
    "injected",
    "detected",
    "corrected",
    "dropped",
    "remaining",
)


@dataclass(frozen=True)
class CategoryRow:
    """One issue-category outcome row with an explained status."""

    category: str
    injected: int
    detected: int
    corrected: int
    dropped: int
    remaining: int
    status: str
    status_detail: str


@dataclass(frozen=True)
class DatasetRow:
    """One dataset outcome row (records processed vs retained)."""

    dataset: str
    input_rows: int
    output_rows: int
    dropped_rows: int


@dataclass(frozen=True)
class QualitySummary:
    """Aggregated Data Quality view content (None = report unavailable)."""

    validation_status: str | None
    total_injected: int | None
    total_detected: int | None
    total_corrected: int | None
    total_dropped: int | None
    total_remaining: int | None
    categories: tuple[CategoryRow, ...] = ()
    datasets: tuple[DatasetRow, ...] = field(default_factory=tuple)


def category_label(key: str) -> str:
    """Display label for an issue-category key (unknown keys prettified)."""
    return CATEGORY_LABELS.get(key, key.replace("_", " ").title())


def category_status(metrics: Mapping[str, int]) -> tuple[str, str]:
    """Status for one category outcome (design.md §26, with explanation).

    Healthy: nothing remains. Attention: issues remain but the pipeline
    detected them (corrections/drops recorded). Issue: issues remain that
    the pipeline never detected (a blind spot). No injected issues is
    Healthy with an explicit note.
    """
    injected = int(metrics.get("injected", 0) or 0)
    detected = int(metrics.get("detected", 0) or 0)
    remaining = int(metrics.get("remaining", 0) or 0)
    if injected == 0:
        return "Healthy", "No issues injected in this category."
    if remaining == 0:
        return "Healthy", f"All {injected} injected issues resolved."
    if detected > 0:
        return (
            "Attention",
            f"{remaining} of {injected} injected issues remain; "
            f"{detected} were detected by the pipeline.",
        )
    return (
        "Issue",
        f"{remaining} of {injected} injected issues remain undetected "
        "by the pipeline.",
    )


def compute_quality_summary(report: Mapping[str, Any] | None) -> QualitySummary:
    """Aggregate the J1 quality report into view content (pure).

    A missing report yields unavailable totals and empty sections so the
    page renders explicit empty states instead of zeros.
    """
    if not report:
        return QualitySummary(None, None, None, None, None, None)
    summary = report.get("summary") or {}
    categories = tuple(
        CategoryRow(
            category=category_label(key),
            injected=int(values.get("injected", 0) or 0),
            detected=int(values.get("detected", 0) or 0),
            corrected=int(values.get("corrected", 0) or 0),
            dropped=int(values.get("dropped", 0) or 0),
            remaining=int(values.get("remaining", 0) or 0),
            status=status,
            status_detail=detail,
        )
        for key, values in sorted(summary.items())
        for status, detail in (category_status(values),)
    )
    datasets = tuple(
        DatasetRow(
            dataset=str(name),
            input_rows=int(info.get("input_rows", 0) or 0),
            output_rows=int(info.get("output_rows", 0) or 0),
            dropped_rows=max(
                0,
                int(info.get("input_rows", 0) or 0)
                - int(info.get("output_rows", 0) or 0),
            ),
        )
        for name, info in sorted((report.get("datasets") or {}).items())
    )
    totals = {key: report.get(f"total_{key}") for key in METRIC_KEYS}
    return QualitySummary(
        validation_status=report.get("validation_status"),
        total_injected=totals["injected"],
        total_detected=totals["detected"],
        total_corrected=totals["corrected"],
        total_dropped=totals["dropped"],
        total_remaining=totals["remaining"],
        categories=categories,
        datasets=datasets,
    )


def load_quality_report(
    path: Path | str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load the tracked J1 quality report (None, error) when unavailable."""
    target = Path(path) if path is not None else DEFAULT_QUALITY_REPORT_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, (
            "Data-quality report not available yet. Run the Spark pipeline "
            "(scripts/run_pipeline.py) to generate it."
        )
    except (ValueError, OSError) as exc:
        return None, f"Data-quality report unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "Data-quality report has an unexpected structure."
    return data, None


def _overview_section(summary: QualitySummary) -> None:
    """Render pipeline-wide totals (records processed + issue lifecycle)."""
    columns = st.columns(6)
    kpis = (
        ("Issues Injected", summary.total_injected, "issues"),
        ("Issues Detected", summary.total_detected, "issues"),
        ("Issues Corrected", summary.total_corrected, "issues"),
        ("Issues Dropped", summary.total_dropped, "issues"),
        ("Issues Remaining", summary.total_remaining, "issues"),
        ("Validation", summary.validation_status, None),
    )
    for column, (label, value, unit) in zip(columns, kpis):
        with column:
            if label == "Validation" and isinstance(value, str):
                st.metric(label=label, value=value)
            else:
                components.kpi_card(label, value, unit=unit)


def _category_section(categories: tuple[CategoryRow, ...]) -> None:
    """Render the per-category injected→remaining table (design §25)."""
    if not categories:
        components.empty_state("No issue-category data is available.")
        return

    def _body() -> None:
        st.dataframe(
            [
                {
                    "Issue type": row.category,
                    "Injected": row.injected,
                    "Detected": row.detected,
                    "Corrected": row.corrected,
                    "Dropped": row.dropped,
                    "Remaining": row.remaining,
                    "Status": row.status,
                }
                for row in categories
            ]
        )
        for row in categories:
            st.caption(f"{row.category}: {row.status} — {row.status_detail}")

    components.analytical_card(
        "Issue categories",
        "Injected vs detected vs corrected/dropped vs remaining per category.",
        method="Measured J1 cleaning output; observed counts only",
        render_body=_body,
    )


def _dataset_section(datasets: tuple[DatasetRow, ...]) -> None:
    """Render per-dataset records processed vs retained."""
    if not datasets:
        components.empty_state("No dataset outcome data is available.")
        return

    def _body() -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [{"Dataset": row.dataset, "Dropped": row.dropped_rows} for row in datasets]
        )
        if not frame.empty and frame["Dropped"].sum() > 0:
            st.bar_chart(frame, x="Dataset", y="Dropped")
        st.dataframe(
            [
                {
                    "Dataset": row.dataset,
                    "Input rows": row.input_rows,
                    "Output rows": row.output_rows,
                    "Dropped": row.dropped_rows,
                }
                for row in datasets
            ]
        )

    components.analytical_card(
        "Dataset outcomes",
        "Records processed and retained per dataset by the cleaning job.",
        method="Measured J1 input/output row counts",
        render_body=_body,
    )


def render_data_quality_page(
    scope: Scope,
    report_path: Path | str | None = None,
) -> None:
    """Render the Data Quality view from actual pipeline output."""
    report, error = load_quality_report(report_path)
    if error is not None or report is None:
        components.empty_state(error or "Data-quality report not available.")
        return
    summary = compute_quality_summary(report)
    if scope.level != "university":
        st.caption(
            "Pipeline-wide quality figures (not scope-filtered: the cleaning "
            "report has per-dataset, not per-school, grain)."
        )

    st.subheader("Quality overview")
    _overview_section(summary)

    st.subheader("Issue categories")
    _category_section(summary.categories)

    st.subheader("Dataset outcomes")
    _dataset_section(summary.datasets)

    st.subheader("Methodology")
    components.analytical_card(
        "Methodology",
        "How to read cleaning outcomes without overstating them.",
        method=(
            "Controlled synthetic injection with exact manifest counts vs "
            "J1 detection/correction/drop accounting; detected counts are "
            "measured pipeline output, not the injected counts restated; "
            "association, never causation"
        ),
    )
