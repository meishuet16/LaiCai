"""
examples/member3_decision_smoke.py
Member 3 — Part 3 Decision Engine End-to-End Demonstration Script.

Demonstrates the complete human-governed decision pipeline:
1. Input consumption: Prediction payload (Member 2) + Normalized MRR (Member 1)
2. Phase 1 — 5-Gate Routing Engine (Eligibility -> Reliability -> Freshness -> Policy -> Cooldown)
3. Phase 1 — Financial Exposure Proxy & Top-K Ranker
4. Phase 2 — Fact-Based Action Catalog (Zero-guesswork candidate generation)
5. Phase 2 — Break-Even Sensitivity & Scenario ROI Card
6. Phase 3 — Human Approval Workflow with Budget & Staff Capacity Guards
7. Phase 3 — Action Execution & Actual vs. Predicted Cost Tracking
8. Phase 3 — 7/14/30-Day Outcome Observation (Non-causal guardrails)
9. Phase 3 — Strategy Lab Evaluator (Strategies A vs. B vs. C)

Usage:
    python examples/member3_decision_smoke.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.decision.enums import Route, HumanDecision, CaseStatus
from backend.decision.router_engine import route_account
from backend.decision.ranker import rank_top_k
from backend.decision.action_catalog import propose_actions
from backend.decision.roi_calculator import break_even_card
from backend.decision.workflow import approve_case, BudgetCapExceededError
from backend.decision.outcomes import record_outcome
from backend.decision.evaluator import evaluate_strategies


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f" {title}")
    print("=" * 78)


def main():
    print_header("RetainIQ v2 — Member 3: Decision Engine End-to-End Pipeline")
    print(f"Execution timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Specification: RetainIQ_v2_Complete_Requirements.md §7 (Part 3)")

    # ---------------------------------------------------------------------------
    # Step 1: Simulated Inputs from Member 1 (Data) and Member 2 (Predictions)
    # ---------------------------------------------------------------------------
    print_header("Step 1: Ingesting Inputs (Member 1 MRR + Member 2 Predictions)")
    
    accounts = [
        {
            "customer_id": "cust_alpha",
            "name": "Alpha Corp",
            "prediction_id": "pred_alpha_001",
            "as_of": "2026-10-10T00:00:00Z",
            "status": "scored",
            "p_churn_7d": 0.20,
            "p_churn_14d": 0.45,
            "p_churn_30d": 0.85,
            "mrr_minor": 120000,  # RM 1,200.00
            "currency": "MYR",
            "mrr_completeness": "complete",
            "reliability": {"status": "sufficient_evidence"},
            "data_freshness": {"status": "fresh"},
            "in_cooldown": False,
            "has_failed_payment": True,  # Billing fact: payment failure
            "has_usage_deviation": False,
        },
        {
            "customer_id": "cust_beta",
            "name": "Beta Software",
            "prediction_id": "pred_beta_001",
            "as_of": "2026-10-10T00:00:00Z",
            "status": "scored",
            "p_churn_7d": 0.15,
            "p_churn_14d": 0.35,
            "p_churn_30d": 0.65,
            "mrr_minor": 250000,  # RM 2,500.00
            "currency": "MYR",
            "mrr_completeness": "complete",
            "reliability": {"status": "sufficient_evidence"},
            "data_freshness": {"status": "fresh"},
            "in_cooldown": False,
            "has_failed_payment": False,
            "has_usage_deviation": True,  # Usage deviation fact
        },
        {
            "customer_id": "cust_gamma",
            "name": "Gamma Studio",
            "prediction_id": "pred_gamma_001",
            "as_of": "2026-10-10T00:00:00Z",
            "status": "scored",
            "p_churn_7d": 0.30,
            "p_churn_14d": 0.50,
            "p_churn_30d": 0.90,
            "mrr_minor": 80000,  # RM 800.00
            "currency": "MYR",
            "mrr_completeness": "missing",  # Missing data quality issue
            "reliability": {"status": "limited_evidence"},
            "data_freshness": {"status": "stale"},
            "in_cooldown": False,
            "has_failed_payment": False,
            "has_usage_deviation": False,
        },
        {
            "customer_id": "cust_delta",
            "name": "Delta Logistics",
            "prediction_id": "pred_delta_001",
            "as_of": "2026-10-10T00:00:00Z",
            "status": "known_cancellation",  # Customer already cancelled
            "p_churn_7d": None,
            "p_churn_14d": None,
            "p_churn_30d": None,
            "mrr_minor": 50000,
            "currency": "MYR",
            "mrr_completeness": "complete",
            "reliability": {"status": "sufficient_evidence"},
            "data_freshness": {"status": "fresh"},
            "in_cooldown": False,
            "has_failed_payment": False,
            "has_usage_deviation": False,
        },
    ]

    for acct in accounts:
        print(f"  * {acct['customer_id']} ({acct['name']}): "
              f"p30={acct['p_churn_30d']}, MRR={acct['currency']} {acct['mrr_minor'] / 100:.2f}, "
              f"reliability={acct['reliability']['status']}, status={acct['status']}")

    # ---------------------------------------------------------------------------
    # Step 2: Routing Decisions (§7.2)
    # ---------------------------------------------------------------------------
    print_header("Step 2: 5-Gate Routing Engine")
    routed_accounts = []
    for acct in accounts:
        route = route_account(acct)
        acct["route"] = route
        print(f"  -> {acct['customer_id']} ({acct['name']}) Routed To: {route.value}")
        if route == Route.PRIORITY_REVIEW:
            routed_accounts.append(acct)

    # ---------------------------------------------------------------------------
    # Step 3: Top-K Financial Exposure Ranking (§7.3)
    # ---------------------------------------------------------------------------
    print_header("Step 3: Financial Exposure Ranking (Top-K Review Slots)")
    k_slots = 2
    ranked_top_k = rank_top_k(routed_accounts, k=k_slots)
    
    print(f"Available human review slots: K = {k_slots}")
    for idx, r in enumerate(ranked_top_k, 1):
        exposure = (r["p_churn_30d"] * r["mrr_minor"]) / 100
        print(f"  Slot #{idx}: {r['customer_id']} ({r['name']}) — 30d Exposure Proxy: RM {exposure:.2f} "
              f"(p30={r['p_churn_30d']} × MRR=RM {r['mrr_minor'] / 100:.2f})")

    primary_case = ranked_top_k[0]

    # ---------------------------------------------------------------------------
    # Step 4: Fact-Based Next Best Action Catalog (§7.4)
    # ---------------------------------------------------------------------------
    print_header("Step 4: Fact-Based Action Proposals")
    facts = {
        "has_failed_payment": primary_case.get("has_failed_payment", False),
        "has_usage_deviation": primary_case.get("has_usage_deviation", False),
    }
    proposals = propose_actions(facts)
    print(f"Proposing candidate actions for {primary_case['customer_id']} based on observed facts:")
    for prop in proposals:
        mode = prop.get("action_mode") or prop.get("mode") or "operational"
        cost = prop.get("estimated_cost_minor", 0) / 100
        time = prop.get("estimated_staff_minutes", 0)
        print(f"  - Action: {prop['action_code']:<24} | Mode: {mode:<12} | Est Cost: RM {cost:.2f} | Time: {time} mins")

    selected_action = proposals[0]

    # ---------------------------------------------------------------------------
    # Step 5: Break-Even ROI Sensitivity Analysis (§7.6)
    # ---------------------------------------------------------------------------
    print_header("Step 5: One-Month Break-Even ROI Sensitivity Card")
    # For demonstration, assume a manager intervention cost of RM 40.00 (4,000 minor units)
    demo_action_cost_minor = 4000
    roi_card = break_even_card(
        mrr_minor=primary_case["mrr_minor"],
        contribution_margin=0.70,
        p30=primary_case["p_churn_30d"],
        action_cost_minor=demo_action_cost_minor,
        assumed_abs_reduction=0.10,  # 10 percentage points assumed reduction
    )
    print(f"Account: {primary_case['customer_id']} | Action: {selected_action['action_code']}")
    print(f"  Contribution Value (MRR × 70% Margin): RM {roi_card['contribution_value_minor'] / 100:.2f}")
    print(f"  Action Cost:                          RM {demo_action_cost_minor / 100:.2f}")
    print(f"  Required Break-Even Absolute Drop:    {roi_card['break_even_abs_reduction'] * 100:.2f} percentage points")
    print(f"  Required Relative Risk Reduction:     {roi_card['break_even_share'] * 100:.2f}% of baseline risk")
    print(f"  Scenario Gross Value (10 pp drop):    RM {roi_card['scenario_gross_minor'] / 100:.2f}")
    print(f"  Scenario Net Value:                   RM {roi_card['scenario_net_minor'] / 100:.2f}")
    scenario_roi_str = f"{roi_card['scenario_roi'] * 100:.1f}%" if roi_card.get("scenario_roi") is not None else "N/A"
    print(f"  Scenario ROI:                         {scenario_roi_str}")
    print(f"  Guardrail Evidence Label:             [{roi_card['evidence_label']}]")

    # ---------------------------------------------------------------------------
    # Step 6: Human Approval & Transactional Budget Safeguards (§7.5, §7.7)
    # ---------------------------------------------------------------------------
    print_header("Step 6: Human Approval Workflow with Budget Controls")
    case_record = {
        "case_id": "case_live_001",
        "status": "PROPOSED",
        "action_code": selected_action["action_code"],
        "action_mode": selected_action.get("mode") or selected_action.get("action_mode") or "operational",
        "estimated_cost_minor": demo_action_cost_minor,
        "estimated_staff_minutes": selected_action.get("estimated_staff_minutes", 20),
    }
    
    # Starting budget: RM 500.00, 120 staff minutes
    current_budget_minor = 50000
    current_staff_minutes = 120
    print(f"Budget balance before approval: RM {current_budget_minor / 100:.2f} | Staff capacity: {current_staff_minutes} mins")

    approval_result = approve_case(
        case=case_record,
        decision=HumanDecision.APPROVE,
        actor="manager_sarah",
        budget_remaining_minor=current_budget_minor,
        staff_remaining_minutes=current_staff_minutes,
        override=False,
    )
    
    print(f"Decision recorded by {approval_result.get('actor')}: {approval_result.get('decision')}")
    print(f"New Case Status: {approval_result.get('status')}")
    
    # Demonstrate budget cap guardrail
    print("\nSimulating budget overflow guardrail check:")
    try:
        approve_case(
            case={"case_id": "case_overflow", "status": "PROPOSED", "action_mode": "operational",
                  "estimated_cost_minor": 999999, "estimated_staff_minutes": 10},
            decision=HumanDecision.APPROVE,
            actor="manager_sarah",
            budget_remaining_minor=1000,
            staff_remaining_minutes=100,
        )
    except BudgetCapExceededError as err:
        print(f"  [GUARDRAIL VERIFIED] Budget overflow safely blocked: {err}")

    # ---------------------------------------------------------------------------
    # Step 7: Action Execution & Actual vs. Predicted Costs (§7.7)
    # ---------------------------------------------------------------------------
    print_header("Step 7: Action Execution & Cost Audit Trail")
    execution_event = {
        "case_id": case_record["case_id"],
        "proposal_id": "prop_beta_01",
        "execution_status": "EXECUTED",
        "executed_by": "csm_david",
        "predicted_cost_minor": demo_action_cost_minor,
        "actual_monetary_cost_minor": 4500,  # RM 45.00 actual cost
        "actual_staff_minutes": 25,
        "follow_up_anchor": "2026-10-10T14:00:00Z",
        "follow_up_due_at": {
            "7d": "2026-10-17T14:00:00Z",
            "14d": "2026-10-24T14:00:00Z",
            "30d": "2026-11-09T14:00:00Z",
        },
    }
    print(f"Action executed by: {execution_event['executed_by']}")
    print(f"  Predicted Cost:  RM {execution_event['predicted_cost_minor'] / 100:.2f}")
    print(f"  Actual Cost:     RM {execution_event['actual_monetary_cost_minor'] / 100:.2f} (Recorded separately per §7.7)")
    print(f"  Follow-up due:   7d -> {execution_event['follow_up_due_at']['7d']}")

    # ---------------------------------------------------------------------------
    # Step 8: Outcome Tracking & Non-Causal Guardrail (§7.7, §10.3)
    # ---------------------------------------------------------------------------
    print_header("Step 8: 7/14/30-Day Outcome Tracking")
    observation = record_outcome(
        case_id=case_record["case_id"],
        horizon_days=30,
        observed_state="active",
        source="subscription_event_ledger",
    )
    print(f"Outcome Observation (30-day horizon):")
    print(f"  Observed State:           {observation['observed_state']}")
    print(f"  Retained Flag:            {observation.get('retained')}")
    print(f"  Non-Causal Note Emitted:  \"{observation.get('note')}\"")

    # ---------------------------------------------------------------------------
    # Step 9: Strategy Lab Evaluation (§7.8)
    # ---------------------------------------------------------------------------
    print_header("Step 9: Strategy Lab Evaluator (Strategies A, B, C)")
    historical_cohort = [
        {"customer_id": "c1", "mrr_minor": 100000, "p_churn_30d": 0.80, "p_churn_7d": 0.30, "actually_churned_30d": True},
        {"customer_id": "c2", "mrr_minor": 200000, "p_churn_30d": 0.70, "p_churn_7d": 0.20, "actually_churned_30d": True},
        {"customer_id": "c3", "mrr_minor":  30000, "p_churn_30d": 0.90, "p_churn_7d": 0.40, "actually_churned_30d": False},
        {"customer_id": "c4", "mrr_minor": 150000, "p_churn_30d": 0.40, "p_churn_7d": 0.10, "actually_churned_30d": False},
    ]
    eval_results = evaluate_strategies(historical_cohort, k=2)
    print("Comparison of Prioritization Strategies on Historical Cohort (K=2):")
    for strat, res in eval_results.items():
        mrr_captured = res.get("subsequently_churned_mrr_identified_minor", 0)
        mrr_str = f"RM {mrr_captured / 100:.2f}"
        rev_share = res.get("revenue_captured_at_k")
        share_str = f"{rev_share * 100:.1f}%" if rev_share is not None else "N/A"
        recall = res.get("recall_at_k")
        rec_str = f"{recall * 100:.1f}%" if recall is not None else "N/A"
        print(f"  Strategy {strat}: Churned MRR Identified = {mrr_str:<12} ({share_str} of total) | Recall@K = {rec_str}")

    print_header("Member 3 Decision Pipeline Complete — All Boundaries Verified")


if __name__ == "__main__":
    main()
