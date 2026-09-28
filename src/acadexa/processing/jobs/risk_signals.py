"""Spark risk signal computation job - J6 (tasks 8.7 & 8.8, rules.md §8, §17, §18, §22).

Job Responsibilities (F-D06, architecture.md §12):
1. Load student features (from J3) and trend indicators (from J5).
2. Apply the five approved rule-based risk signals exactly from configuration:
   - Low attendance (< 75%)
   - LMS decline (<= 50% comparison ratio)
   - Late submissions (> 30% late rate)
   - Marks decline (>= 10 pts drop)
   - Low quiz activity (bottom quartile of course)
3. Construct traceable explainability strings for every signal (task 8.8).
4. Roll up to student-level risk indicators conforming to RISK_INDICATORS_SCHEMA.
5. Save risk indicators to Parquet.
6. Strictly adhere to rules.md §17.3: zero driver-side collect/toPandas calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from acadexa.analytics.risk import (
    RiskSignalThresholds,
    build_student_risk_indicators,
    evaluate_student_course_risk_signals,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class J6Config:
    """Configuration for Spark J6 risk signals job."""

    student_features_path: Path = Path("data/processed/student_features")
    trend_indicators_path: Path = Path("data/processed/trend_indicators")
    output_path: Path = Path("data/processed/risk_indicators")
    course_level_output_path: Path | None = None
    thresholds: RiskSignalThresholds | None = None
    config_path: Path | str | None = None
    evaluation_week_start: str | None = "2026-04-20"
    include_hierarchy: bool = False
    save_parquet: bool = True
    partition_by: tuple[str, ...] = ()


@dataclass
class J6Result:
    """Complete result of running J6 risk signals job."""

    risk_indicators: DataFrame
    total_students: int
    signal_counts_breakdown: dict[int, int]
    flagged_students_count: int
    high_risk_students_count: int
    output_path: Path
    course_risk_indicators: DataFrame | None = None


def run_j6_risk_signals(
    spark: SparkSession,
    config: J6Config | None = None,
) -> J6Result:
    """Execute complete Spark J6 risk signals job.

    Args:
        spark: Active SparkSession.
        config: Optional J6 configuration.

    Returns:
        J6Result containing student risk indicators DataFrame and summary metrics.
    """
    cfg = config or J6Config()
    logger.info("Starting J6 Risk Signals Job")

    # 1. Resolve thresholds from config or arguments
    th = cfg.thresholds
    if th is None:
        th = RiskSignalThresholds.from_config(cfg.config_path)

    logger.info(
        "Using thresholds: attendance < %.1f%%, lms_ratio <= %.2f, late_rate > %.2f, "
        "marks_drop >= %.1f pts, quiz_percentile < %.2f",
        th.attendance_threshold,
        th.lms_comparison_ratio,
        th.late_rate_threshold,
        th.marks_drop_threshold,
        th.quiz_percentile_threshold,
    )

    # 2. Read student features
    student_features_df = spark.read.parquet(str(cfg.student_features_path))

    # 3. Read trend indicators if available
    integrated_df = student_features_df
    trend_path = Path(cfg.trend_indicators_path)
    if trend_path.exists():
        trend_df = spark.read.parquet(str(trend_path))
        join_keys = [
            k for k in ("student_id", "course_id", "semester_id")
            if k in student_features_df.columns and k in trend_df.columns
        ]
        if join_keys:
            # Drop any duplicate non-key columns from trend_df before joining
            drop_cols = [c for c in trend_df.columns if c in student_features_df.columns and c not in join_keys]
            trend_to_join = trend_df.drop(*drop_cols)
            integrated_df = student_features_df.join(trend_to_join, on=join_keys, how="left")

    # 4. Evaluate risk signals at student x course x semester grain
    course_risk_df = evaluate_student_course_risk_signals(integrated_df, thresholds=th)

    # 5. Build student-level risk indicators conforming to schema
    student_risk_df = build_student_risk_indicators(
        course_risk_df,
        evaluation_week_start=cfg.evaluation_week_start,
        include_hierarchy=cfg.include_hierarchy,
    )

    # 6. Compute summary counts (rules.md §17.3: zero collect() calls)
    total_students = student_risk_df.count()
    flagged_students = student_risk_df.filter(F.col("signal_count") > 0).count()
    high_risk_students = student_risk_df.filter(F.col("signal_count") >= 3).count()

    signal_counts_breakdown = {
        i: student_risk_df.filter(F.col("signal_count") == i).count()
        for i in range(6)
    }

    logger.info(
        "Risk analysis complete for %d students: %d flagged (>=1 signal), %d high-risk (>=3 signals)",
        total_students,
        flagged_students,
        high_risk_students,
    )

    # 7. Save outputs to Parquet
    target_output = Path(cfg.output_path)
    if cfg.save_parquet:
        target_output.parent.mkdir(parents=True, exist_ok=True)
        writer = student_risk_df.write.mode("overwrite")
        if cfg.partition_by:
            writer = writer.partitionBy(*cfg.partition_by)
        writer.parquet(str(target_output))
        logger.info("Saved student risk indicators to %s (%d rows)", target_output, total_students)

        if cfg.course_level_output_path:
            course_target = Path(cfg.course_level_output_path)
            course_target.parent.mkdir(parents=True, exist_ok=True)
            course_risk_df.write.mode("overwrite").parquet(str(course_target))
            logger.info("Saved course-level risk evaluations to %s", course_target)

    return J6Result(
        risk_indicators=student_risk_df,
        total_students=total_students,
        signal_counts_breakdown=signal_counts_breakdown,
        flagged_students_count=flagged_students,
        high_risk_students_count=high_risk_students,
        output_path=target_output,
        course_risk_indicators=course_risk_df,
    )
