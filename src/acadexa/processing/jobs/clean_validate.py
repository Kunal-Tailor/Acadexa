"""Spark clean and validate processing job - J1 (tasks 7.3 & 7.4, rules.md §10, §18, §32).

Job Responsibilities (F-D01, architecture.md §12):
1. Deduplicate events and core entities.
2. Normalize identifiers (student_id, course_id, school).
3. Detect orphan records referencing non-existent students.
4. Correct/drop invalid domain ranges (negative durations, attendance > 100%,
   marks outside [0, 100], coursework score > max_score).
5. Parse and standardize inconsistent timestamps.
6. Handle configured non-key nulls according to documented rules.
7. Produce comprehensive data quality report tracking:
   Injected -> Detected -> Corrected -> Dropped -> Remaining.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

logger = logging.getLogger(__name__)

INJECTION_CATEGORIES: tuple[str, ...] = (
    "duplicate_lms_events",
    "nulls_non_key",
    "timestamp_inconsistencies",
    "course_id_formatting",
    "orphan_records",
    "out_of_range_values",
)


@dataclass(frozen=True)
class J1Config:
    """Configuration for Spark J1 clean and validate job."""

    input_format: str = "file"  # "file" or "mongo"
    raw_data_dir: Path = Path("data")
    output_dir: Path = Path("data/processed")
    report_path: Path = Path("reports/quality/j1_quality_report.json")
    manifest_path: Path | None = Path("data/manifests/injection_manifest.json")
    impute_null_durations: bool = True
    impute_null_scores: bool = True
    impute_null_marks: bool = True
    save_parquet: bool = True
    save_report: bool = True


@dataclass
class IssueMetric:
    """Traceable issue metrics for a single quality category (rules.md §10.3, §32)."""

    injected: int = 0
    detected: int = 0
    corrected: int = 0
    dropped: int = 0
    remaining: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert metrics to dictionary."""
        return {
            "injected": self.injected,
            "detected": self.detected,
            "corrected": self.corrected,
            "dropped": self.dropped,
            "remaining": self.remaining,
        }


@dataclass
class DatasetQualityMetrics:
    """Per-dataset quality and cleaning metrics."""

    dataset_name: str
    input_rows: int = 0
    output_rows: int = 0
    issues: dict[str, IssueMetric] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert dataset metrics to dictionary."""
        return {
            "dataset_name": self.dataset_name,
            "input_rows": self.input_rows,
            "output_rows": self.output_rows,
            "issues": {k: v.to_dict() for k, v in self.issues.items()},
        }


@dataclass
class J1QualityReport:
    """Full J1 data quality report (rules.md §10.3, §32, prd.md §14)."""

    manifest_version: str = "1.0.0"
    job_name: str = "J1_clean_and_validate"
    generated_at: str = ""
    summary: dict[str, IssueMetric] = field(default_factory=dict)
    datasets: dict[str, DatasetQualityMetrics] = field(default_factory=dict)
    total_injected: int = 0
    total_detected: int = 0
    total_corrected: int = 0
    total_dropped: int = 0
    total_remaining: int = 0
    validation_status: str = "PASSED"

    def to_dict(self) -> dict[str, Any]:
        """Convert full report to dictionary."""
        return {
            "manifest_version": self.manifest_version,
            "job_name": self.job_name,
            "generated_at": self.generated_at,
            "validation_status": self.validation_status,
            "total_injected": self.total_injected,
            "total_detected": self.total_detected,
            "total_corrected": self.total_corrected,
            "total_dropped": self.total_dropped,
            "total_remaining": self.total_remaining,
            "summary": {k: v.to_dict() for k, v in self.summary.items()},
            "datasets": {k: v.to_dict() for k, v in self.datasets.items()},
        }

    def save(self, output_path: str | Path) -> None:
        """Save report to JSON file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Saved J1 data quality report to %s", target)


