from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from retaniq.api import create_app
from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_service_principal,
    create_customer,
    create_integration,
    create_tenant,
    get_account_snapshot_as_of,
    get_events_as_of,
    initialize_database,
    ingest_event,
    map_customer_identity,
    provision_member2_reader_principal,
    record_observation_coverage,
    revoke_service_principal,
    store_feature_snapshot,
    _require_purposes,
)


class Member1P0ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.db = Path(self.temporary.name) / "reader.sqlite3"
        initialize_database(self.db)
        create_tenant(self.db, "tenant-01")
        create_tenant(self.db, "tenant-02")
        self.sources = {
            "usage": "source-usage",
            "billing": "source-billing",
            "subscription": "source-subscription",
        }
        integration_tokens = {}
        for category, source in self.sources.items():
            integration_tokens[category] = create_integration(
                self.db, "tenant-01", source,
                authorized_purposes=("retention_inference", "billing_valuation") if category == "billing"
                else ("retention_inference",),
                authorized_categories=(category,),
            )
        self.customer = "customer-one"
        create_customer(self.db, "tenant-01", self.customer)
        for category, source in self.sources.items():
            map_customer_identity(self.db, "tenant-01", source, f"external-{category}", self.customer)
        self.usage_token = integration_tokens["usage"]
        self.token_sink: list[str] = []
        self.reader_info = provision_member2_reader_principal(
            self.db, service_principal_id="member2-standard-tenant-01-reader", tenant_id="tenant-01",
            authorized_sources=tuple(self.sources.values()), deliver_token=self.token_sink.append,
        )
        self.token = self.token_sink[-1]
        self.reader = authenticate_service_principal(self.db, self.token)
        ingest_event(self.db, self._usage_principal(), {
            "source": "source-usage", "source_event_id": "usage-1", "external_customer_id": "external-usage",
            "event_type": "session_started", "occurred_at": "2026-09-01T00:00:00Z",
            "attributes": {"feature": "reports"}, "schema_version": "1.0",
        })
        from retaniq.data_foundation import authenticate_integration
        billing = authenticate_integration(self.db, integration_tokens["billing"])
        ingest_event(self.db, billing, {
            "source": "source-billing", "source_event_id": "billing-1", "external_customer_id": "external-billing",
            "event_type": "payment_failed", "occurred_at": "2026-09-02T00:00:00Z",
            "attributes": {"amount_minor": 700, "currency": "USD"}, "schema_version": "1.0",
        })
        outside_token = create_integration(
            self.db, "tenant-01", "source-outside", authorized_purposes=("retention_inference",),
            authorized_categories=("usage",),
        )
        map_customer_identity(self.db, "tenant-01", "source-outside", "external-outside", self.customer)
        outside = authenticate_integration(self.db, outside_token)
        ingest_event(self.db, outside, {
            "source": "source-outside", "source_event_id": "outside-1", "external_customer_id": "external-outside",
            "event_type": "session_started", "occurred_at": "2026-09-03T00:00:00Z",
            "attributes": {"feature": "other"}, "schema_version": "1.0",
        })
        # A malformed out-of-contract row proves read filtering independently of write validation.
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "INSERT INTO canonical_events(tenant_id,source,source_event_id,customer_id,category,event_type,"
                "occurred_at,received_at,source_available_at,schema_version,mapping_version,normalized_payload_sha256) "
                "VALUES('tenant-01','source-usage','forged-category','customer-one','billing','payment_failed',"
                "'2026-09-04T00:00:00.000000Z','2026-09-04T00:00:00.000000Z',"
                "'2026-09-04T00:00:00.000000Z','1.0','canonical-v1',?)", ("f" * 64,),
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.temporary.cleanup()

    def _usage_principal(self):
        from retaniq.data_foundation import authenticate_integration
        return authenticate_integration(self.db, self.usage_token)

    def _provision(self, sink=None):
        return provision_member2_reader_principal(
            self.db, service_principal_id="member2-standard-tenant-01-reader", tenant_id="tenant-01",
            authorized_sources=tuple(self.sources.values()), deliver_token=sink or self.token_sink.append,
        )

    def _post(self, app, path, token):
        environ = {}
        setup_testing_defaults(environ)
        environ.update({"REQUEST_METHOD": "GET", "PATH_INFO": path,
                        "HTTP_AUTHORIZATION": f"Bearer {token}"})
        captured = {}
        body = b"".join(app(environ, lambda status, headers: captured.update(status=status, headers=headers)))
        return captured["status"], json.loads(body)

    def test_minimum_grant_real_auth_and_read_only_behaviour(self):
        self.assertEqual(self.reader.role, "analyst")
        self.assertEqual(self.reader.tenant_id, "tenant-01")
        self.assertEqual(self.reader.authorized_sources, tuple(sorted(self.sources.values())))
        self.assertEqual(self.reader.authorized_purposes, ("retention_inference",))
        events = get_events_as_of(self.db, self.reader, self.customer, "2026-10-12T00:00:00Z")
        self.assertEqual({event["source"] for event in events}, {"source-usage", "source-billing"})
        self.assertNotIn("source-outside", {event["source"] for event in events})
        self.assertNotIn("forged-category", {event["source_event_id"] for event in events})
        self.assertEqual({event["category"] for event in events}, {"usage", "billing"})
        billing_event = next(event for event in events if event["category"] == "billing")
        self.assertEqual(billing_event["attributes"]["payment_status"], "failed")
        self.assertFalse({"amount_minor", "currency"} & set(billing_event["attributes"]))
        self.assertFalse({"billing_valuation", "model_artifact_write", "identity_mapping"}
                         & set(self.reader.authorized_purposes))

    def test_missing_invalid_and_cross_tenant_credentials_are_denied(self):
        from retaniq.data_foundation import authenticate_service_principal
        for token in (None, "not-a-valid-token"):
            with self.assertRaises(DataFoundationError) as denied:
                authenticate_service_principal(self.db, token)
            self.assertEqual(denied.exception.code, "unauthorized")
        create_customer(self.db, "tenant-02", "customer-two")
        with self.assertRaises(DataFoundationError) as denied:
            get_account_snapshot_as_of(self.db, self.reader, "customer-two", "2026-09-30T00:00:00Z")
        self.assertEqual(denied.exception.code, "not_found")

    def test_tampered_source_scope_is_rejected(self):
        from dataclasses import replace
        tampered = replace(self.reader, authorized_sources=(*self.reader.authorized_sources, "foreign-source"))
        with self.assertRaises(DataFoundationError) as denied:
            get_events_as_of(self.db, tampered, self.customer, "2026-09-30T00:00:00Z")
        self.assertEqual(denied.exception.code, "unauthorized")

    def test_reader_cannot_write_artifacts_or_coverage_or_use_admin_route(self):
        with self.assertRaises(DataFoundationError) as artifact:
            store_feature_snapshot(
                self.db, self.reader, self.customer, "2026-09-01T00:00:00Z", "feature-v1",
                "2026-09-01T00:00:00Z", {}, "available",
            )
        self.assertEqual(artifact.exception.code, "purpose_not_authorized")
        with self.assertRaises(DataFoundationError) as coverage:
            record_observation_coverage(self.db, self.reader, {})
        self.assertEqual(coverage.exception.code, "unauthorized")
        with self.assertRaises(DataFoundationError) as identity_mapping:
            _require_purposes(self.reader, "identity_mapping")
        self.assertEqual(identity_mapping.exception.code, "purpose_not_authorized")
        status, response = self._post(create_app(self.db), "/v1/admin/integrations", self.token)
        self.assertEqual(status, "401 Unauthorized")
        self.assertEqual(response["error"], "unauthorized")
        status, response = self._post(create_app(self.db), "/v1/admin/identity-mapping", self.token)
        self.assertEqual(status, "404 Not Found")
        self.assertEqual(response["error"], "not_found")

    def test_retry_rotates_one_fixed_principal_and_revoke_invalidates_it(self):
        new_tokens: list[str] = []
        result = self._provision(new_tokens.append)
        self.assertEqual(result["credential_operation"], "rotate")
        with self.assertRaises(DataFoundationError) as old:
            from retaniq.data_foundation import authenticate_service_principal
            authenticate_service_principal(self.db, self.token)
        self.assertEqual(old.exception.code, "unauthorized")
        rotated = authenticate_service_principal(self.db, new_tokens[0])
        self.assertEqual(rotated.authorized_purposes, ("retention_inference",))
        revoke_service_principal(self.db, "member2-standard-tenant-01-reader")
        with self.assertRaises(DataFoundationError) as revoked:
            from retaniq.data_foundation import authenticate_service_principal
            authenticate_service_principal(self.db, new_tokens[0])
        self.assertEqual(revoked.exception.code, "unauthorized")
        connection = sqlite3.connect(self.db)
        self.assertEqual(connection.execute("select count(*) from service_principals").fetchone()[0], 0)
        self.assertEqual([row[0] for row in connection.execute(
            "select operation from service_principal_credential_audit order by audit_id")],
            ["provision", "rotate", "revoke"])
        connection.close()

    def test_failed_secret_delivery_rolls_back_principal_and_audit(self):
        connection = sqlite3.connect(self.db)
        connection.execute("delete from service_principals")
        connection.execute("delete from service_principal_credential_audit")
        connection.commit()
        connection.close()
        with self.assertRaises(DataFoundationError):
            self._provision(lambda _token: (_ for _ in ()).throw(OSError("sink rejected")))
        connection = sqlite3.connect(self.db)
        self.assertEqual(connection.execute("select count(*) from service_principals").fetchone()[0], 0)
        self.assertEqual(connection.execute("select count(*) from service_principal_credential_audit").fetchone()[0], 0)
        connection.close()

    def test_credentials_are_digest_only_and_never_in_diagnostics(self):
        connection = sqlite3.connect(self.db)
        digest = connection.execute(
            "select token_digest from service_principals where service_principal_id=?",
            ("member2-standard-tenant-01-reader",),
        ).fetchone()[0]
        connection.close()
        self.assertEqual(digest, hashlib.sha256(self.token.encode("ascii")).hexdigest())
        self.assertNotIn(self.token, json.dumps(self.reader_info))
        self.assertNotIn(self.token, json.dumps({"purpose": self.reader.authorized_purposes}))

    def test_revoke_guard_rejects_immutable_standard_source_before_opening_it(self):
        immutable_source = (
            Path.home() / "RetainIQ-private" / "synthetic_saas_v1_2" / "db"
            / "synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3"
        )
        with self.assertRaises(DataFoundationError) as denied:
            revoke_service_principal(immutable_source, "member2-standard-tenant-01-reader")
        self.assertEqual(denied.exception.code, "invalid_contract")


if __name__ == "__main__":
    unittest.main()
