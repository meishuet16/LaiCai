"""Bounded-memory structural and semantic validation for generated datasets."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from retaniq.currency_codes import ISO4217_CURRENT_CODES
from retaniq.data_foundation import EVENT_TYPES


REQUIRED_FILES = {
    "dataset_manifest.json", "customers.csv", "customer_identities.csv", "plan_catalog.csv",
    "subscription_events.csv", "billing_events.csv", "usage_events.csv",
    "observation_coverage.csv", "canonical_events.csv", "scenario_coverage.json",
    "quality_report.json", "split_manifest.json", "label_oracle_fixtures.json",
    "adversarial_fixtures.json",
}
FORBIDDEN_FIELDS = {"will_churn", "churn_risk_class", "future_dropout_reason", "latent_hazard", "latent_state"}


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def validate_dataset(dataset_path: Path | str) -> dict[str, Any]:
    path = Path(dataset_path).resolve()
    manifest_path = path / "dataset_manifest.json"
    if manifest_path.is_file():
        try:
            version = json.loads(manifest_path.read_text(encoding="utf-8")).get("dataset_version")
        except (OSError, json.JSONDecodeError):
            version = None
        if version == "1.2.0":
            from .v12_validation import validate_v12_dataset
            return validate_v12_dataset(path)
    errors: list[str] = []
    warnings: list[str] = []
    measured: Counter[str] = Counter()
    if not path.is_dir():
        return {"status": "FAIL", "errors": ["dataset directory does not exist"], "warnings": [], "measured_counts": {}}
    missing = sorted(REQUIRED_FILES - {item.name for item in path.iterdir() if item.is_file()})
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
    except (OSError, json.JSONDecodeError):
        return {"status": "FAIL", "errors": ["dataset manifest is invalid"], "warnings": [], "measured_counts": {}}
    if manifest.get("dataset_type") != "synthetic_saas" or manifest.get("no_real_customer_data") is not True:
        errors.append("manifest synthetic provenance is missing")
    if manifest.get("track") != "synthetic_saas":
        errors.append("dataset track isolation is missing")
    for name, expected in manifest.get("file_hashes", {}).items():
        file_path = path / Path(name)
        if not file_path.is_file():
            errors.append(f"hashed file is missing: {name}")
            continue
        actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"hash mismatch: {name}")

    customers: set[tuple[str, str]] = set()
    with (path / "customers.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if FORBIDDEN_FIELDS.intersection(reader.fieldnames or ()):
            errors.append("customers export contains a forbidden future-target field")
        for row in reader:
            key = (row.get("tenant_id", ""), row.get("customer_id", ""))
            if not all(key) or key in customers:
                errors.append("customer identity is missing or duplicated")
                continue
            if row.get("dataset_type") != "synthetic_saas":
                errors.append("customer row lacks synthetic provenance")
            customers.add(key)
    measured["customers"] = len(customers)

    identities: dict[tuple[str, str, str], str] = {}
    with (path / "customer_identities.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            customer_key = (row.get("tenant_id", ""), row.get("customer_id", ""))
            identity_key = (row.get("tenant_id", ""), row.get("source", ""), row.get("external_customer_id", ""))
            if customer_key not in customers:
                errors.append("identity references an unknown or cross-tenant customer")
            prior = identities.get(identity_key)
            if prior is not None and prior != row.get("customer_id"):
                errors.append("source identity maps to multiple customers")
            identities[identity_key] = row.get("customer_id", "")
    measured["customer_identities"] = len(identities)

    subscription_owners: dict[tuple[str, str], str] = {}
    source_categories: dict[tuple[str, str], str] = {}
    seen_events: set[tuple[str, str, str]] = set()
    with (path / "canonical_events.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if FORBIDDEN_FIELDS.intersection(reader.fieldnames or ()):
            errors.append("canonical export contains a forbidden future-target field")
        for line_number, row in enumerate(reader, start=2):
            measured["canonical_events"] += 1
            event_key = (row.get("tenant_id", ""), row.get("source", ""), row.get("source_event_id", ""))
            if event_key in seen_events:
                errors.append(f"duplicate event key at canonical line {line_number}")
            seen_events.add(event_key)
            identity_key = (row.get("tenant_id", ""), row.get("source", ""), row.get("external_customer_id", ""))
            if identities.get(identity_key) != row.get("customer_id"):
                errors.append(f"event identity mismatch at canonical line {line_number}")
            event_type = row.get("event_type", "")
            if event_type not in EVENT_TYPES:
                errors.append(f"unsupported event type at canonical line {line_number}")
                continue
            category, allowed = EVENT_TYPES[event_type]
            if row.get("source_category") != category:
                errors.append(f"event category mismatch at canonical line {line_number}")
            source_key = (row.get("tenant_id", ""), row.get("source", ""))
            prior_category = source_categories.setdefault(source_key, category)
            if prior_category != category:
                errors.append(f"source mixes event categories at canonical line {line_number}")
            measured[f"{category}_events"] += 1
            try:
                occurred = _timestamp(row["occurred_at"])
                available = _timestamp(row["source_available_at"])
                received = _timestamp(row["received_at"])
                if not occurred <= available <= received:
                    errors.append(f"impossible event time ordering at canonical line {line_number}")
            except (KeyError, TypeError, ValueError):
                errors.append(f"invalid timestamp at canonical line {line_number}")
            try:
                attributes = json.loads(row.get("attributes_json", ""))
            except json.JSONDecodeError:
                errors.append(f"invalid attributes JSON at canonical line {line_number}")
                continue
            if not isinstance(attributes, dict) or set(attributes) - allowed:
                errors.append(f"unsupported attributes at canonical line {line_number}")
                continue
            if any(field in attributes for field in FORBIDDEN_FIELDS):
                errors.append(f"latent target leakage at canonical line {line_number}")
            if "amount_minor" in attributes:
                amount = attributes["amount_minor"]
                if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                    errors.append(f"invalid monetary amount at canonical line {line_number}")
                if attributes.get("currency") not in ISO4217_CURRENT_CODES:
                    errors.append(f"invalid currency at canonical line {line_number}")
            subscription_id = attributes.get("subscription_id")
            if subscription_id:
                owner_key = (row.get("tenant_id", ""), subscription_id)
                owner = subscription_owners.setdefault(owner_key, row.get("customer_id", ""))
                if owner != row.get("customer_id"):
                    errors.append(f"subscription ownership conflict at canonical line {line_number}")

    for filename, category in (("usage_events.csv", "usage"), ("billing_events.csv", "billing"), ("subscription_events.csv", "subscription")):
        with (path / filename).open(encoding="utf-8", newline="") as stream:
            count = sum(1 for _ in csv.DictReader(stream))
        if count != measured[f"{category}_events"]:
            errors.append(f"{filename} count differs from canonical events")
    with (path / "observation_coverage.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            measured["observation_coverage"] += 1
            if row.get("coverage_status") not in {"complete", "partial", "outage"}:
                errors.append("observation coverage has invalid status")
            if row.get("supports_verified_negative") == "true" and row.get("coverage_status") != "complete":
                errors.append("incomplete coverage incorrectly supports a verified negative")

    expected_counts = manifest.get("actual_counts", {})
    for key in ("customers", "customer_identities", "canonical_events", "usage_events", "billing_events", "subscription_events", "observation_coverage"):
        if expected_counts.get(key) != measured[key]:
            errors.append(f"manifest count mismatch: {key}")
    scenario_counts = manifest.get("actual_scenario_coverage", {})
    for important in ("billing_failures", "payment_recovery", "effective_account_churn", "incomplete_telemetry"):
        if scenario_counts.get(important, 0) == 0:
            warnings.append(f"scenario not observed in this generated profile: {important}")
    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors[:100],
        "warnings": warnings,
        "measured_counts": dict(sorted(measured.items())),
        "dataset_id": manifest.get("dataset_id"),
    }
