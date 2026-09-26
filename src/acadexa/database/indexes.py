"""MongoDB index specifications and query optimization (task 6.5, rules.md §16.3).

Defines and manages indexes based on documented query patterns:
1. Student access:
   - ``students``: unique ``student_id``, compound hierarchy ``[school, department]``.
2. Course & semester access:
   - ``courses``: unique ``course_id``, compound hierarchy ``[school, department]``.
   - ``academic_records``: compound ``[student_id, semester_id]``, compound ``[course_id, semester_id]``.
   - ``attendance``: compound ``[student_id, course_id, week_start]``, compound ``[course_id, semester_id]``.
   - ``coursework``: compound ``[student_id, course_id]``, compound ``[course_id, item_id]``.
3. LMS time-series access:
   - ``lms_events``: compound ``[meta.student_id, meta.course_id, timestamp]``,
     compound ``[meta.course_id, timestamp]``.
4. Gold collections (canonical grains):
   - ``student_features``: unique ``[student_id, semester_id]``.
   - ``course_metrics``: unique ``[course_id, semester_id]``.
   - ``school_summary``: unique ``[school, department]``.
   - ``risk_indicators``: compound ``[student_id, week_start]``.

Architecture & Rules:
- Rules.md §16.3: Indexes created for actual documented query patterns; no speculative indexes.
- Features.md § F-C06: Query optimization across student, course, semester, hierarchy, LMS dimensions.
- Architecture.md § 21.2 & Tech_stack.md § 12: Specific index definitions and execution plan inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pymongo
from pymongo import ASCENDING, IndexModel
from pymongo.database import Database
from pymongo.errors import PyMongoError

from acadexa.database.client import (
    MongoDBConfig,
    MongoConnectionError,
    MongoError,
    get_database,
)
from acadexa.database.collections import (
    ALL_MANAGED_COLLECTIONS,
    CORE_COLLECTIONS,
    GOLD_COLLECTIONS,
    LMS_TIMESERIES_SPEC,
    TIMESERIES_COLLECTIONS,
    init_database,
)


class IndexError(MongoError):
    """Raised when MongoDB index creation or inspection fails."""


@dataclass(frozen=True)
class IndexSummary:
    """Summary of an existing MongoDB collection index."""

    name: str
    keys: list[tuple[str, int | str]]
    unique: bool

    def as_dict(self) -> dict[str, Any]:
        """Return serializable representation."""
        return {
            "name": self.name,
            "keys": list(self.keys),
            "unique": self.unique,
        }


# Canonical index specifications for all managed collections
COLLECTION_INDEX_DEFINITIONS: dict[str, list[IndexModel]] = {
    # ── 1. Core Collections ──────────────────────────────────────────────────
    "students": [
        IndexModel(
            [("student_id", ASCENDING)],
            unique=True,
            name="idx_students_student_id",
        ),
        IndexModel(
            [("school", ASCENDING), ("department", ASCENDING)],
            name="idx_students_hierarchy",
        ),
    ],
    "courses": [
        IndexModel(
            [("course_id", ASCENDING)],
            unique=True,
            name="idx_courses_course_id",
        ),
        IndexModel(
            [("school", ASCENDING), ("department", ASCENDING)],
            name="idx_courses_hierarchy",
        ),
    ],
    "academic_records": [
        IndexModel(
            [("student_id", ASCENDING), ("semester_id", ASCENDING)],
            name="idx_records_student_semester",
        ),
        IndexModel(
            [("course_id", ASCENDING), ("semester_id", ASCENDING)],
            name="idx_records_course_semester",
        ),
    ],
    "attendance": [
        IndexModel(
            [("student_id", ASCENDING), ("course_id", ASCENDING), ("week_start", ASCENDING)],
            name="idx_attendance_student_course_week",
        ),
        IndexModel(
            [("course_id", ASCENDING), ("semester_id", ASCENDING)],
            name="idx_attendance_course_semester",
        ),
    ],
    "coursework": [
        IndexModel(
            [("student_id", ASCENDING), ("course_id", ASCENDING)],
            name="idx_coursework_student_course",
        ),
        IndexModel(
            [("course_id", ASCENDING), ("item_id", ASCENDING)],
            name="idx_coursework_course_item",
        ),
    ],
    # ── 2. LMS Time-Series Collection ────────────────────────────────────────
    "lms_events": [
        IndexModel(
            [
                ("meta.student_id", ASCENDING),
                ("meta.course_id", ASCENDING),
                ("timestamp", ASCENDING),
            ],
            name="idx_lms_student_course_ts",
        ),
        IndexModel(
            [("meta.course_id", ASCENDING), ("timestamp", ASCENDING)],
            name="idx_lms_course_ts",
        ),
    ],
    # ── 3. Gold Analytical Collections ───────────────────────────────────────
    "student_features": [
        IndexModel(
            [("student_id", ASCENDING), ("semester_id", ASCENDING)],
            unique=True,
            name="idx_features_student_semester",
        ),
    ],
    "course_metrics": [
        IndexModel(
            [("course_id", ASCENDING), ("semester_id", ASCENDING)],
            unique=True,
            name="idx_metrics_course_semester",
        ),
    ],
    "school_summary": [
        IndexModel(
            [("school", ASCENDING), ("department", ASCENDING)],
            unique=True,
            name="idx_summary_hierarchy",
        ),
    ],
    "risk_indicators": [
        IndexModel(
            [("student_id", ASCENDING), ("week_start", ASCENDING)],
            name="idx_risk_student_week",
        ),
    ],
}


def create_database_indexes(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    collection_names: Sequence[str] | None = None,
    ensure_collections: bool = True,
) -> dict[str, list[str]]:
    """Create documented indexes on managed collections idempotently (task 6.5).

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig. Uses default environment configuration if omitted.
        collection_names: Optional subset of collection names to index. Defaults
            to all collections with defined index models.
        ensure_collections: If True, ensures database time-series and gold collections
            are initialized prior to index creation.

    Returns:
        Mapping of collection name to list of created index names.

    Raises:
        MongoConnectionError: if MongoDB cannot be reached.
        IndexError: if index creation fails on any collection.
    """
    cfg = config
    db = database if database is not None else get_database(cfg)

    # Verify connectivity
    try:
        db.client.admin.command("ping")
    except PyMongoError as exc:
        masked = cfg.masked_uri if cfg is not None else "MongoDB server"
        raise MongoConnectionError(f"Cannot connect to MongoDB at {masked}: {exc}") from exc

    if ensure_collections:
        # Pre-initialize collections so time-series metadata is correctly established
        init_database(database=db, config=cfg, create_gold_placeholders=True)

    target_collections = (
        collection_names
        if collection_names is not None
        else list(COLLECTION_INDEX_DEFINITIONS.keys())
    )

    created_indexes: dict[str, list[str]] = {}

    for col_name in target_collections:
        if col_name not in COLLECTION_INDEX_DEFINITIONS:
            continue

        models = COLLECTION_INDEX_DEFINITIONS[col_name]
        coll = db[col_name]

        try:
            res = coll.create_indexes(models)
            created_indexes[col_name] = res
        except PyMongoError as exc:
            raise IndexError(
                f"Failed creating indexes on collection '{col_name}': {exc}"
            ) from exc

    return created_indexes


def list_database_indexes(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    collection_names: Sequence[str] | None = None,
) -> dict[str, list[IndexSummary]]:
    """List existing indexes for managed collections.

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.
        collection_names: Optional subset of collection names to inspect.

    Returns:
        Mapping of collection name to list of IndexSummary instances.
    """
    cfg = config
    db = database if database is not None else get_database(cfg)

    existing_collections = set(db.list_collection_names())
    target_names = (
        collection_names
        if collection_names is not None
        else ALL_MANAGED_COLLECTIONS
    )

    result: dict[str, list[IndexSummary]] = {}

    for name in target_names:
        if name not in existing_collections:
            result[name] = []
            continue

        coll = db[name]
        try:
            indexes = list(coll.list_indexes())
            summaries: list[IndexSummary] = []
            for idx_info in indexes:
                idx_name = str(idx_info.get("name", ""))
                key_dict = idx_info.get("key", {})
                keys = list(key_dict.items()) if hasattr(key_dict, "items") else []
                is_unique = bool(idx_info.get("unique", False))
                summaries.append(
                    IndexSummary(
                        name=idx_name,
                        keys=keys,
                        unique=is_unique,
                    )
                )
            result[name] = summaries
        except PyMongoError:
            result[name] = []

    return result


def drop_database_indexes(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    collection_names: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """Drop non-default user indexes from specified or all managed collections.

    Preserves the primary `_id_` index and time-series default `meta_1_timestamp_1` index.

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.
        collection_names: Optional subset of collection names to process.

    Returns:
        Mapping of collection name to list of dropped index names.
    """
    cfg = config
    db = database if database is not None else get_database(cfg)

    existing_collections = set(db.list_collection_names())
    target_names = (
        collection_names
        if collection_names is not None
        else list(COLLECTION_INDEX_DEFINITIONS.keys())
    )

    dropped_indexes: dict[str, list[str]] = {}

    for col_name in target_names:
        if col_name not in existing_collections:
            continue

        coll = db[col_name]
        dropped_for_col: list[str] = []

        try:
            indexes = list(coll.list_indexes())
            for idx in indexes:
                idx_name = idx.get("name", "")
                # Preserve default primary _id index and timeseries default meta index
                if idx_name in ("_id_", "meta_1_timestamp_1"):
                    continue
                try:
                    coll.drop_index(idx_name)
                    dropped_for_col.append(idx_name)
                except PyMongoError:
                    pass
        except PyMongoError:
            pass

        dropped_indexes[col_name] = dropped_for_col

    return dropped_indexes


def explain_query_plan(
    collection_name: str,
    filter_query: Mapping[str, Any],
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> dict[str, Any]:
    """Execute explain() on a query filter to verify index utilization (features.md F-C06).

    Args:
        collection_name: Target collection name.
        filter_query: Query filter dictionary (e.g. {"student_id": "STU001"}).
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        Summary dictionary containing:
        - ``stage``: Winning query execution stage (e.g. 'IXSCAN', 'COLLSCAN', etc.)
        - ``is_indexed``: True if query utilized an index scan.
        - ``index_name``: Name of the index used (or None if collection scan).
        - ``total_docs_examined``: Number of documents scanned.
        - ``n_returned``: Number of matching documents returned.
        - ``execution_time_ms``: Execution duration in milliseconds if available.
    """
    cfg = config
    db = database if database is not None else get_database(cfg)

    coll = db[collection_name]
    try:
        explanation = coll.find(filter_query).explain()
    except PyMongoError as exc:
        raise IndexError(f"Failed explaining query on '{collection_name}': {exc}") from exc

    q_planner = explanation.get("queryPlanner", {})
    winning_plan = q_planner.get("winningPlan", {})

    # Traverse execution stages to identify scan type and index
    def _find_stage_info(plan: dict[str, Any]) -> tuple[str, str | None]:
        stage = plan.get("stage", "UNKNOWN")
        index_name = plan.get("indexName")

        if index_name is not None:
            return stage, str(index_name)

        # Check inputStage
        input_stage = plan.get("inputStage")
        if isinstance(input_stage, dict):
            s, idx = _find_stage_info(input_stage)
            if idx is not None:
                return s, idx

        # Check inputStages (array)
        input_stages = plan.get("inputStages")
        if isinstance(input_stages, list):
            for sub in input_stages:
                if isinstance(sub, dict):
                    s, idx = _find_stage_info(sub)
                    if idx is not None:
                        return s, idx

        return stage, None

    stage, index_name = _find_stage_info(winning_plan)
    is_indexed = (
        index_name is not None
        or "IXSCAN" in stage.upper()
        or stage.upper() == "EXPRESS_IXSCAN"
    )

    stats = explanation.get("executionStats", {})
    return {
        "collection": collection_name,
        "filter": dict(filter_query),
        "stage": stage,
        "is_indexed": is_indexed,
        "index_name": index_name,
        "total_docs_examined": stats.get("totalDocsExamined"),
        "n_returned": stats.get("nReturned"),
        "execution_time_ms": stats.get("executionTimeMillis"),
    }
