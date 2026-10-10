"""Shared SQLite/live-PostgreSQL contracts for immutable model artifacts."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_integration,
    authenticate_service_principal,
    create_customer,
    create_integration,
    create_service_principal,
    create_tenant,
    get_events_as_of,
    initialize_database,
    map_customer_identity,
    store_churn_label,
    store_feature_snapshot,
    store_prediction,
)
from retaniq.database import connect_database
from retaniq.database_config import DatabaseConfig


T0 = "2026-10-01T00:00:00.000000Z"
T1 = "2026-10-05T00:00:00.000000Z"
T2 = "2026-10-10T00:00:00.000000Z"


def _postgres_test_config() -> DatabaseConfig | None:
    dsn = os.environ.get("RETAINIQ_POSTGRES_TEST_DSN")
    if not dsn or os.environ.get("RETAINIQ_POSTGRES_TEST_DISPOSABLE") != "1":
        return None
    try:
        config = DatabaseConfig.from_value(dsn, allow_insecure_local_postgresql=True)
        parsed = urlsplit(config.postgresql_dsn)
        database = unquote(parsed.path.lstrip("/"))
    except (TypeError, ValueError):
        return None
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not database.startswith("retaniq_test_"):
        return None
    return config


class ArtifactPersistenceContract:
    db: str | DatabaseConfig

    def setUp(self):
        suffix = uuid4().hex[:12]
        self.tenant = f"artifact-tenant-{suffix}"
        self.other_tenant = f"artifact-other-{suffix}"
        self.customer = f"artifact-customer-{suffix}"
        self.customer_2 = f"artifact-customer-2-{suffix}"
        self.source = f"artifact-source-{suffix}"
        self.external = f"artifact-external-{suffix}"
        self.dataset_id = f"artifact-dataset-{suffix}"
        if isinstance(self.db, str):
            initialize_database(self.db)
        create_tenant(self.db, self.tenant)
        create_tenant(self.db, self.other_tenant)
        create_customer(self.db, self.tenant, self.customer)
        create_customer(self.db, self.tenant, self.customer_2)
        create_customer(self.db, self.other_tenant, f"other-{suffix}")
        token = create_integration(self.db, self.tenant, self.source)
        map_customer_identity(self.db, self.tenant, self.source, self.external, self.customer)
        map_customer_identity(self.db, self.tenant, self.source, f"external-2-{suffix}", self.customer_2)
        self.integration = authenticate_integration(self.db, token)
        writer_token = create_service_principal(
            self.db, self.tenant, role="analyst", authorized_sources=(self.source,),
            authorized_purposes=("model_artifact_write",),
        )
        self.writer = authenticate_service_principal(self.db, writer_token)
        reader_token = create_service_principal(
            self.db, self.tenant, role="analyst", authorized_sources=(self.source,),
            authorized_purposes=("retention_inference",),
        )
        self.reader = authenticate_service_principal(self.db, reader_token)

    def row(self, statement, parameters=()):
        with connect_database(self.db) as connection:
            return connection.execute(statement, parameters).fetchone()

    def test_feature_snapshot_round_trip_conflicts_and_authorization(self):
        snapshot_id = store_feature_snapshot(
            self.db, self.writer, self.customer, T1, "feature-v3", T0,
            {"sessions_7d": 5, "usage_ratio_30d": 0.75}, "limited",
        )
        stored = self.row(
            "SELECT feature_snapshot_id, tenant_id, customer_id, as_of, feature_version, "
            "data_cutoff_at, features_json, data_quality_status FROM feature_snapshots "
            "WHERE tenant_id=? AND feature_snapshot_id=?",
            (self.tenant, snapshot_id),
        )
        self.assertIsNotNone(stored)
        self.assertEqual(stored["feature_snapshot_id"], snapshot_id)
        self.assertEqual(stored["customer_id"], self.customer)
        self.assertEqual(stored["feature_version"], "feature-v3")
        self.assertEqual(stored["data_quality_status"], "limited")
        self.assertEqual(json.loads(stored["features_json"]), {"sessions_7d": 5, "usage_ratio_30d": 0.75})

        for features in (
            {"sessions_7d": 5, "usage_ratio_30d": 0.75},
            {"sessions_7d": 6},
        ):
            with self.subTest(features=features), self.assertRaises(DataFoundationError) as conflict:
                store_feature_snapshot(
                    self.db, self.writer, self.customer, T1, "feature-v3", T0, features, "available",
                )
            self.assertEqual(conflict.exception.code, "contract_conflict")

        for principal, customer_id, expected in (
            (self.reader, self.customer, "purpose_not_authorized"),
            (self.writer, f"missing-{uuid4().hex[:8]}", "not_found"),
            (self.writer, f"other-{self.other_tenant.split('-')[-1]}", "not_found"),
        ):
            with self.subTest(customer=customer_id), self.assertRaises(DataFoundationError) as denied:
                store_feature_snapshot(
                    self.db, principal, customer_id, T2, f"denied-{uuid4().hex[:6]}", T1,
                    {"sessions_7d": 1}, "available",
                )
            self.assertEqual(denied.exception.code, expected)

        for features in (
            {"account_contact_email": "user@example.invalid"},
            {"mrr_minor": 1200},
        ):
            with self.subTest(restricted=features), self.assertRaises(DataFoundationError):
                store_feature_snapshot(
                    self.db, self.writer, self.customer, T2, f"restricted-{uuid4().hex[:6]}", T1,
                    features, "available",
                )

    def test_labels_preserve_unknown_maturity_horizon_and_immutability(self):
        store_churn_label(
            self.db, self.writer, self.customer, T0, 7, 1, T1, "label-v2",
            churn_type="voluntary", outcome_at="2026-10-04T00:00:00Z",
        )
        store_churn_label(
            self.db, self.writer, self.customer, T0, 14, 0, "2026-10-20T00:00:00Z", "label-v2",
        )
        store_churn_label(self.db, self.writer, self.customer, T0, 30, "unknown", T1, "label-v2")
        rows = self.row(
            "SELECT COUNT(*) AS count FROM churn_labels WHERE tenant_id=? AND customer_id=?",
            (self.tenant, self.customer),
        )
        self.assertEqual(rows["count"], 3)
        positive = self.row(
            "SELECT label, horizon_days, churn_type, outcome_at, label_observed_through, label_policy_version "
            "FROM churn_labels WHERE tenant_id=? AND customer_id=? AND horizon_days=7",
            (self.tenant, self.customer),
        )
        self.assertEqual((positive["label"], positive["horizon_days"], positive["churn_type"]),
                         ("1", 7, "voluntary"))
        self.assertEqual(positive["label_policy_version"], "label-v2")
        self.assertIsNotNone(positive["outcome_at"])
        unknown = self.row(
            "SELECT label, outcome_at, label_observed_through FROM churn_labels "
            "WHERE tenant_id=? AND customer_id=? AND horizon_days=30",
            (self.tenant, self.customer),
        )
        self.assertEqual(unknown["label"], "unknown")
        self.assertIsNone(unknown["outcome_at"])

        invalid = (
            (8, 0, "2026-10-20T00:00:00Z", "label-invalid-horizon", None),
            (7, 1, T1, "label-outcome-after-observation", "2026-10-06T00:00:00Z"),
            (14, 0, T1, "label-negative-before-maturity", None),
        )
        for horizon, label, observed, policy, outcome in invalid:
            with self.subTest(policy=policy), self.assertRaises(DataFoundationError):
                store_churn_label(
                    self.db, self.writer, self.customer, T0, horizon, label, observed, policy,
                    outcome_at=outcome,
                )
        with self.assertRaises(DataFoundationError) as duplicate:
            store_churn_label(self.db, self.writer, self.customer, T0, 7, 0, "2026-10-20T00:00:00Z", "label-v2")
        self.assertEqual(duplicate.exception.code, "contract_conflict")
        with self.assertRaises(DataFoundationError) as cross_tenant:
            store_churn_label(
                self.db, self.writer, f"other-{self.other_tenant.split('-')[-1]}",
                T0, 7, "unknown", T1, "label-cross-tenant",
            )
        self.assertEqual(cross_tenant.exception.code, "not_found")

    def test_prediction_snapshot_contract_and_shared_run_identity(self):
        feature_id = store_feature_snapshot(
            self.db, self.writer, self.customer, T1, "features-v4", T0, {"sessions_7d": 3}, "available",
        )
        base = {
            "prediction_run_id": "shared-run", "as_of": T1, "generated_at": T2,
            "status": "scored", "p_churn_7d": 0.1, "p_churn_14d": 0.2, "p_churn_30d": 0.4,
            "feature_version": "features-v4", "model_version": "model-v7",
            "calibration_version": "cal-v2", "label_policy_version": "label-v2",
            "reliability_status": "limited_evidence", "reliability_reasons": ["stale_source_data"],
            "data_freshness_status": "partially_stale", "input_data_as_of": T0,
            "feature_snapshot_id": feature_id,
            "explanations_by_horizon": {"30d": [{"feature": "sessions_7d", "contribution": 0.2}]},
        }
        self.assertEqual(
            store_prediction(self.db, self.writer, {**base, "prediction_id": "prediction-a",
                                                    "customer_id": self.customer}),
            "prediction-a",
        )
        second_feature = store_feature_snapshot(
            self.db, self.writer, self.customer_2, T1, "features-v4", T0, {"sessions_7d": 1}, "available",
        )
        store_prediction(
            self.db, self.writer,
            {**base, "prediction_id": "prediction-b", "customer_id": self.customer_2,
             "feature_snapshot_id": second_feature},
        )
        rows = self.row(
            "SELECT COUNT(*) AS count FROM predictions WHERE tenant_id=? AND prediction_run_id=?",
            (self.tenant, "shared-run"),
        )
        self.assertEqual(rows["count"], 2)
        saved = self.row(
            "SELECT prediction_id, prediction_run_id, p_churn_7d, p_churn_14d, p_churn_30d, "
            "feature_version, model_version, calibration_version, label_policy_version, reliability_status, "
            "reliability_reasons_json, data_freshness_status, input_data_as_of, uncertainty_status, "
            "explanations_by_horizon_json FROM predictions WHERE tenant_id=? AND prediction_id=?",
            (self.tenant, "prediction-a"),
        )
        self.assertEqual((saved["prediction_id"], saved["prediction_run_id"]), ("prediction-a", "shared-run"))
        self.assertEqual((saved["p_churn_7d"], saved["p_churn_14d"], saved["p_churn_30d"]), (0.1, 0.2, 0.4))
        self.assertEqual(saved["reliability_status"], "limited_evidence")
        self.assertEqual(json.loads(saved["reliability_reasons_json"]), ["stale_source_data"])
        self.assertEqual(saved["data_freshness_status"], "partially_stale")
        self.assertEqual(saved["uncertainty_status"], "not_quantified")
        self.assertEqual(json.loads(saved["explanations_by_horizon_json"]), base["explanations_by_horizon"])

        for prediction in (
            {**base, "prediction_id": "invalid-order", "customer_id": self.customer,
             "p_churn_7d": 0.3, "p_churn_14d": 0.2},
            {**base, "prediction_id": "invalid-range", "customer_id": self.customer,
             "p_churn_30d": 1.1},
            {**base, "prediction_id": "invalid-feature", "customer_id": self.customer,
             "feature_snapshot_id": "missing-feature-snapshot"},
        ):
            with self.subTest(prediction=prediction["prediction_id"]), self.assertRaises(DataFoundationError):
                store_prediction(self.db, self.writer, prediction)

        for index, status in enumerate(("abstained", "known_cancellation", "not_eligible")):
            store_prediction(
                self.db, self.writer,
                {**base, "prediction_id": f"null-probabilities-{index}", "prediction_run_id": f"run-{index}",
                 "customer_id": self.customer, "as_of": f"2026-10-{6 + index:02d}T00:00:00Z",
                 "status": status, "p_churn_7d": None, "p_churn_14d": None, "p_churn_30d": None,
                 "feature_snapshot_id": None},
            )
        with self.assertRaises(DataFoundationError) as conflict:
            store_prediction(
                self.db, self.writer,
                {**base, "prediction_id": "prediction-conflict", "customer_id": self.customer},
            )
        self.assertEqual(conflict.exception.code, "contract_conflict")


class SQLiteArtifactPersistenceTests(ArtifactPersistenceContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "artifacts.sqlite3")
        super().setUp()

    def tearDown(self):
        self.temp.cleanup()


_POSTGRES_TEST_CONFIG = _postgres_test_config()


@unittest.skipUnless(
    _POSTGRES_TEST_CONFIG,
    "requires the explicit disposable loopback PostgreSQL test target",
)
class PostgreSQLArtifactPersistenceTests(ArtifactPersistenceContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = _POSTGRES_TEST_CONFIG
        from postgresql_security_support import bootstrap_test_roles
        bootstrap_test_roles(cls.db)
        initialize_database(cls.db, migrate_postgresql=True)


if __name__ == "__main__":
    unittest.main()
