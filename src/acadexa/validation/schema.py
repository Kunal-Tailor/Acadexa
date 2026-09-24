"""Canonical data schemas — the Phase 3 schema contract.

Each schema is a declarative description of one MongoDB collection:

- ``collection``: collection name
- ``grain``: fields that uniquely identify one record (rules.md §12)
- ``grain_description``: human-readable grain statement
- ``fields``: mapping of field name to constraints with keys:
  ``type`` (Python type), ``required`` (bool), optional ``pattern``
  (regex for identifier formats), optional ``min``/``max`` (numeric
  ranges), optional ``enum`` (allowed scalar values), optional
  ``item_type``/``min_items`` (list fields), optional ``nullable``
  (value may be ``None``), ``description`` (purpose of the field);
  object-valued fields may declare nested ``fields``; schemas may
  additionally declare ``invariants``: cross-field statements that
  records must satisfy, and time-series collections declare
  ``time_field``/``meta_field`` (MongoDB time-series keys)

Schemas are the stable contract referenced by the generator, MongoDB
layer, Spark jobs and dashboard. Changing a schema requires following
the schema-change rule in rules.md §11.
"""

from __future__ import annotations

from datetime import date, datetime

STUDENT_ID_PATTERN = r"^STU\d{6}$"
COURSE_ID_PATTERN = r"^[A-Z]{2,5}\d{3}$"
SEMESTER_ID_PATTERN = r"^S[1-4]$"
SESSION_ID_PATTERN = r"^SES\d{7}$"
SCHOOL_CODE_PATTERN = r"^[A-Z]{3}$"
DIFFICULTY_LEVELS = ("easy", "medium", "hard")
LMS_EVENT_TYPES = (
    "LOGIN",
    "LOGOUT",
    "VIDEO_VIEW",
    "VIDEO_COMPLETE",
    "PDF_VIEW",
    "RESOURCE_DOWNLOAD",
    "QUIZ_ATTEMPT",
    "ASSIGNMENT_VIEW",
    "ASSIGNMENT_SUBMISSION",
    "COURSE_PAGE_VIEW",
    "FORUM_POST",
)

STUDENTS_SCHEMA: dict = {
    "collection": "students",
    "grain": ["student_id"],
    "grain_description": "one document per student",
    "fields": {
        "student_id": {
            "type": str,
            "required": True,
            "pattern": STUDENT_ID_PATTERN,
            "description": "Stable synthetic identifier, e.g. STU010482",
        },
        "school": {
            "type": str,
            "required": True,
            "description": "Hierarchy reference: school name",
        },
        "department": {
            "type": str,
            "required": True,
            "description": "Hierarchy reference: department name",
        },
        "program": {
            "type": str,
            "required": True,
            "description": "Hierarchy reference: program name",
        },
        "batch": {
            "type": int,
            "required": True,
            "min": 2000,
            "description": "Enrollment year of the student cohort",
        },
        "semester": {
            "type": int,
            "required": True,
            "min": 1,
            "max": 4,
            "description": "Current semester index (2 academic years / 4 semesters)",
        },
    },
    "example": {
        "student_id": "STU010482",
        "school": "Computer Engineering & Technology",
        "department": "Computer Science and Applications",
        "program": "B.Tech CSE (AI & DS)",
        "batch": 2024,
        "semester": 3,
    },
}

