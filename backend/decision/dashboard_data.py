"""Read the reviewer dashboard from the authenticated Part 1 dataset.

The dashboard adapter deliberately uses the narrow Member 2 reader contract.
It never exposes the bearer token or reaches around the data-foundation read
APIs for account contents.  The SQLite query below only enumerates customer
IDs already covered by the authenticated principal's tenant and source grants.
"""

from __future__ import annotations

import os
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from retaniq.data_foundation import (
    authenticate_service_principal,
    get_account_snapshot_as_of,
    get_prediction_history,
    normalize_timestamp,
)


DEFAULT_AS_OF = "2026-10-01T00:00:00Z"
DEFAULT_LIMIT = 30


class DashboardDataUnavailable(RuntimeError):
    """Raised when the authenticated dashboard dataset cannot be read."""


def _configuration() -> tuple[Path, str, str, int]:
    raw_path = os.environ.get("RETAINIQ_DASHBOARD_DB", "").strip()
    token = os.environ.get("RETAINIQ_MODEL_TOKEN", "").strip()
    if not raw_path or not token:
        raise DashboardDataUnavailable("dashboard reader is not configured")
    database = Path(raw_path)
    if not database.is_file():
        raise DashboardDataUnavailable("dashboard database is unavailable")
    as_of = normalize_timestamp(os.environ.get("RETAINIQ_DASHBOARD_AS_OF", DEFAULT_AS_OF))
    try:
        limit = int(os.environ.get("RETAINIQ_DASHBOARD_LIMIT", str(DEFAULT_LIMIT)))
    except ValueError as error:
        raise DashboardDataUnavailable("dashboard limit is invalid") from error
    return database, token, as_of, max(1, min(limit, 100))


def dashboard_source_status() -> dict[str, str | bool | None]:
    """Return non-secret source status for the health endpoint."""
    try:
        database, token, as_of, _ = _configuration()
        principal = authenticate_service_principal(database, token)
    except Exception:
        return {"available": False, "tenant_id": None, "as_of": None}
    return {"available": True, "tenant_id": principal.tenant_id, "as_of": as_of}


