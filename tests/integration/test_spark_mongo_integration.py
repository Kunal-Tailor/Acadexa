"""Integration tests for PySpark MongoDB integration (task 7.2, rules.md §7, §16, §19).

Verifies that development collections in MongoDB can be read into PySpark DataFrames,
projected, filtered with pipeline pushdown, and written back cleanly.
"""

from __future__ import annotations

from typing import Generator
import pytest

from acadexa.database.client import mongo_database_context
from acadexa.processing import (
    SparkRuntimeConfig,
    get_or_create_mongo_spark_session,
    read_mongo_collection,
    stop_spark_session,
    verify_spark_mongo_read,
    write_mongo_collection,
)


@pytest.fixture(scope="module")
def spark_mongo() -> Generator:
    """Provide a shared local SparkSession configured with the MongoDB connector."""
    config = SparkRuntimeConfig(
        app_name="AcadexaMongoIntegrationTest",
        master="local[2]",
        driver_memory="1g",
        shuffle_partitions=2,
        default_parallelism=2,
        ui_enabled=False,
    )
    spark = get_or_create_mongo_spark_session(config)
    yield spark
    stop_spark_session(spark)


def test_verify_spark_mongo_read_students(spark_mongo: Generator) -> None:
    """Verify reading development 'students' collection into a Spark DataFrame."""
    diag = verify_spark_mongo_read(spark_mongo, collection_name="students")
    assert diag["status"] == "ok"
    assert diag["collection"] == "students"
    assert diag["row_count"] == 36
    assert "student_id" in diag["columns"]
    assert "school" in diag["columns"]
    assert "department" in diag["columns"]


def test_read_mongo_courses_with_projection(spark_mongo: Generator) -> None:
    """Verify reading 'courses' collection with pushdown column projection."""
    df = read_mongo_collection(
        spark_mongo,
        "courses",
        projection=["course_id", "title", "school"],
    )
    assert df.columns == ["course_id", "title", "school"]
    assert df.count() == 72

    first_row = df.first()
    assert first_row is not None
    assert first_row["course_id"].startswith("CS") or first_row["course_id"].isalnum()


def test_read_mongo_with_pipeline_pushdown(spark_mongo: Generator) -> None:
    """Verify reading with MongoDB aggregation pipeline pushdown."""
    pipeline = [{"$match": {"school": "School of Law"}}]
    df = read_mongo_collection(spark_mongo, "students", pipeline=pipeline)
    count = df.count()
    assert count > 0

    schools = {row["school"] for row in df.select("school").distinct().collect()}
    assert schools == {"School of Law"}


def test_write_and_read_mongo_roundtrip(spark_mongo: Generator) -> None:
    """Verify writing a small DataFrame to MongoDB and reading it back."""
    test_collection = "spark_integration_test_roundtrip"

    # Prepare small DataFrame
    data = [
        ("TEST_STU_01", "CET", 88.5),
        ("TEST_STU_02", "SOM", 94.0),
    ]
    df = spark_mongo.createDataFrame(data, ["student_id", "school", "score"])

    # Write to test collection
    write_mongo_collection(df, test_collection, mode="overwrite")

    # Read back and verify
    read_df = read_mongo_collection(spark_mongo, test_collection)
    assert read_df.count() == 2

    collected = {row["student_id"]: row["score"] for row in read_df.collect()}
    assert collected["TEST_STU_01"] == 88.5
    assert collected["TEST_STU_02"] == 94.0

    # Cleanup test collection
    with mongo_database_context() as db:
        db.drop_collection(test_collection)
