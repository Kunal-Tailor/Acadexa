"""Unit tests for Spark J7 gold analytical collections publication (Tasks 9.1-9.4, rules.md §18, §19)."""

from __future__ import annotations

import ast
from datetime import date, datetime
import inspect
from pathlib import Path
import pytest
from pymongo import MongoClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DateType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from acadexa.database.client import MongoDBConfig, check_connection
from acadexa.processing.jobs.publish_gold import (
    J7Config,
    J7Result,
    build_course_metrics,
    build_school_summary,
    publish_course_metrics,
    publish_risk_indicators,
    publish_school_summary,
    publish_student_features,
    run_j7_publish_gold,
)
import acadexa.processing.jobs.publish_gold as publish_gold_module
from acadexa.processing.jobs.feature_table import build_student_semester_features
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)
from acadexa.processing.mongo import (
    get_or_create_mongo_spark_session,
)
from acadexa.validation import (
    COURSE_METRICS_SCHEMA,
    GoldValidationError,
    RISK_INDICATORS_SCHEMA,
    SCHOOL_SUMMARY_SCHEMA,
    STUDENT_FEATURES_SCHEMA,
    validate_gold_collections,
    validate_gold_dataframe,
    validate_gold_mongodb,
    validate_record,
)
import acadexa.validation.gold as gold_validation_module


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    """Module-scoped SparkSession fixture for gold publication tests."""
    cfg = SparkRuntimeConfig(
        app_name="TestPublishGold",
        master="local[2]",
        shuffle_partitions=2,
    )
    spark = get_or_create_mongo_spark_session(cfg)
    try:
        yield spark
    finally:
        stop_spark_session(spark)


@pytest.fixture
def sample_feature_table(spark_session: SparkSession) -> list[tuple]:
    """Sample student-course-semester feature records for gold testing."""
    return [
        # student_id, course_id, semester_id, attendance_percentage, lms_total_events, total_submissions, late_submissions, exam_marks_trend, academic_score, course_title, school, department, course_difficulty
        ("STU010482", "CSA101", "S1", 80.0, 150, 5, 1, -12.0, 72.0, "Intro CS", "School of Technology", "Computer Science", 0.4),
        ("STU010482", "CSA102", "S1", 77.0, 262, 5, 1, -12.0, 70.4, "Data Struct", "School of Technology", "Computer Science", 0.6),
        ("STU020001", "CSA101", "S1", 90.0, 300, 5, 0, 5.0, 85.0, "Intro CS", "School of Technology", "Computer Science", 0.4),
        ("STU030001", "MGT101", "S1", 85.0, 200, 4, 1, 2.0, 78.0, "Prin Mgmt", "School of Business", "Management", 0.3),
        ("STU030001", "MGT102", "S1", 82.0, 180, 4, 0, 0.0, 75.0, "Marketing", "School of Business", "Management", 0.5),
    ]


@pytest.fixture
def feature_table_df(spark_session: SparkSession, sample_feature_table: list[tuple]):
    """DataFrame for sample feature table."""
    cols = [
        "student_id",
        "course_id",
        "semester_id",
        "attendance_percentage",
        "lms_total_events",
        "total_submissions",
        "late_submissions",
        "exam_marks_trend",
        "academic_score",
        "course_title",
        "school",
        "department",
        "course_difficulty",
    ]
    return spark_session.createDataFrame(sample_feature_table, cols)


