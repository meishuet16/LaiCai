"""Aggregate-only, bounded authenticated pilot for the synthetic STANDARD data.

The CLI deliberately loads Member 1's P0 ``retaniq`` code before importing the
Member 2 adapter. It emits no account identifiers, features, events, or tokens.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping, Sequence


DATASET_ID = "synthetic-saas-v1-2-standard-s2026-970a9d231e68"
MANIFEST_SHA256 = "7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d"
EXPECTED_SOURCE_CATEGORIES = {
    "tenant-01-synthetic-usage-v1-2": "usage",
    "tenant-01-synthetic-billing-v1-2": "billing",
    "tenant-01-synthetic-subscription-v1-2": "subscription",
}
PILOT_SCHEMA_VERSION = "member2-authenticated-standard-pilot-v1"


class PilotError(RuntimeError):
    """A fail-closed pilot precondition or contract violation."""


class TimedReaderAPI:
    """Count high-level reader API calls without retaining returned payloads."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.counts: Counter[str] = Counter()
        self.seconds: Counter[str] = Counter()
        self.account_statuses: dict[tuple[str, str], str] = {}

    def __getattr__(self, name: str):
        operation = getattr(self._delegate, name)
        if not callable(operation):
            return operation

        def counted(*args, **kwargs):
            started = time.perf_counter()
            self.counts[name] += 1
            try:
                result = operation(*args, **kwargs)
                if isinstance(result, (dict, list, tuple)):
                    json.dumps(result, sort_keys=True, allow_nan=False)
                _assert_no_unauthorized_valuation(name, result)
                if name == "get_account_snapshot_as_of" and isinstance(result, Mapping):
                    customer_id = str(args[2])
                    as_of = _canonical_timestamp(str(args[3]))
                    self.account_statuses[(customer_id, as_of)] = str(result.get("status", "unknown"))
                return result
            finally:
                self.seconds[name] += time.perf_counter() - started

        return counted


def _assert_no_unauthorized_valuation(operation: str, result: Any) -> None:
    valuation_fields = {"amount_minor", "discount_minor", "currency", "mrr_minor", "valuation_policy_version"}
    if operation == "get_account_snapshot_as_of" and isinstance(result, Mapping):
        if result.get("valuation") is not None:
            raise PilotError("account snapshot unexpectedly exposed billing valuation")
    elif operation == "get_subscriptions_as_of" and isinstance(result, (list, tuple)):
        if any(valuation_fields.intersection(item) for item in result if isinstance(item, Mapping)):
            raise PilotError("subscription response unexpectedly exposed billing valuation")
    elif operation == "get_events_as_of" and isinstance(result, (list, tuple)):
        for row in result:
            if not isinstance(row, Mapping):
                continue
            attributes = row.get("attributes")
            if not isinstance(attributes, Mapping):
                continue
            exposed = valuation_fields.intersection(attributes)
            if row.get("category") == "subscription":
                changes = attributes.get("changes")
                if isinstance(changes, Mapping):
                    exposed = exposed | valuation_fields.intersection(changes)
            if row.get("category") in {"billing", "subscription"} and exposed:
                raise PilotError("billing event response unexpectedly exposed valuation fields")


