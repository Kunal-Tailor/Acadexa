"""Canonical data schemas — the Phase 3 schema contract.

Each schema is a declarative description of one MongoDB collection:

- ``collection``: collection name
- ``grain``: fields that uniquely identify one record (rules.md §12)
- ``grain_description``: human-readable grain statement
- ``fields``: mapping of field name to constraints with keys:
  ``type`` (Python type), ``required`` (bool), optional ``pattern``
  (regex for identifier formats), optional ``min``/``max`` (numeric
  ranges), optional ``enum`` (allowed scalar values), optional
  ``item_type``/``min_items`` (list fields), ``description``
  (purpose of the field); schemas may additionally declare
  ``invariants``: cross-field statements that records must satisfy

Schemas are the stable contract referenced by the generator, MongoDB
layer, Spark jobs and dashboard. Changing a schema requires following
the schema-change rule in rules.md §11.
"""

from __future__ import annotations

from datetime import date

STUDENT_ID_PATTERN = r"^STU\d{6}$"
COURSE_ID_PATTERN = r"^[A-Z]{2,5}\d{3}$"
SEMESTER_ID_PATTERN = r"^S[1-4]$"
DIFFICULTY_LEVELS = ("easy", "medium", "hard")

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
