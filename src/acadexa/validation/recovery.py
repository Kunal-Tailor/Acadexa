"""Ground-truth recovery comparison (Task 10.2, rules.md §9, §31, features.md F-F01).

Compares what the synthetic generator planted (ground-truth registry,
established before analytical observation) against what Spark analytics
observed (J4 correlation output). Results use non-causal language:
observed statistical association, never causation.

Recovery criteria are predefined constants aligned with
``interpret_spearman_association`` boundaries (±0.10 = no observed
monotonic association):

- Planted positive: recovered when the primary observed Spearman
  coefficient is >= ``RECOVERY_POSITIVE_THRESHOLD`` (0.10).
- Planted negative: recovered when it is <= ``RECOVERY_NEGATIVE_THRESHOLD``.
- Decoy (expected none): correctly shows no association when
  ``abs(coefficient) < DECOY_NULL_THRESHOLD``; otherwise flagged as a
  spurious observed association (the decoy is a negative control, so a
  spurious flag does not fail planted recovery).

Primary observed metric is ``spearman_normalized`` (within-course
normalization per rules.md §20.2), falling back to ``spearman_raw`` when
the normalized value is unavailable.

The comparison never modifies the registry after observing analytics.
Expected relationships are read from the registry file; observed values
are read from J4 output. Each entry is classified as planted / recovered /
not recovered / decoy, plus ``not_evaluated`` when analytics produced no
observation for a planted relationship (e.g. the course-difficulty
confounder, which J4 does not correlate directly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

# Predefined recovery thresholds (fixed before observing analytics).
RECOVERY_POSITIVE_THRESHOLD: float = 0.10
RECOVERY_NEGATIVE_THRESHOLD: float = -0.10
DECOY_NULL_THRESHOLD: float = 0.10

RECOVERY_REPORT_VERSION: str = "1.0.0"
DEFAULT_RECOVERY_REPORT_PATH: Path = Path("reports/recovery/ground_truth_recovery.json")


def _check(condition: bool, message: str) -> None:
    """Raise ValueError with ``message`` when ``condition`` is false."""
    if not condition:
        raise ValueError(message)


def select_primary_observation(observed: Mapping[str, Any]) -> float | None:
    """Select the primary observed Spearman coefficient from a J4 result row.

    Prefers ``spearman_normalized`` (within-course normalized) and falls
    back to ``spearman_raw`` when normalized is missing or null.
    """
    normalized = observed.get("spearman_normalized")
    if normalized is not None:
        return float(normalized)
    raw = observed.get("spearman_raw")
    if raw is not None:
        return float(raw)
    return None


def classify_recovery(
    expected_direction: str,
    relationship_type: str,
    observed_corr: float | None,
) -> str:
    """Classify a single relationship comparison into a recovery status.

    Args:
        expected_direction: Planted expectation (``positive``/``negative``/
            ``none``). ``confounder`` entries are treated as non-directional
            and reported as ``not_evaluated`` by the caller convention.
        relationship_type: ``planted``, ``decoy`` or ``confounder``.
        observed_corr: Primary observed Spearman coefficient, or None when
            analytics produced no usable observation.

    Returns:
        One of ``recovered``, ``not_recovered``, ``correctly_no_association``,
        ``spurious_association``, ``not_evaluated``.
    """
    if observed_corr is None:
        return "not_evaluated"
    if relationship_type == "decoy" or expected_direction == "none":
        if abs(float(observed_corr)) < DECOY_NULL_THRESHOLD:
            return "correctly_no_association"
        return "spurious_association"
    if expected_direction == "positive":
        return (
            "recovered"
            if float(observed_corr) >= RECOVERY_POSITIVE_THRESHOLD
            else "not_recovered"
        )
    if expected_direction == "negative":
        return (
            "recovered"
            if float(observed_corr) <= RECOVERY_NEGATIVE_THRESHOLD
            else "not_recovered"
        )
    return "not_evaluated"


@dataclass
class RecoveryEntry:
    """Comparison outcome for a single planted/decoy relationship."""

    relationship_id: str
    relationship_type: str
    expected_direction: str
    expected_strength: str
    observed_corr: float | None
    observed_metric: str | None
    scope: str
    status: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to a JSON-serializable dictionary."""
        return {
            "relationship_id": self.relationship_id,
            "relationship_type": self.relationship_type,
            "expected_direction": self.expected_direction,
            "expected_strength": self.expected_strength,
            "observed_corr": self.observed_corr,
            "observed_metric": self.observed_metric,
            "scope": self.scope,
            "status": self.status,
            "interpretation": self.interpretation,
        }


