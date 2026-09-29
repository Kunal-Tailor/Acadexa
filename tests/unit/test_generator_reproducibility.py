"""Generator reproducibility validation (Task 10.4, rules.md §8.2, §8.5).

Runs the same development configuration/seed twice into isolated
directories and compares deterministic outputs and manifest
characteristics. Volatile fields (timestamps, durations, disk usage,
absolute output paths) are excluded from comparison; everything that
defines the dataset must match exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

from acadexa.generator.lms_events import read_lms_events_from_parquet
from acadexa.generator.orchestrator import generate_dataset

REPRO_SEED = 42
REPRO_TARGET_STUDENTS = 6

_CORE_COLLECTIONS = (
    "students",
    "courses",
    "academic_records",
    "attendance",
    "coursework",
)

# Manifest keys that vary run to run and must be excluded from comparison.
_VOLATILE_GENERATION_KEYS = {
    "generated_at",
    "generation_duration_sec",
    "disk_usage_bytes",
    "output_files",
    "injection_manifest_path",
    "metadata",
}
_VOLATILE_GROUND_TRUTH_KEYS = {"generation_timestamp"}


def _load_json(path: Path) -> dict:
    """Load a JSON object from ``path``."""
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_list(path: Path) -> list:
    """Load a JSON list from ``path``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list), f"Expected JSON list in {path}"
    return data


def _sorted_event_rows(table) -> list[str]:
    """Serialize LMS event rows deterministically for comparison."""
    return sorted(json.dumps(row, sort_keys=True, default=str) for row in table.to_pylist())


def test_same_seed_same_config_is_fully_reproducible(tmp_path: Path) -> None:
    """Same seed/config twice must yield identical datasets and manifests."""
    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"

    result1 = generate_dataset(
        seed=REPRO_SEED,
        target_students=REPRO_TARGET_STUDENTS,
        data_dir=run1_dir,
        chunk_size=500,
        min_injections=1,
    )
    result2 = generate_dataset(
        seed=REPRO_SEED,
        target_students=REPRO_TARGET_STUDENTS,
        data_dir=run2_dir,
        chunk_size=500,
        min_injections=1,
    )

    # 1. Run-level counts match.
    assert result1.actual_counts == result2.actual_counts
    assert result1.actual_counts["students"] == REPRO_TARGET_STUDENTS

    # 2. Core collection payloads match exactly.
    for name in _CORE_COLLECTIONS:
        records1 = _load_json_list(run1_dir / "generated" / f"{name}.json")
        records2 = _load_json_list(run2_dir / "generated" / f"{name}.json")
        assert len(records1) == result1.actual_counts[name]
        assert records1 == records2, f"Non-deterministic output in {name}.json"

    # 3. LMS Parquet event payloads match exactly (row count + content).
    table1 = read_lms_events_from_parquet(run1_dir / "raw" / "lms_events")
    table2 = read_lms_events_from_parquet(run2_dir / "raw" / "lms_events")
    assert len(table1) == result1.actual_counts["lms_events"]
    assert len(table2) == result2.actual_counts["lms_events"]
    assert table1.schema == table2.schema
    assert _sorted_event_rows(table1) == _sorted_event_rows(table2)

    # 4. Ground-truth registry characteristics match (excluding timestamp).
    gt1 = _load_json(run1_dir / "manifests" / "ground_truth_registry.json")
    gt2 = _load_json(run2_dir / "manifests" / "ground_truth_registry.json")
    for key in _VOLATILE_GROUND_TRUTH_KEYS:
        gt1.pop(key, None)
        gt2.pop(key, None)
    assert gt1 == gt2
    assert gt1["seed"] == REPRO_SEED
    assert len(gt1["decliner_flags"]) == REPRO_TARGET_STUDENTS

    # 5. Generation manifest deterministic characteristics match.
    gen1 = _load_json(run1_dir / "manifests" / "generation_manifest.json")
    gen2 = _load_json(run2_dir / "manifests" / "generation_manifest.json")
    for key in _VOLATILE_GENERATION_KEYS:
        gen1.pop(key, None)
        gen2.pop(key, None)
    assert gen1 == gen2
    assert gen1["seed"] == REPRO_SEED
    assert gen1["actual_counts"] == result1.actual_counts

    # 6. Injection manifest characteristics match exactly (excluding timestamp).
    inj1 = _load_json(run1_dir / "manifests" / "injection_manifest.json")
    inj2 = _load_json(run2_dir / "manifests" / "injection_manifest.json")
    inj1.pop("generated_at", None)
    inj2.pop("generated_at", None)
    inj1.pop("metadata", None)
    inj2.pop("metadata", None)
    assert inj1 == inj2
    assert inj1["seed"] == REPRO_SEED
    assert inj1["total_injected"] == result1.injection_manifest.total_injected
