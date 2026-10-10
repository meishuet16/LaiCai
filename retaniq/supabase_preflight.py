"""Read-only Supabase demo connection and migration-readiness diagnostic."""

from __future__ import annotations

import json
from typing import Mapping

from .database import DatabaseConnection, DatabaseDriverUnavailable, connect_database
from .database_config import (
    DATABASE_BACKEND_ENV,
    SUPABASE_BACKEND,
    DatabaseConfig,
    DatabaseConfigurationError,
)
from .postgresql_migrations import MigrationHistoryError, discover_migrations, plan_migrations


DATABASE_ROLE_PLAN = frozenset({
    "schema_migration",
    "backend_application",
    "tenant_scoped_inference_reader",
    "model_artifact_writer",
    "decision_engine_service",
    "read_only_dashboard",
    "administrative_maintenance",
})

RLS_TABLE_OWNERSHIP = {
    "tenants": "tenant_id",
    "integrations": "tenant_id",
    "customers": "tenant_id",
    "customer_identities": "tenant_id",
    "canonical_events": "tenant_id",
    "usage_events": "tenant_id",
    "billing_events": "tenant_id",
    "subscriptions": "tenant_id",
    "subscription_events": "tenant_id",
    "feature_snapshots": "tenant_id",
    "churn_labels": "tenant_id",
    "predictions": "tenant_id",
    "service_principals": "tenant_id",
    "subscription_owners": "tenant_id",
    "integration_event_categories": "tenant_id",
    "observation_coverage": "tenant_id",
    "dataset_identity": "singleton_global_synthetic_provenance",
    "synthetic_import_checkpoints": "dataset_id_global_operational_state",
    "retaniq_schema_migrations": "migration_schema_metadata",
}
PREFLIGHT_REQUIRED_APP_PRIVILEGES = {
    "integrations": ("SELECT",),
    "service_principals": ("SELECT",),
}


def _migration_readiness(connection: DatabaseConnection) -> str:
    migrations = discover_migrations()
    connection.execute("SET TRANSACTION READ ONLY")
    row = connection.execute(
        "SELECT to_regclass(?) AS migration_table",
        ("public.retaniq_schema_migrations",),
    ).fetchone()
    if row is None or row["migration_table"] is None:
        return "NOT_INITIALIZED"
    rows = connection.execute(
        'SELECT version, checksum FROM "public"."retaniq_schema_migrations" ORDER BY version',
    ).fetchall()
    applied = {str(item["version"]): str(item["checksum"]).strip() for item in rows}
    try:
        if plan_migrations(migrations, applied):
            return "INCOMPLETE_OR_PENDING"
    except MigrationHistoryError:
        return "CHECKSUM_OR_HISTORY_MISMATCH"
    return "CHECKSUMS_MATCH"