@dataclass
class J1Result:
    """Complete result of running J1 clean and validate."""

    students: DataFrame
    courses: DataFrame
    attendance: DataFrame
    coursework: DataFrame
    academic_records: DataFrame
    lms_events: DataFrame
    quality_report: J1QualityReport
    output_paths: dict[str, Path] = field(default_factory=dict)


def load_injection_manifest_counts(
    manifest_path: str | Path | None,
) -> tuple[dict[str, int], dict[str, dict[str, int]], int]:
    """Load ground-truth injected counts from injection_manifest.json if available.

    Returns:
        Tuple of (category_totals, per_dataset_counts, grand_total).
    """
    if manifest_path is None or not Path(manifest_path).exists():
        return {k: 0 for k in INJECTION_CATEGORIES}, {}, 0

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        category_totals = {
            k: data.get("injected_issue_counts", {}).get(k, 0) for k in INJECTION_CATEGORIES
        }
        per_dataset = data.get("per_dataset_counts", {})
        grand_total = data.get("total_injected", sum(category_totals.values()))
        return category_totals, per_dataset, grand_total
    except Exception as exc:
        logger.warning("Failed to load injection manifest from %s: %s", manifest_path, exc)
        return {k: 0 for k in INJECTION_CATEGORIES}, {}, 0


# ─────────────────────────────────────────────────────────────────────────────
# 1. Clean Students Reference Entity
# ─────────────────────────────────────────────────────────────────────────────


def clean_students(
    students_df: DataFrame,
) -> tuple[DataFrame, DatasetQualityMetrics]:
    """Clean students dataset: normalize identifiers and deduplicate."""
    input_rows = students_df.count()

    cleaned_df = students_df.withColumn(
        "student_id", F.trim(F.upper(F.col("student_id")))
    ).dropDuplicates(["student_id"])

    output_rows = cleaned_df.count()
    dropped_dups = input_rows - output_rows

    metrics = DatasetQualityMetrics(
        dataset_name="students",
        input_rows=input_rows,
        output_rows=output_rows,
    )
    if dropped_dups > 0:
        metrics.issues["duplicates"] = IssueMetric(
            detected=dropped_dups,
            dropped=dropped_dups,
        )

    return cleaned_df, metrics


# ─────────────────────────────────────────────────────────────────────────────
# 2. Clean Courses Reference Entity
# ─────────────────────────────────────────────────────────────────────────────


def clean_courses(
    courses_df: DataFrame,
) -> tuple[DataFrame, DatasetQualityMetrics]:
    """Clean courses dataset: normalize course identifiers and deduplicate."""
    input_rows = courses_df.count()

    cleaned_df = courses_df.withColumn(
        "course_id", F.trim(F.upper(F.col("course_id")))
    ).dropDuplicates(["course_id"])

    output_rows = cleaned_df.count()
    dropped_dups = input_rows - output_rows

    metrics = DatasetQualityMetrics(
        dataset_name="courses",
        input_rows=input_rows,
        output_rows=output_rows,
    )
    if dropped_dups > 0:
        metrics.issues["duplicates"] = IssueMetric(
            detected=dropped_dups,
            dropped=dropped_dups,
        )

    return cleaned_df, metrics


# ─────────────────────────────────────────────────────────────────────────────
# 3. Clean Attendance Dataset
# ─────────────────────────────────────────────────────────────────────────────


