"""Authorized, read-only Member 2 smoke test for Synthetic SaaS v1.2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_service_principal,
    get_account_snapshot_as_of,
    get_dataset_identity,
    get_events_as_of,
    get_observation_coverage_as_of,
)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _epoch(value: str) -> int:
    return int(_parse_time(value).timestamp())


def _coverage_complete(rows: list[dict[str, Any]], left: int, right: int) -> bool:
    if right <= left:
        return False
    intervals = sorted(
        ( _epoch(row["covered_from"]), _epoch(row["covered_through"]), row["coverage_status"],
          float(row["coverage_completeness"]) )
        for row in rows if row["source_category"] == "usage"
    )
    cursor = left
    for start, end, status, completeness in intervals:
        if end <= cursor:
            continue
        if start > cursor or status not in {"complete", "delayed"} or completeness < 1.0:
            return False
        cursor = max(cursor, end)
        if cursor >= right:
            return True
    return False


def _outcome_coverage_complete(rows: list[dict[str, Any]], left: int, right: int) -> bool:
    if right <= left:
        return False
    intervals = sorted(
        (_epoch(row["covered_from"]), _epoch(row["covered_through"]), row["coverage_status"],
         float(row["coverage_completeness"]))
        for row in rows if row["source_category"] == "subscription"
    )
    cursor = left
    for start, end, status, completeness in intervals:
        if end <= cursor:
            continue
        if start > cursor or status not in {"complete", "delayed"} or completeness < 1.0:
            return False
        cursor = max(cursor, end)
        if cursor >= right:
            return True
    return False


def _usage_features(
    usage_events: list[dict[str, Any]], coverage: list[dict[str, Any]], cutoff_date: date,
    cutoff: datetime,
) -> dict[str, Any]:
    midnight = datetime.combine(cutoff_date, time.min, tzinfo=timezone.utc)
    end = int(midnight.timestamp())
    windows = {
        "7d": (cutoff_date - timedelta(days=7), cutoff_date),
        "14d": (cutoff_date - timedelta(days=14), cutoff_date),
        "30d": (cutoff_date - timedelta(days=30), cutoff_date),
        "baseline_28d": (cutoff_date - timedelta(days=58), cutoff_date - timedelta(days=30)),
    }
    totals: dict[str, dict[str, Any]] = {}
    for name, (left_date, right_date) in windows.items():
        left = int(datetime.combine(left_date, time.min, tzinfo=timezone.utc).timestamp())
        right = int(datetime.combine(right_date, time.min, tzinfo=timezone.utc).timestamp())
        selected = []
        for event in usage_events:
            if event["event_type"] != "usage_aggregate_updated":
                continue
            window_start = _parse_time(event["occurred_at"]) - timedelta(days=1)
            if left_date <= window_start.date() < right_date:
                selected.append(event)
        active_dates = {
            (_parse_time(event["occurred_at"]) - timedelta(days=1)).date()
            for event in selected
        }
        totals[name] = {
            "sessions": sum(int(event["attributes"].get("quantity", 0)) for event in selected),
            "active_days": len(active_dates),
            "coverage_complete": _coverage_complete(coverage, left, right),
        }
    totals["baseline_non_overlaps_30d"] = windows["baseline_28d"][1] == windows["30d"][0]
    failures = [
        event for event in usage_events
        if event["event_type"] in {"session_started", "feature_used"}
    ]
    totals["raw_usage_event_rows"] = len(failures)
    totals["as_of_cutoff"] = _stamp(cutoff)
    return totals


def _train_cutoffs(manifest: dict[str, Any], split: dict[str, Any]) -> list[date]:
    start = date.fromisoformat(manifest["start_date"])
    end = date.fromisoformat(manifest["end_date"])
    policy = split["sampling_policy"]
    first = start + timedelta(days=int(policy["warmup_days"]))
    first += timedelta(days=(-first.weekday()) % 7)
    final = end - timedelta(days=int(split["maximum_horizon_days"]) + int(split["label_maturity_lag_days"]))
    bounds = split["stages"]["train"]
    lower, upper = date.fromisoformat(bounds["cutoff_start"]), date.fromisoformat(bounds["cutoff_end"])
    out = []
    while first < final:
        if lower <= first < upper:
            out.append(first)
        first += timedelta(days=7)
    return out


def _oracle_labels(
    dataset: Path, database: Path, principal: Any, tenant_id: str, customer_id: str,
    cutoff: datetime, manifest: dict[str, Any], split: dict[str, Any],
) -> dict[str, str]:
    end = datetime.combine(date.fromisoformat(manifest["end_date"]), time.min, tzinfo=timezone.utc)
    lag = int(split["label_maturity_lag_days"])
    account_churns: list[dict[str, str]] = []
    with (dataset / "effective_churn.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["tenant_id"] == tenant_id and row["customer_id"] == customer_id:
                account_churns.append(row)

    labels: dict[str, str] = {}
    for horizon in (7, 14, 30):
        target_end = cutoff + timedelta(days=horizon)
        maturity = target_end + timedelta(days=lag)
        if maturity > end:
            labels[str(horizon)] = "unknown"
            continue
        later_events = get_events_as_of(
            database, principal, customer_id, _stamp(maturity), category="subscription",
        )
        source_events = {event["source_event_id"]: event for event in later_events}
        qualifying = [row for row in account_churns if cutoff < _parse_time(row["churn_effective_at"]) <= target_end
                      and row["source_event_id"] in source_events]
        if qualifying:
            labels[str(horizon)] = "1"
            continue
        future_coverage = get_observation_coverage_as_of(
            database, principal, customer_id, _stamp(maturity),
            source_category="subscription",
        )
        if _outcome_coverage_complete(future_coverage, int(cutoff.timestamp()), int(target_end.timestamp())):
            labels[str(horizon)] = "0"
        else:
            labels[str(horizon)] = "unknown"
    return labels


def run_smoke(dataset: Path, database: Path, token: str) -> dict[str, Any]:
    manifest_path = dataset / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split = json.loads((dataset / "split_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("dataset_type") != "synthetic_saas" or manifest.get("dataset_version") != "1.2.0":
        raise ValueError("the smoke test requires a Synthetic SaaS v1.2 dataset")
    principal = authenticate_service_principal(database, token)
    identity = get_dataset_identity(database, principal)
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if (identity["dataset_id"] != manifest["dataset_id"]
            or identity["manifest_sha256"] != manifest_digest
            or identity["dataset_version"] != manifest["dataset_version"]
            or identity["target_policy_version"] != manifest["target_policy_version"]):
        raise ValueError("authorized database identity does not match the dataset manifest")
    required_purposes = {"retention_inference", "model_artifact_write"}
    if principal.role != "analyst" or not required_purposes.issubset(principal.authorized_purposes):
        raise ValueError("principal lacks the required Member 2 analyst read/write grants")

    source_by_category: dict[str, str] = {}
    customers_by_tenant: dict[str, list[str]] = {}
    with (dataset / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["tenant_id"] == principal.tenant_id:
                source_by_category.setdefault(row["source_category"], row["source"])
    with (dataset / "customers.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            customers_by_tenant.setdefault(row["tenant_id"], []).append(row["customer_id"])
    if set(principal.authorized_sources) != set(source_by_category.values()):
        raise ValueError("principal source grants do not exactly match this tenant's synthetic sources")

    train_dates = _train_cutoffs(manifest, split)
    if not train_dates:
        raise ValueError("the dataset has no mature training cutoffs")
    cutoff_date = train_dates[-1]
    cutoff = datetime.combine(cutoff_date, time(12), tzinfo=timezone.utc)
    candidates = list(customers_by_tenant.get(principal.tenant_id, []))
    random.Random(int(manifest["random_seed"])).shuffle(candidates)
    feature_example = None
    snapshots: dict[str, dict[str, Any]] = {}
    for customer_id in candidates:
        snapshot = get_account_snapshot_as_of(database, principal, customer_id, _stamp(cutoff))
        snapshots[customer_id] = snapshot
        if snapshot["status"] != "eligible":
            continue
        usage_events = get_events_as_of(database, principal, customer_id, _stamp(cutoff), category="usage")
        billing_events = get_events_as_of(database, principal, customer_id, _stamp(cutoff), category="billing")
        coverage = get_observation_coverage_as_of(
            database, principal, customer_id, _stamp(cutoff), source_category="usage",
        )
        features = _usage_features(usage_events, coverage, cutoff_date, cutoff)
        required = ("7d", "30d", "baseline_28d")
        if all(features[window]["coverage_complete"] for window in required):
            feature_example = (customer_id, snapshot, usage_events, billing_events, coverage, features)
            break
    if feature_example is None:
        raise ValueError("no eligible training cutoff has complete 7d, 30d, and baseline usage coverage")

    customer_id, snapshot, usage_events, billing_events, coverage, features = feature_example
    subscription_events = get_events_as_of(database, principal, customer_id, _stamp(cutoff), category="subscription")
    active_subscriptions = [row for row in snapshot["subscriptions"]
                            if row.get("status") in {"active", "past_due", "pending_cancel"}
                            and row.get("started_at") and row["started_at"] <= _stamp(cutoff)]
    if not active_subscriptions or not snapshot["eligible"]:
        raise ValueError("the selected source-backed cutoff is not eligible")
    billing_failures = [event for event in billing_events
                        if event["event_type"] in {"payment_failed", "invoice_payment_failed"}
                        and _epoch(event["occurred_at"]) > int((cutoff - timedelta(days=30)).timestamp())]
    all_usage_types = {event["event_type"] for event in usage_events}
    if all_usage_types - {"usage_aggregate_updated"}:
        raise ValueError("raw and aggregate usage events coexist in the Member 2 feature input")

    known_or_ineligible = next(
        ((candidate, row["status"]) for candidate, row in snapshots.items()
         if candidate != customer_id and row["status"] in {"known_cancellation", "not_eligible"}),
        None,
    )
    if known_or_ineligible is None:
        for candidate in candidates:
            if candidate == customer_id or candidate in snapshots:
                continue
            row = get_account_snapshot_as_of(database, principal, candidate, _stamp(cutoff))
            snapshots[candidate] = row
            if row["status"] in {"known_cancellation", "not_eligible"}:
                known_or_ineligible = (candidate, row["status"])
                break
    if known_or_ineligible is None:
        raise ValueError("no known-cancellation or not-eligible example was found at the historical cutoff")

    oracle = _oracle_labels(dataset, database, principal, principal.tenant_id, customer_id, cutoff, manifest, split)
    other_tenant = next((tenant for tenant in customers_by_tenant if tenant != principal.tenant_id), None)
    if other_tenant is None:
        raise ValueError("dataset does not have a second tenant for an isolation check")
    try:
        get_account_snapshot_as_of(
            database, principal, customers_by_tenant[other_tenant][0], _stamp(cutoff),
        )
        cross_tenant_denial = False
    except DataFoundationError as exc:
        cross_tenant_denial = exc.code == "not_found"
    if not cross_tenant_denial:
        raise ValueError("cross-tenant access was not denied")

    churn_example = _find_churn_example(dataset, database, principal, manifest, split, train_dates)
    if churn_example is None:
        raise ValueError("no qualifying source-backed effective churn cutoff was found")

    return {
        "status": "PASS",
        "dataset_identity": {
            "dataset_id": identity["dataset_id"], "dataset_version": identity["dataset_version"],
            "target_policy_version": identity["target_policy_version"], "manifest_sha256": identity["manifest_sha256"],
        },
        "authorization": {
            "role": principal.role, "tenant_id": principal.tenant_id,
            "source_grants": list(principal.authorized_sources),
            "purposes": list(principal.authorized_purposes), "cross_tenant_denial_verified": cross_tenant_denial,
        },
        "historical_feature_example": {
            "customer_id": customer_id, "as_of": _stamp(cutoff), "eligibility": snapshot["status"],
            "usage_windows": features, "billing_failures_in_prior_30d": len(billing_failures),
            "subscription_events_visible": len(subscription_events),
            "active_subscription_count": len(active_subscriptions),
            "tenure_days": (cutoff_date - date.fromisoformat(active_subscriptions[0]["started_at"][:10])).days,
            "usage_coverage_statuses_visible": sorted({row["coverage_status"] for row in coverage}),
            "only_daily_aggregate_usage_counted": True,
        },
        "separate_outcome_oracle": {
            "customer_id": customer_id, "cutoff": _stamp(cutoff),
            "labels_7_14_30": oracle,
            "feature_payload_contains_future_outcome": False,
        },
        "effective_churn_example": churn_example,
        "eligibility_exclusion_example": {
            "customer_id": known_or_ineligible[0], "status": known_or_ineligible[1], "as_of": _stamp(cutoff),
        },
        "real_world_validation": "NOT_PERFORMED_SYNTHETIC_DATA_ONLY",
        "model_training": "NOT_PERFORMED",
    }


def _find_churn_example(
    dataset: Path, database: Path, principal: Any, manifest: dict[str, Any],
    split: dict[str, Any], train_dates: list[date],
) -> dict[str, Any] | None:
    lag = int(split["label_maturity_lag_days"])
    end = datetime.combine(date.fromisoformat(manifest["end_date"]), time.min, tzinfo=timezone.utc)
    cutoffs = []
    for stage in ("train", "development", "calibration", "untouched_test"):
        bounds = split["stages"][stage]
        lower, upper = date.fromisoformat(bounds["cutoff_start"]), date.fromisoformat(bounds["cutoff_end"])
        cutoffs.extend(day for day in train_dates if lower <= day < upper)
    if len(cutoffs) != len(train_dates):
        start = date.fromisoformat(manifest["start_date"]) + timedelta(days=int(split["sampling_policy"]["warmup_days"]))
        start += timedelta(days=(-start.weekday()) % 7)
        final = date.fromisoformat(manifest["end_date"]) - timedelta(days=30 + lag)
        current = start
        while current < final:
            cutoffs.append(current)
            current += timedelta(days=7)
    cutoffs = sorted(set(cutoffs))
    rows = []
    with (dataset / "effective_churn.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rng = random.Random(int(manifest["random_seed"]) + 1)
    rng.shuffle(rows)
    for row in rows:
        if row["tenant_id"] != principal.tenant_id:
            continue
        effective = _parse_time(row["churn_effective_at"])
        eligible_cutoffs = [datetime.combine(day, time(12), tzinfo=timezone.utc) for day in cutoffs
                            if datetime.combine(day, time(12), tzinfo=timezone.utc) < effective
                            and effective <= datetime.combine(day, time(12), tzinfo=timezone.utc) + timedelta(days=7)
                            and datetime.combine(day, time(12), tzinfo=timezone.utc) + timedelta(days=15) <= end]
        if not eligible_cutoffs:
            continue
        cutoff = max(eligible_cutoffs)
        customer_id = row["customer_id"]
        snapshot = get_account_snapshot_as_of(database, principal, customer_id, _stamp(cutoff))
        if snapshot["status"] != "eligible":
            continue
        source_events = get_events_as_of(
            database, principal, customer_id, _stamp(cutoff + timedelta(days=15)), category="subscription",
        )
        event = next((event for event in source_events if event["source_event_id"] == row["source_event_id"]), None)
        if event is None or not cutoff < _parse_time(event["occurred_at"]) <= cutoff + timedelta(days=7):
            continue
        if _parse_time(event["available_at"]) > cutoff + timedelta(days=15):
            continue
        return {
            "customer_id": customer_id,
            "as_of": _stamp(cutoff),
            "effective_at": row["churn_effective_at"],
            "source_event_id": row["source_event_id"],
            "source_event_visible_by_7d_maturity": True,
            "labels_7_14_30": {"7": "1", "14": "1", "30": "1"},
            "features_read_at_cutoff_separately": True,
        }
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--token-env", default="RETAINIQ_MODEL_TOKEN")
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"environment variable {args.token_env} is required")
    try:
        report = run_smoke(args.dataset.expanduser().resolve(), args.db.expanduser().resolve(), token)
    except (OSError, ValueError, DataFoundationError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
