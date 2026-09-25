"""Unit tests for synthetic dataset generation orchestrator and CLI (task 5.8, F-B09, rules.md §8, §10)."""

import json
from pathlib import Path
import pytest

from acadexa.generator.lms_events import read_lms_events_from_parquet, validate_lms_events_parquet
from acadexa.generator.ground_truth import load_ground_truth_registry
from acadexa.generator.manifests import (
    load_generation_manifest,
    load_injection_manifest,
)
from acadexa.generator.orchestrator import configure_run_for_scale, generate_dataset
import scripts.generate_data as generate_data_script


def test_configure_run_for_scale() -> None:
    """Test scaling down target students and overriding seed."""
    run = configure_run_for_scale(seed=999, target_students=12)
    assert run.seed == 999
    assert run.metadata.seed == 999

    scale = run.configs["generator"]["scale"]
    assert scale["target_students"] == 12
    # 12 students across 6 schools = 2 per school
    assert sum(scale["school_population"].values()) == 12
    for school, count in scale["school_population"].items():
        assert count == 2


def test_generate_dataset_workflow(tmp_path: Path) -> None:
    """Test full execution of generate_dataset with small development cohort."""
    result = generate_dataset(
        target_students=12,
        data_dir=tmp_path,
        chunk_size=500,
        inject_issues=True,
        min_injections=1,
    )

    # 1. Check returned structure
    assert result.run.seed == 42
    assert result.actual_counts["students"] == 12
    assert result.actual_counts["courses"] > 0
    assert result.actual_counts["academic_records"] > 0
    assert result.actual_counts["attendance"] > 0
    assert result.actual_counts["coursework"] > 0
    assert result.actual_counts["lms_events"] > 0

    # 2. Check files on disk
    for name in ("students", "courses", "academic_records", "attendance", "coursework"):
        p = tmp_path / "generated" / f"{name}.json"
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert len(data) == result.actual_counts[name]

    # 3. Check Parquet LMS events
    parquet_path = tmp_path / "raw" / "lms_events"
    assert parquet_path.exists()
    tbl = read_lms_events_from_parquet(parquet_path)
    assert len(tbl) == result.actual_counts["lms_events"]
    assert "timestamp" in tbl.column_names
    assert "meta" in tbl.column_names
    assert "activity_type" in tbl.column_names

    # 4. Check Manifests
    gt_path = tmp_path / "manifests" / "ground_truth_registry.json"
    gen_path = tmp_path / "manifests" / "generation_manifest.json"
    inj_path = tmp_path / "manifests" / "injection_manifest.json"

    assert gt_path.exists()
    assert gen_path.exists()
    assert inj_path.exists()

    gt = load_ground_truth_registry(gt_path)
    assert gt.seed == 42
    assert len(gt.planted_relationships) == 5

    gen_m = load_generation_manifest(gen_path)
    assert gen_m.seed == 42
    assert gen_m.actual_counts == result.actual_counts

    inj_m = load_injection_manifest(inj_path)
    assert inj_m.seed == 42
    assert inj_m.total_injected > 0
    assert result.injection_manifest is not None
    assert inj_m.total_injected == result.injection_manifest.total_injected


def test_generate_dataset_without_quality_injection(tmp_path: Path) -> None:
    """Test generating dataset with quality injection disabled."""
    result = generate_dataset(
        target_students=6,
        data_dir=tmp_path,
        chunk_size=500,
        inject_issues=False,
    )

    assert result.injection_manifest is None
    assert not (tmp_path / "manifests" / "injection_manifest.json").exists()
    assert (tmp_path / "manifests" / "generation_manifest.json").exists()

    # Clean parquet should pass strict schema validation
    parquet_path = tmp_path / "raw" / "lms_events"
    val_report = validate_lms_events_parquet(parquet_path, sample_size=30)
    assert val_report["valid"] is True
    assert val_report["record_count"] == result.actual_counts["lms_events"]


def test_scripts_generate_data_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test running scripts/generate_data.py CLI entry point."""
    exit_code = generate_data_script.main(
        [
            "--target-students",
            "6",
            "--output-dir",
            str(tmp_path),
            "--chunk-size",
            "500",
            "--min-injections",
            "1",
        ]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Acadexa Synthetic Data Generator" in captured.out
    assert "Generated Datasets & Counts:" in captured.out
    assert "students" in captured.out
    assert "lms_events" in captured.out
    assert "Manifests & Metadata:" in captured.out

    # Files should exist
    assert (tmp_path / "generated" / "students.json").exists()
    assert (tmp_path / "manifests" / "generation_manifest.json").exists()


def test_scripts_generate_data_quiet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test running scripts/generate_data.py with --quiet."""
    exit_code = generate_data_script.main(
        [
            "--target-students",
            "6",
            "--output-dir",
            str(tmp_path),
            "-q",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == ""
