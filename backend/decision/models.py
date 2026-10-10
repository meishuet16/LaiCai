"""
models.py — Pydantic request/response schemas for the Decision Engine.

Input contracts:
  - PredictionPayload  : from Member 2's prediction API (prediction_contract.md)
  - MRRRecord          : from Member 1's account_mrr_as_of view (mrr_contract.md)

Output contracts:
  - RouteResult        : result of routing a single prediction
  - DecisionCase       : a stored decision_cases row
  - CaseListResponse   : GET /v1/decisions/cases response

Ref: RetainIQ_v2_Complete_Requirements.md §4.3, §4.4, §7.2–7.7
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .enums import (
    ActionCode, ActionMode, CaseStatus, DataFreshnessStatus,
    HumanDecisionType, MRRCompleteness, ObservedStatus,
    PredictionStatus, ReliabilityStatus, RouteEnum, ScenarioLabel,
    UncertaintyStatus,
)


# ---------------------------------------------------------------------------
# Prediction input (Member 2 → Member 3)
# Ref: prediction_contract.md, §4.3
# ---------------------------------------------------------------------------

class ReliabilityBlock(BaseModel):
    status: ReliabilityStatus
    reasons: list[str] = Field(default_factory=list)


class DataFreshnessBlock(BaseModel):
    status: DataFreshnessStatus
    input_data_as_of: Optional[datetime] = None
    stale_sources: list[str] = Field(default_factory=list)


class UncertaintyBlock(BaseModel):
    status: UncertaintyStatus = UncertaintyStatus.NOT_QUANTIFIED
    method: str = "none"
    intervals: None = None


class PredictionPayload(BaseModel):
    """
    Immutable prediction snapshot from Member 2.
    Part 3 MUST NOT rewrite or re-derive p_churn_* values.
    """
    tenant_id: str
    customer_id: str
    prediction_id: str
    prediction_run_id: str
    as_of: datetime
    generated_at: datetime
    status: PredictionStatus

    # Calibrated cumulative probabilities — null when not scored
    p_churn_7d: Optional[float] = Field(None, ge=0.0, le=1.0)
    p_churn_14d: Optional[float] = Field(None, ge=0.0, le=1.0)
    p_churn_30d: Optional[float] = Field(None, ge=0.0, le=1.0)

    feature_version: str
    model_version: str
    calibration_version: str
    label_policy_version: str

    reliability: ReliabilityBlock
    data_freshness: DataFreshnessBlock
    uncertainty: UncertaintyBlock = Field(default_factory=UncertaintyBlock)
    explanations_by_horizon: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_probability_monotonicity(self) -> "PredictionPayload":
        """Enforce p7 <= p14 <= p30 when all are present."""
        p7, p14, p30 = self.p_churn_7d, self.p_churn_14d, self.p_churn_30d
        if p7 is not None and p14 is not None and p7 > p14:
            raise ValueError(f"Monotonicity violated: p_churn_7d ({p7}) > p_churn_14d ({p14})")
        if p14 is not None and p30 is not None and p14 > p30:
            raise ValueError(f"Monotonicity violated: p_churn_14d ({p14}) > p_churn_30d ({p30})")
        return self

    @model_validator(mode="after")
    def check_scored_has_probabilities(self) -> "PredictionPayload":
        """Scored predictions must have non-null probabilities."""
        if self.status == PredictionStatus.SCORED:
            if self.p_churn_30d is None:
                raise ValueError("status=scored requires non-null p_churn_30d")
        return self


# ---------------------------------------------------------------------------
# MRR input (Member 1 → Member 3)
# Ref: mrr_contract.md, §5.5
# ---------------------------------------------------------------------------

class MRRRecord(BaseModel):
    """
    Point-in-time MRR for one account, from Member 1's account_mrr_as_of view.
    mrr_minor is in integer minor units (e.g. 120000 = RM 1,200.00).
    NEVER use mrr_minor=0 as a fallback for missing MRR.
    """
    tenant_id: str
    customer_id: str
    mrr_as_of: datetime
    mrr_minor: Optional[int] = Field(None, description="Null if missing — never 0")
    currency: str = Field(..., description="ISO-4217 code e.g. MYR, USD")
    mrr_basis_version: str = "mrr_policy_v1"
    subscription_count: int = 0
    mrr_completeness: MRRCompleteness
    mrr_components: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def missing_completeness_implies_null_mrr(self) -> "MRRRecord":
        """mrr_completeness=missing MUST have mrr_minor=null per mrr_contract.md §4."""
        if self.mrr_completeness == MRRCompleteness.MISSING and self.mrr_minor is not None:
            raise ValueError("mrr_completeness=missing requires mrr_minor=null")
        return self


# ---------------------------------------------------------------------------
# Routing policy configuration (admin-set, not user-submitted)
# ---------------------------------------------------------------------------

class RoutingPolicy(BaseModel):
    """
    Admin-configured thresholds for the routing engine.
    Thresholds are selected on development data — never hardcoded from spec examples.
    """
    policy_version: str = "routing_policy_v1"
    p30_threshold: float = Field(
        0.40,
        ge=0.0,
        le=1.0,
        description="Minimum p_churn_30d to qualify for PRIORITY_REVIEW"
    )
    # partially_stale treatment: "human_review" (conservative) or "allow" (permissive)
    partially_stale_treatment: str = "human_review"


# ---------------------------------------------------------------------------
# Routing output
# ---------------------------------------------------------------------------

class RouteResult(BaseModel):
    """Result of the routing engine for one account."""
    tenant_id: str
    customer_id: str
    prediction_id: str
    as_of: datetime
    route: RouteEnum
    route_reason: str
    policy_version: str

    # Populated only for PRIORITY_REVIEW
    exposure_proxy_30d_minor: Optional[int] = None  # p30 * mrr_minor, rounded
    as_of_mrr_minor: Optional[int] = None
    currency: Optional[str] = None
    p_churn_30d: Optional[float] = None
    p_churn_7d: Optional[float] = None
    cooldown_active: bool = False


# ---------------------------------------------------------------------------
# Decision case (stored in decision_cases table)
# ---------------------------------------------------------------------------

class DecisionCase(BaseModel):
    """A stored decision_cases row. Returned in list responses."""
    case_id: UUID
    tenant_id: str
    customer_id: str
    prediction_id: str
    as_of: datetime
    route: RouteEnum
    route_reason: str
    rank: Optional[int] = None  # position in PRIORITY_REVIEW top-K
    exposure_proxy_30d_minor: Optional[int] = None
    as_of_mrr_minor: Optional[int] = None
    currency: Optional[str] = None
    mrr_completeness: Optional[MRRCompleteness] = None
    p_churn_30d: Optional[float] = None
    p_churn_7d: Optional[float] = None
    p_churn_14d: Optional[float] = None
    reliability_status: str
    data_freshness_status: str
    policy_version: str
    cooldown_active: bool
    case_status: CaseStatus
    opened_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    """Response for GET /v1/decisions/cases."""
    tenant_id: str
    as_of: datetime
    policy_version: str
    k_slots_configured: int
    k_slots_remaining: int
    currency: Optional[str] = None
    cases: list[DecisionCase] = Field(default_factory=list)
    human_review_queue: list[DecisionCase] = Field(default_factory=list)
    observe_queue_count: int = 0
    excluded: list[dict[str, str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ROI card (§7.6)
# ---------------------------------------------------------------------------

class ROICard(BaseModel):
    """
    One-month break-even scenario card.
    ALWAYS labeled SCENARIO_ONLY — never claim real retention savings.
    Ref: §7.6
    """
    case_id: str
    as_of_mrr_minor: Optional[int]
    currency: str
    p_churn_30d: Optional[float]
    contribution_margin: float
    action_cost_minor: int
    assumed_abs_reduction: Optional[float]

    # Computed outputs
    contribution_value_minor: Optional[int] = None
    break_even_abs_reduction_pp: Optional[float] = None   # percentage points
    break_even_share_of_baseline_pct: Optional[float] = None  # percent
    scenario_gross_value_minor: Optional[int] = None
    scenario_net_value_minor: Optional[int] = None
    scenario_roi_pct: Optional[float] = None
    break_even_achievable: Optional[bool] = None

    scenario_label: ScenarioLabel = ScenarioLabel.SCENARIO_ONLY
    unavailable_reason: Optional[str] = None   # set when output is N/A
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Human approval request / response (Phase 3 — stub types here)
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    proposal_id: str
    decision_type: HumanDecisionType
    reason: str
    actor: str
    assigned_owner: Optional[str] = None
    modified_action_code: Optional[ActionCode] = None  # for MODIFY


class ApprovalResponse(BaseModel):
    human_decision_id: UUID
    case_id: str
    case_status: CaseStatus
    original_proposal_action: ActionCode
    final_action: ActionCode
    decision_type: HumanDecisionType
    actor: str
    decided_at: datetime
    assigned_owner: Optional[str] = None
    budget_remaining_minor: Optional[int] = None
    staff_minutes_remaining: Optional[int] = None
    follow_up_anchor: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Outcome observation request / response (Phase 3 — stub types here)
# ---------------------------------------------------------------------------

class OutcomeObservationRequest(BaseModel):
    follow_up_anchor: datetime
    horizon_days: int = Field(..., ge=7, le=30)
    observed_status: ObservedStatus
    source_ref: str
    observation_coverage: str  # "complete" | "partial" | "unknown"


class OutcomeObservationResponse(BaseModel):
    observation_id: UUID
    case_id: str
    horizon_days: int
    observed_status: ObservedStatus
    observation_coverage: str
    observed_at: datetime
    note: str = "active_status_is_not_proof_of_retention_effectiveness"
