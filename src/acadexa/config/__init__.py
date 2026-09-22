"""Configuration layer: loading project config files and environment variables."""

from acadexa.config.loader import (
    CONFIG_ROOT,
    PROJECT_ROOT,
    config_path,
    env,
    load_config_file,
    load_environment,
)

__all__ = [
    "CONFIG_ROOT",
    "PROJECT_ROOT",
    "config_path",
    "env",
    "load_config_file",
    "load_environment",
]
