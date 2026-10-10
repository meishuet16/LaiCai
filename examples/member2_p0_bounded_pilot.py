"""One-account, one-cutoff Member 2 read pilot; no writes or raw data output."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_service_principal,
    get_account_snapshot_as_of,
    get_events_as_of,
    get_observation_coverage_as_of,
    get_subscriptions_as_of,
    normalize_timestamp,
)


def run_pilot(database: Path, as_of: str) -> dict[str, Any]:
    cutoff = normalize_timestamp(as_of)
    principal = authenticate_service_principal(database, os.environ.get("RETAINIQ_MODEL_TOKEN"))
    if (principal.tenant_id != "tenant-01" or principal.role != "analyst"
            or principal.authorized_purposes != ("retention_inference",)):
        raise RuntimeError("reader grant contract mismatch")
    source_marks = ",".join("?" for _ in principal.authorized_sources)
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    categories: dict[str, set[str]] = {}
    for row in connection.execute(
        f"SELECT source,category FROM integration_event_categories WHERE tenant_id=? "
        f"AND source IN ({source_marks}) ORDER BY source,category",
        (principal.tenant_id, *principal.authorized_sources),
    ):
        categories.setdefault(row["source"], set()).add(row["category"])
    customer = connection.execute(
        f"SELECT customer_id FROM canonical_events WHERE tenant_id=? AND source IN ({source_marks}) "
        "ORDER BY customer_id LIMIT 1",
        (principal.tenant_id, *principal.authorized_sources),
    ).fetchone()
    other_tenant = connection.execute(
        "SELECT customer_id FROM canonical_events WHERE tenant_id=? ORDER BY customer_id LIMIT 1",
        ("tenant-02",),
    ).fetchone()
    if customer is None or other_tenant is None:
        connection.close()
        raise RuntimeError("bounded pilot data is unavailable")
    customer_id, other_customer_id = customer[0], other_tenant[0]
    before = connection.execute("PRAGMA data_version").fetchone()[0]

    events = get_events_as_of(database, principal, customer_id, cutoff)
    subscriptions = get_subscriptions_as_of(database, principal, customer_id, cutoff)
    snapshot = get_account_snapshot_as_of(database, principal, customer_id, cutoff)
    coverage = get_observation_coverage_as_of(database, principal, customer_id, cutoff)
    if snapshot["tenant_id"] != principal.tenant_id or snapshot["as_of"] != cutoff:
        raise RuntimeError("authenticated tenant or cutoff mismatch")
    if snapshot["valuation"] is not None:
        raise RuntimeError("billing valuation unexpectedly returned")
    for event in events:
        if (event["source"] not in principal.authorized_sources
                or event["category"] not in categories.get(event["source"], set())
                or event["occurred_at"] > cutoff or event["available_at"] > cutoff):
            raise RuntimeError("source, category, or historical cutoff check failed")
        if event["category"] == "billing" and {"amount_minor", "currency"} & set(event["attributes"]):
            raise RuntimeError("billing valuation fields unexpectedly returned")
        json.dumps(event, sort_keys=True, allow_nan=False)
    for row in subscriptions:
        if {"amount_minor", "discount_minor", "currency", "mrr_minor"} & set(row):
            raise RuntimeError("subscription valuation fields unexpectedly returned")
    for row in coverage:
        if (row["source"] not in principal.authorized_sources
                or row["source_category"] not in categories.get(row["source"], set())
                or row["coverage_available_at"] > cutoff):
            raise RuntimeError("coverage source/category or cutoff check failed")
    if snapshot["input_data_as_of"] is not None and snapshot["input_data_as_of"] > cutoff:
        raise RuntimeError("snapshot includes data beyond the cutoff")
    try:
        get_account_snapshot_as_of(database, principal, other_customer_id, cutoff)
    except DataFoundationError as error:
        if error.code != "not_found":
            raise RuntimeError("cross-tenant denial did not match the contract") from None
    else:
        raise RuntimeError("cross-tenant account was readable")
    after = connection.execute("PRAGMA data_version").fetchone()[0]
    connection.close()
    if before != after:
        raise RuntimeError("read pilot changed the SQLite database")

    event_categories = Counter(event["category"] for event in events)
    usage_sessions = sum(
        int(event["attributes"].get("quantity", 0))
        for event in events if event["event_type"] == "usage_aggregate_updated"
    )
    coverage_statuses = Counter(row["coverage_status"] for row in coverage)
    return {
        "status": "BOUNDED_PILOT_PASS",
        "tenant": principal.tenant_id,
        "as_of": cutoff,
        "account_status": snapshot["status"],
        "event_count": len(events),
        "event_counts_by_category": dict(sorted(event_categories.items())),
        "daily_aggregate_sessions": usage_sessions,
        "subscription_count": len(subscriptions),
        "coverage_row_count": len(coverage),
        "coverage_counts_by_status": dict(sorted(coverage_statuses.items())),
        "valuation_fields_returned": False,
        "cross_tenant_denial": "PASS",
        "writes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--as-of", default="2026-10-01T00:00:00Z")
    args = parser.parse_args()
    print(json.dumps(run_pilot(args.db, args.as_of), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
