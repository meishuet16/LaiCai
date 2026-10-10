from datetime import datetime, timedelta, timezone

from retainiq_prediction import (
    BillingFact,
    EligibilityReasonCode,
    EligibilityState,
    InMemoryPointInTimeAdapter,
    SubscriptionFact,
    evaluate_prediction_eligibility,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


def sub(
    record_id,
    *,
    subscription_id="subscription-a",
    status="active",
    is_paying=True,
    occurred_days=0,
    effective_days=None,
    available_days=0,
    event_type="subscription_started",
    cancellation_requested_at=None,
    tenant_id="tenant-a",
    customer_id="customer-a",
):
    return SubscriptionFact(
        record_id=record_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        source="synthetic",
        subscription_id=subscription_id,
        event_type=event_type,
        status=status,
        is_paying=is_paying,
        occurred_at=at(occurred_days),
        effective_at=at(effective_days) if effective_days is not None else None,
        source_available_at=at(available_days),
        received_at=at(available_days),
        cancellation_requested_at=cancellation_requested_at,
    )


def result_for(facts, cutoff_days=10, **kwargs):
    snapshot = InMemoryPointInTimeAdapter(facts).snapshot_for(
        "tenant-a", "customer-a", at(cutoff_days)
    )
    return evaluate_prediction_eligibility(snapshot, **kwargs)


def test_normal_active_customer_is_eligible():
    result = result_for([sub("start")])

    assert result.state is EligibilityState.ELIGIBLE
    assert result.canonical_prediction_status() is None
    assert EligibilityReasonCode.ACTIVE_PAYING_SUBSCRIPTION in result.reason_codes


def test_cancellation_known_at_cutoff_is_not_prospectively_scored():
    result = result_for(
        [
            sub("start"),
            sub(
                "cancel-request",
                event_type="cancellation_requested",
                occurred_days=5,
                effective_days=5,
                available_days=5,
                cancellation_requested_at=at(5),
            ),
        ]
    )

    assert result.state is EligibilityState.KNOWN_CANCELLATION
    assert result.canonical_prediction_status().value == "known_cancellation"


def test_cancellation_requested_after_cutoff_does_not_change_earlier_eligibility():
    result = result_for(
        [
            sub("start"),
            sub(
                "future-cancel",
                event_type="cancellation_requested",
                occurred_days=12,
                effective_days=12,
                available_days=12,
                cancellation_requested_at=at(12),
            ),
        ]
    )

    assert result.state is EligibilityState.ELIGIBLE


def test_cancellation_before_cutoff_but_received_after_cutoff_does_not_leak_retroactively():
    result = result_for(
        [
            sub("start"),
            sub(
                "late-cancel",
                event_type="cancellation_requested",
                occurred_days=5,
                effective_days=5,
                available_days=12,
                cancellation_requested_at=at(5),
            ),
        ]
    )

    assert result.state is EligibilityState.ELIGIBLE


def test_confirmed_terminated_customer_is_not_eligible():
    result = result_for(
        [
            sub("start"),
            sub(
                "terminated",
                status="terminated",
                is_paying=False,
                occurred_days=5,
                effective_days=5,
                available_days=5,
                event_type="subscription_terminated",
            ),
        ]
    )

    assert result.state is EligibilityState.NOT_ELIGIBLE
    assert EligibilityReasonCode.TERMINATED_BEFORE_CUTOFF in result.reason_codes


def test_failed_payment_alone_does_not_equal_churn():
    payment_failure = BillingFact(
        record_id="payment-failure",
        tenant_id="tenant-a",
        customer_id="customer-a",
        source="billing",
        event_type="payment_failed",
        payment_status="failed",
        occurred_at=at(5),
        source_available_at=at(5),
        received_at=at(5),
    )
    snapshot = InMemoryPointInTimeAdapter([sub("start"), payment_failure]).snapshot_for(
        "tenant-a", "customer-a", at(10)
    )

    result = evaluate_prediction_eligibility(snapshot)

    assert result.state is EligibilityState.ELIGIBLE


def test_missing_subscription_evidence_is_insufficient():
    result = result_for([])

    assert result.state is EligibilityState.INSUFFICIENT_DATA
    assert EligibilityReasonCode.MISSING_SUBSCRIPTION_HISTORY in result.reason_codes


def test_ambiguous_multiple_active_subscriptions_requires_explicit_policy():
    result = result_for(
        [
            sub("start-a", subscription_id="subscription-a"),
            sub("start-b", subscription_id="subscription-b"),
        ]
    )

    assert result.state is EligibilityState.INSUFFICIENT_DATA
    assert EligibilityReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY in result.reason_codes


def test_multiple_active_subscriptions_can_be_explicitly_configured():
    from retainiq_prediction import EligibilityPolicy

    result = result_for(
        [
            sub("start-a", subscription_id="subscription-a"),
            sub("start-b", subscription_id="subscription-b"),
        ],
        policy=EligibilityPolicy(account_churn_policy="explicit_team_policy"),
    )

    assert result.state is EligibilityState.ELIGIBLE


def test_unknown_availability_causes_insufficient_subscription_evidence():
    fact = sub("unknown-availability").model_copy(
        update={"source_available_at": None, "received_at": None}
    )
    result = result_for([fact])

    assert result.state is EligibilityState.INSUFFICIENT_DATA
    assert EligibilityReasonCode.HISTORICAL_AVAILABILITY_LIMITED in result.reason_codes


def test_current_future_termination_cannot_overwrite_historical_cutoff_state():
    result = result_for(
        [
            sub("start"),
            sub(
                "future-termination",
                status="terminated",
                is_paying=False,
                occurred_days=0,
                effective_days=20,
                available_days=20,
                event_type="subscription_terminated",
            )
        ],
        cutoff_days=10,
    )

    assert result.state is EligibilityState.ELIGIBLE
