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
    reliability_status: Optional[str] = None
    data_freshness_status: Optional[str] = None
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
# Phase 2: Action Proposal & Customer Facts Models (§7.4, §7.5)
# ---------------------------------------------------------------------------

class SupportingFactRef(BaseModel):
    """Reference to an underlying data row (e.g. usage_events, billing_events)."""
    table: str
    id: str
    description: str


class ActionProposal(BaseModel):
    """
    An executable or human-reviewable proposed action for a decision case.
    Must include supporting fact references — never fabricated.
    """
    proposal_id: str
    case_id: str
    customer_id: str
    action_code: ActionCode
    catalogue_version: str = "action_catalog_v1"
    mode: ActionMode = ActionMode.OPERATIONAL
    eligibility_reason: str
    supporting_fact_refs: list[SupportingFactRef] = Field(default_factory=list)
    estimated_cost_minor: int = 0
    currency: str = "MYR"
    estimated_staff_minutes: int = 0
    cooldown_days: Optional[int] = None
    approval_role: str = "retention_agent"


class DisabledAction(BaseModel):
    """An action catalog entry that cannot produce live executable proposals."""
    action_code: ActionCode
    mode: ActionMode
    reason: str


class CaseProposalsResponse(BaseModel):
    """Response schema for GET /v1/decisions/cases/{case_id}/proposals."""
    case_id: str
    customer_id: str
    proposals: list[ActionProposal] = Field(default_factory=list)
    disabled_actions: list[DisabledAction] = Field(default_factory=list)


class CustomerFacts(BaseModel):
    """
    Point-in-time observed facts for an account at cutoff as_of.
    Used for candidate action generation without resorting to SHAP causal attribution.
    """
    tenant_id: str
    customer_id: str
    as_of: datetime

    # Usage observations (Part 1 usage_events)
    has_usage_deviation: bool = False
    usage_event_id: Optional[str] = None
    usage_deviation_detail: Optional[str] = None

    # Billing observations (Part 1 billing_events)
    has_failed_billing: bool = False
    billing_event_id: Optional[str] = None
    billing_detail: Optional[str] = None

    # Feature / onboarding observations (Part 1 feature events)
    has_feature_gap: bool = False
    feature_event_id: Optional[str] = None
    feature_gap_detail: Optional[str] = None

    # Evidence and data quality flags
    data_quality_issues: list[str] = Field(default_factory=list)
    is_evidence_insufficient: bool = False

    # Account contraindications
    contradictory_status: bool = False
    has_open_action: bool = False
    active_cooldown_actions: list[ActionCode] = Field(default_factory=list)


class BudgetConfigRecord(BaseModel):
    """Admin-configured reviewer capacity and budget caps (§7.5)."""
    tenant_id: str
    currency: str = "MYR"
    policy_period: str = "daily"  # "daily" | "weekly"
    k_slots: int = 10
    staff_minutes_cap: int = 480
    monetary_budget_minor: int = 100000


# ---------------------------------------------------------------------------
# Human approval request / response (Phase 3 — stub types here)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Human approval request / response (Phase 3 — §7.5, §7.7)
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    proposal_id: str
    decision_type: HumanDecisionType
    reason: str
    actor: str
    assigned_owner: Optional[str] = None
    modified_action_code: Optional[ActionCode] = None  # for MODIFY
    override_applied: bool = False
    override_reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    human_decision_id: str
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
    follow_up_due_at: Optional[dict[str, str]] = None


# ---------------------------------------------------------------------------
# Case history (audit trail — §7.7)
# ---------------------------------------------------------------------------

class HistoryEvent(BaseModel):
    event_id: str
    case_id: str
    event_type: str  # CASE_OPENED, PROPOSAL_GENERATED, HUMAN_DECISION, CASE_STATUS_CHANGED, OUTCOME_OBSERVED
    occurred_at: datetime
    actor: str
    details: dict[str, Any] = Field(default_factory=dict)


class CaseHistoryResponse(BaseModel):
    case_id: str
    events: list[HistoryEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Outcome observation request / response (Phase 3 — §7.7)
# ---------------------------------------------------------------------------

class OutcomeObservationRequest(BaseModel):
    follow_up_anchor: datetime
    horizon_days: int = Field(..., ge=7, le=30)
    observed_status: ObservedStatus
    source_ref: str
    observation_coverage: str  # "complete" | "partial" | "unknown"


class OutcomeObservationResponse(BaseModel):
    observation_id: str
    case_id: str
    horizon_days: int
    observed_status: ObservedStatus
    observation_coverage: str
    observed_at: datetime
    note: str = "active_is_not_proof_of_retention_effectiveness"


# ---------------------------------------------------------------------------
# Decision-quality evaluation models (Phase 3 — §7.8)
# ---------------------------------------------------------------------------

class EvaluationCohortAccount(BaseModel):
    customer_id: str
    as_of_mrr_minor: int
    p_churn_30d: float
    p_churn_7d: float = 0.0
    case_opened_at: Optional[datetime] = None
    reliability_status: str = "sufficient_evidence"
    cooldown_active: bool = False
    actually_churned_30d: bool


class EvaluationResponse(BaseModel):
    strategy: str  # "A" | "B" | "C"
    strategy_description: str
    currency: str
    as_of: datetime
    k_slots: int
    revenue_captured_at_k: Optional[float] = None
    subsequently_churned_mrr_identified_minor: Optional[int] = None
    total_churned_mrr_cohort_minor: Optional[int] = None
    recall_at_k: Optional[float] = None
    revenue_captured_label: str = "Subsequently Churned MRR Identified@K"
    evaluation_label: str = "historical_identification_coverage — NOT saved revenue"
    note: Optional[str] = None
    strategies_available: list[str] = Field(default_factory=lambda: ["A", "B", "C"])
    strategy_a_description: str = "Descending calibrated p30 only"
    strategy_b_description: str = "Descending p30 * MRR"
    strategy_c_description: str = "Full RetainIQ: reliability gate + cooldown + top-K + p30xMRR + p7 tie-break"

