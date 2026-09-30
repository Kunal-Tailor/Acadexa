"""Weekly LMS engagement benchmark using pandas (Task 13.2, F-F03).

Implements the ``weekly_lms_engagement`` workload where it is feasible:
read LMS Parquet events and aggregate to weekly student-course summaries
with the same grain and metrics as Spark J2, so later MongoDB/Spark
implementations remain directly comparable. Not a claim about which
engine is superior — the harness records the measured outcome either way.

Category groupings and semester bounds are imported from the J2 job
module (canonical definitions) so the workloads cannot silently drift
apart.
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
from acadexa.processing.jobs.event_aggregation import (
    APPROVED_ACTIVITY_CATEGORIES,
    SEMESTER_BOUNDS,
)

logger = logging.getLogger(__name__)

WORKLOAD_ID: str = "weekly_lms_engagement"

GROUP_COLS: tuple[str, ...] = (
    "student_id",
    "course_id",
    "school",
    "semester_id",
    "week_start",
    "week_number",
)


def load_lms_events_frame(input_path: str | Path) -> pd.DataFrame:
    """Read LMS Parquet events into a pandas DataFrame."""
    target = Path(input_path)
    if not target.exists():
        raise FileNotFoundError(f"LMS events path not found: {target}")
    return pd.read_parquet(target)


def _flatten_identifiers(events: pd.DataFrame) -> pd.DataFrame:
    """Extract trimmed, upper-cased student/course/school identifiers."""
    frame = events.copy()
    if "meta" in frame.columns and frame["meta"].apply(lambda v: isinstance(v, dict)).any():
        meta = frame["meta"].apply(lambda v: v if isinstance(v, dict) else {})
        frame["student_id"] = meta.apply(lambda m: str(m.get("student_id", "")).strip().upper())
        frame["course_id"] = meta.apply(lambda m: str(m.get("course_id", "")).strip().upper())
        frame["school"] = meta.apply(lambda m: m.get("school") or "UNKNOWN")
    else:
        frame["student_id"] = frame["student_id"].astype(str).str.strip().str.upper()
        frame["course_id"] = frame["course_id"].astype(str).str.strip().str.upper()
        if "school" in frame.columns:
            frame["school"] = frame["school"].where(frame["school"].notna(), "UNKNOWN")
        else:
            frame["school"] = "UNKNOWN"
    return frame


def _derive_calendar_fields(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive event_date, Monday week_start, semester_id and week_number."""
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame["event_date"] = frame["timestamp"].dt.date
    frame["week_start"] = (
        frame["timestamp"].dt.normalize()
        - pd.to_timedelta(frame["timestamp"].dt.weekday, unit="D")
    ).dt.date
    frame["semester_id"] = "UNKNOWN"
    sem_start = frame["week_start"]
    for sem_id, start_date, _ in SEMESTER_BOUNDS:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(_).date()
        mask = (frame["week_start"] >= start) & (frame["week_start"] <= end)
        frame.loc[mask, "semester_id"] = sem_id
        sem_start = sem_start.where(~mask, start)
    frame["week_number"] = (
        (pd.to_datetime(frame["week_start"]) - pd.to_datetime(sem_start)).dt.days // 7 + 1
    ).astype(int)
    return frame


def aggregate_weekly_engagement(events: pd.DataFrame) -> pd.DataFrame:
    """Aggregate event-level LMS data into weekly summaries (J2-equivalent).

    Grain: student_id × course_id × school × semester_id × week_start ×
    week_number, with total events, positive-only durations, distinct
    active days, approved category roll-ups and per-type breakdowns.
    """
    if events.empty:
        return pd.DataFrame(
            columns=[*GROUP_COLS, "total_events", "total_duration_sec", "active_days"]
        )
    frame = _derive_calendar_fields(_flatten_identifiers(events))
    durations = pd.to_numeric(frame["duration_sec"], errors="coerce")
    frame["positive_duration"] = durations.where(durations > 0, 0.0)
    activity = frame["activity_type"].astype(str)
    categories = APPROVED_ACTIVITY_CATEGORIES
    frame["is_content"] = activity.isin(categories["content_views"]).astype(int)
    frame["is_assessment"] = activity.isin(categories["assessment_events"]).astype(int)
    frame["is_participation"] = activity.isin(categories["participation_events"]).astype(int)
    frame["is_access"] = activity.isin(categories["access_events"]).astype(int)
    frame["is_video"] = activity.isin(["VIDEO_VIEW", "VIDEO_COMPLETE"]).astype(int)
    frame["is_quiz"] = (activity == "QUIZ_ATTEMPT").astype(int)
    frame["is_aw_view"] = (activity == "ASSIGNMENT_VIEW").astype(int)
    frame["is_aw_submit"] = (activity == "ASSIGNMENT_SUBMISSION").astype(int)
    frame["is_forum"] = (activity == "FORUM_POST").astype(int)
    frame["is_login"] = (activity == "LOGIN").astype(int)

    grouped = frame.groupby(list(GROUP_COLS), as_index=False, sort=True)
    summary = grouped.agg(
        total_events=("activity_type", "size"),
        total_duration_sec=("positive_duration", "sum"),
        active_days=("event_date", "nunique"),
        content_views=("is_content", "sum"),
        assessment_events=("is_assessment", "sum"),
        participation_events=("is_participation", "sum"),
        access_events=("is_access", "sum"),
        video_views=("is_video", "sum"),
        quiz_attempts=("is_quiz", "sum"),
        assignment_views=("is_aw_view", "sum"),
        assignment_submissions=("is_aw_submit", "sum"),
        forum_posts=("is_forum", "sum"),
        logins=("is_login", "sum"),
    )
    summary["total_duration_sec"] = summary["total_duration_sec"].astype(float)
    return summary.sort_values(["student_id", "course_id", "week_start"]).reset_index(drop=True)


def run_weekly_engagement_pandas(
    input_path: str | Path,
    *,
    measure_memory: bool = True,
    extra: dict[str, Any] | None = None,
) -> BenchmarkResult:
    """Run the pandas weekly-engagement workload and record the result.

    The timed workload covers Parquet read plus aggregation; each engine
    implementation includes its own read path, documented in the workload
    definition for comparability.
    """

    def _workload() -> tuple[int, int]:
        events = load_lms_events_frame(input_path)
        summary = aggregate_weekly_engagement(events)
        return len(events), len(summary)

    return run_benchmark(
        WORKLOAD_ID,
        ENGINE_PANDAS,
        _workload,
        measure_memory=measure_memory,
        extra={"input_path": str(input_path), **(extra or {})},
    )
