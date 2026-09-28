"""Temporal trend and decline detection analytics (Task 8.6, features.md F-D05, rules.md §17, §18).

Implements rolling four-week LMS engagement comparison and graded-item score trajectory analysis
matching the exact thresholds defined in config/risk/risk_signals.toml:
- Signal 2 LMS decline: Current 4-week engagement <= 50% of the previous 4-week period.
- Signal 4 Marks decline: Average of the latest 3 graded items >= 10 points below earlier comparison average.
"""

from __future__ import annotations

import logging
from typing import Sequence

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)

# Default parameters from config/risk/risk_signals.toml
DEFAULT_WINDOW_WEEKS: int = 4
DEFAULT_LMS_COMPARISON_RATIO: float = 0.50
DEFAULT_RECENT_GRADED_ITEMS: int = 3
DEFAULT_MARKS_DROP_THRESHOLD: float = 10.0


def compute_lms_four_week_trends(
    lms_weekly_df: DataFrame,
    window_weeks: int = DEFAULT_WINDOW_WEEKS,
    comparison_ratio: float = DEFAULT_LMS_COMPARISON_RATIO,
    partition_keys: Sequence[str] = ("student_id", "course_id", "semester_id"),
) -> DataFrame:
    """Compute rolling 4-week LMS engagement trends and detect significant declines.

    For each student x course x semester across teaching weeks (1..16):
    - Current 4-week events: sum(total_events) over rowsBetween(-3, 0)
    - Previous 4-week events: sum(total_events) over rowsBetween(-7, -4)
    - Decline trigger: week >= 8 AND prev_events > 0 AND (curr_events / prev_events) <= comparison_ratio

    Args:
        lms_weekly_df: DataFrame of weekly engagement summaries (grain: student, course, semester, week_number).
        window_weeks: Number of weeks in rolling window (default: 4).
        comparison_ratio: Threshold ratio defining decline (default: 0.50).
        partition_keys: Partitioning columns for time series (default: student_id, course_id, semester_id).

    Returns:
        DataFrame aggregated to student x course x semester grain with LMS trend indicators.
    """
    keys = list(partition_keys)
    w_order = Window.partitionBy(*[F.col(k) for k in keys]).orderBy("week_number")

    # Rolling window expressions: rowsBetween(-3, 0) for current 4w, rowsBetween(-7, -4) for previous 4w
    curr_4w_offset = -(window_weeks - 1)
    prev_4w_end = -window_weeks
    prev_4w_start = -(2 * window_weeks - 1)

    w_curr_4w = w_order.rowsBetween(curr_4w_offset, 0)
    w_prev_4w = w_order.rowsBetween(prev_4w_start, prev_4w_end)

    windowed_df = (
        lms_weekly_df.withColumn("events_curr_4w", F.sum("total_events").over(w_curr_4w))
        .withColumn("events_prev_4w", F.sum("total_events").over(w_prev_4w))
    )

    # Condition: week_number >= 2 * window_weeks, previous window has activity, ratio <= threshold
    decline_cond = (
        (F.col("week_number") >= (2 * window_weeks))
        & (F.col("events_prev_4w") > 0)
        & ((F.col("events_curr_4w") / F.col("events_prev_4w")) <= F.lit(comparison_ratio))
    )

    windowed_df = windowed_df.withColumn(
        "is_decline_week",
        F.when(decline_cond, F.lit(1)).otherwise(F.lit(0)),
    ).withColumn(
        "decline_trigger_week",
        F.when(decline_cond, F.col("week_number")).otherwise(F.lit(None).cast("int")),
    )

    # Term-end fixed windows: late-term (weeks 13..16) vs mid-term (weeks 9..12) vs early-term (weeks 1..8)
    agg_df = windowed_df.groupBy(*keys).agg(
        # Earliest week where rolling decline was observed
        F.min("decline_trigger_week").cast("int").alias("lms_decline_start_week"),
        F.max("is_decline_week").cast("int").alias("rolling_decline_flag"),
        # Fixed window aggregates
        F.coalesce(
            F.sum(F.when(F.col("week_number").between(1, 8), F.col("total_events")).otherwise(0)),
            F.lit(0),
        ).cast("long").alias("lms_early_events_w1_8"),
        F.coalesce(
            F.sum(F.when(F.col("week_number").between(9, 12), F.col("total_events")).otherwise(0)),
            F.lit(0),
        ).cast("long").alias("lms_prev_4w_events"),
        F.coalesce(
            F.sum(F.when(F.col("week_number").between(13, 16), F.col("total_events")).otherwise(0)),
            F.lit(0),
        ).cast("long").alias("lms_current_4w_events"),
        # Linear slope over 16 teaching weeks: Cov(w, y) / Var(w)
        F.coalesce(
            (F.avg(F.col("week_number") * F.col("total_events")) - F.avg("week_number") * F.avg("total_events"))
            / (F.avg(F.col("week_number") * F.col("week_number")) - F.avg("week_number") * F.avg("week_number")),
            F.lit(0.0),
        ).cast("double").alias("lms_weekly_slope"),
    )

    # Derive term-end ratio and overall LMS decline flag
    final_df = (
        agg_df.withColumn(
            "lms_recent_vs_prior_ratio",
            F.when(
                F.col("lms_prev_4w_events") > 0,
                F.round(F.col("lms_current_4w_events") / F.col("lms_prev_4w_events"), 4),
            ).otherwise(F.lit(1.0)),
        )
        .withColumn(
            "lms_decline_detected",
            F.when(
                (F.col("rolling_decline_flag") == 1)
                | (
                    (F.col("lms_prev_4w_events") > 0)
                    & (F.col("lms_recent_vs_prior_ratio") <= F.lit(comparison_ratio))
                ),
                F.lit(True),
            ).otherwise(F.lit(False)),
        )
        .drop("rolling_decline_flag")
    )

    return final_df


