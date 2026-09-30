"""Feature-table join benchmark using PySpark (Task 13.5, F-F03).

Implements the ``feature_table_join`` workload where it is practical by
running the canonical Spark J3 job (same code path as the pipeline, not
a reimplementation) over cleaned domain Parquet datasets with output to
benchmark scratch space. Not a claim about which engine is superior —
the harness records the measured outcome either way.

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
from acadexa.processing.jobs.feature_table import J3Config, run_j3_feature_table
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)

logger = logging.getLogger(__name__)

WORKLOAD_ID: str = "feature_table_join"

DEFAULT_SPARK_CONFIG = SparkRuntimeConfig(
    app_name="AcadexaBenchmarkSpark",
    master="local[2]",
    driver_memory="2g",
    shuffle_partitions=4,
    default_parallelism=4,
    ui_enabled=False,
)


def run_feature_table_join_spark(
    base_dir: str | Path,
    output_path: str | Path,
    *,
    spark: Any | None = None,
    spark_config: SparkRuntimeConfig | None = None,
    measure_memory: bool = False,
    extra: dict[str, Any] | None = None,
) -> BenchmarkResult:
    """Run the Spark J3 feature-table join workload and record the result.

    Args:
        base_dir: Directory holding the cleaned domain datasets
            (``academic_records``, ``attendance``, ``coursework``,
            ``lms_weekly_engagement``, plus optional ``courses`` and
            ``students`` as in the pipeline).
        output_path: Parquet output directory for the feature table
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
            base = Path(base_dir)
            job_config = J3Config(
                academic_records_path=base / "academic_records",
                attendance_path=base / "attendance",
                coursework_path=base / "coursework",
                lms_path=base / "lms_weekly_engagement",
                courses_path=base / "courses",
                students_path=base / "students",
                output_path=Path(output_path),
                student_rollup_path=None,
                save_parquet=True,
            )
            input_rows = sum(
                session.read.parquet(str(base / name)).count()
                for name in (
                    "academic_records",
                    "attendance",
                    "coursework",
                    "lms_weekly_engagement",
                )
            )
            result = run_j3_feature_table(session, job_config)
            return input_rows, result.total_features_rows
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
            "base_dir": str(base_dir),
            "output_path": str(output_path),
            "join_semantics": "outer",
            "collections": "academic_records+attendance+coursework+lms_weekly+hierarchy",
            "spark_master": resolved_config.master,
            "spark_driver_memory": resolved_config.driver_memory,
            **(extra or {}),
        },
    )
