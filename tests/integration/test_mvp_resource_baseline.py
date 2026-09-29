"""MVP resource/performance smoke test (Task 10.5, rules.md §34, memory.md §24).

Runs the development-scale vertical slice (generation + full Spark
pipeline J1→J7, parquet-only) on a tiny deterministic fixture and records
actual runtime and resource observations. This is a smoke baseline, not a
benchmark and not an optimization task: bounds asserted here are generous
anti-hang / sanity guards only.

Observed baseline (informational only, not asserted; Windows 11,
Python 3.11.9, PySpark local[2] / 1g driver, 12 students, seed 42,
measured 2026-09-29):

```text
Generation (12 students) ............ ~12s wall (66,587 LMS events, deterministic)
Spark pipeline J1→J7 ................ ~110-160s wall (run-to-run variance;
  e.g. J1=38.9s, J2=6.3s, J3=5.3s, J4=22.2s, J5=7.5s, J6=8.6s, J7=14.1s)
Total smoke run ..................... ~120-175s wall (incl. Spark startup)
Total disk (isolated data dir) ...... ~6.2 MB (deterministic)
Python RSS .......................... start=~120 MB, after_gen=~136 MB,
                                      after_pipe=~158 MB (Spark runs in JVM)
```

JVM heap is owned by the Spark driver/workers, not the Python process, so
Python RSS is reported alongside (not instead of) the configured Spark
driver memory. No large driver-side collect is used; all counts come from
in-memory run metadata and manifests.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

from acadexa.generator.orchestrator import generate_dataset
from acadexa.processing.pipeline import PipelineConfig, run_pipeline
from acadexa.processing.spark_session import SparkRuntimeConfig

SMOKE_SEED = 42
SMOKE_TARGET_STUDENTS = 12

# Generous smoke guards only (anti-hang / sanity, not performance targets).
MAX_SMOKE_WALL_SEC = 1800.0
MAX_SMOKE_DISK_BYTES = 2_000_000_000


def _rss_mb() -> float | None:
    """Return current Python process RSS in MB, or None if unmeasurable."""
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None


def _dir_size_bytes(path: Path) -> int:
    """Sum file sizes under ``path`` (0 when the path does not exist)."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _build_smoke_pipeline_config(data_dir: Path) -> PipelineConfig:
    """Isolated parquet-only pipeline config rooted at ``data_dir``."""
    return PipelineConfig(
        data_dir=data_dir,
        raw_data_dir=data_dir / "generated",
        raw_lms_parquet_path=data_dir / "raw" / "lms_events",
        cleaned_data_dir=data_dir / "cleaned",
        processed_data_dir=data_dir / "processed",
        gold_data_dir=data_dir / "gold",
        manifests_dir=data_dir / "manifests",
        analytics_dir=data_dir / "analytics",
        generation_manifest_path=data_dir / "manifests" / "generation_manifest.json",
        injection_manifest_path=data_dir / "manifests" / "injection_manifest.json",
        pipeline_manifest_path=data_dir / "manifests" / "pipeline_run_manifest.json",
        publish_to_mongo=False,
        save_parquet=True,
        validate_gold=True,
        fail_on_validation_error=True,
        seed=SMOKE_SEED,
        run_id="mvp_10_5_resource_smoke",
        spark_runtime_config=SparkRuntimeConfig(
            app_name="AcadexaMVP10_5Smoke",
            master="local[2]",
            driver_memory="1g",
            shuffle_partitions=2,
            default_parallelism=2,
            ui_enabled=False,
        ),
    )


