"""Unit tests for generation and injection manifests (task 5.7, F-I02, rules.md §8.5, §10.2)."""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.manifests import (
    DEFAULT_GENERATION_MANIFEST_PATH,
    DEFAULT_INJECTION_MANIFEST_PATH,
    DEFAULT_MANIFEST_DIR,
    GenerationManifest,
    InjectionManifest,
    build_generation_manifest,
    build_injection_manifest,
    build_manifests,
    load_generation_manifest,
    load_injection_manifest,
    save_generation_manifest,
    save_injection_manifest,
)
from acadexa.generator.quality_injection import (
    DEFAULT_INJECTION_RATES,
    InjectionReport,
    inject_data_quality,
)


@pytest.fixture
def run_fixture() -> GeneratorRun:
    """Fixture providing a seeded GeneratorRun."""
    return GeneratorRun()


def test_generation_manifest_construction_and_validation() -> None:
    """Test manual instantiation, validation, and serialization of GenerationManifest."""
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = GenerationManifest(
        seed=42,
        generated_at=now_iso,
        target_counts={"students": 1000, "courses": 40, "lms_events": 500000},
        actual_counts={"students": 1000, "courses": 40, "lms_events": 500120},
        configuration={"generator": {"seed": 42}},
        generation_duration_sec=12.5,
        disk_usage_bytes=1048576,
        output_files={"lms_events": "data/raw/lms_events.parquet"},
        injected_issues_summary={"duplicate_lms_events": 50},
        injection_manifest_path="data/manifests/injection_manifest.json",
        metadata={"scale": "dev"},
    )

    assert manifest.seed == 42
    assert manifest.target_counts["students"] == 1000
    assert manifest.actual_counts["lms_events"] == 500120
    assert manifest.generation_duration_sec == 12.5

    # Test to_dict and from_dict roundtrip
    data = manifest.to_dict()
    assert data["manifest_version"] == "1.0.0"
    assert data["manifest_type"] == "generation_manifest"
    assert data["seed"] == 42
    assert data["generation_duration_sec"] == 12.5
    assert data["disk_usage_bytes"] == 1048576

    reconstructed = GenerationManifest.from_dict(data)
    assert reconstructed.seed == manifest.seed
    assert reconstructed.generated_at == manifest.generated_at
    assert reconstructed.target_counts == manifest.target_counts
    assert reconstructed.actual_counts == manifest.actual_counts
    assert reconstructed.configuration == manifest.configuration
    assert reconstructed.generation_duration_sec == manifest.generation_duration_sec
    assert reconstructed.disk_usage_bytes == manifest.disk_usage_bytes


