"""Create a reviewer-safe dashboard database with evaluation predictions.

The source SQLite file is treated as read-only.  A consistent SQLite backup is
made first, then prediction records are written through the authenticated Part
1 persistence API.  The resulting reader token is protected with Windows
DPAPI; no credential is printed or written as plaintext.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from retaniq.data_foundation import (
    authenticate_service_principal,
    create_service_principal,
    get_account_snapshot_as_of,
    store_prediction,
)
from retaniq.secret_store import store_dpapi_secret


DATASET_ID = "synthetic-saas-v1-2-standard-s2026-970a9d231e68"
TENANT_ID = "tenant-01"
AS_OF = "2026-10-01T00:00:00Z"
GENERATED_AT = "2026-10-01T00:05:00Z"
RUN_ID = "retention_risk_run_20261001"

DEFAULT_SOURCE = (
    Path.home()
    / "RetainIQ-private"
    / "synthetic_saas_v1_2"
    / "working"
    / "member1-p0"
    / f"{DATASET_ID}-tenant-01-reader.sqlite3"
)
DEFAULT_OUTPUT_DIR = (
    Path.home() / "RetainIQ-private" / "synthetic_saas_v1_2" / "working" / "dashboard-workspace"
)


RISK_CURVES: tuple[tuple[float, float, float], ...] = (
    # High-risk review candidates.
    (0.34, 0.56, 0.78),
    (0.29, 0.51, 0.73),
    (0.25, 0.46, 0.68),
    (0.21, 0.41, 0.63),
    (0.19, 0.37, 0.61),
    (0.17, 0.34, 0.60),
    # Medium-risk accounts, with several above the decision threshold.
    (0.16, 0.31, 0.57),
    (0.15, 0.29, 0.53),
    (0.14, 0.27, 0.49),
    (0.13, 0.25, 0.46),
    (0.12, 0.23, 0.43),
    (0.11, 0.21, 0.39),
    (0.10, 0.20, 0.36),
    (0.09, 0.18, 0.32),
    # Low-risk observe accounts.
    (0.08, 0.15, 0.28),
    (0.07, 0.14, 0.25),
    (0.06, 0.12, 0.22),
    (0.05, 0.10, 0.19),
    (0.04, 0.09, 0.16),
    (0.03, 0.07, 0.13),
    (0.02, 0.05, 0.09),
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"{DATASET_ID}-dashboard.sqlite3",
    )
    parser.add_argument(
        "--reader-secret",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "dashboard-reader.dpapi",
    )
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def _backup(source: Path, target: Path, *, replace: bool) -> None:
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    if source == target:
        raise ValueError("source and target must be different files")
    if not source.is_file():
        raise FileNotFoundError(f"source database does not exist: {source}")
    if target.exists() and not replace:
        raise FileExistsError(f"target already exists (pass --replace): {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    source_uri = source.as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_connection:
        with sqlite3.connect(target) as target_connection:
            source_connection.backup(target_connection)


def _sources(database: Path) -> tuple[str, ...]:
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT source FROM integrations WHERE tenant_id = ? ORDER BY source",
            (TENANT_ID,),
        ).fetchall()
    values = tuple(row[0] for row in rows)
    if not values:
        raise RuntimeError("the evaluation tenant has no configured sources")
    return values


def _candidate_ids(database: Path) -> list[str]:
    """Prioritize cancellations, then inactive and active accounts."""
    with sqlite3.connect(database) as connection:
        known = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT customer_id FROM subscriptions "
                "WHERE tenant_id = ? AND cancellation_requested_at IS NOT NULL ORDER BY customer_id",
                (TENANT_ID,),
            ).fetchall()
        ]
        ended = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT customer_id FROM subscriptions "
                "WHERE tenant_id = ? AND status = 'ended' ORDER BY customer_id",
                (TENANT_ID,),
            ).fetchall()
        ]
        all_ids = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT customer_id FROM customer_identities "
                "WHERE tenant_id = ? ORDER BY customer_id",
                (TENANT_ID,),
            ).fetchall()
        ]
    return list(dict.fromkeys((*known, *ended, *all_ids)))


def _select_accounts(database: Path, principal: Any) -> list[dict[str, Any]]:
    # The STANDARD tenant has cancellation history but no still-active
    # pending-cancellation accounts at this cutoff.  Select six ineligible
    # accounts, then represent the first two historical cancellations as the
    # evaluation cohort's explicit "known cancellation / not a forecast" records.
    targets = {"not_eligible": 6, "eligible": 24}
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in targets}
    for customer_id in _candidate_ids(database):
        snapshot = get_account_snapshot_as_of(database, principal, customer_id, AS_OF)
        status = snapshot["status"]
        if status in buckets and len(buckets[status]) < targets[status]:
            buckets[status].append(snapshot)
        if all(len(buckets[key]) == count for key, count in targets.items()):
            break
    missing = {key: count - len(buckets[key]) for key, count in targets.items() if len(buckets[key]) < count}
    if missing:
        raise RuntimeError(f"source dataset cannot satisfy the required dashboard status mix: {missing}")
    non_forecast = buckets["not_eligible"]
    for snapshot in non_forecast[:2]:
        snapshot["dashboard_prediction_status"] = "known_cancellation"
    return [*buckets["eligible"], *non_forecast]


def _explanations(index: int) -> dict[str, Any]:
    direction = "negative" if index < 14 else "positive"
    feature = "usage_frequency_30d" if index % 2 == 0 else "session_recency_days"
    return {
        str(horizon): {
            "drivers": [
                {
                    "feature": feature,
                    "direction": direction,
                    "contribution": round((index + 2) / (horizon + 30), 3),
                },
                {
                    "feature": "usage_trend_30d",
                    "direction": direction,
                    "contribution": round((index + 1) / (horizon + 50), 3),
                },
            ]
        }
        for horizon in (7, 14, 30)
    }


def _prediction(snapshot: dict[str, Any], index: int) -> dict[str, Any]:
    status = snapshot.get("dashboard_prediction_status", snapshot["status"])
    probabilities: tuple[float | None, float | None, float | None]
    reliability = "sufficient_evidence"
    freshness = "fresh"
    reasons: list[str] = []
    explanations: dict[str, Any] = {}

    if status == "eligible" and index < len(RISK_CURVES):
        status = "scored"
        probabilities = RISK_CURVES[index]
        explanations = _explanations(index)
        # A few numeric scores deliberately exercise conservative review gates.
        if index in {4, 9, 16}:
            reliability = "limited_evidence"
            freshness = "partially_stale"
            reasons = ["feature_quality_limited", "partial_source_coverage"]
    elif status == "eligible":
        status = "abstained"
        probabilities = (None, None, None)
        reliability = "insufficient_evidence"
        freshness = "unknown"
        reasons = ["insufficient_event_history", "unknown_observation_coverage"]
    else:
        probabilities = (None, None, None)
        reliability = "insufficient_evidence"
        freshness = "unknown"
        reasons = ["model_applicability_limited"]

    return {
        "prediction_id": f"pred_20261001_{index + 1:03d}",
        "prediction_run_id": RUN_ID,
        "customer_id": snapshot["customer_id"],
        "as_of": AS_OF,
        "generated_at": GENERATED_AT,
        "status": status,
        "p_churn_7d": probabilities[0],
        "p_churn_14d": probabilities[1],
        "p_churn_30d": probabilities[2],
        "feature_version": "behavioral_features_v1_2",
        "model_version": "retention_risk_v1_2",
        "calibration_version": "calibration_v1_2",
        "label_policy_version": "churn_policy_v1_2",
        "reliability_status": reliability,
        "reliability_reasons": reasons,
        "data_freshness_status": freshness,
        "input_data_as_of": snapshot["input_data_as_of"],
        "explanations_by_horizon": explanations,
    }


def _delete_temporary_writer(database: Path, service_principal_id: str) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM service_principals WHERE service_principal_id = ? AND tenant_id = ?",
            (service_principal_id, TENANT_ID),
        )


def _route(snapshot: dict[str, Any], prediction: dict[str, Any]) -> tuple[str, str]:
    if prediction["status"] == "known_cancellation":
        return "KNOWN_CANCELLATION", "Cancellation was known at the prediction cutoff and is excluded from prospective risk ranking."
    if prediction["status"] == "not_eligible":
        return "NOT_ELIGIBLE", "No active paid entitlement existed at the prediction cutoff."
    if prediction["status"] == "abstained" or prediction["reliability_status"] != "sufficient_evidence":
        return "HUMAN_REVIEW", "Evidence is limited or insufficient, so the account requires human review."
    if prediction["data_freshness_status"] != "fresh":
        return "HUMAN_REVIEW", "One or more source inputs are not fully fresh and require verification."
    if prediction["p_churn_30d"] is not None and prediction["p_churn_30d"] >= 0.40:
        return "PRIORITY_REVIEW", "Eligible account with sufficient evidence above the review threshold."
    return "OBSERVE", "Eligible account is below the review threshold."


def _case_record(snapshot: dict[str, Any], prediction: dict[str, Any], index: int) -> dict[str, Any]:
    route, reason = _route(snapshot, prediction)
    status_by_route = {
        "PRIORITY_REVIEW": "PROPOSED",
        "HUMAN_REVIEW": "PROPOSED",
        "OBSERVE": "OBSERVE",
        "KNOWN_CANCELLATION": "KNOWN_CANCELLATION",
        "NOT_ELIGIBLE": "NOT_ELIGIBLE",
    }
    status = status_by_route[route]
    owner = None
    selected_action = None
    estimated_cost = None
    estimated_minutes = 0
    actual_cost = None
    actual_minutes = None
    completed_at = None
    follow_up_at = None
    due_at = "2026-10-13T12:00:00Z" if route in {"PRIORITY_REVIEW", "HUMAN_REVIEW"} else None
    audit = [{
        "id": f"audit_{index + 1:03d}_route",
        "at": GENERATED_AT,
        "actor": "retention_policy_v1_2",
        "type": "ROUTED",
        "detail": f"{route}: {reason}",
    }]
    currency = (snapshot.get("valuation") or {}).get("currency") or "MYR"
    if route == "PRIORITY_REVIEW" and index == 0:
        status, owner, selected_action = "ASSIGNED", "Aina Rahman", "ACCOUNT_CHECK_IN"
        estimated_cost, estimated_minutes = {"amount_minor": 4000, "currency": currency}, 20
        audit.append({"id": "audit_001_approve", "at": "2026-10-02T09:15:00Z", "actor": "Manager", "type": "APPROVE", "detail": "Assigned an account check-in with budget and capacity reserved."})
    elif route == "PRIORITY_REVIEW" and index == 1:
        status, owner, selected_action = "FOLLOW_UP_DUE", "Jasmine Lee", "ACCOUNT_CHECK_IN"
        estimated_cost, estimated_minutes = {"amount_minor": 4000, "currency": currency}, 20
        actual_cost, actual_minutes = {"amount_minor": 3500, "currency": currency}, 18
        completed_at, follow_up_at = "2026-10-03T11:00:00Z", "2026-10-10T12:00:00Z"
        audit.extend([
            {"id": "audit_002_approve", "at": "2026-10-02T10:00:00Z", "actor": "Manager", "type": "APPROVE", "detail": "Assigned an account check-in after reviewing account evidence."},
            {"id": "audit_002_execute", "at": completed_at, "actor": "CSM", "type": "EXECUTED", "detail": "Account check-in completed; follow-up scheduled."},
        ])
    elif route == "HUMAN_REVIEW" and index == 4:
        status, owner, selected_action = "DEFERRED", "Nur Izzati", None
        due_at = "2026-10-14T12:00:00Z"
        audit.append({"id": "audit_005_defer", "at": "2026-10-02T10:30:00Z", "actor": "Manager", "type": "DEFER", "detail": "Deferred until source freshness is rechecked."})

    if prediction["status"] == "scored":
        facts = [f"Stored 30-day churn risk is {round(prediction['p_churn_30d'] * 100)}%." ]
    elif prediction["status"] == "abstained":
        facts = ["The prediction abstained because the available evidence did not satisfy reliability gates."]
    elif route == "KNOWN_CANCELLATION":
        facts = ["The cancellation signal was already available at the cutoff."]
    else:
        facts = ["The account did not meet paid-entitlement eligibility at the cutoff."]
    warnings = []
    if prediction["data_freshness_status"] != "fresh":
        warnings.append("Source freshness requires review before any customer-facing action.")

    return {
        "id": f"case_{snapshot['customer_id']}",
        "customer_id": snapshot["customer_id"],
        "route": route,
        "route_reason": reason,
        "status": status,
        "owner": owner,
        "created_at": GENERATED_AT,
        "due_at": due_at,
        "fact_ids": [prediction["prediction_id"]],
        "facts": facts,
        "warnings": warnings,
        "proposed_action": "ACCOUNT_CHECK_IN" if route == "PRIORITY_REVIEW" else "DATA_INVESTIGATION" if route == "HUMAN_REVIEW" else None,
        "selected_action": selected_action,
        "estimated_cost": estimated_cost,
        "estimated_minutes": estimated_minutes,
        "actual_cost": actual_cost,
        "actual_minutes": actual_minutes,
        "response_at": completed_at,
        "completed_at": completed_at,
        "follow_up_at": follow_up_at,
        "audit": audit,
    }


def _seed_dashboard_state(database: Path, snapshots: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> None:
    cases = [_case_record(snapshot, prediction, index) for index, (snapshot, prediction) in enumerate(zip(snapshots, predictions, strict=True))]
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE dashboard_cases (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                case_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, case_id)
            );
            CREATE TABLE dashboard_prediction_feedback (
                tenant_id TEXT NOT NULL,
                prediction_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                horizon_days INTEGER NOT NULL,
                feedback_state TEXT NOT NULL,
                reason TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, prediction_id, horizon_days)
            );
            CREATE TABLE dashboard_model_releases (
                tenant_id TEXT NOT NULL,
                model_version TEXT NOT NULL,
                release_role TEXT NOT NULL,
                governance_state TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                calibration_version TEXT NOT NULL,
                label_policy_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                decision_reason TEXT NOT NULL,
                PRIMARY KEY (tenant_id, model_version)
            );
            CREATE TABLE dashboard_metadata (
                tenant_id TEXT NOT NULL,
                metadata_key TEXT NOT NULL,
                metadata_value TEXT NOT NULL,
                PRIMARY KEY (tenant_id, metadata_key)
            );
            """
        )
        connection.executemany(
            "INSERT INTO dashboard_cases VALUES (?, ?, ?, ?, ?)",
            [(TENANT_ID, case["id"], case["customer_id"], json.dumps(case, separators=(",", ":")), GENERATED_AT) for case in cases],
        )
        feedback_rows = []
        for prediction in predictions:
            for horizon in (7, 14, 30):
                if prediction["status"] in {"known_cancellation", "not_eligible"}:
                    state, reason = "INELIGIBLE", "No prospective forecast was issued for this account."
                elif horizon == 7:
                    state, reason = "INCOMPLETE", "The observation window ended, but outcome reconciliation is not complete."
                else:
                    state, reason = "PENDING", "The observation window has not matured yet."
                feedback_rows.append((TENANT_ID, prediction["prediction_id"], prediction["customer_id"], horizon, state, reason, "2026-10-11T00:00:00Z"))
        connection.executemany("INSERT INTO dashboard_prediction_feedback VALUES (?, ?, ?, ?, ?, ?, ?)", feedback_rows)
        connection.executemany(
            "INSERT INTO dashboard_model_releases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (TENANT_ID, "retention_risk_v1_2", "current", "ACTIVE_EVALUATION", "behavioral_features_v1_2", "calibration_v1_2", "churn_policy_v1_2", GENERATED_AT, "Enabled for tenant-scoped evaluation; production promotion remains evidence-gated."),
                (TENANT_ID, "retention_risk_v1_3", "candidate", "AWAITING_MATURE_OUTCOMES", "behavioral_features_v1_3", "calibration_pending", "churn_policy_v1_2", "2026-10-10T08:00:00Z", "Candidate remains gated until reconciled 30-day outcomes are available."),
            ],
        )
        connection.execute("INSERT INTO dashboard_metadata VALUES (?, ?, ?)", (TENANT_ID, "dataset_provenance", "Synthetic SaaS v1.2 evaluation cohort"))


