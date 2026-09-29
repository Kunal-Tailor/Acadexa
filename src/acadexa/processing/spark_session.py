"""PySpark local runtime configuration and session lifecycle management (task 7.1, rules.md §17).

Provides:
- :class:`SparkRuntimeConfig`: Typed configuration dataclass for local PySpark execution,
  supporting environment variable resolution, memory limits, and Windows compatibility.
- :func:`ensure_spark_environment`: Sets required worker/driver Python paths, JVM options,
  and Windows Hadoop paths before Spark initialization.
- :func:`get_or_create_spark_session`: SparkSession factory adhering to Acadexa's local runtime constraints.
- :func:`stop_spark_session`: Clean shutdown helper for Spark sessions.
- :func:`spark_session_context`: Context manager for deterministic Spark session lifecycles.
- :func:`verify_spark_runtime`: Lightweight health verification checking JVM startup, basic
  DataFrame operations, and session metadata.

Rules & Resource Constraints:
- Rules.md §17.1 & §17.2: Spark operates in local mode within the project's resource budget
  (~10-12 GB compute allocation on a 24 GB development host).
- Rules.md §17.4 & §17.5: Lazy evaluation awareness; no unnecessary actions or large driver collects.
- Tech_stack.md §13-§14: Local-first batch processing engine.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterator

from acadexa.config.loader import env, load_environment

DEFAULT_SPARK_APP_NAME: str = "Acadexa"
DEFAULT_SPARK_MASTER: str = "local[*]"
DEFAULT_SPARK_DRIVER_MEMORY: str = "4g"
DEFAULT_SPARK_SHUFFLE_PARTITIONS: int = 8
DEFAULT_SPARK_PARALLELISM: int = 4
DEFAULT_SPARK_TIMEZONE: str = "UTC"

_MEMORY_REGEX: re.Pattern[str] = re.compile(r"^\d+[kKmMgGtT]$")


class SparkRuntimeError(Exception):
    """Base exception for PySpark runtime errors in Acadexa."""


class SparkConfigError(SparkRuntimeError):
    """Raised when PySpark configuration is invalid."""


@dataclass(frozen=True)
class SparkRuntimeConfig:
    """Configuration specification for PySpark local mode runtime.

    Attributes:
        app_name: Name of the Spark application.
        master: Spark master URL (defaults to ``local[*]``).
        driver_memory: Driver heap memory string (e.g., '4g', '2048m').
        shuffle_partitions: Default partition count for joins/aggregations.
        default_parallelism: Default parallelism for RDDs/stages.
        timezone: Session SQL timezone (defaults to 'UTC').
        local_dir: Optional scratch directory for Spark shuffle/spill files.
        ui_enabled: Whether to start the Spark web UI.
        packages: List of Maven coordinates to include (e.g. connectors).
        jars: List of local JAR file paths to include.
        extra_configs: Additional Spark configuration key-value pairs.
    """

    app_name: str = DEFAULT_SPARK_APP_NAME
    master: str = DEFAULT_SPARK_MASTER
    driver_memory: str = DEFAULT_SPARK_DRIVER_MEMORY
    shuffle_partitions: int = DEFAULT_SPARK_SHUFFLE_PARTITIONS
    default_parallelism: int = DEFAULT_SPARK_PARALLELISM
    timezone: str = DEFAULT_SPARK_TIMEZONE
    local_dir: str | None = None
    ui_enabled: bool = False
    packages: list[str] = field(default_factory=list)
    jars: list[str] = field(default_factory=list)
    extra_configs: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate configuration values against constraints.

        Raises:
            SparkConfigError: If any setting violates required formats or constraints.
        """
        if not self.app_name or not self.app_name.strip():
            raise SparkConfigError("app_name must be a non-empty string.")

        if not self.master or not self.master.strip():
            raise SparkConfigError("master must be a non-empty string.")

        if not _MEMORY_REGEX.match(self.driver_memory.strip()):
            raise SparkConfigError(
                f"Invalid driver_memory '{self.driver_memory}'. Must be a number followed by k, m, g, or t (e.g. '4g')."
            )

        if self.shuffle_partitions <= 0:
            raise SparkConfigError(
                f"shuffle_partitions must be a positive integer, got {self.shuffle_partitions}."
            )

        if self.default_parallelism <= 0:
            raise SparkConfigError(
                f"default_parallelism must be a positive integer, got {self.default_parallelism}."
            )

    @classmethod
    def from_env(
        cls,
        env_file: Path | None = None,
        *,
        app_name: str | None = None,
        master: str | None = None,
        driver_memory: str | None = None,
        shuffle_partitions: int | None = None,
        default_parallelism: int | None = None,
        timezone: str | None = None,
        local_dir: str | None = None,
        ui_enabled: bool | None = None,
        packages: list[str] | None = None,
        jars: list[str] | None = None,
        extra_configs: dict[str, str] | None = None,
    ) -> SparkRuntimeConfig:
        """Construct SparkRuntimeConfig using environment variables and explicit overrides.

        Environment variables resolved:
            - ``SPARK_APP_NAME``
            - ``SPARK_MASTER``
            - ``SPARK_DRIVER_MEMORY``
            - ``SPARK_SHUFFLE_PARTITIONS``
            - ``SPARK_DEFAULT_PARALLELISM``
            - ``SPARK_TIMEZONE``
            - ``SPARK_LOCAL_DIR``
            - ``SPARK_UI_ENABLED``
        """
        load_environment(env_file)

        resolved_app = app_name or env("SPARK_APP_NAME", DEFAULT_SPARK_APP_NAME) or DEFAULT_SPARK_APP_NAME
        resolved_master = master or env("SPARK_MASTER", DEFAULT_SPARK_MASTER) or DEFAULT_SPARK_MASTER
        resolved_memory = driver_memory or env("SPARK_DRIVER_MEMORY", DEFAULT_SPARK_DRIVER_MEMORY) or DEFAULT_SPARK_DRIVER_MEMORY

        env_partitions = env("SPARK_SHUFFLE_PARTITIONS")
        resolved_partitions = (
            shuffle_partitions
            if shuffle_partitions is not None
            else (int(env_partitions) if env_partitions and env_partitions.isdigit() else DEFAULT_SPARK_SHUFFLE_PARTITIONS)
        )

        env_parallelism = env("SPARK_DEFAULT_PARALLELISM")
        resolved_parallelism = (
            default_parallelism
            if default_parallelism is not None
            else (int(env_parallelism) if env_parallelism and env_parallelism.isdigit() else DEFAULT_SPARK_PARALLELISM)
        )

        resolved_tz = timezone or env("SPARK_TIMEZONE", DEFAULT_SPARK_TIMEZONE) or DEFAULT_SPARK_TIMEZONE
        resolved_local_dir = local_dir if local_dir is not None else env("SPARK_LOCAL_DIR")

        env_ui = env("SPARK_UI_ENABLED")
        resolved_ui = (
            ui_enabled
            if ui_enabled is not None
            else (env_ui.lower() in {"1", "true", "yes"} if env_ui else False)
        )

        config = cls(
            app_name=resolved_app,
            master=resolved_master,
            driver_memory=resolved_memory,
            shuffle_partitions=resolved_partitions,
            default_parallelism=resolved_parallelism,
            timezone=resolved_tz,
            local_dir=resolved_local_dir,
            ui_enabled=resolved_ui,
            packages=list(packages or []),
            jars=list(jars or []),
            extra_configs=dict(extra_configs or {}),
        )
        config.validate()
        return config


