from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    AvailabilityPolicy,
    BillingFact,
    InMemoryPointInTimeAdapter,
    SubscriptionFact,
    UsageFact,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


def subscription_fact(
    record_id="sub-start",
    *,
    status="active",
    is_paying=True,
    occurred_days=0,
    effective_days=None,
    available_days=0,
    received_days=0,
    cancellation_requested_at=None,
    event_type="subscription_started",
    tenant_id="tenant-a",
    customer_id="customer-a",
):
    return SubscriptionFact(
        record_id=record_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        source="synthetic",
        subscription_id="subscription-a",
        event_type=event_type,
        status=status,
        is_paying=is_paying,
        occurred_at=at(occurred_days),
        effective_at=at(effective_days) if effective_days is not None else None,
        source_available_at=at(available_days),
        received_at=at(received_days),
        cancellation_requested_at=cancellation_requested_at,
    )


def test_only_matching_tenant_and_customer_facts_are_returned():
    adapter = InMemoryPointInTimeAdapter(
        [
            subscription_fact(),
            subscription_fact(record_id="other-tenant", tenant_id="tenant-b"),
            subscription_fact(record_id="other-customer", customer_id="customer-b"),
        ]
    )

    snapshot = adapter.snapshot_for("tenant-a", "customer-a", at(10))

    assert [fact.record_id for fact in snapshot.subscriptions] == ["sub-start"]
    assert snapshot.tenant_id == "tenant-a"
    assert snapshot.customer_id == "customer-a"


def test_future_event_is_excluded():
    adapter = InMemoryPointInTimeAdapter(
        [subscription_fact(record_id="future", occurred_days=11, available_days=11)]
    )

    snapshot = adapter.snapshot_for("tenant-a", "customer-a", at(10))

    assert not snapshot.subscriptions
    assert snapshot.excluded_record_counts["future_event_or_effective_time"] == 1


def test_late_arriving_event_is_excluded_even_when_occurred_before_cutoff():
    adapter = InMemoryPointInTimeAdapter(
        [subscription_fact(record_id="late", occurred_days=8, available_days=12, received_days=12)]
    )

    snapshot = adapter.snapshot_for("tenant-a", "customer-a", at(10))

    assert not snapshot.subscriptions
    assert snapshot.excluded_record_counts["late_arriving_fact"] == 1


def test_source_availability_takes_precedence_over_earlier_received_time():
    fact = subscription_fact(record_id="source-late", available_days=12, received_days=9)
    snapshot = InMemoryPointInTimeAdapter([fact]).snapshot_for("tenant-a", "customer-a", at(10))

    assert not snapshot.subscriptions
    assert snapshot.excluded_record_counts["late_arriving_fact"] == 1


def test_missing_availability_is_not_substituted_with_occurred_at():
    fact = subscription_fact(record_id="unknown-availability")
    fact = fact.model_copy(update={"source_available_at": None, "received_at": None})

    snapshot = InMemoryPointInTimeAdapter([fact]).snapshot_for("tenant-a", "customer-a", at(10))

    assert not snapshot.subscriptions
    assert snapshot.excluded_record_counts["historical_availability_unknown"] == 1
    assert snapshot.limitations


def test_received_at_can_be_used_only_by_explicit_configured_policy():
    fact = subscription_fact(record_id="received-only")
    fact = fact.model_copy(update={"source_available_at": None, "received_at": at(5)})

    conservative = InMemoryPointInTimeAdapter(
        [fact], availability_policy=AvailabilityPolicy.SOURCE_ONLY
    ).snapshot_for("tenant-a", "customer-a", at(10))
    configured = InMemoryPointInTimeAdapter(
        [fact], availability_policy=AvailabilityPolicy.SOURCE_THEN_RECEIVED
    ).snapshot_for("tenant-a", "customer-a", at(10))

    assert not conservative.subscriptions
    assert [item.record_id for item in configured.subscriptions] == ["received-only"]
    assert configured.availability_basis_by_record["received-only"] == "received_at"


def test_naive_fact_timestamps_are_rejected():
    with pytest.raises(ValidationError):
        SubscriptionFact(
            record_id="naive",
            tenant_id="tenant-a",
            customer_id="customer-a",
            source="billing_db",
            occurred_at=datetime(2026, 10, 1),
            status="active",
            is_paying=True,
        )


def test_naive_cutoff_is_rejected():
    adapter = InMemoryPointInTimeAdapter([subscription_fact()])

    with pytest.raises(ValueError, match="timezone-aware"):
        adapter.snapshot_for("tenant-a", "customer-a", datetime(2026, 10, 10))


def test_fact_provenance_fields_are_preserved():
    usage = UsageFact(
        record_id="usage-1",
        tenant_id="tenant-a",
        customer_id="customer-a",
        source="product_app",
        event_type="session_started",
        occurred_at=at(2),
        source_available_at=at(2),
        received_at=at(3),
    )
    billing = BillingFact(
        record_id="billing-1",
        tenant_id="tenant-a",
        customer_id="customer-a",
        source="billing",
        event_type="payment_failed",
        payment_status="failed",
        occurred_at=at(4),
        source_available_at=at(4),
        received_at=at(4),
    )

    snapshot = InMemoryPointInTimeAdapter([usage, billing]).snapshot_for(
        "tenant-a", "customer-a", at(10)
    )

    assert snapshot.usage_events[0].record_id == "usage-1"
    assert snapshot.usage_events[0].source == "product_app"
    assert snapshot.billing_events[0].payment_status == "failed"
