"""Customer prediction eligibility reconstructed from point-in-time facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet

from pydantic import AwareDatetime, BaseModel, ConfigDict

from .contracts import PredictionStatus
from .point_in_time import PointInTimeSnapshot, SubscriptionFact


class EligibilityState(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    KNOWN_CANCELLATION = "KNOWN_CANCELLATION"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EligibilityReasonCode(str, Enum):
    ACTIVE_PAYING_SUBSCRIPTION = "ACTIVE_PAYING_SUBSCRIPTION"
    KNOWN_CANCELLATION_AT_CUTOFF = "KNOWN_CANCELLATION_AT_CUTOFF"
    NO_ACTIVE_PAYING_SUBSCRIPTION = "NO_ACTIVE_PAYING_SUBSCRIPTION"
    TERMINATED_BEFORE_CUTOFF = "TERMINATED_BEFORE_CUTOFF"
    MISSING_SUBSCRIPTION_HISTORY = "MISSING_SUBSCRIPTION_HISTORY"
    SUBSCRIPTION_STATUS_UNRESOLVED = "SUBSCRIPTION_STATUS_UNRESOLVED"
    CONTRADICTORY_LIFECYCLE = "CONTRADICTORY_LIFECYCLE"
    UNRESOLVED_MULTI_SUBSCRIPTION_POLICY = "UNRESOLVED_MULTI_SUBSCRIPTION_POLICY"
    HISTORICAL_AVAILABILITY_LIMITED = "HISTORICAL_AVAILABILITY_LIMITED"


@dataclass(frozen=True)
class EligibilityPolicy:
    """Business policy inputs that remain explicit and replaceable."""

    active_statuses: FrozenSet[str] = field(default_factory=lambda: frozenset({"active"}))
    terminal_statuses: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"cancelled", "terminated", "expired"})
    )
    account_churn_policy: str | None = None


class EligibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    customer_id: str
    as_of: AwareDatetime
    state: EligibilityState
    reason_codes: tuple[EligibilityReasonCode, ...] = ()
    active_subscription_ids: tuple[str, ...] = ()
    considered_subscription_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def canonical_prediction_status(self) -> PredictionStatus | None:
        """Map non-scored eligibility outcomes to the existing contract.

        `ELIGIBLE` returns None because eligibility alone does not create a
        scored prediction. No new statuses are added to PredictionOutput.
        """

        return {
            EligibilityState.KNOWN_CANCELLATION: PredictionStatus.KNOWN_CANCELLATION,
            EligibilityState.NOT_ELIGIBLE: PredictionStatus.NOT_ELIGIBLE,
            EligibilityState.INSUFFICIENT_DATA: PredictionStatus.ABSTAINED,
        }.get(self.state)


def _unique_reasons(*reasons: EligibilityReasonCode) -> tuple[EligibilityReasonCode, ...]:
    return tuple(dict.fromkeys(reasons))


def _latest_subscription_state(
    facts: list[SubscriptionFact], policy: EligibilityPolicy
) -> tuple[str, SubscriptionFact | None, tuple[EligibilityReasonCode, ...]]:
    if not facts:
        return "missing", None, (EligibilityReasonCode.MISSING_SUBSCRIPTION_HISTORY,)

    latest_time = max(fact.point_in_time() for fact in facts)
    latest = [fact for fact in facts if fact.point_in_time() == latest_time]
    state_pairs = {(fact.status.lower(), fact.is_paying) for fact in latest}
    if len(state_pairs) > 1:
        return "ambiguous", None, (EligibilityReasonCode.CONTRADICTORY_LIFECYCLE,)

    selected = latest[-1]
    status = selected.status.lower()
    if status in policy.active_statuses:
        if selected.is_paying is True:
            return "active", selected, (EligibilityReasonCode.ACTIVE_PAYING_SUBSCRIPTION,)
        if selected.is_paying is False:
            return "terminal", selected, (EligibilityReasonCode.NO_ACTIVE_PAYING_SUBSCRIPTION,)
        return "ambiguous", selected, (EligibilityReasonCode.SUBSCRIPTION_STATUS_UNRESOLVED,)
    if status in policy.terminal_statuses or selected.is_paying is False:
        reason = (
            EligibilityReasonCode.TERMINATED_BEFORE_CUTOFF
            if status in policy.terminal_statuses
            else EligibilityReasonCode.NO_ACTIVE_PAYING_SUBSCRIPTION
        )
        return "terminal", selected, (reason,)
    return "ambiguous", selected, (EligibilityReasonCode.SUBSCRIPTION_STATUS_UNRESOLVED,)


def _has_known_cancellation(facts: list[SubscriptionFact], as_of) -> bool:
    for fact in facts:
        for cancellation_at in (fact.cancellation_requested_at, fact.scheduled_termination_at):
            if cancellation_at is not None and cancellation_at <= as_of:
                return True
        if fact.event_type.lower() in {"cancellation_requested", "scheduled_cancellation"}:
            return True
    return False


def evaluate_prediction_eligibility(
    snapshot: PointInTimeSnapshot,
    *,
    policy: EligibilityPolicy | None = None,
) -> EligibilityResult:
    """Evaluate one scoped point-in-time snapshot without using future state."""

    eligibility_policy = policy or EligibilityPolicy()
    by_subscription: dict[str, list[SubscriptionFact]] = {}
    for fact in snapshot.subscriptions:
        by_subscription.setdefault(fact.subscription_id, []).append(fact)

    limitations = list(snapshot.limitations)
    reasons: list[EligibilityReasonCode] = []
    considered = tuple(sorted(by_subscription))
    if not by_subscription:
        reasons.append(EligibilityReasonCode.MISSING_SUBSCRIPTION_HISTORY)
        if snapshot.excluded_record_counts.get("historical_availability_unknown"):
            reasons.append(EligibilityReasonCode.HISTORICAL_AVAILABILITY_LIMITED)
        return EligibilityResult(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=snapshot.as_of,
            state=EligibilityState.INSUFFICIENT_DATA,
            reason_codes=_unique_reasons(*reasons),
            limitations=tuple(limitations),
        )

    active_ids: list[str] = []
    terminal_count = 0
    ambiguous = False
    cancellation_known = False
    for subscription_id, facts in by_subscription.items():
        state, _, state_reasons = _latest_subscription_state(facts, eligibility_policy)
        reasons.extend(state_reasons)
        cancellation_known = cancellation_known or _has_known_cancellation(facts, snapshot.as_of)
        if state == "active":
            active_ids.append(subscription_id)
        elif state == "terminal":
            terminal_count += 1
        else:
            ambiguous = True

    if ambiguous:
        return EligibilityResult(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=snapshot.as_of,
            state=EligibilityState.INSUFFICIENT_DATA,
            reason_codes=_unique_reasons(
                *reasons,
                EligibilityReasonCode.SUBSCRIPTION_STATUS_UNRESOLVED,
            ),
            active_subscription_ids=tuple(sorted(active_ids)),
            considered_subscription_ids=considered,
            limitations=tuple(limitations),
        )

    if len(active_ids) > 1 and eligibility_policy.account_churn_policy is None:
        return EligibilityResult(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=snapshot.as_of,
            state=EligibilityState.INSUFFICIENT_DATA,
            reason_codes=_unique_reasons(
                *reasons,
                EligibilityReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY,
            ),
            active_subscription_ids=tuple(sorted(active_ids)),
            considered_subscription_ids=considered,
            limitations=tuple(limitations),
        )

    if active_ids and cancellation_known:
        return EligibilityResult(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=snapshot.as_of,
            state=EligibilityState.KNOWN_CANCELLATION,
            reason_codes=_unique_reasons(
                *reasons,
                EligibilityReasonCode.KNOWN_CANCELLATION_AT_CUTOFF,
            ),
            active_subscription_ids=tuple(sorted(active_ids)),
            considered_subscription_ids=considered,
            limitations=tuple(limitations),
        )

    if active_ids:
        return EligibilityResult(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=snapshot.as_of,
            state=EligibilityState.ELIGIBLE,
            reason_codes=_unique_reasons(*reasons, EligibilityReasonCode.ACTIVE_PAYING_SUBSCRIPTION),
            active_subscription_ids=tuple(sorted(active_ids)),
            considered_subscription_ids=considered,
            limitations=tuple(limitations),
        )

    if terminal_count == len(by_subscription):
        return EligibilityResult(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=snapshot.as_of,
            state=EligibilityState.NOT_ELIGIBLE,
            reason_codes=_unique_reasons(*reasons, EligibilityReasonCode.NO_ACTIVE_PAYING_SUBSCRIPTION),
            considered_subscription_ids=considered,
            limitations=tuple(limitations),
        )

    return EligibilityResult(
        tenant_id=snapshot.tenant_id,
        customer_id=snapshot.customer_id,
        as_of=snapshot.as_of,
        state=EligibilityState.INSUFFICIENT_DATA,
        reason_codes=_unique_reasons(*reasons, EligibilityReasonCode.SUBSCRIPTION_STATUS_UNRESOLVED),
        active_subscription_ids=tuple(sorted(active_ids)),
        considered_subscription_ids=considered,
        limitations=tuple(limitations),
    )


__all__ = [
    "EligibilityPolicy",
    "EligibilityReasonCode",
    "EligibilityResult",
    "EligibilityState",
    "evaluate_prediction_eligibility",
]