def ensure_spark_environment() -> None:
    """Prepare environment variables for PySpark execution on the local host.

    Handles:
    - Worker and driver Python executable resolution (`PYSPARK_PYTHON`, `PYSPARK_DRIVER_PYTHON`).
    - Windows Hadoop environment resolution (`HADOOP_HOME`, PATH augmentation).
    - Java runtime location detection (`JAVA_HOME`).
    """
    # 1. Python executable: prevent worker/driver mismatches and spaces-in-path issues on Windows
    if "PYSPARK_PYTHON" not in os.environ:
        os.environ["PYSPARK_PYTHON"] = "python"
    if "PYSPARK_DRIVER_PYTHON" not in os.environ:
        os.environ["PYSPARK_DRIVER_PYTHON"] = "python"

    # 2. Windows-specific Hadoop configuration
    if sys.platform == "win32":
        hadoop_home = os.environ.get("HADOOP_HOME")
        if not hadoop_home or not Path(hadoop_home).is_dir():
            candidate_paths = [
                Path("C:/hadoop"),
                Path(__file__).resolve().parents[3] / "tools" / "hadoop",
            ]
            for candidate in candidate_paths:
                if (candidate / "bin" / "winutils.exe").is_file():
                    os.environ["HADOOP_HOME"] = str(candidate)
                    hadoop_bin = str(candidate / "bin")
                    current_path = os.environ.get("PATH", "")
                    if hadoop_bin not in current_path:
                        os.environ["PATH"] = f"{hadoop_bin};{current_path}"
                    break

    # 3. Java home detection if unset
    if "JAVA_HOME" not in os.environ:
        if sys.platform == "win32":
            jdk_candidates = [
                Path("C:/Program Files/Java/jdk-25.0.2"),
                Path("C:/Program Files/Java/latest"),
            ]
            for jdk in jdk_candidates:
                if (jdk / "bin" / "java.exe").is_file():
                    os.environ["JAVA_HOME"] = str(jdk)
                    break


