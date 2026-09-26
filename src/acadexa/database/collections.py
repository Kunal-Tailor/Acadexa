"""MongoDB collection specifications and database initialization (task 6.2, rules.md §11, §16).

Defines canonical collection names, metadata, and database initialization:
- Core operational collections: ``students``, ``courses``, ``academic_records``,
  ``attendance``, ``coursework``.
- Time-series operational collection: ``lms_events`` (timeField='timestamp', metaField='meta').
- Gold analytical collections: ``student_features``, ``course_metrics``,
  ``school_summary``, ``risk_indicators`` (initialized as empty placeholders prior to
  Spark publication in J7).

Architecture & Rules:
- Rules.md §11: Strict schema contracts across the 5 core, 1 timeseries, and 4 gold collections.
- Rules.md §16.1 & §16.2: MongoDB serves operational data, gold analytics, and the defined LMS slice.
- Architecture.md §10: ``lms_events`` uses MongoDB time-series collection capabilities.
- Task 6.2: Core collections and gold placeholders initialized without populating gold data.
"""

from __future__ import annotations

from typing import Any, Sequence

import pymongo
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, PyMongoError

from acadexa.database.client import (
    MongoDBConfig,
    MongoConnectionError,
    get_database,
)

CORE_COLLECTIONS: tuple[str, ...] = (
    "students",
    "courses",
    "academic_records",
    "attendance",
    "coursework",
)

TIMESERIES_COLLECTIONS: tuple[str, ...] = ("lms_events",)

GOLD_COLLECTIONS: tuple[str, ...] = (
    "student_features",
    "course_metrics",
    "school_summary",
    "risk_indicators",
)

ALL_MANAGED_COLLECTIONS: tuple[str, ...] = (
    CORE_COLLECTIONS + TIMESERIES_COLLECTIONS + GOLD_COLLECTIONS
)

LMS_TIMESERIES_SPEC: dict[str, str] = {
    "timeField": "timestamp",
    "metaField": "meta",
    "granularity": "seconds",
}

COLLECTION_METADATA: dict[str, dict[str, Any]] = {
    "students": {
        "type": "core",
        "description": "Student identity, hierarchy mapping, batch, and status",
        "grain": ["student_id"],
    },
    "courses": {
        "type": "core",
        "description": "Academic course catalog with difficulty and school references",
        "grain": ["course_id"],
    },
    "academic_records": {
        "type": "core",
        "description": "Student semester enrollments, component marks, and final letter grades",
        "grain": ["student_id", "course_id", "semester_id"],
    },
    "attendance": {
        "type": "core",
        "description": "Weekly classes conducted and attended per student-course",
        "grain": ["student_id", "course_id", "week_start"],
    },
    "coursework": {
        "type": "core",
        "description": "Assignments and quizzes with submission status, scores, and timestamps",
        "grain": ["student_id", "course_id", "item_id"],
    },
    "lms_events": {
        "type": "timeseries",
        "description": "MongoDB operational serving slice of LMS time-series events",
        "grain": ["timestamp", "meta", "activity_type", "resource_id", "duration_sec", "session_id"],
        "timeseries": LMS_TIMESERIES_SPEC,
    },
    "student_features": {
        "type": "gold",
        "description": "Spark-published analytical features and trends per student per semester",
        "grain": ["student_id", "semester_id"],
    },
    "course_metrics": {
        "type": "gold",
        "description": "Spark-published aggregated course performance and difficulty metrics",
        "grain": ["course_id", "semester_id"],
    },
    "school_summary": {
        "type": "gold",
        "description": "Spark-published school and department-level analytical roll-ups",
        "grain": ["school", "department"],
    },
    "risk_indicators": {
        "type": "gold",
        "description": "Spark-published 5-rule explainable risk signals per student per week",
        "grain": ["student_id", "week_start"],
    },
}


