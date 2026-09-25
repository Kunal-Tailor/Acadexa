"""Controlled data-quality injection (F-B10, memory.md §12, rules.md §10).

Deliberately introduces controlled data-quality problems into generated
records across the six approved categories:
1. Duplicate LMS events (~1%): duplicate event rows.
2. Nulls in non-key fields (~1.5%): duration, resource_id, score, marks.
   Key identifiers must NEVER be nulled (rules.md §10.1).
3. Timestamp format inconsistencies (~1%): non-standard date format strings.
4. Course ID formatting (~0.5%): casing (lowercase, mixed) and whitespace.
5. Orphan records (~0.1%): student_id not present in students collection.
6. Out-of-range values (~0.1%): negative durations, attendance > 100%,
   marks > 100 or < 0, coursework score > max_score.

Architecture & Rules:
- Rules.md §10.1: Key identifiers must not be intentionally nulled.
- Rules.md §10.2: Every injection run must record exact injected counts.
- RNG Isolation (rules.md §8.2, IDE_Context.md §10): All random injection
  draws use the dedicated ``data_quality_injection`` child RNG stream.
- Non-destructive: Functions work on record copies and return modified
  records along with exact counts of injected issues.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np

from acadexa.generator.foundation import GeneratorError, GeneratorRun

INJECTION_RATE_KEYS: tuple[str, ...] = (
    "duplicate_lms_events",
    "nulls_non_key",
    "timestamp_inconsistencies",
    "course_id_formatting",
    "orphan_records",
    "out_of_range_values",
)

DEFAULT_INJECTION_RATES: dict[str, float] = {
    "duplicate_lms_events": 0.01,
    "nulls_non_key": 0.015,
    "timestamp_inconsistencies": 0.01,
    "course_id_formatting": 0.005,
    "orphan_records": 0.001,
    "out_of_range_values": 0.001,
}

# Key fields that must NEVER be nulled under any circumstances (rules.md §10.1)
FORBIDDEN_NULL_KEYS: frozenset[str] = frozenset(
    {
        "student_id",
        "course_id",
        "semester_id",
        "session_id",
        "item_id",
        "week_start",
        "timestamp",
        "assigned_date",
        "due_date",
        "activity_type",
        "school",
    }
)


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _resolve_rng(
    run: GeneratorRun | None = None,
    rng: np.random.Generator | None = None,
) -> np.random.Generator:
    """Resolve the random generator to use, preferring run.child_rng."""
    if rng is not None:
        return rng
    if run is not None:
        return run.child_rng("data_quality_injection")
    return np.random.default_rng(42)


def get_injection_rates(
    run_or_configs: GeneratorRun | dict[str, Any] | None = None,
) -> dict[str, float]:
    """Retrieve validated injection rates from GeneratorRun or configuration dict.

    Falls back to DEFAULT_INJECTION_RATES for any unspecified key.
    """
    if run_or_configs is None:
        return dict(DEFAULT_INJECTION_RATES)

    if isinstance(run_or_configs, GeneratorRun):
        configs = run_or_configs.configs
    else:
        configs = run_or_configs

    gen = configs.get("generator", {})
    if "data_quality_injection" in gen:
        raw = gen["data_quality_injection"]
    elif "data_quality_injection" in configs:
        raw = configs["data_quality_injection"]
    else:
        raw = {}

    rates: dict[str, float] = {}
    for key in INJECTION_RATE_KEYS:
        val = raw.get(key, DEFAULT_INJECTION_RATES[key])
        _check(
            isinstance(val, (int, float)) and not isinstance(val, bool) and 0.0 <= val <= 1.0,
            f"Injection rate '{key}' must be a float in [0.0, 1.0], got {val!r}",
        )
        rates[key] = float(val)
    return rates


def _resolve_rates(
    run: GeneratorRun | None = None,
    rates: dict[str, float] | None = None,
) -> dict[str, float]:
    """Resolve injection rates by merging defaults/config with optional overrides."""
    base = get_injection_rates(run)
    if rates is not None:
        for key, val in rates.items():
            _check(
                isinstance(val, (int, float)) and not isinstance(val, bool) and 0.0 <= val <= 1.0,
                f"Injection rate '{key}' must be a float in [0.0, 1.0], got {val!r}",
            )
            base[key] = float(val)
    return base


@dataclass(frozen=True)
class InjectionReport:
    """Detailed record of exact injected data-quality issues (rules.md §10.2)."""

    seed: int
    rates: dict[str, float]
    issue_counts: dict[str, int]
    collection_counts: dict[str, dict[str, int]]
    total_injected: int
    timestamp: datetime

    @property
    def counts(self) -> dict[str, int]:
        """Convenient alias for issue_counts."""
        return self.issue_counts

    @property
    def per_dataset_counts(self) -> dict[str, dict[str, int]]:
        """Convenient alias for collection_counts."""
        return self.collection_counts

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return {
            "seed": self.seed,
            "timestamp": self.timestamp.isoformat(),
            "rates": dict(self.rates),
            "issue_counts": dict(self.issue_counts),
            "collection_counts": {k: dict(v) for k, v in self.collection_counts.items()},
            "total_injected": self.total_injected,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Duplicate LMS Events
# ─────────────────────────────────────────────────────────────────────────────


def inject_duplicate_lms_events(
    events: list[dict[str, Any]],
    rate: float = 0.01,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Inject duplicate LMS event records (rules.md §10, memory.md §12).

    Args:
        events: List of LMS event records.
        rate: Target duplicate rate (default 0.01, ~1%).
        rng: Optional NumPy random generator.
        min_injections: Minimum number of issues to force on small fixture datasets.

    Returns:
        Tuple of (new events list including duplicates, count of duplicates added).
    """
    _check(0.0 <= rate <= 1.0, f"Rate must be in [0, 1], got {rate}")
    if not events or (rate == 0.0 and min_injections == 0):
        return [copy.deepcopy(e) for e in events], 0

    if rng is None:
        rng = np.random.default_rng(42)

    k = int(len(events) * rate)
    if k == 0 and min_injections > 0:
        k = min(min_injections, len(events))

    if k <= 0:
        return [copy.deepcopy(e) for e in events], 0

    indices = rng.choice(len(events), size=k, replace=False)
    out = [copy.deepcopy(e) for e in events]
    for idx in indices:
        out.append(copy.deepcopy(events[idx]))

    return out, k


