"""Strict differential contract fixtures shared by SQLite and live PostgreSQL."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import psycopg
from psycopg import sql

from retaniq.api import create_app
from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_integration,
    authenticate_service_principal,
    bind_dataset_identity,
    create_customer,
    create_integration,
    create_service_principal,
    create_tenant,
    get_account_snapshot_as_of,
    get_dataset_identity,
    get_events_as_of,
    get_observation_coverage_as_of,
    get_subscriptions_as_of,
    initialize_database,
    ingest_event,
    map_customer_identity,
    record_observation_coverage,
    set_integration_event_categories,
    store_churn_label,
    store_feature_snapshot,
    store_prediction,
)
from retaniq.database import connect_database
from retaniq.database_config import DatabaseConfig
from retaniq.importer import iter_replay_events


AS_OF = "2026-10-10T00:00:00.000000Z"
T0 = "2026-10-01T00:00:00.000000Z"
T1 = "2026-10-05T00:00:00.000000Z"
T2 = AS_OF
T3 = "2026-10-12T00:00:00.000000Z"
_DATASET = {
    "dataset_id": "dual-contract-fixture-v1",
    "dataset_version": "fixture-v1",
    "dataset_type": "synthetic_saas",
    "target_policy_version": "fixture-policy-v1",
    "generator_version": "fixture-generator-v1",
    "manifest_sha256": "d" * 64,
}
_TIME_KEYS = {
    "as_of", "occurred_at", "received_at", "source_available_at", "available_at",
    "data_cutoff_at", "generated_at", "input_data_as_of", "outcome_at",
    "label_observed_through", "covered_from", "covered_through",
    "coverage_available_at", "started_at", "current_period_end", "ended_at",
    "cancellation_requested_at", "valuation_as_of", "last_successful_ingestion_at",
    "last_failure_at",
}


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


def _normalize(value, key: str | None = None):
    """Normalize representation only; retain all business fields and values."""
    if isinstance(value, Mapping) or (hasattr(value, "keys") and callable(value.keys)):
        # event_id is a database-generated surrogate; all canonical source IDs,
        # hashes, tenant/customer IDs, and prediction IDs remain comparison keys.
        return {
            name: _normalize(value[name], name)
            for name in value.keys()
            if name != "event_id"
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        timestamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if key in _TIME_KEYS and isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return value


def _error_code(callback):
    try:
        callback()
    except DataFoundationError as error:
        return error.code
    except ValueError as error:
        return str(error)
    return None


def _request(app, method, path, *, token=None, body=None):
    encoded = json.dumps(body).encode() if body is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(encoded)) if body is not None else "0",
        "CONTENT_TYPE": "application/json",
        "wsgi.input": io.BytesIO(encoded),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    response["body"] = json.loads(b"".join(app(environ, start_response)))
    return response


_PG_CONFIG = _postgres_test_config()


@unittest.skipUnless(
    _PG_CONFIG,
    "requires an explicitly disposable loopback PostgreSQL database named retaniq_test_*",
)
class DualDatabaseContractTests(unittest.TestCase):
    """Run each deterministic public-interface scenario on both actual backends."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.sqlite = str(cls.root / "dual-contract.sqlite3")
        parent = urlsplit(_PG_CONFIG.postgresql_dsn)
        cls.pg_name = f"retaniq_test_contract_{uuid4().hex[:12]}"
        cls.postgres = DatabaseConfig.from_value(
            parent._replace(path=f"/{cls.pg_name}").geturl(),
            allow_insecure_local_postgresql=True,
        )
        with psycopg.connect(_PG_CONFIG.postgresql_dsn, autocommit=True) as admin:
            exists = admin.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (cls.pg_name,),
            ).fetchone()
            if exists is not None:
                raise AssertionError("refusing to reuse an existing differential test database")
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.pg_name)))
        initialize_database(cls.sqlite)
        initialize_database(cls.postgres, migrate_postgresql=True)
        cls.backends = {"sqlite": cls.sqlite, "postgresql": cls.postgres}
        cls._ensure_dataset_identity(cls.sqlite)
        cls._ensure_dataset_identity(cls.postgres)

    @classmethod
    def tearDownClass(cls):
        try:
            with psycopg.connect(_PG_CONFIG.postgresql_dsn, autocommit=True) as admin:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid <> pg_backend_pid()", (cls.pg_name,),
                )
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(cls.pg_name)))
        finally:
            cls.temp.cleanup()

    @staticmethod
    def _ensure_dataset_identity(database):
        bind_dataset_identity(database, **_DATASET)

    def _fixture(self, database, case: str):
        tenant = f"dual-{case}-tenant"
        customer = f"dual-{case}-customer"
        source = f"dual-{case}-source"
        external = f"dual-{case}-external"
        other_tenant = f"dual-{case}-other-tenant"
        other_customer = f"dual-{case}-other-customer"
        create_tenant(database, tenant)
        create_tenant(database, other_tenant)
        create_customer(database, tenant, customer)
        create_customer(database, other_tenant, other_customer)
        integration_token = create_integration(
            database, tenant, source,
            authorized_purposes=("retention_inference", "identity_mapping", "billing_valuation"),
            authorized_categories=("usage", "billing", "subscription"),
        )
        map_customer_identity(database, tenant, source, external, customer)
        writer_token = create_service_principal(
            database, tenant, role="analyst", authorized_sources=(source,),
            authorized_purposes=("retention_inference", "billing_valuation", "model_artifact_write"),
        )
        reader_token = create_service_principal(
            database, tenant, role="analyst", authorized_sources=(source,),
            authorized_purposes=("retention_inference",),
        )
        return {
            "tenant": tenant,
            "customer": customer,
            "source": source,
            "external": external,
            "other_tenant": other_tenant,
            "other_customer": other_customer,
            "integration_token": integration_token,
            "integration": authenticate_integration(database, integration_token),
            "writer": authenticate_service_principal(database, writer_token),
            "reader": authenticate_service_principal(database, reader_token),
        }

    @staticmethod
    def _ingest(database, fixture, source_event_id, event_type, occurred_at, attributes, *, available=None):
        return ingest_event(
            database,
            fixture["integration"],
            {
                "source": fixture["source"],
                "source_event_id": source_event_id,
                "external_customer_id": fixture["external"],
                "event_type": event_type,
                "occurred_at": occurred_at,
                "attributes": attributes,
                "schema_version": "1.0",
            },
            received_at=T1,
            trusted_source_available_at=available,
        )

    def _both(self, case, runner):
        outputs = {
            backend: _normalize(runner(database, case))
            for backend, database in self.backends.items()
        }
        self.assertEqual(outputs["sqlite"], outputs["postgresql"])
        return outputs["sqlite"]

    def test_ingestion_hashes_idempotency_authorization_and_as_of_replay_match(self):
        def scenario(database, case):
            f = self._fixture(database, case)
            self._ingest(database, f, "usage-event", "feature_used", T0,
                         {"feature": "reports", "quantity": 3, "unit": "sessions"}, available=T0)
            duplicate = self._ingest(
                database, f, "usage-event", "feature_used", T0,
                {"feature": "reports", "quantity": 3, "unit": "sessions"}, available=T0,
            )
            conflict = _error_code(lambda: self._ingest(
                database, f, "usage-event", "feature_used", T0,
                {"feature": "exports", "quantity": 3, "unit": "sessions"}, available=T0,
            ))
            self._ingest(database, f, "late-source", "session_started", T0,
                         {"feature": "reports"}, available=T3)
            self._ingest(database, f, "late-receipt", "session_started", T0,
                         {"feature": "exports"})
            self._ingest(database, f, "future-event", "session_started", T3,
                         {"feature": "reports"}, available=T0)
            self._ingest(database, f, "boundary-event", "session_started", T2,
                         {"feature": "exports"}, available=T2)
            before_boundary = get_events_as_of(database, f["writer"], f["customer"], T1)
            at_boundary = get_events_as_of(database, f["writer"], f["customer"], T2)
            at_late_source = get_events_as_of(database, f["writer"], f["customer"], T3)
            replay = list(iter_replay_events(database, f["writer"], T0, T2))
            with connect_database(database) as connection:
                digests = connection.execute(
                    "SELECT source_event_id, normalized_payload_sha256 FROM canonical_events "
                    "WHERE tenant_id=? AND source=? ORDER BY source_event_id",
                    (f["tenant"], f["source"]),
                ).fetchall()
            unauth = _error_code(lambda: store_feature_snapshot(
                database, f["reader"], f["customer"], T1, f"unauthorized-{case}", T0,
                {"sessions_7d": 1}, "available",
            ))
            foreign_write = _error_code(lambda: store_feature_snapshot(
                database, f["writer"], f["other_customer"], T1, f"foreign-{case}", T0,
                {"sessions_7d": 1}, "available",
            ))
            return {
                "duplicate": duplicate["duplicate"],
                "conflict_code": conflict,
                "before_boundary": before_boundary,
                "at_boundary": at_boundary,
                "at_late_source": at_late_source,
                "replay": replay,
                "event_hashes": digests,
                "unauthorized_artifact": unauth,
                "cross_tenant_artifact": foreign_write,
            }

        output = self._both("ingest", scenario)
        self.assertTrue(output["duplicate"])
        self.assertEqual(output["conflict_code"], "idempotency_conflict")
        self.assertEqual(output["unauthorized_artifact"], "purpose_not_authorized")
        self.assertEqual(output["cross_tenant_artifact"], "not_found")
        before_ids = {row["source_event_id"] for row in output["before_boundary"]}
        boundary_ids = {row["source_event_id"] for row in output["at_boundary"]}
        late_ids = {row["source_event_id"] for row in output["at_late_source"]}
        self.assertNotIn("late-source", before_ids)
        self.assertIn("late-receipt", before_ids)  # received_at fallback is inclusive
        self.assertIn("boundary-event", boundary_ids)  # both predicates are inclusive
        self.assertNotIn("future-event", boundary_ids)  # occurrence time still gates visibility
        self.assertNotIn("late-source", boundary_ids)  # source_available_at wins over earlier receipt
        self.assertIn("late-source", late_ids)
        self.assertIn("future-event", late_ids)
        self.assertEqual(
            [row["source_event_id"] for row in output["replay"]],
            [row["source_event_id"] for row in sorted(
                output["replay"],
                key=lambda row: (row["available_at"], row["occurred_at"], row["source_event_id"]),
            )],
        )
        self.assertNotIn("future-event", [row["source_event_id"] for row in output["replay"]])

    def test_subscription_coverage_mrr_and_source_grants_match(self):
        def scenario(database, case):
            f = self._fixture(database, case)
            self._ingest(
                database, f, "subscription-created", "subscription_created", T0,
                {"subscription_id": "dual-sub", "status": "active", "started_at": T0,
                 "plan_id": "annual", "billing_interval": "year", "billing_interval_count": 1,
                 "amount_minor": 12000, "discount_minor": 1200, "currency": "USD"}, available=T0,
            )
            self._ingest(
                database, f, "payment-failed", "payment_failed", T1,
                {"subscription_id": "dual-sub", "amount_minor": 1200, "currency": "USD"}, available=T1,
            )
            self._ingest(
                database, f, "pending-cancel", "cancellation_requested", T3,
                {"subscription_id": "dual-sub", "current_period_end": T3}, available=T1,
            )
            coverage = {
                "coverage_id": "dual-coverage",
                "customer_id": f["customer"],
                "source_category": "usage",
                "covered_from": T0,
                "covered_through": T1,
                "coverage_status": "complete",
                "coverage_completeness": 1.0,
                "coverage_available_at": T2,
                "observation_policy_version": "coverage-v1",
            }
            first = record_observation_coverage(database, f["integration"], coverage)
            repeated = record_observation_coverage(database, f["integration"], coverage)
            coverage_conflict = _error_code(lambda: record_observation_coverage(
                database, f["integration"], {**coverage, "coverage_completeness": 0.5,
                                              "coverage_status": "partial"},
            ))
            snapshot = get_account_snapshot_as_of(database, f["writer"], f["customer"], T2)
            no_billing = get_account_snapshot_as_of(database, f["reader"], f["customer"], T2)
            no_coverage_before = get_observation_coverage_as_of(
                database, f["writer"], f["customer"], T1,
            )
            coverage_at = get_observation_coverage_as_of(database, f["writer"], f["customer"], T2)
            subscriptions = get_subscriptions_as_of(database, f["writer"], f["customer"], T2)
            billing_events = get_events_as_of(
                database, f["reader"], f["customer"], T2, category="billing",
            )
            set_integration_event_categories(database, f["tenant"], f["source"], ("usage",))
            refreshed = authenticate_integration(database, f["integration_token"])
            restricted_billing = get_events_as_of(
                database, refreshed, f["customer"], T2, category="billing",
            )
            with connect_database(database) as connection:
                identity = connection.execute(
                    "SELECT dataset_id, manifest_sha256 FROM dataset_identity WHERE singleton_id=1",
                ).fetchone()
            mismatch = _error_code(lambda: bind_dataset_identity(
                database, **{**_DATASET, "dataset_version": "incompatible"},
            ))
            return {
                "coverage_first": first,
                "coverage_repeat": repeated,
                "coverage_conflict": coverage_conflict,
                "coverage_before": no_coverage_before,
                "coverage_at": coverage_at,
                "snapshot": snapshot,
                "no_billing_snapshot": no_billing,
                "subscriptions": subscriptions,
                "billing_events_redacted": billing_events,
                "billing_after_category_narrowing": restricted_billing,
                "dataset_identity": identity,
                "dataset_mismatch": mismatch,
            }

        output = self._both("lifecycle", scenario)
        self.assertEqual(output["coverage_first"]["status"], "accepted")
        self.assertEqual(output["coverage_repeat"]["status"], "duplicate")
        self.assertEqual(output["coverage_conflict"], "idempotency_conflict")
        self.assertEqual(output["coverage_before"], [])
        self.assertEqual(len(output["coverage_at"]), 1)
        self.assertEqual(output["snapshot"]["status"], "eligible")
        self.assertEqual(output["snapshot"]["valuation"]["mrr_minor"], 900)
        self.assertIsNone(output["no_billing_snapshot"]["valuation"])
        self.assertEqual(output["billing_events_redacted"][0]["payment_status"], "failed")
        self.assertNotIn("amount_minor", output["billing_events_redacted"][0])
        self.assertEqual(output["billing_after_category_narrowing"], [])
        self.assertEqual(output["dataset_mismatch"], "dataset identity mismatch")

    def test_artifact_round_trips_and_contract_failures_match(self):
        def scenario(database, case):
            f = self._fixture(database, case)
            feature_id = store_feature_snapshot(
                database, f["writer"], f["customer"], T1, "feature-v1", T0,
                {"sessions_7d": 4, "usage_ratio_30d": 0.75}, "limited",
            )
            feature_repeat_error = _error_code(lambda: store_feature_snapshot(
                database, f["writer"], f["customer"], T1, "feature-v1", T0,
                {"sessions_7d": 4, "usage_ratio_30d": 0.75}, "limited",
            ))
            feature_conflict = _error_code(lambda: store_feature_snapshot(
                database, f["writer"], f["customer"], T1, "feature-v1", T0,
                {"sessions_7d": 5}, "limited",
            ))
            restricted_feature = _error_code(lambda: store_feature_snapshot(
                database, f["writer"], f["customer"], T2, "restricted-v1", T1,
                {"account_contact_email": "secret@example.invalid"}, "available",
            ))
            store_churn_label(
                database, f["writer"], f["customer"], T0, 7, 1, T2, "label-v1",
                churn_type="voluntary", outcome_at=T1,
            )
            store_churn_label(database, f["writer"], f["customer"], T0, 14, "unknown", T1, "label-v1")
            negative_immature = _error_code(lambda: store_churn_label(
                database, f["writer"], f["customer"], T1, 30, 0, T2, "label-v1",
            ))
            prediction = {
                "prediction_id": "dual-prediction-id",
                "prediction_run_id": "dual-shared-run",
                "customer_id": f["customer"],
                "as_of": T1,
                "generated_at": T2,
                "status": "scored",
                "p_churn_7d": 0.1,
                "p_churn_14d": 0.2,
                "p_churn_30d": 0.4,
                "feature_version": "feature-v1",
                "model_version": "model-v1",
                "calibration_version": "cal-v1",
                "label_policy_version": "label-v1",
                "reliability_status": "limited_evidence",
                "reliability_reasons": ["stale_source_data"],
                "data_freshness_status": "partially_stale",
                "input_data_as_of": T0,
                "feature_snapshot_id": feature_id,
                "explanations_by_horizon": {"30d": [{"feature": "sessions_7d", "contribution": 0.2}]},
            }
            store_prediction(database, f["writer"], prediction)
            bad_probability = _error_code(lambda: store_prediction(
                database, f["writer"], {**prediction, "prediction_id": "bad-probability",
                                         "p_churn_14d": 0.05},
            ))
            forbidden_prediction = _error_code(lambda: store_prediction(
                database, f["reader"], {**prediction, "prediction_id": "forbidden-prediction"},
            ))
            foreign_prediction = _error_code(lambda: store_prediction(
                database, f["writer"], {**prediction, "prediction_id": "foreign-prediction",
                                         "customer_id": f["other_customer"]},
            ))
            with connect_database(database) as connection:
                feature = connection.execute(
                    "SELECT tenant_id, customer_id, as_of, feature_version, data_cutoff_at, features_json, "
                    "data_quality_status FROM feature_snapshots WHERE tenant_id=? AND feature_snapshot_id=?",
                    (f["tenant"], feature_id),
                ).fetchone()
                labels = connection.execute(
                    "SELECT horizon_days, label, outcome_at, label_observed_through, label_policy_version "
                    "FROM churn_labels WHERE tenant_id=? AND customer_id=? ORDER BY horizon_days",
                    (f["tenant"], f["customer"]),
                ).fetchall()
                saved_prediction = connection.execute(
                    "SELECT tenant_id, customer_id, prediction_id, prediction_run_id, as_of, generated_at, "
                    "p_churn_7d, p_churn_14d, p_churn_30d, feature_version, model_version, "
                    "calibration_version, label_policy_version, reliability_status, reliability_reasons_json, "
                    "data_freshness_status, uncertainty_status, explanations_by_horizon_json "
                    "FROM predictions WHERE tenant_id=? AND prediction_id=?",
                    (f["tenant"], "dual-prediction-id"),
                ).fetchone()
            # Surrogate feature ID is deliberately replaced only in the linking
            # column; the actual immutable prediction ID and run ID are compared.
            return {
                "feature": feature,
                "feature_repeat_error": feature_repeat_error,
                "feature_conflict": feature_conflict,
                "restricted_feature": restricted_feature,
                "labels": labels,
                "negative_immature": negative_immature,
                "prediction": {**saved_prediction, "feature_snapshot_id": "fixture-feature-snapshot"},
                "bad_probability": bad_probability,
                "forbidden_prediction": forbidden_prediction,
                "foreign_prediction": foreign_prediction,
            }

        output = self._both("artifacts", scenario)
        self.assertEqual(output["feature_repeat_error"], "contract_conflict")
        self.assertEqual(output["feature_conflict"], "contract_conflict")
        self.assertEqual(output["restricted_feature"], "invalid_contract")
        self.assertEqual(output["negative_immature"], "invalid_contract")
        self.assertEqual(output["bad_probability"], "invalid_contract")
        self.assertEqual(output["forbidden_prediction"], "purpose_not_authorized")
        self.assertEqual(output["foreign_prediction"], "not_found")
        self.assertEqual([row["horizon_days"] for row in output["labels"]], [7, 14])
        self.assertEqual(output["labels"][1]["label"], "unknown")
        self.assertEqual(output["prediction"]["uncertainty_status"], "not_quantified")

    def test_existing_wsgi_routes_match_for_authenticated_requests(self):
        def scenario(database, case):
            f = self._fixture(database, case)
            admin_token = create_service_principal(
                database, f["tenant"], role="admin", authorized_sources=(f["source"],),
                authorized_purposes=("integration_health",),
            )
            app = create_app(database)
            event = {
                "source": f["source"], "source_event_id": "api-event",
                "external_customer_id": f["external"], "event_type": "session_started",
                "occurred_at": T0, "attributes": {"feature": "reports"}, "schema_version": "1.0",
            }
            set_integration_event_categories(database, f["tenant"], f["source"], ("usage",))
            accepted = _request(app, "POST", "/v1/ingest/events", token=f["integration_token"], body=event)
            duplicate = _request(app, "POST", "/v1/ingest/events", token=f["integration_token"], body=event)
            conflict = _request(
                app, "POST", "/v1/ingest/events", token=f["integration_token"],
                body={**event, "attributes": {"feature": "exports"}},
            )
            missing = _request(app, "POST", "/v1/ingest/events", body=event)
            wrong_tenant = _request(
                app, "POST", "/v1/ingest/events", token=f["integration_token"],
                body={**event, "source_event_id": "wrong-tenant-event", "tenant_id": "forged-tenant"},
            )
            wrong_category = _request(
                app, "POST", "/v1/ingest/events", token=f["integration_token"],
                body={**event, "source_event_id": "wrong-category-event", "event_type": "subscription_created",
                      "attributes": {"subscription_id": "forbidden-sub", "status": "active", "started_at": T0}},
            )
            invalid_event = _request(
                app, "POST", "/v1/ingest/events", token=f["integration_token"],
                body={**event, "source_event_id": "invalid-event", "event_type": "unrecognized_event"},
            )
            health = _request(app, "GET", "/v1/integrations", token=f["integration_token"])
            forbidden_admin = _request(app, "GET", "/v1/admin/integrations", token=f["integration_token"])
            admin = _request(app, "GET", "/v1/admin/integrations", token=admin_token)
            def stable_health(response):
                stable = []
                timestamps_valid = True
                for item in response["body"]["integrations"]:
                    for field in ("last_successful_ingestion_at", "last_failure_at"):
                        timestamp = item.get(field)
                        if timestamp is not None:
                            try:
                                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            except (AttributeError, ValueError):
                                timestamps_valid = False
                    stable.append({
                        key: value for key, value in item.items()
                        if key not in {"last_successful_ingestion_at", "last_failure_at"}
                    })
                return {"status": response["status"], "integrations": stable}, timestamps_valid

            stable_health_result, health_timestamps_valid = stable_health(health)
            stable_admin_result, admin_timestamps_valid = stable_health(admin)
            with connect_database(database) as connection:
                persisted_api_events = connection.execute(
                    "SELECT COUNT(*) AS count FROM canonical_events WHERE tenant_id=? AND source_event_id=?",
                    (f["tenant"], "api-event"),
                ).fetchone()["count"]
                rejected_api_events = connection.execute(
                    "SELECT COUNT(*) AS count FROM canonical_events WHERE tenant_id=? AND source_event_id IN "
                    "('wrong-tenant-event', 'wrong-category-event', 'invalid-event')",
                    (f["tenant"],),
                ).fetchone()["count"]
            return {
                "accepted": {"status": accepted["status"], "body": accepted["body"]},
                "duplicate": {"status": duplicate["status"], "body": duplicate["body"]},
                "conflict": {"status": conflict["status"], "body": conflict["body"]},
                "missing": {"status": missing["status"], "body": missing["body"]},
                "wrong_tenant": {"status": wrong_tenant["status"], "body": wrong_tenant["body"]},
                "wrong_category": {"status": wrong_category["status"], "body": wrong_category["body"]},
                "invalid_event": {"status": invalid_event["status"], "body": invalid_event["body"]},
                "persisted_api_events": persisted_api_events,
                "rejected_api_events": rejected_api_events,
                "health": stable_health_result,
                "forbidden_admin": {"status": forbidden_admin["status"], "body": forbidden_admin["body"]},
                "admin": stable_admin_result,
                "health_timestamps_valid": health_timestamps_valid,
                "admin_timestamps_valid": admin_timestamps_valid,
                "dsn_leak": "postgresql://" in json.dumps(
                    [accepted["body"], duplicate["body"], conflict["body"], missing["body"],
                     wrong_tenant["body"], wrong_category["body"], invalid_event["body"]],
                ),
            }

        output = self._both("wsgi", scenario)
        self.assertTrue(output["accepted"]["status"].startswith("201"))
        self.assertTrue(output["duplicate"]["status"].startswith("200"))
        self.assertTrue(output["conflict"]["status"].startswith("409"))
        self.assertTrue(output["missing"]["status"].startswith("401"))
        self.assertTrue(output["wrong_tenant"]["status"].startswith("400"))
        self.assertTrue(output["wrong_category"]["status"].startswith("403"))
        self.assertTrue(output["invalid_event"]["status"].startswith("400"))
        self.assertEqual(output["persisted_api_events"], 1)
        self.assertEqual(output["rejected_api_events"], 0)
        self.assertTrue(output["health"]["status"].startswith("200"))
        self.assertTrue(output["forbidden_admin"]["status"].startswith("401"))
        self.assertTrue(output["admin"]["status"].startswith("200"))
        self.assertTrue(output["health_timestamps_valid"])
        self.assertTrue(output["admin_timestamps_valid"])
        self.assertFalse(output["dsn_leak"])

    def test_concurrent_identical_ingestion_has_equivalent_external_result(self):
        def scenario(database, case):
            f = self._fixture(database, case)
            payload = {
                "source": f["source"], "source_event_id": "concurrent-event",
                "external_customer_id": f["external"], "event_type": "session_started",
                "occurred_at": T0, "attributes": {"feature": "reports"}, "schema_version": "1.0",
            }

            def write(_):
                return ingest_event(database, f["integration"], payload, received_at=T1)

            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(write, range(8)))
            conflict_payloads = (
                {**payload, "source_event_id": "concurrent-conflict", "attributes": {"feature": "reports"}},
                {**payload, "source_event_id": "concurrent-conflict", "attributes": {"feature": "exports"}},
            )

            def compete(candidate):
                try:
                    result = ingest_event(database, f["integration"], candidate, received_at=T1)
                    return "duplicate" if result["duplicate"] else "accepted"
                except DataFoundationError as error:
                    return error.code

            with ThreadPoolExecutor(max_workers=2) as pool:
                conflict_outcomes = list(pool.map(compete, conflict_payloads))
            with connect_database(database) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) AS count FROM canonical_events WHERE tenant_id=? AND source_event_id=?",
                    (f["tenant"], "concurrent-event"),
                ).fetchone()["count"]
                conflict_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM canonical_events WHERE tenant_id=? AND source_event_id=?",
                    (f["tenant"], "concurrent-conflict"),
                ).fetchone()["count"]
            return {
                "statuses": sorted(item["status"] for item in outcomes),
                "event_count": count,
                "conflicting_statuses": sorted(conflict_outcomes),
                "conflicting_event_count": conflict_count,
            }

        output = self._both("concurrency", scenario)
        self.assertEqual(output["statuses"].count("accepted"), 1)
        self.assertEqual(output["statuses"].count("duplicate"), 7)
        self.assertEqual(output["event_count"], 1)
        self.assertEqual(output["conflicting_statuses"], ["accepted", "idempotency_conflict"])
        self.assertEqual(output["conflicting_event_count"], 1)

    def test_subtype_failure_rolls_back_event_and_subscription_owner_on_both_backends(self):
        def scenario(database, case):
            f = self._fixture(database, case)
            trigger = f"dual_abort_subtype_{case}"
            function = f"dual_abort_subtype_fn_{case}"
            with connect_database(database) as connection:
                if connection.backend == "sqlite":
                    connection.execute(
                        f'CREATE TRIGGER "{trigger}" BEFORE INSERT ON subscription_events '
                        "BEGIN SELECT RAISE(ABORT, 'injected subtype failure'); END",
                    )
                else:
                    connection.execute(
                        f'CREATE FUNCTION "{function}"() RETURNS trigger LANGUAGE plpgsql AS $$ '
                        "BEGIN RAISE EXCEPTION 'injected subtype failure'; END $$",
                    )
                    connection.execute(
                        f'CREATE TRIGGER "{trigger}" BEFORE INSERT ON subscription_events '
                        f'FOR EACH ROW EXECUTE FUNCTION "{function}"()',
                    )
            payload = {
                "source": f["source"], "source_event_id": "rollback-subscription-event",
                "external_customer_id": f["external"], "event_type": "subscription_created",
                "occurred_at": T0,
                "attributes": {"subscription_id": "rollback-subscription", "status": "active",
                               "started_at": T0},
                "schema_version": "1.0",
            }
            failed = False
            try:
                ingest_event(database, f["integration"], payload, received_at=T1)
            except Exception:
                failed = True
            with connect_database(database) as connection:
                state = {
                    table: connection.execute(
                        f"SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=? AND {column}=?",
                        (f["tenant"], value),
                    ).fetchone()["count"]
                    for table, column, value in (
                        ("canonical_events", "source_event_id", "rollback-subscription-event"),
                        ("subscription_events", "subscription_id", "rollback-subscription"),
                        ("subscription_owners", "subscription_id", "rollback-subscription"),
                        ("subscriptions", "subscription_id", "rollback-subscription"),
                    )
                }
            return {"failed": failed, "state": state}

        output = self._both("rollback", scenario)
        self.assertTrue(output["failed"])
        self.assertEqual(set(output["state"].values()), {0})

    def test_subscription_owner_race_has_equivalent_tenant_scoped_result(self):
        def scenario(database, case):
            f = self._fixture(database, case)
            customer_b = f"dual-{case}-customer-b"
            external_b = f"dual-{case}-external-b"
            create_customer(database, f["tenant"], customer_b)
            map_customer_identity(database, f["tenant"], f["source"], external_b, customer_b)
            contenders = Barrier(2)

            def claim(item):
                event_id, external, started_at = item
                payload = {
                    "source": f["source"], "source_event_id": event_id,
                    "external_customer_id": external, "event_type": "subscription_created",
                    "occurred_at": started_at,
                    "attributes": {"subscription_id": "shared-subscription", "status": "active",
                                   "started_at": started_at},
                    "schema_version": "1.0",
                }
                contenders.wait()
                try:
                    return ingest_event(database, f["integration"], payload, received_at=T1)["status"]
                except DataFoundationError as error:
                    return error.code

            attempts = (
                ("owner-a", f["external"], T0),
                ("owner-b", external_b, T1),
            )
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(claim, attempts))
            with connect_database(database) as connection:
                owner_rows = connection.execute(
                    "SELECT customer_id FROM subscription_owners WHERE tenant_id=? AND subscription_id=?",
                    (f["tenant"], "shared-subscription"),
                ).fetchall()
                event_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM canonical_events WHERE tenant_id=? "
                    "AND source_event_id IN ('owner-a', 'owner-b')",
                    (f["tenant"],),
                ).fetchone()["count"]
            return {
                "outcomes": sorted(outcomes),
                "owner_count": len(owner_rows),
                "event_count": event_count,
            }

        output = self._both("owner-race", scenario)
        self.assertEqual(output["outcomes"], ["accepted", "contract_conflict"])
        self.assertEqual(output["owner_count"], 1)
        self.assertEqual(output["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