COURSES_SCHEMA: dict = {
    "collection": "courses",
    "grain": ["course_id"],
    "grain_description": "one document per course",
    "fields": {
        "course_id": {
            "type": str,
            "required": True,
            "pattern": COURSE_ID_PATTERN,
            "description": "Stable course identifier, e.g. CSA101 or CSE301",
        },
        "title": {
            "type": str,
            "required": True,
            "description": "Course title from the catalogue",
        },
        "school": {
            "type": str,
            "required": True,
            "description": "Hierarchy reference: school name",
        },
        "department": {
            "type": str,
            "required": True,
            "description": "Hierarchy reference: department name",
        },
        "semester_applicability": {
            "type": list,
            "required": True,
            "item_type": int,
            "min_items": 1,
            "min": 1,
            "max": 4,
            "description": "Semester indexes (1–4) in which the course is offered",
        },
        "difficulty_level": {
            "type": str,
            "required": True,
            "enum": list(DIFFICULTY_LEVELS),
            "description": "Difficulty bucket assigned from generator configuration shares",
        },
        "difficulty": {
            "type": float,
            "required": True,
            "min": 0.0,
            "max": 1.0,
            "description": "Numeric difficulty factor used by the behavioral model",
        },
    },
    "example": {
        "course_id": "CSA101",
        "title": "Programming Fundamentals",
        "school": "School of Computer Engineering & Technology",
        "department": "Computer Science and Applications",
        "semester_applicability": [1, 2],
        "difficulty_level": "easy",
        "difficulty": 0.35,
    },
}

ACADEMIC_RECORDS_SCHEMA: dict = {
    "collection": "academic_records",
    "grain": ["student_id", "course_id", "semester_id"],
    "grain_description": "student × course × semester",
    "fields": {
        "student_id": {
            "type": str,
            "required": True,
            "pattern": STUDENT_ID_PATTERN,
            "description": "Student reference",
        },
        "course_id": {
            "type": str,
            "required": True,
            "pattern": COURSE_ID_PATTERN,
            "description": "Course reference",
        },
        "semester_id": {
            "type": str,
            "required": True,
            "pattern": SEMESTER_ID_PATTERN,
            "description": "Semester reference (ids from config/university/academic_periods.toml)",
        },
        "internal_marks": {
            "type": int,
            "required": True,
            "min": 0,
            "max": 100,
            "description": "Internal assessment marks (validity bound 0–100)",
        },
        "midterm_marks": {
            "type": int,
            "required": True,
            "min": 0,
            "max": 100,
            "description": "Midterm marks (validity bound 0–100)",
        },
        "endterm_marks": {
            "type": int,
            "required": True,
            "min": 0,
            "max": 100,
            "description": "Endterm marks (validity bound 0–100)",
        },
        "final_grade": {
            "type": str,
            "required": True,
            "description": "Term letter grade, e.g. A",
        },
    },
    "example": {
        "student_id": "STU010482",
        "course_id": "CSE301",
        "semester_id": "S1",
        "internal_marks": 34,
        "midterm_marks": 18,
        "endterm_marks": 42,
        "final_grade": "A",
    },
}

ATTENDANCE_SCHEMA: dict = {
    "collection": "attendance",
    "grain": ["student_id", "course_id", "week_start"],
    "grain_description": "student × course × week",
    "fields": {
        "student_id": {
            "type": str,
            "required": True,
            "pattern": STUDENT_ID_PATTERN,
            "description": "Student reference",
        },
        "course_id": {
            "type": str,
            "required": True,
            "pattern": COURSE_ID_PATTERN,
            "description": "Course reference",
        },
        "semester_id": {
            "type": str,
            "required": True,
            "pattern": SEMESTER_ID_PATTERN,
            "description": "Semester reference (ids from config/university/academic_periods.toml)",
        },
        "week_start": {
            "type": date,
            "required": True,
            "description": "Monday starting the attendance week",
        },
        "classes_conducted": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "Raw count of classes conducted that week (denominator)",
        },
        "classes_attended": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "Raw count of classes attended that week; must not exceed classes_conducted",
        },
    },
    "invariants": [
        "classes_attended <= classes_conducted",
        "attendance percentage is derived, never stored as the raw field (rules.md §13)",
        "week_start is a Monday (calendar convention: Monday–Sunday weeks)",
    ],
    "example": {
        "student_id": "STU010482",
        "course_id": "CSE301",
        "semester_id": "S1",
        "week_start": date(2025, 9, 1),
        "classes_conducted": 4,
        "classes_attended": 3,
    },
}

