"""Synthetic LMS event generation and chunked streaming (F-B07, F-B08, task 5.3).

Generates timestamped LMS activity events using only the approved
event types and configuration-driven distributions (rules.md §14).
Preserves valid student, course, semester, and hierarchy context.

Temporal behavior model (F-B08, memory.md §6, original_idea §7.1):
- Weekly rhythms:
  - Fewer events on weekends: activity on Saturday and Sunday is scaled
    by ``behavior.rhythms.weekend_event_factor`` (default 0.40).
  - Diurnal cycle: events are concentrated during active academic and
    study hours (08:00 to 23:00) with realistic session grouping.
- Semester rhythms:
  - Pre-deadline activity spikes: in the days leading up to assignment
    or quiz deadlines for the enrolled course, activity is boosted by
    ``behavior.rhythms.pre_deadline_spike_factor`` (default 1.60).
  - Pre-exam activity spikes: in the days leading up to major examinations
    (midterm and endterm milestones), activity spikes by
    ``behavior.rhythms.pre_exam_spike_factor`` (default 1.80).
  - Mid-semester dip: during the middle weeks of the semester between
    early assessments and midterm exams, activity dips by
    ``behavior.rhythms.mid_semester_dip_factor`` (default 0.80).
  - Decliner engagement fade: students identified as decliners
    (task 4.8) experience week-by-week engagement decay from
    ``behavior.decliners.start_week`` onward with
    ``weekly_engagement_decay`` (default 0.07).
  - Student traits and school profiles: base event volume scales with
    the student's latent ``engagement`` trait (task 4.7) and the
    school's ``lms_activity`` multiplier.

Chunked generation (rules.md §8.4, architecture.md §24, task 5.3):
- Large event datasets are generated and yielded in memory-bounded
  chunks via :func:`generate_lms_events_chunks`, so callers (such as
  the Parquet writer in task 5.4) can write each chunk incrementally
  and release memory rather than accumulating ~70M records in Python RAM.
- :func:`generate_lms_events` is a convenience wrapper for small-scale
  tests and development workflows.

Event structure (per LMS_EVENTS_SCHEMA):
- timestamp: datetime within semester bounds (timeField for MongoDB time-series)
- meta: time-series metaField with student_id, course_id, school
- activity_type: one of the 11 approved event types
- resource_id: resource identifier (nullable)
- duration_sec: event duration in seconds (nullable)
- session_id: LMS session grouping identifier (SESxxxxxxx)

All generation is seeded and reproducible through the dedicated
``run.child_rng("lms_events")`` sub-stream.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from typing import Any

import numpy as np

from acadexa.generator.academic_records import generate_academic_records
from acadexa.generator.behavioral_model import generate_behavioral_traits
from acadexa.generator.coursework import _build_course_items
from acadexa.generator.decliners import generate_decliner_flags
from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students
from acadexa.validation.schema import LMS_EVENT_TYPES

_LMS_SCALE_KEYS = (
    "lms_events_per_student_per_day",
    "teaching_days_per_academic_year",
    "courses_per_student_per_semester",
)

_RHYTHM_PARAM_KEYS = (
    "weekend_event_factor",
    "mid_semester_dip_factor",
    "pre_deadline_spike_factor",
    "pre_exam_spike_factor",
)

_DECLINER_PARAM_KEYS = (
    "start_week",
    "weekly_engagement_decay",
    "component_weeks",
)

# Realistic diurnal hour probability weights (00:00 to 23:00)
_HOURLY_WEIGHTS = np.array(
    [
        0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.015, 0.025,  # 00..07
        0.050, 0.065, 0.075, 0.075, 0.070, 0.070, 0.080, 0.085,  # 08..15
        0.085, 0.080, 0.075, 0.065, 0.050, 0.035, 0.020, 0.010,  # 16..23
    ],
    dtype=float,
)
_HOURLY_WEIGHTS /= _HOURLY_WEIGHTS.sum()


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def generate_lms_events_chunks(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
    records: list[dict[str, Any]] | None = None,
    coursework: list[dict[str, Any]] | None = None,
    chunk_size: int | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Generate timestamped LMS events in memory-bounded chunks (rules.md §8.4, task 5.3).

    Simulates temporal rhythms (weekend reductions, mid-semester dips,
    pre-deadline and pre-exam spikes, and decliner engagement fades)
    while yielding events in discrete chunks of at most ``chunk_size``
    records. This prevents Python driver out-of-memory errors on large datasets.

    Args:
        run: Seeded generator run providing LMS configuration, hierarchy,
            rhythms, coursework, and academic-period configuration.
        students: Previously generated student documents (needed for
            school lookup and traits). When omitted, they are generated.
        records: Previously generated academic records, which define
            enrollments. When omitted, they are generated.
        coursework: Optional previously generated coursework rows. When
            omitted, course item schedules are computed from configuration.
        chunk_size: Maximum number of events per yielded chunk. When omitted,
            reads ``[lms_events].chunk_size`` from configuration (default 100,000).

    Yields:
        Lists of dicts representing LMS events conforming to the
        ``lms_events`` schema contract, each containing at most ``chunk_size``
        events (except possibly the final chunk).

    Raises:
        GeneratorError: if required configuration is missing or
            inconsistent, or if enrollment references invalid entities, or
            if ``chunk_size`` is not a positive integer.
    """
    configs = run.configs
    _check(
        "generator" in configs and "scale" in configs.get("generator", {}),
        "configs missing generator scale configuration",
    )
    scale = configs["generator"]["scale"]
    for key in ("lms_events_per_student_per_day", "teaching_days_per_academic_year"):
        _check(key in scale, f"generator scale missing '{key}'")

    events_per_day = scale["lms_events_per_student_per_day"]
    _check(
        _is_number(events_per_day) and events_per_day > 0,
        "generator scale.lms_events_per_student_per_day must be a positive number",
    )

    teaching_days_year = scale["teaching_days_per_academic_year"]
    _check(
        isinstance(teaching_days_year, int)
        and not isinstance(teaching_days_year, bool)
        and teaching_days_year > 0,
        "generator scale.teaching_days_per_academic_year must be a positive integer",
    )

    courses_per_semester = scale.get("courses_per_student_per_semester", 6)
    _check(
        isinstance(courses_per_semester, int)
        and not isinstance(courses_per_semester, bool)
        and courses_per_semester > 0,
        "generator scale.courses_per_student_per_semester must be a positive integer",
    )

    # Resolve chunk size from argument or configuration
    if chunk_size is None:
        lms_cfg = configs.get("generator", {}).get("lms_events", {})
        if not lms_cfg:
            lms_cfg = configs.get("lms_events", {})
        chunk_size = lms_cfg.get("chunk_size", 100_000)

    _check(
        isinstance(chunk_size, int) and not isinstance(chunk_size, bool) and chunk_size > 0,
        "generator lms_events chunk_size must be a positive integer",
    )

    _check(
        "behavior" in configs.get("generator", {}),
        "configs missing generator behavior configuration",
    )
    behavior = configs["generator"]["behavior"]

    # Rhythm parameters validation (F-B08)
    _check("rhythms" in behavior, "configs missing generator behavior.rhythms")
    rhythms = behavior["rhythms"]
    for key in _RHYTHM_PARAM_KEYS:
        _check(key in rhythms, f"generator behavior.rhythms missing '{key}'")
        _check(
            _is_number(rhythms[key]) and rhythms[key] > 0,
            f"generator behavior.rhythms.{key} must be a positive number",
        )
    weekend_factor = float(rhythms["weekend_event_factor"])
    mid_semester_dip_factor = float(rhythms["mid_semester_dip_factor"])
    pre_deadline_spike_factor = float(rhythms["pre_deadline_spike_factor"])
    pre_exam_spike_factor = float(rhythms["pre_exam_spike_factor"])

    # Decliner parameters validation
    _check("decliners" in behavior, "configs missing generator behavior.decliners")
    decliners_cfg = behavior["decliners"]
    for key in _DECLINER_PARAM_KEYS:
        _check(key in decliners_cfg, f"generator behavior.decliners missing '{key}'")
    decliner_start_week = decliners_cfg["start_week"]
    weekly_decay = decliners_cfg["weekly_engagement_decay"]
    component_weeks = decliners_cfg["component_weeks"]
    midterm_week = component_weeks["midterm"]
    endterm_week = component_weeks["endterm"]

    # Coursework parameters (for item schedule precomputation)
    _check("coursework" in behavior, "configs missing generator behavior.coursework")
    coursework_params = behavior["coursework"]

    # Student traits parameters
    _check(
        "student_traits" in behavior,
        "configs missing generator behavior.student_traits",
    )
    traits_cfg = behavior["student_traits"]
    _check("engagement" in traits_cfg, "generator behavior.student_traits missing 'engagement'")
    engagement_mean = float(traits_cfg["engagement"]["mean"])

    # Academic periods (semesters)
    _check(
        "academic_periods" in configs
        and "semesters" in configs.get("academic_periods", {}),
        "configs missing academic_periods semesters",
    )
    semesters = configs["academic_periods"]["semesters"]
    _check(bool(semesters), "academic_periods must contain at least one semester")

    # Hierarchy: schools and departments
    _check(
        "hierarchy" in configs and "schools" in configs.get("hierarchy", {}),
        "configs missing hierarchy schools configuration",
    )
    name_to_school = {
        spec["name"]: spec["code"]
        for spec in configs["hierarchy"]["schools"].values()
    }

    # Course catalog
    _check(
        "courses" in configs and "courses" in configs.get("courses", {}),
        "configs missing courses configuration",
    )
    course_catalog = configs["courses"]["courses"]

    # School profiles
    school_profiles = configs["generator"].get("school_profiles", {})

    # Generate or accept upstream entities
    if students is None:
        students = generate_students(run)
    if records is None:
        records = generate_academic_records(run, students)

    # Student to school code mapping
    student_school: dict[str, str] = {}
    for student in students:
        school_name = student["school"]
        _check(
            school_name in name_to_school,
            f"student '{student['student_id']}': unknown school '{school_name}'",
        )
        student_school[student["student_id"]] = name_to_school[school_name]

    # Student traits and decliner flags
    traits = generate_behavioral_traits(run, students)
    decliner_flags = generate_decliner_flags(run, students)

    # Event type distribution (configurable, falls back to approved baseline)
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
    lms_config = configs.get("generator", {}).get("lms_events", {})
    if not lms_config:
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
            0.99 <= total <= 1.01,
            f"lms_events.event_type_distribution must sum to 1.0, got {total}",
        )
        event_type_distribution = custom_dist

    event_types = list(LMS_EVENT_TYPES)
    cumulative_probs = np.cumsum([event_type_distribution.get(et, 0.0) for et in event_types])

    # Precompute semester day calendars
    sem_calendar: dict[str, dict[str, Any]] = {}
    for sem_id, sem in semesters.items():
        s_date = sem["start_date"]
        e_date = sem["end_date"]
        n_days = (e_date - s_date).days + 1
        dates = [s_date + timedelta(days=i) for i in range(n_days)]
        weeks = np.array([i // 7 + 1 for i in range(n_days)], dtype=int)
        is_weekend = np.array([d.weekday() in (5, 6) for d in dates], dtype=bool)

        mid_dip_weeks = set(range(max(1, midterm_week - 3), midterm_week))
        is_mid_dip = np.array([w in mid_dip_weeks for w in weeks], dtype=bool)

        midterm_date = s_date + timedelta(weeks=midterm_week - 1, days=4)
        endterm_date = s_date + timedelta(weeks=endterm_week - 1, days=4)
        is_pre_exam = np.array(
            [
                (0 < (midterm_date - d).days <= 3) or (0 < (endterm_date - d).days <= 3)
                for d in dates
            ],
            dtype=bool,
        )

        sem_calendar[sem_id] = {
            "dates": dates,
            "weeks": weeks,
            "is_weekend": is_weekend,
            "is_mid_dip": is_mid_dip,
            "is_pre_exam": is_pre_exam,
            "n_days": n_days,
            "s_date": s_date,
        }

    # Precompute course item deadlines per (course_id, semester_id)
    items_cache: dict[tuple[str, str], set[date]] = {}
    if coursework is not None:
        for item in coursework:
            pass

    rng = run.child_rng("lms_events")
    session_counter = 0

    # Teaching days per semester (2 semesters per academic year)
    teaching_days_per_sem = teaching_days_year / 2.0
    base_events_per_enrollment = (events_per_day / courses_per_semester) * teaching_days_per_sem

    chunk_buffer: list[dict[str, Any]] = []

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

        cal = sem_calendar[semester_id]
        cache_key = (course_id, semester_id)
        if cache_key not in items_cache:
            c_items = _build_course_items(configs, coursework_params, course_id, semester_id)
            items_cache[cache_key] = {item["due_date"] for item in c_items}
        due_dates = items_cache[cache_key]

        # Pre-deadline mask: within 2 days before any assignment or quiz deadline
        is_pre_deadline = np.array(
            [any(0 <= (due - d).days <= 1 for due in due_dates) for d in cal["dates"]],
            dtype=bool,
        )

        # Compute modulated day weights (weekly and semester rhythms)
        weights = np.ones(cal["n_days"], dtype=float)
        weights[cal["is_weekend"]] *= weekend_factor
        weights[cal["is_mid_dip"]] *= mid_semester_dip_factor
        weights[cal["is_pre_exam"]] *= pre_exam_spike_factor
        weights[is_pre_deadline] *= pre_deadline_spike_factor

        # Decliner engagement fade over semester
        is_decliner = decliner_flags[student_id]
        if is_decliner:
            for w in range(decliner_start_week, cal["weeks"].max() + 1):
                mask = cal["weeks"] == w
                decay = (1.0 - weekly_decay) ** (w - decliner_start_week + 1)
                weights[mask] *= decay

        prob = weights / weights.sum()

        # Compute volume for this student in this course
        school_code = student_school[student_id]
        school_mult = school_profiles.get(school_code.lower(), {}).get("lms_activity", 1.0)
        eng_trait = traits[student_id]["engagement"]
        eng_mult = max(0.2, 1.0 + (eng_trait - engagement_mean))

        events_count = int(round(base_events_per_enrollment * school_mult * eng_mult))
        if is_decliner:
            events_count = int(round(events_count * 0.75))
        events_count = max(10, events_count)

        # Sample event days chronologically
        sampled_days = rng.choice(cal["n_days"], size=events_count, p=prob)
        sampled_days.sort()

        # Generate events day-by-day with strictly increasing timestamps within each day
        unique_days, day_counts = np.unique(sampled_days, return_counts=True)
        for day_idx, count in zip(unique_days, day_counts):
            ev_date = cal["dates"][int(day_idx)]

            # Sample hour using diurnal weights, biased towards active hours
            start_hour = int(rng.choice(24, p=_HOURLY_WEIGHTS))
            start_hour = min(21, max(8, start_hour))
            start_min = int(rng.integers(0, 50))
            start_sec = int(rng.integers(0, 60))
            current_dt = datetime.combine(ev_date, time(start_hour, start_min, start_sec))

            session_counter += 1
            current_session = f"SES{session_counter:07d}"

            for j in range(count):
                if j > 0:
                    # Occasional break creates a new session on the same day
                    if rng.random() < 0.20:
                        session_counter += 1
                        current_session = f"SES{session_counter:07d}"
                        gap_sec = int(rng.integers(1800, 5400))  # 30-90 min break
                    else:
                        gap_sec = int(rng.integers(15, 300))     # short interval within session

                    current_dt = current_dt + timedelta(seconds=gap_sec)
                    if current_dt.date() > ev_date:
                        remaining = int(count - j)
                        current_dt = datetime.combine(ev_date, time(23, 59, 59)) - timedelta(
                            seconds=remaining * 10
                        )

                # Sample event type
                u = rng.random()
                act_type = event_types[int(np.searchsorted(cumulative_probs, u))]

                resource_id = None
                if act_type in ("VIDEO_VIEW", "VIDEO_COMPLETE", "PDF_VIEW", "RESOURCE_DOWNLOAD"):
                    resource_id = f"R{rng.integers(1, 1000):03d}"

                duration_sec = None
                if act_type in ("VIDEO_VIEW", "VIDEO_COMPLETE"):
                    duration_sec = int(rng.integers(60, 7200))
                elif act_type == "PDF_VIEW":
                    duration_sec = int(rng.integers(30, 3600))

                chunk_buffer.append(
                    {
                        "timestamp": current_dt,
                        "meta": {
                            "student_id": student_id,
                            "course_id": course_id,
                            "school": school_code,
                        },
                        "activity_type": act_type,
                        "resource_id": resource_id,
                        "duration_sec": duration_sec,
                        "session_id": current_session,
                    }
                )

        # Yield any filled chunks from buffer
        while len(chunk_buffer) >= chunk_size:
            yield chunk_buffer[:chunk_size]
            chunk_buffer = chunk_buffer[chunk_size:]

    # Yield remaining buffered events
    if chunk_buffer:
        yield chunk_buffer
        chunk_buffer = []


def generate_lms_events(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
    records: list[dict[str, Any]] | None = None,
    coursework: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate all LMS events as a single list (convenience wrapper).

    For large datasets, use :func:`generate_lms_events_chunks` to avoid
    accumulating event records in memory (rules.md §8.4, architecture.md §24, task 5.3).

    Args:
        run: Seeded generator run providing LMS configuration, hierarchy,
            rhythms, coursework, and academic-period configuration.
        students: Previously generated student documents (needed for
            school lookup and traits). When omitted, they are generated.
        records: Previously generated academic records, which define
            enrollments. When omitted, they are generated.
        coursework: Optional previously generated coursework rows. When
            omitted, course item schedules are computed from configuration.

    Returns:
        List of dicts representing LMS events conforming to the
        ``lms_events`` schema contract.
    """
    events: list[dict[str, Any]] = []
    for chunk in generate_lms_events_chunks(run, students, records, coursework):
        events.extend(chunk)
    return events
