"""
action_catalog.py — Fact-based Next Best Action catalog & candidate generation (§7.4).

Proposes eligible, fact-based retention options — NOT scientifically proven best interventions.
Ref: RetainIQ_v2_Complete_Requirements.md §7.4

CORE PRINCIPLES:
  1. FACT-BASED ONLY: Use observed customer facts available at cutoff as_of.
     NEVER use SHAP values as causal action triggers.
  2. NO UNSUPPORTED AUTO-EXECUTION: Proposals are presented for human review/approval.
     Simulation-only and disabled actions must NEVER enter live executable proposals.
  3. DATA INTEGRITY: If evidence is stale, missing, or conflicting, route to
     DATA_INVESTIGATION instead of pretending to know the right incentive.
  4. SUPPRESSION & COOLDOWN: Suppress discretionary contact if an open action exists
     or an active cooldown applies.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid

from .enums import ActionCode, ActionMode
from .models import (
    ActionProposal, CaseProposalsResponse, CustomerFacts, DisabledAction,
    SupportingFactRef,
)

CATALOGUE_VERSION = "action_catalog_v1"


@dataclass(frozen=True)
class CatalogEntry:
    """Canonical catalog definition for an action (§7.4)."""
    action_code: ActionCode
    title: str
    description: str
    required_fields: tuple[str, ...]
    eligibility_conditions: str
    contraindications: tuple[str, ...]
    estimated_staff_minutes: int
    estimated_cost_minor: int
    currency: str
    cooldown_days: Optional[int]
    approval_role: str
    mode: ActionMode
    disabled_reason: Optional[str] = None


# Canonical catalog definition
ACTION_CATALOG: dict[ActionCode, CatalogEntry] = {
    ActionCode.ACCOUNT_CHECK_IN: CatalogEntry(
        action_code=ActionCode.ACCOUNT_CHECK_IN,
        title="Account Check-In Call / Email",
        description="Direct outreach by retention agent following measured usage drop.",
        required_fields=("has_usage_deviation", "usage_event_id"),
        eligibility_conditions="Valid measured usage deviation; no contradictory account status.",
        contraindications=("contradictory_status", "cooldown_active", "open_action_exists"),
        estimated_staff_minutes=20,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=7,
        approval_role="retention_agent",
        mode=ActionMode.OPERATIONAL,
    ),
    ActionCode.PAYMENT_RECOVERY: CatalogEntry(
        action_code=ActionCode.PAYMENT_RECOVERY,
        title="Payment Recovery & Dunning Assistance",
        description="Assistance following confirmed past-due invoice or billing failure.",
        required_fields=("has_failed_billing", "billing_event_id"),
        eligibility_conditions="Confirmed failed or past-due billing event under business policy.",
        contraindications=("cooldown_active", "open_action_exists"),
        estimated_staff_minutes=15,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=3,
        approval_role="retention_agent",
        mode=ActionMode.OPERATIONAL,
    ),
    ActionCode.PRODUCT_WALKTHROUGH: CatalogEntry(
        action_code=ActionCode.PRODUCT_WALKTHROUGH,
        title="Targeted Feature / Onboarding Walkthrough",
        description="Specialist onboarding walkthrough addressing an observed product adoption gap.",
        required_fields=("has_feature_gap", "feature_event_id"),
        eligibility_conditions="Usage evidence plus confirmed feature/onboarding gap event.",
        contraindications=("no_feature_events", "cooldown_active", "open_action_exists"),
        estimated_staff_minutes=30,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=14,
        approval_role="csm",
        mode=ActionMode.CONDITIONAL,
    ),
    ActionCode.DATA_INVESTIGATION: CatalogEntry(
        action_code=ActionCode.DATA_INVESTIGATION,
        title="Data Quality & Instrumentation Investigation",
        description="Investigation by data specialist when account signals are stale or missing.",
        required_fields=("is_evidence_insufficient_or_stale",),
        eligibility_conditions="Stale, missing, conflicting or limited source evidence.",
        contraindications=(),
        estimated_staff_minutes=15,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=None,
        approval_role="data_specialist",
        mode=ActionMode.OPERATIONAL,
    ),
    ActionCode.NO_INTERVENTION: CatalogEntry(
        action_code=ActionCode.NO_INTERVENTION,
        title="No Discretionary Action",
        description="Human reviewer decides against intervention with documented rationale.",
        required_fields=(),
        eligibility_conditions="Always available to human reviewer.",
        contraindications=(),
        estimated_staff_minutes=5,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=None,
        approval_role="retention_agent",
        mode=ActionMode.OPERATIONAL,
    ),
    ActionCode.TECH_SUPPORT_ESCALATION: CatalogEntry(
        action_code=ActionCode.TECH_SUPPORT_ESCALATION,
        title="Technical Support Escalation",
        description="Escalation to tier-2 support for open unresolved bug tickets.",
        required_fields=("support_ticket_id",),
        eligibility_conditions="Relevant unresolved ticket status.",
        contraindications=(),
        estimated_staff_minutes=25,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=7,
        approval_role="support_lead",
        mode=ActionMode.DISABLED,
        disabled_reason="Unresolved support ticket data not available in MVP Part 1 dataset",
    ),
    ActionCode.PLAN_REVIEW: CatalogEntry(
        action_code=ActionCode.PLAN_REVIEW,
        title="Plan Right-Sizing Review",
        description="Commercial plan review based on entitlements and utilization.",
        required_fields=("entitlement_data",),
        eligibility_conditions="Documented entitlement mismatch.",
        contraindications=(),
        estimated_staff_minutes=25,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=30,
        approval_role="account_executive",
        mode=ActionMode.SIMULATION_ONLY,
        disabled_reason="Entitlement and plan policy impact logic disabled for live execution in MVP",
    ),
    ActionCode.PAUSE: CatalogEntry(
        action_code=ActionCode.PAUSE,
        title="Subscription Pause Option",
        description="Temporary subscription pause under terms of service.",
        required_fields=("pause_policy_authorization",),
        eligibility_conditions="Customer requested pause capability.",
        contraindications=(),
        estimated_staff_minutes=10,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=60,
        approval_role="billing_specialist",
        mode=ActionMode.SIMULATION_ONLY,
        disabled_reason="Account pause policy disabled for live execution in MVP",
    ),
    ActionCode.DOWNGRADE: CatalogEntry(
        action_code=ActionCode.DOWNGRADE,
        title="Controlled Tier Downgrade",
        description="Transition customer to lower tier to prevent complete churn.",
        required_fields=("downgrade_authorization",),
        eligibility_conditions="Documented down-tier request.",
        contraindications=(),
        estimated_staff_minutes=15,
        estimated_cost_minor=0,
        currency="MYR",
        cooldown_days=30,
        approval_role="account_executive",
        mode=ActionMode.SIMULATION_ONLY,
        disabled_reason="Downgrade workflow disabled for live execution in MVP",
    ),
    ActionCode.CONDITIONAL_DISCOUNT: CatalogEntry(
        action_code=ActionCode.CONDITIONAL_DISCOUNT,
        title="Discretionary Renewal Concession",
        description="Targeted monetary discount with strict executive sign-off.",
        required_fields=("price_objection_ref", "authorization_role"),
        eligibility_conditions="Documented price objection and financial authorization.",
        contraindications=(),
        estimated_staff_minutes=20,
        estimated_cost_minor=15000,
        currency="MYR",
        cooldown_days=90,
        approval_role="finance_manager",
        mode=ActionMode.SIMULATION_ONLY,
        disabled_reason="Discretionary discount authorization not enabled for unverified causal interventions",
    ),
}


def get_disabled_actions_list() -> list[DisabledAction]:
    """Return all actions currently marked disabled or simulation_only."""
    disabled = []
    for entry in ACTION_CATALOG.values():
        if entry.mode in (ActionMode.DISABLED, ActionMode.SIMULATION_ONLY):
            disabled.append(
                DisabledAction(
                    action_code=entry.action_code,
                    mode=entry.mode,
                    reason=entry.disabled_reason or f"Action in mode {entry.mode.value}",
                )
            )
    return disabled


def generate_candidate_proposals(
    case_id: str,
    facts: CustomerFacts,
    currency: str = "MYR",
) -> CaseProposalsResponse:
    """
    Generate candidate action proposals for a single account case (§7.4).

    Rules:
      1. If evidence is insufficient or data quality issues exist:
         propose DATA_INVESTIGATION + NO_INTERVENTION. Do NOT fabricate incentives.
      2. If account already has an open action:
         suppress repeated discretionary contact proposals (only NO_INTERVENTION).
      3. For ACCOUNT_CHECK_IN:
         requires has_usage_deviation + usage_event_id; blocked by contradictory_status or cooldown.
      4. For PAYMENT_RECOVERY:
         requires has_failed_billing + billing_event_id; blocked by cooldown.
      5. For PRODUCT_WALKTHROUGH:
         requires has_feature_gap + feature_event_id; blocked by cooldown.
      6. NO_INTERVENTION is always proposed as an available human choice.
      7. Non-operational actions are attached under disabled_actions, NEVER as executable proposals.
    """
    proposals: list[ActionProposal] = []
    customer_id = facts.customer_id

    # ------------------------------------------------------------------
    # Branch 1: Missing or insufficient evidence -> DATA_INVESTIGATION
    # §7.4: "If evidence is missing, route to investigation instead of
    # pretending to know the right incentive."
    # ------------------------------------------------------------------
    if facts.is_evidence_insufficient or len(facts.data_quality_issues) > 0:
        entry = ACTION_CATALOG[ActionCode.DATA_INVESTIGATION]
        refs = [
            SupportingFactRef(
                table="data_quality_log",
                id=f"dq_{idx+1}",
                description=issue,
            )
            for idx, issue in enumerate(facts.data_quality_issues)
        ]
        if not refs and facts.is_evidence_insufficient:
            refs.append(
                SupportingFactRef(
                    table="prediction_reliability",
                    id="rel_insufficient",
                    description="Insufficient or stale evidence observed at cutoff",
                )
            )

        proposals.append(
            ActionProposal(
                proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                case_id=case_id,
                customer_id=customer_id,
                action_code=ActionCode.DATA_INVESTIGATION,
                catalogue_version=CATALOGUE_VERSION,
                mode=entry.mode,
                eligibility_reason="stale_missing_or_conflicting_evidence",
                supporting_fact_refs=refs,
                estimated_cost_minor=entry.estimated_cost_minor,
                currency=currency,
                estimated_staff_minutes=entry.estimated_staff_minutes,
                cooldown_days=entry.cooldown_days,
                approval_role=entry.approval_role,
            )
        )

    # ------------------------------------------------------------------
    # Branch 2: Account has open action -> suppress discretionary outreach
    # §7.3: "A customer with an open action or applicable cooldown should
    # not repeatedly receive the same discretionary contact proposal."
    # ------------------------------------------------------------------
    elif facts.has_open_action:
        # Discretionary proposals suppressed; human reviewer can monitor or choose NO_INTERVENTION
        pass

    # ------------------------------------------------------------------
    # Branch 3: Standard eligible candidate generation
    # ------------------------------------------------------------------
    else:
        # 1. ACCOUNT_CHECK_IN
        check_in = ACTION_CATALOG[ActionCode.ACCOUNT_CHECK_IN]
        if (
            facts.has_usage_deviation
            and facts.usage_event_id
            and not facts.contradictory_status
            and ActionCode.ACCOUNT_CHECK_IN not in facts.active_cooldown_actions
        ):
            proposals.append(
                ActionProposal(
                    proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                    case_id=case_id,
                    customer_id=customer_id,
                    action_code=ActionCode.ACCOUNT_CHECK_IN,
                    catalogue_version=CATALOGUE_VERSION,
                    mode=check_in.mode,
                    eligibility_reason="usage_deviation_detected_no_contradictory_status",
                    supporting_fact_refs=[
                        SupportingFactRef(
                            table="usage_events",
                            id=facts.usage_event_id,
                            description=facts.usage_deviation_detail or "Measured usage deviation observed",
                        )
                    ],
                    estimated_cost_minor=check_in.estimated_cost_minor,
                    currency=currency,
                    estimated_staff_minutes=check_in.estimated_staff_minutes,
                    cooldown_days=check_in.cooldown_days,
                    approval_role=check_in.approval_role,
                )
            )

        # 2. PAYMENT_RECOVERY
        payment_rec = ACTION_CATALOG[ActionCode.PAYMENT_RECOVERY]
        if (
            facts.has_failed_billing
            and facts.billing_event_id
            and ActionCode.PAYMENT_RECOVERY not in facts.active_cooldown_actions
        ):
            proposals.append(
                ActionProposal(
                    proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                    case_id=case_id,
                    customer_id=customer_id,
                    action_code=ActionCode.PAYMENT_RECOVERY,
                    catalogue_version=CATALOGUE_VERSION,
                    mode=payment_rec.mode,
                    eligibility_reason="confirmed_failed_billing_event",
                    supporting_fact_refs=[
                        SupportingFactRef(
                            table="billing_events",
                            id=facts.billing_event_id,
                            description=facts.billing_detail or "Payment failure or past-due invoice recorded",
                        )
                    ],
                    estimated_cost_minor=payment_rec.estimated_cost_minor,
                    currency=currency,
                    estimated_staff_minutes=payment_rec.estimated_staff_minutes,
                    cooldown_days=payment_rec.cooldown_days,
                    approval_role=payment_rec.approval_role,
                )
            )

        # 3. PRODUCT_WALKTHROUGH (Conditional — only if feature events exist)
        walkthrough = ACTION_CATALOG[ActionCode.PRODUCT_WALKTHROUGH]
        if (
            facts.has_feature_gap
            and facts.feature_event_id
            and ActionCode.PRODUCT_WALKTHROUGH not in facts.active_cooldown_actions
        ):
            proposals.append(
                ActionProposal(
                    proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                    case_id=case_id,
                    customer_id=customer_id,
                    action_code=ActionCode.PRODUCT_WALKTHROUGH,
                    catalogue_version=CATALOGUE_VERSION,
                    mode=walkthrough.mode,
                    eligibility_reason="feature_level_adoption_gap_observed",
                    supporting_fact_refs=[
                        SupportingFactRef(
                            table="feature_events",
                            id=facts.feature_event_id,
                            description=facts.feature_gap_detail or "Product feature or onboarding drop-off observed",
                        )
                    ],
                    estimated_cost_minor=walkthrough.estimated_cost_minor,
                    currency=currency,
                    estimated_staff_minutes=walkthrough.estimated_staff_minutes,
                    cooldown_days=walkthrough.cooldown_days,
                    approval_role=walkthrough.approval_role,
                )
            )

    # ------------------------------------------------------------------
    # Always available option: NO_INTERVENTION (§7.4)
    # Human reviewer can always choose no action with documented reason.
    # ------------------------------------------------------------------
    no_int = ACTION_CATALOG[ActionCode.NO_INTERVENTION]
    proposals.append(
        ActionProposal(
            proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            customer_id=customer_id,
            action_code=ActionCode.NO_INTERVENTION,
            catalogue_version=CATALOGUE_VERSION,
            mode=no_int.mode,
            eligibility_reason="always_available_human_choice",
            supporting_fact_refs=[],
            estimated_cost_minor=no_int.estimated_cost_minor,
            currency=currency,
            estimated_staff_minutes=no_int.estimated_staff_minutes,
            cooldown_days=no_int.cooldown_days,
            approval_role=no_int.approval_role,
        )
    )

    return CaseProposalsResponse(
        case_id=case_id,
        customer_id=customer_id,
        proposals=proposals,
        disabled_actions=get_disabled_actions_list(),
    )
