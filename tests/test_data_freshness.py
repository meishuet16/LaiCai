from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    AvailabilityPolicy,
    DataFreshnessAssessment,
    FreshnessPolicy,
    FreshnessReasonCode,
    FreshnessSource,
    FreshnessStatus,
    SourceFreshnessEvidence,
    assess_data_freshness,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def at(day: int) -> datetime:
    return BASE + timedelta(days=day)


def evidence(
    source: str,
    *,
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    available_day: int = 9,
    watermark_day: int = 9,
    complete: bool | None = True,
    connected: bool = True,
    received_day: int | None = None,
    last_sync_day: int | None = 9,
) -> SourceFreshnessEvidence:
    return SourceFreshnessEvidence(
        tenant_id=tenant_id,
        customer_id=customer_id,
        source=source,
        source_available_at=at(available_day) if available_day is not None else None,
        received_at=at(received_day) if received_day is not None else None,
        last_sync_at=at(last_sync_day) if last_sync_day is not None else None,
        watermark_at=at(watermark_day) if watermark_day is not None else None,
        complete=complete,
        connected=connected,
        source_record_refs=(f"ref-{source}",),
    )


def complete_sources() -> list[SourceFreshnessEvidence]:
    return [
        evidence(FreshnessSource.SUBSCRIPTION_LIFECYCLE.value),
        evidence(FreshnessSource.BILLING_EVENTS.value),
        evidence(FreshnessSource.USAGE_COVERAGE.value),
    ]


def test_healthy_sources_are_fresh_and_preserve_cutoff_evidence():
    result = assess_data_freshness("tenant-a", "customer-a", at(10), complete_sources())

    assert result.status is FreshnessStatus.FRESH
    assert result.input_data_as_of == at(9)
    assert result.policy_version == "freshness_v1"
    assert result.source_record_refs == (
        "ref-subscription_lifecycle",
        "ref-billing_events",
        "ref-usage_coverage",
    )


def test_optional_billing_source_can_be_missing_without_blocking_freshness():
    result = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        [
            evidence(FreshnessSource.SUBSCRIPTION_LIFECYCLE.value),
            evidence(FreshnessSource.USAGE_COVERAGE.value),
        ],
    )

    assert result.status is FreshnessStatus.FRESH
    billing = next(
        item for item in result.source_assessments
        if item.source == FreshnessSource.BILLING_EVENTS.value
    )
    assert billing.missing is True
    assert FreshnessReasonCode.OPTIONAL_SOURCE_MISSING in billing.reason_codes


def test_missing_essential_subscription_source_is_unknown():
    result = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        [evidence(FreshnessSource.USAGE_COVERAGE.value)],
    )

    assert result.status is FreshnessStatus.UNKNOWN
    assert FreshnessSource.SUBSCRIPTION_LIFECYCLE.value in result.missing_sources
    assert FreshnessReasonCode.ESSENTIAL_SOURCE_MISSING in result.reason_codes


def test_stale_subscription_source_is_stale():
    sources = complete_sources()
    sources[0] = evidence(
        FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
        available_day=1,
        watermark_day=1,
        last_sync_day=1,
    )

    result = assess_data_freshness("tenant-a", "customer-a", at(10), sources)

    assert result.status is FreshnessStatus.STALE
    subscription = result.source_assessments[0]
    assert subscription.status is FreshnessStatus.STALE
    assert FreshnessReasonCode.SOURCE_STALE in subscription.reason_codes


def test_healthy_usage_coverage_is_fresh_even_without_recent_activity_event():
    result = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        complete_sources(),
    )

    assert result.source_assessments[-1].status is FreshnessStatus.FRESH


def test_missing_freshness_metadata_is_unknown_not_fresh():
    result = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        [
            evidence(
                FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
                available_day=None,
                watermark_day=None,
                last_sync_day=None,
            ),
            evidence(FreshnessSource.USAGE_COVERAGE.value),
        ],
    )

    subscription = result.source_assessments[0]
    assert subscription.status is FreshnessStatus.UNKNOWN
    assert FreshnessReasonCode.SOURCE_METADATA_MISSING in subscription.reason_codes


def test_future_source_metadata_cannot_influence_past_assessment():
    result = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        [
            evidence(
                FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
                available_day=11,
                watermark_day=11,
                last_sync_day=11,
            ),
            evidence(FreshnessSource.USAGE_COVERAGE.value),
        ],
    )

    subscription = result.source_assessments[0]
    assert subscription.status is FreshnessStatus.UNKNOWN
    assert FreshnessReasonCode.FUTURE_METADATA_EXCLUDED in subscription.reason_codes
    assert result.input_data_as_of == at(9)


def test_source_availability_precedence_remains_configurable():
    item = evidence(
        FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
        available_day=11,
        received_day=9,
        watermark_day=9,
        last_sync_day=9,
    )
    conservative = assess_data_freshness(
        "tenant-a", "customer-a", at(10), [item, evidence(FreshnessSource.USAGE_COVERAGE.value)]
    )
    received_only = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        [item, evidence(FreshnessSource.USAGE_COVERAGE.value)],
        policy=FreshnessPolicy(availability_policy=AvailabilityPolicy.RECEIVED_ONLY),
    )

    assert conservative.source_assessments[0].status is FreshnessStatus.UNKNOWN
    assert received_only.source_assessments[0].status is FreshnessStatus.FRESH


def test_scope_mismatched_evidence_cannot_influence_result():
    result = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        [
            evidence(FreshnessSource.SUBSCRIPTION_LIFECYCLE.value, tenant_id="tenant-b"),
            evidence(FreshnessSource.USAGE_COVERAGE.value),
        ],
    )

    subscription = result.source_assessments[0]
    assert subscription.status is FreshnessStatus.UNKNOWN
    assert FreshnessReasonCode.TENANT_SCOPE_MISMATCH in subscription.reason_codes


def test_timezone_naive_cutoff_and_evidence_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        assess_data_freshness("tenant-a", "customer-a", datetime(2026, 10, 1), [])
    with pytest.raises(ValidationError):
        SourceFreshnessEvidence(
            tenant_id="tenant-a",
            customer_id="customer-a",
            source=FreshnessSource.USAGE_COVERAGE.value,
            source_available_at=datetime(2026, 10, 1),
        )


def test_partial_coverage_is_explicitly_reported():
    result = assess_data_freshness(
        "tenant-a",
        "customer-a",
        at(10),
        [
            evidence(FreshnessSource.SUBSCRIPTION_LIFECYCLE.value),
            evidence(FreshnessSource.USAGE_COVERAGE.value, complete=False),
        ],
    )

    assert result.status is FreshnessStatus.PARTIALLY_STALE
    assert result.source_assessments[-1].status is FreshnessStatus.PARTIALLY_STALE
