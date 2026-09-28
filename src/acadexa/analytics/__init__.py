"""Acadexa analytics package (Phase 8, rules.md §18, folder_structure.md §13)."""

from __future__ import annotations

from acadexa.analytics.metrics import (
    calculate_academic_score,
    calculate_attendance_percentage,
    calculate_attendance_rate,
    calculate_late_submission_rate,
    calculate_missing_rate,
    calculate_quiz_retry_ratio,
    calculate_score_percentage,
)

__all__ = [
    "calculate_academic_score",
    "calculate_attendance_percentage",
    "calculate_attendance_rate",
    "calculate_late_submission_rate",
    "calculate_missing_rate",
    "calculate_quiz_retry_ratio",
    "calculate_score_percentage",
]
