import json
import re
import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from retaniq.postgresql_migrations import discover_migrations
from retaniq.supabase_preflight import DATABASE_ROLE_PLAN, RLS_TABLE_OWNERSHIP, preflight


PROJECT_REF = "abcde12345fghij67890"
ENV = {
    "RETAINIQ_DATABASE_BACKEND": "supabase",
    "RETAINIQ_SUPABASE_PROJECT_URL": f"https://{PROJECT_REF}.supabase.co",
    "RETAINIQ_SUPABASE_EXPECTED_PROJECT_REF": PROJECT_REF,
    "RETAINIQ_SUPABASE_DB_MIGRATION_DSN": (
        f"postgresql://postgres:migration-secret@db.{PROJECT_REF}.supabase.co:5432/postgres?sslmode=require"
    ),
    "RETAINIQ_SUPABASE_DB_APP_DSN": (
        f"postgresql://retainiq_app.{PROJECT_REF}:app-secret@fixture.pooler.supabase.com:5432/postgres?sslmode=require"
    ),
    "RETAINIQ_SUPABASE_CONNECTION_MODE": "SESSION_POOLER",
}


class _Result:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, role, *, bypass=False, missing_privileges=False):
        self.role = role
        self.bypass = bypass
        self.missing_privileges = missing_privileges
        self.closed = False
        self.statements = []

    @contextmanager
    def transaction(self):
        yield self

    def execute(self, statement, parameters=()):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, parameters))
        if normalized == "SELECT 1 AS probe":
            return _Result([{"probe": 1}])
        if "current_database() AS database" in normalized:
            return _Result([{
                "database": "postgres", "role": self.role,
                "server_version": "PostgreSQL 16.test",
                "rolsuper": False, "rolbypassrls": self.bypass,
            }])
        if normalized.startswith("SELECT required.table_name"):
            return _Result([
                {"table_name": table, "privilege": "SELECT", "granted": not self.missing_privileges}
                for table in ("integrations", "service_principals")
            ])
        if normalized.startswith("SELECT to_regclass"):
            return _Result([{"migration_table": "retaniq_schema_migrations"}])
        if normalized.startswith('SELECT version, checksum FROM "public"'):
            return _Result([
                {"version": item.version, "checksum": item.checksum}
                for item in discover_migrations()
            ])
        if normalized == "SELECT current_user AS role":
            return _Result([{"role": self.role}])
        if normalized == "SET TRANSACTION READ ONLY":
            return _Result()
        raise AssertionError(f"unexpected preflight SQL: {normalized}")

    def close(self):
        self.closed = True


def _driver_module():
    return types.ModuleType("psycopg")


class SupabasePreflightTests(unittest.TestCase):
    def test_missing_or_non_supabase_configuration_returns_explicit_blocked(self):
        calls = []
        self.assertEqual(preflight({}, connector=lambda _: calls.append("connected")), {
            "status": "BLOCKED",
            "remote_connectivity": "BLOCKED",
            "reason": "explicit_supabase_demo_target_required",
        })
        self.assertEqual(calls, [])
        result = preflight({"RETAINIQ_DATABASE_BACKEND": "supabase"})
        self.assertEqual(result["remote_connectivity"], "BLOCKED")
        self.assertNotIn("database", result)

    def test_preflight_is_read_only_sanitized_and_closes_both_connections(self):
        connections = []

        def connector(config):
            connection = _FakeConnection("retainiq_app" if not connections else "retainiq_migrator")
            connections.append((config, connection))
            return connection

        with patch.dict(sys.modules, {"psycopg": _driver_module()}):
            result = preflight(ENV, connector=connector)
        self.assertEqual(result["status"], "PREFLIGHT_PASSED_NOT_DEPLOYMENT_APPROVAL")
        self.assertEqual(result["remote_connectivity"], "CONNECTED_READ_ONLY")
        self.assertEqual(result["project_ref"], PROJECT_REF)
        self.assertEqual(result["application_role"], "retainiq_app")
        self.assertEqual(result["server_version"], "PostgreSQL 16.test")
        self.assertEqual(result["migration_role"], "retainiq_migrator")
        self.assertEqual(result["migration_readiness"], "CHECKSUMS_MATCH")
        serialized = json.dumps(result)
        self.assertNotIn("app-secret", serialized)
        self.assertNotIn("migration-secret", serialized)
        self.assertEqual(len(connections), 2)
        for _, connection in connections:
            self.assertTrue(connection.closed)
            self.assertTrue(connection.statements)
            for statement, _ in connection.statements:
                self.assertTrue(statement.startswith("SELECT ") or statement == "SET TRANSACTION READ ONLY")
                self.assertFalse(re.match(r"^(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|TRUNCATE)\b", statement, re.I))
        self.assertTrue(connections[1][0].connection_mode == "DIRECT")

    def test_privileged_app_role_is_reported_as_security_gap(self):
        connections = []

        def connector(config):
            connection = _FakeConnection("retainiq_app", bypass=(not connections))
            connections.append(connection)
            return connection

        with patch.dict(sys.modules, {"psycopg": _driver_module()}):
            result = preflight(ENV, connector=connector)
        self.assertEqual(result["remote_connectivity"], "CONNECTED_READ_ONLY")
        self.assertEqual(result["application_role_rls_bypass"], True)
        self.assertEqual(result["status"], "CONNECTED_WITH_READINESS_GAPS")

    def test_missing_app_table_privileges_are_reported_without_granting_them(self):
        connections = []

        def connector(config):
            connection = _FakeConnection(
                "retainiq_app", missing_privileges=(not connections),
            )
            connections.append(connection)
            return connection

        with patch.dict(sys.modules, {"psycopg": _driver_module()}):
            result = preflight(ENV, connector=connector)
        self.assertEqual(result["application_privileges"], "MISSING")
        self.assertEqual(
            result["application_privileges_missing"],
            ["public.integrations:SELECT", "public.service_principals:SELECT"],
        )
        self.assertEqual(result["status"], "CONNECTED_WITH_READINESS_GAPS")

    def test_connection_failure_does_not_expose_driver_text_and_cleans_up(self):
        app = _FakeConnection("retainiq_app")
        calls = 0

        def connector(_config):
            nonlocal calls
            calls += 1
            if calls == 1:
                return app
            raise RuntimeError("connection failed for password migration-secret")

        with patch.dict(sys.modules, {"psycopg": _driver_module()}):
            result = preflight(ENV, connector=connector)
        self.assertTrue(app.closed)
        self.assertEqual(result["reason"], "read_only_preflight_failed")
        self.assertNotIn("migration-secret", json.dumps(result))

    def test_role_plan_and_rls_inventory_cover_actual_migration_tables(self):
        sql = "\n".join(migration.sql for migration in discover_migrations())
        tables = set(re.findall(r"CREATE TABLE\s+([a-z_]+)", sql, re.IGNORECASE))
        tables.add("retaniq_schema_migrations")
        self.assertEqual(set(RLS_TABLE_OWNERSHIP), tables)
        self.assertEqual(len(DATABASE_ROLE_PLAN), 7)
        self.assertEqual(RLS_TABLE_OWNERSHIP["dataset_identity"], "singleton_global_synthetic_provenance")
        self.assertEqual(RLS_TABLE_OWNERSHIP["synthetic_import_checkpoints"], "dataset_id_global_operational_state")
        self.assertEqual(RLS_TABLE_OWNERSHIP["retaniq_schema_migrations"], "migration_schema_metadata")


if __name__ == "__main__":
    unittest.main()
