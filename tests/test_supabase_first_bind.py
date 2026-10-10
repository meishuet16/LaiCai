from __future__ import annotations

import unittest
from contextlib import AbstractContextManager
from unittest.mock import patch

from retaniq.database_config import DatabaseConfig
from retaniq.supabase_first_bind import (
    APP_TABLES,
    EXPECTED_MIGRATION_VERSIONS,
    LOCKED_TABLES,
    PROJECT_REF,
    RLS_TABLES,
    TENANT_ID,
    TENANT_TABLES,
    FirstBindBlocked,
    _check_privileged_inspector,
    _classify_destination,
    _insert_dataset_identity,
    _privilege_contract,
    _restricted_dsn,
    _validate_tenant_scope,
)
from retaniq.synthetic.canonical_adapter import _verify_import_schema
from retaniq.supabase_import import _runtime_configs


_IDENTITY = {
    "dataset_id": "synthetic-saas-v1-2-standard-s2026-970a9d231e68",
    "dataset_version": "1.2.0",
    "dataset_type": "synthetic_saas",
    "target_policy_version": "effective-account-churn-v1.2",
    "generator_version": "synthetic-saas-v1.2",
    "manifest_sha256": "a" * 64,
}


def _empty_counts() -> dict[str, int]:
    return {name: 0 for name in APP_TABLES}


def _empty_tenant_counts() -> dict[str, dict[str, int]]:
    return {name: {} for name in TENANT_TABLES}


def _scope_counts() -> dict[str, int]:
    return {name: 100 for name in TENANT_TABLES} | {
        "feature_snapshots": 0, "churn_labels": 0, "predictions": 0,
    }


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _RoleConnection:
    def execute(self, statement, parameters=()):
        self.statement = statement
        return _Result({
            "database": "postgres", "role": "postgres", "rolsuper": False,
            "rolcreaterole": True, "rolbypassrls": False,
        })


class _FailingInsertConnection:
    def __init__(self):
        self.rolled_back = False
        self.active = False

    class _Transaction(AbstractContextManager):
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            self.connection.active = True
            return self.connection

        def __exit__(self, exc_type, exc, traceback):
            self.connection.active = False
            self.connection.rolled_back = exc_type is not None
            return False

    def transaction(self):
        return self._Transaction(self)

    def execute(self, statement, parameters=()):
        if not self.active:
            raise AssertionError("identity insert escaped its transaction")
        raise RuntimeError("injected insert failure")


