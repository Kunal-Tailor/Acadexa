"""Unit tests for the pandas/MongoDB feature-table join (Task 13.5, F-F03).

Covers join correctness on hand-built fixtures (outer/left semantics,
identifier normalization, semester derivation, zero fills), the timed
workload wrappers and unreachable-server handling. The Spark engine has
its own module-scoped session file. Fast except live-Mongo parts, which
skip when MongoDB is down.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from acadexa.benchmarks.mongodb.feature_join import (
    aggregate_feature_join_mongo,
    build_feature_join_pipeline,
    run_feature_table_join_mongodb,
)
from acadexa.benchmarks.pandas.feature_join import (
    WORKLOAD_ID,
    aggregate_academic,
    aggregate_attendance,
    aggregate_coursework,
    aggregate_lms_weekly,
    join_feature_table,
    load_domain_frames,
    run_feature_table_join_pandas,
)
from acadexa.benchmarks.runner import ENGINE_MONGODB, ENGINE_PANDAS
from acadexa.database import (
    MongoDBConfig,
    check_connection,
    close_mongo_client,
    get_database,
    get_mongo_client,
)


def _academic() -> pd.DataFrame:
    """Two students/courses with mixed-case identifiers."""
    return pd.DataFrame(
        [
            {"student_id": " s1 ", "course_id": " c1 ", "semester_id": "S1",
             "internal_marks": 30, "midterm_marks": 30, "endterm_marks": 40},
            {"student_id": "S2", "course_id": "C2", "semester_id": "S1",
             "internal_marks": 10, "midterm_marks": 10, "endterm_marks": 10},
        ]
    )


def _attendance() -> pd.DataFrame:
    """Two weekly rows for S1/C1 plus one for S2/C2."""
    return pd.DataFrame(
        [
            {"student_id": "S1", "course_id": "C1", "semester_id": "S1",
             "classes_conducted": 4, "classes_attended": 3},
            {"student_id": "S1", "course_id": "C1", "semester_id": "S1",
             "classes_conducted": 2, "classes_attended": 2},
            {"student_id": "S2", "course_id": "C2", "semester_id": "S1",
             "classes_conducted": 4, "classes_attended": 4},
        ]
    )


def _coursework() -> pd.DataFrame:
    """S1 items in S1/S2 semesters plus an undated UNKNOWN item."""
    return pd.DataFrame(
        [
            {"student_id": "S1", "course_id": "C1", "item_id": "A01",
             "item_type": "ASSIGNMENT", "due_date": "2024-08-01",
             "status": "ON_TIME"},
            {"student_id": "S1", "course_id": "C1", "item_id": "A02",
             "item_type": "ASSIGNMENT", "due_date": "2024-08-01",
             "status": "LATE"},
            {"student_id": "S1", "course_id": "C1", "item_id": "Q01",
             "item_type": "QUIZ", "due_date": "2024-08-01",
             "status": "MISSING"},
            {"student_id": "S2", "course_id": "C2", "item_id": "A01",
             "item_type": "ASSIGNMENT", "due_date": "2025-02-01",
             "status": "ON_TIME"},
            {"student_id": "S1", "course_id": "C1", "item_id": "A09",
             "item_type": "ASSIGNMENT", "due_date": None,
             "status": "ON_TIME"},
        ]
    )


def _lms_weekly() -> pd.DataFrame:
    """Two weekly rows for S1/C1 plus one for S2/C2."""
    return pd.DataFrame(
        [
            {"student_id": "S1", "course_id": "C1", "semester_id": "S1",
             "week_start": "2024-07-15", "total_events": 10},
            {"student_id": "S1", "course_id": "C1", "semester_id": "S1",
             "week_start": "2024-07-22", "total_events": 5},
            {"student_id": "S2", "course_id": "C2", "semester_id": "S1",
             "week_start": "2024-07-15", "total_events": 20},
        ]
    )


def _row(frame: pd.DataFrame, student: str, course: str, semester: str) -> pd.Series:
    """Select one joined row by grain key."""
    matches = frame[
        (frame["student_id"] == student)
        & (frame["course_id"] == course)
        & (frame["semester_id"] == semester)
    ]
    assert len(matches) == 1
    return matches.iloc[0]


def test_join_feature_table_exact_values() -> None:
    """Outer join aggregates every domain with zero fills and normalization."""
    joined = join_feature_table(_academic(), _attendance(), _coursework(), _lms_weekly())
    assert len(joined) == 4  # S1/C1/S1, S2/C2/S1, S1/C1/S2, S1/C1/UNKNOWN

    first = _row(joined, "S1", "C1", "S1")
    assert first["total_marks"] == 100
    assert (first["classes_conducted"], first["classes_attended"]) == (6, 5)
    assert (first["total_coursework"], first["total_submissions"]) == (3, 2)
    assert first["late_submissions"] == 1
    assert first["lms_total_events"] == 15

    second = _row(joined, "S2", "C2", "S1")
    assert second["total_marks"] == 30
    assert second["total_coursework"] == 0  # S2 item lands in S2 semester
    assert second["lms_total_events"] == 20

    unknown = _row(joined, "S1", "C1", "UNKNOWN")
    assert unknown["total_marks"] == 0
    assert unknown["total_coursework"] == 1
    assert unknown["lms_total_events"] == 0

    s2_semester = _row(joined, "S2", "C2", "S2")
    assert s2_semester["total_coursework"] == 1
    assert s2_semester["total_marks"] == 0
    assert s2_semester["lms_total_events"] == 0


def test_domain_aggregations_individually() -> None:
    """Per-domain aggregations normalize ids and count correctly."""
    assert aggregate_academic(_academic())["total_marks"].tolist() == [100, 30]
    att = aggregate_attendance(_attendance())
    assert _row(att, "S1", "C1", "S1")["classes_attended"] == 5
    cwk = aggregate_coursework(_coursework())
    assert len(cwk) == 3  # S1/C1/S1, S2/C2/S1, S1/C1/UNKNOWN
    lms = aggregate_lms_weekly(_lms_weekly())
    assert _row(lms, "S1", "C1", "S1")["lms_total_events"] == 15


def test_load_domain_frames_missing_base(tmp_path: Path) -> None:
    """Missing domain datasets fail fast instead of benchmarking nothing."""
    with pytest.raises(FileNotFoundError, match="Domain dataset not found"):
        load_domain_frames(tmp_path / "nope")


def _write_domain_base(base: Path) -> None:
    """Write the four hand-built domain datasets as Parquet directories."""
    base.mkdir(parents=True, exist_ok=True)
    _academic().to_parquet(base / "academic_records")
    _attendance().to_parquet(base / "attendance")
    _coursework().to_parquet(base / "coursework")
    _lms_weekly().to_parquet(base / "lms_weekly_engagement")


def test_run_feature_table_join_pandas_end_to_end(tmp_path: Path) -> None:
    """Timed join workload on tiny Parquet data records measured results."""
    base = tmp_path / "processed"
    _write_domain_base(base)

    result = run_feature_table_join_pandas(base)
    assert result.workload_id == WORKLOAD_ID
    assert result.engine == ENGINE_PANDAS
    assert result.success is True
    assert result.input_rows == 2 + 3 + 5 + 3
    assert result.output_rows == 4
    assert result.duration_sec >= 0.0
    assert result.extra["join_semantics"] == "outer"


def test_run_benchmarks_cli_feature_join_pandas(tmp_path: Path) -> None:
    """CLI runs the pandas join workload and saves the raw run manifest."""
    import scripts.run_benchmarks as run_benchmarks_script
    from acadexa.benchmarks.runner import BenchmarkRun

    base = tmp_path / "processed"
    _write_domain_base(base)
    manifest_path = tmp_path / "benchmark_run_manifest.json"

    exit_code = run_benchmarks_script.main(
        [
            "--workload",
            "feature_table_join",
            "--engine",
            "pandas",
            "--base-path",
            str(base),
            "--manifest-path",
            str(manifest_path),
            "--quiet",
        ]
    )
    assert exit_code == 0
    run = BenchmarkRun.load(manifest_path)
    assert run.results[0].workload_id == WORKLOAD_ID
    assert run.results[0].output_rows == 4


# ── MongoDB join engine ────────────────────────────────────────────


def test_feature_join_pipeline_structure() -> None:
    """Left join from academic records with compound-key lookups."""
    pipeline = build_feature_join_pipeline()
    operators = [next(iter(stage)) for stage in pipeline]
    assert operators.count("$lookup") == 2
    assert operators[-1] == "$sort"
    lookups = [s["$lookup"] for s in pipeline if "$lookup" in s]
    assert {lk["from"] for lk in lookups} == {"attendance", "coursework"}
    assert lookups[0]["let"] == {"sid": "$student_id", "cid": "$course_id", "sem": "$semester_id"}

    matched = build_feature_join_pipeline({"semester_id": "S1"})
    assert matched[0] == {"$match": {"semester_id": "S1"}}


def _seed_academic() -> list[dict]:
    """Three academic rows, one without any joined domain data."""
    return [
        {"student_id": "S1", "course_id": "C1", "semester_id": "S1",
         "internal_marks": 30, "midterm_marks": 30, "endterm_marks": 40},
        {"student_id": "S2", "course_id": "C2", "semester_id": "S1",
         "internal_marks": 10, "midterm_marks": 10, "endterm_marks": 10},
        {"student_id": "S9", "course_id": "C9", "semester_id": "S1",
         "internal_marks": 5, "midterm_marks": 5, "endterm_marks": 5},
    ]


def _seed_attendance() -> list[dict]:
    return [
        {"student_id": "S1", "course_id": "C1", "semester_id": "S1",
         "classes_conducted": 4, "classes_attended": 3},
        {"student_id": "S1", "course_id": "C1", "semester_id": "S1",
         "classes_conducted": 2, "classes_attended": 2},
    ]


def _seed_coursework() -> list[dict]:
    """Coursework without semester_id (as cleaned); semester derives from due dates."""
    return [
        {"student_id": "S1", "course_id": "C1", "item_id": "A01",
         "item_type": "ASSIGNMENT", "due_date": "2024-08-01", "status": "ON_TIME"},
        {"student_id": "S1", "course_id": "C1", "item_id": "A02",
         "item_type": "ASSIGNMENT", "due_date": "2024-08-01", "status": "LATE"},
        {"student_id": "S1", "course_id": "C1", "item_id": "Q01",
         "item_type": "QUIZ", "due_date": "2024-08-01", "status": "MISSING"},
    ]


def _live_db():
    """Isolated database handle, or skip when MongoDB is unreachable."""
    config = MongoDBConfig(database="test_acadexa_bench_join")
    if not check_connection(config=config):
        pytest.skip("MongoDB is not reachable in current environment")
    client = get_mongo_client(config)
    return config, client, get_database(config, client=client)


def _join_row(rows: list[dict], student: str) -> dict:
    matches = [r for r in rows if r["student_id"] == student]
    assert len(matches) == 1
    return matches[0]


def test_aggregate_feature_join_mongo_on_seeded_data() -> None:
    """Exact left-join aggregation with zero fills for missing domains."""
    _, client, db = _live_db()
    try:
        db["academic_records"].insert_many(_seed_academic())
        db["attendance"].insert_many(_seed_attendance())
        db["coursework"].insert_many(_seed_coursework())

        rows = aggregate_feature_join_mongo(database=db)
        assert len(rows) == 3

        first = _join_row(rows, "S1")
        assert first["course_id"] == "C1"
        assert first["total_marks"] == 100
        assert (first["classes_conducted"], first["classes_attended"]) == (6, 5)
        assert (first["total_coursework"], first["total_submissions"]) == (3, 2)
        assert first["late_submissions"] == 1

        lonely = _join_row(rows, "S9")
        assert lonely["total_marks"] == 15
        assert lonely["classes_conducted"] == 0
        assert lonely["total_coursework"] == 0
        assert lonely["late_submissions"] == 0
    finally:
        client.drop_database("test_acadexa_bench_join")
        close_mongo_client(client)


def test_run_feature_table_join_mongodb_end_to_end() -> None:
    """Timed join workload on seeded data records measured results."""
    _, client, db = _live_db()
    try:
        db["academic_records"].insert_many(_seed_academic())
        db["attendance"].insert_many(_seed_attendance())
        db["coursework"].insert_many(_seed_coursework())

        result = run_feature_table_join_mongodb(database=db)
        assert result.workload_id == WORKLOAD_ID
        assert result.engine == ENGINE_MONGODB
        assert result.success is True
        assert result.input_rows == 3
        assert result.output_rows == 3
        assert result.extra["join_semantics"] == "left"
    finally:
        client.drop_database("test_acadexa_bench_join")
        close_mongo_client(client)


def test_run_feature_table_join_mongodb_unreachable() -> None:
    """Unreachable servers record failure without raising."""
    bad = MongoDBConfig(
        uri="mongodb://localhost:29999",
        database="test_acadexa_bench_join_unreachable",
        server_selection_timeout_ms=100,
        connect_timeout_ms=100,
    )
    result = run_feature_table_join_mongodb(config=bad)
    assert result.success is False
    assert result.error is not None
