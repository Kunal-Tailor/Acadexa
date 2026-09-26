"""Entry point: load development data into MongoDB (task 6.7, rules.md §9, §16).

Executes the reproducible MongoDB development database loading pipeline:
1. Connects to MongoDB using environment variables or optional CLI arguments.
2. Initializes core collections, time-series LMS collection, and gold placeholders.
3. Loads the 5 core academic collections (students, courses, academic_records,
   attendance, coursework) and verifies counts against generation_manifest.json.
4. Loads the defined LMS operational serving slice (latest semester, schools CET & SOM)
   from partitioned Parquet, keeping the full LMS dataset outside MongoDB.
5. Creates documented query indexes across collections.
6. Prints a detailed verification report and exits 0 on success.
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

from acadexa.database import (
    DatabaseLoadSummary,
    GOLD_COLLECTIONS,
    LoadValidationError,
    MongoDBConfig,
    MongoConnectionError,
    load_development_database,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for MongoDB database loader."""
    parser = argparse.ArgumentParser(
        description="Acadexa MongoDB Development Data Loader & Manifest Verifier"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/generated",
        help="Directory containing generated core collection JSON files (default: 'data/generated')",
    )
    parser.add_argument(
        "--lms-parquet-path",
        type=str,
        default="data/raw/lms_events",
        help="Path to raw LMS Parquet dataset (default: 'data/raw/lms_events')",
    )
    parser.add_argument(
        "--manifest-path",
        type=str,
        default="data/manifests/generation_manifest.json",
        help="Path to generation manifest for verification (default: 'data/manifests/generation_manifest.json')",
    )
    parser.add_argument(
        "--uri",
        type=str,
        default=None,
        help="MongoDB connection URI override (default: from environment/config)",
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help="MongoDB database name override (default: from environment/config)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="Insertion batch size (default: 2000)",
    )
    parser.add_argument(
        "--skip-lms",
        action="store_true",
        help="Skip loading the LMS operational serving slice",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip creating query indexes",
    )
    parser.add_argument(
        "--skip-manifest-check",
        action="store_true",
        help="Bypass count verification against generation manifest",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear existing documents before loading",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress console output",
    )
    return parser.parse_args(argv)


def print_summary(summary: DatabaseLoadSummary) -> None:
    """Print structured, human-readable summary of the MongoDB load run."""
    print("=" * 72)
    print(" Acadexa MongoDB Data Loader (Development Serving Layer)")
    print("=" * 72)
    print(f"Database:          {summary.database}")
    print(f"Duration:          {summary.duration_sec}s")
    mf_info = f"Verified ({summary.manifest_path})" if summary.manifest_verified else "Skipped / Not Available"
    print(f"Manifest Check:    {mf_info}")
    print(f"Total Documents:   {summary.total_documents:,}")
    print("-" * 72)
    print("Core Academic Collections:")
    for name, st in summary.core_result.collections.items():
        val_tag = "[VERIFIED]" if st.validated else "[MISMATCH]"
        print(f"  - {name:<18}: {st.actual_db_count:>8} docs  (expected: {st.expected_count:>8}) {val_tag}")

    print("-" * 72)
    if summary.lms_result is not None:
        lms = summary.lms_result
        val_tag = "[VERIFIED]" if lms.validated else "[MISMATCH]"
        print("LMS Operational Time-Series Slice:")
        print(f"  - lms_events        : {lms.actual_db_count:>8} docs  (scanned: {lms.total_scanned:>8}) {val_tag}")
        print(f"    Schools in slice  : {', '.join(lms.spec.schools)} (Computer Engineering & Technology, Business)")
        print(f"    Semester in slice : {lms.spec.semester_id} ({lms.spec.start_date} to {lms.spec.end_date})")
        print("    Remaining events  : Kept outside MongoDB in raw Parquet")
    else:
        print("LMS Serving Slice:   Skipped (--skip-lms)")

    print("-" * 72)
    print("Gold Analytical Collections (Placeholders - 0 docs populated):")
    for name in GOLD_COLLECTIONS:
        print(f"  - {name:<18}:        0 docs (Spark J7 publication target)")

    if summary.indexes:
        print("-" * 72)
        print("Created / Verified Query Indexes:")
        for col, idx_list in summary.indexes.items():
            if idx_list:
                print(f"  - {col:<18}: {', '.join(idx_list)}")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    """Main script entry point for loading data into MongoDB."""
    args = parse_args(argv)

    # Build config overrides
    config_overrides: dict[str, Any] = {}
    if args.uri:
        config_overrides["uri"] = args.uri
    if args.database:
        config_overrides["database"] = args.database

    config = MongoDBConfig.from_env(**config_overrides)

    try:
        summary = load_development_database(
            config=config,
            data_dir=args.data_dir,
            lms_parquet_path=args.lms_parquet_path,
            manifest_path=None if args.skip_manifest_check else args.manifest_path,
            batch_size=args.batch_size,
            clear_existing=not args.no_clear,
            strict_validation=True,
            load_lms=not args.skip_lms,
            create_indexes=not args.skip_indexes,
        )
    except (LoadValidationError, MongoConnectionError) as exc:
        print(f"ERROR: Database loading failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print_summary(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