# ─────────────────────────────────────────────────────────────────────────────
# 2. Nulls in Non-Key Fields
# ─────────────────────────────────────────────────────────────────────────────


def inject_nulls_non_key(
    records: list[dict[str, Any]],
    collection: str,
    rate: float = 0.015,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Inject null values into selected non-key fields (rules.md §10.1).

    Key identifiers are strictly protected and never nulled.

    Args:
        records: List of records to perturb.
        collection: Collection name ('lms_events', 'coursework', 'academic_records').
        rate: Target null rate (default 0.015, ~1.5%).
        rng: Optional NumPy random generator.
        min_injections: Minimum number of issues to force on small fixtures.

    Returns:
        Tuple of (modified records, count of nulls injected).
    """
    _check(0.0 <= rate <= 1.0, f"Rate must be in [0, 1], got {rate}")
    if not records or (rate == 0.0 and min_injections == 0):
        return [copy.deepcopy(r) for r in records], 0

    if rng is None:
        rng = np.random.default_rng(42)

    out = [copy.deepcopy(r) for r in records]

    # Find candidates with eligible non-key fields currently not None
    candidates: list[tuple[int, list[str]]] = []
    for idx, r in enumerate(out):
        eligible: list[str] = []
        if collection == "lms_events":
            if r.get("duration_sec") is not None:
                eligible.append("duration_sec")
            if r.get("resource_id") is not None:
                eligible.append("resource_id")
        elif collection == "coursework":
            if r.get("status") != "MISSING" and r.get("score") is not None:
                eligible.append("score")
        elif collection == "academic_records":
            for f in ("internal_marks", "midterm_marks", "endterm_marks", "final_grade"):
                if r.get(f) is not None:
                    eligible.append(f)
        if eligible:
            candidates.append((idx, eligible))

    if not candidates:
        return out, 0

    k = int(len(candidates) * rate)
    if k == 0 and min_injections > 0:
        k = min(min_injections, len(candidates))

    if k <= 0:
        return out, 0

    chosen_indices = rng.choice(len(candidates), size=k, replace=False)
    injected_count = 0
    for c_idx in chosen_indices:
        rec_idx, fields = candidates[c_idx]
        target_field = str(rng.choice(fields))
        _check(target_field not in FORBIDDEN_NULL_KEYS, "Attempted to null key field")
        out[rec_idx][target_field] = None
        injected_count += 1

    return out, injected_count


# ─────────────────────────────────────────────────────────────────────────────
# 3. Timestamp Format Inconsistencies
# ─────────────────────────────────────────────────────────────────────────────


def inject_timestamp_inconsistencies(
    records: list[dict[str, Any]],
    collection: str,
    rate: float = 0.01,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Inject inconsistent timestamp string formats (rules.md §10, memory.md §12).

    Normal timestamps (datetime objects) are converted to non-standard string formats
    such as '%Y/%m/%d %H:%M:%S', '%d-%m-%Y %H:%M:%S', or '%Y-%m-%dT%H:%M:%SZ'.

    Args:
        records: List of records to perturb.
        collection: Collection name ('lms_events', 'coursework').
        rate: Target inconsistency rate (default 0.01, ~1%).
        rng: Optional NumPy random generator.
        min_injections: Minimum number of issues to force on small fixtures.

    Returns:
        Tuple of (modified records, count of timestamp issues injected).
    """
    _check(0.0 <= rate <= 1.0, f"Rate must be in [0, 1], got {rate}")
    if not records or (rate == 0.0 and min_injections == 0):
        return [copy.deepcopy(r) for r in records], 0

    if rng is None:
        rng = np.random.default_rng(42)

    out = [copy.deepcopy(r) for r in records]

    # Find candidates with a valid datetime timestamp
    candidates: list[tuple[int, str]] = []
    for idx, r in enumerate(out):
        if collection == "lms_events":
            if isinstance(r.get("timestamp"), datetime):
                candidates.append((idx, "timestamp"))
        elif collection == "coursework":
            if isinstance(r.get("submitted_at"), datetime):
                candidates.append((idx, "submitted_at"))

    if not candidates:
        return out, 0

    k = int(len(candidates) * rate)
    if k == 0 and min_injections > 0:
        k = min(min_injections, len(candidates))

    if k <= 0:
        return out, 0

    format_patterns = (
        "%Y/%m/%d %H:%M:%S",   # Slashes
        "%d-%m-%Y %H:%M:%S",   # Day first
        "%Y-%m-%d %H:%M:%S",   # Missing ISO 'T'
        "%Y-%m-%dT%H:%M:%SZ",  # ISO with trailing Z
    )

    chosen_indices = rng.choice(len(candidates), size=k, replace=False)
    injected_count = 0
    for c_idx in chosen_indices:
        rec_idx, field_name = candidates[c_idx]
        dt: datetime = out[rec_idx][field_name]
        chosen_fmt = str(rng.choice(format_patterns))
        out[rec_idx][field_name] = dt.strftime(chosen_fmt)
        injected_count += 1

    return out, injected_count


# ─────────────────────────────────────────────────────────────────────────────
# 4. Course ID Formatting (Casing and Whitespace)
# ─────────────────────────────────────────────────────────────────────────────


def inject_course_id_formatting(
    records: list[dict[str, Any]],
    collection: str,
    rate: float = 0.005,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Inject casing and whitespace anomalies into course_id (memory.md §12).

    Anomalies include lowercase ('cse101'), leading space (' CSE101'),
    trailing space ('CSE101 '), or mixed casing ('Cse101').

    Args:
        records: List of records containing course_id.
        collection: Collection name.
        rate: Target formatting anomaly rate (default 0.005, ~0.5%).
        rng: Optional NumPy random generator.
        min_injections: Minimum number of issues to force on small fixtures.

    Returns:
        Tuple of (modified records, count of formatting issues injected).
    """
    _check(0.0 <= rate <= 1.0, f"Rate must be in [0, 1], got {rate}")
    if not records or (rate == 0.0 and min_injections == 0):
        return [copy.deepcopy(r) for r in records], 0

    if rng is None:
        rng = np.random.default_rng(42)

    out = [copy.deepcopy(r) for r in records]

    # Find candidates with course_id
    candidates: list[int] = []
    for idx, r in enumerate(out):
        if collection == "lms_events":
            if isinstance(r.get("meta"), dict) and "course_id" in r["meta"]:
                candidates.append(idx)
        else:
            if "course_id" in r:
                candidates.append(idx)

    if not candidates:
        return out, 0

    k = int(len(candidates) * rate)
    if k == 0 and min_injections > 0:
        k = min(min_injections, len(candidates))

    if k <= 0:
        return out, 0

    chosen_indices = rng.choice(candidates, size=k, replace=False)
    anomalies = ("lower", "leading_space", "trailing_space", "both_spaces", "mixed")

    injected_count = 0
    for idx in chosen_indices:
        if collection == "lms_events":
            cid = str(out[idx]["meta"]["course_id"])
        else:
            cid = str(out[idx]["course_id"])

        anomaly = rng.choice(anomalies)
        if anomaly == "lower":
            new_cid = cid.lower()
        elif anomaly == "leading_space":
            new_cid = f" {cid}"
        elif anomaly == "trailing_space":
            new_cid = f"{cid} "
        elif anomaly == "both_spaces":
            new_cid = f" {cid.lower()} "
        else:
            new_cid = cid.capitalize()

        if collection == "lms_events":
            out[idx]["meta"]["course_id"] = new_cid
        else:
            out[idx]["course_id"] = new_cid
        injected_count += 1

    return out, injected_count


# ─────────────────────────────────────────────────────────────────────────────
# 5. Orphan Records
# ─────────────────────────────────────────────────────────────────────────────


def inject_orphan_records(
    records: list[dict[str, Any]],
    collection: str,
    rate: float = 0.001,
    rng: np.random.Generator | None = None,
    orphan_prefix: str = "STU999",
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Inject orphan records with non-existent student IDs (rules.md §10).

    Replaces student_id with synthetic identifiers outside the valid university range.

    Args:
        records: List of child records referencing student_id.
        collection: Collection name.
        rate: Target orphan rate (default 0.001, ~0.1%).
        rng: Optional NumPy random generator.
        orphan_prefix: Prefix ensuring ID is outside generated student population.
        min_injections: Minimum number of issues to force on small fixtures.

    Returns:
        Tuple of (modified records, count of orphan records injected).
    """
    _check(0.0 <= rate <= 1.0, f"Rate must be in [0, 1], got {rate}")
    if not records or (rate == 0.0 and min_injections == 0):
        return [copy.deepcopy(r) for r in records], 0

    if rng is None:
        rng = np.random.default_rng(42)

    out = [copy.deepcopy(r) for r in records]

    # Find candidates with student_id
    candidates: list[int] = []
    for idx, r in enumerate(out):
        if collection == "lms_events":
            if isinstance(r.get("meta"), dict) and "student_id" in r["meta"]:
                candidates.append(idx)
        else:
            if "student_id" in r:
                candidates.append(idx)

    if not candidates:
        return out, 0

    k = int(len(candidates) * rate)
    if k == 0 and min_injections > 0:
        k = min(min_injections, len(candidates))

    if k <= 0:
        return out, 0

    chosen_indices = rng.choice(candidates, size=k, replace=False)
    injected_count = 0
    for idx in chosen_indices:
        orphan_suffix = int(rng.integers(100, 999))
        orphan_id = f"{orphan_prefix}{orphan_suffix:03d}"
        if collection == "lms_events":
            out[idx]["meta"]["student_id"] = orphan_id
        else:
            out[idx]["student_id"] = orphan_id
        injected_count += 1

    return out, injected_count


# ─────────────────────────────────────────────────────────────────────────────
# 6. Out-of-Range Values
# ─────────────────────────────────────────────────────────────────────────────


def inject_out_of_range_values(
    records: list[dict[str, Any]],
    collection: str,
    rate: float = 0.001,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Inject domain out-of-range numerical values (memory.md §12).

    Examples:
    - lms_events: negative duration_sec (-120).
    - attendance: classes_attended > classes_conducted (attendance > 100%).
    - academic_records: marks < 0 or marks > 100.
    - coursework: score > max_score.

    Args:
        records: List of records to perturb.
        collection: Collection name.
        rate: Target out-of-range rate (default 0.001, ~0.1%).
        rng: Optional NumPy random generator.
        min_injections: Minimum number of issues to force on small fixtures.

    Returns:
        Tuple of (modified records, count of out-of-range values injected).
    """
    _check(0.0 <= rate <= 1.0, f"Rate must be in [0, 1], got {rate}")
    if not records or (rate == 0.0 and min_injections == 0):
        return [copy.deepcopy(r) for r in records], 0

    if rng is None:
        rng = np.random.default_rng(42)

    out = [copy.deepcopy(r) for r in records]

    # Find candidate records for the given collection
    candidates: list[int] = []
    for idx, r in enumerate(out):
        if collection == "lms_events":
            if r.get("duration_sec") is not None and r["duration_sec"] >= 0:
                candidates.append(idx)
        elif collection == "attendance":
            if r.get("classes_conducted", 0) > 0:
                candidates.append(idx)
        elif collection == "academic_records":
            candidates.append(idx)
        elif collection == "coursework":
            if r.get("score") is not None and r.get("status") != "MISSING":
                candidates.append(idx)

    if not candidates:
        return out, 0

    k = int(len(candidates) * rate)
    if k == 0 and min_injections > 0:
        k = min(min_injections, len(candidates))

    if k <= 0:
        return out, 0

    chosen_indices = rng.choice(candidates, size=k, replace=False)
    injected_count = 0

    for idx in chosen_indices:
        r = out[idx]
        if collection == "lms_events":
            # Negative duration
            r["duration_sec"] = -int(rng.integers(30, 600))
            injected_count += 1
        elif collection == "attendance":
            # Attended exceeds conducted
            conducted = r["classes_conducted"]
            r["classes_attended"] = conducted + int(rng.integers(2, 6))
            injected_count += 1
        elif collection == "academic_records":
            # Pick one marks field and make it either negative or > 100
            field = str(rng.choice(["internal_marks", "midterm_marks", "endterm_marks"]))
            if rng.random() < 0.5:
                r[field] = -int(rng.integers(5, 25))
            else:
                r[field] = int(rng.integers(105, 150))
            injected_count += 1
        elif collection == "coursework":
            # Score exceeds max_score
            max_s = r["max_score"]
            r["score"] = max_s + int(rng.integers(5, 25))
            injected_count += 1

    return out, injected_count


# ─────────────────────────────────────────────────────────────────────────────
# Collection-Level Injection Helpers
# ─────────────────────────────────────────────────────────────────────────────


def inject_quality_issues_lms_events(
    events: list[dict[str, Any]],
    run: GeneratorRun | None = None,
    rates: dict[str, float] | None = None,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Inject all applicable quality issues into an LMS events dataset/chunk."""
    r_rates = _resolve_rates(run, rates)
    r_rng = _resolve_rng(run, rng)

    counts: dict[str, int] = {}
    current = events

    # 1. Duplicates
    current, counts["duplicate_lms_events"] = inject_duplicate_lms_events(
        current, rate=r_rates["duplicate_lms_events"], rng=r_rng, min_injections=min_injections
    )
    # 2. Non-key nulls (duration, resource)
    current, counts["nulls_non_key"] = inject_nulls_non_key(
        current, "lms_events", rate=r_rates["nulls_non_key"], rng=r_rng, min_injections=min_injections
    )
    # 3. Timestamp inconsistencies
    current, counts["timestamp_inconsistencies"] = inject_timestamp_inconsistencies(
        current, "lms_events", rate=r_rates["timestamp_inconsistencies"], rng=r_rng, min_injections=min_injections
    )
    # 4. Course ID formatting
    current, counts["course_id_formatting"] = inject_course_id_formatting(
        current, "lms_events", rate=r_rates["course_id_formatting"], rng=r_rng, min_injections=min_injections
    )
    # 5. Orphan records
    current, counts["orphan_records"] = inject_orphan_records(
        current, "lms_events", rate=r_rates["orphan_records"], rng=r_rng, min_injections=min_injections
    )
    # 6. Out-of-range values (negative duration)
    current, counts["out_of_range_values"] = inject_out_of_range_values(
        current, "lms_events", rate=r_rates["out_of_range_values"], rng=r_rng, min_injections=min_injections
    )

    return current, counts


def inject_quality_issues_academic_records(
    records: list[dict[str, Any]],
    run: GeneratorRun | None = None,
    rates: dict[str, float] | None = None,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Inject quality issues into academic_records (nulls, formatting, orphans, ranges)."""
    r_rates = _resolve_rates(run, rates)
    r_rng = _resolve_rng(run, rng)

    counts: dict[str, int] = {}
    current = records

    current, counts["nulls_non_key"] = inject_nulls_non_key(
        current, "academic_records", rate=r_rates["nulls_non_key"], rng=r_rng, min_injections=min_injections
    )
    current, counts["course_id_formatting"] = inject_course_id_formatting(
        current, "academic_records", rate=r_rates["course_id_formatting"], rng=r_rng, min_injections=min_injections
    )
    current, counts["orphan_records"] = inject_orphan_records(
        current, "academic_records", rate=r_rates["orphan_records"], rng=r_rng, min_injections=min_injections
    )
    current, counts["out_of_range_values"] = inject_out_of_range_values(
        current, "academic_records", rate=r_rates["out_of_range_values"], rng=r_rng, min_injections=min_injections
    )

    return current, counts


def inject_quality_issues_attendance(
    attendance: list[dict[str, Any]],
    run: GeneratorRun | None = None,
    rates: dict[str, float] | None = None,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Inject quality issues into attendance records (formatting, orphans, ranges)."""
    r_rates = _resolve_rates(run, rates)
    r_rng = _resolve_rng(run, rng)

    counts: dict[str, int] = {}
    current = attendance

    current, counts["course_id_formatting"] = inject_course_id_formatting(
        current, "attendance", rate=r_rates["course_id_formatting"], rng=r_rng, min_injections=min_injections
    )
    current, counts["orphan_records"] = inject_orphan_records(
        current, "attendance", rate=r_rates["orphan_records"], rng=r_rng, min_injections=min_injections
    )
    current, counts["out_of_range_values"] = inject_out_of_range_values(
        current, "attendance", rate=r_rates["out_of_range_values"], rng=r_rng, min_injections=min_injections
    )

    return current, counts


def inject_quality_issues_coursework(
    coursework: list[dict[str, Any]],
    run: GeneratorRun | None = None,
    rates: dict[str, float] | None = None,
    rng: np.random.Generator | None = None,
    min_injections: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Inject quality issues into coursework (nulls, timestamps, formatting, orphans, ranges)."""
    r_rates = _resolve_rates(run, rates)
    r_rng = _resolve_rng(run, rng)

    counts: dict[str, int] = {}
    current = coursework

    current, counts["nulls_non_key"] = inject_nulls_non_key(
        current, "coursework", rate=r_rates["nulls_non_key"], rng=r_rng, min_injections=min_injections
    )
    current, counts["timestamp_inconsistencies"] = inject_timestamp_inconsistencies(
        current, "coursework", rate=r_rates["timestamp_inconsistencies"], rng=r_rng, min_injections=min_injections
    )
    current, counts["course_id_formatting"] = inject_course_id_formatting(
        current, "coursework", rate=r_rates["course_id_formatting"], rng=r_rng, min_injections=min_injections
    )
    current, counts["orphan_records"] = inject_orphan_records(
        current, "coursework", rate=r_rates["orphan_records"], rng=r_rng, min_injections=min_injections
    )
    current, counts["out_of_range_values"] = inject_out_of_range_values(
        current, "coursework", rate=r_rates["out_of_range_values"], rng=r_rng, min_injections=min_injections
    )

    return current, counts


# ─────────────────────────────────────────────────────────────────────────────
# Dataset-Wide Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


def inject_data_quality(
    run: GeneratorRun,
    *,
    lms_events: list[dict[str, Any]] | None = None,
    academic_records: list[dict[str, Any]] | None = None,
    attendance: list[dict[str, Any]] | None = None,
    coursework: list[dict[str, Any]] | None = None,
    rates: dict[str, float] | None = None,
    min_injections: int = 0,
) -> tuple[dict[str, list[dict[str, Any]]], InjectionReport]:
    """Inject controlled data-quality issues across all provided datasets (task 5.6).

    Applies the six approved categories at configured rates, records exact
    injected counts, and returns modified collections alongside an InjectionReport.

    Args:
        run: Seeded generator run providing RNG sub-stream and configuration.
        lms_events: Optional LMS event records.
        academic_records: Optional academic records.
        attendance: Optional attendance records.
        coursework: Optional coursework records.
        rates: Optional override dictionary of injection rates.
        min_injections: Optional minimum injected count per active category.

    Returns:
        Tuple of (dict of perturbed datasets, InjectionReport).
    """
    effective_rates = _resolve_rates(run, rates)
    rng = run.child_rng("data_quality_injection")

    result_datasets: dict[str, list[dict[str, Any]]] = {}
    collection_counts: dict[str, dict[str, int]] = {}
    total_issue_counts: dict[str, int] = {k: 0 for k in INJECTION_RATE_KEYS}

    if lms_events is not None:
        pert_lms, lms_c = inject_quality_issues_lms_events(
            lms_events, run=run, rates=effective_rates, rng=rng, min_injections=min_injections
        )
        result_datasets["lms_events"] = pert_lms
        collection_counts["lms_events"] = lms_c
        for k, v in lms_c.items():
            total_issue_counts[k] += v

    if academic_records is not None:
        pert_ar, ar_c = inject_quality_issues_academic_records(
            academic_records, run=run, rates=effective_rates, rng=rng, min_injections=min_injections
        )
        result_datasets["academic_records"] = pert_ar
        collection_counts["academic_records"] = ar_c
        for k, v in ar_c.items():
            total_issue_counts[k] += v

    if attendance is not None:
        pert_att, att_c = inject_quality_issues_attendance(
            attendance, run=run, rates=effective_rates, rng=rng, min_injections=min_injections
        )
        result_datasets["attendance"] = pert_att
        collection_counts["attendance"] = att_c
        for k, v in att_c.items():
            total_issue_counts[k] += v

    if coursework is not None:
        pert_cw, cw_c = inject_quality_issues_coursework(
            coursework, run=run, rates=effective_rates, rng=rng, min_injections=min_injections
        )
        result_datasets["coursework"] = pert_cw
        collection_counts["coursework"] = cw_c
        for k, v in cw_c.items():
            total_issue_counts[k] += v

    total_injected = sum(total_issue_counts.values())

    report = InjectionReport(
        seed=run.seed,
        rates=effective_rates,
        issue_counts=total_issue_counts,
        collection_counts=collection_counts,
        total_injected=total_injected,
        timestamp=datetime.now(timezone.utc),
    )

    return result_datasets, report
