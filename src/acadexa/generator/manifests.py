"""Generation and injection manifests (task 5.7, F-I02, rules.md §8.5, §10.2).

Provides data contracts and serializable models for recording:
1. Generation Manifest:
   - Run seed and configuration snapshot
   - Generation timestamp
   - Target counts vs actual generated counts
   - Output files, duration, and disk usage
   - Injected issue counts summary / reference
2. Injection Manifest:
   - Run seed and injection rates
   - Total injected issue count
   - Exact breakdown of injected issues by category:
     (duplicate_lms_events, nulls_non_key, timestamp_inconsistencies,
      course_id_formatting, orphan_records, out_of_range_values)
   - Exact breakdown per dataset (lms_events, academic_records,
      attendance, coursework)
   - Baseline record counts (pre-injection volumes)

Architecture & Rules:
- Rules.md §8.5: Retain enough metadata to reproduce and audit the dataset
  (seed, configuration, target counts, actual counts, timestamp).
- Rules.md §10.2: Every injection run should record exact injected counts.
- Memory.md §23 & F-I02: Manifests act as ground-truth contracts for downstream
  cleaning evaluation and MongoDB load verification.
- Output location: data/manifests/generation_manifest.json and
  data/manifests/injection_manifest.json.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from acadexa.generator.foundation import GeneratorError, GeneratorRun, _check, _jsonable
from acadexa.generator.quality_injection import DEFAULT_INJECTION_RATES, InjectionReport

DEFAULT_MANIFEST_DIR: Path = Path("data/manifests")
DEFAULT_GENERATION_MANIFEST_PATH: Path = DEFAULT_MANIFEST_DIR / "generation_manifest.json"
DEFAULT_INJECTION_MANIFEST_PATH: Path = DEFAULT_MANIFEST_DIR / "injection_manifest.json"

MANIFEST_VERSION: str = "1.0.0"


def _validate_iso_timestamp(ts: str) -> None:
    """Validate that ts is a valid ISO-8601 timestamp string."""
    _check(isinstance(ts, str), f"Timestamp must be a string, got {type(ts).__name__}")
    try:
        # Normalize trailing Z to +00:00 for fromisoformat compatibility
        normalized = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        datetime.fromisoformat(normalized)
    except (ValueError, TypeError) as exc:
        raise GeneratorError(f"Invalid ISO-8601 timestamp '{ts}': {exc}") from exc


def _validate_counts_dict(counts: dict[str, Any], name: str) -> None:
    """Validate that counts is a dict of non-negative integer values."""
    _check(isinstance(counts, dict), f"{name} must be a dictionary, got {type(counts).__name__}")
    for key, val in counts.items():
        _check(isinstance(key, str), f"{name} key must be a string, got {key!r}")
        _check(
            isinstance(val, int) and not isinstance(val, bool) and val >= 0,
            f"{name}['{key}'] must be a non-negative integer, got {val!r}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Generation Manifest
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GenerationManifest:
    """Manifest describing a synthetic data generation run (F-I02, rules.md §8.5).

    Records the seed, configuration, target counts, actual generated counts,
    and output execution metadata.
    """

    seed: int
    generated_at: str
    target_counts: dict[str, int]
    actual_counts: dict[str, int]
    configuration: dict[str, Any]
    manifest_version: str = MANIFEST_VERSION
    manifest_type: str = "generation_manifest"
    generation_duration_sec: float | None = None
    disk_usage_bytes: dict[str, int] | int | None = None
    output_files: dict[str, str] | None = None
    injected_issues_summary: dict[str, int] | None = None
    injection_manifest_path: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate all fields in the manifest."""
        _check(
            isinstance(self.seed, int) and not isinstance(self.seed, bool),
            f"seed must be an integer, got {self.seed!r}",
        )
        _validate_iso_timestamp(self.generated_at)
        _validate_counts_dict(self.target_counts, "target_counts")
        _validate_counts_dict(self.actual_counts, "actual_counts")
        _check(
            isinstance(self.configuration, dict),
            f"configuration must be a dictionary, got {type(self.configuration).__name__}",
        )
        if self.generation_duration_sec is not None:
            _check(
                isinstance(self.generation_duration_sec, (int, float))
                and not isinstance(self.generation_duration_sec, bool)
                and self.generation_duration_sec >= 0.0,
                f"generation_duration_sec must be non-negative float, got {self.generation_duration_sec!r}",
            )
        if self.disk_usage_bytes is not None:
            if isinstance(self.disk_usage_bytes, dict):
                _validate_counts_dict(self.disk_usage_bytes, "disk_usage_bytes")
            else:
                _check(
                    isinstance(self.disk_usage_bytes, int)
                    and not isinstance(self.disk_usage_bytes, bool)
                    and self.disk_usage_bytes >= 0,
                    f"disk_usage_bytes must be non-negative int or dict, got {self.disk_usage_bytes!r}",
                )
        if self.injected_issues_summary is not None:
            _validate_counts_dict(self.injected_issues_summary, "injected_issues_summary")

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to a JSON-serializable dictionary."""
        d: dict[str, Any] = {
            "manifest_version": self.manifest_version,
            "manifest_type": self.manifest_type,
            "seed": self.seed,
            "generated_at": self.generated_at,
            "target_counts": dict(self.target_counts),
            "actual_counts": dict(self.actual_counts),
            "configuration": _jsonable(self.configuration),
        }
        if self.generation_duration_sec is not None:
            d["generation_duration_sec"] = float(self.generation_duration_sec)
        if self.disk_usage_bytes is not None:
            d["disk_usage_bytes"] = (
                dict(self.disk_usage_bytes)
                if isinstance(self.disk_usage_bytes, dict)
                else int(self.disk_usage_bytes)
            )
        if self.output_files is not None:
            d["output_files"] = dict(self.output_files)
        if self.injected_issues_summary is not None:
            d["injected_issues_summary"] = dict(self.injected_issues_summary)
        if self.injection_manifest_path is not None:
            d["injection_manifest_path"] = str(self.injection_manifest_path)
        if self.metadata is not None:
            d["metadata"] = _jsonable(self.metadata)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationManifest:
        """Create a GenerationManifest from a dictionary representation."""
        _check(isinstance(data, dict), f"data must be a dictionary, got {type(data).__name__}")
        for req in ("seed", "generated_at", "target_counts", "actual_counts", "configuration"):
            _check(req in data, f"GenerationManifest dictionary missing required key '{req}'")

        return cls(
            seed=int(data["seed"]),
            generated_at=str(data["generated_at"]),
            target_counts={str(k): int(v) for k, v in data["target_counts"].items()},
            actual_counts={str(k): int(v) for k, v in data["actual_counts"].items()},
            configuration=copy.deepcopy(data["configuration"]),
            manifest_version=str(data.get("manifest_version", MANIFEST_VERSION)),
            manifest_type=str(data.get("manifest_type", "generation_manifest")),
            generation_duration_sec=(
                float(data["generation_duration_sec"])
                if data.get("generation_duration_sec") is not None
                else None
            ),
            disk_usage_bytes=copy.deepcopy(data.get("disk_usage_bytes")),
            output_files=(
                {str(k): str(v) for k, v in data["output_files"].items()}
                if data.get("output_files") is not None
                else None
            ),
            injected_issues_summary=(
                {str(k): int(v) for k, v in data["injected_issues_summary"].items()}
                if data.get("injected_issues_summary") is not None
                else None
            ),
            injection_manifest_path=(
                str(data["injection_manifest_path"])
                if data.get("injection_manifest_path") is not None
                else None
            ),
            metadata=copy.deepcopy(data.get("metadata")),
        )

    def save(self, path: str | Path | None = None, indent: int = 2) -> Path:
        """Save this GenerationManifest to a JSON file."""
        target = Path(path) if path is not None else DEFAULT_GENERATION_MANIFEST_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
        target.write_text(content, encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path | None = None) -> GenerationManifest:
        """Load a GenerationManifest from a JSON file."""
        target = Path(path) if path is not None else DEFAULT_GENERATION_MANIFEST_PATH
        if not target.exists():
            raise FileNotFoundError(f"Generation manifest not found at: {target}")
        content = json.loads(target.read_text(encoding="utf-8"))
        return cls.from_dict(content)


# ─────────────────────────────────────────────────────────────────────────────
# Injection Manifest
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InjectionManifest:
    """Manifest describing controlled data-quality issues injected into datasets (rules.md §10.2).

    Records exact injected counts across the approved categories and per dataset.
    """

    seed: int
    generated_at: str
    total_injected: int
    injected_issue_counts: dict[str, int]
    per_dataset_counts: dict[str, dict[str, int]]
    rates: dict[str, float]
    manifest_version: str = MANIFEST_VERSION
    manifest_type: str = "injection_manifest"
    baseline_counts: dict[str, int] | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.validate()

    @property
    def counts(self) -> dict[str, int]:
        """Convenient alias for injected_issue_counts."""
        return self.injected_issue_counts

    def validate(self) -> None:
        """Validate all fields in the manifest."""
        _check(
            isinstance(self.seed, int) and not isinstance(self.seed, bool),
            f"seed must be an integer, got {self.seed!r}",
        )
        _validate_iso_timestamp(self.generated_at)
        _check(
            isinstance(self.total_injected, int)
            and not isinstance(self.total_injected, bool)
            and self.total_injected >= 0,
            f"total_injected must be a non-negative integer, got {self.total_injected!r}",
        )
        _validate_counts_dict(self.injected_issue_counts, "injected_issue_counts")

        # Sum of individual category counts must match total_injected
        sum_counts = sum(self.injected_issue_counts.values())
        _check(
            self.total_injected == sum_counts,
            f"total_injected ({self.total_injected}) does not match sum of injected_issue_counts ({sum_counts})",
        )

        # Validate rates
        _check(isinstance(self.rates, dict), f"rates must be a dictionary, got {type(self.rates).__name__}")
        for k, v in self.rates.items():
            _check(
                isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v <= 1.0,
                f"Rate for '{k}' must be float in [0.0, 1.0], got {v!r}",
            )

        # Validate per_dataset_counts
        _check(
            isinstance(self.per_dataset_counts, dict),
            f"per_dataset_counts must be a dictionary, got {type(self.per_dataset_counts).__name__}",
        )
        dataset_total = 0
        for ds_name, sub_counts in self.per_dataset_counts.items():
            _check(isinstance(ds_name, str), f"per_dataset_counts key must be str, got {ds_name!r}")
            _validate_counts_dict(sub_counts, f"per_dataset_counts['{ds_name}']")
            dataset_total += sum(sub_counts.values())

        _check(
            self.total_injected == dataset_total,
            f"total_injected ({self.total_injected}) does not match sum across per_dataset_counts ({dataset_total})",
        )

        if self.baseline_counts is not None:
            _validate_counts_dict(self.baseline_counts, "baseline_counts")

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to a JSON-serializable dictionary."""
        d: dict[str, Any] = {
            "manifest_version": self.manifest_version,
            "manifest_type": self.manifest_type,
            "seed": self.seed,
            "generated_at": self.generated_at,
            "total_injected": self.total_injected,
            "injected_issue_counts": dict(self.injected_issue_counts),
            "per_dataset_counts": {k: dict(v) for k, v in self.per_dataset_counts.items()},
            "rates": {k: float(v) for k, v in self.rates.items()},
        }
        if self.baseline_counts is not None:
            d["baseline_counts"] = dict(self.baseline_counts)
        if self.metadata is not None:
            d["metadata"] = _jsonable(self.metadata)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InjectionManifest:
        """Create an InjectionManifest from a dictionary representation."""
        _check(isinstance(data, dict), f"data must be a dictionary, got {type(data).__name__}")
        for req in (
            "seed",
            "generated_at",
            "total_injected",
            "per_dataset_counts",
            "rates",
        ):
            _check(req in data, f"InjectionManifest dictionary missing required key '{req}'")

        # Support either 'injected_issue_counts' or alias 'counts'
        issue_counts_raw = data.get("injected_issue_counts") or data.get("counts")
        _check(
            issue_counts_raw is not None,
            "InjectionManifest dictionary missing 'injected_issue_counts' or 'counts'",
        )

        return cls(
            seed=int(data["seed"]),
            generated_at=str(data["generated_at"]),
            total_injected=int(data["total_injected"]),
            injected_issue_counts={str(k): int(v) for k, v in issue_counts_raw.items()},
            per_dataset_counts={
                str(k): {str(sub_k): int(sub_v) for sub_k, sub_v in v.items()}
                for k, v in data["per_dataset_counts"].items()
            },
            rates={str(k): float(v) for k, v in data["rates"].items()},
            manifest_version=str(data.get("manifest_version", MANIFEST_VERSION)),
            manifest_type=str(data.get("manifest_type", "injection_manifest")),
            baseline_counts=(
                {str(k): int(v) for k, v in data["baseline_counts"].items()}
                if data.get("baseline_counts") is not None
                else None
            ),
            metadata=copy.deepcopy(data.get("metadata")),
        )

    def save(self, path: str | Path | None = None, indent: int = 2) -> Path:
        """Save this InjectionManifest to a JSON file."""
        target = Path(path) if path is not None else DEFAULT_INJECTION_MANIFEST_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
        target.write_text(content, encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path | None = None) -> InjectionManifest:
        """Load an InjectionManifest from a JSON file."""
        target = Path(path) if path is not None else DEFAULT_INJECTION_MANIFEST_PATH
        if not target.exists():
            raise FileNotFoundError(f"Injection manifest not found at: {target}")
        content = json.loads(target.read_text(encoding="utf-8"))
        return cls.from_dict(content)


