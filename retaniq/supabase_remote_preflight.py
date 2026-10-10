"""Sanitized, read-only catalog preflight for the authorized LaiCai demo.

The password is requested on a controlling terminal with getpass and exists
only in process memory. This module never applies migrations or prints DSNs.
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
import secrets
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

from .database_config import DatabaseConfig
from .postgresql_migrations import (
    MigrationHistoryError,
    PostgreSQLMigrationExecutionError,
    discover_migrations,
    plan_migrations,
    run_postgresql_migrations,
    _safe_migration_diagnostic,
    split_sql_statements,
    verify_postgresql_schema,
)


PROJECT_REF = "mhtzkzqjcsdyjacvcxty"
PROJECT_URL = f"https://{PROJECT_REF}.supabase.co"
DEFAULT_HOST = "aws-0-ap-northeast-2.pooler.supabase.com"
DEFAULT_USER = f"postgres.{PROJECT_REF}"
APP_TABLES = (
    "tenants", "integrations", "customers", "customer_identities", "canonical_events",
    "usage_events", "billing_events", "subscriptions", "subscription_events",
    "feature_snapshots", "churn_labels", "predictions", "service_principals",
    "subscription_owners", "integration_event_categories", "observation_coverage",
    "dataset_identity", "synthetic_import_checkpoints", "retaniq_schema_migrations",
)
CAPABILITY_ROLES = (
    "retaniq_backend", "retaniq_inference_reader", "retaniq_artifact_writer",
    "retaniq_decision_service", "retaniq_dashboard_reader", "retaniq_maintenance",
    "retaniq_authenticator",
)


def _safe_config(host: str, user: str, password: str) -> DatabaseConfig:
    if not re.fullmatch(r"[a-z0-9.-]+\.pooler\.supabase\.com", host):
        raise ValueError("host is not an approved Supabase pooler hostname")
    if user != DEFAULT_USER or not password:
        raise ValueError("migration login does not match the designated project")
    dsn = f"postgresql://{user}:{quote(password, safe='')}@{host}:5432/postgres?sslmode=require"
    return DatabaseConfig.for_supabase_migration_target(
        dsn, project_ref=PROJECT_REF, project_url=PROJECT_URL,
    )


def inspect_catalog(connection: Any) -> dict[str, object]:
    """Inspect target identity, schema, migration history and role capabilities."""
    connection.execute("SET TRANSACTION READ ONLY")
    identity = connection.execute(
        "SELECT current_database() AS database, current_user AS database_role, "
        "inet_server_addr()::text AS server_address, "
        "current_setting(%s) AS server_version, current_setting(%s) AS transaction_read_only, "
        "role.rolsuper, role.rolcreaterole, role.rolcreatedb, role.rolbypassrls "
        "FROM pg_catalog.pg_roles AS role WHERE role.rolname = current_user",
        ("server_version", "transaction_read_only"),
    ).fetchone()
    schema = connection.execute(
        "SELECT pg_catalog.pg_get_userbyid(nspowner) AS owner, "
        "pg_catalog.has_schema_privilege(current_user, oid, 'CREATE') AS can_create, "
        "pg_catalog.pg_has_role(current_user, nspowner, 'USAGE') AS can_manage_acl "
        "FROM pg_catalog.pg_namespace WHERE nspname = 'public'",
    ).fetchone()
    database_owner = connection.execute(
        "SELECT pg_catalog.pg_get_userbyid(database.datdba) AS owner, "
        "database.datdba = current_user_role.oid AS current_role_owns_database "
        "FROM pg_catalog.pg_database AS database "
        "JOIN pg_catalog.pg_roles AS current_user_role ON current_user_role.rolname = current_user "
        "WHERE database.datname = current_database()",
    ).fetchone()
    table_rows = connection.execute(
        "SELECT relation.relname AS table_name, "
        "pg_catalog.pg_get_userbyid(relation.relowner) AS owner, "
        "relation.relrowsecurity AS rls_enabled, relation.relforcerowsecurity AS rls_forced, "
        "EXISTS (SELECT 1 FROM pg_catalog.pg_attribute AS column_info "
        "WHERE column_info.attrelid = relation.oid AND column_info.attname = 'tenant_id' "
        "AND column_info.attnum > 0 AND NOT column_info.attisdropped) AS has_tenant_id "
        "FROM pg_catalog.pg_class AS relation "
        "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
        "WHERE namespace.nspname = 'public' AND relation.relkind IN ('r', 'p') "
        "AND relation.relname = ANY(%s) ORDER BY relation.relname",
        (list(APP_TABLES),),
    ).fetchall()
    table_names = {row["table_name"] for row in table_rows}
    migration_state = "NOT_INITIALIZED"
    pending_versions: list[str] = []
    migration_relation = connection.execute(
        "SELECT pg_catalog.to_regclass(%s) AS name", ("public.retaniq_schema_migrations",),
    ).fetchone()["name"]
    if migration_relation is not None:
        history_rows = connection.execute(
            'SELECT version, checksum FROM "public"."retaniq_schema_migrations" ORDER BY version',
        ).fetchall()
        applied = {str(row["version"]): str(row["checksum"]).strip() for row in history_rows}
        try:
            pending_versions = [
                migration.version for migration in plan_migrations(discover_migrations(), applied)
            ]
            migration_state = "PENDING" if pending_versions else "CHECKSUMS_MATCH"
        except MigrationHistoryError:
            migration_state = "HISTORY_OR_CHECKSUM_MISMATCH"
    elif table_names.intersection(APP_TABLES[:-1]):
        migration_state = "CONFLICTING_EXISTING_RETAINIQ_OBJECTS"
    else:
        # Make the state explicit: an absent history table means every local
        # migration is still pending, rather than an empty pending list.
        pending_versions = [migration.version for migration in discover_migrations()]

    expected_policies = connection.execute(
        "SELECT count(*) AS count FROM pg_catalog.pg_policy policy "
        "JOIN pg_catalog.pg_class relation ON relation.oid = policy.polrelid "
        "JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace "
        "WHERE namespace.nspname = 'public' AND relation.relname = ANY(%s)",
        (list(APP_TABLES),),
    ).fetchone()["count"]
    policy_rows = connection.execute(
        "SELECT relation.relname AS table_name, policy.polname AS policy_name, "
        "policy.polcmd AS command, policy.polpermissive AS permissive, "
        "pg_catalog.pg_get_expr(policy.polqual, policy.polrelid) AS using_expression, "
        "pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid) AS check_expression "
        "FROM pg_catalog.pg_policy AS policy "
        "JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid "
        "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
        "WHERE namespace.nspname = 'public' AND relation.relname = ANY(%s) "
        "ORDER BY relation.relname, policy.polname",
        (list(APP_TABLES),),
    ).fetchall()
    role_rows = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, "
        "rolinherit, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = ANY(%s) ORDER BY rolname",
        (list(CAPABILITY_ROLES) + ["postgres", "service_role", "authenticated", "anon"],),
    ).fetchall()
    membership_rows = connection.execute(
        "SELECT granted_role.rolname AS capability_role, member_role.rolname AS member_role, "
        "membership.inherit_option, membership.set_option, membership.admin_option "
        "FROM pg_catalog.pg_auth_members AS membership "
        "JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid "
        "JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member "
        "WHERE granted_role.rolname = ANY(%s) ORDER BY granted_role.rolname, member_role.rolname",
        (list(CAPABILITY_ROLES),),
    ).fetchall()
    function_rows = connection.execute(
        "SELECT procedure.proname AS function_name, "
        "pg_catalog.pg_get_userbyid(procedure.proowner) AS owner, procedure.prosecdef AS security_definer "
        "FROM pg_catalog.pg_proc AS procedure "
        "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace "
        "WHERE namespace.nspname = 'public' AND procedure.proname = ANY(%s) ORDER BY procedure.proname",
        (["retaniq_authenticate_integration", "retaniq_authenticate_service_principal"],),
    ).fetchall()
    return {
        "status": "CATALOG_PREFLIGHT_READ_ONLY",
        "project_ref": PROJECT_REF,
        "connection_mode": "SESSION_POOLER",
        "destination": dict(identity) if identity is not None else None,
        "public_schema": dict(schema) if schema is not None else None,
        "database_owner": dict(database_owner) if database_owner is not None else None,
        "application_tables": [dict(row) for row in table_rows],
        "migration_history": {"state": migration_state, "pending_versions": pending_versions},
        "rls_policy_count": expected_policies,
        "rls_policies": [dict(row) for row in policy_rows],
        "roles": [dict(row) for row in role_rows],
        "role_memberships": [dict(row) for row in membership_rows],
        "authentication_functions": [dict(row) for row in function_rows],
        "recovery_point": "NOT_VERIFIABLE_FROM_POSTGRES_CATALOG_REQUIRES_DASHBOARD_CONFIRMATION",
        "mutations_performed": False,
    }


def _connect_read_only(config: DatabaseConfig) -> tuple[Any, dict[str, object]]:
    import psycopg
    from psycopg.rows import dict_row

    connection = psycopg.connect(
        config.postgresql_dsn,
        connect_timeout=15,
        application_name="retainiq_readonly_catalog_preflight",
        autocommit=False,
        row_factory=dict_row,
    )
    try:
        with connection.transaction():
            result = inspect_catalog(connection)
        return connection, result
    except Exception:
        connection.close()
        raise


def _deployment_gate(report: dict[str, object]) -> bool:
    destination = report.get("destination")
    schema = report.get("public_schema")
    history = report.get("migration_history")
    existing = report.get("application_tables")
    roles = {row["rolname"]: row for row in report.get("roles", [])}
    expected_roles = set(CAPABILITY_ROLES)
    role_conflicts = any(
        role in roles and (
            roles[role]["rolcanlogin"] or roles[role]["rolsuper"]
            or roles[role]["rolbypassrls"] or roles[role]["rolinherit"]
        )
        for role in expected_roles
    )
    return bool(
        destination
        and destination["database"] == "postgres"
        and destination["database_role"] == "postgres"
        and not destination["rolsuper"]
        and destination["rolcreaterole"]
        and destination["rolbypassrls"]
        and schema
        and schema["can_create"]
        and schema["can_manage_acl"]
        and report.get("database_owner", {}).get("current_role_owns_database")
        and history
        and history["state"] in {"NOT_INITIALIZED", "PENDING", "CHECKSUMS_MATCH"}
        and not role_conflicts
        and not (history["state"] == "NOT_INITIALIZED" and existing)
    )


def _status_exit_code(status: str) -> int:
    if status in {"CATALOG_PREFLIGHT_READ_ONLY", "MIGRATIONS_AND_RESTRICTED_SMOKE_PASS"}:
        return 0
    return 5


def _apply_migrations(
    config: DatabaseConfig,
    *,
    set_phase: Callable[[str], None] | None = None,
) -> dict[str, object]:
    from .database import connect_database

    if set_phase:
        set_phase("role_bootstrap")
    bootstrap_path = Path(__file__).resolve().parent.parent / "security" / "postgresql" / "role_bootstrap.sql"
    bootstrap_sql = bootstrap_path.read_text(encoding="utf-8")
    connection = connect_database(config)
    try:
        with connection.transaction():
            for statement in split_sql_statements(bootstrap_sql):
                connection.raw_connection.execute(statement)
    finally:
        connection.close()

    if set_phase:
        set_phase("migration_runner")
    result = run_postgresql_migrations(config)
    if set_phase:
        set_phase("schema_verification")
    verified = verify_postgresql_schema(config)
    if set_phase:
        set_phase("post_migration_catalog")
    catalog_connection, catalog = _connect_read_only(config)
    catalog_connection.close()

    tables = {row["table_name"]: row for row in catalog["application_tables"]}
    required_tables = set(APP_TABLES)
    protected_tables = required_tables - {"retaniq_schema_migrations"}
    role_rows = {row["rolname"]: row for row in catalog["roles"]}
    functions = catalog["authentication_functions"]
    catalog_pass = bool(
        catalog["migration_history"]["state"] == "CHECKSUMS_MATCH"
        and required_tables.issubset(tables)
        and all(tables[name]["rls_enabled"] and tables[name]["rls_forced"] for name in protected_tables)
        and all(
            name in role_rows and not role_rows[name]["rolcanlogin"]
            and not role_rows[name]["rolsuper"] and not role_rows[name]["rolbypassrls"]
            and not role_rows[name]["rolinherit"]
            for name in CAPABILITY_ROLES
        )
        and len(functions) == 2
        and all(item["owner"] == "retaniq_authenticator" and item["security_definer"] for item in functions)
    )
    security_smoke: dict[str, object] = {
        "status": "NOT_RUN_CATALOG_GAP",
        "restricted_roles_tested": [],
        "passed_scenarios": [],
        "failed_scenario": None,
        "cleanup": "NOT_APPLICABLE",
    }
    if catalog_pass:
        if set_phase:
            set_phase("restricted_login_smoke")
        security_smoke = _remote_security_smoke(config)
    overall_pass = catalog_pass and security_smoke["status"] == "PASS"
    return {
        "status": "MIGRATIONS_AND_RESTRICTED_SMOKE_PASS" if overall_pass else "DEPLOYED_BUT_SECURITY_GATES_INCOMPLETE",
        "project_ref": PROJECT_REF,
        "connection_mode": "SESSION_POOLER",
        "applied_versions": list(result.applied_versions),
        "current_version": verified.current_version,
        "catalog_checks_passed": catalog_pass,
        "restricted_role_smoke": security_smoke,
        "catalog": catalog,
        "mutations_performed": True,
    }


def _connect_restricted_smoke_login(role_name: str, password: str) -> Any:
    import psycopg

    return psycopg.connect(
        host=DEFAULT_HOST,
        port=5432,
        dbname="postgres",
        user=f"{role_name}.{PROJECT_REF}",
        password=password,
        sslmode="require",
        connect_timeout=15,
        application_name="retainiq_remote_rls_smoke",
        prepare_threshold=None,
        # Keep transaction() contexts top-level. With autocommit disabled,
        # the initial identity SELECT opens an implicit outer transaction;
        # later transaction() blocks would then be savepoints, not commits.
        autocommit=True,
    )


def _remote_security_smoke(config: DatabaseConfig) -> dict[str, object]:
    """Run compact remote checks through actual temporary restricted LOGINs."""
    import psycopg
    from psycopg import sql

    suffix = uuid4().hex[:10]
    prefix = f"riq_probe_{suffix}"
    tenant_a, tenant_b = f"{prefix}_a", f"{prefix}_b"
    customer_a, customer_b = f"{prefix}_customer_a", f"{prefix}_customer_b"
    write_customer = f"{prefix}_backend_write"
    snapshot_id = f"{prefix}_snapshot"
    capability_for = {
        "backend": "retaniq_backend",
        "artifact_writer": "retaniq_artifact_writer",
        "dashboard_reader": "retaniq_dashboard_reader",
        "maintenance": "retaniq_maintenance",
    }
    credentials = {
        purpose: (f"{prefix}_{purpose}", secrets.token_urlsafe(32))
        for purpose in capability_for
    }
    admin = psycopg.connect(config.postgresql_dsn, connect_timeout=15, autocommit=True)
    created_roles: list[str] = []
    open_connections: list[Any] = []
    passed: list[str] = []
    failed: str | None = None

    def connect_as(role_name: str, password: str) -> Any:
        connection = _connect_restricted_smoke_login(role_name, password)
        open_connections.append(connection)
        return connection

    def expect_denied(connection: Any, statement: str, parameters: tuple[Any, ...] = ()) -> None:
        connection.execute("SAVEPOINT retainiq_probe_denial")
        try:
            connection.execute(statement, parameters)
        except psycopg.errors.InsufficientPrivilege:
            connection.execute("ROLLBACK TO SAVEPOINT retainiq_probe_denial")
            connection.execute("RELEASE SAVEPOINT retainiq_probe_denial")
            return
        connection.execute("ROLLBACK TO SAVEPOINT retainiq_probe_denial")
        connection.execute("RELEASE SAVEPOINT retainiq_probe_denial")
        raise AssertionError("restricted role unexpectedly completed a denied operation")

    try:
        for purpose, capability in capability_for.items():
            role_name, password = credentials[purpose]
            admin.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 2 PASSWORD {}"
                ).format(sql.Identifier(role_name), sql.Literal(password))
            )
            created_roles.append(role_name)
            admin.execute(
                sql.SQL("GRANT {} TO {}").format(sql.Identifier(capability), sql.Identifier(role_name))
            )

        admin.execute("INSERT INTO tenants(tenant_id) VALUES (%s), (%s)", (tenant_a, tenant_b))
        admin.execute(
            "INSERT INTO customers(tenant_id, customer_id, created_at) "
            "VALUES (%s, %s, CURRENT_TIMESTAMP), (%s, %s, CURRENT_TIMESTAMP)",
            (tenant_a, customer_a, tenant_b, customer_b),
        )

        backend_name, backend_password = credentials["backend"]
        backend = connect_as(backend_name, backend_password)
        if backend.execute("SELECT current_user").fetchone()[0] != backend_name:
            raise AssertionError("backend test connection did not authenticate as its restricted login")
        role_flags = admin.execute(
            "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_catalog.pg_roles WHERE rolname=%s",
            (backend_name,),
        ).fetchone()
        if role_flags != (False, False, False, False):
            raise AssertionError("backend probe login has an unsafe role attribute")
        with backend.transaction():
            if backend.execute(
                "SELECT count(*) FROM customers WHERE customer_id = ANY(%s)",
                ([customer_a, customer_b],),
            ).fetchone()[0] != 0:
                raise AssertionError("backend role could read customers without tenant context")
            backend.execute("SELECT set_config('retaniq.tenant_id', %s, true)", (tenant_a,))
            visible = backend.execute(
                "SELECT customer_id FROM customers WHERE customer_id = ANY(%s) ORDER BY customer_id",
                ([customer_a, customer_b],),
            ).fetchall()
            if visible != [(customer_a,)]:
                raise AssertionError("backend tenant context did not isolate customer reads")
            backend.execute("SELECT set_config('retaniq.tenant_id', %s, true)", (tenant_b,))
            spoofed = backend.execute(
                "SELECT customer_id FROM customers WHERE customer_id = %s", (customer_b,),
            ).fetchone()
            if spoofed != (customer_b,):
                raise AssertionError("shared-role tenant-context spoofability was not reproduced")
            passed.append("shared_backend_role_can_spoof_tenant_guc_LIMITATION_CONFIRMED")
            backend.execute("SELECT set_config('retaniq.tenant_id', %s, true)", (tenant_a,))
            expect_denied(
                backend,
                "INSERT INTO customers(tenant_id, customer_id, created_at) VALUES (%s,%s,CURRENT_TIMESTAMP)",
                (tenant_b, f"{prefix}_forged"),
            )
            expect_denied(
                backend,
                "UPDATE customers SET tenant_id=%s WHERE customer_id=%s RETURNING customer_id",
                (tenant_b, customer_a),
            )
            if backend.execute(
                "INSERT INTO customers(tenant_id, customer_id, created_at) "
                "VALUES (%s,%s,CURRENT_TIMESTAMP) RETURNING customer_id",
                (tenant_a, write_customer),
            ).fetchone()[0] != write_customer:
                raise AssertionError("backend role could not perform its tenant-scoped write")
            passed.extend(("backend_default_deny", "backend_tenant_select", "cross_tenant_insert_denied", "ownership_update_denied", "backend_own_insert_returning"))
        with backend.transaction():
            if backend.execute(
                "SELECT count(*) FROM customers WHERE customer_id = ANY(%s)",
                ([customer_a, customer_b, write_customer],),
            ).fetchone()[0] != 0:
                raise AssertionError("transaction-local tenant context leaked after commit")
            passed.append("backend_context_cleared_after_commit")
            expect_denied(backend, "SET ROLE retaniq_maintenance")
            passed.append("backend_cannot_assume_maintenance")

        artifact_name, artifact_password = credentials["artifact_writer"]
        artifact = connect_as(artifact_name, artifact_password)
        if artifact.execute("SELECT current_user").fetchone()[0] != artifact_name:
            raise AssertionError("artifact test connection did not authenticate as its restricted login")
        with artifact.transaction():
            artifact.execute("SELECT set_config('retaniq.tenant_id', %s, true)", (tenant_a,))
            if artifact.execute(
                "INSERT INTO feature_snapshots(feature_snapshot_id,tenant_id,customer_id,as_of,feature_version,"
                "data_cutoff_at,features_json,data_quality_status) "
                "VALUES (%s,%s,%s,CURRENT_TIMESTAMP,'probe-v1',CURRENT_TIMESTAMP,'{}','complete') "
                "RETURNING feature_snapshot_id",
                (snapshot_id, tenant_a, customer_a),
            ).fetchone()[0] != snapshot_id:
                raise AssertionError("artifact writer could not insert its tenant-scoped snapshot")
            expect_denied(artifact, "SELECT count(*) FROM canonical_events")
            passed.extend(("artifact_tenant_write", "artifact_writer_cannot_read_events"))

        dashboard_name, dashboard_password = credentials["dashboard_reader"]
        dashboard = connect_as(dashboard_name, dashboard_password)
        with dashboard.transaction():
            dashboard.execute("SELECT set_config('retaniq.tenant_id', %s, true)", (tenant_a,))
            if dashboard.execute(
                "SELECT customer_id FROM customers WHERE customer_id = %s", (customer_a,),
            ).fetchone() != (customer_a,):
                raise AssertionError("dashboard reader could not read its tenant customer")
            expect_denied(
                dashboard,
                "INSERT INTO customers(tenant_id, customer_id, created_at) VALUES (%s,%s,CURRENT_TIMESTAMP)",
                (tenant_a, f"{prefix}_dashboard_write"),
            )
            passed.extend(("dashboard_tenant_read", "dashboard_write_denied"))

        maintenance_name, maintenance_password = credentials["maintenance"]
        maintenance = connect_as(maintenance_name, maintenance_password)
        with maintenance.transaction():
            maintenance.execute("SELECT set_config('retaniq.tenant_id', %s, true)", (tenant_a,))
            deleted = maintenance.execute(
                "DELETE FROM customers WHERE customer_id=%s RETURNING customer_id", (customer_b,),
            ).fetchall()
            if deleted:
                raise AssertionError("maintenance role deleted another tenant's customer")
            passed.append("maintenance_cross_tenant_delete_denied")
    except Exception as error:
        failed = f"{type(error).__name__}"
    finally:
        for connection in open_connections:
            try:
                connection.close()
            except Exception:
                pass
        try:
            admin.execute("DELETE FROM feature_snapshots WHERE feature_snapshot_id=%s", (snapshot_id,))
            admin.execute(
                "DELETE FROM customers WHERE tenant_id = ANY(%s)", ([tenant_a, tenant_b],),
            )
            admin.execute("DELETE FROM tenants WHERE tenant_id = ANY(%s)", ([tenant_a, tenant_b],))
        except Exception:
            if failed is None:
                failed = "FixtureCleanupError"
        for role_name in reversed(created_roles):
            try:
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))
            except Exception:
                if failed is None:
                    failed = "TemporaryRoleCleanupError"
        admin.close()
    return {
        "status": "PASS" if failed is None and len(passed) >= 12 else "FAIL",
        "restricted_roles_tested": sorted(credentials),
        "passed_scenarios": passed,
        "failed_scenario": failed,
        "cleanup": "ATTEMPTED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument(
        "--deploy", action="store_true",
        help="after a clean read-only preflight and explicit console confirmation, bootstrap roles and apply migrations",
    )
    args = parser.parse_args()
    password = getpass.getpass("Supabase migration database password: ")
    connection = None
    phase = "read_only_preflight"
    mutation_attempted = False

    def update_phase(value: str) -> None:
        nonlocal phase
        phase = value

    try:
        config = _safe_config(args.host, args.user, password)
        connection, result = _connect_read_only(config)
        connection.close()
        connection = None
        if args.deploy:
            if not _deployment_gate(result):
                print(json.dumps({
                    "status": "BLOCKED_PREFLIGHT_GATE",
                    "project_ref": PROJECT_REF,
                    "mutations_performed": False,
                    "preflight": result,
                }, sort_keys=True, separators=(",", ":")))
                return 3
            print(json.dumps({
                "status": "PREFLIGHT_PASSED_AWAITING_RECOVERY_CONFIRMATION",
                "project_ref": PROJECT_REF,
                "migration_history": result["migration_history"],
                "application_table_count": len(result["application_tables"]),
                "recovery_point": result["recovery_point"],
                "mutations_performed": False,
            }, sort_keys=True, separators=(",", ":")))
            confirmation = input(
                "Confirm this dedicated demo is backed up or disposable/rebuildable; "
                f"type DEPLOY {PROJECT_REF} to apply migrations 001-007: "
            )
            if confirmation != f"DEPLOY {PROJECT_REF}":
                print(json.dumps({
                    "status": "CANCELLED",
                    "project_ref": PROJECT_REF,
                    "mutations_performed": False,
                }, sort_keys=True, separators=(",", ":")))
                return 4
            mutation_attempted = True
            result = _apply_migrations(config, set_phase=update_phase)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return _status_exit_code(result["status"])
    except Exception as error:
        sqlstate, diagnostic_message = _safe_migration_diagnostic(error)
        failure: dict[str, object] = {
            "status": "BLOCKED",
            "project_ref": PROJECT_REF,
            "error_class": type(error).__name__,
            "phase": phase,
            "mutations_performed": mutation_attempted,
            "mutation_status": "MAY_HAVE_OCCURRED" if mutation_attempted else "NONE",
        }
        if sqlstate:
            failure["sqlstate"] = sqlstate
        if diagnostic_message:
            failure["diagnostic_message"] = diagnostic_message
        if isinstance(error, PostgreSQLMigrationExecutionError):
            failure.update({
                "migration_version": error.version,
                "statement_index": error.statement_index,
                "operation": error.operation,
                "sqlstate": error.sqlstate,
                "diagnostic_message": error.diagnostic_message,
            })
        print(json.dumps(failure, sort_keys=True, separators=(",", ":")))
        return 2
    finally:
        if connection is not None:
            connection.close()
        password = ""


if __name__ == "__main__":
    raise SystemExit(main())
