import tempfile
import unittest
from pathlib import Path

from retaniq.synthetic.canonical_adapter import import_dataset
from retaniq.synthetic.config import SyntheticConfig
from retaniq.synthetic.generator import generate_dataset


class SyntheticIntegrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
