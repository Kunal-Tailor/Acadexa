"""Synthetic data generation: seeded, reproducible, configuration-driven."""

from acadexa.generator.academic_records import generate_academic_records
from acadexa.generator.courses import assign_course_difficulty
from acadexa.generator.foundation import (
    GeneratorError,
    GeneratorRun,
    GeneratorRunMetadata,
)
from acadexa.generator.students import generate_students
from acadexa.generator.university import (
    UniversityHierarchy,
    generate_university_hierarchy,
)

__all__ = [
    "GeneratorError",
    "GeneratorRun",
    "GeneratorRunMetadata",
    "UniversityHierarchy",
    "assign_course_difficulty",
    "generate_academic_records",
    "generate_students",
    "generate_university_hierarchy",
]
