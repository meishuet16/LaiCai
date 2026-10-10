import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from retaniq.database import DatabaseConnection, DatabaseConnectionError
from retaniq.database_config import (
    SUPABASE_APP_DSN_ENV,
    SUPABASE_BACKEND,
    SUPABASE_CONNECTION_MODE_ENV,
    SUPABASE_EXPECTED_PROJECT_REF_ENV,
    SUPABASE_MIGRATION_DSN_ENV,
    SUPABASE_MAINTENANCE_DSN_ENV,
    SUPABASE_PROJECT_URL_ENV,
    DatabaseConfig,
    DatabaseConfigurationError,
)
from retaniq.postgresql_migrations import PostgreSQLMigrationError, run_postgresql_migrations


PROJECT_REF = "abcde12345fghij67890"
PROJECT_URL = f"https://{PROJECT_REF}.supabase.co"
DIRECT_APP_DSN = (
    f"postgresql://retainiq_app:app-secret@db.{PROJECT_REF}.supabase.co:5432/postgres?sslmode=require"
)
DIRECT_MIGRATION_DSN = (
    f"postgresql://postgres:migration-secret@db.{PROJECT_REF}.supabase.co:5432/postgres?sslmode=require"
)
SESSION_APP_DSN = (
    f"postgresql://retainiq_app.{PROJECT_REF}:app-secret@fixture.pooler.supabase.com:5432/postgres?sslmode=require"
)
SESSION_MIGRATION_DSN = (
    f"postgresql://postgres.{PROJECT_REF}:migration-secret@fixture.pooler.supabase.com:5432/postgres?sslmode=require"
)
SESSION_MAINTENANCE_DSN = (
    f"postgresql://retaniq_maintenance.{PROJECT_REF}:maintenance-secret@fixture.pooler.supabase.com:5432/postgres?sslmode=require"
)
TRANSACTION_APP_DSN = (
    f"postgresql://retainiq_app.{PROJECT_REF}:app-secret@fixture.pooler.supabase.com:6543/postgres?sslmode=require"
)


def environment(*, mode="DIRECT", app_dsn=DIRECT_APP_DSN, migration_dsn=DIRECT_MIGRATION_DSN):
    return {
        "RETAINIQ_DATABASE_BACKEND": SUPABASE_BACKEND,
        SUPABASE_PROJECT_URL_ENV: PROJECT_URL,
        SUPABASE_EXPECTED_PROJECT_REF_ENV: PROJECT_REF,
        SUPABASE_MIGRATION_DSN_ENV: migration_dsn,
        SUPABASE_APP_DSN_ENV: app_dsn,
        SUPABASE_CONNECTION_MODE_ENV: mode,
    }


