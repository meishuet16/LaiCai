"""Point-in-time-safe 7/14/30-day churn label generation.

Labels are built from later observed lifecycle evidence and never mutate the
prediction-time feature snapshot.  This module does not train models or make
predictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import FrozenSet, Iterable, Literal, Protocol, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .eligibility import (
    EligibilityPolicy,
    EligibilityReasonCode,
    EligibilityState,
    evaluate_prediction_eligibility,
)
from .point_in_time import (
    AvailabilityPolicy,
    InMemoryPointInTimeAdapter,
    PointInTimeSnapshot,
    SubscriptionFact,
)


SUPPORTED_HORIZONS = (7, 14, 30)
HorizonDays = Literal[7, 14, 30]


class LabelStatus(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"


class ChurnType(str, Enum):
    VOLUNTARY_CANCELLATION = "voluntary_cancellation"
    NON_RENEWAL = "non_renewal"
    INVOLUNTARY_TERMINATION = "involuntary_termination"


class LabelReasonCode(str, Enum):
    QUALIFYING_CHURN_OBSERVED = "qualifying_churn_observed"
    FULL_HORIZON_OBSERVED_NO_CHURN = "full_horizon_observed_no_churn"
    OUTCOME_OBSERVATION_INCOMPLETE = "outcome_observation_incomplete"
    OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF = (
        "outcome_not_available_by_evaluation_cutoff"
    )
    KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF = (
        "known_cancellation_at_prediction_cutoff"
    )
    ALREADY_TERMINATED_AT_PREDICTION_CUTOFF = (
        "already_terminated_at_prediction_cutoff"
    )
    ELIGIBILITY_INSUFFICIENT = "eligibility_insufficient"
    UNRESOLVED_MULTI_SUBSCRIPTION_POLICY = (
        "unresolved_multi_subscription_policy"
    )
    CONFLICTING_LIFECYCLE_EVIDENCE = "conflicting_lifecycle_evidence"
    MISSING_OUTCOME_COVERAGE = "missing_outcome_coverage"


class _LabelModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OutcomeObservation(_LabelModel):
    """Evidence that lifecycle outcome observation extends through a cutoff."""

    observation_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    observed_from: AwareDatetime
    observed_through: AwareDatetime
    available_at: AwareDatetime
    subscription_id: str | None = Field(default=None, min_length=1)
    complete: bool = True

    @model_validator(mode="after")
    def validate_observation_range(self) -> "OutcomeObservation":
        if self.observed_through < self.observed_from:
            raise ValueError("observed_through must not precede observed_from")
        return self


class LifecycleOutcomeSnapshot(_LabelModel):
    """Outcome evidence scoped to one account and label evaluation cutoff."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    prediction_as_of: AwareDatetime
    evaluation_as_of: AwareDatetime
    subscription_facts: tuple[SubscriptionFact, ...] = ()
    observations: tuple[OutcomeObservation, ...] = ()
    excluded_record_counts: dict[str, int] = Field(default_factory=dict)
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_cutoffs(self) -> "LifecycleOutcomeSnapshot":
        if self.evaluation_as_of < self.prediction_as_of:
            raise ValueError("evaluation_as_of must not precede prediction_as_of")
        return self