def clean_attendance(
    attendance_df: DataFrame,
    valid_students_df: DataFrame,
    injected_counts: dict[str, int] | None = None,
) -> tuple[DataFrame, DatasetQualityMetrics]:
    """Clean attendance dataset: course formatting, orphans, and range bounds."""
    injected = injected_counts or {}
    input_rows = attendance_df.count()

    # 1. Single-pass detection of formatting and out-of-range issues
    cond_cid = F.col("course_id") != F.trim(F.upper(F.col("course_id")))
    cond_oor = (F.col("classes_attended") > F.col("classes_conducted")) | (
        F.col("classes_attended") < 0
    )

    det_row = attendance_df.select(
        F.sum(F.when(cond_cid, 1).otherwise(0)).alias("cid_issues"),
        F.sum(F.when(cond_oor, 1).otherwise(0)).alias("oor_issues"),
    ).first()

    cid_detected = int(det_row["cid_issues"] or 0)
    oor_detected = int(det_row["oor_issues"] or 0)

    # 2. Normalize identifiers before orphan join
    norm_df = attendance_df.withColumn(
        "student_id", F.trim(F.upper(F.col("student_id")))
    ).withColumn("course_id", F.trim(F.upper(F.col("course_id"))))

    # 3. Detect and drop orphan records
    valid_student_ids = valid_students_df.select("student_id").distinct()
    orphan_df = norm_df.join(
        F.broadcast(valid_student_ids), on="student_id", how="left_anti"
    )
    orphans_detected = orphan_df.count()

    cleaned_df = norm_df.join(
        F.broadcast(valid_student_ids), on="student_id", how="inner"
    )

    # 4. Correct out-of-range classes_attended: clamp to [0, classes_conducted]
    cleaned_df = cleaned_df.withColumn(
        "classes_attended",
        F.when(
            F.col("classes_attended") > F.col("classes_conducted"),
            F.col("classes_conducted"),
        )
        .when(F.col("classes_attended") < 0, 0)
        .otherwise(F.col("classes_attended")),
    )

    # - Recompute attendance_rate accurately
    cleaned_df = cleaned_df.withColumn(
        "attendance_rate",
        F.round(
            F.col("classes_attended")
            / F.when(F.col("classes_conducted") > 0, F.col("classes_conducted")).otherwise(
                1.0
            ),
            4,
        ),
    )

    output_rows = cleaned_df.count()

    metrics = DatasetQualityMetrics(
        dataset_name="attendance",
        input_rows=input_rows,
        output_rows=output_rows,
        issues={
            "course_id_formatting": IssueMetric(
                injected=injected.get("course_id_formatting", 0),
                detected=cid_detected,
                corrected=cid_detected,
                dropped=0,
                remaining=0,
            ),
            "orphan_records": IssueMetric(
                injected=injected.get("orphan_records", 0),
                detected=orphans_detected,
                corrected=0,
                dropped=orphans_detected,
                remaining=0,
            ),
            "out_of_range_values": IssueMetric(
                injected=injected.get("out_of_range_values", 0),
                detected=oor_detected,
                corrected=oor_detected,
                dropped=0,
                remaining=0,
            ),
        },
    )

    return cleaned_df, metrics


# ─────────────────────────────────────────────────────────────────────────────
# 4. Clean Academic Records Dataset
# ─────────────────────────────────────────────────────────────────────────────


