"""
End-to-end: prediction -> routing -> ranking -> action -> approval -> outcome -> evaluation.
Run: pytest tests/decision/test_end_to_end.py -v
"""

import pytest
from backend.decision.router_engine import route_account
from backend.decision.ranker import rank_top_k
from backend.decision.action_catalog import propose_actions
from backend.decision.workflow import approve_case
from backend.decision.outcomes import record_outcome
from backend.decision.enums import Route, HumanDecision


def test_full_pipeline_happy_path():
    # 1. Prediction payload (mock from Member 2)
    prediction = {
        "prediction_id": "pred_e2e_001",
        "customer_id": "cust_e2e",
        "as_of": "2026-10-10T00:00:00Z",
        "status": "scored",
        "p_churn_7d": 0.20,
        "p_churn_14d": 0.45,
        "p_churn_30d": 0.80,
        "reliability": {"status": "sufficient_evidence"},
        "data_freshness": {"status": "fresh"},
    }
    # 2. MRR payload (mock from Member 1)
    mrr = {"mrr_minor": 120000, "currency": "MYR", "mrr_completeness": "complete"}

    # 3. Route
    case_input = {**prediction, **mrr, "in_cooldown": False}
    route = route_account(case_input)
    assert route == Route.PRIORITY_REVIEW

    # 4. Rank
    ranked = rank_top_k([case_input], k=1)
    assert len(ranked) == 1
    assert ranked[0]["customer_id"] == "cust_e2e"

    # 5. Propose actions
    facts = {"has_failed_payment": True}
    proposals = propose_actions(facts)
    assert any(p["action_code"] == "PAYMENT_RECOVERY" for p in proposals)

    # 6. Approve
    case = {"case_id": "case_e2e", "status": "PROPOSED",
            "estimated_cost_minor": 5000, "estimated_staff_minutes": 15,
            "action_mode": "operational"}
    result = approve_case(case, decision=HumanDecision.APPROVE,
                          actor="manager_1",
                          budget_remaining_minor=100000,
                          staff_remaining_minutes=100)
    assert result["status"] in ("ASSIGNED", "HUMAN_REVIEWED")

    # 7. Record outcome
    obs = record_outcome(case_id="case_e2e", horizon_days=30,
                         observed_state="active", source="subscription_event")
    assert obs["observed_state"] == "active"
    # Guardrail: active is NOT proof of retention
    assert obs.get("retained") is not True