"""Spark LMS event weekly aggregation processing job - J2 (task 7.5, rules.md §17, §18).

Job Responsibilities (F-D02, architecture.md §12):
1. Convert event-level LMS data into weekly student-course engagement summaries.
2. Group by student_id, course_id, school, semester_id, week_start, and week_number.
3. Compute total weekly event count and total duration in seconds.
4. Calculate distinct active days in the week [1..7].
5. Aggregate approved activity categories:
   - content_views: VIDEO_VIEW, VIDEO_COMPLETE, PDF_VIEW, RESOURCE_DOWNLOAD, COURSE_PAGE_VIEW
   - assessment_events: QUIZ_ATTEMPT, ASSIGNMENT_VIEW, ASSIGNMENT_SUBMISSION
   - participation_events: FORUM_POST
   - access_events: LOGIN, LOGOUT
6. Compute specific event type breakdowns (video_views, quiz_attempts, assignment_views,
   assignment_submissions, forum_posts, logins).
7. Execute purely via distributed Spark operations without collecting event rows to the driver.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)

# Approved activity category groupings per F-D02, design.md §23, rules.md §14
APPROVED_ACTIVITY_CATEGORIES: dict[str, tuple[str, ...]] = {
    "content_views": (
        "VIDEO_VIEW",
        "VIDEO_COMPLETE",
        "PDF_VIEW",
        "RESOURCE_DOWNLOAD",
        "COURSE_PAGE_VIEW",
    ),
    "assessment_events": (
        "QUIZ_ATTEMPT",
        "ASSIGNMENT_VIEW",
        "ASSIGNMENT_SUBMISSION",
    ),
    "participation_events": (
        "FORUM_POST",
    ),
    "access_events": (
        "LOGIN",
        "LOGOUT",
    ),
}

# University semester date ranges (config/university/academic_periods.toml)
SEMESTER_BOUNDS: tuple[tuple[str, str, str], ...] = (
    ("S1", "2024-07-15", "2024-11-03"),
    ("S2", "2025-01-06", "2025-04-27"),
    ("S3", "2025-07-14", "2025-11-02"),
    ("S4", "2026-01-05", "2026-04-26"),
)


@dataclass(frozen=True)
class J2Config:
    """Configuration for Spark J2 event aggregation job."""

    input_path: Path = Path("data/processed/lms_events")
    raw_fallback_path: Path = Path("data/raw/lms_events")
    output_path: Path = Path("data/processed/lms_weekly_engagement")
    save_parquet: bool = True
    partition_by: tuple[str, ...] = ("semester_id",)


@dataclass
class J2Result:
    """Complete result of running J2 event aggregation."""

    weekly_engagement: DataFrame
    total_input_events: int
    total_output_rows: int
    output_path: Path


def build_semester_expressions() -> tuple[F.Column, F.Column]:
    """Build Spark expressions mapping week_start date to semester_id and week_number.

    Returns:
        Tuple of (semester_id_col, week_number_col).
    """
    # Build semester_id condition chain
    sem_expr = F.lit("UNKNOWN")
    sem_start_expr = F.col("week_start")

    for sem_id, start_date, end_date in reversed(SEMESTER_BOUNDS):
        sem_expr = F.when(
            F.col("week_start").between(start_date, end_date), F.lit(sem_id)
        ).otherwise(sem_expr)
        sem_start_expr = F.when(
            F.col("week_start").between(start_date, end_date), F.lit(start_date)
        ).otherwise(sem_start_expr)

    # Calculate 1-indexed teaching week within semester [1..16]
    week_num_expr = (
        F.datediff(F.col("week_start"), sem_start_expr) / 7 + 1
    ).cast("int")

    return sem_expr, week_num_expr


def aggregate_weekly_lms_events(lms_df: DataFrame) -> DataFrame:
    """Aggregate event-level LMS data into weekly student-course engagement summaries.

    Grain: student_id × course_id × week_start (Monday).

    Args:
        lms_df: Cleaned or raw LMS events DataFrame.

    Returns:
        Aggregated DataFrame with weekly engagement metrics.
    """
    # 1. Flatten nested metadata and extract date/calendar fields
    has_meta_struct = "meta" in lms_df.columns and isinstance(
        lms_df.schema["meta"].dataType.typeName(), str
    )

    if has_meta_struct:
        flat_df = (
            lms_df.withColumn("student_id", F.trim(F.upper(F.col("meta.student_id"))))
            .withColumn("course_id", F.trim(F.upper(F.col("meta.course_id"))))
            .withColumn("school", F.col("meta.school"))
        )
    else:
        flat_df = (
            lms_df.withColumn("student_id", F.trim(F.upper(F.col("student_id"))))
            .withColumn("course_id", F.trim(F.upper(F.col("course_id"))))
            .withColumn(
                "school",
                F.col("school") if "school" in lms_df.columns else F.lit("UNKNOWN"),
            )
        )

    # 2. Derive calendar grain fields
    # week_start: Monday of the event's calendar week
    flat_df = (
        flat_df.withColumn("event_date", F.to_date(F.col("timestamp")))
        .withColumn("week_start", F.to_date(F.date_trunc("week", F.col("timestamp"))))
    )

    # Derive semester_id and week_number
    sem_col, week_num_col = build_semester_expressions()
    flat_df = flat_df.withColumn("semester_id", sem_col).withColumn(
        "week_number", week_num_col
    )

    # 3. Distributed group-by aggregation (rules.md §17.4)
    group_cols = [
        "student_id",
        "course_id",
        "school",
        "semester_id",
        "week_start",
        "week_number",
    ]

    content_types = APPROVED_ACTIVITY_CATEGORIES["content_views"]
    assessment_types = APPROVED_ACTIVITY_CATEGORIES["assessment_events"]
    participation_types = APPROVED_ACTIVITY_CATEGORIES["participation_events"]
    access_types = APPROVED_ACTIVITY_CATEGORIES["access_events"]

    agg_df = flat_df.groupBy(*group_cols).agg(
        # Overall engagement activity
        F.count("*").alias("total_events"),
        F.coalesce(
            F.sum(
                F.when(F.col("duration_sec") > 0, F.col("duration_sec")).otherwise(0)
            ),
            F.lit(0),
        ).alias("total_duration_sec"),
        # Weekly active days (distinct calendar days with activity in [1..7])
        F.countDistinct("event_date").alias("active_days"),
        # Approved activity category roll-ups
        F.sum(
            F.when(F.col("activity_type").isin(*content_types), 1).otherwise(0)
        ).alias("content_views"),
        F.sum(
            F.when(F.col("activity_type").isin(*assessment_types), 1).otherwise(0)
        ).alias("assessment_events"),
        F.sum(
            F.when(F.col("activity_type").isin(*participation_types), 1).otherwise(0)
        ).alias("participation_events"),
        F.sum(
            F.when(F.col("activity_type").isin(*access_types), 1).otherwise(0)
        ).alias("access_events"),
        # Specific event-type breakdowns
        F.sum(
            F.when(
                F.col("activity_type").isin("VIDEO_VIEW", "VIDEO_COMPLETE"), 1
            ).otherwise(0)
        ).alias("video_views"),
        F.sum(
            F.when(F.col("activity_type") == "QUIZ_ATTEMPT", 1).otherwise(0)
        ).alias("quiz_attempts"),
        F.sum(
            F.when(F.col("activity_type") == "ASSIGNMENT_VIEW", 1).otherwise(0)
        ).alias("assignment_views"),
        F.sum(
            F.when(F.col("activity_type") == "ASSIGNMENT_SUBMISSION", 1).otherwise(0)
        ).alias("assignment_submissions"),
        F.sum(
            F.when(F.col("activity_type") == "FORUM_POST", 1).otherwise(0)
        ).alias("forum_posts"),
        F.sum(
            F.when(F.col("activity_type") == "LOGIN", 1).otherwise(0)
        ).alias("logins"),
    )

    return agg_df.orderBy("student_id", "course_id", "week_start")


def run_j2_event_aggregation(
    spark: SparkSession,
    config: J2Config | None = None,
) -> J2Result:
    """Execute complete Spark LMS event aggregation job (J2).

    Args:
        spark: Active SparkSession.
        config: Optional J2 configuration.

    Returns:
        J2Result containing weekly engagement DataFrame and output metadata.
    """
    cfg = config or J2Config()
    input_path = Path(cfg.input_path)
    if not input_path.exists():
        input_path = Path(cfg.raw_fallback_path)

    logger.info("Starting J2 Event Aggregation from %s", input_path)

    # 1. Read input events
    lms_events_df = spark.read.parquet(str(input_path))
    input_events_count = lms_events_df.count()

    # 2. Perform distributed weekly aggregation
    weekly_engagement_df = aggregate_weekly_lms_events(lms_events_df)
    output_rows_count = weekly_engagement_df.count()

    # 3. Save to Parquet
    target_output = Path(cfg.output_path)
    if cfg.save_parquet:
        target_output.parent.mkdir(parents=True, exist_ok=True)
        writer = weekly_engagement_df.write.mode("overwrite")
        if cfg.partition_by:
            writer = writer.partitionBy(*cfg.partition_by)
        writer.parquet(str(target_output))
        logger.info(
            "Saved weekly engagement dataset to %s (%d rows)",
            target_output,
            output_rows_count,
        )

    logger.info(
        "J2 Event Aggregation completed: %d input events aggregated into %d weekly summary rows",
        input_events_count,
        output_rows_count,
    )

    return J2Result(
        weekly_engagement=weekly_engagement_df,
        total_input_events=input_events_count,
        total_output_rows=output_rows_count,
        output_path=target_output,
    )
