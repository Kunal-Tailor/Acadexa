"""Unit tests for representative MongoDB analytical aggregations (task 6.6, rules.md §16.4, features.md F-C07)."""

from __future__ import annotations

from datetime import date, datetime, timezone
import pytest

from acadexa.database import (
    AggregationError,
    MongoDBConfig,
    MongoConnectionError,
    close_mongo_client,
    drop_managed_collections,
    get_attendance_weekly_trends,
    get_course_cohort_multi_facet,
    get_course_performance_summary,
    get_coursework_completion_overview,
    get_database,
    get_lms_activity_timeline,
    get_mongo_client,
    get_student_academic_profile,
    init_database,
    run_aggregation,
)


@pytest.fixture(scope="module")
def agg_test_db():
    """Module-level fixture providing an isolated populated MongoDB test database."""
    config = MongoDBConfig(database="test_acadexa_aggregations")
    client = get_mongo_client(config)
    db = get_database(config, client=client)

    # Initialize collections
    init_database(db, drop_existing=True)

    # 1. Seed Students
    db["students"].insert_many(
        [
            {
                "student_id": "STU001",
                "school": "School of Computer Engineering & Technology",
                "department": "Computer Science and Applications",
                "program": "B.Tech CSE",
                "batch": 2024,
                "semester": 3,
            },
            {
                "student_id": "STU002",
                "school": "School of Computer Engineering & Technology",
                "department": "Computer Science and Applications",
                "program": "B.Tech CSE",
                "batch": 2024,
                "semester": 3,
            },
        ]
    )

    # 2. Seed Courses
    db["courses"].insert_many(
        [
            {
                "course_id": "CSA101",
                "title": "Programming Fundamentals",
                "school": "School of Computer Engineering & Technology",
                "department": "Computer Science and Applications",
                "semester_applicability": [1, 2],
                "difficulty_level": "easy",
                "difficulty": 0.35,
            },
            {
                "course_id": "CSA201",
                "title": "Data Structures",
                "school": "School of Computer Engineering & Technology",
                "department": "Computer Science and Applications",
                "semester_applicability": [2, 3],
                "difficulty_level": "medium",
                "difficulty": 0.55,
            },
        ]
    )

    # 3. Seed Academic Records
    db["academic_records"].insert_many(
        [
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "semester_id": "S1",
                "internal_marks": 35,
                "midterm_marks": 20,
                "endterm_marks": 40,
                "final_grade": "A",
            },
            {
                "student_id": "STU002",
                "course_id": "CSA101",
                "semester_id": "S1",
                "internal_marks": 25,
                "midterm_marks": 15,
                "endterm_marks": 30,
                "final_grade": "C",
            },
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "semester_id": "S2",
                "internal_marks": 38,
                "midterm_marks": 19,
                "endterm_marks": 41,
                "final_grade": "A",
            },
        ]
    )

    # 4. Seed Coursework
    db["coursework"].insert_many(
        [
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "item_id": "A01",
                "item_type": "ASSIGNMENT",
                "assigned_date": "2025-09-01",
                "due_date": "2025-09-08",
                "submitted_at": "2025-09-07T12:00:00",
                "score": 19,
                "max_score": 20,
                "attempts": 1,
                "status": "ON_TIME",
            },
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "item_id": "A02",
                "item_type": "ASSIGNMENT",
                "assigned_date": "2025-09-15",
                "due_date": "2025-09-22",
                "submitted_at": "2025-09-23T10:00:00",
                "score": 15,
                "max_score": 20,
                "attempts": 1,
                "status": "LATE",
            },
            {
                "student_id": "STU002",
                "course_id": "CSA101",
                "item_id": "A01",
                "item_type": "ASSIGNMENT",
                "assigned_date": "2025-09-01",
                "due_date": "2025-09-08",
                "submitted_at": None,
                "score": None,
                "max_score": 20,
                "attempts": 0,
                "status": "MISSING",
            },
        ]
    )

    # 5. Seed Attendance (weekly series)
    db["attendance"].insert_many(
        [
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "semester_id": "S1",
                "week_start": "2025-09-01",
                "classes_conducted": 4,
                "classes_attended": 4,
            },
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "semester_id": "S1",
                "week_start": "2025-09-08",
                "classes_conducted": 4,
                "classes_attended": 3,
            },
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "semester_id": "S1",
                "week_start": "2025-09-15",
                "classes_conducted": 4,
                "classes_attended": 2,
            },
            {
                "student_id": "STU001",
                "course_id": "CSA101",
                "semester_id": "S1",
                "week_start": "2025-09-22",
                "classes_conducted": 4,
                "classes_attended": 1,
            },
        ]
    )

    # 6. Seed LMS Events (Time-Series)
    db["lms_events"].insert_many(
        [
            {
                "timestamp": datetime(2026, 2, 10, 10, 0, 0),
                "meta": {"student_id": "STU001", "course_id": "CSA101", "school": "CET"},
                "activity_type": "LOGIN",
                "resource_id": None,
                "duration_sec": 60,
                "session_id": "SES01",
            },
            {
                "timestamp": datetime(2026, 2, 10, 10, 15, 0),
                "meta": {"student_id": "STU001", "course_id": "CSA101", "school": "CET"},
                "activity_type": "VIDEO_VIEW",
                "resource_id": "R01",
                "duration_sec": 1200,
                "session_id": "SES01",
            },
            {
                "timestamp": datetime(2026, 2, 11, 14, 0, 0),
                "meta": {"student_id": "STU001", "course_id": "CSA101", "school": "CET"},
                "activity_type": "PDF_VIEW",
                "resource_id": "DOC01",
                "duration_sec": 300,
                "session_id": "SES02",
            },
        ]
    )

    yield db

    # Teardown
    drop_managed_collections(db)
    client.drop_database("test_acadexa_aggregations")
    close_mongo_client(client)