COURSEWORK_SCHEMA: dict = {
    "collection": "coursework",
    "grain": ["student_id", "course_id", "item_id"],
    "grain_description": "student × coursework item (item_id unique within a course)",
    "fields": {
        "student_id": {
            "type": str,
            "required": True,
            "pattern": STUDENT_ID_PATTERN,
            "description": "Student reference",
        },
        "course_id": {
            "type": str,
            "required": True,
            "pattern": COURSE_ID_PATTERN,
            "description": "Course reference",
        },
        "item_id": {
            "type": str,
            "required": True,
            "description": "Coursework item identifier within the course, e.g. A07",
        },
        "item_type": {
            "type": str,
            "required": True,
            "enum": ["ASSIGNMENT", "QUIZ"],
            "description": "Unified coursework item type (features.md F-B06)",
        },
        "assigned_date": {
            "type": date,
            "required": True,
            "description": "Date the item was assigned",
        },
        "due_date": {
            "type": date,
            "required": True,
            "description": "Submission deadline",
        },
        "submitted_at": {
            "type": datetime,
            "required": True,
            "nullable": True,
            "description": "Submission timestamp; null when not submitted (status MISSING)",
        },
        "score": {
            "type": int,
            "required": True,
            "nullable": True,
            "min": 0,
            "description": "Earned score; null when not submitted (status MISSING)",
        },
        "max_score": {
            "type": int,
            "required": True,
            "min": 1,
            "description": "Maximum score attainable for the item",
        },
        "attempts": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "Number of attempts made (0 when not submitted)",
        },
        "status": {
            "type": str,
            "required": True,
            "enum": ["ON_TIME", "LATE", "MISSING"],
            "description": "Submission status: LATE is documented (original_idea example); "
            "ON_TIME/MISSING complete the set required by late-submission and "
            "coursework-completion analytics",
        },
    },
    "invariants": [
        "assigned_date <= due_date",
        "status matches timing: MISSING ⟺ submitted_at is null; "
        "LATE ⟺ submitted_at is after the end of the due day "
        "(submitted_at.date() > due_date); otherwise ON_TIME",
        "score is null exactly when status is MISSING; when present, score <= max_score",
    ],
    "example": {
        "student_id": "STU010482",
        "course_id": "CSE301",
        "item_id": "A07",
        "item_type": "ASSIGNMENT",
        "assigned_date": date(2025, 9, 8),
        "due_date": date(2025, 9, 15),
        "submitted_at": datetime(2025, 9, 17, 21, 40, 0),
        "score": 15,
        "max_score": 20,
        "attempts": 1,
        "status": "LATE",
    },
}

LMS_EVENTS_SCHEMA: dict = {
    "collection": "lms_events",
    "grain": [
        "timestamp",
        "meta",
        "activity_type",
        "resource_id",
        "duration_sec",
        "session_id",
    ],
    "grain_description": "one document per LMS event (whole-document identity)",
    "time_field": "timestamp",
    "meta_field": "meta",
    "fields": {
        "timestamp": {
            "type": datetime,
            "required": True,
            "description": "Event timestamp; MongoDB time-series timeField",
        },
        "meta": {
            "type": dict,
            "required": True,
            "description": "Time-series metaField carrying student/course/school context",
            "fields": {
                "student_id": {
                    "type": str,
                    "required": True,
                    "pattern": STUDENT_ID_PATTERN,
                    "description": "Student reference",
                },
                "course_id": {
                    "type": str,
                    "required": True,
                    "pattern": COURSE_ID_PATTERN,
                    "description": "Course reference",
                },
                "school": {
                    "type": str,
                    "required": True,
                    "pattern": SCHOOL_CODE_PATTERN,
                    "description": "Hierarchy school code (config/university/hierarchy.toml), e.g. CET",
                },
            },
        },
        "activity_type": {
            "type": str,
            "required": True,
            "enum": list(LMS_EVENT_TYPES),
            "description": "LMS activity type; closed list per rules.md §14",
        },
        "resource_id": {
            "type": str,
            "required": True,
            "nullable": True,
            "description": "Resource identifier, e.g. R118; null for events without a resource",
        },
        "duration_sec": {
            "type": int,
            "required": True,
            "nullable": True,
            "min": 0,
            "description": "Event duration in seconds; null when not applicable",
        },
        "session_id": {
            "type": str,
            "required": True,
            "pattern": SESSION_ID_PATTERN,
            "description": "LMS session grouping identifier, e.g. SES3320041",
        },
    },
    "example": {
        "timestamp": datetime(2025, 9, 17, 10, 15, 0),
        "meta": {
            "student_id": "STU010482",
            "course_id": "CSE301",
            "school": "CET",
        },
        "activity_type": "VIDEO_VIEW",
        "resource_id": "R118",
        "duration_sec": 1080,
        "session_id": "SES3320041",
    },
}

