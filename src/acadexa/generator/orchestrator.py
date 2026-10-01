"""Development and production dataset generation orchestrator (task 5.8, F-B09, rules.md §8, §10).

Single entry point and high-level workflow orchestrator that ties together:
1. Seeded configuration resolution & scaling (foundation.py)
2. University hierarchy & catalog generation (university.py, courses.py)
3. Student cohort generation (students.py)
4. Synthetic decliner population assignment (decliners.py)
5. Ground-truth registry creation (ground_truth.py)
6. Latent behavioral traits generation (behavioral_model.py)
7. Academic records generation (academic_records.py)
8. Weekly attendance generation (attendance.py)
9. Coursework items & student marks generation (coursework.py)
10. Chunked LMS event generation into Parquet (lms_events.py)
11. Controlled data-quality injection across collections (quality_injection.py)
12. Generation and injection manifests (manifests.py)

Architecture & Rules:
- Rules.md §8: Clean configuration, deterministic seeded randomness, low memory footprint.
- Rules.md §8.4: Chunked LMS generation into Parquet directly.
- Rules.md §9: Ground truth established before analytics observation.
- Rules.md §10.2: Exact injected issue counts recorded in manifests.
- Folder structure §20-§25: Parquet landing in data/raw/lms_events, core collections
  in data/generated/, metadata in data/manifests/.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Iterator

import numpy as np

from acadexa.config import validate_project_config
from acadexa.generator.academic_records import generate_academic_records
from acadexa.generator.attendance import generate_attendance
from acadexa.generator.behavioral_model import generate_behavioral_traits
from acadexa.generator.courses import assign_course_difficulty
from acadexa.generator.coursework import generate_coursework
from acadexa.generator.decliners import generate_decliner_flags
from acadexa.generator.foundation import GeneratorError, GeneratorRun, _check, _jsonable
from acadexa.generator.ground_truth import (
    DEFAULT_GROUND_TRUTH_PATH,
    GroundTruthRegistry,
    generate_ground_truth_registry,
)
from acadexa.generator.lms_events import (
    DEFAULT_LMS_PARQUET_PATH,
    generate_lms_events_chunks,
    write_lms_events_to_parquet,
)
from acadexa.generator.manifests import (
    DEFAULT_GENERATION_MANIFEST_PATH,
    DEFAULT_INJECTION_MANIFEST_PATH,
    GenerationManifest,
    InjectionManifest,
    build_manifests,
)
from acadexa.generator.quality_injection import (
    DEFAULT_INJECTION_RATES,
    INJECTION_RATE_KEYS,
    InjectionReport,
    _resolve_rates,
    inject_quality_issues_academic_records,
    inject_quality_issues_attendance,
    inject_quality_issues_coursework,
    inject_quality_issues_lms_events,
)
from acadexa.generator.students import generate_students
from acadexa.generator.university import generate_university_hierarchy


@dataclass(frozen=True)
class GenerationResult:
    """Detailed result of an orchestrated synthetic dataset generation run."""

    run: GeneratorRun
    actual_counts: dict[str, int]
    output_files: dict[str, Path]
    ground_truth_registry: GroundTruthRegistry
    generation_manifest: GenerationManifest
    injection_manifest: InjectionManifest | None
    duration_sec: float
    disk_usage_bytes: dict[str, int]


def _compute_disk_usage(path: Path) -> int:
    """Compute file or directory total size in bytes."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def configure_run_for_scale(
    configs: dict[str, Any] | None = None,
    *,
    seed: int | None = None,
    target_students: int | None = None,
) -> GeneratorRun:
    """Prepare a GeneratorRun scaled appropriately for development or full scale.

    Args:
        configs: Optional base project configuration dictionary. When omitted,
            clean validated configuration is loaded.
        seed: Optional seed override.
        target_students: Optional target student count override. When provided,
            scales school_population proportionally across all configured schools.

    Returns:
        Configured GeneratorRun instance.
    """
    if configs is None:
        configs = copy.deepcopy(validate_project_config())
    else:
        configs = copy.deepcopy(configs)

    if seed is not None:
        configs["generator"]["generator"]["seed"] = int(seed)

    if target_students is not None:
        _check(
            isinstance(target_students, int) and target_students > 0,
            f"target_students must be a positive integer, got {target_students!r}",
        )
        scale = configs["generator"]["scale"]
        school_pop = scale["school_population"]
        n_schools = len(school_pop)
        per_school = max(1, target_students // n_schools)
        remainder = target_students % n_schools

        new_pop: dict[str, int] = {}
        for idx, school_key in enumerate(school_pop.keys()):
            new_pop[school_key] = per_school + (1 if idx < remainder else 0)

        scale["school_population"] = new_pop
        actual_total = sum(new_pop.values())
        scale["target_students"] = actual_total

    return GeneratorRun(configs)


def generate_dataset(
    *,
    run: GeneratorRun | None = None,
    configs: dict[str, Any] | None = None,
    seed: int | None = None,
    target_students: int | None = 36,
    data_dir: str | Path = "data",
    lms_parquet_path: str | Path | None = None,
    chunk_size: int = 1000,
    inject_issues: bool = True,
    injection_rates: dict[str, float] | None = None,
    min_injections: int = 1,
    save_manifests: bool = True,
    save_core_collections: bool = True,
    save_lms_parquet: bool = True,
    generate_lms_events: bool = True,
) -> GenerationResult:
    """Generate a complete synthetic dataset and write all artifacts (task 5.8).

    Orchestrates the entire generation pipeline:
    - University hierarchy & difficulty-tagged courses
    - Student cohort & decliners
    - Ground-truth registry
    - Behavioral traits, academic records, attendance, coursework
    - Chunked LMS events streamed directly into Parquet
    - Controlled data-quality injection (duplicates, non-key nulls,
      timestamp formatting, course ID formatting, orphans, out-of-range)
    - Generation and injection manifests

    Args:
        run: Optional existing GeneratorRun. When omitted, initialized using
            `configs`, `seed`, and `target_students`.
        configs: Optional project configuration. Defaults to validate_project_config().
        seed: Optional integer seed override.
        target_students: Target student cohort size (default 36 for development scale).
            Pass None to preserve config scale (e.g. 12,000 for full-scale).
        data_dir: Base directory for output datasets (default "data").
        lms_parquet_path: Path for LMS Parquet output. Defaults to data_dir/raw/lms_events.
        chunk_size: LMS event chunk size for streaming (default 1000).
        inject_issues: Whether to inject controlled data-quality issues (default True).
        injection_rates: Optional dictionary of rate overrides for injection.
        min_injections: Minimum injections per category (default 1 for dev scale).
        save_manifests: Whether to save manifests to data_dir/manifests/ (default True).
        save_core_collections: Whether to save students, courses, records, etc.
            to data_dir/generated/ (default True).
        save_lms_parquet: Whether to write LMS events to Parquet (default True).
        generate_lms_events: Whether to generate LMS events at all (default
            True). When False, the LMS event stream is skipped entirely
            (staged full-scale generation runs core collections first and
            generates the event stream in a later task).

    Returns:
        GenerationResult containing generated collections, counts, manifests, and file paths.
    """
    start_time = time.perf_counter()

    base_dir = Path(data_dir)
    generated_dir = base_dir / "generated"
    manifests_dir = base_dir / "manifests"
    raw_dir = base_dir / "raw"

    if lms_parquet_path is None:
        target_lms_path = raw_dir / "lms_events"
    else:
        target_lms_path = Path(lms_parquet_path)

    # 1. Initialize or configure GeneratorRun
    if run is None:
        run = configure_run_for_scale(configs, seed=seed, target_students=target_students)

    # 2. Hierarchy and Courses
    hierarchy = generate_university_hierarchy(run.configs)
    diff_map = assign_course_difficulty(run, hierarchy.courses)
    courses: list[dict[str, Any]] = []
    for c in hierarchy.courses:
        merged = dict(c)
        merged.update(diff_map[c["course_id"]])
        courses.append(merged)

    # 3. Students & Decliners
    students = generate_students(run)
    decliner_flags = generate_decliner_flags(run, students)

    # 4. Ground-Truth Registry (Rules §9: established before analytical observation)
    ground_truth_registry = generate_ground_truth_registry(
        run, students=students, decliner_flags=decliner_flags
    )
    gt_path = manifests_dir / "ground_truth_registry.json"
    if save_manifests:
        ground_truth_registry.save(gt_path)

    # 5. Academic Records, Attendance & Coursework
    academic_records = generate_academic_records(run, students=students)
    attendance = generate_attendance(run, students=students, records=academic_records)
    coursework = generate_coursework(run, students=students, records=academic_records)

    # 7. Quality Injection & Streaming
    clean_records = academic_records
    clean_coursework = coursework

    # 7. Quality Injection & Streaming
    effective_rates = _resolve_rates(run, injection_rates)
    q_rng = run.child_rng("data_quality_injection")

    collection_issue_counts: dict[str, dict[str, int]] = {k: {} for k in (
        "academic_records", "attendance", "coursework", "lms_events"
    )}

    if inject_issues:
        academic_records, ar_counts = inject_quality_issues_academic_records(
            academic_records,
            run=run,
            rates=effective_rates,
            rng=q_rng,
            min_injections=min_injections,
        )
        collection_issue_counts["academic_records"] = ar_counts

        attendance, att_counts = inject_quality_issues_attendance(
            attendance,
            run=run,
            rates=effective_rates,
            rng=q_rng,
            min_injections=min_injections,
        )
        collection_issue_counts["attendance"] = att_counts

        coursework, cw_counts = inject_quality_issues_coursework(
            coursework,
            run=run,
            rates=effective_rates,
            rng=q_rng,
            min_injections=min_injections,
        )
        collection_issue_counts["coursework"] = cw_counts

    # 8. LMS Events Generation with Streaming Injection
    lms_issue_counts: dict[str, int] = {k: 0 for k in INJECTION_RATE_KEYS}
    lms_events_count = 0

    if generate_lms_events:
        def _stream_lms_chunks() -> Iterator[list[dict[str, Any]]]:
            first_chunk = True
            for chunk in generate_lms_events_chunks(
                run,
                students=students,
                records=clean_records,
                coursework=clean_coursework,
                chunk_size=chunk_size,
            ):
                if inject_issues:
                    # Apply min_injections on first chunk only, then pure probability
                    chunk_min = min_injections if first_chunk else 0
                    perturbed, c_counts = inject_quality_issues_lms_events(
                        chunk,
                        run=run,
                        rates=effective_rates,
                        rng=q_rng,
                        min_injections=chunk_min,
                    )
                    for k, v in c_counts.items():
                        lms_issue_counts[k] += v
                    first_chunk = False
                    yield perturbed
                else:
                    yield chunk

        if save_lms_parquet:
            lms_events_count = write_lms_events_to_parquet(
                output_path=target_lms_path,
                run=run,
                chunks=_stream_lms_chunks(),
                chunk_size=chunk_size,
                overwrite=True,
            )
        else:
            # Just consume chunks to count and perturb
            for chunk in _stream_lms_chunks():
                lms_events_count += len(chunk)

    if inject_issues:
        collection_issue_counts["lms_events"] = lms_issue_counts

    # 9. Build Injection Report
    injection_report: InjectionReport | None = None
    if inject_issues:
        total_counts: dict[str, int] = {k: 0 for k in INJECTION_RATE_KEYS}
        for sub in collection_issue_counts.values():
            for k, v in sub.items():
                total_counts[k] += v

        total_injected = sum(total_counts.values())
        injection_report = InjectionReport(
            seed=run.seed,
            rates=effective_rates,
            issue_counts=total_counts,
            collection_counts=collection_issue_counts,
            total_injected=total_injected,
            timestamp=datetime.now(timezone.utc),
        )

    # 10. Save Core Collections
    output_files: dict[str, Path] = {}
    if save_core_collections:
        generated_dir.mkdir(parents=True, exist_ok=True)
        collections_to_save = {
            "students": students,
            "courses": courses,
            "academic_records": academic_records,
            "attendance": attendance,
            "coursework": coursework,
        }
        for name, data in collections_to_save.items():
            path = generated_dir / f"{name}.json"
            content = json.dumps(_jsonable(data), indent=2, ensure_ascii=False)
            path.write_text(content, encoding="utf-8")
            output_files[name] = path

    if save_lms_parquet:
        output_files["lms_events"] = target_lms_path
    if save_manifests:
        output_files["ground_truth_registry"] = gt_path

    # 11. Actual counts
    actual_counts = {
        "students": len(students),
        "courses": len(courses),
        "academic_records": len(academic_records),
        "attendance": len(attendance),
        "coursework": len(coursework),
        "lms_events": lms_events_count,
    }

    # 12. Disk usage
    disk_usage: dict[str, int] = {}
    for name, p in output_files.items():
        disk_usage[name] = _compute_disk_usage(p)

    duration_sec = round(time.perf_counter() - start_time, 2)

    # 13. Build and Save Manifests
    gen_manifest_path = manifests_dir / "generation_manifest.json"
    inj_manifest_path = manifests_dir / "injection_manifest.json"

    # target_students=None preserves config scale (full target), so only an
    # explicit small override counts as a development-scale run.
    scale_label = (
        "development"
        if target_students is not None and target_students < 1000
        else "full"
    )
    gen_manifest, inj_manifest = build_manifests(
        run=run,
        actual_counts=actual_counts,
        injection_report=injection_report,
        generation_duration_sec=duration_sec,
        disk_usage_bytes=disk_usage,
        output_files={k: str(v) for k, v in output_files.items()},
        generation_metadata={"scale": scale_label},
        injection_metadata={"scale": scale_label},
        save=save_manifests,
        generation_manifest_path=gen_manifest_path,
        injection_manifest_path=inj_manifest_path,
    )

    if save_manifests:
        output_files["generation_manifest"] = gen_manifest_path
        if inj_manifest is not None:
            output_files["injection_manifest"] = inj_manifest_path

    return GenerationResult(
        run=run,
        actual_counts=actual_counts,
        output_files=output_files,
        ground_truth_registry=ground_truth_registry,
        generation_manifest=gen_manifest,
        injection_manifest=inj_manifest,
        duration_sec=duration_sec,
        disk_usage_bytes=disk_usage,
    )
