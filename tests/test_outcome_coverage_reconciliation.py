"""Regression tests for Member 1 lifecycle facts and segmented coverage."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction.eligibility import EligibilityPolicy
from retainiq_prediction.label_builder import (
    ChurnLabelBuilder,
    InMemoryLifecycleOutcomeAdapter,
    LabelBuilderConfig,
    LabelStatus,
    LifecycleOutcomeSnapshot,
    OutcomeObservation,
)
from retainiq_prediction.point_in_time import (
    AvailabilityPolicy,
    InMemoryPointInTimeAdapter,
    SubscriptionFact,
)


UTC = timezone.utc
AS_OF = datetime(2025, 1, 1, tzinfo=UTC)


def at(days: int) -> datetime:
    return AS_OF + timedelta(days=days)


def fact(
    record_id: str,
    *,
    day: int,
    event_type: str,
    status: str,
    is_paying: bool,
    available_day: int | None = None,
    subscription_id: str = "sub-a",
) -> SubscriptionFact:
    available = day if available_day is None else available_day
    return SubscriptionFact(
        record_id=record_id,
        tenant_id="tenant-synthetic",
        customer_id="account-synthetic",
        source="synthetic-subscription",
        subscription_id=subscription_id,
        event_type=event_type,
        status=status,
        is_paying=is_paying,
        occurred_at=at(day),
        effective_at=at(day) if day > 0 else None,
        source_available_at=at(available),
        received_at=at(available),
    )


def coverage(
    observation_id: str,
    start: int,
    end: int,
    *,
    available: int = 38,
    category: str = "subscription",
    status: str = "complete",
    completeness: float = 1.0,
    subscription_id: str | None = None,
) -> OutcomeObservation:
    return OutcomeObservation(
        observation_id=observation_id,
        source="synthetic-coverage",
        source_category=category,
        observed_from=at(start),
        observed_through=at(end),
        available_at=at(available),
        subscription_id=subscription_id,
        complete=status == "complete" and completeness == 1.0,
        coverage_status=status,
        coverage_completeness=completeness,
        observation_policy_version="synthetic-coverage-v1",
    )


def build_labels(facts, observations, *, evaluation_day=38, policy=None):
    adapter = InMemoryLifecycleOutcomeAdapter(
        facts,
        observations=observations,
        availability_policy=AvailabilityPolicy.SOURCE_THEN_RECEIVED,
    )
    builder = ChurnLabelBuilder(
        adapter,
        config=LabelBuilderConfig(label_policy_version="effective-account-churn-v1.2"),
        eligibility_policy=policy
        or EligibilityPolicy(
            account_churn_policy="effective-account-churn-v1.2-synthetic-only"
        ),
    )
    return builder.build_labels(
        "tenant-synthetic",
        "account-synthetic",
        AS_OF,
        at(evaluation_day),
        label_generated_at=at(evaluation_day),
    )


def test_member1_ended_status_maps_to_positive_without_feature_time_leakage():
    start = fact(
        "start", day=0, event_type="subscription_created",
        status="active", is_paying=True,
    )
    ended = fact(
        "effective-end", day=5, event_type="voluntary_cancellation",
        status="ended", is_paying=False,
    )
    point_in_time = InMemoryPointInTimeAdapter([start, ended]).snapshot_for(
        "tenant-synthetic", "account-synthetic", AS_OF
    )
    labels = build_labels([start, ended], [coverage("coverage", 0, 38)])

    assert [item.record_id for item in point_in_time.subscriptions] == ["start"]
    assert [item.label for item in labels] == [1, 1, 1]
    assert all(item.label_status is LabelStatus.POSITIVE for item in labels)
    assert all(item.churn_effective_at == at(5) for item in labels)


def test_adjacent_complete_subscription_intervals_mature_negative_labels():
    start = fact(
        "start", day=0, event_type="subscription_created",
        status="active", is_paying=True,
    )
    intervals = [
        coverage("week-1", 0, 7),
        coverage("week-2", 7, 14),
        coverage("week-3", 14, 21),
        coverage("week-4", 21, 28),
        coverage("week-5", 28, 38),
    ]

    labels = build_labels([start], intervals)

    assert [item.label for item in labels] == [0, 0, 0]
    assert all(item.label_status is LabelStatus.NEGATIVE for item in labels)


def test_a_gap_in_segmented_coverage_keeps_uncovered_horizons_unknown():
    start = fact(
        "start", day=0, event_type="subscription_created",
        status="active", is_paying=True,
    )
    intervals = [
        coverage("through-day-8", 0, 8),
        coverage("after-gap", 9, 38),
    ]

    labels = build_labels([start], intervals)

    assert labels[0].label == 0
    assert labels[1].label is None
    assert labels[2].label is None
    assert labels[1].label_status is LabelStatus.UNKNOWN
    assert labels[2].label_status is LabelStatus.UNKNOWN


def test_usage_coverage_cannot_prove_subscription_retention():
    start = fact(
        "start", day=0, event_type="subscription_created",
        status="active", is_paying=True,
    )
    labels = build_labels(
        [start],
        [coverage("usage-only", 0, 38, category="usage")],
    )

    assert all(item.label is None for item in labels)
    assert all(item.label_status is LabelStatus.UNKNOWN for item in labels)


def test_partial_or_outage_intervals_do_not_join_complete_lifecycle_coverage():
    start = fact(
        "start", day=0, event_type="subscription_created",
        status="active", is_paying=True,
    )
    intervals = [
        coverage("complete-left", 0, 14),
        coverage(
            "outage-middle", 14, 21, status="outage", completeness=0.0
        ),
        coverage("complete-right", 21, 38),
    ]

    labels = build_labels([start], intervals)

    assert labels[0].label == 0
    assert labels[1].label == 0
    assert labels[2].label is None
    assert labels[2].label_status is LabelStatus.UNKNOWN


def test_subscription_specific_coverage_must_cover_every_active_entitlement():
    start_a = fact(
        "start-a", day=0, event_type="subscription_created",
        status="active", is_paying=True, subscription_id="sub-a",
    )
    start_b = fact(
        "start-b", day=0, event_type="subscription_created",
        status="active", is_paying=True, subscription_id="sub-b",
    )
    only_a = [
        coverage("a-left", 0, 20, subscription_id="sub-a"),
        coverage("a-right", 20, 38, subscription_id="sub-a"),
    ]

    labels = build_labels([start_a, start_b], only_a)

    assert all(item.label is None for item in labels)
    assert all(item.label_status is LabelStatus.UNKNOWN for item in labels)


def test_outcome_observation_rejects_status_completeness_contradiction():
    with pytest.raises(ValidationError, match="complete must agree"):
        OutcomeObservation(
            observation_id="bad-coverage",
            source="synthetic-coverage",
            observed_from=at(0),
            observed_through=at(38),
            available_at=at(38),
            complete=True,
            coverage_status="partial",
            coverage_completeness=0.6,
        )


def test_prediction_and_outcome_cutoffs_remain_distinct_and_timezone_aware():
    start = fact(
        "start", day=0, event_type="subscription_created",
        status="active", is_paying=True,
    )
    ended = fact(
        "end", day=5, event_type="voluntary_cancellation",
        status="ended", is_paying=False,
    )
    prediction = InMemoryPointInTimeAdapter([start, ended]).snapshot_for(
        "tenant-synthetic", "account-synthetic", AS_OF
    )
    outcome = LifecycleOutcomeSnapshot(
        tenant_id="tenant-synthetic",
        customer_id="account-synthetic",
        prediction_as_of=AS_OF,
        evaluation_as_of=at(38),
        subscription_facts=(start, ended),
        observations=(coverage("coverage", 0, 38),),
    )

    assert prediction.as_of == AS_OF
    assert outcome.prediction_as_of == AS_OF
    assert outcome.evaluation_as_of == at(38)
    assert ended not in prediction.subscriptions
    assert ended in outcome.subscription_facts


def test_reactivation_keeps_first_effective_churn_episode_as_positive():
    lifecycle = [
        fact("start", day=0, event_type="subscription_created", status="active", is_paying=True),
        fact("first-end", day=5, event_type="voluntary_cancellation", status="ended", is_paying=False),
        fact("reactivate", day=10, event_type="subscription_reactivated", status="active", is_paying=True),
        fact("second-end", day=15, event_type="involuntary_termination", status="ended", is_paying=False),
    ]

    labels = build_labels(lifecycle, [coverage("full-history", 0, 38)])

    assert [item.label for item in labels] == [1, 1, 1]
    assert all(item.label_status is LabelStatus.POSITIVE for item in labels)
    assert all(item.churn_effective_at == at(5) for item in labels)
    assert all("first-end" in item.source_evidence_refs for item in labels)


def test_multi_subscription_churn_effective_time_is_final_entitlement_loss():
    lifecycle = [
        fact("start-a", day=0, event_type="subscription_created", status="active", is_paying=True, subscription_id="sub-a"),
        fact("start-b", day=0, event_type="subscription_created", status="active", is_paying=True, subscription_id="sub-b"),
        fact("end-a", day=5, event_type="voluntary_cancellation", status="ended", is_paying=False, subscription_id="sub-a"),
        fact("end-b", day=10, event_type="non_renewal", status="ended", is_paying=False, subscription_id="sub-b"),
    ]

    labels = build_labels(lifecycle, [coverage("full-history", 0, 38)])

    assert [item.label for item in labels] == [0, 1, 1]
    assert labels[0].label_status is LabelStatus.NEGATIVE
    assert labels[1].churn_effective_at == at(10)
    assert labels[2].churn_effective_at == at(10)
    assert {"end-a", "end-b"}.issubset(set(labels[1].source_evidence_refs))


def test_reactivated_entitlement_prevents_false_final_account_churn():
    lifecycle = [
        fact("start-a", day=0, event_type="subscription_created", status="active", is_paying=True, subscription_id="sub-a"),
        fact("start-b", day=0, event_type="subscription_created", status="active", is_paying=True, subscription_id="sub-b"),
        fact("end-a", day=5, event_type="voluntary_cancellation", status="ended", is_paying=False, subscription_id="sub-a"),
        fact("reactivate-a", day=7, event_type="subscription_reactivated", status="active", is_paying=True, subscription_id="sub-a"),
        fact("end-b", day=10, event_type="non_renewal", status="ended", is_paying=False, subscription_id="sub-b"),
    ]

    labels = build_labels(lifecycle, [coverage("full-history", 0, 38)])

    assert [item.label for item in labels] == [0, 0, 0]
    assert all(item.label_status is LabelStatus.NEGATIVE for item in labels)
