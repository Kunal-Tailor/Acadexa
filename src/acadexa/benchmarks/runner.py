"""J8 benchmark harness (Task 13.1, rules.md §18, §30, architecture.md §20).

Repeatable workload definitions, engine-agnostic timing and run metadata
for comparing the same workload across pandas, MongoDB aggregation and
PySpark. Engine implementations live in ``pandas/``, ``mongodb/`` and
``spark/`` subpackages (added per task); formatted result publication
belongs to Task 13.6 — this module saves only the raw run manifest.

Benchmark rules honored here: results are measured, never manufactured;
each result records dataset size, workload, environment, execution time
and memory where practical so measurements stay interpretable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import platform
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

BENCHMARK_MANIFEST_VERSION: str = "1.0.0"
DEFAULT_BENCHMARK_MANIFEST_PATH: Path = Path("reports/benchmarks/benchmark_run_manifest.json")

ENGINE_PANDAS: str = "pandas"
ENGINE_MONGODB: str = "mongodb"
ENGINE_PYSPARK: str = "pyspark"


@dataclass(frozen=True)
class WorkloadDefinition:
    """Repeatable definition of one benchmark workload (engine-agnostic)."""

    workload_id: str
    title: str
    description: str
    input_description: str
    output_grain: str
    metrics: tuple[str, ...]


WORKLOADS: dict[str, WorkloadDefinition] = {
    "weekly_lms_engagement": WorkloadDefinition(
        workload_id="weekly_lms_engagement",
        title="Weekly LMS engagement aggregation",
        description=(
            "Aggregate event-level LMS data into weekly student-course "
            "engagement summaries: total events, positive-only durations, "
            "distinct active days, approved activity-category roll-ups and "
            "per-type breakdowns (same task as Spark J2)."
        ),
        input_description="LMS event records with timestamp, student/course/school identifiers, activity_type and duration_sec",
        output_grain="student_id × course_id × school × semester_id × week_start × week_number",
        metrics=(
            "total_events",
            "total_duration_sec",
            "active_days",
            "content_views",
            "assessment_events",
            "participation_events",
            "access_events",
            "video_views",
            "quiz_attempts",
            "assignment_views",
            "assignment_submissions",
            "forum_posts",
            "logins",
        ),
    ),
}


def get_workload(workload_id: str) -> WorkloadDefinition:
    """Return the registered workload definition (KeyError when unknown)."""
    try:
        return WORKLOADS[workload_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown benchmark workload {workload_id!r}; "
            f"registered: {sorted(WORKLOADS)}"
        ) from exc


def capture_environment(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Capture interpreter/platform/package context for a benchmark run."""
    env: dict[str, Any] = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }
    for package in ("pandas", "pyspark", "pymongo", "pyarrow", "numpy"):
        try:
            module = __import__(package)
            env[f"{package}_version"] = getattr(module, "__version__", "unknown")
        except ImportError:
            env[f"{package}_version"] = "not_installed"
    if extra:
        env.update(extra)
    return env


@dataclass
class BenchmarkResult:
    """Measured outcome of one engine running one workload."""

    workload_id: str
    engine: str
    duration_sec: float
    input_rows: int
    output_rows: int
    peak_memory_mb: float | None = None
    success: bool = True
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a JSON-serializable dictionary."""
        return {
            "workload_id": self.workload_id,
            "engine": self.engine,
            "duration_sec": round(self.duration_sec, 3),
            "input_rows": self.input_rows,
            "output_rows": self.output_rows,
            "peak_memory_mb": self.peak_memory_mb,
            "success": self.success,
            "error": self.error,
            "extra": self.extra,
        }


@dataclass
class BenchmarkRun:
    """Run metadata plus per-engine results for one benchmark invocation."""

    run_id: str
    started_at: str
    manifest_version: str = BENCHMARK_MANIFEST_VERSION
    ended_at: str | None = None
    duration_sec: float = 0.0
    environment: dict[str, Any] = field(default_factory=dict)
    results: list[BenchmarkResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the run manifest to a JSON-serializable dictionary."""
        return {
            "manifest_version": self.manifest_version,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_sec": round(self.duration_sec, 3),
            "environment": self.environment,
            "results": [r.to_dict() for r in self.results],
        }

    def save(self, path: str | Path) -> Path:
        """Save the run manifest to disk as JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        logger.info("Saved benchmark run manifest to %s", target)
        return target

    @classmethod
    def load(cls, path: str | Path) -> BenchmarkRun:
        """Load a run manifest back from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            run_id=data["run_id"],
            started_at=data["started_at"],
            manifest_version=data.get("manifest_version", BENCHMARK_MANIFEST_VERSION),
            ended_at=data.get("ended_at"),
            duration_sec=float(data.get("duration_sec", 0.0)),
            environment=dict(data.get("environment", {})),
            results=[BenchmarkResult(**r) for r in data.get("results", [])],
        )


def run_timed(
    func: Callable[..., Any],
    *args: Any,
    measure_memory: bool = True,
    **kwargs: Any,
) -> tuple[Any, float, float | None]:
    """Execute ``func`` measuring wall time and optional peak memory.

    Memory is the tracemalloc Python-allocator peak in MiB (None when
    measurement is disabled); native allocations outside the Python
    allocator may not be captured, which callers must not overstate.

    Returns:
        ``(return_value, duration_sec, peak_memory_mb)``.
    """
    if measure_memory:
        tracemalloc.start()
    start = time.perf_counter()
    try:
        value = func(*args, **kwargs)
    finally:
        duration = time.perf_counter() - start
        peak_mb: float | None = None
        if measure_memory:
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_mb = round(peak_bytes / (1024 * 1024), 3)
    return value, duration, peak_mb


def run_benchmark(
    workload_id: str,
    engine: str,
    func: Callable[..., tuple[int, int]],
    *args: Any,
    measure_memory: bool = True,
    extra: dict[str, Any] | None = None,
    **kwargs: Any,
) -> BenchmarkResult:
    """Run one engine workload function and record the measured result.

    The engine function must return ``(input_rows, output_rows)``; any
    exception is recorded as an unsuccessful result (never raised), since
    a failed engine is itself a benchmark observation.
    """
    get_workload(workload_id)  # fail fast on unknown workload ids
    start = time.perf_counter()
    try:
        (input_rows, output_rows), duration, peak_mb = run_timed(
            func, *args, measure_memory=measure_memory, **kwargs
        )
        return BenchmarkResult(
            workload_id=workload_id,
            engine=engine,
            duration_sec=duration,
            input_rows=int(input_rows),
            output_rows=int(output_rows),
            peak_memory_mb=peak_mb,
            success=True,
            extra=dict(extra or {}),
        )
    except Exception as exc:
        logger.warning("Benchmark %s/%s failed: %s", workload_id, engine, exc)
        return BenchmarkResult(
            workload_id=workload_id,
            engine=engine,
            duration_sec=time.perf_counter() - start,
            input_rows=0,
            output_rows=0,
            peak_memory_mb=None,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
            extra=dict(extra or {}),
        )


def new_run_id(prefix: str = "bench") -> str:
    """Generate a timestamped benchmark run identifier."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}"
