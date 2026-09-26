"""MongoDB core academic collections loader and count validation (task 6.3, rules.md §16).

Implements loading of the 5 core operational academic collections into MongoDB:
- ``students``
- ``courses``
- ``academic_records``
- ``attendance``
- ``coursework``

Provides strict count validation:
- Validates that records loaded equal records in source dataset.
- Verifies post-insert document counts against MongoDB.
- Validates loaded counts against generation manifests when provided.
- Preserves caller data immutability by copying records before PyMongo's in-place ``_id`` assignment.
- Normalizes ``datetime.date`` instances to ISO-8601 strings for PyMongo BSON encoder compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from pymongo.database import Database
from pymongo.errors import PyMongoError

from acadexa.database.client import (
    MongoDBConfig,
    MongoConnectionError,
    MongoError,
    get_database,
)
from acadexa.database.collections import (
    CORE_COLLECTIONS,
    init_database,
)


class LoadValidationError(MongoError):
    """Raised when document loading or count validation fails."""


@dataclass(frozen=True)
class CollectionLoadStatus:
    """Load and count validation status for a single MongoDB collection."""

    collection: str
    expected_count: int
    inserted_count: int
    actual_db_count: int
    validated: bool
    duration_sec: float

    def as_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation."""
        return {
            "collection": self.collection,
            "expected_count": self.expected_count,
            "inserted_count": self.inserted_count,
            "actual_db_count": self.actual_db_count,
            "validated": self.validated,
            "duration_sec": self.duration_sec,
        }


@dataclass(frozen=True)
class CoreLoadResult:
    """Comprehensive result of loading core academic collections into MongoDB."""

    database: str
    collections: dict[str, CollectionLoadStatus]
    total_expected: int
    total_inserted: int
    all_validated: bool
    duration_sec: float

    def as_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation."""
        return {
            "database": self.database,
            "total_expected": self.total_expected,
            "total_inserted": self.total_inserted,
            "all_validated": self.all_validated,
            "duration_sec": self.duration_sec,
            "collections": {k: v.as_dict() for k, v in self.collections.items()},
        }


def _prepare_document(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Prepare a record dictionary for safe MongoDB insertion.

    1. Shallow-copies the record dictionary so PyMongo's in-place ``_id``
       assignment does not mutate the caller's in-memory data structures.
    2. Converts Python ``datetime.date`` objects to ISO 8601 strings
       ("YYYY-MM-DD") because PyMongo's BSON encoder rejects ``date`` instances.
    """
    out: dict[str, Any] = {}
    for k, v in doc.items():
        if isinstance(v, date) and not isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, Mapping):
            out[k] = _prepare_document(v)
        elif isinstance(v, (list, tuple)):
            out[k] = [
                _prepare_document(item) if isinstance(item, Mapping)
                else item.isoformat() if (isinstance(item, date) and not isinstance(item, datetime))
                else item
                for item in v
            ]
        else:
            out[k] = v
    return out


