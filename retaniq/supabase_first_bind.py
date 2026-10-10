"""One-time, operator-confirmed Supabase runtime-login provisioning and first bind.

This is not a migration runner and is not a routine import connection. The
privileged migration login is used only to inspect the complete catalog, create
two restricted LOGINs, and atomically bind an empty destination to the approved
STANDARD manifest. Tenant data remains the responsibility of the existing
backend/maintenance importer.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import gzip
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from .database_config import DatabaseConfig
from .postgresql_migrations import (
    MigrationHistoryError,
    discover_migrations,
    plan_migrations,
    _safe_migration_diagnostic,
)
from .secret_store import load_dpapi_secret, store_dpapi_secret
from .supabase_remote_preflight import (
    APP_TABLES,
    CAPABILITY_ROLES,
    DEFAULT_HOST,
    DEFAULT_USER,
    PROJECT_REF,
    PROJECT_URL,
    _safe_config,
)
from .synthetic.validator import validate_dataset


APP_LOGIN = "retainiq_backend_login"
MAINTENANCE_LOGIN = "retainiq_maintenance_login"
LOGIN_CAPABILITIES = {
    APP_LOGIN: "retaniq_backend",
    MAINTENANCE_LOGIN: "retaniq_maintenance",
}
TENANT_ID = "tenant-01"
APPROVED_DATASET_ID = "synthetic-saas-v1-2-standard-s2026-970a9d231e68"
DEFAULT_DATASET = (
    Path.home() / "RetainIQ-private" / "synthetic_saas_v1_2" / "standard"
    / APPROVED_DATASET_ID
)
TENANT_TABLES = (
    "tenants", "integrations", "customers", "customer_identities", "canonical_events",
    "usage_events", "billing_events", "subscriptions", "subscription_events",
    "feature_snapshots", "churn_labels", "predictions", "service_principals",
    "subscription_owners", "integration_event_categories", "observation_coverage",
)
GLOBAL_TABLES = ("dataset_identity", "synthetic_import_checkpoints")
RLS_TABLES = tuple(name for name in APP_TABLES if name != "retaniq_schema_migrations")
STREAM_LIMITS = {
    "canonical-events-tenant-01": "canonical_events",
    "canonical-replay-tenant-01": "canonical_events",
    "observation-coverage-tenant-01": "observation_coverage",
    "observation-coverage-replay-tenant-01": "observation_coverage",
}
IDENTITY_FIELDS = (
    "dataset_id", "dataset_version", "dataset_type", "target_policy_version",
    "generator_version", "manifest_sha256",
)
EXPECTED_MIGRATION_VERSIONS = tuple(f"{number:03d}" for number in range(1, 8))
LOCKED_TABLES = tuple(sorted(APP_TABLES))


class FirstBindBlocked(ValueError):
    """A sanitized, fail-closed first-bind condition."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _validate_tenant_scope(tenant_id: str) -> None:
    if tenant_id != TENANT_ID:
        raise FirstBindBlocked("tenant_scope_must_be_tenant_01")


def credential_store_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "RetainIQ" / "supabase-demo" / f"{PROJECT_REF}-runtime-logins.dpapi"