STUDENT_FEATURES_SCHEMA: dict = {
    "collection": "student_features",
    "grain": ["student_id", "semester_id"],
    "grain_description": "student × semester",
    "fields": {
        "student_id": {
            "type": str,
            "required": True,
            "pattern": STUDENT_ID_PATTERN,
            "description": "Student reference",
        },
        "semester_id": {
            "type": str,
            "required": True,
            "pattern": SEMESTER_ID_PATTERN,
            "description": "Semester reference (ids from config/university/academic_periods.toml)",
        },
        "attendance_mean": {
            "type": float,
            "required": True,
            "min": 0.0,
            "max": 100.0,
            "description": "Attendance summary: mean derived attendance percentage for the semester",
        },
        "engagement_count": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "Engagement count: LMS events for the student in the semester",
        },
        "late_submission_rate": {
            "type": float,
            "required": True,
            "min": 0.0,
            "max": 1.0,
            "description": "Fraction of the student's assignments submitted late in the semester",
        },
        "score_trend": {
            "type": float,
            "required": True,
            "description": "Recent-minus-earlier graded-item average in points; negative = declining",
        },
    },
    "example": {
        "student_id": "STU010482",
        "semester_id": "S1",
        "attendance_mean": 78.5,
        "engagement_count": 412,
        "late_submission_rate": 0.2,
        "score_trend": -12.0,
    },
}

COURSE_METRICS_SCHEMA: dict = {
    "collection": "course_metrics",
    "grain": ["course_id", "semester_id"],
    "grain_description": "course × semester",
    "fields": {
        "course_id": {
            "type": str,
            "required": True,
            "pattern": COURSE_ID_PATTERN,
            "description": "Course reference",
        },
        "semester_id": {
            "type": str,
            "required": True,
            "pattern": SEMESTER_ID_PATTERN,
            "description": "Semester reference (ids from config/university/academic_periods.toml)",
        },
        "avg_performance": {
            "type": float,
            "required": True,
            "min": 0.0,
            "max": 100.0,
            "description": "Mean performance of enrolled students in the semester",
        },
        "avg_attendance": {
            "type": float,
            "required": True,
            "min": 0.0,
            "max": 100.0,
            "description": "Mean derived attendance percentage for the course",
        },
        "engagement_count": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "LMS events for the course in the semester",
        },
        "difficulty_adjusted_performance": {
            "type": float,
            "required": True,
            "description": "Within-course normalized performance (z-score style, unbounded)",
        },
    },
    "example": {
        "course_id": "CSA101",
        "semester_id": "S1",
        "avg_performance": 71.2,
        "avg_attendance": 82.4,
        "engagement_count": 15230,
        "difficulty_adjusted_performance": -0.35,
    },
}

