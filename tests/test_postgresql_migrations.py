import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from retaniq.database import DatabaseConnection, DatabaseDriverUnavailable, DatabaseError, connect_database
from retaniq.database_config import DatabaseConfig, DatabaseConfigurationError
from retaniq.postgresql_migrations import (
    MigrationChecksumError,
    MigrationDirectoryError,
    MigrationHistoryError,
    PostgreSQLMigrationExecutionError,
    PostgreSQLMigrationError,
    _safe_migration_diagnostic,
    _sql_operation,
    discover_migrations,
    plan_migrations,
    run_postgresql_migrations,
    split_sql_statements,
)


class PostgreSQLMigrationUnitTests(unittest.TestCase):
    def test_default_migrations_are_ordered_and_have_stable_checksums(self):
        migrations = discover_migrations()
        self.assertEqual(
            [migration.version for migration in migrations],
            ["001", "002", "003", "004", "005", "006", "007"],
        )
        self.assertTrue(all(len(migration.checksum) == 64 for migration in migrations))
        self.assertEqual(migrations, discover_migrations())

    def test_authenticator_owner_transfer_privileges_are_temporary_and_ordered(self):
        migration = next(item for item in discover_migrations() if item.version == "005")
        sql = migration.sql
        grant_membership = sql.index(
            "GRANT retaniq_authenticator TO CURRENT_USER\n    WITH SET TRUE, INHERIT FALSE"
        )
        grant_schema_create = sql.index("GRANT CREATE ON SCHEMA %I TO retaniq_authenticator")
        grant_function_access = sql.index("GRANT EXECUTE ON FUNCTION retaniq_authenticate_integration")
        first_owner_transfer = sql.index("ALTER FUNCTION retaniq_authenticate_integration(TEXT) OWNER")
        revoke_schema_create = sql.index("REVOKE CREATE ON SCHEMA %I FROM retaniq_authenticator")
        revoke_membership = sql.index("REVOKE retaniq_authenticator FROM CURRENT_USER")
        self.assertNotIn("WITH ADMIN TRUE", sql)
        self.assertLess(grant_membership, first_owner_transfer)
        self.assertLess(grant_schema_create, first_owner_transfer)
        self.assertLess(grant_function_access, first_owner_transfer)
        self.assertLess(first_owner_transfer, revoke_schema_create)
        self.assertLess(revoke_schema_create, revoke_membership)

    def test_duplicate_migration_versions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (root / "001_second.sql").write_text("SELECT 2;", encoding="utf-8")
            with self.assertRaises(MigrationDirectoryError):
                discover_migrations(root)

    def test_invalid_and_noncontiguous_migration_versions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "1_bad.sql").write_text("SELECT 1;", encoding="utf-8")
            with self.assertRaises(MigrationDirectoryError):
                discover_migrations(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (root / "003_third.sql").write_text("SELECT 3;", encoding="utf-8")
            with self.assertRaises(MigrationDirectoryError):
                discover_migrations(root)

    def test_missing_migration_directory_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MigrationDirectoryError):
                discover_migrations(Path(directory) / "missing")

    def test_fresh_and_repeated_initialization_plans_are_correct(self):
        migrations = discover_migrations()
        self.assertEqual(plan_migrations(migrations, {}), migrations)
        history = {migration.version: migration.checksum for migration in migrations}
        self.assertEqual(plan_migrations(migrations, history), ())

    def test_modified_or_missing_applied_migration_is_rejected(self):
        migrations = discover_migrations()
        altered = dict.fromkeys([migrations[0].version], "0" * 64)
        with self.assertRaises(MigrationChecksumError):
            plan_migrations(migrations, altered)
        with self.assertRaises(MigrationHistoryError):
            plan_migrations(migrations, {"999": "0" * 64})

    def test_migration_history_must_be_a_contiguous_prefix(self):
        migrations = discover_migrations()
        history = {migrations[1].version: migrations[1].checksum}
        with self.assertRaises(MigrationHistoryError):
            plan_migrations(migrations, history)

    def test_sql_splitter_respects_quoted_semicolons_comments_and_dollar_blocks(self):
        sql = "SELECT ';'; -- comment ;\nSELECT $$a;b$$; /* c; */ SELECT 3"
        self.assertEqual(
            split_sql_statements(sql),
            ("SELECT ';'", "-- comment ;\nSELECT $$a;b$$", "/* c; */ SELECT 3"),
        )
        with self.assertRaises(MigrationDirectoryError):
            split_sql_statements("SELECT 'unterminated")

    def test_migration_failure_diagnostics_keep_sqlstate_and_redact_credentials(self):
        class Diagnostic:
            message_primary = "permission denied (password=never-print-this)"

        class DriverError(Exception):
            sqlstate = "42501"
            diag = Diagnostic()

        sqlstate, message = _safe_migration_diagnostic(DriverError())
        self.assertEqual(sqlstate, "42501")
        self.assertEqual(message, "permission denied (password=[REDACTED])")
        self.assertEqual(_sql_operation("-- leading comment\nALTER FUNCTION f() OWNER TO r"), "ALTER FUNCTION")
        error = PostgreSQLMigrationExecutionError("005", 4, "ALTER FUNCTION", sqlstate, message)
        self.assertEqual((error.version, error.statement_index, error.operation), ("005", 4, "ALTER FUNCTION"))
        self.assertNotIn("never-print-this", str(error))

    def test_postgresql_migrations_reject_sqlite_targets_before_connecting(self):
        with self.assertRaises(DatabaseConfigurationError):
            run_postgresql_migrations(":memory:")

    def test_data_foundation_requires_an_explicit_postgresql_migration_request(self):
        from retaniq.data_foundation import initialize_database
        from retaniq.database import PostgreSQLSchemaNotReady

        config = DatabaseConfig.from_value(
            "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
        )
        with self.assertRaises(PostgreSQLSchemaNotReady):
            initialize_database(config)

    def test_explicit_initialization_routes_to_postgresql_runner(self):
        from unittest.mock import patch

        from retaniq.data_foundation import initialize_database

        config = DatabaseConfig.from_value(
            "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
        )
        with patch("retaniq.postgresql_migrations.run_postgresql_migrations") as runner:
            initialize_database(config, migrate_postgresql=True)
        runner.assert_called_once_with(config)

    def test_init_db_cli_opt_in_is_local_only_and_redacts_the_target(self):
        from unittest.mock import patch

        from retaniq.__main__ import main

        output = StringIO()
        dsn = "postgresql://alice:secret@localhost:5432/retaniq?sslmode=disable"
        with patch.dict(os.environ, {"RETAINIQ_DATABASE_URL": dsn}):
            with patch("retaniq.postgresql_migrations.run_postgresql_migrations") as runner:
                with redirect_stdout(output):
                    result = main(["init-db", "--allow-insecure-local-postgresql"])
        self.assertEqual(result, 0)
        runner.assert_called_once()
        self.assertIn("***", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    def test_init_db_cli_redacts_an_explicit_dsn(self):
        from unittest.mock import patch

        from retaniq.__main__ import main

        output = StringIO()
        dsn = "postgresql://alice:secret@localhost:5432/retaniq?sslmode=disable"
        with patch("retaniq.postgresql_migrations.run_postgresql_migrations") as runner:
            with redirect_stdout(output):
                result = main([
                    "init-db", "--db", dsn, "--allow-insecure-local-postgresql",
                ])
        self.assertEqual(result, 0)
        runner.assert_called_once()
        self.assertIn("***", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    def test_database_connection_error_is_redacted_by_migration_runner(self):
        target = "postgresql://alice:do-not-leak@db.example.test/retaniq?sslmode=verify-full"
        config = DatabaseConfig.from_value(target)
        from unittest.mock import patch

        with patch.object(DatabaseConnection, "open", side_effect=RuntimeError(target)):
            with self.assertRaises(PostgreSQLMigrationError) as raised:
                run_postgresql_migrations(config)
        self.assertNotIn("do-not-leak", str(raised.exception))
        self.assertNotIn("alice", str(raised.exception))

    def test_missing_driver_error_remains_actionable(self):
        config = DatabaseConfig.from_value(
            "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
        )
        from unittest.mock import patch

        with patch.object(DatabaseConnection, "open", side_effect=DatabaseDriverUnavailable(
            "PostgreSQL driver is not installed; install requirements-postgresql.txt",
        )):
            with self.assertRaises(PostgreSQLMigrationError) as raised:
                run_postgresql_migrations(config)
        self.assertIn("requirements-postgresql.txt", str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))


def _disposable_test_config() -> tuple[DatabaseConfig, str] | None:
    dsn = os.environ.get("RETAINIQ_POSTGRES_TEST_DSN")
    if not dsn:
        return None
    if os.environ.get("RETAINIQ_POSTGRES_TEST_DISPOSABLE") != "1":
        return None
    try:
        config = DatabaseConfig.from_value(dsn, allow_insecure_local_postgresql=True)
        parsed = urlsplit(config.postgresql_dsn)
        database_name = unquote(parsed.path.lstrip("/"))
    except (DatabaseConfigurationError, ValueError):
        return None
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return None
    if not database_name.startswith("retaniq_test_"):
        return None
    return config, database_name


_TEST_TARGET = _disposable_test_config()


@unittest.skipUnless(
    _TEST_TARGET,
    "requires RETAINIQ_POSTGRES_TEST_DSN, disposable marker, loopback host, and retaniq_test_ database name",
)
class PostgreSQLMigrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _database_name = _TEST_TARGET
        from postgresql_security_support import bootstrap_test_roles
        bootstrap_test_roles(cls.config)
        cls.schema = f"retaniq_06c_{uuid4().hex[:12]}"
        cls.result = run_postgresql_migrations(cls.config, schema=cls.schema)

    @classmethod
    def tearDownClass(cls):
        connection = connect_database(cls.config)
        try:
            connection.raw_connection.autocommit = True
            connection.execute(f'DROP SCHEMA IF EXISTS "{cls.schema}" CASCADE')
        finally:
            connection.close()

    def _connect(self):
        connection = connect_database(self.config)
        connection.raw_connection.autocommit = True
        connection.execute(f'SET search_path TO "{self.schema}"')
        return connection

    def test_fresh_schema_tables_columns_types_constraints_and_indexes(self):
        self.assertEqual(self.result.applied_versions, ("001", "002", "003", "004", "005", "006", "007"))
        self.assertEqual(self.result.current_version, "007")
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = %s",
                (self.schema,),
            ).fetchall()
            tables = {row["tablename"] for row in rows}
            self.assertEqual(tables, {
                "tenants", "integrations", "customers", "customer_identities", "canonical_events",
                "usage_events", "billing_events", "subscriptions", "subscription_events",
                "feature_snapshots", "churn_labels", "predictions", "service_principals",
                "subscription_owners", "integration_event_categories", "dataset_identity",
                "observation_coverage", "synthetic_import_checkpoints", "retaniq_schema_migrations",
            })

            column_rows = connection.execute(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns WHERE table_schema = %s",
                (self.schema,),
            ).fetchall()
            columns = {(row["table_name"], row["column_name"]): row for row in column_rows}
            expected_columns = {
                "tenants": {"tenant_id": "text"},
                "integrations": {
                    "integration_id": "text", "tenant_id": "text", "source": "text", "token_digest": "text",
                    "authorized_purposes_json": "text", "schema_version": "text", "mapping_version": "text",
                    "created_at": "timestamp with time zone", "last_successful_ingestion_at": "timestamp with time zone",
                    "last_failure_at": "timestamp with time zone", "last_failure_code": "text",
                },
                "customers": {
                    "tenant_id": "text", "customer_id": "text", "account_status": "text",
                    "created_at": "timestamp with time zone",
                },
                "customer_identities": {
                    "tenant_id": "text", "source": "text", "external_customer_id": "text",
                    "customer_id": "text", "created_at": "timestamp with time zone",
                },
                "canonical_events": {
                    "event_id": "bigint", "tenant_id": "text", "source": "text", "source_event_id": "text",
                    "customer_id": "text", "category": "text", "event_type": "text",
                    "occurred_at": "timestamp with time zone", "received_at": "timestamp with time zone",
                    "source_available_at": "timestamp with time zone", "schema_version": "text",
                    "mapping_version": "text", "normalized_payload_sha256": "text",
                },
                "usage_events": {
                    "tenant_id": "text", "event_id": "bigint", "customer_id": "text", "event_type": "text",
                    "feature": "text", "quantity": "bigint", "unit": "text",
                    "occurred_at": "timestamp with time zone", "received_at": "timestamp with time zone",
                    "source_available_at": "timestamp with time zone",
                },
                "billing_events": {
                    "tenant_id": "text", "event_id": "bigint", "customer_id": "text", "subscription_id": "text",
                    "event_type": "text", "payment_status": "text", "amount_minor": "bigint", "currency": "text",
                    "occurred_at": "timestamp with time zone", "received_at": "timestamp with time zone",
                    "source_available_at": "timestamp with time zone",
                },
                "subscriptions": {
                    "tenant_id": "text", "subscription_id": "text", "customer_id": "text", "plan_id": "text",
                    "status": "text", "started_at": "timestamp with time zone",
                    "current_period_end": "timestamp with time zone", "ended_at": "timestamp with time zone",
                    "cancellation_requested_at": "timestamp with time zone", "billing_interval": "text",
                    "billing_interval_count": "bigint", "amount_minor": "bigint", "discount_minor": "bigint",
                    "currency": "text", "updated_at": "timestamp with time zone",
                },
                "subscription_events": {
                    "tenant_id": "text", "event_id": "bigint", "subscription_id": "text", "customer_id": "text",
                    "event_type": "text", "changed_fields_json": "text", "status": "text", "plan_id": "text",
                    "started_at": "timestamp with time zone", "current_period_end": "timestamp with time zone",
                    "ended_at": "timestamp with time zone", "cancellation_requested_at": "timestamp with time zone",
                    "billing_interval": "text", "billing_interval_count": "bigint", "amount_minor": "bigint",
                    "discount_minor": "bigint", "currency": "text", "occurred_at": "timestamp with time zone",
                    "received_at": "timestamp with time zone", "source_available_at": "timestamp with time zone",
                },
                "feature_snapshots": {
                    "feature_snapshot_id": "text", "tenant_id": "text", "customer_id": "text",
                    "as_of": "timestamp with time zone", "feature_version": "text",
                    "data_cutoff_at": "timestamp with time zone", "features_json": "text",
                    "data_quality_status": "text",
                },
                "churn_labels": {
                    "tenant_id": "text", "customer_id": "text", "as_of": "timestamp with time zone",
                    "horizon_days": "bigint", "label": "text", "churn_type": "text",
                    "outcome_at": "timestamp with time zone", "label_observed_through": "timestamp with time zone",
                    "label_policy_version": "text",
                },
                "predictions": {
                    "tenant_id": "text", "prediction_id": "text", "prediction_run_id": "text",
                    "customer_id": "text", "as_of": "timestamp with time zone",
                    "generated_at": "timestamp with time zone", "status": "text", "p_churn_7d": "double precision",
                    "p_churn_14d": "double precision", "p_churn_30d": "double precision",
                    "feature_snapshot_id": "text", "feature_version": "text", "model_version": "text",
                    "calibration_version": "text", "label_policy_version": "text", "reliability_status": "text",
                    "reliability_reasons_json": "text", "data_freshness_status": "text",
                    "input_data_as_of": "timestamp with time zone", "uncertainty_status": "text",
                    "explanations_by_horizon_json": "text",
                },
                "service_principals": {
                    "service_principal_id": "text", "tenant_id": "text", "token_digest": "text", "role": "text",
                    "authorized_sources_json": "text", "authorized_purposes_json": "text",
                    "created_at": "timestamp with time zone",
                },
                "subscription_owners": {"tenant_id": "text", "subscription_id": "text", "customer_id": "text"},
                "integration_event_categories": {"tenant_id": "text", "source": "text", "category": "text"},
                "dataset_identity": {
                    "singleton_id": "bigint", "dataset_id": "text", "dataset_version": "text",
                    "dataset_type": "text", "target_policy_version": "text", "generator_version": "text",
                    "manifest_sha256": "text", "bound_at": "timestamp with time zone",
                },
                "observation_coverage": {
                    "tenant_id": "text", "source": "text", "coverage_id": "text", "customer_id": "text",
                    "source_category": "text", "covered_from": "timestamp with time zone",
                    "covered_through": "timestamp with time zone", "coverage_status": "text",
                    "coverage_completeness": "double precision", "coverage_available_at": "timestamp with time zone",
                    "observation_policy_version": "text", "normalized_payload_sha256": "text",
                },
                "synthetic_import_checkpoints": {
                    "dataset_id": "text", "stream_name": "text", "last_row_number": "bigint",
                    "accepted_count": "bigint", "duplicate_count": "bigint", "rejected_count": "bigint",
                    "updated_at": "timestamp with time zone",
                },
                "retaniq_schema_migrations": {
                    "version": "text", "checksum": "character", "applied_at": "timestamp with time zone",
                },
            }
            expected_column_keys = {
                (table, column) for table, expected in expected_columns.items() for column in expected
            }
            self.assertEqual(set(columns), expected_column_keys)
            for (table, column), expected_type in (
                ((table, column), data_type)
                for table, expected in expected_columns.items()
                for column, data_type in expected.items()
            ):
                self.assertEqual(columns[(table, column)]["data_type"], expected_type, (table, column))

            nullable_columns = {
                ("integrations", "last_successful_ingestion_at"), ("integrations", "last_failure_at"),
                ("integrations", "last_failure_code"), ("canonical_events", "source_available_at"),
                ("usage_events", "feature"), ("usage_events", "quantity"), ("usage_events", "unit"),
                ("usage_events", "source_available_at"), ("billing_events", "subscription_id"),
                ("billing_events", "amount_minor"), ("billing_events", "currency"),
                ("billing_events", "source_available_at"), ("subscriptions", "plan_id"),
                ("subscriptions", "started_at"), ("subscriptions", "current_period_end"),
                ("subscriptions", "ended_at"), ("subscriptions", "cancellation_requested_at"),
                ("subscriptions", "billing_interval"), ("subscriptions", "billing_interval_count"),
                ("subscriptions", "amount_minor"), ("subscriptions", "discount_minor"),
                ("subscriptions", "currency"), ("subscription_events", "status"),
                ("subscription_events", "plan_id"), ("subscription_events", "started_at"),
                ("subscription_events", "current_period_end"), ("subscription_events", "ended_at"),
                ("subscription_events", "cancellation_requested_at"),
                ("subscription_events", "billing_interval"), ("subscription_events", "billing_interval_count"),
                ("subscription_events", "amount_minor"), ("subscription_events", "discount_minor"),
                ("subscription_events", "currency"), ("subscription_events", "source_available_at"),
                ("churn_labels", "churn_type"), ("churn_labels", "outcome_at"),
                ("predictions", "p_churn_7d"), ("predictions", "p_churn_14d"),
                ("predictions", "p_churn_30d"), ("predictions", "feature_snapshot_id"),
                ("predictions", "label_policy_version"), ("predictions", "input_data_as_of"),
            }
            for key, row in columns.items():
                self.assertEqual(row["is_nullable"], "YES" if key in nullable_columns else "NO", key)
            self.assertEqual(columns[("canonical_events", "event_id")]["data_type"], "bigint")
            self.assertEqual(columns[("canonical_events", "occurred_at")]["data_type"], "timestamp with time zone")
            self.assertEqual(columns[("canonical_events", "source_available_at")]["is_nullable"], "YES")
            self.assertEqual(columns[("predictions", "p_churn_7d")]["data_type"], "double precision")
            self.assertEqual(columns[("predictions", "prediction_id")]["is_nullable"], "NO")
            self.assertEqual(columns[("predictions", "prediction_run_id")]["is_nullable"], "NO")
            self.assertEqual(columns[("canonical_events", "normalized_payload_sha256")]["data_type"], "text")

            constraint_rows = connection.execute(
                "SELECT conname, contype, pg_get_constraintdef(oid) AS definition "
                "FROM pg_constraint WHERE connamespace = %s::regnamespace",
                (self.schema,),
            ).fetchall()
            constraints = {row["conname"]: row for row in constraint_rows}
            foreign_keys = {name for name, row in constraints.items() if row["contype"] == "f"}
            self.assertTrue({
                "integrations_tenant_fk", "customers_tenant_fk", "customer_identities_customer_fk",
                "canonical_events_customer_fk", "usage_events_canonical_fk", "usage_events_customer_fk",
                "billing_events_canonical_fk", "billing_events_customer_fk", "subscriptions_customer_fk",
                "subscription_events_canonical_fk", "subscription_events_customer_fk",
                "feature_snapshots_customer_fk", "churn_labels_customer_fk", "predictions_customer_fk",
                "predictions_feature_snapshot_fk", "service_principals_tenant_fk",
                "subscription_owners_customer_fk", "subscription_events_owner_fk", "billing_events_owner_fk",
                "subscriptions_owner_fk", "integration_event_categories_integration_fk",
                "observation_coverage_customer_fk", "observation_coverage_category_fk",
                "synthetic_import_checkpoints_dataset_fk",
            }.issubset(foreign_keys))
            self.assertEqual(sum(row["contype"] == "p" for row in constraints.values()), 19)
            self.assertEqual(constraints["canonical_events_source_key_uq"]["contype"], "u")
            self.assertIn("(tenant_id, source, source_event_id)", constraints["canonical_events_source_key_uq"]["definition"])
            self.assertIn("integrations_token_digest_key", constraints)
            self.assertIn("integrations_tenant_source_uq", constraints)
            self.assertIn("feature_snapshots_account_version_uq", constraints)
            self.assertIn("predictions_account_cutoff_uq", constraints)
            self.assertIn("(tenant_id, customer_id)", constraints["customer_identities_customer_fk"]["definition"])
            self.assertIn("subscription_owners", constraints["subscription_events_owner_fk"]["definition"])
            self.assertIn("feature_snapshots", constraints["predictions_feature_snapshot_fk"]["definition"])
            self.assertIn("p_churn_30d", constraints["predictions_probability_contract"]["definition"])

            index_rows = connection.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = %s",
                (self.schema,),
            ).fetchall()
            indexes = {row["indexname"] for row in index_rows}
            self.assertTrue({
                "canonical_events_account_time", "canonical_events_availability", "subscriptions_account",
                "subscription_events_history", "predictions_run", "observation_coverage_as_of",
            }.issubset(indexes))
        finally:
            connection.close()

    def test_constraints_types_round_trip_and_migration_rerun(self):
        rerun = run_postgresql_migrations(self.config, schema=self.schema)
        self.assertEqual(rerun.applied_versions, ())
        self.assertEqual(rerun.current_version, "007")

        connection = self._connect()
        try:
            import datetime
            import json

            timestamp = datetime.datetime(2026, 10, 10, 12, 30, tzinfo=datetime.timezone.utc)
            payload = '{"a":1,"b":[true,null]}'
            amount_minor = 9_223_372_036_854_000
            with connection.transaction():
                connection.execute("INSERT INTO tenants(tenant_id) VALUES (%s)", ("tenant-a",))
                connection.execute("INSERT INTO tenants(tenant_id) VALUES (%s)", ("tenant-b",))
                connection.execute(
                    "INSERT INTO customers(tenant_id, customer_id, created_at) VALUES (%s, %s, %s)",
                    ("tenant-a", "customer-a", timestamp),
                )
                connection.execute(
                    "INSERT INTO integrations(integration_id, tenant_id, source, token_digest, "
                    "authorized_purposes_json, schema_version, mapping_version, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    ("int-a", "tenant-a", "product", "digest-a", "[]", "1.0", "v1", timestamp),
                )
                connection.execute(
                    "INSERT INTO integration_event_categories(tenant_id, source, category) VALUES (%s, %s, %s)",
                    ("tenant-a", "product", "usage"),
                )
                inserted = connection.execute(
                    "INSERT INTO canonical_events(tenant_id, source, source_event_id, customer_id, category, "
                    "event_type, occurred_at, received_at, source_available_at, schema_version, mapping_version, "
                    "normalized_payload_sha256) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "RETURNING event_id",
                    ("tenant-a", "product", "evt-a", "customer-a", "usage", "session_started", timestamp,
                     timestamp, None, "1.0", "v1", "hash-a"),
                ).fetchone()
                event_id = inserted["event_id"]
                connection.execute(
                    "INSERT INTO usage_events(tenant_id, event_id, customer_id, event_type, quantity, occurred_at, "
                    "received_at, source_available_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    ("tenant-a", event_id, "customer-a", "session_started", 2, timestamp, timestamp, None),
                )
                connection.execute(
                    "INSERT INTO subscription_owners(tenant_id, subscription_id, customer_id) VALUES (%s, %s, %s)",
                    ("tenant-a", "sub-a", "customer-a"),
                )
                connection.execute(
                    "INSERT INTO subscriptions(tenant_id, subscription_id, customer_id, status, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    ("tenant-a", "sub-a", "customer-a", "active", timestamp),
                )
                connection.execute(
                    "INSERT INTO billing_events(tenant_id, event_id, customer_id, subscription_id, event_type, "
                    "payment_status, amount_minor, currency, occurred_at, received_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    ("tenant-a", event_id, "customer-a", "sub-a", "payment_succeeded", "succeeded", amount_minor,
                     "USD", timestamp, timestamp),
                )
                connection.execute(
                    "INSERT INTO feature_snapshots(feature_snapshot_id, tenant_id, customer_id, as_of, "
                    "feature_version, data_cutoff_at, features_json, data_quality_status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    ("feat-a", "tenant-a", "customer-a", timestamp, "f1", timestamp, payload, "ok"),
                )
                connection.execute(
                    "INSERT INTO predictions(tenant_id, prediction_id, prediction_run_id, customer_id, as_of, "
                    "generated_at, status, p_churn_7d, p_churn_14d, p_churn_30d, feature_snapshot_id, "
                    "feature_version, model_version, calibration_version, reliability_status, "
                    "reliability_reasons_json, data_freshness_status, explanations_by_horizon_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    ("tenant-a", "pred-a", "run-a", "customer-a", timestamp, timestamp, "scored", 0.1, 0.2,
                     0.3, "feat-a", "f1", "m1", "c1", "sufficient_evidence", "[]", "fresh", "{}"),
                )
                connection.execute(
                    "INSERT INTO dataset_identity(singleton_id, dataset_id, dataset_version, dataset_type, "
                    "target_policy_version, generator_version, manifest_sha256, bound_at) "
                    "VALUES (1, %s, %s, %s, %s, %s, %s, %s)",
                    ("dataset-test", "1.2", "synthetic_saas", "policy", "generator", "a" * 64, timestamp),
                )
                connection.execute(
                    "INSERT INTO synthetic_import_checkpoints(dataset_id, stream_name, last_row_number, updated_at) "
                    "VALUES (%s, %s, %s, %s)",
                    ("dataset-test", "events", 1, timestamp),
                )

            result = connection.execute(
                "SELECT occurred_at, source_available_at FROM canonical_events WHERE event_id = %s", (event_id,),
            ).fetchone()
            self.assertEqual(result["occurred_at"], timestamp)
            self.assertIsNotNone(result["occurred_at"].tzinfo)
            self.assertIsNone(result["source_available_at"])
            self.assertEqual(json.loads(connection.execute(
                "SELECT features_json FROM feature_snapshots WHERE feature_snapshot_id = %s", ("feat-a",),
            ).fetchone()["features_json"]), {"a": 1, "b": [True, None]})
            self.assertEqual(connection.execute(
                "SELECT amount_minor FROM billing_events WHERE event_id = %s", (event_id,),
            ).fetchone()["amount_minor"], amount_minor)

            with self.assertRaises(DatabaseError):
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO canonical_events(tenant_id, source, source_event_id, customer_id, category, "
                        "event_type, occurred_at, received_at, schema_version, mapping_version, "
                        "normalized_payload_sha256) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        ("tenant-a", "product", "evt-a", "customer-a", "usage", "session_started", timestamp,
                         timestamp, "1.0", "v1", "hash-a"),
                    )
            with self.assertRaises(DatabaseError):
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO customer_identities(tenant_id, source, external_customer_id, customer_id, created_at) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        ("tenant-b", "product", "external-b", "customer-a", timestamp),
                    )
            with self.assertRaises(DatabaseError):
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO customers(tenant_id, customer_id, created_at) VALUES (%s, %s, %s)",
                        ("tenant-missing", "customer-missing", timestamp),
                    )
            with self.assertRaises(DatabaseError):
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO predictions(tenant_id, prediction_id, prediction_run_id, customer_id, as_of, "
                        "generated_at, status, p_churn_7d, p_churn_14d, p_churn_30d, feature_version, model_version, "
                        "calibration_version, reliability_status, reliability_reasons_json, data_freshness_status, "
                        "explanations_by_horizon_json) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        ("tenant-a", "pred-bad", "run-bad", "customer-a", timestamp, timestamp, "scored", 0.1,
                         0.2, 1.1, "f1", "m1", "c1", "sufficient_evidence", "[]", "fresh", "{}"),
                    )
            abstained_at = timestamp + datetime.timedelta(minutes=1)
            with connection.transaction():
                connection.execute(
                    "INSERT INTO predictions(tenant_id, prediction_id, prediction_run_id, customer_id, as_of, "
                    "generated_at, status, p_churn_7d, p_churn_14d, p_churn_30d, feature_version, model_version, "
                    "calibration_version, reliability_status, reliability_reasons_json, data_freshness_status, "
                    "explanations_by_horizon_json) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    ("tenant-a", "pred-abstained", "run-abstained", "customer-a", abstained_at, abstained_at,
                     "abstained", None, None, None, "f1", "m1", "c1", "insufficient_evidence", "[]", "unknown", "{}"),
                )
            self.assertEqual(connection.execute(
                "SELECT p_churn_7d, p_churn_14d, p_churn_30d FROM predictions WHERE prediction_id = %s",
                ("pred-abstained",),
            ).fetchone(), {"p_churn_7d": None, "p_churn_14d": None, "p_churn_30d": None})
            with self.assertRaises(DatabaseError):
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO predictions(tenant_id, prediction_id, prediction_run_id, customer_id, as_of, "
                        "generated_at, status, p_churn_7d, p_churn_14d, p_churn_30d, feature_version, model_version, "
                        "calibration_version, reliability_status, reliability_reasons_json, data_freshness_status, "
                        "explanations_by_horizon_json) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        ("tenant-a", "pred-invalid-abstained", "run-invalid-abstained", "customer-a",
                         abstained_at + datetime.timedelta(minutes=1), abstained_at + datetime.timedelta(minutes=1),
                         "abstained", 0.1, None, None, "f1", "m1", "c1", "insufficient_evidence",
                         "[]", "unknown", "{}"),
                    )
            with self.assertRaisesRegex(RuntimeError, "transaction rollback"):
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO customers(tenant_id, customer_id, created_at) VALUES (%s, %s, %s)",
                        ("tenant-a", "rollback-customer", timestamp),
                    )
                    raise RuntimeError("transaction rollback")
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM customers WHERE tenant_id = %s AND customer_id = %s",
                ("tenant-a", "rollback-customer"),
            ).fetchone())
        finally:
            connection.close()

    def test_modified_applied_migration_checksum_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for migration in discover_migrations():
                shutil.copyfile(migration.path, root / migration.path.name)
            first = root / "001_data_foundation.sql"
            first.write_text(first.read_text(encoding="utf-8") + "\n-- modified\n", encoding="utf-8")
            with self.assertRaises(MigrationChecksumError):
                run_postgresql_migrations(self.config, directory=root, schema=self.schema)

    def test_failed_migration_rolls_back_objects_and_history_row(self):
        schema = f"retaniq_fail_{uuid4().hex[:12]}"
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "001_bootstrap.sql").write_text("CREATE TABLE kept_after_failure (id BIGINT);", encoding="utf-8")
                (root / "002_failure.sql").write_text(
                    "CREATE TABLE rolled_back_marker (id BIGINT); INSERT INTO no_such_table VALUES (1);",
                    encoding="utf-8",
                )
                with self.assertRaises(PostgreSQLMigrationExecutionError) as raised:
                    run_postgresql_migrations(self.config, directory=root, schema=schema)
                self.assertEqual(raised.exception.version, "002")
                self.assertEqual(raised.exception.statement_index, 2)
                self.assertEqual(raised.exception.operation, "INSERT")
                self.assertEqual(raised.exception.sqlstate, "42P01")
            connection = self._connect()
            try:
                connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                connection.execute(f'SET search_path TO "{schema}"')
                tables = {row["tablename"] for row in connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,),
                ).fetchall()}
                versions = {row["version"] for row in connection.execute(
                    "SELECT version FROM retaniq_schema_migrations",
                ).fetchall()}
                self.assertIn("kept_after_failure", tables)
                self.assertNotIn("rolled_back_marker", tables)
                self.assertEqual(versions, {"001"})
            finally:
                connection.close()
        finally:
            connection = self._connect()
            try:
                connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            finally:
                connection.close()

    def test_concurrent_migration_attempts_serialize(self):
        schema = f"retaniq_conc_{uuid4().hex[:12]}"
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(
                    lambda _index: run_postgresql_migrations(self.config, schema=schema),
                    range(2),
                ))
            self.assertEqual(sorted(len(result.applied_versions) for result in results), [0, 7])
            self.assertEqual({result.current_version for result in results}, {"007"})
        finally:
            connection = self._connect()
            try:
                connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
