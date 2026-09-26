"""Unit tests for MongoDB LMS serving slice loader (task 6.4, rules.md §9, §16.2)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import pytest

from acadexa.database import (
    DEFAULT_LMS_SLICE_SCHOOLS,
    DEFAULT_LMS_SLICE_SEMESTER,
    LMSServingSliceSpec,
    LMSSliceLoadResult,
    LoadValidationError,
    MongoDBConfig,
    MongoConnectionError,
    close_mongo_client,
    drop_managed_collections,
    get_database,
    get_mongo_client,
    init_database,
    load_lms_serving_slice,
    stream_lms_slice_records,
)


@pytest.fixture(scope="module")
def lms_test_db():
    """Module-level fixture providing an isolated MongoDB test database."""
    config = MongoDBConfig(database="test_acadexa_lms_slice")
    client = get_mongo_client(config)
    db = get_database(config, client=client)

    # Initialize time-series collection
    init_database(db, drop_existing=True)

    yield db

    # Teardown
    drop_managed_collections(db)
    client.drop_database("test_acadexa_lms_slice")
    close_mongo_client(client)


def test_lms_serving_slice_spec_defaults_and_matching() -> None:
    """Verify LMSServingSliceSpec configuration loading and record matching."""
    spec = LMSServingSliceSpec.from_config()

    assert spec.schools == ("CET", "SOM")
    assert spec.semester_id == "S4"
    assert spec.start_date == date(2026, 1, 5)
    assert spec.end_date == date(2026, 4, 26)

    # 1. Matching records (S4 semester, CET or SOM schools)
    match_cet = {
        "timestamp": datetime(2026, 2, 10, 14, 30, 0),
        "meta": {"student_id": "STU001", "course_id": "CSA101", "school": "CET"},
        "activity_type": "VIDEO_VIEW",
        "resource_id": "R101",
        "duration_sec": 300,
        "session_id": "SES001",
    }
    match_som = {
        "timestamp": "2026-03-15T09:00:00Z",  # ISO string
        "meta": {"student_id": "STU002", "course_id": "MGT101", "school": "SOM"},
        "activity_type": "QUIZ_ATTEMPT",
        "resource_id": "Q101",
        "duration_sec": 600,
        "session_id": "SES002",
    }
    assert spec.matches(match_cet) is True
    assert spec.matches(match_som) is True

    # 2. Non-matching: different school (e.g. SET, SCI, SOL, LAD)
    mismatch_school = {
        "timestamp": datetime(2026, 2, 10, 14, 30, 0),
        "meta": {"student_id": "STU003", "course_id": "MEC101", "school": "SET"},
        "activity_type": "VIDEO_VIEW",
        "resource_id": "R102",
        "duration_sec": 200,
        "session_id": "SES003",
    }
    assert spec.matches(mismatch_school) is False

    # 3. Non-matching: earlier semester (e.g. 2025 S1 or S2)
    mismatch_date = {
        "timestamp": datetime(2025, 9, 10, 14, 30, 0),
        "meta": {"student_id": "STU001", "course_id": "CSA101", "school": "CET"},
        "activity_type": "VIDEO_VIEW",
        "resource_id": "R101",
        "duration_sec": 300,
        "session_id": "SES004",
    }
    assert spec.matches(mismatch_date) is False

    # 4. Malformed records
    assert spec.matches({}) is False
    assert spec.matches({"timestamp": datetime(2026, 2, 1)}) is False
    assert spec.matches({"meta": {"school": "CET"}}) is False

    # 5. Serialization
    spec_dict = spec.as_dict()
    assert spec_dict["semester_id"] == "S4"
    assert spec_dict["schools"] == ["CET", "SOM"]


def test_load_lms_serving_slice_in_memory_records(lms_test_db) -> None:
    """Verify loading and filtering in-memory LMS records into MongoDB time-series collection."""
    test_events = [
        # In-slice: S4, CET
        {
            "timestamp": datetime(2026, 2, 1, 10, 0, 0),
            "meta": {"student_id": "STU001", "course_id": "CSA101", "school": "CET"},
            "activity_type": "LOGIN",
            "resource_id": None,
            "duration_sec": None,
            "session_id": "SES101",
        },
        # In-slice: S4, SOM
        {
            "timestamp": datetime(2026, 3, 1, 11, 0, 0),
            "meta": {"student_id": "STU002", "course_id": "MGT101", "school": "SOM"},
            "activity_type": "PDF_VIEW",
            "resource_id": "DOC01",
            "duration_sec": 120,
            "session_id": "SES102",
        },
        # Out-of-slice: S4, but SET (different school)
        {
            "timestamp": datetime(2026, 2, 1, 10, 0, 0),
            "meta": {"student_id": "STU003", "course_id": "MEC101", "school": "SET"},
            "activity_type": "LOGIN",
            "resource_id": None,
            "duration_sec": None,
            "session_id": "SES103",
        },
        # Out-of-slice: CET, but S2 (different semester)
        {
            "timestamp": datetime(2025, 3, 1, 10, 0, 0),
            "meta": {"student_id": "STU001", "course_id": "CSA101", "school": "CET"},
            "activity_type": "LOGIN",
            "resource_id": None,
            "duration_sec": None,
            "session_id": "SES104",
        },
    ]

    result = load_lms_serving_slice(
        database=lms_test_db,
        records=test_events,
        batch_size=1,  # exercise multiple chunk batches
        clear_existing=True,
    )

    assert isinstance(result, LMSSliceLoadResult)
    assert result.collection == "lms_events"
    assert result.total_scanned == 4
    assert result.slice_selected == 2  # exactly 2 matching events
    assert result.inserted_count == 2
    assert result.actual_db_count == 2
    assert result.validated is True

    # Verify MongoDB time-series collection contents
    docs = list(lms_test_db["lms_events"].find({}))
    assert len(docs) == 2
    schools = {d["meta"]["school"] for d in docs}
    assert schools == {"CET", "SOM"}

    # Verify that timestamp in MongoDB is a valid BSON UTC datetime
    for doc in docs:
        assert isinstance(doc["timestamp"], datetime)
        assert doc["timestamp"].year == 2026

    # Test idempotence: reload with clear_existing=True
    reload_result = load_lms_serving_slice(
        database=lms_test_db,
        records=test_events,
        clear_existing=True,
    )
    assert reload_result.actual_db_count == 2
    assert lms_test_db["lms_events"].count_documents({}) == 2


def test_load_lms_serving_slice_from_parquet_dataset(lms_test_db) -> None:
    """Verify loading from raw Parquet dataset with partition filter and streaming."""
    parquet_path = Path("data/raw/lms_events")
    if not parquet_path.exists():
        pytest.skip("data/raw/lms_events not generated yet on disk")

    spec = LMSServingSliceSpec.from_config()

    # 1. Test streaming generator
    batches = list(stream_lms_slice_records(parquet_path, spec=spec, batch_size=5000))
    assert len(batches) > 0
    total_streamed = sum(len(b) for b in batches)
    assert total_streamed > 0

    # 2. Test loading into MongoDB
    res = load_lms_serving_slice(
        database=lms_test_db,
        parquet_path=parquet_path,
        spec=spec,
        batch_size=5000,
        clear_existing=True,
    )

    assert res.validated is True
    assert res.slice_selected == total_streamed
    assert res.inserted_count == total_streamed
    assert res.actual_db_count == total_streamed
    # Confirm that total scanned was larger than slice selected (not all events loaded)
    assert res.total_scanned >= res.slice_selected

    # Verify MongoDB document counts
    assert lms_test_db["lms_events"].count_documents({}) == total_streamed


def test_load_lms_serving_slice_unreachable() -> None:
    """Verify MongoConnectionError when connecting to unreachable host."""
    unreachable_cfg = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_unreachable",
        server_selection_timeout_ms=50,
        connect_timeout_ms=50,
    )
    with pytest.raises(MongoConnectionError, match="Cannot connect to MongoDB"):
        load_lms_serving_slice(
            records=[],
            config=unreachable_cfg,
        )


def test_load_lms_serving_slice_missing_parquet_raises(lms_test_db) -> None:
    """Verify LoadValidationError when Parquet dataset path is missing."""
    with pytest.raises(LoadValidationError, match="not found"):
        load_lms_serving_slice(
            database=lms_test_db,
            parquet_path="data/raw/non_existent_path",
        )
