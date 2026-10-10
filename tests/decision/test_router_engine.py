"""
test_router_engine.py — Unit tests for the routing engine.

Tests every gate in the 5-step routing pipeline (§7.2).
These are pure function tests — no DB, no FastAPI, no external calls.

Run: pytest tests/decision/test_router_engine.py -v
"""

import pytest
from datetime import datetime, timezone

from backend.decision.enums import (
    DataFreshnessStatus, MRRCompleteness, PredictionStatus,
    ReliabilityStatus, RouteEnum,
)
from backend.decision.models import (
    DataFreshnessBlock, MRRRecord, PredictionPayload, ReliabilityBlock,
    RoutingPolicy, UncertaintyBlock,
)
from backend.decision.router_engine import build_route_result, determine_route

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AS_OF = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)

DEFAULT_POLICY = RoutingPolicy(
    policy_version="routing_policy_v1",
    p30_threshold=0.40,
    partially_stale_treatment="human_review",
)


def make_prediction(
    status: PredictionStatus = PredictionStatus.SCORED,
    p7: float = 0.12,
    p14: float = 0.38,
    p30: float = 0.81,
    reliability: ReliabilityStatus = ReliabilityStatus.SUFFICIENT_EVIDENCE,
    freshness: DataFreshnessStatus = DataFreshnessStatus.FRESH,
) -> PredictionPayload:
    return PredictionPayload(
        tenant_id="tenant_abc",
        customer_id="cust_001",
        prediction_id="pred_001",
        prediction_run_id="run_001",
        as_of=AS_OF,
        generated_at=AS_OF,
        status=status,
        p_churn_7d=p7 if status == PredictionStatus.SCORED else None,
        p_churn_14d=p14 if status == PredictionStatus.SCORED else None,
        p_churn_30d=p30 if status == PredictionStatus.SCORED else None,
        feature_version="features_v1",
        model_version="multihorizon_v1",
        calibration_version="calibration_v1",
        label_policy_version="churn_policy_v1",
        reliability=ReliabilityBlock(status=reliability),
        data_freshness=DataFreshnessBlock(
            status=freshness,
            input_data_as_of=AS_OF,
        ),
        uncertainty=UncertaintyBlock(),
    )


def make_mrr(
    mrr_minor: int | None = 120000,
    currency: str = "MYR",
    completeness: MRRCompleteness = MRRCompleteness.COMPLETE,
) -> MRRRecord:
    return MRRRecord(
        tenant_id="tenant_abc",
        customer_id="cust_001",
        mrr_as_of=AS_OF,
        mrr_minor=mrr_minor,
        currency=currency,
        mrr_completeness=completeness,
        subscription_count=1,
    )


# ---------------------------------------------------------------------------
# STEP 1: Non-predictive states
# ---------------------------------------------------------------------------

class TestNonPredictiveStates:
    def test_not_eligible(self):
        pred = make_prediction(status=PredictionStatus.NOT_ELIGIBLE)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.NOT_ELIGIBLE
        assert "no_valid_active_paying_account" in reason

    def test_known_cancellation(self):
        pred = make_prediction(status=PredictionStatus.KNOWN_CANCELLATION)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.KNOWN_CANCELLATION
        assert "cancel_request_known_at_cutoff" in reason


# ---------------------------------------------------------------------------
# STEP 2: HUMAN_REVIEW gates
# ---------------------------------------------------------------------------

