"""Entry point: execute the development Spark processing pipeline (Tasks 9.5 & 9.6, rules.md §18, §19).

Coordinates the end-to-end analytical pipeline:
  J1 Clean + Validate → J2 Event Aggregation → J3 Feature Table →
  J4 Correlation / J5 Trend Detection / J6 Risk Signals → J7 Publish Gold Data & Validate

Records configuration/seed, start/end status, stage outcomes and output counts
to data/manifests/pipeline_run_manifest.json.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

# Ensure src/ is on sys.path when invoked directly as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from acadexa.processing.pipeline import (
    ALL_STAGES,
    PipelineConfig,
    PipelineResult,
    run_pipeline,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for Spark pipeline runner."""
    parser = argparse.ArgumentParser(
        description="Acadexa Development-Scale End-to-End Spark Pipeline Runner"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Base data directory containing generated/cleaned/processed data (default: 'data')",
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        default=list(ALL_STAGES),
        help=f"Pipeline stages to execute (default: all {' '.join(ALL_STAGES)})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic RNG seed override (default: auto-resolved from generation_manifest.json)",
    )
    parser.add_argument(
        "--skip-mongo",
        action="store_true",
        help="Disable publication to MongoDB (parquet only)",
    )
    parser.add_argument(
        "--uri",
        type=str,
        default=None,
        help="MongoDB connection URI override (default: from ACADEXA_MONGO_URI / localhost)",
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help="MongoDB database name override (default: from ACADEXA_MONGO_DATABASE / acadexa)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Disable post-publication gold collection validation",
    )
    parser.add_argument(
        "--manifest-path",
        type=str,
        default=None,
        help="Path for saving pipeline run manifest (default: <data-dir>/manifests/pipeline_run_manifest.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress console output summary",
    )
    return parser.parse_args(argv)


def print_summary(res: PipelineResult) -> None:
    """Print human-readable summary of the pipeline execution run."""
    meta = res.metadata
    print("\n" + "=" * 76)
    print(" Acadexa End-to-End Spark Processing Pipeline Run Summary")
    print("=" * 76)
    print(f"Run ID:      {meta.run_id}")
    print(f"Status:      {meta.status}")
    print(f"Seed:        {meta.seed}")
    print(f"Duration:    {meta.duration_sec:.2f}s")
    print(f"Start Time:  {meta.start_time}")
    print(f"End Time:    {meta.end_time}")
    print("-" * 76)
    print(f"{'Stage':<6} {'Stage Name':<28} {'Status':<10} {'Duration':<10} {'Output Summary'}")
    print("-" * 76)

    for stage_id, outcome in meta.stage_outcomes.items():
        dur_str = f"{outcome.duration_sec:.2f}s"
        out_summary = ", ".join(f"{k}: {v}" for k, v in outcome.output_counts.items())
        if outcome.status == "SKIPPED":
            out_summary = "[skipped]"
        elif outcome.status == "FAILED":
            out_summary = f"[ERROR: {outcome.error_message}]"
        print(f"{stage_id:<6} {outcome.stage_name:<28} {outcome.status:<10} {dur_str:<10} {out_summary}")

    print("-" * 76)
    if meta.gold_validation_summary:
        print("Gold Collections Validation:")
        for coll, val in meta.gold_validation_summary.items():
            st = "PASSED" if val.get("is_valid") else "FAILED"
            print(f"  - {coll:<18}: [{st}] {val.get('row_count', 0)} rows (grain unique: {val.get('grain_unique')})")
        print("-" * 76)

    manifest_path = Path(meta.configuration.get("data_dir", "data")) / "manifests" / "pipeline_run_manifest.json"
    print(f"Run manifest saved to: {manifest_path}")
    print("=" * 76 + "\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for running the Spark pipeline."""
    args = parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    data_dir = Path(args.data_dir)
    manifest_path = Path(args.manifest_path) if args.manifest_path else data_dir / "manifests" / "pipeline_run_manifest.json"

    cfg = PipelineConfig(
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
        pipeline_manifest_path=manifest_path,
        mongo_uri=args.uri,
        mongo_database=args.database,
        publish_to_mongo=not args.skip_mongo,
        save_parquet=True,
        validate_gold=not args.skip_validation,
        fail_on_validation_error=True,
        stages=tuple(args.stages),
        seed=args.seed,
    )

    try:
        res = run_pipeline(cfg)
        if not args.quiet:
            print_summary(res)
        return 0 if res.success else 1
    except Exception as ex:
        logger.error("Pipeline run failed: %s", ex, exc_info=True)
        if not args.quiet:
            print(f"\n[PIPELINE RUN FAILED]: {ex}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
