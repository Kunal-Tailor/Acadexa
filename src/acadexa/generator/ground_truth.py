"""Synthetic ground-truth registry (F-B09, memory.md §7, §23, rules.md §9).

Establishes the documented ground truth before analytical results are
observed. The ground-truth registry defines:
1. Planted analytical relationships (attendance, LMS engagement, late
   submissions, and coursework) and their expected directions/strengths.
2. Course difficulty as a confounding factor.
3. The decoy relationship (forum activity vs marks) with zero planted
   relationship, serving as a negative control for recovery testing.
4. The exact synthetic decliner population, parameters, and per-student
   decliner status (reusing :func:`generate_decliner_flags`).

Architecture & Rules:
- Rules.md §9 & §31: Ground truth must be established before recovery analysis
  and never modified after inspecting analytical results.
- Memory.md §8: Acadexa measures statistical association, not causation;
  relationships are described as associations, not discoveries about real students.
- Memory.md §23 & F-F01: Analytics pipeline compares what was planted vs what
  was recovered, explicitly distinguishing planted, recovered, and decoy.
- Reproducibility: For a given run seed and student cohort, the ground-truth
  registry is fully deterministic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from acadexa.generator.decliners import _validate_decliner_params, generate_decliner_flags
from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students

DEFAULT_GROUND_TRUTH_PATH: Path = Path("data/manifests/ground_truth_registry.json")

PLANTED_RELATIONSHIPS: list[dict[str, Any]] = [
    {
        "id": "attendance_marks",
        "name": "Attendance to Marks",
        "independent_variable": "attendance_rate",
        "dependent_variable": "final_marks",
        "relationship_type": "planted",
        "expected_direction": "positive",
        "expected_strength": "moderate",
        "description": "Higher student attendance is associated with higher marks.",
        "mechanism": (
            "Diligence trait increases attendance probability via diligence_attendance_weight; "
            "ability trait increases marks via ability_marks_weight; diligence and ability are "
            "positively correlated latent traits."
        ),
    },
    {
        "id": "lms_engagement_marks",
        "name": "LMS Engagement to Marks",
        "independent_variable": "lms_events",
        "dependent_variable": "final_marks",
        "relationship_type": "planted",
        "expected_direction": "positive",
        "expected_strength": "moderate_school_dependent",
        "description": "Higher LMS event count is associated with higher marks, with strength varying by school.",
        "mechanism": (
            "Engagement trait scales base event frequency and attendance; school lms_activity multipliers "
            "(CET highest at 1.40, SOL lowest at 0.85) modulate event volume; engagement correlates with ability."
        ),
    },
    {
        "id": "late_submissions_marks",
        "name": "Late Submission Rate to Marks",
        "independent_variable": "late_submission_rate",
        "dependent_variable": "final_marks",
        "relationship_type": "planted",
        "expected_direction": "negative",
        "expected_strength": "moderate",
        "description": "Higher rate of late coursework submissions is associated with lower marks.",
        "mechanism": (
            "Diligence trait reduces late submission probability via diligence_late_weight; "
            "higher diligence correlates with higher ability and higher marks."
        ),
    },
    {
        "id": "quiz_attempts_marks",
        "name": "Quiz Attempts to Marks",
        "independent_variable": "quiz_attempts",
        "dependent_variable": "final_marks",
        "relationship_type": "planted",
        "expected_direction": "positive",
        "expected_strength": "moderate_school_dependent",
        "description": "Higher quiz activity and attempts are associated with higher marks.",
        "mechanism": (
            "Diligence and school quiz_activity multipliers drive assessment engagement and multiple attempts; "
            "diligent students achieve higher marks."
        ),
    },
    {
        "id": "course_difficulty_confounder",
        "name": "Course Difficulty Confounder",
        "independent_variable": "course_difficulty",
        "dependent_variable": "course_marks_and_attendance",
        "relationship_type": "confounder",
        "expected_direction": "negative",
        "expected_strength": "moderate",
        "description": "Course difficulty acts as a confounding factor shifting marks and attendance jointly across courses.",
        "mechanism": (
            "Course difficulty level applies downward shifts to marks (-8 / -16) and attendance (-0.05 / -0.10); "
            "within-course z-scoring in J4 is required to isolate true student traits from course difficulty effects."
        ),
    },
]

DECOY_RELATIONSHIP: dict[str, Any] = {
    "id": "decoy_forum_marks",
    "name": "Forum Activity to Marks (Decoy)",
    "independent_variable": "forum_events",
    "dependent_variable": "final_marks",
    "relationship_type": "decoy",
    "expected_direction": "none",
    "expected_strength": "none",
    "description": (
        "No intentionally planted relationship between forum activity and marks; "
        "serves as a negative control for recovery testing."
    ),
    "mechanism": (
        "Forum posts and replies are generated as general LMS activity without a specific coupling "
        "to ability or diligence, so recovery analytics must confirm no significant association."
    ),
}


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


@dataclass
class GroundTruthRegistry:
    """Immutable registry of synthetic ground truth known prior to analysis.

    Contains planted relationships, the decoy relationship, decliner behavior
    parameters, and per-student decliner status.
    """

    seed: int
    generation_timestamp: datetime
    planted_relationships: list[dict[str, Any]]
    decoy_relationship: dict[str, Any]
    decliner_behavior: dict[str, Any]
    decliner_flags: dict[str, bool]
    metadata: dict[str, Any]

    @property
    def decliner_student_ids(self) -> list[str]:
        """Sorted list of student identifiers flagged as decliners."""
        return sorted(sid for sid, flag in self.decliner_flags.items() if flag)

    @property
    def planted_relationship_ids(self) -> list[str]:
        """List of planted relationship identifiers."""
        return [r["id"] for r in self.planted_relationships]

    def is_decliner(self, student_id: str) -> bool:
        """Return True if ``student_id`` is flagged as a decliner."""
        return self.decliner_flags.get(student_id, False)

    def get_relationship(self, relationship_id: str) -> dict[str, Any] | None:
        """Lookup a relationship (planted or decoy) by its identifier."""
        if self.decoy_relationship.get("id") == relationship_id:
            return copy.deepcopy(self.decoy_relationship)
        for rel in self.planted_relationships:
            if rel.get("id") == relationship_id:
                return copy.deepcopy(rel)
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry to a JSON-compatible dictionary."""
        return {
            "seed": self.seed,
            "generation_timestamp": self.generation_timestamp.isoformat(),
            "planted_relationships": copy.deepcopy(self.planted_relationships),
            "decoy_relationship": copy.deepcopy(self.decoy_relationship),
            "decliner_behavior": copy.deepcopy(self.decliner_behavior),
            "decliner_flags": dict(self.decliner_flags),
            "metadata": copy.deepcopy(self.metadata),
        }

    def save(self, path: str | Path | None = None) -> Path:
        """Save the registry to disk as a JSON file.

        Args:
            path: Target JSON file path. Defaults to DEFAULT_GROUND_TRUTH_PATH.

        Returns:
            Resolved Path written to.
        """
        target = Path(path) if path is not None else DEFAULT_GROUND_TRUTH_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundTruthRegistry:
        """Reconstruct a GroundTruthRegistry from a dictionary."""
        _check(isinstance(data, dict), "data must be a dictionary")
        _check("seed" in data, "Ground-truth data missing 'seed'")
        _check("generation_timestamp" in data, "Ground-truth data missing 'generation_timestamp'")
        _check("planted_relationships" in data, "Ground-truth data missing 'planted_relationships'")
        _check("decoy_relationship" in data, "Ground-truth data missing 'decoy_relationship'")
        _check("decliner_behavior" in data, "Ground-truth data missing 'decliner_behavior'")
        _check("decliner_flags" in data, "Ground-truth data missing 'decliner_flags'")

        ts = data["generation_timestamp"]
        if isinstance(ts, str):
            generation_timestamp = datetime.fromisoformat(ts)
        elif isinstance(ts, datetime):
            generation_timestamp = ts
        else:
            raise GeneratorError("generation_timestamp must be ISO string or datetime")

        return cls(
            seed=int(data["seed"]),
            generation_timestamp=generation_timestamp,
            planted_relationships=copy.deepcopy(data["planted_relationships"]),
            decoy_relationship=copy.deepcopy(data["decoy_relationship"]),
            decliner_behavior=copy.deepcopy(data["decliner_behavior"]),
            decliner_flags=dict(data["decliner_flags"]),
            metadata=copy.deepcopy(data.get("metadata", {})),
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> GroundTruthRegistry:
        """Load a GroundTruthRegistry from a JSON file.

        Args:
            path: Source JSON file path. Defaults to DEFAULT_GROUND_TRUTH_PATH.

        Returns:
            Parsed GroundTruthRegistry instance.

        Raises:
            FileNotFoundError: if path does not exist.
            GeneratorError: if file contents are invalid.
        """
        target = Path(path) if path is not None else DEFAULT_GROUND_TRUTH_PATH
        if not target.exists():
            raise FileNotFoundError(f"Ground-truth file not found: {target}")
        content = json.loads(target.read_text(encoding="utf-8"))
        return cls.from_dict(content)


def generate_ground_truth_registry(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
    decliner_flags: dict[str, bool] | None = None,
) -> GroundTruthRegistry:
    """Generate the synthetic ground-truth registry for a generator run (task 5.5).

    Establishes the documented ground truth before analytical results are
    observed (rules.md §9, memory.md §23). Reuses :func:`generate_decliner_flags`
    to register the exact decliner student population deterministically.

    Args:
        run: Seeded generator run providing configuration and seed.
        students: Previously generated student documents. When omitted,
            students are generated for this run.
        decliner_flags: Optional pre-computed decliner mapping from
            :func:`generate_decliner_flags`. When omitted, flags are computed.

    Returns:
        Populated :class:`GroundTruthRegistry`.

    Raises:
        GeneratorError: if configuration is missing or invalid.
    """
    configs = run.configs
    _check(
        "generator" in configs and "behavior" in configs.get("generator", {}),
        "configs missing generator behavior configuration",
    )
    behavior = configs["generator"]["behavior"]
    decliner_params = _validate_decliner_params(behavior)

    if students is None:
        students = generate_students(run)

    if decliner_flags is None:
        decliner_flags = generate_decliner_flags(run, students)

    total_students = len(students)
    decliner_ids = sorted(sid for sid, is_dec in decliner_flags.items() if is_dec)
    decliners_count = len(decliner_ids)
    actual_rate = round(decliners_count / total_students, 4) if total_students > 0 else 0.0

    decliner_behavior = {
        "configured_rate": float(decliner_params["rate"]),
        "start_week": int(decliner_params["start_week"]),
        "weekly_engagement_decay": float(decliner_params["weekly_engagement_decay"]),
        "marks_decline_lag_weeks": int(decliner_params["marks_decline_lag_weeks"]),
        "component_weeks": dict(decliner_params["component_weeks"]),
        "marks_weekly_decline": float(decliner_params["marks_weekly_decline"]),
        "score_weekly_decay": float(decliner_params["score_weekly_decay"]),
        "total_students": total_students,
        "decliners_count": decliners_count,
        "actual_decliner_rate": actual_rate,
        "decliner_student_ids": decliner_ids,
    }

    metadata = {
        "registry_version": "1.0",
        "description": "Synthetic ground-truth registry established prior to analytical observation.",
        "analytical_interpretation": "Acadexa measures statistical association, not causation (rules.md §8, memory.md §8).",
        "planted_count": len(PLANTED_RELATIONSHIPS),
        "decoy_count": 1,
    }

    return GroundTruthRegistry(
        seed=run.seed,
        generation_timestamp=datetime.now(timezone.utc),
        planted_relationships=copy.deepcopy(PLANTED_RELATIONSHIPS),
        decoy_relationship=copy.deepcopy(DECOY_RELATIONSHIP),
        decliner_behavior=decliner_behavior,
        decliner_flags=dict(decliner_flags),
        metadata=metadata,
    )


def load_ground_truth_registry(
    path: str | Path | None = None,
) -> GroundTruthRegistry:
    """Load a GroundTruthRegistry from a JSON file.

    Args:
        path: Path to JSON file. Defaults to DEFAULT_GROUND_TRUTH_PATH.

    Returns:
        Loaded GroundTruthRegistry instance.
    """
    return GroundTruthRegistry.load(path)