# ─────────────────────────────────────────────────────────────────────────────
# Builders and Manifest Utilities
# ─────────────────────────────────────────────────────────────────────────────


def build_generation_manifest(
    run: GeneratorRun | None = None,
    *,
    seed: int | None = None,
    configuration: dict[str, Any] | None = None,
    target_counts: dict[str, int] | None = None,
    actual_counts: dict[str, int],
    generated_at: str | datetime | None = None,
    generation_duration_sec: float | None = None,
    disk_usage_bytes: dict[str, int] | int | None = None,
    output_files: dict[str, str] | None = None,
    injection_report: InjectionReport | None = None,
    injection_manifest_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> GenerationManifest:
    """Build a GenerationManifest from a generator run and actual counts (task 5.7).

    Args:
        run: Seeded generator run providing seed, configuration snapshot, and targets.
        seed: Explicit seed if run is omitted or overriden.
        configuration: Explicit configuration if run is omitted or overriden.
        target_counts: Explicit target volumes if run is omitted or overriden.
        actual_counts: Actual counts of generated entities/events.
        generated_at: Timestamp of generation (ISO string or datetime). Defaults to now UTC.
        generation_duration_sec: Optional duration of generation in seconds.
        disk_usage_bytes: Optional disk usage in bytes (int or dict by dataset).
        output_files: Optional mapping of dataset names to file paths.
        injection_report: Optional InjectionReport to record injected issue summary.
        injection_manifest_path: Optional path to the accompanying injection manifest.
        metadata: Optional additional metadata.

    Returns:
        Validated GenerationManifest instance.
    """
    if run is not None:
        if seed is None:
            seed = run.seed
        if configuration is None:
            configuration = run.metadata.configuration
        if target_counts is None:
            target_counts = run.metadata.targets

    _check(seed is not None, "seed must be provided either via 'run' or 'seed'")
    _check(configuration is not None, "configuration must be provided via 'run' or 'configuration'")
    if target_counts is None:
        target_counts = {}

    if generated_at is None:
        ts_str = datetime.now(timezone.utc).isoformat()
    elif isinstance(generated_at, datetime):
        ts_str = generated_at.astimezone(timezone.utc).isoformat()
    else:
        ts_str = str(generated_at)

    injected_summary: dict[str, int] | None = None
    if injection_report is not None:
        injected_summary = dict(injection_report.counts)

    return GenerationManifest(
        seed=seed,
        generated_at=ts_str,
        target_counts=dict(target_counts),
        actual_counts=dict(actual_counts),
        configuration=copy.deepcopy(configuration),
        generation_duration_sec=generation_duration_sec,
        disk_usage_bytes=disk_usage_bytes,
        output_files=output_files,
        injected_issues_summary=injected_summary,
        injection_manifest_path=str(injection_manifest_path) if injection_manifest_path else None,
        metadata=metadata,
    )


def build_injection_manifest(
    run: GeneratorRun | None = None,
    *,
    report: InjectionReport | None = None,
    seed: int | None = None,
    rates: dict[str, float] | None = None,
    total_injected: int | None = None,
    injected_issue_counts: dict[str, int] | None = None,
    per_dataset_counts: dict[str, dict[str, int]] | None = None,
    baseline_counts: dict[str, int] | None = None,
    generated_at: str | datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> InjectionManifest:
    """Build an InjectionManifest from an InjectionReport or explicit values (task 5.7).

    Args:
        run: Optional seeded generator run providing seed.
        report: Optional InjectionReport from :func:`inject_data_quality`.
        seed: Explicit run seed if run is omitted or overriden.
        rates: Injected issue rates mapping. Populated from report or defaults if omitted.
        total_injected: Total count of injected issues. Populated from report if omitted.
        injected_issue_counts: Injected issue counts by category. Populated from report if omitted.
        per_dataset_counts: Injected issue counts per dataset. Populated from report if omitted.
        baseline_counts: Pre-injection record volumes per dataset.
        generated_at: Timestamp (ISO string or datetime). Defaults to now UTC.
        metadata: Optional additional metadata.

    Returns:
        Validated InjectionManifest instance.
    """
    if run is not None and seed is None:
        seed = run.seed

    if report is not None:
        if seed is None and hasattr(report, "seed"):
            seed = report.seed
        if rates is None:
            rates = dict(report.rates)
        if total_injected is None:
            total_injected = report.total_injected
        if injected_issue_counts is None:
            injected_issue_counts = dict(report.counts)
        if per_dataset_counts is None:
            per_dataset_counts = {k: dict(v) for k, v in report.per_dataset_counts.items()}
        if generated_at is None and hasattr(report, "timestamp"):
            generated_at = report.timestamp

    _check(seed is not None, "seed must be provided via 'run', 'report', or 'seed'")

    if rates is None:
        rates = dict(DEFAULT_INJECTION_RATES)
    if injected_issue_counts is None:
        injected_issue_counts = {}
    if per_dataset_counts is None:
        per_dataset_counts = {}
    if total_injected is None:
        total_injected = sum(injected_issue_counts.values())

    if generated_at is None:
        ts_str = datetime.now(timezone.utc).isoformat()
    elif isinstance(generated_at, datetime):
        ts_str = generated_at.astimezone(timezone.utc).isoformat()
    else:
        ts_str = str(generated_at)

    return InjectionManifest(
        seed=seed,
        generated_at=ts_str,
        total_injected=total_injected,
        injected_issue_counts=dict(injected_issue_counts),
        per_dataset_counts={k: dict(v) for k, v in per_dataset_counts.items()},
        rates=dict(rates),
        baseline_counts=dict(baseline_counts) if baseline_counts is not None else None,
        metadata=metadata,
    )


def build_manifests(
    run: GeneratorRun,
    *,
    actual_counts: dict[str, int],
    injection_report: InjectionReport | None = None,
    generation_duration_sec: float | None = None,
    disk_usage_bytes: dict[str, int] | int | None = None,
    output_files: dict[str, str] | None = None,
    baseline_counts: dict[str, int] | None = None,
    generation_metadata: dict[str, Any] | None = None,
    injection_metadata: dict[str, Any] | None = None,
    save: bool = False,
    generation_manifest_path: str | Path = DEFAULT_GENERATION_MANIFEST_PATH,
    injection_manifest_path: str | Path = DEFAULT_INJECTION_MANIFEST_PATH,
) -> tuple[GenerationManifest, InjectionManifest | None]:
    """Build (and optionally save) generation and injection manifests together.

    Args:
        run: Seeded generator run.
        actual_counts: Actual counts of generated entities/events.
        injection_report: Optional InjectionReport from quality injection.
        generation_duration_sec: Optional duration of generation in seconds.
        disk_usage_bytes: Optional disk usage in bytes.
        output_files: Optional output file paths.
        baseline_counts: Optional pre-injection baseline record counts.
        generation_metadata: Optional metadata for generation manifest.
        injection_metadata: Optional metadata for injection manifest.
        save: If True, saves manifests to their target paths.
        generation_manifest_path: Destination path for generation manifest.
        injection_manifest_path: Destination path for injection manifest.

    Returns:
        Tuple of (GenerationManifest, InjectionManifest or None).
    """
    inj_manifest: InjectionManifest | None = None
    inj_path_str: str | None = None

    if injection_report is not None:
        inj_path_str = str(injection_manifest_path)
        inj_manifest = build_injection_manifest(
            run=run,
            report=injection_report,
            baseline_counts=baseline_counts or actual_counts,
            metadata=injection_metadata,
        )

    gen_manifest = build_generation_manifest(
        run=run,
        actual_counts=actual_counts,
        generation_duration_sec=generation_duration_sec,
        disk_usage_bytes=disk_usage_bytes,
        output_files=output_files,
        injection_report=injection_report,
        injection_manifest_path=inj_path_str,
        metadata=generation_metadata,
    )

    if save:
        gen_manifest.save(generation_manifest_path)
        if inj_manifest is not None:
            inj_manifest.save(injection_manifest_path)

    return gen_manifest, inj_manifest


def save_generation_manifest(
    manifest: GenerationManifest,
    path: str | Path | None = None,
    indent: int = 2,
) -> Path:
    """Save a GenerationManifest to a JSON file."""
    return manifest.save(path=path, indent=indent)


def load_generation_manifest(
    path: str | Path | None = None,
) -> GenerationManifest:
    """Load a GenerationManifest from a JSON file."""
    return GenerationManifest.load(path=path)


def save_injection_manifest(
    manifest: InjectionManifest,
    path: str | Path | None = None,
    indent: int = 2,
) -> Path:
    """Save an InjectionManifest to a JSON file."""
    return manifest.save(path=path, indent=indent)


def load_injection_manifest(
    path: str | Path | None = None,
) -> InjectionManifest:
    """Load an InjectionManifest from a JSON file."""
    return InjectionManifest.load(path=path)