def preflight(
    environ: Mapping[str, str] | None = None,
    *,
    connector=connect_database,
) -> dict[str, object]:
    """Probe only explicitly configured Supabase demo targets; never writes."""
    if environ is not None and environ.get(DATABASE_BACKEND_ENV, "").strip().casefold() != SUPABASE_BACKEND:
        return {
            "status": "BLOCKED",
            "remote_connectivity": "BLOCKED",
            "reason": "explicit_supabase_demo_target_required",
        }
    try:
        config = DatabaseConfig.from_environment(environ)
    except DatabaseConfigurationError:
        return {
            "status": "BLOCKED",
            "remote_connectivity": "BLOCKED",
            "reason": "supabase_demo_configuration_missing_or_invalid",
        }
    if not config.is_supabase:
        return {
            "status": "BLOCKED",
            "remote_connectivity": "BLOCKED",
            "reason": "explicit_supabase_demo_target_required",
        }

    report: dict[str, object] = {
        "status": "BLOCKED",
        "remote_connectivity": "BLOCKED",
        "deployment_environment": "supabase_demo",
        "project_ref": config.expected_project_ref,
        "connection_mode": config.connection_mode,
        "tls": config.tls_verification,
        "driver_available": False,
        "application_connection": "NOT_ATTEMPTED",
        "migration_connection": "NOT_ATTEMPTED",
        "migration_readiness": "NOT_CHECKED",
        "application_role_rls_bypass": "NOT_CHECKED",
        "application_privileges": "NOT_CHECKED",
        "application_privileges_missing": [],
        "database": None,
        "server_version": None,
        "application_role": None,
        "migration_role": None,
    }
    try:
        import psycopg  # noqa: F401 - explicit availability check before network access
    except ImportError:
        report["reason"] = "postgresql_driver_unavailable"
        return report
    report["driver_available"] = True

    app_connection: DatabaseConnection | None = None
    migration_connection: DatabaseConnection | None = None
    try:
        app_connection = connector(config)
        with app_connection.transaction():
            app_connection.execute("SET TRANSACTION READ ONLY")
            app_connection.execute("SELECT 1 AS probe").fetchone()
            identity = app_connection.execute(
                "SELECT current_database() AS database, current_user AS role, version() AS server_version, "
                "rolsuper, rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname = current_user",
            ).fetchone()
            if identity is None:
                report["application_connection"] = "CONNECTED_ROLE_METADATA_UNAVAILABLE"
            else:
                report["application_connection"] = "CONNECTED"
                report["database"] = identity["database"]
                report["server_version"] = identity["server_version"]
                report["application_role"] = identity["role"]
                report["application_role_rls_bypass"] = bool(
                    identity["rolsuper"] or identity["rolbypassrls"],
                )
            privilege_rows = app_connection.execute(
                "SELECT required.table_name, required.privilege, "
                "(relation.oid IS NOT NULL AND has_table_privilege(current_user, relation.oid, required.privilege)) "
                "AS granted FROM (VALUES "
                "('integrations', 'SELECT'), ('service_principals', 'SELECT')"
                ") AS required(table_name, privilege) "
                "LEFT JOIN pg_catalog.pg_namespace AS namespace ON namespace.nspname = 'public' "
                "LEFT JOIN pg_catalog.pg_class AS relation ON relation.relnamespace = namespace.oid "
                "AND relation.relname = required.table_name",
            ).fetchall()
            missing = [
                f"public.{item['table_name']}:{item['privilege']}"
                for item in privilege_rows if not item["granted"]
            ]
            report["application_privileges_missing"] = missing
            report["application_privileges"] = "MISSING" if missing else "MINIMUM_PRESENT"

        migration_config = config.for_migrations()
        migration_connection = connector(migration_config)
        with migration_connection.transaction():
            readiness = _migration_readiness(migration_connection)
            role = migration_connection.execute("SELECT current_user AS role").fetchone()
            report["migration_role"] = role["role"] if role else None
        report["migration_readiness"] = readiness
        report["migration_connection"] = "CONNECTED"
        report["remote_connectivity"] = "CONNECTED_READ_ONLY"
        if (
            report["application_connection"] == "CONNECTED"
            and report["application_role_rls_bypass"] is False
            and report["application_privileges"] == "MINIMUM_PRESENT"
            and readiness == "CHECKSUMS_MATCH"
        ):
            report["status"] = "PREFLIGHT_PASSED_NOT_DEPLOYMENT_APPROVAL"
        else:
            report["status"] = "CONNECTED_WITH_READINESS_GAPS"
    except Exception as error:
        # Driver exceptions may contain the DSN. Only expose the safe class and
        # a static reason; do not stringify the exception or its traceback.
        report["reason"] = (
            "postgresql_driver_unavailable" if isinstance(error, DatabaseDriverUnavailable)
            else "read_only_preflight_failed"
        )
    finally:
        for connection in (app_connection, migration_connection):
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
    return report


def main() -> int:
    result = preflight()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["remote_connectivity"] == "CONNECTED_READ_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
