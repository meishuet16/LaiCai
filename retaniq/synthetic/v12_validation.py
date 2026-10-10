"""Independent, bounded-memory validation for Synthetic SaaS v1.2 exports."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import sqlite3
import tempfile
from array import array
from bisect import bisect_right
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from retaniq.currency_codes import ISO4217_CURRENT_CODES
from retaniq.data_foundation import EVENT_TYPES
from .v12_generator import (
    CHURN_FIELDS,
    COVERAGE_FIELDS,
    CUSTOMER_FIELDS,
    EVENT_FIELDS,
    IDENTITY_FIELDS,
    PLAN_FIELDS,
)


REQUIRED_FILES = {
    "dataset_manifest.json", "customers.csv", "tenants.csv", "customer_identities.csv",
    "plan_catalog.csv", "subscription_events.csv", "billing_events.csv", "usage_events.csv",
    "observation_coverage.csv.gz", "canonical_events.csv", "effective_churn.csv",
    "scenario_coverage.json", "quality_report.json", "split_manifest.json",
    "label_oracle_fixtures.json", "adversarial_fixtures.json",
}
FORBIDDEN_FIELDS = {"will_churn", "churn_risk_class", "future_dropout_reason", "latent_hazard", "latent_state"}
VALID_COVERAGE = {
    "complete", "partial", "outage", "delayed", "missing_historical_backfill", "not_created",
    "entitlement_ended", "censored",
}
VALID_VERIFICATION = {"SOURCE_VERIFIED", "SOURCE_PROXY", "LATENT_ONLY", "NOT_OBSERVED", "NOT_SUPPORTED"}


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _row_digest(row: dict[str, str]) -> str:
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _epoch(value: str) -> int:
    return int(_timestamp(value).timestamp())


def _coverage_covers(
    intervals: list[tuple[int, int, str, int, float]],
    left: int,
    right: int,
    knowledge_at: int,
) -> bool:
    """Check contiguous complete source observation over a half-open interval."""
    if right <= left or not intervals:
        return False
    cursor = left
    index = max(0, bisect_right(intervals, left, key=lambda item: item[0]) - 1)
    for covered_from, covered_through, status, available, completeness in intervals[index:]:
        if covered_through <= cursor:
            continue
        if covered_from > cursor:
            return False
        if status not in {"complete", "delayed"} or completeness < 1.0 or available > knowledge_at:
            return False
        cursor = max(cursor, covered_through)
        if cursor >= right:
            return True
    return False


def _state_at(summary: dict[str, Any], cutoff: int) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for event in summary["subscription_events"]:
        occurred, available, event_type, event_id, subscription_id, status, started, period_end, cancellation_at, *_ = event
        if occurred > cutoff:
            break
        if available > cutoff:
            continue
        state = states.setdefault(subscription_id, {"subscription_id": subscription_id})
        if event_type == "subscription_created":
            if status is not None:
                state["status"] = status
            if started is not None:
                state["started_at"] = started
            if period_end is not None:
                state["current_period_end"] = period_end
        elif event_type == "subscription_updated":
            if status is not None:
                state["status"] = status
            if started is not None:
                state["started_at"] = started
            if period_end is not None:
                state["current_period_end"] = period_end
        elif event_type == "cancellation_requested":
            state["status"] = "pending_cancel"
            state["cancellation_requested_at"] = occurred
            if period_end is not None:
                state["current_period_end"] = period_end
        elif event_type in {
            "subscription_cancelled_effective", "subscription_non_renewed_effective",
            "subscription_involuntary_terminated",
        }:
            state["status"] = "ended"
            state["ended_at"] = occurred
    return states


def _usage_sum(summary: dict[str, Any], left_day: date, right_day: date, cutoff: int, start: date) -> int:
    values: array | None = summary.get("usage_values")
    if values is None:
        total = 0
    else:
        left = max(0, (left_day - start).days)
        right = min(len(values), (right_day - start).days)
        total = sum(values[left:right]) if right > left else 0
    left_index = (left_day - start).days
    right_index = (right_day - start).days
    total += sum(quantity for day_index, quantity, available in summary["late_usage"]
                 if left_index <= day_index < right_index and available <= cutoff)
    return int(total)


def validate_v12_dataset(dataset_path: Path | str) -> dict[str, Any]:
    path = Path(dataset_path).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    measured: Counter[str] = Counter()
    if not path.is_dir():
        return {"status": "FAIL", "errors": ["dataset directory does not exist"], "warnings": [], "measured_counts": {}}
    file_names = {item.relative_to(path).as_posix() for item in path.rglob("*") if item.is_file()}
    missing = sorted(REQUIRED_FILES - file_names)
    if missing:
        return {"status": "FAIL", "errors": [f"missing required file: {name}" for name in missing], "warnings": [], "measured_counts": {}}
    documentation = path / "documentation"
    required_docs = {
        "data_dictionary.md", "generation_methodology.md", "synthetic_label_policy.md",
        "dataset_isolation.md", "reproduction_instructions.md",
    }
    if not documentation.is_dir() or required_docs - {item.name for item in documentation.glob("*.md")}:
        errors.append("generated documentation set is incomplete")
    try:
        manifest = json.loads((path / "dataset_manifest.json").read_text(encoding="utf-8"))
        scenarios = json.loads((path / "scenario_coverage.json").read_text(encoding="utf-8"))
        quality = json.loads((path / "quality_report.json").read_text(encoding="utf-8"))
        split = json.loads((path / "split_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "FAIL", "errors": ["a required JSON artifact is invalid"], "warnings": [], "measured_counts": {}}

    if manifest.get("dataset_version") != "1.2.0" or manifest.get("generator_code_version") != "synthetic-saas-v1.2":
        errors.append("manifest is not Synthetic SaaS v1.2")
    if manifest.get("generator_build_revision") != manifest.get("configuration", {}).get("generator_build_revision"):
        errors.append("generator build revision differs from the recorded configuration")
    if manifest.get("dataset_type") != "synthetic_saas" or manifest.get("no_real_customer_data") is not True:
        errors.append("manifest synthetic provenance is missing")
    if manifest.get("track") != "synthetic_saas" or manifest.get("target") != "effective_account_churn_7_14_30":
        errors.append("dataset track or target isolation is missing")
    if manifest.get("end_date_exclusive") is not True:
        errors.append("simulation end date must be explicitly exclusive")
    if split.get("dataset_id") != manifest.get("dataset_id") or split.get("target_policy_version") != manifest.get("target_policy_version"):
        errors.append("split manifest identity differs from dataset manifest")
    if quality.get("dataset_id") != manifest.get("dataset_id") or quality.get("dataset_type") != "synthetic_saas":
        errors.append("quality report identity differs from dataset manifest")
    if scenarios.get("dataset_id") != manifest.get("dataset_id") or scenarios.get("overlap_allowed") is not True:
        errors.append("scenario report identity or overlap policy is invalid")

    expected_hashes = manifest.get("file_hashes", {})
    expected_sizes = manifest.get("file_sizes_bytes", {})
    if set(expected_hashes) != file_names - {"dataset_manifest.json"}:
        errors.append("manifest hash inventory does not match generated files")
    for name, expected in expected_hashes.items():
        file_path = path / Path(name)
        if not file_path.is_file():
            errors.append(f"hashed file is missing: {name}")
            continue
        if _sha256(file_path) != expected:
            errors.append(f"hash mismatch: {name}")
        if expected_sizes.get(name) != file_path.stat().st_size:
            errors.append(f"file size mismatch: {name}")

    if scenarios.get("overlap_allowed") is not True:
        errors.append("scenario overlap must be allowed")
    for scenario in scenarios.get("scenarios", []):
        if scenario.get("verification_status") not in VALID_VERIFICATION:
            errors.append("scenario report has an invalid verification status")
        if not scenario.get("scenario_name") or not scenario.get("detection_rule") or not scenario.get("source_evidence"):
            errors.append("scenario report is missing a stable rule or evidence reference")
        if not isinstance(scenario.get("distinct_account_count"), int) or scenario["distinct_account_count"] < 0:
            errors.append("scenario account count is invalid")
    if quality.get("direct_target_fields_exported") is not False or quality.get("latent_state_exported") is not False:
        errors.append("quality report indicates target or latent-state leakage")

    start = date.fromisoformat(manifest["start_date"])
    end = date.fromisoformat(manifest["end_date"])
    if end <= start:
        errors.append("simulation dates are invalid")
    stages = split.get("stages", {})
    maturity_lag_days = split.get("label_maturity_lag_days")
    if isinstance(maturity_lag_days, bool) or not isinstance(maturity_lag_days, int) or maturity_lag_days < 0:
        errors.append("split manifest maturity lag is invalid")
        maturity_lag_days = 8
    maximum_label_span = 30 + maturity_lag_days
    stage_names = ("train", "development", "calibration", "untouched_test")
    ordered_stages = sorted(stages, key=lambda name: stages[name].get("cutoff_start", ""))
    if set(stages) != set(stage_names) or ordered_stages != list(stage_names):
        errors.append("chronological stages are missing or out of order")
    elif split.get("cohort_readiness") == "READY":
        if start != date(2024, 10, 1) or end != date(2026, 10, 1):
            errors.append("chronological cohorts are marked ready outside the default 24-month window")
        first_cutoff = start + timedelta(days=int(split.get("sampling_policy", {}).get("warmup_days", 63)))
        first_cutoff += timedelta(days=(-first_cutoff.weekday()) % 7)
        final_cutoff = end - timedelta(days=maximum_label_span)
        sampled_dates: list[date] = []
        current = first_cutoff
        while current < final_cutoff:
            sampled_dates.append(current)
            current += timedelta(days=7)
        sampled_by_stage = {
            name: [day for day in sampled_dates
                   if date.fromisoformat(bounds["cutoff_start"]) <= day < date.fromisoformat(bounds["cutoff_end"])]
            for name, bounds in stages.items()
        }
        for previous_name, next_name in zip(stage_names, stage_names[1:]):
            previous_dates = sampled_by_stage[previous_name]
            next_dates = sampled_by_stage[next_name]
            if previous_dates and next_dates and previous_dates[-1] + timedelta(days=maximum_label_span) > next_dates[0]:
                errors.append(f"{previous_name} labels can mature across the {next_name} boundary")
        test_dates = sampled_by_stage["untouched_test"]
        if test_dates and test_dates[-1] + timedelta(days=maximum_label_span) > end:
            errors.append("untouched test labels do not have a full 30-day horizon and availability lag")
    elif split.get("cohort_readiness") == "NOT_READY_CUSTOM_WINDOW":
        warnings.append("custom simulation window does not claim chronological training cohort readiness")
    else:
        errors.append("split manifest has an unknown cohort readiness state")

    customers: dict[tuple[str, str], dict[str, str]] = {}
    with (path / "customers.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CUSTOMER_FIELDS or FORBIDDEN_FIELDS.intersection(reader.fieldnames or ()):
            errors.append("customer export schema is invalid or leaks a target field")
        for row in reader:
            key = (row.get("tenant_id", ""), row.get("customer_id", ""))
            if not all(key) or key in customers:
                errors.append("customer identity is missing or duplicated")
                continue
            if row.get("dataset_type") != "synthetic_saas":
                errors.append("customer row lacks synthetic provenance")
            customers[key] = row
    measured["customers"] = len(customers)
    if len(customers) != manifest.get("account_count"):
        errors.append("manifest account count differs from customer export")

    simulation_days = max(1, (end - start).days)
    event_summaries: dict[tuple[str, str], dict[str, Any]] = {}
    for (tenant_id, customer_id), customer in customers.items():
        event_summaries[(tenant_id, customer_id)] = {
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "created_at": _epoch(customer["account_created_at"]),
            "created_date": date.fromisoformat(customer["account_created_at"][:10]),
            "cohort": customer["onboarding_cohort"],
            "usage_values": None,
            "late_usage": [],
            "usage_rows": 0,
            "usage_sessions": 0,
            "usage_features": Counter(),
            "feature_dates": {},
            "subscription_currencies": Counter(),
            "subscription_events": [],
            "billing_events": [],
            "source_churn_events": [],
            "account_churns": [],
            "plan_states": {},
            "missing_mrr": False,
        }

    identities: dict[tuple[str, str, str], str] = {}
    source_category: dict[tuple[str, str], str] = {}
    with (path / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != IDENTITY_FIELDS:
            errors.append("customer identity schema is invalid")
        for row in reader:
            customer_key = (row.get("tenant_id", ""), row.get("customer_id", ""))
            identity_key = (row.get("tenant_id", ""), row.get("source", ""), row.get("external_customer_id", ""))
            if customer_key not in customers:
                errors.append("identity references an unknown or cross-tenant customer")
            if identity_key in identities:
                errors.append("source identity is duplicated")
            identities[identity_key] = row.get("customer_id", "")
            source_key = (row.get("tenant_id", ""), row.get("source", ""))
            prior = source_category.setdefault(source_key, row.get("source_category", ""))
            if prior != row.get("source_category"):
                errors.append("a source identity mixes event categories")
    measured["customer_identities"] = len(identities)

    plan_ids: set[tuple[str, str]] = set()
    with (path / "plan_catalog.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PLAN_FIELDS:
            errors.append("plan catalogue schema is invalid")
        for row in reader:
            key = (row.get("tenant_id", ""), row.get("plan_id", ""))
            if not all(key) or key in plan_ids:
                errors.append("plan identity is missing or duplicated")
            plan_ids.add(key)
            try:
                if int(row["amount_minor"]) < 0 or int(row["billing_interval_count"]) < 1:
                    errors.append("plan amount or billing interval count is invalid")
                if row["currency"] not in ISO4217_CURRENT_CODES:
                    errors.append("plan currency is invalid")
            except (KeyError, ValueError):
                errors.append("plan numeric fields are invalid")
    measured["plans"] = len(plan_ids)

    temp_dir = tempfile.TemporaryDirectory(prefix="retaniq-v12-validate-")
    db = sqlite3.connect(str(Path(temp_dir.name) / "event_keys.sqlite3"))
    db.execute("CREATE TABLE event_rows (tenant_id TEXT, source TEXT, event_id TEXT, category TEXT, digest TEXT, PRIMARY KEY(tenant_id, source, event_id))")
    batch: list[tuple[str, str, str, str, str]] = []
    effective_events: dict[str, tuple[str, str, str, str, str]] = {}
    subscription_event_by_id: dict[str, tuple[str, str, str, str, str, str]] = {}
    subscription_owners: dict[tuple[str, str], str] = {}
    usage_rows_by_customer: Counter[tuple[str, str]] = Counter()
    active_days_by_customer: Counter[tuple[str, str]] = Counter()
    event_types_by_customer: dict[tuple[str, str], Counter[str]] = {}
    tenant_weekday_sessions: Counter[tuple[str, int]] = Counter()
    tenant_month_sessions: Counter[tuple[str, str]] = Counter()
    file_counts: Counter[str] = Counter()

    with (path / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != EVENT_FIELDS or FORBIDDEN_FIELDS.intersection(reader.fieldnames or ()):
            errors.append("canonical event schema is invalid or leaks a target field")
        for line_number, row in enumerate(reader, start=2):
            measured["canonical_events"] += 1
            file_counts[row.get("source_category", "")] += 1
            tenant_id, customer_id, source, event_id = (row.get(key, "") for key in ("tenant_id", "customer_id", "source", "source_event_id"))
            category = row.get("source_category", "")
            if (tenant_id, customer_id) not in customers:
                errors.append(f"event references unknown customer at canonical line {line_number}")
            if identities.get((tenant_id, source, row.get("external_customer_id", ""))) != customer_id:
                errors.append(f"event identity mismatch at canonical line {line_number}")
            if source_category.get((tenant_id, source)) != category:
                errors.append(f"event source category mismatch at canonical line {line_number}")
            event_type = row.get("event_type", "")
            if event_type not in EVENT_TYPES:
                errors.append(f"unsupported event type at canonical line {line_number}")
                continue
            expected_category, allowed = EVENT_TYPES[event_type]
            if expected_category != category:
                errors.append(f"event category mismatch at canonical line {line_number}")
            try:
                occurred = _timestamp(row["occurred_at"])
                available = _timestamp(row["source_available_at"])
                simulated_received = _timestamp(row["simulated_received_at"])
                if not occurred <= available <= simulated_received:
                    errors.append(f"impossible source event time ordering at canonical line {line_number}")
            except (KeyError, TypeError, ValueError):
                errors.append(f"invalid source event timestamp at canonical line {line_number}")
                continue
            try:
                attributes = json.loads(row.get("attributes_json", ""))
            except json.JSONDecodeError:
                errors.append(f"invalid event JSON at canonical line {line_number}")
                continue
            if not isinstance(attributes, dict) or set(attributes) - allowed or FORBIDDEN_FIELDS.intersection(attributes):
                errors.append(f"unsupported or latent event attribute at canonical line {line_number}")
                continue
            sub_id = attributes.get("subscription_id")
            if sub_id:
                owner_key = (tenant_id, sub_id)
                prior = subscription_owners.setdefault(owner_key, customer_id)
                if prior != customer_id:
                    errors.append(f"subscription ownership conflict at canonical line {line_number}")
            if "amount_minor" in attributes:
                if isinstance(attributes["amount_minor"], bool) or not isinstance(attributes["amount_minor"], int) or attributes["amount_minor"] < 0:
                    errors.append(f"invalid monetary amount at canonical line {line_number}")
                if attributes.get("currency") not in ISO4217_CURRENT_CODES:
                    errors.append(f"invalid currency at canonical line {line_number}")
            if event_type == "usage_aggregate_updated":
                if occurred.hour or occurred.minute or occurred.second or occurred.microsecond:
                    errors.append(f"daily usage window does not end at UTC midnight at canonical line {line_number}")
                if attributes.get("unit") != "sessions" or not isinstance(attributes.get("quantity"), int) or isinstance(attributes.get("quantity"), bool) or attributes.get("quantity", 0) <= 0:
                    errors.append(f"daily usage aggregate is invalid at canonical line {line_number}")
                usage_rows_by_customer[(tenant_id, customer_id)] += 1
                active_days_by_customer[(tenant_id, customer_id)] += 1
                summary = event_summaries[(tenant_id, customer_id)]
                if summary["usage_values"] is None:
                    summary["usage_values"] = array("I", [0]) * simulation_days
                window_start = occurred.date() - timedelta(days=1)
                day_index = (window_start - start).days
                quantity = int(attributes["quantity"])
                summary["usage_rows"] += 1
                summary["usage_sessions"] += quantity
                if 0 <= day_index < simulation_days:
                    if (available - occurred).total_seconds() > 24 * 3600:
                        summary["late_usage"].append((day_index, quantity, int(available.timestamp())))
                    else:
                        summary["usage_values"][day_index] += quantity
                feature = attributes.get("feature")
                if feature:
                    summary["usage_features"][feature] += 1
                    feature_dates = summary["feature_dates"].setdefault(feature, [window_start, window_start, 0])
                    feature_dates[0] = min(feature_dates[0], window_start)
                    feature_dates[1] = max(feature_dates[1], window_start)
                    feature_dates[2] += 1
                tenant_weekday_sessions[(tenant_id, window_start.weekday())] += quantity
                tenant_month_sessions[(tenant_id, window_start.strftime("%Y-%m"))] += quantity
            per_customer = event_types_by_customer.setdefault((tenant_id, customer_id), Counter())
            per_customer[event_type] += 1
            summary = event_summaries[(tenant_id, customer_id)]
            occurred_epoch = int(occurred.timestamp())
            available_epoch = int(available.timestamp())
            if expected_category == "subscription":
                sub_id = attributes.get("subscription_id", "")
                started_epoch = _epoch(attributes["started_at"]) if attributes.get("started_at") else None
                period_end_epoch = _epoch(attributes["current_period_end"]) if attributes.get("current_period_end") else None
                cancel_epoch = _epoch(attributes["cancellation_requested_at"]) if attributes.get("cancellation_requested_at") else None
                summary["subscription_events"].append((
                    occurred_epoch, available_epoch, event_type, event_id, sub_id,
                    attributes.get("status"), started_epoch, period_end_epoch, cancel_epoch,
                    attributes.get("plan_id"), attributes.get("billing_interval"),
                    attributes.get("billing_interval_count"), attributes.get("amount_minor"),
                    attributes.get("currency"), attributes.get("discount_minor"),
                ))
                subscription_event_by_id[event_id] = (
                    tenant_id, customer_id, row["occurred_at"], row["source_available_at"],
                    event_type, sub_id,
                )
                if event_type == "subscription_created" and not {"amount_minor", "currency"}.issubset(attributes):
                    summary["missing_mrr"] = True
                if attributes.get("plan_id"):
                    summary["plan_states"].setdefault(sub_id, set()).add((
                        attributes.get("plan_id"), attributes.get("billing_interval"),
                        attributes.get("billing_interval_count"), attributes.get("amount_minor"),
                    ))
            elif expected_category == "billing":
                summary["billing_events"].append((
                    occurred_epoch, available_epoch, event_type, event_id,
                    attributes.get("subscription_id"), attributes.get("amount_minor"), attributes.get("currency"),
                ))
            if expected_category == "subscription" and attributes.get("currency"):
                summary["subscription_currencies"][attributes["currency"]] += 1
            if event_type in {"subscription_cancelled_effective", "subscription_non_renewed_effective", "subscription_involuntary_terminated"}:
                effective_events[event_id] = (tenant_id, customer_id, row["occurred_at"], row["source_available_at"], event_type)
                summary["source_churn_events"].append((occurred_epoch, available_epoch, event_id, event_type))
            batch.append((tenant_id, source, event_id, category, _row_digest(row)))
            measured[f"{category}_events"] += 1
            if len(batch) >= 10000:
                before = db.total_changes
                db.executemany("INSERT OR IGNORE INTO event_rows VALUES (?, ?, ?, ?, ?)", batch)
                if db.total_changes - before != len(batch):
                    errors.append("canonical event identity is duplicated")
                db.commit()
                batch.clear()
    if batch:
        before = db.total_changes
        db.executemany("INSERT OR IGNORE INTO event_rows VALUES (?, ?, ?, ?, ?)", batch)
        if db.total_changes - before != len(batch):
            errors.append("canonical event identity is duplicated")
        db.commit()

    for filename, category in (("usage_events.csv", "usage"), ("billing_events.csv", "billing"), ("subscription_events.csv", "subscription")):
        count = 0
        with (path / filename).open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != EVENT_FIELDS:
                errors.append(f"{filename} schema is invalid")
            for row in reader:
                count += 1
                key = (row.get("tenant_id", ""), row.get("source", ""), row.get("source_event_id", ""))
                match = db.execute("SELECT category, digest FROM event_rows WHERE tenant_id=? AND source=? AND event_id=?", key).fetchone()
                if match != (category, _row_digest(row)):
                    errors.append(f"{filename} row does not match canonical event stream")
                    break
        if count != measured[f"{category}_events"]:
            errors.append(f"{filename} count differs from canonical events")
        measured[filename.removesuffix(".csv") + "_file_rows"] = count

    measured["usage_active_days"] = sum(active_days_by_customer.values())
    measured["subscription_owners"] = len(subscription_owners)
    if measured["canonical_events"] != sum(file_counts.values()):
        errors.append("canonical event category totals do not reconcile")

    churn_count = 0
    churn_customers: set[tuple[str, str]] = set()
    with (path / "effective_churn.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CHURN_FIELDS:
            errors.append("effective churn evidence schema is invalid")
        for row in reader:
            churn_count += 1
            key = (row.get("tenant_id", ""), row.get("customer_id", ""))
            churn_customers.add(key)
            source_event = effective_events.get(row.get("source_event_id", ""))
            if source_event is None or source_event[:3] != (key[0], key[1], row.get("churn_effective_at", "")):
                errors.append("effective churn row lacks a matching source lifecycle event")
            elif key in event_summaries:
                event_summaries[key]["account_churns"].append((
                    _epoch(row["churn_effective_at"]), _epoch(source_event[3]), row["source_event_id"],
                    row["churn_type"], int(row["episode_number"]),
                ))
    measured["effective_churn_episodes"] = churn_count
    measured["churned_accounts"] = len(churn_customers)
    churn_episodes_by_account: Counter[tuple[str, str]] = Counter()
    for summary in event_summaries.values():
        summary["subscription_events"].sort(key=lambda item: (item[0], item[1], item[3]))
    with (path / "effective_churn.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row.get("tenant_id", ""), row.get("customer_id", ""))
            source_event = subscription_event_by_id.get(row.get("source_event_id", ""))
            try:
                effective_at = _epoch(row["churn_effective_at"])
                episode_number = int(row["episode_number"])
                subscriptions_ended = int(row["subscriptions_ended_at_loss"])
            except (KeyError, TypeError, ValueError):
                errors.append("effective churn row has invalid episode or termination counts")
                continue
            churn_episodes_by_account[key] += 1
            if episode_number != churn_episodes_by_account[key]:
                errors.append("effective churn episode numbers are not sequential per account")
            if source_event is None or source_event[:2] != key or source_event[2] != row["churn_effective_at"]:
                continue
            if source_event[4] not in {
                "subscription_cancelled_effective", "subscription_non_renewed_effective",
                "subscription_involuntary_terminated",
            }:
                errors.append("effective churn evidence references a non-termination source event")
                continue
            summary = event_summaries.get(key)
            if summary is None:
                continue
            state_at_loss = _state_at(summary, _epoch(source_event[3]))
            surviving = [state for subscription_id, state in state_at_loss.items()
                         if subscription_id != source_event[5]
                         and state.get("status") in {"active", "past_due", "pending_cancel"}
                         and state.get("started_at") is not None and state["started_at"] <= effective_at
                         and (state.get("current_period_end") is None or state["current_period_end"] >= effective_at)]
            if surviving:
                errors.append(
                    "effective churn was recorded while another paid subscription remained entitled "
                    f"for {key[0]}/{key[1]} at {row['churn_effective_at']}: "
                    f"{sorted(surviving_state['subscription_id'] for surviving_state in surviving)}"
                )
            expected_ended = sum(
                event[0] == effective_at and event[2] in {
                    "subscription_cancelled_effective", "subscription_non_renewed_effective",
                    "subscription_involuntary_terminated",
                }
                for event in summary["subscription_events"]
            )
            if subscriptions_ended != expected_ended:
                errors.append("effective churn termination count differs from the subscription source events")

    cohort_ready = split.get("cohort_readiness") == "READY"
    cohort_label_counts: dict[str, Any] = {"status": "AUDIT_PENDING" if cohort_ready else "NOT_READY_CUSTOM_WINDOW", "stages": {}}
    stage_dates: dict[str, list[date]] = {name: [] for name in ("train", "development", "calibration", "untouched_test")}
    if cohort_ready:
        first_cutoff = start + timedelta(days=int(split.get("sampling_policy", {}).get("warmup_days", 63)))
        first_cutoff += timedelta(days=(-first_cutoff.weekday()) % 7)
        final_cutoff = end - timedelta(days=34)
        all_cutoffs: list[date] = []
        current_cutoff = first_cutoff
        while current_cutoff < final_cutoff:
            all_cutoffs.append(current_cutoff)
            current_cutoff += timedelta(days=7)
        for stage_name, bounds in split.get("stages", {}).items():
            lower = date.fromisoformat(bounds["cutoff_start"])
            upper = date.fromisoformat(bounds["cutoff_end"])
            stage_dates[stage_name] = [value for value in all_cutoffs if lower <= value < upper]

    def _new_horizon_counts() -> dict[str, Any]:
        return {
            "positive": 0, "negative": 0, "unknown": 0,
            "unique_accounts": set(), "positive_accounts": set(), "negative_accounts": set(),
            "positive_churn_episodes": set(), "mature_followup_cutoffs": 0,
            "outcome_coverage_complete_cutoffs": 0, "eligible_samples": 0,
            "unknown_due_to_immaturity": 0, "unknown_due_to_incomplete_outcome_coverage": 0,
        }

    for stage_name, dates in stage_dates.items():
        cohort_label_counts["stages"][stage_name] = {
            "cutoff_dates": len(dates), "candidate_account_cutoffs": 0,
            "eligible_samples": 0, "unique_eligible_accounts": set(),
            "known_cancellation_exclusions": 0,
            "feature_sufficiency": {"7d": 0, "14d": 0, "30d": 0, "baseline_28d": 0,
                                    "insufficient_7d": 0, "insufficient_30d": 0, "insufficient_baseline": 0},
            "usage_behavior": Counter(),
            "source_evidence": {
                "cutoffs_with_payment_failure_in_prior_30d": 0,
                "cutoffs_with_payment_recovery_in_prior_30d": 0,
                "cutoffs_with_payment_success_in_prior_30d": 0,
                "cutoffs_with_subscription_renewal_in_prior_30d": 0,
                "cutoffs_with_plan_change_in_prior_30d": 0,
                "cutoffs_with_multiple_active_subscriptions": 0,
                "accounts_with_payment_failure": set(),
                "accounts_with_payment_recovery": set(),
                "accounts_with_subscription_renewal": set(),
                "accounts_with_plan_change": set(),
            },
            "horizons": {str(horizon): _new_horizon_counts() for horizon in (7, 14, 30)},
        }

    scenario_rules = {
        "source_observed_churn": "At least one final-entitlement loss is present in effective_churn.csv and references its canonical source event.",
        "full_period_observed_no_churn": "No effective account-loss event and complete subscription outcome coverage through the last fully covered interval.",
        "high_usage_before_churn": "At least 20 daily sessions in a complete usage-covered 30-day window immediately before a source-backed account-loss event.",
        "low_usage_before_churn": "At most 3 daily sessions in a complete usage-covered 30-day window immediately before a source-backed account-loss event.",
        "high_usage_without_churn": "At least one eligible, fully observed 30-day window has 20 or more sessions and no source-backed loss appears in the full lifecycle ledger.",
        "low_usage_without_churn": "At least one eligible, fully observed 30-day window has at most 3 sessions and no source-backed loss appears in the full lifecycle ledger.",
        "measurable_usage_decline": "A fully observed personal 30-day window is at least 25 percent below the earlier non-overlapping 28-day baseline rate.",
        "measurable_usage_increase": "A fully observed personal 30-day window is at least 25 percent above the earlier non-overlapping 28-day baseline rate.",
        "temporary_decline_then_recovery": "Fully observed sampled personal windows show a 30-day decline of at least 35 percent from the earlier baseline followed within 14–70 days by recovery to at least 80 percent of that baseline.",
        "observed_30d_inactivity": "No usage aggregate is present in a 30-day interval whose usage source coverage is complete and visible as of the cutoff.",
        "long_inactivity_then_recovery": "A complete 30-day zero-session interval is followed by a later complete 30-day interval with positive sessions.",
        "predominant_feature_change": "Daily aggregates show more than one predominant feature for the same customer.",
        "predominant_feature_abandonment_proxy": "The last aggregate on a prior predominant feature precedes a later predominant feature after complete coverage; this is a source proxy, not proof of feature-level use.",
        "high_session_volume_variability": "At least 10 positive daily aggregates have a session-count coefficient of variation above 0.70.",
        "single_billing_failure": "Exactly one source-backed payment-failure event exists for the customer.",
        "repeated_billing_failures": "At least two source-backed payment-failure events exist for the customer.",
        "payment_recovery_after_failure": "An invoice paid event for a subscription follows a payment failure within 14 days.",
        "past_due_late_recovery": "A source-visible past_due subscription update is followed by invoice payment and an active entitlement extension within 7 days.",
        "past_due_termination": "A source-visible past_due subscription update is followed by involuntary termination within 8 days.",
        "payment_failure_without_churn": "A source-backed payment failure is not followed by account churn within 30 days.",
        "involuntary_termination": "The source-backed account-loss episode is classified as involuntary termination.",
        "voluntary_effective_cancellation": "A source-backed account-loss episode follows an effective voluntary cancellation.",
        "subscription_non_renewal": "A source-backed subscription_non_renewed_effective event ends an entitlement.",
        "known_cancellation_request": "A cancellation_requested source event precedes an effective end event.",
        "stable_subscription_renewal": "A dated active subscription update extends current_period_end and is not immediately followed by effective termination.",
        "plan_change": "Dated source events show more than one plan ID for one subscription.",
        "billing_interval_change": "Dated source events show more than one interval/count for one subscription.",
        "partial_subscription_cancellation": "One subscription ends while another subscription for the account remains entitled.",
        "multiple_active_subscriptions": "Two or more source-backed subscription entitlement intervals overlap.",
        "reactivation_after_churn": "A new subscription is created after a source-backed account-level churn episode.",
        "missing_mrr": "A subscription_created event omits its amount or currency fields.",
        "annual_subscription": "A source subscription event records a yearly billing interval.",
        "quarterly_subscription": "A source subscription event records a quarterly billing interval.",
        "account_specific_usage_gap": "The customer usage source ledger contains a partial or missing historical-backfill interval.",
        "source_outage_observed": "The customer/source coverage ledger records an outage interval.",
        "delayed_source_events": "At least one source event becomes available more than 24 hours after occurrence.",
        "silent_but_observed_account": "A complete usage-covered 30-day interval has no daily usage aggregate.",
        "newly_acquired_account_last_6m": "The source customer row places account creation within six months of the simulation end.",
        "right_censored_active_at_end": "At least one dated source subscription state remains entitled at the exclusive simulation end.",
        "complete_subscription_outcome_window": "The subscription source ledger has a complete interval available through the last full observed week.",
        "unknown_30d_outcome_windows": "An eligible uncanceled cutoff has no source-verified positive and lacks complete mature 30-day outcome coverage.",
        "unexpected_sudden_churn": "A source-backed loss follows a complete 30-day active usage window without a measurable 25 percent decline from the earlier non-overlapping baseline.",
        "repeated_usage_regime_changes": "At least two transitions among low, medium, and high fully observed 30-day usage across sampled cutoffs.",
        "price_change": "Dated source events for one subscription record a changed amount_minor.",
        "recurring_discount": "A source subscription event records a positive discount_minor.",
        "upgrade": "A dated subscription plan change increases amount_minor for the same subscription (source proxy for tier upgrade).",
        "downgrade": "A dated subscription plan change decreases amount_minor for the same subscription (source proxy for tier downgrade).",
        "currency_diversity": "Source subscription records use more than one ISO currency across the dataset.",
        "payment_failure_without_churn": "A source-backed payment failure is followed by complete subscription outcome coverage for 30 days without account churn.",
    }
    scenario_accounts: dict[str, set[tuple[str, str]]] = {name: set() for name in scenario_rules}
    scenario_event_counts: Counter[str] = Counter()
    usage_density_tenant: dict[str, Counter[str]] = {}
    usage_density_cohort: dict[str, Counter[str]] = {}
    feature_history_by_tenant: dict[str, Counter[str]] = {}
    feature_history_by_cohort: dict[str, Counter[str]] = {}
    behavior_by_tenant: dict[str, Counter[str]] = {}
    behavior_by_cohort: dict[str, Counter[str]] = {}
    behavior_window_counts: Counter[str] = Counter()
    unknown_30d_by_account: set[tuple[str, str]] = set()
    cutoff_stage = {cutoff: stage_name for stage_name, dates in stage_dates.items() for cutoff in dates}
    audited_currencies: set[str] = set()

    def audit_account(key: tuple[str, str], coverage_rows: list[dict[str, Any]]) -> None:
        summary = event_summaries.get(key)
        customer = customers.get(key)
        if summary is None or customer is None:
            return
        tenant_id, customer_id = key
        by_category: dict[str, list[tuple[int, int, str, int, float]]] = {"usage": [], "billing": [], "subscription": []}
        for row in coverage_rows:
            try:
                by_category[row["source_category"]].append((
                    _epoch(row["covered_from"]), _epoch(row["covered_through"]),
                    row["coverage_status"], _epoch(row["coverage_available_at"]),
                    float(row["coverage_completeness"]),
                ))
            except (KeyError, ValueError):
                continue
        for intervals in by_category.values():
            intervals.sort(key=lambda item: item[0])
        usage_intervals = by_category["usage"]
        outcome_intervals = by_category["subscription"]
        created_date = summary["created_date"]
        created_epoch = summary["created_at"]
        end_epoch = int(datetime.combine(end, time.min, tzinfo=timezone.utc).timestamp())
        end_for_coverage = end_epoch - 7 * 86400
        account_churns = sorted(summary["account_churns"])
        summary["subscription_events"].sort(key=lambda item: (item[0], item[1], item[3]))
        summary["billing_events"].sort(key=lambda item: (item[0], item[1], item[3]))
        account_event_count = len(summary["subscription_events"]) + len(summary["billing_events"]) + summary["usage_rows"]

        # Account-month exposure is explicit and includes time after churn, so
        # this event-density denominator is comparable across tenants/cohorts.
        exposure_months = max(0.0, (end - created_date).days / 30.4375)
        for grouping, group_key in ((usage_density_tenant, tenant_id), (usage_density_cohort, summary["cohort"])):
            totals = grouping.setdefault(group_key, Counter())
            totals["accounts"] += 1
            totals["account_months"] += exposure_months
            totals["usage_events"] += summary["usage_rows"]
            totals["usage_sessions"] += summary["usage_sessions"]

        if account_churns:
            scenario_accounts["source_observed_churn"].add(key)
            scenario_event_counts["source_observed_churn"] += len(account_churns)
        source_outage_rows = [row for row in coverage_rows if row["coverage_status"] == "outage"]
        usage_gap_rows = [row for row in coverage_rows if row["source_category"] == "usage" and row["coverage_status"] in {"partial", "missing_historical_backfill"}]
        if usage_gap_rows:
            scenario_accounts["account_specific_usage_gap"].add(key)
            scenario_event_counts["account_specific_usage_gap"] += len(usage_gap_rows)
        if source_outage_rows:
            scenario_accounts["source_outage_observed"].add(key)
            scenario_event_counts["source_outage_observed"] += len(source_outage_rows)
        if summary["missing_mrr"]:
            scenario_accounts["missing_mrr"].add(key)
            scenario_event_counts["missing_mrr"] += 1
        if len(summary["usage_features"]) > 1:
            scenario_accounts["predominant_feature_change"].add(key)
            scenario_event_counts["predominant_feature_change"] += len(summary["usage_features"])
            ordered_features = sorted(summary["feature_dates"].items(), key=lambda item: item[1][0])
            if len(ordered_features) > 1:
                prior_last = ordered_features[0][1][1]
                later_first = ordered_features[1][1][0]
                if later_first > prior_last and _coverage_covers(
                    usage_intervals,
                    int(datetime.combine(prior_last + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp()),
                    int(datetime.combine(later_first + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp()),
                    end_epoch,
                ):
                    scenario_accounts["predominant_feature_abandonment_proxy"].add(key)
                    scenario_event_counts["predominant_feature_abandonment_proxy"] += 1
        if summary["subscription_currencies"]:
            scenario_accounts["currency_diversity"].add(key)
            scenario_event_counts["currency_diversity"] += sum(summary["subscription_currencies"].values())

        positive_daily = [value for value in (summary["usage_values"] or ()) if value > 0]
        if len(positive_daily) >= 10:
            mean = sum(positive_daily) / len(positive_daily)
            variance = sum((value - mean) ** 2 for value in positive_daily) / len(positive_daily)
            if mean > 0 and math.sqrt(variance) / mean > 0.70:
                scenario_accounts["high_session_volume_variability"].add(key)
                scenario_event_counts["high_session_volume_variability"] += len(positive_daily)
        subscription_events = summary["subscription_events"]
        billing_events = summary["billing_events"]
        starts: dict[str, int] = {}
        ends: dict[str, int] = {}
        previous_contract: dict[str, tuple[int | None, int | None, str | None]] = {}
        renewal_event_ids: set[str] = set()
        plan_change_event_ids: set[str] = set()
        extended_renewals = 0
        amount_changes = 0
        amount_direction: Counter[str] = Counter()
        discounted_events = 0
        for event in subscription_events:
            occurred, _, event_type, _, subscription_id, _, started, _, _, plan_id, interval, interval_count, amount, currency, _ = event
            if event_type == "subscription_created":
                starts[subscription_id] = started if started is not None else occurred
            if currency:
                audited_currencies.add(currency)
            prior_contract = previous_contract.get(subscription_id)
            if event_type == "subscription_updated" and amount is not None and prior_contract and prior_contract[0] is not None:
                if amount != prior_contract[0]:
                    amount_changes += 1
                    if plan_id != prior_contract[2]:
                        amount_direction["upgrade" if amount > prior_contract[0] else "downgrade"] += 1
            if event_type == "subscription_updated" and event[7] is not None and event[5] == "active":
                if prior_contract and prior_contract[1] is not None and event[7] > prior_contract[1]:
                    extended_renewals += 1
                    renewal_event_ids.add(event[3])
            if event_type == "subscription_updated" and plan_id is not None:
                if prior_contract and prior_contract[2] is not None and plan_id != prior_contract[2]:
                    plan_change_event_ids.add(event[3])
            if event[14] is not None and event[14] > 0:
                discounted_events += 1
            if any(value is not None for value in (amount, event[7], plan_id)):
                previous_contract[subscription_id] = (
                    amount if amount is not None else (prior_contract[0] if prior_contract else None),
                    event[7] if event[7] is not None else (prior_contract[1] if prior_contract else None),
                    plan_id if plan_id is not None else (prior_contract[2] if prior_contract else None),
                )
            if event_type in {"subscription_cancelled_effective", "subscription_non_renewed_effective", "subscription_involuntary_terminated"}:
                ends[subscription_id] = occurred
        if len(starts) > 1:
            for _, state in summary["plan_states"].items():
                plan_ids = {row[0] for row in state if row[0] is not None}
                intervals = {(row[1], row[2]) for row in state if row[1] is not None}
                if len(plan_ids) > 1:
                    scenario_accounts["plan_change"].add(key)
                if len(intervals) > 1:
                    scenario_accounts["billing_interval_change"].add(key)
        else:
            for state in summary["plan_states"].values():
                plan_ids = {row[0] for row in state if row[0] is not None}
                intervals = {(row[1], row[2]) for row in state if row[1] is not None}
                if len(plan_ids) > 1:
                    scenario_accounts["plan_change"].add(key)
                if len(intervals) > 1:
                    scenario_accounts["billing_interval_change"].add(key)
        for states in summary["plan_states"].values():
            for _, interval, _, _, in states:
                if interval == "year":
                    scenario_accounts["annual_subscription"].add(key)
                if interval == "quarter":
                    scenario_accounts["quarterly_subscription"].add(key)
        scenario_event_counts["plan_change"] += int(key in scenario_accounts["plan_change"])
        scenario_event_counts["billing_interval_change"] += int(key in scenario_accounts["billing_interval_change"])
        scenario_event_counts["annual_subscription"] += int(key in scenario_accounts["annual_subscription"])
        scenario_event_counts["quarterly_subscription"] += int(key in scenario_accounts["quarterly_subscription"])

        if starts:
            ordered_changes: list[tuple[int, int]] = []
            for subscription_id, started in starts.items():
                ordered_changes.append((started, 1))
                if subscription_id in ends:
                    ordered_changes.append((ends[subscription_id], -1))
            active_count = maximum_active = 0
            for _, delta in sorted(ordered_changes, key=lambda item: (item[0], item[1])):
                active_count += delta
                maximum_active = max(maximum_active, active_count)
            if maximum_active > 1:
                scenario_accounts["multiple_active_subscriptions"].add(key)
                scenario_event_counts["multiple_active_subscriptions"] += maximum_active
            partial_ends = 0
            for ended_id, ended_at in ends.items():
                if any(other_id != ended_id and started <= ended_at and (other_id not in ends or ends[other_id] > ended_at)
                       for other_id, started in starts.items()):
                    partial_ends += 1
            if partial_ends:
                scenario_accounts["partial_subscription_cancellation"].add(key)
                scenario_event_counts["partial_subscription_cancellation"] += partial_ends
        if extended_renewals:
            scenario_accounts["stable_subscription_renewal"].add(key)
            scenario_event_counts["stable_subscription_renewal"] += extended_renewals
        if amount_changes:
            scenario_accounts["price_change"].add(key)
            scenario_event_counts["price_change"] += amount_changes
        if discounted_events:
            scenario_accounts["recurring_discount"].add(key)
            scenario_event_counts["recurring_discount"] += discounted_events
        for name, count in amount_direction.items():
            scenario_accounts[name].add(key)
            scenario_event_counts[name] += count
        if any(event[2] == "cancellation_requested" for event in subscription_events):
            scenario_accounts["known_cancellation_request"].add(key)
            scenario_event_counts["known_cancellation_request"] += sum(event[2] == "cancellation_requested" for event in subscription_events)
        if any(event[2] == "subscription_involuntary_terminated" for event in subscription_events):
            scenario_accounts["involuntary_termination"].add(key)
            scenario_event_counts["involuntary_termination"] += sum(event[2] == "subscription_involuntary_terminated" for event in subscription_events)
        if any(event[2] == "subscription_cancelled_effective" for event in subscription_events):
            scenario_accounts["voluntary_effective_cancellation"].add(key)
            scenario_event_counts["voluntary_effective_cancellation"] += sum(event[2] == "subscription_cancelled_effective" for event in subscription_events)
        if any(event[2] == "subscription_non_renewed_effective" for event in subscription_events):
            scenario_accounts["subscription_non_renewal"].add(key)
            scenario_event_counts["subscription_non_renewal"] += sum(event[2] == "subscription_non_renewed_effective" for event in subscription_events)
        if any(started > churn[0] for churn in account_churns for started in starts.values()):
            scenario_accounts["reactivation_after_churn"].add(key)
            scenario_event_counts["reactivation_after_churn"] += sum(
                started > churn[0] for churn in account_churns for started in starts.values()
            )

        failure_events = [event for event in billing_events if event[2] in {"payment_failed", "invoice_payment_failed"}]
        paid_events = [event for event in billing_events if event[2] in {"payment_succeeded", "invoice_paid"}]
        if len(failure_events) == 1:
            scenario_accounts["single_billing_failure"].add(key)
            scenario_event_counts["single_billing_failure"] += 1
        elif len(failure_events) > 1:
            scenario_accounts["repeated_billing_failures"].add(key)
            scenario_event_counts["repeated_billing_failures"] += len(failure_events)
        recovered = [failure for failure in failure_events if any(
            success[4] == failure[4] and 0 < success[0] - failure[0] <= 14 * 86400 for success in paid_events
        )]
        if recovered:
            scenario_accounts["payment_recovery_after_failure"].add(key)
            scenario_event_counts["payment_recovery_after_failure"] += len(recovered)
        past_due_events = [event for event in subscription_events
                           if event[2] == "subscription_updated" and event[5] == "past_due"]
        late_recoveries = []
        past_due_terminations = []
        for past_due in past_due_events:
            _, _, _, _, subscription_id = past_due[:5]
            recovered_within_dunning = any(
                success[4] == subscription_id and 0 < success[0] - past_due[0] <= 7 * 86400
                for success in paid_events
            ) and any(
                state[2] == "subscription_updated" and state[4] == subscription_id
                and state[5] == "active" and 0 < state[0] - past_due[0] <= 7 * 86400
                for state in subscription_events
            )
            terminated_within_dunning = any(
                state[2] == "subscription_involuntary_terminated" and state[4] == subscription_id
                and 0 < state[0] - past_due[0] <= 8 * 86400
                for state in subscription_events
            )
            if recovered_within_dunning:
                late_recoveries.append(past_due)
            if terminated_within_dunning:
                past_due_terminations.append(past_due)
        if late_recoveries:
            scenario_accounts["past_due_late_recovery"].add(key)
            scenario_event_counts["past_due_late_recovery"] += len(late_recoveries)
        if past_due_terminations:
            scenario_accounts["past_due_termination"].add(key)
            scenario_event_counts["past_due_termination"] += len(past_due_terminations)
        unchurned_failures = [failure for failure in failure_events if not any(
            failure[0] < churn[0] <= failure[0] + 30 * 86400 for churn in account_churns
        ) and _coverage_covers(
            outcome_intervals, failure[0], failure[0] + 30 * 86400,
            failure[0] + (30 + maturity_lag_days) * 86400,
        )]
        if unchurned_failures:
            scenario_accounts["payment_failure_without_churn"].add(key)
            scenario_event_counts["payment_failure_without_churn"] += len(unchurned_failures)

        delayed_count = sum(available - occurred > 86400 for occurred, available, *_ in subscription_events + billing_events)
        for day_index, _, available in summary["late_usage"]:
            window_end = int(datetime.combine(start + timedelta(days=day_index + 1), time.min, tzinfo=timezone.utc).timestamp())
            delayed_count += int(available - window_end > 86400)
        if delayed_count:
            scenario_accounts["delayed_source_events"].add(key)
            scenario_event_counts["delayed_source_events"] += delayed_count

        if account_churns:
            for churn in account_churns:
                churn_date = datetime.fromtimestamp(churn[0], timezone.utc).date()
                left = churn_date - timedelta(days=30)
                right = churn_date
                if left >= created_date and _coverage_covers(
                    usage_intervals,
                    int(datetime.combine(left, time.min, tzinfo=timezone.utc).timestamp()),
                    int(datetime.combine(right, time.min, tzinfo=timezone.utc).timestamp()), end_epoch,
                ):
                    before_churn = _usage_sum(summary, left, right, end_epoch, start)
                    if before_churn >= 20:
                        scenario_accounts["high_usage_before_churn"].add(key)
                        scenario_event_counts["high_usage_before_churn"] += 1
                    if before_churn <= 3:
                        scenario_accounts["low_usage_before_churn"].add(key)
                        scenario_event_counts["low_usage_before_churn"] += 1
                    older_left = left - timedelta(days=30)
                    if older_left >= created_date and _coverage_covers(
                        usage_intervals,
                        int(datetime.combine(older_left, time.min, tzinfo=timezone.utc).timestamp()),
                        int(datetime.combine(right, time.min, tzinfo=timezone.utc).timestamp()), end_epoch,
                    ):
                        prior = _usage_sum(summary, older_left, left, end_epoch, start)
                        if before_churn > 3 and before_churn >= 0.75 * prior:
                            scenario_accounts["unexpected_sudden_churn"].add(key)
                            scenario_event_counts["unexpected_sudden_churn"] += 1
        elif _coverage_covers(outcome_intervals, created_epoch, end_for_coverage, end_epoch):
            scenario_accounts["full_period_observed_no_churn"].add(key)
            scenario_event_counts["full_period_observed_no_churn"] += 1
        if _coverage_covers(outcome_intervals, created_epoch, end_for_coverage, end_epoch):
            scenario_accounts["complete_subscription_outcome_window"].add(key)
            scenario_event_counts["complete_subscription_outcome_window"] += 1
        if created_date >= end - timedelta(days=183):
            scenario_accounts["newly_acquired_account_last_6m"].add(key)
            scenario_event_counts["newly_acquired_account_last_6m"] += 1
        end_state = _state_at(summary, end_epoch - 1)
        entitled_at_end = [state for state in end_state.values()
                           if state.get("status") in {"active", "past_due", "pending_cancel"}
                           and state.get("started_at") is not None and state["started_at"] < end_epoch
                           and (state.get("current_period_end") is None or state["current_period_end"] >= end_epoch)]
        if entitled_at_end:
            scenario_accounts["right_censored_active_at_end"].add(key)
            scenario_event_counts["right_censored_active_at_end"] += len(entitled_at_end)

        feature_windows: list[tuple[date, int, int]] = []
        saw_inactivity = False
        regimes: list[str] = []
        for cutoff_date, stage_name in sorted(cutoff_stage.items()):
            if cutoff_date < created_date:
                continue
            cutoff = int(datetime.combine(cutoff_date, time(12), tzinfo=timezone.utc).timestamp())
            feature_end = int(datetime.combine(cutoff_date, time.min, tzinfo=timezone.utc).timestamp())
            stage = cohort_label_counts["stages"][stage_name]
            stage["candidate_account_cutoffs"] += 1
            active = [state for state in _state_at(summary, cutoff).values()
                      if state.get("status") in {"active", "past_due", "pending_cancel"}
                      and state.get("started_at") is not None and state["started_at"] <= cutoff]
            if not active:
                continue
            stage["eligible_samples"] += 1
            stage["unique_eligible_accounts"].add(customer_id)
            if len(active) > 1:
                scenario_accounts["multiple_active_subscriptions"].add(key)
            known_cancel = all(state.get("status") == "pending_cancel" or state.get("cancellation_requested_at") is not None for state in active)
            if known_cancel:
                stage["known_cancellation_exclusions"] += 1
                continue

            evidence = stage["source_evidence"]
            prior30_start = cutoff - 30 * 86400
            prior30_billing = [event for event in summary["billing_events"]
                               if prior30_start < event[0] <= cutoff and event[1] <= cutoff]
            recent_failures = [event for event in prior30_billing if event[2] in {"payment_failed", "invoice_payment_failed"}]
            recent_successes = [event for event in prior30_billing if event[2] in {"payment_succeeded", "invoice_paid"}]
            recovered_recently = any(
                failure[4] == success[4] and 0 < success[0] - failure[0] <= 14 * 86400
                for failure in recent_failures for success in recent_successes
            )
            recent_renewals = [event for event in summary["subscription_events"]
                               if event[3] in renewal_event_ids and prior30_start < event[0] <= cutoff and event[1] <= cutoff]
            recent_plan_changes = [event for event in summary["subscription_events"]
                                   if event[3] in plan_change_event_ids and prior30_start < event[0] <= cutoff and event[1] <= cutoff]
            evidence["cutoffs_with_payment_failure_in_prior_30d"] += int(bool(recent_failures))
            evidence["cutoffs_with_payment_recovery_in_prior_30d"] += int(recovered_recently)
            evidence["cutoffs_with_payment_success_in_prior_30d"] += int(bool(recent_successes))
            evidence["cutoffs_with_subscription_renewal_in_prior_30d"] += int(bool(recent_renewals))
            evidence["cutoffs_with_plan_change_in_prior_30d"] += int(bool(recent_plan_changes))
            evidence["cutoffs_with_multiple_active_subscriptions"] += int(len(active) > 1)
            if recent_failures:
                evidence["accounts_with_payment_failure"].add(customer_id)
            if recovered_recently:
                evidence["accounts_with_payment_recovery"].add(customer_id)
            if recent_renewals:
                evidence["accounts_with_subscription_renewal"].add(customer_id)
            if recent_plan_changes:
                evidence["accounts_with_plan_change"].add(customer_id)

            day_left_7 = cutoff_date - timedelta(days=7)
            day_left_14 = cutoff_date - timedelta(days=14)
            day_left_30 = cutoff_date - timedelta(days=30)
            day_left_base = cutoff_date - timedelta(days=58)
            day_right_base = cutoff_date - timedelta(days=30)
            suff7 = day_left_7 >= created_date and _coverage_covers(
                usage_intervals, int(datetime.combine(day_left_7, time.min, tzinfo=timezone.utc).timestamp()), feature_end, cutoff,
            )
            suff14 = day_left_14 >= created_date and _coverage_covers(
                usage_intervals, int(datetime.combine(day_left_14, time.min, tzinfo=timezone.utc).timestamp()), feature_end, cutoff,
            )
            suff30 = day_left_30 >= created_date and _coverage_covers(
                usage_intervals, int(datetime.combine(day_left_30, time.min, tzinfo=timezone.utc).timestamp()), feature_end, cutoff,
            )
            suffbase = day_left_base >= created_date and _coverage_covers(
                usage_intervals,
                int(datetime.combine(day_left_base, time.min, tzinfo=timezone.utc).timestamp()),
                int(datetime.combine(day_right_base, time.min, tzinfo=timezone.utc).timestamp()), cutoff,
            )
            suff = stage["feature_sufficiency"]
            suff["7d"] += int(suff7)
            suff["14d"] += int(suff14)
            suff["30d"] += int(suff30)
            suff["baseline_28d"] += int(suffbase)
            suff["insufficient_7d"] += int(not suff7)
            suff["insufficient_30d"] += int(not suff30)
            suff["insufficient_baseline"] += int(not suffbase)
            suff["insufficient_7d_short_tenure"] = suff.get("insufficient_7d_short_tenure", 0) + int(not suff7 and day_left_7 < created_date)
            suff["insufficient_7d_coverage"] = suff.get("insufficient_7d_coverage", 0) + int(not suff7 and day_left_7 >= created_date)
            suff["insufficient_30d_short_tenure"] = suff.get("insufficient_30d_short_tenure", 0) + int(not suff30 and day_left_30 < created_date)
            suff["insufficient_30d_coverage"] = suff.get("insufficient_30d_coverage", 0) + int(not suff30 and day_left_30 >= created_date)
            suff["insufficient_baseline_short_tenure"] = suff.get("insufficient_baseline_short_tenure", 0) + int(not suffbase and day_left_base < created_date)
            suff["insufficient_baseline_coverage"] = suff.get("insufficient_baseline_coverage", 0) + int(not suffbase and day_left_base >= created_date)
            for grouping, group_key in ((feature_history_by_tenant, tenant_id),
                                        (feature_history_by_cohort, summary["cohort"])):
                group = grouping.setdefault(group_key, Counter())
                group["eligible_cutoffs"] += 1
                group["sufficient_7d"] += int(suff7)
                group["sufficient_14d"] += int(suff14)
                group["sufficient_30d"] += int(suff30)
                group["sufficient_baseline_28d"] += int(suffbase)
                group["insufficient_7d_source_coverage"] += int(not suff7 and day_left_7 >= created_date)
                group["insufficient_30d_source_coverage"] += int(not suff30 and day_left_30 >= created_date)
                group["insufficient_baseline_source_coverage"] += int(not suffbase and day_left_base >= created_date)
            recent30 = _usage_sum(summary, day_left_30, cutoff_date, cutoff, start) if suff30 else 0
            base28 = _usage_sum(summary, day_left_base, day_right_base, cutoff, start) if suffbase else 0
            if suff30:
                feature_windows.append((cutoff_date, recent30, base28 if suffbase else -1))
                behavior_window_counts["observed_30d_windows"] += 1
                stage["usage_behavior"]["observed_30d_windows"] += 1
                for grouping, group_key in ((behavior_by_tenant, tenant_id),
                                            (behavior_by_cohort, summary["cohort"])):
                    grouping.setdefault(group_key, Counter())["observed_30d_windows"] += 1
                if recent30 == 0:
                    behavior_window_counts["inactivity_windows"] += 1
                    stage["usage_behavior"]["inactivity_windows"] += 1
                    for grouping, group_key in ((behavior_by_tenant, tenant_id),
                                                (behavior_by_cohort, summary["cohort"])):
                        grouping.setdefault(group_key, Counter())["inactivity_windows"] += 1
                    saw_inactivity = True
                    scenario_accounts["observed_30d_inactivity"].add(key)
                    scenario_accounts["silent_but_observed_account"].add(key)
                elif saw_inactivity:
                    scenario_accounts["long_inactivity_then_recovery"].add(key)
                if recent30 >= 20:
                    behavior_window_counts["high_usage_windows"] += 1
                    stage["usage_behavior"]["high_usage_windows"] += 1
                    for grouping, group_key in ((behavior_by_tenant, tenant_id),
                                                (behavior_by_cohort, summary["cohort"])):
                        grouping.setdefault(group_key, Counter())["high_usage_windows"] += 1
                if recent30 <= 3:
                    behavior_window_counts["low_usage_windows"] += 1
                    stage["usage_behavior"]["low_usage_windows"] += 1
                    for grouping, group_key in ((behavior_by_tenant, tenant_id),
                                                (behavior_by_cohort, summary["cohort"])):
                        grouping.setdefault(group_key, Counter())["low_usage_windows"] += 1
                regime = "low" if recent30 <= 3 else "high" if recent30 >= 20 else "medium"
                regimes.append(regime)
            if suff30 and suffbase and base28 >= 5:
                expected30 = base28 * 30 / 28
                behavior_window_counts["baseline_comparable_windows"] += 1
                stage["usage_behavior"]["baseline_comparable_windows"] += 1
                for grouping, group_key in ((behavior_by_tenant, tenant_id),
                                            (behavior_by_cohort, summary["cohort"])):
                    grouping.setdefault(group_key, Counter())["baseline_comparable_windows"] += 1
                if recent30 <= 0.75 * expected30:
                    behavior_window_counts["decline_windows"] += 1
                    stage["usage_behavior"]["decline_windows"] += 1
                    for grouping, group_key in ((behavior_by_tenant, tenant_id),
                                                (behavior_by_cohort, summary["cohort"])):
                        grouping.setdefault(group_key, Counter())["decline_windows"] += 1
                    scenario_accounts["measurable_usage_decline"].add(key)
                    scenario_event_counts["measurable_usage_decline"] += 1
                elif recent30 >= 1.25 * expected30:
                    behavior_window_counts["increase_windows"] += 1
                    stage["usage_behavior"]["increase_windows"] += 1
                    for grouping, group_key in ((behavior_by_tenant, tenant_id),
                                                (behavior_by_cohort, summary["cohort"])):
                        grouping.setdefault(group_key, Counter())["increase_windows"] += 1
                    scenario_accounts["measurable_usage_increase"].add(key)
                    scenario_event_counts["measurable_usage_increase"] += 1
            # Label availability is independent of usage feature availability.
            # A complete subscription source interval can establish outcomes even
            # when usage telemetry is sparse or missing.
            for horizon in (7, 14, 30):
                target_end = cutoff + horizon * 86400
                maturity = target_end + maturity_lag_days * 86400
                stats = stage["horizons"][str(horizon)]
                stats["eligible_samples"] += 1
                stats["unique_accounts"].add(customer_id)
                if maturity <= end_epoch:
                    stats["mature_followup_cutoffs"] += 1
                future_churn = next((churn for churn in account_churns
                                     if cutoff < churn[0] <= target_end and churn[1] <= maturity), None)
                covered = _coverage_covers(outcome_intervals, cutoff, target_end, maturity)
                if covered:
                    stats["outcome_coverage_complete_cutoffs"] += 1
                if future_churn is not None:
                    label = "positive"
                    stats["positive_churn_episodes"].add(future_churn[2])
                    stats["positive_accounts"].add(customer_id)
                elif maturity <= end_epoch and covered:
                    label = "negative"
                    stats["negative_accounts"].add(customer_id)
                else:
                    label = "unknown"
                    if maturity > end_epoch:
                        stats["unknown_due_to_immaturity"] += 1
                    elif not covered:
                        stats["unknown_due_to_incomplete_outcome_coverage"] += 1
                    if horizon == 30:
                        unknown_30d_by_account.add(key)
                stats[label] += 1
                if suff30 and horizon == 30 and label == "negative":
                    if recent30 >= 20:
                        scenario_accounts["high_usage_without_churn"].add(key)
                        scenario_event_counts["high_usage_without_churn"] += 1
                    if recent30 <= 3:
                        scenario_accounts["low_usage_without_churn"].add(key)
                        scenario_event_counts["low_usage_without_churn"] += 1

        # Compare distinct observed windows to detect a decline followed by
        # recovery; this remains a source-derived proxy, not a latent state.
        declines = [(when, current, baseline) for when, current, baseline in feature_windows
                    if baseline >= 5 and current <= 0.65 * baseline * 30 / 28]
        recoveries = [(when, current, baseline) for when, current, baseline in feature_windows
                      if baseline >= 5 and current >= 0.8 * baseline * 30 / 28]
        if any(14 <= (recovery[0] - decline[0]).days <= 70 and recovery[2] >= 0
               for decline in declines for recovery in recoveries if recovery[0] > decline[0]):
            scenario_accounts["temporary_decline_then_recovery"].add(key)
            scenario_event_counts["temporary_decline_then_recovery"] += 1
        regime_changes = sum(left != right for left, right in zip(regimes, regimes[1:]))
        if regime_changes >= 2:
            scenario_accounts["repeated_usage_regime_changes"].add(key)
            scenario_event_counts["repeated_usage_regime_changes"] += regime_changes

        if key in unknown_30d_by_account:
            scenario_accounts["unknown_30d_outcome_windows"].add(key)

    coverage_status: Counter[str] = Counter()
    coverage_customer_category: set[tuple[str, str, str]] = set()
    coverage_by_category: dict[str, Counter[str]] = {category: Counter() for category in ("usage", "billing", "subscription")}
    coverage_by_tenant: dict[str, Counter[str]] = {}
    coverage_by_cohort: dict[str, Counter[str]] = {}
    current_coverage_key: tuple[str, str] | None = None
    current_coverage_rows: list[dict[str, Any]] = []
    audited_coverage_accounts: set[tuple[str, str]] = set()

    def flush_coverage_account() -> None:
        nonlocal current_coverage_key, current_coverage_rows
        if current_coverage_key is not None:
            audit_account(current_coverage_key, current_coverage_rows)
            audited_coverage_accounts.add(current_coverage_key)
        current_coverage_key = None
        current_coverage_rows = []

    with gzip.open(path / "observation_coverage.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != COVERAGE_FIELDS:
            errors.append("observation coverage schema is invalid")
        for row in reader:
            measured["observation_coverage"] += 1
            key = (row.get("tenant_id", ""), row.get("customer_id", ""))
            if key != current_coverage_key:
                if key in audited_coverage_accounts:
                    errors.append("observation coverage rows are not grouped by customer")
                flush_coverage_account()
                current_coverage_key = key
            current_coverage_rows.append(row)
            source_key = (row.get("tenant_id", ""), row.get("source", ""))
            category = row.get("source_category", "")
            if key not in customers or source_category.get(source_key) != category:
                errors.append("observation interval references an unknown customer or source")
            status = row.get("coverage_status", "")
            if status not in VALID_COVERAGE:
                errors.append("observation coverage has an unsupported status")
            try:
                covered_from = _timestamp(row["covered_from"])
                covered_through = _timestamp(row["covered_through"])
                available_at = _timestamp(row["coverage_available_at"])
                if covered_through <= covered_from or available_at < covered_through:
                    errors.append("observation coverage interval or availability is invalid")
                if not row.get("observation_policy_version"):
                    errors.append("observation coverage policy version is missing")
                completeness = float(row["coverage_completeness"])
                if not 0.0 <= completeness <= 1.0:
                    errors.append("observation coverage completeness is outside 0..1")
            except (KeyError, TypeError, ValueError):
                errors.append("observation coverage timestamp or completeness is invalid")
            coverage_status[status] += 1
            if category in coverage_by_category:
                coverage_by_category[category][status] += 1
            coverage_label = f"{category}:{status}"
            coverage_by_tenant.setdefault(key[0], Counter())[coverage_label] += 1
            cohort_name = customers.get(key, {}).get("onboarding_cohort", "unknown")
            coverage_by_cohort.setdefault(cohort_name, Counter())[coverage_label] += 1
            coverage_customer_category.add((key[0], key[1], category))
    flush_coverage_account()
    measured.update({f"coverage_{name}": count for name, count in coverage_status.items()})
    measured["coverage_customer_category_pairs"] = len(coverage_customer_category)

    for category, count in coverage_by_category.items():
        for status, rows in count.items():
            measured[f"{category}_coverage_{status}"] = rows

    cohort_stages: dict[str, Any] = {}
    for stage_name, stage in cohort_label_counts["stages"].items():
        unique_eligible = len(stage["unique_eligible_accounts"])
        stage["unique_eligible_accounts"] = unique_eligible
        feature_denominator = stage["eligible_samples"] - stage["known_cancellation_exclusions"]
        stage["feature_history_denominator"] = feature_denominator
        stage["feature_sufficiency_fractions"] = {
            name: (count / feature_denominator if feature_denominator else None)
            for name, count in stage["feature_sufficiency"].items()
            if name in {"7d", "14d", "30d", "baseline_28d"}
        }
        stage["source_evidence"] = {
            name: len(value) if isinstance(value, set) else int(value)
            for name, value in stage["source_evidence"].items()
        }
        usage_behavior = dict(stage["usage_behavior"])
        observed_windows = usage_behavior.get("observed_30d_windows", 0)
        comparable_windows = usage_behavior.get("baseline_comparable_windows", 0)
        usage_behavior["inactivity_fraction"] = (
            usage_behavior.get("inactivity_windows", 0) / observed_windows if observed_windows else None
        )
        usage_behavior["decline_fraction_of_comparable_windows"] = (
            usage_behavior.get("decline_windows", 0) / comparable_windows if comparable_windows else None
        )
        usage_behavior["increase_fraction_of_comparable_windows"] = (
            usage_behavior.get("increase_windows", 0) / comparable_windows if comparable_windows else None
        )
        stage["usage_behavior"] = usage_behavior
        for horizon, stats in stage["horizons"].items():
            stats["unique_accounts"] = len(stats["unique_accounts"])
            stats["positive_accounts"] = len(stats["positive_accounts"])
            stats["negative_accounts"] = len(stats["negative_accounts"])
            stats["distinct_positive_churn_episodes"] = len(stats.pop("positive_churn_episodes"))
        cohort_stages[stage_name] = stage
    cohort_label_counts["stages"] = cohort_stages
    minimum_classes = {
        "minimum_positive_samples": 50,
        "minimum_negative_samples": 50,
        "minimum_unique_positive_accounts": 20,
        "minimum_unique_negative_accounts": 20,
    }
    class_coverage: dict[str, Any] = {}
    for stage_name, stage in cohort_stages.items():
        class_coverage[stage_name] = {}
        for horizon, stats in stage["horizons"].items():
            class_coverage[stage_name][horizon] = {
                "positive_samples": stats["positive"],
                "negative_samples": stats["negative"],
                "unique_positive_accounts": stats["positive_accounts"],
                "unique_negative_accounts": stats["negative_accounts"],
                "meets_minimums": (
                    stats["positive"] >= minimum_classes["minimum_positive_samples"]
                    and stats["negative"] >= minimum_classes["minimum_negative_samples"]
                    and stats["positive_accounts"] >= minimum_classes["minimum_unique_positive_accounts"]
                    and stats["negative_accounts"] >= minimum_classes["minimum_unique_negative_accounts"]
                ),
            }
    cohort_label_counts["minimum_class_coverage"] = minimum_classes
    cohort_label_counts["class_coverage_by_stage"] = class_coverage
    cohort_label_counts["status"] = (
        "READY" if cohort_ready and all(
            summary["meets_minimums"]
            for stage_summary in class_coverage.values()
            for summary in stage_summary.values()
        ) else "INSUFFICIENT_CLASS_COVERAGE" if cohort_ready else "NOT_READY_CUSTOM_WINDOW"
    )
    cohort_label_counts["policy"] = {
        "positive": f"A source-backed effective account-level entitlement loss occurs in (cutoff, cutoff+horizon] and its source event is available by horizon end plus the {maturity_lag_days}-day maturity lag.",
        "negative": f"No qualifying loss, complete subscription-outcome coverage over (cutoff, cutoff+horizon], the coverage is available by horizon end plus {maturity_lag_days} days, and the horizon has matured by the exclusive simulation end.",
        "unknown": "Neither a source-verified positive nor a mature, completely observed negative can be established.",
        "known_cancellation": "Exclude cutoffs where all active paid subscriptions already have a source-visible cancellation request.",
        "feature_independence": "Usage feature sufficiency is audited separately; missing usage does not remove a valid subscription outcome label.",
    }

    def _density_report(groups: dict[str, Counter[str]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for group, totals in sorted(groups.items()):
            accounts = int(totals["accounts"])
            account_months = float(totals["account_months"])
            events = int(totals["usage_events"])
            output[group] = {
                "accounts": accounts,
                "simulated_account_months": round(account_months, 2),
                "usage_events": events,
                "active_days": events,
                "sessions": int(totals["usage_sessions"]),
                "usage_events_per_account_month": round(events / account_months, 4) if account_months else 0.0,
                "active_days_per_account": round(events / accounts, 3) if accounts else 0.0,
            }
        return output

    usage_density_by_tenant = _density_report(usage_density_tenant)
    usage_density_by_cohort = _density_report(usage_density_cohort)
    def _feature_history_report(groups: dict[str, Counter[str]]) -> dict[str, Any]:
        output = {}
        for group_name, values in sorted(groups.items()):
            denominator = int(values["eligible_cutoffs"])
            output[group_name] = {
                "eligible_cutoffs": denominator,
                "sufficient_cutoffs": {
                    name.removeprefix("sufficient_"): int(value)
                    for name, value in values.items() if name.startswith("sufficient_")
                },
                "sufficiency_fractions": {
                    name.removeprefix("sufficient_"): value / denominator if denominator else None
                    for name, value in values.items() if name.startswith("sufficient_")
                },
                "insufficient_due_to_source_coverage": {
                    name.removeprefix("insufficient_").removesuffix("_source_coverage"): int(value)
                    for name, value in values.items() if name.startswith("insufficient_")
                },
            }
        return output

    def _behavior_group_report(groups: dict[str, Counter[str]]) -> dict[str, Any]:
        output = {}
        for group_name, values in sorted(groups.items()):
            row = {name: int(value) for name, value in values.items()}
            observed = row.get("observed_30d_windows", 0)
            comparable = row.get("baseline_comparable_windows", 0)
            row["inactivity_fraction"] = row.get("inactivity_windows", 0) / observed if observed else None
            row["decline_fraction_of_comparable_windows"] = row.get("decline_windows", 0) / comparable if comparable else None
            row["increase_fraction_of_comparable_windows"] = row.get("increase_windows", 0) / comparable if comparable else None
            output[group_name] = row
        return output

    feature_history_by_tenant_report = _feature_history_report(feature_history_by_tenant)
    feature_history_by_cohort_report = _feature_history_report(feature_history_by_cohort)
    behavior_by_tenant_report = _behavior_group_report(behavior_by_tenant)
    behavior_by_cohort_report = _behavior_group_report(behavior_by_cohort)
    coverage_by_tenant_report = {name: dict(sorted(values.items())) for name, values in sorted(coverage_by_tenant.items())}
    coverage_by_cohort_report = {name: dict(sorted(values.items())) for name, values in sorted(coverage_by_cohort.items())}
    behavior_window_report = dict(sorted(behavior_window_counts.items()))
    behavior_window_report.update({
        "inactivity_fraction_of_observed_30d_windows": (
            behavior_window_counts["inactivity_windows"] / behavior_window_counts["observed_30d_windows"]
            if behavior_window_counts["observed_30d_windows"] else None
        ),
        "decline_fraction_of_baseline_comparable_windows": (
            behavior_window_counts["decline_windows"] / behavior_window_counts["baseline_comparable_windows"]
            if behavior_window_counts["baseline_comparable_windows"] else None
        ),
        "increase_fraction_of_baseline_comparable_windows": (
            behavior_window_counts["increase_windows"] / behavior_window_counts["baseline_comparable_windows"]
            if behavior_window_counts["baseline_comparable_windows"] else None
        ),
    })

    proxy_scenarios = {
        "high_usage_before_churn", "low_usage_before_churn", "measurable_usage_decline",
        "measurable_usage_increase", "temporary_decline_then_recovery", "predominant_feature_abandonment_proxy",
        "high_session_volume_variability", "unexpected_sudden_churn", "repeated_usage_regime_changes",
    }
    source_scenarios = []
    for name, rule in sorted(scenario_rules.items()):
        keys = scenario_accounts.get(name, set())
        tenants = Counter(customers[key]["tenant_id"] for key in keys if key in customers)
        cohorts = Counter(customers[key]["onboarding_cohort"] for key in keys if key in customers)
        count = len(keys)
        source_scenarios.append({
            "scenario_name": name,
            "detection_rule": rule,
            "source_evidence": "canonical_events.csv, usage_events.csv, subscription_events.csv, billing_events.csv, effective_churn.csv, and/or observation_coverage.csv.gz as named by the detection rule",
            "distinct_account_count": count,
            "event_count": int(scenario_event_counts.get(name, 0)),
            "tenant_distribution": dict(sorted(tenants.items())),
            "cohort_distribution": dict(sorted(cohorts.items())),
            "verification_status": ("NOT_OBSERVED" if count == 0 else "SOURCE_PROXY" if name in proxy_scenarios else "SOURCE_VERIFIED"),
        })
    if scenarios.get("audit_method"):
        exported_scenario_counts = {
            row.get("scenario_name"): row.get("distinct_account_count")
            for row in scenarios.get("scenarios", [])
        }
        recomputed_scenario_counts = {
            row["scenario_name"]: row["distinct_account_count"] for row in source_scenarios
        }
        if exported_scenario_counts != recomputed_scenario_counts:
            errors.append("scenario report account counts differ from independent source audit")
        if manifest.get("scenario_counts") != recomputed_scenario_counts:
            errors.append("manifest scenario counts differ from independent source audit")
        if split.get("cohort_label_audit") != cohort_label_counts:
            errors.append("split manifest label audit differs from independent source audit")

    coverage_by_source_category = {
        category: dict(sorted(status_counts.items()))
        for category, status_counts in sorted(coverage_by_category.items())
    }
    usage_rhythm_by_tenant: dict[str, Any] = {}
    tenant_ids = sorted({tenant_id for tenant_id, _ in tenant_weekday_sessions})
    for tenant_id in tenant_ids:
        weekday_sessions = sum(tenant_weekday_sessions[(tenant_id, day)] for day in range(5))
        weekend_sessions = sum(tenant_weekday_sessions[(tenant_id, day)] for day in range(5, 7))
        weekday_daily_mean = weekday_sessions / 5
        weekend_daily_mean = weekend_sessions / 2
        usage_rhythm_by_tenant[tenant_id] = {
            "weekday_sessions_observed": weekday_sessions,
            "weekend_sessions_observed": weekend_sessions,
            "mean_weekday_sessions_per_weekday": round(weekday_daily_mean, 3),
            "mean_weekend_sessions_per_weekend_day": round(weekend_daily_mean, 3),
            "weekday_to_weekend_daily_ratio": round(weekday_daily_mean / weekend_daily_mean, 3) if weekend_daily_mean else None,
            "sessions_by_calendar_month": {
                month: value for (tenant, month), value in sorted(tenant_month_sessions.items())
                if tenant == tenant_id
            },
        }

    if manifest.get("actual_counts", {}).get("customers") != measured["customers"]:
        errors.append("manifest customer count mismatch")
    if manifest.get("actual_counts", {}).get("customer_identities") != measured["customer_identities"]:
        errors.append("manifest customer identity count mismatch")
    if manifest.get("actual_counts", {}).get("canonical_events") != measured["canonical_events"]:
        errors.append("manifest canonical event count mismatch")
    for category in ("usage", "billing", "subscription"):
        if manifest.get("actual_counts", {}).get(f"{category}_events") != measured[f"{category}_events"]:
            errors.append(f"manifest {category} count mismatch")
    if manifest.get("actual_counts", {}).get("effective_churn_episodes") != measured["effective_churn_episodes"]:
        errors.append("manifest effective churn count mismatch")
    if manifest.get("actual_counts", {}).get("observation_coverage") != measured["observation_coverage"]:
        errors.append("manifest observation coverage count mismatch")
    if quality.get("status") != "PASS":
        warnings.append("quality report has not recorded a completed independent validation")
    if measured["effective_churn_episodes"] == 0:
        warnings.append("no effective account churn was observed in this profile")
    if measured["usage_events"] != measured["usage_active_days"]:
        errors.append("daily usage events and active-day counts do not reconcile")

    db.close()
    temp_dir.cleanup()
    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors[:100],
        "warnings": warnings,
        "measured_counts": dict(sorted(measured.items())),
        "coverage_status_counts": dict(sorted(coverage_status.items())),
        "coverage_by_source_category": coverage_by_source_category,
        "usage_density_by_tenant": usage_density_by_tenant,
        "usage_density_by_cohort": usage_density_by_cohort,
        "feature_history_by_tenant": feature_history_by_tenant_report,
        "feature_history_by_cohort": feature_history_by_cohort_report,
        "behavior_by_tenant": behavior_by_tenant_report,
        "behavior_by_cohort": behavior_by_cohort_report,
        "coverage_by_tenant": coverage_by_tenant_report,
        "coverage_by_cohort": coverage_by_cohort_report,
        "usage_rhythm_by_tenant": usage_rhythm_by_tenant,
        "behavior_windows": behavior_window_report,
        "cohort_label_audit": cohort_label_counts,
        "source_scenarios": source_scenarios,
        "dataset_id": manifest.get("dataset_id"),
        "scenario_reported_counts": {
            row["scenario_name"]: row["distinct_account_count"] for row in scenarios.get("scenarios", [])
        },
        "note": "Independent source validation only; no model has been trained and no real-world predictive claim is made.",
    }
