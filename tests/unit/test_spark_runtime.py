"""Unit tests for PySpark local mode runtime and session management (task 7.1, rules.md §17)."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from acadexa.processing import (
    DEFAULT_SPARK_APP_NAME,
    DEFAULT_SPARK_DRIVER_MEMORY,
    DEFAULT_SPARK_MASTER,
    DEFAULT_SPARK_PARALLELISM,
    DEFAULT_SPARK_SHUFFLE_PARTITIONS,
    DEFAULT_SPARK_TIMEZONE,
    SparkConfigError,
    SparkRuntimeConfig,
    SparkRuntimeError,
    ensure_spark_environment,
    get_or_create_spark_session,
    spark_session_context,
    stop_spark_session,
    verify_spark_runtime,
)


def test_spark_runtime_config_defaults() -> None:
    """Verify default parameters of SparkRuntimeConfig."""
    config = SparkRuntimeConfig()
    assert config.app_name == DEFAULT_SPARK_APP_NAME
    assert config.master == DEFAULT_SPARK_MASTER
    assert config.driver_memory == DEFAULT_SPARK_DRIVER_MEMORY
    assert config.shuffle_partitions == DEFAULT_SPARK_SHUFFLE_PARTITIONS
    assert config.default_parallelism == DEFAULT_SPARK_PARALLELISM
    assert config.timezone == DEFAULT_SPARK_TIMEZONE
    assert config.local_dir is None
    assert config.ui_enabled is False
    assert config.packages == []
    assert config.jars == []
    assert config.extra_configs == {}
    config.validate()


def test_spark_runtime_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify constructing configuration from environment variables and overrides."""
    monkeypatch.setenv("SPARK_APP_NAME", "EnvApp")
    monkeypatch.setenv("SPARK_MASTER", "local[4]")
    monkeypatch.setenv("SPARK_DRIVER_MEMORY", "2g")
    monkeypatch.setenv("SPARK_SHUFFLE_PARTITIONS", "16")
    monkeypatch.setenv("SPARK_DEFAULT_PARALLELISM", "8")
    monkeypatch.setenv("SPARK_TIMEZONE", "UTC")
    monkeypatch.setenv("SPARK_UI_ENABLED", "true")

    config = SparkRuntimeConfig.from_env()
    assert config.app_name == "EnvApp"
    assert config.master == "local[4]"
    assert config.driver_memory == "2g"
    assert config.shuffle_partitions == 16
    assert config.default_parallelism == 8
    assert config.timezone == "UTC"
    assert config.ui_enabled is True

    # Test explicit override takes precedence
    override_config = SparkRuntimeConfig.from_env(
        master="local[1]",
        driver_memory="1g",
        shuffle_partitions=4,
    )
    assert override_config.master == "local[1]"
    assert override_config.driver_memory == "1g"
    assert override_config.shuffle_partitions == 4


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"app_name": ""}, "app_name must be a non-empty string"),
        ({"master": "  "}, "master must be a non-empty string"),
        ({"driver_memory": "invalid"}, "Invalid driver_memory"),
        ({"driver_memory": "4x"}, "Invalid driver_memory"),
        ({"shuffle_partitions": 0}, "shuffle_partitions must be a positive integer"),
        ({"shuffle_partitions": -2}, "shuffle_partitions must be a positive integer"),
        ({"default_parallelism": 0}, "default_parallelism must be a positive integer"),
    ],
)
def test_spark_runtime_config_validation_failures(kwargs: dict, match: str) -> None:
    """Verify validation raises SparkConfigError for invalid parameter configurations."""
    config = SparkRuntimeConfig(**kwargs)
    with pytest.raises(SparkConfigError, match=match):
        config.validate()


def test_ensure_spark_environment() -> None:
    """Verify environment setup populates Python and Hadoop variables."""
    ensure_spark_environment()
    assert "PYSPARK_PYTHON" in os.environ
    assert "PYSPARK_DRIVER_PYTHON" in os.environ
    if os.name == "nt":
        # On Windows, HADOOP_HOME must be present and directory must exist if configured
        hadoop_home = os.environ.get("HADOOP_HOME")
        assert hadoop_home is not None
        assert Path(hadoop_home).is_dir()
        assert (Path(hadoop_home) / "bin" / "winutils.exe").is_file()


def test_spark_session_context_and_verification() -> None:
    """Verify starting local SparkSession, running verification check, and stopping cleanly."""
    test_config = SparkRuntimeConfig(
        app_name="AcadexaTestRuntime",
        master="local[2]",
        driver_memory="1g",
        shuffle_partitions=2,
        default_parallelism=2,
        ui_enabled=False,
    )

    with spark_session_context(test_config) as spark:
        # Verify active session instance
        assert spark is not None
        assert spark.sparkContext.appName == "AcadexaTestRuntime"
        assert spark.sparkContext.master.startswith("local")

        # Run verification helper
        diag = verify_spark_runtime(spark)
        assert diag["status"] == "ok"
        assert diag["app_name"] == "AcadexaTestRuntime"
        assert diag["test_row_count"] == 5
        assert "spark_version" in diag
        assert "python_version" in diag

        # Verify DataFrame creation and transformations
        data = [("CET", 101, 85.0), ("SOM", 102, 92.5), ("CET", 103, 78.0)]
        df = spark.createDataFrame(data, ["school_id", "course_id", "score"])

        assert df.count() == 3
        filtered = df.filter(df["score"] >= 80.0)
        assert filtered.count() == 2

        # Grouping and aggregation check
        summary = df.groupBy("school_id").count().collect()
        summary_dict = {row["school_id"]: row["count"] for row in summary}
        assert summary_dict == {"CET": 2, "SOM": 1}

    # After context exit, session should be stopped
    from pyspark.sql import SparkSession
    active = SparkSession.getActiveSession()
    assert active is None or active._jsc.sc().isStopped()


def test_stop_spark_session_idempotent() -> None:
    """Verify stop_spark_session can be called safely even when no session is active."""
    stop_spark_session(None)
