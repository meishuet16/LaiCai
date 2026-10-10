"""Current Member 1/2 policy observations and explicitly proposed contracts.

The test-only ProposedHeartbeat and aggregate fixtures below are
CONTRACT_PROPOSAL doubles, not Member 1 production APIs.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction import (
    EligibilityPolicy,
    EligibilityState,
    FreshnessSource,
    FreshnessStatus,
    InMemoryPointInTimeAdapter,
    SourceFreshnessEvidence,
    SubscriptionFact,
    assess_data_freshness,
    evaluate_prediction_eligibility,
)


UTC = timezone.utc
BASE = datetime(2026, 1, 1, tzinfo=UTC)
AS_OF = BASE + timedelta(days=20)
TENANT = "tenant-contract-fixture"
ACCOUNT = "account-contract-fixture"


def at(day: int) -> datetime:
    return BASE + timedelta(days=day)


def sub(
    record_id: str,
    *,
    subscription_id: str = "sub-a",
    day: int = 0,
    status: str = "active",
    paying: bool = True,
    event_type: str = "subscription_started",
    cancellation_day: int | None = None,
) -> SubscriptionFact:
    return SubscriptionFact(
        record_id=record_id,
        tenant_id=TENANT,
        customer_id=ACCOUNT,
        source="synthetic-contract-fixture",
        subscription_id=subscription_id,
        event_type=event_type,
        status=status,
        is_paying=paying,
        occurred_at=at(day),
        effective_at=at(day) if day else None,
        source_available_at=at(day),
        received_at=at(day),
        cancellation_requested_at=(
            at(cancellation_day) if cancellation_day is not None else None
        ),
    )


def eligibility(*facts: SubscriptionFact):
    snapshot = InMemoryPointInTimeAdapter(facts).snapshot_for(
        TENANT, ACCOUNT, AS_OF
    )
    # This is the explicit Synthetic SaaS v1.2 adapter policy, not an adopted
    # real-customer multi-subscription policy.
    policy = EligibilityPolicy(
        active_statuses=frozenset({"active", "past_due", "pending_cancel"}),
        terminal_statuses=frozenset(
            {"ended", "cancelled", "terminated", "expired"}
        ),
        account_churn_policy="effective-account-churn-v1.2-synthetic-only",
    )
    return evaluate_prediction_eligibility(snapshot, policy=policy)


def test_single_active_subscription_without_request_is_eligible():
    assert eligibility(sub("start")).state is EligibilityState.ELIGIBLE


def test_single_pending_cancellation_is_known_cancellation():
    result = eligibility(
        sub("start"),
        sub(
            "request", day=10, status="pending_cancel",
            event_type="cancellation_requested", cancellation_day=10,
        ),
    )
    assert result.state is EligibilityState.KNOWN_CANCELLATION


def test_two_active_one_pending_cancellation_uses_current_member2_any_rule():
    result = eligibility(
        sub("start-a", subscription_id="sub-a"),
        sub("start-b", subscription_id="sub-b"),
        sub(
            "request-a", subscription_id="sub-a", day=10,
            status="pending_cancel", event_type="cancellation_requested",
            cancellation_day=10,
        ),
    )
    assert result.state is EligibilityState.KNOWN_CANCELLATION
    # Member 1's current all-active rule is covered by its existing
    # test_data_foundation::test_partial_subscription_cancellation_keeps_account_eligible.


def test_two_active_all_pending_is_known_cancellation():
    result = eligibility(
        sub("start-a", subscription_id="sub-a"),
        sub("start-b", subscription_id="sub-b"),
        sub(
            "request-a", subscription_id="sub-a", day=10,
            status="pending_cancel", event_type="cancellation_requested",
            cancellation_day=10,
        ),
        sub(
            "request-b", subscription_id="sub-b", day=11,
            status="pending_cancel", event_type="cancellation_requested",
            cancellation_day=11,
        ),
    )
    assert result.state is EligibilityState.KNOWN_CANCELLATION


def test_ended_subscription_without_request_does_not_end_remaining_account():
    result = eligibility(
        sub("start-a", subscription_id="sub-a"),
        sub(
            "ended-a", subscription_id="sub-a", day=10,
            status="ended", paying=False, event_type="subscription_cancelled_effective",
        ),
        sub("start-b", subscription_id="sub-b"),
    )
    assert result.state is EligibilityState.ELIGIBLE


def test_request_on_ended_subscription_still_routes_member2_known_today():
    result = eligibility(
        sub("start-a", subscription_id="sub-a"),
        sub(
            "request-a", subscription_id="sub-a", day=5,
            status="pending_cancel", event_type="cancellation_requested",
            cancellation_day=5,
        ),
        sub(
            "ended-a", subscription_id="sub-a", day=10,
            status="ended", paying=False, event_type="subscription_cancelled_effective",
        ),
        sub("start-b", subscription_id="sub-b"),
    )
    assert result.state is EligibilityState.KNOWN_CANCELLATION


def test_member2_current_scan_does_not_clear_a_reversed_request():
    result = eligibility(
        sub("start"),
        sub(
            "request", day=5, status="pending_cancel",
            event_type="cancellation_requested", cancellation_day=5,
        ),
        sub(
            "reversal", day=10, status="active", event_type="subscription_updated",
        ),
    )
    assert result.state is EligibilityState.KNOWN_CANCELLATION


def test_future_cancellation_does_not_change_earlier_cutoff():
    result = eligibility(
        sub("start"),
        sub(
            "future-request", day=25, status="pending_cancel",
            event_type="cancellation_requested", cancellation_day=25,
        ),
    )
    assert result.state is EligibilityState.ELIGIBLE


def test_final_entitlement_loss_is_not_eligible_at_that_cutoff():
    result = eligibility(
        sub("start"),
        sub(
            "end", day=10, status="ended", paying=False,
            event_type="subscription_cancelled_effective",
        ),
    )
    assert result.state is EligibilityState.NOT_ELIGIBLE


def test_absent_heartbeat_is_unknown_not_fresh():
    result = assess_data_freshness(TENANT, ACCOUNT, AS_OF, evidence=[])
    assert result.status is FreshnessStatus.UNKNOWN
    lifecycle = next(
        item for item in result.source_assessments
        if item.source == FreshnessSource.SUBSCRIPTION_LIFECYCLE.value
    )
    assert lifecycle.missing is True


def test_current_source_outage_signal_is_stale_not_fresh():
    item = SourceFreshnessEvidence(
        tenant_id=TENANT,
        customer_id=ACCOUNT,
        source=FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
        source_available_at=at(19),
        received_at=at(19),
        last_sync_at=at(19),
        watermark_at=at(19),
        connected=False,
    )
    result = assess_data_freshness(TENANT, ACCOUNT, AS_OF, [item])
    source = next(x for x in result.source_assessments if x.source == item.source)
    assert source.status is FreshnessStatus.STALE


@dataclass(frozen=True)
class ProposedHeartbeat:
    """CONTRACT_PROPOSAL double only; no Member 1 API implements this type."""

    tenant_id: str
    source: str
    category: str
    observed_at: datetime
    source_available_at: datetime | None
    received_at: datetime
    status: str
    last_successful_sync_at: datetime | None
    observed_through: datetime | None
    expected_cadence: timedelta | None
    policy_version: str
    provenance: str


def test_contract_proposal_healthy_heartbeat_has_distinct_times_and_provenance():
    heartbeat = ProposedHeartbeat(
        tenant_id=TENANT,
        source="source-fixture",
        category="subscription",
        observed_at=at(19),
        source_available_at=at(19),
        received_at=at(19),
        status="healthy",
        last_successful_sync_at=at(19),
        observed_through=at(19),
        expected_cadence=timedelta(hours=1),
        policy_version="source-health-contract-proposal-v1",
        provenance="synthetic contract fixture; not a live health record",
    )
    assert heartbeat.status == "healthy"
    assert heartbeat.observed_through <= AS_OF
    assert heartbeat.source_available_at <= AS_OF
    assert "not a live" in heartbeat.provenance


def test_contract_proposal_unknown_aggregate_diagnostics_are_not_zero():
    # CONTRACT_PROPOSAL only: no production aggregate diagnostic endpoint exists.
    report = {
        "statistics_status": "unavailable",
        "events_examined": None,
        "excluded_by_occurrence_cutoff": None,
        "excluded_by_availability_cutoff": None,
    }
    assert report["statistics_status"] == "unavailable"
    assert report["events_examined"] is None
    assert report["excluded_by_availability_cutoff"] is None


@pytest.mark.parametrize(
    "positive_rows,positive_accounts,expected",
    [(13, 13, False), (59, 17, False), (50, 20, True)],
)
def test_contract_proposal_stage_support_fixture_applies_row_and_account_minima(
    positive_rows, positive_accounts, expected
):
    # CONTRACT_PROPOSAL/report arithmetic fixture, not a production readiness API.
    assert (positive_rows >= 50 and positive_accounts >= 20) is expected
