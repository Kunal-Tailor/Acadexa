"""Canonical data schemas — the Phase 3 schema contract.

Each schema is a declarative description of one MongoDB collection:

- ``collection``: collection name
- ``grain``: fields that uniquely identify one record (rules.md §12)
- ``grain_description``: human-readable grain statement
- ``fields``: mapping of field name to constraints with keys:
  ``type`` (Python type), ``required`` (bool), optional ``pattern``
  (regex for identifier formats), optional ``min``/``max`` (numeric
  ranges), ``description`` (purpose of the field)

Schemas are the stable contract referenced by the generator, MongoDB
layer, Spark jobs and dashboard. Changing a schema requires following
the schema-change rule in rules.md §11.
"""

from __future__ import annotations

STUDENT_ID_PATTERN = r"^STU\d{6}$"

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
