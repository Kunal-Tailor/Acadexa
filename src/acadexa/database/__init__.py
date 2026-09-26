"""MongoDB operational and serving data layer (rules.md §7, §16)."""

from acadexa.database.client import (
    DEFAULT_MONGODB_DATABASE,
    DEFAULT_MONGODB_URI,
    MongoDBConfig,
    MongoConfigError,
    MongoConnectionError,
    MongoError,
    check_connection,
    close_mongo_client,
    get_database,
    get_mongo_client,
    mask_mongo_uri,
    mongo_client_context,
    mongo_database_context,
    ping_mongodb,
)

__all__ = [
    "DEFAULT_MONGODB_DATABASE",
    "DEFAULT_MONGODB_URI",
    "MongoDBConfig",
    "MongoConfigError",
    "MongoConnectionError",
    "MongoError",
    "check_connection",
    "close_mongo_client",
    "get_database",
    "get_mongo_client",
    "mask_mongo_uri",
    "mongo_client_context",
    "mongo_database_context",
    "ping_mongodb",
]
