"""Adapter from generated canonical CSV rows into the real Part 1 ingestion path."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_integration,
    authenticate_service_principal,
    bind_dataset_identity,
    create_service_principal,
    get_dataset_identity,
    get_synthetic_import_checkpoint,
    get_tenant_table_counts,
    get_account_snapshot_as_of,
    ingest_events_batch,
    initialize_database,
    provision_synthetic_identities,
    provision_synthetic_integration_token,
    provision_member2_reader_principal,
    record_observation_coverage_batch,
    get_observation_coverage_as_of,
)
from retaniq.database_config import DatabaseConfig, resolve_database_config
from retaniq.postgresql_migrations import verify_postgresql_schema


def _database_target(value: DatabaseConfig | Path | str) -> DatabaseConfig | str:
    if isinstance(value, DatabaseConfig):
        return value
    if isinstance(value, str) and "://" in value:
        return resolve_database_config(value)
    return str(Path(value).resolve())


def _load_manifest(dataset_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((dataset_path / "dataset_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("dataset manifest is missing or invalid") from exc
    if manifest.get("dataset_type") != "synthetic_saas" or manifest.get("track") != "synthetic_saas":
        raise ValueError("only an isolated synthetic_saas dataset may use this adapter")
    return manifest


def provision_member2_reader(
    dataset_path: Path | str,
    database_path: DatabaseConfig | Path | str,
    tenant_id: str,
    *,
    deliver_token: Any,
) -> dict[str, Any]:
    """Provision a tenant-01 retention-only principal after a verified import."""
    dataset = Path(dataset_path).resolve()
    database = _database_target(database_path)
    manifest = _load_manifest(dataset)
    dataset_id = manifest["dataset_id"]
    if (tenant_id != "tenant-01"
            or dataset_id != "synthetic-saas-v1-2-standard-s2026-970a9d231e68"):
        raise ValueError("the P0 reader only supports the approved STANDARD tenant-01 dataset")
    database_config = resolve_database_config(database)
    if not database_config.is_sqlite:
        raise ValueError("the P0 reader requires the approved SQLite working copy")
    expected_database = (
        Path.home() / "RetainIQ-private" / "synthetic_saas_v1_2" / "working" / "member1-p0"
        / f"{dataset_id}-tenant-01-reader.sqlite3"
    ).resolve()
    if Path(database_config.sqlite_path).resolve() != expected_database:
        raise ValueError("the P0 reader may only be provisioned in its dedicated working copy")
    initialize_database(database_config)
    manifest_digest = hashlib.sha256((dataset / "dataset_manifest.json").read_bytes()).hexdigest()
    expected_identity = {
        "dataset_id": dataset_id,
        "dataset_version": manifest["dataset_version"],
        "dataset_type": "synthetic_saas",
        "target_policy_version": manifest["target_policy_version"],
        "generator_version": manifest["generator_code_version"],
        "manifest_sha256": manifest_digest,
    }
    try:
        read_only = sqlite3.connect(Path(database_config.sqlite_path).as_uri() + "?mode=ro", uri=True)
        read_only.row_factory = sqlite3.Row
        identity = read_only.execute(
            "SELECT dataset_id, dataset_version, dataset_type, target_policy_version, "
            "generator_version, manifest_sha256 FROM dataset_identity WHERE singleton_id=1",
        ).fetchone()
        if identity is None or dict(identity) != expected_identity:
            raise ValueError("working database dataset identity does not match the approved manifest")
        expected_events = int(manifest["actual_counts"]["canonical_events"])
        expected_coverage = int(manifest["actual_counts"]["observation_coverage"])
        event_count = read_only.execute("SELECT COUNT(*) FROM canonical_events").fetchone()[0]
        coverage_count = read_only.execute("SELECT COUNT(*) FROM observation_coverage").fetchone()[0]
        if event_count != expected_events or coverage_count != expected_coverage:
            raise ValueError("working database does not contain the complete STANDARD import")
        imported_sources = {
            row["source"]: row["category"] for row in read_only.execute(
                "SELECT i.source, c.category FROM integrations i JOIN integration_event_categories c "
                "ON c.tenant_id=i.tenant_id AND c.source=i.source WHERE i.tenant_id=? ORDER BY i.source",
                (tenant_id,),
            )
        }
        read_only.close()
    except sqlite3.Error:
        raise ValueError("working database import verification failed") from None

    sources_by_category: dict[str, str] = {}
    with (dataset / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["tenant_id"] != tenant_id:
                continue
            category, source = row["source_category"], row["source"]
            previous = sources_by_category.setdefault(category, source)
            if previous != source:
                raise ValueError("one tenant has multiple source IDs for a category")
    if set(sources_by_category) != {"usage", "billing", "subscription"}:
        raise ValueError("the selected tenant does not have the complete synthetic source grant set")
    expected_sources = dict(sources_by_category)
    if imported_sources != {source: category for category, source in expected_sources.items()}:
        raise ValueError("working database source/category grants do not match dataset metadata")
    principal_info = provision_member2_reader_principal(
        database, service_principal_id="member2-standard-tenant-01-reader", tenant_id=tenant_id,
        authorized_sources=tuple(expected_sources.values()), deliver_token=deliver_token,
    )
    return {"status": "PROVISIONED", "dataset_id": dataset_id, **principal_info}


def import_dataset(
    dataset_path: Path | str,
    database_path: DatabaseConfig | Path | str,
    *,
    verify_idempotency: bool = False,
    tenant_id: str | None = None,
    maintenance_database_path: DatabaseConfig | Path | str | None = None,
) -> dict[str, Any]:
    """Provision and import a full dataset or an explicitly scoped tenant subset.

    Credentials exist only in memory for this run and are never written to the
    generated dataset or returned in the result.
    """
    dataset = Path(dataset_path).resolve()
    database = _database_target(database_path)
    manifest = _load_manifest(dataset)
    database_config = resolve_database_config(database)
    if tenant_id is not None and (not isinstance(tenant_id, str) or not tenant_id.strip()):
        raise ValueError("tenant scope must be a non-empty tenant ID")
    if database_config.is_supabase and (
        tenant_id != "tenant-01"
        or (maintenance_database_path is None and not database_config.maintenance_dsn)
    ):
        raise ValueError("Supabase import requires explicit tenant-01 scope and a separate maintenance login")
    if database_config.is_postgresql:
        verify_postgresql_schema(database_config)
    else:
        initialize_database(database_config)
    maintenance_database = (
        _database_target(maintenance_database_path)
        if maintenance_database_path is not None
        else database_config.for_maintenance() if database_config.is_supabase
        else database
    )
    maintenance_config = resolve_database_config(maintenance_database)
    if database_config.is_postgresql and not maintenance_config.is_postgresql:
        raise ValueError("PostgreSQL tenant writes require a PostgreSQL maintenance target")
    if database_config.is_supabase:
        if (not maintenance_config.is_supabase
                or maintenance_config.expected_project_ref != database_config.expected_project_ref
                or maintenance_config.connection_mode not in {"DIRECT", "SESSION_POOLER"}
                or maintenance_config.postgresql_dsn == database_config.postgresql_dsn):
            raise ValueError("maintenance connection must target the same Supabase project using a session-capable mode")
    scope_tenant_id = tenant_id
    manifest_bytes = (dataset / "dataset_manifest.json").read_bytes()
    bind_dataset_identity(
        maintenance_database,
        dataset_id=manifest["dataset_id"],
        dataset_version=manifest["dataset_version"],
        dataset_type=manifest["dataset_type"],
        target_policy_version=manifest["target_policy_version"],
        generator_version=manifest["generator_code_version"],
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )

    customers_by_tenant: dict[str, list[str]] = defaultdict(list)
    excluded_customer_ids: dict[str, str] = {}
    customer_rows: list[tuple[str, str]] = []
    with (dataset / "customers.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            row_tenant_id = row["tenant_id"]
            customer_id = row["customer_id"]
            if scope_tenant_id is not None and row_tenant_id != scope_tenant_id:
                excluded_customer_ids.setdefault(row_tenant_id, customer_id)
                continue
            customer_rows.append((row_tenant_id, customer_id))
            customers_by_tenant[row_tenant_id].append(customer_id)

    source_categories: dict[tuple[str, str], str] = {}
    identity_tuples: list[tuple[str, str, str, str]] = []
    with (dataset / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if scope_tenant_id is not None and row["tenant_id"] != scope_tenant_id:
                continue
            identity_tuples.append((row["tenant_id"], row["source"], row["external_customer_id"], row["customer_id"]))
            key = (row["tenant_id"], row["source"])
            prior = source_categories.setdefault(key, row["source_category"])
            if prior != row["source_category"]:
                raise ValueError("one source may not mix canonical event categories")

    provision_synthetic_identities(
        database, dataset_id=manifest["dataset_id"], customers=customer_rows, identities=identity_tuples,
        maintenance_path=maintenance_database,
    )

    principals = {}
    for (tenant_id, source), category in sorted(source_categories.items()):
        token = provision_synthetic_integration_token(
            database, dataset_id=manifest["dataset_id"], tenant_id=tenant_id,
            source=source, category=category, maintenance_path=maintenance_database,
        )
        principals[(tenant_id, source)] = authenticate_integration(database, token)

    counts: Counter[str] = Counter()

    stream_suffix = f"-{scope_tenant_id}" if scope_tenant_id is not None else ""
    batch_checkpoint_path = maintenance_database if maintenance_config.is_postgresql else None

    def import_once(*, repeat: bool) -> int:
        stream_name = ("canonical-replay" if repeat else "canonical-events") + stream_suffix
        checkpoint = get_synthetic_import_checkpoint(
            maintenance_database, dataset_id=manifest["dataset_id"], stream_name=stream_name,
            tenant_id=scope_tenant_id,
        )["last_row_number"]
        batch: list[dict[str, Any]] = []
        batch_start = 0
        row_number = 0

        def flush_batch(last_row_number: int) -> None:
            nonlocal batch, batch_start
            if not batch:
                return
            result = ingest_events_batch(
                database, batch, dataset_id=manifest["dataset_id"], stream_name=stream_name,
                first_row_number=batch_start, last_row_number=last_row_number,
                checkpoint_path=batch_checkpoint_path,
            )
            key = "repeat_" if repeat else ""
            counts[f"{key}accepted"] += result["accepted"]
            counts[f"{key}duplicates"] += result["duplicates"]
            batch = []
            batch_start = 0

        with (dataset / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if scope_tenant_id is not None and row["tenant_id"] != scope_tenant_id:
                    continue
                row_number += 1
                if row_number <= checkpoint:
                    continue
                principal = principals[(row["tenant_id"], row["source"])]
                envelope = {
                    "source": row["source"],
                    "source_event_id": row["source_event_id"],
                    "external_customer_id": row["external_customer_id"],
                    "event_type": row["event_type"],
                    "occurred_at": row["occurred_at"],
                    "attributes": json.loads(row["attributes_json"]),
                    "schema_version": row["schema_version"],
                }
                if batch_start == 0:
                    batch_start = row_number
                batch.append({
                    "principal": principal,
                    "payload": envelope,
                    "trusted_source_available_at": row["source_available_at"],
                })
                if len(batch) >= 1000:
                    flush_batch(row_number)
            flush_batch(row_number)
        return row_number

    def import_coverage_once(*, repeat: bool) -> int:
        stream_name = ("observation-coverage-replay" if repeat else "observation-coverage") + stream_suffix
        checkpoint = get_synthetic_import_checkpoint(
            maintenance_database, dataset_id=manifest["dataset_id"], stream_name=stream_name,
            tenant_id=scope_tenant_id,
        )["last_row_number"]
        batch: list[dict[str, Any]] = []
        batch_start = 0
        row_number = 0

        def flush_batch(last_row_number: int) -> None:
            nonlocal batch, batch_start
            if not batch:
                return
            result = record_observation_coverage_batch(
                database, batch, dataset_id=manifest["dataset_id"], stream_name=stream_name,
                first_row_number=batch_start, last_row_number=last_row_number,
                checkpoint_path=batch_checkpoint_path,
            )
            key = "repeat_" if repeat else ""
            counts[f"{key}coverage_accepted"] += result["accepted"]
            counts[f"{key}coverage_duplicates"] += result["duplicates"]
            batch = []
            batch_start = 0

        with gzip.open(dataset / "observation_coverage.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if scope_tenant_id is not None and row["tenant_id"] != scope_tenant_id:
                    continue
                row_number += 1
                if row_number <= checkpoint:
                    continue
                principal = principals[(row["tenant_id"], row["source"])]
                compact_start = "".join(char for char in row["covered_from"] if char.isalnum())
                coverage_id = f"coverage-{row['customer_id']}-{row['source_category']}-{compact_start}"
                record = {
                    "coverage_id": coverage_id,
                    "customer_id": row["customer_id"],
                    "source_category": row["source_category"],
                    "covered_from": row["covered_from"],
                    "covered_through": row["covered_through"],
                    "coverage_status": row["coverage_status"],
                    "coverage_completeness": float(row["coverage_completeness"]),
                    "coverage_available_at": row["coverage_available_at"],
                    "observation_policy_version": row["observation_policy_version"],
                }
                if batch_start == 0:
                    batch_start = row_number
                batch.append({"principal": principal, "record": record})
                if len(batch) >= 1000:
                    flush_batch(row_number)
            flush_batch(row_number)
        return row_number

    expected_event_rows = import_once(repeat=False)
    expected_coverage_rows = import_coverage_once(repeat=False)
    replay_checkpoint = None
    replay_coverage_checkpoint = None
    if verify_idempotency:
        import_once(repeat=True)
        import_coverage_once(repeat=True)
        replay_checkpoint = get_synthetic_import_checkpoint(
            maintenance_database, dataset_id=manifest["dataset_id"],
            stream_name="canonical-replay" + stream_suffix, tenant_id=scope_tenant_id,
        )
        replay_coverage_checkpoint = get_synthetic_import_checkpoint(
            maintenance_database, dataset_id=manifest["dataset_id"],
            stream_name="observation-coverage-replay" + stream_suffix, tenant_id=scope_tenant_id,
        )

    service_principals = {}
    for tenant_id in sorted(customers_by_tenant):
        sources = tuple(sorted(source for (source_tenant, source) in source_categories if source_tenant == tenant_id))
        token = create_service_principal(
            database, tenant_id, role="analyst", authorized_sources=sources,
            authorized_purposes=("retention_inference", "billing_valuation", "model_artifact_write"),
        )
        service_principals[tenant_id] = authenticate_service_principal(database, token)

    snapshots_checked = 0
    cutoff = f"{manifest['end_date']}T23:59:59Z"
    for tenant_id, customers in sorted(customers_by_tenant.items()):
        for customer_id in customers[:3]:
            get_account_snapshot_as_of(database, service_principals[tenant_id], customer_id, cutoff)
            get_observation_coverage_as_of(
                database, service_principals[tenant_id], customer_id, cutoff, source_category="usage",
            )
            snapshots_checked += 1

    cross_tenant_denial = False
    if len(service_principals) >= 2:
        first, second = sorted(service_principals)[:2]
        try:
            get_account_snapshot_as_of(
                database, service_principals[first], customers_by_tenant[second][0], cutoff,
            )
        except DataFoundationError as exc:
            cross_tenant_denial = exc.code == "not_found"
    elif service_principals and excluded_customer_ids:
        tenant = next(iter(service_principals))
        try:
            get_account_snapshot_as_of(
                database, service_principals[tenant], next(iter(excluded_customer_ids.values())), cutoff,
            )
        except DataFoundationError as exc:
            cross_tenant_denial = exc.code == "not_found"

    expected = expected_event_rows
    checkpoint = get_synthetic_import_checkpoint(
        maintenance_database, dataset_id=manifest["dataset_id"],
        stream_name="canonical-events" + stream_suffix, tenant_id=scope_tenant_id,
    )
    coverage_checkpoint = get_synthetic_import_checkpoint(
        maintenance_database, dataset_id=manifest["dataset_id"],
        stream_name="observation-coverage" + stream_suffix, tenant_id=scope_tenant_id,
    )
    database_event_count = checkpoint["database_event_count"]
    expected_coverage = expected_coverage_rows
    verified = (checkpoint["last_row_number"] == expected and database_event_count == expected
                and coverage_checkpoint["last_row_number"] == expected_coverage
                and coverage_checkpoint["database_coverage_count"] == expected_coverage
                and snapshots_checked > 0 and cross_tenant_denial)
    if verify_idempotency:
        verified = (verified and counts["repeat_accepted"] == 0 and replay_checkpoint is not None
                    and replay_checkpoint["last_row_number"] == expected
                    and replay_checkpoint["duplicate_count"] == expected
                    and replay_coverage_checkpoint is not None
                    and replay_coverage_checkpoint["last_row_number"] == expected_coverage
                    and replay_coverage_checkpoint["duplicate_count"] == expected_coverage)
    tenant_table_counts = {
        scoped_tenant: get_tenant_table_counts(database, scoped_tenant)
        for scoped_tenant in customers_by_tenant
    }
    return {
        "status": "VERIFIED" if verified else "PARTIAL",
        "dataset_id": manifest["dataset_id"],
        "import_scope": scope_tenant_id or "all_dataset_tenants",
        "imported_tenant_count": len(customers_by_tenant),
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "tenant_table_counts": tenant_table_counts,
        "database": str(database),
        "accepted": counts["accepted"],
        "duplicates": counts["duplicates"],
        "repeat_duplicates": counts["repeat_duplicates"] or (replay_checkpoint or {}).get("duplicate_count", 0),
        "repeat_accepted": counts["repeat_accepted"],
        "database_event_count": database_event_count,
        "coverage_accepted": counts["coverage_accepted"],
        "coverage_duplicates": counts["coverage_duplicates"],
        "database_coverage_count": coverage_checkpoint["database_coverage_count"],
        "last_row_number": checkpoint["last_row_number"],
        "historical_snapshots_checked": snapshots_checked,
        "cross_tenant_denial_verified": cross_tenant_denial,
        "credentials_persisted": False,
        "service_principals_provisioned": len(service_principals),
    }
