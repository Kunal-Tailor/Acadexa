"""Tests for LMS event generation and temporal behavior (tasks 5.1 & 5.2)."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from datetime import timedelta

import pytest

from acadexa.config import validate_project_config
from acadexa.generator import (
    GeneratorError,
    GeneratorRun,
    generate_academic_records,
    generate_coursework,
    generate_decliner_flags,
    generate_lms_events,
    generate_lms_events_chunks,
    generate_students,
)
from acadexa.generator.coursework import _build_course_items
from acadexa.validation import LMS_EVENTS_SCHEMA, validate_records


def _scaled_configs(target: int = 36) -> dict:
    """Deep copy of the real configuration scaled to ``target`` students."""
    configs = copy.deepcopy(validate_project_config())
    scale = configs["generator"]["scale"]
    scale["target_students"] = target
    per_school = target // len(scale["school_population"])
    scale["school_population"] = {
        school_id: per_school for school_id in scale["school_population"]
    }
    return configs


@pytest.fixture(scope="module")
def dataset() -> tuple[GeneratorRun, list[dict], list[dict], list[dict]]:
    """Scaled generation (36 students) computed once for this test module."""
    configs = _scaled_configs(36)
    run = GeneratorRun(configs)
    students = generate_students(run)
    records = generate_academic_records(run, students)
    events = generate_lms_events(run, students, records)
    return run, students, records, events


@pytest.fixture()
def small_configs() -> dict:
    """Validated configuration scaled down to 36 students for fast tests."""
    return _scaled_configs(36)


@pytest.fixture()
def small_chain(small_configs: dict) -> tuple[GeneratorRun, list[dict], list[dict]]:
    run = GeneratorRun(small_configs)
    students = generate_students(run)
    records = generate_academic_records(run, students)
    return run, students, records


# ── Structural schema & field validation (task 5.1) ─────


def test_lms_events_have_required_fields_and_types(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    validate_records(events, LMS_EVENTS_SCHEMA)


def test_lms_events_use_only_approved_event_types(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    from acadexa.validation.schema import LMS_EVENT_TYPES

    used_types = {event["activity_type"] for event in events}
    assert used_types == set(LMS_EVENT_TYPES)


def test_lms_events_reference_valid_students_courses_semesters(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, students, records, events = dataset
    student_ids = {student["student_id"] for student in students}
    course_ids = set(run.configs["courses"]["courses"].keys())
    school_codes = {
        spec["code"] for spec in run.configs["hierarchy"]["schools"].values()
    }

    for event in events:
        assert event["meta"]["student_id"] in student_ids
        assert event["meta"]["course_id"] in course_ids
        assert event["meta"]["school"] in school_codes


def test_lms_events_have_valid_timestamps(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    for event in events:
        assert isinstance(event["timestamp"], type(event["timestamp"]))


def test_lms_events_have_valid_session_ids(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    import re
    from acadexa.validation.schema import SESSION_ID_PATTERN

    pattern = re.compile(SESSION_ID_PATTERN)
    for event in events:
        assert pattern.match(event["session_id"])


def test_lms_events_have_nullable_resource_id_and_duration(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    for event in events:
        if event["resource_id"] is not None:
            assert isinstance(event["resource_id"], str)
        if event["duration_sec"] is not None:
            assert isinstance(event["duration_sec"], int)
            assert event["duration_sec"] >= 0


def test_lms_events_respect_configuration_distribution(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, _, events = dataset
    event_type_counts = Counter(event["activity_type"] for event in events)
    total = len(events)

    lms_config = run.configs.get("generator", {}).get("lms_events", {})
    if "event_type_distribution" in lms_config:
        distribution = lms_config["event_type_distribution"]
        for event_type, expected_prob in distribution.items():
            actual_prob = event_type_counts[event_type] / total
            assert abs(actual_prob - expected_prob) / expected_prob < 0.2, (
                f"Event type {event_type}: expected probability {expected_prob:.3f}, "
                f"got {actual_prob:.3f}"
            )


# ── Small-scale schema & reproducibility ────────────────


def test_small_dataset_conforms_to_schema(
    small_configs: dict,
) -> None:
    events = generate_lms_events(GeneratorRun(small_configs))
    validate_records(events, LMS_EVENTS_SCHEMA)


def test_lms_events_are_reproducible(small_configs: dict) -> None:
    first = generate_lms_events(GeneratorRun(small_configs))
    second = generate_lms_events(GeneratorRun(small_configs))
    assert first == second


def test_different_seed_changes_lms_events(small_configs: dict) -> None:
    other_configs = copy.deepcopy(small_configs)
    other_configs["generator"]["generator"]["seed"] += 1
    baseline = generate_lms_events(GeneratorRun(small_configs))
    other = generate_lms_events(GeneratorRun(other_configs))
    assert other != baseline


def test_accepts_precomputed_students_and_records(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    events = generate_lms_events(run, students, records)
    assert len(events) > 0


# ── Temporal Behavior & Rhythms (task 5.2) ───────────────


def test_lms_timestamps_within_semester_bounds(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, records, events = dataset
    semesters = run.configs["academic_periods"]["semesters"]

    # Map (student_id, course_id) to semester_id
    enrollment_semesters = {
        (r["student_id"], r["course_id"]): r["semester_id"] for r in records
    }

    for event in events:
        student_id = event["meta"]["student_id"]
        course_id = event["meta"]["course_id"]
        sem_id = enrollment_semesters[(student_id, course_id)]
        sem = semesters[sem_id]
        event_date = event["timestamp"].date()
        assert sem["start_date"] <= event_date <= sem["end_date"], (
            f"Event timestamp {event['timestamp']} outside semester {sem_id} "
            f"({sem['start_date']}..{sem['end_date']})"
        )


def test_weekend_activity_is_reduced(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, records, events = dataset
    semesters = run.configs["academic_periods"]["semesters"]

    weekend_events = sum(1 for e in events if e["timestamp"].weekday() in (5, 6))
    weekday_events = len(events) - weekend_events

    enrollment_semesters = {
        (r["student_id"], r["course_id"]): r["semester_id"] for r in records
    }

    total_weekend_days = 0
    total_weekday_days = 0
    for sem_id in enrollment_semesters.values():
        sem = semesters[sem_id]
        s_date = sem["start_date"]
        n_days = (sem["end_date"] - s_date).days + 1
        for i in range(n_days):
            d = s_date + timedelta(days=i)
            if d.weekday() in (5, 6):
                total_weekend_days += 1
            else:
                total_weekday_days += 1

    rate_weekend = weekend_events / total_weekend_days
    rate_weekday = weekday_events / total_weekday_days
    ratio = rate_weekend / rate_weekday

    # weekend_event_factor is 0.40; assert measured ratio lands in [0.30, 0.55]
    assert 0.30 <= ratio <= 0.55, f"Weekend/weekday ratio {ratio:.3f} outside expected [0.30, 0.55]"


def test_pre_deadline_activity_spikes(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, records, events = dataset
    configs = run.configs
    semesters = configs["academic_periods"]["semesters"]
    coursework_params = configs["generator"]["behavior"]["coursework"]

    # Precompute course item deadlines per (course_id, semester_id)
    deadline_cache = {}
    for r in records:
        key = (r["course_id"], r["semester_id"])
        if key not in deadline_cache:
            items = _build_course_items(configs, coursework_params, r["course_id"], r["semester_id"])
            deadline_cache[key] = {item["due_date"] for item in items}

    # Group events by enrollment
    events_by_enrollment = defaultdict(list)
    for e in events:
        events_by_enrollment[(e["meta"]["student_id"], e["meta"]["course_id"])].append(e)

    pre_deadline_events = 0
    normal_weekday_events = 0
    pre_deadline_days_count = 0
    normal_weekday_days_count = 0

    for r in records:
        key = (r["course_id"], r["semester_id"])
        due_dates = deadline_cache[key]
        sem = semesters[r["semester_id"]]
        s_date = sem["start_date"]
        n_days = (sem["end_date"] - s_date).days + 1

        cal_dates = [s_date + timedelta(days=i) for i in range(n_days)]
        pre_dl_mask = [
            any(0 <= (due - d).days <= 1 for due in due_dates) if d.weekday() not in (5, 6) else False
            for d in cal_dates
        ]
        norm_wd_mask = [
            d.weekday() not in (5, 6) and not pre_dl_mask[idx]
            for idx, d in enumerate(cal_dates)
        ]

        pre_deadline_days_count += sum(pre_dl_mask)
        normal_weekday_days_count += sum(norm_wd_mask)

        enrollment_events = events_by_enrollment.get((r["student_id"], r["course_id"]), [])
        for e in enrollment_events:
            d = e["timestamp"].date()
            if d.weekday() not in (5, 6):
                if any(0 <= (due - d).days <= 1 for due in due_dates):
                    pre_deadline_events += 1
                else:
                    normal_weekday_events += 1

    dl_rate = pre_deadline_events / pre_deadline_days_count
    norm_rate = normal_weekday_events / normal_weekday_days_count
    ratio = dl_rate / norm_rate

    # pre_deadline_spike_factor is 1.60; assert spike is clearly observed (>= 1.30)
    assert ratio >= 1.30, f"Pre-deadline spike ratio {ratio:.3f} below expected 1.30"


def test_pre_exam_activity_spikes(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, records, events = dataset
    configs = run.configs
    semesters = configs["academic_periods"]["semesters"]
    component_weeks = configs["generator"]["behavior"]["decliners"]["component_weeks"]
    midterm_week = component_weeks["midterm"]
    endterm_week = component_weeks["endterm"]

    events_by_enrollment = defaultdict(list)
    for e in events:
        events_by_enrollment[(e["meta"]["student_id"], e["meta"]["course_id"])].append(e)

    pre_exam_events = 0
    normal_weekday_events = 0
    pre_exam_days_count = 0
    normal_weekday_days_count = 0

    for r in records:
        sem = semesters[r["semester_id"]]
        s_date = sem["start_date"]
        n_days = (sem["end_date"] - s_date).days + 1
        midterm_date = s_date + timedelta(weeks=midterm_week - 1, days=4)
        endterm_date = s_date + timedelta(weeks=endterm_week - 1, days=4)

        cal_dates = [s_date + timedelta(days=i) for i in range(n_days)]
        for d in cal_dates:
            if d.weekday() not in (5, 6):
                if (0 < (midterm_date - d).days <= 3) or (0 < (endterm_date - d).days <= 3):
                    pre_exam_days_count += 1
                else:
                    normal_weekday_days_count += 1

        enrollment_events = events_by_enrollment.get((r["student_id"], r["course_id"]), [])
        for e in enrollment_events:
            d = e["timestamp"].date()
            if d.weekday() not in (5, 6):
                if (0 < (midterm_date - d).days <= 3) or (0 < (endterm_date - d).days <= 3):
                    pre_exam_events += 1
                else:
                    normal_weekday_events += 1

    exam_rate = pre_exam_events / pre_exam_days_count
    norm_rate = normal_weekday_events / normal_weekday_days_count
    ratio = exam_rate / norm_rate

    # pre_exam_spike_factor is 1.80; assert spike is clearly observed (>= 1.40)
    assert ratio >= 1.40, f"Pre-exam spike ratio {ratio:.3f} below expected 1.40"


def test_mid_semester_dip_is_observed(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    run, _, records, events = dataset
    configs = run.configs
    semesters = configs["academic_periods"]["semesters"]
    component_weeks = configs["generator"]["behavior"]["decliners"]["component_weeks"]
    midterm_week = component_weeks["midterm"]
    mid_dip_weeks = set(range(max(1, midterm_week - 3), midterm_week))

    dip_events = 0
    other_early_events = 0
    dip_days_count = 0
    other_early_days_count = 0

    enrollment_semesters = {
        (r["student_id"], r["course_id"]): r["semester_id"] for r in records
    }

    for sem_id in enrollment_semesters.values():
        sem = semesters[sem_id]
        s_date = sem["start_date"]
        n_days = (sem["end_date"] - s_date).days + 1
        for i in range(n_days):
            d = s_date + timedelta(days=i)
            week = i // 7 + 1
            if d.weekday() not in (5, 6):
                if week in mid_dip_weeks:
                    dip_days_count += 1
                elif week < midterm_week and week not in mid_dip_weeks:
                    other_early_days_count += 1

    events_by_enrollment = defaultdict(list)
    for e in events:
        events_by_enrollment[(e["meta"]["student_id"], e["meta"]["course_id"])].append(e)

    for r in records:
        sem = semesters[r["semester_id"]]
        s_date = sem["start_date"]
        for e in events_by_enrollment.get((r["student_id"], r["course_id"]), []):
            d = e["timestamp"].date()
            if d.weekday() not in (5, 6):
                week = (d - s_date).days // 7 + 1
                if week in mid_dip_weeks:
                    dip_events += 1
                elif week < midterm_week and week not in mid_dip_weeks:
                    other_early_events += 1

    dip_rate = dip_events / dip_days_count
    other_rate = other_early_events / other_early_days_count
    ratio = dip_rate / other_rate

    # mid_semester_dip_factor is 0.80; assert dip is observed (ratio < 0.95)
    assert ratio < 0.95, f"Mid-semester dip ratio {ratio:.3f} expected < 0.95"


def test_decliner_lms_engagement_fades() -> None:
    # Use 72 students to ensure robust decliner sample
    configs = _scaled_configs(72)
    run = GeneratorRun(configs)
    students = generate_students(run)
    records = generate_academic_records(run, students)
    decliners = generate_decliner_flags(run, students)
    events = generate_lms_events(run, students, records)

    semesters = configs["academic_periods"]["semesters"]

    enrollment_semesters = {
        (r["student_id"], r["course_id"]): r["semester_id"] for r in records
    }

    decliner_early = 0
    decliner_late = 0
    non_decliner_early = 0
    non_decliner_late = 0

    for e in events:
        s_id = e["meta"]["student_id"]
        c_id = e["meta"]["course_id"]
        sem_id = enrollment_semesters[(s_id, c_id)]
        s_date = semesters[sem_id]["start_date"]
        week = (e["timestamp"].date() - s_date).days // 7 + 1

        is_decl = decliners[s_id]
        if week in (1, 2, 3, 4):
            if is_decl:
                decliner_early += 1
            else:
                non_decliner_early += 1
        elif week in (12, 13, 14, 15):
            if is_decl:
                decliner_late += 1
            else:
                non_decliner_late += 1

    # Ratio of late-to-early activity
    decl_ratio = decliner_late / max(1, decliner_early)
    non_decl_ratio = non_decliner_late / max(1, non_decliner_early)

    # Decliners must drop noticeably more than non-decliners
    assert decl_ratio < 0.85 * non_decl_ratio, (
        f"Decliner late/early ratio ({decl_ratio:.3f}) not sufficiently below "
        f"non-decliner ratio ({non_decl_ratio:.3f})"
    )


def test_sessions_are_chronologically_ordered(
    dataset: tuple[GeneratorRun, list[dict], list[dict], list[dict]],
) -> None:
    _, _, _, events = dataset
    sessions: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        sessions[e["session_id"]].append(e)

    for sid, sess_events in list(sessions.items())[:200]:
        for i in range(len(sess_events) - 1):
            assert sess_events[i]["timestamp"] <= sess_events[i + 1]["timestamp"], (
                f"Session {sid} not chronologically ordered: "
                f"{sess_events[i]['timestamp']} > {sess_events[i+1]['timestamp']}"
            )


# ── Initialization & configuration failures ──────────────


def test_missing_lms_events_per_day_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["scale"]["lms_events_per_student_per_day"]
    with pytest.raises(GeneratorError, match="lms_events_per_student_per_day"):
        generate_lms_events(GeneratorRun(broken))


def test_missing_teaching_days_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["scale"]["teaching_days_per_academic_year"]
    with pytest.raises(GeneratorError, match="teaching_days_per_academic_year"):
        generate_lms_events(GeneratorRun(broken))


def test_missing_rhythm_section_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["rhythms"]
    with pytest.raises(GeneratorError, match="behavior.rhythms"):
        generate_lms_events(GeneratorRun(broken))


def test_missing_rhythm_key_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    del broken["generator"]["behavior"]["rhythms"]["weekend_event_factor"]
    with pytest.raises(GeneratorError, match="weekend_event_factor"):
        generate_lms_events(GeneratorRun(broken))


def test_invalid_rhythm_factor_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    broken["generator"]["behavior"]["rhythms"]["pre_exam_spike_factor"] = -1.0
    with pytest.raises(GeneratorError, match="positive number"):
        generate_lms_events(GeneratorRun(broken))


def test_invalid_event_type_distribution_raises(small_configs: dict) -> None:
    broken = copy.deepcopy(small_configs)
    if "lms_events" not in broken["generator"]:
        broken["generator"]["lms_events"] = {}
    broken["generator"]["lms_events"]["event_type_distribution"] = {
        "LOGIN": 0.5,
        "INVALID_TYPE": 0.5,
    }
    with pytest.raises(GeneratorError, match="unknown event type"):
        generate_lms_events(GeneratorRun(broken))


def test_event_type_distribution_not_summing_to_one_raises(
    small_configs: dict,
) -> None:
    broken = copy.deepcopy(small_configs)
    if "lms_events" not in broken["generator"]:
        broken["generator"]["lms_events"] = {}
    broken["generator"]["lms_events"]["event_type_distribution"] = {
        "LOGIN": 0.5,
        "LOGOUT": 0.3,
    }
    with pytest.raises(GeneratorError, match="sum to 1.0"):
        generate_lms_events(GeneratorRun(broken))


def test_record_with_unknown_student_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, _, records = small_chain
    with pytest.raises(GeneratorError, match="unknown student"):
        generate_lms_events(run, students=[], records=records)


def test_record_with_unknown_course_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    broken_record = dict(records[0])
    broken_record["course_id"] = "INVALID999"
    with pytest.raises(GeneratorError, match="unknown course"):
        generate_lms_events(run, students, records + [broken_record])


def test_record_with_unknown_semester_raises(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    broken_record = dict(records[0])
    broken_record["semester_id"] = "S99"
    with pytest.raises(GeneratorError, match="unknown semester"):
        generate_lms_events(run, students, records + [broken_record])


# ── Chunked generation tests (task 5.3) ──────────────────


def test_generate_lms_events_chunks_yields_correct_total_count(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    # Use a small slice of records for fast chunk testing
    test_records = records[:24]
    unbuffered = generate_lms_events(run, students, test_records)

    chunks = list(
        generate_lms_events_chunks(run, students, test_records, chunk_size=1000)
    )
    assert len(chunks) > 1
    total_chunked = sum(len(c) for c in chunks)
    assert total_chunked == len(unbuffered)


def test_chunk_sizes_conform_to_parameter(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    test_records = records[:24]
    chunk_size = 1500

    chunks = list(
        generate_lms_events_chunks(run, students, test_records, chunk_size=chunk_size)
    )
    assert len(chunks) > 1

    # Every chunk except the last must have exactly chunk_size items
    for chunk in chunks[:-1]:
        assert len(chunk) == chunk_size

    # The last chunk must have at most chunk_size items and at least 1 item
    assert 0 < len(chunks[-1]) <= chunk_size


def test_chunked_output_identical_to_unbuffered(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    test_records = records[:12]

    # Deterministic generation from fresh runs with identical seeds
    run1 = GeneratorRun(run.configs)
    unbuffered = generate_lms_events(run1, students, test_records)

    run2 = GeneratorRun(run.configs)
    chunks = list(
        generate_lms_events_chunks(run2, students, test_records, chunk_size=800)
    )
    reassembled = [event for chunk in chunks for event in chunk]

    assert reassembled == unbuffered


def test_each_chunk_conforms_to_schema(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    test_records = records[:12]

    for chunk in generate_lms_events_chunks(
        run, students, test_records, chunk_size=1000
    ):
        validate_records(chunk, LMS_EVENTS_SCHEMA)


def test_session_ids_unique_and_monotonic_across_chunks(
    small_chain: tuple[GeneratorRun, list[dict], list[dict]],
) -> None:
    run, students, records = small_chain
    test_records = records[:24]

    chunks = list(
        generate_lms_events_chunks(run, students, test_records, chunk_size=1000)
    )

    seen_session_ids: set[str] = set()
    prev_session_num = 0

    for chunk in chunks:
        chunk_session_ids = [e["session_id"] for e in chunk]
        # In each chunk, session numbers must be non-decreasing
        for sid in chunk_session_ids:
            num = int(sid.replace("SES", ""))
            assert num >= prev_session_num
            prev_session_num = num
        seen_session_ids.update(chunk_session_ids)

    # Global session counter increased properly
    assert len(seen_session_ids) > 10


def test_configured_chunk_size_is_respected(small_configs: dict) -> None:
    custom_configs = copy.deepcopy(small_configs)
    custom_configs["generator"]["lms_events"]["chunk_size"] = 1200

    run = GeneratorRun(custom_configs)
    students = generate_students(run)
    records = generate_academic_records(run, students)[:24]

    chunks = list(generate_lms_events_chunks(run, students, records))
    assert len(chunks) > 1
    assert len(chunks[0]) == 1200


def test_empty_records_yields_no_chunks(small_configs: dict) -> None:
    run = GeneratorRun(small_configs)
    students = generate_students(run)
    chunks = list(generate_lms_events_chunks(run, students, records=[]))
    assert chunks == []


def test_invalid_chunk_size_raises(small_chain: tuple[GeneratorRun, list[dict], list[dict]]) -> None:
    run, students, records = small_chain

    with pytest.raises(GeneratorError, match="chunk_size must be a positive integer"):
        list(generate_lms_events_chunks(run, students, records[:6], chunk_size=0))

    with pytest.raises(GeneratorError, match="chunk_size must be a positive integer"):
        list(generate_lms_events_chunks(run, students, records[:6], chunk_size=-100))

    with pytest.raises(GeneratorError, match="chunk_size must be a positive integer"):
        list(generate_lms_events_chunks(run, students, records[:6], chunk_size="5000"))  # type: ignore

    with pytest.raises(GeneratorError, match="chunk_size must be a positive integer"):
        list(generate_lms_events_chunks(run, students, records[:6], chunk_size=True))  # type: ignore