class TestHumanReviewGates:
    def test_abstained_routes_to_human_review(self):
        pred = make_prediction(status=PredictionStatus.ABSTAINED)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW
        assert "abstained" in reason

    def test_insufficient_evidence_routes_to_human_review(self):
        pred = make_prediction(reliability=ReliabilityStatus.INSUFFICIENT_EVIDENCE)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW
        assert "insufficient_evidence" in reason

    def test_limited_evidence_routes_to_human_review(self):
        pred = make_prediction(reliability=ReliabilityStatus.LIMITED_EVIDENCE)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW
        assert "limited_evidence" in reason

    def test_stale_data_routes_to_human_review(self):
        pred = make_prediction(freshness=DataFreshnessStatus.STALE)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW
        assert "stale" in reason

    def test_unknown_freshness_routes_to_human_review(self):
        pred = make_prediction(freshness=DataFreshnessStatus.UNKNOWN)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW

    def test_partially_stale_conservative_routes_to_human_review(self):
        pred = make_prediction(freshness=DataFreshnessStatus.PARTIALLY_STALE)
        policy = RoutingPolicy(partially_stale_treatment="human_review")
        route, reason = determine_route(pred, make_mrr(), False, policy)
        assert route == RouteEnum.HUMAN_REVIEW
        assert "partially_stale" in reason

    def test_missing_mrr_record_routes_to_human_review(self):
        """None MRR → HUMAN_REVIEW. Never use 0 as fallback."""
        pred = make_prediction()
        route, reason = determine_route(pred, None, False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW
        assert "mrr_record_unavailable" in reason

    def test_null_mrr_minor_routes_to_human_review(self):
        """mrr_minor=null → HUMAN_REVIEW. Never use 0."""
        pred = make_prediction()
        mrr = make_mrr(mrr_minor=None, completeness=MRRCompleteness.MISSING)
        route, reason = determine_route(pred, mrr, False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW
        assert "missing_mrr_valuation" in reason

    def test_high_risk_does_not_override_limited_evidence(self):
        """
        Critical: p_churn_30d=0.99 must NOT override data inadequacy.
        High risk alone never bypasses the evidence gate.
        """
        pred = make_prediction(p30=0.99, reliability=ReliabilityStatus.LIMITED_EVIDENCE)
        route, _ = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW, (
            "High risk score must not override limited evidence — §7.2"
        )

    def test_high_risk_does_not_override_missing_mrr(self):
        """High risk + missing MRR → still HUMAN_REVIEW."""
        pred = make_prediction(p30=0.99)
        route, _ = determine_route(pred, None, False, DEFAULT_POLICY)
        assert route == RouteEnum.HUMAN_REVIEW


# ---------------------------------------------------------------------------
# STEP 3: Review policy threshold
# ---------------------------------------------------------------------------

class TestReviewThreshold:
    def test_below_threshold_routes_to_observe(self):
        # Use p7=0.10, p14=0.18, p30=0.25 to satisfy monotonicity (p7<=p14<=p30)
        pred = make_prediction(p7=0.10, p14=0.18, p30=0.25)  # below 0.40 threshold
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.OBSERVE
        assert "below_review_policy_threshold" in reason

    def test_exactly_at_threshold_routes_to_priority_review(self):
        pred = make_prediction(p30=0.40)
        route, _ = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.PRIORITY_REVIEW

    def test_above_threshold_routes_to_priority_review(self):
        pred = make_prediction(p30=0.81)
        route, _ = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.PRIORITY_REVIEW


# ---------------------------------------------------------------------------
# STEP 4: Cooldown gate
# ---------------------------------------------------------------------------

class TestCooldownGate:
    def test_cooldown_active_routes_to_observe(self):
        pred = make_prediction(p30=0.81)
        route, reason = determine_route(pred, make_mrr(), True, DEFAULT_POLICY)
        assert route == RouteEnum.OBSERVE
        assert "cooldown" in reason

    def test_cooldown_inactive_routes_to_priority_review(self):
        pred = make_prediction(p30=0.81)
        route, _ = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.PRIORITY_REVIEW


# ---------------------------------------------------------------------------
# STEP 5: Happy path — PRIORITY_REVIEW
# ---------------------------------------------------------------------------

class TestPriorityReview:
    def test_fully_eligible_account_routes_to_priority_review(self):
        pred = make_prediction(p30=0.81)
        route, reason = determine_route(pred, make_mrr(), False, DEFAULT_POLICY)
        assert route == RouteEnum.PRIORITY_REVIEW
        assert "eligible_sufficient_evidence" in reason

    def test_exposure_proxy_computed_correctly(self):
        """exposure_proxy = round(p30 * mrr_minor) = round(0.65 * 120000) = 78000"""
        pred = make_prediction(p7=0.22, p14=0.45, p30=0.65)
        mrr = make_mrr(mrr_minor=120000)
        result = build_route_result(pred, mrr, False, DEFAULT_POLICY)
        assert result.route == RouteEnum.PRIORITY_REVIEW
        assert result.exposure_proxy_30d_minor == 78000
        assert result.currency == "MYR"

    def test_exposure_proxy_null_for_non_priority_routes(self):
        """exposure_proxy must be null for HUMAN_REVIEW routes."""
        pred = make_prediction(reliability=ReliabilityStatus.LIMITED_EVIDENCE)
        result = build_route_result(pred, make_mrr(), False, DEFAULT_POLICY)
        assert result.route == RouteEnum.HUMAN_REVIEW
        assert result.exposure_proxy_30d_minor is None


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------

class TestModelValidation:
    def test_monotonicity_violation_p7_gt_p14_raises(self):
        with pytest.raises(ValueError, match="Monotonicity violated"):
            make_prediction(p7=0.50, p14=0.30, p30=0.81)  # p7 > p14 invalid

    def test_monotonicity_violation_p14_gt_p30_raises(self):
        with pytest.raises(ValueError, match="Monotonicity violated"):
            make_prediction(p7=0.12, p14=0.90, p30=0.50)  # p14 > p30 invalid

    def test_mrr_missing_completeness_with_non_null_mrr_raises(self):
        with pytest.raises(ValueError, match="mrr_completeness=missing requires mrr_minor=null"):
            MRRRecord(
                tenant_id="t",
                customer_id="c",
                mrr_as_of=AS_OF,
                mrr_minor=500,              # non-null with missing completeness — invalid
                currency="MYR",
                mrr_completeness=MRRCompleteness.MISSING,
            )
