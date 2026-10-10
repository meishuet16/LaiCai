"""Structural tests for the historical preparation path (synthetic fixtures only).

Tenant authorization, adapter identity, feature semantics, and the broader
label/split/reliability edge matrix are additionally exercised by
test_sqlite_data_adapter.py, test_feature_builder.py, test_label_builder.py,
test_temporal_splits.py, test_reliability.py, and test_data_freshness.py.
"""

from datetime import date, datetime, time, timedelta, timezone
import gzip
import json

import pytest

from retainiq_prediction.eligibility import EligibilityPolicy
from retainiq_prediction.historical_dataset_preparation import (
    _CachedLifecycleOutcomeAdapter,
    _write_jsonl_gzip,
    build_cutoff_schedule,
    label_evaluation_cutoff,
)
from retainiq_prediction.label_builder import (
    ChurnLabelBuilder,
    LabelBuilderConfig,
    LabelReasonCode,
    LabelStatus,
    LifecycleOutcomeSnapshot,
    OutcomeObservation,
)
from retainiq_prediction.point_in_time import InMemoryPointInTimeAdapter, SubscriptionFact


UTC = timezone.utc
AS_OF = datetime(2025, 1, 1, tzinfo=UTC)


def at(days: int) -> datetime:
    return AS_OF + timedelta(days=days)


def subscription_fact(
    record_id: str,
    *,
    sub_id: str,
    day: int,
    status: str,
    event_type: str,
    is_paying: bool,
    effective_day: int | None = None,
    available_day: int | None = None,
) -> SubscriptionFact:
    available = day if available_day is None else available_day
    return SubscriptionFact(
        record_id=record_id,
        tenant_id="tenant-synthetic",
        customer_id="account-synthetic",
        source="synthetic_lifecycle",
        subscription_id=sub_id,
        event_type=event_type,
        status=status,
        is_paying=is_paying,
        occurred_at=at(day),
        effective_at=at(effective_day) if effective_day is not None else None,
        source_available_at=at(available),
        received_at=at(available),
    )


def test_weekly_cutoff_schedule_is_utc_deterministic_and_stage_separated():
    dataset = {
        "start_date": "2024-10-01",
        "end_date": "2025-12-01",
        "end_date_exclusive": True,
    }
    splits = {
        "sampling_policy": {
            "frequency": "weekly",
            "cutoff_utc": "Monday 12:00:00Z",
            "warmup_days": 63,
        },
        "label_maturity_lag_days": 8,
        "stages": {
            "train": {"cutoff_start": "2024-12-01", "cutoff_end": "2024-12-22", "mature_before": "2025-02-01"},
            "development": {"cutoff_start": "2025-03-01", "cutoff_end": "2025-03-16", "mature_before": "2025-05-01"},
            "calibration": {"cutoff_start": "2025-06-01", "cutoff_end": "2025-06-15", "mature_before": "2025-08-01"},
            "untouched_test": {"cutoff_start": "2025-09-01", "cutoff_end": "2025-09-16", "mature_before": "2025-11-01"},
        },
    }
    first = build_cutoff_schedule(dataset, splits)
    second = build_cutoff_schedule(dataset, splits)
    assert first == second
    assert [item.as_of.date() for item in first] == [
        date(2024, 12, 9), date(2024, 12, 16),
        date(2025, 3, 3), date(2025, 3, 10),
        date(2025, 6, 2), date(2025, 6, 9),
        date(2025, 9, 1), date(2025, 9, 8), date(2025, 9, 15),
    ]
    assert all(item.as_of.tzinfo is UTC and item.as_of.hour == 12 for item in first)


def test_weekly_schedule_rejects_unknown_or_overlapping_stage_contracts():
    dataset = {"start_date": "2024-10-01", "end_date": "2025-12-01", "end_date_exclusive": True}
    splits = {
        "sampling_policy": {"frequency": "daily", "cutoff_utc": "Monday 12:00:00Z", "warmup_days": 63},
        "stages": {},
    }
    with pytest.raises(ValueError, match="weekly"):
        build_cutoff_schedule(dataset, splits)


def test_label_evaluation_cutoff_respects_horizon_maturity_and_stage_freeze():
    assert label_evaluation_cutoff(AS_OF, 7, at(40), 8) == at(15)
    assert label_evaluation_cutoff(AS_OF, 30, at(20), 8) == at(20)
    with pytest.raises(ValueError, match="timezone-aware"):
        label_evaluation_cutoff(datetime(2025, 1, 1), 7, at(50), 8)


