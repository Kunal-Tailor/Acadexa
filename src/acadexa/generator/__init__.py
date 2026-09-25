"""Synthetic data generation: seeded, reproducible, configuration-driven."""

from acadexa.generator.academic_records import generate_academic_records
from acadexa.generator.attendance import generate_attendance
from acadexa.generator.behavioral_model import generate_behavioral_traits
from acadexa.generator.courses import assign_course_difficulty
from acadexa.generator.coursework import generate_coursework
from acadexa.generator.decliners import generate_decliner_flags
from acadexa.generator.foundation import (
    GeneratorError,
    GeneratorRun,
    GeneratorRunMetadata,
)
from acadexa.generator.ground_truth import (
    DECOY_RELATIONSHIP,
    DEFAULT_GROUND_TRUTH_PATH,
    PLANTED_RELATIONSHIPS,
    GroundTruthRegistry,
    generate_ground_truth_registry,
    load_ground_truth_registry,
)
from acadexa.generator.lms_events import (
    DEFAULT_LMS_PARQUET_PATH,
    LMS_PARQUET_SCHEMA,
    generate_development_lms_parquet,
    generate_lms_events,
    generate_lms_events_chunks,
    read_lms_events_from_parquet,
    validate_lms_events_parquet,
    write_lms_events_to_parquet,
)
from acadexa.generator.quality_injection import (
    DEFAULT_INJECTION_RATES,
    INJECTION_RATE_KEYS,
    InjectionReport,
    get_injection_rates,
    inject_course_id_formatting,
    inject_data_quality,
    inject_duplicate_lms_events,
    inject_nulls_non_key,
    inject_orphan_records,
    inject_out_of_range_values,
    inject_quality_issues_academic_records,
    inject_quality_issues_attendance,
    inject_quality_issues_coursework,
    inject_quality_issues_lms_events,
    inject_timestamp_inconsistencies,
)
from acadexa.generator.students import generate_students
from acadexa.generator.university import (
    UniversityHierarchy,
    generate_university_hierarchy,
)

__all__ = [
    "DECOY_RELATIONSHIP",
    "DEFAULT_GROUND_TRUTH_PATH",
    "DEFAULT_INJECTION_RATES",
    "DEFAULT_LMS_PARQUET_PATH",
    "GeneratorError",
    "GeneratorRun",
    "GeneratorRunMetadata",
    "GroundTruthRegistry",
    "INJECTION_RATE_KEYS",
    "InjectionReport",
    "LMS_PARQUET_SCHEMA",
    "PLANTED_RELATIONSHIPS",
    "UniversityHierarchy",
    "assign_course_difficulty",
    "generate_academic_records",
    "generate_attendance",
    "generate_behavioral_traits",
    "generate_coursework",
    "generate_decliner_flags",
    "generate_development_lms_parquet",
    "generate_ground_truth_registry",
    "generate_lms_events",
    "generate_lms_events_chunks",
    "generate_students",
    "generate_university_hierarchy",
    "get_injection_rates",
    "inject_course_id_formatting",
    "inject_data_quality",
    "inject_duplicate_lms_events",
    "inject_nulls_non_key",
    "inject_orphan_records",
    "inject_out_of_range_values",
    "inject_quality_issues_academic_records",
    "inject_quality_issues_attendance",
    "inject_quality_issues_coursework",
    "inject_quality_issues_lms_events",
    "inject_timestamp_inconsistencies",
    "load_ground_truth_registry",
    "read_lms_events_from_parquet",
    "validate_lms_events_parquet",
    "write_lms_events_to_parquet",
]
