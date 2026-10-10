"""Bounded dual-backend synthetic import, checkpoint, and replay verification."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql

from retaniq.data_foundation import (
    authenticate_service_principal,
    bind_dataset_identity,
    get_dataset_identity,
    get_synthetic_import_checkpoint,
)
from retaniq.database_config import DatabaseConfig
from retaniq.importer import iter_replay_events
from retaniq.synthetic.canonical_adapter import import_dataset, provision_member2_reader
from retaniq.synthetic.config import SyntheticConfig
from retaniq.synthetic.generator import generate_dataset


def _postgres_test_config() -> DatabaseConfig | None:
    dsn = os.environ.get("RETAINIQ_POSTGRES_TEST_DSN")
    if not dsn or os.environ.get("RETAINIQ_POSTGRES_TEST_DISPOSABLE") != "1":
        return None
    try:
        config = DatabaseConfig.from_value(dsn, allow_insecure_local_postgresql=True)
        parsed = urlsplit(config.postgresql_dsn)
        name = unquote(parsed.path.lstrip("/"))
    except (TypeError, ValueError):
        return None
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not name.startswith("retaniq_test_"):
        return None
    return config


_PARENT_CONFIG = _postgres_test_config()


@unittest.skipUnless(_PARENT_CONFIG, "requires an explicitly disposable loopback PostgreSQL test database")
class PostgreSQLImportReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        dataset = generate_dataset(
            SyntheticConfig.from_profile(
                "quick", seed=2026, account_count=12, tenant_count=4,
                start_date="2025-01-01", end_date="2025-05-31",
            ),
            cls.root / "dataset",
        )
        cls.dataset = Path(dataset["dataset_path"])
        cls.manifest = dataset
        parsed = urlsplit(_PARENT_CONFIG.postgresql_dsn)
        cls.child_name = f"retaniq_test_import_{uuid4().hex[:10]}"
        cls.postgres = DatabaseConfig.from_value(
            urlunsplit(parsed._replace(path=f"/{cls.child_name}")),
            allow_insecure_local_postgresql=True,
        )
        with psycopg.connect(_PARENT_CONFIG.postgresql_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.child_name)))
        cls.sqlite = str(cls.root / "synthetic.sqlite3")

    @classmethod
    def tearDownClass(cls):
        try:
            with psycopg.connect(_PARENT_CONFIG.postgresql_dsn, autocommit=True) as admin:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(cls.child_name)))
        finally:
            cls.temp.cleanup()

    def test_quick_import_checkpoints_replay_and_provenance_match(self):
        expected_events = self.manifest["actual_counts"]["canonical_events"]
        expected_coverage = self.manifest["actual_counts"]["observation_coverage"]
        pg_result = import_dataset(self.dataset, self.postgres, verify_idempotency=True)
        sqlite_result = import_dataset(self.dataset, self.sqlite, verify_idempotency=True)
        comparable = (
            "status", "accepted", "duplicates", "repeat_duplicates", "repeat_accepted",
            "database_event_count", "coverage_accepted", "coverage_duplicates", "database_coverage_count",
        )
        self.assertTrue(all(pg_result[key] == sqlite_result[key] for key in comparable))
        self.assertEqual(pg_result["status"], "VERIFIED")
        self.assertEqual(pg_result["accepted"], expected_events)
        self.assertEqual(pg_result["repeat_duplicates"], expected_events)
        self.assertEqual(pg_result["repeat_accepted"], 0)
        self.assertEqual(pg_result["database_event_count"], expected_events)
        self.assertEqual(pg_result["coverage_accepted"], expected_coverage)
        self.assertEqual(pg_result["database_coverage_count"], expected_coverage)
        self.assertFalse(pg_result["credentials_persisted"])

        event_checkpoint = get_synthetic_import_checkpoint(
            self.postgres, dataset_id=self.manifest["dataset_id"], stream_name="canonical-events",
        )
        coverage_checkpoint = get_synthetic_import_checkpoint(
            self.postgres, dataset_id=self.manifest["dataset_id"], stream_name="observation-coverage",
        )
        self.assertEqual(event_checkpoint["last_row_number"], expected_events)
        self.assertEqual(event_checkpoint["accepted_count"], expected_events)
        self.assertEqual(event_checkpoint["database_event_count"], expected_events)
        self.assertEqual(coverage_checkpoint["last_row_number"], expected_coverage)
        self.assertEqual(coverage_checkpoint["accepted_count"], expected_coverage)
        self.assertEqual(coverage_checkpoint["database_coverage_count"], expected_coverage)

        with (self.dataset / "customers.csv").open(encoding="utf-8", newline="") as stream:
            tenant_id = next(csv.DictReader(stream))["tenant_id"]
        pg_reader = provision_member2_reader(self.dataset, self.postgres, tenant_id)
        sqlite_reader = provision_member2_reader(self.dataset, self.sqlite, tenant_id)
        self.assertNotIn("billing_valuation", pg_reader["authorized_purposes"])
        self.assertEqual(
            set(pg_reader["authorized_purposes"]),
            {"retention_inference", "model_artifact_write"},
        )
        self.assertEqual(set(sqlite_reader["authorized_purposes"]), set(pg_reader["authorized_purposes"]))
        self.assertNotIn("token", pg_result)
        pg_principal = authenticate_service_principal(self.postgres, pg_reader["token"])
        sqlite_principal = authenticate_service_principal(self.sqlite, sqlite_reader["token"])
        pg_identity = get_dataset_identity(self.postgres, pg_principal)
        sqlite_identity = get_dataset_identity(self.sqlite, sqlite_principal)
        self.assertEqual(pg_identity, sqlite_identity)
        self.assertEqual(pg_identity["dataset_id"], self.manifest["dataset_id"])

        for database in (self.postgres, self.sqlite):
            with self.assertRaisesRegex(ValueError, "dataset identity mismatch"):
                bind_dataset_identity(
                    database, dataset_id=self.manifest["dataset_id"], dataset_version="wrong-version",
                    dataset_type="synthetic_saas", target_policy_version=self.manifest["target_policy_version"],
                    generator_version=self.manifest["generator_code_version"],
                    manifest_sha256=pg_identity["manifest_sha256"],
                )

        start, end = "2025-01-01T00:00:00Z", "2025-07-01T00:00:00Z"
        pg_replay = list(iter_replay_events(self.postgres, pg_principal, start, end))
        sqlite_replay = list(iter_replay_events(self.sqlite, sqlite_principal, start, end))
        self.assertEqual(len(pg_replay), len(sqlite_replay))
        for pg_event, sqlite_event in zip(pg_replay, sqlite_replay):
            self.assertIsNotNone(pg_event["received_at"])
            self.assertIsNotNone(sqlite_event["received_at"])
            # Receipt is the independent processing timestamp and naturally differs
            # between two imports; source availability and all event content must match.
            self.assertEqual(
                {**pg_event, "received_at": "<import-received-at>"},
                {**sqlite_event, "received_at": "<import-received-at>"},
            )
        self.assertEqual(
            pg_replay,
            sorted(pg_replay, key=lambda event: (event["available_at"], event["occurred_at"], event["event_id"])),
        )
        self.assertTrue(all(start <= row["available_at"] <= end for row in pg_replay))
        self.assertTrue(all(row["source_available_at"] is not None for row in pg_replay))


if __name__ == "__main__":
    unittest.main()
