from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction import (
    DatasetProvenance,
    DatasetStatus,
    HistoricalDatasetAdapter,
    ProvenanceEvidenceType,
    assess_dataset_readiness,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def ts(days: int) -> str:
    return (BASE + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def synthetic_provenance(evidence_type=ProvenanceEvidenceType.SYNTHETIC):
    return DatasetProvenance(
        source_name="synthetic readiness fixture",
        license_or_authorization="test-only synthetic fixture",
        evidence_type=evidence_type,
        availability_assumption="Synthetic fixture timestamps are treated as source availability for structural testing only.",
    )


def valid_adapter(*, observed_through=30, include_availability=True):
    usage_events = []
    for index, day in enumerate((0, 7, 14, 21, 28, 35)):
        row = {
            "tenant_id": "tenant_fixture",
            "customer_id": "customer_fixture",
            "event_id": f"usage_{index}",
            "occurred_at": ts(day),
        }
        if include_availability:
            row["received_at"] = ts(day)
        usage_events.append(row)

    subscription_events = []
    for index, day in enumerate((0, 5)):
        row = {
            "tenant_id": "tenant_fixture",
            "customer_id": "customer_fixture",
            "event_id": f"subscription_{index}",
            "event_type": "subscription_started" if index == 0 else "plan_changed",
            "occurred_at": ts(day),
        }
        if include_availability:
            row["received_at"] = ts(day)
        subscription_events.append(row)

    return HistoricalDatasetAdapter(
        accounts=[{"tenant_id": "tenant_fixture", "customer_id": "customer_fixture"}],
        subscriptions=[
            {
                "tenant_id": "tenant_fixture",
                "customer_id": "customer_fixture",
                "subscription_id": "subscription_fixture",
                "started_at": ts(0),
                "status": "active",
            }
        ],
        subscription_events=subscription_events,
        usage_events=usage_events,
        outcomes=[
            {
                "tenant_id": "tenant_fixture",
                "customer_id": "customer_fixture",
                "outcome_id": "outcome_positive",
                "as_of": ts(0),
                "label_observed_through": ts(30),
                "churn_effective_at": ts(5),
            },
            {
                "tenant_id": "tenant_fixture",
                "customer_id": "customer_fixture",
                "outcome_id": "outcome_negative",
                "as_of": ts(0),
                "label_observed_through": ts(observed_through),
                "churn_effective_at": None,
            },
        ],
    )


def test_no_dataset_is_blocked():
    report = assess_dataset_readiness(None)

    assert report.status is DatasetStatus.BLOCKED
    assert report.eligible_for_genuine_training is False
    assert "No historical dataset was supplied." in report.blockers


def test_static_churn_table_without_temporal_evidence_is_blocked():
    adapter = HistoricalDatasetAdapter(
        accounts=[
            {"tenant_id": "tenant_fixture", "customer_id": "customer_1", "Churn": "Yes"},
            {"tenant_id": "tenant_fixture", "customer_id": "customer_2", "Churn": "No"},
        ]
    )

    report = assess_dataset_readiness(adapter)

    assert report.status is DatasetStatus.BLOCKED
    assert not report.supported_horizons
    assert any("usage or billing" in blocker for blocker in report.blockers)
    assert any("churn-effective" in blocker for blocker in report.blockers)


def test_missing_churn_effective_timestamps_is_blocked():
    adapter = valid_adapter()
    adapter = HistoricalDatasetAdapter(
        accounts=adapter.accounts,
        subscriptions=adapter.subscriptions,
        subscription_events=adapter.subscription_events,
        usage_events=adapter.usage_events,
        outcomes=[{**row, "churn_effective_at": None} for row in adapter.outcomes],
    )

    report = assess_dataset_readiness(adapter, provenance=synthetic_provenance())

    assert report.status is DatasetStatus.BLOCKED
    assert any("churn-effective" in blocker for blocker in report.blockers)


def test_invalid_timestamp_is_reported_as_blocking_quality_issue():
    adapter = valid_adapter()
    adapter = HistoricalDatasetAdapter(
        accounts=adapter.accounts,
        subscriptions=adapter.subscriptions,
        subscription_events=adapter.subscription_events,
        usage_events=[{**adapter.usage_events[0], "occurred_at": "not-a-timestamp"}],
        outcomes=adapter.outcomes,
    )

    report = assess_dataset_readiness(adapter, provenance=synthetic_provenance())

    assert report.status is DatasetStatus.BLOCKED
    assert any("usage_events.occurred_at" in issue for issue in report.data_quality_issues)
    assert any("invalid value(s)" in issue for issue in report.data_quality_issues)


def test_missing_source_availability_is_reported_without_inventing_it():
    report = assess_dataset_readiness(
        valid_adapter(include_availability=False), provenance=synthetic_provenance()
    )

    assert report.status is DatasetStatus.PARTIAL
    assert 7 in report.supported_horizons
    assert 14 in report.supported_horizons
    assert 30 in report.supported_horizons
    assert any("availability" in issue for issue in report.unsupported_or_unverified)


def test_incomplete_30_day_coverage_does_not_establish_30_day_readiness():
    report = assess_dataset_readiness(
        valid_adapter(observed_through=14), provenance=synthetic_provenance()
    )

    assert report.status is DatasetStatus.PARTIAL
    assert 7 in report.supported_horizons
    assert 14 in report.supported_horizons
    assert 30 not in report.supported_horizons
    assert any("30-day" in issue for issue in report.unsupported_or_unverified)


def test_structurally_valid_synthetic_longitudinal_fixture_is_not_real_readiness():
    report = assess_dataset_readiness(
        valid_adapter(), provenance=synthetic_provenance()
    )

    assert report.status is DatasetStatus.PARTIAL
    assert report.supported_horizons == [7, 14, 30]
    assert report.eligible_for_genuine_training is False
    assert any("provenance" in issue for issue in report.unsupported_or_unverified)


def test_duplicate_event_records_are_reported():
    adapter = valid_adapter()
    duplicate_usage = [*adapter.usage_events, adapter.usage_events[0]]
    adapter = HistoricalDatasetAdapter(
        accounts=adapter.accounts,
        subscriptions=adapter.subscriptions,
        subscription_events=adapter.subscription_events,
        usage_events=duplicate_usage,
        outcomes=adapter.outcomes,
    )

    report = assess_dataset_readiness(adapter, provenance=synthetic_provenance())

    assert report.status is DatasetStatus.BLOCKED
    assert any("Duplicate records" in issue for issue in report.data_quality_issues)
