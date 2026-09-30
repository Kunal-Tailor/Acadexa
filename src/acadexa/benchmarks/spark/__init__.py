"""PySpark benchmark workloads (Phase 13, architecture.md §20)."""

from acadexa.benchmarks.spark.feature_join import (
    run_feature_table_join_spark,
)
from acadexa.benchmarks.spark.weekly_engagement import (
    run_weekly_engagement_spark,
)

__all__ = [
    "run_feature_table_join_spark",
    "run_weekly_engagement_spark",
]