def test_course_performance_summary_aggregation(agg_test_db) -> None:
    """Verify $match, $group, $project, $sort in course performance summary."""
    summary = get_course_performance_summary("CSA101", database=agg_test_db)
    assert len(summary) == 2  # S1 and S2

    s1 = next(s for s in summary if s["semester_id"] == "S1")
    assert s1["course_id"] == "CSA101"
    assert s1["total_enrolled"] == 2
    assert s1["avg_internal"] == 30.0  # (35 + 25) / 2
    assert s1["avg_midterm"] == 17.5   # (20 + 15) / 2
    assert s1["avg_endterm"] == 35.0   # (40 + 30) / 2
    assert s1["avg_total"] == 82.5     # (95 + 70) / 2
    assert set(s1["grades"]) == {"A", "C"}

    # Test semester filter
    s2_only = get_course_performance_summary("CSA101", semester_id="S2", database=agg_test_db)
    assert len(s2_only) == 1
    assert s2_only[0]["semester_id"] == "S2"
    assert s2_only[0]["total_enrolled"] == 1


def test_student_academic_profile_lookup_and_unwind(agg_test_db) -> None:
    """Verify $match, $lookup, $unwind, $project, $sort in student transcript."""
    profile = get_student_academic_profile("STU001", database=agg_test_db)
    assert len(profile) == 2  # STU001 is enrolled in CSA101 in S1 and S2

    rec1 = profile[0]
    assert rec1["student_id"] == "STU001"
    assert rec1["school"] == "School of Computer Engineering & Technology"
    assert rec1["course_id"] == "CSA101"
    assert rec1["course_title"] == "Programming Fundamentals"  # joined from courses collection
    assert rec1["difficulty_level"] == "easy"
    assert rec1["semester_id"] == "S1"
    assert rec1["total_marks"] == 95  # 35 + 20 + 40
    assert rec1["final_grade"] == "A"


def test_coursework_completion_overview_group_and_lookup(agg_test_db) -> None:
    """Verify $match, $group, $lookup, $unwind, $project, $sort in coursework tracking."""
    overview = get_coursework_completion_overview("CSA101", database=agg_test_db)
    assert len(overview) == 2

    # Sorted by missing_count descending -> STU002 has 1 missing, STU001 has 0
    assert overview[0]["student_id"] == "STU002"
    assert overview[0]["missing_count"] == 1
    assert overview[0]["completion_rate"] == 0.0
    assert overview[0]["program"] == "B.Tech CSE"  # joined from students

    assert overview[1]["student_id"] == "STU001"
    assert overview[1]["total_items"] == 2
    assert overview[1]["on_time_count"] == 1
    assert overview[1]["late_count"] == 1
    assert overview[1]["missing_count"] == 0
    assert overview[1]["completion_rate"] == 100.0


