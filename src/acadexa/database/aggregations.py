"""Representative MongoDB analytical aggregations (task 6.6, rules.md §16.4, features.md F-C07).

Implements realistic operational and analytical aggregation pipelines across MongoDB collections:
1. ``$match``: Query filtering by student, course, semester, or temporal bounds.
2. ``$group``: Component mark statistics, submission counters, grade distribution.
3. ``$project``: Computed fields, score conversions, attendance rates, field reshaping.
4. ``$sort``: Performance rankings, chronological ordering, and hierarchical sorting.
5. ``$lookup``: Operational joins across students, courses, academic_records, and coursework.
6. ``$unwind``: Array destructuring of joined multi-record relationships.
7. ``$setWindowFields``: Sliding window rolling averages and cumulative attendance metrics.
8. ``$facet``: Multi-dimensional cohort dashboard analysis in a single round-trip.

Architecture & Rules:
- Rules.md §16.4: Demonstrates MongoDB aggregation where appropriate for operational
  summaries, drill-downs, and dashboard serving.
- Features.md § F-C07: Required operators used in meaningful workloads.
- Architecture.md § 21.2 & Tech_stack.md § 11: MongoDB aggregation responsibilities.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Sequence

from pymongo.database import Database
from pymongo.errors import PyMongoError

from acadexa.database.client import (
    MongoDBConfig,
    MongoConnectionError,
    MongoError,
    get_database,
)


class AggregationError(MongoError):
    """Raised when MongoDB aggregation pipeline execution fails."""


def run_aggregation(
    collection_name: str,
    pipeline: Sequence[Mapping[str, Any]],
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> list[dict[str, Any]]:
    """Execute an arbitrary aggregation pipeline against a collection.

    Args:
        collection_name: Target collection name.
        pipeline: Sequence of MongoDB aggregation stage mappings.
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        List of resulting documents.

    Raises:
        MongoConnectionError: if MongoDB cannot be reached.
        AggregationError: if aggregation execution fails.
    """
    cfg = config
    db = database if database is not None else get_database(cfg)

    # Verify connectivity
    try:
        db.client.admin.command("ping")
    except PyMongoError as exc:
        masked = cfg.masked_uri if cfg is not None else "MongoDB server"
        raise MongoConnectionError(f"Cannot connect to MongoDB at {masked}: {exc}") from exc

    coll = db[collection_name]
    try:
        cursor = coll.aggregate(list(pipeline))
        return list(cursor)
    except PyMongoError as exc:
        raise AggregationError(
            f"Aggregation pipeline failed on collection '{collection_name}': {exc}"
        ) from exc


def get_course_performance_summary(
    course_id: str,
    semester_id: str | None = None,
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> list[dict[str, Any]]:
    """Aggregate course performance statistics by semester ($match, $group, $project, $sort).

    Workload: Course Analytics drill-down. Computes cohort size, average internal,
    midterm, endterm, and overall marks, along with letter grade distributions.

    Args:
        course_id: Target course identifier (e.g. 'CSA101').
        semester_id: Optional semester filter (e.g. 'S1').
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        List of summarized course performance documents per semester.
    """
    match_stage: dict[str, Any] = {"course_id": course_id}
    if semester_id is not None:
        match_stage["semester_id"] = semester_id

    pipeline: list[dict[str, Any]] = [
        # 1. $match
        {"$match": match_stage},
        # 2. $group
        {
            "$group": {
                "_id": {
                    "course_id": "$course_id",
                    "semester_id": "$semester_id",
                },
                "total_enrolled": {"$sum": 1},
                "avg_internal": {"$avg": "$internal_marks"},
                "avg_midterm": {"$avg": "$midterm_marks"},
                "avg_endterm": {"$avg": "$endterm_marks"},
                "avg_total": {
                    "$avg": {
                        "$add": [
                            {"$ifNull": ["$internal_marks", 0]},
                            {"$ifNull": ["$midterm_marks", 0]},
                            {"$ifNull": ["$endterm_marks", 0]},
                        ]
                    }
                },
                "grades": {"$push": "$final_grade"},
            }
        },
        # 3. $project
        {
            "$project": {
                "_id": 0,
                "course_id": "$_id.course_id",
                "semester_id": "$_id.semester_id",
                "total_enrolled": 1,
                "avg_internal": {"$round": ["$avg_internal", 2]},
                "avg_midterm": {"$round": ["$avg_midterm", 2]},
                "avg_endterm": {"$round": ["$avg_endterm", 2]},
                "avg_total": {"$round": ["$avg_total", 2]},
                "grades": 1,
            }
        },
        # 4. $sort
        {"$sort": {"semester_id": 1}},
    ]

    return run_aggregation("academic_records", pipeline, database=database, config=config)


def get_student_academic_profile(
    student_id: str,
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> list[dict[str, Any]]:
    """Build complete student transcript joining courses ($match, $lookup, $unwind, $project, $sort).

    Workload: Student Profile drill-down. Joins ``students`` identity with their
    ``academic_records`` and resolves course titles from ``courses``.

    Args:
        student_id: Target student identifier (e.g. 'STU010482').
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        List of course enrollment records with joined student hierarchy and course metadata.
    """
    pipeline: list[dict[str, Any]] = [
        # 1. $match student identity
        {"$match": {"student_id": student_id}},
        # 2. $lookup academic records
        {
            "$lookup": {
                "from": "academic_records",
                "localField": "student_id",
                "foreignField": "student_id",
                "as": "records",
            }
        },
        # 3. $unwind records array
        {"$unwind": "$records"},
        # 4. $lookup course metadata
        {
            "$lookup": {
                "from": "courses",
                "localField": "records.course_id",
                "foreignField": "course_id",
                "as": "course_info",
            }
        },
        # 5. $unwind course info
        {
            "$unwind": {
                "path": "$course_info",
                "preserveNullAndEmptyArrays": True,
            }
        },
        # 6. $project unified transcript document
        {
            "$project": {
                "_id": 0,
                "student_id": 1,
                "school": 1,
                "department": 1,
                "program": 1,
                "batch": 1,
                "semester_id": "$records.semester_id",
                "course_id": "$records.course_id",
                "course_title": {"$ifNull": ["$course_info.title", "Unknown Course"]},
                "difficulty_level": "$course_info.difficulty_level",
                "internal_marks": "$records.internal_marks",
                "midterm_marks": "$records.midterm_marks",
                "endterm_marks": "$records.endterm_marks",
                "total_marks": {
                    "$add": [
                        {"$ifNull": ["$records.internal_marks", 0]},
                        {"$ifNull": ["$records.midterm_marks", 0]},
                        {"$ifNull": ["$records.endterm_marks", 0]},
                    ]
                },
                "final_grade": "$records.final_grade",
            }
        },
        # 7. $sort chronologically by semester and course
        {"$sort": {"semester_id": 1, "course_id": 1}},
    ]

    return run_aggregation("students", pipeline, database=database, config=config)


def get_coursework_completion_overview(
    course_id: str,
    student_id: str | None = None,
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> list[dict[str, Any]]:
    """Aggregate coursework completion rates per student ($match, $group, $lookup, $unwind, $project, $sort).

    Workload: Instructor Assignment/Quiz overview. Computes submission status
    counters (on-time, late, missing), completion percentages, and joins student info.

    Args:
        course_id: Target course identifier.
        student_id: Optional student filter.
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        List of coursework completion metrics per student sorted by missing items descending.
    """
    match_stage: dict[str, Any] = {"course_id": course_id}
    if student_id is not None:
        match_stage["student_id"] = student_id

    pipeline: list[dict[str, Any]] = [
        # 1. $match
        {"$match": match_stage},
        # 2. $group
        {
            "$group": {
                "_id": {
                    "student_id": "$student_id",
                    "course_id": "$course_id",
                },
                "total_items": {"$sum": 1},
                "on_time_count": {
                    "$sum": {"$cond": [{"$eq": ["$status", "ON_TIME"]}, 1, 0]}
                },
                "late_count": {
                    "$sum": {"$cond": [{"$eq": ["$status", "LATE"]}, 1, 0]}
                },
                "missing_count": {
                    "$sum": {"$cond": [{"$eq": ["$status", "MISSING"]}, 1, 0]}
                },
                "avg_score": {"$avg": "$score"},
                "total_max_score": {"$sum": "$max_score"},
            }
        },
        # 3. $lookup student details
        {
            "$lookup": {
                "from": "students",
                "localField": "_id.student_id",
                "foreignField": "student_id",
                "as": "student",
            }
        },
        # 4. $unwind
        {
            "$unwind": {
                "path": "$student",
                "preserveNullAndEmptyArrays": True,
            }
        },
        # 5. $project
        {
            "$project": {
                "_id": 0,
                "student_id": "$_id.student_id",
                "course_id": "$_id.course_id",
                "program": "$student.program",
                "school": "$student.school",
                "total_items": 1,
                "on_time_count": 1,
                "late_count": 1,
                "missing_count": 1,
                "completion_rate": {
                    "$round": [
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        {"$subtract": ["$total_items", "$missing_count"]},
                                        {"$max": ["$total_items", 1]},
                                    ]
                                },
                                100,
                            ]
                        },
                        1,
                    ]
                },
                "avg_score": {"$round": ["$avg_score", 2]},
            }
        },
        # 6. $sort by missing submissions descending (identifying students needing support)
        {"$sort": {"missing_count": -1, "completion_rate": 1}},
    ]

    return run_aggregation("coursework", pipeline, database=database, config=config)


def get_attendance_weekly_trends(
    student_id: str,
    course_id: str,
    window_size: int = 3,
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> list[dict[str, Any]]:
    """Compute moving average and cumulative attendance ($match, $project, $sort, $setWindowFields).

    Workload: Trend detection for student disengagement. Uses MongoDB 5.0+
    ``$setWindowFields`` to calculate a rolling average attendance rate over the previous
    N weeks, cumulative conduct/attendance, and week sequence rank.

    Args:
        student_id: Target student identifier.
        course_id: Target course identifier.
        window_size: Sliding window size for moving average (default 3 weeks).
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        Chronological list of weekly attendance records with rolling averages and cumulative counts.
    """
    pipeline: list[dict[str, Any]] = [
        # 1. $match
        {"$match": {"student_id": student_id, "course_id": course_id}},
        # 2. $project weekly attendance rate
        {
            "$project": {
                "_id": 0,
                "student_id": 1,
                "course_id": 1,
                "semester_id": 1,
                "week_start": 1,
                "classes_conducted": 1,
                "classes_attended": 1,
                "weekly_rate": {
                    "$round": [
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        "$classes_attended",
                                        {"$max": ["$classes_conducted", 1]},
                                    ]
                                },
                                100,
                            ]
                        },
                        1,
                    ]
                },
            }
        },
        # 3. $sort chronologically
        {"$sort": {"week_start": 1}},
        # 4. $setWindowFields for rolling window average and cumulative stats
        {
            "$setWindowFields": {
                "partitionBy": "$student_id",
                "sortBy": {"week_start": 1},
                "output": {
                    "rolling_avg_attendance": {
                        "$avg": "$weekly_rate",
                        "window": {"documents": [-window_size + 1, "current"]},
                    },
                    "cumulative_classes_conducted": {
                        "$sum": "$classes_conducted",
                        "window": {"documents": ["unbounded", "current"]},
                    },
                    "cumulative_classes_attended": {
                        "$sum": "$classes_attended",
                        "window": {"documents": ["unbounded", "current"]},
                    },
                    "week_sequence": {
                        "$documentNumber": {},
                    },
                },
            }
        },
        # 5. $project to round rolling average
        {
            "$project": {
                "student_id": 1,
                "course_id": 1,
                "semester_id": 1,
                "week_start": 1,
                "classes_conducted": 1,
                "classes_attended": 1,
                "weekly_rate": 1,
                "rolling_avg_attendance": {"$round": ["$rolling_avg_attendance", 1]},
                "cumulative_classes_conducted": 1,
                "cumulative_classes_attended": 1,
                "week_sequence": 1,
            }
        },
    ]

    return run_aggregation("attendance", pipeline, database=database, config=config)


def get_course_cohort_multi_facet(
    course_id: str,
    semester_id: str | None = None,
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> dict[str, Any]:
    """Execute multi-faceted cohort performance analytics ($match, $facet, $group, $sort, $project).

    Workload: Course Executive Dashboard. In a single database query, simultaneously computes:
    - ``grade_distribution``: counts per letter grade (A, B, C, etc.)
    - ``overall_stats``: cohort min, max, average total marks, and student count
    - ``top_performers``: top 5 highest-performing students
    - ``component_averages``: breakdown of internal, midterm, and endterm averages

    Args:
        course_id: Target course identifier.
        semester_id: Optional semester filter.
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        Dictionary containing all faceted analytical subsections.
    """
    match_stage: dict[str, Any] = {"course_id": course_id}
    if semester_id is not None:
        match_stage["semester_id"] = semester_id

    pipeline: list[dict[str, Any]] = [
        # 1. $match
        {"$match": match_stage},
        # 2. $facet with 4 analytical sub-pipelines
        {
            "$facet": {
                # Facet A: Grade Distribution
                "grade_distribution": [
                    {"$group": {"_id": "$final_grade", "count": {"$sum": 1}}},
                    {"$project": {"_id": 0, "grade": "$_id", "count": 1}},
                    {"$sort": {"grade": 1}},
                ],
                # Facet B: Overall Cohort Statistics
                "overall_stats": [
                    {
                        "$group": {
                            "_id": None,
                            "cohort_size": {"$sum": 1},
                            "min_total": {
                                "$min": {
                                    "$add": [
                                        {"$ifNull": ["$internal_marks", 0]},
                                        {"$ifNull": ["$midterm_marks", 0]},
                                        {"$ifNull": ["$endterm_marks", 0]},
                                    ]
                                }
                            },
                            "max_total": {
                                "$max": {
                                    "$add": [
                                        {"$ifNull": ["$internal_marks", 0]},
                                        {"$ifNull": ["$midterm_marks", 0]},
                                        {"$ifNull": ["$endterm_marks", 0]},
                                    ]
                                }
                            },
                            "avg_total": {
                                "$avg": {
                                    "$add": [
                                        {"$ifNull": ["$internal_marks", 0]},
                                        {"$ifNull": ["$midterm_marks", 0]},
                                        {"$ifNull": ["$endterm_marks", 0]},
                                    ]
                                }
                            },
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "cohort_size": 1,
                            "min_total": 1,
                            "max_total": 1,
                            "avg_total": {"$round": ["$avg_total", 2]},
                        }
                    },
                ],
                # Facet C: Component Averages
                "component_averages": [
                    {
                        "$group": {
                            "_id": None,
                            "avg_internal": {"$avg": "$internal_marks"},
                            "avg_midterm": {"$avg": "$midterm_marks"},
                            "avg_endterm": {"$avg": "$endterm_marks"},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "avg_internal": {"$round": ["$avg_internal", 2]},
                            "avg_midterm": {"$round": ["$avg_midterm", 2]},
                            "avg_endterm": {"$round": ["$avg_endterm", 2]},
                        }
                    },
                ],
                # Facet D: Top Performers
                "top_performers": [
                    {
                        "$project": {
                            "_id": 0,
                            "student_id": 1,
                            "final_grade": 1,
                            "total_marks": {
                                "$add": [
                                    {"$ifNull": ["$internal_marks", 0]},
                                    {"$ifNull": ["$midterm_marks", 0]},
                                    {"$ifNull": ["$endterm_marks", 0]},
                                ]
                            },
                        }
                    },
                    {"$sort": {"total_marks": -1}},
                    {"$limit": 5},
                ],
            }
        },
    ]

    results = run_aggregation("academic_records", pipeline, database=database, config=config)
    if not results:
        return {
            "grade_distribution": [],
            "overall_stats": [],
            "component_averages": [],
            "top_performers": [],
        }
    return results[0]


def get_lms_activity_timeline(
    course_id: str,
    student_id: str | None = None,
    school: str | None = None,
    database: Database | None = None,
    config: MongoDBConfig | None = None,
) -> list[dict[str, Any]]:
    """Aggregate daily LMS events from time-series collection ($match, $project, $group, $sort).

    Workload: Daily engagement breakdown for the LMS operational serving slice.

    Args:
        course_id: Target course identifier.
        student_id: Optional student filter.
        school: Optional school filter.
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.

    Returns:
        Daily aggregated list of LMS activities with event count and duration.
    """
    match_stage: dict[str, Any] = {"meta.course_id": course_id}
    if student_id is not None:
        match_stage["meta.student_id"] = student_id
    if school is not None:
        match_stage["meta.school"] = school

    pipeline: list[dict[str, Any]] = [
        # 1. $match
        {"$match": match_stage},
        # 2. $project date string
        {
            "$project": {
                "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "activity_type": 1,
                "duration_sec": {"$ifNull": ["$duration_sec", 0]},
            }
        },
        # 3. $group by day and activity_type
        {
            "$group": {
                "_id": {
                    "day": "$day",
                    "activity_type": "$activity_type",
                },
                "event_count": {"$sum": 1},
                "total_duration_sec": {"$sum": "$duration_sec"},
            }
        },
        # 4. $project clean output
        {
            "$project": {
                "_id": 0,
                "day": "$_id.day",
                "activity_type": "$_id.activity_type",
                "event_count": 1,
                "total_duration_sec": 1,
                "total_duration_min": {"$round": [{"$divide": ["$total_duration_sec", 60]}, 1]},
            }
        },
        # 5. $sort chronologically
        {"$sort": {"day": 1, "activity_type": 1}},
    ]

    return run_aggregation("lms_events", pipeline, database=database, config=config)
