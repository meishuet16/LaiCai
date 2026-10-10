import tempfile
import sqlite3
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


if __name__ == "__main__":
    unittest.main()