def clean_academic_records(
    academic_df: DataFrame,
    valid_students_df: DataFrame,
    injected_counts: dict[str, int] | None = None,
    impute_null_marks: bool = True,
) -> tuple[DataFrame, DatasetQualityMetrics]:
    """Clean academic records: course formatting, orphans, marks range, non-key nulls."""
    injected = injected_counts or {}
    input_rows = academic_df.count()

    # 1. Single-pass detection
    cond_cid = F.col("course_id") != F.trim(F.upper(F.col("course_id")))
    cond_oor = (
        (F.col("internal_marks") < 0)
        | (F.col("internal_marks") > 100)
        | (F.col("midterm_marks") < 0)
        | (F.col("midterm_marks") > 100)
        | (F.col("endterm_marks") < 0)
        | (F.col("endterm_marks") > 100)
    )
    cond_nulls = (
        F.col("internal_marks").isNull()
        | F.col("midterm_marks").isNull()
        | F.col("endterm_marks").isNull()
        | F.col("final_grade").isNull()
    )

    det_row = academic_df.select(
        F.sum(F.when(cond_cid, 1).otherwise(0)).alias("cid_issues"),
        F.sum(F.when(cond_oor, 1).otherwise(0)).alias("oor_issues"),
        F.sum(F.when(cond_nulls, 1).otherwise(0)).alias("null_issues"),
    ).first()

    cid_detected = int(det_row["cid_issues"] or 0)
    oor_detected = int(det_row["oor_issues"] or 0)
    null_detected = int(det_row["null_issues"] or 0)

    # 2. Normalize identifiers before orphan join
    norm_df = academic_df.withColumn(
        "student_id", F.trim(F.upper(F.col("student_id")))
    ).withColumn("course_id", F.trim(F.upper(F.col("course_id"))))

    # 3. Detect and drop orphans
    valid_student_ids = valid_students_df.select("student_id").distinct()
    orphan_df = norm_df.join(
        F.broadcast(valid_student_ids), on="student_id", how="left_anti"
    )
    orphans_detected = orphan_df.count()

    cleaned_df = norm_df.join(
        F.broadcast(valid_student_ids), on="student_id", how="inner"
    )

    # 4. Clamp marks to [0, 100]
    for col_name in ("internal_marks", "midterm_marks", "endterm_marks"):
        cleaned_df = cleaned_df.withColumn(
            col_name,
            F.when(F.col(col_name) < 0, 0)
            .when(F.col(col_name) > 100, 100)
            .otherwise(F.col(col_name)),
        )

    # Handle null marks and grade
    null_corrected = 0
    null_remaining = null_detected
    if impute_null_marks:
        # Fill missing marks with 0
        for col_name in ("internal_marks", "midterm_marks", "endterm_marks"):
            cleaned_df = cleaned_df.withColumn(
                col_name, F.coalesce(F.col(col_name), F.lit(0))
            )

        # Compute unweighted mean marks
        mean_marks = (
            F.col("internal_marks") + F.col("midterm_marks") + F.col("endterm_marks")
        ) / 3.0

        # Recalculate final_grade if null using standard grade scale
        computed_grade = (
            F.when(mean_marks >= 90.0, "A")
            .when(mean_marks >= 80.0, "B")
            .when(mean_marks >= 70.0, "C")
            .when(mean_marks >= 60.0, "D")
            .otherwise("F")
        )
        cleaned_df = cleaned_df.withColumn(
            "final_grade", F.coalesce(F.col("final_grade"), computed_grade)
        )
        null_corrected = null_detected
        null_remaining = 0

    output_rows = cleaned_df.count()

    metrics = DatasetQualityMetrics(
        dataset_name="academic_records",
        input_rows=input_rows,
        output_rows=output_rows,
        issues={
            "course_id_formatting": IssueMetric(
                injected=injected.get("course_id_formatting", 0),
                detected=cid_detected,
                corrected=cid_detected,
                dropped=0,
                remaining=0,
            ),
            "orphan_records": IssueMetric(
                injected=injected.get("orphan_records", 0),
                detected=orphans_detected,
                corrected=0,
                dropped=orphans_detected,
                remaining=0,
            ),
            "out_of_range_values": IssueMetric(
                injected=injected.get("out_of_range_values", 0),
                detected=oor_detected,
                corrected=oor_detected,
                dropped=0,
                remaining=0,
            ),
            "nulls_non_key": IssueMetric(
                injected=injected.get("nulls_non_key", 0),
                detected=null_detected,
                corrected=null_corrected,
                dropped=0,
                remaining=null_remaining,
            ),
        },
    )

    return cleaned_df, metrics


# ─────────────────────────────────────────────────────────────────────────────
# 5. Clean Coursework Dataset
# ─────────────────────────────────────────────────────────────────────────────