def _manifest_plan(dataset_path: Path, tenant_id: str) -> dict[str, Any]:
    _validate_tenant_scope(tenant_id)
    validation = validate_dataset(dataset_path)
    if validation.get("status") != "PASS":
        raise FirstBindBlocked("standard_dataset_validation_failed")
    manifest_path = dataset_path / "dataset_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (
        manifest.get("dataset_id") != APPROVED_DATASET_ID
        or manifest.get("profile") != "standard"
        or manifest.get("dataset_type") != "synthetic_saas"
        or manifest.get("track") != "synthetic_saas"
        or manifest.get("no_real_customer_data") is not True
    ):
        raise FirstBindBlocked("dataset_is_not_the_approved_standard_manifest")

    customers: set[str] = set()
    with (dataset_path / "customers.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("tenant_id") == tenant_id:
                customers.add(row["customer_id"])

    identities: dict[tuple[str, str], str] = {}
    sources: dict[str, str] = {}
    with (dataset_path / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("tenant_id") == tenant_id:
                identities[(row["source"], row["external_customer_id"])] = row["customer_id"]
                source = row["source"]
                category = row["source_category"]
                previous = sources.setdefault(source, category)
                if previous != category:
                    raise FirstBindBlocked("dataset_source_category_conflict")

    event_counts = {"usage": 0, "billing": 0, "subscription": 0}
    subscription_ids: set[str] = set()
    subscription_owners: set[tuple[str, str]] = set()
    event_rows = 0
    with (dataset_path / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("tenant_id") != tenant_id:
                continue
            event_rows += 1
            category = row["source_category"]
            if category not in event_counts:
                raise FirstBindBlocked("dataset_event_category_invalid")
            event_counts[category] += 1
            try:
                attributes = json.loads(row["attributes_json"])
            except (KeyError, TypeError, json.JSONDecodeError):
                raise FirstBindBlocked("dataset_event_payload_invalid") from None
            subscription_id = attributes.get("subscription_id")
            if subscription_id:
                subscription_ids.add(subscription_id)
                subscription_owners.add((subscription_id, row["customer_id"]))

    coverage_rows = 0
    with gzip.open(dataset_path / "observation_coverage.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("tenant_id") == tenant_id:
                coverage_rows += 1

    scope_counts = {
        "tenants": 1,
        "integrations": len(sources),
        "customers": len(customers),
        "customer_identities": len(identities),
        "canonical_events": event_rows,
        "usage_events": event_counts["usage"],
        "billing_events": event_counts["billing"],
        "subscriptions": len(subscription_ids),
        "subscription_events": event_counts["subscription"],
        "feature_snapshots": 0,
        "churn_labels": 0,
        "predictions": 0,
        "service_principals": 1,
        "subscription_owners": len(subscription_owners),
        "integration_event_categories": len(sources),
        "observation_coverage": coverage_rows,
    }
    identity = {
        "dataset_id": manifest["dataset_id"],
        "dataset_version": manifest["dataset_version"],
        "dataset_type": manifest["dataset_type"],
        "target_policy_version": manifest["target_policy_version"],
        "generator_version": manifest["generator_code_version"],
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    return {
        "identity": identity,
        "scope_counts": scope_counts,
        "customer_ids": customers,
        "identity_map": identities,
        "sources": sources,
        "subscription_ids": subscription_ids,
        "subscription_owners": subscription_owners,
        "event_rows": event_rows,
        "coverage_rows": coverage_rows,
    }


def _identity_matches(existing: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    return all(existing.get(field) == expected[field] for field in IDENTITY_FIELDS)


def _classify_destination(
    *,
    identity: Mapping[str, Any] | None,
    table_counts: Mapping[str, int],
    tenant_counts: Mapping[str, Mapping[str, int]],
    checkpoints: list[Mapping[str, Any]],
    expected_identity: Mapping[str, Any],
    scope_counts: Mapping[str, int],
) -> str:
    if identity is None:
        has_tenant_rows = any(int(table_counts.get(table, 0)) for table in TENANT_TABLES)
        has_checkpoints = bool(checkpoints or table_counts.get("synthetic_import_checkpoints", 0))
        if has_tenant_rows or has_checkpoints or table_counts.get("dataset_identity", 0):
            raise FirstBindBlocked("unbound_destination_contains_data")
        return "EMPTY_DESTINATION"

    if not _identity_matches(identity, expected_identity):
        raise FirstBindBlocked("dataset_identity_mismatch")
    if table_counts.get("dataset_identity") != 1:
        raise FirstBindBlocked("dataset_identity_cardinality_invalid")

    for table in TENANT_TABLES:
        tenants = tenant_counts.get(table, {})
        if any(tenant != TENANT_ID and int(count) > 0 for tenant, count in tenants.items()):
            raise FirstBindBlocked("cross_tenant_rows_present")
        if int(table_counts.get(table, 0)) > int(scope_counts.get(table, 0)):
            raise FirstBindBlocked("tenant_table_exceeds_manifest_scope")

    if int(table_counts.get("feature_snapshots", 0)) or int(table_counts.get("churn_labels", 0)) or int(
        table_counts.get("predictions", 0)
    ):
        raise FirstBindBlocked("unexpected_model_artifact_rows_present")

    checkpoint_by_name: dict[str, Mapping[str, Any]] = {}
    for checkpoint in checkpoints:
        stream = str(checkpoint.get("stream_name", ""))
        if checkpoint.get("dataset_id") != expected_identity["dataset_id"] or stream not in STREAM_LIMITS:
            raise FirstBindBlocked("unexpected_import_checkpoint")
        if stream in checkpoint_by_name:
            raise FirstBindBlocked("duplicate_import_checkpoint")
        checkpoint_by_name[stream] = checkpoint
        last_row = int(checkpoint.get("last_row_number", -1))
        accepted = int(checkpoint.get("accepted_count", -1))
        duplicates = int(checkpoint.get("duplicate_count", -1))
        rejected = int(checkpoint.get("rejected_count", -1))
        maximum = int(scope_counts[STREAM_LIMITS[stream]])
        if last_row < 0 or last_row > maximum or min(accepted, duplicates, rejected) < 0:
            raise FirstBindBlocked("import_checkpoint_range_invalid")
        if rejected != 0 or accepted + duplicates != last_row:
            raise FirstBindBlocked("import_checkpoint_counters_inconsistent")
        if "replay" in stream and (accepted != 0 or duplicates != last_row):
            raise FirstBindBlocked("replay_checkpoint_inconsistent")

    for base, replay in (
        ("canonical-events-tenant-01", "canonical-replay-tenant-01"),
        ("observation-coverage-tenant-01", "observation-coverage-replay-tenant-01"),
    ):
        replay_checkpoint = checkpoint_by_name.get(replay)
        base_checkpoint = checkpoint_by_name.get(base)
        if replay_checkpoint and (
            base_checkpoint is None
            or int(replay_checkpoint["last_row_number"]) > int(base_checkpoint["last_row_number"])
        ):
            raise FirstBindBlocked("replay_checkpoint_exceeds_primary_checkpoint")

    event_checkpoint = checkpoint_by_name.get("canonical-events-tenant-01")
    coverage_checkpoint = checkpoint_by_name.get("observation-coverage-tenant-01")
    expected_event_count = int(event_checkpoint["accepted_count"]) if event_checkpoint else 0
    expected_coverage_count = int(coverage_checkpoint["accepted_count"]) if coverage_checkpoint else 0
    if int(table_counts.get("canonical_events", 0)) != expected_event_count:
        raise FirstBindBlocked("canonical_event_checkpoint_mismatch")
    if int(table_counts.get("observation_coverage", 0)) != expected_coverage_count:
        raise FirstBindBlocked("coverage_checkpoint_mismatch")
    return "MATCHING_TENANT01_RESUME"


def _validate_resumable_rows(
    connection: Any,
    plan: Mapping[str, Any],
    table_counts: Mapping[str, int],
) -> None:
    existing_customers = {
        row["customer_id"] for row in connection.execute(
            "SELECT customer_id FROM public.customers WHERE tenant_id = %s", (TENANT_ID,),
        ).fetchall()
    }
    if not existing_customers.issubset(plan["customer_ids"]):
        raise FirstBindBlocked("unexpected_customer_rows_present")

    existing_identities = {
        (row["source"], row["external_customer_id"]): row["customer_id"]
        for row in connection.execute(
            "SELECT source, external_customer_id, customer_id FROM public.customer_identities "
            "WHERE tenant_id = %s", (TENANT_ID,),
        ).fetchall()
    }
    if any(plan["identity_map"].get(key) != customer for key, customer in existing_identities.items()):
        raise FirstBindBlocked("unexpected_customer_identity_rows_present")

    sources = {
        row["source"] for row in connection.execute(
            "SELECT source FROM public.integrations WHERE tenant_id = %s", (TENANT_ID,),
        ).fetchall()
    }
    if not sources.issubset(plan["sources"]):
        raise FirstBindBlocked("unexpected_integration_source_present")

    categories = {
        (row["source"], row["category"])
        for row in connection.execute(
            "SELECT source, category FROM public.integration_event_categories WHERE tenant_id = %s",
            (TENANT_ID,),
        ).fetchall()
    }
    if any(plan["sources"].get(source) != category for source, category in categories):
        raise FirstBindBlocked("unexpected_source_category_present")

    owners = {
        (row["subscription_id"], row["customer_id"])
        for row in connection.execute(
            "SELECT subscription_id, customer_id FROM public.subscription_owners WHERE tenant_id = %s",
            (TENANT_ID,),
        ).fetchall()
    }
    if not owners.issubset(plan["subscription_owners"]):
        raise FirstBindBlocked("unexpected_subscription_owner_present")

    subscriptions = {
        (row["subscription_id"], row["customer_id"])
        for row in connection.execute(
            "SELECT subscription_id, customer_id FROM public.subscriptions WHERE tenant_id = %s",
            (TENANT_ID,),
        ).fetchall()
    }
    if not subscriptions.issubset(plan["subscription_owners"]):
        raise FirstBindBlocked("unexpected_subscription_projection_present")

    canonical_by_category = {
        row["category"]: int(row["row_count"])
        for row in connection.execute(
            "SELECT category, count(*) AS row_count FROM public.canonical_events "
            "WHERE tenant_id=%s GROUP BY category", (TENANT_ID,),
        ).fetchall()
    }
    for category, table in (
        ("usage", "usage_events"),
        ("billing", "billing_events"),
        ("subscription", "subscription_events"),
    ):
        if int(table_counts[table]) != canonical_by_category.get(category, 0):
            raise FirstBindBlocked("canonical_event_subtype_count_mismatch")

    principals = connection.execute(
        "SELECT role, authorized_sources_json, authorized_purposes_json "
        "FROM public.service_principals WHERE tenant_id = %s", (TENANT_ID,),
    ).fetchall()
    if len(principals) > 1:
        raise FirstBindBlocked("unexpected_service_principal_rows_present")
    for principal in principals:
        try:
            sources_json = json.loads(principal["authorized_sources_json"])
            purposes_json = json.loads(principal["authorized_purposes_json"])
        except (TypeError, json.JSONDecodeError):
            raise FirstBindBlocked("service_principal_grants_invalid") from None
        if (
            principal["role"] != "analyst"
            or sources_json != sorted(plan["sources"])
            or purposes_json != ["billing_valuation", "model_artifact_write", "retention_inference"]
        ):
            raise FirstBindBlocked("unexpected_service_principal_grants")


def _table_inventory(connection: Any) -> tuple[dict[str, Any], dict[str, dict[str, int]], dict[str, int]]:
    from psycopg import sql

    rows = connection.execute(
        "SELECT relation.relname AS table_name, pg_catalog.pg_get_userbyid(relation.relowner) AS owner, "
        "relation.relrowsecurity AS rls_enabled, relation.relforcerowsecurity AS rls_forced, "
        "EXISTS (SELECT 1 FROM pg_catalog.pg_attribute column_info WHERE column_info.attrelid=relation.oid "
        "AND column_info.attname='tenant_id' AND column_info.attnum>0 AND NOT column_info.attisdropped) AS has_tenant_id, "
        "(SELECT count(*) FROM pg_catalog.pg_policy policy WHERE policy.polrelid=relation.oid) AS policy_count "
        "FROM pg_catalog.pg_class relation JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relation.relnamespace "
        "WHERE namespace.nspname='public' AND relation.relkind IN ('r','p') AND relation.relname=ANY(%s) "
        "ORDER BY relation.relname", (list(APP_TABLES),),
    ).fetchall()
    inventory = {row["table_name"]: dict(row) for row in rows}
    if set(inventory) != set(APP_TABLES):
        raise FirstBindBlocked("application_table_inventory_incomplete")
    for table in RLS_TABLES:
        row = inventory[table]
        if not row["has_tenant_id"] and table in TENANT_TABLES:
            raise FirstBindBlocked("tenant_column_inventory_mismatch")
        if not row["rls_enabled"] or not row["rls_forced"] or int(row["policy_count"]) < 1:
            raise FirstBindBlocked("rls_catalog_gate_failed")

    counts: dict[str, int] = {}
    tenant_counts: dict[str, dict[str, int]] = {}
    for table in APP_TABLES:
        relation = sql.Identifier("public", table)
        counts[table] = int(connection.execute(
            sql.SQL("SELECT count(*) AS row_count FROM {}").format(relation),
        ).fetchone()["row_count"])
        if table in TENANT_TABLES:
            grouped = connection.execute(
                sql.SQL("SELECT tenant_id, count(*) AS row_count FROM {} GROUP BY tenant_id").format(relation),
            ).fetchall()
            tenant_counts[table] = {str(row["tenant_id"]): int(row["row_count"]) for row in grouped}
    return inventory, tenant_counts, counts


def _check_privileged_inspector(connection: Any) -> dict[str, Any]:
    role = connection.execute(
        "SELECT current_database() AS database, current_user AS role, role.rolsuper, role.rolcreaterole, "
        "role.rolbypassrls FROM pg_catalog.pg_roles role WHERE role.rolname=current_user",
    ).fetchone()
    if not role or role["database"] != "postgres" or not role["rolbypassrls"] or not role["rolcreaterole"]:
        raise FirstBindBlocked("migration_login_lacks_required_inspection_or_role_capability")
    if role["rolsuper"]:
        # Supabase's managed postgres login is expected to be a non-superuser;
        # BYPASSRLS and narrow ownership/CREATEROLE capabilities suffice here.
        raise FirstBindBlocked("unexpected_superuser_migration_login")

    owners = connection.execute(
        "SELECT relation.relname, pg_catalog.pg_get_userbyid(relation.relowner) AS owner "
        "FROM pg_catalog.pg_class relation JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relation.relnamespace "
        "WHERE namespace.nspname='public' AND relation.relkind IN ('r','p') AND relation.relname=ANY(%s)",
        (list(APP_TABLES),),
    ).fetchall()
    if any(row["owner"] != role["role"] for row in owners):
        raise FirstBindBlocked("migration_login_does_not_own_all_locked_tables")

    cap_rows = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolinherit "
        "FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)", (list(CAPABILITY_ROLES),),
    ).fetchall()
    capabilities = {row["rolname"]: row for row in cap_rows}
    if set(capabilities) != set(CAPABILITY_ROLES) or any(
        row["rolcanlogin"] or row["rolsuper"] or row["rolcreaterole"] or row["rolcreatedb"]
        or row["rolbypassrls"] or row["rolinherit"] for row in capabilities.values()
    ):
        raise FirstBindBlocked("capability_role_catalog_gate_failed")
    return dict(role)


def _migration_state(connection: Any) -> str:
    relation = connection.execute(
        "SELECT pg_catalog.to_regclass('public.retaniq_schema_migrations') AS relation",
    ).fetchone()["relation"]
    if relation is None:
        raise FirstBindBlocked("migration_history_missing")
    rows = connection.execute(
        'SELECT version, checksum FROM public.retaniq_schema_migrations ORDER BY version',
    ).fetchall()
    applied = {str(row["version"]): str(row["checksum"]).strip() for row in rows}
    try:
        pending = plan_migrations(discover_migrations(), applied)
    except MigrationHistoryError:
        raise FirstBindBlocked("migration_history_or_checksum_mismatch") from None
    if pending or tuple(sorted(applied)) != EXPECTED_MIGRATION_VERSIONS:
        raise FirstBindBlocked("all_seven_postgresql_migrations_must_be_applied")
    return "CHECKSUMS_MATCH"


def _snapshot(connection: Any, plan: Mapping[str, Any], *, read_only: bool) -> dict[str, Any]:
    if read_only:
        connection.execute("SET TRANSACTION READ ONLY")
    connection.execute("SET LOCAL row_security = off")
    role = _check_privileged_inspector(connection)
    if connection.execute("SELECT current_setting('row_security') AS mode").fetchone()["mode"] != "off":
        raise FirstBindBlocked("unfiltered_row_inspection_unavailable")
    _migration_state(connection)
    inventory, tenant_counts, counts = _table_inventory(connection)
    if any(row["owner"] != role["role"] for row in inventory.values()):
        raise FirstBindBlocked("migration_login_does_not_own_all_locked_tables")
    identity_rows = connection.execute(
        "SELECT singleton_id, dataset_id, dataset_version, dataset_type, target_policy_version, "
        "generator_version, manifest_sha256 FROM public.dataset_identity ORDER BY singleton_id",
    ).fetchall()
    if len(identity_rows) > 1:
        raise FirstBindBlocked("dataset_identity_cardinality_invalid")
    identity = dict(identity_rows[0]) if identity_rows else None
    checkpoints = [dict(row) for row in connection.execute(
        "SELECT dataset_id, stream_name, last_row_number, accepted_count, duplicate_count, rejected_count "
        "FROM public.synthetic_import_checkpoints ORDER BY dataset_id, stream_name",
    ).fetchall()]
    destination_state = _classify_destination(
        identity=identity,
        table_counts=counts,
        tenant_counts=tenant_counts,
        checkpoints=checkpoints,
        expected_identity=plan["identity"],
        scope_counts=plan["scope_counts"],
    )
    if destination_state == "MATCHING_TENANT01_RESUME":
        _validate_resumable_rows(connection, plan, counts)
    return {
        "role": role,
        "inventory": inventory,
        "table_counts": counts,
        "tenant_counts": tenant_counts,
        "identity": identity,
        "checkpoints": checkpoints,
        "destination_state": destination_state,
    }


def _login_name(base_name: str, host: str) -> str:
    return f"{base_name}.{PROJECT_REF}" if host.casefold().endswith(".pooler.supabase.com") else base_name


def _restricted_dsn(admin_dsn: str, base_name: str, password: str) -> str:
    parsed = urlsplit(admin_dsn)
    host = parsed.hostname or ""
    user = _login_name(base_name, host)
    port = parsed.port or 5432
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    return urlunsplit(("postgresql", netloc, parsed.path or "/postgres", parsed.query, ""))


def _load_or_prepare_credentials(
    admin_dsn: str,
    existing_logins: Mapping[str, bool],
) -> tuple[dict[str, Any], bool]:
    path = credential_store_path()
    if path.exists():
        try:
            payload = json.loads(load_dpapi_secret(path))
        except (OSError, ValueError, json.JSONDecodeError):
            raise FirstBindBlocked("protected_runtime_credential_store_unreadable") from None
        if payload.get("project_ref") != PROJECT_REF or set(payload.get("logins", {})) != set(LOGIN_CAPABILITIES):
            raise FirstBindBlocked("protected_runtime_credential_store_project_mismatch")
        return payload, True

    parsed = urlsplit(admin_dsn)
    host = parsed.hostname or ""
    passwords: dict[str, str] = {}
    for login, exists in existing_logins.items():
        if exists:
            prompt = f"Existing {login} password (input hidden): "
            password = getpass.getpass(prompt)
            if not password:
                raise FirstBindBlocked("existing_runtime_login_password_required")
            passwords[login] = password
        else:
            passwords[login] = secrets.token_urlsafe(36)
    payload = {
        "project_ref": PROJECT_REF,
        "connection_mode": "SESSION_POOLER" if host.casefold().endswith(".pooler.supabase.com") else "DIRECT",
        "project_url": PROJECT_URL,
        "logins": {
            login: {
                "database_role": login,
                "username": _login_name(login, host),
                "password": password,
                "dsn": _restricted_dsn(admin_dsn, login, password),
                "capability": LOGIN_CAPABILITIES[login],
            }
            for login, password in passwords.items()
        },
    }
    return payload, False


def _role_catalog(connection: Any) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolreplication, "
        "rolbypassrls, rolinherit FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)",
        (list(LOGIN_CAPABILITIES),),
    ).fetchall()
    result: dict[str, Any] = {}
    for row in rows:
        memberships = connection.execute(
            "SELECT granted.rolname AS role_name, membership.inherit_option, membership.set_option, "
            "membership.admin_option FROM pg_catalog.pg_auth_members membership "
            "JOIN pg_catalog.pg_roles granted ON granted.oid=membership.roleid "
            "WHERE membership.member=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=%s)",
            (row["rolname"],),
        ).fetchall()
        result[row["rolname"]] = {**dict(row), "memberships": [dict(item) for item in memberships]}
    return result


def _validate_existing_login(role: Mapping[str, Any], capability: str) -> bool:
    if (
        not role["rolcanlogin"] or role["rolsuper"] or role["rolcreaterole"] or role["rolcreatedb"]
        or role["rolreplication"] or role["rolbypassrls"] or not role["rolinherit"]
    ):
        raise FirstBindBlocked("existing_runtime_login_has_unsafe_attributes")
    memberships = role["memberships"]
    if any(item["role_name"] != capability or item["admin_option"] for item in memberships):
        raise FirstBindBlocked("existing_runtime_login_has_unexpected_membership")
    if memberships and (
        len(memberships) != 1 or not memberships[0]["inherit_option"]
    ):
        raise FirstBindBlocked("existing_runtime_login_membership_invalid")
    return bool(
        memberships and memberships[0]["set_option"] is False
        and memberships[0]["admin_option"] is False
    )


def _provision_logins(connection: Any, payload: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    from psycopg import sql

    provisioned: list[str] = []
    changed: list[str] = []
    with connection.transaction():
        roles = _role_catalog(connection)
        for login, capability in LOGIN_CAPABILITIES.items():
            role = roles.get(login)
            if role is None:
                password = payload["logins"][login]["password"]
                connection.execute(sql.SQL(
                    "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 10 PASSWORD {}"
                ).format(sql.Identifier(login), sql.Literal(password)))
                provisioned.append(login)
                changed.append(login)
            elif not _validate_existing_login(role, capability):
                changed.append(login)
            connection.execute(sql.SQL(
                "GRANT {} TO {} WITH INHERIT TRUE, SET FALSE, ADMIN FALSE"
            ).format(sql.Identifier(capability), sql.Identifier(login)))
    return provisioned, changed


def _expect_denied(connection: Any, statement: str) -> None:
    connection.execute("SAVEPOINT retainiq_first_bind_denial")
    try:
        connection.execute(statement)
    except Exception as error:
        if getattr(error, "sqlstate", None) != "42501":
            connection.execute("ROLLBACK TO SAVEPOINT retainiq_first_bind_denial")
            connection.execute("RELEASE SAVEPOINT retainiq_first_bind_denial")
            raise
        connection.execute("ROLLBACK TO SAVEPOINT retainiq_first_bind_denial")
        connection.execute("RELEASE SAVEPOINT retainiq_first_bind_denial")
        return
    connection.execute("ROLLBACK TO SAVEPOINT retainiq_first_bind_denial")
    connection.execute("RELEASE SAVEPOINT retainiq_first_bind_denial")
    raise FirstBindBlocked("restricted_login_unexpectedly_allowed_privileged_operation")


def _privilege_contract(capability: str) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    if capability == "retaniq_backend":
        return (
            (("customers", "SELECT"), ("customers", "INSERT"), ("customers", "UPDATE")),
            (("customers", "DELETE"), ("dataset_identity", "SELECT"),
             ("synthetic_import_checkpoints", "SELECT"), ("retaniq_schema_migrations", "SELECT")),
        )
    if capability == "retaniq_maintenance":
        return (
            (("customers", "SELECT"), ("customers", "INSERT"), ("customers", "UPDATE"),
             ("customers", "DELETE"), ("dataset_identity", "SELECT"), ("dataset_identity", "INSERT"),
             ("dataset_identity", "UPDATE"), ("dataset_identity", "DELETE"),
             ("synthetic_import_checkpoints", "SELECT"), ("synthetic_import_checkpoints", "INSERT"),
             ("synthetic_import_checkpoints", "UPDATE"), ("synthetic_import_checkpoints", "DELETE")),
            (("retaniq_schema_migrations", "SELECT"),),
        )
    raise FirstBindBlocked("unsupported_runtime_capability")


def _verify_restricted_login(connection: Any, login: str, capability: str) -> None:
    current = connection.execute(
        "SELECT current_user AS login, pg_catalog.pg_has_role(current_user, %s, 'USAGE') AS has_capability",
        (capability,),
    ).fetchone()
    if current["login"] != login or not current["has_capability"]:
        raise FirstBindBlocked("restricted_login_identity_or_membership_failed")
    attributes = connection.execute(
        "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
        "FROM pg_catalog.pg_roles WHERE rolname=current_user",
    ).fetchone()
    if any(attributes[key] for key in attributes):
        raise FirstBindBlocked("restricted_login_has_privileged_role_attribute")
    create = connection.execute(
        "SELECT pg_catalog.has_schema_privilege(current_user, 'public', 'CREATE') AS can_create",
    ).fetchone()["can_create"]
    if create:
        raise FirstBindBlocked("restricted_login_can_create_in_public_schema")
    owns_protected_table = connection.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class relation "
        "JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relation.relnamespace "
        "WHERE namespace.nspname='public' AND relation.relname=ANY(%s) "
        "AND relation.relowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)) AS owns_table",
        (list(APP_TABLES),),
    ).fetchone()["owns_table"]
    if owns_protected_table:
        raise FirstBindBlocked("restricted_login_owns_protected_table")

    allowed, denied = _privilege_contract(capability)
    for table, privilege in allowed:
        if not connection.execute(
            "SELECT pg_catalog.has_table_privilege(current_user, %s, %s) AS allowed",
            (f"public.{table}", privilege),
        ).fetchone()["allowed"]:
            raise FirstBindBlocked("restricted_login_missing_required_table_privilege")
    for table, privilege in denied:
        if connection.execute(
            "SELECT pg_catalog.has_table_privilege(current_user, %s, %s) AS allowed",
            (f"public.{table}", privilege),
        ).fetchone()["allowed"]:
            raise FirstBindBlocked("restricted_login_has_unintended_table_privilege")

    with connection.transaction():
        if int(connection.execute("SELECT count(*) AS visible FROM public.tenants").fetchone()["visible"]) != 0:
            raise FirstBindBlocked("tenant_rls_did_not_default_deny")
        _expect_denied(connection, "SET ROLE postgres")
        if capability == "retaniq_backend":
            _expect_denied(connection, "SELECT dataset_id FROM public.dataset_identity")
            _expect_denied(connection, "SET ROLE retaniq_maintenance")
        else:
            _expect_denied(connection, "SELECT version FROM public.retaniq_schema_migrations")
            _expect_denied(connection, "CREATE SCHEMA retainiq_first_bind_probe")


def _test_logins(payload: Mapping[str, Any]) -> list[str]:
    import psycopg
    from psycopg.rows import dict_row

    tested: list[str] = []
    for login, capability in LOGIN_CAPABILITIES.items():
        try:
            connection = psycopg.connect(
                payload["logins"][login]["dsn"], connect_timeout=15,
                application_name="retainiq_first_bind_restricted_login_test",
                row_factory=dict_row, autocommit=True, prepare_threshold=None,
            )
        except Exception:
            raise FirstBindBlocked("restricted_login_authentication_failed") from None
        try:
            _verify_restricted_login(connection, login, capability)
        finally:
            connection.close()
        tested.append(login)
    return tested


def _lock_and_bind(connection: Any, plan: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    connection.execute("SET LOCAL lock_timeout = '30s'")
    connection.execute("SET LOCAL statement_timeout = '300s'")
    connection.execute(
        "SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))",
        (f"retainiq:first-bind:{PROJECT_REF}:{plan['identity']['dataset_id']}",),
    )
    _lock_destination_tables(connection)
    snapshot = _snapshot(connection, plan, read_only=False)
    state = snapshot["destination_state"]
    if state == "EMPTY_DESTINATION":
        _insert_dataset_identity(connection, plan["identity"])
        state = "FIRST_BIND_CREATED"
        snapshot["table_counts"]["dataset_identity"] = 1
    elif state == "MATCHING_TENANT01_RESUME":
        state = "MATCHING_TENANT01_RESUME"
    return state, snapshot


def _insert_dataset_identity(connection: Any, identity: Mapping[str, Any]) -> None:
    inserted = connection.execute(
        "INSERT INTO public.dataset_identity(singleton_id, dataset_id, dataset_version, dataset_type, "
        "target_policy_version, generator_version, manifest_sha256, bound_at) "
        "VALUES (1, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) RETURNING dataset_id",
        tuple(identity[field] for field in IDENTITY_FIELDS),
    ).fetchone()
    if not inserted or inserted["dataset_id"] != identity["dataset_id"]:
        raise FirstBindBlocked("dataset_identity_insert_not_confirmed")


def _lock_destination_tables(connection: Any) -> None:
    from psycopg import sql

    qualified = sql.SQL(", ").join(sql.Identifier("public", table) for table in LOCKED_TABLES)
    connection.execute(sql.SQL("LOCK TABLE {} IN SHARE MODE").format(qualified))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m retaniq.supabase_first_bind",
        description="Provision restricted Supabase logins and bind approved STANDARD tenant-01 provenance once.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--tenant-id", default=TENANT_ID)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not sys.stdin.isatty():
        print(json.dumps({"status": "BLOCKED", "reason": "interactive_terminal_required", "mutations_performed": False}))
        return 2
    admin = None
    mutation_committed = False
    phase = "dataset_validation"
    try:
        dataset_path = args.dataset.expanduser().resolve()
        plan = _manifest_plan(dataset_path, args.tenant_id)
        password = getpass.getpass("Supabase migration database password: ")
        if not password:
            raise FirstBindBlocked("migration_login_password_required")
        config = _safe_config(args.host, args.user, password)
        import psycopg
        from psycopg.rows import dict_row

        admin = psycopg.connect(
            config.postgresql_dsn, connect_timeout=15,
            application_name="retainiq_supabase_first_bind_bootstrap",
            row_factory=dict_row, autocommit=False,
        )
        phase = "read_only_destination_preflight"
        with admin.transaction():
            snapshot = _snapshot(admin, plan, read_only=True)
            roles = _role_catalog(admin)
        if not roles:
            existing_logins = {login: False for login in LOGIN_CAPABILITIES}
        else:
            existing_logins = {login: login in roles for login in LOGIN_CAPABILITIES}
        payload, credentials_reused = _load_or_prepare_credentials(config.postgresql_dsn, existing_logins)
        print(json.dumps({
            "status": "READ_ONLY_PREFLIGHT_READY",
            "project_ref": PROJECT_REF,
            "migration_history": "CHECKSUMS_MATCH",
            "application_tables_verified": len(snapshot["inventory"]),
            "forced_rls_tables_verified": len(RLS_TABLES),
            "tenant_scoped_rows": sum(snapshot["table_counts"][table] for table in TENANT_TABLES),
            "global_checkpoint_rows": snapshot["table_counts"]["synthetic_import_checkpoints"],
            "destination_state": snapshot["destination_state"],
            "runtime_logins": {login: "EXISTS" if present else "WILL_CREATE" for login, present in existing_logins.items()},
            "credentials": "EXISTING_DPAPI" if credentials_reused else "WILL_STORE_CURRENT_USER_DPAPI",
            "recovery_point": "OPERATOR_MUST_CONFIRM_IN_SUPABASE_DASHBOARD",
            "mutations_performed": False,
        }, sort_keys=True, separators=(",", ":")))
        confirmation = input(
            "In Supabase Dashboard verify project " + PROJECT_REF
            + " and confirm a backup/recovery point or that it is disposable/rebuildable. "
            + "Authorize restricted LOGIN provisioning and tenant-01 first bind by typing "
            + f"PROVISION AND BIND {PROJECT_REF} {APPROVED_DATASET_ID}: "
        )
        if confirmation != f"PROVISION AND BIND {PROJECT_REF} {APPROVED_DATASET_ID}":
            print(json.dumps({"status": "CANCELLED", "project_ref": PROJECT_REF, "mutations_performed": False}))
            return 4

        if not credentials_reused:
            store_dpapi_secret(credential_store_path(), json.dumps(payload, separators=(",", ":")))
        phase = "restricted_login_provisioning"
        provisioned, role_changes = _provision_logins(admin, payload)
        mutation_committed = bool(role_changes)
        phase = "restricted_login_tests"
        tested = _test_logins(payload)
        phase = "locked_final_occupancy_recheck_and_first_bind"
        with admin.transaction():
            binding, final_snapshot = _lock_and_bind(admin, plan)
        if binding == "FIRST_BIND_CREATED":
            mutation_committed = True

        tenant_rows_after = sum(final_snapshot["table_counts"][table] for table in TENANT_TABLES)
        result = {
            "status": "FIRST_BIND_READY",
            "project_ref": PROJECT_REF,
            "dataset_id": plan["identity"]["dataset_id"],
            "tenant_scope": TENANT_ID,
            "binding": binding,
            "migration_history": "CHECKSUMS_MATCH",
            "application_tables_verified": len(final_snapshot["inventory"]),
            "forced_rls_tables_verified": len(RLS_TABLES),
            "tenant_scoped_rows": tenant_rows_after,
            "global_checkpoint_rows": final_snapshot["table_counts"]["synthetic_import_checkpoints"],
            "restricted_logins_tested": tested,
            "restricted_logins_created": provisioned,
            "login_bypassrls": False,
            "tenant_context_boundary": "TRUSTED_BACKEND_TRANSACTION_LOCAL_GUC_NOT_DATABASE_AUTHENTICATION",
            "runtime_credentials": "CURRENT_USER_DPAPI_PROTECTED",
            "mutations_performed": bool(role_changes) or binding == "FIRST_BIND_CREATED",
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as error:
        result: dict[str, Any] = {
            "status": "BLOCKED",
            "project_ref": PROJECT_REF,
            "phase": phase,
            "reason": error.reason if isinstance(error, FirstBindBlocked) else type(error).__name__,
            "mutations_performed": mutation_committed,
            "mutation_status": "COMMITTED" if mutation_committed else "NONE_OR_ROLLED_BACK",
        }
        sqlstate, diagnostic = _safe_migration_diagnostic(error)
        if sqlstate:
            result["sqlstate"] = sqlstate
        if diagnostic:
            result["diagnostic_message"] = diagnostic
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 2
    finally:
        if admin is not None:
            admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
