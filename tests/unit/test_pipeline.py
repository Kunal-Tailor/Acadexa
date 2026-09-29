"""Unit tests for Spark pipeline orchestration and run metadata (Tasks 9.5 & 9.6, rules.md §18, §19)."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from acadexa.processing.pipeline import (
    ALL_STAGES,
    PipelineConfig,
    PipelineResult,
    PipelineRunMetadata,
    StageOutcome,
    run_pipeline,
)
import acadexa.processing.pipeline as pipeline_module
from scripts.run_pipeline import parse_args, print_summary


def test_pipeline_config_defaults_and_seed_resolution(tmp_path: Path) -> None:
    """Verify PipelineConfig defaults and seed resolution from generation manifest (Task 9.6)."""
    cfg = PipelineConfig()
    assert cfg.stages == ALL_STAGES
    assert cfg.publish_to_mongo is True
    assert cfg.save_parquet is True
    assert cfg.validate_gold is True

    # When seed is explicitly given
    cfg_explicit = PipelineConfig(seed=42)
    assert cfg_explicit.resolved_seed() == 42

    # When seed is read from generation manifest
    manifest_file = tmp_path / "generation_manifest.json"
    manifest_file.write_text(json.dumps({"seed": 2026, "target_students": 36}), encoding="utf-8")
    cfg_manifest = PipelineConfig(generation_manifest_path=manifest_file)
    assert cfg_manifest.resolved_seed() == 2026


def test_stage_outcome_serialization() -> None:
    """Verify StageOutcome serialization to dictionary (Task 9.6)."""
    outcome = StageOutcome(
        stage_id="J1",
        stage_name="Clean and Validate",
        status="SUCCESS",
        start_time="2026-09-29T10:00:00+00:00",
        end_time="2026-09-29T10:00:05+00:00",
        duration_sec=5.1234,
        output_counts={"students": 36, "attendance": 2160},
        details={"total_cleaned": 2196},
    )
    d = outcome.to_dict()
    assert d["stage_id"] == "J1"
    assert d["status"] == "SUCCESS"
    assert d["duration_sec"] == 5.123
    assert d["output_counts"]["students"] == 36
    assert d["error_message"] is None


def test_pipeline_run_metadata_lifecycle_and_manifest(tmp_path: Path) -> None:
    """Verify PipelineRunMetadata records stage outcomes and saves JSON manifest (Task 9.6)."""
    manifest_path = tmp_path / "pipeline_run_manifest.json"

    meta = PipelineRunMetadata(
        run_id="run_test_001",
        start_time=datetime.now(timezone.utc).isoformat(),
        seed=42,
        configuration={"data_dir": "data", "publish_to_mongo": True},
    )

    # Record stages
    st1 = StageOutcome(
        stage_id="J1",
        stage_name="Clean and Validate",
        status="SUCCESS",
        start_time=datetime.now(timezone.utc).isoformat(),
        end_time=datetime.now(timezone.utc).isoformat(),
        duration_sec=1.5,
        output_counts={"students": 36, "attendance": 2160},
    )
    st2 = StageOutcome(
        stage_id="J2",
        stage_name="Event Aggregation",
        status="SKIPPED",
        start_time=datetime.now(timezone.utc).isoformat(),
        end_time=datetime.now(timezone.utc).isoformat(),
        duration_sec=0.0,
    )
    meta.record_stage(st1)
    meta.record_stage(st2)

    meta.status = "SUCCESS"
    meta.end_time = datetime.now(timezone.utc).isoformat()
    meta.duration_sec = 2.5
    meta.gold_validation_summary = {
        "student_features": {"is_valid": True, "row_count": 36, "grain_unique": True}
    }

    # Save manifest
    saved_file = meta.save_manifest(manifest_path)
    assert saved_file.exists()

    # Read back and verify contract
    loaded = json.loads(saved_file.read_text(encoding="utf-8"))
    assert loaded["manifest_version"] == "1.0.0"
    assert loaded["run_id"] == "run_test_001"
    assert loaded["status"] == "SUCCESS"
    assert loaded["seed"] == 42
    assert "J1" in loaded["stage_outcomes"]
    assert loaded["stage_outcomes"]["J1"]["status"] == "SUCCESS"
    assert loaded["stage_outcomes"]["J2"]["status"] == "SKIPPED"
    assert loaded["output_counts"]["students"] == 36
    assert loaded["gold_validation_summary"]["student_features"]["is_valid"] is True


def test_run_pipeline_orchestrates_stages_and_records_manifest(tmp_path: Path) -> None:
    """Verify run_pipeline executes configured stages in order and saves manifest (Tasks 9.5 & 9.6)."""
    manifest_file = tmp_path / "manifests" / "pipeline_run_manifest.json"

    # Mock Spark session and jobs to verify orchestration without running full Spark cluster
    mock_spark = MagicMock()

    cfg = PipelineConfig(
        data_dir=tmp_path,
        pipeline_manifest_path=manifest_file,
        stages=("J1", "J2"),
        seed=100,
        publish_to_mongo=False,
    )

    mock_j1_res = MagicMock()
    mock_j1_res.counts = {"students": 10, "courses": 4}

    mock_j2_res = MagicMock()
    mock_j2_res.total_output_rows = 25
    mock_j2_res.total_input_events = 100
    mock_j2_res.student_count = 10
    mock_j2_res.course_count = 4

    with patch("acadexa.processing.pipeline.run_j1_clean_and_validate", return_value=mock_j1_res) as p_j1, \
         patch("acadexa.processing.pipeline.run_j2_event_aggregation", return_value=mock_j2_res) as p_j2:

        res = run_pipeline(cfg, spark=mock_spark)

        assert res.success is True
        assert res.metadata.status == "SUCCESS"
        assert res.metadata.seed == 100
        p_j1.assert_called_once()
        p_j2.assert_called_once()

        # Check recorded outcomes
        assert "J1" in res.metadata.stage_outcomes
        assert res.metadata.stage_outcomes["J1"].status == "SUCCESS"
        assert "J2" in res.metadata.stage_outcomes
        assert res.metadata.stage_outcomes["J2"].status == "SUCCESS"
        assert "J3" in res.metadata.stage_outcomes
        assert res.metadata.stage_outcomes["J3"].status == "SKIPPED"

        # Check output counts
        assert res.metadata.output_counts["students"] == 10
        assert res.metadata.output_counts["lms_weekly_engagement"] == 25

        # Check manifest was written
        assert manifest_file.exists()
        saved_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert saved_manifest["status"] == "SUCCESS"


def test_run_pipeline_records_failure_on_error(tmp_path: Path) -> None:
    """Verify run_pipeline records FAILED status and error in manifest when a stage errors (Task 9.6)."""
    manifest_file = tmp_path / "manifests" / "pipeline_run_manifest.json"
    mock_spark = MagicMock()

    cfg = PipelineConfig(
        data_dir=tmp_path,
        pipeline_manifest_path=manifest_file,
        stages=("J1", "J2"),
        seed=100,
        publish_to_mongo=False,
    )

    with patch(
        "acadexa.processing.pipeline.run_j1_clean_and_validate",
        side_effect=RuntimeError("Data quality injection failure"),
    ):
        with pytest.raises(RuntimeError, match="Data quality injection failure"):
            run_pipeline(cfg, spark=mock_spark)

        # Manifest must still be saved recording failure status
        assert manifest_file.exists()
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest_data["status"] == "FAILED"
        assert "Data quality injection failure" in manifest_data["error"]


def test_scripts_run_pipeline_cli_parsing_and_summary(tmp_path: Path, capsys) -> None:
    """Verify scripts/run_pipeline.py CLI argument parsing and summary output (Task 9.5)."""
    # 1. Test argument parsing
    args = parse_args([
        "--data-dir", str(tmp_path),
        "--stages", "J1", "J2", "J3",
        "--seed", "123",
        "--skip-mongo",
        "--skip-validation",
        "-q",
    ])
    assert args.data_dir == str(tmp_path)
    assert args.stages == ["J1", "J2", "J3"]
    assert args.seed == 123
    assert args.skip_mongo is True
    assert args.skip_validation is True
    assert args.quiet is True

    # 2. Test print_summary formatting
    meta = PipelineRunMetadata(
        run_id="run_cli_test",
        start_time="2026-09-29T10:00:00+00:00",
        end_time="2026-09-29T10:00:10+00:00",
        duration_sec=10.0,
        status="SUCCESS",
        seed=123,
        stage_outcomes={
            "J1": StageOutcome(
                stage_id="J1",
                stage_name="Clean and Validate",
                status="SUCCESS",
                start_time="2026-09-29T10:00:00+00:00",
                end_time="2026-09-29T10:00:02+00:00",
                duration_sec=2.0,
                output_counts={"students": 36},
            ),
            "J2": StageOutcome(
                stage_id="J2",
                stage_name="Event Aggregation",
                status="SKIPPED",
                start_time="2026-09-29T10:00:02+00:00",
                end_time="2026-09-29T10:00:02+00:00",
                duration_sec=0.0,
            ),
        },
        output_counts={"students": 36},
        gold_validation_summary={"student_features": {"is_valid": True, "row_count": 36, "grain_unique": True}},
        configuration={"data_dir": str(tmp_path)},
    )
    res = PipelineResult(metadata=meta, success=True)

    print_summary(res)
    captured = capsys.readouterr()
    assert "Acadexa End-to-End Spark Processing Pipeline Run Summary" in captured.out
    assert "run_cli_test" in captured.out
    assert "Clean and Validate" in captured.out
    assert "students: 36" in captured.out
    assert "SKIPPED" in captured.out
    assert "Gold Collections Validation" in captured.out


def test_no_large_collect_or_driver_iteration_in_pipeline() -> None:
    """Explicitly verify zero driver-side collect/toPandas in pipeline.py (rules.md §17.3)."""
    source_file = Path(inspect.getfile(pipeline_module))
    tree = ast.parse(source_file.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called_method = node.func.attr
            assert called_method not in (
                "collect",
                "toPandas",
                "toArray",
            ), f"Forbidden driver-side collect/toPandas call '{called_method}' found on line {node.lineno} in {source_file.name}"
