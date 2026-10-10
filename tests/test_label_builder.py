from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    ChurnLabelBuilder,
    InMemoryLifecycleOutcomeAdapter,
    LabelReasonCode,
    LabelStatus,
    OutcomeObservation,
    PredictionOutput,
    PredictionStatus,
    Reliability,
    ReliabilityStatus,
    DataFreshness,
    FreshnessStatus,
    Uncertainty,
    FeatureSnapshot,
    FeatureValues,
    FeatureQuality,
    PersonalBaselineStatus,
    UsageCoverageStatus,
    SubscriptionFact,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)
AS_OF = BASE


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


def active_fact(
    record_id: str = "sub-start",
    *,
    subscription_id: str = "sub-a",
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    day: int = 0,
    event_type: str = "subscription_started",
    cancellation_requested_at: datetime | None = None,
) -> SubscriptionFact:
    return SubscriptionFact(
        record_id=record_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        source="synthetic_lifecycle",
        subscription_id=subscription_id,
        event_type=event_type,
        status="active",
        is_paying=True,
        occurred_at=at(day),
        source_available_at=at(day),
        received_at=at(day),
        cancellation_requested_at=cancellation_requested_at,
    )


def churn_fact(
    day: int,
    *,
    event_type: str = "cancellation_effective",
    status: str = "cancelled",
    record_id: str | None = None,
    subscription_id: str = "sub-a",
    available_day: int | None = None,
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
) -> SubscriptionFact:
    available = day if available_day is None else available_day
    return SubscriptionFact(
        record_id=record_id or f"churn-{day}-{event_type}",
        tenant_id=tenant_id,
        customer_id=customer_id,
        source="synthetic_lifecycle",
        subscription_id=subscription_id,
        event_type=event_type,
        status=status,
        is_paying=False,
        occurred_at=at(day),
        effective_at=at(day),
        source_available_at=at(available),
        received_at=at(available),
    )


def observation(
    through_day: int,
    *,
    available_day: int = 30,
    observation_id: str = "lifecycle-observation",
    subscription_id: str | None = None,
    complete: bool = True,
) -> OutcomeObservation:
    return OutcomeObservation(
        observation_id=observation_id,
        source="synthetic_lifecycle",
        observed_from=AS_OF,
        observed_through=at(through_day),
        available_at=at(available_day),
        subscription_id=subscription_id,
        complete=complete,
    )


def labels(
    facts,
    observations=(),
    *,
    evaluation_day: int = 30,
    eligibility_policy=None,
):
    adapter = InMemoryLifecycleOutcomeAdapter(facts, observations=observations)
    return ChurnLabelBuilder(
        adapter,
        eligibility_policy=eligibility_policy,
    ).build_labels("tenant-a", "customer-a", AS_OF, at(evaluation_day))


def by_horizon(result):
    return {item.horizon_days: item for item in result}


def test_churn_within_seven_days_is_positive_for_all_horizons():
    result = by_horizon(labels([active_fact(), churn_fact(5)], [observation(30)]))

    assert [result[h].label for h in (7, 14, 30)] == [1, 1, 1]
    assert all(item.label_status is LabelStatus.POSITIVE for item in result.values())


def test_churn_at_day_ten_is_negative_then_positive():
    result = by_horizon(labels([active_fact(), churn_fact(10)], [observation(30)]))

    assert result[7].label == 0
    assert result[14].label == 1
    assert result[30].label == 1


def test_churn_at_day_twenty_is_negative_for_short_horizons():
    result = by_horizon(labels([active_fact(), churn_fact(20)], [observation(30)]))

    assert result[7].label == 0
    assert result[14].label == 0
    assert result[30].label == 1


def test_no_churn_with_full_observation_is_negative_for_all_horizons():
    result = by_horizon(labels([active_fact()], [observation(30)]))

    assert [result[h].label for h in (7, 14, 30)] == [0, 0, 0]
    assert all(item.reason_codes == (LabelReasonCode.FULL_HORIZON_OBSERVED_NO_CHURN,) for item in result.values())


