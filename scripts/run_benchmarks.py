"""Entry point: run the J8 benchmark suite (Phase 13, rules.md §18, §30).

Executes registered benchmark workloads per engine, records measured
timing/memory/dataset metadata to a run manifest, publishes the measured
benchmark report (JSON + Markdown, no conclusions), and prints a summary.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure src/ is on sys.path when invoked directly as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from acadexa.benchmarks.runner import (
    DEFAULT_BENCHMARK_MANIFEST_PATH,
    ENGINE_MONGODB,
    ENGINE_PANDAS,
    ENGINE_PYSPARK,
    WORKLOADS,
    BenchmarkRun,
    capture_environment,
    new_run_id,
)
from acadexa.benchmarks.pandas import (
    run_feature_table_join_pandas,
    run_weekly_engagement_pandas,
)
from acadexa.benchmarks.mongodb import (
    run_feature_table_join_mongodb,
    run_weekly_engagement_mongodb,
)
from acadexa.benchmarks.spark import (
    run_feature_table_join_spark,
    run_weekly_engagement_spark,
)
from acadexa.benchmarks.report import build_benchmark_report, save_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Acadexa J8 Benchmark Runner (measured results only)"
    )
    parser.add_argument(
        "--workload",
        type=str,
        default="weekly_lms_engagement",
        choices=sorted(WORKLOADS),
        help="Registered workload to execute (default: 'weekly_lms_engagement')",
    )
    parser.add_argument(
        "--engine",
        type=str,
        default=ENGINE_PANDAS,
        choices=[ENGINE_PANDAS, ENGINE_MONGODB, ENGINE_PYSPARK],
        help="Engine implementation to run (default: 'pandas')",
    )
    parser.add_argument(
        "--input-path",
        type=str,
        default="data/raw/lms_events",
        help="Workload input path: Parquet directory (pandas/Spark) "
        "(default: 'data/raw/lms_events')",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="lms_events",
        help="MongoDB collection for the MongoDB engine (default: 'lms_events')",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=None,
        help="Spark engine Parquet output directory (default: temporary directory)",
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default="data/processed",
        help="Base directory of cleaned domain datasets for the "
        "feature-table join pandas/Spark engines (default: 'data/processed')",
    )
    parser.add_argument(
        "--manifest-path",
        type=str,
        default=str(DEFAULT_BENCHMARK_MANIFEST_PATH),
        help="Path for saving the raw run manifest JSON",
    )
    parser.add_argument(
        "--no-measure-memory",
        action="store_true",
        help="Disable tracemalloc peak-memory measurement",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing the formatted benchmark report files",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Regenerate report files from an existing manifest without running",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress console output summary",
    )
    return parser.parse_args(argv)


def print_summary(run: BenchmarkRun) -> None:
    """Print a human-readable summary of the benchmark run."""
    print("=" * 66)
    print(" Acadexa J8 Benchmark Run (measured results, no conclusions)")
    print("=" * 66)
    print(f"Run ID:   {run.run_id}")
    print(f"Duration: {run.duration_sec}s")
    print("-" * 66)
    for res in run.results:
        status = "SUCCESS" if res.success else f"FAILED: {res.error}"
        mem = f"{res.peak_memory_mb} MB" if res.peak_memory_mb is not None else "n/a"
        print(f"  - {res.workload_id} [{res.engine}]: {status}")
        print(
            f"    {res.duration_sec}s | in={res.input_rows} out={res.output_rows} "
            f"| peak_mem={mem}"
        )
    print("-" * 66)
    print("Environment:")
    for key, value in run.environment.items():
        print(f"  - {key}: {value}")
    print("=" * 66)


def _scratch_output_dir(prefix: str) -> tuple[str, bool]:
    """Create a temporary Spark output directory (caller cleans up)."""
    return tempfile.mkdtemp(prefix=prefix), True


def _run_spark_with_cleanup(func, output_arg: str | None, prefix: str, *args):
    """Run a Spark engine function with temporary output handling."""
    output_path = output_arg
    cleanup_output = False
    if output_path is None:
        output_path, cleanup_output = _scratch_output_dir(prefix)
    try:
        return func(*args, output_path)
    finally:
        if cleanup_output:
            shutil.rmtree(output_path, ignore_errors=True)


def _execute_workload(args: argparse.Namespace):
    """Dispatch one workload/engine combination (Tasks 13.2–13.5)."""
    measure = not args.no_measure_memory
    if args.workload == "weekly_lms_engagement" and args.engine == ENGINE_PANDAS:
        return run_weekly_engagement_pandas(args.input_path, measure_memory=measure)
    if args.workload == "weekly_lms_engagement" and args.engine == ENGINE_MONGODB:
        return run_weekly_engagement_mongodb(
            collection=args.collection, measure_memory=measure
        )
    if args.workload == "weekly_lms_engagement" and args.engine == ENGINE_PYSPARK:
        return _run_spark_with_cleanup(
            run_weekly_engagement_spark,
            args.output_path,
            "acadexa_bench_spark_",
            args.input_path,
        )
    if args.workload == "feature_table_join" and args.engine == ENGINE_PANDAS:
        return run_feature_table_join_pandas(args.base_path, measure_memory=measure)
    if args.workload == "feature_table_join" and args.engine == ENGINE_MONGODB:
        return run_feature_table_join_mongodb(measure_memory=measure)
    if args.workload == "feature_table_join" and args.engine == ENGINE_PYSPARK:
        return _run_spark_with_cleanup(
            run_feature_table_join_spark,
            args.output_path,
            "acadexa_bench_join_",
            args.base_path,
        )
    return None


def _publish_outputs(run: BenchmarkRun, manifest_path: str, quiet: bool) -> None:
    """Save the raw manifest plus the formatted benchmark report (Task 13.6)."""
    run.save(manifest_path)
    report = build_benchmark_report(run)
    json_path, md_path = save_report(report, manifest_path)
    if not quiet:
        print_summary(run)
        print(f"Benchmark report: {json_path} and {md_path}")


def main(argv: list[str] | None = None) -> int:
    """Main script entry point for running benchmarks."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.report_only:
        run = BenchmarkRun.load(args.manifest_path)
        _, _ = save_report(build_benchmark_report(run), args.manifest_path)
        if not args.quiet:
            print(f"Regenerated benchmark report from {args.manifest_path}")
        return 0

    started_dt = datetime.now(timezone.utc)
    started_wall = time.perf_counter()

    run = BenchmarkRun(
        run_id=new_run_id(),
        started_at=started_dt.isoformat(),
        environment=capture_environment(
            {"workload": args.workload, "engine": args.engine, "input_path": args.input_path}
        ),
    )

    result = _execute_workload(args)
    if result is None:
        print(f"ERROR: unsupported workload/engine: {args.workload}/{args.engine}")
        return 2
    run.results.append(result)

    run.duration_sec = round(time.perf_counter() - started_wall, 3)
    run.ended_at = datetime.now(timezone.utc).isoformat()
    if args.no_report:
        run.save(args.manifest_path)
        if not args.quiet:
            print_summary(run)
    else:
        _publish_outputs(run, args.manifest_path, args.quiet)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
