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
from datetime import date, datetime, time as dttime, timezone
import json
from pathlib import Path
import time
from typing import Any, Iterable, Mapping, Sequence

import pyarrow as pa
import pyarrow.dataset as ds
from pymongo.database import Database
from pymongo.errors import PyMongoError

from acadexa.config import config_path, load_config_file
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

DEFAULT_LMS_SLICE_SCHOOLS: tuple[str, ...] = ("CET", "SOM")
DEFAULT_LMS_SLICE_SEMESTER: str = "S4"


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


# ─────────────────────────────────────────────────────────────────────────────
# LMS Serving Slice Loading (Task 6.4, Rules.md §9, §16.2, Architecture.md §14)
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_lms_dt(val: Any) -> datetime:
    """Normalize datetime, date, string, or PyArrow timestamp to naive UTC datetime."""
    if isinstance(val, str):
        val_clean = val.strip()
        for fmt in (
            None,
            "%Y/%m/%d %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ):
            if fmt is None:
                try:
                    dt = datetime.fromisoformat(val_clean.replace("Z", "+00:00"))
                    break
                except ValueError:
                    continue
            else:
                try:
                    dt = datetime.strptime(val_clean, fmt)
                    break
                except ValueError:
                    continue
        else:
            raise ValueError(f"Cannot parse timestamp: {val!r}")
    elif isinstance(val, date) and not isinstance(val, datetime):
        dt = datetime.combine(val, dttime.min)
    elif isinstance(val, datetime):
        dt = val
    elif hasattr(val, "as_py"):
        py_val = val.as_py()
        if isinstance(py_val, datetime):
            dt = py_val
        elif isinstance(py_val, str):
            return _normalize_lms_dt(py_val)
        else:
            raise TypeError(f"Unsupported Arrow timestamp type: {type(py_val).__name__}")
    else:
        raise TypeError(f"Expected datetime, date, or str, got {type(val).__name__}")

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@dataclass(frozen=True)
class LMSServingSliceSpec:
    """Specification defining the operational LMS serving slice loaded into MongoDB.

    Per rules.md §9, §16.2 and architecture.md §14:
    - Slice covers: Latest semester (S4) + Schools: Computer Engineering & Technology (CET) + Business (SOM).
    - Full LMS event dataset remains in raw Parquet; only this slice enters MongoDB.
    """

    schools: tuple[str, ...] = DEFAULT_LMS_SLICE_SCHOOLS
    semester_id: str = DEFAULT_LMS_SLICE_SEMESTER
    start_date: datetime | date | None = None
    end_date: datetime | date | None = None

    @classmethod
    def from_config(
        cls,
        semester_id: str = DEFAULT_LMS_SLICE_SEMESTER,
        schools: Sequence[str] = DEFAULT_LMS_SLICE_SCHOOLS,
    ) -> LMSServingSliceSpec:
        """Resolve slice specification from academic calendar configuration.

        Looks up semester bounds in config/university/academic_periods.toml.
        """
        start_d: date | datetime | None = None
        end_d: date | datetime | None = None
        try:
            cfg_p = config_path("university", "academic_periods.toml")
            if cfg_p.is_file():
                cal = load_config_file(cfg_p)
                semesters = cal.get("semesters", {})
                if semester_id in semesters:
                    sem = semesters[semester_id]
                    start_d = sem.get("start_date")
                    end_d = sem.get("end_date")
        except Exception:
            pass

        # Fallback to configured S4 calendar dates if config lookup was unavailable
        if start_d is None:
            start_d = date(2026, 1, 5)
        if end_d is None:
            end_d = date(2026, 4, 26)

        return cls(
            schools=tuple(s.strip().upper() for s in schools),
            semester_id=semester_id,
            start_date=start_d,
            end_date=end_d,
        )

    def matches(self, record: Mapping[str, Any]) -> bool:
        """Return True if an LMS event record falls within the serving slice."""
        meta = record.get("meta")
        if not isinstance(meta, Mapping):
            return False
        school = str(meta.get("school", "")).strip().upper()
        if not school or school not in self.schools:
            return False

        ts = record.get("timestamp")
        if ts is None:
            return False

        try:
            dt = _normalize_lms_dt(ts)
        except (ValueError, TypeError):
            return False

        if self.start_date is not None:
            s_dt = _normalize_lms_dt(self.start_date)
            if dt < s_dt:
                return False

        if self.end_date is not None:
            e_dt = _normalize_lms_dt(self.end_date)
            if isinstance(self.end_date, date) and not isinstance(self.end_date, datetime):
                e_dt = e_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            if dt > e_dt:
                return False

        return True

    def as_dict(self) -> dict[str, Any]:
        """Return serializable representation of slice specification."""
        return {
            "schools": list(self.schools),
            "semester_id": self.semester_id,
            "start_date": self.start_date.isoformat() if self.start_date is not None else None,
            "end_date": self.end_date.isoformat() if self.end_date is not None else None,
        }


@dataclass(frozen=True)
class LMSSliceLoadResult:
    """Detailed result of loading the LMS serving slice into MongoDB."""

    database: str
    collection: str
    total_scanned: int
    slice_selected: int
    inserted_count: int
    actual_db_count: int
    spec: LMSServingSliceSpec
    validated: bool
    duration_sec: float

    def as_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation."""
        return {
            "database": self.database,
            "collection": self.collection,
            "total_scanned": self.total_scanned,
            "slice_selected": self.slice_selected,
            "inserted_count": self.inserted_count,
            "actual_db_count": self.actual_db_count,
            "validated": self.validated,
            "duration_sec": self.duration_sec,
            "spec": self.spec.as_dict(),
        }


def stream_lms_slice_records(
    parquet_path: Path | str,
    spec: LMSServingSliceSpec | None = None,
    *,
    batch_size: int = 5000,
) -> Iterable[list[dict[str, Any]]]:
    """Yield memory-bounded batches of LMS events matching the serving slice from Parquet.

    Args:
        parquet_path: Root path of the partitioned LMS Parquet dataset.
        spec: Optional slice specification (defaults to latest semester, schools CET & SOM).
        batch_size: Batch size of yielded event lists.

    Yields:
        Lists of prepared LMS event dictionaries matching the serving slice.
    """
    p_path = Path(parquet_path)
    if not p_path.exists():
        raise LoadValidationError(f"LMS Parquet dataset path not found: {p_path}")

    slice_spec = spec if spec is not None else LMSServingSliceSpec.from_config()

    try:
        dataset = ds.dataset(p_path, format="parquet", partitioning="hive")
    except Exception as exc:
        raise LoadValidationError(f"Failed opening LMS Parquet dataset at {p_path}: {exc}") from exc

    # Push down year/month partition filter if bounds exist within the same calendar year
    pushdown_filter = None
    if slice_spec.start_date is not None and slice_spec.end_date is not None:
        s_d = slice_spec.start_date if isinstance(slice_spec.start_date, date) else slice_spec.start_date.date()
        e_d = slice_spec.end_date if isinstance(slice_spec.end_date, date) else slice_spec.end_date.date()
        if s_d.year == e_d.year:
            pushdown_filter = (
                (ds.field("year") == s_d.year)
                & (ds.field("month") >= s_d.month)
                & (ds.field("month") <= e_d.month)
            )

    try:
        scanner = dataset.scanner(filter=pushdown_filter, batch_size=batch_size)
    except Exception as exc:
        raise LoadValidationError(f"Failed scanning Parquet dataset: {exc}") from exc

    buffer: list[dict[str, Any]] = []
    for batch in scanner.to_batches():
        for row in batch.to_pylist():
            if slice_spec.matches(row):
                doc = {
                    "timestamp": _normalize_lms_dt(row["timestamp"]),
                    "meta": {
                        "student_id": row["meta"]["student_id"],
                        "course_id": row["meta"]["course_id"],
                        "school": str(row["meta"]["school"]).strip().upper(),
                    },
                    "activity_type": row["activity_type"],
                    "resource_id": row.get("resource_id"),
                    "duration_sec": row.get("duration_sec"),
                    "session_id": row["session_id"],
                }
                buffer.append(doc)
                if len(buffer) >= batch_size:
                    yield buffer
                    buffer = []

    if buffer:
        yield buffer


def load_lms_serving_slice(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    parquet_path: Path | str | None = None,
    records: Iterable[Mapping[str, Any]] | None = None,
    spec: LMSServingSliceSpec | None = None,
    batch_size: int = 2000,
    clear_existing: bool = True,
    strict_validation: bool = True,
    ensure_initialized: bool = True,
) -> LMSSliceLoadResult:
    """Load the defined LMS operational serving slice into MongoDB (task 6.4, rules.md §9, §16.2).

    Only the operational slice is stored in MongoDB:
    - Latest semester (S4)
    - Computer Engineering & Technology (CET) + School of Management/Business (SOM)

    The full event history remains in raw Parquet outside MongoDB.

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig. Uses default environment configuration if omitted.
        parquet_path: Optional path to raw LMS Parquet dataset (defaults to 'data/raw/lms_events').
        records: Optional in-memory iterable of event records (overrides parquet_path).
        spec: Optional slice specification (defaults to latest semester, schools CET & SOM).
        batch_size: Number of documents per insert_many batch.
        clear_existing: If True, clears existing documents in lms_events before inserting.
        strict_validation: If True, raises LoadValidationError on count mismatch.
        ensure_initialized: If True, ensures database time-series collection exists prior to load.

    Returns:
        LMSSliceLoadResult with metrics on scanned, selected, inserted, and verified counts.

    Raises:
        MongoConnectionError: if MongoDB cannot be reached.
        LoadValidationError: if count validation fails or Parquet dataset is missing.
    """
    start_time = time.perf_counter()
    cfg = config
    db = database if database is not None else get_database(cfg)

    # Verify connectivity
    try:
        db.client.admin.command("ping")
    except PyMongoError as exc:
        masked = cfg.masked_uri if cfg is not None else "MongoDB server"
        raise MongoConnectionError(f"Cannot connect to MongoDB at {masked}: {exc}") from exc

    # Ensure collection exists as time-series
    if ensure_initialized:
        init_database(database=db, config=cfg, create_gold_placeholders=True)

    slice_spec = spec if spec is not None else LMSServingSliceSpec.from_config()
    coll = db["lms_events"]

    if clear_existing:
        try:
            coll.delete_many({})
        except PyMongoError as exc:
            raise LoadValidationError(f"Failed clearing collection 'lms_events': {exc}") from exc

    total_scanned = 0
    slice_selected = 0
    inserted_count = 0

    if records is not None:
        # In-memory stream or list
        buffer: list[dict[str, Any]] = []
        for rec in records:
            total_scanned += 1
            if slice_spec.matches(rec):
                slice_selected += 1
                doc = {
                    "timestamp": _normalize_lms_dt(rec["timestamp"]),
                    "meta": {
                        "student_id": rec["meta"]["student_id"],
                        "course_id": rec["meta"]["course_id"],
                        "school": str(rec["meta"]["school"]).strip().upper(),
                    },
                    "activity_type": rec["activity_type"],
                    "resource_id": rec.get("resource_id"),
                    "duration_sec": rec.get("duration_sec"),
                    "session_id": rec["session_id"],
                }
                buffer.append(doc)
                if len(buffer) >= batch_size:
                    try:
                        res = coll.insert_many(buffer, ordered=True)
                        inserted_count += len(res.inserted_ids)
                    except PyMongoError as exc:
                        raise LoadValidationError(f"Failed inserting LMS slice batch: {exc}") from exc
                    buffer = []

        if buffer:
            try:
                res = coll.insert_many(buffer, ordered=True)
                inserted_count += len(res.inserted_ids)
            except PyMongoError as exc:
                raise LoadValidationError(f"Failed inserting LMS slice batch: {exc}") from exc
            buffer = []

    else:
        # Parquet source
        effective_path = Path(parquet_path) if parquet_path is not None else Path("data/raw/lms_events")
        if not effective_path.exists():
            raise LoadValidationError(f"LMS Parquet dataset directory not found at: {effective_path}")

        try:
            dataset = ds.dataset(effective_path, format="parquet", partitioning="hive")
        except Exception as exc:
            raise LoadValidationError(f"Failed opening LMS Parquet dataset at {effective_path}: {exc}") from exc

        pushdown_filter = None
        if slice_spec.start_date is not None and slice_spec.end_date is not None:
            s_d = slice_spec.start_date if isinstance(slice_spec.start_date, date) else slice_spec.start_date.date()
            e_d = slice_spec.end_date if isinstance(slice_spec.end_date, date) else slice_spec.end_date.date()
            if s_d.year == e_d.year:
                pushdown_filter = (
                    (ds.field("year") == s_d.year)
                    & (ds.field("month") >= s_d.month)
                    & (ds.field("month") <= e_d.month)
                )

        try:
            scanner = dataset.scanner(filter=pushdown_filter, batch_size=batch_size)
        except Exception as exc:
            raise LoadValidationError(f"Failed scanning Parquet dataset: {exc}") from exc

        buffer = []
        for batch in scanner.to_batches():
            total_scanned += len(batch)
            for row in batch.to_pylist():
                if slice_spec.matches(row):
                    slice_selected += 1
                    doc = {
                        "timestamp": _normalize_lms_dt(row["timestamp"]),
                        "meta": {
                            "student_id": row["meta"]["student_id"],
                            "course_id": row["meta"]["course_id"],
                            "school": str(row["meta"]["school"]).strip().upper(),
                        },
                        "activity_type": row["activity_type"],
                        "resource_id": row.get("resource_id"),
                        "duration_sec": row.get("duration_sec"),
                        "session_id": row["session_id"],
                    }
                    buffer.append(doc)
                    if len(buffer) >= batch_size:
                        try:
                            res = coll.insert_many(buffer, ordered=True)
                            inserted_count += len(res.inserted_ids)
                        except PyMongoError as exc:
                            raise LoadValidationError(f"Failed inserting LMS slice batch: {exc}") from exc
                        buffer = []

        if buffer:
            try:
                res = coll.insert_many(buffer, ordered=True)
                inserted_count += len(res.inserted_ids)
            except PyMongoError as exc:
                raise LoadValidationError(f"Failed inserting LMS slice batch: {exc}") from exc
            buffer = []

    # Query MongoDB post-insertion count
    try:
        actual_db_count = coll.count_documents({})
    except PyMongoError as exc:
        raise LoadValidationError(f"Failed counting documents in collection 'lms_events': {exc}") from exc

    duration_sec = round(time.perf_counter() - start_time, 3)

    validated = (
        (actual_db_count == slice_selected)
        if clear_existing
        else (inserted_count == slice_selected)
    )

    if not validated and strict_validation:
        raise LoadValidationError(
            f"LMS serving slice count validation failed: expected {slice_selected} events, "
            f"inserted {inserted_count}, but MongoDB reports {actual_db_count} documents in collection 'lms_events'"
        )

    return LMSSliceLoadResult(
        database=db.name,
        collection="lms_events",
        total_scanned=total_scanned,
        slice_selected=slice_selected,
        inserted_count=inserted_count,
        actual_db_count=actual_db_count,
        spec=slice_spec,
        validated=validated,
        duration_sec=duration_sec,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Development Database Loading Entry Workflow (Task 6.7, Rules.md §9, §16)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DatabaseLoadSummary:
    """Complete summary of a full development database loading and verification run."""

    database: str
    core_result: CoreLoadResult
    lms_result: LMSSliceLoadResult | None
    indexes: dict[str, list[str]]
    manifest_path: Path | None
    manifest_verified: bool
    total_documents: int
    duration_sec: float

    def as_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation."""
        return {
            "database": self.database,
            "core_result": self.core_result.as_dict(),
            "lms_result": self.lms_result.as_dict() if self.lms_result is not None else None,
            "indexes": self.indexes,
            "manifest_path": str(self.manifest_path) if self.manifest_path is not None else None,
            "manifest_verified": self.manifest_verified,
            "total_documents": self.total_documents,
            "duration_sec": self.duration_sec,
        }


def load_development_database(
    database: Database | None = None,
    config: MongoDBConfig | None = None,
    *,
    data_dir: Path | str | None = None,
    lms_parquet_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    spec: LMSServingSliceSpec | None = None,
    batch_size: int = 2000,
    clear_existing: bool = True,
    strict_validation: bool = True,
    load_lms: bool = True,
    create_indexes: bool = True,
) -> DatabaseLoadSummary:
    """Load core collections and LMS serving slice into MongoDB and verify counts (task 6.7).

    Executes the full development-scale database loading workflow:
    1. Connects to MongoDB using environment or supplied configuration.
    2. Initializes core collections, time-series LMS collection, and gold placeholders.
    3. Loads the 5 core collections with count verification against generation manifests.
    4. Loads the LMS operational serving slice (latest semester, schools CET & SOM) from Parquet.
    5. Creates documented query indexes across collections.
    6. Produces a comprehensive verification report.

    Args:
        database: Optional pymongo Database instance.
        config: Optional MongoDBConfig.
        data_dir: Directory containing core collection JSON files (defaults to 'data/generated').
        lms_parquet_path: Path to raw LMS Parquet dataset (defaults to 'data/raw/lms_events').
        manifest_path: Path to generation manifest for verification (defaults to 'data/manifests/generation_manifest.json').
        spec: Optional LMS serving slice specification.
        batch_size: Batch size for insertions.
        clear_existing: If True, clears existing documents before loading.
        strict_validation: If True, raises LoadValidationError on count mismatch.
        load_lms: If True, loads the LMS operational slice.
        create_indexes: If True, creates documented query indexes after loading.

    Returns:
        DatabaseLoadSummary with full metrics and verification status.

    Raises:
        MongoConnectionError: if database cannot be reached.
        LoadValidationError: if any count validation fails.
    """
    start_time = time.perf_counter()
    cfg = config
    db = database if database is not None else get_database(cfg)

    # 1. Verify connectivity and initialize database collections
    init_database(database=db, config=cfg, create_gold_placeholders=True)

    # 2. Resolve paths
    effective_data_dir = Path(data_dir) if data_dir is not None else Path("data/generated")
    effective_lms_path = Path(lms_parquet_path) if lms_parquet_path is not None else Path("data/raw/lms_events")
    effective_manifest_path = (
        Path(manifest_path)
        if manifest_path is not None
        else Path("data/manifests/generation_manifest.json")
    )

    manifest_verified = False
    resolved_manifest: Path | None = None
    if effective_manifest_path.is_file():
        resolved_manifest = effective_manifest_path
        manifest_verified = True
    elif strict_validation and manifest_path is not None:
        raise LoadValidationError(f"Generation manifest file not found: {effective_manifest_path}")

    # 3. Load 5 Core Academic Collections
    core_result = load_core_academic_data(
        database=db,
        config=cfg,
        data_dir=effective_data_dir,
        manifest_path=resolved_manifest,
        batch_size=batch_size,
        clear_existing=clear_existing,
        strict_validation=strict_validation,
        ensure_initialized=False,
    )

    # 4. Load LMS Operational Serving Slice
    lms_result: LMSSliceLoadResult | None = None
    if load_lms:
        if not effective_lms_path.exists():
            if strict_validation:
                raise LoadValidationError(f"LMS Parquet dataset not found at {effective_lms_path}")
        else:
            lms_result = load_lms_serving_slice(
                database=db,
                config=cfg,
                parquet_path=effective_lms_path,
                spec=spec,
                batch_size=batch_size,
                clear_existing=clear_existing,
                strict_validation=strict_validation,
                ensure_initialized=False,
            )

    # 5. Create Documented Query Indexes
    indexes_created: dict[str, list[str]] = {}
    if create_indexes:
        from acadexa.database.indexes import create_database_indexes

        indexes_created = create_database_indexes(
            database=db,
            config=cfg,
            ensure_collections=False,
        )

    # 6. Total documents
    total_docs = core_result.total_inserted + (lms_result.inserted_count if lms_result else 0)
    duration_sec = round(time.perf_counter() - start_time, 3)

    return DatabaseLoadSummary(
        database=db.name,
        core_result=core_result,
        lms_result=lms_result,
        indexes=indexes_created,
        manifest_path=resolved_manifest,
        manifest_verified=manifest_verified,
        total_documents=total_docs,
        duration_sec=duration_sec,
    )