@dataclass
class RecoveryReport:
    """Full ground-truth recovery comparison report."""

    report_version: str = RECOVERY_REPORT_VERSION
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    seed: int | None = None
    entries: list[RecoveryEntry] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to a JSON-serializable dictionary."""
        return {
            "report_version": self.report_version,
            "generated_at": self.generated_at,
            "seed": self.seed,
            "summary": dict(self.summary),
            "entries": [e.to_dict() for e in self.entries],
        }

    def save(self, path: str | Path) -> Path:
        """Save the report to disk as JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> RecoveryReport:
        """Load a report back from a JSON file."""
        target = Path(path)
        data = json.loads(target.read_text(encoding="utf-8"))
        entries = [RecoveryEntry(**e) for e in data.get("entries", [])]
        return cls(
            report_version=data.get("report_version", RECOVERY_REPORT_VERSION),
            generated_at=data.get("generated_at", ""),
            seed=data.get("seed"),
            entries=entries,
            summary=dict(data.get("summary", {})),
        )


def _interpret_entry(
    relationship_id: str,
    expected_direction: str,
    observed_corr: float | None,
    status: str,
) -> str:
    """Build a non-causal human-readable interpretation for one entry."""
    if observed_corr is None:
        return (
            f"{relationship_id}: no observed association available; "
            "planted expectation not evaluated."
        )
    observed_desc = (
        f"observed Spearman association {observed_corr:.3f} "
        f"(planted expectation: {expected_direction})"
    )
    if status == "recovered":
        return f"{relationship_id}: recovered planted association; {observed_desc}."
    if status == "not_recovered":
        return f"{relationship_id}: planted association not recovered; {observed_desc}."
    if status == "correctly_no_association":
        return (
            f"{relationship_id}: decoy correctly shows no observed "
            f"monotonic association; {observed_desc}."
        )
    if status == "spurious_association":
        return (
            f"{relationship_id}: decoy shows a spurious observed "
            f"association (negative control); {observed_desc}."
        )
    return f"{relationship_id}: not evaluated; {observed_desc}."