def test_observation_ending_at_day_ten_only_matures_seven_day_negative():
    result = by_horizon(
        labels(
            [active_fact()],
            [observation(10, available_day=10)],
            evaluation_day=10,
        )
    )

    assert result[7].label == 0
    assert result[14].label is None
    assert result[30].label is None
    assert result[14].label_status is LabelStatus.UNKNOWN


def test_missing_outcome_coverage_is_unknown_not_negative():
    result = by_horizon(labels([active_fact()], []))

    assert all(item.label is None for item in result.values())
    assert all(item.label_status is LabelStatus.UNKNOWN for item in result.values())


def test_payment_failure_without_termination_is_not_churn():
    payment_failure = active_fact(
        record_id="payment-failure",
        event_type="payment_failed",
        day=5,
    )
    result = by_horizon(labels([active_fact(), payment_failure], [observation(30)]))

    assert [result[h].label for h in (7, 14, 30)] == [0, 0, 0]


def test_known_cancellation_before_prediction_cutoff_excludes_all_labels():
    request = active_fact(
        record_id="cancel-request",
        day=-1,
        event_type="cancellation_requested",
        cancellation_requested_at=at(-1),
    )
    result = by_horizon(labels([active_fact(), request], [observation(30)]))

    assert all(item.label is None for item in result.values())
    assert all(item.label_status is LabelStatus.EXCLUDED for item in result.values())
    assert all(
        item.reason_codes == (LabelReasonCode.KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF,)
        for item in result.values()
    )


def test_cancellation_request_after_as_of_does_not_exclude_earlier_cutoff():
    request = active_fact(
        record_id="future-cancel-request",
        day=5,
        event_type="cancellation_requested",
        cancellation_requested_at=at(5),
    )
    result = by_horizon(
        labels([active_fact(), request, churn_fact(10)], [observation(30)])
    )

    assert result[7].label == 0
    assert result[14].label == 1


def test_churn_exactly_at_horizon_boundary_is_positive():
    result = by_horizon(labels([active_fact(), churn_fact(7)], [observation(30)]))

    assert result[7].label == 1
    assert result[7].churn_effective_at == at(7)


def test_churn_exactly_at_as_of_is_not_a_prospective_positive_and_excludes_account():
    result = by_horizon(
        labels([active_fact(day=-1), churn_fact(0)], [observation(30)])
    )

    assert all(item.label is None for item in result.values())
    assert all(item.label_status is LabelStatus.EXCLUDED for item in result.values())
    assert all(
        item.reason_codes == (LabelReasonCode.ALREADY_TERMINATED_AT_PREDICTION_CUTOFF,)
        for item in result.values()
    )


def test_future_outcome_unavailable_at_evaluation_cutoff_does_not_create_label():
    result = by_horizon(
        labels(
            [active_fact(), churn_fact(10, available_day=20)],
            [observation(15, available_day=15)],
            evaluation_day=15,
        )
    )

    assert result[7].label is None
    assert result[14].label is None
    assert result[30].label is None
    assert result[14].reason_codes == (
        LabelReasonCode.OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF,
    )


def test_late_arriving_churn_becomes_positive_only_after_availability():
    facts = [active_fact(), churn_fact(10, available_day=20)]
    adapter = InMemoryLifecycleOutcomeAdapter(facts, observations=[observation(30)])
    builder = ChurnLabelBuilder(adapter)

    before = by_horizon(builder.build_labels("tenant-a", "customer-a", AS_OF, at(15)))
    after = by_horizon(builder.build_labels("tenant-a", "customer-a", AS_OF, at(20)))

    assert before[14].label is None
    assert after[14].label == 1


def test_already_terminated_account_at_prediction_cutoff_is_excluded():
    result = by_horizon(
        labels([active_fact(day=-2), churn_fact(-1)], [observation(30)])
    )

    assert all(item.label_status is LabelStatus.EXCLUDED for item in result.values())


def test_unresolved_multi_subscription_policy_is_unsupported():
    facts = [
        active_fact(record_id="sub-a-start", subscription_id="sub-a"),
        active_fact(record_id="sub-b-start", subscription_id="sub-b"),
    ]
    result = by_horizon(labels(facts, [observation(30)]))

    assert all(item.label is None for item in result.values())
    assert all(item.label_status is LabelStatus.UNSUPPORTED for item in result.values())
    assert all(
        item.reason_codes == (LabelReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY,)
        for item in result.values()
    )


