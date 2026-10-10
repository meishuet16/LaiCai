"""Small authenticated STANDARD reader smoke; emits counts and checks only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path

from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_service_principal,
    get_account_snapshot_as_of,
    get_events_as_of,
    get_observation_coverage_as_of,
    get_subscriptions_as_of,
    normalize_timestamp,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_smoke(database: Path, as_of: str = "2026-10-01T00:00:00Z") -> dict[str, object]:
    cutoff = normalize_timestamp(as_of)
    token = os.environ.get("RETAINIQ_MODEL_TOKEN")
    principal = authenticate_service_principal(database, token)
    if (principal.tenant_id != "tenant-01" or principal.role != "analyst"
            or principal.authorized_purposes != ("retention_inference",)
            or len(principal.authorized_sources) != 3):
        raise RuntimeError("reader grant contract mismatch")

    uri = database.resolve().as_uri() + "?mode=ro"
    observer = sqlite3.connect(uri, uri=True)
    observer.row_factory = sqlite3.Row
    before_version = observer.execute("PRAGMA data_version").fetchone()[0]
    before_stat = database.stat()
    customer = observer.execute(
        "SELECT customer_id FROM canonical_events WHERE tenant_id=? ORDER BY customer_id LIMIT 1",
        (principal.tenant_id,),
    ).fetchone()
    other_tenant = observer.execute(
        "SELECT customer_id FROM canonical_events WHERE tenant_id=? ORDER BY customer_id LIMIT 1",
        ("tenant-02",),
    ).fetchone()
    if customer is None or other_tenant is None:
        raise RuntimeError("smoke dataset rows are unavailable")
    categories_by_source: dict[str, set[str]] = {}
    for row in observer.execute(
        "SELECT source, category FROM integration_event_categories WHERE tenant_id=? ORDER BY source,category",
        (principal.tenant_id,),
    ):
        if row["source"] in principal.authorized_sources:
            categories_by_source.setdefault(row["source"], set()).add(row["category"])
    customer_id, other_customer_id = customer[0], other_tenant[0]
    observer.close()

    events = get_events_as_of(database, principal, customer_id, as_of)
    subscriptions = get_subscriptions_as_of(database, principal, customer_id, as_of)
    snapshot = get_account_snapshot_as_of(database, principal, customer_id, as_of)
    coverage = get_observation_coverage_as_of(database, principal, customer_id, as_of)
    if snapshot["tenant_id"] != "tenant-01" or snapshot["as_of"] != cutoff:
        raise RuntimeError("authenticated snapshot scope or cutoff mismatch")
    if snapshot["valuation"] is not None:
        raise RuntimeError("billing valuation unexpectedly present")
    for event in events:
        if (event["source"] not in principal.authorized_sources
                or event["category"] not in categories_by_source.get(event["source"], set())
                or event["occurred_at"] > cutoff or event["available_at"] > cutoff):
            raise RuntimeError("event source or historical visibility check failed")
        if event["category"] == "billing" and {"amount_minor", "currency"} & set(event["attributes"]):
            raise RuntimeError("billing valuation fields unexpectedly present")
        json.dumps(event, sort_keys=True, allow_nan=False)
    for row in subscriptions:
        if {"amount_minor", "discount_minor", "currency", "mrr_minor"} & set(row):
            raise RuntimeError("subscription valuation fields unexpectedly present")
        json.dumps(row, sort_keys=True, allow_nan=False)
    for row in coverage:
        if (row["source"] not in principal.authorized_sources
                or row["source_category"] not in categories_by_source.get(row["source"], set())
                or row["coverage_available_at"] > cutoff):
            raise RuntimeError("coverage source or historical visibility check failed")
    if snapshot["input_data_as_of"] is not None and snapshot["input_data_as_of"] > cutoff:
        raise RuntimeError("snapshot includes data beyond its cutoff")
    json.dumps(snapshot, sort_keys=True, allow_nan=False)
    json.dumps(coverage, sort_keys=True, allow_nan=False)

    try:
        get_account_snapshot_as_of(database, principal, other_customer_id, as_of)
    except DataFoundationError as error:
        if error.code != "not_found":
            raise RuntimeError("cross-tenant request returned an unexpected denial") from None
    else:
        raise RuntimeError("cross-tenant account was readable")

    observer = sqlite3.connect(uri, uri=True)
    after_version = observer.execute("PRAGMA data_version").fetchone()[0]
    observer.close()
    after_stat = database.stat()
    if before_version != after_version or before_stat.st_mtime_ns != after_stat.st_mtime_ns:
        raise RuntimeError("historical read changed the SQLite database")
    return {
        "status": "AUTHENTICATED_SMOKE_PASS",
        "tenant": principal.tenant_id,
        "purpose_count": len(principal.authorized_purposes),
        "source_count": len(principal.authorized_sources),
        "event_count": len(events),
        "subscription_count": len(subscriptions),
        "coverage_row_count": len(coverage),
        "valuation_fields_returned": False,
        "historical_cutoff": cutoff,
        "cross_tenant_denial": "PASS",
        "database_unchanged_during_reads": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--as-of", default="2026-10-01T00:00:00Z")
    args = parser.parse_args()
    print(json.dumps(run_smoke(args.db, args.as_of), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