def init_database(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    drop_existing: bool = False,
    create_gold_placeholders: bool = True,
) -> dict[str, Any]:
    """Initialize MongoDB collections for Acadexa (task 6.2).

    Creates:
    - 5 core operational collections: students, courses, academic_records, attendance, coursework
    - 1 time-series operational collection: lms_events
    - 4 gold analytical collections: student_features, course_metrics, school_summary, risk_indicators
      (created as empty collection placeholders ready for Spark J7 publication)

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig. Uses default environment configuration if omitted.
        drop_existing: If True, drops existing managed collections before creation.
        create_gold_placeholders: If True, explicitly creates gold placeholder collections.

    Returns:
        Summary dictionary detailing database name, created collections, and status.

    Raises:
        MongoConnectionError: if the database cannot be reached.
    """
    cfg = config
    db = database if database is not None else get_database(cfg)

    # Verify connectivity
    try:
        db.client.admin.command("ping")
    except PyMongoError as exc:
        masked = cfg.masked_uri if cfg is not None else "MongoDB server"
        raise MongoConnectionError(f"Cannot connect to MongoDB at {masked}: {exc}") from exc


    if drop_existing:
        drop_managed_collections(db)

    existing_collections = set(db.list_collection_names())

    created: list[str] = []
    already_existing: list[str] = []

    # 1. Core Collections
    for name in CORE_COLLECTIONS:
        if name in existing_collections:
            already_existing.append(name)
        else:
            try:
                db.create_collection(name)
                created.append(name)
            except CollectionInvalid:
                already_existing.append(name)

    # 2. Time-Series Collection (lms_events)
    for name in TIMESERIES_COLLECTIONS:
        if name in existing_collections:
            already_existing.append(name)
        else:
            try:
                db.create_collection(
                    name,
                    timeseries=LMS_TIMESERIES_SPEC,
                )
                created.append(name)
            except CollectionInvalid:
                already_existing.append(name)

    # 3. Gold Analytical Collection Placeholders (Spark J7 publication targets)
    if create_gold_placeholders:
        for name in GOLD_COLLECTIONS:
            if name in existing_collections:
                already_existing.append(name)
            else:
                try:
                    db.create_collection(name)
                    created.append(name)
                except CollectionInvalid:
                    already_existing.append(name)

    return {
        "database": db.name,
        "status": "initialized",
        "collections_created": created,
        "collections_existing": already_existing,
        "core_collections": list(CORE_COLLECTIONS),
        "timeseries_collections": list(TIMESERIES_COLLECTIONS),
        "gold_collections": list(GOLD_COLLECTIONS),
        "all_managed_collections": list(ALL_MANAGED_COLLECTIONS),
    }


def verify_database_collections(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> dict[str, Any]:
    """Verify presence, count, and configuration of all managed collections.

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        Status mapping detailing collection counts, time-series status, and integrity.
    """
    db = database if database is not None else get_database(config)

    existing = set(db.list_collection_names())
    status: dict[str, Any] = {
        "database": db.name,
        "collections": {},
        "all_core_present": True,
        "timeseries_present": True,
        "all_gold_present": True,
    }

    # Inspect each managed collection
    for name, meta in COLLECTION_METADATA.items():
        is_present = name in existing
        count = 0
        is_ts = meta["type"] == "timeseries"

        if is_present:
            try:
                count = db[name].count_documents({})
            except PyMongoError:
                count = -1

        status["collections"][name] = {
            "present": is_present,
            "type": meta["type"],
            "count": count,
            "grain": meta.get("grain", []),
        }

        if meta["type"] == "core" and not is_present:
            status["all_core_present"] = False
        elif meta["type"] == "timeseries" and not is_present:
            status["timeseries_present"] = False
        elif meta["type"] == "gold" and not is_present:
            status["all_gold_present"] = False

    status["ready"] = (
        status["all_core_present"]
        and status["timeseries_present"]
        and status["all_gold_present"]
    )
    return status


def drop_managed_collections(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    collection_names: Sequence[str] | None = None,
) -> list[str]:
    """Drop specified or all managed Acadexa collections from database.

    Args:
        database: Optional Database instance.
        config: Optional MongoDBConfig.
        collection_names: Optional subset of collection names to drop. Defaults
            to ALL_MANAGED_COLLECTIONS.

    Returns:
        List of dropped collection names.
    """
    db = database if database is not None else get_database(config)
    existing = set(db.list_collection_names())

    target_names = collection_names if collection_names is not None else ALL_MANAGED_COLLECTIONS
    dropped: list[str] = []

    for name in target_names:
        if name in existing:
            try:
                db.drop_collection(name)
                dropped.append(name)
            except PyMongoError:
                pass

    return dropped
