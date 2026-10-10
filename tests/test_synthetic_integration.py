import tempfile
import sqlite3
import csv
import gzip
import hashlib
import unittest
from pathlib import Path

from retaniq.synthetic.canonical_adapter import import_dataset
from retaniq.synthetic.config import SyntheticConfig
from retaniq.synthetic.generator import generate_dataset


class SyntheticIntegrationTests(unittest.TestCase):
    def test_database_rejects_a_second_dataset_before_importing_any_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = dict(
                account_count=4, tenant_count=2,
                start_date="2025-01-01", end_date="2025-04-30",
            )
            first = generate_dataset(
                SyntheticConfig.from_profile("quick", seed=2026, **common), root / "first",
            )
            second = generate_dataset(
                SyntheticConfig.from_profile("quick", seed=2027, **common), root / "second",
            )
            database = root / "shared.sqlite3"
            import_dataset(Path(first["dataset_path"]), database)
            connection = sqlite3.connect(database)
            before = connection.execute("SELECT COUNT(*) FROM canonical_events").fetchone()[0]
            connection.close()
            with self.assertRaisesRegex(ValueError, "dataset identity"):
                import_dataset(Path(second["dataset_path"]), database)
            connection = sqlite3.connect(database)
            after = connection.execute("SELECT COUNT(*) FROM canonical_events").fetchone()[0]
            connection.close()
            self.assertEqual(after, before)

    def test_quick_dataset_imports_through_canonical_ingestion_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = generate_dataset(
                SyntheticConfig.from_profile(
                    "quick", seed=2026, account_count=12, tenant_count=4,
                    start_date="2025-01-01", end_date="2025-05-31",
                ),
                root / "output",
            )
            result = import_dataset(Path(manifest["dataset_path"]), root / "retaniq.sqlite3", verify_idempotency=True)
            self.assertEqual(result["status"], "VERIFIED")
            self.assertEqual(result["accepted"], manifest["actual_counts"]["canonical_events"])
            self.assertEqual(result["repeat_duplicates"], manifest["actual_counts"]["canonical_events"])
            self.assertGreater(result["historical_snapshots_checked"], 0)
            self.assertTrue(result["cross_tenant_denial_verified"])
            connection = sqlite3.connect(root / "retaniq.sqlite3")
            received, source_available = connection.execute(
                "SELECT received_at, source_available_at FROM canonical_events ORDER BY event_id LIMIT 1",
            ).fetchone()
            connection.close()
            self.assertGreaterEqual(received, source_available)
            repeated = import_dataset(
                Path(manifest["dataset_path"]), root / "retaniq.sqlite3", verify_idempotency=True,
            )
            self.assertEqual(repeated["status"], "VERIFIED")
            self.assertEqual(repeated["database_event_count"], manifest["actual_counts"]["canonical_events"])

    def test_tenant_scoped_import_preserves_manifest_and_excludes_other_tenants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = generate_dataset(
                SyntheticConfig.from_profile(
                    "quick", seed=2028, account_count=12, tenant_count=4,
                    start_date="2025-01-01", end_date="2025-05-31",
                ),
                root / "output",
            )
            dataset = Path(manifest["dataset_path"])
            expected_events = expected_coverage = 0
            with (dataset / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
                expected_events = sum(row["tenant_id"] == "tenant-01" for row in csv.DictReader(stream))
            with gzip.open(dataset / "observation_coverage.csv.gz", "rt", encoding="utf-8", newline="") as stream:
                expected_coverage = sum(row["tenant_id"] == "tenant-01" for row in csv.DictReader(stream))

            database = root / "tenant-01.sqlite3"
            result = import_dataset(
                dataset, database, tenant_id="tenant-01", verify_idempotency=True,
            )
            self.assertEqual(result["status"], "VERIFIED")
            self.assertEqual(result["import_scope"], "tenant-01")
            self.assertEqual(result["imported_tenant_count"], 1)
            self.assertEqual(result["database_event_count"], expected_events)
            self.assertEqual(result["database_coverage_count"], expected_coverage)
            self.assertEqual(result["repeat_duplicates"], expected_events)
            self.assertEqual(result["source_manifest_sha256"], hashlib.sha256(
                (dataset / "dataset_manifest.json").read_bytes(),
            ).hexdigest())
            self.assertEqual(set(result["tenant_table_counts"]), {"tenant-01"})
            self.assertEqual(result["tenant_table_counts"]["tenant-01"]["customers"], 3)

            connection = sqlite3.connect(database)
            for table in (
                "tenants", "customers", "customer_identities", "integrations", "canonical_events",
                "observation_coverage", "service_principals",
            ):
                with self.subTest(table=table):
                    self.assertEqual(connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE tenant_id <> 'tenant-01'",
                    ).fetchone()[0], 0)
            identity = connection.execute(
                "SELECT dataset_id, manifest_sha256 FROM dataset_identity WHERE singleton_id=1",
            ).fetchone()
            connection.close()
            self.assertEqual(identity[0], manifest["dataset_id"])
            self.assertEqual(identity[1], result["source_manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
