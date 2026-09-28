"""Acadexa Spark pipeline processing jobs (Phase 7-9, rules.md §18).

Planned sequence:
- J1: Clean and Validate (clean_validate.py)
- J2: Event Aggregation (event_aggregation.py)
- J3: Feature Table (feature_table.py)
- J4: Correlation (correlation.py)
- J5: Trend Detection (trend_detection.py)
- J6: Risk Signals (risk_signals.py)
- J7: Publish Gold Data (publish_gold.py)
- J8: Benchmark (benchmarks)
"""

from __future__ import annotations

from acadexa.processing.jobs.clean_validate import (
    INJECTION_CATEGORIES,
    DatasetQualityMetrics,
    IssueMetric,
    J1Config,
    J1QualityReport,
    J1Result,
    clean_academic_records,
    clean_attendance,
    clean_courses,
    clean_coursework,
    clean_lms_events,
    clean_students,
    load_injection_manifest_counts,
    run_j1_clean_and_validate,
)
from acadexa.processing.jobs.event_aggregation import (
    APPROVED_ACTIVITY_CATEGORIES,
    J2Config,
    J2Result,
    aggregate_weekly_lms_events,
    run_j2_event_aggregation,
)
from acadexa.processing.jobs.feature_table import (
    J3Config,
    J3Result,
    aggregate_attendance_features,
    aggregate_coursework_features,
    aggregate_lms_features,
    build_integrated_student_features,
    build_student_semester_features,
    run_j3_feature_table,
)
from acadexa.processing.jobs.correlation import (
    J4Config,
    J4Result,
    run_j4_correlation,
)
from acadexa.processing.jobs.trend_detection import (
    J5Config,
    J5Result,
    run_j5_trend_detection,
)
from acadexa.processing.jobs.risk_signals import (
    J6Config,
    J6Result,
    run_j6_risk_signals,
)
from acadexa.processing.jobs.publish_gold import (
    J7Config,
    J7Result,
    build_course_metrics,
    build_school_summary,
    publish_course_metrics,
    publish_school_summary,
    publish_student_features,
    run_j7_publish_gold,
)

__all__ = [
    # J1 Clean and Validate
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
    # J2 Event Aggregation
    "APPROVED_ACTIVITY_CATEGORIES",
    "J2Config",
    "J2Result",
    "aggregate_weekly_lms_events",
    "run_j2_event_aggregation",
    # J3 Feature Table
    "J3Config",
    "J3Result",
    "aggregate_attendance_features",
    "aggregate_coursework_features",
    "aggregate_lms_features",
    "build_integrated_student_features",
    "build_student_semester_features",
    "run_j3_feature_table",
    # J4 Correlation
    "J4Config",
    "J4Result",
    "run_j4_correlation",
    # J5 Trend Detection
    "J5Config",
    "J5Result",
    "run_j5_trend_detection",
    # J6 Risk Signals
    "J6Config",
    "J6Result",
    "run_j6_risk_signals",
    # J7 Publish Gold Data
    "J7Config",
    "J7Result",
    "build_course_metrics",
    "build_school_summary",
    "publish_course_metrics",
    "publish_school_summary",
    "publish_student_features",
    "run_j7_publish_gold",
]