def clean_coursework(
    cw_df: DataFrame,
    valid_students_df: DataFrame,
    injected_counts: dict[str, int] | None = None,
    impute_null_scores: bool = True,
) -> tuple[DataFrame, DatasetQualityMetrics]:
    """Clean coursework dataset: course formatting, orphans, scores, timestamps, nulls."""
    injected = injected_counts or {}
    input_rows = cw_df.count()

    # Define robust timestamp parsing expression
    standard_ts = F.try_to_timestamp(
        F.col("submitted_at"), F.lit("yyyy-MM-dd'T'HH:mm:ss")
    )
    coalesced_ts = F.coalesce(
        standard_ts,
        F.try_to_timestamp(F.col("submitted_at"), F.lit("yyyy/MM/dd HH:mm:ss")),
        F.try_to_timestamp(F.col("submitted_at"), F.lit("dd-MM-yyyy HH:mm:ss")),
        F.try_to_timestamp(F.col("submitted_at"), F.lit("yyyy-MM-dd HH:mm:ss")),
        F.try_to_timestamp(F.col("submitted_at"), F.lit("yyyy-MM-dd'T'HH:mm:ss'Z'")),
        F.try_to_timestamp(F.col("submitted_at")),
    )

    # Single-pass detection
    cond_cid = F.col("course_id") != F.trim(F.upper(F.col("course_id")))
    cond_oor = (F.col("score") < 0) | (F.col("score") > F.col("max_score"))
    cond_null_score = (F.col("status") != "MISSING") & F.col("score").isNull()
    cond_ts_issue = (
        F.col("submitted_at").isNotNull()
        & standard_ts.isNull()
        & coalesced_ts.isNotNull()
    )

    det_row = cw_df.select(
        F.sum(F.when(cond_cid, 1).otherwise(0)).alias("cid_issues"),
        F.sum(F.when(cond_oor, 1).otherwise(0)).alias("oor_issues"),
        F.sum(F.when(cond_null_score, 1).otherwise(0)).alias("null_issues"),
        F.sum(F.when(cond_ts_issue, 1).otherwise(0)).alias("ts_issues"),
    ).first()

    cid_detected = int(det_row["cid_issues"] or 0)
    oor_detected = int(det_row["oor_issues"] or 0)
    null_detected = int(det_row["null_issues"] or 0)
    ts_detected = int(det_row["ts_issues"] or 0)

    # 2. Normalize identifiers before orphan join
    norm_df = cw_df.withColumn(
        "student_id", F.trim(F.upper(F.col("student_id")))
    ).withColumn("course_id", F.trim(F.upper(F.col("course_id"))))

    # 3. Detect and drop orphans
    valid_student_ids = valid_students_df.select("student_id").distinct()
    orphan_df = norm_df.join(
        F.broadcast(valid_student_ids), on="student_id", how="left_anti"
    )
    orphans_detected = orphan_df.count()

    cleaned_df = norm_df.join(
        F.broadcast(valid_student_ids), on="student_id", how="inner"
    )

    # 4. Standardize submitted_at timestamp
    cleaned_df = cleaned_df.withColumn("submitted_at", coalesced_ts)

    # Clamp score to [0, max_score]
    cleaned_df = cleaned_df.withColumn(
        "score",
        F.when(F.col("score") < 0, 0.0)
        .when(F.col("score") > F.col("max_score"), F.col("max_score"))
        .otherwise(F.col("score")),
    )

    # Handle null scores
    null_corrected = 0
    null_remaining = null_detected
    if impute_null_scores:
        cleaned_df = cleaned_df.withColumn(
            "score",
            F.when(
                (F.col("status") != "MISSING") & F.col("score").isNull(),
                F.lit(0.0),
            ).otherwise(F.col("score")),
        )
        null_corrected = null_detected
        null_remaining = 0

    output_rows = cleaned_df.count()

    metrics = DatasetQualityMetrics(
        dataset_name="coursework",
        input_rows=input_rows,
        output_rows=output_rows,
        issues={
            "course_id_formatting": IssueMetric(
                injected=injected.get("course_id_formatting", 0),
                detected=cid_detected,
                corrected=cid_detected,
                dropped=0,
                remaining=0,
            ),
            "orphan_records": IssueMetric(
                injected=injected.get("orphan_records", 0),
                detected=orphans_detected,
                corrected=0,
                dropped=orphans_detected,
                remaining=0,
            ),
            "out_of_range_values": IssueMetric(
                injected=injected.get("out_of_range_values", 0),
                detected=oor_detected,
                corrected=oor_detected,
                dropped=0,
                remaining=0,
            ),
            "timestamp_inconsistencies": IssueMetric(
                injected=injected.get("timestamp_inconsistencies", 0),
                detected=ts_detected,
                corrected=ts_detected,
                dropped=0,
                remaining=0,
            ),
            "nulls_non_key": IssueMetric(
                injected=injected.get("nulls_non_key", 0),
                detected=null_detected,
                corrected=null_corrected,
                dropped=0,
                remaining=null_remaining,
            ),
        },
    )

    return cleaned_df, metrics


