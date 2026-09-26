"""Unit tests for MongoDB configuration and connection handling (task 6.1, rules.md §7, §16)."""

import os
from pathlib import Path
import pytest

from acadexa.database import (
    DEFAULT_MONGODB_DATABASE,
    DEFAULT_MONGODB_URI,
    MongoDBConfig,
    MongoConfigError,
    MongoConnectionError,
    check_connection,
    close_mongo_client,
    get_database,
    get_mongo_client,
    mask_mongo_uri,
    mongo_client_context,
    mongo_database_context,
    ping_mongodb,
)


def test_mask_mongo_uri() -> None:
    """Verify password masking in various MongoDB URI formats."""
    # Standard URI with password
    uri1 = "mongodb://user:supersecret@localhost:27017/acadexa"
    assert mask_mongo_uri(uri1) == "mongodb://user:****@localhost:27017/acadexa"

    # SRV URI with password and options
    uri2 = "mongodb+srv://admin:pass123@cluster0.abc.mongodb.net/acadexa?retryWrites=true"
    assert mask_mongo_uri(uri2) == "mongodb+srv://admin:****@cluster0.abc.mongodb.net/acadexa?retryWrites=true"

    # URI without credentials
    uri3 = "mongodb://localhost:27017"
    assert mask_mongo_uri(uri3) == "mongodb://localhost:27017"

    # Edge cases
    assert mask_mongo_uri("") == ""
    assert mask_mongo_uri(None) == ""  # type: ignore


def test_mongodb_config_defaults() -> None:
    """Verify default MongoDB configuration parameters and representation."""
    config = MongoDBConfig()
    assert config.uri == DEFAULT_MONGODB_URI
    assert config.database == DEFAULT_MONGODB_DATABASE
    assert config.server_selection_timeout_ms == 5000
    assert config.max_pool_size == 100
    assert config.min_pool_size == 0
    assert config.appname == "acadexa"
    assert config.retry_writes is True

    # Representation should use masked URI
    secret_config = MongoDBConfig(uri="mongodb://admin:secretpass@localhost:27017")
    assert "secretpass" not in repr(secret_config)
    assert "****" in repr(secret_config)


def test_mongodb_config_validation() -> None:
    """Verify validation logic for invalid configuration values."""
    # Invalid URI schemes
    with pytest.raises(MongoConfigError, match="Invalid MongoDB URI scheme"):
        MongoDBConfig(uri="http://localhost:27017")

    with pytest.raises(MongoConfigError, match="non-empty string"):
        MongoDBConfig(uri="   ")

    # Invalid database names
    with pytest.raises(MongoConfigError, match="non-empty string"):
        MongoDBConfig(database="")

    for bad_char in ("/", "\\", ".", '"', "*", "<", ">", ":", "|", "?", "$", " "):
        with pytest.raises(MongoConfigError, match="illegal character"):
            MongoDBConfig(database=f"test{bad_char}db")

    with pytest.raises(MongoConfigError, match="exceeds 63 bytes"):
        MongoDBConfig(database="a" * 64)

    # Invalid timeouts and pool sizes
    with pytest.raises(MongoConfigError, match="positive integer"):
        MongoDBConfig(server_selection_timeout_ms=-100)

    with pytest.raises(MongoConfigError, match="positive integer"):
        MongoDBConfig(server_selection_timeout_ms=0)

    with pytest.raises(MongoConfigError, match="cannot exceed max_pool_size"):
        MongoDBConfig(min_pool_size=50, max_pool_size=10)


def test_mongodb_config_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify loading configuration from environment variables and .env files."""
    # Clean env
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    monkeypatch.delenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", raising=False)

    # Defaults when env is empty
    cfg1 = MongoDBConfig.from_env()
    assert cfg1.uri == DEFAULT_MONGODB_URI
    assert cfg1.database == DEFAULT_MONGODB_DATABASE

    # With environment variables
    monkeypatch.setenv("MONGODB_URI", "mongodb://testuser:testpass@localhost:27018")
    monkeypatch.setenv("MONGODB_DATABASE", "custom_acadexa")
    monkeypatch.setenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "3000")

    cfg2 = MongoDBConfig.from_env()
    assert cfg2.uri == "mongodb://testuser:testpass@localhost:27018"
    assert cfg2.database == "custom_acadexa"
    assert cfg2.server_selection_timeout_ms == 3000
    assert cfg2.masked_uri == "mongodb://testuser:****@localhost:27018"

    # Programmatic override takes precedence
    cfg3 = MongoDBConfig.from_env(database="overridden_db")
    assert cfg3.database == "overridden_db"

    # From custom env file
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "MONGODB_URI=mongodb://envfile_user:envfile_pass@127.0.0.1:27017\n"
        "MONGODB_DATABASE=from_file_db\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)

    cfg4 = MongoDBConfig.from_env(env_file=env_file)
    assert cfg4.uri == "mongodb://envfile_user:envfile_pass@127.0.0.1:27017"
    assert cfg4.database == "from_file_db"


def test_get_mongo_client_and_database() -> None:
    """Verify client factory and database resolution."""
    config = MongoDBConfig(database="test_acadexa")
    client = get_mongo_client(config)
    try:
        db = get_database(config, client=client)
        assert db.name == "test_acadexa"
    finally:
        close_mongo_client(client)


def test_check_connection_and_ping_live() -> None:
    """Verify live connectivity check and ping diagnostics against running MongoDB."""
    config = MongoDBConfig.from_env()
    # Check boolean health check
    is_live = check_connection(config=config, timeout_ms=2000)
    assert is_live is True

    # Check ping diagnostic metadata
    ping_res = ping_mongodb(config=config, timeout_ms=2000)
    assert ping_res["status"] == "connected"
    assert ping_res["database"] == config.database
    assert ping_res["uri"] == config.masked_uri
    assert isinstance(ping_res["latency_ms"], float)
    assert ping_res["latency_ms"] >= 0.0
    assert "version" in ping_res["server_version"] or ping_res["server_version"] != "unknown"


def test_unreachable_connection_handling() -> None:
    """Verify graceful handling and masked URI when MongoDB host is unreachable."""
    # Point to an unused non-responsive port
    unreachable_cfg = MongoDBConfig(
        uri="mongodb://secret_user:super_secret_pw@127.0.0.1:29999",
        database="acadexa",
        server_selection_timeout_ms=50,
        connect_timeout_ms=50,
    )

    # Boolean check returns False without raising
    is_live = check_connection(config=unreachable_cfg, timeout_ms=50)
    assert is_live is False

    # ping_mongodb raises MongoConnectionError with credentials masked
    with pytest.raises(MongoConnectionError) as exc_info:
        ping_mongodb(config=unreachable_cfg, timeout_ms=50)

    err_msg = str(exc_info.value)
    assert "super_secret_pw" not in err_msg
    assert "secret_user:****@127.0.0.1:29999" in err_msg


def test_mongo_client_contexts() -> None:
    """Verify context managers safely yield and close clients."""
    config = MongoDBConfig.from_env()

    # Client context
    with mongo_client_context(config) as client:
        assert client is not None
        assert check_connection(client=client) is True

    # Database context
    with mongo_database_context(config) as db:
        assert db.name == config.database
