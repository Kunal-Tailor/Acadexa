"""Spark temporal trend detection processing job - J5 (task 8.6, rules.md §17, §18).

Job Responsibilities (F-D05, architecture.md §12):
1. Compute rolling 4-week LMS engagement trends over weekly event summaries.
2. Detect LMS engagement decline where current 4w <= 50% of prior 4w, and identify decline start week.
3. Compute graded-item coursework score trajectory across the semester.
4. Detect marks decline where latest 3 graded items drop >= 10 points below earlier average.
5. Integrate temporal trends at the student x course x semester grain.
6. Save trend indicators to Parquet.
7. Comply strictly with rules.md §17.3: zero driver-side collect/toPandas calls.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from acadexa.analytics.trends import (
    DEFAULT_LMS_COMPARISON_RATIO,
    DEFAULT_MARKS_DROP_THRESHOLD,
    DEFAULT_RECENT_GRADED_ITEMS,
    DEFAULT_WINDOW_WEEKS,
    compute_coursework_marks_trends,
    compute_lms_four_week_trends,
    integrate_temporal_trends,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class J5Config:
    """Configuration for Spark J5 trend detection job."""

    lms_weekly_path: Path = Path("data/processed/lms_weekly_engagement")
    coursework_path: Path = Path("data/processed/coursework")
    academic_records_path: Path = Path("data/processed/academic_records")
    output_path: Path = Path("data/processed/trend_indicators")
    window_weeks: int = DEFAULT_WINDOW_WEEKS
    comparison_ratio: float = DEFAULT_LMS_COMPARISON_RATIO
    recent_items: int = DEFAULT_RECENT_GRADED_ITEMS
    marks_drop_threshold: float = DEFAULT_MARKS_DROP_THRESHOLD
    save_parquet: bool = True
    partition_by: tuple[str, ...] = ("semester_id",)


@dataclass
class J5Result:
    """Complete result of running J5 trend detection job."""

    trend_indicators: DataFrame
    total_rows: int
    lms_decline_count: int
    marks_decline_count: int
    output_path: Path


def run_j5_trend_detection(
    spark: SparkSession,
    config: J5Config | None = None,
) -> J5Result:
    """Execute complete Spark J5 trend detection job.

    Args:
        spark: Active SparkSession.
        config: Optional J5 configuration.

    Returns:
        J5Result containing trend indicators DataFrame and summary counts.
    """
    cfg = config or J5Config()
    logger.info("Starting J5 Trend Detection")

    # 1. Read input processed datasets
    lms_weekly_df = spark.read.parquet(str(cfg.lms_weekly_path))
    coursework_df = spark.read.parquet(str(cfg.coursework_path))
    acad_df = None
    if cfg.academic_records_path.exists():
        acad_df = spark.read.parquet(str(cfg.academic_records_path))

    # 2. Compute LMS 4-week engagement trends
    logger.info(
        "Computing rolling %d-week LMS engagement trends (decline ratio <= %.2f)",
        cfg.window_weeks,
        cfg.comparison_ratio,
    )
    lms_trends_df = compute_lms_four_week_trends(
        lms_weekly_df=lms_weekly_df,
        window_weeks=cfg.window_weeks,
        comparison_ratio=cfg.comparison_ratio,
    )

    # 3. Compute coursework marks trends
    logger.info(
        "Computing coursework marks trends (latest %d items, drop threshold >= %.1f pts)",
        cfg.recent_items,
        cfg.marks_drop_threshold,
    )
    marks_trends_df = compute_coursework_marks_trends(
        coursework_df=coursework_df,
        recent_items=cfg.recent_items,
        drop_threshold=cfg.marks_drop_threshold,
    )

    # 4. Integrate temporal trends
    trends_df = integrate_temporal_trends(
        lms_trends_df=lms_trends_df,
        marks_trends_df=marks_trends_df,
        academic_records_df=acad_df,
    )

    total_rows = trends_df.count()
    lms_decliners = trends_df.filter(F.col("lms_decline_detected") == True).count()
    marks_decliners = trends_df.filter(F.col("marks_decline_detected") == True).count()

    logger.info(
        "Trend analysis complete across %d observations: %d LMS decliners, %d marks decliners",
        total_rows,
        lms_decliners,
        marks_decliners,
    )

    # 5. Save results to Parquet
    target_output = Path(cfg.output_path)
    if cfg.save_parquet:
        target_output.parent.mkdir(parents=True, exist_ok=True)
        writer = trends_df.write.mode("overwrite")
        if cfg.partition_by:
            writer = writer.partitionBy(*cfg.partition_by)
        writer.parquet(str(target_output))
        logger.info("Saved trend indicators to %s (%d rows)", target_output, total_rows)

    return J5Result(
        trend_indicators=trends_df,
        total_rows=total_rows,
        lms_decline_count=lms_decliners,
        marks_decline_count=marks_decliners,
        output_path=target_output,
    )
