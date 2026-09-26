"""Unit tests for MongoDB query indexes and execution plan verification (task 6.5, rules.md §16.3)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from acadexa.database import (
    ALL_MANAGED_COLLECTIONS,
    COLLECTION_INDEX_DEFINITIONS,
    CORE_COLLECTIONS,
    GOLD_COLLECTIONS,
    IndexSummary,
    MongoDBConfig,
    MongoConnectionError,
    close_mongo_client,
    create_database_indexes,
    drop_database_indexes,
    drop_managed_collections,
    explain_query_plan,
    get_database,
    get_mongo_client,
    init_database,
    list_database_indexes,
)


@pytest.fixture(scope="module")
def index_test_db():
    """Module-level fixture providing an isolated MongoDB test database."""
    config = MongoDBConfig(database="test_acadexa_indexes")
    client = get_mongo_client(config)
    db = get_database(config, client=client)

    # Initialize collections
    init_database(db, drop_existing=True)

    yield db

    # Teardown
    drop_managed_collections(db)
    client.drop_database("test_acadexa_indexes")
    close_mongo_client(client)


def test_index_definitions_specification() -> None:
    """Verify that index definitions match documented query patterns (features.md F-C06)."""
    # 1. All core collections must have defined indexes
    for name in CORE_COLLECTIONS:
        assert name in COLLECTION_INDEX_DEFINITIONS
        assert len(COLLECTION_INDEX_DEFINITIONS[name]) >= 2

    # 2. Student and course unique identifiers
    students_models = {m.document["name"]: m.document for m in COLLECTION_INDEX_DEFINITIONS["students"]}
    assert "idx_students_student_id" in students_models
    assert students_models["idx_students_student_id"].get("unique") is True

    courses_models = {m.document["name"]: m.document for m in COLLECTION_INDEX_DEFINITIONS["courses"]}
    assert "idx_courses_course_id" in courses_models
    assert courses_models["idx_courses_course_id"].get("unique") is True

    # 3. Hierarchy access [school, department]
    assert "idx_students_hierarchy" in students_models
    assert "idx_courses_hierarchy" in courses_models

    # 4. Course & Semester access [course_id, semester_id]
    records_models = {m.document["name"]: m.document for m in COLLECTION_INDEX_DEFINITIONS["academic_records"]}
    assert "idx_records_course_semester" in records_models

    attendance_models = {m.document["name"]: m.document for m in COLLECTION_INDEX_DEFINITIONS["attendance"]}
    assert "idx_attendance_course_semester" in attendance_models

    # 5. LMS time-series access [meta.student_id, meta.course_id, timestamp]
    lms_models = {m.document["name"]: m.document for m in COLLECTION_INDEX_DEFINITIONS["lms_events"]}
    assert "idx_lms_student_course_ts" in lms_models
    assert "idx_lms_course_ts" in lms_models

    # 6. Gold collections have grain indexes
    for name in GOLD_COLLECTIONS:
        assert name in COLLECTION_INDEX_DEFINITIONS


def test_create_and_list_database_indexes(index_test_db) -> None:
    """Verify end-to-end index creation, inspection, idempotence, and selective dropping."""
    # 1. Create indexes across all managed collections
    res = create_database_indexes(database=index_test_db)
    assert len(res) >= 10
    assert "students" in res
    assert "idx_students_student_id" in res["students"]
    assert "idx_students_hierarchy" in res["students"]
    assert "lms_events" in res
    assert "idx_lms_student_course_ts" in res["lms_events"]

    # 2. List indexes and verify IndexSummary structure
    indexes = list_database_indexes(database=index_test_db)
    assert "students" in indexes
    summary_map = {idx.name: idx for idx in indexes["students"]}
    assert "idx_students_student_id" in summary_map
    assert summary_map["idx_students_student_id"].unique is True
    assert summary_map["idx_students_student_id"].keys == [("student_id", 1)]

    # 3. Idempotence: re-running does not error and returns index names
    res_repeat = create_database_indexes(database=index_test_db)
    assert "students" in res_repeat
    assert "idx_students_student_id" in res_repeat["students"]

    # 4. Drop user indexes and verify default _id_ and time-series meta index are preserved
    dropped = drop_database_indexes(database=index_test_db, collection_names=["students"])
    assert "students" in dropped
    assert "idx_students_student_id" in dropped["students"]

    post_drop_indexes = list_database_indexes(database=index_test_db, collection_names=["students"])
    remaining_names = [idx.name for idx in post_drop_indexes["students"]]
    assert remaining_names == ["_id_"]

    # Re-create to restore
    create_database_indexes(database=index_test_db, collection_names=["students"])


def test_explain_query_plan_optimization(index_test_db) -> None:
    """Verify that indexed queries utilize index scan (IXSCAN) while unindexed queries use COLLSCAN."""
    # Ensure indexes exist
    create_database_indexes(database=index_test_db, collection_names=["students"])

    # Insert test student documents
    index_test_db["students"].delete_many({})
    index_test_db["students"].insert_many(
        [
            {
                "student_id": "STU100001",
                "school": "School of Computer Engineering & Technology",
                "department": "Computer Science and Applications",
                "program": "B.Tech CSE",
                "batch": 2024,
                "semester": 3,
            },
            {
                "student_id": "STU100002",
                "school": "School of Management",
                "department": "Management Studies",
                "program": "MBA",
                "batch": 2025,
                "semester": 1,
            },
        ]
    )

    # 1. Query by unique student_id -> must utilize index
    plan_id = explain_query_plan(
        collection_name="students",
        filter_query={"student_id": "STU100001"},
        database=index_test_db,
    )
    assert plan_id["collection"] == "students"
    assert plan_id["is_indexed"] is True
    assert plan_id["index_name"] == "idx_students_student_id"
    assert "IXSCAN" in plan_id["stage"].upper()

    # 2. Query by hierarchy [school, department] -> must utilize hierarchy index
    plan_hierarchy = explain_query_plan(
        collection_name="students",
        filter_query={
            "school": "School of Computer Engineering & Technology",
            "department": "Computer Science and Applications",
        },
        database=index_test_db,
    )
    assert plan_hierarchy["is_indexed"] is True
    assert plan_hierarchy["index_name"] == "idx_students_hierarchy"
    assert "IXSCAN" in plan_hierarchy["stage"].upper()

    # 3. Query by unindexed field (program only) -> must fall back to collection scan (COLLSCAN)
    plan_unindexed = explain_query_plan(
        collection_name="students",
        filter_query={"program": "B.Tech CSE"},
        database=index_test_db,
    )
    assert plan_unindexed["is_indexed"] is False
    assert plan_unindexed["stage"].upper() == "COLLSCAN"


def test_create_database_indexes_unreachable() -> None:
    """Verify MongoConnectionError when connecting to an unreachable host."""
    unreachable_cfg = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_unreachable",
        server_selection_timeout_ms=50,
        connect_timeout_ms=50,
    )
    with pytest.raises(MongoConnectionError, match="Cannot connect to MongoDB"):
        create_database_indexes(config=unreachable_cfg)
