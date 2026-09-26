"""Unit tests for MongoDB Spark configuration and integration helpers (task 7.2, rules.md §7, §19)."""

from __future__ import annotations

import pytest

from acadexa.database.client import mask_mongo_uri
from acadexa.processing import (
    DEFAULT_MONGO_SPARK_CONNECTOR,
    MONGO_SPARK_FORMAT,
    SparkRuntimeConfig,
    build_collection_connection_uri,
    configure_spark_mongo_integration,
)


def test_mongo_spark_constants() -> None:
    """Verify default connector format and maven coordinates."""
    assert MONGO_SPARK_FORMAT == "mongodb"
    assert "mongo-spark-connector" in DEFAULT_MONGO_SPARK_CONNECTOR
    assert "2.13" in DEFAULT_MONGO_SPARK_CONNECTOR
    assert "11.1.0" in DEFAULT_MONGO_SPARK_CONNECTOR


def test_build_collection_connection_uri_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify constructing collection connection URI with defaults."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "acadexa")

    uri = build_collection_connection_uri("students")
    assert uri == "mongodb://localhost:27017/acadexa.students"


def test_build_collection_connection_uri_custom() -> None:
    """Verify constructing connection URI with explicit database and URI overrides."""
    uri = build_collection_connection_uri(
        "courses",
        database="test_db",
        uri="mongodb://customhost:27018",
    )
    assert uri == "mongodb://customhost:27018/test_db.courses"


def test_build_collection_connection_uri_empty_raises() -> None:
    """Verify empty collection name raises ValueError."""
    with pytest.raises(ValueError, match="collection_name must be a non-empty string"):
        build_collection_connection_uri("   ")


def test_configure_spark_mongo_integration_enriches_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify configure_spark_mongo_integration adds connector dependencies and read/write URIs."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://testuser:secretpass@mongo.internal:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "acadexa_prod")

    base_config = SparkRuntimeConfig(
        app_name="TestApp",
        master="local[2]",
        driver_memory="2g",
    )

    enriched = configure_spark_mongo_integration(base_config)
    assert enriched.app_name == "TestApp"
    assert enriched.master == "local[2]"
    assert enriched.driver_memory == "2g"

    # Must contain connector either via local jars or via packages
    assert len(enriched.jars) > 0 or DEFAULT_MONGO_SPARK_CONNECTOR in enriched.packages

    # Base read/write URIs must be set
    assert "spark.mongodb.read.connection.uri" in enriched.extra_configs
    assert "spark.mongodb.write.connection.uri" in enriched.extra_configs
    assert "acadexa_prod" in enriched.extra_configs["spark.mongodb.read.connection.uri"]

    # Verify credentials masking works on connection URI
    read_uri = enriched.extra_configs["spark.mongodb.read.connection.uri"]
    masked = mask_mongo_uri(read_uri)
    assert "secretpass" not in masked
    assert "***@" in masked