@pytest.fixture
def sample_risk_indicators_df(spark_session: SparkSession):
    """Sample DataFrame for student risk indicators."""
    data = [
        (
            "STU010482",
            date(2026, 4, 20),
            3,
            True,
            True,
            False,
            True,
            False,
            {
                "low_attendance": "term-to-date attendance 68.0% < 75.0% threshold",
                "lms_decline": "last 4 weeks = 42.0% of previous 4 weeks (<= 50.0% threshold)",
                "late_submissions": "late rate 20.0% <= 30.0% threshold",
                "marks_decline": "recent graded items dropped by 12.0 pts (>= 10.0 pts below)",
                "low_quiz_activity": "quiz attempts 6 not in bottom quartile (>= 25.0th percentile)",
            },
            datetime(2026, 4, 20, 10, 0, 0),
        ),
        (
            "STU020001",
            date(2026, 4, 20),
            0,
            False,
            False,
            False,
            False,
            False,
            {
                "low_attendance": "term-to-date attendance 90.0% >= 75.0% threshold",
                "lms_decline": "LMS activity stable (ratio 120.0% > 50.0% threshold)",
                "late_submissions": "late rate 0.0% <= 30.0% threshold",
                "marks_decline": "graded items trajectory stable (drop 0.0 pts < 10.0 pts threshold)",
                "low_quiz_activity": "quiz attempts 8 not in bottom quartile (>= 25.0th percentile)",
            },
            datetime(2026, 4, 20, 10, 0, 0),
        ),
        (
            "STU030001",
            date(2026, 4, 20),
            1,
            False,
            False,
            True,
            False,
            False,
            {
                "low_attendance": "term-to-date attendance 85.0% >= 75.0% threshold",
                "lms_decline": "LMS activity stable (ratio 95.0% > 50.0% threshold)",
                "late_submissions": "late rate 35.0% > 30.0% threshold",
                "marks_decline": "graded items trajectory stable (drop 2.0 pts < 10.0 pts threshold)",
                "low_quiz_activity": "quiz attempts 5 not in bottom quartile (>= 25.0th percentile)",
            },
            datetime(2026, 4, 20, 10, 0, 0),
        ),
    ]
    schema = StructType([
        StructField("student_id", StringType(), False),
        StructField("week_start", DateType(), False),
        StructField("signal_count", IntegerType(), False),
        StructField("low_attendance", BooleanType(), False),
        StructField("lms_decline", BooleanType(), False),
        StructField("late_submissions", BooleanType(), False),
        StructField("marks_decline", BooleanType(), False),
        StructField("low_quiz_activity", BooleanType(), False),
        StructField(
            "explanations",
            StructType([
                StructField("low_attendance", StringType(), False),
                StructField("lms_decline", StringType(), False),
                StructField("late_submissions", StringType(), False),
                StructField("marks_decline", StringType(), False),
                StructField("low_quiz_activity", StringType(), False),
            ]),
            False,
        ),
        StructField("computed_at", TimestampType(), False),
    ])
    return spark_session.createDataFrame(data, schema)


def test_build_student_features_conforms_to_schema(feature_table_df) -> None:
    """Verify build_student_semester_features output strictly conforms to STUDENT_FEATURES_SCHEMA (Task 9.1)."""
    sf_df = build_student_semester_features(feature_table_df)

    # Check grain: student_id x semester_id
    total_count = sf_df.count()
    distinct_grain = sf_df.select("student_id", "semester_id").distinct().count()
    assert total_count == distinct_grain == 3

    # Collect and validate each record with Phase 3 validator
    records = sf_df.toPandas().to_dict(orient="records")
    for rec in records:
        validate_record(rec, STUDENT_FEATURES_SCHEMA)

    # Verify specific aggregation values for STU010482
    stu1 = next(r for r in records if r["student_id"] == "STU010482")
    assert stu1["attendance_mean"] == pytest.approx(78.5, 0.01)
    assert stu1["engagement_count"] == 412
    assert stu1["late_submission_rate"] == pytest.approx(0.2, 0.01)
    assert stu1["score_trend"] == pytest.approx(-12.0, 0.01)


def test_build_course_metrics_conforms_to_schema(feature_table_df) -> None:
    """Verify build_course_metrics output strictly conforms to COURSE_METRICS_SCHEMA (Task 9.2)."""
    cm_df = build_course_metrics(feature_table_df)

    # Check grain: course_id x semester_id
    total_count = cm_df.count()
    distinct_grain = cm_df.select("course_id", "semester_id").distinct().count()
    assert total_count == distinct_grain == 4  # CSA101, CSA102, MGT101, MGT102

    # Required fields in schema
    expected_fields = {"course_id", "semester_id", "avg_performance", "avg_attendance", "engagement_count", "difficulty_adjusted_performance"}
    assert expected_fields.issubset(set(cm_df.columns))

    records = cm_df.toPandas().to_dict(orient="records")
    for rec in records:
        validate_record(rec, COURSE_METRICS_SCHEMA)

    # Check CSA101: 2 students (72.0 and 85.0 -> avg 78.5; attendance 80.0 and 90.0 -> avg 85.0)
    csa101 = next(r for r in records if r["course_id"] == "CSA101")
    assert csa101["avg_performance"] == pytest.approx(78.5, 0.01)
    assert csa101["avg_attendance"] == pytest.approx(85.0, 0.01)
    assert csa101["engagement_count"] == 450
    assert isinstance(csa101["difficulty_adjusted_performance"], float)


