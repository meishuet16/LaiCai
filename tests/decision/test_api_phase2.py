"""
test_api_phase2.py — Integration tests for Phase 2 FastAPI endpoints.

Tests:
  - GET /v1/decisions/cases/{case_id}/proposals
  - GET /v1/decisions/cases/{case_id}/roi
"""

from fastapi.testclient import TestClient
import pytest

from backend.decision.main import app

client = TestClient(app)
AUTH_HEADERS = {"X-Tenant-Id": "tenant_abc"}


def test_health_and_frontend_routing_boundary_without_database():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["evidence_kind"] == "synthetic"

    response = client.post(
        "/v1/decisions/route",
        headers=AUTH_HEADERS,
        json={
            "tenant_id": "tenant_abc",
            "customer_id": "c02",
            "prediction_id": "demo_pred_c02",
            "prediction_run_id": "demo_run_20261010",
            "as_of": "2026-10-10T00:00:00Z",
            "generated_at": "2026-10-10T00:00:10Z",
            "status": "scored",
            "p_churn_7d": 0.30,
            "p_churn_14d": 0.45,
            "p_churn_30d": 0.70,
            "feature_version": "demo_features_v1",
            "model_version": "demo_model_v1",
            "calibration_version": "demo_calibration_v1",
            "label_policy_version": "demo_churn_policy_v1",
            "reliability": {"status": "sufficient_evidence", "reasons": []},
            "data_freshness": {
                "status": "fresh",
                "input_data_as_of": "2026-10-10T00:00:00Z",
                "stale_sources": [],
            },
            "uncertainty": {"status": "not_quantified", "method": "none", "intervals": None},
            "explanations_by_horizon": {},
            "mrr": {
                "tenant_id": "tenant_abc",
                "customer_id": "c02",
                "mrr_as_of": "2026-10-10T00:00:00Z",
                "mrr_minor": 10000,
                "currency": "MYR",
                "mrr_basis_version": "demo_mrr_policy_v1",
                "subscription_count": 1,
                "mrr_completeness": "complete",
            },
            "cooldown_active": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["route"] == "PRIORITY_REVIEW"
    assert response.json()["exposure_proxy_30d_minor"] == 7000


def test_get_proposals_demo_case():
    """GET /v1/decisions/cases/case_002/proposals returns live fact-based proposals."""
    resp = client.get("/v1/decisions/cases/case_002/proposals", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] == "case_002"
    assert data["customer_id"] == "cust_002"

    proposals = data["proposals"]
    action_codes = [p["action_code"] for p in proposals]

    # case_002 facts contain usage deviation and failed billing
    assert "ACCOUNT_CHECK_IN" in action_codes
    assert "PAYMENT_RECOVERY" in action_codes
    assert "NO_INTERVENTION" in action_codes

    # Verify fact references attached
    check_in = next(p for p in proposals if p["action_code"] == "ACCOUNT_CHECK_IN")
    assert len(check_in["supporting_fact_refs"]) > 0
    assert check_in["supporting_fact_refs"][0]["table"] == "usage_events"

    # Verify disabled actions list
    disabled = data["disabled_actions"]
    disabled_codes = [d["action_code"] for d in disabled]
    assert "TECH_SUPPORT_ESCALATION" in disabled_codes
    assert "CONDITIONAL_DISCOUNT" in disabled_codes


def test_get_roi_card_spec_arithmetic():
    """GET /v1/decisions/cases/case_002/roi computes exact spec numbers live."""
    resp = client.get(
        "/v1/decisions/cases/case_002/roi",
        params={
            "action_cost": 15000,
            "contribution_margin": 0.70,
            "assumed_reduction": 0.10,
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] == "case_002"
    assert data["contribution_value_minor"] == 84000
    assert data["break_even_abs_reduction_pp"] == 17.86
    assert data["break_even_share_of_baseline_pct"] == 27.47
    assert data["scenario_gross_value_minor"] == 8400
    assert data["scenario_net_value_minor"] == -6600
    assert data["scenario_roi_pct"] == -44.0
    assert data["break_even_achievable"] is True
    assert data["scenario_label"] == "SCENARIO_ONLY"
