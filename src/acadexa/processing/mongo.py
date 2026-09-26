"""MongoDB Spark integration layer (task 7.2, rules.md §7, §19, tech_stack.md §15).

Provides:
- :func:`configure_spark_mongo_integration`: Enriches SparkRuntimeConfig with MongoDB connector
  JARs/packages and default connection options.
- :func:`get_or_create_mongo_spark_session`: Session factory with MongoDB connector preconfigured.
- :func:`read_mongo_collection`: Reads a MongoDB collection into a Spark DataFrame using DataSource V2
  (format ``mongodb``), with support for column projection and pushdown aggregation pipelines.
- :func:`write_mongo_collection`: Writes a Spark DataFrame into a MongoDB collection.
- :func:`verify_spark_mongo_read`: Verifies that a small development collection can be read into a DataFrame.

Security & Rules:
- Rules.md §7: Credentials come strictly from environment configuration; masked for all logs/diagnostics.
- Rules.md §19.1: Uses the official configured MongoDB/Spark DataSource V2 integration.
- Rules.md §19.2 & §19.3: Reads only required fields where practical, avoiding unnecessary full-collection scans.
- Rules.md §19.5: Masks MongoDB URI credentials in diagnostics and representations.
- Rules.md §19.6: Pinned connector version: ``org.mongodb.spark:mongo-spark-connector_2.13:11.1.0`` (Spark 4.x / Scala 2.13).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from acadexa.database.client import MongoDBConfig, mask_mongo_uri
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    SparkRuntimeError,
    get_or_create_spark_session,
)

DEFAULT_MONGO_SPARK_CONNECTOR: str = "org.mongodb.spark:mongo-spark-connector_2.13:11.1.0"
MONGO_SPARK_FORMAT: str = "mongodb"
READ_URI_OPTION: str = "spark.mongodb.read.connection.uri"
WRITE_URI_OPTION: str = "spark.mongodb.write.connection.uri"
DATABASE_OPTION: str = "spark.mongodb.read.database"
COLLECTION_OPTION: str = "spark.mongodb.read.collection"
AGGREGATION_PIPELINE_OPTION: str = "spark.mongodb.read.aggregation.pipeline"


def find_cached_mongo_jars() -> list[str]:
    """Locate locally cached MongoDB connector JARs in the Ivy repository cache.

    Returns:
        list[str]: Absolute paths to local JAR files if present, else empty list.
    """
    ivy_jars_dir = Path.home() / ".ivy2.5.2" / "jars"
    if not ivy_jars_dir.is_dir():
        return []

    patterns = [
        "*mongo-spark-connector*.jar",
        "*bson*.jar",
        "*mongodb-driver*.jar",
    ]
    found: set[Path] = set()
    for pattern in patterns:
        for jar_path in ivy_jars_dir.glob(pattern):
            if jar_path.is_file():
                found.add(jar_path.resolve())

    # We need at least the connector, driver, and bson jars
    has_connector = any("mongo-spark-connector" in p.name for p in found)
    has_driver = any("mongodb-driver" in p.name for p in found)
    has_bson = any("bson" in p.name for p in found)

    if has_connector and has_driver and has_bson:
        return sorted([str(p) for p in found])
    return []


def _resolve_mongo_config(uri: str | None = None, database: str | None = None) -> MongoDBConfig:
    """Resolve MongoDB configuration, passing only non-None overrides."""
    overrides: dict[str, Any] = {}
    if uri is not None:
        overrides["uri"] = uri
    if database is not None:
        overrides["database"] = database
    return MongoDBConfig.from_env(**overrides)


def configure_spark_mongo_integration(
    config: SparkRuntimeConfig | None = None,
    *,
    uri: str | None = None,
    database: str | None = None,
) -> SparkRuntimeConfig:
    """Enrich a SparkRuntimeConfig with MongoDB connector packages or local JARs.

    Args:
        config: Base runtime configuration. If None, loaded from environment.
        uri: Optional MongoDB connection URI override.
        database: Optional MongoDB database name override.

    Returns:
        SparkRuntimeConfig: Updated configuration with connector dependencies and options.
    """
    base = config or SparkRuntimeConfig.from_env()
    mongo_cfg = _resolve_mongo_config(uri=uri, database=database)

    # Resolve local cached JARs first to allow offline execution; fallback to Maven coordinate
    local_jars = find_cached_mongo_jars()
    jars = list(base.jars)
    packages = list(base.packages)

    if local_jars:
        for jar in local_jars:
            if jar not in jars:
                jars.append(jar)
    else:
        if DEFAULT_MONGO_SPARK_CONNECTOR not in packages:
            packages.append(DEFAULT_MONGO_SPARK_CONNECTOR)

    # Set default base URI configs
    extra_configs = dict(base.extra_configs)
    base_uri = f"{mongo_cfg.uri.rstrip('/')}/{mongo_cfg.database}"
    if READ_URI_OPTION not in extra_configs:
        extra_configs[READ_URI_OPTION] = base_uri
    if WRITE_URI_OPTION not in extra_configs:
        extra_configs[WRITE_URI_OPTION] = base_uri

    updated_config = SparkRuntimeConfig(
        app_name=base.app_name,
        master=base.master,
        driver_memory=base.driver_memory,
        shuffle_partitions=base.shuffle_partitions,
        default_parallelism=base.default_parallelism,
        timezone=base.timezone,
        local_dir=base.local_dir,
        ui_enabled=base.ui_enabled,
        packages=packages,
        jars=jars,
        extra_configs=extra_configs,
    )
    updated_config.validate()
    return updated_config


def get_or_create_mongo_spark_session(
    config: SparkRuntimeConfig | None = None,
    *,
    uri: str | None = None,
    database: str | None = None,
) -> Any:
    """Create or retrieve a SparkSession configured with the MongoDB Spark connector.

    Args:
        config: Base runtime configuration.
        uri: Optional MongoDB connection URI override.
        database: Optional MongoDB database override.

    Returns:
        pyspark.sql.SparkSession: Initialized SparkSession.
    """
    mongo_spark_config = configure_spark_mongo_integration(config, uri=uri, database=database)
    return get_or_create_spark_session(mongo_spark_config)


def build_collection_connection_uri(
    collection_name: str,
    *,
    database: str | None = None,
    uri: str | None = None,
) -> str:
    """Build full MongoDB connection URI including database and collection namespace.

    Args:
        collection_name: Name of target collection.
        database: Database name override.
        uri: Connection URI override.

    Returns:
        str: Fully qualified connection string `mongodb://host:port/db.collection`.
    """
    clean_col = collection_name.strip()
    if not clean_col:
        raise ValueError("collection_name must be a non-empty string.")
    mongo_cfg = _resolve_mongo_config(uri=uri, database=database)
    return f"{mongo_cfg.uri.rstrip('/')}/{mongo_cfg.database}.{clean_col}"


def read_mongo_collection(
    spark: Any,
    collection_name: str,
    *,
    database: str | None = None,
    uri: str | None = None,
    projection: list[str] | None = None,
    pipeline: list[dict[str, Any]] | None = None,
) -> Any:
    """Read a MongoDB collection into a Spark DataFrame using DataSource V2.

    Args:
        spark: Active SparkSession.
        collection_name: Name of MongoDB collection to read.
        database: Optional database override.
        uri: Optional connection URI override.
        projection: Optional column names to select (pushdown projection).
        pipeline: Optional MongoDB aggregation pipeline stages to push down.

    Returns:
        pyspark.sql.DataFrame: DataFrame representing collection data.

    Raises:
        SparkRuntimeError: If reading from MongoDB fails.
    """
    conn_uri = build_collection_connection_uri(collection_name, database=database, uri=uri)

    try:
        reader = spark.read.format(MONGO_SPARK_FORMAT).option(READ_URI_OPTION, conn_uri)

        if pipeline:
            pipeline_json = json.dumps(pipeline)
            reader = reader.option(AGGREGATION_PIPELINE_OPTION, pipeline_json)

        df = reader.load()

        if projection:
            df = df.select(*projection)

        return df
    except Exception as exc:
        masked = mask_mongo_uri(conn_uri)
        raise SparkRuntimeError(
            f"Failed to read MongoDB collection '{collection_name}' at '{masked}': {exc}"
        ) from exc


def write_mongo_collection(
    df: Any,
    collection_name: str,
    *,
    database: str | None = None,
    uri: str | None = None,
    mode: str = "append",
) -> None:
    """Write a Spark DataFrame into a MongoDB collection using DataSource V2.

    Args:
        df: Spark DataFrame to write.
        collection_name: Target MongoDB collection.
        database: Optional database override.
        uri: Optional connection URI override.
        mode: Spark write mode ('append', 'overwrite', 'error', 'ignore').

    Raises:
        SparkRuntimeError: If writing to MongoDB fails.
    """
    conn_uri = build_collection_connection_uri(collection_name, database=database, uri=uri)

    try:
        df.write.format(MONGO_SPARK_FORMAT).option(WRITE_URI_OPTION, conn_uri).mode(mode).save()
    except Exception as exc:
        masked = mask_mongo_uri(conn_uri)
        raise SparkRuntimeError(
            f"Failed to write DataFrame to MongoDB collection '{collection_name}' at '{masked}': {exc}"
        ) from exc


def verify_spark_mongo_read(
    spark: Any,
    collection_name: str = "students",
    *,
    database: str | None = None,
    uri: str | None = None,
) -> dict[str, Any]:
    """Verify that a MongoDB collection can be read into a Spark DataFrame.

    Performs a count action and retrieves the schema to confirm working integration.

    Args:
        spark: Active SparkSession.
        collection_name: Target collection to test (defaults to 'students').
        database: Optional database override.
        uri: Optional connection URI override.

    Returns:
        dict[str, Any]: Diagnostic results containing collection, row count, columns, and status.

    Raises:
        SparkRuntimeError: If verification read fails.
    """
    mongo_cfg = _resolve_mongo_config(uri=uri, database=database)
    df = read_mongo_collection(spark, collection_name, database=mongo_cfg.database, uri=mongo_cfg.uri)
    count = df.count()
    columns = df.columns

    return {
        "status": "ok",
        "collection": collection_name,
        "database": mongo_cfg.database,
        "uri": mask_mongo_uri(mongo_cfg.uri),
        "row_count": count,
        "columns": columns,
    }
