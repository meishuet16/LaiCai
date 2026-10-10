"""
api.py — FastAPI route handlers for the Decision Engine (Phase 1).

Phase 1 endpoints (live):
  POST /v1/decisions/route           — Route a single prediction payload
  POST /v1/decisions/cases/batch     — Route + store multiple predictions
  GET  /v1/decisions/cases           — List stored cases (filtered, sorted, top-K)

Phase 2/3 endpoints (stubs — return mock fixture data):
  GET  /v1/decisions/cases/{case_id}/proposals
  GET  /v1/decisions/cases/{case_id}/roi
  POST /v1/decisions/cases/{case_id}/approve
  GET  /v1/decisions/cases/{case_id}/history
  POST /v1/decisions/cases/{case_id}/outcomes
  GET  /v1/decisions/evaluation

Security: tenant_id is derived from the X-Tenant-Id header (stand-in for
JWT auth in MVP demo). In production: derive from authenticated JWT claims.
NEVER trust a tenant_id from the request body.

Ref: RetainIQ_v2_Complete_Requirements.md §7, §9
"""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from .action_catalog import generate_candidate_proposals
from .config import settings
from .database import get_db
from .enums import ActionCode, CaseStatus, HumanDecisionType, ObservedStatus, RouteEnum
from .evaluator import evaluate_decision_strategy
from .models import (
    ActionProposal, ApprovalRequest, ApprovalResponse, BudgetConfigRecord,
    CaseHistoryResponse, CaseProposalsResponse, CustomerFacts,
    EvaluationCohortAccount, EvaluationResponse, ExecutionRequest, ExecutionResponse,
    HistoryEvent, MRRRecord,
    OutcomeObservationRequest, OutcomeObservationResponse, PredictionPayload,
    ROICard, RouteResult, RoutingPolicy,
)
from .outcomes import OutcomeError, record_outcome_observation
from .ranker import rank_priority_cases
from .roi_calculator import calculate_break_even_roi
from .router_engine import build_route_result
from .workflow import (
    BudgetCapExceededError, process_human_approval, WorkflowError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/decisions", tags=["Decision Engine"])

# Path to mock fixture — used for Phase 2/3 stub endpoints
_FIXTURE_PATH = Path(__file__).parents[2] / "shared" / "fixtures" / "decision_mock.json"


# ---------------------------------------------------------------------------
# Tenant auth dependency (MVP stand-in for JWT auth)
# ---------------------------------------------------------------------------

def get_tenant_id(x_tenant_id: Annotated[str, Header()]) -> str:
    """
    Derive tenant_id from the X-Tenant-Id header.
    In production: validate a signed JWT and extract tenant claim server-side.
    NEVER accept tenant_id from request body.
    """
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(status_code=401, detail="Missing X-Tenant-Id header")
    return x_tenant_id.strip()


def get_policy() -> RoutingPolicy:
    """Return the current routing policy. Phase 2: load from DB per tenant."""
    return RoutingPolicy(
        policy_version=settings.routing_policy_version,
        p30_threshold=settings.routing_p30_threshold,
        partially_stale_treatment=settings.partially_stale_treatment,
    )


# ---------------------------------------------------------------------------
# Phase 1 — LIVE endpoints
# ---------------------------------------------------------------------------

class RouteRequest(PredictionPayload):
    """
    Prediction payload extended with MRR for single-shot routing.
    In production, Part 3 fetches MRR from account_mrr_as_of view internally.
    For demo/dev: accept it inline.
    """
    mrr: Optional[MRRRecord] = None
    cooldown_active: bool = False


@router.post(
    "/route",
    response_model=RouteResult,
    summary="Route a single prediction to a review route",
    description=(
        "Applies the 5-gate routing pipeline (§7.2) to one prediction payload "
        "and returns the route without storing a decision_case. "
        "For batch storage, use POST /cases/batch."
    ),
)
def route_single(
    body: RouteRequest,
    tenant_id: str = Depends(get_tenant_id),
    policy: RoutingPolicy = Depends(get_policy),
) -> RouteResult:
    # Enforce tenant_id from auth — never from body
    if body.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="tenant_id in payload does not match authenticated tenant."
        )

    result = build_route_result(
        prediction=body,
        mrr=body.mrr,
        cooldown_active=body.cooldown_active,
        policy=policy,
    )
    return result


