"""
test_api_phase3.py — Integration tests for Phase 3 FastAPI endpoints.

Tests:
  - POST /v1/decisions/cases/{case_id}/approve
  - GET  /v1/decisions/cases/{case_id}/history
  - POST /v1/decisions/cases/{case_id}/outcomes
  - GET  /v1/decisions/evaluation
"""

from fastapi.testclient import TestClient
import pytest

from backend.decision.main import app

client = TestClient(app)
AUTH_HEADERS = {"X-Tenant-Id": "tenant_abc"}


def test_approve_case_live_endpoint():
    resp = client.post(
        "/v1/decisions/cases/case_002/approve",
        json={
            "proposal_id": "prop_002_a",
            "decision_type": "APPROVE",
            "reason": "Usage drop confirmed by usage_events. Scheduling check-in call.",
            "actor": "agent_sarah",
            "assigned_owner": "agent_sarah",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] == "case_002"
    assert data["case_status"] == "ASSIGNED"
    assert data["decision_type"] == "APPROVE"
    assert data["final_action"] == "ACCOUNT_CHECK_IN"
    assert data["actor"] == "agent_sarah"
    assert data["follow_up_anchor"] is not None
    assert "7d" in data["follow_up_due_at"]


def test_get_case_history_live_endpoint():
    resp = client.get("/v1/decisions/cases/case_002/history", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] == "case_002"
    assert len(data["events"]) > 0
    event_types = [e["event_type"] for e in data["events"]]
    assert "CASE_OPENED" in event_types


def test_record_outcome_live_endpoint():
    resp = client.post(
        "/v1/decisions/cases/case_002/outcomes",
        json={
            "follow_up_anchor": "2026-10-10T09:14:00Z",
            "horizon_days": 7,
            "observed_status": "active",
            "source_ref": "subscriptions.cust_002",
            "observation_coverage": "complete",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] == "case_002"
    assert data["horizon_days"] == 7
    assert data["observed_status"] == "active"
    assert data["note"] == "active_is_not_proof_of_retention_effectiveness"


def test_get_evaluation_live_endpoint():
    resp = client.get(
        "/v1/decisions/evaluation",
        params={"strategy": "C", "currency": "MYR", "k": 3},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["strategy"] == "C"
    assert data["currency"] == "MYR"
    assert data["k_slots"] == 3
    assert data["revenue_captured_label"] == "Subsequently Churned MRR Identified@K"
    assert data["revenue_captured_at_k"] is not None
    assert "historical_identification_coverage" in data["evaluation_label"]


def test_record_execution_live_endpoint():
    resp = client.post(
        "/v1/decisions/cases/case_002/execution",
        json={
            "proposal_id": "prop_002_a",
            "human_decision_id": "hd_002_123",
            "execution_status": "EXECUTED",
            "execution_note": "Called customer; offered 15% annual billing discount.",
            "actual_monetary_cost_minor": 4500,
            "actual_staff_minutes": 20,
            "executed_by": "agent_sarah",
            "follow_up_anchor": "2026-10-10T12:00:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "case_002"
    assert data["execution_status"] == "EXECUTED"
    assert data["actual_monetary_cost_minor"] == 4500
    assert data["actual_staff_minutes"] == 20
    assert data["currency"] == "MYR"
    assert data["executed_by"] == "agent_sarah"
    assert data["case_status"] == "FOLLOW_UP_DUE"
    assert "7d" in data["follow_up_due_at"]
    assert "14d" in data["follow_up_due_at"]
    assert "30d" in data["follow_up_due_at"]


def test_record_execution_failed_closes_case():
    resp = client.post(
        "/v1/decisions/cases/case_002/execution",
        json={
            "proposal_id": "prop_002_a",
            "human_decision_id": "hd_002_123",
            "execution_status": "FAILED",
            "execution_note": "Customer contact details invalid / unreachable.",
            "actual_monetary_cost_minor": 0,
            "actual_staff_minutes": 5,
            "executed_by": "agent_sarah",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_status"] == "FAILED"
    assert data["case_status"] == "CLOSED"


def test_missing_tenant_header_rejected():
    resp = client.post(
        "/v1/decisions/cases/case_002/approve",
        json={
            "proposal_id": "prop_002_a",
            "decision_type": "APPROVE",
            "reason": "Test without header",
            "actor": "agent_sarah",
        },
    )
    # FastAPI returns 422 (missing required header) or 401
    assert resp.status_code in (401, 422)

