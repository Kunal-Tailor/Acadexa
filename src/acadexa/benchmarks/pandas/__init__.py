"""pandas benchmark workloads (Phase 13, architecture.md §20)."""

from acadexa.benchmarks.pandas.weekly_engagement import (
    aggregate_weekly_engagement,
    load_lms_events_frame,
    run_weekly_engagement_pandas,
)

__all__ = [
    "aggregate_weekly_engagement",
    "load_lms_events_frame",
    "run_weekly_engagement_pandas",
]
