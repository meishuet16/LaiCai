"""Live dual-backend ingestion checks; PostgreSQL runs only on guarded test DBs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from urllib.parse import unquote, urlsplit
from uuid import uuid4
from unittest.mock import patch

from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_integration,
    authenticate_service_principal,
    create_customer,
    create_integration,
    create_service_principal,
    create_tenant,
    get_integration_health,
    get_synthetic_import_checkpoint,
    get_tenant_integration_health,
    ingest_event,
    ingest_events_batch,
    initialize_database,
    map_customer_identity,
)
from retaniq.database import connect_database
from retaniq.database_config import DatabaseConfig
from retaniq.importer import import_csv


T0 = "2026-10-01T00:00:00.000000Z"
T1 = "2026-10-05T00:00:00.000000Z"
T2 = "2026-10-10T00:00:00.000000Z"
T3 = "2026-10-12T00:00:00.000000Z"
DATASET_ID = "pg-ingestion-parity-test-v1"


def _test_config() -> DatabaseConfig | None:
    dsn = os.environ.get("RETAINIQ_POSTGRES_TEST_DSN")
    if not dsn or os.environ.get("RETAINIQ_POSTGRES_TEST_DISPOSABLE") != "1":
        return None
    try:
        config = DatabaseConfig.from_value(dsn, allow_insecure_local_postgresql=True)
        parsed = urlsplit(config.postgresql_dsn)
        database = unquote(parsed.path.lstrip("/"))
    except (ValueError, TypeError):
        return None
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not database.startswith("retaniq_test_"):
        return None
    return config


_TEST_CONFIG = _test_config()


@unittest.skipUnless(
    _TEST_CONFIG,
    "requires an explicitly disposable loopback PostgreSQL database named retaniq_test_*",
)
class PostgreSQLIngestionParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = _TEST_CONFIG
        from postgresql_security_support import bootstrap_test_roles
        bootstrap_test_roles(cls.database)
        initialize_database(cls.database, migrate_postgresql=True)
        with connect_database(cls.database) as connection:
            timestamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
            connection.execute(
                "INSERT INTO dataset_identity(singleton_id, dataset_id, dataset_version, dataset_type, "
                "target_policy_version, generator_version, manifest_sha256, bound_at) "
                "VALUES (1, ?, '1.0', 'synthetic_saas', 'test-policy-v1', 'test-generator-v1', ?, ?) "
                "ON CONFLICT(singleton_id) DO NOTHING",
                (DATASET_ID, "a" * 64, timestamp),
            )
            identity = connection.execute(
                "SELECT dataset_id FROM dataset_identity WHERE singleton_id=1",
            ).fetchone()
            if identity["dataset_id"] != DATASET_ID:
                raise RuntimeError("disposable test database already contains another dataset identity")

    def setUp(self):
        suffix = uuid4().hex[:12]
        self.tenant = f"tenant-{suffix}"
        self.other_tenant = f"other-{suffix}"
        self.source = f"source-{suffix}"
        self.customer_a = f"customer-a-{suffix}"
        self.customer_b = f"customer-b-{suffix}"
        self.external_a = f"external-a-{suffix}"
        self.external_b = f"external-b-{suffix}"
        create_tenant(self.database, self.tenant)
        create_tenant(self.database, self.other_tenant)
        create_customer(self.database, self.tenant, self.customer_a)
        create_customer(self.database, self.tenant, self.customer_b)
        create_customer(self.database, self.other_tenant, f"customer-{suffix}")
        self.token = create_integration(
            self.database, self.tenant, self.source,
            authorized_categories=("usage", "billing", "subscription"),
        )
        map_customer_identity(self.database, self.tenant, self.source, self.external_a, self.customer_a)
        map_customer_identity(self.database, self.tenant, self.source, self.external_b, self.customer_b)
        self.principal = authenticate_integration(self.database, self.token)

    def _event(self, event_id: str, *, event_type="session_started", attributes=None, external=None,
               occurred_at=T0):
        return {
            "source": self.source,
            "source_event_id": event_id,
            "external_customer_id": external or self.external_a,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "attributes": attributes or {"feature": "reports"},
            "schema_version": "1.0",
        }

    def _query(self, statement, parameters=()):
        with connect_database(self.database) as connection:
            return connection.execute(statement, parameters).fetchall()

    def test_integration_and_service_authentication_grants_and_token_rotation(self):
        with self.assertRaises(DataFoundationError) as raised:
            authenticate_integration(self.database, "not-a-valid-bearer")
        self.assertEqual(raised.exception.code, "unauthorized")
        with connect_database(self.database) as connection:
            row = connection.execute(
                "SELECT token_digest FROM integrations WHERE integration_id=?",
                (self.principal.integration_id,),
            ).fetchone()
        self.assertEqual(len(row["token_digest"]), 64)
        self.assertNotEqual(row["token_digest"], self.token)

        service_token = create_service_principal(
            self.database, self.tenant, role="operator", authorized_sources=(self.source,),
            authorized_purposes=("integration_health",),
        )
        service = authenticate_service_principal(self.database, service_token)
        self.assertEqual(service.authorized_sources, (self.source,))
        self.assertEqual(get_tenant_integration_health(self.database, service)[0]["source"], self.source)
        forged = replace(self.principal, tenant_id=self.other_tenant)
        with self.assertRaises(DataFoundationError) as tenant_denial:
            ingest_event(self.database, forged, self._event("forged-principal"), received_at=T1)
        self.assertEqual(tenant_denial.exception.code, "unauthorized")
        forged_service = replace(service, tenant_id=self.other_tenant)
        with self.assertRaises(DataFoundationError) as service_denial:
            get_tenant_integration_health(self.database, forged_service)
        self.assertEqual(service_denial.exception.code, "unauthorized")
        with connect_database(self.database) as connection:
            connection.execute(
                "UPDATE integrations SET token_digest=? WHERE integration_id=?",
                (hashlib.sha256(uuid4().hex.encode("ascii")).hexdigest(), self.principal.integration_id),
            )
        with self.assertRaises(DataFoundationError) as revoked:
            authenticate_integration(self.database, self.token)
        self.assertEqual(revoked.exception.code, "unauthorized")

    def test_identity_mapping_is_tenant_scoped_idempotent_and_race_safe(self):
        map_customer_identity(self.database, self.tenant, self.source, self.external_a, self.customer_a)
        with self.assertRaises(DataFoundationError) as conflict:
            map_customer_identity(self.database, self.tenant, self.source, self.external_a, self.customer_b)
        self.assertEqual(conflict.exception.code, "contract_conflict")
        with self.assertRaises(DataFoundationError) as missing:
            map_customer_identity(self.database, self.tenant, self.source, "external-x", "foreign-customer")
        self.assertEqual(missing.exception.code, "not_found")
        with self.assertRaises(DataFoundationError) as cross_tenant:
            map_customer_identity(
                self.database, self.tenant, self.source, "external-cross-tenant",
                f"customer-{self.other_tenant.removeprefix('other-')}",
            )
        self.assertEqual(cross_tenant.exception.code, "not_found")

        race_external = f"race-{uuid4().hex[:12]}"
        barrier = Barrier(8)

        def same_mapping(_):
            barrier.wait()
            map_customer_identity(self.database, self.tenant, self.source, race_external, self.customer_a)
            return "ok"

        with ThreadPoolExecutor(max_workers=8) as executor:
            self.assertEqual(list(executor.map(same_mapping, range(8))), ["ok"] * 8)
        self.assertEqual(self._query(
            "SELECT customer_id FROM customer_identities WHERE tenant_id=? AND source=? AND external_customer_id=?",
            (self.tenant, self.source, race_external),
        )[0]["customer_id"], self.customer_a)

        conflicting_external = f"conflict-{uuid4().hex[:12]}"
        conflict_barrier = Barrier(2)

        def conflicting_mapping(args):
            customer_id = args
            conflict_barrier.wait()
            try:
                map_customer_identity(
                    self.database, self.tenant, self.source, conflicting_external, customer_id,
                )
                return "accepted"
            except DataFoundationError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(conflicting_mapping, (self.customer_a, self.customer_b)))
        self.assertCountEqual(outcomes, ["accepted", "contract_conflict"])

    def test_authorization_and_restricted_attributes_reject_without_partial_event(self):
        usage_token = create_integration(self.database, self.tenant, f"usage-only-{uuid4().hex[:8]}")
        usage_principal = authenticate_integration(self.database, usage_token)
        with self.assertRaises(DataFoundationError) as category:
            ingest_event(
                self.database, usage_principal,
                {**self._event("unauthorized-category", event_type="subscription_created",
                               attributes={"subscription_id": "sub-a", "status": "active", "started_at": T0}),
                 "source": usage_principal.source},
                received_at=T1,
            )
        self.assertEqual(category.exception.code, "event_category_not_authorized")

        wrong_source = self._event("wrong-source")
        wrong_source["source"] = f"ungranted-{uuid4().hex[:8]}"
        with self.assertRaises(DataFoundationError) as source:
            ingest_event(self.database, self.principal, wrong_source, received_at=T1)
        self.assertEqual(source.exception.code, "source_not_authorized")

        wrong_tenant = {**self._event("wrong-tenant"), "tenant_id": self.other_tenant}
        with self.assertRaises(DataFoundationError) as tenant:
            ingest_event(self.database, self.principal, wrong_tenant, received_at=T1)
        self.assertEqual(tenant.exception.code, "invalid_event")

        narrow_source = f"billing-{uuid4().hex[:8]}"
        narrow_token = create_integration(
            self.database, self.tenant, narrow_source, authorized_purposes=("retention_inference",),
            authorized_categories=("billing",),
        )
        map_customer_identity(self.database, self.tenant, narrow_source, self.external_a, self.customer_a)
        narrow = authenticate_integration(self.database, narrow_token)
        with self.assertRaises(DataFoundationError) as purpose:
            ingest_event(
                self.database, narrow,
                self._event("unauthorized-purpose", event_type="payment_failed",
                            attributes={"amount_minor": 500, "currency": "USD"}),
                received_at=T1,
            )
        self.assertEqual(purpose.exception.code, "source_not_authorized")

        rejected = self._event("restricted-field", attributes={"email": "secret@example.invalid"})
        with self.assertRaises(DataFoundationError) as restricted:
            ingest_event(self.database, self.principal, rejected, received_at=T1)
        self.assertEqual(restricted.exception.code, "invalid_event")
        self.assertNotIn("secret@example.invalid", str(restricted.exception))
        with self.assertRaises(DataFoundationError) as unmapped:
            ingest_event(
                self.database, self.principal,
                self._event("unmapped-event", external="unmapped-external"), received_at=T1,
            )
        self.assertEqual(unmapped.exception.code, "identity_not_mapped")
        self.assertEqual(self._query(
            "SELECT COUNT(*) AS n FROM canonical_events WHERE tenant_id=? "
            "AND source_event_id IN (?, ?, ?, ?, ?, ?)",
            (self.tenant, "unauthorized-category", "unauthorized-purpose", "restricted-field",
             "wrong-source", "wrong-tenant", "unmapped-event"),
        )[0]["n"], 0)
        self.assertEqual(get_integration_health(self.database, self.principal)[0]["last_failure_code"],
                         "identity_not_mapped")

    def test_usage_persistence_availability_timestamps_and_event_idempotency(self):
        payload = self._event("usage-event")
        first = ingest_event(
            self.database, self.principal, payload, received_at=T1, trusted_source_available_at=T2,
        )
        replay = ingest_event(
            self.database, self.principal, payload, received_at=T3, trusted_source_available_at=T2,
        )
        self.assertFalse(first["duplicate"])
        self.assertTrue(replay["duplicate"])
        self.assertEqual(first["event_id"], replay["event_id"])
        event = self._query(
            "SELECT occurred_at, received_at, source_available_at, source_event_id, category, event_type, "
            "schema_version, mapping_version, normalized_payload_sha256 FROM canonical_events WHERE event_id=?",
            (first["event_id"],),
        )[0]
        self.assertEqual((event["source_event_id"], event["category"], event["event_type"],
                          event["schema_version"], event["mapping_version"]),
                         ("usage-event", "usage", "session_started", "1.0", "canonical-v1"))
        self.assertEqual(len(event["normalized_payload_sha256"]), 64)
        self.assertEqual(event["occurred_at"], datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(event["received_at"], datetime(2026, 10, 5, tzinfo=timezone.utc))
        self.assertEqual(event["source_available_at"], datetime(2026, 10, 10, tzinfo=timezone.utc))
        subtype = self._query(
            "SELECT feature FROM usage_events WHERE tenant_id=? AND event_id=?",
            (self.tenant, first["event_id"]),
        )
        self.assertEqual(subtype[0]["feature"], "reports")
        health = get_integration_health(self.database, self.principal)[0]
        self.assertEqual(health["last_successful_ingestion_at"], "2026-10-12T00:00:00.000000Z")
        self.assertIsNone(health["last_failure_code"])

        with self.assertRaises(DataFoundationError) as conflict:
            ingest_event(
                self.database, self.principal,
                self._event("usage-event", attributes={"feature": "exports"}), received_at=T3,
            )
        self.assertEqual(conflict.exception.code, "idempotency_conflict")

    def test_billing_failure_and_subscription_lifecycle_keep_distinct_semantics(self):
        subscription_id = f"sub-{uuid4().hex[:10]}"
        created = self._event(
            "subscription-created", event_type="subscription_created",
            attributes={"subscription_id": subscription_id, "status": "active", "started_at": T0},
        )
        ingest_event(self.database, self.principal, created, received_at=T0)
        payment = self._event(
            "payment-failed", event_type="payment_failed",
            attributes={"subscription_id": subscription_id, "amount_minor": 1000, "currency": "USD"},
            occurred_at=T1,
        )
        ingest_event(self.database, self.principal, payment, received_at=T1)
        status = self._query(
            "SELECT status FROM subscriptions WHERE tenant_id=? AND subscription_id=?",
            (self.tenant, subscription_id),
        )[0]["status"]
        self.assertEqual(status, "active")
        billing = self._query(
            "SELECT payment_status FROM billing_events WHERE tenant_id=? AND subscription_id=?",
            (self.tenant, subscription_id),
        )
        self.assertEqual(billing[0]["payment_status"], "failed")

        ingest_event(
            self.database, self.principal,
            self._event("cancel-request", event_type="cancellation_requested",
                        attributes={"subscription_id": subscription_id, "current_period_end": T3},
                        occurred_at=T2),
            received_at=T2,
        )
        pending = self._query(
            "SELECT status, ended_at, cancellation_requested_at FROM subscriptions "
            "WHERE tenant_id=? AND subscription_id=?", (self.tenant, subscription_id),
        )[0]
        self.assertEqual(pending["status"], "pending_cancel")
        self.assertIsNone(pending["ended_at"])
        self.assertEqual(pending["cancellation_requested_at"].astimezone(timezone.utc),
                         datetime(2026, 10, 10, tzinfo=timezone.utc))

        ingest_event(
            self.database, self.principal,
            self._event("cancel-effective", event_type="subscription_cancelled_effective",
                        attributes={"subscription_id": subscription_id}, occurred_at=T3),
            received_at=T3,
        )
        final = self._query(
            "SELECT status, ended_at FROM subscriptions WHERE tenant_id=? AND subscription_id=?",
            (self.tenant, subscription_id),
        )[0]
        self.assertEqual(final["status"], "ended")
        self.assertEqual(final["ended_at"].astimezone(timezone.utc), datetime(2026, 10, 12, tzinfo=timezone.utc))

    def test_csv_import_reuses_authenticated_event_path_and_preserves_trusted_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.csv"
            path.write_text(
                "source_id,external_id,type,occurred,attributes,available\n"
                f"csv-event,{self.external_a},session_started,{T0},"
                f"{json.dumps({'feature': 'reports'})},{T2}\n",
                encoding="utf-8",
            )
            result = import_csv(
                self.database, self.principal, str(path),
                {"mapping_version": "csv-map-v2", "columns": {
                    "source_event_id": "source_id", "external_customer_id": "external_id",
                    "event_type": "type", "occurred_at": "occurred", "attributes": "attributes",
                    "source_available_at": "available",
                }},
                received_at=T1, trust_source_availability=True,
            )
        self.assertEqual((result["accepted"], result["duplicates"], result["rejected"]), (1, 0, 0))
        row = self._query(
            "SELECT source_available_at, mapping_version FROM canonical_events "
            "WHERE tenant_id=? AND source_event_id='csv-event'", (self.tenant,),
        )[0]
        self.assertEqual(row["source_available_at"], datetime(2026, 10, 10, tzinfo=timezone.utc))
        self.assertEqual(row["mapping_version"], "csv-map-v2")

    def test_concurrent_identical_and_conflicting_event_retries(self):
        event_id = f"race-event-{uuid4().hex[:10]}"
        payload = self._event(event_id)
        barrier = Barrier(8)

        def retry(_):
            barrier.wait()
            return ingest_event(self.database, self.principal, payload, received_at=T1)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(retry, range(8)))
        self.assertEqual(sum(not result["duplicate"] for result in results), 1)
        self.assertEqual(sum(result["duplicate"] for result in results), 7)
        event_rows = self._query(
            "SELECT event_id FROM canonical_events WHERE tenant_id=? AND source_event_id=?",
            (self.tenant, event_id),
        )
        self.assertEqual(len(event_rows), 1)
        self.assertEqual(len(self._query(
            "SELECT event_id FROM usage_events WHERE tenant_id=? AND event_id=?",
            (self.tenant, event_rows[0]["event_id"]),
        )), 1)

        competing_id = f"race-conflict-{uuid4().hex[:10]}"
        variants = (
            self._event(competing_id, attributes={"feature": "reports"}),
            self._event(competing_id, attributes={"feature": "exports"}),
        )
        conflict_barrier = Barrier(2)

        def compete(candidate):
            conflict_barrier.wait()
            try:
                result = ingest_event(self.database, self.principal, candidate, received_at=T1)
                return "duplicate" if result["duplicate"] else "accepted"
            except DataFoundationError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(compete, variants))
        self.assertEqual(outcomes.count("accepted"), 1)
        self.assertEqual(outcomes.count("idempotency_conflict"), 1)
        self.assertEqual(len(self._query(
            "SELECT event_id FROM canonical_events WHERE tenant_id=? AND source_event_id=?",
            (self.tenant, competing_id),
        )), 1)

    def test_subscription_owner_race_is_resolved_by_database_constraints(self):
        subscription_id = f"shared-sub-{uuid4().hex[:10]}"
        barrier = Barrier(2)

        def claim(args):
            event_id, external, started_at = args
            payload = self._event(
                event_id, external=external, event_type="subscription_created",
                attributes={"subscription_id": subscription_id, "status": "active", "started_at": started_at},
            )
            barrier.wait()
            try:
                return ingest_event(self.database, self.principal, payload, received_at=T1)["status"]
            except DataFoundationError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(claim, (
                ("owner-race-a", self.external_a, T0), ("owner-race-b", self.external_b, T1),
            )))
        self.assertEqual(outcomes.count("accepted"), 1)
        self.assertEqual(outcomes.count("contract_conflict"), 1)
        owner = self._query(
            "SELECT customer_id FROM subscription_owners WHERE tenant_id=? AND subscription_id=?",
            (self.tenant, subscription_id),
        )
        self.assertEqual(len(owner), 1)
        self.assertEqual(len(self._query(
            "SELECT event_id FROM canonical_events WHERE tenant_id=? AND source_event_id IN (?, ?)",
            (self.tenant, "owner-race-a", "owner-race-b"),
        )), 1)

    def test_subtype_failure_rolls_back_event_owner_and_projection(self):
        subscription_id = f"rollback-sub-{uuid4().hex[:10]}"
        payload = self._event(
            "rollback-event", event_type="subscription_created",
            attributes={"subscription_id": subscription_id, "status": "active", "started_at": T0},
        )
        with patch("retaniq.data_foundation._record_subscription_event", side_effect=RuntimeError("injected")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                ingest_event(self.database, self.principal, payload, received_at=T1)
        for table, predicate in (
            ("canonical_events", "source_event_id='rollback-event'"),
            ("subscription_events", "event_type='subscription_created'"),
            ("subscription_owners", "subscription_id='" + subscription_id + "'"),
            ("subscriptions", "subscription_id='" + subscription_id + "'"),
        ):
            rows = self._query(f"SELECT COUNT(*) AS n FROM {table} WHERE tenant_id=? AND {predicate}", (self.tenant,))
            self.assertEqual(rows[0]["n"], 0, table)

    def test_batch_checkpoint_commits_with_events_and_rolls_back_together(self):
        failed_stream = f"failed-{uuid4().hex[:10]}"
        records = [
            {"principal": self.principal, "payload": self._event(f"batch-{uuid4().hex[:10]}")}
            for _ in range(2)
        ]
        from retaniq.data_foundation import _persist_normalized_event as persist

        calls = 0

        def fail_after_first(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected batch failure")
            return persist(*args, **kwargs)

        with patch("retaniq.data_foundation._persist_normalized_event", side_effect=fail_after_first):
            with self.assertRaisesRegex(RuntimeError, "injected batch failure"):
                ingest_events_batch(
                    self.database, records, dataset_id=DATASET_ID, stream_name=failed_stream,
                    first_row_number=1, last_row_number=2,
                )
        failed_checkpoint = get_synthetic_import_checkpoint(
            self.database, dataset_id=DATASET_ID, stream_name=failed_stream,
        )
        self.assertEqual(failed_checkpoint["last_row_number"], 0)
        for record in records:
            self.assertEqual(len(self._query(
                "SELECT event_id FROM canonical_events WHERE tenant_id=? AND source_event_id=?",
                (self.tenant, record["payload"]["source_event_id"]),
            )), 0)

        stream = f"accepted-{uuid4().hex[:10]}"
        accepted = ingest_events_batch(
            self.database, records, dataset_id=DATASET_ID, stream_name=stream,
            first_row_number=1, last_row_number=2,
        )
        self.assertEqual((accepted["accepted"], accepted["duplicates"], accepted["last_row_number"]), (2, 0, 2))
        replay = ingest_events_batch(
            self.database, records, dataset_id=DATASET_ID, stream_name=stream,
            first_row_number=1, last_row_number=2,
        )
        self.assertEqual((replay["accepted"], replay["duplicates"], replay["last_row_number"]), (0, 2, 2))
        self.assertEqual(get_synthetic_import_checkpoint(
            self.database, dataset_id=DATASET_ID, stream_name=stream,
        )["accepted_count"], 2)

    def test_historical_reads_use_postgresql_without_fallback(self):
        from retaniq.data_foundation import (
            get_account_snapshot_as_of,
            get_events_as_of,
            get_observation_coverage_as_of,
            get_subscriptions_as_of,
        )

        self.assertEqual(get_events_as_of(self.database, self.principal, self.customer_a, T2), [])
        self.assertEqual(get_subscriptions_as_of(self.database, self.principal, self.customer_a, T2), [])
        self.assertEqual(get_observation_coverage_as_of(self.database, self.principal, self.customer_a, T2), [])
        self.assertEqual(
            get_account_snapshot_as_of(self.database, self.principal, self.customer_a, T2)["status"],
            "not_eligible",
        )


if __name__ == "__main__":
    unittest.main()
