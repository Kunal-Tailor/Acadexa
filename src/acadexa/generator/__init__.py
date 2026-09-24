"""Synthetic data generation: seeded, reproducible, configuration-driven."""

from acadexa.generator.foundation import (
    GeneratorError,
    GeneratorRun,
    GeneratorRunMetadata,
)
from acadexa.generator.university import (
    UniversityHierarchy,
    generate_university_hierarchy,
)

__all__ = [
    "GeneratorError",
    "GeneratorRun",
    "GeneratorRunMetadata",
    "UniversityHierarchy",
    "generate_university_hierarchy",
]
