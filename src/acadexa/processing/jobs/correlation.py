"""Spark correlation analytics processing job - J4 (task 8.4, rules.md §8, §17, §18).

Job Responsibilities (F-D04, architecture.md §12):
1. Load integrated student features from J3.
2. Standardize variables using within-course z-scores (Task 8.3).
3. Compute distributed Spearman rank correlations for approved planted relationships:
   - Attendance vs Academic Marks (positive association)
   - LMS Engagement vs Academic Marks (positive association, school-dependent)
   - Late Submissions vs Academic Marks (negative association)
   - Quiz Attempts vs Academic Marks (positive association)
4. Compute distributed Spearman rank correlation for the decoy relationship:
   - Forum Activity vs Academic Marks (negative control, expected null association)
5. Evaluate correlations both overall and stratified by school.
6. Record outputs to Parquet.
7. Comply strictly with rules.md §17.3: zero driver-side collect/toPandas calls.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Sequence

from pyspark.sql import DataFrame, SparkSession

from acadexa.analytics.correlation import (
    APPROVED_CORRELATION_RELATIONSHIPS,
    evaluate_planted_and_decoy_correlations,
)
from acadexa.analytics.normalization import normalize_within_course

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class J4Config:
    """Configuration for Spark J4 correlation analytics job."""

    input_path: Path = Path("data/processed/student_features")
    output_path: Path = Path("data/processed/correlations")
    save_parquet: bool = True
    group_by_col: str = "school"
    partition_by_course: tuple[str, ...] = ("course_id", "semester_id")
    relationships: Sequence[dict[str, Any]] = APPROVED_CORRELATION_RELATIONSHIPS
    include_pearson: bool = True


@dataclass
class J4Result:
    """Complete result of running J4 correlation analytics job."""

    overall_correlations: DataFrame
    school_correlations: DataFrame
    normalized_features: DataFrame
    total_relationships_evaluated: int
    output_path: Path


def run_j4_correlation(
    spark: SparkSession,
    config: J4Config | None = None,
) -> J4Result:
    """Execute complete Spark J4 correlation analytics job.

    Args:
        spark: Active SparkSession.
        config: Optional J4 configuration.

    Returns:
        J4Result containing overall and school correlation DataFrames.
    """
    cfg = config or J4Config()
    logger.info("Starting J4 Correlation Analytics from %s", cfg.input_path)

    # 1. Read integrated student features
    features_df = spark.read.parquet(str(cfg.input_path))

    # 2. Apply within-course normalization (Task 8.3)
    logger.info("Applying within-course z-score normalization across course offerings")
    norm_features_df = normalize_within_course(
        features_df, partition_cols=cfg.partition_by_course
    )

    # 3. Compute overall Spearman (and optional Pearson) correlations
    logger.info(
        "Evaluating overall correlations across %d relationships (include_pearson=%s)",
        len(cfg.relationships),
        cfg.include_pearson,
    )
    overall_df = evaluate_planted_and_decoy_correlations(
        df=norm_features_df,
        relationships=cfg.relationships,
        group_by_col=None,
        include_pearson=cfg.include_pearson,
    )

    # 4. Compute school-stratified correlations
    logger.info(
        "Evaluating school-stratified correlations (grouped by %s, include_pearson=%s)",
        cfg.group_by_col,
        cfg.include_pearson,
    )
    school_df = evaluate_planted_and_decoy_correlations(
        df=norm_features_df,
        relationships=cfg.relationships,
        group_by_col=cfg.group_by_col,
        include_pearson=cfg.include_pearson,
    )

    total_evaluated = len(cfg.relationships)

    # 5. Save results to Parquet
    target_output = Path(cfg.output_path)
    if cfg.save_parquet:
        overall_path = target_output / "overall"
        school_path = target_output / "by_school"
        target_output.mkdir(parents=True, exist_ok=True)

        overall_df.write.mode("overwrite").parquet(str(overall_path))
        school_df.write.mode("overwrite").parquet(str(school_path))
        logger.info("Saved overall correlations to %s", overall_path)
        logger.info("Saved school correlations to %s", school_path)

    logger.info("J4 Correlation Analytics completed successfully")

    return J4Result(
        overall_correlations=overall_df,
        school_correlations=school_df,
        normalized_features=norm_features_df,
        total_relationships_evaluated=total_evaluated,
        output_path=target_output,
    )
