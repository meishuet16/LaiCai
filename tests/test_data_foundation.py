import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from retaniq.api import create_app
from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_integration,
    create_customer,
    create_integration,
    create_tenant,
    get_account_snapshot_as_of,
    get_events_as_of,
    get_integration_health,
    get_subscriptions_as_of,
    initialize_database,
    list_eligible_accounts_as_of,
    map_customer_identity,
    store_churn_label,
    store_feature_snapshot,
    store_prediction,
    ingest_event,
)
from retaniq.importer import import_csv, iter_replay_events


T0 = "2026-10-01T00:00:00.000000Z"
T1 = "2026-10-05T00:00:00.000000Z"
T2 = "2026-10-10T00:00:00.000000Z"
T3 = "2026-10-12T00:00:00.000000Z"


def post_wsgi(app, path, body, token=None):
    encoded = json.dumps(body).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(encoded)),
        "CONTENT_TYPE": "application/json",
        "wsgi.input": io.BytesIO(encoded),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response))
    response["body"] = json.loads(payload) if payload else None
    return response


def get_wsgi(app, path, token=None):
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "CONTENT_LENGTH": "0"}
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response))
    response["body"] = json.loads(payload) if payload else None
    return response


def usage_event(source_event_id="evt-usage-1", **overrides):
    event = {
        "source": "product_app",
        "source_event_id": source_event_id,
        "external_customer_id": "acct-a",
        "event_type": "session_started",
        "occurred_at": T0,
        "attributes": {"feature": "reports"},
        "schema_version": "1.0",
    }
    event.update(overrides)
    return event


class DataFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "retaniq.sqlite3")
        initialize_database(self.db)
        create_tenant(self.db, "tenant-a")
        create_tenant(self.db, "tenant-b")
        self.token_a = create_integration(
            self.db, "tenant-a", "product_app", authorized_categories=("usage", "billing", "subscription"),
        )
        self.token_b = create_integration(self.db, "tenant-b", "product_app")
        create_customer(self.db, "tenant-a", "customer-a")
        create_customer(self.db, "tenant-b", "customer-b")
        map_customer_identity(self.db, "tenant-a", "product_app", "acct-a", "customer-a")
        map_customer_identity(self.db, "tenant-b", "product_app", "acct-a", "customer-b")
        self.principal_a = authenticate_integration(self.db, self.token_a)
        self.principal_b = authenticate_integration(self.db, self.token_b)

    def tearDown(self):
        self.temp.cleanup()

    def test_schema_001_upgrade_preserves_history_and_refuses_conflicting_owners(self):
        migration_001 = (Path(__file__).resolve().parents[1] / "migrations" / "001_data_foundation.sql").read_text(
            encoding="utf-8",
        )

        def prepare_legacy(path, conflicting_owner):
            connection = sqlite3.connect(path)
            connection.execute(
                "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)",
            )
            connection.executescript(
                "BEGIN IMMEDIATE;\n" + migration_001 +
                "\nINSERT INTO schema_migrations(version, applied_at) "
                "VALUES ('001_data_foundation', '2026-10-01T00:00:00Z');\nCOMMIT;"
            )
            with connection:
                connection.execute("INSERT INTO tenants(tenant_id) VALUES ('tenant-a')")
                connection.execute(
                    "INSERT INTO customers(tenant_id, customer_id, account_status, created_at) "
                    "VALUES ('tenant-a', 'customer-a', 'active', ?)", (T0,),
                )
                for source in ("product_app", "idle_app"):
                    connection.execute(
                        "INSERT INTO integrations(integration_id, tenant_id, source, token_digest, "
                        "authorized_purposes_json, schema_version, mapping_version, created_at) "
                        "VALUES (?, 'tenant-a', ?, ?, '[\"retention_inference\"]', '1.0', 'canonical-v1', ?)",
                        (f"legacy-{source}", source, f"digest-{source}", T0),
                    )
                connection.execute(
                    "INSERT INTO canonical_events(event_id, tenant_id, source, source_event_id, customer_id, "
                    "category, event_type, occurred_at, received_at, source_available_at, schema_version, "
                    "mapping_version, normalized_payload_sha256) VALUES (1, 'tenant-a', 'product_app', "
                    "'legacy-sub-1', 'customer-a', 'subscription', 'subscription_created', ?, ?, NULL, '1.0', "
                    "'canonical-v1', 'hash-1')", (T0, T0),
                )
                connection.execute(
                    "INSERT INTO subscription_events(tenant_id, event_id, subscription_id, customer_id, "
                    "event_type, changed_fields_json, status, started_at, occurred_at, received_at) "
                    "VALUES ('tenant-a', 1, 'sub-legacy', 'customer-a', 'subscription_created', "
                    "'[\"status\",\"started_at\"]', 'active', ?, ?, ?)", (T0, T0, T0),
                )
                connection.execute(
                    "INSERT INTO canonical_events(event_id, tenant_id, source, source_event_id, customer_id, "
                    "category, event_type, occurred_at, received_at, source_available_at, schema_version, "
                    "mapping_version, normalized_payload_sha256) VALUES (3, 'tenant-a', 'product_app', "
                    "'legacy-usage', 'customer-a', 'usage', 'session_started', ?, ?, NULL, '1.0', "
                    "'canonical-v1', 'hash-3')", (T0, T0),
                )
                connection.execute(
                    "INSERT INTO subscriptions(tenant_id, subscription_id, customer_id, status, started_at, updated_at) "
                    "VALUES ('tenant-a', 'sub-legacy', 'customer-a', 'active', ?, ?)", (T0, T0),
                )
                if conflicting_owner:
                    connection.execute(
                        "INSERT INTO customers(tenant_id, customer_id, account_status, created_at) "
                        "VALUES ('tenant-a', 'customer-other', 'active', ?)", (T0,),
                    )
                    connection.execute(
                        "INSERT INTO canonical_events(event_id, tenant_id, source, source_event_id, customer_id, "
                        "category, event_type, occurred_at, received_at, source_available_at, schema_version, "
                        "mapping_version, normalized_payload_sha256) VALUES (2, 'tenant-a', 'billing_app', "
                        "'legacy-sub-2', 'customer-other', 'subscription', 'subscription_updated', ?, ?, NULL, '1.0', "
                        "'canonical-v1', 'hash-2')", (T1, T1),
                    )
                    connection.execute(
                        "INSERT INTO subscription_events(tenant_id, event_id, subscription_id, customer_id, "
                        "event_type, changed_fields_json, status, started_at, occurred_at, received_at) "
                        "VALUES ('tenant-a', 2, 'sub-legacy', 'customer-other', 'subscription_updated', "
                        "'[\"status\"]', 'active', ?, ?, ?)", (T0, T1, T1),
                    )
            connection.close()

        legacy_path = str(Path(self.temp.name) / "legacy-v1.sqlite3")
        prepare_legacy(legacy_path, conflicting_owner=False)
        initialize_database(legacy_path)
        connection = sqlite3.connect(legacy_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM subscription_events").fetchone()[0], 1)
            self.assertEqual(
                connection.execute(
                    "SELECT customer_id FROM subscription_owners WHERE tenant_id='tenant-a' AND subscription_id='sub-legacy'",
                ).fetchone()[0], "customer-a",
            )
            self.assertIn(
                "subscription_owners",
                {row[2] for row in connection.execute("PRAGMA foreign_key_list(subscription_events)")},
            )
            self.assertIsNotNone(connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='service_principals'",
            ).fetchone())
            self.assertEqual(
                {row[0] for row in connection.execute(
                    "SELECT category FROM integration_event_categories "
                    "WHERE tenant_id='tenant-a' AND source='product_app'",
                )},
                {"usage", "subscription"},
            )
            self.assertEqual(
                [row[0] for row in connection.execute(
                    "SELECT category FROM integration_event_categories "
                    "WHERE tenant_id='tenant-a' AND source='idle_app'",
                )],
                ["usage"],
            )
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM schema_migrations "
                    "WHERE version='003_integration_event_categories'",
                ).fetchone()[0],
                1,
            )
        finally:
            connection.close()

        conflicted_path = str(Path(self.temp.name) / "legacy-conflicted.sqlite3")
        prepare_legacy(conflicted_path, conflicting_owner=True)
        with self.assertRaises(DataFoundationError) as caught:
            initialize_database(conflicted_path)
        self.assertEqual(caught.exception.code, "contract_conflict")
        connection = sqlite3.connect(conflicted_path)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM schema_migrations WHERE version LIKE '002_%'").fetchone()[0],
                0,
            )
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='subscription_owners'",
            ).fetchone())
        finally:
            connection.close()

    def test_ingest_endpoint_rejects_missing_authentication(self):
        response = post_wsgi(create_app(self.db), "/v1/ingest/events", usage_event())
        self.assertTrue(response["status"].startswith("401"))
        self.assertEqual(response["body"]["error"], "unauthorized")

    def test_authenticated_push_endpoint_accepts_then_deduplicates(self):
        app = create_app(self.db)
        first = post_wsgi(app, "/v1/ingest/events", usage_event(), self.token_a)
        repeat = post_wsgi(app, "/v1/ingest/events", usage_event(), self.token_a)
        self.assertTrue(first["status"].startswith("201"))
        self.assertTrue(repeat["status"].startswith("200"))
        self.assertEqual(first["body"]["event_id"], repeat["body"]["event_id"])

    def test_integration_health_endpoint_is_authenticated_and_redacted(self):
        app = create_app(self.db)
        missing_auth = get_wsgi(app, "/v1/integrations")
        response = get_wsgi(app, "/v1/integrations", self.token_a)
        self.assertTrue(missing_auth["status"].startswith("401"))
        self.assertTrue(response["status"].startswith("200"))
        rendered = json.dumps(response["body"])
        self.assertIn("product_app", rendered)
        self.assertNotIn(self.token_a, rendered)
        self.assertNotIn("token_digest", rendered)

    def test_tenant_is_derived_from_authentication_and_body_tenant_is_rejected(self):
        with self.assertRaises(DataFoundationError) as caught:
            ingest_event(self.db, self.principal_a, usage_event(tenant_id="tenant-b"), received_at=T1)
        self.assertEqual(caught.exception.code, "invalid_event")
        self.assertNotIn("tenant-b", str(caught.exception))
        with self.assertRaises(DataFoundationError):
            ingest_event(
                self.db, self.principal_a,
                {**usage_event(), "source_available_at": T0}, received_at=T1,
            )

    def test_unknown_identity_is_rejected_without_fuzzy_merge(self):
        with self.assertRaises(DataFoundationError) as caught:
            ingest_event(
                self.db,
                self.principal_a,
                usage_event(external_customer_id="unmapped-account"),
                received_at=T1,
            )
        self.assertEqual(caught.exception.code, "identity_not_mapped")

    def test_source_authorization_enforces_configured_purposes(self):
        token = create_integration(
            self.db, "tenant-b", "billing_app", authorized_purposes=("retention_inference",),
            authorized_categories=("billing",),
        )
        map_customer_identity(self.db, "tenant-b", "billing_app", "acct-b", "customer-b")
        principal = authenticate_integration(self.db, token)
        payload = {
            "source": "billing_app", "source_event_id": "evt-bill", "external_customer_id": "acct-b",
            "event_type": "payment_failed", "occurred_at": T1,
            "attributes": {"amount_minor": 100, "currency": "MYR"}, "schema_version": "1.0",
        }
        with self.assertRaises(DataFoundationError) as caught:
            ingest_event(self.db, principal, payload, received_at=T2)
        self.assertEqual(caught.exception.code, "source_not_authorized")

    def test_data_reads_and_writes_enforce_purpose_scope(self):
        token = create_integration(
            self.db, "tenant-a", "identity_bridge", authorized_purposes=("identity_mapping",),
        )
        principal = authenticate_integration(self.db, token)

        restricted_operations = (
            lambda: get_events_as_of(self.db, principal, "customer-a", T2, category="usage"),
            lambda: get_account_snapshot_as_of(self.db, principal, "customer-a", T2),
            lambda: store_feature_snapshot(
                self.db, principal, "customer-a", T1, "features-v1", T1, {"sessions_7d": 1}, "available",
            ),
            lambda: store_churn_label(
                self.db, principal, "customer-a", T0, 7, "unknown", T0, "label-v1",
            ),
            lambda: store_prediction(
                self.db, principal,
                {"prediction_id": "pred-scope", "prediction_run_id": "run-scope", "customer_id": "customer-a",
                 "as_of": T1, "generated_at": T2, "status": "abstained", "p_churn_7d": None,
                 "p_churn_14d": None, "p_churn_30d": None, "feature_version": "features-v1",
                 "model_version": "model-v1", "calibration_version": "cal-v1",
                 "reliability_status": "insufficient_evidence", "data_freshness_status": "unknown"},
            ),
        )
        for index, operation in enumerate(restricted_operations):
            with self.subTest(operation=index):
                with self.assertRaises(DataFoundationError) as caught:
                    operation()
                self.assertEqual(caught.exception.code, "purpose_not_authorized")

    def test_integration_cannot_write_ml_artifacts_for_other_source_or_tenant_accounts(self):
        create_customer(self.db, "tenant-a", "customer-billing-only")
        map_customer_identity(
            self.db, "tenant-a", "billing_app", "acct-billing-only", "customer-billing-only",
        )

        def operations(customer_id, suffix):
            return (
                lambda: store_feature_snapshot(
                    self.db, self.principal_a, customer_id, T1, f"cross-source-{suffix}", T1,
                    {"sessions_7d": 1}, "available",
                ),
                lambda: store_churn_label(
                    self.db, self.principal_a, customer_id, T0, 7, "unknown", T1,
                    f"cross-source-label-{suffix}",
                ),
                lambda: store_prediction(
                    self.db, self.principal_a,
                    {"prediction_id": f"cross-source-pred-{suffix}",
                     "prediction_run_id": f"cross-source-run-{suffix}", "customer_id": customer_id,
                     "as_of": T1, "generated_at": T2, "status": "abstained", "p_churn_7d": None,
                     "p_churn_14d": None, "p_churn_30d": None, "feature_version": "features-v1",
                     "model_version": "model-v1", "calibration_version": "cal-v1",
                     "reliability_status": "insufficient_evidence", "data_freshness_status": "unknown"},
                ),
            )

        for customer_id, suffix in (("customer-billing-only", "billing"), ("customer-b", "tenant")):
            for index, operation in enumerate(operations(customer_id, suffix)):
                with self.subTest(customer=customer_id, artifact=index):
                    with self.assertRaises(DataFoundationError):
                        operation()

        from retaniq import data_foundation as foundation
        writer_token = foundation.create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("product_app",),
            authorized_purposes=("retention_inference", "model_artifact_write"),
        )
        writer = foundation.authenticate_service_principal(self.db, writer_token)
        for customer_id in ("customer-billing-only", "customer-b"):
            with self.subTest(service_customer=customer_id):
                with self.assertRaises(DataFoundationError) as denied:
                    store_feature_snapshot(
                        self.db, writer, customer_id, T1, f"unauthorized-service-{customer_id}", T1,
                        {"sessions_7d": 1}, "available",
                    )
                self.assertEqual(denied.exception.code, "not_found")

    def test_model_artifact_write_requires_analyst_role_and_explicit_purpose(self):
        from retaniq import data_foundation as foundation

        principals = (
            foundation.authenticate_service_principal(
                self.db,
                foundation.create_service_principal(
                    self.db, "tenant-a", role="analyst", authorized_sources=("product_app",),
                    authorized_purposes=("retention_inference",),
                ),
            ),
            foundation.authenticate_service_principal(
                self.db,
                foundation.create_service_principal(
                    self.db, "tenant-a", role="operator", authorized_sources=("product_app",),
                    authorized_purposes=("retention_inference", "model_artifact_write"),
                ),
            ),
        )
        for index, principal in enumerate(principals):
            with self.subTest(principal=index):
                with self.assertRaises(DataFoundationError) as denied:
                    store_feature_snapshot(
                        self.db, principal, "customer-a", T1, f"unauthorized-writer-{index}", T1,
                        {"sessions_7d": 1}, "available",
                    )
                expected_code = "purpose_not_authorized" if index == 0 else "unauthorized"
                self.assertEqual(denied.exception.code, expected_code)

    def test_authorized_model_writer_can_read_multiple_sources_and_persist_artifacts(self):
        from retaniq import data_foundation as foundation

        billing_token = create_integration(
            self.db, "tenant-a", "billing_app", authorized_purposes=("retention_inference",),
            authorized_categories=("billing",),
        )
        billing = authenticate_integration(self.db, billing_token)
        map_customer_identity(self.db, "tenant-a", "billing_app", "acct-a-billing", "customer-a")
        ingest_event(
            self.db, self.principal_a, usage_event("evt-model-writer-usage"), received_at=T0,
        )
        ingest_event(
            self.db, billing,
            {"source": "billing_app", "source_event_id": "evt-model-writer-payment",
             "external_customer_id": "acct-a-billing", "event_type": "payment_failed",
             "occurred_at": T1, "attributes": {}, "schema_version": "1.0"},
            received_at=T1,
        )
        writer_token = foundation.create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("product_app", "billing_app"),
            authorized_purposes=("retention_inference", "model_artifact_write"),
        )
        writer = foundation.authenticate_service_principal(self.db, writer_token)
        snapshot = get_account_snapshot_as_of(self.db, writer, "customer-a", T2)
        self.assertEqual(len(snapshot["usage_events"]), 1)
        self.assertEqual(len(snapshot["billing_events"]), 1)

        feature_id = store_feature_snapshot(
            self.db, writer, "customer-a", T2, "multi-source-features-v1", T2,
            {"sessions_7d": len(snapshot["usage_events"]),
             "failed_payments_30d": len(snapshot["billing_events"])}, "available",
        )
        store_churn_label(
            self.db, writer, "customer-a", T0, 7, "unknown", T1, "multi-source-label-v1",
        )
        prediction_id = store_prediction(
            self.db, writer,
            {"prediction_id": "multi-source-prediction", "prediction_run_id": "multi-source-run",
             "customer_id": "customer-a", "as_of": T2, "generated_at": T3, "status": "abstained",
             "p_churn_7d": None, "p_churn_14d": None, "p_churn_30d": None,
             "feature_version": "multi-source-features-v1", "model_version": "model-v1",
             "calibration_version": "cal-v1", "reliability_status": "limited_evidence",
             "data_freshness_status": "fresh", "feature_snapshot_id": feature_id,
             "explanations_by_horizon": {"30d": [{"feature": "failed_payments_30d",
                                                  "contribution": 0.25}]}},
        )
        self.assertEqual(prediction_id, "multi-source-prediction")

    def test_usage_only_integration_cannot_submit_subscription_or_billing_categories(self):
        token = create_integration(
            self.db, "tenant-a", "usage_only", authorized_purposes=("retention_inference",),
        )
        map_customer_identity(self.db, "tenant-a", "usage_only", "acct-usage-only", "customer-a")
        principal = authenticate_integration(self.db, token)
        ingest_event(
            self.db, principal,
            {"source": "usage_only", "source_event_id": "evt-authorized-usage",
             "external_customer_id": "acct-usage-only", "event_type": "feature_used",
             "occurred_at": T0, "attributes": {"feature": "reports", "quantity": 1, "unit": "events"},
             "schema_version": "1.0"},
            received_at=T0,
        )
        prohibited = (
            {"source": "usage_only", "source_event_id": "evt-unapproved-termination",
             "external_customer_id": "acct-usage-only", "event_type": "subscription_cancelled_effective",
             "occurred_at": T1, "attributes": {"subscription_id": "sub-usage-only-termination"},
             "schema_version": "1.0"},
            {"source": "usage_only", "source_event_id": "evt-unapproved-payment",
             "external_customer_id": "acct-usage-only", "event_type": "payment_failed",
             "occurred_at": T1, "attributes": {"amount_minor": 500, "currency": "MYR"},
             "schema_version": "1.0"},
        )
        for payload in prohibited:
            with self.subTest(event_type=payload["event_type"]):
                with self.assertRaises(DataFoundationError) as caught:
                    ingest_event(self.db, principal, payload, received_at=T1)
                self.assertEqual(caught.exception.code, "event_category_not_authorized")
        http_termination = {
            **prohibited[0], "source_event_id": "evt-unapproved-http-termination",
        }
        response = post_wsgi(
            create_app(self.db), "/v1/ingest/events", http_termination, token,
        )
        self.assertTrue(response["status"].startswith("403"))
        self.assertEqual(response["body"]["error"], "event_category_not_authorized")
        connection = sqlite3.connect(self.db)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM canonical_events WHERE source='usage_only'",
                ).fetchone()[0], 1,
            )
        finally:
            connection.close()

    def test_multicategory_integration_requires_explicit_category_grants(self):
        token = create_integration(
            self.db, "tenant-a", "multi_category", authorized_purposes=("retention_inference",),
            authorized_categories=("usage", "subscription"),
        )
        map_customer_identity(self.db, "tenant-a", "multi_category", "acct-multi", "customer-a")
        principal = authenticate_integration(self.db, token)
        accepted = ingest_event(
            self.db, principal,
            {"source": "multi_category", "source_event_id": "evt-explicit-termination",
             "external_customer_id": "acct-multi", "event_type": "subscription_cancelled_effective",
             "occurred_at": T1, "attributes": {"subscription_id": "sub-explicit-termination"},
             "schema_version": "1.0"},
            received_at=T1,
        )
        self.assertEqual(accepted["status"], "accepted")
        with self.assertRaises(DataFoundationError) as denied:
            ingest_event(
                self.db, principal,
                {"source": "multi_category", "source_event_id": "evt-explicit-but-ungranted-payment",
                 "external_customer_id": "acct-multi", "event_type": "payment_failed",
                 "occurred_at": T1, "attributes": {"amount_minor": 500, "currency": "MYR"},
                 "schema_version": "1.0"},
                received_at=T1,
            )
        self.assertEqual(denied.exception.code, "event_category_not_authorized")

    def test_operator_can_replace_event_category_grants_and_refresh_principal(self):
        from retaniq.data_foundation import set_integration_event_categories

        token = create_integration(
            self.db, "tenant-a", "change_categories", authorized_purposes=("retention_inference",),
        )
        map_customer_identity(self.db, "tenant-a", "change_categories", "acct-change", "customer-a")
        stale_principal = authenticate_integration(self.db, token)
        set_integration_event_categories(
            self.db, "tenant-a", "change_categories", ("usage", "subscription"),
        )
        termination = {
            "source": "change_categories", "source_event_id": "evt-after-category-config",
            "external_customer_id": "acct-change", "event_type": "subscription_cancelled_effective",
            "occurred_at": T1, "attributes": {"subscription_id": "sub-after-config"},
            "schema_version": "1.0",
        }
        with self.assertRaises(DataFoundationError) as stale:
            ingest_event(self.db, stale_principal, termination, received_at=T1)
        self.assertEqual(stale.exception.code, "unauthorized")
        refreshed = authenticate_integration(self.db, token)
        self.assertEqual(
            ingest_event(self.db, refreshed, termination, received_at=T1)["status"], "accepted",
        )

    def test_retention_only_reader_can_read_usage_but_not_valuation_data(self):
        ingest_event(self.db, self.principal_a, usage_event(), received_at=T0)
        self.add_subscription(
            "evt-retention-reader-sub", "subscription_created", T0,
            {"subscription_id": "sub-retention-reader", "status": "active", "started_at": T0,
             "billing_interval": "month", "billing_interval_count": 1,
             "amount_minor": 2500, "currency": "MYR"},
        )
        payment = {
            "source": "product_app", "source_event_id": "evt-retention-reader-payment",
            "external_customer_id": "acct-a", "event_type": "payment_failed", "occurred_at": T1,
            "attributes": {"subscription_id": "sub-retention-reader", "amount_minor": 2500, "currency": "MYR"},
            "schema_version": "1.0",
        }
        ingest_event(self.db, self.principal_a, payment, received_at=T1)
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "UPDATE integrations SET authorized_purposes_json='[\"retention_inference\"]' "
                "WHERE integration_id=?", (self.principal_a.integration_id,),
            )
            connection.commit()
        finally:
            connection.close()
        principal = authenticate_integration(self.db, self.token_a)

        usage = get_events_as_of(self.db, principal, "customer-a", T2, category="usage")
        self.assertEqual(len(usage), 1)
        billing = get_events_as_of(self.db, principal, "customer-a", T2, category="billing")
        self.assertEqual(billing[0]["payment_status"], "failed")
        self.assertNotIn("amount_minor", billing[0])
        self.assertNotIn("currency", billing[0])
        snapshot = get_account_snapshot_as_of(self.db, principal, "customer-a", T2)
        self.assertIsNone(snapshot["valuation"])
        self.assertNotIn("amount_minor", snapshot["subscriptions"][0])
        self.assertNotIn("mrr_minor", snapshot["subscriptions"][0])
        financial_features = (
            {"mrr_minor": 2500}, {"amount_minor": 2500}, {"currency": "MYR"},
        )
        for index, features in enumerate(financial_features):
            with self.subTest(features=features):
                with self.assertRaises(DataFoundationError) as caught:
                    store_feature_snapshot(
                        self.db, principal, "customer-a", T2, f"financial-{index}", T2,
                        features, "available",
                    )
                self.assertEqual(caught.exception.code, "invalid_contract")
        with self.assertRaises(DataFoundationError) as financial_explanation:
            store_prediction(
                self.db, principal,
                {"prediction_id": "pred-financial-scope", "prediction_run_id": "run-financial-scope",
                 "customer_id": "customer-a", "as_of": T2, "generated_at": T2, "status": "abstained",
                 "p_churn_7d": None, "p_churn_14d": None, "p_churn_30d": None,
                 "feature_version": "features-v1", "model_version": "model-v1",
                 "calibration_version": "cal-v1", "reliability_status": "insufficient_evidence",
                 "data_freshness_status": "unknown", "explanations_by_horizon": {"mrr_minor": 2500}},
            )
        self.assertEqual(financial_explanation.exception.code, "invalid_contract")

    def test_integration_reads_are_source_scoped_and_service_reads_aggregate_only_granted_sources(self):
        from retaniq import data_foundation as foundation

        billing_token = create_integration(
            self.db, "tenant-a", "billing_app", authorized_purposes=("retention_inference",),
            authorized_categories=("subscription",),
        )
        excluded_token = create_integration(
            self.db, "tenant-a", "support_app", authorized_purposes=("retention_inference",),
        )
        map_customer_identity(self.db, "tenant-a", "billing_app", "acct-a-billing", "customer-a")
        map_customer_identity(self.db, "tenant-a", "support_app", "acct-a-support", "customer-a")
        billing_principal = authenticate_integration(self.db, billing_token)
        excluded_principal = authenticate_integration(self.db, excluded_token)
        billing_subscription = {
            "source": "billing_app", "source_event_id": "evt-sub-from-billing",
            "external_customer_id": "acct-a-billing", "event_type": "subscription_created",
            "occurred_at": T0,
            "attributes": {"subscription_id": "sub-billing", "status": "active", "started_at": T0},
            "schema_version": "1.0",
        }
        ingest_event(self.db, billing_principal, billing_subscription, received_at=T0)
        ingest_event(
            self.db, self.principal_a,
            usage_event("evt-usage-from-product"), received_at=T1,
        )
        ingest_event(
            self.db, excluded_principal,
            {"source": "support_app", "source_event_id": "evt-usage-ungranted",
             "external_customer_id": "acct-a-support", "event_type": "feature_used",
             "occurred_at": T1, "attributes": {"feature": "reports"}, "schema_version": "1.0"},
            received_at=T1,
        )

        # A source token in the same tenant must not see billing's subscription.
        self.assertEqual(
            get_events_as_of(self.db, self.principal_a, "customer-a", T2, category="subscription"), [],
        )
        self.assertEqual(get_subscriptions_as_of(self.db, self.principal_a, "customer-a", T2), [])
        self.assertFalse(get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)["eligible"])
        self.assertEqual(list_eligible_accounts_as_of(self.db, self.principal_a, T2), [])
        self.assertEqual(
            [event["source"] for event in iter_replay_events(self.db, self.principal_a, T0, T2)],
            ["product_app"],
        )

        service_token = foundation.create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("product_app", "billing_app"),
            authorized_purposes=("retention_inference",),
        )
        service = foundation.authenticate_service_principal(self.db, service_token)
        with self.assertRaises(DataFoundationError) as service_write:
            ingest_event(self.db, service, usage_event("evt-service-cannot-ingest"), received_at=T2)
        self.assertEqual(service_write.exception.code, "unauthorized")
        events = get_events_as_of(self.db, service, "customer-a", T2)
        self.assertEqual({event["source"] for event in events}, {"product_app", "billing_app"})
        self.assertNotIn("support_app", {event["source"] for event in events})
        self.assertEqual(
            {event["source"] for event in iter_replay_events(self.db, service, T0, T2)},
            {"product_app", "billing_app"},
        )
        snapshot = get_account_snapshot_as_of(self.db, service, "customer-a", T2)
        self.assertTrue(snapshot["eligible"])
        self.assertEqual([row["subscription_id"] for row in snapshot["subscriptions"]], ["sub-billing"])
        self.assertEqual(
            [row["customer_id"] for row in list_eligible_accounts_as_of(self.db, service, T2)],
            ["customer-a"],
        )

    def test_account_snapshot_requires_an_authorized_source_identity_mapping(self):
        from retaniq import data_foundation as foundation

        billing_token = create_integration(
            self.db, "tenant-a", "billing_app", authorized_purposes=("retention_inference",),
            authorized_categories=("subscription",),
        )
        billing = authenticate_integration(self.db, billing_token)
        create_customer(self.db, "tenant-a", "billing-only-customer")
        map_customer_identity(
            self.db, "tenant-a", "billing_app", "billing-only-account", "billing-only-customer",
        )
        ingest_event(
            self.db, billing,
            {"source": "billing_app", "source_event_id": "evt-billing-only-subscription",
             "external_customer_id": "billing-only-account", "event_type": "subscription_created",
             "occurred_at": T0, "attributes": {"subscription_id": "sub-billing-only",
             "status": "active", "started_at": T0}, "schema_version": "1.0"},
            received_at=T0,
        )

        # Tenant membership alone must not authorize probing another source's account ID.
        with self.assertRaises(DataFoundationError) as denied:
            get_account_snapshot_as_of(self.db, self.principal_a, "billing-only-customer", T2)
        self.assertEqual(denied.exception.code, "not_found")
        self.assertNotIn(
            "billing-only-customer",
            {row["customer_id"] for row in list_eligible_accounts_as_of(self.db, self.principal_a, T2)},
        )

        service_token = foundation.create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("billing_app",),
            authorized_purposes=("retention_inference",),
        )
        service = foundation.authenticate_service_principal(self.db, service_token)
        self.assertTrue(
            get_account_snapshot_as_of(self.db, service, "billing-only-customer", T2)["eligible"],
        )

    def test_feature_and_explanation_storage_accepts_typed_values_and_rejects_free_text(self):
        safe_features = {
            "sessions_7d": 17,
            "usage_ratio_30d": 0.72,
            "is_new_account": False,
            "subscription_status": "active",
            "plan_id": "growth-v2",
            "plan_tier": "premium",
            "usage_trend_category": "declining",
        }
        snapshot_id = store_feature_snapshot(
            self.db, self.principal_a, "customer-a", T1, "features-safe-v1", T1,
            safe_features, "available",
        )
        self.assertTrue(snapshot_id)

        safe_prediction = {
            "prediction_id": "pred-safe-explanation", "prediction_run_id": "run-safe-explanation",
            "customer_id": "customer-a", "as_of": T1, "generated_at": T2, "status": "scored",
            "p_churn_7d": 0.1, "p_churn_14d": 0.2, "p_churn_30d": 0.3,
            "feature_version": "features-safe-v1", "model_version": "model-v1",
            "calibration_version": "cal-v1", "reliability_status": "limited_evidence",
            "data_freshness_status": "fresh", "feature_snapshot_id": snapshot_id,
            "reliability_reasons": ["short_personal_usage_history"],
            "explanations_by_horizon": {
                "30d": [
                    {"feature": "sessions_7d", "contribution": 0.24},
                    {"feature": "usage_ratio_30d", "contribution": -0.13},
                ],
            },
        }
        self.assertEqual(store_prediction(self.db, self.principal_a, safe_prediction), "pred-safe-explanation")

        unsafe_feature_values = (
            {"source_note": "The customer said they may leave next month."},
            {"api_key": "sk_live_123456789012345678"},
            {"card_number": "4111111111111111"},
            {"sessions_7d": 4111111111111111},
            {"support_comment": "call me at +60123456789"},
            {"plan_tier": "4111-1111-1111-1111"},
            {"feature": "6012.345.6789"},
            {"feature": "acct.4111-1111-1111-1111"},
            {"feature": "support-6012.345.6789"},
            {"plan_tier": "custom premium tier"},
            {"plan_tier": "platinum"},
        )
        for index, features in enumerate(unsafe_feature_values):
            with self.subTest(feature=features):
                with self.assertRaises(DataFoundationError):
                    store_feature_snapshot(
                        self.db, self.principal_a, "customer-a", T1, f"unsafe-feature-{index}", T1,
                        features, "available",
                    )

        unsafe_explanations = (
            {"30d": {"summary": "The customer said they may leave next month."}},
            {"30d": [{"feature": "Authorization: Bearer sk_live_123456789012345678", "contribution": 0.2}]},
            {"30d": {"private_note": "cancel this account"}},
            {"30d": {"card_number": "4111111111111111"}},
            {"30d": {"sessions_7d": 4111111111111111}},
            {"30d": [{"feature": "60123456789", "contribution": 0.15}]},
            {"30d": {"plan_tier": "4111-1111-1111-1111"}},
            {"30d": [{"feature": "6012.345.6789", "contribution": 0.15}]},
            {"30d": [{"feature": "acct.4111-1111-1111-1111", "contribution": 0.15}]},
            {"30d": [{"feature": "support-6012.345.6789", "contribution": 0.15}]},
            {"30d": [{"feature": "user@example.invalid", "contribution": 0.15}]},
        )
        for index, explanations in enumerate(unsafe_explanations):
            customer_id = f"customer-unsafe-explanation-{index}"
            create_customer(self.db, "tenant-a", customer_id)
            with self.subTest(explanation=explanations):
                with self.assertRaises(DataFoundationError):
                    store_prediction(
                        self.db, self.principal_a,
                        {**safe_prediction, "prediction_id": f"pred-unsafe-explanation-{index}",
                         "customer_id": customer_id, "as_of": T2, "feature_snapshot_id": None,
                         "explanations_by_horizon": explanations},
                    )

        for index, free_text in enumerate((
            "Short personal usage history", "Provider error: secret = abc123",
            "Contact at user@example.invalid",
        )):
            customer_id = f"customer-unsafe-reason-{index}"
            create_customer(self.db, "tenant-a", customer_id)
            with self.subTest(reason=free_text):
                with self.assertRaises(DataFoundationError):
                    store_prediction(
                        self.db, self.principal_a,
                        {**safe_prediction, "prediction_id": f"pred-unsafe-reason-{index}",
                         "customer_id": customer_id, "as_of": T2, "feature_snapshot_id": None,
                         "reliability_reasons": [free_text]},
                    )

    def test_subscription_id_cannot_move_between_accounts_in_same_tenant(self):
        self.add_subscription(
            "evt-owner-created", "subscription_created", T0,
            {"subscription_id": "sub-stable-owner", "status": "active", "started_at": T0,
             "plan_id": "owner-plan"},
        )
        create_customer(self.db, "tenant-a", "customer-other")
        billing_token = create_integration(
            self.db, "tenant-a", "billing_app", authorized_purposes=("retention_inference",),
            authorized_categories=("subscription",),
        )
        map_customer_identity(self.db, "tenant-a", "billing_app", "acct-other", "customer-other")
        billing_principal = authenticate_integration(self.db, billing_token)
        conflicting_event = {
            "source": "billing_app", "source_event_id": "evt-owner-collision",
            "external_customer_id": "acct-other", "event_type": "subscription_updated",
            "occurred_at": T1,
            "attributes": {"subscription_id": "sub-stable-owner", "plan_id": "other-plan"},
            "schema_version": "1.0",
        }
        with self.assertRaises(DataFoundationError) as caught:
            ingest_event(self.db, billing_principal, conflicting_event, received_at=T1)
        self.assertEqual(caught.exception.code, "contract_conflict")

        connection = sqlite3.connect(self.db)
        try:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM canonical_events WHERE source='billing_app' AND source_event_id='evt-owner-collision'",
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM subscription_events WHERE tenant_id='tenant-a' AND subscription_id='sub-stable-owner'",
            ).fetchone()[0], 1)
            projection = connection.execute(
                "SELECT customer_id, plan_id FROM subscriptions WHERE tenant_id='tenant-a' AND subscription_id='sub-stable-owner'",
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(projection, ("customer-a", "owner-plan"))
        snapshot = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(snapshot["subscriptions"][0]["customer_id"], "customer-a")
        self.assertEqual(snapshot["subscriptions"][0]["plan_id"], "owner-plan")

    def test_later_account_status_change_does_not_rewrite_historical_eligibility(self):
        self.add_subscription(
            "evt-temporal-status", "subscription_created", T0,
            {"subscription_id": "sub-temporal-status", "status": "active", "started_at": T0},
        )
        before_status_change = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T1)
        self.assertTrue(before_status_change["eligible"])
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "UPDATE customers SET account_status='inactive' WHERE tenant_id='tenant-a' AND customer_id='customer-a'",
            )
        finally:
            connection.close()
        prior_cutoff = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T1)
        later_cutoff = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T3)
        self.assertEqual(prior_cutoff["status"], "eligible")
        self.assertEqual(later_cutoff["status"], "eligible")
        self.assertEqual(
            [account["customer_id"] for account in list_eligible_accounts_as_of(self.db, self.principal_a, T1)],
            ["customer-a"],
        )

    def test_tenant_integration_health_requires_operator_role_purpose_and_tenant_scope(self):
        from dataclasses import replace
        from retaniq import data_foundation as foundation

        billing_token = create_integration(
            self.db, "tenant-a", "billing_app", authorized_purposes=("retention_inference",),
        )
        narrow_token = create_integration(
            self.db, "tenant-a", "usage_narrow", authorized_purposes=("retention_inference",),
        )
        narrow_principal = authenticate_integration(self.db, narrow_token)
        with self.assertRaises(DataFoundationError):
            foundation.get_tenant_integration_health(self.db, narrow_principal)

        analyst_token = foundation.create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("product_app", "billing_app"),
            authorized_purposes=("integration_health",),
        )
        analyst = foundation.authenticate_service_principal(self.db, analyst_token)
        with self.assertRaises(DataFoundationError):
            foundation.get_tenant_integration_health(self.db, analyst)

        narrow_operator_token = foundation.create_service_principal(
            self.db, "tenant-a", role="operator", authorized_sources=("product_app", "billing_app"),
            authorized_purposes=("retention_inference",),
        )
        narrow_operator = foundation.authenticate_service_principal(self.db, narrow_operator_token)
        with self.assertRaises(DataFoundationError) as narrow_health:
            foundation.get_tenant_integration_health(self.db, narrow_operator)
        self.assertEqual(narrow_health.exception.code, "purpose_not_authorized")

        operator_token = foundation.create_service_principal(
            self.db, "tenant-a", role="operator", authorized_sources=("product_app", "billing_app"),
            authorized_purposes=("integration_health",),
        )
        operator = foundation.authenticate_service_principal(self.db, operator_token)
        health = foundation.get_tenant_integration_health(self.db, operator)
        self.assertEqual({item["source"] for item in health}, {"product_app", "billing_app"})
        self.assertTrue(all(item["tenant_id"] == "tenant-a" for item in health))
        self.assertNotIn(operator_token, json.dumps(health))
        self.assertNotIn("token_digest", json.dumps(health))
        with self.assertRaises(DataFoundationError):
            foundation.get_tenant_integration_health(self.db, replace(operator, tenant_id="tenant-b"))

        self.assertTrue(
            get_wsgi(create_app(self.db), "/v1/admin/integrations", self.token_a)["status"].startswith("401"),
        )
        self.assertTrue(
            get_wsgi(create_app(self.db), "/v1/admin/integrations", operator_token)["status"].startswith("200"),
        )

    def test_tenant_scopes_event_reads_and_identity_writes(self):
        ingest_event(self.db, self.principal_b, usage_event(), received_at=T1)
        visible = get_events_as_of(self.db, self.principal_a, "customer-b", T2)
        self.assertEqual(visible, [])
        with self.assertRaises(DataFoundationError):
            map_customer_identity(self.db, "tenant-a", "product_app", "acct-other", "customer-b")

    def test_duplicate_source_event_is_idempotent_and_conflicts_are_rejected(self):
        first = ingest_event(self.db, self.principal_a, usage_event(), received_at=T1)
        second = ingest_event(self.db, self.principal_a, usage_event(), received_at=T2)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(len(get_events_as_of(self.db, self.principal_a, "customer-a", T2)), 1)
        with self.assertRaises(DataFoundationError) as caught:
            ingest_event(
                self.db,
                self.principal_a,
                usage_event(attributes={"feature": "exports"}),
                received_at=T2,
            )
        self.assertEqual(caught.exception.code, "idempotency_conflict")

    def test_unapproved_fields_are_rejected_and_error_does_not_echo_payload(self):
        marker = "private-value-must-not-leak"
        with self.assertRaises(DataFoundationError) as caught:
            ingest_event(
                self.db,
                self.principal_a,
                usage_event(attributes={"email": marker}),
                received_at=T1,
            )
        self.assertEqual(caught.exception.code, "invalid_event")
        self.assertNotIn(marker, str(caught.exception))
        self.assertNotIn(marker.encode(), Path(self.db).read_bytes())

    def test_http_error_and_log_do_not_echo_restricted_value(self):
        marker = "private-http-marker"
        with self.assertLogs("retaniq.api", level="WARNING") as captured:
            response = post_wsgi(create_app(self.db), "/v1/ingest/events",
                                 usage_event(attributes={"private_note": marker}), self.token_a)
        self.assertTrue(response["status"].startswith("400"))
        self.assertNotIn(marker, json.dumps(response["body"]))
        self.assertNotIn(marker, "\n".join(captured.output))

    def test_malformed_event_is_rejected_without_raw_body_echo(self):
        marker = "do-not-echo-this-event"
        with self.assertRaises(DataFoundationError) as caught:
            ingest_event(
                self.db,
                self.principal_a,
                usage_event(occurred_at=marker),
                received_at=T1,
            )
        self.assertEqual(caught.exception.code, "invalid_event")
        self.assertNotIn(marker, str(caught.exception))

    def test_event_with_late_source_availability_is_excluded_at_cutoff(self):
        ingest_event(
            self.db,
            self.principal_a,
            usage_event(),
            received_at=T3,
            trusted_source_available_at=T3,
        )
        self.assertEqual(get_events_as_of(self.db, self.principal_a, "customer-a", T2), [])
        self.assertEqual(len(get_events_as_of(self.db, self.principal_a, "customer-a", T3)), 1)

    def test_live_event_received_after_cutoff_cannot_retroactively_appear(self):
        ingest_event(self.db, self.principal_a, usage_event(), received_at=T3)
        self.assertEqual(get_events_as_of(self.db, self.principal_a, "customer-a", T2), [])
        self.assertEqual(len(get_events_as_of(self.db, self.principal_a, "customer-a", T3)), 1)

    def add_subscription(self, source_event_id, event_type, occurred_at, attributes):
        envelope = {
            "source": "product_app",
            "source_event_id": source_event_id,
            "external_customer_id": "acct-a",
            "event_type": event_type,
            "occurred_at": occurred_at,
            "attributes": attributes,
            "schema_version": "1.0",
        }
        return ingest_event(self.db, self.principal_a, envelope, received_at=occurred_at)

    def test_subscription_state_reconstructs_by_cutoff_and_pending_cancel_is_known(self):
        self.add_subscription(
            "evt-sub-create",
            "subscription_created",
            T0,
            {
                "subscription_id": "sub-1",
                "status": "active",
                "started_at": T0,
                "billing_interval": "month",
                "billing_interval_count": 1,
                "amount_minor": 10000,
                "discount_minor": 1000,
                "currency": "MYR",
            },
        )
        before_request = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T1)
        self.assertEqual(before_request["status"], "eligible")
        self.assertEqual(before_request["valuation"]["mrr_minor"], 9000)
        self.add_subscription("evt-cancel-request", "cancellation_requested", T2, {"subscription_id": "sub-1"})
        before_known = get_subscriptions_as_of(self.db, self.principal_a, "customer-a", T1)
        at_request = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(before_known[0]["status"], "active")
        self.assertEqual(at_request["status"], "known_cancellation")
        self.assertEqual(at_request["subscriptions"][0]["ended_at"], None)

    def test_payment_failure_is_billing_risk_not_subscription_termination(self):
        self.add_subscription(
            "evt-sub-create",
            "subscription_created",
            T0,
            {"subscription_id": "sub-1", "status": "active", "started_at": T0},
        )
        payment = {
            "source": "product_app",
            "source_event_id": "evt-payment-fail",
            "external_customer_id": "acct-a",
            "event_type": "payment_failed",
            "occurred_at": T1,
            "attributes": {"subscription_id": "sub-1", "amount_minor": 10000, "currency": "MYR"},
            "schema_version": "1.0",
        }
        ingest_event(self.db, self.principal_a, payment, received_at=T1)
        snapshot = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(snapshot["status"], "eligible")
        self.assertEqual(snapshot["subscriptions"][0]["status"], "active")
        self.assertEqual(snapshot["billing_events"][0]["payment_status"], "failed")

    def test_as_of_mrr_normalizes_intervals_discounts_and_missing_prices(self):
        cases = [
            ("month", 1, 12000, 2000, 10000),
            ("quarter", 1, 30000, 0, 10000),
            ("year", 2, 240000, 0, 10000),
            ("week", 52, 120000, 0, 10000),
        ]
        for index, (interval, count, amount, discount, expected) in enumerate(cases):
            with self.subTest(interval=interval, count=count):
                sub_id = f"sub-{index}"
                self.add_subscription(
                    f"evt-{sub_id}", "subscription_created", T0,
                    {"subscription_id": sub_id, "status": "active", "started_at": T0,
                     "billing_interval": interval, "billing_interval_count": count,
                     "amount_minor": amount, "discount_minor": discount, "currency": "MYR"},
                )
                snapshot = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
                item = next(row for row in snapshot["subscriptions"] if row["subscription_id"] == sub_id)
                self.assertEqual(item["mrr_minor"], expected)
        self.add_subscription(
            "evt-missing-price", "subscription_created", T0,
            {"subscription_id": "sub-missing", "status": "active", "started_at": T0, "currency": "MYR"},
        )
        states = get_subscriptions_as_of(self.db, self.principal_a, "customer-a", T2)
        missing = next(row for row in states if row["subscription_id"] == "sub-missing")
        self.assertIsNone(missing["mrr_minor"])

    def test_account_mrr_does_not_sum_mixed_currencies_or_missing_values(self):
        for sub_id, currency in (("sub-myr", "MYR"), ("sub-usd", "USD")):
            self.add_subscription(
                f"evt-{sub_id}", "subscription_created", T0,
                {"subscription_id": sub_id, "status": "active", "started_at": T0,
                 "billing_interval": "month", "amount_minor": 10000, "currency": currency},
            )
        snapshot = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(snapshot["valuation"]["status"], "mixed_currency")
        self.assertIsNone(snapshot["valuation"]["mrr_minor"])

    def test_multiple_subscriptions_sum_only_when_currency_matches(self):
        for sub_id, amount in (("sub-one", 10000), ("sub-two", 2500)):
            self.add_subscription(
                f"evt-{sub_id}", "subscription_created", T0,
                {"subscription_id": sub_id, "status": "active", "started_at": T0,
                 "billing_interval": "month", "billing_interval_count": 1,
                 "amount_minor": amount, "currency": "MYR"},
            )
        snapshot = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(snapshot["valuation"]["mrr_minor"], 12500)
        self.assertEqual(snapshot["valuation"]["currency"], "MYR")

    def test_zero_decimal_currency_keeps_source_minor_units(self):
        self.add_subscription(
            "evt-jpy", "subscription_created", T0,
            {"subscription_id": "sub-jpy", "status": "active", "started_at": T0,
             "billing_interval": "month", "billing_interval_count": 1,
             "amount_minor": 600, "currency": "JPY"},
        )
        snapshot = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(snapshot["valuation"]["currency"], "JPY")
        self.assertEqual(snapshot["valuation"]["mrr_minor"], 600)

    def test_non_iso_currency_code_is_rejected_before_valuation(self):
        with self.assertRaises(DataFoundationError) as caught:
            self.add_subscription(
                "evt-unsupported-currency", "subscription_created", T0,
                {"subscription_id": "sub-bad-currency", "status": "active", "started_at": T0,
                 "billing_interval": "month", "billing_interval_count": 1,
                 "amount_minor": 1000, "currency": "ZZZ"},
            )
        self.assertEqual(caught.exception.code, "invalid_event")

    def test_price_change_is_reconstructed_at_historical_cutoff(self):
        self.add_subscription(
            "evt-sub-create", "subscription_created", T0,
            {"subscription_id": "sub-1", "status": "active", "started_at": T0,
             "billing_interval": "month", "billing_interval_count": 1,
             "amount_minor": 10000, "currency": "MYR"},
        )
        self.add_subscription(
            "evt-price-change", "subscription_updated", T2,
            {"subscription_id": "sub-1", "amount_minor": 20000, "currency": "MYR"},
        )
        at_t1 = get_subscriptions_as_of(self.db, self.principal_a, "customer-a", T1)
        at_t2 = get_subscriptions_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(at_t1[0]["mrr_minor"], 10000)
        self.assertEqual(at_t2[0]["mrr_minor"], 20000)

    def test_daily_eligibility_enumeration_includes_silent_accounts(self):
        self.add_subscription(
            "evt-silent-sub", "subscription_created", T0,
            {"subscription_id": "sub-silent", "status": "active", "started_at": T0,
             "billing_interval": "month", "billing_interval_count": 1,
             "amount_minor": 1000, "currency": "MYR"},
        )
        eligible = list_eligible_accounts_as_of(self.db, self.principal_a, T2)
        self.assertEqual([account["customer_id"] for account in eligible], ["customer-a"])
        self.assertEqual(eligible[0]["usage_events"], [])

    def test_partial_subscription_cancellation_keeps_account_eligible(self):
        for sub_id in ("sub-one", "sub-two"):
            self.add_subscription(
                f"evt-{sub_id}", "subscription_created", T0,
                {"subscription_id": sub_id, "status": "active", "started_at": T0,
                 "billing_interval": "month", "billing_interval_count": 1,
                 "amount_minor": 1000, "currency": "MYR"},
            )
        self.add_subscription("evt-cancel-one", "cancellation_requested", T1, {"subscription_id": "sub-one"})
        snapshot = get_account_snapshot_as_of(self.db, self.principal_a, "customer-a", T2)
        self.assertEqual(snapshot["status"], "eligible")
        self.assertEqual(snapshot["valuation"]["mrr_minor"], 2000)

    def test_feature_label_prediction_storage_contracts(self):
        feature_id = store_feature_snapshot(
            self.db, self.principal_a, "customer-a", T1, "features-v1", T1,
            {"sessions_7d": 3, "mrr_minor": 2500, "currency": "MYR"}, "available",
        )
        self.assertTrue(feature_id)
        with self.assertRaises(DataFoundationError):
            store_feature_snapshot(
                self.db, self.principal_a, "customer-a", T1, "features-v1", T1,
                {"email": "private@example.invalid"}, "available",
            )
        with self.assertRaises(DataFoundationError):
            store_feature_snapshot(
                self.db, self.principal_a, "customer-a", T1, "features-v2", T1,
                {"account_contact_email": "private@example.invalid"}, "available",
            )
        store_churn_label(
            self.db, self.principal_a, "customer-a", T1, 7, "unknown", T1,
            "churn-label-v1",
        )
        with self.assertRaises(DataFoundationError) as invalid_label:
            store_churn_label(
                self.db, self.principal_a, "customer-a", T0, 7, True, T3,
                "churn-label-bool-v1",
            )
        self.assertEqual(invalid_label.exception.code, "invalid_contract")
        with self.assertRaises(DataFoundationError):
            store_churn_label(
                self.db, self.principal_a, "customer-a", T1, 30, 0, T1,
                "churn-label-v1",
            )
        with self.assertRaises(DataFoundationError) as insufficient_positive_coverage:
            store_churn_label(
                self.db, self.principal_a, "customer-a", T0, 7, 1, T0,
                "churn-label-positive-v1", outcome_at=T1,
            )
        self.assertEqual(insufficient_positive_coverage.exception.code, "invalid_contract")
        prediction_id = store_prediction(
            self.db, self.principal_a,
            {"prediction_id": "pred-1", "prediction_run_id": "run-1", "customer_id": "customer-a",
             "as_of": T1, "generated_at": T2, "status": "scored", "p_churn_7d": 0.1,
             "p_churn_14d": 0.2, "p_churn_30d": 0.3, "feature_version": "features-v1",
             "model_version": "model-v1", "calibration_version": "cal-v1",
              "reliability_status": "limited_evidence", "data_freshness_status": "unknown",
              "feature_snapshot_id": feature_id,
              "explanations_by_horizon": {"mrr_minor": 2500}},
        )
        self.assertEqual(prediction_id, "pred-1")
        with self.assertRaises(DataFoundationError) as future_input:
            store_prediction(
                self.db, self.principal_a,
                {"prediction_id": "pred-future-input", "prediction_run_id": "run-future-input",
                 "customer_id": "customer-a", "as_of": T0, "generated_at": T2, "status": "abstained",
                 "p_churn_7d": None, "p_churn_14d": None, "p_churn_30d": None,
                 "feature_version": "features-v1", "model_version": "model-v1",
                 "calibration_version": "cal-v1", "reliability_status": "insufficient_evidence",
                 "data_freshness_status": "fresh", "input_data_as_of": T2},
            )
        self.assertEqual(future_input.exception.code, "invalid_contract")
        for index, unsafe_reason in enumerate((
            "Source error for private@example.invalid", "Adapter error; phone number: +60123456789",
            "Provider rejected API key: sk_live_123456789",
            "Provider response Authorization: Bearer sk_live_123456789",
        )):
            with self.subTest(unsafe_reason=unsafe_reason):
                with self.assertRaises(DataFoundationError) as caught:
                    store_prediction(
                        self.db, self.principal_a,
                        {"prediction_id": f"pred-private-reason-{index}",
                         "prediction_run_id": f"run-private-reason-{index}",
                         "customer_id": "customer-a", "as_of": T0, "generated_at": T2,
                         "status": "abstained", "p_churn_7d": None, "p_churn_14d": None,
                         "p_churn_30d": None, "feature_version": "features-v1",
                         "model_version": "model-v1", "calibration_version": "cal-v1",
                         "reliability_status": "insufficient_evidence", "data_freshness_status": "unknown",
                         "reliability_reasons": [unsafe_reason]},
                    )
                self.assertEqual(caught.exception.code, "invalid_contract")
        with self.assertRaises(DataFoundationError):
            store_prediction(
                self.db, self.principal_a,
                {"prediction_id": "pred-2", "prediction_run_id": "run-2", "customer_id": "customer-a",
                 "as_of": T1, "generated_at": T2, "status": "scored", "p_churn_7d": 0.2,
                 "p_churn_14d": 0.1, "p_churn_30d": 0.3, "feature_version": "features-v1",
                 "model_version": "model-v1", "calibration_version": "cal-v1",
                 "reliability_status": "limited_evidence", "data_freshness_status": "unknown"},
            )

    def test_prediction_rejects_feature_snapshot_for_wrong_account_cutoff_or_version(self):
        for customer_id in ("customer-other", "customer-cutoff", "customer-version"):
            create_customer(self.db, "tenant-a", customer_id)
            map_customer_identity(
                self.db, "tenant-a", "product_app", f"acct-{customer_id}", customer_id,
            )
        other_account_snapshot = store_feature_snapshot(
            self.db, self.principal_a, "customer-other", T1, "features-v1", T1,
            {"sessions_7d": 1}, "available",
        )
        other_cutoff_snapshot = store_feature_snapshot(
            self.db, self.principal_a, "customer-cutoff", T2, "features-v1", T2,
            {"sessions_7d": 2}, "available",
        )
        other_version_snapshot = store_feature_snapshot(
            self.db, self.principal_a, "customer-version", T1, "features-v2", T1,
            {"sessions_7d": 3}, "available",
        )
        base = {
            "prediction_run_id": "run-mismatch",
            "as_of": T1, "generated_at": T2, "status": "abstained", "p_churn_7d": None,
            "p_churn_14d": None, "p_churn_30d": None, "feature_version": "features-v1",
            "model_version": "model-v1", "calibration_version": "cal-v1",
            "reliability_status": "insufficient_evidence", "data_freshness_status": "unknown",
        }
        mismatches = (
            ("customer-a", other_account_snapshot),
            ("customer-cutoff", other_cutoff_snapshot),
            ("customer-version", other_version_snapshot),
        )
        for index, (customer_id, feature_id) in enumerate(mismatches):
            with self.subTest(feature_snapshot_id=feature_id):
                with self.assertRaises(DataFoundationError) as caught:
                    store_prediction(
                        self.db, self.principal_a,
                        {**base, "customer_id": customer_id, "prediction_id": f"pred-mismatch-{index}",
                         "feature_snapshot_id": feature_id},
                    )
                self.assertEqual(caught.exception.code, "invalid_contract")

    def test_csv_import_counts_invalid_and_duplicate_rows_and_replay_preserves_times(self):
        csv_path = Path(self.temp.name) / "history.csv"
        csv_path.write_text(
            "event_id,account,event,happened,available,attributes_json\n"
            f"evt-h1,acct-a,session_started,{T0},{T1},{{\"feature\":\"reports\"}}\n"
            f"evt-h1,acct-a,session_started,{T0},{T1},{{\"feature\":\"reports\"}}\n"
            "evt-bad,acct-a,session_started,not-a-time,,{}\n",
            encoding="utf-8",
        )
        summary = import_csv(
            self.db,
            self.principal_a,
            str(csv_path),
            {"mapping_version": "csv-v1", "columns": {
                "source_event_id": "event_id", "external_customer_id": "account",
                "event_type": "event", "occurred_at": "happened",
                "source_available_at": "available", "attributes": "attributes_json",
            }},
            received_at=T3,
            trust_source_availability=True,
        )
        self.assertEqual(summary["accepted"], 1)
        self.assertEqual(summary["duplicates"], 1)
        self.assertEqual(summary["rejected"], 1)
        replayed = list(iter_replay_events(self.db, self.principal_a, T0, T2))
        self.assertEqual(len(replayed), 1)
        self.assertEqual(replayed[0]["occurred_at"], T0)
        self.assertEqual(replayed[0]["source_available_at"], T1)
        self.assertEqual(replayed[0]["available_at"], T1)

    def test_import_cannot_trust_availability_without_explicit_operator_flag(self):
        mapping = {
            "mapping_version": "csv-v1",
            "columns": {
                "source_event_id": "event_id", "external_customer_id": "account",
                "event_type": "event", "occurred_at": "happened",
                "source_available_at": "available", "attributes": "attributes_json",
            },
        }
        with self.assertRaises(DataFoundationError) as caught:
            import_csv(self.db, self.principal_a, "unused.csv", mapping)
        self.assertEqual(caught.exception.code, "invalid_import_mapping")

    def test_invalid_csv_header_does_not_change_configured_mapping_version(self):
        csv_path = Path(self.temp.name) / "wrong-header.csv"
        csv_path.write_text("wrong,columns\n1,2\n", encoding="utf-8")
        mapping = {
            "mapping_version": "csv-v2",
            "columns": {
                "source_event_id": "event_id", "external_customer_id": "account",
                "event_type": "event", "occurred_at": "happened", "attributes": "attributes_json",
            },
        }
        with self.assertRaises(DataFoundationError) as caught:
            import_csv(self.db, self.principal_a, str(csv_path), mapping)
        self.assertEqual(caught.exception.code, "invalid_csv")
        self.assertEqual(get_integration_health(self.db, self.principal_a)[0]["mapping_version"], "canonical-v1")

    def test_integration_health_is_tenant_scoped_and_never_contains_secret(self):
        try:
            ingest_event(
                self.db, self.principal_a,
                usage_event(attributes={"email": "private@example.invalid"}), received_at=T1,
            )
        except DataFoundationError:
            pass
        health = get_integration_health(self.db, self.principal_a)
        serialized = json.dumps(health)
        self.assertEqual(len(health), 1)
        self.assertEqual(health[0]["tenant_id"], "tenant-a")
        self.assertNotIn(self.token_a, serialized)
        self.assertNotIn("token_hash", serialized)
        self.assertEqual(health[0]["authorized_purposes"], ["billing_valuation", "retention_inference"])
        self.assertEqual(health[0]["last_failure_code"], "invalid_event")


if __name__ == "__main__":
    unittest.main()
