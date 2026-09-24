"""Tests for configuration-driven university hierarchy generation (task 4.2)."""

from __future__ import annotations

import copy
import re

import pytest

from acadexa.config import validate_project_config
from acadexa.generator import GeneratorError, generate_university_hierarchy
from acadexa.validation import COURSE_ID_PATTERN


@pytest.fixture()
def configs() -> dict:
    return validate_project_config()


# ── Structure matches configuration ─────────────────────


def test_default_load_generates_hierarchy() -> None:
    hierarchy = generate_university_hierarchy()
    assert hierarchy.schools and hierarchy.departments
    assert hierarchy.programs and hierarchy.courses


def test_counts_match_configuration(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    assert len(hierarchy.schools) == len(configs["hierarchy"]["schools"]) == 6
    assert len(hierarchy.departments) == len(configs["hierarchy"]["departments"]) == 18
    assert len(hierarchy.programs) == len(configs["hierarchy"]["programs"]) == 40
    assert len(hierarchy.courses) == len(configs["courses"]["courses"])


def test_university_metadata_matches_config(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    assert hierarchy.university == configs["hierarchy"]["university"]
    assert hierarchy.university["name"] == "RAS University"


def test_school_records_match_config(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    for school in hierarchy.schools:
        spec = configs["hierarchy"]["schools"][school["id"]]
        assert school["code"] == spec["code"]
        assert school["name"] == spec["name"]


def test_course_ids_and_titles_match_configuration(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    catalogue = configs["courses"]["courses"]
    assert [c["course_id"] for c in hierarchy.courses] == list(catalogue)
    for course in hierarchy.courses:
        assert course["title"] == catalogue[course["course_id"]]["title"]
        assert re.match(COURSE_ID_PATTERN, course["course_id"])


# ── Referential integrity ───────────────────────────────


def test_department_school_references_resolve(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    school_ids = {school["id"] for school in hierarchy.schools}
    assert all(dept["school_id"] in school_ids for dept in hierarchy.departments)


def test_program_department_references_resolve(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    department_ids = {dept["id"] for dept in hierarchy.departments}
    assert all(program["department_id"] in department_ids for program in hierarchy.programs)


def test_course_hierarchy_names_resolve(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    schools = {school["id"]: school["name"] for school in hierarchy.schools}
    departments = {dept["id"]: dept for dept in hierarchy.departments}
    catalogue = configs["courses"]["courses"]
    for course in hierarchy.courses:
        department = departments[catalogue[course["course_id"]]["department"]]
        assert course["department"] == department["name"]
        assert course["school"] == schools[department["school_id"]]


def test_specific_course_resolution(configs: dict) -> None:
    hierarchy = generate_university_hierarchy(configs)
    course = next(c for c in hierarchy.courses if c["course_id"] == "CSA101")
    assert course["title"] == "Programming Fundamentals"
    assert course["department"] == "Computer Science and Applications"
    assert course["school"] == "School of Computer Engineering & Technology"


# ── Determinism & configuration-driven behavior ────────


def test_generation_is_deterministic(configs: dict) -> None:
    first = generate_university_hierarchy(configs)
    second = generate_university_hierarchy(configs)
    assert first == second


def test_added_school_appears_without_code_changes(configs: dict) -> None:
    extended = copy.deepcopy(configs)
    extended["hierarchy"]["schools"]["new"] = {"code": "NEW", "name": "School of Testing"}
    extended["hierarchy"]["departments"]["nwd"] = {
        "school": "new",
        "code": "NWD",
        "name": "New Department",
    }
    extended["hierarchy"]["programs"]["bnew"] = {
        "department": "nwd",
        "degree": "B.Sc",
        "name": "B.Sc New",
    }
    extended["courses"]["courses"]["NWD101"] = {
        "title": "Test Course",
        "department": "nwd",
    }
    hierarchy = generate_university_hierarchy(extended)
    assert any(s["id"] == "new" for s in hierarchy.schools)
    course = next(c for c in hierarchy.courses if c["course_id"] == "NWD101")
    assert course["school"] == "School of Testing"
    assert course["department"] == "New Department"


# ── Initialization failures ─────────────────────────────


def test_missing_hierarchy_configuration_raises() -> None:
    with pytest.raises(GeneratorError, match="missing 'hierarchy'"):
        generate_university_hierarchy({"courses": {"courses": {}}})


def test_unknown_course_department_raises(configs: dict) -> None:
    broken = copy.deepcopy(configs)
    broken["courses"]["courses"]["CSA101"]["department"] = "ghost"
    with pytest.raises(GeneratorError, match="unknown department 'ghost'"):
        generate_university_hierarchy(broken)


def test_unknown_department_school_raises(configs: dict) -> None:
    broken = copy.deepcopy(configs)
    broken["hierarchy"]["departments"]["csa"]["school"] = "ghost"
    with pytest.raises(GeneratorError, match="unknown school 'ghost'"):
        generate_university_hierarchy(broken)