def _load_json_file(path: Path | str) -> list[dict[str, Any]]:
    """Read and parse a JSON dataset file containing a list of records."""
    file_path = Path(path)
    if not file_path.is_file():
        raise LoadValidationError(f"Dataset file does not exist: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LoadValidationError(f"Invalid JSON in dataset file {file_path}: {exc}") from exc
    except OSError as exc:
        raise LoadValidationError(f"Failed to read dataset file {file_path}: {exc}") from exc

    if not isinstance(data, list):
        raise LoadValidationError(
            f"Dataset file {file_path} must contain a JSON array of records, got {type(data).__name__}"
        )
    return data


def load_core_collection(
    collection_name: str,
    records: Sequence[Mapping[str, Any]] | Path | str,
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    batch_size: int = 1000,
    clear_existing: bool = True,
    strict_validation: bool = True,
) -> CollectionLoadStatus:
    """Load documents into a single core academic collection with count validation.

    Args:
        collection_name: Target collection name (must be in CORE_COLLECTIONS).
        records: Sequence of record dictionaries, or Path/str to a JSON file.
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig. Uses default environment configuration if omitted.
        batch_size: Number of records to insert per batch.
        clear_existing: If True, deletes existing collection documents before insertion.
        strict_validation: If True, raises LoadValidationError when count mismatch occurs.

    Returns:
        CollectionLoadStatus detailing expected, inserted, and verified database counts.

    Raises:
        ValueError: if collection_name is not in CORE_COLLECTIONS.
        MongoConnectionError: if MongoDB cannot be reached.
        LoadValidationError: if count validation fails and strict_validation is True.
    """
    if collection_name not in CORE_COLLECTIONS:
        raise ValueError(
            f"Invalid collection '{collection_name}'. Expected one of {CORE_COLLECTIONS}"
        )

    if batch_size < 1:
        raise ValueError(f"batch_size must be positive integer, got {batch_size}")

    # Resolve dataset records
    if isinstance(records, (str, Path)):
        doc_list: Sequence[Mapping[str, Any]] = _load_json_file(records)
    else:
        doc_list = records

    expected_count = len(doc_list)
    start_time = time.perf_counter()

    # Resolve database and test connection
    cfg = config
    db = database if database is not None else get_database(cfg)
    try:
        db.client.admin.command("ping")
    except PyMongoError as exc:
        masked = cfg.masked_uri if cfg is not None else "MongoDB server"
        raise MongoConnectionError(f"Cannot connect to MongoDB at {masked}: {exc}") from exc

    coll = db[collection_name]

    # Clear existing if requested
    if clear_existing:
        try:
            coll.delete_many({})
        except PyMongoError as exc:
            raise LoadValidationError(
                f"Failed to clear collection '{collection_name}': {exc}"
            ) from exc

    # Batch insertion
    inserted_count = 0
    if expected_count > 0:
        for i in range(0, expected_count, batch_size):
            chunk = doc_list[i : i + batch_size]
            prepared_chunk = [_prepare_document(r) for r in chunk]
            try:
                res = coll.insert_many(prepared_chunk, ordered=True)
                inserted_count += len(res.inserted_ids)
            except PyMongoError as exc:
                raise LoadValidationError(
                    f"Failed inserting batch into '{collection_name}' at index {i}: {exc}"
                ) from exc

    # Query post-insertion count from MongoDB
    try:
        actual_db_count = coll.count_documents({})
    except PyMongoError as exc:
        raise LoadValidationError(
            f"Failed counting documents in collection '{collection_name}': {exc}"
        ) from exc

    duration_sec = round(time.perf_counter() - start_time, 3)

    # Validate count
    validated = (
        (actual_db_count == expected_count)
        if clear_existing
        else (inserted_count == expected_count)
    )

    if not validated and strict_validation:
        raise LoadValidationError(
            f"Count validation failed for collection '{collection_name}': "
            f"expected {expected_count} records, inserted {inserted_count}, "
            f"but MongoDB reports {actual_db_count} documents"
        )

    return CollectionLoadStatus(
        collection=collection_name,
        expected_count=expected_count,
        inserted_count=inserted_count,
        actual_db_count=actual_db_count,
        validated=validated,
        duration_sec=duration_sec,
    )


def load_core_academic_data(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    data_dir: Path | str | None = None,
    data: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    manifest_path: Path | str | None = None,
    batch_size: int = 1000,
    clear_existing: bool = True,
    strict_validation: bool = True,
    ensure_initialized: bool = True,
) -> CoreLoadResult:
    """Load all 5 core academic collections into MongoDB with inserted count validation.

    The 5 core collections are:
    - ``students``
    - ``courses``
    - ``academic_records``
    - ``attendance``
    - ``coursework``

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig. Uses default environment configuration if omitted.
        data_dir: Optional directory containing <collection>.json files (defaults to 'data/generated').
        data: Optional in-memory mapping of collection name to records. Takes precedence over data_dir.
        manifest_path: Optional path to generation_manifest.json to validate counts against.
        batch_size: Number of records to insert per batch.
        clear_existing: If True, clears existing documents before insertion.
        strict_validation: If True, raises LoadValidationError on count mismatch.
        ensure_initialized: If True, ensures database and collection placeholders exist prior to loading.

    Returns:
        CoreLoadResult with status and metrics for all 5 core collections.

    Raises:
        MongoConnectionError: if database cannot be reached.
        LoadValidationError: if any core collection is missing or count validation fails.
    """
    start_time = time.perf_counter()
    cfg = config
    db = database if database is not None else get_database(cfg)

    # Ensure database collections exist
    if ensure_initialized:
        init_database(database=db, config=cfg, create_gold_placeholders=True)

    # Load generation manifest if provided
    manifest_counts: dict[str, int] | None = None
    if manifest_path is not None:
        mf_path = Path(manifest_path)
        if not mf_path.is_file():
            raise LoadValidationError(f"Generation manifest not found at {mf_path}")
        try:
            mf_data = json.loads(mf_path.read_text(encoding="utf-8"))
            manifest_counts = mf_data.get("actual_counts", {})
        except Exception as exc:
            raise LoadValidationError(f"Failed to read generation manifest {mf_path}: {exc}") from exc

    # Resolve sources for each core collection
    effective_data_dir = Path(data_dir) if data_dir is not None else Path("data/generated")

    collection_statuses: dict[str, CollectionLoadStatus] = {}
    total_expected = 0
    total_inserted = 0

    for name in CORE_COLLECTIONS:
        # 1. Resolve records
        if data is not None and name in data:
            records: Sequence[Mapping[str, Any]] | Path = data[name]
        else:
            json_file = effective_data_dir / f"{name}.json"
            if not json_file.is_file():
                raise LoadValidationError(
                    f"Core collection file missing for '{name}' at {json_file}. "
                    f"Provide 'data' mapping or ensure '{effective_data_dir}' contains '{name}.json'."
                )
            records = json_file

        # 2. Load collection
        status = load_core_collection(
            collection_name=name,
            records=records,
            database=db,
            config=cfg,
            batch_size=batch_size,
            clear_existing=clear_existing,
            strict_validation=strict_validation,
        )

        # 3. Validate against generation manifest if provided
        if manifest_counts is not None and name in manifest_counts:
            expected_mf = manifest_counts[name]
            if status.actual_db_count != expected_mf:
                if strict_validation:
                    raise LoadValidationError(
                        f"Manifest count mismatch for '{name}': manifest recorded {expected_mf} "
                        f"records, but MongoDB contains {status.actual_db_count} documents"
                    )

        collection_statuses[name] = status
        total_expected += status.expected_count
        total_inserted += status.inserted_count

    all_validated = all(s.validated for s in collection_statuses.values())
    total_duration = round(time.perf_counter() - start_time, 3)

    return CoreLoadResult(
        database=db.name,
        collections=collection_statuses,
        total_expected=total_expected,
        total_inserted=total_inserted,
        all_validated=all_validated,
        duration_sec=total_duration,
    )
