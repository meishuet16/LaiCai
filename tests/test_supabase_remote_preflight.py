import unittest
from unittest.mock import patch

from retaniq.supabase_remote_preflight import (
    CAPABILITY_ROLES,
    DEFAULT_HOST,
    DEFAULT_USER,
    PROJECT_REF,
    _connect_restricted_smoke_login,
    _deployment_gate,
    _safe_config,
    _status_exit_code,
)


def eligible_report():
    return {
        "destination": {
            "database": "postgres",
            "database_role": "postgres",
            "rolsuper": False,
            "rolcreaterole": True,
            "rolbypassrls": True,
        },
        "public_schema": {"can_create": True, "can_manage_acl": True},
        "database_owner": {"current_role_owns_database": True},
        "migration_history": {"state": "NOT_INITIALIZED"},
        "application_tables": [],
        "roles": [],
    }


class SupabaseRemotePreflightTests(unittest.TestCase):
    def test_restricted_smoke_connections_autocommit_outside_explicit_transactions(self):
        with patch("psycopg.connect") as connect:
            _connect_restricted_smoke_login("probe_backend", "local-test-only")
        self.assertTrue(connect.call_args.kwargs["autocommit"])
        self.assertEqual(connect.call_args.kwargs["prepare_threshold"], None)

    def test_password_is_encoded_in_memory_and_redacted_from_config(self):
        config = _safe_config(DEFAULT_HOST, DEFAULT_USER, "test @:/? secret")
        self.assertIn("test%20%40%3A%2F%3F%20secret", config.postgresql_dsn)
        self.assertNotIn("secret", config.redacted_target)
        self.assertEqual(config.expected_project_ref, PROJECT_REF)

    def test_deployment_gate_requires_clean_expected_admin_target(self):
        self.assertTrue(_deployment_gate(eligible_report()))
        for key, value in (
            ("rolsuper", True),
            ("rolcreaterole", False),
            ("rolbypassrls", False),
        ):
            report = eligible_report()
            report["destination"][key] = value
            self.assertFalse(_deployment_gate(report), key)

    def test_deployment_gate_rejects_conflicts_and_invalid_capability_roles(self):
        report = eligible_report()
        report["application_tables"] = [{"table_name": "customers"}]
        self.assertFalse(_deployment_gate(report))

        report = eligible_report()
        report["roles"] = [{
            "rolname": CAPABILITY_ROLES[0], "rolcanlogin": True, "rolsuper": False,
            "rolbypassrls": False, "rolinherit": False,
        }]
        self.assertFalse(_deployment_gate(report))

    def test_successful_deployment_status_is_treated_as_success(self):
        self.assertEqual(_status_exit_code("CATALOG_PREFLIGHT_READ_ONLY"), 0)
        self.assertEqual(_status_exit_code("MIGRATIONS_AND_RESTRICTED_SMOKE_PASS"), 0)
        self.assertEqual(_status_exit_code("DEPLOYED_BUT_SECURITY_GATES_INCOMPLETE"), 5)


if __name__ == "__main__":
    unittest.main()
