"""Synthetic decliner population (memory.md §6, original_idea §7.1).

Approximately 8% of students are **decliners**: their engagement fades
during the semester and their marks drop a few weeks later. The
declines give trend detection (F-D05) and the marks-decline risk
signal (F-D06) real structure to find.

Engineering decisions:

- Selection is an independent Bernoulli draw per student from the
  dedicated ``decliners`` RNG child stream, so the population is
  reproducible from the seed and unaffected by changes to other
  generator streams.
- Decliner status is hidden generator state: it is never written to
  the ``students`` collection (frozen students schema, F-B02), exactly
  like the behavioral traits.
- Decline timing is entirely configuration-driven (no hard-coded
  constants): ``rate``, ``start_week``, ``weekly_engagement_decay``,
  ``marks_decline_lag_weeks``, ``component_weeks``,
  ``marks_weekly_decline`` and ``score_weekly_decay``. This module
  validates the whole ``behavior.decliners`` section; consumers call
  :func:`generate_decliner_flags` first and then read the validated
  parameters.
- Declines are deterministic post-processing applied after each
  consumer's random draws, so non-decliner rows are byte-identical to
  a run without decliners and no consumer RNG stream shifts position.

Decline model applied by the consumers:

- Weekly attendance multiplies the weekly probability by
  ``(1 − weekly_engagement_decay) ** elapsed`` for weeks on or after
  ``start_week`` (engagement fade).
- Academic-record components lose ``marks_weekly_decline`` points per
  week from ``start_week + marks_decline_lag_weeks`` onward, timed by
  each component's configured collection week (marks lag engagement).
- Coursework score quality decays by ``score_weekly_decay`` per week
  for items due from the marks-decline start onward.

LMS event decay uses the same engagement fade and is applied by the
LMS generator (tasks 5.1/5.2); nothing LMS-specific is implemented
here.
"""

from __future__ import annotations

from typing import Any

from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students

_DECLINER_PARAM_KEYS = (
    "rate",
    "start_week",
    "weekly_engagement_decay",
    "marks_decline_lag_weeks",
    "component_weeks",
    "marks_weekly_decline",
    "score_weekly_decay",
)


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_decliner_params(behavior: dict[str, Any]) -> dict[str, Any]:
    """Validate and return the ``behavior.decliners`` configuration."""
    _check(
        "decliners" in behavior,
        "configs missing generator behavior.decliners",
    )
    params = behavior["decliners"]
    for key in _DECLINER_PARAM_KEYS:
        _check(
            key in params,
            f"generator behavior.decliners missing '{key}'",
        )
    rate = params["rate"]
    _check(
        _is_number(rate) and 0.0 <= rate <= 1.0,
        "generator behavior.decliners.rate must be in [0, 1]",
    )
    start_week = params["start_week"]
    _check(
        isinstance(start_week, int)
        and not isinstance(start_week, bool)
        and start_week >= 1,
        "generator behavior.decliners.start_week must be a positive integer",
    )
    engagement_decay = params["weekly_engagement_decay"]
    _check(
        _is_number(engagement_decay) and 0.0 <= engagement_decay < 1.0,
        "generator behavior.decliners.weekly_engagement_decay must be in [0, 1)",
    )
    lag = params["marks_decline_lag_weeks"]
    _check(
        isinstance(lag, int)
        and not isinstance(lag, bool)
        and lag >= 1,
        "generator behavior.decliners.marks_decline_lag_weeks "
        "must be a positive integer",
    )
    component_weeks = params["component_weeks"]
    _check(
        isinstance(component_weeks, dict)
        and all(
            key in component_weeks for key in ("internal", "midterm", "endterm")
        ),
        "generator behavior.decliners.component_weeks must define "
        "internal/midterm/endterm",
    )
    weeks_list = [component_weeks[key] for key in ("internal", "midterm", "endterm")]
    _check(
        all(
            isinstance(week, int) and not isinstance(week, bool) and week >= 1
            for week in weeks_list
        )
        and weeks_list[0] < weeks_list[1] < weeks_list[2],
        "generator behavior.decliners.component_weeks must be positive integers "
        "with internal < midterm < endterm",
    )
    marks_weekly_decline = params["marks_weekly_decline"]
    _check(
        _is_number(marks_weekly_decline) and marks_weekly_decline >= 0,
        "generator behavior.decliners.marks_weekly_decline must be >= 0",
    )
    score_decay = params["score_weekly_decay"]
    _check(
        _is_number(score_decay) and 0.0 <= score_decay < 1.0,
        "generator behavior.decliners.score_weekly_decay must be in [0, 1)",
    )
    return params


def generate_decliner_flags(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
) -> dict[str, bool]:
    """Select the decliner population for every student (task 4.8).

    Args:
        run: Seeded generator run whose ``configs`` contain the
            validated ``behavior.decliners`` configuration.
        students: Previously generated student documents. When
            omitted, :func:`generate_students` is called for this run.

    Returns:
        Mapping of ``student_id`` to ``True`` for decliners and
        ``False`` otherwise, drawn independently with probability
        ``rate`` per student.

    Raises:
        GeneratorError: if required decliner configuration is missing
            or out of range.
    """
    configs = run.configs
    _check(
        "generator" in configs and "behavior" in configs.get("generator", {}),
        "configs missing generator behavior configuration",
    )
    behavior = configs["generator"]["behavior"]
    params = _validate_decliner_params(behavior)

    if students is None:
        students = generate_students(run)

    rate = float(params["rate"])
    rng = run.child_rng("decliners")
    draws = rng.random(len(students))
    return {
        student["student_id"]: bool(draws[index] < rate)
        for index, student in enumerate(students)
    }