def compute_coursework_marks_trends(
    coursework_df: DataFrame,
    recent_items: int = DEFAULT_RECENT_GRADED_ITEMS,
    drop_threshold: float = DEFAULT_MARKS_DROP_THRESHOLD,
    partition_keys: Sequence[str] = ("student_id", "course_id", "semester_id"),
) -> DataFrame:
    """Compute score trends across graded coursework items and detect performance decline.

    Compares average score percentage of the latest N items against earlier items in the course.
    Formula: marks_drop = earlier_avg_score_pct - recent_avg_score_pct >= drop_threshold (default: 10 pts).

    Args:
        coursework_df: Cleaned coursework DataFrame.
        recent_items: Number of most recent graded items to evaluate (default: 3).
        drop_threshold: Minimum point drop defining decline (default: 10.0 points).
        partition_keys: Grouping keys for course offering (default: student_id, course_id, semester_id).

    Returns:
        DataFrame aggregated to student x course x semester grain with marks trend indicators.
    """
    keys = list(partition_keys)

    # Ensure semester_id is available
    df = coursework_df
    if "semester_id" not in df.columns:
        # Import semester helper
        from acadexa.processing.jobs.feature_table import derive_semester_id_from_date
        df = df.withColumn("semester_id", derive_semester_id_from_date("due_date"))

    # Filter graded items with scores
    graded_df = df.filter(F.col("score").isNotNull() & (F.col("max_score") > 0))
    graded_df = graded_df.withColumn(
        "item_score_pct",
        (F.col("score") / F.col("max_score")) * 100.0,
    )

    # Window ordered by due_date descending to identify latest N items
    w_desc = Window.partitionBy(*[F.col(k) for k in keys]).orderBy(F.col("due_date").desc(), F.col("item_id").desc())
    ranked_df = graded_df.withColumn("recency_rank", F.row_number().over(w_desc))

    # Aggregate recent vs earlier items
    agg_df = ranked_df.groupBy(*keys).agg(
        F.count("*").cast("int").alias("total_graded_items"),
        F.round(
            F.avg(F.when(F.col("recency_rank") <= F.lit(recent_items), F.col("item_score_pct"))),
            2,
        ).cast("double").alias("recent_coursework_avg"),
        F.round(
            F.avg(F.when(F.col("recency_rank") > F.lit(recent_items), F.col("item_score_pct"))),
            2,
        ).cast("double").alias("earlier_coursework_avg"),
    )

    # Compute drop points and decline indicator
    res_df = (
        agg_df.withColumn(
            "marks_drop_points",
            F.when(
                F.col("earlier_coursework_avg").isNotNull() & F.col("recent_coursework_avg").isNotNull(),
                F.round(F.col("earlier_coursework_avg") - F.col("recent_coursework_avg"), 2),
            ).otherwise(F.lit(0.0)),
        )
        .withColumn(
            "marks_decline_detected",
            F.when(
                (F.col("earlier_coursework_avg").isNotNull())
                & (F.col("marks_drop_points") >= F.lit(drop_threshold)),
                F.lit(True),
            ).otherwise(F.lit(False)),
        )
    )

    return res_df


def integrate_temporal_trends(
    lms_trends_df: DataFrame,
    marks_trends_df: DataFrame,
    academic_records_df: DataFrame | None = None,
    join_keys: Sequence[str] = ("student_id", "course_id", "semester_id"),
) -> DataFrame:
    """Integrate LMS and marks trends into a unified temporal indicators DataFrame.

    Args:
        lms_trends_df: Aggregated LMS 4-week trend DataFrame.
        marks_trends_df: Aggregated coursework marks trend DataFrame.
        academic_records_df: Optional academic records for term-level marks comparison.
        join_keys: Join columns defining student-course offering grain.

    Returns:
        Unified DataFrame with all temporal indicators.
    """
    keys = list(join_keys)
    joined = lms_trends_df.join(marks_trends_df, on=keys, how="outer")

    if academic_records_df is not None:
        acad_clean = academic_records_df.withColumn(
            "exam_marks_trend",
            (F.col("endterm_marks") - F.col("internal_marks")).cast("int"),
        ).select(*keys, "exam_marks_trend")
        joined = joined.join(acad_clean, on=keys, how="left")
    else:
        joined = joined.withColumn("exam_marks_trend", F.lit(0))

    # Fill defaults for absent records
    defaults = {
        "lms_decline_detected": False,
        "lms_recent_vs_prior_ratio": 1.0,
        "lms_current_4w_events": 0,
        "lms_prev_4w_events": 0,
        "lms_early_events_w1_8": 0,
        "lms_weekly_slope": 0.0,
        "marks_decline_detected": False,
        "marks_drop_points": 0.0,
        "total_graded_items": 0,
        "exam_marks_trend": 0,
    }

    for col_name, val in defaults.items():
        if col_name in joined.columns:
            joined = joined.withColumn(col_name, F.coalesce(F.col(col_name), F.lit(val)))

    return joined.orderBy(*keys)
