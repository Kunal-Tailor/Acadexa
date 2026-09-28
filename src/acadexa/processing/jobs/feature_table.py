"""Spark integrated student feature table construction job - J3 (tasks 8.1 & 8.2, rules.md §17, §18).

Job Responsibilities (F-D03, architecture.md §12):
1. Aggregate cleaned attendance observations to student x course x semester grain.
2. Aggregate cleaned coursework observations (assignments and quizzes) to student x course x semester grain.
3. Aggregate weekly LMS engagement summaries to student x course x semester grain.
4. Integrate academic records, attendance, coursework, and LMS engagement into a unified feature table
   at the canonical grain: student_id x course_id x semester_id.
5. Join university hierarchy and course metadata (course difficulty, school, department).
6. Implement all required derived features:
   - Attendance percentage, rate, and missed classes.
   - Late submission rate, late assignment rate, missing coursework rate, score percentages.
   - Quiz retry ratio and total quiz attempts.
   - Academic composite score and exam marks trend.
   - LMS event counts, duration in hours, active days, and category breakdowns.
7. Provide student-level semester roll-up matching the student_features gold collection schema.
8. Execute strictly via distributed Spark operations without collecting rows to driver.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from acadexa.analytics.metrics import (
    calculate_academic_score,
    calculate_attendance_percentage,
    calculate_attendance_rate,
    calculate_late_submission_rate,
    calculate_missing_rate,
    calculate_quiz_retry_ratio,
    calculate_score_percentage,
)

logger = logging.getLogger(__name__)

# University semester date ranges (config/university/academic_periods.toml)
SEMESTER_BOUNDS: tuple[tuple[str, str, str], ...] = (
    ("S1", "2024-07-15", "2024-11-03"),
    ("S2", "2025-01-06", "2025-04-27"),
    ("S3", "2025-07-14", "2025-11-02"),
    ("S4", "2026-01-05", "2026-04-26"),
)


@dataclass(frozen=True)
class J3Config:
    """Configuration for Spark J3 integrated student feature table job."""

    academic_records_path: Path = Path("data/processed/academic_records")
    attendance_path: Path = Path("data/processed/attendance")
    coursework_path: Path = Path("data/processed/coursework")
    lms_path: Path = Path("data/processed/lms_weekly_engagement")
    courses_path: Path = Path("data/processed/courses")
    students_path: Path = Path("data/processed/students")
    output_path: Path = Path("data/processed/student_features")
    student_rollup_path: Path | None = None
    save_parquet: bool = True
    partition_by: tuple[str, ...] = ("semester_id",)
    join_mode: str = "outer"  # "outer", "left", "inner"


@dataclass
class J3Result:
    """Complete result of running J3 feature table construction."""

    feature_table: DataFrame
    student_rollup: DataFrame | None
    total_features_rows: int
    total_students: int
    output_path: Path


def derive_semester_id_from_date(date_col_name: str) -> F.Column:
    """Build Spark expression mapping calendar date to semester_id.

    Args:
        date_col_name: Name of the date or timestamp column.

    Returns:
        PySpark Column representing semester_id (e.g. S1, S2, S3, S4).
    """
    sem_expr = F.lit("UNKNOWN")
    for sem_id, start_date, end_date in reversed(SEMESTER_BOUNDS):
        sem_expr = F.when(
            F.to_date(F.col(date_col_name)).between(start_date, end_date),
            F.lit(sem_id),
        ).otherwise(sem_expr)
    return sem_expr


def aggregate_attendance_features(attendance_df: DataFrame) -> DataFrame:
    """Aggregate weekly attendance observations to student x course x semester grain.

    Args:
        attendance_df: Cleaned attendance DataFrame.

    Returns:
        Aggregated DataFrame with attendance counts and derived metrics.
    """
    norm_df = (
        attendance_df.withColumn(
            "student_id", F.trim(F.upper(F.col("student_id")))
        )
        .withColumn("course_id", F.trim(F.upper(F.col("course_id"))))
        .withColumn("semester_id", F.trim(F.upper(F.col("semester_id"))))
    )

    agg = norm_df.groupBy("student_id", "course_id", "semester_id").agg(
        F.sum("classes_conducted").cast("int").alias("classes_conducted"),
        F.sum("classes_attended").cast("int").alias("classes_attended"),
        F.countDistinct("week_start").cast("int").alias("attendance_weeks"),
    )

    return (
        agg.withColumn(
            "classes_missed",
            (F.col("classes_conducted") - F.col("classes_attended")).cast("int"),
        )
        .withColumn(
            "attendance_rate",
            calculate_attendance_rate("classes_attended", "classes_conducted"),
        )
        .withColumn(
            "attendance_percentage",
            calculate_attendance_percentage("classes_attended", "classes_conducted"),
        )
    )


def aggregate_coursework_features(
    coursework_df: DataFrame,
    academic_records_df: DataFrame | None = None,
) -> DataFrame:
    """Aggregate coursework items (assignments & quizzes) to student x course x semester grain.

    Args:
        coursework_df: Cleaned coursework DataFrame.
        academic_records_df: Optional academic records to verify semester mapping.

    Returns:
        Aggregated DataFrame with coursework performance, lateness, and completion metrics.
    """
    norm_df = coursework_df.withColumn(
        "student_id", F.trim(F.upper(F.col("student_id")))
    ).withColumn("course_id", F.trim(F.upper(F.col("course_id"))))

    # Derive semester_id if not explicitly present in coursework
    if "semester_id" not in norm_df.columns:
        norm_df = norm_df.withColumn(
            "semester_id", derive_semester_id_from_date("due_date")
        )
    else:
        norm_df = norm_df.withColumn(
            "semester_id", F.trim(F.upper(F.col("semester_id")))
        )

    agg = norm_df.groupBy("student_id", "course_id", "semester_id").agg(
        # Item counts
        F.count("*").cast("int").alias("total_coursework"),
        F.sum(F.when(F.col("item_type") == "ASSIGNMENT", 1).otherwise(0))
        .cast("int")
        .alias("total_assignments"),
        F.sum(F.when(F.col("item_type") == "QUIZ", 1).otherwise(0))
        .cast("int")
        .alias("total_quizzes"),
        # Submissions
        F.sum(
            F.when(F.col("status").isin("ON_TIME", "LATE"), 1).otherwise(0)
        )
        .cast("int")
        .alias("total_submissions"),
        F.sum(
            F.when(
                (F.col("item_type") == "ASSIGNMENT")
                & F.col("status").isin("ON_TIME", "LATE"),
                1,
            ).otherwise(0)
        )
        .cast("int")
        .alias("submitted_assignments"),
        F.sum(
            F.when(
                (F.col("item_type") == "QUIZ")
                & F.col("status").isin("ON_TIME", "LATE"),
                1,
            ).otherwise(0)
        )
        .cast("int")
        .alias("submitted_quizzes"),
        # Lateness
        F.sum(F.when(F.col("status") == "LATE", 1).otherwise(0))
        .cast("int")
        .alias("late_submissions"),
        F.sum(
            F.when(
                (F.col("item_type") == "ASSIGNMENT")
                & (F.col("status") == "LATE"),
                1,
            ).otherwise(0)
        )
        .cast("int")
        .alias("late_assignments"),
        # Missing
        F.sum(F.when(F.col("status") == "MISSING", 1).otherwise(0))
        .cast("int")
        .alias("missing_submissions"),
        F.sum(
            F.when(
                (F.col("item_type") == "ASSIGNMENT")
                & (F.col("status") == "MISSING"),
                1,
            ).otherwise(0)
        )
        .cast("int")
        .alias("missing_assignments"),
        F.sum(
            F.when(
                (F.col("item_type") == "QUIZ")
                & (F.col("status") == "MISSING"),
                1,
            ).otherwise(0)
        )
        .cast("int")
        .alias("missing_quizzes"),
        # Scores
        F.coalesce(F.sum("score"), F.lit(0.0))
        .cast("double")
        .alias("coursework_total_score"),
        F.coalesce(F.sum("max_score"), F.lit(0.0))
        .cast("double")
        .alias("coursework_max_score"),
        F.coalesce(
            F.sum(
                F.when(
                    F.col("item_type") == "ASSIGNMENT", F.col("score")
                ).otherwise(0.0)
            ),
            F.lit(0.0),
        )
        .cast("double")
        .alias("assignment_total_score"),
        F.coalesce(
            F.sum(
                F.when(
                    F.col("item_type") == "ASSIGNMENT", F.col("max_score")
                ).otherwise(0.0)
            ),
            F.lit(0.0),
        )
        .cast("double")
        .alias("assignment_max_score"),
        F.coalesce(
            F.sum(
                F.when(
                    F.col("item_type") == "QUIZ", F.col("score")
                ).otherwise(0.0)
            ),
            F.lit(0.0),
        )
        .cast("double")
        .alias("quiz_total_score"),
        F.coalesce(
            F.sum(
                F.when(
                    F.col("item_type") == "QUIZ", F.col("max_score")
                ).otherwise(0.0)
            ),
            F.lit(0.0),
        )
        .cast("double")
        .alias("quiz_max_score"),
        # Quiz attempts
        F.coalesce(
            F.sum(
                F.when(
                    F.col("item_type") == "QUIZ", F.col("attempts")
                ).otherwise(0)
            ),
            F.lit(0),
        )
        .cast("int")
        .alias("total_quiz_attempts"),
    )

    # Derived rates and percentages
    return (
        agg.withColumn(
            "late_submission_rate",
            calculate_late_submission_rate("late_submissions", "total_submissions"),
        )
        .withColumn(
            "late_assignment_rate",
            calculate_late_submission_rate("late_assignments", "total_assignments"),
        )
        .withColumn(
            "missing_coursework_rate",
            calculate_missing_rate("missing_submissions", "total_coursework"),
        )
        .withColumn(
            "coursework_score_pct",
            calculate_score_percentage("coursework_total_score", "coursework_max_score"),
        )
        .withColumn(
            "assignment_score_pct",
            calculate_score_percentage("assignment_total_score", "assignment_max_score"),
        )
        .withColumn(
            "quiz_score_pct",
            calculate_score_percentage("quiz_total_score", "quiz_max_score"),
        )
        .withColumn(
            "quiz_retry_ratio",
            calculate_quiz_retry_ratio("total_quiz_attempts", "total_quizzes"),
        )
    )


def aggregate_lms_features(lms_weekly_df: DataFrame) -> DataFrame:
    """Aggregate weekly LMS engagement summaries to student x course x semester grain.

    Args:
        lms_weekly_df: Cleaned weekly engagement DataFrame from J2.

    Returns:
        Aggregated DataFrame with semester total events, durations, and category breakdowns.
    """
    norm_df = (
        lms_weekly_df.withColumn(
            "student_id", F.trim(F.upper(F.col("student_id")))
        )
        .withColumn("course_id", F.trim(F.upper(F.col("course_id"))))
        .withColumn("semester_id", F.trim(F.upper(F.col("semester_id"))))
    )

    agg = norm_df.groupBy("student_id", "course_id", "semester_id").agg(
        # Overall engagement
        F.coalesce(F.sum("total_events"), F.lit(0))
        .cast("long")
        .alias("lms_total_events"),
        F.coalesce(F.sum("total_duration_sec"), F.lit(0))
        .cast("long")
        .alias("lms_total_duration_sec"),
        F.coalesce(F.sum("active_days"), F.lit(0))
        .cast("int")
        .alias("lms_active_days_total"),
        F.countDistinct(
            F.when(F.col("total_events") > 0, F.col("week_start"))
        )
        .cast("int")
        .alias("lms_active_weeks"),
        # Category roll-ups
        F.coalesce(F.sum("content_views"), F.lit(0))
        .cast("long")
        .alias("lms_content_views"),
        F.coalesce(F.sum("assessment_events"), F.lit(0))
        .cast("long")
        .alias("lms_assessment_events"),
        F.coalesce(F.sum("participation_events"), F.lit(0))
        .cast("long")
        .alias("lms_participation_events"),
        F.coalesce(F.sum("access_events"), F.lit(0))
        .cast("long")
        .alias("lms_access_events"),
        # Event type breakdowns
        F.coalesce(F.sum("video_views"), F.lit(0))
        .cast("long")
        .alias("lms_video_views"),
        F.coalesce(F.sum("quiz_attempts"), F.lit(0))
        .cast("long")
        .alias("lms_quiz_attempts"),
        F.coalesce(F.sum("assignment_views"), F.lit(0))
        .cast("long")
        .alias("lms_assignment_views"),
        F.coalesce(F.sum("assignment_submissions"), F.lit(0))
        .cast("long")
        .alias("lms_assignment_submissions"),
        F.coalesce(F.sum("forum_posts"), F.lit(0))
        .cast("long")
        .alias("lms_forum_posts"),
        F.coalesce(F.sum("logins"), F.lit(0))
        .cast("long")
        .alias("lms_logins"),
    )

    return (
        agg.withColumn(
            "lms_total_duration_hours",
            F.round(F.col("lms_total_duration_sec") / 3600.0, 2).cast("double"),
        )
        .withColumn(
            "lms_active_days_per_week_avg",
            F.when(
                F.col("lms_active_weeks") > 0,
                F.col("lms_active_days_total") / F.col("lms_active_weeks"),
            )
            .otherwise(0.0)
            .cast("double"),
        )
        .withColumn(
            "lms_events_per_active_day",
            F.when(
                F.col("lms_active_days_total") > 0,
                F.col("lms_total_events") / F.col("lms_active_days_total"),
            )
            .otherwise(0.0)
            .cast("double"),
        )
    )


def build_integrated_student_features(
    academic_records_df: DataFrame,
    attendance_df: DataFrame,
    coursework_df: DataFrame,
    lms_weekly_df: DataFrame,
    courses_df: DataFrame | None = None,
    students_df: DataFrame | None = None,
    join_mode: str = "outer",
) -> DataFrame:
    """Join academic, attendance, coursework, and LMS summaries at student x course x semester grain.

    Args:
        academic_records_df: Cleaned academic records DataFrame.
        attendance_df: Cleaned attendance DataFrame.
        coursework_df: Cleaned coursework DataFrame.
        lms_weekly_df: Cleaned weekly LMS engagement DataFrame.
        courses_df: Optional courses DataFrame for hierarchy and difficulty metadata.
        students_df: Optional students DataFrame for cohort and program metadata.
        join_mode: Join strategy ("outer", "left", "inner").

    Returns:
        Unified DataFrame at canonical grain: student_id x course_id x semester_id.
    """
    # 1. Normalize academic records and derive academic metrics
    acad_clean = (
        academic_records_df.withColumn(
            "student_id", F.trim(F.upper(F.col("student_id")))
        )
        .withColumn("course_id", F.trim(F.upper(F.col("course_id"))))
        .withColumn("semester_id", F.trim(F.upper(F.col("semester_id"))))
        .withColumn("internal_marks", F.col("internal_marks").cast("int"))
        .withColumn("midterm_marks", F.col("midterm_marks").cast("int"))
        .withColumn("endterm_marks", F.col("endterm_marks").cast("int"))
        .withColumn("final_grade", F.col("final_grade"))
        .withColumn(
            "total_marks",
            (
                F.col("internal_marks")
                + F.col("midterm_marks")
                + F.col("endterm_marks")
            ).cast("int"),
        )
        .withColumn(
            "academic_score",
            calculate_academic_score(
                "internal_marks", "midterm_marks", "endterm_marks"
            ),
        )
        .withColumn(
            "exam_marks_trend",
            (F.col("endterm_marks") - F.col("internal_marks")).cast("int"),
        )
    )

    # 2. Aggregate domain summaries
    att_summary = aggregate_attendance_features(attendance_df)
    cw_summary = aggregate_coursework_features(coursework_df, acad_clean)
    lms_summary = aggregate_lms_features(lms_weekly_df)

    # 3. Construct join backbone (spine)
    join_keys = ["student_id", "course_id", "semester_id"]

    if join_mode == "outer":
        spine = (
            acad_clean.select(*join_keys)
            .union(att_summary.select(*join_keys))
            .union(cw_summary.select(*join_keys))
            .union(lms_summary.select(*join_keys))
            .distinct()
        )
        joined = (
            spine.join(acad_clean, on=join_keys, how="left")
            .join(att_summary, on=join_keys, how="left")
            .join(cw_summary, on=join_keys, how="left")
            .join(lms_summary, on=join_keys, how="left")
        )
    elif join_mode == "left":
        joined = (
            acad_clean.join(att_summary, on=join_keys, how="left")
            .join(cw_summary, on=join_keys, how="left")
            .join(lms_summary, on=join_keys, how="left")
        )
    else:  # inner
        joined = (
            acad_clean.join(att_summary, on=join_keys, how="inner")
            .join(cw_summary, on=join_keys, how="inner")
            .join(lms_summary, on=join_keys, how="inner")
        )

    # 4. Fill missing numeric values from absent domain records
    numeric_zero_cols = {
        # Attendance defaults
        "classes_conducted": 0,
        "classes_attended": 0,
        "classes_missed": 0,
        "attendance_weeks": 0,
        "attendance_rate": 0.0,
        "attendance_percentage": 0.0,
        # Coursework defaults
        "total_coursework": 0,
        "total_assignments": 0,
        "total_quizzes": 0,
        "total_submissions": 0,
        "submitted_assignments": 0,
        "submitted_quizzes": 0,
        "late_submissions": 0,
        "late_assignments": 0,
        "missing_submissions": 0,
        "missing_assignments": 0,
        "missing_quizzes": 0,
        "total_quiz_attempts": 0,
        "late_submission_rate": 0.0,
        "late_assignment_rate": 0.0,
        "missing_coursework_rate": 0.0,
        "coursework_total_score": 0.0,
        "coursework_max_score": 0.0,
        "assignment_total_score": 0.0,
        "assignment_max_score": 0.0,
        "quiz_total_score": 0.0,
        "quiz_max_score": 0.0,
        "coursework_score_pct": 0.0,
        "assignment_score_pct": 0.0,
        "quiz_score_pct": 0.0,
        "quiz_retry_ratio": 0.0,
        # LMS defaults
        "lms_total_events": 0,
        "lms_total_duration_sec": 0,
        "lms_total_duration_hours": 0.0,
        "lms_active_days_total": 0,
        "lms_active_weeks": 0,
        "lms_active_days_per_week_avg": 0.0,
        "lms_events_per_active_day": 0.0,
        "lms_content_views": 0,
        "lms_assessment_events": 0,
        "lms_participation_events": 0,
        "lms_access_events": 0,
        "lms_video_views": 0,
        "lms_quiz_attempts": 0,
        "lms_assignment_views": 0,
        "lms_assignment_submissions": 0,
        "lms_forum_posts": 0,
        "lms_logins": 0,
    }

    for col_name, default_val in numeric_zero_cols.items():
        if col_name in joined.columns:
            joined = joined.withColumn(
                col_name, F.coalesce(F.col(col_name), F.lit(default_val))
            )

    # 5. Join course metadata
    if courses_df is not None:
        c_clean = (
            courses_df.withColumn(
                "course_id", F.trim(F.upper(F.col("course_id")))
            )
            .withColumnRenamed("title", "course_title")
            .withColumnRenamed("school", "course_school")
            .withColumnRenamed("department", "course_department")
            .withColumnRenamed("difficulty", "course_difficulty")
            .withColumnRenamed("difficulty_level", "course_difficulty_level")
        )
        meta_cols = [
            "course_id",
            "course_title",
            "course_school",
            "course_department",
            "course_difficulty",
            "course_difficulty_level",
        ]
        available_meta = [c for c in meta_cols if c in c_clean.columns]
        joined = joined.join(
            c_clean.select(*available_meta), on="course_id", how="left"
        )

    # 6. Join student metadata
    if students_df is not None:
        s_clean = (
            students_df.withColumn(
                "student_id", F.trim(F.upper(F.col("student_id")))
            )
            .withColumnRenamed("school", "student_school")
            .withColumnRenamed("department", "student_department")
            .withColumnRenamed("semester", "cohort_semester")
        )
        stud_cols = [
            "student_id",
            "student_school",
            "student_department",
            "program",
            "batch",
            "cohort_semester",
        ]
        available_stud = [c for c in stud_cols if c in s_clean.columns]
        joined = joined.join(
            s_clean.select(*available_stud), on="student_id", how="left"
        )

    # 7. Unify school and department hierarchy fields
    school_col = F.lit("UNKNOWN")
    dept_col = F.lit("UNKNOWN")
    if "course_school" in joined.columns:
        school_col = F.coalesce(F.col("course_school"), school_col)
    if "student_school" in joined.columns:
        school_col = F.coalesce(F.col("student_school"), school_col)
    if "course_department" in joined.columns:
        dept_col = F.coalesce(F.col("course_department"), dept_col)
    if "student_department" in joined.columns:
        dept_col = F.coalesce(F.col("student_department"), dept_col)

    joined = joined.withColumn("school", school_col).withColumn(
        "department", dept_col
    )

    return joined.orderBy("student_id", "course_id", "semester_id")


def build_student_semester_features(feature_table_df: DataFrame) -> DataFrame:
    """Roll up student-course features to student x semester grain (features.md F-D03, schema.py).

    Args:
        feature_table_df: Integrated student-course-semester DataFrame.

    Returns:
        DataFrame conforming to the student_features gold collection schema:
        [student_id, semester_id, attendance_mean, engagement_count, late_submission_rate, score_trend].
    """
    rollup = feature_table_df.groupBy("student_id", "semester_id").agg(
        # Mean derived attendance percentage across enrolled courses
        F.round(F.avg("attendance_percentage"), 2)
        .cast("double")
        .alias("attendance_mean"),
        # Total LMS events across enrolled courses
        F.coalesce(F.sum("lms_total_events"), F.lit(0))
        .cast("int")
        .alias("engagement_count"),
        # Fraction of student's submissions submitted late
        F.when(
            F.sum("total_submissions") > 0,
            F.round(F.sum("late_submissions") / F.sum("total_submissions"), 4),
        )
        .otherwise(0.0)
        .cast("double")
        .alias("late_submission_rate"),
        # Graded-item / exam score trend (recent vs earlier)
        F.coalesce(F.round(F.avg("exam_marks_trend"), 2), F.lit(0.0))
        .cast("double")
        .alias("score_trend"),
        # Supporting analytical fields
        F.countDistinct("course_id").cast("int").alias("enrolled_courses_count"),
        F.coalesce(F.round(F.avg("academic_score"), 2), F.lit(0.0))
        .cast("double")
        .alias("avg_academic_score"),
        F.first("student_school", ignorenulls=True).alias("student_school"),
        F.first("student_department", ignorenulls=True).alias("student_department"),
    )

    return rollup.orderBy("student_id", "semester_id")


def run_j3_feature_table(
    spark: SparkSession,
    config: J3Config | None = None,
) -> J3Result:
    """Execute complete Spark integrated student feature table construction job (J3).

    Args:
        spark: Active SparkSession.
        config: Optional J3 configuration.

    Returns:
        J3Result containing integrated feature table, student rollup, and output metadata.
    """
    cfg = config or J3Config()
    logger.info("Starting J3 Integrated Student Feature Construction")

    # 1. Read cleaned domain datasets
    logger.info("Reading cleaned domain datasets from %s", cfg.academic_records_path.parent)
    acad_df = spark.read.parquet(str(cfg.academic_records_path))
    att_df = spark.read.parquet(str(cfg.attendance_path))
    cw_df = spark.read.parquet(str(cfg.coursework_path))
    lms_df = spark.read.parquet(str(cfg.lms_path))

    courses_df = None
    if cfg.courses_path.exists():
        courses_df = spark.read.parquet(str(cfg.courses_path))

    students_df = None
    if cfg.students_path.exists():
        students_df = spark.read.parquet(str(cfg.students_path))

    # 2. Build integrated student feature table
    feature_table = build_integrated_student_features(
        academic_records_df=acad_df,
        attendance_df=att_df,
        coursework_df=cw_df,
        lms_weekly_df=lms_df,
        courses_df=courses_df,
        students_df=students_df,
        join_mode=cfg.join_mode,
    )

    total_feature_rows = feature_table.count()
    distinct_students = feature_table.select("student_id").distinct().count()

    # 3. Build student-level semester roll-up
    student_rollup = build_student_semester_features(feature_table)

    # 4. Save to Parquet
    target_output = Path(cfg.output_path)
    if cfg.save_parquet:
        target_output.parent.mkdir(parents=True, exist_ok=True)
        writer = feature_table.write.mode("overwrite")
        if cfg.partition_by:
            writer = writer.partitionBy(*cfg.partition_by)
        writer.parquet(str(target_output))
        logger.info(
            "Saved integrated feature table to %s (%d rows)",
            target_output,
            total_feature_rows,
        )

        if cfg.student_rollup_path is not None:
            rollup_path = Path(cfg.student_rollup_path)
            rollup_path.parent.mkdir(parents=True, exist_ok=True)
            student_rollup.write.mode("overwrite").parquet(str(rollup_path))
            logger.info("Saved student rollup features to %s", rollup_path)

    logger.info(
        "J3 Feature Table completed: %d rows constructed across %d students",
        total_feature_rows,
        distinct_students,
    )

    return J3Result(
        feature_table=feature_table,
        student_rollup=student_rollup,
        total_features_rows=total_feature_rows,
        total_students=distinct_students,
        output_path=target_output,
    )
