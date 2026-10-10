"""
router_engine.py — Core routing logic for the Decision Engine.

Converts a prediction payload + MRR record into one of five canonical routes.
Routes are applied in STRICT ORDER — no skipping to financial ranking.

Order (Ref: §7.2):
  1. NOT_ELIGIBLE
  2. KNOWN_CANCELLATION
  3. HUMAN_REVIEW  (multiple triggers — data/evidence quality gates)
  4. PRIORITY_REVIEW vs OBSERVE  (threshold + cooldown)

Critical rules:
  - High risk score ALONE never overrides data inadequacy.
  - Missing MRR → HUMAN_REVIEW, never use 0 as fallback.
  - SHAP values (explanations_by_horizon) are model associations,
    NOT causal action triggers — do not use them in routing logic.
  - Part 3 must NOT rewrite p_churn_* values from the prediction.
"""

from __future__ import annotations
from typing import Optional

from .enums import (
    DataFreshnessStatus, MRRCompleteness, PredictionStatus,
    ReliabilityStatus, RouteEnum,
)
from .models import MRRRecord, PredictionPayload, RoutingPolicy, RouteResult


def determine_route(
    prediction: PredictionPayload,
    mrr: Optional[MRRRecord],
    cooldown_active: bool,
    policy: RoutingPolicy,
) -> tuple[RouteEnum, str]:
    """
    Determine the canonical route for one account prediction.

    Args:
        prediction:      Frozen prediction payload from Member 2.
        mrr:             MRR record from Member 1's account_mrr_as_of view.
                         None means the record could not be fetched at all.
        cooldown_active: True if the account is under a discretionary
                         contact cooldown (caller's responsibility to check).
        policy:          Admin-configured routing thresholds.

    Returns:
        (RouteEnum, reason_string) — the route and a machine-readable reason.

    NOTE: Cooldowns suppress discretionary outreach only.
          They do NOT block mandatory notices or normal support.
    """

    # ------------------------------------------------------------------
    # STEP 1: Non-predictive states — check prediction.status first
    # These short-circuit all further routing.
    # ------------------------------------------------------------------
    if prediction.status == PredictionStatus.NOT_ELIGIBLE:
        return RouteEnum.NOT_ELIGIBLE, "no_valid_active_paying_account"

    if prediction.status == PredictionStatus.KNOWN_CANCELLATION:
        return RouteEnum.KNOWN_CANCELLATION, "cancel_request_known_at_cutoff"

    # ------------------------------------------------------------------
    # STEP 2: HUMAN_REVIEW — evidence/data quality gates
    # ANY one of these triggers investigation routing.
    # High risk score does NOT override these gates.
    # ------------------------------------------------------------------

    # 2a. Abstained — model could not produce a score
    if prediction.status == PredictionStatus.ABSTAINED:
        return RouteEnum.HUMAN_REVIEW, "abstained_insufficient_evidence"

    # 2b. Reliability gate — insufficient evidence
    if prediction.reliability.status == ReliabilityStatus.INSUFFICIENT_EVIDENCE:
        return RouteEnum.HUMAN_REVIEW, "insufficient_evidence"

    # 2c. Reliability gate — limited evidence (prediction possible but weak)
    if prediction.reliability.status == ReliabilityStatus.LIMITED_EVIDENCE:
        return RouteEnum.HUMAN_REVIEW, "limited_evidence_requires_investigation"

    # 2d. Stale data — material outage or late source coverage
    if prediction.data_freshness.status == DataFreshnessStatus.STALE:
        return RouteEnum.HUMAN_REVIEW, "materially_stale_data"

    # 2e. Unknown freshness — treat conservatively
    if prediction.data_freshness.status == DataFreshnessStatus.UNKNOWN:
        return RouteEnum.HUMAN_REVIEW, "unknown_data_freshness"

    # 2f. Partially stale — check policy setting.
    #     Critical billing/subscription staleness prevents ranked recommendations.
    #     MVP: conservative route to HUMAN_REVIEW for any partial staleness.
    #     Future: check stale_sources list against source-importance config.
    if prediction.data_freshness.status == DataFreshnessStatus.PARTIALLY_STALE:
        if policy.partially_stale_treatment == "human_review":
            return RouteEnum.HUMAN_REVIEW, "partially_stale_data_requires_verification"
        # else: "allow" — fall through to financial ranking

    # 2g. Missing MRR — cannot compute exposure proxy for ranking.
    #     NEVER substitute 0; route to investigation.
    if mrr is None:
        return RouteEnum.HUMAN_REVIEW, "mrr_record_unavailable_requires_investigation"

    if mrr.mrr_minor is None or mrr.mrr_completeness == MRRCompleteness.MISSING:
        return RouteEnum.HUMAN_REVIEW, "missing_mrr_valuation_requires_investigation"

    # Guard: p_churn_30d must be non-null for financial ranking (scored status)
    if prediction.p_churn_30d is None:
        return RouteEnum.HUMAN_REVIEW, "missing_p_churn_30d_cannot_rank"

    # ------------------------------------------------------------------
    # STEP 3: Review policy threshold
    # Accounts below the threshold are monitored but not outreached.
    # ------------------------------------------------------------------
    if prediction.p_churn_30d < policy.p30_threshold:
        return RouteEnum.OBSERVE, "below_review_policy_threshold"

    # ------------------------------------------------------------------
    # STEP 4: Cooldown gate
    # Suppress repeated discretionary contact proposals.
    # Does NOT block mandatory notices or support.
    # ------------------------------------------------------------------
    if cooldown_active:
        return RouteEnum.OBSERVE, "discretionary_contact_cooldown_active"

    # ------------------------------------------------------------------
    # STEP 5: PRIORITY_REVIEW
    # All gates passed — eligible for ranked review.
    # ------------------------------------------------------------------
    return RouteEnum.PRIORITY_REVIEW, "eligible_sufficient_evidence_above_threshold"


def build_route_result(
    prediction: PredictionPayload,
    mrr: Optional[MRRRecord],
    cooldown_active: bool,
    policy: RoutingPolicy,
) -> RouteResult:
    """
    Run the routing engine and return a fully populated RouteResult.
    Computes exposure_proxy_30d only for PRIORITY_REVIEW routes.
    """
    route, reason = determine_route(prediction, mrr, cooldown_active, policy)

    exposure_proxy: Optional[int] = None
    as_of_mrr_minor: Optional[int] = None
    currency: Optional[str] = None

    if route == RouteEnum.PRIORITY_REVIEW and mrr is not None and mrr.mrr_minor is not None:
        # exposure_proxy_30d = p30 * mrr_minor, in same minor-unit currency
        # This is a ranking proxy — NOT exact cash loss
        exposure_proxy = round(prediction.p_churn_30d * mrr.mrr_minor)
        as_of_mrr_minor = mrr.mrr_minor
        currency = mrr.currency

    return RouteResult(
        tenant_id=prediction.tenant_id,
        customer_id=prediction.customer_id,
        prediction_id=prediction.prediction_id,
        as_of=prediction.as_of,
        route=route,
        route_reason=reason,
        policy_version=policy.policy_version,
        exposure_proxy_30d_minor=exposure_proxy,
        as_of_mrr_minor=as_of_mrr_minor,
        currency=currency,
        p_churn_30d=prediction.p_churn_30d,
        p_churn_7d=prediction.p_churn_7d,
        cooldown_active=cooldown_active,
    )
