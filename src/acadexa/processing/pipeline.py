"""Acadexa end-to-end Spark processing pipeline orchestrator (Tasks 9.5 & 9.6, rules.md §18, §19).

Coordinates the execution of Spark analytical jobs in documented order:
  J1 Clean + Validate
          ↓
  J2 Event Aggregation
          ↓
  J3 Feature Table
          ↓
  J4 Correlation / J5 Trend Detection / J6 Risk Signals
          ↓
  J7 Publish Gold Data & Validate

Tracks comprehensive pipeline run metadata and stage outcomes:
- Configuration snapshot & seed handling (tied to generation manifest)
- Start/end timestamps, duration, and status
- Stage outcomes: status (SUCCESS/FAILED/SKIPPED), duration, output counts, details
- Output counts across all stages
- Gold validation results summary
- Manifest persistence to data/manifests/pipeline_run_manifest.json
- Strictly zero driver-side collect/toPandas calls (rules.md §17.3)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any
import uuid

from pyspark.sql import DataFrame, SparkSession

from acadexa.processing.jobs import (
    J1Config,
    J1Result,
    J2Config,
    J2Result,
    J3Config,
    J3Result,
    J4Config,
    J4Result,
    J5Config,
    J5Result,
    J6Config,
    J6Result,
    J7Config,
    J7Result,
    run_j1_clean_and_validate,
    run_j2_event_aggregation,
    run_j3_feature_table,
    run_j4_correlation,
    run_j5_trend_detection,
    run_j6_risk_signals,
    run_j7_publish_gold,
)
from acadexa.processing.mongo import (
    get_or_create_mongo_spark_session,
)
from acadexa.processing.spark_session import (
    SparkRuntimeConfig,
    get_or_create_spark_session,
    stop_spark_session,
)

logger = logging.getLogger(__name__)

ALL_STAGES: tuple[str, ...] = ("J1", "J2", "J3", "J4", "J5", "J6", "J7")

STAGE_NAMES: dict[str, str] = {
    "J1": "Clean and Validate",
    "J2": "Event Aggregation",
    "J3": "Feature Table",
    "J4": "Correlation Analytics",
    "J5": "Trend Detection",
    "J6": "Risk Signals",
    "J7": "Publish Gold Data",
}

MANIFEST_VERSION: str = "1.0.0"


@dataclass
class StageOutcome:
    """Outcome and execution metrics for an individual pipeline stage (Task 9.6)."""

    stage_id: str
    stage_name: str
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    start_time: str
    end_time: str
    duration_sec: float
    output_counts: dict[str, int] = field(default_factory=dict)
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert StageOutcome to serializable dictionary."""
        return {
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_sec": round(self.duration_sec, 3),
            "output_counts": self.output_counts,
            "error_message": self.error_message,
            "details": self.details,
        }


