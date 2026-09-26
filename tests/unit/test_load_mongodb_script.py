"""Unit tests for scripts/load_mongodb.py CLI entry point (task 6.7, rules.md §9, §16)."""

from __future__ import annotations

from pathlib import Path
import pytest

from acadexa.database import (
    MongoDBConfig,
    close_mongo_client,
    get_database,
    get_mongo_client,
)
from scripts.load_mongodb import main, parse_args


def test_parse_args_defaults() -> None:
    """Verify default CLI arguments for load_mongodb."""
    args = parse_args([])
    assert args.data_dir == "data/generated"
    assert args.lms_parquet_path == "data/raw/lms_events"
    assert args.manifest_path == "data/manifests/generation_manifest.json"
    assert args.batch_size == 2000
    assert args.skip_lms is False
    assert args.skip_indexes is False
    assert args.skip_manifest_check is False
    assert args.no_clear is False
    assert args.quiet is False


def test_parse_args_custom() -> None:
    """Verify custom CLI flag parsing."""
    args = parse_args(
        [
            "--data-dir", "custom/data",
            "--lms-parquet-path", "custom/lms",
            "--manifest-path", "custom/manifest.json",
            "--database", "custom_db",
            "--uri", "mongodb://localhost:27017",
            "--batch-size", "500",
            "--skip-lms",
            "--skip-indexes",
            "--skip-manifest-check",
            "--no-clear",
            "--quiet",
        ]
    )
    assert args.data_dir == "custom/data"
    assert args.lms_parquet_path == "custom/lms"
    assert args.manifest_path == "custom/manifest.json"
    assert args.database == "custom_db"
    assert args.uri == "mongodb://localhost:27017"
    assert args.batch_size == 500
    assert args.skip_lms is True
    assert args.skip_indexes is True
    assert args.skip_manifest_check is True
    assert args.no_clear is True
    assert args.quiet is True


def test_main_cli_execution_with_test_db() -> None:
    """Verify end-to-end CLI script execution against an isolated database."""
    test_db_name = "test_acadexa_cli_load"
    cfg = MongoDBConfig(database=test_db_name)
    client = get_mongo_client(cfg)

    try:
        # Run script targeting test database
        exit_code = main(
            [
                "--database", test_db_name,
                "--batch-size", "5000",
                "--quiet",
            ]
        )
        assert exit_code == 0

        db = get_database(cfg, client=client)
        assert db["students"].count_documents({}) == 36
        assert db["courses"].count_documents({}) == 72
        assert db["academic_records"].count_documents({}) == 864
        assert db["attendance"].count_documents({}) == 13824
        assert db["coursework"].count_documents({}) == 9964
        assert db["lms_events"].count_documents({}) == 22357

        # Gold collections are placeholders (0 documents)
        assert db["student_features"].count_documents({}) == 0
        assert db["course_metrics"].count_documents({}) == 0
        assert db["school_summary"].count_documents({}) == 0
        assert db["risk_indicators"].count_documents({}) == 0
    finally:
        client.drop_database(test_db_name)
        close_mongo_client(client)


def test_main_cli_error_unreachable_host() -> None:
    """Verify script exits with code 1 when MongoDB host is unreachable."""
    exit_code = main(
        [
            "--uri", "mongodb://localhost:29999",
            "--database", "test_unreachable",
            "--quiet",
        ]
    )
    assert exit_code == 1


def test_main_cli_error_missing_manifest() -> None:
    """Verify script exits with code 1 when manifest is explicitly missing."""
    exit_code = main(
        [
            "--manifest-path", "data/manifests/non_existent_manifest.json",
            "--quiet",
        ]
    )
    assert exit_code == 1
