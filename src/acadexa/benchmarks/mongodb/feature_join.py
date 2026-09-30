"""Feature-table join benchmark using MongoDB aggregation (Task 13.5, F-F03).

Implements the ``feature_table_join`` workload where it is practical:
left-join academic records to attendance and coursework summaries at
student × course × semester grain via ``$lookup`` with compound-key
pipelines. LMS weekly aggregates live outside MongoDB by architecture,
so the MongoDB scope is the three operational collections — recorded on
the result, since cross-engine scopes differ honestly by design here.
Not a claim about which engine is superior.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from acadexa.benchmarks.runner import (
    ENGINE_MONGODB,
    BenchmarkResult,
    run_benchmark,
)
from acadexa.database import (
    MongoDBConfig,
    close_mongo_client,
    get_database,
    get_mongo_client,
    run_aggregation,
)
from acadexa.processing.jobs.event_aggregation import SEMESTER_BOUNDS

logger = logging.getLogger(__name__)

WORKLOAD_ID: str = "feature_table_join"
JOIN_KEYS: tuple[str, str, str] = ("student_id", "course_id", "semester_id")


def _semester_from_due_date() -> dict[str, Any]:
    """Semester expression for coursework (explicit id, else due-date bounds).

    Mirrors J3, which derives semester from due_date when the field is
    absent (cleaned coursework carries no semester_id).
    """
    parsed = {"$dateFromString": {"dateString": "$due_date", "onError": None, "onNull": None}}
    branches = [
        {
            "case": {
                "$and": [
                    {"$gte": [parsed, {"$toDate": f"{start}T00:00:00Z"}]},
                    {"$lte": [parsed, {"$toDate": f"{end}T00:00:00Z"}]},
                ]
            },
            "then": sem_id,
        }
        for sem_id, start, end in SEMESTER_BOUNDS
    ]
    derived: dict[str, Any] = {"$switch": {"branches": branches, "default": "UNKNOWN"}}
    return {
        "$cond": [
            {"$ne": [{"$type": "$semester_id"}, "missing"]},
            {"$toUpper": {"$trim": {"input": "$semester_id"}}},
            derived,
        ]
    }


def _compound_match(semester_expr: str = "$semester_id") -> list[dict[str, Any]]:
    """Match foreign rows on the three join keys (academic scope)."""
    return [
        {
            "$match": {
                "$expr": {
                    "$and": [
                        {"$eq": ["$student_id", "$$sid"]},
                        {"$eq": ["$course_id", "$$cid"]},
                        {"$eq": [semester_expr, "$$sem"]},
                    ]
                }
            }
        }
    ]


def build_feature_join_pipeline(
    match: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the feature-table join pipeline (pure, no I/O).

    Left join from academic records: attendance sums and coursework
    counts per join key, missing domain records yielding zeros.
    """
    pipeline: list[dict[str, Any]] = []
    if match:
        pipeline.append({"$match": dict(match)})
    pipeline.extend(
        [
            {
                "$lookup": {
                    "from": "attendance",
                    "let": {
                        "sid": "$student_id",
                        "cid": "$course_id",
                        "sem": "$semester_id",
                    },
                    "pipeline": [
                        *_compound_match(),
                        {
                            "$group": {
                                "_id": None,
                                "conducted": {"$sum": "$classes_conducted"},
                                "attended": {"$sum": "$classes_attended"},
                            }
                        },
                    ],
                    "as": "att",
                }
            },
            {
                "$lookup": {
                    "from": "coursework",
                    "let": {
                        "sid": "$student_id",
                        "cid": "$course_id",
                        "sem": "$semester_id",
                    },
                    "pipeline": [
                        {"$addFields": {"_sem": _semester_from_due_date()}},
                        *_compound_match("$_sem"),
                        {
                            "$group": {
                                "_id": None,
                                "items": {"$sum": 1},
                                "submissions": {
                                    "$sum": {
                                        "$cond": [
                                            {"$in": ["$status", ["ON_TIME", "LATE"]]},
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "late": {
                                    "$sum": {
                                        "$cond": [{"$eq": ["$status", "LATE"]}, 1, 0]
                                    }
                                },
                            }
                        },
                    ],
                    "as": "cwk",
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "student_id": 1,
                    "course_id": 1,
                    "semester_id": 1,
                    "total_marks": {
                        "$add": ["$internal_marks", "$midterm_marks", "$endterm_marks"]
                    },
                    "classes_conducted": {
                        "$ifNull": [{"$first": "$att.conducted"}, 0]
                    },
                    "classes_attended": {
                        "$ifNull": [{"$first": "$att.attended"}, 0]
                    },
                    "total_coursework": {
                        "$ifNull": [{"$first": "$cwk.items"}, 0]
                    },
                    "total_submissions": {
                        "$ifNull": [{"$first": "$cwk.submissions"}, 0]
                    },
                    "late_submissions": {
                        "$ifNull": [{"$first": "$cwk.late"}, 0]
                    },
                }
            },
            {"$sort": {"student_id": 1, "course_id": 1, "semester_id": 1}},
        ]
    )
    return pipeline


def aggregate_feature_join_mongo(
    database: Any | None = None,
    config: MongoDBConfig | None = None,
    match: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run the feature-table join aggregation against MongoDB.

    Raises:
        MongoConnectionError: if MongoDB cannot be reached.
        AggregationError: if aggregation execution fails.
    """
    return run_aggregation(
        "academic_records",
        build_feature_join_pipeline(match),
        database=database,
        config=config,
    )


def run_feature_table_join_mongodb(
    database: Any | None = None,
    config: MongoDBConfig | None = None,
    match: Mapping[str, Any] | None = None,
    *,
    measure_memory: bool = True,
    extra: dict[str, Any] | None = None,
) -> BenchmarkResult:
    """Run the MongoDB feature-table join workload and record the result."""

    def _workload() -> tuple[int, int]:
        if database is not None:
            input_rows = int(database["academic_records"].count_documents(dict(match or {})))
            joined = aggregate_feature_join_mongo(database=database, match=match)
            return input_rows, len(joined)
        client = get_mongo_client(config or MongoDBConfig.from_env())
        try:
            db = get_database(config, client=client)
            input_rows = int(db["academic_records"].count_documents(dict(match or {})))
            joined = aggregate_feature_join_mongo(database=db, match=match)
            return input_rows, len(joined)
        finally:
            close_mongo_client(client)

    return run_benchmark(
        WORKLOAD_ID,
        ENGINE_MONGODB,
        _workload,
        measure_memory=measure_memory,
        extra={
            "join_semantics": "left",
            "collections": "academic_records+attendance+coursework",
            **(extra or {}),
        },
    )
