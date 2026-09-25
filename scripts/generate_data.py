"""Entry point: generate development-scale synthetic dataset (task 5.8, F-B09, rules.md §8, §10).

Executes the complete synthetic data generation pipeline:
- University hierarchy & difficulty-weighted courses
- Student cohort & decliners
- Synthetic ground-truth registry
- Latent behavioral traits, academic records, weekly attendance, coursework
- Controlled data-quality injection (duplicates, non-key nulls, timestamp inconsistencies,
  course-ID formatting, orphan records, out-of-range values)
- Chunked LMS events written directly to Parquet
- Generation and injection manifests
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Ensure src/ is on sys.path when invoked directly as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from acadexa.generator.orchestrator import GenerationResult, generate_dataset


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for synthetic data generator."""
    parser = argparse.ArgumentParser(
        description="Acadexa Development-Scale Synthetic Data Generator"
    )
    parser.add_argument(
        "--target-students",
        type=int,
        default=36,
        help="Target student population size for development scale (default: 36)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic RNG seed override (default: configured seed)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Base data output directory (default: 'data')",
    )
    parser.add_argument(
        "--lms-parquet-path",
        type=str,
        default=None,
        help="Explicit path for LMS Parquet dataset (default: <output-dir>/raw/lms_events)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for streaming LMS event generation (default: 1000)",
    )
    parser.add_argument(
        "--skip-quality-injection",
        action="store_true",
        help="Disable controlled data-quality injection",
    )
    parser.add_argument(
        "--min-injections",
        type=int,
        default=1,
        help="Minimum injections per active issue category (default: 1)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress console output summary",
    )
    return parser.parse_args(argv)


def print_summary(res: GenerationResult) -> None:
    """Print human-readable summary of the generation run."""
    print("=" * 66)
    print(" Acadexa Synthetic Data Generator (Development Scale)")
    print("=" * 66)
    print(f"Seed:             {res.run.seed}")
    print(f"Duration:         {res.duration_sec}s")
    print(f"Output Directory: {res.output_files.get('students', Path()).parent.parent}")
    print("-" * 66)
    print("Generated Datasets & Counts:")
    for name, count in res.actual_counts.items():
        p = res.output_files.get(name, "")
        size_str = ""
        if name in res.disk_usage_bytes:
            kb = res.disk_usage_bytes[name] / 1024
            size_str = f" ({kb:.1f} KB)"
        print(f"  - {name:<18}: {count:>8} records{size_str} -> {p}")

    print("-" * 66)
    if res.injection_manifest is not None:
        print(f"Data Quality Injections (Total: {res.injection_manifest.total_injected}):")
        for cat, cnt in res.injection_manifest.injected_issue_counts.items():
            rate = res.injection_manifest.rates.get(cat, 0.0)
            print(f"  - {cat:<26}: {cnt:>5} injected (rate: {rate * 100:.1f}%)")
    else:
        print("Data Quality Injections: Skipped")

    print("-" * 66)
    print("Manifests & Metadata:")
    print(f"  - Ground Truth Registry: {res.output_files.get('ground_truth_registry', 'None')}")
    print(f"  - Generation Manifest:   {res.output_files.get('generation_manifest', 'None')}")
    if res.injection_manifest is not None:
        print(f"  - Injection Manifest:    {res.output_files.get('injection_manifest', 'None')}")
    print("=" * 66)


def main(argv: list[str] | None = None) -> int:
    """Main script entry point for data generation."""
    args = parse_args(argv)

    result = generate_dataset(
        seed=args.seed,
        target_students=args.target_students,
        data_dir=args.output_dir,
        lms_parquet_path=args.lms_parquet_path,
        chunk_size=args.chunk_size,
        inject_issues=not args.skip_quality_injection,
        min_injections=args.min_injections,
        save_manifests=True,
        save_core_collections=True,
        save_lms_parquet=True,
    )

    if not args.quiet:
        print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
