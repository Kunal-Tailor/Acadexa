"""MongoDB benchmark workloads (Phase 13, architecture.md §20)."""

from acadexa.benchmarks.mongodb.weekly_engagement import (
    aggregate_weekly_engagement_mongo,
    build_weekly_engagement_pipeline,
    run_weekly_engagement_mongodb,
)

__all__ = [
    "aggregate_weekly_engagement_mongo",
    "build_weekly_engagement_pipeline",
    "run_weekly_engagement_mongodb",
]
