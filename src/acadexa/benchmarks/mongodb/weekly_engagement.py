"""Weekly LMS engagement benchmark using MongoDB aggregation (Task 13.3, F-F03).

Implements the ``weekly_lms_engagement`` workload where it is feasible:
aggregate the LMS event serving collection into weekly student-course
summaries with the same grain and metrics as Spark J2, so the pandas and
PySpark implementations remain directly comparable. Not a claim about
which engine is superior — the harness records the measured outcome
either way.

The pipeline uses ``$match``/``$project``/``$group``/``$sort`` over the
``meta``/``timestamp`` event shape (the same operators as the existing
LMS timeline aggregation) and works on regular and time-series
collections alike. Semester bounds and activity categories are imported
from the J2 job module (canonical definitions) so the workloads cannot
silently drift apart.

Caveat: results are materialized to the driver to count output rows,
which bounds practical input size; at full slice scale prefer a
``$merge``-based variant (out of scope for this task).
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

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
from acadexa.processing.jobs.event_aggregation import (
    APPROVED_ACTIVITY_CATEGORIES,
    SEMESTER_BOUNDS,
)

logger = logging.getLogger(__name__)

WORKLOAD_ID: str = "weekly_lms_engagement"
DEFAULT_COLLECTION: str = "lms_events"


def _semester_switch(field: str) -> dict[str, Any]:
    """Build a $switch mapping week dates to semester ids (J2-equivalent)."""
    branches = [
        {
            "case": {
                "$and": [
                    {"$gte": [field, {"$toDate": f"{start}T00:00:00Z"}]},
                    {"$lte": [field, {"$toDate": f"{end}T00:00:00Z"}]},
                ]
            },
            "then": sem_id,
        }
        for sem_id, start, end in SEMESTER_BOUNDS
    ]
    return {"$switch": {"branches": branches, "default": "UNKNOWN"}}


def _semester_start_switch(field: str) -> dict[str, Any]:
    """Build a $switch mapping week dates to semester start dates."""
    branches = [
        {
            "case": {
                "$and": [
                    {"$gte": [field, {"$toDate": f"{start}T00:00:00Z"}]},
                    {"$lte": [field, {"$toDate": f"{end}T00:00:00Z"}]},
                ]
            },
            "then": {"$toDate": f"{start}T00:00:00Z"},
        }
        for _, start, end in SEMESTER_BOUNDS
    ]
    return {"$switch": {"branches": branches, "default": field}}


def _category_sum(field: str, types: Sequence[str]) -> dict[str, Any]:
    """Build a $sum counting events whose activity_type is in ``types``."""
    return {"$sum": {"$cond": [{"$in": [f"${field}", list(types)]}, 1, 0]}}


def build_weekly_engagement_pipeline(
    match: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the weekly-engagement aggregation pipeline (pure, no I/O).

    Grain: student_id × course_id × school × semester_id × week_start ×
    week_number, with total events, positive-only durations, distinct
    active days, approved category roll-ups and per-type breakdowns.
    """
    categories = APPROVED_ACTIVITY_CATEGORIES
    pipeline: list[dict[str, Any]] = []
    if match:
        pipeline.append({"$match": dict(match)})
    pipeline.extend(
        [
            {
                "$project": {
                    "student_id": {"$toUpper": {"$trim": {"input": "$meta.student_id"}}},
                    "course_id": {"$toUpper": {"$trim": {"input": "$meta.course_id"}}},
                    "school": {"$ifNull": ["$meta.school", "UNKNOWN"]},
                    "activity_type": 1,
                    "duration_sec": {"$ifNull": ["$duration_sec", 0]},
                    "event_day": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                    },
                    "week_start": {
                        "$dateTrunc": {
                            "date": "$timestamp",
                            "unit": "week",
                            "startOfWeek": "monday",
                        }
                    },
                }
            },
            {
                "$addFields": {
                    "semester_id": _semester_switch("$week_start"),
                    "sem_start": _semester_start_switch("$week_start"),
                }
            },
            {
                "$addFields": {
                    "week_number": {
                        "$toInt": {
                            "$trunc": {
                                "$add": [
                                    {
                                        "$divide": [
                                            {
                                                "$dateDiff": {
                                                    "startDate": "$sem_start",
                                                    "endDate": "$week_start",
                                                    "unit": "day",
                                                }
                                            },
                                            7,
                                        ]
                                    },
                                    1,
                                ]
                            }
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "student_id": "$student_id",
                        "course_id": "$course_id",
                        "school": "$school",
                        "semester_id": "$semester_id",
                        "week_start": "$week_start",
                        "week_number": "$week_number",
                    },
                    "total_events": {"$sum": 1},
                    "total_duration_sec": {
                        "$sum": {
                            "$cond": [{"$gt": ["$duration_sec", 0]}, "$duration_sec", 0]
                        }
                    },
                    "days": {"$addToSet": "$event_day"},
                    "content_views": _category_sum("activity_type", categories["content_views"]),
                    "assessment_events": _category_sum("activity_type", categories["assessment_events"]),
                    "participation_events": _category_sum("activity_type", categories["participation_events"]),
                    "access_events": _category_sum("activity_type", categories["access_events"]),
                    "video_views": _category_sum("activity_type", ["VIDEO_VIEW", "VIDEO_COMPLETE"]),
                    "quiz_attempts": _category_sum("activity_type", ["QUIZ_ATTEMPT"]),
                    "assignment_views": _category_sum("activity_type", ["ASSIGNMENT_VIEW"]),
                    "assignment_submissions": _category_sum("activity_type", ["ASSIGNMENT_SUBMISSION"]),
                    "forum_posts": _category_sum("activity_type", ["FORUM_POST"]),
                    "logins": _category_sum("activity_type", ["LOGIN"]),
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "student_id": "$_id.student_id",
                    "course_id": "$_id.course_id",
                    "school": "$_id.school",
                    "semester_id": "$_id.semester_id",
                    "week_start": "$_id.week_start",
                    "week_number": "$_id.week_number",
                    "total_events": 1,
                    "total_duration_sec": 1,
                    "active_days": {"$size": "$days"},
                    "content_views": 1,
                    "assessment_events": 1,
                    "participation_events": 1,
                    "access_events": 1,
                    "video_views": 1,
                    "quiz_attempts": 1,
                    "assignment_views": 1,
                    "assignment_submissions": 1,
                    "forum_posts": 1,
                    "logins": 1,
                }
            },
            {"$sort": {"student_id": 1, "course_id": 1, "week_start": 1}},
        ]
    )
    return pipeline


