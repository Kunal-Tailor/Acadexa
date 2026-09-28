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
]
