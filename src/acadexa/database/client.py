"""MongoDB client setup, configuration, and connection management (task 6.1, rules.md §7, §16).

Provides:
- :class:`MongoDBConfig`: Environment-driven configuration dataclass with
  safe default local fallbacks, validation, and credentials masking.
- :func:`get_mongo_client`: Client factory with configurable pool and timeout options.
- :func:`get_database`: Database access helper using configured database name.
- :func:`check_connection`: Non-raising boolean health check.
- :func:`ping_mongodb`: Diagnostic ping measuring latency and server version.
- :func:`close_mongo_client`: Clean resource cleanup.
- :func:`mongo_client_context` and :func:`mongo_database_context`: Context managers
  for safe deterministic client lifecycles.

Rules & Security:
- Rules.md §7: Credentials must come from environment configuration or ``.env``.
  Passwords and secrets are never committed or exposed in source code.
- Rules.md §7 & §19: URI masking ensures credentials are never logged or exposed
  in exception messages or string representations.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

import pymongo
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from acadexa.config.loader import load_environment

DEFAULT_MONGODB_URI: str = "mongodb://localhost:27017"
DEFAULT_MONGODB_DATABASE: str = "acadexa"

_INVALID_DB_CHARS: set[str] = {"/", "\\", ".", '"', "*", "<", ">", ":", "|", "?", "$", "\0", " "}


class MongoError(Exception):
    """Base exception for Acadexa database operations."""


class MongoConfigError(MongoError):
    """Raised when MongoDB configuration is invalid or missing."""


class MongoConnectionError(MongoError):
    """Raised when connecting or pinging MongoDB fails."""


def mask_mongo_uri(uri: str) -> str:
    """Mask password credentials in a MongoDB URI string for safe logging.

    Args:
        uri: Raw MongoDB connection string.

    Returns:
        Connection string with password replaced by ``****``.
    """
    if not isinstance(uri, str) or not uri:
        return ""
    try:
        parts = urlsplit(uri)
        if parts.password:
            # Replace password in netloc
            safe_netloc = parts.netloc.replace(f":{parts.password}@", ":****@")
            return urlunsplit((parts.scheme, safe_netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        # Fallback if URL parsing encounters non-standard scheme
        pass
    return uri


@dataclass(frozen=True)
class MongoDBConfig:
    """MongoDB connection configuration loaded from environment (rules.md §7).

    Attributes:
        uri: Connection URI string (defaults to ``MONGODB_URI`` or ``mongodb://localhost:27017``).
        database: Target database name (defaults to ``MONGODB_DATABASE`` or ``acadexa``).
        server_selection_timeout_ms: Timeout in milliseconds for server discovery (default 5000).
        connect_timeout_ms: Timeout in milliseconds for initial socket connection (default 5000).
        socket_timeout_ms: Timeout in milliseconds for socket operations (default 30000).
        max_pool_size: Maximum connection pool size (default 100).
        min_pool_size: Minimum connection pool size (default 0).
        appname: Application name identifying connections in MongoDB logs (default 'acadexa').
        retry_writes: Whether to enable retryable writes (default True).
        retry_reads: Whether to enable retryable reads (default True).
    """

    uri: str = DEFAULT_MONGODB_URI
    database: str = DEFAULT_MONGODB_DATABASE
    server_selection_timeout_ms: int = 5000
    connect_timeout_ms: int = 5000
    socket_timeout_ms: int = 30000
    max_pool_size: int = 100
    min_pool_size: int = 0
    appname: str = "acadexa"
    retry_writes: bool = True
    retry_reads: bool = True

    def __post_init__(self) -> None:
        self.validate()

    @property
    def masked_uri(self) -> str:
        """Return URI with password credentials masked."""
        return mask_mongo_uri(self.uri)

    def validate(self) -> None:
        """Validate configuration values."""
        if not isinstance(self.uri, str) or not self.uri.strip():
            raise MongoConfigError("MongoDB URI must be a non-empty string.")

        stripped_uri = self.uri.strip()
        if not (stripped_uri.startswith("mongodb://") or stripped_uri.startswith("mongodb+srv://")):
            raise MongoConfigError(
                f"Invalid MongoDB URI scheme: '{self.masked_uri}'. Must start with 'mongodb://' or 'mongodb+srv://'."
            )

        if not isinstance(self.database, str) or not self.database.strip():
            raise MongoConfigError("MongoDB database name must be a non-empty string.")

        db_name = self.database.strip()
        for char in db_name:
            if char in _INVALID_DB_CHARS:
                raise MongoConfigError(
                    f"MongoDB database name '{db_name}' contains illegal character '{char}'."
                )

        if len(db_name.encode("utf-8")) > 63:
            raise MongoConfigError(
                f"MongoDB database name '{db_name}' exceeds 63 bytes limit."
            )

        for name, val in (
            ("server_selection_timeout_ms", self.server_selection_timeout_ms),
            ("connect_timeout_ms", self.connect_timeout_ms),
            ("socket_timeout_ms", self.socket_timeout_ms),
            ("max_pool_size", self.max_pool_size),
        ):
            if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                raise MongoConfigError(f"{name} must be a positive integer, got {val!r}")

        if not isinstance(self.min_pool_size, int) or isinstance(self.min_pool_size, bool) or self.min_pool_size < 0:
            raise MongoConfigError(f"min_pool_size must be a non-negative integer, got {self.min_pool_size!r}")

        if self.min_pool_size > self.max_pool_size:
            raise MongoConfigError(
                f"min_pool_size ({self.min_pool_size}) cannot exceed max_pool_size ({self.max_pool_size})."
            )

    @classmethod
    def from_env(
        cls,
        env_file: Path | str | None = None,
        **overrides: Any,
    ) -> MongoDBConfig:
        """Load MongoDB configuration from environment variables and optional .env file.

        Args:
            env_file: Optional path to ``.env`` file.
            **overrides: Explicit keyword arguments overriding environment variables.

        Returns:
            Validated :class:`MongoDBConfig` instance.
        """
        if env_file is not None:
            load_environment(Path(env_file))
        else:
            load_environment()

        env_uri = os.environ.get("MONGODB_URI", DEFAULT_MONGODB_URI)
        env_db = os.environ.get("MONGODB_DATABASE", DEFAULT_MONGODB_DATABASE)

        config_kwargs: dict[str, Any] = {
            "uri": env_uri,
            "database": env_db,
        }

        # Optional integer overrides from environment
        if "MONGODB_SERVER_SELECTION_TIMEOUT_MS" in os.environ:
            try:
                config_kwargs["server_selection_timeout_ms"] = int(
                    os.environ["MONGODB_SERVER_SELECTION_TIMEOUT_MS"]
                )
            except ValueError as exc:
                raise MongoConfigError(
                    f"Invalid MONGODB_SERVER_SELECTION_TIMEOUT_MS: {os.environ['MONGODB_SERVER_SELECTION_TIMEOUT_MS']}"
                ) from exc

        if "MONGODB_MAX_POOL_SIZE" in os.environ:
            try:
                config_kwargs["max_pool_size"] = int(os.environ["MONGODB_MAX_POOL_SIZE"])
            except ValueError as exc:
                raise MongoConfigError(
                    f"Invalid MONGODB_MAX_POOL_SIZE: {os.environ['MONGODB_MAX_POOL_SIZE']}"
                ) from exc

        # Apply programmatic keyword overrides
        config_kwargs.update(overrides)

        return cls(**config_kwargs)

    def get_client_kwargs(self) -> dict[str, Any]:
        """Return kwargs dictionary suitable for passing to pymongo.MongoClient."""
        return {
            "serverSelectionTimeoutMS": self.server_selection_timeout_ms,
            "connectTimeoutMS": self.connect_timeout_ms,
            "socketTimeoutMS": self.socket_timeout_ms,
            "maxPoolSize": self.max_pool_size,
            "minPoolSize": self.min_pool_size,
            "appName": self.appname,
            "retryWrites": self.retry_writes,
            "retryReads": self.retry_reads,
        }

    def __repr__(self) -> str:
        return (
            f"MongoDBConfig(uri={self.masked_uri!r}, database={self.database!r}, "
            f"server_selection_timeout_ms={self.server_selection_timeout_ms})"
        )


def get_mongo_client(
    config: MongoDBConfig | None = None,
    **kwargs: Any,
) -> pymongo.MongoClient:
    """Create and return a pymongo.MongoClient instance.

    Args:
        config: Optional MongoDBConfig. When omitted, loaded from environment via
            :meth:`MongoDBConfig.from_env`.
        **kwargs: Additional parameters passed to :class:`pymongo.MongoClient`.

    Returns:
        Connected or configured :class:`pymongo.MongoClient`.

    Raises:
        MongoConfigError: if configuration is invalid.
    """
    if config is None:
        config = MongoDBConfig.from_env()

    client_params = config.get_client_kwargs()
    client_params.update(kwargs)

    try:
        return pymongo.MongoClient(config.uri, **client_params)
    except PyMongoError as exc:
        raise MongoConfigError(
            f"Failed to initialize MongoClient for '{config.masked_uri}': {exc}"
        ) from exc


def get_database(
    config: MongoDBConfig | None = None,
    client: pymongo.MongoClient | None = None,
) -> pymongo.database.Database:
    """Get the target MongoDB Database instance.

    Args:
        config: Optional MongoDBConfig. Loaded from environment if omitted.
        client: Optional existing MongoClient. Initialized if omitted.

    Returns:
        :class:`pymongo.database.Database` for the configured database name.
    """
    if config is None:
        config = MongoDBConfig.from_env()

    active_client = client if client is not None else get_mongo_client(config)
    return active_client[config.database]


def check_connection(
    client: pymongo.MongoClient | None = None,
    config: MongoDBConfig | None = None,
    timeout_ms: int | None = None,
) -> bool:
    """Check whether MongoDB server is reachable via a ping command.

    Args:
        client: Optional existing MongoClient.
        config: Optional configuration.
        timeout_ms: Optional server selection timeout override in milliseconds.

    Returns:
        True if reachable and responding, False otherwise.
    """
    owns_client = False
    active_client = client

    try:
        if active_client is None:
            if config is None:
                config = MongoDBConfig.from_env()
            if timeout_ms is not None:
                active_client = get_mongo_client(config, serverSelectionTimeoutMS=timeout_ms)
            else:
                active_client = get_mongo_client(config)
            owns_client = True

        active_client.admin.command("ping")
        return True
    except (PyMongoError, MongoError):
        return False
    finally:
        if owns_client and active_client is not None:
            close_mongo_client(active_client)


def ping_mongodb(
    client: pymongo.MongoClient | None = None,
    config: MongoDBConfig | None = None,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    """Ping MongoDB server and return diagnostic connection metadata.

    Args:
        client: Optional existing MongoClient.
        config: Optional configuration.
        timeout_ms: Optional server selection timeout override in milliseconds.

    Returns:
        Diagnostic dictionary containing connection status, latency, server version,
        and database details.

    Raises:
        MongoConnectionError: if the server is unreachable or fails to respond.
    """
    if config is None:
        config = MongoDBConfig.from_env()

    owns_client = False
    active_client = client

    try:
        if active_client is None:
            opts: dict[str, Any] = {}
            if timeout_ms is not None:
                opts["serverSelectionTimeoutMS"] = timeout_ms
            active_client = get_mongo_client(config, **opts)
            owns_client = True

        t0 = time.perf_counter()
        ping_res = active_client.admin.command("ping")
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        server_info: dict[str, Any] = {}
        try:
            server_info = active_client.server_info()
        except PyMongoError:
            pass

        return {
            "status": "connected",
            "database": config.database,
            "uri": config.masked_uri,
            "latency_ms": latency_ms,
            "server_version": server_info.get("version", "unknown"),
            "ping_response": ping_res,
        }
    except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
        raise MongoConnectionError(
            f"Cannot connect to MongoDB at '{config.masked_uri}': server selection timed out. ({exc})"
        ) from exc
    except PyMongoError as exc:
        raise MongoConnectionError(
            f"MongoDB ping failed for '{config.masked_uri}': {exc}"
        ) from exc
    finally:
        if owns_client and active_client is not None:
            close_mongo_client(active_client)


def close_mongo_client(client: pymongo.MongoClient | None) -> None:
    """Safely close a MongoClient instance."""
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


@contextmanager
def mongo_client_context(
    config: MongoDBConfig | None = None,
    **kwargs: Any,
) -> Iterator[pymongo.MongoClient]:
    """Context manager providing a managed MongoClient that closes on exit.

    Args:
        config: Optional configuration.
        **kwargs: Additional parameters passed to MongoClient.

    Yields:
        Open :class:`pymongo.MongoClient` instance.
    """
    client = get_mongo_client(config, **kwargs)
    try:
        yield client
    finally:
        close_mongo_client(client)


@contextmanager
def mongo_database_context(
    config: MongoDBConfig | None = None,
    **kwargs: Any,
) -> Iterator[pymongo.database.Database]:
    """Context manager providing a managed Database instance that closes client on exit.

    Args:
        config: Optional configuration.
        **kwargs: Additional parameters passed to MongoClient.

    Yields:
        :class:`pymongo.database.Database` for the configured database.
    """
    if config is None:
        config = MongoDBConfig.from_env()

    with mongo_client_context(config, **kwargs) as client:
        yield client[config.database]
