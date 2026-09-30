"""pandas benchmark workloads (Phase 13, architecture.md §20)."""

from acadexa.benchmarks.pandas.feature_join import (
    aggregate_academic,
    aggregate_attendance,
    aggregate_coursework,
    aggregate_lms_weekly,
    join_feature_table,
    load_domain_frames,
    run_feature_table_join_pandas,
)
from acadexa.benchmarks.pandas.weekly_engagement import (
    aggregate_weekly_engagement,
    load_lms_events_frame,
    run_weekly_engagement_pandas,
)

__all__ = [
    "aggregate_academic",
    "aggregate_attendance",
    "aggregate_coursework",
    "aggregate_lms_weekly",
    "aggregate_weekly_engagement",
    "join_feature_table",
    "load_domain_frames",
    "load_lms_events_frame",
    "run_feature_table_join_pandas",
    "run_weekly_engagement_pandas",
]