# ─────────────────────────────────────────────────────────────────────────────
# 6. Clean LMS Events Dataset
# ─────────────────────────────────────────────────────────────────────────────


def clean_lms_events(
    lms_df: DataFrame,
    valid_students_df: DataFrame,
    injected_counts: dict[str, int] | None = None,
    impute_null_durations: bool = True,
) -> tuple[DataFrame, DatasetQualityMetrics]:
    """Clean LMS events: duplicates, orphans, course formatting, duration range, nulls."""
    injected = injected_counts or {}
    input_rows = lms_df.count()

    # 1. Deduplicate exact duplicate rows
    dedup_df = lms_df.dropDuplicates()
    dedup_rows = dedup_df.count()
    duplicates_dropped = input_rows - dedup_rows

    # 2. Single-pass detection on deduplicated dataset
    cond_cid = F.col("meta.course_id") != F.trim(F.upper(F.col("meta.course_id")))
    cond_oor = F.col("duration_sec") < 0
    cond_null_dur = (
        F.col("activity_type").isin("VIDEO_VIEW", "VIDEO_COMPLETE", "PDF_VIEW")
        & F.col("duration_sec").isNull()
    )

    det_row = dedup_df.select(
        F.sum(F.when(cond_cid, 1).otherwise(0)).alias("cid_issues"),
        F.sum(F.when(cond_oor, 1).otherwise(0)).alias("oor_issues"),
        F.sum(F.when(cond_null_dur, 1).otherwise(0)).alias("null_issues"),
    ).first()

    cid_detected = int(det_row["cid_issues"] or 0)
    oor_detected = int(det_row["oor_issues"] or 0)
    null_detected = int(det_row["null_issues"] or 0)

    # 3. Standardize meta struct (student_id, course_id, school) before orphan join
    norm_df = dedup_df.withColumn(
        "meta",
        F.struct(
            F.trim(F.upper(F.col("meta.student_id"))).alias("student_id"),
            F.trim(F.upper(F.col("meta.course_id"))).alias("course_id"),
            F.col("meta.school").alias("school"),
        ),
    )

    # 4. Detect and filter orphans
    valid_student_ids = valid_students_df.select("student_id").distinct()
    orphan_df = norm_df.join(
        F.broadcast(valid_student_ids),
        norm_df["meta.student_id"] == valid_student_ids["student_id"],
        how="left_anti",
    )
    orphans_detected = orphan_df.count()

    cleaned_df = norm_df.join(
        F.broadcast(valid_student_ids),
        norm_df["meta.student_id"] == valid_student_ids["student_id"],
        how="inner",
    ).drop(valid_student_ids["student_id"])

    # 5. Clamp negative durations to 0
    cleaned_df = cleaned_df.withColumn(
        "duration_sec",
        F.when(F.col("duration_sec") < 0, F.lit(0)).otherwise(F.col("duration_sec")),
    )

    # Handle null durations
    null_corrected = 0
    null_remaining = null_detected
    if impute_null_durations:
        cleaned_df = cleaned_df.withColumn(
            "duration_sec",
            F.when(
                F.col("activity_type").isin("VIDEO_VIEW", "VIDEO_COMPLETE", "PDF_VIEW")
                & F.col("duration_sec").isNull(),
                F.lit(0),
            ).otherwise(F.col("duration_sec")),
        )
        null_corrected = null_detected
        null_remaining = 0

    output_rows = cleaned_df.count()

    metrics = DatasetQualityMetrics(
        dataset_name="lms_events",
        input_rows=input_rows,
        output_rows=output_rows,
        issues={
            "duplicate_lms_events": IssueMetric(
                injected=injected.get("duplicate_lms_events", 0),
                detected=duplicates_dropped,
                corrected=0,
                dropped=duplicates_dropped,
                remaining=0,
            ),
            "course_id_formatting": IssueMetric(
                injected=injected.get("course_id_formatting", 0),
                detected=cid_detected,
                corrected=cid_detected,
                dropped=0,
                remaining=0,
            ),
            "orphan_records": IssueMetric(
                injected=injected.get("orphan_records", 0),
                detected=orphans_detected,
                corrected=0,
                dropped=orphans_detected,
                remaining=0,
            ),
            "out_of_range_values": IssueMetric(
                injected=injected.get("out_of_range_values", 0),
                detected=oor_detected,
                corrected=oor_detected,
                dropped=0,
                remaining=0,
            ),
            "nulls_non_key": IssueMetric(
                injected=injected.get("nulls_non_key", 0),
                detected=null_detected,
                corrected=null_corrected,
                dropped=0,
                remaining=null_remaining,
            ),
        },
    )

    return cleaned_df, metrics


