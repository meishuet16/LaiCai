import csv
import json
import tempfile
import unittest
from pathlib import Path

from retaniq.synthetic.config import SyntheticConfig
from retaniq.synthetic.generator import generate_dataset
from retaniq.synthetic.validator import validate_dataset


class SyntheticGeneratorTests(unittest.TestCase):
    def test_configuration_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            SyntheticConfig.from_profile("quick", account_count=0)
        with self.assertRaises(ValueError):
            SyntheticConfig.from_profile("quick", tenant_count=5, account_count=4)
        with self.assertRaises(ValueError):
            SyntheticConfig.from_profile("quick", start_date="2026-02-01", end_date="2026-01-01")

    def test_fixed_seed_reproduces_logical_file_hashes(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            config = SyntheticConfig.from_profile(
                "quick", seed=2026, account_count=16, tenant_count=4,
                start_date="2025-01-01", end_date="2025-06-30",
            )
            manifest_a = generate_dataset(config, Path(first))
            manifest_b = generate_dataset(config, Path(second))
            self.assertEqual(manifest_a["dataset_id"], manifest_b["dataset_id"])
            self.assertEqual(manifest_a["file_hashes"], manifest_b["file_hashes"])
            self.assertEqual(manifest_a["actual_counts"], manifest_b["actual_counts"])

    def test_generated_family_has_linked_identities_and_no_target_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SyntheticConfig.from_profile(
                "quick", seed=17, account_count=20, tenant_count=4,
                start_date="2025-01-01", end_date="2025-08-31",
            )
            manifest = generate_dataset(config, Path(directory))
            dataset_dir = Path(manifest["dataset_path"])
            with (dataset_dir / "customers.csv").open(encoding="utf-8", newline="") as stream:
                customers = list(csv.DictReader(stream))
            with (dataset_dir / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
                identities = list(csv.DictReader(stream))
            self.assertEqual(len(customers), 20)
            self.assertEqual(len(identities), 60)
            self.assertEqual({row["source_category"] for row in identities}, {"usage", "billing", "subscription"})

            with (dataset_dir / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                self.assertFalse({"will_churn", "churn_risk_class", "latent_hazard"} & set(reader.fieldnames or ()))
                for row in reader:
                    self.assertLessEqual(row["occurred_at"], row["source_available_at"])
                    self.assertLessEqual(row["source_available_at"], row["received_at"])

            report = validate_dataset(dataset_dir)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["errors"], [])

    def test_different_seed_changes_generated_content(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            common = dict(account_count=12, tenant_count=4, start_date="2025-01-01", end_date="2025-04-30")
            a = generate_dataset(SyntheticConfig.from_profile("quick", seed=1, **common), Path(first))
            b = generate_dataset(SyntheticConfig.from_profile("quick", seed=2, **common), Path(second))
            self.assertNotEqual(a["file_hashes"]["canonical_events.csv"], b["file_hashes"]["canonical_events.csv"])

    def test_oracle_fixtures_preserve_horizon_and_unknown_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = generate_dataset(
                SyntheticConfig.from_profile(
                    "quick", seed=9, account_count=12, tenant_count=4,
                    start_date="2025-01-01", end_date="2025-04-30",
                ),
                Path(directory),
            )
            fixtures = json.loads((Path(manifest["dataset_path"]) / "label_oracle_fixtures.json").read_text(encoding="utf-8"))
            labels = {item["case"]: item["labels"] for item in fixtures["fixtures"]}
            self.assertEqual(labels["churn_day_5"], {"7": "1", "14": "1", "30": "1"})
            self.assertEqual(labels["churn_day_20"], {"7": "0", "14": "0", "30": "1"})
            self.assertEqual(labels["censored_day_10"], {"7": "0", "14": "unknown", "30": "unknown"})


if __name__ == "__main__":
    unittest.main()
