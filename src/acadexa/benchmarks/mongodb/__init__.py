"""MongoDB benchmark workloads (Phase 13, architecture.md §20)."""

from acadexa.benchmarks.mongodb.feature_join import (
    aggregate_feature_join_mongo,
    build_feature_join_pipeline,
    run_feature_table_join_mongodb,
)
from acadexa.benchmarks.mongodb.weekly_engagement import (
    aggregate_weekly_engagement_mongo,
    build_weekly_engagement_pipeline,
    run_weekly_engagement_mongodb,
)

__all__ = [
    "aggregate_feature_join_mongo",
    "aggregate_weekly_engagement_mongo",
    "build_feature_join_pipeline",
    "build_weekly_engagement_pipeline",
    "run_feature_table_join_mongodb",
    "run_weekly_engagement_mongodb",
]