def test_late_effective_churn_known_after_stage_freeze_stays_unknown():
    start = subscription_fact(
        "start-a", sub_id="sub-a", day=0, status="active",
        event_type="subscription_started", is_paying=True,
    )
    late_end = subscription_fact(
        "end-a", sub_id="sub-a", day=5, effective_day=5, available_day=20,
        status="cancelled", event_type="cancellation_effective", is_paying=False,
    )
    base = LifecycleOutcomeSnapshot(
        tenant_id="tenant-synthetic",
        customer_id="account-synthetic",
        prediction_as_of=AS_OF,
        evaluation_as_of=at(30),
        subscription_facts=(start, late_end),
        observations=(OutcomeObservation(
            observation_id="future-coverage",
            source="synthetic_lifecycle",
            observed_from=AS_OF,
            observed_through=at(30),
            available_at=at(10),
            complete=True,
        ),),
    )
    prediction = InMemoryPointInTimeAdapter([start]).snapshot_for(
        "tenant-synthetic", "account-synthetic", AS_OF
    )
    cached = _CachedLifecycleOutcomeAdapter(
        prediction, base, horizon_days=7, maturity_lag_days=8
    )
    label = next(item for item in ChurnLabelBuilder(
        cached,
        config=LabelBuilderConfig(label_policy_version="synthetic-v1.2"),
        eligibility_policy=EligibilityPolicy(account_churn_policy="all_subscriptions_end"),
    ).build_labels(
        "tenant-synthetic", "account-synthetic", AS_OF, at(15), label_generated_at=at(15)
    ) if item.horizon_days == 7)
    assert label.label is None
    assert label.label_status is LabelStatus.UNKNOWN
    assert LabelReasonCode.OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF in label.reason_codes


def test_full_horizon_negative_waits_for_horizon_to_elapsed():
    start = subscription_fact(
        "start-a", sub_id="sub-a", day=0, status="active",
        event_type="subscription_started", is_paying=True,
    )
    base = LifecycleOutcomeSnapshot(
        tenant_id="tenant-synthetic",
        customer_id="account-synthetic",
        prediction_as_of=AS_OF,
        evaluation_as_of=at(30),
        subscription_facts=(start,),
        observations=(OutcomeObservation(
            observation_id="synthetic-coverage",
            source="synthetic_lifecycle",
            observed_from=AS_OF,
            observed_through=at(30),
            available_at=at(10),
            complete=True,
        ),),
    )
    prediction = InMemoryPointInTimeAdapter([start]).snapshot_for(
        "tenant-synthetic", "account-synthetic", AS_OF
    )
    cached = _CachedLifecycleOutcomeAdapter(
        prediction, base, horizon_days=30, maturity_lag_days=8
    )
    result = ChurnLabelBuilder(
        cached,
        config=LabelBuilderConfig(label_policy_version="synthetic-v1.2"),
        eligibility_policy=EligibilityPolicy(account_churn_policy="all_subscriptions_end"),
    ).build_labels(
        "tenant-synthetic", "account-synthetic", AS_OF, at(20), label_generated_at=at(20)
    )
    label_30 = next(item for item in result if item.horizon_days == 30)
    assert label_30.label is None
    assert label_30.label_status is LabelStatus.UNKNOWN


def test_synthetic_final_entitlement_loss_requires_all_cutoff_subscriptions_to_end():
    sub_a = subscription_fact(
        "start-a", sub_id="sub-a", day=0, status="active",
        event_type="subscription_started", is_paying=True,
    )
    sub_b = subscription_fact(
        "start-b", sub_id="sub-b", day=0, status="active",
        event_type="subscription_started", is_paying=True,
    )
    partial_end = subscription_fact(
        "end-a", sub_id="sub-a", day=5, effective_day=5, status="cancelled",
        event_type="cancellation_effective", is_paying=False,
    )
    complete_coverage = OutcomeObservation(
        observation_id="synthetic-coverage",
        source="synthetic_lifecycle",
        observed_from=AS_OF,
        observed_through=at(30),
        available_at=at(30),
        complete=True,
    )
    adapter = InMemoryPointInTimeAdapter([sub_a, sub_b])
    prediction = adapter.snapshot_for("tenant-synthetic", "account-synthetic", AS_OF)
    outcome = LifecycleOutcomeSnapshot(
        tenant_id="tenant-synthetic", customer_id="account-synthetic",
        prediction_as_of=AS_OF, evaluation_as_of=at(38),
        subscription_facts=(sub_a, sub_b, partial_end),
        observations=(complete_coverage,),
    )

    class OutcomeAdapter:
        def prediction_snapshot_for(self, *args):
            return prediction

        def outcome_snapshot_for(self, *args):
            return outcome.model_copy(update={"evaluation_as_of": args[3]})

    labels = ChurnLabelBuilder(
        OutcomeAdapter(),
        config=LabelBuilderConfig(label_policy_version="effective-account-churn-v1.2"),
        eligibility_policy=EligibilityPolicy(account_churn_policy="effective-account-churn-v1.2-synthetic-only"),
    ).build_labels(
        "tenant-synthetic", "account-synthetic", AS_OF, at(38), label_generated_at=at(38)
    )
    assert all(label.label == 0 for label in labels)
    assert all(label.label_status is LabelStatus.NEGATIVE for label in labels)


def test_deterministic_gzip_artifact_has_stable_checksum(tmp_path):
    rows = [{"b": 2, "a": 1}, {"snapshot": "synthetic", "value": None}]
    first_path, second_path = tmp_path / "first.jsonl.gz", tmp_path / "second.jsonl.gz"
    first = _write_jsonl_gzip(first_path, rows)
    second = _write_jsonl_gzip(second_path, rows)
    assert first["sha256"] == second["sha256"]
    assert first["records"] == second["records"] == 2
    with gzip.open(first_path, "rt", encoding="utf-8") as stream:
        decoded = [json.loads(line) for line in stream]
    assert decoded == rows
