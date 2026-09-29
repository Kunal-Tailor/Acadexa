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
- J4 Correlation Analytics job
- J5 Temporal Trend Detection job
- J6 Risk Signals job
- J7 Gold Data Publication job
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
    J4Config,
    J4Result,
    J5Config,
    J5Result,
    J6Config,
    J6Result,
    J7Config,
    J7Result,
    aggregate_attendance_features,
    aggregate_coursework_features,
    aggregate_lms_features,
    aggregate_weekly_lms_events,
    build_course_metrics,
    build_integrated_student_features,
    build_school_summary,
    build_student_semester_features,
    clean_academic_records,
    clean_attendance,
    clean_courses,
    clean_coursework,
    clean_lms_events,
    clean_students,
    load_injection_manifest_counts,
    publish_course_metrics,
    publish_risk_indicators,
    publish_school_summary,
    publish_student_features,
    run_j1_clean_and_validate,
    run_j2_event_aggregation,
    run_j3_feature_table,
    run_j4_correlation,
    run_j5_trend_detection,
    run_j6_risk_signals,
    run_j7_publish_gold,
)
from acadexa.processing.pipeline import (
    ALL_STAGES,
    PipelineConfig,
    PipelineResult,
    PipelineRunMetadata,
    StageOutcome,
    run_pipeline,
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
    # J4 Correlation Analytics job
    "J4Config",
    "J4Result",
    "run_j4_correlation",
    # J5 Trend Detection job
    "J5Config",
    "J5Result",
    "run_j5_trend_detection",
    # J6 Risk Signals job
    "J6Config",
    "J6Result",
    "run_j6_risk_signals",
    # J7 Gold Data Publication job
    "J7Config",
    "J7Result",
    "build_course_metrics",
    "build_school_summary",
    "publish_course_metrics",
    "publish_risk_indicators",
    "publish_school_summary",
    "publish_student_features",
    "run_j7_publish_gold",
    # Pipeline Orchestration
    "ALL_STAGES",
    "PipelineConfig",
    "PipelineResult",
    "PipelineRunMetadata",
    "StageOutcome",
    "run_pipeline",
]