def get_or_create_spark_session(config: SparkRuntimeConfig | None = None) -> Any:
    """Create a new SparkSession or retrieve an existing active session.

    Args:
        config: Runtime configuration options. If None, defaults are loaded from environment.

    Returns:
        pyspark.sql.SparkSession: The active SparkSession instance.

    Raises:
        SparkRuntimeError: If PySpark is not installed or initialization fails.
    """
    ensure_spark_environment()

    resolved_config = config or SparkRuntimeConfig.from_env()
    resolved_config.validate()

    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise SparkRuntimeError(
            "PySpark is not installed. Please install pyspark to run batch processing."
        ) from exc

    builder = (
        SparkSession.builder.appName(resolved_config.app_name)
        .master(resolved_config.master)
        .config("spark.driver.memory", resolved_config.driver_memory)
        .config("spark.sql.shuffle.partitions", str(resolved_config.shuffle_partitions))
        .config("spark.default.parallelism", str(resolved_config.default_parallelism))
        .config("spark.sql.session.timeZone", resolved_config.timezone)
        .config("spark.ui.enabled", "true" if resolved_config.ui_enabled else "false")
    )

    if resolved_config.local_dir:
        builder = builder.config("spark.local.dir", resolved_config.local_dir)

    if resolved_config.packages:
        builder = builder.config("spark.jars.packages", ",".join(resolved_config.packages))

    jars_to_load = list(resolved_config.jars)
    if not jars_to_load:
        try:
            from acadexa.processing.mongo import find_cached_mongo_jars

            jars_to_load = find_cached_mongo_jars()
        except Exception:
            pass

    if jars_to_load:
        builder = builder.config("spark.jars", ",".join(jars_to_load))

    for key, value in resolved_config.extra_configs.items():
        builder = builder.config(key, value)

    try:
        spark = builder.getOrCreate()
    except Exception as exc:
        raise SparkRuntimeError(f"Failed to start local SparkSession: {exc}") from exc

    # Set log level to WARN to keep logs focused and clean
    try:
        spark.sparkContext.setLogLevel("WARN")
    except Exception:
        pass

    return spark


def stop_spark_session(spark: Any = None) -> None:
    """Stop the provided SparkSession or the active session.

    Args:
        spark: SparkSession instance to stop. If None, retrieves the active session if any.
    """
    try:
        if spark is not None:
            spark.stop()
        else:
            from pyspark.sql import SparkSession

            active = SparkSession.getActiveSession()
            if active is not None:
                active.stop()
    except Exception:
        pass


@contextmanager
def spark_session_context(config: SparkRuntimeConfig | None = None) -> Iterator[Any]:
    """Context manager for managing SparkSession lifecycle deterministically.

    Yields:
        pyspark.sql.SparkSession: Initialized active SparkSession.
    """
    spark = get_or_create_spark_session(config)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


def verify_spark_runtime(spark: Any) -> dict[str, Any]:
    """Verify that the SparkSession is healthy and capable of executing operations.

    Executes a minimal distributed computation and gathers session diagnostic metadata.

    Args:
        spark: An active SparkSession instance.

    Returns:
        dict[str, Any]: Diagnostics including Spark version, master, app name, and verification row count.

    Raises:
        SparkRuntimeError: If the verification query fails.
    """
    try:
        test_df = spark.range(5)
        row_count = test_df.count()
        if row_count != 5:
            raise SparkRuntimeError(f"Spark range computation unexpected count: {row_count} (expected 5)")

        sc = spark.sparkContext
        conf = spark.conf

        return {
            "status": "ok",
            "spark_version": spark.version,
            "python_version": sys.version.split()[0],
            "master": sc.master,
            "app_name": sc.appName,
            "driver_memory": conf.get("spark.driver.memory", "default"),
            "shuffle_partitions": conf.get("spark.sql.shuffle.partitions", "default"),
            "timezone": conf.get("spark.sql.session.timeZone", "default"),
            "ui_web_url": sc.uiWebUrl,
            "test_row_count": row_count,
        }
    except Exception as exc:
        raise SparkRuntimeError(f"Spark runtime health check failed: {exc}") from exc
