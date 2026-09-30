"""Entry point: run the J8 benchmark suite (Tasks 13.1 & 13.2, rules.md §18, §30).

Executes registered benchmark workloads per engine, records measured
timing/memory/dataset metadata to a run manifest, and prints a summary.
Formatted result publication belongs to Task 13.6; this script saves only
the raw run manifest. Engine choices grow as later Phase 13 tasks land.
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
from acadexa.benchmarks.pandas import run_weekly_engagement_pandas
from acadexa.benchmarks.mongodb import run_weekly_engagement_mongodb
from acadexa.benchmarks.spark import run_weekly_engagement_spark


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


def main(argv: list[str] | None = None) -> int:
    """Main script entry point for running benchmarks."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    started_dt = datetime.now(timezone.utc)
    started_wall = time.perf_counter()

    run = BenchmarkRun(
        run_id=new_run_id(),
        started_at=started_dt.isoformat(),
        environment=capture_environment(
            {"workload": args.workload, "engine": args.engine, "input_path": args.input_path}
        ),
    )

    if args.workload == "weekly_lms_engagement" and args.engine == ENGINE_PANDAS:
        result = run_weekly_engagement_pandas(
            args.input_path, measure_memory=not args.no_measure_memory
        )
    elif args.workload == "weekly_lms_engagement" and args.engine == ENGINE_MONGODB:
        result = run_weekly_engagement_mongodb(
            collection=args.collection,
            measure_memory=not args.no_measure_memory,
        )
    elif args.workload == "weekly_lms_engagement" and args.engine == ENGINE_PYSPARK:
        output_path = args.output_path
        cleanup_output = False
        if output_path is None:
            output_path = tempfile.mkdtemp(prefix="acadexa_bench_spark_")
            cleanup_output = True
        try:
            result = run_weekly_engagement_spark(args.input_path, output_path)
        finally:
            if cleanup_output:
                shutil.rmtree(output_path, ignore_errors=True)
    else:
        print(f"ERROR: unsupported workload/engine: {args.workload}/{args.engine}")
        return 2
    run.results.append(result)

    run.duration_sec = round(time.perf_counter() - started_wall, 3)
    run.ended_at = datetime.now(timezone.utc).isoformat()
    run.save(args.manifest_path)

    if not args.quiet:
        print_summary(run)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
