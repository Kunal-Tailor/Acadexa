"""End-to-end MVP pipeline integration test (Task 10.1, rules.md §29).

Covers the complete development-scale vertical slice on a small fixture dataset:

```text
Generator
→ Parquet (full LMS) + generated core JSON + manifests
→ Spark J1 → J2 → J3 → J4/J5/J6 → J7
→ gold collections (Parquet) + pipeline run manifest
```

Plus a MongoDB serving-layer round-trip (Generator → MongoDB) that is skipped
when MongoDB is not reachable, per the established test convention.

Uses only a tiny deterministic fixture (12 students). No full-scale data,
no large driver-side collect, no ground-truth recovery (Task 10.2) and no
risk-boundary validation (Task 10.3).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from acadexa.database import (
    MongoDBConfig,
    check_connection,
    close_mongo_client,
    drop_managed_collections,
    get_database,
    get_mongo_client,
    init_database,
    load_core_academic_data,
)
from acadexa.generator.lms_events import read_lms_events_from_parquet
from acadexa.generator.manifests import load_generation_manifest
from acadexa.generator.orchestrator import generate_dataset
from acadexa.processing.pipeline import PipelineConfig, run_pipeline
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)
from acadexa.validation import validate_gold_dataframe


MVP_SEED = 42
MVP_TARGET_STUDENTS = 12


def _build_mvp_pipeline_config(data_dir: Path) -> PipelineConfig:
    """Build an isolated parquet-only PipelineConfig rooted at ``data_dir``."""
    return PipelineConfig(
        data_dir=data_dir,
        raw_data_dir=data_dir / "generated",
        raw_lms_parquet_path=data_dir / "raw" / "lms_events",
        cleaned_data_dir=data_dir / "cleaned",
        processed_data_dir=data_dir / "processed",
        gold_data_dir=data_dir / "gold",
        manifests_dir=data_dir / "manifests",
        analytics_dir=data_dir / "analytics",
        generation_manifest_path=data_dir / "manifests" / "generation_manifest.json",
        injection_manifest_path=data_dir / "manifests" / "injection_manifest.json",
        pipeline_manifest_path=data_dir / "manifests" / "pipeline_run_manifest.json",
        publish_to_mongo=False,
        save_parquet=True,
        validate_gold=True,
        fail_on_validation_error=True,
        seed=MVP_SEED,
        run_id="mvp_10_1_test_run",
        spark_runtime_config=SparkRuntimeConfig(
            app_name="AcadexaMVP10_1",
            master="local[2]",
            driver_memory="1g",
            shuffle_partitions=2,
            default_parallelism=2,
            ui_enabled=False,
        ),
    )


def test_mvp_generation_to_gold_parquet_end_to_end(tmp_path: Path) -> None:
    """Verify generation → Parquet → Spark → gold collections on a tiny dataset."""
    # --- Stage 1: Generate ---
    result = generate_dataset(
        seed=MVP_SEED,
        target_students=MVP_TARGET_STUDENTS,
        data_dir=tmp_path,
        chunk_size=500,
        inject_issues=True,
        min_injections=1,
    )

    assert result.actual_counts["students"] == MVP_TARGET_STUDENTS
    assert result.actual_counts["courses"] > 0
    assert result.actual_counts["academic_records"] > 0
    assert result.actual_counts["attendance"] > 0
    assert result.actual_counts["coursework"] > 0
    assert result.actual_counts["lms_events"] > 0

    # --- Stage 2: Land (Parquet + generated JSON + manifests) ---
    for name in ("students", "courses", "academic_records", "attendance", "coursework"):
        generated_file = tmp_path / "generated" / f"{name}.json"
        assert generated_file.exists()
        records = json.loads(generated_file.read_text(encoding="utf-8"))
        assert len(records) == result.actual_counts[name]

    lms_parquet_path = tmp_path / "raw" / "lms_events"
    assert lms_parquet_path.exists()
    lms_table = read_lms_events_from_parquet(lms_parquet_path)
    assert len(lms_table) == result.actual_counts["lms_events"]

    generation_manifest = load_generation_manifest(
        tmp_path / "manifests" / "generation_manifest.json"
    )
    assert generation_manifest.seed == MVP_SEED
    assert generation_manifest.actual_counts == result.actual_counts
    assert (tmp_path / "manifests" / "injection_manifest.json").exists()
    assert (tmp_path / "manifests" / "ground_truth_registry.json").exists()

    # --- Stage 3+4: Process + Analyze + Publish (Spark J1 → J7) ---
    cfg = _build_mvp_pipeline_config(tmp_path)
    pipeline_result = run_pipeline(cfg)

    assert pipeline_result.success is True
    assert pipeline_result.metadata.status == "SUCCESS"
    assert pipeline_result.metadata.seed == MVP_SEED
    for stage_id in ("J1", "J2", "J3", "J4", "J5", "J6", "J7"):
        assert stage_id in pipeline_result.metadata.stage_outcomes
        assert pipeline_result.metadata.stage_outcomes[stage_id].status == "SUCCESS"

    pipeline_manifest_path = tmp_path / "manifests" / "pipeline_run_manifest.json"
    assert pipeline_manifest_path.exists()
    manifest_data = json.loads(pipeline_manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["status"] == "SUCCESS"
    assert manifest_data["seed"] == MVP_SEED

    # --- Stage 5: Serve (gold Parquet validation) ---
    for collection in (
        "student_features",
        "course_metrics",
        "school_summary",
        "risk_indicators",
    ):
        assert (tmp_path / "gold" / collection).exists(), (
            f"Gold parquet missing for {collection}"
        )

    spark = get_or_create_spark_session(
        SparkRuntimeConfig(
            app_name="AcadexaMVP10_1Validate",
            master="local[2]",
            shuffle_partitions=2,
            ui_enabled=False,
        )
    )
    try:
        for collection in (
            "student_features",
            "course_metrics",
            "school_summary",
            "risk_indicators",
        ):
            df = spark.read.parquet(str(tmp_path / "gold" / collection))
            validation = validate_gold_dataframe(df, collection)
            assert validation.is_valid is True, (
                f"Gold collection {collection} failed validation: {validation.errors}"
            )
            assert validation.row_count > 0
            assert validation.grain_unique is True
    finally:
        stop_spark_session(spark)

    # Gold validation summary recorded in the pipeline manifest.
    gold_summary = manifest_data.get("gold_validation_summary", {})
    assert set(gold_summary.keys()) == {
        "student_features",
        "course_metrics",
        "school_summary",
        "risk_indicators",
    }
    for summary in gold_summary.values():
        assert summary["is_valid"] is True


def test_mvp_generator_to_mongodb_core_load(tmp_path: Path) -> None:
    """Verify Generator → MongoDB core-collection loading against the manifest."""
    mongo_cfg = MongoDBConfig(database="test_acadexa_mvp_10_1")
    if not check_connection(config=mongo_cfg):
        pytest.skip("MongoDB is not reachable in current environment")

    generate_dataset(
        seed=MVP_SEED,
        target_students=6,
        data_dir=tmp_path,
        chunk_size=500,
        inject_issues=True,
        min_injections=1,
    )

    client = get_mongo_client(mongo_cfg)
    try:
        db = get_database(mongo_cfg, client=client)
        init_database(db, drop_existing=True)

        load_result = load_core_academic_data(
            database=db,
            data_dir=tmp_path / "generated",
            manifest_path=tmp_path / "manifests" / "generation_manifest.json",
            clear_existing=True,
            strict_validation=True,
        )

        assert load_result.all_validated is True
        manifest_counts = json.loads(
            (tmp_path / "manifests" / "generation_manifest.json").read_text(
                encoding="utf-8"
            )
        )["actual_counts"]
        for collection in (
            "students",
            "courses",
            "academic_records",
            "attendance",
            "coursework",
        ):
            assert load_result.collections[collection].validated is True
            assert (
                load_result.collections[collection].actual_db_count
                == manifest_counts[collection]
            )
            assert db[collection].count_documents({}) == manifest_counts[collection]
    finally:
        try:
            db = get_database(mongo_cfg, client=client)
            drop_managed_collections(db)
            client.drop_database("test_acadexa_mvp_10_1")
        finally:
            close_mongo_client(client)
