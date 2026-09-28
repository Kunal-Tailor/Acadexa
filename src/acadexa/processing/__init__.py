"""Acadexa PySpark processing layer (Phase 7-9, rules.md §17-19).

Exports:
- Spark session lifecycle:
  - :class:`SparkRuntimeConfig`: Configuration for PySpark local mode runtime.
  - :class:`SparkRuntimeError`, :class:`SparkConfigError`: Processing error classes.
  - :func:`ensure_spark_environment`: Sets up required local/Windows environment variables.
  - :func:`get_or_create_spark_session`: Session factory for local Spark execution.
  - :func:`stop_spark_session`: Clean shutdown helper.
  - :func:`spark_session_context`: Context manager for deterministic Spark session lifecycles.
  - :func:`verify_spark_runtime`: Lightweight health verification.
- MongoDB Spark integration:
  - :data:`DEFAULT_MONGO_SPARK_CONNECTOR`: Pinned connector dependency coordinate.
  - :data:`MONGO_SPARK_FORMAT`: Connector format string ("mongodb").
  - :func:`configure_spark_mongo_integration`: Configures Spark session with MongoDB connector.
  - :func:`get_or_create_mongo_spark_session`: Session factory with MongoDB connector.
  - :func:`read_mongo_collection`: Reads a MongoDB collection into a Spark DataFrame.
  - :func:`write_mongo_collection`: Writes a Spark DataFrame into a MongoDB collection.
  - :func:`verify_spark_mongo_read`: Verifies reading development collections into Spark.
- J1 Clean and Validate job
- J2 LMS Event Aggregation job
- J3 Integrated Student Feature Table job
"""

from __future__ import annotations

from acadexa.processing.mongo import (
    DEFAULT_MONGO_SPARK_CONNECTOR,
    MONGO_SPARK_FORMAT,
    build_collection_connection_uri,
    configure_spark_mongo_integration,
    get_or_create_mongo_spark_session,
    read_mongo_collection,
    verify_spark_mongo_read,
    write_mongo_collection,
)
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
from acadexa.processing.jobs import (
    APPROVED_ACTIVITY_CATEGORIES,
    INJECTION_CATEGORIES,
    DatasetQualityMetrics,
    IssueMetric,
    J1Config,
    J1QualityReport,
    J1Result,
    J2Config,
    J2Result,
    J3Config,
    J3Result,
    aggregate_attendance_features,
    aggregate_coursework_features,
    aggregate_lms_features,
    aggregate_weekly_lms_events,
    build_integrated_student_features,
    build_student_semester_features,
    clean_academic_records,
    clean_attendance,
    clean_courses,
    clean_coursework,
    clean_lms_events,
    clean_students,
    load_injection_manifest_counts,
    run_j1_clean_and_validate,
    run_j2_event_aggregation,
    run_j3_feature_table,
)

__all__ = [
    # Spark session lifecycle
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
    # MongoDB Spark integration
    "DEFAULT_MONGO_SPARK_CONNECTOR",
    "MONGO_SPARK_FORMAT",
    "build_collection_connection_uri",
    "configure_spark_mongo_integration",
    "get_or_create_mongo_spark_session",
    "read_mongo_collection",
    "verify_spark_mongo_read",
    "write_mongo_collection",
    # J1 Clean and Validate job
    "INJECTION_CATEGORIES",
    "DatasetQualityMetrics",
    "IssueMetric",
    "J1Config",
    "J1QualityReport",
    "J1Result",
    "clean_academic_records",
    "clean_attendance",
    "clean_courses",
    "clean_coursework",
    "clean_lms_events",
    "clean_students",
    "load_injection_manifest_counts",
    "run_j1_clean_and_validate",
    # J2 Event Aggregation job
    "APPROVED_ACTIVITY_CATEGORIES",
    "J2Config",
    "J2Result",
    "aggregate_weekly_lms_events",
    "run_j2_event_aggregation",
    # J3 Feature Table job
    "J3Config",
    "J3Result",
    "aggregate_attendance_features",
    "aggregate_coursework_features",
    "aggregate_lms_features",
    "build_integrated_student_features",
    "build_student_semester_features",
    "run_j3_feature_table",
]
