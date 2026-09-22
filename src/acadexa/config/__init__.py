"""Configuration layer: loading, and validating project configuration files."""

from acadexa.config.loader import (
    CONFIG_ROOT,
    PROJECT_ROOT,
    config_path,
    env,
    load_config_file,
    load_environment,
)
from acadexa.config.validation import (
    ConfigurationError,
    validate_academic_periods,
    validate_courses,
    validate_generator,
    validate_hierarchy,
    validate_project_config,
    validate_risk,
)

__all__ = [
    "CONFIG_ROOT",
    "PROJECT_ROOT",
    "ConfigurationError",
    "config_path",
    "env",
    "load_config_file",
    "load_environment",
    "validate_academic_periods",
    "validate_courses",
    "validate_generator",
    "validate_hierarchy",
    "validate_project_config",
    "validate_risk",
]
