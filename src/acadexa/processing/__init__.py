"""Acadexa PySpark processing layer (Phase 7-9, rules.md §17-19).

Exports:
- :class:`SparkRuntimeConfig`: Configuration for PySpark local mode runtime.
- :class:`SparkRuntimeError`, :class:`SparkConfigError`: Processing error classes.
- :func:`ensure_spark_environment`: Sets up required local/Windows environment variables.
- :func:`get_or_create_spark_session`: Session factory for local Spark execution.
- :func:`stop_spark_session`: Clean shutdown helper.
- :func:`spark_session_context`: Context manager for deterministic Spark session lifecycles.
- :func:`verify_spark_runtime`: Lightweight health verification.
"""

from __future__ import annotations

from acadexa.processing.spark_session import (
    DEFAULT_SPARK_APP_NAME,
    DEFAULT_SPARK_DRIVER_MEMORY,
    DEFAULT_SPARK_MASTER,
    DEFAULT_SPARK_PARALLELISM,
    DEFAULT_SPARK_SHUFFLE_PARTITIONS,
    DEFAULT_SPARK_TIMEZONE,
    SparkConfigError,
    SparkRuntimeConfig,
    SparkRuntimeError,
    ensure_spark_environment,
    get_or_create_spark_session,
    spark_session_context,
    stop_spark_session,
    verify_spark_runtime,
)

__all__ = [
    "DEFAULT_SPARK_APP_NAME",
    "DEFAULT_SPARK_DRIVER_MEMORY",
    "DEFAULT_SPARK_MASTER",
    "DEFAULT_SPARK_PARALLELISM",
    "DEFAULT_SPARK_SHUFFLE_PARTITIONS",
    "DEFAULT_SPARK_TIMEZONE",
    "SparkConfigError",
    "SparkRuntimeConfig",
    "SparkRuntimeError",
    "ensure_spark_environment",
    "get_or_create_spark_session",
    "spark_session_context",
    "stop_spark_session",
    "verify_spark_runtime",
]
