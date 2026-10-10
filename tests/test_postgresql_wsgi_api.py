"""Live checks for the existing WSGI routes on SQLite and PostgreSQL."""

from __future__ import annotations

import io
import json
import os
import unittest
from urllib.parse import unquote, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql

from retaniq.api import create_app
from retaniq.data_foundation import (
    authenticate_integration,
    authenticate_service_principal,
    create_customer,
    create_integration,
    create_service_principal,
    create_tenant,
    initialize_database,
    map_customer_identity,
)
from retaniq.database_config import DatabaseConfig
from retaniq.postgresql_migrations import MigrationHistoryError


def _test_config() -> DatabaseConfig | None:
    dsn = os.environ.get("RETAINIQ_POSTGRES_TEST_DSN")
    if not dsn or os.environ.get("RETAINIQ_POSTGRES_TEST_DISPOSABLE") != "1":
        return None
    try:
        config = DatabaseConfig.from_value(dsn, allow_insecure_local_postgresql=True)
        parsed = urlsplit(config.postgresql_dsn)
        db_name = unquote(parsed.path.lstrip("/"))
    except (TypeError, ValueError):
        return None
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not db_name.startswith("retaniq_test_"):
        return None
    return config


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


_CONFIG = _test_config()


@unittest.skipUnless(_CONFIG, "requires an explicitly disposable loopback PostgreSQL database")
class PostgreSQLWSGIAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = _CONFIG
        initialize_database(cls.config, migrate_postgresql=True)
        cls.server = psycopg.connect(cls.config.postgresql_dsn, connect_timeout=4)
        identity = cls.server.execute(
            "SELECT current_database(), version(), current_setting('data_directory')",
        ).fetchone()
        cls.assert_identity = identity
        if not identity[0].startswith("retaniq_test_") or "PostgreSQL 16." not in identity[1]:
            raise AssertionError("PostgreSQL test target identity does not match expected disposable server")
        cls.server.close()

    def setUp(self):
        suffix = uuid4().hex[:10]
        self.tenant = f"wsgi-tenant-{suffix}"
        self.customer = f"wsgi-customer-{suffix}"
        self.source = f"wsgi-source-{suffix}"
        self.external = f"wsgi-external-{suffix}"
        create_tenant(self.config, self.tenant)
        create_customer(self.config, self.tenant, self.customer)
        token = create_integration(
            self.config, self.tenant, self.source,
            authorized_purposes=("retention_inference",), authorized_categories=("usage",),
        )
        map_customer_identity(self.config, self.tenant, self.source, self.external, self.customer)
        self.token = token
        self.principal = authenticate_integration(self.config, token)
        admin_token = create_service_principal(
            self.config, self.tenant, role="admin", authorized_sources=(self.source,),
            authorized_purposes=("integration_health",),
        )
        self.admin_token = admin_token
        self.app = create_app(self.config)

    def event(self, **overrides):
        payload = {
            "source": self.source, "source_event_id": f"event-{uuid4().hex[:8]}",
            "external_customer_id": self.external, "event_type": "session_started",
            "occurred_at": "2026-10-01T00:00:00Z", "attributes": {"feature": "reports"},
            "schema_version": "1.0",
        }
        payload.update(overrides)
        return payload

    def test_existing_ingestion_and_health_routes_use_postgresql(self):
        accepted = _request(
            self.app, "POST", "/v1/ingest/events", token=self.token, body=self.event(),
        )
        self.assertTrue(accepted["status"].startswith("201"))
        self.assertEqual(accepted["body"]["status"], "accepted")
        health = _request(self.app, "GET", "/v1/integrations", token=self.token)
        self.assertTrue(health["status"].startswith("200"))
        self.assertEqual(len(health["body"]["integrations"]), 1)
        admin_without_rights = _request(self.app, "GET", "/v1/admin/integrations", token=self.token)
        self.assertTrue(admin_without_rights["status"].startswith("401"))
        admin = _request(self.app, "GET", "/v1/admin/integrations", token=self.admin_token)
        self.assertTrue(admin["status"].startswith("200"))
        self.assertEqual(len(admin["body"]["integrations"]), 1)

    def test_auth_tenant_category_and_bad_request_rejections_are_atomic(self):
        missing = _request(self.app, "POST", "/v1/ingest/events", body=self.event())
        invalid = _request(
            self.app, "POST", "/v1/ingest/events", token="not-a-valid-token", body=self.event(),
        )
        wrong_tenant = _request(
            self.app, "POST", "/v1/ingest/events", token=self.token,
            body=self.event(external_customer_id=f"unmapped-{uuid4().hex[:6]}", tenant_id="other-tenant"),
        )
        wrong_category = _request(
            self.app, "POST", "/v1/ingest/events", token=self.token,
            body=self.event(
                event_type="subscription_created",
                attributes={"subscription_id": "sub-1", "status": "active", "started_at": "2026-10-01T00:00:00Z"},
            ),
        )
        self.assertTrue(missing["status"].startswith("401"))
        self.assertTrue(invalid["status"].startswith("401"))
        self.assertTrue(wrong_tenant["status"].startswith("400"))
        self.assertTrue(wrong_category["status"].startswith("403"))
        with psycopg.connect(self.config.postgresql_dsn) as connection:
            count = connection.execute(
                "SELECT count(*) FROM canonical_events WHERE tenant_id=%s AND customer_id=%s",
                (self.tenant, self.customer),
            ).fetchone()[0]
        self.assertEqual(count, 0)
        rendered = json.dumps([missing["body"], invalid["body"], wrong_tenant["body"], wrong_category["body"]])
        self.assertNotIn("postgresql://", rendered)

    def test_startup_requires_migrated_schema_and_does_not_leak_target(self):
        db_name = f"retaniq_test_uninit_{uuid4().hex[:10]}"
        parsed = urlsplit(self.config.postgresql_dsn)
        child = DatabaseConfig.from_value(
            urlunsplit(parsed._replace(path=f"/{db_name}")),
            allow_insecure_local_postgresql=True,
        )
        with psycopg.connect(self.config.postgresql_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        try:
            with self.assertRaises(MigrationHistoryError) as raised:
                create_app(child)
            self.assertEqual(str(raised.exception), "PostgreSQL schema has not been initialized")
            self.assertNotIn(child.postgresql_dsn, str(raised.exception))
        finally:
            with psycopg.connect(self.config.postgresql_dsn, autocommit=True) as admin:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))


if __name__ == "__main__":
    unittest.main()