def test_cross_tenant_and_customer_outcomes_cannot_leak():
    facts = [
        active_fact(),
        churn_fact(5, tenant_id="tenant-b"),
        churn_fact(5, customer_id="customer-b"),
    ]
    result = by_horizon(labels(facts, [observation(30)]))

    assert all(item.label == 0 for item in result.values())


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValidationError):
        SubscriptionFact(
            record_id="naive",
            tenant_id="tenant-a",
            customer_id="customer-a",
            source="synthetic",
            subscription_id="sub-a",
            event_type="subscription_started",
            status="active",
            is_paying=True,
            occurred_at=datetime(2026, 10, 1),
            source_available_at=at(0),
            received_at=at(0),
        )
    with pytest.raises(ValidationError):
        OutcomeObservation(
            observation_id="naive",
            source="synthetic",
            observed_from=datetime(2026, 10, 1),
            observed_through=at(7),
            available_at=at(7),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        ChurnLabelBuilder(
            InMemoryLifecycleOutcomeAdapter([active_fact()])
        ).build_labels("tenant-a", "customer-a", AS_OF, datetime(2026, 10, 31))


def test_labels_are_reproducible_and_policy_versioned():
    from retainiq_prediction import LabelBuilderConfig

    adapter = InMemoryLifecycleOutcomeAdapter(
        [active_fact(), churn_fact(10)], observations=[observation(30)]
    )
    config = LabelBuilderConfig(label_policy_version="labels_test_v2")
    builder = ChurnLabelBuilder(adapter, config=config)
    first = builder.build_labels("tenant-a", "customer-a", AS_OF, at(30))
    second = builder.build_labels("tenant-a", "customer-a", AS_OF, at(30))

    assert [item.model_dump(mode="json") for item in first] == [
        item.model_dump(mode="json") for item in second
    ]
    assert all(item.label_policy_version == "labels_test_v2" for item in first)


def test_conflicting_lifecycle_evidence_is_not_definitive():
    result = by_horizon(
        labels(
            [
                active_fact(),
                churn_fact(10, event_type="cancellation_effective", status="cancelled"),
                churn_fact(
                    10,
                    event_type="involuntary_termination",
                    status="terminated",
                    record_id="conflict",
                ),
            ],
            [observation(30)],
        )
    )

    assert result[14].label is None
    assert result[14].label_status is LabelStatus.UNKNOWN
    assert result[14].reason_codes == (
        LabelReasonCode.CONFLICTING_LIFECYCLE_EVIDENCE,
    )


def test_label_builder_does_not_mutate_feature_or_prediction_contract_objects():
    feature_snapshot = FeatureSnapshot(
        tenant_id="tenant-a",
        customer_id="customer-a",
        as_of=AS_OF,
        feature_version="features_test",
        data_cutoff_at=AS_OF,
        feature_values=FeatureValues(
            personal_baseline_availability_status=PersonalBaselineStatus.UNAVAILABLE
        ),
        data_quality=FeatureQuality(
            usage_coverage_status=UsageCoverageStatus.UNKNOWN,
            personal_baseline_status=PersonalBaselineStatus.UNAVAILABLE,
            baseline_weeks_requested=4,
        ),
    )
    prediction = PredictionOutput(
        tenant_id="tenant-a",
        customer_id="customer-a",
        prediction_id="prediction-1",
        prediction_run_id="run-1",
        as_of=AS_OF,
        generated_at=AS_OF,
        status=PredictionStatus.ABSTAINED,
        feature_version="features_test",
        model_version="model_none",
        calibration_version="calibration_none",
        label_policy_version="labels_test",
        reliability=Reliability(status=ReliabilityStatus.INSUFFICIENT_EVIDENCE),
        data_freshness=DataFreshness(status=FreshnessStatus.UNKNOWN),
        uncertainty=Uncertainty(),
    )
    feature_before = feature_snapshot.model_dump(mode="json")
    prediction_before = prediction.model_dump(mode="json")

    labels([active_fact()], [observation(30)])

    assert feature_snapshot.model_dump(mode="json") == feature_before
    assert prediction.model_dump(mode="json") == prediction_before
