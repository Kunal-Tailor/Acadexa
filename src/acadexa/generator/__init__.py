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
from acadexa.generator.students import generate_students
from acadexa.generator.university import (
    UniversityHierarchy,
    generate_university_hierarchy,
)

__all__ = [
    "DEFAULT_LMS_PARQUET_PATH",
    "GeneratorError",
    "GeneratorRun",
    "GeneratorRunMetadata",
    "LMS_PARQUET_SCHEMA",
    "UniversityHierarchy",
    "assign_course_difficulty",
    "generate_academic_records",
    "generate_attendance",
    "generate_behavioral_traits",
    "generate_coursework",
    "generate_decliner_flags",
    "generate_development_lms_parquet",
    "generate_lms_events",
    "generate_lms_events_chunks",
    "generate_students",
    "generate_university_hierarchy",
    "read_lms_events_from_parquet",
    "validate_lms_events_parquet",
    "write_lms_events_to_parquet",
]
