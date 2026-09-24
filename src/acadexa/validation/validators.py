"""Record-level validation against the Phase 3 schema contract.

Checks required fields, data types, identifier formats (patterns),
numeric ranges, enum membership, list constraints, nested object
fields, and record-grain uniqueness across a collection of records.

Raises :class:`SchemaError` with a specific message on the first
failure, mirroring the configuration validator's fail-fast style.

Notes:

- Declarative ``invariants`` strings in schemas are documentation for
  consumers and are not executed here.
- Unknown record keys (such as MongoDB's ``_id``) are ignored.
- An ``int`` is accepted where a schema declares ``float``; ``bool``
  is never accepted where ``int`` or ``float`` is declared.
"""

from __future__ import annotations

import re
from typing import Any


class SchemaError(ValueError):
    """Raised when a record fails schema validation."""


def _check(condition: bool, message: str) -> None:
    """Raise SchemaError with ``message`` when ``condition`` is false."""
    if not condition:
        raise SchemaError(message)


def _validate_value(value: Any, spec: dict[str, Any], context: str) -> None:
    """Validate one field value against its field specification."""
    if value is None:
        _check(spec.get("nullable", False), f"{context}: value may not be null")
        return

    expected = spec["type"]
    if expected is float:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
    else:
        ok = isinstance(value, expected)
    _check(
        ok,
        f"{context}: expected {expected.__name__}, got {type(value).__name__}",
    )

    if "pattern" in spec:
        _check(
            re.match(spec["pattern"], value) is not None,
            f"{context}: {value!r} does not match pattern {spec['pattern']!r}",
        )
    if "enum" in spec:
        _check(
            value in spec["enum"],
            f"{context}: {value!r} is not one of {spec['enum']}",
        )
    if expected in (int, float):
        if "min" in spec:
            _check(
                value >= spec["min"],
                f"{context}: {value!r} is below minimum {spec['min']}",
            )
        if "max" in spec:
            _check(
                value <= spec["max"],
                f"{context}: {value!r} is above maximum {spec['max']}",
            )

    if expected is dict:
        for name, subspec in spec.get("fields", {}).items():
            if name not in value:
                _check(
                    not subspec.get("required", True),
                    f"{context}.{name}: missing required field",
                )
                continue
            _validate_value(value[name], subspec, f"{context}.{name}")
    elif expected is list:
        if "min_items" in spec:
            _check(
                len(value) >= spec["min_items"],
                f"{context}: expected at least {spec['min_items']} item(s), "
                f"got {len(value)}",
            )
        if "item_type" in spec:
            item_spec: dict[str, Any] = {"type": spec["item_type"]}
            for bound in ("min", "max"):
                if bound in spec:
                    item_spec[bound] = spec[bound]
            for index, item in enumerate(value):
                _validate_value(item, item_spec, f"{context}[{index}]")


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate one record against ``schema``.

    Verifies required fields, data types, identifier formats, numeric
    ranges, enums, list constraints and nested object fields.

    Raises:
        SchemaError: on the first violation.
    """
    collection = schema["collection"]
    _check(
        isinstance(record, dict),
        f"{collection}: record must be a mapping, got {type(record).__name__}",
    )
    for name, spec in schema["fields"].items():
        required = spec.get("required", True)
        if name not in record:
            _check(not required, f"{collection}: missing required field '{name}'")
            continue
        _validate_value(record[name], spec, f"{collection}: field '{name}'")


def _freeze(value: Any) -> Any:
    """Convert a value into a hashable form for grain-key comparison."""
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(sub)) for key, sub in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def validate_records(records: list[dict[str, Any]], schema: dict[str, Any]) -> None:
    """Validate every record and enforce uniqueness at the schema grain.

    Each record is checked with :func:`validate_record`; the grain key
    (the schema's ``grain`` fields) must then be unique across the
    batch, per rules.md §12.

    Raises:
        SchemaError: on the first violation or duplicate grain key.
    """
    grain = schema["grain"]
    collection = schema["collection"]
    seen: set[tuple] = set()
    for position, record in enumerate(records):
        validate_record(record, schema)
        key = tuple(_freeze(record[name]) for name in grain)
        _check(
            key not in seen,
            f"{collection}: duplicate record at grain "
            f"({', '.join(grain)}) at index {position}",
        )
        seen.add(key)
