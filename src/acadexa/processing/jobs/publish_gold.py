"""Spark gold analytical collections publication job - J7 (tasks 9.1-9.4, rules.md §18, §19).

Job Responsibilities (F-D07, architecture.md §12, §13):
1. Load integrated student features from J3.
2. Build student x semester roll-up for `student_features` conforming to STUDENT_FEATURES_SCHEMA (Task 9.1).
3. Publish `student_features` to MongoDB and Parquet (Task 9.1).
4. Aggregate course-level metrics for `course_metrics` conforming to COURSE_METRICS_SCHEMA (Task 9.2).
5. Publish `course_metrics` to MongoDB and Parquet (Task 9.2).
6. Aggregate school and department summary for `school_summary` conforming to SCHOOL_SUMMARY_SCHEMA (Task 9.2).
7. Publish `school_summary` to MongoDB and Parquet (Task 9.2).
8. Publish `risk_indicators` with signal breakdown and run metadata conforming to RISK_INDICATORS_SCHEMA (Task 9.3).
9. Add validation after publication to confirm counts, grain and required fields of all gold collections (Task 9.4).
10. Strictly adhere to rules.md §17.3: zero driver-side collect/toPandas calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from acadexa.processing.jobs.feature_table import build_student_semester_features
from acadexa.processing.mongo import write_mongo_collection
from acadexa.validation.gold import (
    GOLD_COLLECTIONS,
    GOLD_SCHEMAS,
    GoldCollectionValidationResult,
    GoldValidationError,
    validate_gold_collections,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class J7Config:
    """Configuration for Spark J7 gold publication job."""

    student_features_path: Path = Path("data/processed/student_features")
    risk_indicators_path: Path = Path("data/processed/risk_indicators")
    mongo_uri: str | None = None
    mongo_database: str | None = None
    write_mode: str = "overwrite"
    publish_to_mongo: bool = True
    save_parquet: bool = True
    parquet_base_path: Path = Path("data/gold")
    # Toggles for target gold collections
    publish_student_features: bool = True
    publish_course_metrics: bool = True
    publish_school_summary: bool = True
    publish_risk_indicators: bool = True
    # Post-publication validation (Task 9.4)
    validate_after_publication: bool = True
    fail_on_validation_error: bool = True
    evaluation_week_start: str | None = "2026-04-20"


@dataclass
class J7Result:
    """Result of running J7 gold publication job."""

    student_features: DataFrame | None = None
    course_metrics: DataFrame | None = None
    school_summary: DataFrame | None = None
    risk_indicators: DataFrame | None = None
    student_features_count: int = 0
    course_metrics_count: int = 0
    school_summary_count: int = 0
    risk_indicators_count: int = 0
    published_collections: list[str] = field(default_factory=list)
    risk_signal_breakdown: dict[str, Any] = field(default_factory=dict)
    validation_report: dict[str, GoldCollectionValidationResult] = field(default_factory=dict)


def build_course_metrics(feature_table_df: DataFrame) -> DataFrame:
    """Aggregate student-course features to course x semester grain (features.md F-D07, schema.py).

    Args:
        feature_table_df: Integrated student-course-semester DataFrame.

    Returns:
        DataFrame conforming to the course_metrics gold collection schema:
        [course_id, semester_id, avg_performance, avg_attendance, engagement_count, difficulty_adjusted_performance].
    """
    agg_exprs = [
        # Mean academic performance (0-100)
        F.coalesce(F.round(F.avg("academic_score"), 2), F.lit(0.0))
        .cast("double")
        .alias("avg_performance"),
        # Mean attendance percentage (0-100)
        F.coalesce(F.round(F.avg("attendance_percentage"), 2), F.lit(0.0))
        .cast("double")
        .alias("avg_attendance"),
        # Total LMS events
        F.coalesce(F.sum("lms_total_events"), F.lit(0))
        .cast("int")
        .alias("engagement_count"),
        F.countDistinct("student_id").cast("int").alias("enrolled_students_count"),
    ]

    if "course_title" in feature_table_df.columns:
        agg_exprs.append(F.first("course_title", ignorenulls=True).alias("course_title"))
    if "school" in feature_table_df.columns:
        agg_exprs.append(F.first("school", ignorenulls=True).alias("school"))
    elif "course_school" in feature_table_df.columns:
        agg_exprs.append(F.first("course_school", ignorenulls=True).alias("school"))
    if "department" in feature_table_df.columns:
        agg_exprs.append(F.first("department", ignorenulls=True).alias("department"))
    elif "course_department" in feature_table_df.columns:
        agg_exprs.append(F.first("course_department", ignorenulls=True).alias("department"))
    if "course_difficulty" in feature_table_df.columns:
        agg_exprs.append(F.first("course_difficulty", ignorenulls=True).alias("course_difficulty"))

    course_agg = feature_table_df.groupBy("course_id", "semester_id").agg(*agg_exprs)

    # Standardize avg_performance across courses within semester (z-score style, unbounded)
    w_sem = Window.partitionBy("semester_id")
    mean_sem = F.avg("avg_performance").over(w_sem)
    std_sem = F.stddev("avg_performance").over(w_sem)

    course_metrics_df = course_agg.withColumn(
        "difficulty_adjusted_performance",
        F.when(
            std_sem.isNotNull() & (std_sem > 0),
            F.round((F.col("avg_performance") - mean_sem) / std_sem, 2),
        )
        .otherwise(0.0)
        .cast("double"),
    )

    return course_metrics_df.orderBy("course_id", "semester_id")


def build_school_summary(feature_table_df: DataFrame) -> DataFrame:
    """Roll up student-course features to school x department grain (features.md F-D07, schema.py).

    Args:
        feature_table_df: Integrated student-course-semester DataFrame.

    Returns:
        DataFrame conforming to the school_summary gold collection schema:
        [school, department, student_count, course_count, avg_performance, avg_attendance, engagement_count].
    """
    school_col = (
        F.col("school")
        if "school" in feature_table_df.columns
        else F.col("student_school")
        if "student_school" in feature_table_df.columns
        else F.col("course_school")
    )
    dept_col = (
        F.col("department")
        if "department" in feature_table_df.columns
        else F.col("student_department")
        if "student_department" in feature_table_df.columns
        else F.col("course_department")
    )

    clean_df = feature_table_df.withColumn("_school", school_col).withColumn("_department", dept_col)

    summary = clean_df.groupBy(
        F.col("_school").alias("school"),
        F.col("_department").alias("department"),
    ).agg(
        # Distinct student count in department roll-up
        F.countDistinct("student_id").cast("int").alias("student_count"),
        # Distinct course count in department roll-up
        F.countDistinct("course_id").cast("int").alias("course_count"),
        # Mean academic performance (0-100)
        F.coalesce(F.round(F.avg("academic_score"), 2), F.lit(0.0))
        .cast("double")
        .alias("avg_performance"),
        # Mean derived attendance percentage (0-100)
        F.coalesce(F.round(F.avg("attendance_percentage"), 2), F.lit(0.0))
        .cast("double")
        .alias("avg_attendance"),
        # Total LMS events
        F.coalesce(F.sum("lms_total_events"), F.lit(0))
        .cast("int")
        .alias("engagement_count"),
    )

    return summary.orderBy("school", "department")


def publish_student_features(
    spark: SparkSession,
    feature_table_df: DataFrame,
    config: J7Config | None = None,
) -> tuple[DataFrame, int]:
    """Build and publish student_features to MongoDB and Parquet (Task 9.1).

    Grain: student_id x semester_id.
    Schema: STUDENT_FEATURES_SCHEMA.

    Args:
        spark: Active SparkSession.
        feature_table_df: Feature table DataFrame.
        config: Optional J7 configuration.

    Returns:
        tuple[DataFrame, int]: Published DataFrame and row count.
    """
    cfg = config or J7Config()
    student_features_df = build_student_semester_features(feature_table_df)
    total_count = student_features_df.count()

    if cfg.save_parquet:
        out_path = Path(cfg.parquet_base_path) / "student_features"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        student_features_df.write.mode(cfg.write_mode).parquet(str(out_path))
        logger.info("Saved student_features to Parquet at %s (%d rows)", out_path, total_count)

    if cfg.publish_to_mongo:
        write_mongo_collection(
            student_features_df,
            collection_name="student_features",
            database=cfg.mongo_database,
            uri=cfg.mongo_uri,
            mode=cfg.write_mode,
        )
        logger.info("Published %d records to MongoDB collection 'student_features'", total_count)

    return student_features_df, total_count


def publish_course_metrics(
    spark: SparkSession,
    feature_table_df: DataFrame,
    config: J7Config | None = None,
) -> tuple[DataFrame, int]:
    """Build and publish course_metrics to MongoDB and Parquet (Task 9.2).

    Grain: course_id x semester_id.
    Schema: COURSE_METRICS_SCHEMA.

    Args:
        spark: Active SparkSession.
        feature_table_df: Feature table DataFrame.
        config: Optional J7 configuration.

    Returns:
        tuple[DataFrame, int]: Published DataFrame and row count.
    """
    cfg = config or J7Config()
    course_metrics_df = build_course_metrics(feature_table_df)
    total_count = course_metrics_df.count()

    if cfg.save_parquet:
        out_path = Path(cfg.parquet_base_path) / "course_metrics"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        course_metrics_df.write.mode(cfg.write_mode).parquet(str(out_path))
        logger.info("Saved course_metrics to Parquet at %s (%d rows)", out_path, total_count)

    if cfg.publish_to_mongo:
        write_mongo_collection(
            course_metrics_df,
            collection_name="course_metrics",
            database=cfg.mongo_database,
            uri=cfg.mongo_uri,
            mode=cfg.write_mode,
        )
        logger.info("Published %d records to MongoDB collection 'course_metrics'", total_count)

    return course_metrics_df, total_count


def publish_school_summary(
    spark: SparkSession,
    feature_table_df: DataFrame,
    config: J7Config | None = None,
) -> tuple[DataFrame, int]:
    """Build and publish school_summary to MongoDB and Parquet (Task 9.2).

    Grain: school x department.
    Schema: SCHOOL_SUMMARY_SCHEMA.

    Args:
        spark: Active SparkSession.
        feature_table_df: Feature table DataFrame.
        config: Optional J7 configuration.

    Returns:
        tuple[DataFrame, int]: Published DataFrame and row count.
    """
    cfg = config or J7Config()
    school_summary_df = build_school_summary(feature_table_df)
    total_count = school_summary_df.count()

    if cfg.save_parquet:
        out_path = Path(cfg.parquet_base_path) / "school_summary"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        school_summary_df.write.mode(cfg.write_mode).parquet(str(out_path))
        logger.info("Saved school_summary to Parquet at %s (%d rows)", out_path, total_count)

    if cfg.publish_to_mongo:
        write_mongo_collection(
            school_summary_df,
            collection_name="school_summary",
            database=cfg.mongo_database,
            uri=cfg.mongo_uri,
            mode=cfg.write_mode,
        )
        logger.info("Published %d records to MongoDB collection 'school_summary'", total_count)

    return school_summary_df, total_count


def publish_risk_indicators(
    spark: SparkSession,
    risk_indicators_df: DataFrame,
    config: J7Config | None = None,
) -> tuple[DataFrame, int, dict[str, Any]]:
    """Publish risk_indicators to MongoDB and Parquet with signal breakdown and run metadata (Task 9.3).

    Grain: student_id x week_start.
    Schema: RISK_INDICATORS_SCHEMA.

    Args:
        spark: Active SparkSession.
        risk_indicators_df: DataFrame containing student risk indicators.
        config: Optional J7 configuration.

    Returns:
        tuple[DataFrame, int, dict[str, Any]]: Published DataFrame, row count, and signal breakdown dict.
    """
    cfg = config or J7Config()
    df = risk_indicators_df

    # 1. Ensure run metadata (computed_at timestamp)
    if "computed_at" not in df.columns:
        df = df.withColumn("computed_at", F.current_timestamp())

    # 2. Ensure week_start is present per grain
    if "week_start" not in df.columns:
        week_val = cfg.evaluation_week_start or "2026-04-20"
        df = df.withColumn("week_start", F.to_date(F.lit(week_val)))

    # 3. Ensure signal_count is computed
    if "signal_count" not in df.columns:
        sig_expr = (
            F.when(F.col("low_attendance") == True, 1).otherwise(0)
            + F.when(F.col("lms_decline") == True, 1).otherwise(0)
            + F.when(F.col("late_submissions") == True, 1).otherwise(0)
            + F.when(F.col("marks_decline") == True, 1).otherwise(0)
            + F.when(F.col("low_quiz_activity") == True, 1).otherwise(0)
        )
        df = df.withColumn("signal_count", sig_expr.cast("int"))

    # 4. Compute signal breakdown summary in a single distributed Spark aggregation
    agg_exprs = [
        F.count("*").alias("total_students"),
        F.sum(F.when(F.col("signal_count") > 0, 1).otherwise(0)).alias("flagged_students"),
        F.sum(F.when(F.col("signal_count") >= 3, 1).otherwise(0)).alias("high_risk_students"),
    ]
    for i in range(6):
        agg_exprs.append(
            F.sum(F.when(F.col("signal_count") == i, 1).otherwise(0)).alias(f"sig_{i}")
        )
    for flag in ["low_attendance", "lms_decline", "late_submissions", "marks_decline", "low_quiz_activity"]:
        agg_exprs.append(
            F.sum(F.when(F.col(flag) == True, 1).otherwise(0)).alias(f"flag_{flag}")
        )

    summary_row = df.agg(*agg_exprs).first()
    total_count = int(summary_row["total_students"] or 0)
    flagged_count = int(summary_row["flagged_students"] or 0)
    high_risk_count = int(summary_row["high_risk_students"] or 0)
    counts_by_signal = {i: int(summary_row[f"sig_{i}"] or 0) for i in range(6)}
    flag_counts = {
        flag: int(summary_row[f"flag_{flag}"] or 0)
        for flag in ["low_attendance", "lms_decline", "late_submissions", "marks_decline", "low_quiz_activity"]
    }
    breakdown: dict[str, Any] = {
        "total_students": total_count,
        "flagged_students": flagged_count,
        "high_risk_students": high_risk_count,
        "signal_count_distribution": counts_by_signal,
        "flag_counts": flag_counts,
    }

    # 5. Save to Parquet
    if cfg.save_parquet:
        out_path = Path(cfg.parquet_base_path) / "risk_indicators"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.write.mode(cfg.write_mode).parquet(str(out_path))
        logger.info("Saved risk_indicators to Parquet at %s (%d rows)", out_path, total_count)

    # 6. Publish to MongoDB
    if cfg.publish_to_mongo:
        write_mongo_collection(
            df,
            collection_name="risk_indicators",
            database=cfg.mongo_database,
            uri=cfg.mongo_uri,
            mode=cfg.write_mode,
        )
        logger.info("Published %d records to MongoDB collection 'risk_indicators'", total_count)

    return df, total_count, breakdown


def run_j7_publish_gold(
    spark: SparkSession,
    config: J7Config | None = None,
    feature_table_df: DataFrame | None = None,
    risk_indicators_df: DataFrame | None = None,
) -> J7Result:
    """Execute Spark J7 gold data publication job with post-publication validation (Tasks 9.1-9.4).

    Args:
        spark: Active SparkSession.
        config: Optional J7 configuration.
        feature_table_df: Optional pre-loaded feature table DataFrame.
        risk_indicators_df: Optional pre-computed risk indicators DataFrame.

    Returns:
        J7Result containing published DataFrames, row counts, breakdown, and validation report.
    """
    cfg = config or J7Config()
    logger.info("Starting J7 Gold Data Publication")

    published: list[str] = []
    sf_df = None
    sf_count = 0
    cm_df = None
    cm_count = 0
    ss_df = None
    ss_count = 0
    ri_df = None
    ri_count = 0
    ri_breakdown: dict[str, Any] = {}

    # Read feature table if any feature-table-derived collection is enabled
    needs_feat_df = cfg.publish_student_features or cfg.publish_course_metrics or cfg.publish_school_summary
    ft_df = feature_table_df
    if needs_feat_df and ft_df is None:
        feat_path = Path(cfg.student_features_path)
        ft_df = spark.read.parquet(str(feat_path))

    # 1. Publish student_features (Task 9.1)
    if cfg.publish_student_features and ft_df is not None:
        sf_df, sf_count = publish_student_features(spark, ft_df, cfg)
        published.append("student_features")

    # 2. Publish course_metrics (Task 9.2)
    if cfg.publish_course_metrics and ft_df is not None:
        cm_df, cm_count = publish_course_metrics(spark, ft_df, cfg)
        published.append("course_metrics")

    # 3. Publish school_summary (Task 9.2)
    if cfg.publish_school_summary and ft_df is not None:
        ss_df, ss_count = publish_school_summary(spark, ft_df, cfg)
        published.append("school_summary")

    # 4. Publish risk_indicators (Task 9.3)
    if cfg.publish_risk_indicators:
        ri_input = risk_indicators_df
        if ri_input is None:
            ri_path = Path(cfg.risk_indicators_path)
            if ri_path.exists():
                ri_input = spark.read.parquet(str(ri_path))
            else:
                logger.warning(
                    "Risk indicators path not found (%s) and no risk_indicators_df provided. "
                    "Skipping risk_indicators publication.",
                    ri_path,
                )
        if ri_input is not None:
            ri_df, ri_count, ri_breakdown = publish_risk_indicators(spark, ri_input, cfg)
            published.append("risk_indicators")

    # 5. Post-publication validation (Task 9.4)
    validation_report: dict[str, GoldCollectionValidationResult] = {}
    if cfg.validate_after_publication:
        dfs_to_validate: dict[str, DataFrame] = {}
        if sf_df is not None:
            dfs_to_validate["student_features"] = sf_df
        if cm_df is not None:
            dfs_to_validate["course_metrics"] = cm_df
        if ss_df is not None:
            dfs_to_validate["school_summary"] = ss_df
        if ri_df is not None:
            dfs_to_validate["risk_indicators"] = ri_df

        validation_report = validate_gold_collections(
            dfs=dfs_to_validate,
            fail_fast=cfg.fail_on_validation_error,
        )
        logger.info(
            "Gold validation complete across %d collections: %s",
            len(validation_report),
            [r.summary() for r in validation_report.values()],
        )

    logger.info(
        "J7 complete. Published: %s (SF: %d, CM: %d, SS: %d, RI: %d)",
        published,
        sf_count,
        cm_count,
        ss_count,
        ri_count,
    )

    return J7Result(
        student_features=sf_df,
        course_metrics=cm_df,
        school_summary=ss_df,
        risk_indicators=ri_df,
        student_features_count=sf_count,
        course_metrics_count=cm_count,
        school_summary_count=ss_count,
        risk_indicators_count=ri_count,
        published_collections=published,
        risk_signal_breakdown=ri_breakdown,
        validation_report=validation_report,
    )
