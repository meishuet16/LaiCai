"""Shared SQLite/live-PostgreSQL contracts for historical Data Foundation reads."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

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
    get_events_as_of,
    get_observation_coverage_as_of,
    get_subscriptions_as_of,
    initialize_database,
    ingest_event,
    map_customer_identity,
    record_observation_coverage,
    set_integration_event_categories,
)
from retaniq.database import connect_database
from retaniq.database_config import DatabaseConfig


T0 = "2026-10-01T00:00:00.000000Z"
T1 = "2026-10-05T00:00:00.000000Z"
T2 = "2026-10-10T00:00:00.000000Z"
T3 = "2026-10-12T00:00:00.000000Z"


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


class HistoricalQueryContract:
    """Test the same event/lifecycle/coverage behavior on both database backends."""

    db: str | DatabaseConfig

    def setUp(self):
        suffix = uuid4().hex[:12]
        self.tenant = f"tenant-{suffix}"
        self.customer = f"customer-{suffix}"
        self.source = f"source-{suffix}"
        self.external = f"external-{suffix}"
        self.dataset_id = f"coverage-test-{suffix}"
        if isinstance(self.db, str):
            bind_dataset_identity(
                self.db, dataset_id=self.dataset_id, dataset_version="test-v1", dataset_type="synthetic_saas",
                target_policy_version="test-policy-v1", generator_version="test-generator-v1",
                manifest_sha256="a" * 64,
            )
        create_tenant(self.db, self.tenant)
        create_customer(self.db, self.tenant, self.customer)
        self.token = create_integration(
            self.db, self.tenant, self.source,
            authorized_purposes=("retention_inference", "identity_mapping", "billing_valuation"),
            authorized_categories=("usage", "billing", "subscription"),
        )
        map_customer_identity(self.db, self.tenant, self.source, self.external, self.customer)
        self.principal = authenticate_integration(self.db, self.token)
        self.no_billing_token = create_service_principal(
            self.db, self.tenant, role="analyst", authorized_sources=(self.source,),
            authorized_purposes=("retention_inference",),
        )
        self.no_billing = authenticate_service_principal(self.db, self.no_billing_token)

    def event(self, source_event_id, event_type, occurred_at, attributes, *, available=None, source=None):
        return ingest_event(
            self.db, self.principal,
            {"source": source or self.source, "source_event_id": source_event_id,
             "external_customer_id": self.external, "event_type": event_type,
             "occurred_at": occurred_at, "attributes": attributes, "schema_version": "1.0"},
            received_at=T1 if available is None else available,
            trusted_source_available_at=available,
        )

    def test_event_cutoff_uses_occurrence_and_existing_availability_fallback(self):
        self.event("visible", "feature_used", T0, {"feature": "reports", "quantity": 4, "unit": "sessions"})
        self.event("late-available", "session_started", T0, {"feature": "reports"}, available=T3)
        self.event("future-occurrence", "session_started", T3, {"feature": "reports"}, available=T0)
        at_t1 = get_events_as_of(self.db, self.principal, self.customer, T1)
        self.assertEqual([row["source_event_id"] for row in at_t1], ["visible"])
        self.assertEqual(at_t1[0]["attributes"], {"feature": "reports", "quantity": 4, "unit": "sessions"})
        at_boundary = get_events_as_of(self.db, self.principal, self.customer, T3)
        self.assertEqual(
            {row["source_event_id"] for row in at_boundary},
            {"visible", "late-available", "future-occurrence"},
        )

    def test_time_offset_equivalence_and_stable_same_timestamp_order(self):
        self.event("same-z", "session_started", T0, {"feature": "reports"})
        self.event("same-offset", "session_started", "2026-10-01T08:00:00+08:00", {"feature": "exports"})
        utc = get_events_as_of(self.db, self.principal, self.customer, T1)
        offset = get_events_as_of(self.db, self.principal, self.customer, "2026-10-05T08:00:00+08:00")
        self.assertEqual(utc, offset)
        self.assertEqual([row["source_event_id"] for row in utc], ["same-z", "same-offset"])

    def test_authorization_redaction_and_cross_tenant_isolation(self):
        self.event("money", "invoice_paid", T0,
                   {"subscription_id": "sub-money", "amount_minor": 1350, "currency": "JPY"})
        restricted = get_events_as_of(self.db, self.no_billing, self.customer, T1)
        self.assertNotIn("amount_minor", restricted[0])
        self.assertNotIn("currency", restricted[0]["attributes"])
        self.assertEqual(get_events_as_of(self.db, self.no_billing, "not-this-customer", T1), [])
        service_token = create_service_principal(
            self.db, self.tenant, role="analyst", authorized_sources=(self.source,),
            authorized_purposes=("retention_inference",),
        )
        service = authenticate_service_principal(self.db, service_token)
        self.assertEqual(get_events_as_of(self.db, service, self.customer, T1)[0]["payment_status"], "succeeded")
        with self.assertRaises(DataFoundationError):
            get_events_as_of(self.db, service, self.customer, T1, category="unknown")

    def test_stored_category_grants_filter_historical_reads(self):
        self.event("historical-billing", "invoice_paid", T0,
                   {"subscription_id": "sub-category", "amount_minor": 800, "currency": "USD"})
        set_integration_event_categories(self.db, self.tenant, self.source, ("usage",))
        refreshed = authenticate_integration(self.db, self.token)
        self.assertEqual(get_events_as_of(self.db, refreshed, self.customer, T2, category="billing"), [])
        self.assertEqual(get_subscriptions_as_of(self.db, refreshed, self.customer, T2), [])

    def test_historical_subscription_lifecycle_and_cutoff_valuation(self):
        self.event("sub-created", "subscription_created", T0,
                   {"subscription_id": "sub-1", "status": "active", "started_at": T0,
                    "plan_id": "starter", "billing_interval": "year", "billing_interval_count": 1,
                    "amount_minor": 12000, "discount_minor": 1200, "currency": "JPY"})
        self.event("sub-price-later", "subscription_updated", T2,
                   {"subscription_id": "sub-1", "plan_id": "pro", "amount_minor": 24000,
                    "currency": "JPY"})
        self.event("cancel-later", "cancellation_requested", T3,
                   {"subscription_id": "sub-1", "current_period_end": T3})
        early = get_account_snapshot_as_of(self.db, self.principal, self.customer, T1)
        self.assertEqual(early["status"], "eligible")
        self.assertEqual(early["valuation"]["mrr_minor"], 900)
        self.assertEqual(early["subscriptions"][0]["plan_id"], "starter")
        later = get_account_snapshot_as_of(self.db, self.principal, self.customer, T2)
        self.assertEqual(later["subscriptions"][0]["plan_id"], "pro")
        self.assertEqual(later["valuation"]["mrr_minor"], 1900)
        self.assertEqual(get_account_snapshot_as_of(self.db, self.principal, self.customer, T2)["status"], "eligible")
        at_cancel = get_account_snapshot_as_of(self.db, self.principal, self.customer, T3)
        self.assertEqual(at_cancel["status"], "known_cancellation")
        self.assertIsNone(at_cancel["subscriptions"][0]["ended_at"])

    def test_payment_failure_does_not_end_entitlement_and_unauthorized_mrr_is_absent(self):
        self.event("sub-active", "subscription_created", T0,
                   {"subscription_id": "sub-2", "status": "active", "started_at": T0,
                    "billing_interval": "month", "billing_interval_count": 1,
                    "amount_minor": 4500, "currency": "USD"})
        self.event("pay-fail", "payment_failed", T2,
                   {"subscription_id": "sub-2", "amount_minor": 4500, "currency": "USD"})
        snapshot = get_account_snapshot_as_of(self.db, self.no_billing, self.customer, T2)
        self.assertEqual(snapshot["status"], "eligible")
        self.assertIsNone(snapshot["valuation"])
        self.assertNotIn("mrr_minor", snapshot["subscriptions"][0])
        billing = get_events_as_of(self.db, self.no_billing, self.customer, T2, category="billing")
        self.assertEqual(billing[0]["payment_status"], "failed")
        self.assertNotIn("amount_minor", billing[0])

    def test_multiple_subscriptions_partial_termination_and_reactivation(self):
        for source_event_id, subscription_id in (("first-active", "sub-a"), ("second-active", "sub-b")):
            self.event(source_event_id, "subscription_created", T0,
                       {"subscription_id": subscription_id, "status": "active", "started_at": T0,
                        "billing_interval": "month", "billing_interval_count": 1,
                        "amount_minor": 1000, "currency": "USD"})
        self.event("first-ends", "subscription_cancelled_effective", T2, {"subscription_id": "sub-a"})
        partial = get_account_snapshot_as_of(self.db, self.principal, self.customer, T2)
        self.assertEqual(partial["status"], "eligible")
        self.assertEqual([row["status"] for row in partial["subscriptions"]], ["ended", "active"])
        self.assertEqual(partial["valuation"]["mrr_minor"], 1000)
        self.event("second-ends", "subscription_non_renewed_effective", T3, {"subscription_id": "sub-b"})
        ended = get_account_snapshot_as_of(self.db, self.principal, self.customer, T3)
        self.assertEqual(ended["status"], "not_eligible")
        self.event("second-reactivates", "subscription_updated", T3,
                   {"subscription_id": "sub-b", "status": "active", "started_at": T3,
                    "amount_minor": 1500, "currency": "USD"})
        reactivated = get_account_snapshot_as_of(self.db, self.principal, self.customer, T3)
        self.assertEqual(reactivated["status"], "eligible")
        self.assertEqual(reactivated["valuation"]["mrr_minor"], 1500)

    def test_missing_and_mixed_currency_valuation_remain_unavailable(self):
        self.event("priced-sub", "subscription_created", T0,
                   {"subscription_id": "sub-priced", "status": "active", "started_at": T0,
                    "billing_interval": "month", "billing_interval_count": 1,
                    "amount_minor": 1000, "currency": "USD"})
        self.event("unpriced-sub", "subscription_created", T0,
                   {"subscription_id": "sub-unpriced", "status": "active", "started_at": T0})
        missing = get_account_snapshot_as_of(self.db, self.principal, self.customer, T1)
        self.assertEqual(missing["valuation"]["status"], "missing_price")
        self.event("unpriced-currency", "subscription_updated", T2,
                   {"subscription_id": "sub-unpriced", "billing_interval": "month",
                    "billing_interval_count": 1, "amount_minor": 1000, "currency": "EUR"})
        mixed = get_account_snapshot_as_of(self.db, self.principal, self.customer, T2)
        self.assertEqual(mixed["valuation"]["status"], "mixed_currency")
        self.assertIsNone(mixed["valuation"]["mrr_minor"])

    def test_historical_queries_do_not_mutate_event_history(self):
        self.event("read-only", "session_started", T0, {"feature": "reports"})
        with connect_database(self.db) as connection:
            before = connection.execute("SELECT COUNT(*) AS n FROM canonical_events").fetchone()["n"]
        get_events_as_of(self.db, self.principal, self.customer, T1)
        get_subscriptions_as_of(self.db, self.principal, self.customer, T1)
        get_account_snapshot_as_of(self.db, self.principal, self.customer, T1)
        get_observation_coverage_as_of(self.db, self.principal, self.customer, T1)
        with connect_database(self.db) as connection:
            after = connection.execute("SELECT COUNT(*) AS n FROM canonical_events").fetchone()["n"]
        self.assertEqual(before, after)

    def test_coverage_as_of_idempotency_and_missing_is_not_zero(self):
        record = {
            "coverage_id": "coverage-complete", "customer_id": self.customer,
            "source_category": "usage", "covered_from": T0, "covered_through": T1,
            "coverage_status": "complete", "coverage_completeness": 1.0,
            "coverage_available_at": T2, "observation_policy_version": "coverage-v1",
        }
        self.assertEqual(record_observation_coverage(self.db, self.principal, record)["status"], "accepted")
        self.assertEqual(record_observation_coverage(self.db, self.principal, record)["status"], "duplicate")
        changed = {**record, "coverage_completeness": 0.75, "coverage_status": "partial"}
        with self.assertRaises(DataFoundationError) as conflict:
            record_observation_coverage(self.db, self.principal, changed)
        self.assertEqual(conflict.exception.code, "idempotency_conflict")
        self.assertEqual(get_observation_coverage_as_of(self.db, self.principal, self.customer, T1), [])
        rows = get_observation_coverage_as_of(self.db, self.principal, self.customer, T2, source_category="usage")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["coverage_status"], "complete")
        self.assertEqual(rows[0]["covered_from"], T0)
        self.assertEqual(get_events_as_of(self.db, self.principal, self.customer, T2, category="usage"), [])

    def test_coverage_partial_and_tenant_source_scope(self):
        record = {
            "coverage_id": "coverage-partial", "customer_id": self.customer,
            "source_category": "usage", "covered_from": T0, "covered_through": T1,
            "coverage_status": "partial", "coverage_completeness": 0.5,
            "coverage_available_at": T2, "observation_policy_version": "coverage-v1",
        }
        record_observation_coverage(self.db, self.principal, record)
        overlapping = {**record, "coverage_id": "coverage-overlap", "covered_through": T2,
                       "coverage_available_at": T3}
        record_observation_coverage(self.db, self.principal, overlapping)
        foreign_tenant = f"foreign-{self.tenant}"
        foreign_customer = f"foreign-{self.customer}"
        create_tenant(self.db, foreign_tenant)
        create_customer(self.db, foreign_tenant, foreign_customer)
        with self.assertRaises(DataFoundationError) as cross_tenant:
            record_observation_coverage(
                self.db, self.principal, {**record, "coverage_id": "foreign-coverage",
                                          "customer_id": foreign_customer},
            )
        self.assertEqual(cross_tenant.exception.code, "identity_not_mapped")
        other_source = f"other-{self.source}"
        create_integration(self.db, self.tenant, other_source)
        token = create_service_principal(
            self.db, self.tenant, role="analyst", authorized_sources=(f"other-{self.source}",),
            authorized_purposes=("retention_inference",),
        )
        other = authenticate_service_principal(self.db, token)
        self.assertEqual(get_observation_coverage_as_of(self.db, other, self.customer, T3), [])
        visible = get_observation_coverage_as_of(self.db, self.principal, self.customer, T3)
        self.assertEqual(len(visible), 2)
        self.assertEqual({row["coverage_id"] for row in visible}, {"coverage-partial", "coverage-overlap"})
        self.assertEqual(visible[0]["coverage_status"], "partial")
        self.assertEqual(visible[0]["coverage_completeness"], 0.5)


class SQLiteHistoricalQueryTests(HistoricalQueryContract, unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self._temp.name) / "history.sqlite3")
        initialize_database(self.db)
        super().setUp()

    def tearDown(self):
        self._temp.cleanup()


_POSTGRES_CONFIG = _postgres_test_config()


@unittest.skipUnless(
    _POSTGRES_CONFIG,
    "requires an explicitly disposable loopback PostgreSQL database named retaniq_test_*",
)
class PostgreSQLHistoricalQueryTests(HistoricalQueryContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = _POSTGRES_CONFIG
        from postgresql_security_support import bootstrap_test_roles
        bootstrap_test_roles(cls.db)
        initialize_database(cls.db, migrate_postgresql=True)
        with connect_database(cls.db) as connection:
            identity = connection.execute("SELECT dataset_id FROM dataset_identity WHERE singleton_id=1").fetchone()
            if identity is None:
                connection.execute(
                    "INSERT INTO dataset_identity(singleton_id, dataset_id, dataset_version, dataset_type, "
                    "target_policy_version, generator_version, manifest_sha256, bound_at) "
                    "VALUES (1, ?, 'test-v1', 'synthetic_saas', 'test-policy-v1', 'test-generator-v1', ?, ?)",
                    ("pg-ingestion-parity-test-v1", "b" * 64, datetime(2026, 10, 1, tzinfo=timezone.utc)),
                )


if __name__ == "__main__":
    unittest.main()
