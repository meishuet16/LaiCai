"""
workflow.py — Human authority state machine & transactional approval safeguards (§7.5, §7.7).

Manages the case approval workflow:
  PROPOSED -> HUMAN_REVIEWED -> ASSIGNED -> EXECUTED -> FOLLOW_UP_DUE -> CLOSED
                         \\-> CLOSED_NO_ACTION
                         \\-> REJECTED

RULES (§7.5, §7.7):
  1. Human Authority: Decisions include APPROVE, MODIFY, REJECT, NO_INTERVENTION, DEFER.
  2. Audit Preservation: Preserves original system proposal and final human choice.
  3. Action Guard: Non-operational / simulation-only actions can NEVER be selected on MODIFY.
  4. Capacity Enforcement: Enforces remaining budget and staff-minute caps transactionally;
     requires explicit authorized override with reason to exceed caps.
  5. Idempotency: Approving an already decided case returns existing decision without double-deduction.
  6. Follow-up Anchor: For approved/modified actions, anchors follow-up at decided_at with
     due dates at 7d, 14d, and 30d.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from .action_catalog import ACTION_CATALOG
from .enums import ActionCode, ActionMode, CaseStatus, HumanDecisionType
from .models import (
    ActionProposal, ApprovalRequest, ApprovalResponse, BudgetConfigRecord,
    HistoryEvent,
)


class WorkflowError(Exception):
    """Domain error in workflow processing."""
    pass


class BudgetCapExceededError(WorkflowError):
    """Raised when an approval would exceed monetary or staff-minute caps."""
    pass


def process_human_approval(
    case_id: str,
    request: ApprovalRequest,
    original_proposal: ActionProposal,
    current_status: CaseStatus,
    budget_config: BudgetConfigRecord,
    already_spent_monetary_minor: int = 0,
    already_spent_staff_minutes: int = 0,
    existing_decision: Optional[dict[str, Any]] = None,
) -> tuple[ApprovalResponse, list[HistoryEvent]]:
    """
    Process a human review decision on an action proposal.

    Returns:
        (ApprovalResponse, list of new audit events to record)
    """
    now = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Idempotency check: if this proposal was already approved/decided
    # ------------------------------------------------------------------
    if existing_decision is not None:
        return ApprovalResponse(
            human_decision_id=str(existing_decision.get("human_decision_id")),
            case_id=case_id,
            case_status=current_status,
            original_proposal_action=original_proposal.action_code,
            final_action=ActionCode(existing_decision.get("final_action_code")),
            decision_type=HumanDecisionType(existing_decision.get("decision_type")),
            actor=existing_decision.get("actor", request.actor),
            decided_at=existing_decision.get("decided_at", now),
            assigned_owner=existing_decision.get("assigned_owner"),
            budget_remaining_minor=max(
                0, budget_config.monetary_budget_minor - already_spent_monetary_minor
            ),
            staff_minutes_remaining=max(
                0, budget_config.staff_minutes_cap - already_spent_staff_minutes
            ),
            follow_up_anchor=existing_decision.get("decided_at"),
            follow_up_due_at={
                "7d": (existing_decision.get("decided_at", now) + timedelta(days=7)).isoformat(),
                "14d": (existing_decision.get("decided_at", now) + timedelta(days=14)).isoformat(),
                "30d": (existing_decision.get("decided_at", now) + timedelta(days=30)).isoformat(),
            } if existing_decision.get("decision_type") in ("APPROVE", "MODIFY") else None,
        ), []

    # ------------------------------------------------------------------
    # Step 1: Resolve Final Action and Action Mode
    # ------------------------------------------------------------------
    original_action = original_proposal.action_code
    monetary_cost = 0
    staff_minutes = 0

    if request.decision_type == HumanDecisionType.APPROVE:
        final_action = original_action
        new_status = CaseStatus.ASSIGNED
        monetary_cost = original_proposal.estimated_cost_minor
        staff_minutes = original_proposal.estimated_staff_minutes

    elif request.decision_type == HumanDecisionType.MODIFY:
        if not request.modified_action_code:
            raise WorkflowError("modified_action_code is required when decision_type is MODIFY")

        final_action = request.modified_action_code
        cat_entry = ACTION_CATALOG.get(final_action)
        if not cat_entry:
            raise WorkflowError(f"Unknown action code: {final_action}")

        # Non-operational actions can NEVER be approved live
        if cat_entry.mode in (ActionMode.DISABLED, ActionMode.SIMULATION_ONLY):
            raise WorkflowError(
                f"Action '{final_action.value}' is in mode '{cat_entry.mode.value}' "
                "and cannot enter live execution."
            )

        new_status = CaseStatus.ASSIGNED
        monetary_cost = cat_entry.estimated_cost_minor
        staff_minutes = cat_entry.estimated_staff_minutes

    elif request.decision_type == HumanDecisionType.REJECT:
        final_action = original_action
        new_status = CaseStatus.REJECTED
        monetary_cost = 0
        staff_minutes = 0

    elif request.decision_type == HumanDecisionType.NO_INTERVENTION:
        final_action = ActionCode.NO_INTERVENTION
        new_status = CaseStatus.CLOSED_NO_ACTION
        monetary_cost = 0
        staff_minutes = 5  # Documented human decision review time

    elif request.decision_type == HumanDecisionType.DEFER:
        final_action = original_action
        new_status = CaseStatus.HUMAN_REVIEWED
        monetary_cost = 0
        staff_minutes = 0

    else:
        raise WorkflowError(f"Unsupported decision type: {request.decision_type}")

    # ------------------------------------------------------------------
    # Step 2: Transactional Budget and Staff Capacity Enforcement (§7.5)
    # ------------------------------------------------------------------
    budget_limit = budget_config.monetary_budget_minor
    staff_limit = budget_config.staff_minutes_cap

    new_spent_monetary = already_spent_monetary_minor + monetary_cost
    new_spent_staff = already_spent_staff_minutes + staff_minutes

    if new_spent_monetary > budget_limit or new_spent_staff > staff_limit:
        if not request.override_applied:
            raise BudgetCapExceededError(
                f"Budget or capacity cap exceeded: "
                f"monetary needed={new_spent_monetary}/{budget_limit}, "
                f"staff needed={new_spent_staff}/{staff_limit}. "
                "Requires authorized override to proceed."
            )
        if not request.override_reason or not request.override_reason.strip():
            raise WorkflowError("Override requested but no override_reason provided.")

    budget_remaining = max(0, budget_limit - new_spent_monetary)
    staff_remaining = max(0, staff_limit - new_spent_staff)

    # ------------------------------------------------------------------
    # Step 3: Anchor follow-up timing
    # ------------------------------------------------------------------
    follow_up_anchor = None
    follow_up_due_at = None

    if request.decision_type in (HumanDecisionType.APPROVE, HumanDecisionType.MODIFY):
        follow_up_anchor = now
        follow_up_due_at = {
            "7d": (now + timedelta(days=7)).isoformat(),
            "14d": (now + timedelta(days=14)).isoformat(),
            "30d": (now + timedelta(days=30)).isoformat(),
        }

    # ------------------------------------------------------------------
    # Step 4: Construct audit trail events (Immutable append-only history)
    # ------------------------------------------------------------------
    decision_id = f"hd_{uuid.uuid4().hex[:8]}"

    event_decision = HistoryEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        event_type="HUMAN_DECISION",
        occurred_at=now,
        actor=request.actor,
        details={
            "human_decision_id": decision_id,
            "decision_type": request.decision_type.value,
            "original_action": original_action.value,
            "final_action": final_action.value,
            "reason": request.reason,
            "assigned_owner": request.assigned_owner,
            "monetary_cost_minor": monetary_cost,
            "staff_minutes_spent": staff_minutes,
            "override_applied": request.override_applied,
            "override_reason": request.override_reason,
        },
    )

    event_status = HistoryEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        event_type="CASE_STATUS_CHANGED",
        occurred_at=now + timedelta(milliseconds=1),
        actor=request.actor,
        details={
            "from": current_status.value,
            "to": new_status.value,
            "trigger": "human_decision",
        },
    )

    events = [event_decision, event_status]

    response = ApprovalResponse(
        human_decision_id=decision_id,
        case_id=case_id,
        case_status=new_status,
        original_proposal_action=original_action,
        final_action=final_action,
        decision_type=request.decision_type,
        actor=request.actor,
        decided_at=now,
        assigned_owner=request.assigned_owner,
        budget_remaining_minor=budget_remaining,
        staff_minutes_remaining=staff_remaining,
        follow_up_anchor=follow_up_anchor,
        follow_up_due_at=follow_up_due_at,
    )

    return response, events
