"""Schema validation tests using small fixtures (task 3.8).

Covers required fields, data types, identifier formats, numeric
ranges, enums, nullable and nested fields, list constraints, and
expected record grain.
"""

from __future__ import annotations

import copy

import pytest

from acadexa.validation import (
    ALL_SCHEMAS,
    ACADEMIC_RECORDS_SCHEMA,
    ATTENDANCE_SCHEMA,
    COURSES_SCHEMA,
    COURSEWORK_SCHEMA,
    LMS_EVENTS_SCHEMA,
    RISK_INDICATORS_SCHEMA,
    STUDENT_FEATURES_SCHEMA,
    STUDENTS_SCHEMA,
    SchemaError,
    validate_record,
    validate_records,
)


def _example(collection: str) -> dict:
    return copy.deepcopy(ALL_SCHEMAS[collection]["example"])


# ── Every schema example conforms ───────────────────────


@pytest.mark.parametrize("collection", sorted(ALL_SCHEMAS))
def test_schema_example_conforms(collection: str) -> None:
    schema = ALL_SCHEMAS[collection]
    validate_record(schema["example"], schema)
    validate_records([schema["example"]], schema)


def test_all_core_and_gold_collections_registered() -> None:
    assert set(ALL_SCHEMAS) == {
        "students",
        "courses",
        "academic_records",
        "attendance",
        "coursework",
        "lms_events",
        "student_features",
        "course_metrics",
        "school_summary",
        "risk_indicators",
    }


# ── Required fields ─────────────────────────────────────


def test_missing_required_field_raises() -> None:
    record = _example("students")
    del record["batch"]
    with pytest.raises(SchemaError, match="missing required field 'batch'"):
        validate_record(record, STUDENTS_SCHEMA)


def test_null_on_non_nullable_field_raises() -> None:
    record = _example("students")
    record["school"] = None
    with pytest.raises(SchemaError, match="value may not be null"):
        validate_record(record, STUDENTS_SCHEMA)


def test_non_mapping_record_raises() -> None:
    with pytest.raises(SchemaError, match="record must be a mapping"):
        validate_record(["not", "a", "record"], STUDENTS_SCHEMA)  # type: ignore[arg-type]


# ── Data types ──────────────────────────────────────────


def test_wrong_type_raises() -> None:
    record = _example("students")
    record["batch"] = "2024"
    with pytest.raises(SchemaError, match="expected int, got str"):
        validate_record(record, STUDENTS_SCHEMA)


def test_bool_rejected_for_int_field_raises() -> None:
    record = _example("students")
    record["batch"] = True
    with pytest.raises(SchemaError, match="expected int, got bool"):
        validate_record(record, STUDENTS_SCHEMA)


def test_float_rejected_for_int_field_raises() -> None:
    record = _example("students")
    record["batch"] = 2024.5
    with pytest.raises(SchemaError, match="expected int, got float"):
        validate_record(record, STUDENTS_SCHEMA)


def test_int_accepted_for_float_field() -> None:
    record = _example("student_features")
    record["attendance_mean"] = 78
    validate_record(record, STUDENT_FEATURES_SCHEMA)


# ── Identifier formats ──────────────────────────────────


def test_bad_student_id_pattern_raises() -> None:
    record = _example("students")
    record["student_id"] = "ABC123"
    with pytest.raises(SchemaError, match="does not match pattern"):
        validate_record(record, STUDENTS_SCHEMA)


def test_bad_course_id_pattern_raises() -> None:
    record = _example("academic_records")
    record["course_id"] = "cs1"
    with pytest.raises(SchemaError, match="does not match pattern"):
        validate_record(record, ACADEMIC_RECORDS_SCHEMA)


def test_bad_semester_id_pattern_raises() -> None:
    record = _example("student_features")
    record["semester_id"] = "SEM1"
    with pytest.raises(SchemaError, match="does not match pattern"):
        validate_record(record, STUDENT_FEATURES_SCHEMA)


def test_bad_session_id_pattern_raises() -> None:
    record = _example("lms_events")
    record["session_id"] = "SESS1"
    with pytest.raises(SchemaError, match="does not match pattern"):
        validate_record(record, LMS_EVENTS_SCHEMA)


# ── Enums ───────────────────────────────────────────────


def test_bad_course_item_type_raises() -> None:
    record = _example("coursework")
    record["item_type"] = "ESSAY"
    with pytest.raises(SchemaError, match="is not one of"):
        validate_record(record, COURSEWORK_SCHEMA)


def test_bad_coursework_status_raises() -> None:
    record = _example("coursework")
    record["status"] = "PENDING"
    with pytest.raises(SchemaError, match="is not one of"):
        validate_record(record, COURSEWORK_SCHEMA)


def test_bad_lms_activity_type_raises() -> None:
    record = _example("lms_events")
    record["activity_type"] = "CHAT_MESSAGE"
    with pytest.raises(SchemaError, match="is not one of"):
        validate_record(record, LMS_EVENTS_SCHEMA)


