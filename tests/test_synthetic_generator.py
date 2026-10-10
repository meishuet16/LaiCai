import csv
import gzip
import io
import json
import random
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from retaniq.synthetic.config import SyntheticConfig
from retaniq.synthetic.generator import add_billing_period, generate_dataset
from retaniq.synthetic.validator import validate_dataset
from retaniq.synthetic.v12_generator import _EventWriter, _account_churn_episodes, _payment_recovery_mode


class SyntheticGeneratorTests(unittest.TestCase):
    def test_simultaneous_subscription_replacement_does_not_create_account_churn(self):
        replacement_at = datetime(2025, 4, 25, tzinfo=timezone.utc)
        lifecycles = [
            {
                "subscription_id": "sub-old", "started_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
                "ended_at": replacement_at, "end_type": "involuntary", "end_event_id": "evt-old-end",
            },
            {
                "subscription_id": "sub-new", "started_at": replacement_at,
                "ended_at": None, "end_type": "", "end_event_id": "",
            },
        ]
        self.assertEqual(_account_churn_episodes(lifecycles), [])

    def test_past_due_payment_can_recover_late_or_terminate(self):
        modes = [_payment_recovery_mode(random.Random(seed), 0.6) for seed in range(1000)]
        self.assertIn("immediate_recovery", modes)
        self.assertIn("late_recovery", modes)
        self.assertIn("termination", modes)

    def test_event_writer_retains_only_the_current_account_week_summaries(self):
        fields = ("tenant_id", "source", "source_category", "source_event_id", "external_customer_id",
                  "customer_id", "event_type", "occurred_at", "source_available_at",
                  "simulated_received_at", "attributes_json", "schema_version")
        writers = {}
        for category in ("usage", "billing", "subscription", "canonical"):
            writer = csv.DictWriter(io.StringIO(), fieldnames=fields)
            writers[category] = writer
        event_writer = _EventWriter(writers, Counter())
        event_writer.begin_account("tenant-01", "customer-01")
        event_writer.write(
            tenant_id="tenant-01", category="usage", source="source-usage", event_id="event-1",
            external_customer_id="external-1", customer_id="customer-01", event_type="usage_aggregate_updated",
            occurred_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            attributes={"feature": "reports", "quantity": 2, "unit": "sessions"},
            rng=random.Random(1),
        )
        self.assertLessEqual(len(event_writer.max_available), 1)
        event_writer.begin_account("tenant-01", "customer-02")
        self.assertEqual(event_writer.max_available, {})
        self.assertFalse(hasattr(event_writer, "account_event_rows"))

    def test_v12_exports_daily_usage_window_and_available_customer_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = generate_dataset(
                SyntheticConfig.from_profile(
                    "quick", seed=71, account_count=12, tenant_count=4,
                    start_date="2024-10-01", end_date="2025-02-01",
                ),
                Path(directory),
            )
            dataset = Path(manifest["dataset_path"])
            self.assertEqual(manifest["dataset_version"], "1.2.0")
            self.assertEqual(manifest["generator_code_version"], "synthetic-saas-v1.2")
            self.assertTrue(manifest["dataset_id"].startswith("synthetic-saas-v1-2-quick-"))
            with (dataset / "usage_events.csv").open(encoding="utf-8", newline="") as stream:
                usage_rows = list(csv.DictReader(stream))
            self.assertTrue(usage_rows)
            for row in usage_rows:
                event_at = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
                self.assertEqual(event_at.hour, 0)
                self.assertEqual(event_at.minute, 0)
                self.assertEqual(event_at.second, 0)
                self.assertEqual(row["event_type"], "usage_aggregate_updated")
                attributes = json.loads(row["attributes_json"])
                self.assertEqual(attributes["unit"], "sessions")
                self.assertGreaterEqual(attributes["quantity"], 1)
                self.assertGreaterEqual(row["source_available_at"], row["occurred_at"])
            with gzip.open(dataset / "observation_coverage.csv.gz", "rt", encoding="utf-8", newline="") as stream:
                coverage_rows = list(csv.DictReader(stream))
            self.assertTrue(coverage_rows)
            self.assertTrue({"customer_id", "source", "covered_from", "covered_through",
                             "coverage_status", "coverage_available_at", "observation_policy_version"}
                            .issubset(coverage_rows[0]))
            scenario_report = json.loads((dataset / "scenario_coverage.json").read_text(encoding="utf-8"))
            self.assertTrue(scenario_report["overlap_allowed"])
            self.assertTrue(scenario_report["scenarios"])
            self.assertTrue(all("detection_rule" in row and "distinct_account_count" in row
                                and row["verification_status"] in {
                                    "SOURCE_VERIFIED", "SOURCE_PROXY", "LATENT_ONLY",
                                    "NOT_OBSERVED", "NOT_SUPPORTED",
                                } for row in scenario_report["scenarios"]))
            quality = json.loads((dataset / "quality_report.json").read_text(encoding="utf-8"))
            self.assertEqual(quality["status"], "PASS")

    def test_v12_profiles_use_the_full_exclusive_24_month_window(self):
        config = SyntheticConfig.from_profile("full", seed=2026)
        self.assertEqual(config.generator_version, "synthetic-saas-v1.2")
        self.assertEqual(config.start_date, "2024-10-01")
        self.assertEqual(config.end_date, "2026-10-01")
        self.assertEqual(config.target_policy_version, "effective-account-churn-v1.2")

    def test_independent_cutoff_audit_separates_features_from_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = generate_dataset(
                SyntheticConfig.from_profile("quick", seed=44, account_count=24, tenant_count=4),
                Path(directory),
            )
            dataset = Path(manifest["dataset_path"])
            split = json.loads((dataset / "split_manifest.json").read_text(encoding="utf-8"))
            validation = manifest["validation"]
            self.assertEqual(split["sampling_policy"]["warmup_days"], 63)
            self.assertEqual(split["label_maturity_lag_days"], 8)
            self.assertIn("cohort_label_audit", validation)
            self.assertIn("usage_density_by_tenant", validation)
            train = validation["cohort_label_audit"]["stages"]["train"]
            self.assertEqual(
                train["feature_history_denominator"],
                train["eligible_samples"] - train["known_cancellation_exclusions"],
            )
            self.assertIn("cutoffs_with_payment_failure_in_prior_30d", train["source_evidence"])
            self.assertIn("decline_fraction_of_comparable_windows", train["usage_behavior"])
            for horizon in ("7", "14", "30"):
                counts = train["horizons"][horizon]
                self.assertEqual(
                    counts["eligible_samples"],
                    counts["positive"] + counts["negative"] + counts["unknown"],
                )
            scenarios = {item["scenario_name"]: item for item in validation["source_scenarios"]}
            self.assertIn("high_usage_before_churn", scenarios)
            self.assertIn("past_due_late_recovery", scenarios)
            self.assertIn("past_due_termination", scenarios)
            expected_high = "SOURCE_VERIFIED" if scenarios["high_usage_before_churn"]["distinct_account_count"] else "NOT_OBSERVED"
            expected_recovery = "SOURCE_PROXY" if scenarios["temporary_decline_then_recovery"]["distinct_account_count"] else "NOT_OBSERVED"
            self.assertEqual(scenarios["high_usage_before_churn"]["verification_status"], expected_high)
            self.assertEqual(scenarios["temporary_decline_then_recovery"]["verification_status"], expected_recovery)

    def test_calendar_billing_periods_preserve_month_end_and_leap_years(self):
        self.assertEqual(
            add_billing_period("2025-01-31T12:00:00Z", "month", 1),
            "2025-02-28T12:00:00Z",
        )
        self.assertEqual(
            add_billing_period("2024-01-31T12:00:00Z", "month", 1),
            "2024-02-29T12:00:00Z",
        )
        self.assertEqual(
            add_billing_period("2024-02-29T12:00:00Z", "year", 1),
            "2025-02-28T12:00:00Z",
        )
        self.assertEqual(
            add_billing_period("2025-01-31T12:00:00Z", "quarter", 2),
            "2025-07-31T12:00:00Z",
        )

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
                self.assertIn("simulated_received_at", reader.fieldnames or ())
                self.assertNotIn("received_at", reader.fieldnames or ())
                for row in reader:
                    self.assertLessEqual(row["occurred_at"], row["source_available_at"])
                    self.assertLessEqual(row["source_available_at"], row["simulated_received_at"])

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
            labels = {item["case"]: item["expected"] for item in fixtures["cases"]}
            self.assertEqual(labels["final_entitlement_loss_day_5"], {"7": "1", "14": "1", "30": "1"})
            self.assertEqual(labels["final_entitlement_loss_day_20"], {"7": "0", "14": "0", "30": "1"})
            self.assertEqual(labels["outcome_coverage_gap"], {"7": "0", "14": "unknown", "30": "unknown"})


if __name__ == "__main__":
    unittest.main()
