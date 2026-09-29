"""Shared dashboard data-access layer (Task 11.1, rules.md §23, §26).

The single place where Streamlit code reaches MongoDB serving data (core
operational collections + gold analytical collections). Heavy joins and
large-scale transformations stay in Spark; this layer performs bounded,
indexed lookups only.

Failure contract (rules.md §23.5): database failures return a controlled
``(records, error)`` pair with ``records == []``. Values are never
fabricated when the database is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from acadexa.database import (
    MongoDBConfig,
    check_connection,
    close_mongo_client,
    get_database,
    get_mongo_client,
)
from acadexa.database.collections import ALL_MANAGED_COLLECTIONS
from acadexa.dashboard.config import DashboardConfig

logger = logging.getLogger(__name__)


class DataAccessError(Exception):
    """Raised only for programmer errors (unknown collection); runtime DB
    failures are returned as controlled error strings instead."""


def _check(condition: bool, message: str) -> None:
    """Raise DataAccessError with ``message`` when ``condition`` is false."""
    if not condition:
        raise DataAccessError(message)


class DashboardDataAccess:
    """Bounded MongoDB reads for the Streamlit dashboard.

    Args:
        config: Dashboard configuration (MongoDB settings from environment).
        db: Optional pre-opened database handle (used by tests to inject a
            double without opening a real connection).
    """

    def __init__(
        self, config: DashboardConfig | None = None, db: Any | None = None
    ) -> None:
        self.config = config or DashboardConfig.from_env()
        self._db = db
        self._client: Any | None = None
        self._last_error: str | None = None

    def _database(self) -> Any:
        """Return the database handle, opening a client on first use."""
        if self._db is not None:
            return self._db
        cfg: MongoDBConfig = self.config.database
        self._client = get_mongo_client(cfg)
        self._db = get_database(cfg, client=self._client)
        return self._db

    def close(self) -> None:
        """Release the MongoDB client opened by this instance, if any."""
        if self._client is not None:
            close_mongo_client(self._client)
            self._client = None
            self._db = None

    @property
    def last_error(self) -> str | None:
        """Most recent controlled database error, if any."""
        return self._last_error

    def is_reachable(self) -> bool:
        """Non-raising MongoDB reachability check."""
        return check_connection(config=self.config.database)

    def fetch(
        self,
        collection: str,
        scope_filter: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch up to ``limit`` documents with an optional scope filter.

        Returns:
            ``(records, error)`` where ``error`` is None on success. On any
            database failure ``records`` is ``[]`` and ``error`` describes
            the controlled failure state for the UI.
        """
        _check(
            collection in ALL_MANAGED_COLLECTIONS,
            f"Unknown dashboard collection: {collection!r}",
        )
        query = dict(scope_filter or {})
        bound = limit if limit is not None else self.config.default_query_limit
        try:
            cursor = self._database()[collection].find(query).limit(bound)
            records = list(cursor)
        except Exception as exc:
            self._last_error = f"Dashboard data unavailable ({collection}): {exc}"
            logger.warning(self._last_error)
            return [], self._last_error
        self._last_error = None
        return records, None

    def collection_count(self, collection: str) -> tuple[int, str | None]:
        """Return the document count for ``collection`` or a controlled error."""
        _check(
            collection in ALL_MANAGED_COLLECTIONS,
            f"Unknown dashboard collection: {collection!r}",
        )
        try:
            count = int(self._database()[collection].count_documents({}))
        except Exception as exc:
            self._last_error = f"Dashboard data unavailable ({collection}): {exc}"
            logger.warning(self._last_error)
            return 0, self._last_error
        self._last_error = None
        return count, None

    def gold_status(self) -> dict[str, dict[str, Any]]:
        """Report per-gold-collection ``{"count": n, "error": e}`` status.

        Used by the dashboard shell to show serving-layer health without
        fabricating KPI values.
        """
        status: dict[str, dict[str, Any]] = {}
        for name in self.config.gold_collections:
            count, error = self.collection_count(name)
            status[name] = {"count": count, "error": error}
        return status