def test_generation_manifest_validation_failures() -> None:
    """Test validation errors for invalid GenerationManifest parameters."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # Invalid seed
    with pytest.raises(GeneratorError, match="seed must be an integer"):
        GenerationManifest(
            seed="not_an_int",  # type: ignore
            generated_at=now_iso,
            target_counts={},
            actual_counts={},
            configuration={},
        )

    # Boolean seed rejected
    with pytest.raises(GeneratorError, match="seed must be an integer"):
        GenerationManifest(
            seed=True,  # type: ignore
            generated_at=now_iso,
            target_counts={},
            actual_counts={},
            configuration={},
        )

    # Invalid timestamp
    with pytest.raises(GeneratorError, match="Invalid ISO-8601 timestamp"):
        GenerationManifest(
            seed=42,
            generated_at="invalid-date-string",
            target_counts={},
            actual_counts={},
            configuration={},
        )

    # Negative actual counts
    with pytest.raises(GeneratorError, match="non-negative integer"):
        GenerationManifest(
            seed=42,
            generated_at=now_iso,
            target_counts={"students": 100},
            actual_counts={"students": -5},
            configuration={},
        )

    # Non-dict configuration
    with pytest.raises(GeneratorError, match="configuration must be a dictionary"):
        GenerationManifest(
            seed=42,
            generated_at=now_iso,
            target_counts={},
            actual_counts={},
            configuration="invalid",  # type: ignore
        )

    # Negative duration
    with pytest.raises(GeneratorError, match="generation_duration_sec must be non-negative"):
        GenerationManifest(
            seed=42,
            generated_at=now_iso,
            target_counts={},
            actual_counts={},
            configuration={},
            generation_duration_sec=-2.0,
        )


def test_build_generation_manifest_with_run(run_fixture: GeneratorRun) -> None:
    """Test building GenerationManifest automatically from GeneratorRun."""
    actual_counts = {
        "students": 100,
        "courses": 10,
        "academic_records": 800,
        "attendance": 5000,
        "coursework": 1200,
        "lms_events": 25000,
    }

    report = InjectionReport(
        seed=run_fixture.seed,
        rates=dict(DEFAULT_INJECTION_RATES),
        issue_counts={"duplicate_lms_events": 10, "nulls_non_key": 5},
        collection_counts={"lms_events": {"duplicate_lms_events": 10, "nulls_non_key": 5}},
        total_injected=15,
        timestamp=datetime.now(timezone.utc),
    )

    manifest = build_generation_manifest(
        run=run_fixture,
        actual_counts=actual_counts,
        generation_duration_sec=3.45,
        disk_usage_bytes={"lms_events": 102400},
        output_files={"lms_events": "data/raw/lms_events.parquet"},
        injection_report=report,
        injection_manifest_path="data/manifests/injection_manifest.json",
        metadata={"scale": "dev"},
    )

    assert manifest.seed == run_fixture.seed
    assert manifest.target_counts == run_fixture.metadata.targets
    assert manifest.actual_counts == actual_counts
    assert manifest.generation_duration_sec == 3.45
    assert manifest.disk_usage_bytes == {"lms_events": 102400}
    assert manifest.injected_issues_summary == {"duplicate_lms_events": 10, "nulls_non_key": 5}
    assert manifest.injection_manifest_path == "data/manifests/injection_manifest.json"
    assert manifest.metadata == {"scale": "dev"}


def test_generation_manifest_save_and_load(tmp_path: Path, run_fixture: GeneratorRun) -> None:
    """Test saving and loading GenerationManifest from file."""
    manifest = build_generation_manifest(
        run=run_fixture,
        actual_counts={"students": 50},
        generation_duration_sec=1.2,
    )

    file_path = tmp_path / "custom_manifests" / "test_generation_manifest.json"
    saved_path = manifest.save(file_path)
    assert saved_path == file_path
    assert file_path.exists()

    # Load via class method
    loaded = GenerationManifest.load(file_path)
    assert loaded.seed == manifest.seed
    assert loaded.actual_counts == manifest.actual_counts
    assert loaded.generation_duration_sec == 1.2

    # Load via helper function
    loaded2 = load_generation_manifest(file_path)
    assert loaded2.seed == manifest.seed

    # Save via helper function
    file_path2 = tmp_path / "test_gen2.json"
    save_generation_manifest(manifest, file_path2)
    assert file_path2.exists()

    # Non-existent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        GenerationManifest.load(tmp_path / "does_not_exist.json")


def test_injection_manifest_construction_and_validation() -> None:
    """Test manual instantiation and validation of InjectionManifest."""
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = InjectionManifest(
        seed=101,
        generated_at=now_iso,
        total_injected=10,
        injected_issue_counts={
            "duplicate_lms_events": 4,
            "nulls_non_key": 3,
            "timestamp_inconsistencies": 1,
            "course_id_formatting": 1,
            "orphan_records": 1,
            "out_of_range_values": 0,
        },
        per_dataset_counts={
            "lms_events": {
                "duplicate_lms_events": 4,
                "nulls_non_key": 2,
                "timestamp_inconsistencies": 1,
                "course_id_formatting": 1,
                "orphan_records": 1,
                "out_of_range_values": 0,
            },
            "academic_records": {
                "nulls_non_key": 1,
            },
        },
        rates=dict(DEFAULT_INJECTION_RATES),
        baseline_counts={"lms_events": 1000, "academic_records": 200},
    )

    assert manifest.seed == 101
    assert manifest.total_injected == 10
    assert manifest.counts == manifest.injected_issue_counts
    assert manifest.counts["duplicate_lms_events"] == 4

    # Roundtrip to_dict and from_dict
    data = manifest.to_dict()
    assert data["manifest_version"] == "1.0.0"
    assert data["manifest_type"] == "injection_manifest"
    assert data["total_injected"] == 10
    assert data["baseline_counts"]["lms_events"] == 1000

    reconstructed = InjectionManifest.from_dict(data)
    assert reconstructed.seed == manifest.seed
    assert reconstructed.total_injected == manifest.total_injected
    assert reconstructed.injected_issue_counts == manifest.injected_issue_counts
    assert reconstructed.per_dataset_counts == manifest.per_dataset_counts
    assert reconstructed.rates == manifest.rates


def test_injection_manifest_validation_failures() -> None:
    """Test validation errors for invalid InjectionManifest parameters."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # Mismatch between total_injected and sum of injected_issue_counts
    with pytest.raises(GeneratorError, match="does not match sum of injected_issue_counts"):
        InjectionManifest(
            seed=42,
            generated_at=now_iso,
            total_injected=10,
            injected_issue_counts={"duplicate_lms_events": 5},  # sum is 5, not 10
            per_dataset_counts={"lms_events": {"duplicate_lms_events": 5}},
            rates={"duplicate_lms_events": 0.01},
        )

    # Mismatch between total_injected and sum across per_dataset_counts
    with pytest.raises(GeneratorError, match="does not match sum across per_dataset_counts"):
        InjectionManifest(
            seed=42,
            generated_at=now_iso,
            total_injected=5,
            injected_issue_counts={"duplicate_lms_events": 5},
            per_dataset_counts={"lms_events": {"duplicate_lms_events": 4}},  # sum is 4, not 5
            rates={"duplicate_lms_events": 0.01},
        )

    # Invalid rate > 1.0
    with pytest.raises(GeneratorError, match="Rate for 'duplicate_lms_events' must be float in"):
        InjectionManifest(
            seed=42,
            generated_at=now_iso,
            total_injected=0,
            injected_issue_counts={},
            per_dataset_counts={},
            rates={"duplicate_lms_events": 1.5},
        )

    # Negative count
    with pytest.raises(GeneratorError, match="non-negative integer"):
        InjectionManifest(
            seed=42,
            generated_at=now_iso,
            total_injected=0,
            injected_issue_counts={"duplicate_lms_events": -1},
            per_dataset_counts={},
            rates={},
        )


