"""Tests for deterministic seed handling and run metadata (task 4.1)."""

from __future__ import annotations

import copy
import json
from datetime import datetime

import numpy as np
import pytest

from acadexa.config import validate_project_config
from acadexa.generator import GeneratorError, GeneratorRun


@pytest.fixture()
def configs() -> dict:
    return validate_project_config()


# ── Deterministic initialization ────────────────────────


def test_same_configuration_initializes_reproducibly(configs: dict) -> None:
    first = GeneratorRun(configs)
    second = GeneratorRun(configs)
    assert first.seed == second.seed
    assert np.array_equal(first.rng.random(100), second.rng.random(100))


def test_different_seed_produces_different_stream(configs: dict) -> None:
    other = copy.deepcopy(configs)
    other["generator"]["generator"]["seed"] = configs["generator"]["generator"]["seed"] + 1
    assert not np.array_equal(
        GeneratorRun(configs).rng.random(50),
        GeneratorRun(other).rng.random(50),
    )


def test_run_reads_seed_from_configuration(configs: dict) -> None:
    run = GeneratorRun(configs)
    assert run.seed == configs["generator"]["generator"]["seed"]


def test_default_initialization_loads_project_config() -> None:
    run = GeneratorRun()
    assert run.seed == 42
    assert isinstance(run.rng, np.random.Generator)


# ── Named sub-streams ───────────────────────────────────


def test_child_rng_reproducible_per_name(configs: dict) -> None:
    first = GeneratorRun(configs)
    second = GeneratorRun(configs)
    assert np.array_equal(
        first.child_rng("students").random(20),
        second.child_rng("students").random(20),
    )


def test_child_rng_distinct_per_name(configs: dict) -> None:
    run = GeneratorRun(configs)
    assert not np.array_equal(
        run.child_rng("students").random(20),
        run.child_rng("events").random(20),
    )


def test_child_rng_rejects_empty_name(configs: dict) -> None:
    with pytest.raises(GeneratorError, match="non-empty"):
        GeneratorRun(configs).child_rng("")


# ── Run metadata ────────────────────────────────────────


def test_metadata_records_seed_and_targets(configs: dict) -> None:
    run = GeneratorRun(configs)
    assert run.metadata.seed == run.seed
    assert run.metadata.targets == {
        "target_students": 12000,
        "target_courses": 250,
        "target_lms_events": 70000000,
    }


def test_metadata_timestamp_is_aware_datetime(configs: dict) -> None:
    timestamp = GeneratorRun(configs).metadata.generation_timestamp
    assert isinstance(timestamp, datetime)
    assert timestamp.tzinfo is not None


def test_metadata_configuration_is_snapshot(configs: dict) -> None:
    run = GeneratorRun(configs)
    configs["generator"]["generator"]["seed"] = 999
    assert run.seed == 42
    assert run.metadata.configuration["generator"]["generator"]["seed"] == 42


def test_metadata_as_dict_is_json_serializable(configs: dict) -> None:
    run = GeneratorRun(configs)
    parsed = json.loads(json.dumps(run.metadata.as_dict()))
    assert parsed["seed"] == run.seed
    assert isinstance(parsed["generation_timestamp"], str)
    start_date = parsed["configuration"]["academic_periods"]["semesters"]["S1"]["start_date"]
    assert isinstance(start_date, str)


# ── Initialization failures ─────────────────────────────


def test_missing_seed_raises(configs: dict) -> None:
    broken = copy.deepcopy(configs)
    del broken["generator"]["generator"]["seed"]
    with pytest.raises(GeneratorError, match="missing seed"):
        GeneratorRun(broken)


def test_bool_seed_raises(configs: dict) -> None:
    broken = copy.deepcopy(configs)
    broken["generator"]["generator"]["seed"] = True
    with pytest.raises(GeneratorError, match="must be an integer"):
        GeneratorRun(broken)


def test_missing_target_volume_raises(configs: dict) -> None:
    broken = copy.deepcopy(configs)
    del broken["generator"]["scale"]["target_students"]
    with pytest.raises(GeneratorError, match="target volume 'target_students'"):
        GeneratorRun(broken)
