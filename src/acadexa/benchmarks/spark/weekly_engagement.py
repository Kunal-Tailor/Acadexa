"""Weekly LMS engagement benchmark using PySpark (Task 13.4, F-F03).

Implements the ``weekly_lms_engagement`` workload where it is feasible:
run the canonical Spark J2 aggregation (same code path as the pipeline,
not a reimplementation) over Parquet events and record the measured
outcome, directly comparable with the pandas and MongoDB engines. Not a
claim about which engine is superior — the harness records the measured
outcome either way.

Spark executes in worker JVMs, so tracemalloc peak memory is meaningless
here: memory measurement defaults off and the configured driver memory
is recorded in the result extras instead.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from acadexa.benchmarks.runner import (
    ENGINE_PYSPARK,
    BenchmarkResult,
    run_benchmark,
)
from acadexa.processing.jobs.event_aggregation import J2Config, run_j2_event_aggregation
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)

logger = logging.getLogger(__name__)

WORKLOAD_ID: str = "weekly_lms_engagement"

DEFAULT_SPARK_CONFIG = SparkRuntimeConfig(
    app_name="AcadexaBenchmarkSpark",
    master="local[2]",
    driver_memory="2g",
    shuffle_partitions=4,
    default_parallelism=4,
    ui_enabled=False,
)


def run_weekly_engagement_spark(
    input_path: str | Path,
    output_path: str | Path,
    *,
    spark: Any | None = None,
    spark_config: SparkRuntimeConfig | None = None,
    measure_memory: bool = False,
    extra: dict[str, Any] | None = None,
) -> BenchmarkResult:
    """Run the Spark J2 weekly-engagement workload and record the result.

    Args:
        input_path: Parquet input directory with LMS events.
        output_path: Parquet output directory for weekly summaries
            (benchmark scratch space, not the pipeline output).
        spark: Optional active SparkSession (used as-is, never stopped).
        spark_config: Session configuration when creating a session.
        measure_memory: Passed through to the harness (meaningless for
            JVM execution; the configured driver memory is recorded
            instead).
        extra: Additional metadata recorded on the result.
    """

    def _workload() -> tuple[int, int]:
        owns_session = spark is None
        session = spark if spark is not None else get_or_create_spark_session(
            spark_config or DEFAULT_SPARK_CONFIG
        )
        try:
            job_config = J2Config(
                input_path=Path(input_path),
                raw_fallback_path=Path(input_path),
                output_path=Path(output_path),
                save_parquet=True,
            )
            result = run_j2_event_aggregation(session, job_config)
            return result.total_input_events, result.total_output_rows
        finally:
            if owns_session:
                stop_spark_session(session)

    resolved_config = spark_config or DEFAULT_SPARK_CONFIG
    return run_benchmark(
        WORKLOAD_ID,
        ENGINE_PYSPARK,
        _workload,
        measure_memory=measure_memory,
        extra={
            "input_path": str(input_path),
            "output_path": str(output_path),
            "spark_master": resolved_config.master,
            "spark_driver_memory": resolved_config.driver_memory,
            **(extra or {}),
        },
    )