def test_mvp_resource_smoke_baseline(tmp_path: Path, capsys) -> None:
    """Run the dev-scale slice and record runtime/resource observations."""
    smoke_start = time.perf_counter()
    rss_start = _rss_mb()

    # --- Phase 1: Generation ---
    gen_start = time.perf_counter()
    gen_result = generate_dataset(
        seed=SMOKE_SEED,
        target_students=SMOKE_TARGET_STUDENTS,
        data_dir=tmp_path,
        chunk_size=500,
        min_injections=1,
    )
    gen_duration = time.perf_counter() - gen_start
    rss_after_gen = _rss_mb()

    assert gen_result.actual_counts["students"] == SMOKE_TARGET_STUDENTS
    assert gen_result.actual_counts["lms_events"] > 0

    # --- Phase 2: Spark pipeline J1 → J7 ---
    pipe_start = time.perf_counter()
    pipe_result = run_pipeline(_build_smoke_pipeline_config(tmp_path))
    pipe_duration = time.perf_counter() - pipe_start
    rss_after_pipe = _rss_mb()

    assert pipe_result.success is True
    assert pipe_result.metadata.status == "SUCCESS"
    for stage_id in ("J1", "J2", "J3", "J4", "J5", "J6", "J7"):
        assert pipe_result.metadata.stage_outcomes[stage_id].status == "SUCCESS"
    for gold_key in (
        "gold_student_features",
        "gold_course_metrics",
        "gold_school_summary",
        "gold_risk_indicators",
    ):
        assert pipe_result.metadata.output_counts.get(gold_key, 0) > 0

    # --- Phase 3: Observations (measure, do not optimize) ---
    stage_durations = {
        sid: round(outcome.duration_sec, 2)
        for sid, outcome in pipe_result.metadata.stage_outcomes.items()
    }
    disk_usage = {
        name: _dir_size_bytes(tmp_path / name)
        for name in ("generated", "raw", "cleaned", "processed", "gold", "manifests", "analytics")
    }
    total_disk = sum(disk_usage.values())
    total_wall = time.perf_counter() - smoke_start

    try:
        psutil_version: str | None = __import__("psutil").__version__
    except Exception:
        psutil_version = None

    report = {
        "report_version": "1.0.0",
        "report_type": "mvp_resource_smoke_baseline",
        "note": "Smoke baseline only: generous sanity observations, not a benchmark.",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "spark_master": "local[2]",
            "spark_driver_memory": "1g",
            "psutil": psutil_version,
        },
        "configuration": {
            "target_students": SMOKE_TARGET_STUDENTS,
            "seed": SMOKE_SEED,
            "publish_to_mongo": False,
        },
        "generation": {
            "duration_sec": round(gen_duration, 2),
            "actual_counts": dict(gen_result.actual_counts),
        },
        "pipeline": {
            "wall_duration_sec": round(pipe_duration, 2),
            "manifest_duration_sec": round(pipe_result.metadata.duration_sec, 2),
            "stage_durations_sec": stage_durations,
            "output_counts": dict(pipe_result.metadata.output_counts),
        },
        "memory_observations_mb": {
            "python_rss_start": rss_start,
            "python_rss_after_generation": rss_after_gen,
            "python_rss_after_pipeline": rss_after_pipe,
            "comment": (
                "Python RSS only; Spark executes in JVM driver/workers "
                "under the configured driver memory."
            ),
        },
        "disk_usage_bytes": {**disk_usage, "total": total_disk},
        "total_wall_sec": round(total_wall, 2),
    }
    report_path = tmp_path / "mvp_resource_baseline.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with capsys.disabled():
        print("\n[MVP 10.5 resource smoke baseline]")
        print(f"  Generation: {gen_duration:.1f}s ({gen_result.actual_counts['lms_events']} LMS events)")
        print(f"  Pipeline:   {pipe_duration:.1f}s " + ", ".join(
            f"{sid}={stage_durations[sid]:.1f}s" for sid in ("J1", "J2", "J3", "J4", "J5", "J6", "J7")
        ))
        print(f"  Disk total: {total_disk / (1024 * 1024):.1f} MB | Wall total: {total_wall:.1f}s")
        print(f"  Python RSS: start={rss_start} MB after_gen={rss_after_gen} MB after_pipe={rss_after_pipe} MB")
        print(f"  Report: {report_path}")

    # --- Smoke guards (generous; anti-hang / sanity only) ---
    assert report_path.exists()
    assert total_wall < MAX_SMOKE_WALL_SEC
    assert total_disk > 0
    assert total_disk < MAX_SMOKE_DISK_BYTES
