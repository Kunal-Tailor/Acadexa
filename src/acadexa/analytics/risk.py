"""Rule-based risk signal detection and explainability (Tasks 8.7 & 8.8, rules.md §8, §17, §18, §22).

Implements the five approved rule-based risk signals exactly from config/risk/risk_signals.toml:
1. Low attendance: term-to-date attendance below 75%
2. LMS decline: 4-week engagement <= 50% of prior 4-week period
3. Late submissions: more than 30% of assignments submitted late
4. Marks decline: recent 3 graded items drop >= 10 points below earlier average
5. Low quiz activity: quiz attempts in bottom quartile within student's course

Each triggered signal contributes one point (signal count 0..5).
Traceable explainability strings provide full transparency for each indicator without black-box ML.
Zero driver-side iteration or large collect/toPandas calls (rules.md §17.3).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from acadexa.config.loader import load_config_file

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH: Path = Path("config/risk/risk_signals.toml")


@dataclass(frozen=True)
class RiskSignalThresholds:
    """Configured thresholds for the five approved rule-based risk signals."""

    attendance_threshold: float = 75.0
    lms_comparison_ratio: float = 0.50
    late_rate_threshold: float = 0.30
    marks_drop_threshold: float = 10.0
    quiz_percentile_threshold: float = 0.25

    @classmethod
    def from_config(cls, path: Path | str | None = None) -> RiskSignalThresholds:
        """Load thresholds from config/risk/risk_signals.toml or fallback to defaults."""
        cfg_file = Path(path) if path is not None else DEFAULT_CONFIG_PATH
        if not cfg_file.is_file():
            logger.warning("Risk config %s not found, using default thresholds", cfg_file)
            return cls()

        data = load_config_file(cfg_file)
        signals = data.get("signals", {})

        return cls(
            attendance_threshold=float(
                signals.get("low_attendance", {}).get("threshold_percent", 75.0)
            ),
            lms_comparison_ratio=float(
                signals.get("lms_decline", {}).get("comparison_ratio", 0.50)
            ),
            late_rate_threshold=float(
                signals.get("late_submissions", {}).get("late_rate_threshold", 0.30)
            ),
            marks_drop_threshold=float(
                signals.get("marks_decline", {}).get("point_drop_threshold", 10.0)
            ),
            quiz_percentile_threshold=float(
                signals.get("low_quiz_activity", {}).get("percentile_threshold", 0.25)
            ),
        )


def evaluate_student_course_risk_signals(
    df: DataFrame,
    thresholds: RiskSignalThresholds | None = None,
) -> DataFrame:
    """Evaluate five risk signals with explainability at student x course x semester grain.

    Args:
        df: Integrated DataFrame containing student features and trend indicators.
        thresholds: Configured risk signal thresholds.

    Returns:
        DataFrame enriched with 5 boolean signal flags, signal_count, and explanation strings.
    """
    th = thresholds or RiskSignalThresholds()
    df_eval = df

    # Ensure expected columns exist with defaults if missing
    if "attendance_percentage" not in df_eval.columns:
        df_eval = df_eval.withColumn("attendance_percentage", F.lit(None).cast("double"))
    if "lms_decline_detected" not in df_eval.columns:
        df_eval = df_eval.withColumn("lms_decline_detected", F.lit(False))
    if "lms_recent_vs_prior_ratio" not in df_eval.columns:
        df_eval = df_eval.withColumn("lms_recent_vs_prior_ratio", F.lit(None).cast("double"))
    if "lms_prev_4w_events" not in df_eval.columns:
        df_eval = df_eval.withColumn("lms_prev_4w_events", F.lit(0).cast("long"))
    if "marks_decline_detected" not in df_eval.columns:
        df_eval = df_eval.withColumn("marks_decline_detected", F.lit(False))
    if "marks_drop_points" not in df_eval.columns:
        df_eval = df_eval.withColumn("marks_drop_points", F.lit(None).cast("double"))
    if "total_quiz_attempts" not in df_eval.columns:
        df_eval = df_eval.withColumn("total_quiz_attempts", F.lit(0).cast("int"))

    # Integer display thresholds for clear explanation strings
    th_att_display = (
        int(th.attendance_threshold)
        if th.attendance_threshold.is_integer()
        else th.attendance_threshold
    )
    th_lms_pct = (
        int(th.lms_comparison_ratio * 100)
        if (th.lms_comparison_ratio * 100).is_integer()
        else (th.lms_comparison_ratio * 100)
    )
    th_late_pct = (
        int(th.late_rate_threshold * 100)
        if (th.late_rate_threshold * 100).is_integer()
        else (th.late_rate_threshold * 100)
    )
    th_marks_display = (
        int(th.marks_drop_threshold)
        if th.marks_drop_threshold.is_integer()
        else th.marks_drop_threshold
    )
    th_quiz_pct = (
        int(th.quiz_percentile_threshold * 100)
        if (th.quiz_percentile_threshold * 100).is_integer()
        else (th.quiz_percentile_threshold * 100)
    )

    # 1. Low attendance (Signal 1: term-to-date attendance below threshold)
    low_att_cond = F.col("attendance_percentage").isNotNull() & (
        F.col("attendance_percentage") < F.lit(th.attendance_threshold)
    )
    df_eval = df_eval.withColumn(
        "low_attendance", F.when(low_att_cond, F.lit(True)).otherwise(F.lit(False))
    )

    # 2. LMS decline (Signal 2: 4w engagement <= 50% of prior 4w)
    lms_decl_cond = (
        (F.col("lms_decline_detected") == True)
        | (
            F.col("lms_recent_vs_prior_ratio").isNotNull()
            & (F.col("lms_recent_vs_prior_ratio") <= F.lit(th.lms_comparison_ratio))
            & (F.col("lms_prev_4w_events") > 0)
        )
    )
    df_eval = df_eval.withColumn(
        "lms_decline", F.when(lms_decl_cond, F.lit(True)).otherwise(F.lit(False))
    )

    # 3. Late submissions (Signal 3: > 30% assignments late)
    late_col = F.coalesce(
        F.col("late_assignment_rate") if "late_assignment_rate" in df_eval.columns else F.lit(None),
        F.col("late_submission_rate") if "late_submission_rate" in df_eval.columns else F.lit(None),
        F.lit(0.0),
    )
    late_sub_cond = late_col > F.lit(th.late_rate_threshold)
    df_eval = df_eval.withColumn(
        "late_submissions", F.when(late_sub_cond, F.lit(True)).otherwise(F.lit(False))
    )

    # 4. Marks decline (Signal 4: recent 3 graded items drop >= 10 pts)
    marks_decl_cond = (
        (F.col("marks_decline_detected") == True)
        | (
            F.col("marks_drop_points").isNotNull()
            & (F.col("marks_drop_points") >= F.lit(th.marks_drop_threshold))
        )
    )
    df_eval = df_eval.withColumn(
        "marks_decline", F.when(marks_decl_cond, F.lit(True)).otherwise(F.lit(False))
    )

    # 5. Low quiz activity (Signal 5: bottom quartile within course offering)
    partition_cols = [c for c in ("course_id", "semester_id") if c in df_eval.columns]
    if partition_cols:
        w_course = Window.partitionBy(*partition_cols)
    else:
        w_course = Window.partitionBy()
    quiz_attempts_col = F.coalesce(F.col("total_quiz_attempts"), F.lit(0))
    quiz_rank = F.percent_rank().over(w_course.orderBy(quiz_attempts_col))
    low_quiz_cond = quiz_rank < F.lit(th.quiz_percentile_threshold)
    df_eval = df_eval.withColumn(
        "low_quiz_activity", F.when(low_quiz_cond, F.lit(True)).otherwise(F.lit(False))
    )

    # 6. Composite signal count (0..5)
    signal_count_expr = (
        F.when(F.col("low_attendance"), 1).otherwise(0)
        + F.when(F.col("lms_decline"), 1).otherwise(0)
        + F.when(F.col("late_submissions"), 1).otherwise(0)
        + F.when(F.col("marks_decline"), 1).otherwise(0)
        + F.when(F.col("low_quiz_activity"), 1).otherwise(0)
    )
    df_eval = df_eval.withColumn("signal_count", signal_count_expr.cast("int"))

    # 7. Traceable explainability strings (Task 8.8)
    exp_att = F.when(
        F.col("low_attendance"),
        F.concat(
            F.lit("term-to-date attendance "),
            F.round(F.col("attendance_percentage"), 1),
            F.lit("% < "),
            F.lit(th_att_display),
            F.lit("% threshold"),
        ),
    ).otherwise(
        F.when(
            F.col("attendance_percentage").isNotNull(),
            F.concat(
                F.lit("term-to-date attendance "),
                F.round(F.col("attendance_percentage"), 1),
                F.lit("% >= "),
                F.lit(th_att_display),
                F.lit("% threshold"),
            ),
        ).otherwise(F.lit("attendance data not recorded"))
    )

    exp_lms = F.when(
        F.col("lms_decline"),
        F.concat(
            F.lit("last 4 weeks = "),
            F.round(F.coalesce(F.col("lms_recent_vs_prior_ratio"), F.lit(0.0)) * 100, 1),
            F.lit("% of previous 4 weeks (<= "),
            F.lit(th_lms_pct),
            F.lit("% threshold)"),
        ),
    ).otherwise(
        F.concat(
            F.lit("LMS activity stable (ratio "),
            F.round(F.coalesce(F.col("lms_recent_vs_prior_ratio"), F.lit(1.0)) * 100, 1),
            F.lit("% > "),
            F.lit(th_lms_pct),
            F.lit("% threshold)"),
        )
    )

    exp_late = F.when(
        F.col("late_submissions"),
        F.concat(
            F.lit("late rate "),
            F.round(late_col * 100, 1),
            F.lit("% > "),
            F.lit(th_late_pct),
            F.lit("% threshold"),
        ),
    ).otherwise(
        F.concat(
            F.lit("late rate "),
            F.round(late_col * 100, 1),
            F.lit("% <= "),
            F.lit(th_late_pct),
            F.lit("% threshold"),
        )
    )

    exp_marks = F.when(
        F.col("marks_decline"),
        F.concat(
            F.lit("recent graded items dropped by "),
            F.round(F.coalesce(F.col("marks_drop_points"), F.lit(0.0)), 1),
            F.lit(" pts (>= "),
            F.lit(th_marks_display),
            F.lit(" pts below)"),
        ),
    ).otherwise(
        F.concat(
            F.lit("graded items trajectory stable (drop "),
            F.round(F.coalesce(F.col("marks_drop_points"), F.lit(0.0)), 1),
            F.lit(" pts < "),
            F.lit(th_marks_display),
            F.lit(" pts threshold)"),
        )
    )

    exp_quiz = F.when(
        F.col("low_quiz_activity"),
        F.concat(
            F.lit("quiz attempts ("),
            quiz_attempts_col,
            F.lit(") in bottom quartile of course (< "),
            F.lit(th_quiz_pct),
            F.lit("th percentile)"),
        ),
    ).otherwise(
        F.concat(
            F.lit("quiz attempts "),
            quiz_attempts_col,
            F.lit(" not in bottom quartile (>= "),
            F.lit(th_quiz_pct),
            F.lit("th percentile)"),
        )
    )

    df_eval = df_eval.withColumn(
        "explanations",
        F.struct(
            exp_att.alias("low_attendance"),
            exp_lms.alias("lms_decline"),
            exp_late.alias("late_submissions"),
            exp_marks.alias("marks_decline"),
            exp_quiz.alias("low_quiz_activity"),
        ),
    )

    return df_eval


def build_student_risk_indicators(
    df_course_risk: DataFrame,
    evaluation_week_start: str | None = None,
    include_hierarchy: bool = False,
) -> DataFrame:
    """Roll up student-course risk evaluations to student-level risk indicators conforming to schema.py.

    Grain: student_id x week_start.

    Args:
        df_course_risk: DataFrame from evaluate_student_course_risk_signals.
        evaluation_week_start: Optional ISO date string for evaluation week (default: 2026-04-20).
        include_hierarchy: Whether to include school and department columns.

    Returns:
        DataFrame conforming to RISK_INDICATORS_SCHEMA.
    """
    week_start_val = evaluation_week_start or "2026-04-20"
    week_start_col = F.to_date(F.lit(week_start_val))

    agg_exprs = [
        # Student triggers signal if triggered in any enrolled course
        (F.max(F.when(F.col("low_attendance"), 1).otherwise(0)) == 1).alias("low_attendance"),
        (F.max(F.when(F.col("lms_decline"), 1).otherwise(0)) == 1).alias("lms_decline"),
        (F.max(F.when(F.col("late_submissions"), 1).otherwise(0)) == 1).alias("late_submissions"),
        (F.max(F.when(F.col("marks_decline"), 1).otherwise(0)) == 1).alias("marks_decline"),
        (F.max(F.when(F.col("low_quiz_activity"), 1).otherwise(0)) == 1).alias("low_quiz_activity"),
        # Explanations: pick triggered explanation if signal is true, otherwise fallback to un-triggered
        F.coalesce(
            F.max(F.when(F.col("low_attendance"), F.col("explanations.low_attendance"))),
            F.first("explanations.low_attendance", ignorenulls=True),
        ).alias("exp_att"),
        F.coalesce(
            F.max(F.when(F.col("lms_decline"), F.col("explanations.lms_decline"))),
            F.first("explanations.lms_decline", ignorenulls=True),
        ).alias("exp_lms"),
        F.coalesce(
            F.max(F.when(F.col("late_submissions"), F.col("explanations.late_submissions"))),
            F.first("explanations.late_submissions", ignorenulls=True),
        ).alias("exp_late"),
        F.coalesce(
            F.max(F.when(F.col("marks_decline"), F.col("explanations.marks_decline"))),
            F.first("explanations.marks_decline", ignorenulls=True),
        ).alias("exp_marks"),
        F.coalesce(
            F.max(F.when(F.col("low_quiz_activity"), F.col("explanations.low_quiz_activity"))),
            F.first("explanations.low_quiz_activity", ignorenulls=True),
        ).alias("exp_quiz"),
    ]

    if "student_school" in df_course_risk.columns:
        agg_exprs.append(F.first("student_school", ignorenulls=True).alias("school"))
    elif "school" in df_course_risk.columns:
        agg_exprs.append(F.first("school", ignorenulls=True).alias("school"))

    if "student_department" in df_course_risk.columns:
        agg_exprs.append(F.first("student_department", ignorenulls=True).alias("department"))
    elif "department" in df_course_risk.columns:
        agg_exprs.append(F.first("department", ignorenulls=True).alias("department"))

    student_risk = df_course_risk.groupBy("student_id").agg(*agg_exprs)

    # Calculate overall student signal count (0..5)
    signal_count_expr = (
        F.when(F.col("low_attendance"), 1).otherwise(0)
        + F.when(F.col("lms_decline"), 1).otherwise(0)
        + F.when(F.col("late_submissions"), 1).otherwise(0)
        + F.when(F.col("marks_decline"), 1).otherwise(0)
        + F.when(F.col("low_quiz_activity"), 1).otherwise(0)
    )

    res = (
        student_risk.withColumn("signal_count", signal_count_expr.cast("int"))
        .withColumn("week_start", week_start_col)
        .withColumn("computed_at", F.current_timestamp())
        .withColumn(
            "explanations",
            F.struct(
                F.col("exp_att").alias("low_attendance"),
                F.col("exp_lms").alias("lms_decline"),
                F.col("exp_late").alias("late_submissions"),
                F.col("exp_marks").alias("marks_decline"),
                F.col("exp_quiz").alias("low_quiz_activity"),
            ),
        )
        .drop("exp_att", "exp_lms", "exp_late", "exp_marks", "exp_quiz")
    )

    cols_to_select = [
        "student_id",
        "week_start",
        "signal_count",
        "low_attendance",
        "lms_decline",
        "late_submissions",
        "marks_decline",
        "low_quiz_activity",
        "explanations",
        "computed_at",
    ]
    if include_hierarchy and "school" in res.columns and "department" in res.columns:
        cols_to_select.extend(["school", "department"])

    return res.select(*cols_to_select).orderBy("student_id")