SCHOOL_SUMMARY_SCHEMA: dict = {
    "collection": "school_summary",
    "grain": ["school", "department"],
    "grain_description": "school × department roll-up",
    "fields": {
        "school": {
            "type": str,
            "required": True,
            "description": "Hierarchy reference: school name (config/university/hierarchy.toml)",
        },
        "department": {
            "type": str,
            "required": True,
            "description": "Hierarchy reference: department name",
        },
        "student_count": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "Students in the department roll-up",
        },
        "course_count": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "Courses in the roll-up",
        },
        "avg_performance": {
            "type": float,
            "required": True,
            "min": 0.0,
            "max": 100.0,
            "description": "Mean performance across the roll-up",
        },
        "avg_attendance": {
            "type": float,
            "required": True,
            "min": 0.0,
            "max": 100.0,
            "description": "Mean derived attendance percentage across the roll-up",
        },
        "engagement_count": {
            "type": int,
            "required": True,
            "min": 0,
            "description": "LMS events for the roll-up",
        },
    },
    "example": {
        "school": "School of Computer Engineering & Technology",
        "department": "Computer Science and Applications",
        "student_count": 1840,
        "course_count": 12,
        "avg_performance": 73.5,
        "avg_attendance": 80.1,
        "engagement_count": 245000,
    },
}

RISK_INDICATORS_SCHEMA: dict = {
    "collection": "risk_indicators",
    "grain": ["student_id", "week_start"],
    "grain_description": "student × week",
    "fields": {
        "student_id": {
            "type": str,
            "required": True,
            "pattern": STUDENT_ID_PATTERN,
            "description": "Student reference",
        },
        "week_start": {
            "type": date,
            "required": True,
            "description": "Monday starting the evaluation week",
        },
        "signal_count": {
            "type": int,
            "required": True,
            "min": 0,
            "max": 5,
            "description": "Observed signal count 0–5; not a prediction (prd.md §15.3)",
        },
        "low_attendance": {
            "type": bool,
            "required": True,
            "description": "Signal 1 flag: term-to-date attendance below threshold",
        },
        "lms_decline": {
            "type": bool,
            "required": True,
            "description": "Signal 2 flag: last 4 weeks at or below the decline threshold",
        },
        "late_submissions": {
            "type": bool,
            "required": True,
            "description": "Signal 3 flag: more than the configured share of assignments late",
        },
        "marks_decline": {
            "type": bool,
            "required": True,
            "description": "Signal 4 flag: recent graded-item average below earlier average by threshold",
        },
        "low_quiz_activity": {
            "type": bool,
            "required": True,
            "description": "Signal 5 flag: quiz attempts in the bottom quartile of the student's course",
        },
        "explanations": {
            "type": dict,
            "required": True,
            "description": "Per-signal traceability to the underlying metric/value (tasks.md 8.8)",
            "fields": {
                "low_attendance": {
                    "type": str,
                    "required": True,
                    "description": "Metric/value behind the low-attendance flag",
                },
                "lms_decline": {
                    "type": str,
                    "required": True,
                    "description": "Metric/value behind the LMS-decline flag",
                },
                "late_submissions": {
                    "type": str,
                    "required": True,
                    "description": "Metric/value behind the late-submissions flag",
                },
                "marks_decline": {
                    "type": str,
                    "required": True,
                    "description": "Metric/value behind the marks-decline flag",
                },
                "low_quiz_activity": {
                    "type": str,
                    "required": True,
                    "description": "Metric/value behind the low-quiz-activity flag",
                },
            },
        },
        "computed_at": {
            "type": datetime,
            "required": True,
            "description": "Timestamp of the pipeline run that published this record (tasks.md 9.3 run metadata)",
        },
    },
    "invariants": [
        "signal_count equals the number of true signal flags "
        "(each signal contributes one point, maximum 5)",
    ],
    "example": {
        "student_id": "STU010482",
        "week_start": date(2025, 11, 3),
        "signal_count": 3,
        "low_attendance": True,
        "lms_decline": True,
        "late_submissions": False,
        "marks_decline": True,
        "low_quiz_activity": False,
        "explanations": {
            "low_attendance": "term-to-date attendance 68.0% < 75% threshold",
            "lms_decline": "last 4 weeks = 42% of previous 4 weeks (<= 50% threshold)",
            "late_submissions": "late rate 20.0% <= 30% threshold",
            "marks_decline": "recent average -12.0 pts vs earlier average (>= 10 pts below)",
            "low_quiz_activity": "quiz attempts 6 not in bottom quartile",
        },
        "computed_at": datetime(2025, 11, 3, 6, 0, 0),
    },
}