@dataclass
class PipelineRunMetadata:
    """Comprehensive pipeline run metadata contract (Task 9.6, rules.md §8.5, §18)."""

    run_id: str
    start_time: str
    manifest_version: str = MANIFEST_VERSION
    pipeline_name: str = "acadexa_spark_pipeline"
    end_time: str | None = None
    duration_sec: float = 0.0
    status: str = "IN_PROGRESS"  # "SUCCESS", "FAILED", "IN_PROGRESS"
    seed: int | None = None
    configuration: dict[str, Any] = field(default_factory=dict)
    stage_outcomes: dict[str, StageOutcome] = field(default_factory=dict)
    output_counts: dict[str, int] = field(default_factory=dict)
    gold_validation_summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def record_stage(self, outcome: StageOutcome) -> None:
        """Record the outcome of an executed stage."""
        self.stage_outcomes[outcome.stage_id] = outcome
        if outcome.output_counts:
            self.output_counts.update(outcome.output_counts)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to JSON-serializable dictionary."""
        return {
            "manifest_version": self.manifest_version,
            "pipeline_name": self.pipeline_name,
            "run_id": self.run_id,
            "status": self.status,
            "seed": self.seed,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_sec": round(self.duration_sec, 3),
            "configuration": self.configuration,
            "stage_outcomes": {
                k: v.to_dict() for k, v in self.stage_outcomes.items()
            },
            "output_counts": self.output_counts,
            "gold_validation_summary": self.gold_validation_summary,
            "error": self.error,
        }

    def save_manifest(self, path: Path | str) -> Path:
        """Save pipeline run metadata manifest to JSON file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info("Saved pipeline run metadata manifest to %s", target)
        return target


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for end-to-end Spark pipeline execution (Task 9.5)."""

    data_dir: Path = Path("data")
    raw_data_dir: Path = Path("data/generated")
    raw_lms_parquet_path: Path = Path("data/raw/lms_events")
    cleaned_data_dir: Path = Path("data/cleaned")
    processed_data_dir: Path = Path("data/processed")
    gold_data_dir: Path = Path("data/gold")
    manifests_dir: Path = Path("data/manifests")
    analytics_dir: Path = Path("data/analytics")
    generation_manifest_path: Path = Path("data/manifests/generation_manifest.json")
    injection_manifest_path: Path = Path("data/manifests/injection_manifest.json")
    pipeline_manifest_path: Path = Path("data/manifests/pipeline_run_manifest.json")
    # MongoDB serving configuration
    mongo_uri: str | None = None
    mongo_database: str | None = None
    publish_to_mongo: bool = True
    save_parquet: bool = True
    # Validation settings
    validate_gold: bool = True
    fail_on_validation_error: bool = True
    # Pipeline stages to run
    stages: tuple[str, ...] = ALL_STAGES
    seed: int | None = None
    run_id: str | None = None
    spark_runtime_config: SparkRuntimeConfig | None = None

    def resolved_seed(self) -> int | None:
        """Resolve seed from explicit config or generation manifest."""
        if self.seed is not None:
            return self.seed
        gen_path = Path(self.generation_manifest_path)
        if gen_path.exists():
            try:
                data = json.loads(gen_path.read_text(encoding="utf-8"))
                return data.get("seed") or data.get("run", {}).get("seed")
            except Exception as ex:
                logger.warning("Could not read seed from generation manifest: %s", ex)
        return None


@dataclass
class PipelineResult:
    """Result of end-to-end Spark pipeline execution."""

    metadata: PipelineRunMetadata
    success: bool
    j1_result: J1Result | None = None
    j2_result: J2Result | None = None
    j3_result: J3Result | None = None
    j4_result: J4Result | None = None
    j5_result: J5Result | None = None
    j6_result: J6Result | None = None
    j7_result: J7Result | None = None


def run_pipeline(
    config: PipelineConfig | None = None,
    spark: SparkSession | None = None,
) -> PipelineResult:
    """Execute the development Spark processing pipeline in documented order (Task 9.5 & 9.6).

    Sequence:
    J1 Clean + Validate → J2 Event Aggregation → J3 Feature Table →
    J4 Correlation / J5 Trend Detection / J6 Risk Signals → J7 Publish Gold Data

    Records complete pipeline run metadata and stage outcomes to pipeline_run_manifest.json.

    Args:
        config: Optional PipelineConfig (defaults to standard development settings).
        spark: Optional active SparkSession. If None, creates a session from runtime config.

    Returns:
        PipelineResult containing metadata, stage outcomes, and execution status.
    """
    cfg = config or PipelineConfig()
    start_time_dt = datetime.now(timezone.utc)
    start_time_iso = start_time_dt.isoformat()
    start_wall = time.perf_counter()

    run_id = cfg.run_id or f"run_{start_time_dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    seed = cfg.resolved_seed()

    config_snapshot = {
        "data_dir": str(cfg.data_dir),
        "raw_data_dir": str(cfg.raw_data_dir),
        "cleaned_data_dir": str(cfg.cleaned_data_dir),
        "processed_data_dir": str(cfg.processed_data_dir),
        "gold_data_dir": str(cfg.gold_data_dir),
        "stages": list(cfg.stages),
        "publish_to_mongo": cfg.publish_to_mongo,
        "save_parquet": cfg.save_parquet,
        "validate_gold": cfg.validate_gold,
    }

    metadata = PipelineRunMetadata(
        run_id=run_id,
        start_time=start_time_iso,
        seed=seed,
        configuration=config_snapshot,
    )

    logger.info("=" * 70)
    logger.info("Starting Acadexa Spark Processing Pipeline [run_id=%s, seed=%s]", run_id, seed)
    logger.info("Configured stages: %s", cfg.stages)
    logger.info("=" * 70)

    # Manage SparkSession lifecycle
    owns_spark = False
    spark_session = spark
    if spark_session is None:
        owns_spark = True
        rt_cfg = cfg.spark_runtime_config or SparkRuntimeConfig(
            app_name=f"AcadexaPipeline_{run_id}",
            master="local[2]",
            shuffle_partitions=2,
        )
        if cfg.publish_to_mongo:
            spark_session = get_or_create_mongo_spark_session(rt_cfg)
        else:
            spark_session = get_or_create_spark_session(rt_cfg)

    j1_res: J1Result | None = None
    j2_res: J2Result | None = None
    j3_res: J3Result | None = None
    j4_res: J4Result | None = None
    j5_res: J5Result | None = None
    j6_res: J6Result | None = None
    j7_res: J7Result | None = None

    active_stages = set(cfg.stages)

    try:
        # =====================================================================
        # Stage J1 — Clean and Validate
        # =====================================================================
        if "J1" in active_stages:
            st_start = time.perf_counter()
            st_iso = datetime.now(timezone.utc).isoformat()
            logger.info(">>> Executing Stage J1: Clean and Validate")
            cfg_j1 = J1Config(
                raw_data_dir=cfg.data_dir,
                output_dir=cfg.cleaned_data_dir,
                report_path=cfg.manifests_dir / "data_quality_report.json",
                manifest_path=cfg.injection_manifest_path,
                save_parquet=cfg.save_parquet,
            )
            j1_res = run_j1_clean_and_validate(spark_session, cfg_j1)
            st_dur = time.perf_counter() - st_start
            st_end_iso = datetime.now(timezone.utc).isoformat()

            if hasattr(j1_res, "counts"):
                j1_counts = j1_res.counts
            elif hasattr(j1_res, "quality_report") and hasattr(j1_res.quality_report, "datasets"):
                j1_counts = {
                    name: metric.output_rows
                    for name, metric in j1_res.quality_report.datasets.items()
                }
            else:
                j1_counts = {}

            metadata.record_stage(
                StageOutcome(
                    stage_id="J1",
                    stage_name=STAGE_NAMES["J1"],
                    status="SUCCESS",
                    start_time=st_iso,
                    end_time=st_end_iso,
                    duration_sec=st_dur,
                    output_counts=j1_counts,
                    details={
                        "cleaned_datasets": list(j1_counts.keys()),
                        "total_cleaned_records": sum(j1_counts.values()),
                    },
                )
            )
        else:
            metadata.record_stage(
                StageOutcome(
                    stage_id="J1",
                    stage_name=STAGE_NAMES["J1"],
                    status="SKIPPED",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    duration_sec=0.0,
                )
            )

        # =====================================================================
        # Stage J2 — Event Aggregation
        # =====================================================================
        if "J2" in active_stages:
            st_start = time.perf_counter()
            st_iso = datetime.now(timezone.utc).isoformat()
            logger.info(">>> Executing Stage J2: Event Aggregation")
            cfg_j2 = J2Config(
                input_path=cfg.cleaned_data_dir / "lms_events",
                raw_fallback_path=cfg.raw_lms_parquet_path,
                output_path=cfg.processed_data_dir / "lms_weekly_engagement",
                save_parquet=cfg.save_parquet,
            )
            j2_res = run_j2_event_aggregation(spark_session, cfg_j2)
            st_dur = time.perf_counter() - st_start
            st_end_iso = datetime.now(timezone.utc).isoformat()

            metadata.record_stage(
                StageOutcome(
                    stage_id="J2",
                    stage_name=STAGE_NAMES["J2"],
                    status="SUCCESS",
                    start_time=st_iso,
                    end_time=st_end_iso,
                    duration_sec=st_dur,
                    output_counts={"lms_weekly_engagement": j2_res.total_output_rows},
                    details={
                        "total_input_events": j2_res.total_input_events,
                        "total_output_rows": j2_res.total_output_rows,
                    },
                )
            )
        else:
            metadata.record_stage(
                StageOutcome(
                    stage_id="J2",
                    stage_name=STAGE_NAMES["J2"],
                    status="SKIPPED",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    duration_sec=0.0,
                )
            )

        # =====================================================================
        # Stage J3 — Feature Table
        # =====================================================================
        if "J3" in active_stages:
            st_start = time.perf_counter()
            st_iso = datetime.now(timezone.utc).isoformat()
            logger.info(">>> Executing Stage J3: Feature Table")
            cfg_j3 = J3Config(
                academic_records_path=cfg.cleaned_data_dir / "academic_records",
                attendance_path=cfg.cleaned_data_dir / "attendance",
                coursework_path=cfg.cleaned_data_dir / "coursework",
                lms_path=cfg.processed_data_dir / "lms_weekly_engagement",
                courses_path=cfg.cleaned_data_dir / "courses",
                students_path=cfg.cleaned_data_dir / "students",
                output_path=cfg.processed_data_dir / "student_features",
                save_parquet=cfg.save_parquet,
            )
            j3_res = run_j3_feature_table(spark_session, cfg_j3)
            st_dur = time.perf_counter() - st_start
            st_end_iso = datetime.now(timezone.utc).isoformat()

            metadata.record_stage(
                StageOutcome(
                    stage_id="J3",
                    stage_name=STAGE_NAMES["J3"],
                    status="SUCCESS",
                    start_time=st_iso,
                    end_time=st_end_iso,
                    duration_sec=st_dur,
                    output_counts={"student_course_features": j3_res.total_features_rows},
                    details={
                        "total_students": j3_res.total_students,
                        "total_features_rows": j3_res.total_features_rows,
                    },
                )
            )
        else:
            metadata.record_stage(
                StageOutcome(
                    stage_id="J3",
                    stage_name=STAGE_NAMES["J3"],
                    status="SKIPPED",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    duration_sec=0.0,
                )
            )

        # =====================================================================
        # Stage J4 — Correlation Analytics
        # =====================================================================
        if "J4" in active_stages:
            st_start = time.perf_counter()
            st_iso = datetime.now(timezone.utc).isoformat()
            logger.info(">>> Executing Stage J4: Correlation Analytics")
            cfg_j4 = J4Config(
                input_path=cfg.processed_data_dir / "student_features",
                output_path=cfg.processed_data_dir / "correlations",
                include_pearson=True,
                save_parquet=cfg.save_parquet,
            )
            j4_res = run_j4_correlation(spark_session, cfg_j4)
            st_dur = time.perf_counter() - st_start
            st_end_iso = datetime.now(timezone.utc).isoformat()

            metadata.record_stage(
                StageOutcome(
                    stage_id="J4",
                    stage_name=STAGE_NAMES["J4"],
                    status="SUCCESS",
                    start_time=st_iso,
                    end_time=st_end_iso,
                    duration_sec=st_dur,
                    output_counts={"correlations_evaluated": j4_res.total_relationships_evaluated},
                    details={
                        "total_relationships_evaluated": j4_res.total_relationships_evaluated,
                    },
                )
            )
        else:
            metadata.record_stage(
                StageOutcome(
                    stage_id="J4",
                    stage_name=STAGE_NAMES["J4"],
                    status="SKIPPED",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    duration_sec=0.0,
                )
            )

        # =====================================================================
        # Stage J5 — Trend Detection
        # =====================================================================
        if "J5" in active_stages:
            st_start = time.perf_counter()
            st_iso = datetime.now(timezone.utc).isoformat()
            logger.info(">>> Executing Stage J5: Trend Detection")
            cfg_j5 = J5Config(
                lms_weekly_path=cfg.processed_data_dir / "lms_weekly_engagement",
                coursework_path=cfg.cleaned_data_dir / "coursework",
                academic_records_path=cfg.cleaned_data_dir / "academic_records",
                output_path=cfg.processed_data_dir / "trend_indicators",
                save_parquet=cfg.save_parquet,
            )
            j5_res = run_j5_trend_detection(spark_session, cfg_j5)
            st_dur = time.perf_counter() - st_start
            st_end_iso = datetime.now(timezone.utc).isoformat()

            metadata.record_stage(
                StageOutcome(
                    stage_id="J5",
                    stage_name=STAGE_NAMES["J5"],
                    status="SUCCESS",
                    start_time=st_iso,
                    end_time=st_end_iso,
                    duration_sec=st_dur,
                    output_counts={"trend_indicators": j5_res.total_rows},
                    details={
                        "total_rows": j5_res.total_rows,
                        "lms_decline_count": j5_res.lms_decline_count,
                        "marks_decline_count": j5_res.marks_decline_count,
                    },
                )
            )
        else:
            metadata.record_stage(
                StageOutcome(
                    stage_id="J5",
                    stage_name=STAGE_NAMES["J5"],
                    status="SKIPPED",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    duration_sec=0.0,
                )
            )

        # =====================================================================
        # Stage J6 — Risk Signals
        # =====================================================================
        if "J6" in active_stages:
            st_start = time.perf_counter()
            st_iso = datetime.now(timezone.utc).isoformat()
            logger.info(">>> Executing Stage J6: Risk Signals")
            cfg_j6 = J6Config(
                student_features_path=cfg.processed_data_dir / "student_features",
                trend_indicators_path=cfg.processed_data_dir / "trend_indicators",
                output_path=cfg.processed_data_dir / "risk_indicators",
                save_parquet=cfg.save_parquet,
            )
            j6_res = run_j6_risk_signals(spark_session, cfg_j6)
            st_dur = time.perf_counter() - st_start
            st_end_iso = datetime.now(timezone.utc).isoformat()

            metadata.record_stage(
                StageOutcome(
                    stage_id="J6",
                    stage_name=STAGE_NAMES["J6"],
                    status="SUCCESS",
                    start_time=st_iso,
                    end_time=st_end_iso,
                    duration_sec=st_dur,
                    output_counts={"risk_indicators": j6_res.total_students},
                    details={
                        "total_students": j6_res.total_students,
                        "flagged_students": j6_res.flagged_students_count,
                        "high_risk_students": j6_res.high_risk_students_count,
                        "signal_counts_breakdown": j6_res.signal_counts_breakdown,
                    },
                )
            )
        else:
            metadata.record_stage(
                StageOutcome(
                    stage_id="J6",
                    stage_name=STAGE_NAMES["J6"],
                    status="SKIPPED",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    duration_sec=0.0,
                )
            )

        # =====================================================================
        # Stage J7 — Publish Gold Data & Validate
        # =====================================================================
        if "J7" in active_stages:
            st_start = time.perf_counter()
            st_iso = datetime.now(timezone.utc).isoformat()
            logger.info(">>> Executing Stage J7: Publish Gold Data & Validate")
            cfg_j7 = J7Config(
                student_features_path=cfg.processed_data_dir / "student_features",
                risk_indicators_path=cfg.processed_data_dir / "risk_indicators",
                parquet_base_path=cfg.gold_data_dir,
                mongo_uri=cfg.mongo_uri,
                mongo_database=cfg.mongo_database,
                publish_to_mongo=cfg.publish_to_mongo,
                save_parquet=cfg.save_parquet,
                validate_after_publication=cfg.validate_gold,
                fail_on_validation_error=cfg.fail_on_validation_error,
            )
            # Use in-memory DataFrames from J3/J6 if available
            ft_df = j3_res.feature_table if j3_res is not None else None
            ri_df = j6_res.risk_indicators if j6_res is not None else None

            j7_res = run_j7_publish_gold(
                spark_session,
                cfg_j7,
                feature_table_df=ft_df,
                risk_indicators_df=ri_df,
            )
            st_dur = time.perf_counter() - st_start
            st_end_iso = datetime.now(timezone.utc).isoformat()

            val_summary = {
                k: {"is_valid": v.is_valid, "row_count": v.row_count, "grain_unique": v.grain_unique}
                for k, v in j7_res.validation_report.items()
            }
            metadata.gold_validation_summary = val_summary

            metadata.record_stage(
                StageOutcome(
                    stage_id="J7",
                    stage_name=STAGE_NAMES["J7"],
                    status="SUCCESS",
                    start_time=st_iso,
                    end_time=st_end_iso,
                    duration_sec=st_dur,
                    output_counts={
                        "gold_student_features": j7_res.student_features_count,
                        "gold_course_metrics": j7_res.course_metrics_count,
                        "gold_school_summary": j7_res.school_summary_count,
                        "gold_risk_indicators": j7_res.risk_indicators_count,
                    },
                    details={
                        "published_collections": j7_res.published_collections,
                        "risk_signal_breakdown": j7_res.risk_signal_breakdown,
                        "validation_report": val_summary,
                    },
                )
            )
        else:
            metadata.record_stage(
                StageOutcome(
                    stage_id="J7",
                    stage_name=STAGE_NAMES["J7"],
                    status="SKIPPED",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    duration_sec=0.0,
                )
            )

        metadata.status = "SUCCESS"
        success = True

    except Exception as ex:
        logger.error("Pipeline failed: %s", ex, exc_info=True)
        metadata.status = "FAILED"
        metadata.error = str(ex)
        success = False
        raise

    finally:
        total_duration = time.perf_counter() - start_wall
        metadata.duration_sec = total_duration
        metadata.end_time = datetime.now(timezone.utc).isoformat()

        # Persist pipeline run metadata manifest (Task 9.6)
        try:
            metadata.save_manifest(cfg.pipeline_manifest_path)
        except Exception as save_ex:
            logger.error("Failed to save pipeline manifest: %s", save_ex)

        if owns_spark and spark_session is not None:
            stop_spark_session(spark_session)

    logger.info("=" * 70)
    logger.info(
        "Pipeline finished with status: %s in %.2fs",
        metadata.status,
        metadata.duration_sec,
    )
    logger.info("Total output records: %s", metadata.output_counts)
    logger.info("=" * 70)

    return PipelineResult(
        metadata=metadata,
        success=success,
        j1_result=j1_res,
        j2_result=j2_res,
        j3_result=j3_res,
        j4_result=j4_res,
        j5_result=j5_res,
        j6_result=j6_res,
        j7_result=j7_res,
    )
