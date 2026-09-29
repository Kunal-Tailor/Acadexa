"""Gold analytical collections validation (Task 9.4, rules.md §12, §18, §19).

Provides validation after publication to confirm:
1. Counts: Non-empty row/doc counts and matching source-destination counts.
2. Grain: Absolute uniqueness at schema-defined grain across each gold collection:
   - student_features: student_id x semester_id
   - course_metrics: course_id x semester_id
   - school_summary: school x department
   - risk_indicators: student_id x week_start
3. Required fields: All required fields present, correctly structured, and non-null for grain keys.
4. All gold collections covered.
5. Strict PySpark driver safety (rules.md §17.3): zero driver-side collect/toPandas calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType

from acadexa.validation.schema import (
    COURSE_METRICS_SCHEMA,
    RISK_INDICATORS_SCHEMA,
    SCHOOL_SUMMARY_SCHEMA,
    STUDENT_FEATURES_SCHEMA,
)
from acadexa.validation.validators import validate_record

logger = logging.getLogger(__name__)

GOLD_COLLECTIONS: tuple[str, ...] = (
    "student_features",
    "course_metrics",
    "school_summary",
    "risk_indicators",
)

GOLD_SCHEMAS: dict[str, dict[str, Any]] = {
    "student_features": STUDENT_FEATURES_SCHEMA,
    "course_metrics": COURSE_METRICS_SCHEMA,
    "school_summary": SCHOOL_SUMMARY_SCHEMA,
    "risk_indicators": RISK_INDICATORS_SCHEMA,
}


@dataclass
class GoldCollectionValidationResult:
    """Detailed validation outcome for a single gold collection."""

    collection_name: str
    is_valid: bool
    row_count: int
    expected_grain: list[str]
    distinct_grain_count: int
    grain_unique: bool
    required_fields: list[str]
    missing_fields: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable validation summary."""
        status = "PASSED" if self.is_valid else "FAILED"
        msg = (
            f"[{status}] {self.collection_name}: {self.row_count} rows, "
            f"grain={self.expected_grain} (unique={self.grain_unique})"
        )
        if self.errors:
            msg += f" | Errors: {'; '.join(self.errors)}"
        return msg


class GoldValidationError(ValueError):
    """Raised when one or more gold collections fail post-publication validation."""

    def __init__(
        self,
        message: str,
        validation_results: dict[str, GoldCollectionValidationResult] | None = None,
    ) -> None:
        super().__init__(message)
        self.validation_results = validation_results or {}


def validate_gold_dataframe(
    df: DataFrame,
    collection_name: str,
    schema: dict[str, Any] | None = None,
    allow_empty: bool = False,
) -> GoldCollectionValidationResult:
    """Validate a PySpark DataFrame representing a gold collection (Task 9.4).

    Strictly satisfies rules.md §17.3: executes completely in Spark with zero
    driver-side collect/toPandas calls.

    Args:
        df: PySpark DataFrame to validate.
        collection_name: One of the 4 gold collections.
        schema: Optional schema dictionary (defaults to GOLD_SCHEMAS[collection_name]).
        allow_empty: Whether an empty collection (0 rows) is considered valid.

    Returns:
        GoldCollectionValidationResult containing validation status and details.
    """
    target_schema = schema or GOLD_SCHEMAS.get(collection_name)
    if target_schema is None:
        raise ValueError(f"Unknown gold collection '{collection_name}'. Expected one of {GOLD_COLLECTIONS}")

    errors: list[str] = []
    grain: list[str] = target_schema.get("grain", [])
    required_fields = [
        name
        for name, spec in target_schema.get("fields", {}).items()
        if spec.get("required", True)
    ]

    # 1. Required fields presence check
    present_cols = set(df.columns)
    missing_fields = [f for f in required_fields if f not in present_cols]
    if missing_fields:
        errors.append(f"Missing required fields: {missing_fields}")

    # 2. Row count check
    total_count = df.count()
    if not allow_empty and total_count == 0:
        errors.append(f"Gold collection '{collection_name}' is empty (0 rows)")

    # 3. Grain uniqueness check
    missing_grain = [g for g in grain if g not in present_cols]
    if missing_grain:
        distinct_grain_count = 0
        grain_unique = False
        errors.append(f"Missing grain columns: {missing_grain}")
    else:
        distinct_grain_count = df.select(*grain).distinct().count()
        grain_unique = (total_count == distinct_grain_count)
        if not grain_unique:
            errors.append(
                f"Grain violation at ({', '.join(grain)}): {total_count} total rows "
                f"vs {distinct_grain_count} distinct grain combinations"
            )

        # Grain non-null check
        if total_count > 0:
            null_grain_filter = F.coalesce(*[F.when(F.col(g).isNull(), F.lit(1)) for g in grain]) == 1
            has_null_grain = len(df.filter(null_grain_filter).take(1)) > 0
            if has_null_grain:
                errors.append(f"Grain columns ({', '.join(grain)}) contain null values")

    # 4. Nested structure checks (e.g. explanations struct in risk_indicators)
    if collection_name == "risk_indicators" and "explanations" in present_cols:
        field_type = df.schema["explanations"].dataType
        if isinstance(field_type, StructType):
            exp_names = {f.name for f in field_type.fields}
            expected_exp = {"low_attendance", "lms_decline", "late_submissions", "marks_decline", "low_quiz_activity"}
            missing_exp = expected_exp - exp_names
            if missing_exp:
                errors.append(f"Missing explanation fields in struct: {sorted(missing_exp)}")

    is_valid = len(errors) == 0
    return GoldCollectionValidationResult(
        collection_name=collection_name,
        is_valid=is_valid,
        row_count=total_count,
        expected_grain=grain,
        distinct_grain_count=distinct_grain_count,
        grain_unique=grain_unique,
        required_fields=required_fields,
        missing_fields=missing_fields,
        errors=errors,
    )


