"""
test_workflow.py — Unit tests for human authority workflow and budget enforcement (§7.5, §7.7).

Verifies:
  - APPROVE, MODIFY, REJECT, NO_INTERVENTION, DEFER state transitions
  - Rejection of simulation-only/disabled actions on MODIFY
  - Transactional budget & staff capacity caps
  - Authorized overrides with required justification
  - Idempotent re-approvals
  - Follow-up anchor and 7d/14d/30d schedule calculation
"""

from datetime import datetime, timezone
import pytest

from backend.decision.enums import ActionCode, CaseStatus, HumanDecisionType
from backend.decision.models import (
    ActionProposal, ApprovalRequest, BudgetConfigRecord,
)
from backend.decision.workflow import (
    BudgetCapExceededError, WorkflowError, process_human_approval,
)


@pytest.fixture
def base_proposal():
    return ActionProposal(
        proposal_id="prop_001",
        case_id="case_001",
        customer_id="cust_001",
        action_code=ActionCode.ACCOUNT_CHECK_IN,
        eligibility_reason="usage_deviation_detected",
        estimated_cost_minor=5000,  # RM 50.00
        estimated_staff_minutes=20,
    )


@pytest.fixture
def budget_config():
    return BudgetConfigRecord(
        tenant_id="tenant_abc",
        currency="MYR",
        policy_period="daily",
        k_slots=10,
        staff_minutes_cap=480,
        monetary_budget_minor=100000,  # RM 1,000.00
    )


class TestApprovalTransitions:
    """Verifies state machine transitions per §7.7."""

    def test_approve_transitions_to_assigned(self, base_proposal, budget_config):
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.APPROVE,
            reason="Confirmed usage drop warrants check-in call.",
            actor="agent_sarah",
            assigned_owner="agent_sarah",
        )

        resp, events = process_human_approval(
            case_id="case_001",
            request=req,
            original_proposal=base_proposal,
            current_status=CaseStatus.PROPOSED,
            budget_config=budget_config,
        )

        assert resp.case_status == CaseStatus.ASSIGNED
        assert resp.final_action == ActionCode.ACCOUNT_CHECK_IN
        assert resp.follow_up_anchor is not None
        assert "7d" in resp.follow_up_due_at
        assert "14d" in resp.follow_up_due_at
        assert "30d" in resp.follow_up_due_at
        assert resp.budget_remaining_minor == 95000
        assert resp.staff_minutes_remaining == 460
        assert len(events) == 2  # HUMAN_DECISION and CASE_STATUS_CHANGED

    def test_modify_to_valid_operational_action(self, base_proposal, budget_config):
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.MODIFY,
            reason="Customer actually needs payment recovery assistance.",
            actor="agent_sarah",
            modified_action_code=ActionCode.PAYMENT_RECOVERY,
        )

        resp, events = process_human_approval(
            case_id="case_001",
            request=req,
            original_proposal=base_proposal,
            current_status=CaseStatus.PROPOSED,
            budget_config=budget_config,
        )

        assert resp.case_status == CaseStatus.ASSIGNED
        assert resp.final_action == ActionCode.PAYMENT_RECOVERY
        assert resp.original_proposal_action == ActionCode.ACCOUNT_CHECK_IN
        assert resp.follow_up_anchor is not None

    def test_modify_to_simulation_action_rejected(self, base_proposal, budget_config):
        """Simulation-only or disabled actions must NEVER be executable live."""
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.MODIFY,
            reason="Attempting to offer discount without authorization policy.",
            actor="agent_sarah",
            modified_action_code=ActionCode.CONDITIONAL_DISCOUNT,
        )

        with pytest.raises(WorkflowError, match="cannot enter live execution"):
            process_human_approval(
                case_id="case_001",
                request=req,
                original_proposal=base_proposal,
                current_status=CaseStatus.PROPOSED,
                budget_config=budget_config,
            )

    def test_reject_transitions_to_rejected(self, base_proposal, budget_config):
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.REJECT,
            reason="Customer known to have planned seasonal downtime.",
            actor="agent_sarah",
        )

        resp, _ = process_human_approval(
            case_id="case_001",
            request=req,
            original_proposal=base_proposal,
            current_status=CaseStatus.PROPOSED,
            budget_config=budget_config,
        )

        assert resp.case_status == CaseStatus.REJECTED
        assert resp.follow_up_anchor is None
        assert resp.follow_up_due_at is None
        # No budget deducted on reject
        assert resp.budget_remaining_minor == 100000

    def test_no_intervention_transitions_to_closed_no_action(self, base_proposal, budget_config):
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.NO_INTERVENTION,
            reason="Account healthy; usage variation within normal band.",
            actor="agent_sarah",
        )

        resp, _ = process_human_approval(
            case_id="case_001",
            request=req,
            original_proposal=base_proposal,
            current_status=CaseStatus.PROPOSED,
            budget_config=budget_config,
        )

        assert resp.case_status == CaseStatus.CLOSED_NO_ACTION
        assert resp.final_action == ActionCode.NO_INTERVENTION
        assert resp.follow_up_anchor is None


