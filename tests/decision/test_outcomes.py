"""
test_outcomes.py — Unit tests for outcome observation tracking at 7/14/30d horizons (§7.7).

Verifies:
  - Allowed horizons (7, 14, 30 days) and rejection of invalid horizons
  - Observation coverage values ('complete', 'partial', 'unknown')
  - Strict guardrail note: 'active_is_not_proof_of_retention_effectiveness'
  - Unknown status rule: unknown/incomplete observation is NOT a successful retention outcome
"""

from datetime import datetime, timezone
import pytest

from backend.decision.enums import ObservedStatus
from backend.decision.models import OutcomeObservationRequest
from backend.decision.outcomes import OutcomeError, record_outcome_observation


def test_valid_7d_active_observation():
    req = OutcomeObservationRequest(
        follow_up_anchor=datetime(2026, 10, 10, 9, 0, 0, tzinfo=timezone.utc),
        horizon_days=7,
        observed_status=ObservedStatus.ACTIVE,
        source_ref="subscriptions.cust_002",
        observation_coverage="complete",
    )

    resp, event = record_outcome_observation(case_id="case_002", request=req)

    assert resp.case_id == "case_002"
    assert resp.horizon_days == 7
    assert resp.observed_status == ObservedStatus.ACTIVE
    assert resp.observation_coverage == "complete"
    assert resp.note == "active_is_not_proof_of_retention_effectiveness"
    assert event.event_type == "OUTCOME_OBSERVED"


def test_valid_30d_churned_observation():
    req = OutcomeObservationRequest(
        follow_up_anchor=datetime(2026, 10, 10, 9, 0, 0, tzinfo=timezone.utc),
        horizon_days=30,
        observed_status=ObservedStatus.CHURNED,
        source_ref="subscriptions.cust_002",
        observation_coverage="complete",
    )

    resp, event = record_outcome_observation(case_id="case_002", request=req)

    assert resp.horizon_days == 30
    assert resp.observed_status == ObservedStatus.CHURNED


def test_unknown_status_notes_incomplete_outcome():
    """Spec §7.7: Unknown/incomplete observation is not a successful retention outcome."""
    req = OutcomeObservationRequest(
        follow_up_anchor=datetime(2026, 10, 10, 9, 0, 0, tzinfo=timezone.utc),
        horizon_days=14,
        observed_status=ObservedStatus.UNKNOWN,
        source_ref="billing_export",
        observation_coverage="unknown",
    )

    resp, _ = record_outcome_observation(case_id="case_002", request=req)

    assert resp.observed_status == ObservedStatus.UNKNOWN
    assert "not_a_successful_retention_outcome" in resp.note


def test_invalid_horizon_raises_error():
    """Only 7, 14, 30 day horizons are allowed."""
    with pytest.raises(Exception):  # pydantic ge/le or domain
        OutcomeObservationRequest(
            follow_up_anchor=datetime(2026, 10, 10, 9, 0, 0, tzinfo=timezone.utc),
            horizon_days=5,  # Invalid
            observed_status=ObservedStatus.ACTIVE,
            source_ref="test",
            observation_coverage="complete",
        )


def test_invalid_coverage_raises_error():
    req = OutcomeObservationRequest(
        follow_up_anchor=datetime(2026, 10, 10, 9, 0, 0, tzinfo=timezone.utc),
        horizon_days=7,
        observed_status=ObservedStatus.ACTIVE,
        source_ref="test",
        observation_coverage="invalid_coverage",
    )

    with pytest.raises(OutcomeError, match="observation_coverage must be one of"):
        record_outcome_observation(case_id="case_002", request=req)
