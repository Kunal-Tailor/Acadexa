"""Unit tests for MongoDB core academic collections loader (task 6.3, rules.md §16)."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import pytest

from acadexa.database import (
    CORE_COLLECTIONS,
    GOLD_COLLECTIONS,
    CollectionLoadStatus,
    CoreLoadResult,
    LoadValidationError,
    MongoDBConfig,
    MongoConnectionError,
    close_mongo_client,
    drop_managed_collections,
    get_database,
    get_mongo_client,
    init_database,
    load_core_academic_data,
    load_core_collection,
)


@pytest.fixture(scope="module")
def loader_test_db():
    """Module-level fixture providing an isolated MongoDB test database."""
    config = MongoDBConfig(database="test_acadexa_loader")
    client = get_mongo_client(config)
    db = get_database(config, client=client)

    # Clean initial state
    init_database(db, drop_existing=True)

    yield db

    # Teardown
    drop_managed_collections(db)
    client.drop_database("test_acadexa_loader")
    close_mongo_client(client)


def test_load_core_collection_in_memory_and_immutability(loader_test_db) -> None:
    """Verify single collection loading, count validation, and caller immutability."""
    sample_students = [
        {
            "student_id": "STU000001",
            "school": "School of Computer Engineering & Technology",
            "department": "Computer Science and Applications",
            "program": "B.Tech Computer Science and Engineering",
            "batch": 2024,
            "semester": 3,
        },
        {
            "student_id": "STU000002",
            "school": "School of Electrical Engineering",
            "department": "Electrical and Electronics",
            "program": "B.Tech Electrical Engineering",
            "batch": 2024,
            "semester": 3,
        },
        {
            "student_id": "STU000003",
            "school": "School of Business",
            "department": "Management Studies",
            "program": "BBA",
            "batch": 2025,
            "semester": 1,
        },
    ]

    # Verify input dicts do not have _id
    for s in sample_students:
        assert "_id" not in s

    status = load_core_collection(
        collection_name="students",
        records=sample_students,
        database=loader_test_db,
        batch_size=2,  # exercise batch chunking
        clear_existing=True,
    )

    assert isinstance(status, CollectionLoadStatus)
    assert status.collection == "students"
    assert status.expected_count == 3
    assert status.inserted_count == 3
    assert status.actual_db_count == 3
    assert status.validated is True
    assert status.duration_sec >= 0.0

    # Verify that caller's original in-memory dictionaries were NOT mutated by PyMongo _id
    for s in sample_students:
        assert "_id" not in s

    # Verify documents in MongoDB
    docs = list(loader_test_db["students"].find({}, {"_id": 0}))
    assert len(docs) == 3
    assert docs[0]["student_id"] == "STU000001"


def test_load_core_collection_date_normalization(loader_test_db) -> None:
    """Verify datetime.date normalization to ISO-8601 strings (PyMongo compatibility)."""
    attendance_records = [
        {
            "student_id": "STU000001",
            "course_id": "CSA101",
            "semester_id": "S1",
            "week_start": date(2025, 9, 1),  # Python date object
            "classes_conducted": 4,
            "classes_attended": 4,
        },
        {
            "student_id": "STU000001",
            "course_id": "CSA101",
            "semester_id": "S1",
            "week_start": date(2025, 9, 8),
            "classes_conducted": 4,
            "classes_attended": 3,
        },
    ]

    status = load_core_collection(
        collection_name="attendance",
        records=attendance_records,
        database=loader_test_db,
        clear_existing=True,
    )
    assert status.validated is True
    assert status.actual_db_count == 2

    # Verify that week_start was stored as string "YYYY-MM-DD"
    stored = list(loader_test_db["attendance"].find({"student_id": "STU000001"}))
    assert len(stored) == 2
    assert stored[0]["week_start"] == "2025-09-01"
    assert stored[1]["week_start"] == "2025-09-08"


def test_load_core_collection_invalid_collection_name(loader_test_db) -> None:
    """Verify that attempting to load a non-core collection raises ValueError."""
    with pytest.raises(ValueError, match="Expected one of"):
        load_core_collection(
            collection_name="lms_events",  # timeseries, not core
            records=[],
            database=loader_test_db,
        )

    with pytest.raises(ValueError, match="Expected one of"):
        load_core_collection(
            collection_name="student_features",  # gold, not core
            records=[],
            database=loader_test_db,
        )


def test_load_core_academic_data_in_memory(loader_test_db) -> None:
    """Verify loading all 5 core collections from in-memory data dictionary."""
    core_data = {
        "students": [
            {
                "student_id": "STU000001",
                "school": "School of Computer Engineering & Technology",
                "department": "Computer Science and Applications",
                "program": "B.Tech CSE",
                "batch": 2024,
                "semester": 3,
            }
        ],
        "courses": [
            {
                "course_id": "CSA101",
                "title": "Programming Fundamentals",
                "school": "School of Computer Engineering & Technology",
                "department": "Computer Science and Applications",
                "semester_applicability": [1, 2],
                "difficulty_level": "easy",
                "difficulty": 0.35,
            }
        ],
        "academic_records": [
            {
                "student_id": "STU000001",
                "course_id": "CSA101",
                "semester_id": "S1",
                "internal_marks": 35,
                "midterm_marks": 18,
                "endterm_marks": 40,
                "final_grade": "A",
            }
        ],
        "attendance": [
            {
                "student_id": "STU000001",
                "course_id": "CSA101",
                "semester_id": "S1",
                "week_start": "2025-09-01",
                "classes_conducted": 4,
                "classes_attended": 4,
            }
        ],
        "coursework": [
            {
                "student_id": "STU000001",
                "course_id": "CSA101",
                "item_id": "A01",
                "item_type": "ASSIGNMENT",
                "assigned_date": "2025-09-08",
                "due_date": "2025-09-15",
                "submitted_at": "2025-09-14T18:00:00",
                "score": 18,
                "max_score": 20,
                "attempts": 1,
                "status": "ON_TIME",
            }
        ],
    }

    result = load_core_academic_data(
        database=loader_test_db,
        data=core_data,
        batch_size=500,
        clear_existing=True,
    )

    assert isinstance(result, CoreLoadResult)
    assert result.database == loader_test_db.name
    assert result.all_validated is True
    assert result.total_expected == 5
    assert result.total_inserted == 5
    assert len(result.collections) == 5

    for name in CORE_COLLECTIONS:
        assert name in result.collections
        assert result.collections[name].validated is True
        assert result.collections[name].actual_db_count == 1
        assert loader_test_db[name].count_documents({}) == 1

    # Gold collections must remain untouched (0 documents)
    for gold_col in GOLD_COLLECTIONS:
        assert loader_test_db[gold_col].count_documents({}) == 0


def test_load_core_academic_data_from_files_and_manifest(tmp_path: Path, loader_test_db) -> None:
    """Verify loading from JSON files on disk and validating against generation manifest."""
    data_dir = tmp_path / "generated"
    data_dir.mkdir(parents=True)
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)

    # 1. Write dummy JSON files
    actual_counts = {
        "students": 2,
        "courses": 1,
        "academic_records": 2,
        "attendance": 3,
        "coursework": 2,
    }

    (data_dir / "students.json").write_text(
        json.dumps(
            [
                {"student_id": "STU001", "school": "S1", "department": "D1", "program": "P1", "batch": 2024, "semester": 1},
                {"student_id": "STU002", "school": "S1", "department": "D1", "program": "P1", "batch": 2024, "semester": 1},
            ]
        ),
        encoding="utf-8",
    )

    (data_dir / "courses.json").write_text(
        json.dumps(
            [
                {"course_id": "C01", "title": "Math", "school": "S1", "department": "D1", "semester_applicability": [1], "difficulty_level": "medium", "difficulty": 0.5},
            ]
        ),
        encoding="utf-8",
    )

    (data_dir / "academic_records.json").write_text(
        json.dumps(
            [
                {"student_id": "STU001", "course_id": "C01", "semester_id": "S1", "internal_marks": 30, "midterm_marks": 15, "endterm_marks": 40, "final_grade": "B"},
                {"student_id": "STU002", "course_id": "C01", "semester_id": "S1", "internal_marks": 35, "midterm_marks": 20, "endterm_marks": 45, "final_grade": "A"},
            ]
        ),
        encoding="utf-8",
    )

    (data_dir / "attendance.json").write_text(
        json.dumps(
            [
                {"student_id": "STU001", "course_id": "C01", "semester_id": "S1", "week_start": "2025-09-01", "classes_conducted": 3, "classes_attended": 3},
                {"student_id": "STU001", "course_id": "C01", "semester_id": "S1", "week_start": "2025-09-08", "classes_conducted": 3, "classes_attended": 2},
                {"student_id": "STU002", "course_id": "C01", "semester_id": "S1", "week_start": "2025-09-01", "classes_conducted": 3, "classes_attended": 3},
            ]
        ),
        encoding="utf-8",
    )

    (data_dir / "coursework.json").write_text(
        json.dumps(
            [
                {"student_id": "STU001", "course_id": "C01", "item_id": "A01", "item_type": "ASSIGNMENT", "assigned_date": "2025-09-01", "due_date": "2025-09-08", "submitted_at": "2025-09-07T12:00:00", "score": 10, "max_score": 10, "attempts": 1, "status": "ON_TIME"},
                {"student_id": "STU002", "course_id": "C01", "item_id": "A01", "item_type": "ASSIGNMENT", "assigned_date": "2025-09-01", "due_date": "2025-09-08", "submitted_at": "2025-09-08T12:00:00", "score": 9, "max_score": 10, "attempts": 1, "status": "ON_TIME"},
            ]
        ),
        encoding="utf-8",
    )

    manifest_path = manifest_dir / "generation_manifest.json"
    manifest_path.write_text(
        json.dumps({"actual_counts": actual_counts}),
        encoding="utf-8",
    )

    # 2. Execute load and validation
    result = load_core_academic_data(
        database=loader_test_db,
        data_dir=data_dir,
        manifest_path=manifest_path,
        clear_existing=True,
    )

    assert result.all_validated is True
    assert result.total_expected == 10
    assert result.total_inserted == 10

    # Check serialization
    res_dict = result.as_dict()
    assert res_dict["total_inserted"] == 10
    assert "students" in res_dict["collections"]


def test_load_core_academic_data_manifest_mismatch_raises(tmp_path: Path, loader_test_db) -> None:
    """Verify LoadValidationError when manifest count does not match loaded count."""
    data_dir = tmp_path / "gen_mismatch"
    data_dir.mkdir()
    manifest_dir = tmp_path / "mf_mismatch"
    manifest_dir.mkdir()

    for name in CORE_COLLECTIONS:
        (data_dir / f"{name}.json").write_text("[]", encoding="utf-8")

    manifest_path = manifest_dir / "generation_manifest.json"
    manifest_path.write_text(
        json.dumps({"actual_counts": {"students": 999, "courses": 0, "academic_records": 0, "attendance": 0, "coursework": 0}}),
        encoding="utf-8",
    )

    with pytest.raises(LoadValidationError, match="Manifest count mismatch for 'students'"):
        load_core_academic_data(
            database=loader_test_db,
            data_dir=data_dir,
            manifest_path=manifest_path,
            strict_validation=True,
        )


def test_load_core_academic_data_missing_file_raises(tmp_path: Path, loader_test_db) -> None:
    """Verify LoadValidationError when a required core collection JSON file is missing."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    with pytest.raises(LoadValidationError, match="Core collection file missing"):
        load_core_academic_data(
            database=loader_test_db,
            data_dir=empty_dir,
            strict_validation=True,
        )


def test_load_core_academic_data_unreachable() -> None:
    """Verify MongoConnectionError when connecting to an unreachable MongoDB host."""
    unreachable_cfg = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_unreachable",
        server_selection_timeout_ms=50,
        connect_timeout_ms=50,
    )
    with pytest.raises(MongoConnectionError, match="Cannot connect to MongoDB"):
        load_core_collection(
            collection_name="students",
            records=[],
            config=unreachable_cfg,
        )