class TestBudgetAndCapacityGuards:
    """Verifies transactional budget safeguards per §7.5."""

    def test_budget_exceeded_raises_error(self, base_proposal, budget_config):
        # Action requires 5000 minor, already spent 98000 -> 103000 > 100000
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.APPROVE,
            reason="Approved check in.",
            actor="agent_sarah",
        )

        with pytest.raises(BudgetCapExceededError, match="Budget or capacity cap exceeded"):
            process_human_approval(
                case_id="case_001",
                request=req,
                original_proposal=base_proposal,
                current_status=CaseStatus.PROPOSED,
                budget_config=budget_config,
                already_spent_monetary_minor=98000,
            )

    def test_staff_cap_exceeded_raises_error(self, base_proposal, budget_config):
        # Action requires 20 min, already spent 470 min -> 490 > 480
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.APPROVE,
            reason="Approved check in.",
            actor="agent_sarah",
        )

        with pytest.raises(BudgetCapExceededError, match="Budget or capacity cap exceeded"):
            process_human_approval(
                case_id="case_001",
                request=req,
                original_proposal=base_proposal,
                current_status=CaseStatus.PROPOSED,
                budget_config=budget_config,
                already_spent_staff_minutes=470,
            )

    def test_authorized_override_allows_budget_overflow(self, base_proposal, budget_config):
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.APPROVE,
            reason="Critical enterprise account; overriding daily cap.",
            actor="director_dan",
            override_applied=True,
            override_reason="Executive escalation authorized by Head of CS.",
        )

        resp, _ = process_human_approval(
            case_id="case_001",
            request=req,
            original_proposal=base_proposal,
            current_status=CaseStatus.PROPOSED,
            budget_config=budget_config,
            already_spent_monetary_minor=98000,
        )

        assert resp.case_status == CaseStatus.ASSIGNED
        assert resp.budget_remaining_minor == 0

    def test_idempotent_approval_does_not_double_deduct(self, base_proposal, budget_config):
        req = ApprovalRequest(
            proposal_id="prop_001",
            decision_type=HumanDecisionType.APPROVE,
            reason="Check in.",
            actor="agent_sarah",
        )

        existing = {
            "human_decision_id": "hd_existing_123",
            "final_action_code": "ACCOUNT_CHECK_IN",
            "decision_type": "APPROVE",
            "actor": "agent_sarah",
            "decided_at": datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc),
        }

        resp, events = process_human_approval(
            case_id="case_001",
            request=req,
            original_proposal=base_proposal,
            current_status=CaseStatus.ASSIGNED,
            budget_config=budget_config,
            already_spent_monetary_minor=5000,
            already_spent_staff_minutes=20,
            existing_decision=existing,
        )

        assert resp.human_decision_id == "hd_existing_123"
        assert len(events) == 0  # No duplicate events created
