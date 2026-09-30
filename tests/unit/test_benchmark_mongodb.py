"""Unit tests for the MongoDB weekly-engagement benchmark (Task 13.3, F-F03).

Covers pipeline construction (pure, hermetic), exact aggregation on
seeded data in an isolated database, the timed workload wrapper and
unreachable-server handling. Live parts skip when MongoDB is down.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from acadexa.benchmarks.mongodb.weekly_engagement import (
    DEFAULT_COLLECTION,
    WORKLOAD_ID,
    aggregate_weekly_engagement_mongo,
    build_weekly_engagement_pipeline,
    run_weekly_engagement_mongodb,
)
from acadexa.benchmarks.runner import ENGINE_MONGODB
from acadexa.database import (
    MongoDBConfig,
    check_connection,
    close_mongo_client,
    get_database,
    get_mongo_client,
)
from acadexa.processing.jobs.event_aggregation import (
    APPROVED_ACTIVITY_CATEGORIES,
    SEMESTER_BOUNDS,
)


def _seed_events() -> list[dict]:
    """Hand-built events mirroring the pandas fixture (BSON datetimes)."""
    base = {"course_id": " cs101 ", "school": "ENG"}
    return [
        {
            "timestamp": datetime(2024, 7, 15, 10, 0, 0),
            "meta": {"student_id": " stu1 ", **base},
            "activity_type": "VIDEO_VIEW",
            "duration_sec": 300,
        },
        {
            "timestamp": datetime(2024, 7, 15, 11, 0, 0),
            "meta": {"student_id": "STU1", **{k: v.strip() for k, v in base.items()}},
            "activity_type": "LOGIN",
            "duration_sec": None,
        },
        {
            "timestamp": datetime(2024, 7, 16, 10, 0, 0),
            "meta": {"student_id": "STU1", **{k: v.strip() for k, v in base.items()}},
            "activity_type": "QUIZ_ATTEMPT",
            "duration_sec": -5,
        },
        {
            "timestamp": datetime(2024, 7, 22, 10, 0, 0),
            "meta": {"student_id": "STU1", **{k: v.strip() for k, v in base.items()}},
            "activity_type": "FORUM_POST",
            "duration_sec": 60,
        },
        {
            "timestamp": datetime(2024, 7, 15, 12, 0, 0),
            "meta": {"student_id": "STU2", "course_id": "CS101", "school": "ENG"},
            "activity_type": "VIDEO_VIEW",
            "duration_sec": 100,
        },
        {
            "timestamp": datetime(2023, 1, 2, 10, 0, 0),
            "meta": {"student_id": "STU1", "course_id": "CS101", "school": "ENG"},
            "activity_type": "LOGIN",
            "duration_sec": 10,
        },
    ]


def test_pipeline_structure_without_match() -> None:
    """Pipeline stages, Monday weeks and J2-equivalent grain without $match."""
    pipeline = build_weekly_engagement_pipeline()
    operators = [next(iter(stage)) for stage in pipeline]
    assert operators[0] == "$project"
    assert "$group" in operators
    assert operators[-1] == "$sort"
    assert all("$match" not in stage for stage in pipeline)

    project = pipeline[0]["$project"]
    assert project["week_start"]["$dateTrunc"]["startOfWeek"] == "monday"

    group_id = next(s["$group"]["_id"] for s in pipeline if "$group" in s)
    assert sorted(group_id) == [
        "course_id",
        "school",
        "semester_id",
        "student_id",
        "week_number",
        "week_start",
    ]


def test_pipeline_match_is_first_stage_only_when_given() -> None:
    """Optional $match leads the pipeline and nothing else changes."""
    match = {"meta.school": "ENG"}
    with_match = build_weekly_engagement_pipeline(match)
    without_match = build_weekly_engagement_pipeline()
    assert with_match[0] == {"$match": match}
    assert with_match[1:] == without_match


def test_pipeline_categories_and_semesters_match_j2() -> None:
    """Category sets and semester branches track the canonical J2 constants."""
    pipeline = build_weekly_engagement_pipeline()
    dump = str(pipeline)
    for category, types in APPROVED_ACTIVITY_CATEGORIES.items():
        for event_type in types:
            assert event_type in dump, f"{event_type} ({category}) missing"
    add_fields = next(s for s in pipeline if "$addFields" in s and "semester_id" in s["$addFields"])
    branches = add_fields["$addFields"]["semester_id"]["$switch"]["branches"]
    assert [b["then"] for b in branches] == [sem for sem, _, _ in SEMESTER_BOUNDS]


def _live_db():
    """Isolated database handle, or skip when MongoDB is unreachable."""
    config = MongoDBConfig(database="test_acadexa_bench_mongo")
    if not check_connection(config=config):
        pytest.skip("MongoDB is not reachable in current environment")
    client = get_mongo_client(config)
    db = get_database(config, client=client)
    return config, client, db


def _row(rows: list[dict], student: str, week: str) -> dict:
    """Select one weekly group row by student and ISO week_start."""
    matches = [
        r
        for r in rows
        if r["student_id"] == student and r["week_start"].date().isoformat() == week
    ]
    assert len(matches) == 1
    return matches[0]


def test_aggregate_matches_j2_semantics_on_seeded_data() -> None:
    """Exact weekly aggregation over seeded events in an isolated collection."""
    _, client, db = _live_db()
    try:
        db["bench_lms_events"].drop()
        db["bench_lms_events"].insert_many(_seed_events())

        rows = aggregate_weekly_engagement_mongo(
            database=db, collection="bench_lms_events"
        )
        assert len(rows) == 4

        first = _row(rows, "STU1", "2024-07-15")
        assert first["course_id"] == "CS101"
        assert first["school"] == "ENG"
        assert first["semester_id"] == "S1"
        assert first["week_number"] == 1
        assert isinstance(first["week_number"], int)
        assert first["total_events"] == 3
        assert first["total_duration_sec"] == 300  # null/negative contribute 0
        assert first["active_days"] == 2
        assert first["content_views"] == 1
        assert first["assessment_events"] == 1
        assert first["access_events"] == 1
        assert first["participation_events"] == 0
        assert first["video_views"] == 1
        assert first["quiz_attempts"] == 1
        assert first["logins"] == 1

        second = _row(rows, "STU1", "2024-07-22")
        assert (second["total_events"], second["forum_posts"]) == (1, 1)
        assert second["week_number"] == 2

        unknown = _row(rows, "STU1", "2023-01-02")
        assert unknown["semester_id"] == "UNKNOWN"
        assert unknown["week_number"] == 1
    finally:
        client.drop_database("test_acadexa_bench_mongo")
        close_mongo_client(client)


def test_run_weekly_engagement_mongodb_end_to_end() -> None:
    """Timed workload on seeded data records measured results."""
    _, client, db = _live_db()
    try:
        db["bench_lms_events"].drop()
        db["bench_lms_events"].insert_many(_seed_events())

        result = run_weekly_engagement_mongodb(
            database=db, collection="bench_lms_events"
        )
        assert result.workload_id == WORKLOAD_ID
        assert result.engine == ENGINE_MONGODB
        assert result.success is True
        assert result.error is None
        assert result.input_rows == 6
        assert result.output_rows == 4
        assert result.duration_sec >= 0.0
        assert result.extra["collection"] == "bench_lms_events"
    finally:
        client.drop_database("test_acadexa_bench_mongo")
        close_mongo_client(client)


def test_run_weekly_engagement_mongodb_unreachable() -> None:
    """Unreachable servers record failure without raising."""
    bad = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_acadexa_bench_unreachable",
        server_selection_timeout_ms=100,
        connect_timeout_ms=100,
    )
    result = run_weekly_engagement_mongodb(config=bad, collection="bench_lms_events")
    assert result.success is False
    assert result.input_rows == 0
    assert result.error is not None


def test_default_collection_is_lms_events() -> None:
    """The benchmark targets the LMS serving collection by default."""
    assert DEFAULT_COLLECTION == "lms_events"


def test_run_benchmarks_cli_mongodb_engine(tmp_path: Path) -> None:
    """CLI runs the MongoDB engine against live data and saves the manifest."""
    from acadexa.benchmarks.runner import BenchmarkRun
    import scripts.run_benchmarks as run_benchmarks_script

    cfg = MongoDBConfig.from_env()
    if not check_connection(config=cfg):
        pytest.skip("MongoDB is not reachable in current environment")

    manifest_path = tmp_path / "benchmark_run_manifest.json"
    exit_code = run_benchmarks_script.main(
        [
            "--workload",
            "weekly_lms_engagement",
            "--engine",
            "mongodb",
            "--manifest-path",
            str(manifest_path),
            "--quiet",
        ]
    )
    assert exit_code == 0
    assert manifest_path.exists()

    run = BenchmarkRun.load(manifest_path)
    assert len(run.results) == 1
    assert run.results[0].engine == ENGINE_MONGODB
    assert run.results[0].input_rows > 0
    assert run.results[0].output_rows > 0
