"""Course difficulty assignment (F-B03 difficulty metadata).

Assigns each configured course a difficulty bucket (easy / medium /
hard) and a numeric difficulty factor in ``[0, 1]`` from the generator
configuration shares (rules.md §8.3: configuration-driven, none
hard-coded). Assignment is seeded per :class:`GeneratorRun`, so the
same seed always buckets the same courses the same way.

Numeric difficulty ranges per bucket (engineering parameter):

- easy: ``[0.0, 0.4)``
- medium: ``[0.4, 0.7)``
- hard: ``[0.7, 1.0)``

Academic-record generation uses ``difficulty`` as a marks drag
(``difficulty × course_difficulty.max_score_drag`` points removed
from expected marks) — the documented confounder (memory.md §7).
Later behavioral tasks must reuse this assignment so course documents
and academic records agree on each course's difficulty.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from acadexa.generator.foundation import GeneratorError, GeneratorRun

_SHARE_KEYS = {
    "easy": "easy_share",
    "medium": "medium_share",
    "hard": "hard_share",
}
_LEVEL_RANGES = {
    "easy": (0.0, 0.4),
    "medium": (0.4, 0.7),
    "hard": (0.7, 1.0),
}


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _bucket_counts(shares: dict[str, float], total: int) -> dict[str, int]:
    """Allocate ``total`` courses across buckets by largest remainder."""
    raw = {level: shares[level] * total for level in shares}
    counts = {level: int(value) for level, value in raw.items()}
    remainder = total - sum(counts.values())
    ranked = sorted(
        shares,
        key=lambda level: (raw[level] - counts[level], level),
        reverse=True,
    )
    for level in ranked[:remainder]:
        counts[level] += 1
    return counts


def assign_course_difficulty(
    run: GeneratorRun,
    courses: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Assign difficulty buckets and factors to ``courses``.

    Args:
        run: Seeded generator run providing the validated
            ``course_difficulty`` configuration and the deterministic
            ``course_difficulty`` random sub-stream.
        courses: Hierarchy course records, each with a ``course_id``.

    Returns:
        Mapping of ``course_id`` to ``{"difficulty_level", "difficulty"}``.

    Raises:
        GeneratorError: if configuration is missing/invalid or a
            course lacks a ``course_id``.
    """
    _check(
        "generator" in run.configs
        and "course_difficulty" in run.configs.get("generator", {}),
        "configs missing generator course_difficulty configuration",
    )
    difficulty_config = run.configs["generator"]["course_difficulty"]
    for share_key in _SHARE_KEYS.values():
        _check(
            share_key in difficulty_config,
            f"generator course_difficulty missing '{share_key}'",
        )
    _check(bool(courses), "assign_course_difficulty: courses must not be empty")

    shares = {
        level: float(difficulty_config[share_key])
        for level, share_key in _SHARE_KEYS.items()
    }

    rng = run.child_rng("course_difficulty")
    order = rng.permutation(len(courses))
    counts = _bucket_counts(shares, len(courses))

    assignments: dict[str, dict[str, Any]] = {}
    position = 0
    for level in _SHARE_KEYS:
        low, high = _LEVEL_RANGES[level]
        for offset in range(counts[level]):
            course = courses[int(order[position + offset])]
            course_id = course.get("course_id")
            _check(
                isinstance(course_id, str) and course_id != "",
                "assign_course_difficulty: course missing 'course_id'",
            )
            assignments[course_id] = {
                "difficulty_level": level,
                "difficulty": float(rng.uniform(low, high)),
            }
        position += counts[level]
    return assignments
