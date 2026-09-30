"""Feature-table join benchmark using pandas (Task 13.5, F-F03).

Implements the ``feature_table_join`` workload where it is feasible:
read cleaned domain Parquet datasets, aggregate lightly to student ×
course × semester grain, outer-join the four domains and fill missing
numerics — the join-focused subset of Spark J3 (per-domain metric depth
beyond the join is J3's job, not this benchmark's). Semester attribution
for coursework mirrors J3 (due-date mapped through the canonical
semester bounds). Not a claim about which engine is superior — the
harness records the measured outcome either way.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from acadexa.benchmarks.runner import (
    ENGINE_PANDAS,
    BenchmarkResult,
    run_benchmark,
)
from acadexa.processing.jobs.event_aggregation import SEMESTER_BOUNDS

logger = logging.getLogger(__name__)

WORKLOAD_ID: str = "feature_table_join"
JOIN_KEYS: tuple[str, str, str] = ("student_id", "course_id", "semester_id")

NUMERIC_FILL_ZERO: tuple[str, ...] = (
    "total_marks",
    "classes_conducted",
    "classes_attended",
    "total_coursework",
    "total_submissions",
    "late_submissions",
    "lms_total_events",
)


def _norm_ids(
    frame: pd.DataFrame, keys: tuple[str, ...] = JOIN_KEYS
) -> pd.DataFrame:
    """Trim and upper-case join keys (J3-equivalent normalization)."""
    frame = frame.copy()
    for key in keys:
        frame[key] = frame[key].astype(str).str.strip().str.upper()
    return frame


def _semester_from_date(dates: pd.Series) -> pd.Series:
    """Map calendar dates to semester ids through canonical bounds."""
    parsed = pd.to_datetime(dates, errors="coerce").dt.date
    result = pd.Series("UNKNOWN", index=parsed.index)
    for sem_id, start, end in SEMESTER_BOUNDS:
        mask = (
            parsed.notna()
            & (parsed >= pd.to_datetime(start).date())
            & (parsed <= pd.to_datetime(end).date())
        )
        result = result.where(~mask, sem_id)
    return result


def aggregate_academic(academic: pd.DataFrame) -> pd.DataFrame:
    """Academic rows with total marks at join grain (already grained)."""
    frame = _norm_ids(academic)
    for column in ("internal_marks", "midterm_marks", "endterm_marks"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    frame["total_marks"] = (
        frame["internal_marks"] + frame["midterm_marks"] + frame["endterm_marks"]
    )
    return frame[[*JOIN_KEYS, "total_marks"]]


def aggregate_attendance(attendance: pd.DataFrame) -> pd.DataFrame:
    """Sum conducted/attended classes at join grain."""
    frame = _norm_ids(attendance)
    frame["classes_conducted"] = pd.to_numeric(
        frame["classes_conducted"], errors="coerce"
    ).fillna(0).astype(int)
    frame["classes_attended"] = pd.to_numeric(
        frame["classes_attended"], errors="coerce"
    ).fillna(0).astype(int)
    return (
        frame.groupby(list(JOIN_KEYS), as_index=False, sort=True)
        .agg(classes_conducted=("classes_conducted", "sum"),
             classes_attended=("classes_attended", "sum"))
    )


def aggregate_coursework(coursework: pd.DataFrame) -> pd.DataFrame:
    """Count items/submissions/late at join grain (semester from due date)."""
    frame = _norm_ids(coursework, keys=("student_id", "course_id"))
    if "semester_id" in frame.columns:
        frame["semester_id"] = (
            frame["semester_id"].astype(str).str.strip().str.upper()
        )
    else:
        frame["semester_id"] = _semester_from_date(frame["due_date"])
    status = frame["status"].astype(str)
    frame["is_submission"] = status.isin(["ON_TIME", "LATE"]).astype(int)
    frame["is_late"] = (status == "LATE").astype(int)
    return (
        frame.groupby(list(JOIN_KEYS), as_index=False, sort=True)
        .agg(total_coursework=("item_id", "size"),
             total_submissions=("is_submission", "sum"),
             late_submissions=("is_late", "sum"))
    )


def aggregate_lms_weekly(lms_weekly: pd.DataFrame) -> pd.DataFrame:
    """Sum weekly LMS events up to join grain."""
    frame = _norm_ids(lms_weekly)
    frame["total_events"] = pd.to_numeric(
        frame["total_events"], errors="coerce"
    ).fillna(0).astype(int)
    grouped = (
        frame.groupby(list(JOIN_KEYS), as_index=False, sort=True)
        .agg(lms_total_events=("total_events", "sum"))
    )
    return grouped


def join_feature_table(
    academic: pd.DataFrame,
    attendance: pd.DataFrame,
    coursework: pd.DataFrame,
    lms_weekly: pd.DataFrame,
) -> pd.DataFrame:
    """Outer-join the four domain summaries at join grain (J3 join subset).

    Missing domain records fill numerics with zero; the union spine keeps
    keys present in any single domain.
    """
    acad = aggregate_academic(academic)
    att = aggregate_attendance(attendance)
    cwk = aggregate_coursework(coursework)
    lms = aggregate_lms_weekly(lms_weekly)

    spine = pd.concat(
        [df[list(JOIN_KEYS)] for df in (acad, att, cwk, lms)], ignore_index=True
    ).drop_duplicates()
    joined = spine.merge(acad, on=list(JOIN_KEYS), how="left")
    for summary in (att, cwk, lms):
        joined = joined.merge(summary, on=list(JOIN_KEYS), how="left")
    for column in NUMERIC_FILL_ZERO:
        if column in joined.columns:
            joined[column] = joined[column].fillna(0)
    return joined.sort_values(list(JOIN_KEYS)).reset_index(drop=True)


def load_domain_frames(base_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Read the four cleaned domain datasets from ``base_dir``."""
    base = Path(base_dir)
    names = ("academic_records", "attendance", "coursework", "lms_weekly_engagement")
    frames = {}
    for name in names:
        target = base / name
        if not target.exists():
            raise FileNotFoundError(f"Domain dataset not found: {target}")
        frames[name] = pd.read_parquet(target)
    return frames


def run_feature_table_join_pandas(
    base_dir: str | Path,
    *,
    measure_memory: bool = True,
    extra: dict[str, Any] | None = None,
) -> BenchmarkResult:
    """Run the pandas feature-table join workload and record the result.

    The timed workload covers Parquet reads plus aggregation and join;
    each engine implementation includes its own read path, documented in
    the workload definition for comparability.
    """

    def _workload() -> tuple[int, int]:
        frames = load_domain_frames(base_dir)
        joined = join_feature_table(
            frames["academic_records"],
            frames["attendance"],
            frames["coursework"],
            frames["lms_weekly_engagement"],
        )
        return sum(len(frames[name]) for name in frames), len(joined)

    return run_benchmark(
        WORKLOAD_ID,
        ENGINE_PANDAS,
        _workload,
        measure_memory=measure_memory,
        extra={
            "base_dir": str(base_dir),
            "join_semantics": "outer",
            "collections": "academic_records+attendance+coursework+lms_weekly",
            **(extra or {}),
        },
    )
