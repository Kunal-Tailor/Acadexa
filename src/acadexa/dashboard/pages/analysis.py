"""Analysis view (Task 12.5, docs/design.md §20–§22, features.md F-E07).

The technical centerpiece: cross-factor correlations, trend analysis,
engagement analysis, ground-truth recovery and methodology notes — all
from served gold data, never from raw Parquet or Spark jobs.

Design note: J4/J5 pipeline outputs live in Parquet and are not served in
MongoDB, so this page derives serving-scale analytics from bounded gold
reads. Rank correlations are computed in pure Python over fetched
``student_features`` rows (presentation-layer aggregation over
already-aggregated gold data, like the means on other pages — not
large-scale processing). Coefficients use raw gold values, not
within-course normalized ones; the Spark J4 job computes the normalized
counterpart (stated in the methodology section).

Interpretation boundaries mirror the canonical
``analytics.correlation.interpret_spearman_association`` (±0.10/±0.25/
±0.50); a unit test pins them equal. Recovery classification reuses
:func:`validation.recovery.compare_ground_truth_recovery` directly.

Structure mirrors the earlier pages:

- :func:`fetch_analysis_data` — bounded, scope-aware MongoDB reads.
- :func:`spearman_rank_correlation` / :func:`interpret_association` —
  pure statistics over record lists.
- :func:`compute_analysis_summary` — pure aggregation.
- :func:`render_analysis_page` — Streamlit rendering with shared components.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from acadexa.config.loader import PROJECT_ROOT
from acadexa.dashboard import components, layout
from acadexa.dashboard.data_access import DashboardDataAccess
from acadexa.dashboard.permissions import Scope, build_mongo_scope_filter
from acadexa.validation.recovery import compare_ground_truth_recovery

GROUND_TRUTH_REGISTRY_PATH: Path = (
    PROJECT_ROOT / "data" / "manifests" / "ground_truth_registry.json"
)

# Registry relationship → (gold x field, gold y field, display name).
# Quiz-attempt and decoy-forum relationships have no gold feature fields,
# so they evaluate to not_evaluated (honest, per recovery conventions).
ANALYSED_RELATIONSHIPS: tuple[tuple[str, str, str, str], ...] = (
    ("attendance_marks", "attendance_mean", "avg_academic_score", "Attendance vs Marks"),
    ("lms_engagement_marks", "engagement_count", "avg_academic_score", "LMS Engagement vs Marks"),
    ("late_submissions_marks", "late_submission_rate", "avg_academic_score", "Late Submissions vs Marks"),
)


@dataclass(frozen=True)
class CorrelationResult:
    """One observed cross-factor association (None = not computable)."""

    relationship_id: str
    name: str
    spearman_rho: float | None
    sample_size: int
    interpretation: str


@dataclass(frozen=True)
class AnalysisSummary:
    """Aggregated Analysis view content."""

    student_count: int
    correlations: tuple[CorrelationResult, ...] = ()
    mean_score_trend: float | None = None
    declining: int = 0
    improving: int = 0
    stable: int = 0
    lms_decline_rate: float | None = None
    marks_decline_rate: float | None = None
    mean_engagement: float | None = None
    total_engagement: int | None = None
    recovery_entries: tuple[dict[str, Any], ...] = ()
    recovery_summary: dict[str, int] = field(default_factory=dict)


def _fractional_ranks(values: list[float]) -> list[float]:
    """Average fractional ranks with tie averaging (1-based)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    pos = 0
    while pos < len(order):
        end = pos
        while end + 1 < len(order) and values[order[end + 1]] == values[order[pos]]:
            end += 1
        avg_rank = (pos + 1 + end + 1) / 2.0
        for k in range(pos, end + 1):
            ranks[order[k]] = avg_rank
        pos = end + 1
    return ranks


def spearman_rank_correlation(xs: list[float], ys: list[float]) -> float | None:
    """Pure-Python Spearman ρ over paired observations (None when degenerate).

    Pearson correlation of fractional ranks; None with fewer than three
    pairs or zero rank variance on either side.
    """
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys)]
    if len(pairs) < 3:
        return None
    rx, ry = _fractional_ranks([p[0] for p in pairs]), _fractional_ranks([p[1] for p in pairs])
    n = len(pairs)
    mean_x, mean_y = sum(rx) / n, sum(ry) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return round(cov / (var_x**0.5 * var_y**0.5), 3)