def aggregate_weekly_engagement_mongo(
    database: Any | None = None,
    config: MongoDBConfig | None = None,
    collection: str = DEFAULT_COLLECTION,
    match: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run the weekly-engagement aggregation against MongoDB.

    Raises:
        MongoConnectionError: if MongoDB cannot be reached.
        AggregationError: if aggregation execution fails.
    """
    return run_aggregation(
        collection,
        build_weekly_engagement_pipeline(match),
        database=database,
        config=config,
    )


def run_weekly_engagement_mongodb(
    database: Any | None = None,
    config: MongoDBConfig | None = None,
    collection: str = DEFAULT_COLLECTION,
    match: Mapping[str, Any] | None = None,
    *,
    measure_memory: bool = True,
    extra: dict[str, Any] | None = None,
) -> BenchmarkResult:
    """Run the MongoDB weekly-engagement workload and record the result.

    The timed workload covers the aggregation execution; input rows are
    counted with the same match filter for comparability.
    """

    def _workload() -> tuple[int, int]:
        if database is not None:
            input_rows = int(database[collection].count_documents(dict(match or {})))
            summary = aggregate_weekly_engagement_mongo(
                database=database, collection=collection, match=match
            )
            return input_rows, len(summary)
        client = get_mongo_client(config or MongoDBConfig.from_env())
        try:
            db = get_database(config, client=client)
            input_rows = int(db[collection].count_documents(dict(match or {})))
            summary = aggregate_weekly_engagement_mongo(
                database=db, collection=collection, match=match
            )
            return input_rows, len(summary)
        finally:
            close_mongo_client(client)

    return run_benchmark(
        WORKLOAD_ID,
        ENGINE_MONGODB,
        _workload,
        measure_memory=measure_memory,
        extra={"collection": collection, **(extra or {})},
    )