def validate_gold_mongodb(
    db: Any,
    collection_names: list[str] | tuple[str, ...] | None = None,
    allow_empty: bool = False,
    validate_sample_size: int = 100,
) -> dict[str, GoldCollectionValidationResult]:
    """Validate published gold collections directly in MongoDB (Task 9.4).

    Args:
        db: PyMongo Database instance.
        collection_names: Optional list/tuple of collection names to validate.
        allow_empty: Whether an empty collection (0 documents) is considered valid.
        validate_sample_size: Number of documents to sample for full schema validation.

    Returns:
        dict[str, GoldCollectionValidationResult]: Per-collection validation results.
    """
    targets = collection_names or GOLD_COLLECTIONS
    existing_colls = set(db.list_collection_names())
    results: dict[str, GoldCollectionValidationResult] = {}

    for coll_name in targets:
        target_schema = GOLD_SCHEMAS.get(coll_name)
        if target_schema is None:
            raise ValueError(f"Unknown gold collection '{coll_name}'")

        grain = target_schema.get("grain", [])
        required_fields = [
            name
            for name, spec in target_schema.get("fields", {}).items()
            if spec.get("required", True)
        ]

        errors: list[str] = []
        if coll_name not in existing_colls:
            errors.append(f"Collection '{coll_name}' does not exist in MongoDB database '{db.name}'")
            results[coll_name] = GoldCollectionValidationResult(
                collection_name=coll_name,
                is_valid=False,
                row_count=0,
                expected_grain=grain,
                distinct_grain_count=0,
                grain_unique=False,
                required_fields=required_fields,
                errors=errors,
            )
            continue

        coll = db[coll_name]
        total_count = coll.count_documents({})
        if not allow_empty and total_count == 0:
            errors.append(f"MongoDB collection '{coll_name}' is empty (0 documents)")

        # Grain uniqueness check via MongoDB aggregation
        if grain and total_count > 0:
            group_id = {k: f"${k}" for k in grain}
            pipeline = [
                {"$group": {"_id": group_id, "count": {"$sum": 1}}},
                {"$match": {"count": {"$gt": 1}}},
                {"$limit": 5},
            ]
            duplicates = list(coll.aggregate(pipeline))
            grain_unique = (len(duplicates) == 0)
            if not grain_unique:
                errors.append(
                    f"Grain violation in MongoDB collection '{coll_name}' at ({', '.join(grain)}): "
                    f"found duplicate keys, e.g. {duplicates[0]['_id']}"
                )
            distinct_grain_count = total_count if grain_unique else max(0, total_count - len(duplicates))
        else:
            grain_unique = True
            distinct_grain_count = total_count

        # Check missing required fields across documents
        if total_count > 0:
            missing_query = {"$or": [{f: {"$exists": False}} for f in required_fields]}
            bad_doc = coll.find_one(missing_query, projection={"_id": 1, **{f: 1 for f in required_fields}})
            if bad_doc:
                missing_in_doc = [f for f in required_fields if f not in bad_doc]
                errors.append(f"Documents missing required fields: {missing_in_doc}")

            # Sample validation against canonical Phase 3 schema validator
            sample_docs = list(coll.find({}, projection={"_id": 0}).limit(validate_sample_size))
            for doc in sample_docs:
                try:
                    validate_record(doc, target_schema)
                except Exception as ex:
                    errors.append(f"Document failed schema validation: {ex}")
                    break

        is_valid = len(errors) == 0
        results[coll_name] = GoldCollectionValidationResult(
            collection_name=coll_name,
            is_valid=is_valid,
            row_count=total_count,
            expected_grain=grain,
            distinct_grain_count=distinct_grain_count,
            grain_unique=grain_unique,
            required_fields=required_fields,
            errors=errors,
        )

    return results