def test_build_injection_manifest_from_report(run_fixture: GeneratorRun) -> None:
    """Test building InjectionManifest directly from an InjectionReport."""
    sample_events = [
        {"event_id": f"EVT{i:04d}", "student_id": "STU001", "course_id": "CS101", "duration_sec": 100}
        for i in range(50)
    ]
    _, report = inject_data_quality(
        run=run_fixture,
        lms_events=sample_events,
        min_injections=1,
    )

    manifest = build_injection_manifest(
        run=run_fixture,
        report=report,
        baseline_counts={"lms_events": 50},
        metadata={"env": "test"},
    )

    assert manifest.seed == run_fixture.seed
    assert manifest.total_injected == report.total_injected
    assert manifest.injected_issue_counts == report.counts
    assert manifest.per_dataset_counts == report.per_dataset_counts
    assert manifest.rates == report.rates
    assert manifest.baseline_counts == {"lms_events": 50}
    assert manifest.metadata == {"env": "test"}


def test_injection_manifest_save_and_load(tmp_path: Path, run_fixture: GeneratorRun) -> None:
    """Test saving and loading InjectionManifest."""
    report = InjectionReport(
        seed=run_fixture.seed,
        rates=dict(DEFAULT_INJECTION_RATES),
        issue_counts={"duplicate_lms_events": 2, "nulls_non_key": 1},
        collection_counts={"lms_events": {"duplicate_lms_events": 2, "nulls_non_key": 1}},
        total_injected=3,
        timestamp=datetime.now(timezone.utc),
    )

    manifest = build_injection_manifest(run=run_fixture, report=report)
    file_path = tmp_path / "custom_inj_manifest.json"

    saved_path = manifest.save(file_path)
    assert saved_path == file_path
    assert file_path.exists()

    loaded = InjectionManifest.load(file_path)
    assert loaded.seed == manifest.seed
    assert loaded.total_injected == 3
    assert loaded.injected_issue_counts == report.counts

    # Standalone loader and saver
    file_path2 = tmp_path / "custom_inj_manifest_2.json"
    save_injection_manifest(manifest, file_path2)
    assert file_path2.exists()
    loaded2 = load_injection_manifest(file_path2)
    assert loaded2.total_injected == 3


def test_build_manifests_combined(tmp_path: Path, run_fixture: GeneratorRun) -> None:
    """Test combined build_manifests orchestration with optional saving."""
    report = InjectionReport(
        seed=run_fixture.seed,
        rates=dict(DEFAULT_INJECTION_RATES),
        issue_counts={"duplicate_lms_events": 5},
        collection_counts={"lms_events": {"duplicate_lms_events": 5}},
        total_injected=5,
        timestamp=datetime.now(timezone.utc),
    )

    gen_path = tmp_path / "manifests" / "generation_manifest.json"
    inj_path = tmp_path / "manifests" / "injection_manifest.json"

    gen_m, inj_m = build_manifests(
        run=run_fixture,
        actual_counts={"students": 100, "lms_events": 5000},
        injection_report=report,
        generation_duration_sec=2.1,
        save=True,
        generation_manifest_path=gen_path,
        injection_manifest_path=inj_path,
    )

    assert gen_m is not None
    assert inj_m is not None
    assert gen_path.exists()
    assert inj_path.exists()

    assert gen_m.actual_counts["students"] == 100
    assert gen_m.injected_issues_summary == {"duplicate_lms_events": 5}
    assert gen_m.injection_manifest_path == str(inj_path)
    assert inj_m.total_injected == 5

    # Verify loaded manifests match
    loaded_gen = load_generation_manifest(gen_path)
    loaded_inj = load_injection_manifest(inj_path)
    assert loaded_gen.seed == run_fixture.seed
    assert loaded_inj.seed == run_fixture.seed


def test_manifest_reproducibility(run_fixture: GeneratorRun) -> None:
    """Verify that two runs initialized with identical seeds produce identical manifest configuration."""
    run2 = GeneratorRun()
    assert run_fixture.seed == run2.seed

    m1 = build_generation_manifest(run_fixture, actual_counts={"students": 50})
    m2 = build_generation_manifest(run2, actual_counts={"students": 50})

    assert m1.seed == m2.seed
    assert m1.target_counts == m2.target_counts
    assert m1.configuration == m2.configuration
