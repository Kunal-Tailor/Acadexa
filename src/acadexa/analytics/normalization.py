"""Within-course normalization for cross-factor learning analytics (Task 8.3, features.md F-D04, rules.md §17).

Provides within-course standardization (z-score normalization) to decouple student behavioral
traits and performance from course difficulty and grading variance confounders.
"""

from __future__ import annotations

import logging
from typing import Sequence

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)

# Default metrics normalized within course sections
DEFAULT_NORMALIZATION_METRICS: tuple[str, ...] = (
    "academic_score",
    "total_marks",
    "attendance_percentage",
    "attendance_rate",
    "lms_total_events",
    "late_submission_rate",
    "total_quiz_attempts",
    "coursework_score_pct",
    "lms_forum_posts",
)


def normalize_within_course(
    df: DataFrame,
    metric_cols: Sequence[str] | None = None,
    partition_cols: Sequence[str] = ("course_id", "semester_id"),
    prefix: str = "z_",
) -> DataFrame:
    """Standardize metrics using within-course z-scores.

    Calculates: z = (x - mean(x)) / stddev(x) partitioned by course section.
    When standard deviation is zero or null (e.g. single-student or zero-variance sections),
    z-score safely evaluates to 0.0.

    Args:
        df: Input DataFrame containing student-course observations.
        metric_cols: Sequence of numeric metric column names to normalize.
            Defaults to DEFAULT_NORMALIZATION_METRICS present in df.
        partition_cols: Grouping columns defining course offerings (default: course_id, semester_id).
        prefix: Column prefix for normalized variables (default: "z_").

    Returns:
        DataFrame enriched with normalized z-score columns.
    """
    selected_metrics = (
        [c for c in metric_cols if c in df.columns]
        if metric_cols is not None
        else [c for c in DEFAULT_NORMALIZATION_METRICS if c in df.columns]
    )

    if not selected_metrics:
        logger.warning("No matching metric columns found for within-course normalization")
        return df

    # Window partitioned by course offering
    w = Window.partitionBy(*[F.col(c) for c in partition_cols])
    result_df = df

    for col_name in selected_metrics:
        z_col_name = f"{prefix}{col_name}"
        mean_expr = F.avg(F.col(col_name)).over(w)
        std_expr = F.stddev(F.col(col_name)).over(w)

        result_df = result_df.withColumn(
            z_col_name,
            F.when(
                std_expr.isNotNull() & (std_expr > 0),
                (F.col(col_name) - mean_expr) / std_expr,
            )
            .otherwise(0.0)
            .cast("double"),
        )

    # Alias difficulty_adjusted_performance if academic_score was normalized
    if "z_academic_score" in result_df.columns and "difficulty_adjusted_performance" not in result_df.columns:
        result_df = result_df.withColumn(
            "difficulty_adjusted_performance", F.col("z_academic_score")
        )

    return result_df