def test_attendance_weekly_trends_set_window_fields(agg_test_db) -> None:
    """Verify $match, $project, $sort, $setWindowFields in rolling attendance calculations."""
    trends = get_attendance_weekly_trends("STU001", "CSA101", window_size=3, database=agg_test_db)
    assert len(trends) == 4

    # Rates:
    # Week 1: 4/4 = 100%
    # Week 2: 3/4 = 75%
    # Week 3: 2/4 = 50%
    # Week 4: 1/4 = 25%
    w1, w2, w3, w4 = trends

    assert w1["week_sequence"] == 1
    assert w1["weekly_rate"] == 100.0
    assert w1["rolling_avg_attendance"] == 100.0
    assert w1["cumulative_classes_conducted"] == 4
    assert w1["cumulative_classes_attended"] == 4

    assert w2["week_sequence"] == 2
    assert w2["weekly_rate"] == 75.0
    assert w2["rolling_avg_attendance"] == 87.5  # (100 + 75) / 2
    assert w2["cumulative_classes_conducted"] == 8
    assert w2["cumulative_classes_attended"] == 7

    assert w3["week_sequence"] == 3
    assert w3["weekly_rate"] == 50.0
    assert w3["rolling_avg_attendance"] == 75.0  # (100 + 75 + 50) / 3
    assert w3["cumulative_classes_conducted"] == 12
    assert w3["cumulative_classes_attended"] == 9

    assert w4["week_sequence"] == 4
    assert w4["weekly_rate"] == 25.0
    assert w4["rolling_avg_attendance"] == 50.0  # (75 + 50 + 25) / 3 (window size 3 excludes week 1)
    assert w4["cumulative_classes_conducted"] == 16
    assert w4["cumulative_classes_attended"] == 10


def test_course_cohort_multi_facet_aggregation(agg_test_db) -> None:
    """Verify $match, $facet, $group, $sort, $project in multi-faceted course dashboard analysis."""
    facets = get_course_cohort_multi_facet("CSA101", semester_id="S1", database=agg_test_db)

    # 1. Facet: Grade Distribution
    assert "grade_distribution" in facets
    grades = {g["grade"]: g["count"] for g in facets["grade_distribution"]}
    assert grades == {"A": 1, "C": 1}

    # 2. Facet: Overall Statistics
    assert "overall_stats" in facets
    stats = facets["overall_stats"][0]
    assert stats["cohort_size"] == 2
    assert stats["min_total"] == 70.0
    assert stats["max_total"] == 95.0
    assert stats["avg_total"] == 82.5

    # 3. Facet: Component Averages
    assert "component_averages" in facets
    comp = facets["component_averages"][0]
    assert comp["avg_internal"] == 30.0
    assert comp["avg_midterm"] == 17.5
    assert comp["avg_endterm"] == 35.0

    # 4. Facet: Top Performers
    assert "top_performers" in facets
    assert len(facets["top_performers"]) == 2
    assert facets["top_performers"][0]["student_id"] == "STU001"
    assert facets["top_performers"][0]["total_marks"] == 95


def test_lms_activity_timeline_aggregation(agg_test_db) -> None:
    """Verify $match, $project, $group, $sort in time-series LMS daily activity aggregation."""
    timeline = get_lms_activity_timeline("CSA101", database=agg_test_db)
    assert len(timeline) == 3

    # Days: 2026-02-10 (LOGIN: 1, VIDEO_VIEW: 1), 2026-02-11 (PDF_VIEW: 1)
    d1_login = next(t for t in timeline if t["day"] == "2026-02-10" and t["activity_type"] == "LOGIN")
    assert d1_login["event_count"] == 1
    assert d1_login["total_duration_sec"] == 60

    d1_video = next(t for t in timeline if t["day"] == "2026-02-10" and t["activity_type"] == "VIDEO_VIEW")
    assert d1_video["event_count"] == 1
    assert d1_video["total_duration_sec"] == 1200
    assert d1_video["total_duration_min"] == 20.0

    d2_pdf = next(t for t in timeline if t["day"] == "2026-02-11" and t["activity_type"] == "PDF_VIEW")
    assert d2_pdf["event_count"] == 1
    assert d2_pdf["total_duration_sec"] == 300


def test_run_aggregation_error_handling(agg_test_db) -> None:
    """Verify AggregationError when invalid pipeline stages are executed."""
    with pytest.raises(AggregationError, match="Aggregation pipeline failed"):
        run_aggregation("students", [{"$invalidStage": {}}], database=agg_test_db)


def test_run_aggregation_unreachable() -> None:
    """Verify MongoConnectionError when connecting to an unreachable host."""
    unreachable_cfg = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_unreachable",
        server_selection_timeout_ms=50,
        connect_timeout_ms=50,
    )
    with pytest.raises(MongoConnectionError, match="Cannot connect to MongoDB"):
        run_aggregation("students", [], config=unreachable_cfg)