def interpret_association(correlation: float | None) -> str:
    """Standardized non-causal interpretation (mirrors canonical boundaries)."""
    if correlation is None:
        return "Insufficient variation to determine association"
    r = float(correlation)
    if r >= 0.50:
        return "Strong positive association"
    if r >= 0.25:
        return "Moderate positive association"
    if r >= 0.10:
        return "Weak positive association"
    if r > -0.10:
        return "No observed monotonic association"
    if r > -0.25:
        return "Weak negative association"
    if r > -0.50:
        return "Moderate negative association"
    return "Strong negative association"


def _mean(values: list[float]) -> float | None:
    """Rounded mean of ``values`` (None when empty)."""
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def compute_correlations(
    student_features: list[dict[str, Any]],
) -> tuple[CorrelationResult, ...]:
    """Observe cross-factor associations over gold feature rows (pure)."""
    results = []
    for rel_id, x_field, y_field, name in ANALYSED_RELATIONSHIPS:
        pairs = [
            (d[x_field], d[y_field])
            for d in student_features
            if d.get(x_field) is not None and d.get(y_field) is not None
        ]
        rho = spearman_rank_correlation(
            [p[0] for p in pairs], [p[1] for p in pairs]
        )
        results.append(
            CorrelationResult(
                relationship_id=rel_id,
                name=name,
                spearman_rho=rho,
                sample_size=len(pairs),
                interpretation=interpret_association(rho),
            )
        )
    return tuple(results)


