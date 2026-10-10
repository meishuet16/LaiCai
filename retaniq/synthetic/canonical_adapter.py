"""Adapter from generated canonical CSV rows into the real Part 1 ingestion path."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_integration,
    authenticate_service_principal,
    create_customer,
    create_integration,
    create_service_principal,
    create_tenant,
    get_account_snapshot_as_of,
    ingest_event,
    initialize_database,
    map_customer_identity,
)


def _load_manifest(dataset_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((dataset_path / "dataset_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("dataset manifest is missing or invalid") from exc
    if manifest.get("dataset_type") != "synthetic_saas" or manifest.get("track") != "synthetic_saas":
        raise ValueError("only an isolated synthetic_saas dataset may use this adapter")
    return manifest


def import_dataset(
    dataset_path: Path | str,
    database_path: Path | str,
    *,
    verify_idempotency: bool = False,
) -> dict[str, Any]:
    """Provision synthetic identities and import every event via ``ingest_event``.

    Credentials exist only in memory for this run and are never written to the
    generated dataset or returned in the result.
    """
    dataset = Path(dataset_path).resolve()
    database = Path(database_path).resolve()
    manifest = _load_manifest(dataset)
    initialize_database(database)

    customers_by_tenant: dict[str, list[str]] = defaultdict(list)
    with (dataset / "customers.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            tenant_id = row["tenant_id"]
            customer_id = row["customer_id"]
            create_tenant(database, tenant_id)
            create_customer(database, tenant_id, customer_id)
            customers_by_tenant[tenant_id].append(customer_id)

    source_categories: dict[tuple[str, str], str] = {}
    identity_rows: list[dict[str, str]] = []
    with (dataset / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            identity_rows.append(row)
            key = (row["tenant_id"], row["source"])
            prior = source_categories.setdefault(key, row["source_category"])
            if prior != row["source_category"]:
                raise ValueError("one source may not mix canonical event categories")

    principals = {}
    for (tenant_id, source), category in sorted(source_categories.items()):
        purposes = ("retention_inference", "billing_valuation")
        token = create_integration(
            database, tenant_id, source,
            authorized_purposes=purposes,
            authorized_categories=(category,),
        )
        principals[(tenant_id, source)] = authenticate_integration(database, token)
    for row in identity_rows:
        map_customer_identity(
            database, row["tenant_id"], row["source"],
            row["external_customer_id"], row["customer_id"],
        )

    counts: Counter[str] = Counter()

    def import_once(*, repeat: bool) -> None:
        with (dataset / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
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
                result = ingest_event(
                    database, principal, envelope, received_at=row["received_at"],
                    trusted_source_available_at=row["source_available_at"],
                )
                if repeat:
                    counts["repeat_duplicates" if result["duplicate"] else "repeat_accepted"] += 1
                else:
                    counts["duplicates" if result["duplicate"] else "accepted"] += 1

    import_once(repeat=False)
    if verify_idempotency:
        import_once(repeat=True)

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
    verified = counts["accepted"] == expected and snapshots_checked > 0 and cross_tenant_denial
    if verify_idempotency:
        verified = verified and counts["repeat_duplicates"] == expected and counts["repeat_accepted"] == 0
    return {
        "status": "VERIFIED" if verified else "PARTIAL",
        "dataset_id": manifest["dataset_id"],
        "database": str(database),
        "accepted": counts["accepted"],
        "duplicates": counts["duplicates"],
        "repeat_duplicates": counts["repeat_duplicates"],
        "repeat_accepted": counts["repeat_accepted"],
        "historical_snapshots_checked": snapshots_checked,
        "cross_tenant_denial_verified": cross_tenant_denial,
        "credentials_persisted": False,
        "service_principals_provisioned": len(service_principals),
    }
