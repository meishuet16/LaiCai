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
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from .config import settings
from .database import get_db
from .enums import CaseStatus, RouteEnum
from .models import (
    MRRRecord, PredictionPayload, RouteResult, RoutingPolicy,
)
from .ranker import rank_priority_cases
from .router_engine import build_route_result

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
    summary="[STUB] Get action proposals for a case",
    description="Phase 2 — returns mock fixture data until action catalog is implemented.",
)
def get_proposals(
    case_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    fixture = _load_fixture()
    data = fixture.get("GET /v1/decisions/cases/{case_id}/proposals", {})
    data["_stub"] = True
    data["_note"] = "SYNTHETIC_FIXTURE — Phase 2 not yet implemented"
    return data


@router.get(
    "/cases/{case_id}/roi",
    summary="[STUB] Get break-even ROI card for a case",
    description=(
        "Phase 2 — returns mock ROI card. "
        "Always labeled SCENARIO_ONLY. "
        "Formula: break_even = action_cost / (MRR * margin); see §7.6."
    ),
)
def get_roi_card(
    case_id: str,
    action_cost: int = Query(..., ge=0, description="Action cost in minor currency units"),
    contribution_margin: float = Query(..., gt=0.0, le=1.0),
    assumed_reduction: float = Query(..., ge=0.0, le=1.0),
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    fixture = _load_fixture()
    data = fixture.get("GET /v1/decisions/cases/{case_id}/roi", {})
    data["_stub"] = True
    data["_note"] = "SYNTHETIC_FIXTURE — live ROI calculation in Phase 2"
    return data


@router.post(
    "/cases/{case_id}/approve",
    summary="[STUB] Human approval for a case proposal",
    description="Phase 3 — human decision workflow with append-only audit trail.",
)
def approve_case(
    case_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    fixture = _load_fixture()
    data = fixture.get("POST /v1/decisions/cases/{case_id}/approve — response", {})
    data["_stub"] = True
    data["_note"] = "SYNTHETIC_FIXTURE — human approval workflow in Phase 3"
    return data


@router.get(
    "/cases/{case_id}/history",
    summary="[STUB] Append-only event history for a case",
    description="Phase 3 — full audit trail of proposals and human decisions.",
)
def get_case_history(
    case_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    fixture = _load_fixture()
    data = fixture.get("GET /v1/decisions/cases/{case_id}/history", {})
    data["_stub"] = True
    data["_note"] = "SYNTHETIC_FIXTURE — append-only history in Phase 3"
    return data


@router.post(
    "/cases/{case_id}/outcomes",
    summary="[STUB] Record outcome observation at 7/14/30 days",
    description=(
        "Phase 3 — observe active/churned/unknown status at follow-up horizons. "
        "unknown is NOT a successful retention outcome."
    ),
)
def record_outcome(
    case_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    fixture = _load_fixture()
    data = fixture.get("POST /v1/decisions/cases/{case_id}/outcomes — response", {})
    data["_stub"] = True
    data["_note"] = "SYNTHETIC_FIXTURE — outcome tracking in Phase 3"
    return data


@router.get(
    "/evaluation",
    summary="[STUB] RevenueCaptured@K evaluation (A/B/C strategies)",
    description=(
        "Phase 3 — historical identification coverage. "
        "NOT saved revenue. Requires frozen held-out replay data."
    ),
)
def get_evaluation(
    strategy: str = Query("C", pattern="^[ABC]$"),
    currency: str = Query(settings.default_currency),
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    fixture = _load_fixture()
    data = fixture.get("GET /v1/decisions/evaluation?strategy=C&currency=MYR", {})
    data["strategy"] = strategy
    data["currency"] = currency
    data["_stub"] = True
    data["_note"] = "SYNTHETIC_FIXTURE — real evaluation requires historical replay data"
    return data


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
                    result.route_reason,       # reliability_status placeholder (from routing)
                    "fresh",                   # data_freshness_status placeholder
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
