"""Configuration loading: project config files and environment variables.

Loads non-secret configuration from files under ``config/`` and secrets/local
settings from environment variables and an optional ``.env`` file. Secrets are
never hard-coded; ``.env`` is git-ignored and only ``.env.example`` is tracked.
"""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = PROJECT_ROOT / "config"


def load_environment(env_file: Path | None = None, *, override: bool = False) -> None:
    """Load KEY=VALUE pairs from a ``.env`` file into the process environment.

    Existing environment variables are not overwritten unless ``override`` is
    True. Missing files are ignored so the loader is safe to call anywhere.
    """
    path = env_file if env_file is not None else PROJECT_ROOT / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value


def env(key: str, default: str | None = None, *, required: bool = False) -> str | None:
    """Return an environment variable value, optionally requiring it to exist."""
    value = os.environ.get(key, default)
    if required and value is None:
        raise KeyError(f"Required environment variable not set: {key}")
    return value


def config_path(*parts: str | Path) -> Path:
    """Resolve a path under the project ``config/`` directory."""
    return CONFIG_ROOT.joinpath(*[str(p) for p in parts])


def load_config_file(path: Path | str) -> dict[str, Any]:
    """Read a ``.toml`` or ``.json`` configuration file into a dict.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the format is unsupported or the root is not a table.
    """
    config_file = Path(path)
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    suffix = config_file.suffix.lower()
    if suffix == ".toml":
        with config_file.open("rb") as handle:
            data: Any = tomllib.load(handle)
    elif suffix == ".json":
        with config_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        raise ValueError(f"Unsupported configuration format: {config_file.suffix}")
    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be a table/object: {config_file}")
    return data
