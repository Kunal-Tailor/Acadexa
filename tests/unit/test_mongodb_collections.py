"""Unit tests for MongoDB collections initialization and verification (task 6.2, rules.md §11, §16)."""

from __future__ import annotations

import pytest

from acadexa.database import (
    ALL_MANAGED_COLLECTIONS,
    COLLECTION_METADATA,
    CORE_COLLECTIONS,
    GOLD_COLLECTIONS,
    LMS_TIMESERIES_SPEC,
    TIMESERIES_COLLECTIONS,
    MongoDBConfig,
    MongoConnectionError,
    close_mongo_client,
    drop_managed_collections,
    get_database,
    get_mongo_client,
    init_database,
    verify_database_collections,
)


def test_collection_constants_and_metadata() -> None:
    """Verify canonical collection names, metadata specifications, and grains."""
    # Check collection groupings
    assert len(CORE_COLLECTIONS) == 5
    assert set(CORE_COLLECTIONS) == {
        "students",
        "courses",
        "academic_records",
        "attendance",
        "coursework",
    }

    assert len(TIMESERIES_COLLECTIONS) == 1
    assert TIMESERIES_COLLECTIONS == ("lms_events",)

    assert len(GOLD_COLLECTIONS) == 4
    assert set(GOLD_COLLECTIONS) == {
        "student_features",
        "course_metrics",
        "school_summary",
        "risk_indicators",
    }

    assert len(ALL_MANAGED_COLLECTIONS) == 10
    assert ALL_MANAGED_COLLECTIONS == CORE_COLLECTIONS + TIMESERIES_COLLECTIONS + GOLD_COLLECTIONS

    # LMS Time-Series specification matches rules.md §11 / architecture.md §10
    assert LMS_TIMESERIES_SPEC["timeField"] == "timestamp"
    assert LMS_TIMESERIES_SPEC["metaField"] == "meta"
    assert LMS_TIMESERIES_SPEC["granularity"] == "seconds"

    # Collection metadata mapping
    assert len(COLLECTION_METADATA) == 10
    for name in ALL_MANAGED_COLLECTIONS:
        assert name in COLLECTION_METADATA
        meta = COLLECTION_METADATA[name]
        assert "type" in meta
        assert "description" in meta
        assert "grain" in meta
        assert len(meta["grain"]) > 0


@pytest.fixture(scope="module")
def test_db():
    """Module-level fixture providing an isolated MongoDB test database."""
    config = MongoDBConfig(database="test_acadexa_collections")
    client = get_mongo_client(config)
    db = get_database(config, client=client)

    # Ensure clean start
    drop_managed_collections(db)

    yield db

    # Teardown
    drop_managed_collections(db)
    client.drop_database("test_acadexa_collections")
    close_mongo_client(client)


def test_init_database_lifecycle(test_db) -> None:
    """Verify end-to-end collection initialization, idempotence, and teardown."""
    # Initial state should show uninitialized database
    initial_status = verify_database_collections(test_db)
    assert initial_status["ready"] is False
    assert initial_status["all_core_present"] is False
    assert initial_status["all_gold_present"] is False

    # 1. Initialize database with all core, timeseries, and gold collections
    res = init_database(test_db, drop_existing=True)
    assert res["status"] == "initialized"
    assert len(res["collections_created"]) == 10
    assert len(res["collections_existing"]) == 0
    assert set(res["collections_created"]) == set(ALL_MANAGED_COLLECTIONS)

    # 2. Verify all collections exist
    names = set(test_db.list_collection_names())
    for col in ALL_MANAGED_COLLECTIONS:
        assert col in names

    # 3. Verify collection inspection status
    status = verify_database_collections(test_db)
    assert status["ready"] is True
    assert status["all_core_present"] is True
    assert status["timeseries_present"] is True
    assert status["all_gold_present"] is True

    # 4. Verify gold collections are empty placeholders (0 documents)
    for gold_col in GOLD_COLLECTIONS:
        assert test_db[gold_col].count_documents({}) == 0
        assert status["collections"][gold_col]["count"] == 0

    # 5. Verify idempotence: calling init_database again does not error
    res_repeat = init_database(test_db, drop_existing=False)
    assert res_repeat["status"] == "initialized"
    assert len(res_repeat["collections_created"]) == 0
    assert len(res_repeat["collections_existing"]) == 10

    # 6. Verify drop_managed_collections
    dropped = drop_managed_collections(test_db)
    assert len(dropped) == 10
    post_drop_status = verify_database_collections(test_db)
    assert post_drop_status["ready"] is False
    assert post_drop_status["all_core_present"] is False


def test_init_database_without_gold_placeholders(test_db) -> None:
    """Verify init_database with create_gold_placeholders=False."""
    drop_managed_collections(test_db)

    res = init_database(test_db, create_gold_placeholders=False)
    assert res["status"] == "initialized"
    assert set(res["collections_created"]) == set(CORE_COLLECTIONS + TIMESERIES_COLLECTIONS)

    status = verify_database_collections(test_db)
    assert status["all_core_present"] is True
    assert status["timeseries_present"] is True
    assert status["all_gold_present"] is False
    assert status["ready"] is False

    # Clean up
    drop_managed_collections(test_db)


def test_init_database_unreachable() -> None:
    """Verify init_database raises MongoConnectionError when host is unreachable."""
    unreachable_cfg = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_unreachable",
        server_selection_timeout_ms=50,
        connect_timeout_ms=50,
    )
    with pytest.raises(MongoConnectionError, match="Cannot connect to MongoDB"):
        init_database(config=unreachable_cfg)