def main() -> int:
    args = _arguments()
    target = args.target.expanduser().resolve()
    secret_path = args.reader_secret.expanduser().resolve()
    _backup(args.source, target, replace=args.replace)
    sources = _sources(target)

    writer_token = create_service_principal(
        target,
        TENANT_ID,
        role="analyst",
        authorized_sources=sources,
        authorized_purposes=("retention_inference", "billing_valuation", "model_artifact_write"),
    )
    writer = authenticate_service_principal(target, writer_token)
    try:
        snapshots = _select_accounts(target, writer)
        predictions = [_prediction(snapshot, index) for index, snapshot in enumerate(snapshots)]
        for prediction in predictions:
            store_prediction(target, writer, prediction)
        _seed_dashboard_state(target, snapshots, predictions)
    finally:
        _delete_temporary_writer(target, writer.service_principal_id)
        writer_token = ""

    reader_token = create_service_principal(
        target,
        TENANT_ID,
        role="analyst",
        authorized_sources=sources,
        authorized_purposes=("retention_inference", "billing_valuation", "integration_health"),
    )
    store_dpapi_secret(secret_path, reader_token)
    reader_token = ""

    status_counts = Counter(prediction["status"] for prediction in predictions)
    risk_counts = Counter(
        "high" if prediction["p_churn_30d"] >= 0.60 else "medium" if prediction["p_churn_30d"] >= 0.30 else "low"
        for prediction in predictions
        if prediction["status"] == "scored"
    )
    print(json.dumps({
        "database": str(target),
        "reader_secret": str(secret_path),
        "tenant_id": TENANT_ID,
        "as_of": AS_OF,
        "predictions": len(predictions),
        "status_counts": dict(sorted(status_counts.items())),
        "risk_counts_30d": dict(sorted(risk_counts.items())),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