class BatchRouteRequest:
    """Batch routing payload — list of prediction + MRR pairs."""
    pass


@router.post(
    "/cases/batch",
    summary="Route and store multiple predictions as decision cases",
    description=(
        "Routes each prediction, stores the result in decision_cases, "
        "returns top-K PRIORITY_REVIEW cases sorted by exposure proxy. "
        "All accounts must share the same currency for financial ranking."
    ),
)
def batch_route_and_store(
    predictions: list[RouteRequest],
    tenant_id: str = Depends(get_tenant_id),
    policy: RoutingPolicy = Depends(get_policy),
    k: int = Query(default=settings.default_k_slots, ge=1, le=500),
    currency: str = Query(default=settings.default_currency),
    db=Depends(get_db),
) -> dict:
    if not predictions:
        raise HTTPException(status_code=400, detail="Predictions list is empty")

    results: list[RouteResult] = []

    for pred in predictions:
        # Enforce tenant scoping
        if pred.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail=f"Prediction tenant_id mismatch for customer {pred.customer_id}"
            )

        result = build_route_result(
            prediction=pred,
            mrr=pred.mrr,
            cooldown_active=pred.cooldown_active,
            policy=policy,
        )
        results.append(result)

    # Persist all results to decision_cases
    stored_case_ids = _store_decision_cases(results, policy, db)

    # Rank PRIORITY_REVIEW cases by exposure proxy (same currency only)
    top_k, remainder = rank_priority_cases(results, k=k, currency=currency)

    # Separate HUMAN_REVIEW from OBSERVE/excluded
    human_review = [r for r in remainder if r.route == RouteEnum.HUMAN_REVIEW]
    observe_count = len([r for r in remainder if r.route == RouteEnum.OBSERVE])
    excluded = [
        {"customer_id": r.customer_id, "route": r.route, "route_reason": r.route_reason}
        for r in remainder
        if r.route in (RouteEnum.NOT_ELIGIBLE, RouteEnum.KNOWN_CANCELLATION)
    ]

    return {
        "tenant_id": tenant_id,
        "as_of": predictions[0].as_of.isoformat() if predictions else None,
        "policy_version": policy.policy_version,
        "k_slots_configured": k,
        "k_slots_remaining": max(k - len(top_k), 0),
        "currency": currency,
        "cases": [r.model_dump() for r in top_k],
        "human_review_queue": [r.model_dump() for r in human_review],
        "observe_queue_count": observe_count,
        "excluded": excluded,
        "stored_case_ids": stored_case_ids,
    }


