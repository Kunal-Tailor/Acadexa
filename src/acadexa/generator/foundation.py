"""Deterministic generator foundation: seed handling and run metadata.

Implements F-I01 (seeded generation) and the initialization-time part
of F-I02 / rules.md §8.5: every run records the seed, a configuration
snapshot, target volumes and the generation timestamp. Actual
generated counts and injected-issue counts are recorded later by the
generation/injection manifest (task 5.7).

Given the same validated configuration — and therefore the same seed —
two :class:`GeneratorRun` instances initialize with identical random
streams (rules.md §8.2).
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import numpy as np

from acadexa.config import validate_project_config

TARGET_VOLUME_KEYS = ("target_students", "target_courses", "target_lms_events")


class GeneratorError(ValueError):
    """Raised when generator run initialization fails."""


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _jsonable(value: Any) -> Any:
    """Convert configuration values into JSON-serializable forms."""
    if isinstance(value, dict):
        return {key: _jsonable(sub) for key, sub in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class GeneratorRunMetadata:
    """Generation metadata known when a run initializes (F-I02)."""

    seed: int
    generation_timestamp: datetime
    targets: dict[str, int]
    configuration: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation (dates as ISO-8601)."""
        return {
            "seed": self.seed,
            "generation_timestamp": self.generation_timestamp.isoformat(),
            "targets": dict(self.targets),
            "configuration": _jsonable(self.configuration),
        }


class GeneratorRun:
    """A reproducible generator run initialized from project configuration.

    Args:
        configs: The result of :func:`validate_project_config`. When
            omitted, the project configuration is loaded and validated.
    """

    def __init__(self, configs: dict[str, Any] | None = None) -> None:
        if configs is None:
            configs = validate_project_config()
        _check(
            isinstance(configs, dict),
            "configs must be a mapping from validate_project_config()",
        )
        _check("generator" in configs, "configs missing 'generator' configuration")
        generator_config = configs["generator"]
        _check(
            isinstance(generator_config, dict) and "generator" in generator_config,
            "generator configuration missing [generator] seed table",
        )
        seed_table = generator_config["generator"]
        _check(
            isinstance(seed_table, dict) and "seed" in seed_table,
            "generator configuration missing seed",
        )
        seed = seed_table["seed"]
        _check(
            isinstance(seed, int) and not isinstance(seed, bool),
            f"generator seed must be an integer, got {type(seed).__name__}",
        )

        scale = generator_config.get("scale", {})
        targets: dict[str, int] = {}
        for key in TARGET_VOLUME_KEYS:
            _check(key in scale, f"generator scale missing target volume '{key}'")
            targets[key] = scale[key]

        self.seed: int = seed
        self.configs: dict[str, Any] = copy.deepcopy(configs)
        self.metadata = GeneratorRunMetadata(
            seed=seed,
            generation_timestamp=datetime.now(timezone.utc),
            targets=targets,
            configuration=self.configs,
        )
        self._rng = np.random.default_rng(seed)

    @property
    def rng(self) -> np.random.Generator:
        """The run's primary seeded random generator."""
        return self._rng

    def child_rng(self, name: str) -> np.random.Generator:
        """Return a deterministic named sub-stream derived from the run seed.

        The same seed and name always produce the same stream, and
        distinct names produce independent streams, so subsystems can
        draw randomness without depending on call order. Derivation uses
        SHA-256 (never Python's per-process randomized ``hash()``).
        """
        _check(
            isinstance(name, str) and name != "",
            "child_rng name must be a non-empty string",
        )
        digest = hashlib.sha256(f"{self.seed}/{name}".encode("utf-8")).digest()
        return np.random.default_rng(int.from_bytes(digest, "big"))
