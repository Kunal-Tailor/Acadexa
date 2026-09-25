"""Tests for LMS event Parquet I/O and validation (task 5.4).

Verifies:
- Parquet schema alignment with canonical LMS_EVENTS_SCHEMA.
- Incremental chunked writing to single Parquet files and partitioned datasets.
- Clean read-back of Parquet tables and Python dicts.
- Validation of Parquet datasets against schema rules and identifier constraints.
- Development-scale dataset generation directly into Parquet landing storage.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    LMS_PARQUET_SCHEMA,
    generate_academic_records,
    generate_development_lms_parquet,
    generate_lms_events_chunks,
    generate_students,
    read_lms_events_from_parquet,
    validate_lms_events_parquet,
    write_lms_events_to_parquet,
)
from acadexa.validation import LMS_EVENTS_SCHEMA, SchemaError, validate_record


def _make_sample_events(count: int = 10) -> list[dict]:
    """Create a deterministic list of valid LMS event dictionaries."""
    events = []
    base_dt = datetime(2025, 9, 1, 9, 0, 0)
    for i in range(count):
        # Alternate dates between Sept 2025 and Oct 2025
        dt = datetime(2025, 9 if i % 2 == 0 else 10, (i % 25) + 1, 10 + (i % 8), i % 60)
        events.append(
            {
                "timestamp": dt,
                "meta": {
                    "student_id": f"STU{100000 + i:06d}",
                    "course_id": "CSE101",
                    "school": "CET",
                },
                "activity_type": "VIDEO_VIEW" if i % 2 == 0 else "LOGIN",
                "resource_id": f"R{100 + i}" if i % 2 == 0 else None,
                "duration_sec": 300 + i * 10 if i % 2 == 0 else None,
                "session_id": f"SES{2000000 + i:07d}",
            }
        )
    return events


def test_parquet_schema_definition() -> None:
    """Verify LMS_PARQUET_SCHEMA matches canonical fields, types, and nullability."""
    expected_fields = [
        "timestamp",
        "meta",
        "activity_type",
        "resource_id",
        "duration_sec",
        "session_id",
    ]
    assert LMS_PARQUET_SCHEMA.names == expected_fields

    # Check meta struct
    meta_field = LMS_PARQUET_SCHEMA.field("meta")
    assert pa.types.is_struct(meta_field.type)
    meta_subfields = {f.name: f.type for f in meta_field.type}
    assert meta_subfields == {
        "student_id": pa.string(),
        "course_id": pa.string(),
        "school": pa.string(),
    }

    # Check timestamp type
    assert pa.types.is_timestamp(LMS_PARQUET_SCHEMA.field("timestamp").type)

    # Check nullability contracts
    assert not LMS_PARQUET_SCHEMA.field("timestamp").nullable
    assert not LMS_PARQUET_SCHEMA.field("meta").nullable
    assert not LMS_PARQUET_SCHEMA.field("activity_type").nullable
    assert LMS_PARQUET_SCHEMA.field("resource_id").nullable
    assert LMS_PARQUET_SCHEMA.field("duration_sec").nullable
    assert not LMS_PARQUET_SCHEMA.field("session_id").nullable


def test_write_single_file_and_read_back(tmp_path: Path) -> None:
    """Write events to a single .parquet file and read back as Table and dicts."""
    sample = _make_sample_events(20)
    out_file = tmp_path / "events.parquet"

    written = write_lms_events_to_parquet(out_file, events=sample)
    assert written == 20
    assert out_file.is_file()

    # Read as Table
    table = read_lms_events_from_parquet(out_file, as_dicts=False)
    assert isinstance(table, pa.Table)
    assert len(table) == 20
    assert table.column_names == LMS_PARQUET_SCHEMA.names

    # Read as dicts
    records = read_lms_events_from_parquet(out_file, as_dicts=True)
    assert isinstance(records, list)
    assert len(records) == 20

    # Validate each record against canonical schema
    for record in records:
        validate_record(record, LMS_EVENTS_SCHEMA)

    assert records[0]["meta"]["student_id"] == "STU100000"
    assert records[0]["activity_type"] == "VIDEO_VIEW"
    assert records[1]["activity_type"] == "LOGIN"
    assert records[1]["resource_id"] is None
    assert records[1]["duration_sec"] is None


def test_write_partitioned_dataset_and_read_back(tmp_path: Path) -> None:
    """Write events to a partitioned directory and verify year/month directory layout."""
    sample = _make_sample_events(30)
    out_dir = tmp_path / "lms_events_partitioned"

    written = write_lms_events_to_parquet(
        out_dir,
        events=sample,
        partition_cols=["year", "month"],
    )
    assert written == 30
    assert out_dir.is_dir()

    # Check partition directories exist (events span 2025/09 and 2025/10)
    p_sep = out_dir / "year=2025" / "month=9"
    p_oct = out_dir / "year=2025" / "month=10"
    assert p_sep.is_dir()
    assert p_oct.is_dir()

    # Read back full partitioned dataset
    table = read_lms_events_from_parquet(out_dir)
    assert len(table) == 30

    # Validate report on partitioned directory
    report = validate_lms_events_parquet(out_dir)
    assert report["valid"] is True
    assert report["record_count"] == 30
    assert report["sample_checked"] == 30


def test_write_from_chunks_iterator(tmp_path: Path) -> None:
    """Stream chunks from an iterator into write_lms_events_to_parquet."""
    sample = _make_sample_events(25)
    # Split into chunks of 10, 10, 5
    chunks = [sample[0:10], sample[10:20], sample[20:25]]

    out_file = tmp_path / "chunked.parquet"
    written = write_lms_events_to_parquet(out_file, chunks=iter(chunks))
    assert written == 25

    table = read_lms_events_from_parquet(out_file)
    assert len(table) == 25

    # Check that row groups match chunk writes
    parquet_file = pq.ParquetFile(str(out_file))
    assert parquet_file.num_row_groups == 3


def test_write_from_run_chunks(tmp_path: Path) -> None:
    """Write to Parquet by providing run, students, and records."""
    configs = copy.deepcopy(validate_project_config())
    scale = configs["generator"]["scale"]
    scale["target_students"] = 6
    scale["school_population"] = {s: 1 for s in scale["school_population"]}
    run = GeneratorRun(configs)

    students = generate_students(run)
    records = generate_academic_records(run, students)

    out_file = tmp_path / "run_events.parquet"
    written = write_lms_events_to_parquet(
        out_file,
        run=run,
        students=students,
        records=records,
        chunk_size=1000,
    )
    assert written > 0

    table = read_lms_events_from_parquet(out_file)
    assert len(table) == written
    report = validate_lms_events_parquet(out_file, sample_size=50)
    assert report["valid"] is True
    assert report["sample_checked"] == 50


def test_validate_lms_events_parquet_success(tmp_path: Path) -> None:
    """Validation helper returns expected dictionary on valid dataset."""
    sample = _make_sample_events(15)
    out_file = tmp_path / "valid.parquet"
    write_lms_events_to_parquet(out_file, events=sample)

    report = validate_lms_events_parquet(out_file, sample_size=10)
    assert report["valid"] is True
    assert report["record_count"] == 15
    assert report["sample_checked"] == 10
    assert "timestamp" in report["columns"]
    assert "meta" in report["columns"]


def test_validate_lms_events_parquet_nonexistent_path(tmp_path: Path) -> None:
    """Validation helper raises FileNotFoundError when path does not exist."""
    with pytest.raises(FileNotFoundError, match="Parquet path does not exist"):
        validate_lms_events_parquet(tmp_path / "missing.parquet")


def test_validate_lms_events_parquet_empty_dataset(tmp_path: Path) -> None:
    """Validation helper raises SchemaError when dataset contains 0 records."""
    out_file = tmp_path / "empty.parquet"
    write_lms_events_to_parquet(out_file, events=[])

    with pytest.raises(SchemaError, match="contains 0 records"):
        validate_lms_events_parquet(out_file)


def test_validate_lms_events_parquet_missing_columns(tmp_path: Path) -> None:
    """Validation helper raises SchemaError when required columns are absent."""
    out_file = tmp_path / "incomplete.parquet"
    bad_schema = pa.schema([pa.field("timestamp", pa.timestamp("us"))])
    bad_table = pa.Table.from_pylist(
        [{"timestamp": datetime(2025, 9, 1, 10, 0)}],
        schema=bad_schema,
    )
    pq.write_table(bad_table, str(out_file))

    with pytest.raises(SchemaError, match="missing required columns"):
        validate_lms_events_parquet(out_file)


def test_validate_lms_events_parquet_invalid_meta_field(tmp_path: Path) -> None:
    """Validation helper raises SchemaError when meta is not a struct or missing fields."""
    out_file = tmp_path / "bad_meta.parquet"
    bad_schema = pa.schema(
        [
            pa.field("timestamp", pa.timestamp("us")),
            pa.field("meta", pa.string()),  # Should be struct
            pa.field("activity_type", pa.string()),
            pa.field("resource_id", pa.string()),
            pa.field("duration_sec", pa.int64()),
            pa.field("session_id", pa.string()),
        ]
    )
    bad_table = pa.Table.from_pylist(
        [
            {
                "timestamp": datetime(2025, 9, 1, 10, 0),
                "meta": "not_a_struct",
                "activity_type": "LOGIN",
                "resource_id": None,
                "duration_sec": None,
                "session_id": "SES1000001",
            }
        ],
        schema=bad_schema,
    )
    pq.write_table(bad_table, str(out_file))

    with pytest.raises(SchemaError, match="must be a struct"):
        validate_lms_events_parquet(out_file)


def test_validate_lms_events_parquet_invalid_record_content(tmp_path: Path) -> None:
    """Validation helper raises SchemaError when record content violates LMS schema."""
    out_file = tmp_path / "invalid_content.parquet"
    sample = [
        {
            "timestamp": datetime(2025, 9, 1, 10, 0),
            "meta": {
                "student_id": "INVALID_STUDENT_ID",  # Fails regex pattern
                "course_id": "CSE101",
                "school": "CET",
            },
            "activity_type": "LOGIN",
            "resource_id": None,
            "duration_sec": None,
            "session_id": "SES1000001",
        }
    ]
    write_lms_events_to_parquet(out_file, events=sample)

    with pytest.raises(SchemaError, match="does not match pattern"):
        validate_lms_events_parquet(out_file)


def test_write_invalid_parameters(tmp_path: Path) -> None:
    """Check that invalid argument combinations raise GeneratorError."""
    # partition_cols with single file
    with pytest.raises(GeneratorError, match="partition_cols cannot be specified"):
        write_lms_events_to_parquet(
            tmp_path / "single.parquet",
            events=_make_sample_events(2),
            partition_cols=["year"],
        )

    # Missing run, chunks, and events
    with pytest.raises(GeneratorError, match="One of 'run', 'chunks', or 'events'"):
        write_lms_events_to_parquet(tmp_path / "any.parquet")


def test_read_projection(tmp_path: Path) -> None:
    """Test projecting specific columns during read."""
    sample = _make_sample_events(5)
    out_file = tmp_path / "proj.parquet"
    write_lms_events_to_parquet(out_file, events=sample)

    table = read_lms_events_from_parquet(
        out_file,
        columns=["activity_type", "session_id"],
    )
    assert table.column_names == ["activity_type", "session_id"]
    assert len(table) == 5


def test_overwrite_behavior(tmp_path: Path) -> None:
    """Test overwriting existing file and partitioned dataset."""
    # 1. Single file overwrite
    f_path = tmp_path / "test.parquet"
    write_lms_events_to_parquet(f_path, events=_make_sample_events(5))
    assert len(read_lms_events_from_parquet(f_path)) == 5
    write_lms_events_to_parquet(f_path, events=_make_sample_events(12), overwrite=True)
    assert len(read_lms_events_from_parquet(f_path)) == 12

    # 2. Directory overwrite
    d_path = tmp_path / "dir_parquet"
    write_lms_events_to_parquet(d_path, events=_make_sample_events(5))
    assert len(read_lms_events_from_parquet(d_path)) == 5
    write_lms_events_to_parquet(d_path, events=_make_sample_events(8), overwrite=True)
    assert len(read_lms_events_from_parquet(d_path)) == 8


def test_generate_development_lms_parquet(tmp_path: Path) -> None:
    """Generate small development-scale LMS dataset and validate end-to-end (task 5.4)."""
    dev_dir = tmp_path / "lms_events_dev"
    total_events = generate_development_lms_parquet(
        output_path=dev_dir,
        target_students=6,
        chunk_size=500,
    )
    assert total_events > 0

    # Validate read-back
    report = validate_lms_events_parquet(dev_dir, sample_size=100)
    assert report["valid"] is True
    assert report["record_count"] == total_events
    assert report["sample_checked"] == 100