class SupabaseConfigurationTests(unittest.TestCase):
    def test_explicit_supabase_environment_selects_postgresql_without_fallback(self):
        config = DatabaseConfig.from_environment(environment())
        self.assertTrue(config.is_postgresql)
        self.assertTrue(config.is_supabase)
        self.assertEqual(config.expected_project_ref, PROJECT_REF)
        self.assertEqual(config.connection_mode, "DIRECT")
        self.assertEqual(config.deployment_environment, "supabase_demo")

    def test_all_supported_modes_are_classified_from_dashboard_connection_shapes(self):
        cases = (
            ("DIRECT", DIRECT_APP_DSN),
            ("SESSION_POOLER", SESSION_APP_DSN),
            ("TRANSACTION_POOLER", TRANSACTION_APP_DSN),
        )
        for mode, dsn in cases:
            with self.subTest(mode=mode):
                config = DatabaseConfig.from_environment(environment(mode=mode, app_dsn=dsn))
                self.assertEqual(config.connection_mode, mode)

    def test_missing_supabase_fields_fail_closed_and_do_not_fall_back(self):
        for env in (
            {"RETAINIQ_DATABASE_BACKEND": SUPABASE_BACKEND},
            {**environment(), SUPABASE_APP_DSN_ENV: ""},
            {**environment(), "RETAINIQ_DATABASE_URL": "sqlite:///fallback.sqlite3"},
        ):
            with self.subTest(keys=tuple(env)):
                with self.assertRaises(DatabaseConfigurationError):
                    DatabaseConfig.from_environment(env)

    def test_runtime_configuration_does_not_require_migration_credentials(self):
        runtime_env = environment()
        runtime_env.pop(SUPABASE_MIGRATION_DSN_ENV)
        config = DatabaseConfig.from_environment(runtime_env)
        self.assertTrue(config.is_supabase)
        self.assertIsNone(config.migration_dsn)
        with self.assertRaises(DatabaseConfigurationError):
            config.for_migrations()

    def test_project_url_and_expected_project_ref_must_match(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment({**environment(), SUPABASE_EXPECTED_PROJECT_REF_ENV: "otherref123456789012"})
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment({**environment(), SUPABASE_PROJECT_URL_ENV: "http://example.invalid"})

    def test_app_and_migration_dsns_must_belong_to_expected_project_and_role_separation(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment({
                **environment(),
                SUPABASE_APP_DSN_ENV: "postgresql://postgres:pw@db.otherref123456789012.supabase.co/postgres?sslmode=require",
            })
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment(environment(migration_dsn=DIRECT_APP_DSN))

    def test_insecure_tls_and_malformed_supabase_dsns_are_rejected(self):
        invalid = (
            DIRECT_APP_DSN.replace("sslmode=require", "sslmode=disable"),
            DIRECT_APP_DSN.replace("sslmode=require", "sslmode=prefer"),
            DIRECT_APP_DSN.replace("postgresql://", "postgres://"),
            "postgresql://postgres:pw@db.example.invalid/postgres?sslmode=require",
            DIRECT_APP_DSN.replace("app-secret@", "@"),
        )
        for dsn in invalid:
            with self.subTest(dsn=dsn.split("@")[1] if "@" in dsn else dsn):
                with self.assertRaises(DatabaseConfigurationError):
                    DatabaseConfig.from_environment(environment(app_dsn=dsn))

    def test_tls_verification_level_is_not_overstated(self):
        encrypted_only = DatabaseConfig.from_environment(environment())
        self.assertEqual(encrypted_only.tls_verification, "encrypted_only_server_identity_unverified")
        verified = DIRECT_APP_DSN.replace("sslmode=require", "sslmode=verify-full&sslrootcert=%2Ftmp%2Fca.pem")
        full = DatabaseConfig.from_environment(environment(app_dsn=verified))
        self.assertEqual(full.tls_verification, "ca_and_hostname_verified")
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment(environment(app_dsn=DIRECT_APP_DSN.replace("sslmode=require", "sslmode=verify-full")))

    def test_secrets_are_absent_from_repr_and_safe_target(self):
        config = DatabaseConfig.from_environment(environment())
        rendered = repr(config) + config.redacted_target
        for secret in ("app-secret", "migration-secret"):
            self.assertNotIn(secret, rendered)
        self.assertIn("***", rendered)

    def test_migration_configuration_is_separate_and_preserves_direct_mode(self):
        migration = DatabaseConfig.from_environment(environment(mode="SESSION_POOLER", app_dsn=SESSION_APP_DSN)).for_migrations()
        self.assertEqual(migration.connection_mode, "DIRECT")
        self.assertEqual(migration.target, DIRECT_MIGRATION_DSN)
        self.assertTrue(migration.is_supabase)

    def test_maintenance_configuration_is_separate_session_capable_and_secret_safe(self):
        config = DatabaseConfig.from_environment({
            **environment(mode="SESSION_POOLER", app_dsn=SESSION_APP_DSN),
            SUPABASE_MAINTENANCE_DSN_ENV: SESSION_MAINTENANCE_DSN,
        })
        maintenance = config.for_maintenance()
        self.assertEqual(maintenance.connection_mode, "SESSION_POOLER")
        self.assertTrue(maintenance.is_supabase)
        self.assertNotIn("maintenance-secret", repr(config) + config.redacted_target)
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment({
                **environment(mode="SESSION_POOLER", app_dsn=SESSION_APP_DSN),
                SUPABASE_MAINTENANCE_DSN_ENV: SESSION_APP_DSN,
            })

    def test_session_pooler_is_accepted_as_a_session_locked_migration_target(self):
        config = DatabaseConfig.from_environment(
            environment(mode="SESSION_POOLER", app_dsn=SESSION_APP_DSN, migration_dsn=SESSION_MIGRATION_DSN),
        )
        migration = config.for_migrations()
        self.assertEqual(migration.connection_mode, "SESSION_POOLER")
        self.assertEqual(migration.target, SESSION_MIGRATION_DSN)

    def test_migration_only_target_is_project_validated_without_runtime_dsn(self):
        config = DatabaseConfig.for_supabase_migration_target(
            SESSION_MIGRATION_DSN,
            project_ref=PROJECT_REF,
            project_url=PROJECT_URL,
        )
        self.assertTrue(config.is_supabase)
        self.assertEqual(config.connection_mode, "SESSION_POOLER")
        self.assertEqual(config.target, SESSION_MIGRATION_DSN)
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.for_supabase_migration_target(
                TRANSACTION_APP_DSN,
                project_ref=PROJECT_REF,
                project_url=PROJECT_URL,
            )

    def test_transaction_pooler_is_rejected_by_session_locked_migrations(self):
        config = DatabaseConfig.from_environment(environment(mode="TRANSACTION_POOLER", app_dsn=TRANSACTION_APP_DSN))
        with self.assertRaisesRegex(PostgreSQLMigrationError, "session-level migration advisory lock"):
            run_postgresql_migrations(config)

    def test_migration_runner_selects_separate_direct_credentials(self):
        config = DatabaseConfig.from_environment(environment(mode="SESSION_POOLER", app_dsn=SESSION_APP_DSN))
        with patch("retaniq.postgresql_migrations.DatabaseConnection.open", side_effect=DatabaseConnectionError("safe")) as opened:
            with self.assertRaises(PostgreSQLMigrationError):
                run_postgresql_migrations(config)
        selected = opened.call_args.args[0]
        self.assertEqual(selected.target, DIRECT_MIGRATION_DSN)
        self.assertEqual(selected.connection_mode, "DIRECT")

    def test_migration_runner_selects_separate_session_pooler_credentials(self):
        config = DatabaseConfig.from_environment(
            environment(mode="SESSION_POOLER", app_dsn=SESSION_APP_DSN, migration_dsn=SESSION_MIGRATION_DSN),
        )
        with patch("retaniq.postgresql_migrations.DatabaseConnection.open", side_effect=DatabaseConnectionError("safe")) as opened:
            with self.assertRaises(PostgreSQLMigrationError):
                run_postgresql_migrations(config)
        selected = opened.call_args.args[0]
        self.assertEqual(selected.target, SESSION_MIGRATION_DSN)
        self.assertEqual(selected.connection_mode, "SESSION_POOLER")

    def test_transaction_pooler_disables_psycopg_prepared_statements(self):
        fake_psycopg = types.ModuleType("psycopg")
        fake_rows = types.ModuleType("psycopg.rows")
        fake_rows.dict_row = object()
        fake_connection = MagicMock()
        fake_psycopg.connect = MagicMock(return_value=fake_connection)
        config = DatabaseConfig.from_environment(environment(mode="TRANSACTION_POOLER", app_dsn=TRANSACTION_APP_DSN))
        with patch.dict(sys.modules, {"psycopg": fake_psycopg, "psycopg.rows": fake_rows}):
            connection = DatabaseConnection.open(config)
        kwargs = fake_psycopg.connect.call_args.kwargs
        self.assertIsNone(kwargs["prepare_threshold"])
        connection.close()


if __name__ == "__main__":
    unittest.main()
