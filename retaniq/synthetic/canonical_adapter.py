"""Adapter from generated canonical CSV rows into the real Part 1 ingestion path."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
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
    get_account_snapshot_as_of,
    ingest_events_batch,
    initialize_database,
    provision_synthetic_identities,
    provision_synthetic_integration_token,
    record_observation_coverage_batch,
    get_observation_coverage_as_of,
)
from retaniq.database_config import DatabaseConfig, resolve_database_config


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
    include_billing_valuation: bool = False,
) -> dict[str, Any]:
    """Create a tenant/source-scoped analyst principal after a complete import.

    The bearer token is returned once to the local caller and is never written
    to the database in plaintext, dataset files, or logs.
    """
    dataset = Path(dataset_path).resolve()
    database = _database_target(database_path)
    manifest = _load_manifest(dataset)
    dataset_id = manifest["dataset_id"]
    expected_events = int(manifest["actual_counts"]["canonical_events"])
    expected_coverage = int(manifest["actual_counts"]["observation_coverage"])
    event_checkpoint = get_synthetic_import_checkpoint(
        database, dataset_id=dataset_id, stream_name="canonical-events",
    )
    coverage_checkpoint = get_synthetic_import_checkpoint(
        database, dataset_id=dataset_id, stream_name="observation-coverage",
    )
    if (event_checkpoint["last_row_number"] != expected_events
            or event_checkpoint["database_event_count"] != expected_events
            or coverage_checkpoint["last_row_number"] != expected_coverage
            or coverage_checkpoint["database_coverage_count"] != expected_coverage):
        raise ValueError("the database does not contain the complete dataset import")

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

    purposes = ["retention_inference", "model_artifact_write"]
    if include_billing_valuation:
        purposes.append("billing_valuation")
    token = create_service_principal(
        database, tenant_id, role="analyst",
        authorized_sources=tuple(sorted(sources_by_category.values())),
        authorized_purposes=tuple(purposes),
    )
    principal = authenticate_service_principal(database, token)
    identity = get_dataset_identity(database, principal)
    expected_manifest_digest = hashlib.sha256((dataset / "dataset_manifest.json").read_bytes()).hexdigest()
    if (identity["dataset_id"] != dataset_id
            or identity["dataset_version"] != manifest["dataset_version"]
            or identity["target_policy_version"] != manifest["target_policy_version"]
            or identity["generator_version"] != manifest["generator_code_version"]
            or identity["manifest_sha256"] != expected_manifest_digest):
        raise ValueError("database dataset identity does not match the selected manifest")
    return {
        "status": "PROVISIONED",
        "dataset_id": dataset_id,
        "tenant_id": tenant_id,
        "authorized_sources": list(principal.authorized_sources),
        "authorized_purposes": list(principal.authorized_purposes),
        "token": token,
    }


def import_dataset(
    dataset_path: Path | str,
    database_path: DatabaseConfig | Path | str,
    *,
    verify_idempotency: bool = False,
) -> dict[str, Any]:
    """Provision synthetic identities and import every event via ``ingest_event``.

    Credentials exist only in memory for this run and are never written to the
    generated dataset or returned in the result.
    """
    dataset = Path(dataset_path).resolve()
    database = _database_target(database_path)
    manifest = _load_manifest(dataset)
    database_config = resolve_database_config(database)
    initialize_database(database_config, migrate_postgresql=database_config.is_postgresql)
    manifest_bytes = (dataset / "dataset_manifest.json").read_bytes()
    bind_dataset_identity(
        database,
        dataset_id=manifest["dataset_id"],
        dataset_version=manifest["dataset_version"],
        dataset_type=manifest["dataset_type"],
        target_policy_version=manifest["target_policy_version"],
        generator_version=manifest["generator_code_version"],
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )

    customers_by_tenant: dict[str, list[str]] = defaultdict(list)
    customer_rows: list[tuple[str, str]] = []
    with (dataset / "customers.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            tenant_id = row["tenant_id"]
            customer_id = row["customer_id"]
            customer_rows.append((tenant_id, customer_id))
            customers_by_tenant[tenant_id].append(customer_id)

    source_categories: dict[tuple[str, str], str] = {}
    identity_tuples: list[tuple[str, str, str, str]] = []
    with (dataset / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            identity_tuples.append((row["tenant_id"], row["source"], row["external_customer_id"], row["customer_id"]))
            key = (row["tenant_id"], row["source"])
            prior = source_categories.setdefault(key, row["source_category"])
            if prior != row["source_category"]:
                raise ValueError("one source may not mix canonical event categories")

    provision_synthetic_identities(
        database, dataset_id=manifest["dataset_id"], customers=customer_rows, identities=identity_tuples,
    )

    principals = {}
    for (tenant_id, source), category in sorted(source_categories.items()):
        token = provision_synthetic_integration_token(
            database, dataset_id=manifest["dataset_id"], tenant_id=tenant_id,
            source=source, category=category,
        )
        principals[(tenant_id, source)] = authenticate_integration(database, token)

    counts: Counter[str] = Counter()

    def import_once(*, repeat: bool) -> None:
        stream_name = "canonical-replay" if repeat else "canonical-events"
        checkpoint = get_synthetic_import_checkpoint(
            database, dataset_id=manifest["dataset_id"], stream_name=stream_name,
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
            )
            key = "repeat_" if repeat else ""
            counts[f"{key}accepted"] += result["accepted"]
            counts[f"{key}duplicates"] += result["duplicates"]
            batch = []
            batch_start = 0

        with (dataset / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
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

    def import_coverage_once(*, repeat: bool) -> None:
        stream_name = "observation-coverage-replay" if repeat else "observation-coverage"
        checkpoint = get_synthetic_import_checkpoint(
            database, dataset_id=manifest["dataset_id"], stream_name=stream_name,
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
            )
            key = "repeat_" if repeat else ""
            counts[f"{key}coverage_accepted"] += result["accepted"]
            counts[f"{key}coverage_duplicates"] += result["duplicates"]
            batch = []
            batch_start = 0

        with gzip.open(dataset / "observation_coverage.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
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

    import_once(repeat=False)
    import_coverage_once(repeat=False)
    replay_checkpoint = None
    replay_coverage_checkpoint = None
    if verify_idempotency:
        import_once(repeat=True)
        import_coverage_once(repeat=True)
        replay_checkpoint = get_synthetic_import_checkpoint(
            database, dataset_id=manifest["dataset_id"], stream_name="canonical-replay",
        )
        replay_coverage_checkpoint = get_synthetic_import_checkpoint(
            database, dataset_id=manifest["dataset_id"], stream_name="observation-coverage-replay",
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

    cross_tenant_denial = len(service_principals) < 2
    if len(service_principals) >= 2:
        first, second = sorted(service_principals)[:2]
        try:
            get_account_snapshot_as_of(
                database, service_principals[first], customers_by_tenant[second][0], cutoff,
            )
        except DataFoundationError as exc:
            cross_tenant_denial = exc.code == "not_found"

    expected = manifest["actual_counts"]["canonical_events"]
    checkpoint = get_synthetic_import_checkpoint(
        database, dataset_id=manifest["dataset_id"], stream_name="canonical-events",
    )
    coverage_checkpoint = get_synthetic_import_checkpoint(
        database, dataset_id=manifest["dataset_id"], stream_name="observation-coverage",
    )
    database_event_count = checkpoint["database_event_count"]
    expected_coverage = manifest["actual_counts"]["observation_coverage"]
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
    return {
        "status": "VERIFIED" if verified else "PARTIAL",
        "dataset_id": manifest["dataset_id"],
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