class SupabaseFirstBindTests(unittest.TestCase):
    def classify(self, *, identity=None, table_counts=None, tenant_counts=None, checkpoints=None):
        return _classify_destination(
            identity=identity,
            table_counts=table_counts or _empty_counts(),
            tenant_counts=tenant_counts or _empty_tenant_counts(),
            checkpoints=checkpoints or [],
            expected_identity=_IDENTITY,
            scope_counts=_scope_counts(),
        )

    def test_genuinely_empty_destination_is_bindable(self):
        self.assertEqual(self.classify(), "EMPTY_DESTINATION")

    def test_rls_hidden_rows_fail_closed_without_bypassrls_inspector(self):
        with self.assertRaisesRegex(FirstBindBlocked, "inspection_or_role_capability"):
            _check_privileged_inspector(_RoleConnection())

    def test_unbound_destination_with_any_tenant_or_checkpoint_rows_is_rejected(self):
        counts = _empty_counts()
        counts["customers"] = 1
        with self.assertRaisesRegex(FirstBindBlocked, "unbound_destination_contains_data"):
            self.classify(table_counts=counts)

        counts = _empty_counts()
        counts["synthetic_import_checkpoints"] = 1
        checkpoint = [{
            "dataset_id": _IDENTITY["dataset_id"], "stream_name": "canonical-events-tenant-01",
            "last_row_number": 1, "accepted_count": 1, "duplicate_count": 0, "rejected_count": 0,
        }]
        with self.assertRaisesRegex(FirstBindBlocked, "unbound_destination_contains_data"):
            self.classify(table_counts=counts, checkpoints=checkpoint)

    def test_matching_partial_tenant01_checkpoint_is_resumable(self):
        counts = _empty_counts()
        counts.update({"dataset_identity": 1, "synthetic_import_checkpoints": 1,
                       "tenants": 1, "customers": 1, "canonical_events": 3})
        tenants = _empty_tenant_counts()
        tenants.update({"tenants": {TENANT_ID: 1}, "customers": {TENANT_ID: 1},
                        "canonical_events": {TENANT_ID: 3}})
        checkpoint = [{
            "dataset_id": _IDENTITY["dataset_id"], "stream_name": "canonical-events-tenant-01",
            "last_row_number": 3, "accepted_count": 3, "duplicate_count": 0, "rejected_count": 0,
        }]
        self.assertEqual(
            self.classify(identity=_IDENTITY, table_counts=counts, tenant_counts=tenants, checkpoints=checkpoint),
            "MATCHING_TENANT01_RESUME",
        )

    def test_wrong_identity_is_rejected(self):
        wrong = {**_IDENTITY, "manifest_sha256": "b" * 64}
        counts = _empty_counts()
        counts["dataset_identity"] = 1
        with self.assertRaisesRegex(FirstBindBlocked, "dataset_identity_mismatch"):
            self.classify(identity=wrong, table_counts=counts)

    def test_cross_tenant_rows_are_rejected_even_when_identity_matches(self):
        counts = _empty_counts()
        counts["dataset_identity"] = 1
        counts["customers"] = 1
        tenants = _empty_tenant_counts()
        tenants["customers"] = {"tenant-02": 1}
        with self.assertRaisesRegex(FirstBindBlocked, "cross_tenant_rows_present"):
            self.classify(identity=_IDENTITY, table_counts=counts, tenant_counts=tenants)

    def test_invalid_stream_and_inconsistent_checkpoint_are_rejected(self):
        counts = _empty_counts()
        counts["dataset_identity"] = 1
        counts["synthetic_import_checkpoints"] = 1
        wrong_stream = [{
            "dataset_id": _IDENTITY["dataset_id"], "stream_name": "canonical-events",
            "last_row_number": 1, "accepted_count": 1, "duplicate_count": 0, "rejected_count": 0,
        }]
        with self.assertRaisesRegex(FirstBindBlocked, "unexpected_import_checkpoint"):
            self.classify(identity=_IDENTITY, table_counts=counts, checkpoints=wrong_stream)

        bad_counters = [{
            "dataset_id": _IDENTITY["dataset_id"], "stream_name": "canonical-events-tenant-01",
            "last_row_number": 4, "accepted_count": 2, "duplicate_count": 0, "rejected_count": 0,
        }]
        with self.assertRaisesRegex(FirstBindBlocked, "import_checkpoint_counters_inconsistent"):
            self.classify(identity=_IDENTITY, table_counts=counts, checkpoints=bad_counters)

    def test_scope_rejects_tenant_other_than_tenant01(self):
        with self.assertRaisesRegex(FirstBindBlocked, "tenant_scope_must_be_tenant_01"):
            _validate_tenant_scope("tenant-02")

    def test_backend_and_maintenance_permissions_are_separate(self):
        backend_allowed, backend_denied = _privilege_contract("retaniq_backend")
        maintenance_allowed, maintenance_denied = _privilege_contract("retaniq_maintenance")
        self.assertIn(("customers", "INSERT"), backend_allowed)
        self.assertIn(("dataset_identity", "SELECT"), backend_denied)
        self.assertIn(("synthetic_import_checkpoints", "UPDATE"), maintenance_allowed)
        self.assertIn(("retaniq_schema_migrations", "SELECT"), maintenance_denied)
        self.assertNotIn(("retaniq_schema_migrations", "SELECT"), maintenance_allowed)

    def test_lock_set_covers_every_app_table_in_stable_order(self):
        self.assertEqual(LOCKED_TABLES, tuple(sorted(APP_TABLES)))
        self.assertEqual(len(LOCKED_TABLES), 19)
        self.assertEqual(len(RLS_TABLES), 18)
        self.assertEqual(len(TENANT_TABLES), 16)
        self.assertTrue({"dataset_identity", "synthetic_import_checkpoints", "retaniq_schema_migrations"}.issubset(LOCKED_TABLES))

    def test_first_bind_insert_failure_is_rolled_back_by_transaction_boundary(self):
        connection = _FailingInsertConnection()
        with self.assertRaisesRegex(RuntimeError, "injected insert failure"):
            with connection.transaction():
                _insert_dataset_identity(connection, _IDENTITY)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.active)

    def test_migration_version_inventory_is_seven_ordered_versions(self):
        self.assertEqual(EXPECTED_MIGRATION_VERSIONS, tuple(f"{i:03d}" for i in range(1, 8)))

    def test_supabase_import_does_not_read_migration_metadata_as_backend(self):
        config = DatabaseConfig.for_supabase_migration_target(
            f"postgresql://postgres.{PROJECT_REF}:pw@aws-0-ap-northeast-2.pooler.supabase.com:"
            "5432/postgres?sslmode=require",
            project_ref=PROJECT_REF,
            project_url=f"https://{PROJECT_REF}.supabase.co",
        )
        with patch("retaniq.synthetic.canonical_adapter.verify_postgresql_schema") as verify:
            _verify_import_schema(config)
        verify.assert_not_called()

    def test_local_postgresql_import_keeps_checksum_verification(self):
        config = DatabaseConfig.from_value(
            "postgresql://test:test@127.0.0.1:5432/retaniq_test",
            allow_insecure_local_postgresql=True,
        )
        with patch("retaniq.synthetic.canonical_adapter.verify_postgresql_schema") as verify:
            _verify_import_schema(config)
        verify.assert_called_once_with(config)

    def test_restricted_dsns_use_pooler_role_identity_and_escape_password(self):
        admin_dsn = (
            f"postgresql://postgres.{PROJECT_REF}:migration@aws-0-ap-northeast-2.pooler.supabase.com:"
            "5432/postgres?sslmode=require"
        )
        dsn = _restricted_dsn(admin_dsn, "retainiq_backend_login", "p@ss/word:with?chars")
        self.assertIn(f"retainiq_backend_login.{PROJECT_REF}", dsn)
        self.assertIn("p%40ss%2Fword%3Awith%3Fchars", dsn)
        self.assertIn("sslmode=require", dsn)
        self.assertNotIn("migration@", dsn)

    def test_import_wrapper_uses_only_distinct_restricted_runtime_dsns(self):
        from retaniq.supabase_first_bind import (
            APP_LOGIN, LOGIN_CAPABILITIES, MAINTENANCE_LOGIN, PROJECT_URL,
        )
        from retaniq.supabase_import import _runtime_configs

        admin_dsn = (
            f"postgresql://postgres.{PROJECT_REF}:not-stored@aws-0-ap-northeast-2.pooler.supabase.com:"
            "5432/postgres?sslmode=require"
        )
        payload = {
            "project_ref": PROJECT_REF,
            "project_url": PROJECT_URL,
            "connection_mode": "SESSION_POOLER",
            "logins": {
                login: {
                    "database_role": login,
                    "capability": capability,
                    "dsn": _restricted_dsn(admin_dsn, login, f"secret-{login}"),
                }
                for login, capability in LOGIN_CAPABILITIES.items()
            },
        }
        serialized = __import__("json").dumps(payload)
        with patch("retaniq.supabase_import.credential_store_path"):
            with patch("retaniq.supabase_import.load_dpapi_secret", return_value=serialized):
                app, maintenance = _runtime_configs()
        self.assertTrue(app.is_supabase)
        self.assertEqual(app.connection_mode, "SESSION_POOLER")
        self.assertIsNone(app.migration_dsn)
        self.assertEqual(app.target, payload["logins"][APP_LOGIN]["dsn"])
        self.assertEqual(maintenance.target, payload["logins"][MAINTENANCE_LOGIN]["dsn"])
        self.assertNotEqual(app.target, maintenance.target)
        self.assertNotIn("not-stored", app.target + maintenance.target)


if __name__ == "__main__":
    unittest.main()