def test_bad_difficulty_level_raises() -> None:
    record = _example("courses")
    record["difficulty_level"] = "nightmare"
    with pytest.raises(SchemaError, match="is not one of"):
        validate_record(record, COURSES_SCHEMA)


# ── Numeric ranges ──────────────────────────────────────


def test_signal_count_above_maximum_raises() -> None:
    record = _example("risk_indicators")
    record["signal_count"] = 6
    with pytest.raises(SchemaError, match="is above maximum 5"):
        validate_record(record, RISK_INDICATORS_SCHEMA)


def test_attendance_mean_above_maximum_raises() -> None:
    record = _example("student_features")
    record["attendance_mean"] = 150.0
    with pytest.raises(SchemaError, match="is above maximum"):
        validate_record(record, STUDENT_FEATURES_SCHEMA)


def test_negative_duration_below_minimum_raises() -> None:
    record = _example("lms_events")
    record["duration_sec"] = -5
    with pytest.raises(SchemaError, match="is below minimum 0"):
        validate_record(record, LMS_EVENTS_SCHEMA)


# ── Nullable fields ─────────────────────────────────────


def test_coursework_null_submission_and_score_pass() -> None:
    record = _example("coursework")
    record["submitted_at"] = None
    record["score"] = None
    record["status"] = "MISSING"
    record["attempts"] = 0
    validate_record(record, COURSEWORK_SCHEMA)


def test_lms_null_resource_and_duration_pass() -> None:
    record = _example("lms_events")
    record["resource_id"] = None
    record["duration_sec"] = None
    validate_record(record, LMS_EVENTS_SCHEMA)


# ── Nested objects ──────────────────────────────────────


def test_meta_missing_school_raises() -> None:
    record = _example("lms_events")
    del record["meta"]["school"]
    with pytest.raises(SchemaError, match=r"'meta'\.school: missing required field"):
        validate_record(record, LMS_EVENTS_SCHEMA)


def test_meta_bad_school_code_raises() -> None:
    record = _example("lms_events")
    record["meta"]["school"] = "cet"
    with pytest.raises(SchemaError, match="does not match pattern"):
        validate_record(record, LMS_EVENTS_SCHEMA)


def test_explanations_missing_key_raises() -> None:
    record = _example("risk_indicators")
    del record["explanations"]["marks_decline"]
    with pytest.raises(
        SchemaError, match=r"'explanations'\.marks_decline: missing required field"
    ):
        validate_record(record, RISK_INDICATORS_SCHEMA)


# ── Lists ───────────────────────────────────────────────


def test_empty_semester_applicability_raises() -> None:
    record = _example("courses")
    record["semester_applicability"] = []
    with pytest.raises(SchemaError, match="expected at least 1 item"):
        validate_record(record, COURSES_SCHEMA)


def test_wrong_list_item_type_raises() -> None:
    record = _example("courses")
    record["semester_applicability"] = ["1", 2]
    with pytest.raises(SchemaError, match="expected int, got str"):
        validate_record(record, COURSES_SCHEMA)


def test_list_item_out_of_range_raises() -> None:
    record = _example("courses")
    record["semester_applicability"] = [1, 5]
    with pytest.raises(SchemaError, match="is above maximum 4"):
        validate_record(record, COURSES_SCHEMA)


# ── Expected record grain ───────────────────────────────


def test_duplicate_student_grain_raises() -> None:
    record = _example("students")
    with pytest.raises(SchemaError, match="duplicate record at grain"):
        validate_records([record, copy.deepcopy(record)], STUDENTS_SCHEMA)


def test_distinct_student_grain_passes() -> None:
    first = _example("students")
    second = copy.deepcopy(first)
    second["student_id"] = "STU000001"
    validate_records([first, second], STUDENTS_SCHEMA)


def test_duplicate_attendance_grain_raises() -> None:
    record = _example("attendance")
    other = copy.deepcopy(record)
    other["classes_attended"] = 4
    with pytest.raises(SchemaError, match="duplicate record at grain"):
        validate_records([record, other], ATTENDANCE_SCHEMA)


def test_attendance_same_student_distinct_weeks_pass() -> None:
    first = _example("attendance")
    second = copy.deepcopy(first)
    second["week_start"] = first["week_start"].fromordinal(
        first["week_start"].toordinal() + 7
    )
    validate_records([first, second], ATTENDANCE_SCHEMA)


def test_duplicate_lms_event_grain_raises() -> None:
    record = _example("lms_events")
    with pytest.raises(SchemaError, match="duplicate record at grain"):
        validate_records([record, copy.deepcopy(record)], LMS_EVENTS_SCHEMA)


def test_distinct_lms_events_pass() -> None:
    first = _example("lms_events")
    second = copy.deepcopy(first)
    second["timestamp"] = first["timestamp"].replace(minute=16)
    validate_records([first, second], LMS_EVENTS_SCHEMA)