def compare_ground_truth_recovery(
    ground_truth: Mapping[str, Any],
    observed_correlations: list[Mapping[str, Any]],
    *,
    scope: str = "overall",
    seed: int | None = None,
) -> RecoveryReport:
    """Compare planted ground truth against observed J4 correlations.

    Args:
        ground_truth: Ground-truth registry mapping with
            ``planted_relationships`` and ``decoy_relationship`` keys
            (as produced by ``GroundTruthRegistry.to_dict()``). The mapping
            is read, never modified.
        observed_correlations: J4 correlation rows (overall scope) as
            mappings with ``relationship_id``, ``spearman_raw`` and
            ``spearman_normalized`` keys.
        scope: Scope label recorded on each entry (default ``overall``).
        seed: Optional seed recorded on the report. When omitted, taken
            from ``ground_truth`` when present.

    Returns:
        Populated :class:`RecoveryReport` distinguishing planted,
        recovered, not recovered and decoy outcomes.
    """
    _check(isinstance(ground_truth, Mapping), "ground_truth must be a mapping")
    planted = list(ground_truth.get("planted_relationships", []))
    decoy = ground_truth.get("decoy_relationship")
    _check(isinstance(planted, list), "ground_truth missing 'planted_relationships'")
    _check(isinstance(decoy, Mapping), "ground_truth missing 'decoy_relationship'")

    observed_by_id: dict[str, Mapping[str, Any]] = {}
    for row in observed_correlations:
        rel_id = row.get("relationship_id")
        if rel_id is None:
            continue
        row_scope = row.get("scope", scope)
        if row_scope != scope and row.get("scope") is not None:
            # Prefer rows matching the requested scope; keep first match.
            if rel_id in observed_by_id:
                continue
        observed_by_id[str(rel_id)] = row

    resolved_seed = seed
    if resolved_seed is None:
        raw_seed = ground_truth.get("seed")
        resolved_seed = int(raw_seed) if raw_seed is not None else None

    entries: list[RecoveryEntry] = []
    for rel in list(planted) + [dict(decoy)]:
        rel_id = str(rel.get("id", "unknown"))
        rel_type = str(rel.get("relationship_type", "planted"))
        expected_direction = str(rel.get("expected_direction", "unknown"))
        expected_strength = str(rel.get("expected_strength", "unknown"))

        observed = observed_by_id.get(rel_id)
        if observed is None:
            status = "not_evaluated"
            observed_corr: float | None = None
            observed_metric: str | None = None
        else:
            observed_corr = select_primary_observation(observed)
            if "spearman_normalized" in observed and observed.get(
                "spearman_normalized"
            ) is not None:
                observed_metric = "spearman_normalized"
            else:
                observed_metric = "spearman_raw"
            status = classify_recovery(
                expected_direction, rel_type, observed_corr
            )

        entries.append(
            RecoveryEntry(
                relationship_id=rel_id,
                relationship_type=rel_type,
                expected_direction=expected_direction,
                expected_strength=expected_strength,
                observed_corr=observed_corr,
                observed_metric=observed_metric,
                scope=scope,
                status=status,
                interpretation=_interpret_entry(
                    rel_id, expected_direction, observed_corr, status
                ),
            )
        )

    summary: dict[str, int] = {
        "planted": sum(1 for e in entries if e.relationship_type == "planted"),
        "recovered": sum(1 for e in entries if e.status == "recovered"),
        "not_recovered": sum(1 for e in entries if e.status == "not_recovered"),
        "decoy": sum(1 for e in entries if e.relationship_type == "decoy"),
        "decoy_clean": sum(
            1 for e in entries if e.status == "correctly_no_association"
        ),
        "decoy_spurious": sum(
            1 for e in entries if e.status == "spurious_association"
        ),
        "not_evaluated": sum(1 for e in entries if e.status == "not_evaluated"),
    }

    return RecoveryReport(seed=resolved_seed, entries=entries, summary=summary)


def evaluate_recovery_from_paths(
    ground_truth_path: str | Path,
    correlations_path: str | Path,
    output_path: str | Path | None = None,
    *,
    scope: str = "overall",
) -> RecoveryReport:
    """Evaluate recovery from a registry file and J4 correlations on disk.

    Args:
        ground_truth_path: Path to ``ground_truth_registry.json``.
        correlations_path: Path to J4 overall correlations Parquet directory
            (``.../correlations/overall``) or a JSON file containing a list
            of correlation rows.
        output_path: Optional path to save the JSON recovery report.
            Defaults to ``reports/recovery/ground_truth_recovery.json`` when
            omitted.
        scope: Correlation scope to compare (default ``overall``).

    Returns:
        The populated :class:`RecoveryReport` (also saved to disk).
    """
    gt_path = Path(ground_truth_path)
    _check(gt_path.exists(), f"Ground-truth file not found: {gt_path}")
    ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))

    corr_path = Path(correlations_path)
    _check(corr_path.exists(), f"Correlations path not found: {corr_path}")
    if corr_path.suffix == ".json":
        observed = json.loads(corr_path.read_text(encoding="utf-8"))
        if isinstance(observed, dict):
            observed = observed.get("entries", observed)
        observed_rows = list(observed)
    else:
        # Parquet directory: small result set (one row per relationship), so
        # a local read of the tiny output is intentional and bounded.
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ValueError(
                "pyarrow is required to read Parquet correlations output"
            ) from exc
        table = pq.read_table(str(corr_path))
        observed_rows = table.to_pylist()

    report = compare_ground_truth_recovery(
        ground_truth,
        observed_rows,
        scope=scope,
        seed=ground_truth.get("seed"),
    )
    target = Path(output_path) if output_path is not None else DEFAULT_RECOVERY_REPORT_PATH
    report.save(target)
    return report