class ChurnLabel(_LabelModel):
    """One explicit label for one account, cutoff, and horizon."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    evaluation_as_of: AwareDatetime
    horizon_days: HorizonDays
    label: Literal[0, 1] | None = None
    label_status: LabelStatus
    churn_type: ChurnType | None = None
    churn_effective_at: AwareDatetime | None = None
    label_observed_through: AwareDatetime
    label_policy_version: str = Field(min_length=1)
    source_evidence_refs: tuple[str, ...] = ()
    label_generated_at: AwareDatetime
    reason_codes: tuple[LabelReasonCode, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_label_state(self) -> "ChurnLabel":
        if self.evaluation_as_of < self.as_of:
            raise ValueError("evaluation_as_of must not precede as_of")
        if self.label_status is LabelStatus.POSITIVE:
            if self.label != 1 or self.churn_effective_at is None:
                raise ValueError("positive labels require label=1 and churn_effective_at")
            horizon_end = self.as_of + timedelta(days=int(self.horizon_days))
            if not self.as_of < self.churn_effective_at <= horizon_end:
                raise ValueError("positive churn must fall inside (as_of, as_of+horizon]")
        elif self.label_status is LabelStatus.NEGATIVE:
            if self.label != 0 or self.churn_effective_at is not None or self.churn_type is not None:
                raise ValueError("negative labels require label=0 and no churn event")
        elif self.label is not None:
            raise ValueError("unknown, excluded, and unsupported labels must be null")
        if self.label_status is not LabelStatus.POSITIVE and self.churn_type is not None:
            raise ValueError("churn_type is only valid for positive labels")
        return self


@dataclass(frozen=True)
class ChurnEventSemantics:
    """Explicit mapping from canonical lifecycle event types to churn types."""

    voluntary_event_types: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            {"cancellation_effective", "voluntary_cancellation", "cancelled"}
        )
    )
    non_renewal_event_types: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"non_renewal", "expired"})
    )
    involuntary_event_types: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            {"involuntary_termination", "collection_termination"}
        )
    )
    terminal_statuses: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"cancelled", "terminated", "expired"})
    )


@dataclass(frozen=True)
class LabelBuilderConfig:
    label_policy_version: str = "churn_labels_v1"
    availability_policy: AvailabilityPolicy = AvailabilityPolicy.SOURCE_THEN_RECEIVED
    churn_events: ChurnEventSemantics = field(default_factory=ChurnEventSemantics)

    def __post_init__(self) -> None:
        if not self.label_policy_version.strip():
            raise ValueError("label_policy_version must be non-empty")


class LifecycleOutcomeAdapter(Protocol):
    """Replaceable Member 1 boundary for prediction and later outcomes."""

    def prediction_snapshot_for(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> PointInTimeSnapshot:
        """Return the facts knowable at the prediction cutoff."""

    def outcome_snapshot_for(
        self,
        tenant_id: str,
        customer_id: str,
        prediction_as_of: datetime,
        evaluation_as_of: datetime,
    ) -> LifecycleOutcomeSnapshot:
        """Return outcome facts and coverage available by evaluation_as_of."""


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _availability_time(
    fact: SubscriptionFact, policy: AvailabilityPolicy
) -> tuple[datetime | None, str | None]:
    if policy is AvailabilityPolicy.SOURCE_ONLY:
        return fact.source_available_at, "source_available_at" if fact.source_available_at else None
    if policy is AvailabilityPolicy.RECEIVED_ONLY:
        return fact.received_at, "received_at" if fact.received_at else None
    if fact.source_available_at is not None:
        return fact.source_available_at, "source_available_at"
    if fact.received_at is not None:
        return fact.received_at, "received_at"
    return None, None


class InMemoryLifecycleOutcomeAdapter:
    """Synthetic-only adapter using existing typed subscription facts."""

    def __init__(
        self,
        facts: Iterable[SubscriptionFact],
        *,
        observations: Iterable[OutcomeObservation] = (),
        availability_policy: AvailabilityPolicy = AvailabilityPolicy.SOURCE_THEN_RECEIVED,
    ) -> None:
        self._facts = tuple(facts)
        self._observations = tuple(observations)
        self.availability_policy = availability_policy
        self._prediction_adapter = InMemoryPointInTimeAdapter(
            self._facts, availability_policy=availability_policy
        )

    def prediction_snapshot_for(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> PointInTimeSnapshot:
        return self._prediction_adapter.snapshot_for(tenant_id, customer_id, as_of)

    def outcome_snapshot_for(
        self,
        tenant_id: str,
        customer_id: str,
        prediction_as_of: datetime,
        evaluation_as_of: datetime,
    ) -> LifecycleOutcomeSnapshot:
        _require_aware(prediction_as_of, "prediction_as_of")
        _require_aware(evaluation_as_of, "evaluation_as_of")
        if evaluation_as_of < prediction_as_of:
            raise ValueError("evaluation_as_of must not precede prediction_as_of")

        included: list[SubscriptionFact] = []
        excluded: dict[str, int] = {}
        limitations: list[str] = []

        def exclude(reason: str) -> None:
            excluded[reason] = excluded.get(reason, 0) + 1

        for fact in self._facts:
            if fact.tenant_id != tenant_id or fact.customer_id != customer_id:
                continue
            event_time = fact.point_in_time()
            if event_time > evaluation_as_of:
                exclude("future_outcome_not_yet_observable")
                continue
            available_at, _ = _availability_time(fact, self.availability_policy)
            if available_at is None:
                exclude("historical_availability_unknown")
                continue
            if available_at > evaluation_as_of:
                exclude("late_outcome_not_available")
                continue
            included.append(fact)

        usable_observations: list[OutcomeObservation] = []
        for observation in self._observations:
            if observation.available_at > evaluation_as_of:
                exclude("observation_not_available")
                continue
            usable_observations.append(observation)

        if excluded.get("late_outcome_not_available"):
            limitations.append(
                "Some outcome facts were available only after evaluation_as_of and were excluded."
            )
        if excluded.get("historical_availability_unknown"):
            limitations.append(
                "Some matching outcome facts had no usable availability timestamp and were excluded."
            )
        if excluded.get("observation_not_available"):
            limitations.append(
                "Some lifecycle observation coverage became available after evaluation_as_of."
            )

        return LifecycleOutcomeSnapshot(
            tenant_id=tenant_id,
            customer_id=customer_id,
            prediction_as_of=prediction_as_of,
            evaluation_as_of=evaluation_as_of,
            subscription_facts=tuple(
                sorted(included, key=lambda fact: (fact.point_in_time(), fact.record_id))
            ),
            observations=tuple(usable_observations),
            excluded_record_counts=excluded,
            limitations=tuple(dict.fromkeys(limitations)),
        )


@dataclass(frozen=True)
class _QualifyingEvent:
    fact: SubscriptionFact
    churn_type: ChurnType


class ChurnLabelBuilder:
    """Build mature or explicitly unknown labels without lookahead."""

    def __init__(
        self,
        adapter: LifecycleOutcomeAdapter,
        *,
        config: LabelBuilderConfig | None = None,
        eligibility_policy: EligibilityPolicy | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or LabelBuilderConfig()
        self.eligibility_policy = eligibility_policy or EligibilityPolicy()

    def build_labels(
        self,
        tenant_id: str,
        customer_id: str,
        as_of: datetime,
        evaluation_as_of: datetime,
        *,
        label_generated_at: datetime | None = None,
    ) -> tuple[ChurnLabel, ...]:
        """Build independent 7/14/30-day labels for one prediction cutoff."""

        _require_aware(as_of, "as_of")
        _require_aware(evaluation_as_of, "evaluation_as_of")
        if evaluation_as_of < as_of:
            raise ValueError("evaluation_as_of must not precede as_of")
        generated_at = label_generated_at or evaluation_as_of
        _require_aware(generated_at, "label_generated_at")

        prediction_snapshot = self.adapter.prediction_snapshot_for(
            tenant_id, customer_id, as_of
        )
        outcome_snapshot = self.adapter.outcome_snapshot_for(
            tenant_id, customer_id, as_of, evaluation_as_of
        )
        eligibility = evaluate_prediction_eligibility(
            prediction_snapshot, policy=self.eligibility_policy
        )
        base_refs = tuple(
            dict.fromkeys(
                [fact.record_id for fact in prediction_snapshot.subscriptions]
                + [fact.record_id for fact in outcome_snapshot.subscription_facts]
                + [observation.observation_id for observation in outcome_snapshot.observations]
            )
        )
        base_limitations = tuple(
            dict.fromkeys(eligibility.limitations + outcome_snapshot.limitations)
        )

        if eligibility.state is not EligibilityState.ELIGIBLE:
            return tuple(
                self._non_prospective_label(
                    tenant_id,
                    customer_id,
                    as_of,
                    evaluation_as_of,
                    horizon,
                    generated_at,
                    base_refs,
                    base_limitations,
                    eligibility.reason_codes,
                )
                for horizon in SUPPORTED_HORIZONS
            )

        active_ids = set(eligibility.active_subscription_ids)
        outcome_facts = [
            fact
            for fact in outcome_snapshot.subscription_facts
            if fact.subscription_id in active_ids
        ]
        early_termination = [
            event
            for event in self._qualifying_events(outcome_facts)
            if event.fact.effective_at is not None and event.fact.effective_at <= as_of
        ]
        if early_termination:
            return tuple(
                self._excluded_label(
                    tenant_id,
                    customer_id,
                    as_of,
                    evaluation_as_of,
                    horizon,
                    generated_at,
                    base_refs,
                    base_limitations,
                    LabelReasonCode.ALREADY_TERMINATED_AT_PREDICTION_CUTOFF,
                )
                for horizon in SUPPORTED_HORIZONS
            )

        return tuple(
            self._build_horizon_label(
                tenant_id,
                customer_id,
                as_of,
                evaluation_as_of,
                horizon,
                generated_at,
                active_ids,
                outcome_facts,
                outcome_snapshot,
                base_refs,
                base_limitations,
            )
            for horizon in SUPPORTED_HORIZONS
        )

    def build_for(self, *args, **kwargs) -> tuple[ChurnLabel, ...]:
        """Compatibility alias for callers that use ``build_for`` terminology."""

        return self.build_labels(*args, **kwargs)

    def _build_horizon_label(
        self,
        tenant_id: str,
        customer_id: str,
        as_of: datetime,
        evaluation_as_of: datetime,
        horizon: int,
        generated_at: datetime,
        active_ids: set[str],
        outcome_facts: Sequence[SubscriptionFact],
        outcome_snapshot: LifecycleOutcomeSnapshot,
        base_refs: tuple[str, ...],
        base_limitations: tuple[str, ...],
    ) -> ChurnLabel:
        horizon_end = as_of + timedelta(days=horizon)
        candidates = [
            event
            for event in self._qualifying_events(outcome_facts)
            if event.fact.effective_at is not None
            and as_of < event.fact.effective_at <= horizon_end
        ]
        conflict = self._has_conflicting_evidence(outcome_facts, candidates)
        if conflict:
            return self._unknown_label(
                tenant_id,
                customer_id,
                as_of,
                evaluation_as_of,
                horizon,
                generated_at,
                base_refs,
                base_limitations,
                LabelReasonCode.CONFLICTING_LIFECYCLE_EVIDENCE,
            )

        selected = self._select_account_event(candidates, active_ids)
        if selected == "conflict":
            return self._unknown_label(
                tenant_id,
                customer_id,
                as_of,
                evaluation_as_of,
                horizon,
                generated_at,
                base_refs,
                base_limitations,
                LabelReasonCode.CONFLICTING_LIFECYCLE_EVIDENCE,
            )
        if isinstance(selected, _QualifyingEvent):
            return ChurnLabel(
                tenant_id=tenant_id,
                customer_id=customer_id,
                as_of=as_of,
                evaluation_as_of=evaluation_as_of,
                horizon_days=horizon,  # type: ignore[arg-type]
                label=1,
                label_status=LabelStatus.POSITIVE,
                churn_type=selected.churn_type,
                churn_effective_at=selected.fact.effective_at,
                label_observed_through=evaluation_as_of,
                label_policy_version=self.config.label_policy_version,
                source_evidence_refs=tuple(
                    dict.fromkeys(base_refs + (selected.fact.record_id,))
                ),
                label_generated_at=generated_at,
                reason_codes=(LabelReasonCode.QUALIFYING_CHURN_OBSERVED,),
                limitations=base_limitations,
            )

        if outcome_snapshot.excluded_record_counts.get("late_outcome_not_available"):
            return self._unknown_label(
                tenant_id,
                customer_id,
                as_of,
                evaluation_as_of,
                horizon,
                generated_at,
                base_refs,
                base_limitations,
                LabelReasonCode.OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF,
            )

        if self._coverage_through(
            outcome_snapshot.observations,
            as_of,
            horizon_end,
            active_ids,
        ):
            return ChurnLabel(
                tenant_id=tenant_id,
                customer_id=customer_id,
                as_of=as_of,
                evaluation_as_of=evaluation_as_of,
                horizon_days=horizon,  # type: ignore[arg-type]
                label=0,
                label_status=LabelStatus.NEGATIVE,
                label_observed_through=horizon_end,
                label_policy_version=self.config.label_policy_version,
                source_evidence_refs=base_refs,
                label_generated_at=generated_at,
                reason_codes=(LabelReasonCode.FULL_HORIZON_OBSERVED_NO_CHURN,),
                limitations=base_limitations,
            )

        reason = (
            LabelReasonCode.OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF
            if outcome_snapshot.excluded_record_counts.get("late_outcome_not_available")
            else LabelReasonCode.MISSING_OUTCOME_COVERAGE
        )
        return self._unknown_label(
            tenant_id,
            customer_id,
            as_of,
            evaluation_as_of,
            horizon,
            generated_at,
            base_refs,
            base_limitations,
            reason,
            observed_through=self._latest_observed_through(
                outcome_snapshot.observations, as_of, evaluation_as_of, horizon_end
            ),
        )

    def _qualifying_events(
        self, facts: Sequence[SubscriptionFact]
    ) -> tuple[_QualifyingEvent, ...]:
        semantics = self.config.churn_events
        events: list[_QualifyingEvent] = []
        for fact in facts:
            if fact.effective_at is None:
                continue
            if fact.status.strip().lower() not in semantics.terminal_statuses:
                continue
            event_type = fact.event_type.strip().lower()
            churn_type: ChurnType | None = None
            if event_type in {item.lower() for item in semantics.voluntary_event_types}:
                churn_type = ChurnType.VOLUNTARY_CANCELLATION
            elif event_type in {item.lower() for item in semantics.non_renewal_event_types}:
                churn_type = ChurnType.NON_RENEWAL
            elif event_type in {item.lower() for item in semantics.involuntary_event_types}:
                churn_type = ChurnType.INVOLUNTARY_TERMINATION
            if churn_type is not None:
                events.append(_QualifyingEvent(fact=fact, churn_type=churn_type))
        return tuple(events)

    def _select_account_event(
        self, candidates: Sequence[_QualifyingEvent], active_ids: set[str]
    ) -> _QualifyingEvent | str | None:
        by_subscription: dict[str, list[_QualifyingEvent]] = {}
        for candidate in candidates:
            by_subscription.setdefault(candidate.fact.subscription_id, []).append(candidate)
        for values in by_subscription.values():
            if len({(item.fact.record_id, item.fact.effective_at, item.churn_type) for item in values}) > 1:
                return "conflict"

        if len(active_ids) <= 1:
            return candidates[0] if candidates else None
        policy = self.eligibility_policy.account_churn_policy
        if policy == "any_subscription_end":
            return min(candidates, key=lambda item: item.fact.effective_at or item.fact.point_in_time()) if candidates else None
        if policy == "all_subscriptions_end":
            if set(by_subscription) == active_ids and all(by_subscription.values()):
                selected = min(
                    (values[0] for values in by_subscription.values()),
                    key=lambda item: item.fact.effective_at or item.fact.point_in_time(),
                )
                return selected
            return None
        return "conflict"

    @staticmethod
    def _has_conflicting_evidence(
        facts: Sequence[SubscriptionFact], candidates: Sequence[_QualifyingEvent]
    ) -> bool:
        candidate_keys = {
            (event.fact.subscription_id, event.fact.effective_at) for event in candidates
        }
        for fact in facts:
            if (fact.subscription_id, fact.effective_at) in candidate_keys:
                if fact.event_type.strip().lower() not in {
                    event.fact.event_type.strip().lower() for event in candidates
                } and fact.status.strip().lower() not in {"cancelled", "terminated", "expired"}:
                    return True
        return False

    @staticmethod
    def _coverage_through(
        observations: Sequence[OutcomeObservation],
        as_of: datetime,
        horizon_end: datetime,
        active_ids: set[str],
    ) -> bool:
        relevant = [
            observation
            for observation in observations
            if observation.complete
            and observation.observed_from <= as_of
            and observation.observed_through >= horizon_end
            and (
                observation.subscription_id is None
                or observation.subscription_id in active_ids
            )
        ]
        if any(observation.subscription_id is None for observation in relevant):
            return True
        return active_ids and active_ids.issubset(
            {observation.subscription_id for observation in relevant}
        )

    def _non_prospective_label(
        self,
        tenant_id: str,
        customer_id: str,
        as_of: datetime,
        evaluation_as_of: datetime,
        horizon: int,
        generated_at: datetime,
        refs: tuple[str, ...],
        limitations: tuple[str, ...],
        eligibility_reasons: Sequence[EligibilityReasonCode],
    ) -> ChurnLabel:
        if EligibilityReasonCode.KNOWN_CANCELLATION_AT_CUTOFF in eligibility_reasons:
            status = LabelStatus.EXCLUDED
            reason = LabelReasonCode.KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF
        elif EligibilityReasonCode.TERMINATED_BEFORE_CUTOFF in eligibility_reasons:
            status = LabelStatus.EXCLUDED
            reason = LabelReasonCode.ALREADY_TERMINATED_AT_PREDICTION_CUTOFF
        elif any(
            reason_code is EligibilityReasonCode.NO_ACTIVE_PAYING_SUBSCRIPTION
            for reason_code in eligibility_reasons
        ):
            status = LabelStatus.EXCLUDED
            reason = LabelReasonCode.ALREADY_TERMINATED_AT_PREDICTION_CUTOFF
        elif EligibilityReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY in eligibility_reasons:
            status = LabelStatus.UNSUPPORTED
            reason = LabelReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY
        else:
            status = LabelStatus.UNSUPPORTED
            reason = LabelReasonCode.ELIGIBILITY_INSUFFICIENT
        return ChurnLabel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=as_of,
            evaluation_as_of=evaluation_as_of,
            horizon_days=horizon,  # type: ignore[arg-type]
            label=None,
            label_status=status,
            label_observed_through=as_of,
            label_policy_version=self.config.label_policy_version,
            source_evidence_refs=refs,
            label_generated_at=generated_at,
            reason_codes=(reason,),
            limitations=limitations,
        )

    def _excluded_label(
        self,
        tenant_id: str,
        customer_id: str,
        as_of: datetime,
        evaluation_as_of: datetime,
        horizon: int,
        generated_at: datetime,
        refs: tuple[str, ...],
        limitations: tuple[str, ...],
        reason: LabelReasonCode,
    ) -> ChurnLabel:
        return ChurnLabel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=as_of,
            evaluation_as_of=evaluation_as_of,
            horizon_days=horizon,  # type: ignore[arg-type]
            label_status=LabelStatus.EXCLUDED,
            label_observed_through=as_of,
            label_policy_version=self.config.label_policy_version,
            source_evidence_refs=refs,
            label_generated_at=generated_at,
            reason_codes=(reason,),
            limitations=limitations,
        )

    def _unknown_label(
        self,
        tenant_id: str,
        customer_id: str,
        as_of: datetime,
        evaluation_as_of: datetime,
        horizon: int,
        generated_at: datetime,
        refs: tuple[str, ...],
        limitations: tuple[str, ...],
        reason: LabelReasonCode,
        *,
        observed_through: datetime | None = None,
    ) -> ChurnLabel:
        return ChurnLabel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=as_of,
            evaluation_as_of=evaluation_as_of,
            horizon_days=horizon,  # type: ignore[arg-type]
            label_status=LabelStatus.UNKNOWN,
            label_observed_through=observed_through or as_of,
            label_policy_version=self.config.label_policy_version,
            source_evidence_refs=refs,
            label_generated_at=generated_at,
            reason_codes=(reason,),
            limitations=limitations,
        )

    @staticmethod
    def _latest_observed_through(
        observations: Sequence[OutcomeObservation],
        as_of: datetime,
        evaluation_as_of: datetime,
        horizon_end: datetime,
    ) -> datetime:
        usable = [
            observation.observed_through
            for observation in observations
            if observation.complete
            and observation.available_at <= evaluation_as_of
            and observation.observed_from <= as_of
        ]
        if not usable:
            return as_of
        return min(max(usable), horizon_end)


__all__ = [
    "ChurnEventSemantics",
    "ChurnLabel",
    "ChurnLabelBuilder",
    "ChurnType",
    "HorizonDays",
    "InMemoryLifecycleOutcomeAdapter",
    "LabelBuilderConfig",
    "LabelReasonCode",
    "LabelStatus",
    "LifecycleOutcomeAdapter",
    "LifecycleOutcomeSnapshot",
    "OutcomeObservation",
    "SUPPORTED_HORIZONS",
]
