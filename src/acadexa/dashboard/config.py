"""Dashboard configuration (Task 11.1, folder_structure.md §14, rules.md §6).

Centralizes non-secret Streamlit dashboard settings: application title,
MongoDB serving configuration (credentials always come from the
environment via :class:`MongoDBConfig`), served collection names and the
dummy-user configuration path. No secrets are stored here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from acadexa.config.loader import PROJECT_ROOT, config_path
from acadexa.database import GOLD_COLLECTIONS, MongoDBConfig

APP_TITLE: str = "Acadexa — Academic Intelligence"
APP_SUBTITLE: str = "RAS University (synthetic data demonstration)"

DEFAULT_DUMMY_USERS_PATH: Path = config_path("dashboard", "dummy_users.toml")

OPERATIONAL_COLLECTIONS: tuple[str, ...] = (
    "students",
    "courses",
    "academic_records",
    "attendance",
    "coursework",
    "lms_events",
)

DEFAULT_QUERY_LIMIT: int = 500


@dataclass(frozen=True)
class DashboardConfig:
    """Non-secret configuration for the Streamlit dashboard."""

    app_title: str = APP_TITLE
    app_subtitle: str = APP_SUBTITLE
    database: MongoDBConfig = field(default_factory=MongoDBConfig)
    gold_collections: tuple[str, ...] = GOLD_COLLECTIONS
    operational_collections: tuple[str, ...] = OPERATIONAL_COLLECTIONS
    dummy_users_path: Path = DEFAULT_DUMMY_USERS_PATH
    default_query_limit: int = DEFAULT_QUERY_LIMIT
    project_root: Path = PROJECT_ROOT

    @classmethod
    def from_env(
        cls,
        dummy_users_path: Path | str | None = None,
        default_query_limit: int = DEFAULT_QUERY_LIMIT,
    ) -> DashboardConfig:
        """Build dashboard configuration with MongoDB settings from the environment."""
        return cls(
            database=MongoDBConfig.from_env(),
            dummy_users_path=Path(dummy_users_path)
            if dummy_users_path is not None
            else DEFAULT_DUMMY_USERS_PATH,
            default_query_limit=default_query_limit,
        )