def load_ground_truth_registry(
    path: Path | str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load the tracked ground-truth registry (None, error) when unavailable."""
    target = Path(path) if path is not None else GROUND_TRUTH_REGISTRY_PATH
    try:
        return json.loads(target.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"Ground-truth registry not found: {target}"
    except (ValueError, OSError) as exc:
        return None, f"Ground-truth registry unreadable: {exc}"


def compute_recovery(
    ground_truth: Mapping[str, Any] | None,
    correlations: tuple[CorrelationResult, ...],
    scope_label: str,
) -> tuple[tuple[dict[str, Any], ...], dict[str, int]]:
    """Compare planted expectations vs observed associations (pure).

    Unobservable relationships (quiz attempts, decoy forum activity,
    difficulty confounder) evaluate to not_evaluated per recovery
    conventions. Returns ``(entries, summary)`` as plain dicts.
    """
    if ground_truth is None:
        return (), {}
    observed = [
        {
            "relationship_id": c.relationship_id,
            "spearman_raw": c.spearman_rho,
            "spearman_normalized": None,
            "scope": scope_label,
        }
        for c in correlations
    ]
    report = compare_ground_truth_recovery(
        ground_truth, observed, scope=scope_label
    )
    return (
        tuple(e.to_dict() for e in report.entries),
        dict(report.summary),
    )


def compute_analysis_summary(
    student_features: list[dict[str, Any]],
    risk_indicators: list[dict[str, Any]],
    ground_truth: Mapping[str, Any] | None,
    scope_label: str,
) -> AnalysisSummary:
    """Aggregate Analysis view content (pure)."""
    students = {str(d.get("student_id")) for d in student_features if d.get("student_id")}
    correlations = compute_correlations(student_features)

    trends = [float(d["score_trend"]) for d in student_features if d.get("score_trend") is not None]
    engagements = [int(d["engagement_count"]) for d in student_features if d.get("engagement_count") is not None]

    lms_flags = [d.get("lms_decline") is True for d in risk_indicators]
    marks_flags = [d.get("marks_decline") is True for d in risk_indicators]

    entries, summary = compute_recovery(ground_truth, correlations, scope_label)
    return AnalysisSummary(
        student_count=len(students),
        correlations=correlations,
        mean_score_trend=_mean(trends),
        declining=sum(1 for v in trends if v < 0),
        improving=sum(1 for v in trends if v > 0),
        stable=sum(1 for v in trends if v == 0),
        lms_decline_rate=round(sum(lms_flags) / len(lms_flags) * 100, 1) if lms_flags else None,
        marks_decline_rate=round(sum(marks_flags) / len(marks_flags) * 100, 1) if marks_flags else None,
        mean_engagement=_mean([float(v) for v in engagements]),
        total_engagement=sum(engagements) if engagements else None,
        recovery_entries=entries,
        recovery_summary=summary,
    )


def fetch_analysis_data(
    access: DashboardDataAccess,
    scope: Scope,
    semester: str | None,
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    """Fetch scoped gold records for the Analysis view.

    ``student_features`` carry no course field, so course-scoped users
    resolve enrolled students via ``academic_records`` first. Risk rows
    (no semester field) are restricted in Python to scoped students and
    aggregate all semesters in scope. Returns ``(records, error)``
    following the data-access failure contract.
    """
    feature_filter = build_mongo_scope_filter(
        scope, school_field="student_school", department_field="student_department"
    )
    if scope.level == "courses":
        if not scope.courses:
            return {}, "This view is unavailable for the current scope."
        enrolled_rows, error = access.fetch(
            "academic_records", {"course_id": {"$in": list(scope.courses)}}
        )
        if error is not None:
            return {}, error
        enrolled = {str(d.get("student_id")) for d in enrolled_rows if d.get("student_id")}
        if not enrolled:
            return {"student_features": [], "risk_indicators": []}, None
        feature_filter = {"student_id": {"$in": sorted(enrolled)}}
    if semester:
        feature_filter = {**feature_filter, "semester_id": semester}

    features, error = access.fetch("student_features", feature_filter)
    if error is not None:
        return {}, error
    risk_docs, error = access.fetch("risk_indicators", {})
    if error is not None:
        return {}, error
    scoped = {str(d.get("student_id")) for d in features}
    return (
        {
            "student_features": features,
            "risk_indicators": [d for d in risk_docs if str(d.get("student_id")) in scoped],
        },
        None,
    )


def correlation_table_rows(
    correlations: tuple[CorrelationResult, ...],
) -> list[dict[str, Any]]:
    """Ranked association table rows with uniformly string coefficients.

    Coefficients render as fixed-precision strings (missing as "—") so the
    column stays Arrow-safe instead of mixing floats and strings.
    """
    return [
        {
            "Relationship": c.name,
            "Spearman ρ": f"{c.spearman_rho:.3f}" if c.spearman_rho is not None else "—",
            "Sample": c.sample_size,
            "Interpretation": c.interpretation,
        }
        for c in correlations
    ]


def recovery_table_rows(
    entries: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    """Recovery comparison table rows with uniformly string coefficients."""
    return [
        {
            "Relationship": e["relationship_id"],
            "Expected": e["expected_direction"],
            "Observed ρ": f"{e['observed_corr']:.3f}"
            if e["observed_corr"] is not None
            else "—",
            "Status": e["status"],
        }
        for e in entries
    ]


def _correlation_section(correlations: tuple[CorrelationResult, ...]) -> None:
    """Render the ranked association table with interpretations."""
    rows = correlation_table_rows(correlations)
    if not rows or all(c.spearman_rho is None for c in correlations):
        components.empty_state("No correlation data is available for this selection.")
        return

    def _body() -> None:
        st.dataframe(rows)

    components.analytical_card(
        "Factor relationships",
        "Rank correlations between academic factors over served gold features.",
        method="Spearman ρ on gold values; association, not causation",
        render_body=_body,
    )


def _trend_section(summary: AnalysisSummary) -> None:
    """Render trend detection summary with four-window methodology note."""
    if summary.student_count == 0:
        components.empty_state("No trend data is available for this selection.")
        return

    def _body() -> None:
        st.caption(
            f"Mean score trend {components.format_value(summary.mean_score_trend, 'pts')} · "
            f"{summary.declining} declining · {summary.improving} improving · "
            f"{summary.stable} stable"
        )
        if summary.lms_decline_rate is not None:
            st.caption(
                f"LMS decline flagged for {summary.lms_decline_rate}% of assessed students "
                "(current 4 weeks at or below 50% of the previous 4 weeks)."
            )
        if summary.marks_decline_rate is not None:
            st.caption(
                f"Marks decline flagged for {summary.marks_decline_rate}% of assessed students "
                "(latest graded items 10+ points below the earlier average)."
            )

    components.analytical_card(
        "Trend detection",
        "Engagement and marks movement observed in gold data.",
        method="Four-week engagement windows; graded-item averages; association, not causation",
        render_body=_body,
    )


def _engagement_section(summary: AnalysisSummary) -> None:
    """Render LMS engagement summary from gold engagement counts."""
    if summary.total_engagement is None:
        components.empty_state("No engagement data is available for this selection.")
        return

    def _body() -> None:
        st.caption(
            f"{components.format_value(summary.total_engagement, 'events')} total · "
            f"{components.format_value(summary.mean_engagement, 'events')} mean per student "
            f"across {summary.student_count} students."
        )

    components.analytical_card(
        "Engagement analysis",
        "LMS event volumes per student from gold features.",
        method="Summed gold engagement counts; observed volumes only",
        render_body=_body,
    )


def _recovery_section(
    entries: tuple[dict[str, Any], ...], summary: dict[str, int], available: bool
) -> None:
    """Render planted-vs-observed recovery comparison (never causal)."""
    if not available:
        components.empty_state(
            "Ground-truth recovery is unavailable: the registry file is missing."
        )
        return
    if not entries:
        components.empty_state("No recovery data is available for this selection.")
        return

    def _body() -> None:
        st.dataframe(recovery_table_rows(entries))
        st.caption(
            f"Recovered {summary.get('recovered', 0)} of {summary.get('planted', 0)} "
            f"planted associations · decoy clean: {summary.get('decoy_clean', 0)} · "
            f"not evaluated: {summary.get('not_evaluated', 0)}."
        )

    components.analytical_card(
        "Ground-truth recovery",
        "Planted synthetic relationships vs observed serving-data associations.",
        method="Fixed ±0.10 recovery thresholds; association, not causation",
        render_body=_body,
    )


def _methodology_section() -> None:
    """Render analytical methodology notes (design.md §39)."""
    components.analytical_card(
        "Methodology",
        "How to read this page without misinterpreting synthetic results.",
        method=(
            "Spearman rank correlation on served gold values (not within-course "
            "normalized — the Spark J4 job computes the normalized counterpart); "
            "association, never causation; risk counts are observed signals, "
            "not failure predictions; all data is fully synthetic"
        ),
    )


def render_analysis_page(
    scope: Scope,
    filters: Mapping[str, str | None],
    access: DashboardDataAccess,
) -> None:
    """Render the Analysis view from actual gold data."""
    records, error = fetch_analysis_data(access, scope, (filters or {}).get("semester"))
    if error is not None:
        components.error_state(
            "Unable to load analysis view.",
            "The analytical data service is currently unavailable. "
            "Please check the database connection and try again.",
        )
        return
    ground_truth, gt_error = load_ground_truth_registry()
    summary = compute_analysis_summary(
        records["student_features"],
        records["risk_indicators"],
        ground_truth,
        scope.level,
    )
    context = layout.academic_context_label(filters or {})
    if (filters or {}).get("semester"):
        context += " (risk aggregates all semesters in scope)"

    st.subheader("Analysis overview")
    components.analytical_card(
        "Analysis overview",
        f"Cross-factor, trend and engagement analysis over {summary.student_count} "
        f"students in scope ({context}).",
        method="Served gold data; bounded reads only",
    )

    st.subheader("Factor relationships")
    _correlation_section(summary.correlations)

    st.subheader("Trend detection")
    _trend_section(summary)

    st.subheader("Engagement analysis")
    _engagement_section(summary)

    st.subheader("Ground-truth recovery")
    _recovery_section(summary.recovery_entries, summary.recovery_summary, ground_truth is not None)
    if gt_error is not None:
        st.caption(gt_error)

    st.subheader("Methodology")
    _methodology_section()
