"""Reusable dashboard UI components (Task 11.5, docs/design.md).

One consistent implementation per component kind (design.md §47):
KPI card (§12/§13/§48), analytical card (§48), status badge (§26/§31),
risk-signal card (§19/§48), empty state (§30) and error state (§31).

Formatting helpers and input validation are pure (Streamlit-free) so
component contracts are unit-testable; only the ``render_*``/named
render functions require a Streamlit runtime. All values shown must come
from the data layer — components never fabricate numbers (rules.md §23).
Missing data renders as an explicit "Data unavailable", never as zero.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import streamlit as st

# The five approved risk signals, matching the risk analytics grain.
RISK_SIGNAL_KEYS: tuple[str, ...] = (
    "low_attendance",
    "lms_decline",
    "late_submissions",
    "marks_decline",
    "low_quiz_activity",
)

RISK_SIGNAL_LABELS: dict[str, str] = {
    "low_attendance": "Attendance",
    "lms_decline": "LMS decline",
    "late_submissions": "Late submissions",
    "marks_decline": "Marks decline",
    "low_quiz_activity": "Quiz activity",
}

MAX_SIGNAL_COUNT: int = 5

STATUS_LEVELS: tuple[str, ...] = ("ok", "info", "warning", "error")


def format_value(value: float | int | None, unit: str | None = None) -> str:
    """Format a KPI value with units (design.md §13).

    ``None`` renders as explicit "Data unavailable" — missing data is never
    shown as zero. ``"percent"`` renders one decimal with a % sign;
    otherwise thousands separators apply with an optional unit suffix.
    """
    if value is None:
        return "Data unavailable"
    if unit == "percent":
        return f"{float(value):.1f}%"
    if unit:
        return f"{value:,} {unit}"
    return f"{value:,}"


def risk_summary_text(signal_count: int) -> str:
    """Return the ``N / 5`` risk-signal summary (design.md §19)."""
    _check_signal_count(signal_count)
    return f"{signal_count} / {MAX_SIGNAL_COUNT}"


def risk_attention_text(signal_count: int) -> str:
    """Non-sensational risk caption: observed indicators, never predictions."""
    _check_signal_count(signal_count)
    if signal_count == 0:
        return "No observed indicators"
    if signal_count == 1:
        return "1 observed indicator requires attention"
    return f"{signal_count} observed indicators require attention"


def _check_signal_count(signal_count: int) -> None:
    """Fail fast on out-of-contract signal counts."""
    if (
        not isinstance(signal_count, int)
        or isinstance(signal_count, bool)
        or not 0 <= signal_count <= MAX_SIGNAL_COUNT
    ):
        raise ValueError(
            f"signal_count must be an integer 0–{MAX_SIGNAL_COUNT}, "
            f"got {signal_count!r}"
        )


def _check_triggered(triggered: Mapping[str, bool]) -> None:
    """Fail fast when the signal breakdown drifts from the five-signal contract."""
    unknown = set(triggered) - set(RISK_SIGNAL_KEYS)
    if unknown:
        raise ValueError(f"Unknown risk signals: {sorted(unknown)}")


def _check_status_level(level: str) -> None:
    """Fail fast on unknown status levels."""
    if level not in STATUS_LEVELS:
        raise ValueError(f"Unknown status level {level!r}; expected one of {list(STATUS_LEVELS)}")


# ── Streamlit render functions ───────────────────────────────────────


def kpi_card(
    label: str,
    value: float | int | None,
    unit: str | None = None,
    context: str | None = None,
    comparison: str | None = None,
    help_text: str | None = None,
) -> None:
    """Render a KPI card: label, value, unit, time context (design §12/§48)."""
    st.metric(label=label, value=format_value(value, unit), delta=comparison)
    details = " · ".join(part for part in (context, help_text) if part)
    if details:
        st.caption(details)


def analytical_card(
    title: str,
    explanation: str,
    method: str | None = None,
    render_body: Callable[[], None] | None = None,
) -> None:
    """Render an analytical card: title, explanation, body, method (§48)."""
    st.markdown(f"**{title}**")
    st.caption(explanation)
    if render_body is not None:
        render_body()
    if method:
        st.caption(f"Method: {method}")


def status_badge(level: str, text: str) -> None:
    """Render a status badge: ok/info/warning/error (design §26/§31)."""
    _check_status_level(level)
    if level == "ok":
        st.success(text)
    elif level == "info":
        st.info(text)
    elif level == "warning":
        st.warning(text)
    else:
        st.error(text)


def risk_signal_card(
    signal_count: int,
    triggered: Mapping[str, bool],
    explanations: Mapping[str, str] | None = None,
) -> None:
    """Render the five-rule risk-signal card (design.md §19/§48).

    Shows the ``N / 5`` count, a non-sensational attention line, the
    per-signal triggered breakdown (auditable) and the methodology note:
    a count of predefined observed signals, not a failure prediction.
    """
    _check_signal_count(signal_count)
    _check_triggered(triggered)
    st.markdown("**Risk Signals**")
    st.markdown(f"## {risk_summary_text(signal_count)}")
    st.caption(risk_attention_text(signal_count))
    for key in RISK_SIGNAL_KEYS:
        is_set = bool(triggered.get(key, False))
        marker = "● Triggered" if is_set else "○ Not triggered"
        line = f"{RISK_SIGNAL_LABELS[key]} — {marker}"
        if explanations and explanations.get(key):
            line += f": {explanations[key]}"
        st.caption(line)
    st.caption(
        "Risk indicator = count of five predefined observed signals. "
        "It is not a failure prediction model."
    )


def empty_state(message: str) -> None:
    """Render an explicit empty state (design.md §30)."""
    st.info(message)


def error_state(title: str, detail: str) -> None:
    """Render a user-friendly error without raw stack traces (§31)."""
    st.error(f"{title}\n\n{detail}")
