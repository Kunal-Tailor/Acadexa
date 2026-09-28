"""Acadexa analytics package (Phase 8, rules.md §18, folder_structure.md §13)."""

from __future__ import annotations

from acadexa.analytics.correlation import (
    APPROVED_CORRELATION_RELATIONSHIPS,
    assign_fractional_ranks,
    compute_spearman_correlation,
    evaluate_planted_and_decoy_correlations,
    interpret_spearman_association,
)
from acadexa.analytics.metrics import (
    calculate_academic_score,
    calculate_attendance_percentage,
    calculate_attendance_rate,
    calculate_late_submission_rate,
    calculate_missing_rate,
    calculate_quiz_retry_ratio,
    calculate_score_percentage,
)
from acadexa.analytics.normalization import (
    DEFAULT_NORMALIZATION_METRICS,
    normalize_within_course,
)

__all__ = [
    # Metrics
    "calculate_academic_score",
    "calculate_attendance_percentage",
    "calculate_attendance_rate",
    "calculate_late_submission_rate",
    "calculate_missing_rate",
    "calculate_quiz_retry_ratio",
    "calculate_score_percentage",
    # Normalization
    "DEFAULT_NORMALIZATION_METRICS",
    "normalize_within_course",
    # Correlation
    "APPROVED_CORRELATION_RELATIONSHIPS",
    "assign_fractional_ranks",
    "compute_spearman_correlation",
    "evaluate_planted_and_decoy_correlations",
    "interpret_spearman_association",
]