def test_build_school_summary_conforms_to_schema(feature_table_df) -> None:
    """Verify build_school_summary output strictly conforms to SCHOOL_SUMMARY_SCHEMA (Task 9.2)."""
    ss_df = build_school_summary(feature_table_df)

    # Check grain: school x department
    total_count = ss_df.count()
    distinct_grain = ss_df.select("school", "department").distinct().count()
    assert total_count == distinct_grain == 2  # Tech/CS, Business/Management

    expected_fields = {"school", "department", "student_count", "course_count", "avg_performance", "avg_attendance", "engagement_count"}
    assert expected_fields.issubset(set(ss_df.columns))

    records = ss_df.toPandas().to_dict(orient="records")
    for rec in records:
        validate_record(rec, SCHOOL_SUMMARY_SCHEMA)

    tech = next(r for r in records if r["school"] == "School of Technology")
    assert tech["department"] == "Computer Science"
    assert tech["student_count"] == 2
    assert tech["course_count"] == 2
    assert tech["engagement_count"] == 712


def test_publish_risk_indicators_with_breakdown_and_metadata(
    spark_session: SparkSession,
    sample_risk_indicators_df,
    tmp_path: Path,
) -> None:
    """Verify publish_risk_indicators calculates signal breakdown and preserves run metadata (Task 9.3)."""
    gold_path = tmp_path / "gold"
    cfg = J7Config(
        parquet_base_path=gold_path,
        save_parquet=True,
        publish_to_mongo=False,
    )

    published_df, count, breakdown = publish_risk_indicators(
        spark_session,
        sample_risk_indicators_df,
        config=cfg,
    )

    assert count == 3
    assert (gold_path / "risk_indicators").exists()

    # Verify signal breakdown
    assert breakdown["total_students"] == 3
    assert breakdown["flagged_students"] == 2
    assert breakdown["high_risk_students"] == 1
    assert breakdown["signal_count_distribution"] == {0: 1, 1: 1, 2: 0, 3: 1, 4: 0, 5: 0}
    assert breakdown["flag_counts"]["low_attendance"] == 1
    assert breakdown["flag_counts"]["lms_decline"] == 1
    assert breakdown["flag_counts"]["late_submissions"] == 1
    assert breakdown["flag_counts"]["marks_decline"] == 1
    assert breakdown["flag_counts"]["low_quiz_activity"] == 0

    # Verify schema conformance
    records = published_df.toPandas().to_dict(orient="records")
    for rec in records:
        validate_record(rec, RISK_INDICATORS_SCHEMA)


def test_validate_gold_dataframe_checks_count_grain_fields(
    sample_risk_indicators_df,
    feature_table_df,
) -> None:
    """Verify validate_gold_dataframe validates counts, grains, and required fields (Task 9.4)."""
    # 1. Valid risk indicators pass
    res_ri = validate_gold_dataframe(sample_risk_indicators_df, "risk_indicators")
    assert res_ri.is_valid is True
    assert res_ri.row_count == 3
    assert res_ri.grain_unique is True
    assert res_ri.errors == []

    # 2. Negative test: Grain violation (duplicate student_id x week_start)
    dup_df = sample_risk_indicators_df.union(sample_risk_indicators_df.limit(1))
    res_dup = validate_gold_dataframe(dup_df, "risk_indicators")
    assert res_dup.is_valid is False
    assert res_dup.grain_unique is False
    assert any("Grain violation" in err for err in res_dup.errors)

    # 3. Negative test: Missing required fields
    missing_col_df = sample_risk_indicators_df.drop("signal_count")
    res_missing = validate_gold_dataframe(missing_col_df, "risk_indicators")
    assert res_missing.is_valid is False
    assert "signal_count" in res_missing.missing_fields

    # 4. Negative test: Empty DataFrame
    empty_df = sample_risk_indicators_df.filter(F.lit(False))
    res_empty = validate_gold_dataframe(empty_df, "risk_indicators", allow_empty=False)
    assert res_empty.is_valid is False
    assert any("empty" in err for err in res_empty.errors)