def _canonical_timestamp(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
        value[:-1] + "+00:00" if value.endswith("Z") else value
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def require_reader_token(environment: Mapping[str, str] | None = None) -> str:
    """Return a non-empty injected token, never its value in diagnostics."""

    values = os.environ if environment is None else environment
    token = values.get("RETAINIQ_MODEL_TOKEN")
    if not isinstance(token, str) or not token:
        raise PilotError("RETAINIQ_MODEL_TOKEN is absent; use Member 1's DPAPI wrapper")
    return token


def authenticate_reader(data_foundation: Any, database_path: str | Path, environment=None):
    """Authenticate without reflecting a token or provider error details."""

    token = require_reader_token(environment)
    try:
        return data_foundation.authenticate_service_principal(database_path, token)
    except Exception as error:
        error_code = getattr(error, "code", None)
        suffix = f" ({error_code})" if isinstance(error_code, str) else ""
        raise PilotError(f"reader authentication failed{suffix}") from None
    finally:
        token = None


def validate_reader_principal(principal: Any) -> None:
    if (getattr(principal, "tenant_id", None) != "tenant-01"
            or getattr(principal, "role", None) != "analyst"
            or getattr(principal, "authorized_purposes", None) != ("retention_inference",)
            or set(getattr(principal, "authorized_sources", ())) != set(EXPECTED_SOURCE_CATEGORIES)):
        raise PilotError("authenticated reader grants do not match the approved narrow scope")


def validate_dataset_files(
    dataset_path: str | Path,
    *,
    expected_dataset_id: str = DATASET_ID,
    expected_manifest_sha256: str = MANIFEST_SHA256,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    root = Path(dataset_path).resolve()
    manifest_bytes = (root / "dataset_manifest.json").read_bytes()
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    split_manifest = json.loads((root / "split_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("dataset_id") != expected_dataset_id or digest != expected_manifest_sha256:
        raise PilotError("dataset identity or manifest checksum does not match the authorized STANDARD handoff")
    if (manifest.get("dataset_type") != "synthetic_saas"
            or manifest.get("no_real_customer_data") is not True
            or manifest.get("target_policy_version") != "effective-account-churn-v1.2"
            or split_manifest.get("dataset_id") != expected_dataset_id):
        raise PilotError("dataset provenance or frozen split policy is incompatible")
    return manifest, split_manifest, digest


def select_tenant_customer_ids(
    dataset_path: str | Path,
    *,
    dataset_id: str = DATASET_ID,
    tenant_id: str = "tenant-01",
    limit: int = 30,
) -> tuple[str, ...]:
    """Select deterministically from identity inventory only, never from labels."""

    if not 1 <= limit <= 30:
        raise ValueError("pilot account limit must be between 1 and 30")
    candidates: set[str] = set()
    with (Path(dataset_path) / "customers.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"tenant_id", "customer_id"}.issubset(reader.fieldnames or ()):
            raise PilotError("customer identity inventory lacks required columns")
        for row in reader:
            if row.get("tenant_id") == tenant_id and row.get("customer_id"):
                candidates.add(row["customer_id"])
    if not candidates:
        raise PilotError("no tenant-scoped candidate identities were found")
    ranked = sorted(
        candidates,
        key=lambda customer_id: hashlib.sha256(
            f"{dataset_id}|{tenant_id}|{customer_id}".encode("utf-8")
        ).hexdigest(),
    )
    return tuple(ranked[:limit])


def select_one_other_tenant_customer(dataset_path: str | Path, tenant_id: str) -> str:
    """Choose an internal cross-tenant denial probe without returning its ID."""

    candidates: list[str] = []
    with (Path(dataset_path) / "customers.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("tenant_id") and row["tenant_id"] != tenant_id and row.get("customer_id"):
                candidates.append(row["customer_id"])
    if not candidates:
        raise PilotError("no other-tenant fixture exists for a denial probe")
    return min(candidates)


def select_development_cutoffs(
    dataset_manifest: Mapping[str, Any], split_manifest: Mapping[str, Any]
):
    """Take first/last TRAIN and last VALIDATION cutoffs from the frozen schedule."""

    from retainiq_prediction.historical_dataset_preparation import build_cutoff_schedule
    from retainiq_prediction.temporal_splits import SplitName

    schedule = build_cutoff_schedule(dataset_manifest, split_manifest)
    train = [item for item in schedule if item.split is SplitName.TRAIN]
    validation = [item for item in schedule if item.split is SplitName.VALIDATION]
    if len(train) < 2 or not validation:
        raise PilotError("frozen schedule lacks two TRAIN and one VALIDATION cutoffs")
    selected = (train[0], train[-1], validation[-1])
    if len({item.as_of for item in selected}) != 3:
        raise PilotError("frozen development cutoff selection is not unique")
    if any(item.split not in {SplitName.TRAIN, SplitName.VALIDATION} for item in selected):
        raise PilotError("pilot selection attempted to include a non-development cutoff")
    return selected


def assert_facts_available_by(facts: Iterable[Any], cutoff: datetime, *, context: str) -> None:
    for fact in facts:
        occurred = getattr(fact, "occurred_at", None)
        source_available = getattr(fact, "source_available_at", None)
        received = getattr(fact, "received_at", None)
        available = source_available or received
        if occurred is None or occurred > cutoff or available is None or available > cutoff:
            raise PilotError(f"{context} contained a fact not demonstrably available by its cutoff")


def _connection_state(evidence: Sequence[Any]) -> str:
    states = [item.connected for item in evidence]
    if any(state is False for state in states):
        return "explicitly_disconnected"
    if states and all(state is True for state in states):
        return "connected"
    return "unknown"


def _increment(counter: Counter[str], value: Any) -> None:
    key = getattr(value, "value", value)
    counter[str(key)] += 1


def run_bounded_pilot(
    adapter: Any,
    dataset_path: str | Path,
    *,
    account_limit: int = 30,
    customer_ids: Sequence[str] | None = None,
    cutoffs: Sequence[Any] | None = None,
    reader_api: TimedReaderAPI | None = None,
    principal: Any | None = None,
    other_tenant_customer_id: str | None = None,
    expected_dataset_id: str = DATASET_ID,
    expected_manifest_sha256: str = MANIFEST_SHA256,
) -> dict[str, Any]:
    """Run at most 30 x 3 pairs and return aggregate-only evidence."""

    from retainiq_prediction.data_freshness import (
        FreshnessReasonCode, assess_data_freshness,
    )
    from retainiq_prediction.eligibility import EligibilityState
    from retainiq_prediction.feature_builder import FeatureBuilder
    from retainiq_prediction.historical_dataset_preparation import (
        _CachedLifecycleOutcomeAdapter, label_evaluation_cutoff,
    )
    from retainiq_prediction.label_builder import (
        ChurnLabelBuilder, LabelBuilderConfig, LabelStatus,
    )
    from retainiq_prediction.reliability import assess_reliability
    from retainiq_prediction.temporal_splits import SplitName

    started = time.perf_counter()
    manifest, split_manifest, digest = validate_dataset_files(
        dataset_path,
        expected_dataset_id=expected_dataset_id,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    if adapter.provenance.dataset_id != manifest["dataset_id"] or adapter.provenance.manifest_sha256 != digest:
        raise PilotError("authenticated adapter provenance does not match the source manifest")
    tenant_id = adapter.tenant_id
    if tenant_id != "tenant-01":
        raise PilotError("pilot requires the authenticated tenant-01 principal")
    cohort = tuple(customer_ids) if customer_ids is not None else select_tenant_customer_ids(
        dataset_path, dataset_id=manifest["dataset_id"], tenant_id=tenant_id, limit=account_limit
    )
    if not cohort or len(cohort) > 30 or len(set(cohort)) != len(cohort):
        raise PilotError("cohort must contain 1-30 unique account identities")
    selected_cutoffs = tuple(cutoffs) if cutoffs is not None else select_development_cutoffs(
        manifest, split_manifest
    )
    if (not selected_cutoffs or len(selected_cutoffs) > 3
            or len({item.as_of for item in selected_cutoffs}) != len(selected_cutoffs)
            or any(item.split not in {SplitName.TRAIN, SplitName.VALIDATION} for item in selected_cutoffs)):
        raise PilotError("cutoffs must be unique TRAIN/VALIDATION development cutoffs, at most three")
    for cutoff in selected_cutoffs:
        if cutoff.as_of.tzinfo is None or cutoff.as_of.utcoffset() is None:
            raise PilotError("prediction cutoffs must be timezone-aware")

    feature_builder = FeatureBuilder(adapter, config=adapter.feature_builder_config())
    eligibility_policy = adapter.synthetic_eligibility_policy()
    maturity_lag = int(split_manifest["label_maturity_lag_days"])
    label_config = LabelBuilderConfig(
        label_policy_version=str(manifest["target_policy_version"]),
        availability_policy=adapter.availability_policy,
    )
    counters: dict[str, Counter[str]] = {
        key: Counter() for key in (
            "eligibility", "freshness", "reliability", "connectivity", "freshness_reasons",
            "reliability_reasons", "coverage_quality", "coverage_interval_status",
            "baseline", "label_status_7", "label_status_14", "label_status_30",
            "label_reason_7", "label_reason_14", "label_reason_30", "source_category_pairs",
            "point_in_time_exclusions", "member1_member2_status_pairs",
        )
    }
    eligible_accounts_by_horizon = {h: {"positive": set(), "negative": set()} for h in (7, 14, 30)}
    eligible_customer_ids: set[str] = set()
    stage_label_status: dict[str, dict[int, Counter[str]]] = {
        stage: {horizon: Counter() for horizon in (7, 14, 30)}
        for stage in (SplitName.TRAIN.value, SplitName.VALIDATION.value)
    }
    stage_label_accounts: dict[str, dict[int, dict[str, set[str]]]] = {
        stage: {
            horizon: {"positive": set(), "negative": set()}
            for horizon in (7, 14, 30)
        }
        for stage in stage_label_status
    }
    pair_count = 0
    eligible_pair_count = 0
    missing_usage_coverage_pairs = 0
    no_account_event_pairs = 0
    nonempty_usage_event_pairs = 0
    nonempty_billing_event_pairs = 0
    nonempty_subscription_event_pairs = 0
    outcome_read_pairs = 0
    late_or_unavailable_label_pairs: Counter[str] = Counter()
    outcome_coverage_statuses: Counter[str] = Counter()
    cross_tenant_probe_count = 0
    candidate_api_calls = 0
    eligible_api_calls = 0

    for cutoff in selected_cutoffs:
        for customer_id in cohort:
            pair_count += 1
            pair_calls_before = sum(reader_api.counts.values()) if reader_api is not None else 0
            snapshot = adapter.snapshot_for(tenant_id, customer_id, cutoff.as_of)
            if (snapshot.tenant_id, snapshot.customer_id, snapshot.as_of) != (
                tenant_id, customer_id, cutoff.as_of
            ):
                raise PilotError("adapter returned a mismatched tenant/account/cutoff")
            assert_facts_available_by(
                (*snapshot.subscriptions, *snapshot.usage_events, *snapshot.billing_events),
                cutoff.as_of,
                context="point-in-time feature input",
            )
            if not (snapshot.usage_events or snapshot.billing_events or snapshot.subscriptions):
                no_account_event_pairs += 1
            if snapshot.usage_events:
                nonempty_usage_event_pairs += 1
            if snapshot.billing_events:
                nonempty_billing_event_pairs += 1
            if snapshot.subscriptions:
                nonempty_subscription_event_pairs += 1
            for category, facts in (
                ("usage", snapshot.usage_events),
                ("billing", snapshot.billing_events),
                ("subscription", snapshot.subscriptions),
            ):
                for fact in facts:
                    expected_category = EXPECTED_SOURCE_CATEGORIES.get(fact.source)
                    if expected_category != category:
                        raise PilotError("authenticated response contained an unexpected source/category pair")
                    counters["source_category_pairs"][f"{fact.source}:{category}"] += 1
            for key, value in snapshot.excluded_record_counts.items():
                counters["point_in_time_exclusions"][key] += int(value)

            eligibility = adapter.eligibility_from_snapshot(snapshot, policy=eligibility_policy)
            _increment(counters["eligibility"], eligibility.state)
            if reader_api is not None:
                status = reader_api.account_statuses.get(
                    (customer_id, _canonical_timestamp(cutoff.as_of))
                )
                mapped = {
                    EligibilityState.ELIGIBLE: "eligible",
                    EligibilityState.KNOWN_CANCELLATION: "known_cancellation",
                    EligibilityState.NOT_ELIGIBLE: "not_eligible",
                    EligibilityState.INSUFFICIENT_DATA: "insufficient_data",
                }.get(eligibility.state)
                if status is not None and mapped is not None:
                    counters["member1_member2_status_pairs"][f"{status}|{eligibility.state.value}"] += 1

            coverage = adapter.coverage_records_for(tenant_id, customer_id, cutoff.as_of)
            for item in coverage:
                if item.available_at > cutoff.as_of:
                    raise PilotError("future usage-coverage evidence reached a prediction cutoff")
                if item.source_category != "usage" or EXPECTED_SOURCE_CATEGORIES.get(item.source) != "usage":
                    raise PilotError("authenticated coverage response had an unexpected source/category pair")
                counters["coverage_interval_status"][item.status] += 1
                counters["source_category_pairs"][f"{item.source}:{item.source_category}"] += 1
            if not coverage:
                missing_usage_coverage_pairs += 1

            evidence = adapter.freshness_evidence_from(snapshot, coverage)
            _increment(counters["connectivity"], _connection_state(evidence))
            freshness = assess_data_freshness(
                tenant_id, customer_id, cutoff.as_of, evidence, evaluated_at=cutoff.as_of
            )
            _increment(counters["freshness"], freshness.status)
            for reason in freshness.reason_codes:
                _increment(counters["freshness_reasons"], reason)
            feature_snapshot = None
            if eligibility.state is EligibilityState.ELIGIBLE:
                eligible_pair_count += 1
                eligible_customer_ids.add(customer_id)
                feature_snapshot = feature_builder.build_from_point_in_time(
                    snapshot, usage_coverage=coverage
                )
                if feature_snapshot.data_cutoff_at > cutoff.as_of:
                    raise PilotError("feature snapshot exceeded its prediction cutoff")
                _increment(counters["coverage_quality"], feature_snapshot.data_quality.usage_coverage_status)
                _increment(counters["baseline"], feature_snapshot.data_quality.personal_baseline_status)
                reliability = assess_reliability(
                    eligibility, feature_snapshot, freshness, evaluated_at=cutoff.as_of
                )
                _increment(counters["reliability"], reliability.status)
                for reason in reliability.reason_codes:
                    _increment(counters["reliability_reasons"], reason)

            evaluation_cutoffs = {
                horizon: label_evaluation_cutoff(
                    cutoff.as_of, horizon, cutoff.label_freeze, maturity_lag
                )
                for horizon in (7, 14, 30)
            }
            outcome = None
            if eligibility.state is EligibilityState.ELIGIBLE:
                outcome = adapter.outcome_snapshot_for(
                    tenant_id, customer_id, cutoff.as_of, cutoff.label_freeze
                )
                outcome_read_pairs += 1
                assert_facts_available_by(
                    outcome.subscription_facts, cutoff.label_freeze, context="outcome label input"
                )
                for observation in outcome.observations:
                    outcome_coverage_statuses[
                        observation.coverage_status or (
                            "complete" if observation.complete else "incomplete"
                        )
                    ] += 1
            for horizon in (7, 14, 30):
                cached = _CachedLifecycleOutcomeAdapter(
                    snapshot, outcome, horizon_days=horizon, maturity_lag_days=maturity_lag
                )
                labels = ChurnLabelBuilder(
                    cached, config=label_config, eligibility_policy=eligibility_policy
                ).build_labels(
                    tenant_id, customer_id, cutoff.as_of, evaluation_cutoffs[horizon],
                    label_generated_at=evaluation_cutoffs[horizon],
                )
                label = next(item for item in labels if int(item.horizon_days) == horizon)
                _increment(counters[f"label_status_{horizon}"], label.label_status)
                stage = cutoff.split.value
                stage_status_counter = stage_label_status.get(stage, {}).get(horizon)
                if stage_status_counter is not None:
                    _increment(stage_status_counter, label.label_status)
                for reason in label.reason_codes:
                    _increment(counters[f"label_reason_{horizon}"], reason)
                if label.label_status is LabelStatus.POSITIVE:
                    eligible_accounts_by_horizon[horizon]["positive"].add(customer_id)
                    if stage in stage_label_accounts:
                        stage_label_accounts[stage][horizon]["positive"].add(customer_id)
                elif label.label_status is LabelStatus.NEGATIVE:
                    eligible_accounts_by_horizon[horizon]["negative"].add(customer_id)
                    if stage in stage_label_accounts:
                        stage_label_accounts[stage][horizon]["negative"].add(customer_id)
                if any(
                    getattr(reason, "value", reason) == "outcome_not_available_by_evaluation_cutoff"
                    for reason in label.reason_codes
                ):
                    late_or_unavailable_label_pairs[str(horizon)] += 1
            if reader_api is not None:
                pair_calls = sum(reader_api.counts.values()) - pair_calls_before
                candidate_api_calls += pair_calls
                if eligibility.state is EligibilityState.ELIGIBLE:
                    eligible_api_calls += pair_calls

    cross_tenant_denial = "NOT_RUN"
    if principal is not None and other_tenant_customer_id is not None and reader_api is not None:
        from retaniq.data_foundation import DataFoundationError

        try:
            cross_tenant_probe_count = 1
            reader_api.get_account_snapshot_as_of(
                adapter.database_path, principal, other_tenant_customer_id,
                _canonical_timestamp(selected_cutoffs[0].as_of),
            )
        except DataFoundationError as error:
            if getattr(error, "code", None) != "not_found":
                raise PilotError("cross-tenant denial probe returned an unexpected error") from None
            cross_tenant_denial = "PASS"
        else:
            raise PilotError("cross-tenant account was readable")

    total_seconds = time.perf_counter() - started
    labels_report: dict[str, Any] = {}
    for horizon in (7, 14, 30):
        statuses = counters[f"label_status_{horizon}"]
        positives = int(statuses.get(LabelStatus.POSITIVE.value, 0))
        negatives = int(statuses.get(LabelStatus.NEGATIVE.value, 0))
        usable = positives + negatives
        labels_report[str(horizon)] = {
            "candidate_snapshots": pair_count,
            "eligible_snapshots_with_label": eligible_pair_count,
            "positive": positives,
            "negative": negatives,
            "unknown": int(statuses.get(LabelStatus.UNKNOWN.value, 0)),
            "excluded": int(statuses.get(LabelStatus.EXCLUDED.value, 0)),
            "unsupported": int(statuses.get(LabelStatus.UNSUPPORTED.value, 0)),
            "usable_supervised": usable,
            "positive_prevalence_among_usable": positives / usable if usable else None,
            "unique_positive_accounts": len(eligible_accounts_by_horizon[horizon]["positive"]),
            "unique_negative_accounts": len(eligible_accounts_by_horizon[horizon]["negative"]),
            "reason_counts": dict(sorted(counters[f"label_reason_{horizon}"].items())),
            "outcome_not_available_by_evaluation_cutoff": late_or_unavailable_label_pairs[str(horizon)],
        }

    stage_label_report: dict[str, dict[str, Any]] = {}
    for stage in stage_label_status:
        stage_label_report[stage] = {}
        for horizon in (7, 14, 30):
            statuses = stage_label_status[stage][horizon]
            stage_label_report[stage][str(horizon)] = {
                "positive": int(statuses.get(LabelStatus.POSITIVE.value, 0)),
                "negative": int(statuses.get(LabelStatus.NEGATIVE.value, 0)),
                "unknown": int(statuses.get(LabelStatus.UNKNOWN.value, 0)),
                "excluded": int(statuses.get(LabelStatus.EXCLUDED.value, 0)),
                "unsupported": int(statuses.get(LabelStatus.UNSUPPORTED.value, 0)),
                "unique_positive_accounts": len(stage_label_accounts[stage][horizon]["positive"]),
                "unique_negative_accounts": len(stage_label_accounts[stage][horizon]["negative"]),
            }

    api_counts = dict(sorted(reader_api.counts.items())) if reader_api is not None else {}
    all_data_calls = sum(
        count for name, count in api_counts.items()
        if name in {
            "get_account_snapshot_as_of", "get_events_as_of", "get_subscriptions_as_of",
            "get_observation_coverage_as_of",
        }
    )
    data_calls = candidate_api_calls
    return {
        "schema_version": PILOT_SCHEMA_VERSION,
        "evidence_type": "SYNTHETIC_ONLY",
        "dataset": {
            "dataset_id": manifest["dataset_id"],
            "manifest_sha256": digest,
            "target_policy_version": manifest["target_policy_version"],
            "tenant_scope": tenant_id,
        },
        "sampling": {
            "method": "ascending SHA-256(dataset_id|tenant_id|customer_id) over customers.csv identity rows; label/outcome blind",
            "candidate_accounts": len(cohort),
            "unique_accounts": len(cohort),
            "candidate_account_cutoff_pairs": pair_count,
            "repeated_account_snapshot_rows": pair_count - len(cohort),
            "cutoffs": [
                {
                    "stage": item.split.value,
                    "as_of": _canonical_timestamp(item.as_of),
                    "label_freeze": _canonical_timestamp(item.label_freeze),
                }
                for item in selected_cutoffs
            ],
            "test_cutoffs_selected": 0,
        },
        "eligibility": {
            "candidate_pairs": pair_count,
            "states": dict(sorted(counters["eligibility"].items())),
            "eligible_pairs": eligible_pair_count,
            "unique_eligible_accounts": len(eligible_customer_ids),
            "repeated_eligible_snapshot_rows": eligible_pair_count - len(eligible_customer_ids),
            "known_cancellation_pairs": int(counters["eligibility"].get(EligibilityState.KNOWN_CANCELLATION.value, 0)),
            "not_eligible_pairs": int(counters["eligibility"].get(EligibilityState.NOT_ELIGIBLE.value, 0)),
            "insufficient_data_pairs": int(counters["eligibility"].get(EligibilityState.INSUFFICIENT_DATA.value, 0)),
        },
        "labels": labels_report,
        "label_statuses_by_development_stage": stage_label_report,
        "source_state": {
            "connectivity_by_candidate_pair": dict(sorted(counters["connectivity"].items())),
            "freshness_by_candidate_pair": dict(sorted(counters["freshness"].items())),
            "freshness_reason_occurrences": dict(sorted(counters["freshness_reasons"].items())),
            "source_not_connected_reason_occurrences": int(counters["freshness_reasons"].get(FreshnessReasonCode.SOURCE_NOT_CONNECTED.value, 0)),
            "explicit_disconnected_evidence_exposed": False,
            "missing_independent_heartbeat_pairs": pair_count,
            "no_account_event_pairs": no_account_event_pairs,
            "pairs_with_usage_events": nonempty_usage_event_pairs,
            "pairs_with_billing_events": nonempty_billing_event_pairs,
            "pairs_with_subscription_events": nonempty_subscription_event_pairs,
            "pairs_with_no_usage_coverage": missing_usage_coverage_pairs,
            "usage_coverage_interval_statuses": dict(sorted(counters["coverage_interval_status"].items())),
            "subscription_outcome_coverage_interval_statuses": dict(sorted(outcome_coverage_statuses.items())),
            "feature_usage_coverage_status_eligible_pairs": dict(sorted(counters["coverage_quality"].items())),
            "freshness_policy_version": "freshness_v1",
            "reason_note": "No independent historical connection/heartbeat API is exposed; silence and absent coverage are not treated as disconnection.",
        },
        "reliability": {
            "denominator_eligible_pairs": eligible_pair_count,
            "status_counts": dict(sorted(counters["reliability"].items())),
            "reason_occurrences": dict(sorted(counters["reliability_reasons"].items())),
            "reliability_abstention_required_pairs": int(counters["reliability"].get("insufficient_evidence", 0)),
            "reliability_abstention_required_fraction": (
                counters["reliability"].get("insufficient_evidence", 0) / eligible_pair_count
                if eligible_pair_count else None
            ),
            "baseline_status_eligible_pairs": dict(sorted(counters["baseline"].items())),
        },
        "member1_member2_eligibility_comparison": {
            "status_pair_counts": dict(sorted(counters["member1_member2_status_pairs"].items())),
            "disagreement_pairs": sum(
                count for key, count in counters["member1_member2_status_pairs"].items()
                if key.split("|", 1)[0] != {
                    "ELIGIBLE": "eligible", "KNOWN_CANCELLATION": "known_cancellation",
                    "NOT_ELIGIBLE": "not_eligible",
                }.get(key.split("|", 1)[1], "unmapped")
            ),
            "known_cancellation_policy_conflict_observed": int(
                counters["eligibility"].get(EligibilityState.KNOWN_CANCELLATION.value, 0)
            ) > 0,
            "policy_note": "Member 1's account snapshot can report NOT_ELIGIBLE when no active subscription is found; Member 2 preserves absent lifecycle history as INSUFFICIENT_DATA. A sampled mismatch is counted above. Known-cancellation rule differences remain unresolved.",
        },
        "point_in_time": {
            "adapter_excluded_record_counts": dict(sorted(counters["point_in_time_exclusions"].items())),
            "feature_facts_checked_for_occurred_and_available_at_cutoff": True,
            "late_rows_hidden_by_member1_api_are_not_enumerable": True,
        },
        "authorization": {
            "cross_tenant_denial_probe": cross_tenant_denial,
            "source_category_pairs_observed": dict(sorted(counters["source_category_pairs"].items())),
        },
        "performance": {
            "elapsed_seconds_excluding_outer_authentication": round(total_seconds, 6),
            "candidate_pairs_per_second": round(pair_count / total_seconds, 6) if total_seconds else None,
            "candidate_data_read_api_calls": data_calls,
            "eligible_case_data_read_api_calls": eligible_api_calls,
            "eligible_outcome_snapshot_pairs": outcome_read_pairs,
            "cross_tenant_denial_probe_calls": cross_tenant_probe_count,
            "all_high_level_data_api_calls_including_denial_probe": all_data_calls,
            "identity_api_calls": int(api_counts.get("get_dataset_identity", 0)),
            "data_read_api_calls_per_candidate": data_calls / pair_count if pair_count else None,
            "data_read_api_calls_per_eligible_pair": eligible_api_calls / eligible_pair_count if eligible_pair_count else None,
            "high_level_api_call_counts": api_counts,
            "high_level_api_seconds": {
                key: round(value, 6) for key, value in sorted(reader_api.seconds.items())
            } if reader_api is not None else {},
            "call_count_scope": "Counts calls made through the adapter reader boundary; nested internal SQL statements inside Member 1 APIs are not separately instrumented.",
        },
        "limits": [
            "Synthetic pilot only; not real-world validation or training-readiness evidence.",
            "The sample is label-blind but repeated account snapshots are correlated.",
            "Member 1 filters unavailable/future rows before returning; excluded raw-row totals cannot be measured through this API.",
            "No TEST cutoff or TEST outcome was read.",
        ],
    }


def _load_member1_runtime(member1_root: str | Path):
    root = Path(member1_root).resolve()
    expected_module = root / "retaniq" / "data_foundation.py"
    if not expected_module.is_file():
        raise PilotError("Member 1 P0 data-foundation module is missing")
    loaded = sys.modules.get("retaniq")
    if loaded is not None:
        loaded_path = Path(getattr(loaded, "__file__", "")).resolve()
        if root not in loaded_path.parents:
            raise PilotError("a different retaniq package was imported before Member 1 P0 bootstrap")
    sys.path.insert(0, str(root))
    data_foundation = importlib.import_module("retaniq.data_foundation")
    if Path(data_foundation.__file__).resolve() != expected_module.resolve():
        raise PilotError("Member 1 P0 import resolved to an unexpected worktree")
    adapter_module = importlib.import_module("retainiq_prediction.sqlite_data_adapter")
    for operation in (
        "get_dataset_identity", "get_account_snapshot_as_of", "get_events_as_of",
        "get_observation_coverage_as_of", "get_subscriptions_as_of",
    ):
        method = getattr(adapter_module._Member1API, operation)
        if method.__module__ != data_foundation.__name__:
            raise PilotError("Member 2 adapter is not bound to the Member 1 P0 API implementation")
    return data_foundation, adapter_module


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--member1-root", type=Path, required=True)
    args = parser.parse_args(argv)
    process_started = time.perf_counter()
    try:
        data_foundation, adapter_module = _load_member1_runtime(args.member1_root)
        auth_started = time.perf_counter()
        principal = authenticate_reader(data_foundation, args.db)
        authentication_seconds = time.perf_counter() - auth_started
        os.environ.pop("RETAINIQ_MODEL_TOKEN", None)
        validate_reader_principal(principal)
        reader = TimedReaderAPI(adapter_module._Member1API)
        adapter = adapter_module.SQLiteDataAdapter(
            args.db, args.dataset, principal, reader_api=reader
        )
        if (adapter.provenance.dataset_id != DATASET_ID
                or adapter.provenance.manifest_sha256 != MANIFEST_SHA256):
            raise PilotError("authenticated working-copy identity does not match the approved manifest")
        other_id = select_one_other_tenant_customer(args.dataset, principal.tenant_id)
        report = run_bounded_pilot(
            adapter, args.dataset, reader_api=reader, principal=principal,
            other_tenant_customer_id=other_id,
        )
        report["authorization"].update({
            "tenant": principal.tenant_id,
            "role": principal.role,
            "authorized_purposes": list(principal.authorized_purposes),
            "authorized_source_count": len(principal.authorized_sources),
            "billing_valuation_authorized": "billing_valuation" in principal.authorized_purposes,
            "model_artifact_write_authorized": "model_artifact_write" in principal.authorized_purposes,
            "member1_data_foundation_path": str(Path(data_foundation.__file__).resolve()),
            "member2_adapter_path": str(Path(adapter_module.__file__).resolve()),
        })
        report["performance"]["authentication_seconds"] = round(
            authentication_seconds, 6
        )
        report["performance"]["end_to_end_seconds"] = round(
            time.perf_counter() - process_started, 6
        )
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0
    except Exception as error:
        # Do not expose exception reprs: provider/OS errors can carry sensitive context.
        code = getattr(error, "code", None)
        safe_name = type(error).__name__
        print(json.dumps({
            "status": "PILOT_BLOCKED",
            "error_type": safe_name,
            "error_code": code if isinstance(code, str) else None,
            "message": str(error) if isinstance(error, (PilotError, ValueError)) else "authenticated pilot failed safely",
        }, sort_keys=True), file=sys.stderr)
        return 2
    finally:
        os.environ.pop("RETAINIQ_MODEL_TOKEN", None)


if __name__ == "__main__":
    raise SystemExit(main())