# ─────────────────────────────────────────────────────────────────────────────
# 7. Quality Report Builder
# ─────────────────────────────────────────────────────────────────────────────


def build_j1_quality_report(
    dataset_metrics: dict[str, DatasetQualityMetrics],
    manifest_category_totals: dict[str, int] | None = None,
    manifest_grand_total: int = 0,
) -> J1QualityReport:
    """Consolidate per-dataset cleaning metrics into J1QualityReport."""
    summary: dict[str, IssueMetric] = {
        cat: IssueMetric(injected=manifest_category_totals.get(cat, 0) if manifest_category_totals else 0)
        for cat in INJECTION_CATEGORIES
    }

    # Aggregate across datasets
    for ds_metrics in dataset_metrics.values():
        for cat, issue in ds_metrics.issues.items():
            if cat in summary:
                summary[cat].detected += issue.detected
                summary[cat].corrected += issue.corrected
                summary[cat].dropped += issue.dropped
                summary[cat].remaining += issue.remaining

    total_injected = (
        manifest_grand_total
        if manifest_grand_total > 0
        else sum(m.injected for m in summary.values())
    )
    total_detected = sum(m.detected for m in summary.values())
    total_corrected = sum(m.corrected for m in summary.values())
    total_dropped = sum(m.dropped for m in summary.values())
    total_remaining = sum(m.remaining for m in summary.values())

    return J1QualityReport(
        manifest_version="1.0.0",
        job_name="J1_clean_and_validate",
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        datasets=dataset_metrics,
        total_injected=total_injected,
        total_detected=total_detected,
        total_corrected=total_corrected,
        total_dropped=total_dropped,
        total_remaining=total_remaining,
        validation_status="PASSED" if total_remaining == 0 else "WARNING_ISSUES_REMAIN",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. J1 Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


def run_j1_clean_and_validate(
    spark: SparkSession,
    config: J1Config | None = None,
) -> J1Result:
    """Execute complete Spark clean and validate job (J1).

    Args:
        spark: Active SparkSession.
        config: Optional J1 configuration.

    Returns:
        J1Result containing cleaned DataFrames and data quality report.
    """
    cfg = config or J1Config()
    logger.info("Starting J1 Clean and Validate job (data_dir: %s)", cfg.raw_data_dir)

    # 1. Load ground truth injection counts
    manifest_totals, per_dataset_injected, grand_total = load_injection_manifest_counts(
        cfg.manifest_path
    )

    # 2. Load input DataFrames
    raw_dir = Path(cfg.raw_data_dir)
    if cfg.input_format == "mongo":
        from acadexa.processing.mongo import read_mongo_collection

        students_raw = read_mongo_collection(spark, "students")
        courses_raw = read_mongo_collection(spark, "courses")
        attendance_raw = read_mongo_collection(spark, "attendance")
        coursework_raw = read_mongo_collection(spark, "coursework")
        academic_raw = read_mongo_collection(spark, "academic_records")
        lms_raw = read_mongo_collection(spark, "lms_events")
    else:
        gen_dir = raw_dir / "generated"
        lms_path = raw_dir / "raw" / "lms_events"
        if not lms_path.exists():
            lms_path = raw_dir / "lms_events"

        students_raw = spark.read.option("multiline", "true").json(
            str(gen_dir / "students.json")
        )
        courses_raw = spark.read.option("multiline", "true").json(
            str(gen_dir / "courses.json")
        )
        attendance_raw = spark.read.option("multiline", "true").json(
            str(gen_dir / "attendance.json")
        )
        coursework_raw = spark.read.option("multiline", "true").json(
            str(gen_dir / "coursework.json")
        )
        academic_raw = spark.read.option("multiline", "true").json(
            str(gen_dir / "academic_records.json")
        )
        lms_raw = spark.read.parquet(str(lms_path))

    # 3. Clean reference entities first
    clean_stud_df, stud_metrics = clean_students(students_raw)
    clean_crs_df, crs_metrics = clean_courses(courses_raw)

    # 4. Clean domain collections using cleaned students reference
    clean_att_df, att_metrics = clean_attendance(
        attendance_df=attendance_raw,
        valid_students_df=clean_stud_df,
        injected_counts=per_dataset_injected.get("attendance"),
    )

    clean_acad_df, acad_metrics = clean_academic_records(
        academic_df=academic_raw,
        valid_students_df=clean_stud_df,
        injected_counts=per_dataset_injected.get("academic_records"),
        impute_null_marks=cfg.impute_null_marks,
    )

    clean_cw_df, cw_metrics = clean_coursework(
        cw_df=coursework_raw,
        valid_students_df=clean_stud_df,
        injected_counts=per_dataset_injected.get("coursework"),
        impute_null_scores=cfg.impute_null_scores,
    )

    clean_lms_df, lms_metrics = clean_lms_events(
        lms_df=lms_raw,
        valid_students_df=clean_stud_df,
        injected_counts=per_dataset_injected.get("lms_events"),
        impute_null_durations=cfg.impute_null_durations,
    )

    # 5. Build consolidated Quality Report
    dataset_metrics = {
        "students": stud_metrics,
        "courses": crs_metrics,
        "attendance": att_metrics,
        "academic_records": acad_metrics,
        "coursework": cw_metrics,
        "lms_events": lms_metrics,
    }

    report = build_j1_quality_report(
        dataset_metrics=dataset_metrics,
        manifest_category_totals=manifest_totals,
        manifest_grand_total=grand_total,
    )

    # 6. Save outputs
    output_paths: dict[str, Path] = {}
    if cfg.save_parquet:
        out_base = Path(cfg.output_dir)
        out_base.mkdir(parents=True, exist_ok=True)

        datasets_to_save = {
            "students": clean_stud_df,
            "courses": clean_crs_df,
            "attendance": clean_att_df,
            "academic_records": clean_acad_df,
            "coursework": clean_cw_df,
            "lms_events": clean_lms_df,
        }

        for name, df in datasets_to_save.items():
            target_path = out_base / name
            df.write.mode("overwrite").parquet(str(target_path))
            output_paths[name] = target_path
            logger.info("Saved cleaned %s to %s", name, target_path)

    if cfg.save_report:
        report.save(cfg.report_path)
        output_paths["quality_report"] = Path(cfg.report_path)

    logger.info(
        "J1 Clean and Validate complete. Detected: %d, Corrected: %d, Dropped: %d, Remaining: %d",
        report.total_detected,
        report.total_corrected,
        report.total_dropped,
        report.total_remaining,
    )

    return J1Result(
        students=clean_stud_df,
        courses=clean_crs_df,
        attendance=clean_att_df,
        coursework=clean_cw_df,
        academic_records=clean_acad_df,
        lms_events=clean_lms_df,
        quality_report=report,
        output_paths=output_paths,
    )
