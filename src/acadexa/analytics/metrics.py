"""Domain metric calculations and expressions (Task 8.2, features.md F-D03, rules.md §13).

Provides canonical, reusable PySpark Column expressions for academic,
attendance, coursework, and LMS engagement derived metrics.
"""

from __future__ import annotations

from pyspark.sql import Column
from pyspark.sql import functions as F


def calculate_attendance_rate(
    attended_col: str | Column = "classes_attended",
    conducted_col: str | Column = "classes_conducted",
) -> Column:
    """Compute attendance rate as a ratio in [0.0, 1.0].

    Args:
        attended_col: Column or column name for classes attended.
        conducted_col: Column or column name for classes conducted.

    Returns:
        PySpark Column representing attendance rate.
    """
    att = F.col(attended_col) if isinstance(attended_col, str) else attended_col
    cond = F.col(conducted_col) if isinstance(conducted_col, str) else conducted_col
    return F.when(cond > 0, att / cond).otherwise(0.0).cast("double")


def calculate_attendance_percentage(
    attended_col: str | Column = "classes_attended",
    conducted_col: str | Column = "classes_conducted",
) -> Column:
    """Compute attendance percentage in [0.0, 100.0].

    Args:
        attended_col: Column or column name for classes attended.
        conducted_col: Column or column name for classes conducted.

    Returns:
        PySpark Column representing attendance percentage.
    """
    return (calculate_attendance_rate(attended_col, conducted_col) * 100.0).cast("double")


def calculate_late_submission_rate(
    late_col: str | Column = "late_submissions",
    total_col: str | Column = "total_submissions",
) -> Column:
    """Compute late submission rate as a fraction in [0.0, 1.0].

    Args:
        late_col: Column or column name for late submission count.
        total_col: Column or column name for total submission count.

    Returns:
        PySpark Column representing late submission rate.
    """
    late = F.col(late_col) if isinstance(late_col, str) else late_col
    tot = F.col(total_col) if isinstance(total_col, str) else total_col
    return F.when(tot > 0, late / tot).otherwise(0.0).cast("double")


def calculate_missing_rate(
    missing_col: str | Column = "missing_submissions",
    total_col: str | Column = "total_coursework",
) -> Column:
    """Compute missing coursework rate as a fraction in [0.0, 1.0].

    Args:
        missing_col: Column or column name for missing submission count.
        total_col: Column or column name for total coursework items count.

    Returns:
        PySpark Column representing missing rate.
    """
    miss = F.col(missing_col) if isinstance(missing_col, str) else missing_col
    tot = F.col(total_col) if isinstance(total_col, str) else total_col
    return F.when(tot > 0, miss / tot).otherwise(0.0).cast("double")


def calculate_score_percentage(
    score_col: str | Column = "total_score",
    max_score_col: str | Column = "max_score",
) -> Column:
    """Compute coursework score percentage in [0.0, 100.0].

    Args:
        score_col: Column or column name for earned score.
        max_score_col: Column or column name for maximum attainable score.

    Returns:
        PySpark Column representing percentage score.
    """
    sc = F.col(score_col) if isinstance(score_col, str) else score_col
    mx = F.col(max_score_col) if isinstance(max_score_col, str) else max_score_col
    return F.when(mx > 0, (sc / mx) * 100.0).otherwise(0.0).cast("double")


def calculate_quiz_retry_ratio(
    attempts_col: str | Column = "total_quiz_attempts",
    quizzes_col: str | Column = "total_quizzes",
) -> Column:
    """Compute average quiz retry ratio (attempts per quiz).

    Args:
        attempts_col: Column or column name for total quiz attempts.
        quizzes_col: Column or column name for total quiz count.

    Returns:
        PySpark Column representing retry ratio.
    """
    att = F.col(attempts_col) if isinstance(attempts_col, str) else attempts_col
    qz = F.col(quizzes_col) if isinstance(quizzes_col, str) else quizzes_col
    return F.when(qz > 0, att / qz).otherwise(0.0).cast("double")


def calculate_academic_score(
    internal_col: str | Column = "internal_marks",
    midterm_col: str | Column = "midterm_marks",
    endterm_col: str | Column = "endterm_marks",
) -> Column:
    """Compute unweighted mean academic score across three assessment components.

    Formula: (internal + midterm + endterm) / 3.0

    Args:
        internal_col: Column or column name for internal marks.
        midterm_col: Column or column name for midterm marks.
        endterm_col: Column or column name for endterm marks.

    Returns:
        PySpark Column representing composite academic score [0.0, 100.0].
    """
    inter = F.col(internal_col) if isinstance(internal_col, str) else internal_col
    mid = F.col(midterm_col) if isinstance(midterm_col, str) else midterm_col
    end = F.col(endterm_col) if isinstance(endterm_col, str) else endterm_col
    return ((inter + mid + end) / 3.0).cast("double")
