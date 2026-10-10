"""Batch, event-triggered and chronological inference orchestration.

The module composes the existing ``PredictionPipeline`` and the canonical
Part 1 prediction writer. It does not implement an API, database schema,
business-action cooldown, or a production schedule. Tenant scope comes from
the configured source/principal; callers cannot select a tenant for a run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .contracts import (
    FreshnessStatus,
    PredictionOutput,
    PredictionStatus,
    ReliabilityStatus,
)
from .data_freshness import SourceFreshnessEvidence
from .feature_builder import UsageCoverage
from .prediction_pipeline import (
    PipelineResult,
    PipelineStatus,
    PredictionPipeline,
    PredictionRequest,
)


class _OperationalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StoreDisposition(str, Enum):
    INSERTED = "inserted"
    ALREADY_PRESENT = "already_present"


class BatchItemStatus(str, Enum):
    STORED = "stored"
    ALREADY_PRESENT = "already_present"
    MODEL_NOT_READY = "model_not_ready"
    PIPELINE_NOT_COMPLETED = "pipeline_not_completed"
    PERSISTENCE_FAILED = "persistence_failed"
    INPUT_EVIDENCE_FAILED = "input_evidence_failed"


class PredictionPersistenceConflict(ValueError):
    """An immutable account/cutoff key already has different content."""


class PredictionSnapshotStore(Protocol):
    """Append-only store interface for canonical prediction snapshots."""

    def append_if_absent(self, prediction: PredictionOutput) -> StoreDisposition:
        """Insert once; accept an identical retry and reject conflicting data."""

    def history_for(
        self, tenant_id: str, customer_id: str
    ) -> tuple[PredictionOutput, ...]:
        """Return immutable snapshots in chronological order."""


def _semantic_json(prediction: PredictionOutput) -> str:
    """Canonical comparison excluding only nondeterministic generation time."""

    return prediction.model_dump_json(exclude={"generated_at"}, by_alias=False)


class InMemoryPredictionSnapshotStore:
    """Synthetic/test-only append-only store implementing the canonical shape."""

    def __init__(self) -> None:
        self._predictions: dict[tuple[str, str, datetime], PredictionOutput] = {}

    def append_if_absent(self, prediction: PredictionOutput) -> StoreDisposition:
        key = (prediction.tenant_id, prediction.customer_id, prediction.as_of)
        existing = self._predictions.get(key)
        if existing is not None:
            if _semantic_json(existing) != _semantic_json(prediction):
                raise PredictionPersistenceConflict(
                    "prediction account/cutoff is immutable and already has different content"
                )
            return StoreDisposition.ALREADY_PRESENT
        self._predictions[key] = prediction.model_copy(deep=True)
        return StoreDisposition.INSERTED

    def history_for(
        self, tenant_id: str, customer_id: str
    ) -> tuple[PredictionOutput, ...]:
        return tuple(
            prediction.model_copy(deep=True)
            for prediction in sorted(
                (
                    item
                    for (item_tenant, item_customer, _), item in self._predictions.items()
                    if item_tenant == tenant_id and item_customer == customer_id
                ),
                key=lambda item: (item.as_of, item.prediction_id),
            )
        )

    def get(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> PredictionOutput | None:
        item = self._predictions.get((tenant_id, customer_id, as_of))
        return item.model_copy(deep=True) if item is not None else None


class ExistingPredictionReader(Protocol):
    def __call__(
        self,
        database_path: str | Path,
        principal: Any,
        customer_id: str,
        as_of: datetime,
    ) -> PredictionOutput | Mapping[str, Any] | None:
        """Read one canonical tenant-scoped prediction, or return ``None``."""


class DataFoundationPredictionSnapshotStore:
    """Persist through Member 1's canonical writer with a required read guard.

    The existing Part 1 writer is append-only and rejects duplicate keys. A
    tenant-authorized reader is required so exact job retries can be recognized
    before writing; this adapter intentionally does not query SQLite directly.
    """

    def __init__(
        self,
        database_path: str | Path,
        principal: Any,
        *,
        read_prediction: ExistingPredictionReader,
        read_history: Callable[..., Sequence[PredictionOutput | Mapping[str, Any]]]
        | None = None,
        write_prediction: Callable[[str | Path, Any, dict[str, Any]], str]
        | None = None,
    ) -> None:
        if not getattr(principal, "tenant_id", None):
            raise ValueError("an authenticated tenant-scoped principal is required")
        if not callable(read_prediction):
            raise ValueError("an authenticated prediction reader is required for idempotency")
        self.database_path = database_path
        self.principal = principal
        self.read_prediction = read_prediction
        self.read_history = read_history
        self.write_prediction = write_prediction

    @property
    def tenant_id(self) -> str:
        """Tenant derived from the authenticated Part 1 principal."""

        return str(self.principal.tenant_id)

    def _reader_value(self, value: PredictionOutput | Mapping[str, Any] | None):
        if value is None or isinstance(value, PredictionOutput):
            return value
        return PredictionOutput.model_validate(value)

    def append_if_absent(self, prediction: PredictionOutput) -> StoreDisposition:
        if prediction.tenant_id != self.tenant_id:
            raise PermissionError("prediction tenant does not match authenticated principal")
        existing = self._reader_value(
            self.read_prediction(
                self.database_path,
                self.principal,
                prediction.customer_id,
                prediction.as_of,
            )
        )
        if existing is not None:
            if (
                existing.tenant_id != prediction.tenant_id
                or existing.customer_id != prediction.customer_id
                or existing.as_of != prediction.as_of
            ):
                raise PermissionError("prediction reader returned an out-of-scope identity")
            if _semantic_json(existing) != _semantic_json(prediction):
                raise PredictionPersistenceConflict(
                    "prediction account/cutoff is immutable and already has different content"
                )
            return StoreDisposition.ALREADY_PRESENT

        writer = self.write_prediction
        if writer is None:
            from retaniq.data_foundation import store_prediction

            writer = store_prediction
        returned_id = writer(
            self.database_path,
            self.principal,
            _member1_prediction_payload(prediction),
        )
        if returned_id != prediction.prediction_id:
            raise RuntimeError("canonical writer returned an unexpected prediction identity")
        return StoreDisposition.INSERTED

    def history_for(
        self, tenant_id: str, customer_id: str
    ) -> tuple[PredictionOutput, ...]:
        if tenant_id != self.tenant_id:
            raise PermissionError("prediction history tenant does not match authenticated principal")
        if self.read_history is None:
            raise NotImplementedError(
                "Member 1 must expose an authenticated prediction-history reader"
            )
        rows = self.read_history(
            self.database_path, self.principal, customer_id
        )
        predictions = tuple(self._reader_value(row) for row in rows)
        if any(item is None for item in predictions):
            raise ValueError("prediction history reader returned an empty row")
        typed = tuple(item for item in predictions if item is not None)
        if any(
            item.tenant_id != tenant_id or item.customer_id != customer_id
            for item in typed
        ):
            raise PermissionError("prediction history reader returned out-of-scope data")
        return tuple(sorted(typed, key=lambda item: (item.as_of, item.prediction_id)))


def _member1_prediction_payload(prediction: PredictionOutput) -> dict[str, Any]:
    """Map the canonical contract to the existing Member 1 writer arguments."""

    return {
        "prediction_id": prediction.prediction_id,
        "prediction_run_id": prediction.prediction_run_id,
        "customer_id": prediction.customer_id,
        "as_of": prediction.as_of.isoformat(),
        "generated_at": prediction.generated_at.isoformat(),
        "status": prediction.status.value,
        "p_churn_7d": prediction.p_churn_7d,
        "p_churn_14d": prediction.p_churn_14d,
        "p_churn_30d": prediction.p_churn_30d,
        "feature_version": prediction.feature_version,
        "model_version": prediction.model_version,
        "calibration_version": prediction.calibration_version,
        "label_policy_version": prediction.label_policy_version,
        "reliability_status": prediction.reliability.status.value,
        "reliability_reasons": list(prediction.reliability.reasons),
        "data_freshness_status": prediction.data_freshness.status.value,
        "input_data_as_of": (
            prediction.data_freshness.input_data_as_of.isoformat()
            if prediction.data_freshness.input_data_as_of is not None
            else None
        ),
        "explanations_by_horizon": prediction.explanations_by_horizon,
    }


class _AccountPredictionSource(Protocol):
    @property
    def tenant_id(self) -> str:
        """Tenant fixed by the authenticated source principal."""

    def eligible_accounts_as_of(self, as_of: datetime) -> Sequence[str]: ...

    def coverage_for(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> Sequence[UsageCoverage]: ...

    def freshness_evidence_for(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> Sequence[SourceFreshnessEvidence]: ...


class _BatchItem(_OperationalModel):
    customer_id: str = Field(min_length=1)
    status: BatchItemStatus
    pipeline_status: PipelineStatus | None = None
    prediction_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    elapsed_seconds: float = Field(ge=0)
    synthetic_test_only: bool = False


class PredictionBatchReport(_OperationalModel):
    tenant_id: str = Field(min_length=1)
    as_of: AwareDatetime
    prediction_run_id: str = Field(min_length=1)
    candidate_account_count: int = Field(ge=0)
    items: tuple[_BatchItem, ...] = ()
    elapsed_seconds: float = Field(ge=0)

    @property
    def stored_count(self) -> int:
        return sum(item.status is BatchItemStatus.STORED for item in self.items)

    @property
    def already_present_count(self) -> int:
        return sum(item.status is BatchItemStatus.ALREADY_PRESENT for item in self.items)

    @property
    def model_not_ready_count(self) -> int:
        return sum(item.status is BatchItemStatus.MODEL_NOT_READY for item in self.items)


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


class DailyPredictionBatch:
    """Run all currently eligible accounts, including silent accounts."""

    def __init__(
        self,
        source: _AccountPredictionSource,
        pipeline: PredictionPipeline,
        store: PredictionSnapshotStore,
    ) -> None:
        self.source = source
        self.pipeline = pipeline
        self.store = store
        store_tenant = getattr(store, "tenant_id", None)
        if store_tenant is not None and source.tenant_id != store_tenant:
            raise PermissionError("source and prediction store tenant scopes differ")

    def run(self, as_of: datetime, prediction_run_id: str) -> PredictionBatchReport:
        _require_aware(as_of, "as_of")
        if not prediction_run_id.strip():
            raise ValueError("prediction_run_id must be non-empty")
        started = perf_counter()
        tenant_id = self.source.tenant_id
        customers = tuple(self.source.eligible_accounts_as_of(as_of))
        if any(not isinstance(customer_id, str) or not customer_id.strip() for customer_id in customers):
            raise ValueError("eligible-account source returned an invalid customer identity")
        if len(customers) != len(set(customers)):
            raise ValueError("eligible-account source returned duplicate customer identities")
        results = tuple(
            self.run_customer(customer_id, as_of, prediction_run_id)
            for customer_id in sorted(customers)
        )
        return PredictionBatchReport(
            tenant_id=tenant_id,
            as_of=as_of,
            prediction_run_id=prediction_run_id,
            candidate_account_count=len(customers),
            items=results,
            elapsed_seconds=max(0.0, perf_counter() - started),
        )

    def run_customer(
        self, customer_id: str, as_of: datetime, prediction_run_id: str
    ) -> _BatchItem:
        _require_aware(as_of, "as_of")
        if not customer_id.strip() or not prediction_run_id.strip():
            raise ValueError("customer_id and prediction_run_id must be non-empty")
        started = perf_counter()
        tenant_id = self.source.tenant_id
        try:
            coverage = tuple(self.source.coverage_for(tenant_id, customer_id, as_of))
            freshness = tuple(
                self.source.freshness_evidence_for(tenant_id, customer_id, as_of)
            )
        except Exception as exc:
            return _BatchItem(
                customer_id=customer_id,
                status=BatchItemStatus.INPUT_EVIDENCE_FAILED,
                reason_codes=(f"INPUT_EVIDENCE_{type(exc).__name__.upper()}",),
                elapsed_seconds=max(0.0, perf_counter() - started),
            )
        request = PredictionRequest(
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=as_of,
            prediction_run_id=prediction_run_id,
            usage_coverage=coverage,
            freshness_evidence=freshness,
        )
        try:
            result = self.pipeline.run(request)
        except Exception as exc:
            return _BatchItem(
                customer_id=customer_id,
                status=BatchItemStatus.PIPELINE_NOT_COMPLETED,
                pipeline_status=PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reason_codes=(f"PIPELINE_{type(exc).__name__.upper()}",),
                elapsed_seconds=max(0.0, perf_counter() - started),
            )
        if (
            result.tenant_id != tenant_id
            or result.customer_id != customer_id
            or result.as_of != as_of
            or result.prediction_run_id != prediction_run_id
        ):
            return _BatchItem(
                customer_id=customer_id,
                status=BatchItemStatus.PIPELINE_NOT_COMPLETED,
                pipeline_status=PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reason_codes=("PIPELINE_IDENTITY_MISMATCH",),
                elapsed_seconds=max(0.0, perf_counter() - started),
            )
        prediction = result.prediction
        if prediction is None:
            item_status = (
                BatchItemStatus.MODEL_NOT_READY
                if result.pipeline_status is PipelineStatus.MODEL_BUNDLE_NOT_READY
                else BatchItemStatus.PIPELINE_NOT_COMPLETED
            )
            return _BatchItem(
                customer_id=customer_id,
                status=item_status,
                pipeline_status=result.pipeline_status,
                reason_codes=tuple(code.value for code in result.reason_codes),
                elapsed_seconds=max(0.0, perf_counter() - started),
                synthetic_test_only=result.synthetic_test_only,
            )
        if (
            prediction.tenant_id != tenant_id
            or prediction.customer_id != customer_id
            or prediction.as_of != as_of
            or prediction.prediction_run_id != prediction_run_id
        ):
            return _BatchItem(
                customer_id=customer_id,
                status=BatchItemStatus.PIPELINE_NOT_COMPLETED,
                pipeline_status=PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reason_codes=("PREDICTION_IDENTITY_MISMATCH",),
                elapsed_seconds=max(0.0, perf_counter() - started),
            )
        try:
            disposition = self.store.append_if_absent(prediction)
        except Exception as exc:
            return _BatchItem(
                customer_id=customer_id,
                status=BatchItemStatus.PERSISTENCE_FAILED,
                pipeline_status=result.pipeline_status,
                prediction_id=prediction.prediction_id,
                reason_codes=(f"PERSISTENCE_{type(exc).__name__.upper()}",),
                elapsed_seconds=max(0.0, perf_counter() - started),
                synthetic_test_only=result.synthetic_test_only,
            )
        return _BatchItem(
            customer_id=customer_id,
            status=(
                BatchItemStatus.STORED
                if disposition is StoreDisposition.INSERTED
                else BatchItemStatus.ALREADY_PRESENT
            ),
            pipeline_status=result.pipeline_status,
            prediction_id=prediction.prediction_id,
            elapsed_seconds=max(0.0, perf_counter() - started),
            synthetic_test_only=result.synthetic_test_only,
        )


class SourceChangeEvent(_OperationalModel):
    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    event_category: str = Field(min_length=1)
    occurred_at: AwareDatetime
    available_at: AwareDatetime

    @model_validator(mode="after")
    def ordered_availability(self) -> "SourceChangeEvent":
        if self.available_at < self.occurred_at:
            raise ValueError("event availability cannot precede occurrence")
        return self


class EventTriggerStatus(str, Enum):
    TRIGGER_HANDLED = "trigger_handled"
    DUPLICATE_IGNORED = "duplicate_ignored"
    REJECTED_SCOPE = "rejected_scope"
    REJECTED_NOT_AVAILABLE = "rejected_not_available"
    REJECTED_CONFLICT = "rejected_conflict"


class EventTriggerResult(_OperationalModel):
    status: EventTriggerStatus
    event_id: str
    item: _BatchItem | None = None
    reason_code: str | None = None


class EventTriggeredPrediction:
    """Recompute for an authorized source change after its availability time."""

    def __init__(self, batch: DailyPredictionBatch) -> None:
        self.batch = batch
        self._events: dict[tuple[str, str, str], tuple[str, EventTriggerResult]] = {}

    @staticmethod
    def _fingerprint(event: SourceChangeEvent) -> str:
        raw = json.dumps(
            event.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def on_source_change(
        self,
        event: SourceChangeEvent,
        *,
        as_of: datetime,
        prediction_run_id: str,
    ) -> EventTriggerResult:
        _require_aware(as_of, "as_of")
        if event.tenant_id != self.batch.source.tenant_id:
            return EventTriggerResult(
                status=EventTriggerStatus.REJECTED_SCOPE,
                event_id=event.event_id,
                reason_code="TENANT_SCOPE_MISMATCH",
            )
        if event.occurred_at > as_of or event.available_at > as_of:
            return EventTriggerResult(
                status=EventTriggerStatus.REJECTED_NOT_AVAILABLE,
                event_id=event.event_id,
                reason_code="SOURCE_CHANGE_NOT_AVAILABLE_AT_CUTOFF",
            )
        key = (event.tenant_id, event.source, event.event_id)
        fingerprint = self._fingerprint(event)
        previous = self._events.get(key)
        if previous is not None:
            if previous[0] != fingerprint:
                return EventTriggerResult(
                    status=EventTriggerStatus.REJECTED_CONFLICT,
                    event_id=event.event_id,
                    reason_code="SOURCE_EVENT_ID_CONFLICT",
                )
            return previous[1].model_copy(
                update={"status": EventTriggerStatus.DUPLICATE_IGNORED}
            )
        item = self.batch.run_customer(
            event.customer_id, as_of, prediction_run_id
        )
        result = EventTriggerResult(
            status=EventTriggerStatus.TRIGGER_HANDLED,
            event_id=event.event_id,
            item=item,
        )
        self._events[key] = (fingerprint, result)
        return result


class RiskChange(_OperationalModel):
    tenant_id: str
    customer_id: str
    previous_prediction_id: str
    prediction_id: str
    previous_as_of: AwareDatetime
    as_of: AwareDatetime
    p7_change: float | None = None
    p14_change: float | None = None
    p30_change: float | None = None
    comparable_model_versions: bool
    note: str


def risk_evolution(predictions: Sequence[PredictionOutput]) -> tuple[RiskChange, ...]:
    """Describe changes between real persisted snapshots, not a future curve."""

    by_account: dict[tuple[str, str], list[PredictionOutput]] = {}
    seen: set[tuple[str, str, datetime]] = set()
    for prediction in predictions:
        key = (prediction.tenant_id, prediction.customer_id, prediction.as_of)
        if key in seen:
            raise ValueError("risk history contains duplicate account/cutoff snapshots")
        seen.add(key)
        by_account.setdefault(key[:2], []).append(prediction)
    changes: list[RiskChange] = []
    for (tenant_id, customer_id), rows in sorted(by_account.items()):
        ordered = sorted(rows, key=lambda item: (item.as_of, item.prediction_id))
        for previous, current in zip(ordered, ordered[1:]):
            comparable = (
                previous.status is PredictionStatus.SCORED
                and current.status is PredictionStatus.SCORED
                and previous.model_version == current.model_version
                and previous.calibration_version == current.calibration_version
                and previous.feature_version == current.feature_version
            )
            changes.append(
                RiskChange(
                    tenant_id=tenant_id,
                    customer_id=customer_id,
                    previous_prediction_id=previous.prediction_id,
                    prediction_id=current.prediction_id,
                    previous_as_of=previous.as_of,
                    as_of=current.as_of,
                    p7_change=(current.p_churn_7d - previous.p_churn_7d) if comparable else None,  # type: ignore[operator]
                    p14_change=(current.p_churn_14d - previous.p_churn_14d) if comparable else None,  # type: ignore[operator]
                    p30_change=(current.p_churn_30d - previous.p_churn_30d) if comparable else None,  # type: ignore[operator]
                    comparable_model_versions=comparable,
                    note=(
                        "change between persisted model predictions; not a forecast trajectory"
                        if comparable
                        else "not comparable: a prediction was non-scored or model/feature/calibration version changed"
                    ),
                )
            )
    return tuple(changes)


class AlertPolicy(_OperationalModel):
    """Versioned risk-alert policy; not Part 3 discretionary-contact policy."""

    policy_version: str = Field(min_length=1)
    probability_threshold: float = Field(ge=0.0, le=1.0)
    minimum_reliability: ReliabilityStatus = ReliabilityStatus.SUFFICIENT_EVIDENCE
    allowed_freshness: frozenset[FreshnessStatus] = frozenset(
        {FreshnessStatus.FRESH, FreshnessStatus.PARTIALLY_STALE}
    )
    require_rising_risk: bool = True
    minimum_p30_increase: float = Field(default=0.0, ge=0.0, le=1.0)
    allow_initial_threshold_alert: bool = True
    cooldown: timedelta = timedelta(days=7)
    period_days: int = Field(default=7, ge=1, le=366)
    maximum_alerts_per_period: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def require_policy(self) -> "AlertPolicy":
        if not self.allowed_freshness:
            raise ValueError("at least one freshness status must be allowed")
        if self.cooldown < timedelta(0):
            raise ValueError("cooldown must not be negative")
        return self


class HistoricalRiskAlert(_OperationalModel):
    tenant_id: str
    customer_id: str
    prediction_id: str
    alerted_at: AwareDatetime
    policy_version: str = Field(min_length=1)


class RiskAlertDecision(_OperationalModel):
    tenant_id: str
    customer_id: str
    prediction_id: str
    as_of: AwareDatetime
    policy_version: str
    selected: bool
    reason_code: str
    p_churn_30d: float | None = Field(default=None, ge=0.0, le=1.0)


def _period_key(as_of: datetime, period_days: int) -> int:
    return as_of.astimezone(timezone.utc).date().toordinal() // period_days


def apply_alert_policy(
    current_predictions: Sequence[PredictionOutput],
    *,
    prior_predictions: Sequence[PredictionOutput],
    prior_alerts: Sequence[HistoricalRiskAlert],
    policy: AlertPolicy,
) -> tuple[RiskAlertDecision, ...]:
    """Apply versioned eligibility, trend, cooldown and reviewer-budget gates."""

    if not current_predictions:
        return ()
    cutoffs = {item.as_of for item in current_predictions}
    tenants = {item.tenant_id for item in current_predictions}
    if len(cutoffs) != 1 or len(tenants) != 1:
        raise ValueError("alert budget evaluation requires one tenant and one cutoff batch")
    if len({item.customer_id for item in current_predictions}) != len(current_predictions):
        raise ValueError("alert batch has duplicate account predictions")
    cutoff = next(iter(cutoffs))
    if any(item.tenant_id not in tenants for item in prior_predictions):
        raise PermissionError("prior prediction history crosses tenant scope")
    if any(item.tenant_id not in tenants for item in prior_alerts):
        raise PermissionError("prior alert history crosses tenant scope")

    prior_by_account: dict[tuple[str, str], list[PredictionOutput]] = {}
    for item in prior_predictions:
        if item.as_of < cutoff:
            prior_by_account.setdefault((item.tenant_id, item.customer_id), []).append(item)
    last_alert_by_account: dict[tuple[str, str], datetime] = {}
    for alert in prior_alerts:
        if alert.alerted_at > cutoff:
            continue
        key = (alert.tenant_id, alert.customer_id)
        last_alert_by_account[key] = max(
            last_alert_by_account.get(key, alert.alerted_at), alert.alerted_at
        )

    candidates: list[PredictionOutput] = []
    decisions: dict[str, RiskAlertDecision] = {}
    reliability_rank = {
        ReliabilityStatus.INSUFFICIENT_EVIDENCE: 0,
        ReliabilityStatus.LIMITED_EVIDENCE: 1,
        ReliabilityStatus.SUFFICIENT_EVIDENCE: 2,
    }
    for prediction in current_predictions:
        reason: str | None = None
        if prediction.status is not PredictionStatus.SCORED or prediction.p_churn_30d is None:
            reason = "PREDICTION_NOT_SCORED"
        elif reliability_rank[prediction.reliability.status] < reliability_rank[
            policy.minimum_reliability
        ]:
            reason = "RELIABILITY_BELOW_POLICY"
        if reason is None and prediction.data_freshness.status not in policy.allowed_freshness:
            reason = "FRESHNESS_NOT_ALLOWED"
        if reason is None and prediction.p_churn_30d < policy.probability_threshold:  # type: ignore[operator]
            reason = "BELOW_PROBABILITY_THRESHOLD"
        key = (prediction.tenant_id, prediction.customer_id)
        previous = max(
            prior_by_account.get(key, ()), key=lambda item: item.as_of, default=None
        )
        if reason is None and policy.require_rising_risk:
            if previous is None:
                if not policy.allow_initial_threshold_alert:
                    reason = "RISK_TREND_UNAVAILABLE"
            elif (
                previous.status is not PredictionStatus.SCORED
                or previous.p_churn_30d is None
                or previous.model_version != prediction.model_version
                or previous.calibration_version != prediction.calibration_version
                or previous.feature_version != prediction.feature_version
            ):
                reason = "RISK_TREND_NOT_COMPARABLE"
            elif prediction.p_churn_30d - previous.p_churn_30d < policy.minimum_p30_increase:  # type: ignore[operator]
                reason = "RISK_NOT_RISING"
        last_alert = last_alert_by_account.get(key)
        if (
            reason is None
            and last_alert is not None
            and cutoff - last_alert < policy.cooldown
        ):
            reason = "COOLDOWN_ACTIVE"
        if reason is None:
            candidates.append(prediction)
            reason = "AWAITING_PERIOD_BUDGET"
        decisions[prediction.prediction_id] = RiskAlertDecision(
            tenant_id=prediction.tenant_id,
            customer_id=prediction.customer_id,
            prediction_id=prediction.prediction_id,
            as_of=prediction.as_of,
            policy_version=policy.policy_version,
            selected=False,
            reason_code=reason,
            p_churn_30d=prediction.p_churn_30d,
        )

    selected_accounts: set[tuple[str, str]] = set()
    period_candidates = sorted(
        candidates,
        key=lambda item: (
            -float(item.p_churn_30d),
            item.tenant_id,
            item.customer_id,
            item.prediction_id,
        ),
    )
    period_id = _period_key(cutoff, policy.period_days)
    prior_period_prediction_ids = {
        alert.prediction_id
        for alert in prior_alerts
        if alert.alerted_at <= cutoff
        and _period_key(alert.alerted_at, policy.period_days) == period_id
    }
    remaining_budget = max(
        0, policy.maximum_alerts_per_period - len(prior_period_prediction_ids)
    )
    for prediction in period_candidates:
        decision = decisions[prediction.prediction_id]
        key = (prediction.tenant_id, prediction.customer_id)
        if len(selected_accounts) >= remaining_budget:
            decisions[prediction.prediction_id] = decision.model_copy(
                update={"reason_code": "PERIOD_BUDGET_EXHAUSTED"}
            )
            continue
        if key in selected_accounts:
            decisions[prediction.prediction_id] = decision.model_copy(
                update={"reason_code": "ACCOUNT_ALREADY_SELECTED_IN_PERIOD"}
            )
            continue
        selected_accounts.add(key)
        decisions[prediction.prediction_id] = decision.model_copy(
            update={"selected": True, "reason_code": "ALERT_SELECTED"}
        )
    return tuple(decisions[item.prediction_id] for item in current_predictions)


class ReplayReport(_OperationalModel):
    tenant_id: str
    customer_id: str
    cutoffs: tuple[AwareDatetime, ...]
    prediction_run_ids: tuple[str, ...]
    items: tuple[_BatchItem, ...]
    changes: tuple[RiskChange, ...]
    synthetic_demo_only: bool


class PointInTimeReplayRunner:
    """Replay requested cutoffs through the live feature/prediction path.

    No labels/outcomes are accepted by this API. Outcomes can only be passed
    to the existing evaluator after this method returns persisted predictions.
    The source adapter is responsible for ordered, point-in-time event reads;
    this runner never writes/replays source events through Part 1 ingestion.
    """

    def __init__(self, batch: DailyPredictionBatch) -> None:
        self.batch = batch

    def replay_customer(
        self,
        customer_id: str,
        cutoffs: Sequence[datetime],
        *,
        prediction_run_prefix: str,
    ) -> ReplayReport:
        ordered = tuple(cutoffs)
        if not customer_id.strip() or not prediction_run_prefix.strip():
            raise ValueError("customer_id and prediction_run_prefix must be non-empty")
        if not ordered:
            raise ValueError("at least one replay cutoff is required")
        for cutoff in ordered:
            _require_aware(cutoff, "replay cutoff")
        if tuple(sorted(ordered)) != ordered or len(set(ordered)) != len(ordered):
            raise ValueError("replay cutoffs must be strictly chronological and unique")
        items: list[_BatchItem] = []
        run_ids: list[str] = []
        predictions: list[PredictionOutput] = []
        for index, cutoff in enumerate(ordered):
            run_id = f"{prediction_run_prefix}_{index + 1:04d}"
            run_ids.append(run_id)
            item = self.batch.run_customer(customer_id, cutoff, run_id)
            items.append(item)
            if item.status in {BatchItemStatus.STORED, BatchItemStatus.ALREADY_PRESENT}:
                stored = self.batch.store.history_for(
                    self.batch.source.tenant_id, customer_id
                )
                matching = next(
                    (
                        row
                        for row in stored
                        if row.as_of == cutoff and row.prediction_run_id == run_id
                    ),
                    None,
                )
                if matching is None:
                    raise RuntimeError("prediction write was not visible in canonical history")
                predictions.append(matching)
        return ReplayReport(
            tenant_id=self.batch.source.tenant_id,
            customer_id=customer_id,
            cutoffs=ordered,
            prediction_run_ids=tuple(run_ids),
            items=tuple(items),
            changes=risk_evolution(predictions),
            synthetic_demo_only=any(item.synthetic_test_only for item in items),
        )


__all__ = [
    "AlertPolicy",
    "BatchItemStatus",
    "DataFoundationPredictionSnapshotStore",
    "DailyPredictionBatch",
    "EventTriggeredPrediction",
    "EventTriggerResult",
    "EventTriggerStatus",
    "HistoricalRiskAlert",
    "InMemoryPredictionSnapshotStore",
    "PointInTimeReplayRunner",
    "PredictionBatchReport",
    "PredictionPersistenceConflict",
    "ReplayReport",
    "RiskAlertDecision",
    "RiskChange",
    "SourceChangeEvent",
    "StoreDisposition",
    "apply_alert_policy",
    "risk_evolution",
]