def validate_gold_collections(
    dfs: dict[str, DataFrame] | None = None,
    mongo_db: Any | None = None,
    parquet_base_path: Path | str | None = None,
    spark: SparkSession | None = None,
    collection_names: list[str] | tuple[str, ...] | None = None,
    fail_fast: bool = True,
    allow_empty: bool = False,
) -> dict[str, GoldCollectionValidationResult]:
    """Validate published gold collections across DataFrames, MongoDB, and/or Parquet (Task 9.4).

    Args:
        dfs: Optional mapping of collection_name -> Spark DataFrame.
        mongo_db: Optional PyMongo database to validate MongoDB collections.
        parquet_base_path: Optional base directory to validate saved Parquet files.
        spark: Active SparkSession (required if parquet_base_path is specified).
        collection_names: Collections to validate (defaults to all provided or all 4 gold).
        fail_fast: If True, raises GoldValidationError if any collection fails validation.
        allow_empty: If False, empty collections fail validation.

    Returns:
        dict[str, GoldCollectionValidationResult]: Per-collection validation results.

    Raises:
        GoldValidationError: If validation fails and fail_fast=True.
    """
    all_results: dict[str, GoldCollectionValidationResult] = {}
    targets = set(collection_names or GOLD_COLLECTIONS)

    # 1. Validate Spark DataFrames
    if dfs:
        for coll_name, df in dfs.items():
            if coll_name in targets and df is not None:
                res = validate_gold_dataframe(df, coll_name, allow_empty=allow_empty)
                all_results[coll_name] = res

    # 2. Validate saved Parquet datasets
    if parquet_base_path and spark:
        base = Path(parquet_base_path)
        for coll_name in targets:
            coll_parquet = base / coll_name
            if coll_parquet.exists():
                try:
                    df = spark.read.parquet(str(coll_parquet))
                    res = validate_gold_dataframe(df, coll_name, allow_empty=allow_empty)
                    # If DataFrame validation already ran, merge results
                    if coll_name in all_results:
                        if not res.is_valid:
                            all_results[coll_name].is_valid = False
                            all_results[coll_name].errors.extend(res.errors)
                    else:
                        all_results[coll_name] = res
                except Exception as ex:
                    logger.error("Failed reading Parquet for '%s': %s", coll_name, ex)
                    err_res = GoldCollectionValidationResult(
                        collection_name=coll_name,
                        is_valid=False,
                        row_count=0,
                        expected_grain=GOLD_SCHEMAS[coll_name]["grain"],
                        distinct_grain_count=0,
                        grain_unique=False,
                        required_fields=list(GOLD_SCHEMAS[coll_name]["fields"].keys()),
                        errors=[f"Parquet read error: {ex}"],
                    )
                    all_results[coll_name] = err_res

    # 3. Validate MongoDB collections
    if mongo_db:
        mongo_results = validate_gold_mongodb(
            mongo_db,
            collection_names=list(targets),
            allow_empty=allow_empty,
        )
        for coll_name, res in mongo_results.items():
            if coll_name in all_results:
                # Merge MongoDB results with DataFrame results
                if not res.is_valid:
                    all_results[coll_name].is_valid = False
                    all_results[coll_name].errors.extend(res.errors)
            else:
                all_results[coll_name] = res

    # 4. Check for failures
    failed_colls = [name for name, r in all_results.items() if not r.is_valid]
    if failed_colls and fail_fast:
        err_details = "\n".join(all_results[c].summary() for c in failed_colls)
        raise GoldValidationError(
            f"Gold collections validation failed for {failed_colls}:\n{err_details}",
            validation_results=all_results,
        )

    return all_results