def test_run_j7_publish_all_four_collections_and_validate(
    spark_session: SparkSession,
    feature_table_df,
    sample_risk_indicators_df,
    tmp_path: Path,
) -> None:
    """Verify run_j7_publish_gold publishes all 4 collections and performs post-publication validation (Tasks 9.3 & 9.4)."""
    gold_path = tmp_path / "gold"
    feat_path = tmp_path / "student_features"
    feature_table_df.write.parquet(str(feat_path))

    cfg = J7Config(
        student_features_path=feat_path,
        parquet_base_path=gold_path,
        save_parquet=True,
        publish_to_mongo=False,
        publish_student_features=True,
        publish_course_metrics=True,
        publish_school_summary=True,
        publish_risk_indicators=True,
        validate_after_publication=True,
        fail_on_validation_error=True,
    )

    res = run_j7_publish_gold(
        spark_session,
        cfg,
        feature_table_df=feature_table_df,
        risk_indicators_df=sample_risk_indicators_df,
    )

    # Check all 4 collections published
    assert set(res.published_collections) == {
        "student_features",
        "course_metrics",
        "school_summary",
        "risk_indicators",
    }
    assert res.student_features_count == 3
    assert res.course_metrics_count == 4
    assert res.school_summary_count == 2
    assert res.risk_indicators_count == 3

    # Check post-publication validation report (Task 9.4)
    assert len(res.validation_report) == 4
    for coll_name, val_res in res.validation_report.items():
        assert val_res.is_valid is True, f"Collection {coll_name} failed validation: {val_res.errors}"
        assert val_res.grain_unique is True
        assert val_res.row_count > 0

    # Check signal breakdown recorded in J7Result (Task 9.3)
    assert res.risk_signal_breakdown["total_students"] == 3
    assert res.risk_signal_breakdown["flagged_students"] == 2

    # Check all 4 Parquet files exist
    for coll in ["student_features", "course_metrics", "school_summary", "risk_indicators"]:
        assert (gold_path / coll).exists()


def test_run_j7_validation_failure_raises_gold_validation_error(
    spark_session: SparkSession,
    feature_table_df,
    sample_risk_indicators_df,
    tmp_path: Path,
) -> None:
    """Verify run_j7_publish_gold raises GoldValidationError when post-publication validation fails (Task 9.4)."""
    gold_path = tmp_path / "gold"
    # Corrupt risk indicators with duplicate rows
    corrupt_ri = sample_risk_indicators_df.union(sample_risk_indicators_df.limit(1))

    cfg = J7Config(
        parquet_base_path=gold_path,
        save_parquet=True,
        publish_to_mongo=False,
        publish_student_features=False,
        publish_course_metrics=False,
        publish_school_summary=False,
        publish_risk_indicators=True,
        validate_after_publication=True,
        fail_on_validation_error=True,
    )

    with pytest.raises(GoldValidationError) as exc_info:
        run_j7_publish_gold(
            spark_session,
            cfg,
            risk_indicators_df=corrupt_ri,
        )

    assert "risk_indicators" in str(exc_info.value)
    assert "Grain violation" in str(exc_info.value)


def test_run_j7_publish_gold_parquet_only(spark_session: SparkSession, feature_table_df, tmp_path: Path) -> None:
    """Verify run_j7_publish_gold job with Parquet persistence and collection toggles (Tasks 9.1 & 9.2)."""
    feat_path = tmp_path / "student_features"
    feature_table_df.write.parquet(str(feat_path))

    gold_path = tmp_path / "gold"

    # 1. Test Task 9.1 toggle: student_features only
    cfg_91 = J7Config(
        student_features_path=feat_path,
        parquet_base_path=gold_path,
        save_parquet=True,
        publish_to_mongo=False,
        publish_student_features=True,
        publish_course_metrics=False,
        publish_school_summary=False,
        publish_risk_indicators=False,
    )
    res_91 = run_j7_publish_gold(spark_session, cfg_91)
    assert res_91.student_features_count == 3
    assert res_91.course_metrics_count == 0
    assert res_91.school_summary_count == 0
    assert res_91.published_collections == ["student_features"]
    assert (gold_path / "student_features").exists()
    assert not (gold_path / "course_metrics").exists()

    # 2. Test Task 9.2 toggle: course_metrics and school_summary only
    cfg_92 = J7Config(
        student_features_path=feat_path,
        parquet_base_path=gold_path,
        save_parquet=True,
        publish_to_mongo=False,
        publish_student_features=False,
        publish_course_metrics=True,
        publish_school_summary=True,
        publish_risk_indicators=False,
    )
    res_92 = run_j7_publish_gold(spark_session, cfg_92)
    assert res_92.student_features_count == 0
    assert res_92.course_metrics_count == 4
    assert res_92.school_summary_count == 2
    assert set(res_92.published_collections) == {"course_metrics", "school_summary"}
    assert (gold_path / "course_metrics").exists()
    assert (gold_path / "school_summary").exists()

    # Verify saved parquet reads cleanly
    saved_cm = spark_session.read.parquet(str(gold_path / "course_metrics"))
    assert saved_cm.count() == 4
    saved_ss = spark_session.read.parquet(str(gold_path / "school_summary"))
    assert saved_ss.count() == 2


