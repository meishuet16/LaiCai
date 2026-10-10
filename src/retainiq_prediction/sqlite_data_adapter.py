"""Read-only bridge from Member 1's authenticated API into Member 2's types."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field

from retaniq.data_foundation import (
    DataFoundationError, ServicePrincipal, get_account_snapshot_as_of,
    get_dataset_identity, get_events_as_of, get_observation_coverage_as_of,
    get_subscriptions_as_of, list_eligible_accounts_as_of,
)
from .data_freshness import FreshnessSource, SourceFreshnessEvidence
from .eligibility import EligibilityPolicy, EligibilityResult, evaluate_prediction_eligibility
from .feature_builder import FeatureBuilderConfig, UsageCoverage
from .label_builder import LifecycleOutcomeSnapshot, OutcomeObservation
from .point_in_time import (
    AvailabilityPolicy, BillingFact, FactCategory, PointInTimeSnapshot,
    SubscriptionFact, UsageFact, _require_scoped_request,
)


class DatasetIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    dataset_type: str = Field(min_length=1)
    target_policy_version: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_status: str = "SYNTHETIC_ONLY"


class _ReadAPI(Protocol):
    def get_dataset_identity(self, path: str | Path, principal: ServicePrincipal) -> dict[str, str]: ...
    def get_account_snapshot_as_of(self, path: str | Path, principal: ServicePrincipal, customer_id: str, as_of: str) -> dict[str, Any]: ...
    def get_events_as_of(self, path: str | Path, principal: ServicePrincipal, customer_id: str, as_of: str, *, category: str | None = None) -> list[dict[str, Any]]: ...
    def get_observation_coverage_as_of(self, path: str | Path, principal: ServicePrincipal, customer_id: str, as_of: str, *, source_category: str | None = None) -> list[dict[str, Any]]: ...
    def get_subscriptions_as_of(self, path: str | Path, principal: ServicePrincipal, customer_id: str, as_of: str) -> list[dict[str, Any]]: ...
    def list_eligible_accounts_as_of(self, path: str | Path, principal: ServicePrincipal, as_of: str) -> list[dict[str, Any]]: ...


def _stamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _datetime(value: str | datetime | None, name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    else:
        raise ValueError(f"{name} must be an ISO timestamp or datetime")
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return result


def _availability(row: dict[str, Any]) -> tuple[datetime | None, str | None]:
    source = _datetime(row.get("source_available_at"), "source_available_at")
    if source is not None:
        return source, "source_available_at"
    received = _datetime(row.get("received_at"), "received_at")
    return received, "received_at" if received is not None else None


_ACTIVE = frozenset({"active", "past_due", "pending_cancel"})
_EFFECTIVE_TYPES = {
    "subscription_cancelled_effective": "voluntary_cancellation",
    "subscription_non_renewed_effective": "non_renewal",
    "subscription_involuntary_terminated": "involuntary_termination",
}


class SQLiteDataAdapter:
    """Tenant-bound Member 1 API adapter; no direct database SQL is used."""

    def __init__(
        self, database_path: str | Path, dataset_path: str | Path,
        principal: ServicePrincipal, *,
        availability_policy: AvailabilityPolicy = AvailabilityPolicy.SOURCE_THEN_RECEIVED,
        reader_api: _ReadAPI | None = None,
    ) -> None:
        self.database_path = Path(database_path).resolve()
        self.dataset_path = Path(dataset_path).resolve()
        self.principal = principal
        self.availability_policy = availability_policy
        self.reader_api = reader_api or _Member1API
        if not self.database_path.is_file() or not self.dataset_path.is_dir():
            raise ValueError("database and dataset paths must exist")
        if not isinstance(principal, ServicePrincipal):
            raise DataFoundationError("unauthorized")
        if "retention_inference" not in principal.authorized_purposes:
            raise DataFoundationError("purpose_not_authorized")
        if availability_policy is not AvailabilityPolicy.SOURCE_THEN_RECEIVED:
            raise ValueError("Member 1 currently enforces source availability, then received_at")
        try:
            raw = (self.dataset_path / "dataset_manifest.json").read_bytes()
            manifest = json.loads(raw)
            if manifest.get("dataset_type") != "synthetic_saas":
                raise ValueError("only synthetic_saas provenance is supported")
            expected = {
                "dataset_id": manifest["dataset_id"],
                "dataset_version": str(manifest["dataset_version"]),
                "dataset_type": "synthetic_saas",
                "target_policy_version": manifest["target_policy_version"],
                "generator_version": manifest["generator_code_version"],
                "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            }
            stored = self.reader_api.get_dataset_identity(self.database_path, principal)
            if any(stored.get(key) != val for key, val in expected.items()):
                raise ValueError("SQLite dataset identity does not match the manifest")
            self.provenance = DatasetIdentity(**expected)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError("dataset manifest is missing or invalid") from exc

    @property
    def tenant_id(self) -> str:
        return self.principal.tenant_id

    def _scope(self, tenant_id: str, customer_id: str, as_of: datetime) -> None:
        _require_scoped_request(tenant_id, customer_id, as_of)
        if tenant_id != self.tenant_id:
            raise DataFoundationError("unauthorized")

    def _rows(self, customer_id: str, as_of: datetime, category: str | None = None):
        rows = self.reader_api.get_events_as_of(
            self.database_path, self.principal, customer_id, _stamp(as_of), category=category
        )
        included, excluded, limitations = [], {}, []
        for row in rows:
            if row.get("customer_id") != customer_id:
                raise DataFoundationError("contract_conflict")
            occurred = _datetime(row.get("occurred_at"), "occurred_at")
            available, _ = _availability(row)
            if occurred is None:
                excluded["missing_event_time"] = excluded.get("missing_event_time", 0) + 1
            elif occurred > as_of:
                excluded["future_event_or_effective_time"] = excluded.get("future_event_or_effective_time", 0) + 1
            elif available is None:
                excluded["historical_availability_unknown"] = excluded.get("historical_availability_unknown", 0) + 1
            elif available > as_of:
                excluded["late_arriving_fact"] = excluded.get("late_arriving_fact", 0) + 1
            else:
                included.append(row)
        if excluded.get("historical_availability_unknown"):
            limitations.append("Facts without usable historical availability evidence were excluded.")
        if excluded.get("late_arriving_fact"):
            limitations.append("Late-arriving facts were excluded at this cutoff.")
        if excluded.get("future_event_or_effective_time"):
            limitations.append("Facts occurring after this cutoff were excluded.")
        return included, excluded, limitations

    @staticmethod
    def _map_facts(
        tenant_id: str, customer_id: str, rows: Sequence[dict[str, Any]],
        as_of: datetime,
    ):
        subs, usage, billing, basis = [], [], [], {}
        states: dict[str, dict[str, Any]] = {}
        for row in rows:
            event_id, source = str(row.get("event_id", "")), str(row.get("source", ""))
            category, event_type = row.get("category"), str(row.get("event_type", ""))
            occurred = _datetime(row.get("occurred_at"), "occurred_at")
            received = _datetime(row.get("received_at"), "received_at")
            source_available = _datetime(row.get("source_available_at"), "source_available_at")
            if not event_id or not source or occurred is None:
                continue
            attrs = dict(row.get("attributes") or {})
            _, availability_basis = _availability(row)
            if availability_basis:
                basis[event_id] = availability_basis
            provenance_attrs = {
                **attrs,
                "source_event_id": row.get("source_event_id"),
                "source_category": category,
                "source_event_type": event_type,
            }
            common = dict(
                record_id=event_id, tenant_id=tenant_id, customer_id=customer_id,
                source=source, occurred_at=occurred,
                source_available_at=source_available, received_at=received,
            )
            if category == "usage":
                if event_type == "usage_aggregate_updated":
                    quantity = attrs.get("quantity")
                    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
                        provenance_attrs["adapter_quantity_invalid"] = True
                usage.append(UsageFact(
                    **common, event_type=event_type, attributes=provenance_attrs
                ))
            elif category == "billing":
                status = row.get("payment_status") or attrs.get("payment_status")
                billing.append(BillingFact(
                    **common, event_type=event_type,
                    payment_status=str(status) if status is not None else None,
                    attributes=provenance_attrs,
                ))
            elif category == "subscription":
                subscription_id = str(row.get("subscription_id") or attrs.get("subscription_id") or "")
                if not subscription_id:
                    continue
                state = states.setdefault(subscription_id, {})
                state.update(attrs.get("changes") or {})
                normalized_type = _EFFECTIVE_TYPES.get(event_type, event_type)
                ended = _datetime(state.get("ended_at"), "ended_at")
                future_termination = ended is not None and ended > as_of
                if normalized_type in _EFFECTIVE_TYPES.values() and not future_termination:
                    state["status"] = "ended"
                status = state.get("status")
                if future_termination and (
                    normalized_type in _EFFECTIVE_TYPES.values()
                    or (isinstance(status, str) and status.lower() in {"ended", "cancelled", "terminated", "expired"})
                ):
                    normalized_type = "scheduled_cancellation"
                    status = "pending_cancel"
                if not isinstance(status, str) or not status:
                    continue
                effective = ended if ended is not None and ended <= as_of and normalized_type in _EFFECTIVE_TYPES.values() else occurred
                cancellation = _datetime(state.get("cancellation_requested_at"), "cancellation_requested_at")
                scheduled = None
                if event_type in {"cancellation_requested", "scheduled_cancellation"} or status == "pending_cancel":
                    scheduled = ended or _datetime(state.get("current_period_end"), "current_period_end")
                subs.append(SubscriptionFact(
                    **common, subscription_id=subscription_id,
                    event_type=normalized_type, status=status,
                    is_paying=status.lower() in _ACTIVE,
                    effective_at=effective,
                    cancellation_requested_at=cancellation,
                    scheduled_termination_at=scheduled,
                    attributes={
                        **provenance_attrs,
                        "subscription_state_reconstructed_from_lifecycle_events": True,
                    },
                ))
        return tuple(subs), tuple(usage), tuple(billing), basis

    def snapshot_for(self, tenant_id: str, customer_id: str, as_of: datetime) -> PointInTimeSnapshot:
        self._scope(tenant_id, customer_id, as_of)
        account = self.reader_api.get_account_snapshot_as_of(
            self.database_path, self.principal, customer_id, _stamp(as_of)
        )
        if account.get("tenant_id") != self.tenant_id or account.get("customer_id") != customer_id:
            raise DataFoundationError("contract_conflict")
        rows, excluded, limitations = self._rows(customer_id, as_of)
        subs, usage, billing, basis = self._map_facts(tenant_id, customer_id, rows, as_of)
        if any(fact.attributes.get("adapter_quantity_invalid") for fact in usage):
            limitations.append(
                "A daily usage aggregate lacked a valid nonnegative integer quantity and was not counted."
            )
        # Cross-check the owner-provided as-of fold without using it as a
        # substitute for timestamped lifecycle evidence.
        projected = self.reader_api.get_subscriptions_as_of(
            self.database_path, self.principal, customer_id, _stamp(as_of)
        )
        latest_by_id = {}
        for fact in subs:
            previous = latest_by_id.get(fact.subscription_id)
            if previous is None or (fact.point_in_time(), fact.record_id) > (
                previous.point_in_time(), previous.record_id
            ):
                latest_by_id[fact.subscription_id] = fact
        for item in projected:
            start = _datetime(item.get("started_at"), "started_at")
            if item.get("customer_id", customer_id) != customer_id or (
                start is not None and start > as_of
            ):
                raise DataFoundationError("contract_conflict")
            fact = latest_by_id.get(str(item.get("subscription_id", "")))
            status = item.get("status")
            if fact is None or not isinstance(status, str) or fact.status.lower() != status.lower():
                limitations.append(
                    "Member 1's as-of subscription fold disagrees with mapped lifecycle evidence."
                )
        return PointInTimeSnapshot(
            tenant_id=tenant_id, customer_id=customer_id, as_of=as_of,
            availability_policy=self.availability_policy,
            subscriptions=subs, usage_events=usage, billing_events=billing,
            availability_basis_by_record=basis,
            excluded_record_counts=excluded, limitations=tuple(limitations),
        )

    def coverage_records_for(self, tenant_id: str, customer_id: str, as_of: datetime, *, source_category: str = "usage") -> tuple[UsageCoverage, ...]:
        self._scope(tenant_id, customer_id, as_of)
        rows = self.reader_api.get_observation_coverage_as_of(
            self.database_path, self.principal, customer_id, _stamp(as_of),
            source_category=source_category,
        )
        result = []
        for row in rows:
            if row.get("tenant_id") not in {None, tenant_id} or row.get("customer_id") != customer_id:
                raise DataFoundationError("contract_conflict")
            start = _datetime(row.get("covered_from"), "covered_from")
            end = _datetime(row.get("covered_through"), "covered_through")
            available = _datetime(row.get("coverage_available_at"), "coverage_available_at")
            if start is None or end is None or available is None or available > as_of:
                continue
            status = str(row.get("coverage_status", "unknown"))
            completeness = float(row.get("coverage_completeness", 0.0))
            result.append(UsageCoverage(
                coverage_id=str(row["coverage_id"]), source=str(row["source"]),
                observed_from=start, observed_to=end, available_at=available,
                complete=status == "complete" and completeness == 1.0,
                status=status, completeness=completeness,
                source_category=str(row["source_category"]),
                observation_policy_version=str(row["observation_policy_version"]),
            ))
        return tuple(result)

    def coverage_for(self, tenant_id: str, customer_id: str, as_of: datetime) -> tuple[UsageCoverage, ...]:
        return self.coverage_records_for(tenant_id, customer_id, as_of)

    @staticmethod
    def feature_builder_config() -> FeatureBuilderConfig:
        return FeatureBuilderConfig(
            session_event_types=frozenset({"session_started", "usage_aggregate_updated"}),
            quantity_event_types=frozenset({"usage_aggregate_updated"}),
        )

    @staticmethod
    def synthetic_eligibility_policy() -> EligibilityPolicy:
        """Return the explicit Synthetic SaaS v1.2 lifecycle policy only."""

        return EligibilityPolicy(
            active_statuses=frozenset({"active", "past_due", "pending_cancel"}),
            terminal_statuses=frozenset({"ended", "cancelled", "terminated", "expired"}),
            account_churn_policy="effective-account-churn-v1.2-synthetic-only",
        )

    def eligibility_from_snapshot(
        self, snapshot: PointInTimeSnapshot, *, policy: EligibilityPolicy | None = None
    ) -> EligibilityResult:
        self._scope(snapshot.tenant_id, snapshot.customer_id, snapshot.as_of)
        selected = policy or self.synthetic_eligibility_policy()
        return evaluate_prediction_eligibility(
            snapshot, policy=selected
        )

    def eligibility_for(self, tenant_id: str, customer_id: str, as_of: datetime, *, policy: EligibilityPolicy | None = None) -> EligibilityResult:
        return self.eligibility_from_snapshot(
            self.snapshot_for(tenant_id, customer_id, as_of), policy=policy
        )

    def prediction_snapshot_for(self, tenant_id: str, customer_id: str, as_of: datetime) -> PointInTimeSnapshot:
        return self.snapshot_for(tenant_id, customer_id, as_of)

    def outcome_snapshot_for(self, tenant_id: str, customer_id: str, prediction_as_of: datetime, evaluation_as_of: datetime) -> LifecycleOutcomeSnapshot:
        self._scope(tenant_id, customer_id, prediction_as_of)
        if evaluation_as_of.tzinfo is None or evaluation_as_of.utcoffset() is None or evaluation_as_of < prediction_as_of:
            raise ValueError("evaluation_as_of must be aware and not precede prediction_as_of")
        rows, excluded, limitations = self._rows(customer_id, evaluation_as_of, "subscription")
        subs, _, _, _ = self._map_facts(
            tenant_id, customer_id, rows, evaluation_as_of
        )
        coverage_rows = self.reader_api.get_observation_coverage_as_of(
            self.database_path, self.principal, customer_id, _stamp(evaluation_as_of),
            source_category="subscription",
        )
        observations = []
        for row in coverage_rows:
            start = _datetime(row.get("covered_from"), "covered_from")
            end = _datetime(row.get("covered_through"), "covered_through")
            available = _datetime(row.get("coverage_available_at"), "coverage_available_at")
            if start is None or end is None or available is None:
                continue
            complete = row.get("coverage_status") == "complete" and float(row.get("coverage_completeness", 0)) == 1.0
            observations.append(OutcomeObservation(
                observation_id=str(row["coverage_id"]), source=str(row["source"]),
                observed_from=start, observed_through=end, available_at=available,
                complete=complete,
            ))
        return LifecycleOutcomeSnapshot(
            tenant_id=tenant_id, customer_id=customer_id,
            prediction_as_of=prediction_as_of, evaluation_as_of=evaluation_as_of,
            subscription_facts=subs, observations=tuple(observations),
            excluded_record_counts=excluded, limitations=tuple(limitations),
        )

    def freshness_evidence_for(self, tenant_id: str, customer_id: str, as_of: datetime) -> tuple[SourceFreshnessEvidence, ...]:
        snapshot = self.snapshot_for(tenant_id, customer_id, as_of)
        coverage = self.coverage_records_for(tenant_id, customer_id, as_of)
        return self.freshness_evidence_from(snapshot, coverage)

    def freshness_evidence_from(
        self,
        snapshot: PointInTimeSnapshot,
        coverage: Sequence[UsageCoverage],
    ) -> tuple[SourceFreshnessEvidence, ...]:
        """Map already-read, scoped evidence into the canonical freshness input."""

        tenant_id, customer_id, as_of = snapshot.tenant_id, snapshot.customer_id, snapshot.as_of
        self._scope(tenant_id, customer_id, as_of)
        if any(
            item.available_at > as_of
            for item in coverage
        ):
            raise ValueError("future coverage cannot be used for cutoff freshness")
        result = []
        for source, facts in (
            (FreshnessSource.SUBSCRIPTION_LIFECYCLE.value, snapshot.subscriptions),
            (FreshnessSource.BILLING_EVENTS.value, snapshot.billing_events),
        ):
            latest = max(facts, key=lambda f: f.point_in_time(), default=None)
            result.append(SourceFreshnessEvidence(
                tenant_id=tenant_id, customer_id=customer_id, source=source,
                source_available_at=latest.source_available_at if latest else None,
                received_at=latest.received_at if latest else None,
                watermark_at=latest.point_in_time() if latest else None,
                complete=None, connected=latest is not None,
                source_record_refs=tuple(f.record_id for f in facts),
                limitations=("No independent completeness watermark is exposed by Member 1.",),
            ))
        usages = [row for row in coverage if row.source_category == "usage"]
        latest_coverage = max(usages, key=lambda row: row.observed_to, default=None)
        result.append(SourceFreshnessEvidence(
            tenant_id=tenant_id, customer_id=customer_id,
            source=FreshnessSource.USAGE_COVERAGE.value,
            source_available_at=latest_coverage.available_at if latest_coverage else None,
            watermark_at=latest_coverage.observed_to if latest_coverage else None,
            complete=all(row.complete for row in usages) if usages else None,
            connected=bool(usages),
            source_record_refs=tuple(row.coverage_id for row in usages),
            limitations=("No usage coverage is available at this cutoff.",) if not usages else (),
        ))
        return tuple(result)

    def eligible_accounts_as_of(self, as_of: datetime) -> tuple[str, ...]:
        rows = self.reader_api.list_eligible_accounts_as_of(
            self.database_path, self.principal, _stamp(as_of)
        )
        return tuple(str(row["customer_id"]) for row in rows)


class _Member1API:
    get_dataset_identity = staticmethod(get_dataset_identity)
    get_account_snapshot_as_of = staticmethod(get_account_snapshot_as_of)
    get_events_as_of = staticmethod(get_events_as_of)
    get_observation_coverage_as_of = staticmethod(get_observation_coverage_as_of)
    get_subscriptions_as_of = staticmethod(get_subscriptions_as_of)
    list_eligible_accounts_as_of = staticmethod(list_eligible_accounts_as_of)


__all__ = ["DatasetIdentity", "SQLiteDataAdapter"]
