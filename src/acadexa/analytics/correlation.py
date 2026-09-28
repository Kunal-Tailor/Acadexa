"""Spearman correlation analytics engine (Task 8.4, features.md F-D04, rules.md §8, §18).

Implements distributed Spearman rank correlation analysis across planted relationships
and the decoy relationship, supporting overall and school-stratified evaluations.
All results are explicitly documented as statistical associations, never as causal effects.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Sequence

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)

# Approved analytical relationships for recovery testing (ground_truth.py, features.md F-B09)
APPROVED_CORRELATION_RELATIONSHIPS: tuple[dict[str, str], ...] = (
    {
        "relationship_id": "attendance_marks",
        "name": "Attendance vs Academic Marks",
        "independent_var_raw": "attendance_percentage",
        "independent_var_norm": "z_attendance_percentage",
        "dependent_var_raw": "academic_score",
        "dependent_var_norm": "z_academic_score",
        "relationship_type": "planted",
        "expected_direction": "positive",
        "expected_strength": "moderate",
    },
    {
        "relationship_id": "lms_engagement_marks",
        "name": "LMS Engagement vs Academic Marks",
        "independent_var_raw": "lms_total_events",
        "independent_var_norm": "z_lms_total_events",
        "dependent_var_raw": "academic_score",
        "dependent_var_norm": "z_academic_score",
        "relationship_type": "planted",
        "expected_direction": "positive",
        "expected_strength": "moderate_school_dependent",
    },
    {
        "relationship_id": "late_submissions_marks",
        "name": "Late Submissions vs Academic Marks",
        "independent_var_raw": "late_submission_rate",
        "independent_var_norm": "z_late_submission_rate",
        "dependent_var_raw": "academic_score",
        "dependent_var_norm": "z_academic_score",
        "relationship_type": "planted",
        "expected_direction": "negative",
        "expected_strength": "moderate",
    },
    {
        "relationship_id": "quiz_attempts_marks",
        "name": "Quiz Attempts vs Academic Marks",
        "independent_var_raw": "total_quiz_attempts",
        "independent_var_norm": "z_total_quiz_attempts",
        "dependent_var_raw": "academic_score",
        "dependent_var_norm": "z_academic_score",
        "relationship_type": "planted",
        "expected_direction": "positive",
        "expected_strength": "moderate",
    },
    {
        "relationship_id": "decoy_forum_marks",
        "name": "Forum Activity vs Academic Marks (Decoy)",
        "independent_var_raw": "lms_forum_posts",
        "independent_var_norm": "z_lms_forum_posts",
        "dependent_var_raw": "academic_score",
        "dependent_var_norm": "z_academic_score",
        "relationship_type": "decoy",
        "expected_direction": "none",
        "expected_strength": "none",
    },
)


def interpret_spearman_association(correlation: float | None) -> str:
    """Provide standardized non-causal interpretation of Spearman coefficient.

    Rules.md §8: Results are reported as associations, never as causal claims.
    """
    if correlation is None:
        return "Insufficient variation to determine association"

    r = float(correlation)
    if r >= 0.50:
        return "Strong positive association"
    if r >= 0.25:
        return "Moderate positive association"
    if r >= 0.10:
        return "Weak positive association"
    if r > -0.10:
        return "No observed monotonic association"
    if r > -0.25:
        return "Weak negative association"
    if r > -0.50:
        return "Moderate negative association"
    return "Strong negative association"


def assign_fractional_ranks(
    df: DataFrame,
    col_name: str,
    rank_col_name: str,
    partition_cols: Sequence[str] | None = None,
) -> DataFrame:
    """Compute standard average fractional ranks for ties in PySpark.

    Formula: rank_avg = rank_min + (tie_count - 1.0) / 2.0

    Args:
        df: Input DataFrame.
        col_name: Target numeric column to rank.
        rank_col_name: Output rank column name.
        partition_cols: Optional sequence of partition columns (e.g. school).

    Returns:
        DataFrame with fractional rank column.
    """
    if partition_cols:
        w_order = Window.partitionBy(*[F.col(c) for c in partition_cols]).orderBy(F.col(col_name))
        w_part = Window.partitionBy(*[F.col(c) for c in partition_cols], F.col(col_name))
    else:
        w_order = Window.orderBy(F.col(col_name))
        w_part = Window.partitionBy(F.col(col_name))

    min_rank = F.rank().over(w_order)
    tie_count = F.count("*").over(w_part)
    avg_rank = min_rank + (tie_count - 1.0) / 2.0

    return df.withColumn(rank_col_name, avg_rank.cast("double"))


def compute_spearman_correlation(
    df: DataFrame,
    col_x: str,
    col_y: str,
    group_by_col: str | None = None,
) -> DataFrame:
    """Compute distributed Spearman rank correlation between two columns.

    Args:
        df: Input DataFrame containing observations.
        col_x: First variable column name.
        col_y: Second variable column name.
        group_by_col: Optional column name for stratified correlation (e.g. 'school').

    Returns:
        DataFrame containing correlation results:
        - If group_by_col is None: [spearman_corr, sample_size]
        - If group_by_col is present: [group_col, spearman_corr, sample_size]
    """
    # Filter valid non-null rows
    valid_df = df.filter(F.col(col_x).isNotNull() & F.col(col_y).isNotNull())

    partition_cols = [group_by_col] if group_by_col else None
    ranked_df = assign_fractional_ranks(valid_df, col_x, "_rank_x", partition_cols)
    ranked_df = assign_fractional_ranks(ranked_df, col_y, "_rank_y", partition_cols)

    if group_by_col:
        return (
            ranked_df.groupBy(group_by_col)
            .agg(
                F.coalesce(F.corr("_rank_x", "_rank_y"), F.lit(0.0))
                .cast("double")
                .alias("spearman_corr"),
                F.count("*").cast("int").alias("sample_size"),
            )
            .orderBy(group_by_col)
        )

    return ranked_df.agg(
        F.coalesce(F.corr("_rank_x", "_rank_y"), F.lit(0.0))
        .cast("double")
        .alias("spearman_corr"),
        F.count("*").cast("int").alias("sample_size"),
    )


def evaluate_planted_and_decoy_correlations(
    df: DataFrame,
    relationships: Sequence[dict[str, Any]] = APPROVED_CORRELATION_RELATIONSHIPS,
    group_by_col: str | None = None,
) -> DataFrame:
    """Evaluate Spearman correlations for all configured planted and decoy relationships.

    Computes both raw metric correlations and within-course normalized (z-scored) correlations
    to observe relationship recovery with and without the course difficulty confounder.

    Args:
        df: DataFrame containing both raw and normalized metrics.
        relationships: Sequence of relationship specifications to evaluate.
        group_by_col: Optional stratification column (e.g. 'school').

    Returns:
        Consolidated DataFrame with correlation evaluations across relationships.
    """
    results: list[DataFrame] = []

    for rel in relationships:
        rel_id = rel["relationship_id"]
        rel_name = rel["name"]
        rel_type = rel["relationship_type"]
        exp_dir = rel.get("expected_direction", "unknown")
        exp_str = rel.get("expected_strength", "unknown")

        x_raw = rel["independent_var_raw"]
        y_raw = rel["dependent_var_raw"]
        x_norm = rel.get("independent_var_norm")
        y_norm = rel.get("dependent_var_norm")

        if x_raw not in df.columns or y_raw not in df.columns:
            logger.warning("Skipping correlation %s: columns %s or %s missing", rel_id, x_raw, y_raw)
            continue

        # 1. Compute raw Spearman correlation
        raw_corr_df = compute_spearman_correlation(df, x_raw, y_raw, group_by_col)
        raw_corr_df = raw_corr_df.withColumnRenamed("spearman_corr", "spearman_raw")

        # 2. Compute normalized Spearman correlation if columns present
        if x_norm and y_norm and x_norm in df.columns and y_norm in df.columns:
            norm_corr_df = compute_spearman_correlation(df, x_norm, y_norm, group_by_col)
            norm_corr_df = norm_corr_df.withColumnRenamed("spearman_corr", "spearman_normalized")

            if group_by_col:
                combined = raw_corr_df.join(
                    norm_corr_df.select(group_by_col, "spearman_normalized"),
                    on=group_by_col,
                    how="left",
                )
            else:
                combined = raw_corr_df.crossJoin(
                    norm_corr_df.select("spearman_normalized")
                )
        else:
            combined = raw_corr_df.withColumn(
                "spearman_normalized", F.lit(None).cast("double")
            )

        # 3. Add relationship metadata
        combined = (
            combined.withColumn("relationship_id", F.lit(rel_id))
            .withColumn("relationship_name", F.lit(rel_name))
            .withColumn("relationship_type", F.lit(rel_type))
            .withColumn("independent_variable", F.lit(x_raw))
            .withColumn("dependent_variable", F.lit(y_raw))
            .withColumn("expected_direction", F.lit(exp_dir))
            .withColumn("expected_strength", F.lit(exp_str))
            .withColumn(
                "scope",
                F.col(group_by_col) if group_by_col else F.lit("overall"),
            )
        )
        results.append(combined)

    if not results:
        raise ValueError("No valid relationships could be evaluated from DataFrame columns")

    # Union all evaluated relationship rows
    consolidated = results[0]
    for r in results[1:]:
        consolidated = consolidated.unionByName(r)

    # Reorder columns logically
    first_cols = [
        "relationship_id",
        "relationship_name",
        "relationship_type",
        "scope",
        "independent_variable",
        "dependent_variable",
        "spearman_raw",
        "spearman_normalized",
        "expected_direction",
        "expected_strength",
        "sample_size",
    ]
    actual_cols = [c for c in first_cols if c in consolidated.columns]
    remaining = [c for c in consolidated.columns if c not in actual_cols]

    return consolidated.select(*(actual_cols + remaining)).orderBy("relationship_id", "scope")