def test_j7_publish_to_mongodb_roundtrip(
    spark_session: SparkSession,
    feature_table_df,
    sample_risk_indicators_df,
    tmp_path: Path,
) -> None:
    """Verify live publication to all 4 MongoDB collections and validate via validate_gold_mongodb (Tasks 9.1-9.4)."""
    mongo_cfg = MongoDBConfig.from_env()
    if not check_connection(config=mongo_cfg):
        pytest.skip("MongoDB is not reachable in current environment")

    feat_path = tmp_path / "student_features"
    feature_table_df.write.parquet(str(feat_path))

    cfg = J7Config(
        student_features_path=feat_path,
        mongo_uri=mongo_cfg.uri,
        mongo_database=mongo_cfg.database,
        publish_to_mongo=True,
        save_parquet=False,
        publish_student_features=True,
        publish_course_metrics=True,
        publish_school_summary=True,
        publish_risk_indicators=True,
        validate_after_publication=True,
    )

    res = run_j7_publish_gold(
        spark_session,
        cfg,
        feature_table_df=feature_table_df,
        risk_indicators_df=sample_risk_indicators_df,
    )
    assert res.student_features_count == 3
    assert res.course_metrics_count == 4
    assert res.school_summary_count == 2
    assert res.risk_indicators_count == 3

    # Verify directly in MongoDB using PyMongo
    client = MongoClient(mongo_cfg.uri, serverSelectionTimeoutMS=2000)
    db = client[mongo_cfg.database]

    # Check student_features
    sf_docs = list(db["student_features"].find({}, {"_id": 0}))
    assert len(sf_docs) == 3
    for doc in sf_docs:
        validate_record(doc, STUDENT_FEATURES_SCHEMA)

    # Check course_metrics
    cm_docs = list(db["course_metrics"].find({}, {"_id": 0}))
    assert len(cm_docs) == 4
    for doc in cm_docs:
        validate_record(doc, COURSE_METRICS_SCHEMA)

    # Check school_summary
    ss_docs = list(db["school_summary"].find({}, {"_id": 0}))
    assert len(ss_docs) == 2
    for doc in ss_docs:
        validate_record(doc, SCHOOL_SUMMARY_SCHEMA)

    # Check risk_indicators (Task 9.3)
    ri_docs = list(db["risk_indicators"].find({}, {"_id": 0}))
    assert len(ri_docs) == 3
    for doc in ri_docs:
        validate_record(doc, RISK_INDICATORS_SCHEMA)

    # Validate all 4 collections via validate_gold_mongodb (Task 9.4)
    mongo_val_results = validate_gold_mongodb(db)
    assert len(mongo_val_results) == 4
    for coll_name, val_res in mongo_val_results.items():
        assert val_res.is_valid is True, f"MongoDB collection {coll_name} failed validation: {val_res.errors}"


def test_no_large_collect_or_driver_iteration_in_j7_and_validation() -> None:
    """Explicitly verify no driver-side collect/toPandas exists in publish_gold or gold validation (rules.md §17.3)."""
    for module in (publish_gold_module, gold_validation_module):
        source_file = Path(inspect.getfile(module))
        tree = ast.parse(source_file.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                called_method = node.func.attr
                assert called_method not in (
                    "collect",
                    "toPandas",
                    "toArray",
                ), f"Forbidden driver-side collect/toPandas call '{called_method}' found on line {node.lineno} in {source_file.name}"