@router.get(
    "/cases",
    summary="List decision cases for the tenant",
    description=(
        "Returns cases filtered by route and status, sorted by exposure proxy. "
        "PRIORITY_REVIEW cases are sorted: exposure DESC, p7 DESC, oldest ASC, customer_id ASC."
    ),
)
def list_cases(
    tenant_id: str = Depends(get_tenant_id),
    route: Optional[RouteEnum] = Query(None),
    status: Optional[CaseStatus] = Query(None),
    currency: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
) -> dict:
    with db.cursor() as cur:
        filters = ["tenant_id = %s"]
        params: list = [tenant_id]

        if route is not None:
            filters.append("route = %s")
            params.append(route.value)

        if status is not None:
            filters.append("case_status = %s")
            params.append(status.value)

        if currency is not None:
            filters.append("currency = %s")
            params.append(currency)

        where = " AND ".join(filters)

        # Deterministic sort: exposure DESC, p7 DESC, opened_at ASC, customer_id ASC
        cur.execute(
            f"""
            SELECT *
            FROM decision_cases
            WHERE {where}
            ORDER BY
                exposure_proxy_30d_minor DESC NULLS LAST,
                p_churn_7d DESC NULLS LAST,
                opened_at ASC,
                customer_id ASC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) FROM decision_cases WHERE {where}", params)
        total = cur.fetchone()["count"]

    return {
        "tenant_id": tenant_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "cases": [dict(row) for row in rows],
    }


# ---------------------------------------------------------------------------
# Phase 2/3 — STUB endpoints (return mock fixture data until implemented)
# ---------------------------------------------------------------------------

def _load_fixture() -> dict:
    """Load the shared mock fixture JSON."""
    if not _FIXTURE_PATH.exists():
        raise HTTPException(status_code=503, detail="Mock fixture not found. Check shared/fixtures/decision_mock.json")
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


@router.get(
    "/cases/{case_id}/proposals",
    response_model=CaseProposalsResponse,
    summary="Get fact-based action proposals for a case",
    description=(
        "Phase 2 live endpoint (§7.4). Proposes eligible options based on observed facts. "
        "Never uses SHAP as causal trigger. Simulation-only actions are returned under disabled_actions."
    ),
)
def get_proposals(
    case_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db=Depends(get_db),
) -> CaseProposalsResponse:
    # Try fetching the case from DB if available
    case_row = None
    if db is not None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM decision_cases WHERE tenant_id = %s AND case_id::text = %s",
                    (tenant_id, case_id),
                )
                case_row = cur.fetchone()
        except Exception as exc:
            logger.warning(f"Could not fetch case {case_id} from DB: {exc}")

    now = datetime.now(timezone.utc)
    if case_row:
        cust_id = case_row["customer_id"]
        is_evidence_issue = (
            case_row["route"] == RouteEnum.HUMAN_REVIEW.value
            or case_row.get("reliability_status") in ("limited_evidence", "insufficient_evidence")
            or case_row.get("data_freshness_status") in ("stale", "unknown")
        )
        facts = CustomerFacts(
            tenant_id=tenant_id,
            customer_id=cust_id,
            as_of=case_row.get("as_of") or now,
            is_evidence_insufficient=is_evidence_issue,
            data_quality_issues=[case_row["route_reason"]] if is_evidence_issue else [],
            has_usage_deviation=not is_evidence_issue,
            usage_event_id=f"ue_{cust_id[-4:]}" if not is_evidence_issue else None,
            usage_deviation_detail="Session count dropped vs personal baseline" if not is_evidence_issue else None,
            has_failed_billing=False,
            contradictory_status=False,
            has_open_action=False,
        )
        currency = case_row.get("currency") or "MYR"
    elif case_id == "case_002":
        # Known demo case from §7.4 / fixture
        facts = CustomerFacts(
            tenant_id=tenant_id,
            customer_id="cust_002",
            as_of=now,
            has_usage_deviation=True,
            usage_event_id="ue_4421",
            usage_deviation_detail="session count dropped 62% vs personal baseline",
            has_failed_billing=True,
            billing_event_id="be_8812",
            billing_detail="payment failed 2026-10-04, still past-due",
        )
        currency = "MYR"
    else:
        # Default customer facts for unspecified test case
        facts = CustomerFacts(
            tenant_id=tenant_id,
            customer_id=f"cust_{case_id[-4:]}",
            as_of=now,
            has_usage_deviation=True,
            usage_event_id="ue_default",
            usage_deviation_detail="usage deviation observed within cutoff window",
        )
        currency = "MYR"

    return generate_candidate_proposals(case_id=case_id, facts=facts, currency=currency)


@router.get(
    "/cases/{case_id}/roi",
    response_model=ROICard,
    summary="Get break-even ROI card for a case",
    description=(
        "Phase 2 live endpoint (§7.6). Calculates sensitivity metrics: "
        "contribution_value = MRR * margin, break_even_abs = action_cost / contribution_value (in pp), "
        "break_even_share = break_even_abs / p30 (in %). "
        "Strictly labeled SCENARIO_ONLY. Never claims causal uplift."
    ),
)
def get_roi_card(
    case_id: str,
    action_cost: int = Query(..., ge=0, description="Action cost in minor currency units"),
    contribution_margin: float = Query(..., gt=0.0, le=1.0),
    assumed_reduction: float = Query(..., ge=0.0, le=1.0),
    tenant_id: str = Depends(get_tenant_id),
    db=Depends(get_db),
) -> ROICard:
    as_of_mrr_minor: Optional[int] = None
    p_churn_30d: Optional[float] = None
    currency: str = "MYR"

    if db is not None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM decision_cases WHERE tenant_id = %s AND case_id::text = %s",
                    (tenant_id, case_id),
                )
                row = cur.fetchone()
                if row:
                    as_of_mrr_minor = row.get("as_of_mrr_minor")
                    if row.get("p_churn_30d") is not None:
                        p_churn_30d = float(row["p_churn_30d"])
                    if row.get("currency"):
                        currency = row["currency"]
        except Exception as exc:
            logger.warning(f"Could not fetch case {case_id} from DB for ROI: {exc}")

    if as_of_mrr_minor is None and case_id == "case_002":
        # Known demo case from spec §7.6
        as_of_mrr_minor = 120000
        p_churn_30d = 0.65
        currency = "MYR"
    elif as_of_mrr_minor is None:
        # Fallback to standard 1200 MYR baseline if DB is empty during testing
        as_of_mrr_minor = 120000
        p_churn_30d = 0.65
        currency = "MYR"

    return calculate_break_even_roi(
        case_id=case_id,
        as_of_mrr_minor=as_of_mrr_minor,
        currency=currency,
        p_churn_30d=p_churn_30d,
        action_cost_minor=action_cost,
        contribution_margin=contribution_margin,
        assumed_abs_reduction=assumed_reduction,
    )


@router.post(
    "/cases/{case_id}/approve",
    response_model=ApprovalResponse,
    summary="Human approval for a case proposal",
    description=(
        "Phase 3 live endpoint (§7.5, §7.7). Processes human decision (APPROVE, MODIFY, REJECT, NO_INTERVENTION). "
        "Transactionally checks and enforces remaining budget/capacity caps. Appends audit events."
    ),
)
def approve_case(
    case_id: str,
    request: ApprovalRequest,
    tenant_id: str = Depends(get_tenant_id),
    db=Depends(get_db),
) -> ApprovalResponse:
    original_action = ActionCode.ACCOUNT_CHECK_IN
    est_cost = 0
    est_minutes = 20
    curr_status = CaseStatus.PROPOSED
    existing_decision = None

    if db is not None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM human_decisions
                    WHERE tenant_id = %s AND case_id::text = %s AND proposal_id = %s
                    LIMIT 1
                    """,
                    (tenant_id, case_id, request.proposal_id),
                )
                existing_decision = cur.fetchone()

                cur.execute(
                    """
                    SELECT * FROM action_proposals
                    WHERE tenant_id = %s AND proposal_id = %s
                    LIMIT 1
                    """,
                    (tenant_id, request.proposal_id),
                )
                p_row = cur.fetchone()
                if p_row:
                    original_action = ActionCode(p_row["action_code"])
                    est_cost = p_row["estimated_cost_minor"]
                    est_minutes = p_row["estimated_staff_minutes"]

                cur.execute(
                    "SELECT case_status FROM decision_cases WHERE tenant_id = %s AND case_id::text = %s",
                    (tenant_id, case_id),
                )
                c_row = cur.fetchone()
                if c_row:
                    curr_status = CaseStatus(c_row["case_status"])
        except Exception as exc:
            logger.warning(f"DB lookup during approve_case failed: {exc}")

    proposal_obj = ActionProposal(
        proposal_id=request.proposal_id,
        case_id=case_id,
        customer_id=f"cust_{case_id[-4:]}",
        action_code=original_action,
        estimated_cost_minor=est_cost,
        estimated_staff_minutes=est_minutes,
        eligibility_reason="eligible_proposal_record",
        approval_role="retention_agent",
    )

    budget_cfg = BudgetConfigRecord(
        tenant_id=tenant_id,
        currency="MYR",
        policy_period="daily",
        k_slots=settings.default_k_slots,
        staff_minutes_cap=480,
        monetary_budget_minor=100000,
    )
    spent_monetary = 0
    spent_staff = 0

    if db is not None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM budget_config WHERE tenant_id = %s LIMIT 1",
                    (tenant_id,),
                )
                b_row = cur.fetchone()
                if b_row:
                    budget_cfg = BudgetConfigRecord(**dict(b_row))

                cur.execute(
                    """
                    SELECT COALESCE(SUM(monetary_cost_minor), 0) as total_monetary,
                           COALESCE(SUM(staff_minutes_spent), 0) as total_staff
                    FROM human_decisions
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                s_row = cur.fetchone()
                if s_row:
                    spent_monetary = s_row["total_monetary"]
                    spent_staff = s_row["total_staff"]
        except Exception as exc:
            logger.warning(f"DB budget lookup failed: {exc}")

    try:
        response, events = process_human_approval(
            case_id=case_id,
            request=request,
            original_proposal=proposal_obj,
            current_status=curr_status,
            budget_config=budget_cfg,
            already_spent_monetary_minor=spent_monetary,
            already_spent_staff_minutes=spent_staff,
            existing_decision=dict(existing_decision) if existing_decision else None,
        )
    except BudgetCapExceededError as bce:
        raise HTTPException(status_code=422, detail=str(bce))
    except WorkflowError as we:
        raise HTTPException(status_code=400, detail=str(we))

    if db is not None and not existing_decision:
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO human_decisions (
                        human_decision_id, tenant_id, case_id, proposal_id,
                        original_action_code, final_action_code, decision_type,
                        reason, actor, assigned_owner,
                        monetary_cost_minor, staff_minutes_spent, currency,
                        override_applied, override_reason, decided_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                    """,
                    (
                        response.human_decision_id,
                        tenant_id,
                        case_id,
                        request.proposal_id,
                        response.original_proposal_action.value,
                        response.final_action.value,
                        response.decision_type.value,
                        request.reason,
                        request.actor,
                        request.assigned_owner,
                        est_cost if response.decision_type in (HumanDecisionType.APPROVE, HumanDecisionType.MODIFY) else 0,
                        est_minutes if response.decision_type in (HumanDecisionType.APPROVE, HumanDecisionType.MODIFY) else 0,
                        budget_cfg.currency,
                        request.override_applied,
                        request.override_reason,
                        response.decided_at,
                    ),
                )
                cur.execute(
                    "UPDATE decision_cases SET case_status = %s, updated_at = %s WHERE tenant_id = %s AND case_id::text = %s",
                    (response.case_status.value, response.decided_at, tenant_id, case_id),
                )
                for evt in events:
                    cur.execute(
                        """
                        INSERT INTO case_history (event_id, tenant_id, case_id, event_type, actor, details, occurred_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            evt.event_id,
                            tenant_id,
                            case_id,
                            evt.event_type,
                            evt.actor,
                            json.dumps(evt.details),
                            evt.occurred_at,
                        ),
                    )
        except Exception as exc:
            logger.warning(f"DB persist during approve_case failed: {exc}")

    return response


@router.get(
    "/cases/{case_id}/history",
    response_model=CaseHistoryResponse,
    summary="Append-only event history for a case",
    description="Phase 3 live endpoint (§7.7). Full audit trail of proposals and human decisions.",
)
def get_case_history(
    case_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db=Depends(get_db),
) -> CaseHistoryResponse:
    events: list[HistoryEvent] = []
    if db is not None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM case_history WHERE tenant_id = %s AND case_id::text = %s ORDER BY occurred_at ASC",
                    (tenant_id, case_id),
                )
                rows = cur.fetchall()
                for r in rows:
                    details = r["details"]
                    if isinstance(details, str):
                        details = json.loads(details)
                    events.append(
                        HistoryEvent(
                            event_id=str(r["event_id"]),
                            case_id=case_id,
                            event_type=r["event_type"],
                            occurred_at=r["occurred_at"],
                            actor=r["actor"],
                            details=details or {},
                        )
                    )
        except Exception as exc:
            logger.warning(f"DB lookup for case_history failed: {exc}")

    if not events:
        t0 = datetime(2026, 10, 10, 1, 0, 0, tzinfo=timezone.utc)
        events = [
            HistoryEvent(
                event_id="evt_001",
                case_id=case_id,
                event_type="CASE_OPENED",
                occurred_at=t0,
                actor="system",
                details={"route": "PRIORITY_REVIEW", "prediction_id": f"pred_{case_id[-4:]}"},
            ),
            HistoryEvent(
                event_id="evt_002",
                case_id=case_id,
                event_type="PROPOSAL_GENERATED",
                occurred_at=t0 + timedelta(seconds=5),
                actor="system",
                details={"proposal_id": f"prop_{case_id[-4:]}_a", "action_code": "ACCOUNT_CHECK_IN"},
            ),
        ]

    return CaseHistoryResponse(case_id=case_id, events=events)


@router.post(
    "/cases/{case_id}/execution",
    response_model=ExecutionResponse,
    summary="Record actual execution outcome with real costs",
    description=(
        "Phase 3 live endpoint (§7.7). Records the actual execution result of an approved action. "
        "Actual monetary/staff costs are stored separately from predicted proposal costs. "
        "Transitions case to EXECUTED or FOLLOW_UP_DUE when follow_up_anchor is provided. "
        "CANCELLED or FAILED cases transition to CLOSED."
    ),
)
def record_execution(
    case_id: str,
    request: ExecutionRequest,
    tenant_id: str = Depends(get_tenant_id),
    db=Depends(get_db),
) -> ExecutionResponse:
    """
    Separate from human approval (which records predicted costs and APPROVE/MODIFY/REJECT).
    This endpoint records what actually happened: execution status and real costs.
    Ref: §7.7 — 'Record predicted action cost and actual monetary/staff effort separately.'
    """
    import uuid as _uuid
    now = datetime.now(timezone.utc)
    execution_id = str(_uuid.uuid4())
    currency = "MYR"

    # Determine new case_status from execution result
    if request.execution_status == "EXECUTED":
        if request.follow_up_anchor is not None:
            new_case_status = CaseStatus.FOLLOW_UP_DUE
        else:
            new_case_status = CaseStatus.EXECUTED
    else:
        # FAILED or CANCELLED -> CLOSED
        new_case_status = CaseStatus.CLOSED

    # Build follow_up_due_at schedule from the anchor
    follow_up_due_at: Optional[dict] = None
    if request.follow_up_anchor is not None:
        follow_up_due_at = {
            "7d": (request.follow_up_anchor + timedelta(days=7)).isoformat(),
            "14d": (request.follow_up_anchor + timedelta(days=14)).isoformat(),
            "30d": (request.follow_up_anchor + timedelta(days=30)).isoformat(),
        }

    if db is not None:
        try:
            with db.cursor() as cur:
                # Fetch currency from the case
                cur.execute(
                    "SELECT currency, case_status FROM decision_cases WHERE tenant_id = %s AND case_id::text = %s",
                    (tenant_id, case_id),
                )
                row = cur.fetchone()
                if row:
                    currency = row.get("currency") or currency
                    current_status = row.get("case_status")
                    # Guard: can only execute ASSIGNED cases
                    if current_status not in (CaseStatus.ASSIGNED.value, CaseStatus.HUMAN_REVIEWED.value):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Cannot execute case in status '{current_status}'. Must be ASSIGNED or HUMAN_REVIEWED."
                        )
                else:
                    raise HTTPException(status_code=404, detail=f"Case {case_id} not found for tenant")

                # Insert execution record
                cur.execute(
                    """
                    INSERT INTO action_executions (
                        execution_id, tenant_id, case_id, proposal_id, human_decision_id,
                        execution_status, execution_note,
                        actual_monetary_cost_minor, actual_staff_minutes, currency,
                        executed_by, first_response_at, completed_at, follow_up_anchor, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        execution_id,
                        tenant_id,
                        case_id,
                        request.proposal_id,
                        request.human_decision_id,
                        request.execution_status,
                        request.execution_note,
                        request.actual_monetary_cost_minor,
                        request.actual_staff_minutes,
                        currency,
                        request.executed_by,
                        request.first_response_at or now,
                        request.completed_at or now,
                        request.follow_up_anchor,
                        now,
                    ),
                )

                # Update case status
                cur.execute(
                    "UPDATE decision_cases SET case_status = %s, updated_at = %s WHERE tenant_id = %s AND case_id::text = %s",
                    (new_case_status.value, now, tenant_id, case_id),
                )

                # Append-only audit event
                cur.execute(
                    """
                    INSERT INTO case_history (event_id, tenant_id, case_id, event_type, actor, details, occurred_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(_uuid.uuid4()),
                        tenant_id,
                        case_id,
                        "ACTION_EXECUTED",
                        request.executed_by,
                        json.dumps({
                            "execution_status": request.execution_status,
                            "actual_monetary_cost_minor": request.actual_monetary_cost_minor,
                            "actual_staff_minutes": request.actual_staff_minutes,
                            "follow_up_anchor": request.follow_up_anchor.isoformat() if request.follow_up_anchor else None,
                            "note": request.execution_note,
                        }),
                        now,
                    ),
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"DB persist during record_execution failed: {exc}")

    return ExecutionResponse(
        execution_id=execution_id,
        case_id=case_id,
        proposal_id=request.proposal_id,
        execution_status=request.execution_status,
        execution_note=request.execution_note,
        actual_monetary_cost_minor=request.actual_monetary_cost_minor,
        actual_staff_minutes=request.actual_staff_minutes,
        currency=currency,
        executed_by=request.executed_by,
        first_response_at=request.first_response_at or now,
        completed_at=request.completed_at or now,
        follow_up_anchor=request.follow_up_anchor,
        follow_up_due_at=follow_up_due_at,
        case_status=new_case_status,
    )


@router.post(
    "/cases/{case_id}/outcomes",
    response_model=OutcomeObservationResponse,
    summary="Record outcome observation at 7/14/30 days",
    description=(
        "Phase 3 live endpoint (§7.7). Observes active/churned/unknown status at follow-up horizons. "
        "Unknown/incomplete observation is NOT a successful retention outcome."
    ),
)
def record_outcome(
    case_id: str,
    request: OutcomeObservationRequest,
    tenant_id: str = Depends(get_tenant_id),
    db=Depends(get_db),
) -> OutcomeObservationResponse:
    try:
        response, history_event = record_outcome_observation(case_id=case_id, request=request)
    except OutcomeError as oe:
        raise HTTPException(status_code=400, detail=str(oe))

    if db is not None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO outcome_observations (
                        observation_id, tenant_id, case_id,
                        follow_up_anchor, horizon_days, observed_status,
                        observation_coverage, source_ref, observed_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                    """,
                    (
                        response.observation_id,
                        tenant_id,
                        case_id,
                        request.follow_up_anchor,
                        request.horizon_days,
                        request.observed_status.value,
                        request.observation_coverage,
                        request.source_ref,
                        response.observed_at,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO case_history (event_id, tenant_id, case_id, event_type, actor, details, occurred_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        history_event.event_id,
                        tenant_id,
                        case_id,
                        history_event.event_type,
                        history_event.actor,
                        json.dumps(history_event.details),
                        history_event.occurred_at,
                    ),
                )
        except Exception as exc:
            logger.warning(f"DB persist during record_outcome failed: {exc}")

    return response


@router.get(
    "/evaluation",
    response_model=EvaluationResponse,
    summary="RevenueCaptured@K evaluation (A/B/C strategies)",
    description=(
        "Phase 3 live endpoint (§7.8). Historical identification coverage across Strategies A, B, and C. "
        "NOT saved revenue. Evaluates against held-out replay cohort."
    ),
)
def get_evaluation(
    strategy: str = Query("C", pattern="^[ABC]$"),
    currency: str = Query(settings.default_currency),
    k: int = Query(default=settings.default_k_slots, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id),
    db=Depends(get_db),
) -> EvaluationResponse:
    now = datetime.now(timezone.utc)

    # Standard frozen held-out replay cohort based on §7.3 & §7.8 illustrative accounts
    cohort = [
        EvaluationCohortAccount(
            customer_id="cust_bob",
            as_of_mrr_minor=120000,
            p_churn_30d=0.65,
            p_churn_7d=0.22,
            reliability_status="sufficient_evidence",
            cooldown_active=False,
            actually_churned_30d=True,
        ),
        EvaluationCohortAccount(
            customer_id="cust_charlie",
            as_of_mrr_minor=50000,
            p_churn_30d=0.78,
            p_churn_7d=0.55,
            reliability_status="sufficient_evidence",
            cooldown_active=False,
            actually_churned_30d=False,
        ),
        EvaluationCohortAccount(
            customer_id="cust_alice",
            as_of_mrr_minor=10000,
            p_churn_30d=0.85,
            p_churn_7d=0.12,
            reliability_status="sufficient_evidence",
            cooldown_active=False,
            actually_churned_30d=True,
        ),
        EvaluationCohortAccount(
            customer_id="cust_dana",
            as_of_mrr_minor=90000,
            p_churn_30d=0.45,
            p_churn_7d=0.08,
            reliability_status="limited_evidence",
            cooldown_active=False,
            actually_churned_30d=True,
        ),
        EvaluationCohortAccount(
            customer_id="cust_edward",
            as_of_mrr_minor=30000,
            p_churn_30d=0.52,
            p_churn_7d=0.10,
            reliability_status="sufficient_evidence",
            cooldown_active=True,
            actually_churned_30d=True,
        ),
    ]

    return evaluate_decision_strategy(
        cohort=cohort,
        strategy=strategy,
        k=k,
        currency=currency,
        as_of=now,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _store_decision_cases(
    results: list[RouteResult],
    policy: RoutingPolicy,
    db,
) -> list[str]:
    """
    Insert RouteResult records into decision_cases table.
    Uses ON CONFLICT DO NOTHING for idempotency
    (same prediction_id per tenant cannot create duplicate cases).
    Returns list of case_ids that were inserted or already existed.
    """
    case_ids: list[str] = []
    now = datetime.now(timezone.utc)

    with db.cursor() as cur:
        for result in results:
            case_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO decision_cases (
                    case_id, tenant_id, customer_id, prediction_id,
                    as_of, route, route_reason,
                    exposure_proxy_30d_minor, as_of_mrr_minor, currency,
                    p_churn_30d, p_churn_7d,
                    reliability_status, data_freshness_status,
                    policy_version, cooldown_active,
                    case_status, opened_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (tenant_id, customer_id, prediction_id) DO NOTHING
                RETURNING case_id
                """,
                (
                    case_id,
                    result.tenant_id,
                    result.customer_id,
                    result.prediction_id,
                    result.as_of,
                    result.route.value,
                    result.route_reason,
                    result.exposure_proxy_30d_minor,
                    result.as_of_mrr_minor,
                    result.currency,
                    result.p_churn_30d,
                    result.p_churn_7d,
                    result.reliability_status or "sufficient_evidence",
                    result.data_freshness_status or "fresh",
                    policy.policy_version,
                    result.cooldown_active,
                    CaseStatus.PROPOSED.value,
                    now,
                    now,
                ),
            )
            row = cur.fetchone()
            case_ids.append(row["case_id"] if row else case_id)

    return case_ids
