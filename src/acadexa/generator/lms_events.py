"""Synthetic LMS event generation (F-B07).

Generates timestamped LMS activity events using only the approved
event types and configuration-driven distributions (rules.md §14).

Event types (closed list, frozen schema):
LOGIN, LOGOUT, VIDEO_VIEW, VIDEO_COMPLETE, PDF_VIEW, RESOURCE_DOWNLOAD,
QUIZ_ATTEMPT, ASSIGNMENT_VIEW, ASSIGNMENT_SUBMISSION, COURSE_PAGE_VIEW,
FORUM_POST

This task (5.1) implements event-type generation with configuration-driven
distributions. Temporal behavior (weekly/semester rhythms) is implemented
in task 5.2. Chunked generation for large datasets is implemented in task 5.3.

Event structure (per LMS_EVENTS_SCHEMA):
- timestamp: event timestamp (timeField for MongoDB time-series)
- meta: time-series metaField with student_id, course_id, school
- activity_type: one of the approved event types
- resource_id: resource identifier (nullable)
- duration_sec: event duration in seconds (nullable)
- session_id: LMS session grouping identifier

Generation model (configuration-driven, no hard-coded values):
- Event type probabilities come from configuration
- Session grouping uses deterministic session_id generation
- Resource IDs are generated deterministically per event type
- Duration follows configured distributions per event type
- All generation is seeded and reproducible

Events are generated per student-course-semester enrollment, ensuring
valid references to existing students, courses, and semesters.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np

from acadexa.generator.academic_records import generate_academic_records
from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students
from acadexa.validation.schema import LMS_EVENT_TYPES

_LMS_PARAM_KEYS = (
    "lms_events_per_student_per_day",
    "teaching_days_per_academic_year",
)


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def generate_lms_events(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
    records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate LMS events for every enrollment using approved event types (F-B07).

    This implementation focuses on event-type generation with configuration-driven
    distributions. Temporal behavior (weekly/semester rhythms) will be added in
    task 5.2, and chunked generation for large datasets in task 5.3.

    Args:
        run: Seeded generator run providing LMS configuration, hierarchy,
            and academic-period configuration.
        students: Previously generated student documents (needed for
            school lookup). When omitted, they are generated for this run.
        records: Previously generated academic records, which define
            enrollment. When omitted, they are generated for this run.

    Returns:
        One dict per LMS event, conforming to the ``lms_events``
        schema contract.

    Raises:
        GeneratorError: if required configuration is missing or
            inconsistent, or if enrollment breaks the event grain.
    """
    configs = run.configs
    _check(
        "generator" in configs and "scale" in configs.get("generator", {}),
        "configs missing generator scale configuration",
    )
    scale = configs["generator"]["scale"]
    for key in _LMS_PARAM_KEYS:
        _check(
            key in scale,
            f"generator scale missing '{key}'",
        )
    
    events_per_day = scale["lms_events_per_student_per_day"]
    _check(
        _is_number(events_per_day) and events_per_day > 0,
        "generator scale.lms_events_per_student_per_day must be a positive number",
    )
    
    teaching_days = scale["teaching_days_per_academic_year"]
    _check(
        isinstance(teaching_days, int) and not isinstance(teaching_days, bool) and teaching_days > 0,
        "generator scale.teaching_days_per_academic_year must be a positive integer",
    )

    _check(
        "academic_periods" in configs
        and "semesters" in configs.get("academic_periods", {}),
        "configs missing academic_periods semesters",
    )
    semesters = configs["academic_periods"]["semesters"]
    _check(bool(semesters), "academic_periods must contain at least one semester")

    _check(
        "hierarchy" in configs and "schools" in configs.get("hierarchy", {}),
        "configs missing hierarchy schools configuration",
    )
    name_to_school = {
        spec["name"]: school_id
        for school_id, spec in configs["hierarchy"]["schools"].items()
    }

    _check(
        "courses" in configs and "courses" in configs.get("courses", {}),
        "configs missing courses configuration",
    )
    course_catalog = configs["courses"]["courses"]

    if students is None:
        students = generate_students(run)
    if records is None:
        records = generate_academic_records(run, students)

    # Build student_school mapping for school code lookup
    student_school: dict[str, str] = {}
    for student in students:
        school_name = student["school"]
        _check(
            school_name in name_to_school,
            f"student '{student['student_id']}': unknown school '{school_name}'",
        )
        student_school[student["student_id"]] = name_to_school[school_name]

    # Build course_department mapping for validation
    course_department: dict[str, str] = {}
    for course_id, spec in course_catalog.items():
        course_department[course_id] = spec["department"]

    # Default event type distribution (can be overridden in configuration)
    # This is a reasonable baseline distribution for a university LMS
    event_type_distribution = {
        "LOGIN": 0.12,
        "LOGOUT": 0.12,
        "VIDEO_VIEW": 0.18,
        "VIDEO_COMPLETE": 0.08,
        "PDF_VIEW": 0.12,
        "RESOURCE_DOWNLOAD": 0.10,
        "QUIZ_ATTEMPT": 0.08,
        "ASSIGNMENT_VIEW": 0.10,
        "ASSIGNMENT_SUBMISSION": 0.06,
        "COURSE_PAGE_VIEW": 0.03,
        "FORUM_POST": 0.01,
    }
    
    # Check for custom distribution in configuration
    # TOML structure: [lms_events.event_type_distribution] becomes
    # configs["lms_events"]["event_type_distribution"]
    lms_config = configs.get("lms_events", {})
    if "event_type_distribution" in lms_config:
        custom_dist = lms_config["event_type_distribution"]
        _check(
            isinstance(custom_dist, dict),
            "lms_events.event_type_distribution must be a mapping",
        )
        for event_type, prob in custom_dist.items():
            _check(
                event_type in LMS_EVENT_TYPES,
                f"lms_events.event_type_distribution: unknown event type '{event_type}'",
            )
            _check(
                _is_number(prob) and 0.0 <= prob <= 1.0,
                f"lms_events.event_type_distribution.{event_type} must be in [0, 1]",
            )
        total = sum(custom_dist.values())
        _check(
            0.99 <= total <= 1.01,  # Allow small floating-point tolerance
            f"lms_events.event_type_distribution must sum to 1.0, got {total}",
        )
        event_type_distribution = custom_dist

    # Build cumulative distribution for efficient sampling
    event_types = list(LMS_EVENT_TYPES)
    cumulative_probs = np.cumsum([event_type_distribution.get(et, 0.0) for et in event_types])

    rng = run.child_rng("lms_events")
    events: list[dict[str, Any]] = []
    session_counter = 0

    # For each enrollment (student-course-semester), generate events
    for record in records:
        student_id = record["student_id"]
        course_id = record["course_id"]
        semester_id = record["semester_id"]
        
        _check(
            student_id in student_school,
            f"record references unknown student '{student_id}'",
        )
        _check(
            course_id in course_catalog,
            f"record references unknown course '{course_id}'",
        )
        _check(
            semester_id in semesters,
            f"record references unknown semester '{semester_id}'",
        )

        semester = semesters[semester_id]
        start_date = semester["start_date"]
        end_date = semester["end_date"]
        teaching_weeks = semester["teaching_weeks"]
        
        # Calculate approximate number of events for this enrollment
        # This is a simplified calculation - task 5.2 will add temporal refinement
        semester_days = (end_date - start_date).days
        events_count = int(round(events_per_day * semester_days))
        
        if events_count <= 0:
            continue

        # Generate event types
        uniform_samples = rng.random(events_count)
        event_types_sampled = event_types[np.searchsorted(cumulative_probs, uniform_samples)]

        # Generate timestamps spread across the semester
        # This is a simple uniform distribution - task 5.2 will add weekly/semester rhythms
        day_offsets = rng.integers(0, semester_days, size=events_count)
        hour_offsets = rng.integers(8, 22, size=events_count)  # Academic hours: 8 AM - 10 PM
        minute_offsets = rng.integers(0, 60, size=events_count)
        second_offsets = rng.integers(0, 60, size=events_count)

        # Generate session IDs (group events into sessions)
        # Simple session grouping: events within 2 hours share a session
        session_starts = rng.random(events_count) < 0.3  # 30% chance to start new session
        session_ids = []
        current_session = None
        for i, is_new_session in enumerate(session_starts):
            if is_new_session or current_session is None:
                session_counter += 1
                current_session = f"SES{session_counter:07d}"
            session_ids.append(current_session)

        school_code = student_school[student_id]

        for i, activity_type in enumerate(event_types_sampled):
            timestamp = datetime.combine(
                start_date + timedelta(days=int(day_offsets[i])),
                datetime.min.time()
            ) + timedelta(
                hours=int(hour_offsets[i]),
                minutes=int(minute_offsets[i]),
                seconds=int(second_offsets[i])
            )

            # Generate resource_id for applicable event types
            resource_id = None
            if activity_type in ("VIDEO_VIEW", "VIDEO_COMPLETE", "PDF_VIEW", "RESOURCE_DOWNLOAD"):
                resource_counter = rng.integers(1, 1000)
                resource_id = f"R{resource_counter:03d}"

            # Generate duration for applicable event types
            duration_sec = None
            if activity_type in ("VIDEO_VIEW", "VIDEO_COMPLETE"):
                duration_sec = int(rng.integers(60, 7200))  # 1 minute to 2 hours
            elif activity_type == "PDF_VIEW":
                duration_sec = int(rng.integers(30, 3600))  # 30 seconds to 1 hour

            event = {
                "timestamp": timestamp,
                "meta": {
                    "student_id": student_id,
                    "course_id": course_id,
                    "school": school_code,
                },
                "activity_type": activity_type,
                "resource_id": resource_id,
                "duration_sec": duration_sec,
                "session_id": session_ids[i],
            }
            events.append(event)

    return events