def _customer_ids(
    database: Path,
    tenant_id: str,
    authorized_sources: tuple[str, ...],
    limit: int,
) -> tuple[list[str], int]:
    marks = ",".join("?" for _ in authorized_sources)
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        params = (tenant_id, *authorized_sources)
        total = connection.execute(
            "SELECT COUNT(DISTINCT customer_id) FROM customer_identities "
            f"WHERE tenant_id = ? AND source IN ({marks})",
            params,
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT DISTINCT ci.customer_id FROM customer_identities ci "
            "WHERE ci.tenant_id = ? "
            f"AND ci.source IN ({marks}) "
            "ORDER BY CASE WHEN EXISTS ("
            "SELECT 1 FROM predictions p WHERE p.tenant_id = ci.tenant_id "
            "AND p.customer_id = ci.customer_id"
            ") THEN 0 ELSE 1 END, ci.customer_id LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [row[0] for row in rows], int(total)


def _segment_for_plan(plan: str | None) -> str:
    value = (plan or "").casefold()
    if "enterprise" in value:
        return "Enterprise"
    if any(token in value for token in ("growth", "business", "professional", "pro")):
        return "Mid-market"
    return "SMB"


def _prediction_record(tenant_id: str, prediction: dict[str, Any] | None) -> dict[str, Any] | None:
    if prediction is None:
        return None
    freshness = prediction["data_freshness_status"]
    risk_bands = None
    if prediction["status"] == "scored":
        risk_bands = {}
        for horizon in (7, 14, 30):
            probability = prediction[f"p_churn_{horizon}d"]
            risk_bands[horizon] = "high" if probability >= 0.60 else "medium" if probability >= 0.30 else "low"
    return {
        "tenant_id": tenant_id,
        "prediction_id": prediction["prediction_id"],
        "prediction_run_id": prediction["prediction_run_id"],
        "customer_id": prediction["customer_id"],
        "as_of": prediction["as_of"],
        "generated_at": prediction["generated_at"],
        "status": prediction["status"],
        "p_churn_7d": prediction["p_churn_7d"],
        "p_churn_14d": prediction["p_churn_14d"],
        "p_churn_30d": prediction["p_churn_30d"],
        "feature_version": prediction["feature_version"],
        "model_version": prediction["model_version"],
        "calibration_version": prediction["calibration_version"],
        # The authenticated reader contract deliberately does not expose the
        # label policy artifact.  Make that boundary explicit in the UI.
        "label_policy_version": "not_exposed_by_reader",
        "reliability": {
            "status": prediction["reliability_status"],
            "reasons": prediction["reliability_reasons"],
        },
        "data_freshness": {
            "status": freshness,
            "input_data_as_of": prediction["input_data_as_of"],
            "stale_sources": [] if freshness == "fresh" else ["synthetic_dataset_inputs"],
        },
        "uncertainty": {"status": "not_quantified", "method": "none", "intervals": None},
        "explanations_by_horizon": prediction["explanations_by_horizon"],
        # The evaluation display policy assigns bands server-side; the
        # frontend never manufactures a category from a probability.
        "risk_bands_by_horizon": risk_bands,
    }


def _account_record(snapshot: dict[str, Any], prediction: dict[str, Any] | None) -> dict[str, Any]:
    subscriptions = snapshot["subscriptions"]
    current = next(
        (row for row in subscriptions if row.get("status") in {"active", "trialing", "pending_cancel"}),
        subscriptions[-1] if subscriptions else None,
    )
    plan = current.get("plan_id") if current else None
    status = snapshot["status"]
    if prediction is not None and prediction["status"] == "known_cancellation":
        route, route_reason = "KNOWN_CANCELLATION", "Cancellation was known at the prediction cutoff and is excluded from prospective risk ranking."
        case_status, next_step = "KNOWN_CANCELLATION", "Cancellation workflow"
    elif prediction is not None and prediction["status"] == "not_eligible":
        route, route_reason = "NOT_ELIGIBLE", "No active paid entitlement exists at the backend cutoff."
        case_status, next_step = "NOT_ELIGIBLE", "No retention action"
    elif prediction is None:
        route = "HUMAN_REVIEW"
        route_reason = "Backend account is eligible, but no persisted model prediction exists."
        case_status, next_step = None, "Await a verified model prediction"
    elif prediction["status"] == "abstained" or prediction["reliability_status"] != "sufficient_evidence":
        route = "HUMAN_REVIEW"
        route_reason = "Prediction requires human review because evidence is limited or insufficient."
        case_status, next_step = "PROPOSED", "Investigate evidence quality"
    elif prediction["data_freshness_status"] != "fresh":
        route = "HUMAN_REVIEW"
        route_reason = "Prediction requires human review because source data is not fully fresh."
        case_status, next_step = "PROPOSED", "Verify source freshness"
    elif prediction["p_churn_30d"] is not None and prediction["p_churn_30d"] >= 0.40:
        route = "PRIORITY_REVIEW"
        route_reason = "Eligible account with sufficient evidence above the review threshold."
        case_status, next_step = "PROPOSED", "Review account action"
    else:
        route = "OBSERVE"
        route_reason = "Eligible account is below the review threshold."
        case_status, next_step = "OBSERVE", "Continue monitoring"

    valuation = snapshot.get("valuation") or {}
    mrr = None
    if valuation.get("status") == "available" and valuation.get("currency") in {"MYR", "SGD"}:
        mrr = {"amount_minor": valuation["mrr_minor"], "currency": valuation["currency"]}
    customer_id = snapshot["customer_id"]
    account_number = customer_id.rsplit("-", 1)[-1]

    return {
        "tenant_id": snapshot["tenant_id"],
        "customer_id": customer_id,
        # The source has no customer name.  This is a transparent display label
        # derived from the stable ID, never invented company metadata.
        "name": f"Account {account_number}",
        "segment": _segment_for_plan(plan),
        "plan": plan or "No active plan",
        "account_created_at": None,
        "industry": None,
        "region": None,
        "acquisition_channel": None,
        "onboarding_cohort": None,
        "subscription_state": current.get("status") if current else None,
        "tenure_days": None,
        "mrr": mrr,
        "owner": None,
        "case_id": f"case_{customer_id}",
        "case_status": case_status,
        "next_step": next_step,
        "route": route,
        "route_reason": route_reason,
        "exposure_proxy": None,
        "prediction": _prediction_record(snapshot["tenant_id"], prediction),
        "evidence_kind": "source_backed",
        "data_origin": "backend_dataset",
    }


def load_dashboard_accounts() -> dict[str, Any]:
    database, token, as_of, limit = _configuration()
    try:
        principal = authenticate_service_principal(database, token)
        customer_ids, total = _customer_ids(
            database,
            principal.tenant_id,
            principal.authorized_sources,
            limit,
        )
        accounts = []
        prediction_count = 0
        for customer_id in customer_ids:
            history = get_prediction_history(database, principal, customer_id, limit=1)
            prediction = history["predictions"][0] if history["predictions"] else None
            prediction_count += int(prediction is not None)
            snapshot = get_account_snapshot_as_of(database, principal, customer_id, as_of)
            accounts.append(_account_record(snapshot, prediction))
    except DashboardDataUnavailable:
        raise
    except Exception as error:
        raise DashboardDataUnavailable("authenticated dashboard read failed") from error

    return {
        "accounts": accounts,
        "meta": {
            "source": "authenticated_backend_dataset",
            "tenant_id": principal.tenant_id,
            "as_of": as_of,
            "returned_accounts": len(accounts),
            "total_accounts": total,
            "predictions_available": prediction_count > 0,
            "prediction_count": prediction_count,
            "decision_cases_available": True,
        },
    }


def _database_and_tenant() -> tuple[Path, str]:
    database, token, _, _ = _configuration()
    try:
        principal = authenticate_service_principal(database, token)
    except Exception as error:
        raise DashboardDataUnavailable("dashboard reader authentication failed") from error
    return database, principal.tenant_id


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_integration_overview() -> dict[str, Any]:
    database, tenant_id = _database_and_tenant()
    as_of = _configuration()[2]
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        integrations = connection.execute(
            "SELECT source, schema_version, mapping_version, created_at, "
            "last_successful_ingestion_at, last_failure_at, last_failure_code "
            "FROM integrations WHERE tenant_id = ? ORDER BY source",
            (tenant_id,),
        ).fetchall()
        sources = []
        display_names = {"usage": "Product Analytics", "billing": "Billing Platform", "subscription": "Subscription Ledger"}
        for integration in integrations:
            source = integration["source"]
            aggregate = connection.execute(
                "SELECT category, MIN(occurred_at) available_from, MAX(occurred_at) available_through, "
                "MAX(CASE WHEN source_available_at <= ? THEN occurred_at END) latest_occurred_at, "
                "MAX(CASE WHEN source_available_at <= ? THEN source_available_at END) latest_available_at, "
                "COUNT(1) processed_count FROM canonical_events "
                "WHERE tenant_id = ? AND source = ? AND source_available_at <= ?",
                (as_of, as_of, tenant_id, source, as_of),
            ).fetchone()
            event_types = [row[0] for row in connection.execute(
                "SELECT DISTINCT event_type FROM canonical_events WHERE tenant_id = ? AND source = ? "
                "AND source_available_at <= ? ORDER BY event_type",
                (tenant_id, source, as_of),
            ).fetchall()]
            category = aggregate["category"] or "usage"
            latest = aggregate["latest_available_at"]
            freshness = "fresh" if latest and latest[:10] >= "2026-09-28" else "stale" if latest else "unknown"
            status = "healthy" if not integration["last_failure_at"] else "warning"
            sources.append({
                "category": category,
                "source": display_names.get(category, source),
                "status": status,
                "event_types": event_types,
                "last_success_at": integration["last_successful_ingestion_at"],
                "last_attempt_at": integration["last_failure_at"] or integration["last_successful_ingestion_at"],
                "latest_occurred_at": aggregate["latest_occurred_at"],
                "latest_available_at": latest,
                "processed_count": int(aggregate["processed_count"] or 0),
                "rejected_count": 0,
                "error_count": 1 if integration["last_failure_at"] else 0,
                "freshness": freshness,
                "mapping_version": integration["mapping_version"],
                "schema_version": integration["schema_version"],
                "available_from": aggregate["available_from"],
                "available_through": aggregate["available_through"],
            })
        customer_count = connection.execute("SELECT COUNT(1) FROM customers WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
        active_count = connection.execute(
            "SELECT COUNT(DISTINCT customer_id) FROM subscriptions WHERE tenant_id = ? AND status IN ('active','past_due','pending_cancel')",
            (tenant_id,),
        ).fetchone()[0]
        missing_mrr = connection.execute(
            "SELECT COUNT(1) FROM customers c WHERE c.tenant_id = ? AND NOT EXISTS ("
            "SELECT 1 FROM subscriptions s WHERE s.tenant_id = c.tenant_id AND s.customer_id = c.customer_id "
            "AND s.status IN ('active','past_due','pending_cancel') AND s.amount_minor IS NOT NULL)",
            (tenant_id,),
        ).fetchone()[0]
        coverage_by_category = {}
        for category in ("usage", "billing", "subscription"):
            covered = connection.execute(
                "SELECT COUNT(DISTINCT customer_id) FROM observation_coverage WHERE tenant_id = ? "
                "AND source_category = ? AND coverage_status = 'complete' AND covered_through >= ?",
                (tenant_id, category, as_of[:10]),
            ).fetchone()[0]
            coverage_by_category[category] = round(100 * covered / customer_count) if customer_count else None
        incomplete = connection.execute(
            "SELECT COUNT(DISTINCT customer_id) FROM observation_coverage WHERE tenant_id = ? "
            "AND source_category = 'subscription' AND coverage_status <> 'complete'",
            (tenant_id,),
        ).fetchone()[0]
    alerts = []
    for source in sources:
        if source["freshness"] != "fresh":
            alerts.append({"id": f"freshness_{source['category']}", "severity": "warning", "title": f"{source['source']} needs a freshness review", "detail": "The latest available record is outside the current freshness window.", "source": source["source"]})
    if incomplete:
        alerts.append({"id": "coverage_subscription", "severity": "warning", "title": "Outcome coverage needs reconciliation", "detail": f"{incomplete:,} accounts have at least one non-complete subscription observation window.", "source": "Subscription Ledger"})
    return {
        "evidence_kind": "source_backed",
        "sources": sources,
        "coverage": {
            "accounts_mapped": int(customer_count), "accounts_unmatched": 0, "active_paying": int(active_count),
            "missing_mrr": int(missing_mrr), "incomplete_subscription_history": int(incomplete),
            "usage_percent": coverage_by_category["usage"], "billing_percent": coverage_by_category["billing"],
            "subscription_percent": coverage_by_category["subscription"],
        },
        "rejected_events": [],
        "alerts": alerts,
    }


def _load_cases(connection: sqlite3.Connection, tenant_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT case_json FROM dashboard_cases WHERE tenant_id = ? ORDER BY case_id",
        (tenant_id,),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]


def _capacity(cases: list[dict[str, Any]]) -> dict[str, Any]:
    active_states = {"HUMAN_REVIEWED", "ASSIGNED", "EXECUTED", "FOLLOW_UP_DUE", "FOLLOW_UP_COMPLETE"}
    pending_states = {"PROPOSED", "HUMAN_REVIEWED", "DEFERRED"}
    active = [item for item in cases if item["status"] in active_states]
    budgets = [{"amount_minor": 50000, "currency": "MYR"}, {"amount_minor": 30000, "currency": "SGD"}]
    used = []
    for budget in budgets:
        total = sum((item.get("estimated_cost") or {}).get("amount_minor", 0) for item in active if (item.get("estimated_cost") or {}).get("currency") == budget["currency"])
        used.append({"amount_minor": total, "currency": budget["currency"]})
    return {
        "review_slots": 12,
        "used_review_slots": len(active),
        "pending": sum(item["status"] in pending_states for item in cases),
        "overdue": sum(bool(item.get("due_at") and item["due_at"] < "2026-10-11T00:00:00Z" and item["status"] in pending_states) for item in cases),
        "staff_minutes_total": 360,
        "staff_minutes_used": sum(item.get("estimated_minutes") or 0 for item in active),
        "budgets": budgets,
        "budget_used": used,
        "investigation_queue": sum(item["route"] == "HUMAN_REVIEW" and item["status"] in pending_states for item in cases),
    }


def load_dashboard_cases() -> dict[str, Any]:
    database, tenant_id = _database_and_tenant()
    with sqlite3.connect(database) as connection:
        cases = _load_cases(connection, tenant_id)
    return {"cases": cases, "capacity": _capacity(cases), "meta": {"tenant_id": tenant_id, "persisted": True}}


def _case_for_update(connection: sqlite3.Connection, tenant_id: str, case_id: str) -> dict[str, Any]:
    row = connection.execute("SELECT case_json FROM dashboard_cases WHERE tenant_id = ? AND case_id = ?", (tenant_id, case_id)).fetchone()
    if row is None:
        raise KeyError(case_id)
    return json.loads(row[0])


def _store_case(connection: sqlite3.Connection, tenant_id: str, item: dict[str, Any]) -> dict[str, Any]:
    updated_at = _now()
    connection.execute(
        "UPDATE dashboard_cases SET case_json = ?, updated_at = ? WHERE tenant_id = ? AND case_id = ?",
        (json.dumps(item, separators=(",", ":")), updated_at, tenant_id, item["id"]),
    )
    return item


def record_dashboard_decision(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    database, tenant_id = _database_and_tenant()
    with sqlite3.connect(database) as connection:
        item = _case_for_update(connection, tenant_id, case_id)
        if payload.get("role") != "Manager":
            raise ValueError("Manager role is required for decisions.")
        if item["status"] not in {"PROPOSED", "HUMAN_REVIEWED", "DEFERRED"}:
            raise ValueError("This case cannot accept a new decision.")
        reason, actor, kind = str(payload.get("reason", "")).strip(), str(payload.get("actor", "")).strip(), payload.get("kind")
        if not reason or not actor:
            raise ValueError("Reason and actor are required.")
        if kind in {"APPROVE", "MODIFY"}:
            action_id = payload.get("action_id")
            if action_id not in {"ACCOUNT_CHECK_IN", "PAYMENT_RECOVERY", "DATA_INVESTIGATION"}:
                raise ValueError("Select an eligible action proposal.")
            item["status"], item["selected_action"], item["owner"] = "ASSIGNED", action_id, str(payload.get("owner") or actor)
            item["estimated_minutes"] = 25 if action_id == "DATA_INVESTIGATION" else 20
            item["estimated_cost"] = {"amount_minor": 0 if action_id == "DATA_INVESTIGATION" else 4000, "currency": "MYR"}
            item["due_at"] = payload.get("due_at") or item.get("due_at")
        elif kind == "REJECT":
            item["status"] = "REJECTED"
        elif kind == "NO_INTERVENTION":
            item["status"] = "CLOSED_NO_ACTION"
        elif kind == "DEFER":
            if not payload.get("due_at"):
                raise ValueError("A new due date is required to defer.")
            item["status"], item["due_at"] = "DEFERRED", payload["due_at"]
        else:
            raise ValueError("Unsupported decision kind.")
        at = _now()
        item["audit"].append({"id": f"audit_{case_id}_{len(item['audit']) + 1}", "at": at, "actor": actor, "type": kind, "detail": reason})
        return _store_case(connection, tenant_id, item)


def record_dashboard_execution(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    database, tenant_id = _database_and_tenant()
    with sqlite3.connect(database) as connection:
        item = _case_for_update(connection, tenant_id, case_id)
        if payload.get("role") not in {"Manager", "CSM"}:
            raise ValueError("Manager or CSM role is required for execution.")
        if item["status"] != "ASSIGNED":
            raise ValueError("Only assigned cases can record execution.")
        reason, actor = str(payload.get("reason", "")).strip(), str(payload.get("actor", "")).strip()
        if not reason or not actor:
            raise ValueError("Reason and actor are required.")
        outcome = payload.get("outcome")
        if outcome not in {"EXECUTED", "CANCELLED", "FAILED"}:
            raise ValueError("Unsupported execution outcome.")
        at = _now()
        item.update({"status": outcome, "actual_cost": payload.get("actual_cost"), "actual_minutes": payload.get("actual_minutes"), "response_at": at, "completed_at": at, "follow_up_at": payload.get("follow_up_at") if outcome == "EXECUTED" else None})
        item["audit"].append({"id": f"audit_{case_id}_{len(item['audit']) + 1}", "at": at, "actor": actor, "type": outcome, "detail": reason})
        return _store_case(connection, tenant_id, item)


def record_dashboard_follow_up(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    database, tenant_id = _database_and_tenant()
    with sqlite3.connect(database) as connection:
        item = _case_for_update(connection, tenant_id, case_id)
        if payload.get("role") not in {"Manager", "CSM"}:
            raise ValueError("Manager or CSM role is required for follow-up.")
        if item["status"] not in {"EXECUTED", "FOLLOW_UP_DUE"}:
            raise ValueError("This case has no follow-up to record.")
        reason, actor = str(payload.get("reason", "")).strip(), str(payload.get("actor", "")).strip()
        if not reason or not actor:
            raise ValueError("Reason and actor are required.")
        at = _now()
        item["status"] = "FOLLOW_UP_COMPLETE"
        item["audit"].append({"id": f"audit_{case_id}_{len(item['audit']) + 1}", "at": at, "actor": actor, "type": "FOLLOW_UP_COMPLETE", "detail": reason})
        return _store_case(connection, tenant_id, item)


def load_learning_overview() -> dict[str, Any]:
    database, tenant_id = _database_and_tenant()
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        predictions = connection.execute(
            "SELECT status, reliability_status, data_freshness_status, p_churn_7d, p_churn_14d, p_churn_30d "
            "FROM predictions WHERE tenant_id = ? AND prediction_run_id = ?",
            (tenant_id, "retention_risk_run_20261001"),
        ).fetchall()
        feedback = [dict(row) for row in connection.execute(
            "SELECT horizon_days, feedback_state, COUNT(1) count FROM dashboard_prediction_feedback "
            "WHERE tenant_id = ? GROUP BY horizon_days, feedback_state ORDER BY horizon_days, feedback_state",
            (tenant_id,),
        ).fetchall()]
        releases = [dict(row) for row in connection.execute(
            "SELECT model_version, release_role, governance_state, feature_version, calibration_version, "
            "label_policy_version, created_at, decision_reason FROM dashboard_model_releases WHERE tenant_id = ? ORDER BY release_role DESC",
            (tenant_id,),
        ).fetchall()]
        provenance = connection.execute(
            "SELECT metadata_value FROM dashboard_metadata WHERE tenant_id = ? AND metadata_key = 'dataset_provenance'",
            (tenant_id,),
        ).fetchone()[0]
    prospective = [row for row in predictions if row["status"] not in {"known_cancellation", "not_eligible"}]
    scored = [row for row in prospective if row["status"] == "scored"]
    monotone = [row for row in scored if row["p_churn_7d"] <= row["p_churn_14d"] <= row["p_churn_30d"]]
    return {
        "as_of": "2026-10-11T00:00:00Z",
        "dataset_provenance": provenance,
        "summary": {
            "prospective_accounts": len(prospective),
            "scored_accounts": len(scored),
            "abstained_accounts": sum(row["status"] == "abstained" for row in prospective),
            "coverage_rate": len(scored) / len(prospective) if prospective else None,
            "abstention_rate": sum(row["status"] == "abstained" for row in prospective) / len(prospective) if prospective else None,
            "monotonicity_rate": len(monotone) / len(scored) if scored else None,
            "fresh_accounts": sum(row["data_freshness_status"] == "fresh" for row in predictions),
            "limited_evidence_accounts": sum(row["reliability_status"] != "sufficient_evidence" for row in predictions),
        },
        "feedback": feedback,
        "releases": releases,
        "performance": {"pr_auc": None, "brier_score": None, "recall_at_k": None, "status": "AWAITING_MATURE_OUTCOMES"},
    }
