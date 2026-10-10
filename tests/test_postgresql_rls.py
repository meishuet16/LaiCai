"""Live, restricted-login PostgreSQL RLS and role-permission evidence."""

from __future__ import annotations

import os
import hashlib
import unittest
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from retaniq.database import connect_database
from retaniq.database_config import DatabaseConfig, DatabaseConfigurationError
from retaniq.postgresql_migrations import run_postgresql_migrations, split_sql_statements


def _test_config():
    dsn = os.environ.get("RETAINIQ_POSTGRES_TEST_DSN")
    if not dsn or os.environ.get("RETAINIQ_POSTGRES_TEST_DISPOSABLE") != "1":
        return None
    try:
        config = DatabaseConfig.from_value(dsn, allow_insecure_local_postgresql=True)
        parsed = urlsplit(config.postgresql_dsn)
        database = parsed.path.lstrip("/")
    except (DatabaseConfigurationError, ValueError):
        return None
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not database.startswith("retaniq_test_"):
        return None
    return config


_TEST_CONFIG = _test_config()


@unittest.skipUnless(
    _TEST_CONFIG,
    "requires explicit disposable loopback PostgreSQL test DSN",
)
class PostgreSQLRLSIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg import sql

        cls.psycopg = psycopg
        cls.sql = sql
        cls.admin_config = _TEST_CONFIG
        cls.schema = "public"
        cls.database = f"retaniq_test_rls_{uuid4().hex[:12]}"
        parsed = urlsplit(cls.admin_config.postgresql_dsn)
        cls.admin_dsn = cls.admin_config.postgresql_dsn
        cls.database_dsn = urlunsplit((parsed.scheme, parsed.netloc, f"/{cls.database}", parsed.query, parsed.fragment))
        admin = psycopg.connect(cls.admin_dsn, autocommit=True)
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database)))
        finally:
            admin.close()
        cls.config = DatabaseConfig.from_value(cls.database_dsn, allow_insecure_local_postgresql=True)
        admin = connect_database(cls.config)
        try:
            admin.raw_connection.autocommit = True
            bootstrap = Path(__file__).resolve().parents[1] / "security" / "postgresql" / "role_bootstrap.sql"
            for statement in split_sql_statements(bootstrap.read_text(encoding="utf-8")):
                admin.raw_connection.execute(statement)
        finally:
            admin.close()
        cls.migration_result = run_postgresql_migrations(cls.config)
        cls.suffix = uuid4().hex[:10]
        cls.logins = {}
        cls.login_roles = []
        cls.login_configs = {}
        for capability in ("backend", "inference_reader", "artifact_writer", "decision_service", "dashboard_reader", "maintenance"):
            role = f"retaniq_test_{capability}_{cls.suffix}"
            password = uuid4().hex + uuid4().hex
            admin = psycopg.connect(cls.database_dsn, autocommit=True)
            try:
                admin.execute(
                    sql.SQL("CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {} IN ROLE {}")
                    .format(sql.Identifier(role), sql.Literal(password), sql.Identifier(f"retaniq_{capability}")),
                )
            finally:
                admin.close()
            login_dsn = urlunsplit((parsed.scheme, f"{role}:{password}@{parsed.hostname}:{parsed.port or 5432}", f"/{cls.database}", parsed.query, parsed.fragment))
            cls.logins[capability] = login_dsn
            cls.login_configs[capability] = DatabaseConfig.from_value(
                login_dsn, allow_insecure_local_postgresql=True,
            )
            cls.login_roles.append(role)

        admin = connect_database(cls.config)
        try:
            admin.raw_connection.autocommit = True
            admin.execute("INSERT INTO tenants(tenant_id) VALUES ('tenant_a'), ('tenant_b')")
            admin.execute(
                "INSERT INTO customers(tenant_id, customer_id, created_at) "
                "VALUES ('tenant_a', 'customer_a', CURRENT_TIMESTAMP), ('tenant_b', 'customer_b', CURRENT_TIMESTAMP)",
            )
            admin.execute(
                "INSERT INTO integrations(integration_id, tenant_id, source, token_digest, authorized_purposes_json, schema_version, mapping_version, created_at) "
                "VALUES ('integration_a', 'tenant_a', 'source_a', %s, '[\"retention_inference\"]', '1.0', 'canonical-v1', CURRENT_TIMESTAMP)",
                (hashlib.sha256(b"verified test integration token 01").hexdigest(),),
            )
            admin.execute("INSERT INTO integration_event_categories(tenant_id,source,category) VALUES ('tenant_a','source_a','usage')")
            admin.execute(
                "INSERT INTO integrations(integration_id, tenant_id, source, token_digest, authorized_purposes_json, schema_version, mapping_version, created_at) "
                "VALUES ('integration_b', 'tenant_b', 'source_b', repeat('e',64), '[\"retention_inference\"]', '1.0', 'canonical-v1', CURRENT_TIMESTAMP)"
            )
            admin.execute("INSERT INTO integration_event_categories(tenant_id,source,category) VALUES ('tenant_b','source_b','usage')")
            admin.execute(
                "INSERT INTO service_principals(service_principal_id,tenant_id,token_digest,role,authorized_sources_json,authorized_purposes_json,created_at) "
                "VALUES ('principal_a','tenant_a',repeat('b',64),'analyst','[\"source_a\"]','[\"retention_inference\"]',CURRENT_TIMESTAMP)"
            )
            writer_token = "verified test artifact writer token 01"
            admin.execute(
                "INSERT INTO service_principals(service_principal_id,tenant_id,token_digest,role,authorized_sources_json,authorized_purposes_json,created_at) "
                "VALUES ('principal_writer','tenant_a',%s,'analyst','[\"source_a\"]','[\"model_artifact_write\"]',CURRENT_TIMESTAMP)",
                (hashlib.sha256(writer_token.encode()).hexdigest(),),
            )
            admin.execute(
                "INSERT INTO integrations(integration_id,tenant_id,source,token_digest,authorized_purposes_json,schema_version,mapping_version,created_at) "
                "VALUES ('integration_private','tenant_a','private_source',repeat('9',64),'[\"retention_inference\"]','1.0','canonical-v1',CURRENT_TIMESTAMP)"
            )
            admin.execute("INSERT INTO integration_event_categories(tenant_id,source,category) VALUES ('tenant_a','private_source','usage')")
            admin.execute(
                "INSERT INTO canonical_events(tenant_id,source,source_event_id,customer_id,category,event_type,occurred_at,received_at,schema_version,mapping_version,normalized_payload_sha256) "
                "VALUES ('tenant_a','source_a','evt_a','customer_a','usage','feature_used',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'1.0','canonical-v1',repeat('c',64)), "
                "('tenant_b','source_b','evt_b','customer_b','usage','feature_used',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'1.0','canonical-v1',repeat('d',64))"
            )
            admin.execute("INSERT INTO customer_identities(tenant_id,source,external_customer_id,customer_id,created_at) VALUES ('tenant_a','source_a','external_a','customer_a',CURRENT_TIMESTAMP),('tenant_b','source_b','external_b','customer_b',CURRENT_TIMESTAMP)")
            for tenant, event_id, customer, source, subscription in (
                ("tenant_a", "evt_a", "customer_a", "source_a", "sub_a"),
                ("tenant_b", "evt_b", "customer_b", "source_b", "sub_b"),
            ):
                canonical_id = admin.execute("SELECT event_id FROM canonical_events WHERE tenant_id=%s AND source_event_id=%s", (tenant, event_id)).fetchone()["event_id"]
                admin.execute("INSERT INTO usage_events(tenant_id,event_id,customer_id,event_type,occurred_at,received_at) VALUES (%s,%s,%s,'feature_used',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (tenant, canonical_id, customer))
                admin.execute("INSERT INTO billing_events(tenant_id,event_id,customer_id,event_type,payment_status,occurred_at,received_at) VALUES (%s,%s,%s,'payment_succeeded','succeeded',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (tenant, canonical_id, customer))
                admin.execute("INSERT INTO subscription_owners(tenant_id,subscription_id,customer_id) VALUES (%s,%s,%s)", (tenant, subscription, customer))
                admin.execute("INSERT INTO subscriptions(tenant_id,subscription_id,customer_id,status,updated_at) VALUES (%s,%s,%s,'active',CURRENT_TIMESTAMP)", (tenant, subscription, customer))
                admin.execute("INSERT INTO subscription_events(tenant_id,event_id,subscription_id,customer_id,event_type,changed_fields_json,occurred_at,received_at) VALUES (%s,%s,%s,%s,'subscription_updated','[]',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (tenant, canonical_id, subscription, customer))
                snapshot_id = f"snapshot_{tenant[-1]}"
                admin.execute("INSERT INTO feature_snapshots(feature_snapshot_id,tenant_id,customer_id,as_of,feature_version,data_cutoff_at,features_json,data_quality_status) VALUES (%s,%s,%s,CURRENT_TIMESTAMP,'v1',CURRENT_TIMESTAMP,'{}','complete')", (snapshot_id, tenant, customer))
                admin.execute("INSERT INTO churn_labels(tenant_id,customer_id,as_of,horizon_days,label,label_observed_through,label_policy_version) VALUES (%s,%s,CURRENT_TIMESTAMP,7,'unknown',CURRENT_TIMESTAMP,'v1')", (tenant, customer))
                admin.execute("INSERT INTO predictions(tenant_id,prediction_id,prediction_run_id,customer_id,as_of,generated_at,status,feature_snapshot_id,feature_version,model_version,calibration_version,reliability_status,reliability_reasons_json,data_freshness_status,explanations_by_horizon_json) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'abstained',%s,'v1','m1','c1','insufficient_evidence','[]','unknown','{}')", (tenant, f"prediction_{tenant[-1]}", f"run_{tenant[-1]}", customer, snapshot_id))
                admin.execute("INSERT INTO observation_coverage(tenant_id,source,coverage_id,customer_id,source_category,covered_from,covered_through,coverage_status,coverage_completeness,coverage_available_at,observation_policy_version,normalized_payload_sha256) VALUES (%s,%s,%s,%s,'usage',CURRENT_TIMESTAMP - INTERVAL '1 day',CURRENT_TIMESTAMP,'complete',1,CURRENT_TIMESTAMP,'v1',repeat('f',64))", (tenant, source, f"coverage_{tenant[-1]}", customer))
            admin.execute("INSERT INTO dataset_identity(singleton_id,dataset_id,dataset_version,dataset_type,target_policy_version,generator_version,manifest_sha256,bound_at) VALUES (1,'dataset_test','1.0','synthetic_saas','target_v1','generator_v1',repeat('a',64),CURRENT_TIMESTAMP)")
            admin.execute("INSERT INTO synthetic_import_checkpoints(dataset_id,stream_name,last_row_number,updated_at) VALUES ('dataset_test','events',0,CURRENT_TIMESTAMP)")
        finally:
            admin.close()

    @classmethod
    def tearDownClass(cls):
        if not getattr(cls, "admin_dsn", None):
            return
        admin = cls.psycopg.connect(cls.admin_dsn, autocommit=True)
        try:
            for role in cls.login_roles:
                admin.execute(cls.sql.SQL("DROP ROLE IF EXISTS {}").format(cls.sql.Identifier(role)))
            admin.execute(cls.sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(cls.sql.Identifier(cls.database)))
        finally:
            admin.close()

    def _connect(self, capability):
        return self.psycopg.connect(self.logins[capability], autocommit=True, prepare_threshold=None)

    def _begin(self, connection, tenant="tenant_a"):
        connection.execute("BEGIN")
        if tenant is not None:
            connection.execute("SELECT set_config('retaniq.tenant_id', %s, true)", (tenant,))

    def _expect_denied(self, connection, statement):
        connection.execute("SAVEPOINT denied_attempt")
        try:
            with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):
                connection.execute(statement)
        finally:
            connection.execute("ROLLBACK TO SAVEPOINT denied_attempt")
            connection.execute("RELEASE SAVEPOINT denied_attempt")

    def test_catalog_forces_rls_on_all_tenant_and_global_data_tables(self):
        with self.psycopg.connect(self.database_dsn) as connection:
            rows = connection.execute(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r' AND c.relname <> 'retaniq_schema_migrations'"
            ).fetchall()
        self.assertEqual(len(rows), 18)
        self.assertTrue(all(row[1] and row[2] for row in rows))
        self.assertEqual(self.migration_result.current_version, "007")

    def test_role_table_function_sequence_and_policy_catalog(self):
        with self.psycopg.connect(self.database_dsn) as connection:
            capabilities = connection.execute(
                "SELECT rolname, rolcanlogin, rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname LIKE 'retaniq_%' AND rolname NOT LIKE 'retaniq_test_%' ORDER BY rolname"
            ).fetchall()
            owners = connection.execute(
                "SELECT c.relname,r.rolname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='public' AND c.relkind='r' "
                "AND c.relname <> 'retaniq_schema_migrations'"
            ).fetchall()
            views = connection.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind IN ('v','m')"
            ).fetchone()[0]
            triggers = connection.execute(
                "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal"
            ).fetchone()[0]
            definers = connection.execute(
                "SELECT p.proname,r.rolname,p.prosecdef,p.proconfig "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "JOIN pg_roles r ON r.oid=p.proowner WHERE n.nspname='public' AND p.proname LIKE 'retaniq_authenticate_%'"
            ).fetchall()
            sequence_count = connection.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='S'"
            ).fetchone()[0]
            policies = connection.execute("SELECT tablename,policyname FROM pg_policies WHERE schemaname='public'").fetchall()
            authenticator_create = connection.execute(
                "SELECT has_schema_privilege('retaniq_authenticator', %s, 'CREATE')",
                (self.schema,),
            ).fetchone()[0]
            authenticator_set_membership = connection.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_auth_members membership "
                "JOIN pg_roles granted_role ON granted_role.oid=membership.roleid "
                "JOIN pg_roles member_role ON member_role.oid=membership.member "
                "WHERE granted_role.rolname='retaniq_authenticator' "
                "AND member_role.rolname=current_user AND membership.set_option)",
            ).fetchone()[0]
        self.assertTrue(capabilities)
        self.assertTrue(all(not role[1] and not role[2] and not role[3] for role in capabilities))
        self.assertTrue(all(owner[1] not in {role[0] for role in capabilities} for owner in owners))
        self.assertEqual(views, 0)
        self.assertEqual(triggers, 0)
        self.assertEqual(sequence_count, 1)
        self.assertEqual(len(definers), 2)
        self.assertTrue(all(row[2] and row[1] == "retaniq_authenticator" and "search_path=pg_catalog, public" in row[3][0] for row in definers))
        self.assertFalse(authenticator_create)
        self.assertFalse(authenticator_set_membership)
        policy_names = {(row[0], row[1]) for row in policies}
        for table in ("tenants", "integrations", "customers", "customer_identities", "canonical_events", "usage_events", "billing_events", "subscriptions", "subscription_events", "feature_snapshots", "churn_labels", "predictions", "service_principals", "subscription_owners", "integration_event_categories", "observation_coverage"):
            self.assertIn((table, "tenant_backend_scope"), policy_names)

    def test_every_tenant_table_has_positive_and_cross_tenant_negative_evidence(self):
        tenant_tables = (
            "tenants", "integrations", "customers", "customer_identities", "canonical_events",
            "usage_events", "billing_events", "subscriptions", "subscription_events",
            "feature_snapshots", "churn_labels", "predictions", "service_principals",
            "subscription_owners", "integration_event_categories", "observation_coverage",
        )
        connection = self._connect("backend")
        try:
            self._begin(connection, "tenant_a")
            for table in tenant_tables:
                self.assertGreater(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0, table)
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table} WHERE tenant_id='tenant_b'").fetchone()[0], 0, table)
        finally:
            connection.execute("ROLLBACK")
            connection.close()

    def test_missing_invalid_and_transaction_ended_context_fail_closed(self):
        connection = self._connect("backend")
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM customers").fetchone()[0], 0)
            self._begin(connection, "no_such_tenant")
            self.assertEqual(connection.execute("SELECT count(*) FROM customers").fetchone()[0], 0)
            connection.execute("COMMIT")
            self.assertEqual(connection.execute("SELECT count(*) FROM customers").fetchone()[0], 0)
        finally:
            connection.close()

    def test_tenants_are_isolated_for_select_insert_update_delete_and_returning(self):
        connection = self._connect("backend")
        try:
            self._begin(connection)
            self.assertEqual(connection.execute("SELECT customer_id FROM customers ORDER BY customer_id").fetchall(), [("customer_a",)])
            self.assertEqual(connection.execute("SELECT count(*) FROM customers WHERE tenant_id='tenant_b'").fetchone()[0], 0)
            self._expect_denied(connection, "INSERT INTO customers(tenant_id,customer_id,created_at) VALUES ('tenant_b','forged',CURRENT_TIMESTAMP) RETURNING customer_id")
            connection.execute("ROLLBACK")
            self._begin(connection)
            self._expect_denied(connection, "UPDATE customers SET tenant_id='tenant_b' WHERE customer_id='customer_a' RETURNING customer_id")
            self._expect_denied(connection, "INSERT INTO customers(tenant_id,customer_id,created_at) VALUES ('tenant_b','customer_b',CURRENT_TIMESTAMP) ON CONFLICT(tenant_id,customer_id) DO UPDATE SET account_status='inactive'")
            connection.execute("ROLLBACK")
            self._begin(connection, "tenant_b")
            self.assertEqual(connection.execute("SELECT customer_id FROM customers").fetchall(), [("customer_b",)])
            connection.execute("COMMIT")
        finally:
            connection.close()

        maintenance = self._connect("maintenance")
        try:
            self._begin(maintenance, "tenant_a")
            self.assertEqual(maintenance.execute("DELETE FROM customers WHERE tenant_id='tenant_b'").rowcount, 0)
        finally:
            maintenance.execute("ROLLBACK")
            maintenance.close()

    def test_all_tenant_tables_reject_cross_tenant_insert_update_and_delete(self):
        tenant_tables = (
            "tenants", "integrations", "customers", "customer_identities", "canonical_events",
            "usage_events", "billing_events", "subscriptions", "subscription_events",
            "feature_snapshots", "churn_labels", "predictions", "service_principals",
            "subscription_owners", "integration_event_categories", "observation_coverage",
        )
        backend = self._connect("backend")
        try:
            self._begin(backend, "tenant_a")
            for table in tenant_tables:
                columns = backend.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                    (table,),
                ).fetchall()
                column_names = [row[0] for row in columns]
                insert_sql = self.sql.SQL("INSERT INTO {} ({}) SELECT {} FROM {} WHERE tenant_id='tenant_a' LIMIT 1").format(
                    self.sql.Identifier(table),
                    self.sql.SQL(",").join(map(self.sql.Identifier, column_names)),
                    self.sql.SQL(",").join(
                        self.sql.SQL("'tenant_b'::text") if name == "tenant_id" else self.sql.Identifier(name)
                        for name in column_names
                    ),
                    self.sql.Identifier(table),
                )
                with self.subTest(table=table, operation="insert"):
                    self._expect_denied(backend, insert_sql)
                with self.subTest(table=table, operation="update"):
                    self._expect_denied(backend, f"UPDATE {table} SET tenant_id='tenant_b' WHERE tenant_id='tenant_a'")
            backend.execute("ROLLBACK")
        finally:
            backend.close()

        maintenance = self._connect("maintenance")
        try:
            self._begin(maintenance, "tenant_a")
            for table in tenant_tables:
                with self.subTest(table=table, operation="delete"):
                    deleted = maintenance.execute(f"DELETE FROM {table} WHERE tenant_id='tenant_b'").rowcount
                    self.assertEqual(deleted, 0, table)
        finally:
            maintenance.execute("ROLLBACK")
            maintenance.close()

    def test_child_reads_and_joins_obey_tenant_scope(self):
        connection = self._connect("inference_reader")
        try:
            self._begin(connection)
            self.assertEqual(connection.execute("SELECT count(*) FROM canonical_events").fetchone()[0], 1)
            self.assertEqual(
                connection.execute("SELECT count(*) FROM canonical_events e JOIN customers c USING (tenant_id,customer_id) WHERE c.tenant_id='tenant_b'").fetchone()[0],
                0,
            )
        finally:
            connection.execute("ROLLBACK")
            connection.close()

    def test_roles_cannot_escalate_or_create_schema(self):
        connection = self._connect("backend")
        try:
            self._begin(connection)
            self._expect_denied(connection, "CREATE SCHEMA retaniq_forbidden")
            self._expect_denied(connection, "ALTER TABLE customers DISABLE ROW LEVEL SECURITY")
            self._expect_denied(connection, "GRANT retaniq_maintenance TO CURRENT_USER")
            self.assertFalse(connection.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()[0])
        finally:
            connection.close()

    def test_inference_is_read_only_and_artifact_writer_cannot_read_source_events(self):
        reader = self._connect("inference_reader")
        try:
            self._begin(reader)
            self.assertEqual(reader.execute("SELECT count(*) FROM canonical_events").fetchone()[0], 1)
            self._expect_denied(reader, "INSERT INTO customers(tenant_id,customer_id,created_at) VALUES ('tenant_a','nope',CURRENT_TIMESTAMP)")
            reader.execute("ROLLBACK")
        finally:
            reader.close()
        writer = self._connect("artifact_writer")
        try:
            self._begin(writer)
            self._expect_denied(writer, "SELECT * FROM canonical_events")
            self._expect_denied(writer, "INSERT INTO predictions(tenant_id,prediction_id,prediction_run_id,customer_id,as_of,generated_at,status,feature_version,model_version,calibration_version,reliability_status,reliability_reasons_json,data_freshness_status,explanations_by_horizon_json) VALUES ('tenant_b','p','r','customer_b',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'abstained','v','m','c','insufficient_evidence','[]','unknown','{}')")
        finally:
            writer.execute("ROLLBACK")
            writer.close()

    def test_restricted_artifact_writer_uses_verified_source_scope_for_real_writes(self):
        from retaniq.data_foundation import (
            authenticate_service_principal, store_churn_label,
            store_feature_snapshot, store_prediction,
        )

        principal = authenticate_service_principal(
            self.login_configs["backend"], "verified test artifact writer token 01",
        )
        writer_config = self.login_configs["artifact_writer"]
        snapshot_id = store_feature_snapshot(
            writer_config, principal, "customer_a", "2030-01-01T00:00:00Z",
            "feature-v1", "2030-01-01T00:00:00Z", {"sessions_7d": 2}, "available",
        )
        store_churn_label(
            writer_config, principal, "customer_a", "2030-01-01T00:00:00Z",
            7, "unknown", "2030-01-02T00:00:00Z", "label-v1",
        )
        prediction = {
            "prediction_id": "restricted-prediction", "prediction_run_id": "restricted-run",
            "customer_id": "customer_a", "as_of": "2030-01-01T00:00:00Z",
            "generated_at": "2030-01-02T00:00:00Z", "status": "scored",
            "p_churn_7d": 0.1, "p_churn_14d": 0.2, "p_churn_30d": 0.3,
            "feature_snapshot_id": snapshot_id, "feature_version": "feature-v1",
            "model_version": "model-v1", "calibration_version": "calibration-v1",
            "reliability_status": "sufficient_evidence", "data_freshness_status": "fresh",
            "input_data_as_of": "2030-01-01T00:00:00Z",
            "explanations_by_horizon": {},
        }
        self.assertEqual(store_prediction(writer_config, principal, prediction), "restricted-prediction")

        writer = self._connect("artifact_writer")
        try:
            self._begin(writer, "tenant_a")
            writer.execute("SELECT set_config('retaniq.authorized_sources', 'source_a', true)")
            writer.execute("SELECT set_config('retaniq.service_principal_id', 'principal_writer', true)")
            self.assertEqual(
                writer.execute("SELECT count(*) FROM customer_identities WHERE source='source_a'").fetchone()[0], 1,
            )
            self.assertEqual(
                writer.execute("SELECT count(*) FROM customer_identities WHERE source='private_source'").fetchone()[0], 0,
            )
            self._expect_denied(writer, "SELECT * FROM canonical_events")
        finally:
            writer.execute("ROLLBACK")
            writer.close()

    def test_dashboard_and_decision_roles_are_read_only(self):
        for capability in ("dashboard_reader", "decision_service"):
            connection = self._connect(capability)
            try:
                self._begin(connection)
                if capability == "dashboard_reader":
                    self.assertEqual(connection.execute("SELECT count(*) FROM customers").fetchone()[0], 1)
                self._expect_denied(connection, "DELETE FROM customers WHERE tenant_id='tenant_a'")
            finally:
                connection.execute("ROLLBACK")
                connection.close()

    def test_authentication_bootstrap_derives_tenant_from_verified_digest(self):
        connection = self._connect("backend")
        try:
            connection.execute("BEGIN")
            invalid = connection.execute("SELECT tenant_id FROM retaniq_authenticate_integration(%s)", ("0" * 64,)).fetchall()
            self.assertEqual(invalid, [])
            self.assertIn(connection.execute("SELECT current_setting('retaniq.tenant_id', true)").fetchone()[0], (None, ""))
            connection.execute("ROLLBACK")
            connection.execute("BEGIN")
            digest = hashlib.sha256(b"verified test integration token 01").hexdigest()
            row = connection.execute("SELECT tenant_id FROM retaniq_authenticate_integration(%s)", (digest,)).fetchone()
            self.assertEqual(row[0], "tenant_a")
            self.assertEqual(connection.execute("SELECT current_setting('retaniq.tenant_id')").fetchone()[0], "tenant_a")
            connection.execute("COMMIT")
            self.assertIn(connection.execute("SELECT current_setting('retaniq.tenant_id', true)").fetchone()[0], (None, ""))
            connection.execute("BEGIN")
            service = connection.execute("SELECT tenant_id FROM retaniq_authenticate_service_principal(%s)", ("b" * 64,)).fetchone()
            self.assertEqual(service[0], "tenant_a")
        finally:
            connection.close()

    def test_python_authentication_and_repository_scope_use_verified_principal(self):
        from retaniq.data_foundation import authenticate_integration, get_events_as_of

        config = self.login_configs["backend"]
        principal = authenticate_integration(config, "verified test integration token 01")
        self.assertEqual(principal.tenant_id, "tenant_a")
        events = get_events_as_of(config, principal, "customer_a", "2030-01-01T00:00:00Z")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "source_a")
        with self.assertRaises(Exception):
            authenticate_integration(config, "invalid token with sufficient length")

    def test_transaction_context_does_not_leak_on_reused_connection(self):
        connection = self._connect("backend")
        try:
            self._begin(connection)
            self.assertEqual(connection.execute("SELECT count(*) FROM customers").fetchone()[0], 1)
            connection.execute("COMMIT")
            self.assertIn(connection.execute("SELECT current_setting('retaniq.tenant_id', true)").fetchone()[0], (None, ""))
            self._begin(connection, "tenant_b")
            self.assertEqual(connection.execute("SELECT customer_id FROM customers").fetchall(), [("customer_b",)])
            connection.execute("ROLLBACK")
            self.assertIn(connection.execute("SELECT current_setting('retaniq.tenant_id', true)").fetchone()[0], (None, ""))
        finally:
            connection.execute("ROLLBACK")
            connection.close()

    def test_custom_guc_spoofing_is_possible_to_a_compromised_shared_role(self):
        connection = self._connect("backend")
        try:
            self._begin(connection, "tenant_b")
            self.assertEqual(connection.execute("SELECT customer_id FROM customers").fetchall(), [("customer_b",)])
        finally:
            connection.execute("ROLLBACK")
            connection.close()

    def test_role_inheritance_and_global_table_denial(self):
        connection = self._connect("backend")
        try:
            self._begin(connection)
            for table in ("dataset_identity", "synthetic_import_checkpoints", "retaniq_schema_migrations"):
                self._expect_denied(connection, f"SELECT * FROM {table}")
            self._expect_denied(connection, "SET ROLE retaniq_maintenance")
        finally:
            connection.execute("ROLLBACK")
            connection.close()

        maintenance = self._connect("maintenance")
        try:
            self._begin(maintenance, tenant=None)
            self.assertEqual(maintenance.execute("SELECT dataset_id FROM dataset_identity").fetchall(), [("dataset_test",)])
            maintenance.execute(
                "INSERT INTO synthetic_import_checkpoints(dataset_id,stream_name,last_row_number,updated_at) "
                "VALUES ('dataset_test','security-test',0,CURRENT_TIMESTAMP)"
            )
            self.assertEqual(
                maintenance.execute("SELECT count(*) FROM synthetic_import_checkpoints WHERE stream_name='security-test'").fetchone()[0], 1,
            )
        finally:
            maintenance.execute("ROLLBACK")
            maintenance.close()


if __name__ == "__main__":
    unittest.main()
