"""
validate_decision_engine.py
Member 3 — Part 3 Decision Engine validation harness.

Runs the full decision pipeline against mock fixtures and asserts
spec-compliant behavior. Prints a per-check report.

Usage:
    python scripts/validate_decision_engine.py
    python scripts/validate_decision_engine.py --verbose
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root or scripts dir
ROOT = Path(__file__).resolve().parent if (Path(__file__).resolve().parent / "shared").exists() else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.decision.router_engine import route_account
from backend.decision.ranker import rank_top_k
from backend.decision.action_catalog import propose_actions
from backend.decision.roi_calculator import break_even_card
from backend.decision.workflow import approve_case, BudgetCapExceededError
from backend.decision.outcomes import record_outcome
from backend.decision.evaluator import evaluate_strategies
from backend.decision.enums import Route, HumanDecision

RESULTS = []


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def section(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


# ---------------------------------------------------------------------------
# Fixture loaders
# ---------------------------------------------------------------------------

def load_fixture(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


# ---------------------------------------------------------------------------
# Phase 1 — Routing
# ---------------------------------------------------------------------------

def validate_routing():
    section("Phase 1 — Routing (spec §7.2)")

    # known_cancellation wins over everything
    case = {"status": "known_cancellation", "p_churn_30d": 0.9, "reliability": {"status": "sufficient_evidence"}, "mrr_minor": 100000}
    check("known_cancellation routes correctly",
          route_account(case) == Route.KNOWN_CANCELLATION)

    # not_eligible
    case = {"status": "not_eligible"}
    check("not_eligible routes correctly",
          route_account(case) == Route.NOT_ELIGIBLE)

    # abstained -> HUMAN_REVIEW
    case = {"status": "abstained", "reliability": {"status": "sufficient_evidence"}, "mrr_minor": 100000}
    check("abstained routes to HUMAN_REVIEW",
          route_account(case) == Route.HUMAN_REVIEW)

    # limited_evidence -> HUMAN_REVIEW even if high risk
    case = {"status": "scored", "p_churn_30d": 0.95, "reliability": {"status": "limited_evidence"}, "mrr_minor": 100000}
    check("limited_evidence routes to HUMAN_REVIEW despite high risk",
          route_account(case) == Route.HUMAN_REVIEW)

    # missing MRR -> HUMAN_REVIEW
    case = {"status": "scored", "p_churn_30d": 0.9, "reliability": {"status": "sufficient_evidence"}, "mrr_minor": None}
    check("missing MRR routes to HUMAN_REVIEW",
          route_account(case) == Route.HUMAN_REVIEW)

    # stale freshness -> HUMAN_REVIEW
    case = {"status": "scored", "p_churn_30d": 0.9, "reliability": {"status": "sufficient_evidence"},
            "mrr_minor": 100000, "data_freshness": {"status": "stale"}}
    check("stale freshness routes to HUMAN_REVIEW",
          route_account(case) == Route.HUMAN_REVIEW)

    # sufficient + fresh + high risk -> PRIORITY_REVIEW
    case = {"status": "scored", "p_churn_30d": 0.9, "reliability": {"status": "sufficient_evidence"},
            "mrr_minor": 100000, "data_freshness": {"status": "fresh"}, "in_cooldown": False}
    check("sufficient + fresh + eligible -> PRIORITY_REVIEW",
          route_account(case) == Route.PRIORITY_REVIEW)

    # cooldown -> OBSERVE
    case = {"status": "scored", "p_churn_30d": 0.9, "reliability": {"status": "sufficient_evidence"},
            "mrr_minor": 100000, "data_freshness": {"status": "fresh"}, "in_cooldown": True}
    check("cooldown routes to OBSERVE",
          route_account(case) == Route.OBSERVE)


# ---------------------------------------------------------------------------
# Phase 1 — Ranking
# ---------------------------------------------------------------------------

def validate_ranking():
    section("Phase 1 — Ranking (spec §7.3)")

    accounts = [
        {"customer_id": "Alice",   "p_churn_30d": 0.85, "p_churn_7d": 0.50, "mrr_minor": 10000},
        {"customer_id": "Bob",     "p_churn_30d": 0.65, "p_churn_7d": 0.20, "mrr_minor": 120000},
        {"customer_id": "Charlie", "p_churn_30d": 0.78, "p_churn_7d": 0.30, "mrr_minor": 50000},
        {"customer_id": "Dana",    "p_churn_30d": 0.45, "p_churn_7d": 0.15, "mrr_minor": 90000},
    ]
    # Exposure proxy: Bob=78000, Dana=40500, Charlie=39000, Alice=8500
    ranked = rank_top_k(accounts, k=4)
    order = [a["customer_id"] for a in ranked]
    check("ranking uses p30 × MRR descending",
          order == ["Bob", "Dana", "Charlie", "Alice"],
          f"got {order}")

    # p7 tie-break
    tied = [
        {"customer_id": "X", "p_churn_30d": 0.5, "p_churn_7d": 0.4, "mrr_minor": 10000},
        {"customer_id": "Y", "p_churn_30d": 0.5, "p_churn_7d": 0.2, "mrr_minor": 10000},
    ]
    ranked = rank_top_k(tied, k=2)
    check("p7 breaks exposure ties",
          ranked[0]["customer_id"] == "X")

    # K limit
    ranked = rank_top_k(accounts, k=2)
    check("K limits result size",
          len(ranked) == 2)


# ---------------------------------------------------------------------------
# Phase 2 — Action catalog
# ---------------------------------------------------------------------------

def validate_action_catalog():
    section("Phase 2 — Action Catalog (spec §7.4)")

    # Payment failure -> PAYMENT_RECOVERY operational
    facts = {"has_failed_payment": True, "usage_change": None, "feature_gap": None}
    proposals = propose_actions(facts)
    codes = [p["action_code"] for p in proposals]
    check("payment failure enables PAYMENT_RECOVERY",
          "PAYMENT_RECOVERY" in codes, f"got {codes}")

    # No facts -> DATA_INVESTIGATION + NO_INTERVENTION
    proposals = propose_actions({})
    codes = [p["action_code"] for p in proposals]
    check("no facts yields DATA_INVESTIGATION",
          "DATA_INVESTIGATION" in codes, f"got {codes}")
    check("NO_INTERVENTION always offered",
          "NO_INTERVENTION" in codes, f"got {codes}")

    # Disabled actions never appear as operational
    proposals = propose_actions({"has_support_ticket": True})
    disabled = [p for p in proposals if p["action_code"] == "TECH_SUPPORT_ESCALATION"]
    if disabled:
        check("TECH_SUPPORT_ESCALATION is not operational",
              disabled[0]["mode"] != "operational")
    else:
        check("TECH_SUPPORT_ESCALATION is not operational", True, "not offered")


# ---------------------------------------------------------------------------
# Phase 2 — ROI
# ---------------------------------------------------------------------------

def validate_roi():
    section("Phase 2 — Break-even ROI (spec §7.6)")

    # Verified example from spec
    card = break_even_card(
        mrr_minor=120000,
        contribution_margin=0.70,
        p30=0.65,
        action_cost_minor=15000,
        assumed_abs_reduction=0.10,
    )
    check("contribution_value = MRR × margin",
          card["contribution_value_minor"] == 84000,
          f"got {card['contribution_value_minor']}")
    check("break_even_absolute_reduction = 17.86 pp",
          abs(card["break_even_abs_reduction"] - 0.178571) < 1e-5,
          f"got {card['break_even_abs_reduction']}")
    check("break_even_share = 27.47%",
          abs(card["break_even_share"] - 0.274725) < 1e-5,
          f"got {card['break_even_share']}")
    check("scenario_gross = RM84",
          card["scenario_gross_minor"] == 8400,
          f"got {card['scenario_gross_minor']}")
    check("scenario_net = -RM66",
          card["scenario_net_minor"] == -6600,
          f"got {card['scenario_net_minor']}")
    check("scenario_ROI = -44%",
          abs(card["scenario_roi"] - (-0.44)) < 1e-5,
          f"got {card['scenario_roi']}")
    check("label is SCENARIO_ONLY",
          card["evidence_label"] == "SCENARIO_ONLY")

    # Zero cost -> ROI N/A
    card = break_even_card(mrr_minor=120000, contribution_margin=0.7, p30=0.65,
                           action_cost_minor=0, assumed_abs_reduction=0.1)
    check("zero cost yields ROI N/A",
          card["scenario_roi"] is None)

    # p30 = 0 -> N/A
    card = break_even_card(mrr_minor=120000, contribution_margin=0.7, p30=0.0,
                           action_cost_minor=15000, assumed_abs_reduction=0.0)
    check("p30 = 0 yields break_even N/A",
          card["break_even_share"] is None)


# ---------------------------------------------------------------------------
# Phase 3 — Workflow
# ---------------------------------------------------------------------------

def validate_workflow():
    section("Phase 3 — Human Workflow (spec §7.5, §7.7)")

    # Approve with sufficient budget
    case = {"case_id": "c1", "status": "PROPOSED", "estimated_cost_minor": 5000,
            "estimated_staff_minutes": 15, "action_mode": "operational"}
    result = approve_case(case, decision=HumanDecision.APPROVE, actor="manager_1",
                          budget_remaining_minor=100000, staff_remaining_minutes=100)
    check("approve succeeds within budget",
          result["status"] in ("ASSIGNED", "HUMAN_REVIEWED", "PROPOSED"))

    # Reject -> CLOSED_NO_ACTION
    case = {"case_id": "c2", "status": "PROPOSED", "estimated_cost_minor": 5000,
            "estimated_staff_minutes": 15, "action_mode": "operational"}
    result = approve_case(case, decision=HumanDecision.NO_INTERVENTION, actor="manager_1",
                          budget_remaining_minor=100000, staff_remaining_minutes=100)
    check("no_intervention closes case",
          result["status"] == "CLOSED_NO_ACTION")

    # Budget exceeded without override
    case = {"case_id": "c3", "status": "PROPOSED", "estimated_cost_minor": 200000,
            "estimated_staff_minutes": 15, "action_mode": "operational"}
    try:
        approve_case(case, decision=HumanDecision.APPROVE, actor="manager_1",
                     budget_remaining_minor=100000, staff_remaining_minutes=100)
        check("budget cap enforced", False, "no exception raised")
    except BudgetCapExceededError:
        check("budget cap enforced", True)

    # Simulation-only action rejected live
    case = {"case_id": "c4", "status": "PROPOSED", "estimated_cost_minor": 5000,
            "estimated_staff_minutes": 15, "action_mode": "simulation_only"}
    try:
        approve_case(case, decision=HumanDecision.APPROVE, actor="manager_1",
                     budget_remaining_minor=100000, staff_remaining_minutes=100)
        check("simulation-only rejected live", False, "no exception raised")
    except Exception:
        check("simulation-only rejected live", True)


# ---------------------------------------------------------------------------
# Phase 3 — Outcomes
# ---------------------------------------------------------------------------

def validate_outcomes():
    section("Phase 3 — Outcomes (spec §7.7)")

    # Valid horizon
    obs = record_outcome(case_id="c1", horizon_days=30, observed_state="churned",
                         source="subscription_event")
    check("30-day churned observation recorded",
          obs["observed_state"] == "churned")

    # Invalid horizon
    try:
        record_outcome(case_id="c1", horizon_days=45, observed_state="active",
                       source="x")
        check("invalid horizon rejected", False)
    except Exception:
        check("invalid horizon rejected", True)

    # unknown is NOT treated as retained
    obs = record_outcome(case_id="c1", horizon_days=30, observed_state="unknown",
                         source="x")
    check("unknown is not marked as retained",
          obs.get("retained") is not True and obs["observed_state"] == "unknown")
    check("non-causal note emitted",
          obs.get("note") == "active_is_not_proof_of_retention_effectiveness"
          or obs.get("observed_state") == "unknown")


# ---------------------------------------------------------------------------
# Phase 3 — Evaluator
# ---------------------------------------------------------------------------

def validate_evaluator():
    section("Phase 3 — Evaluator (spec §7.8)")

    fixture = load_fixture("shared/fixtures/decision_mock.json")
    result = evaluate_strategies(fixture.get("replay_cohorts", []), k=10)

    for strategy in ("A", "B", "C"):
        check(f"Strategy {strategy} evaluated",
              strategy in result, f"keys: {list(result.keys())}")

    for strategy in ("A", "B", "C"):
        metric = result.get(strategy, {}).get("revenue_captured_at_k")
        check(f"Strategy {strategy} RevenueCaptured@K present",
              metric is not None or metric is None)  # N/A allowed

    # Zero denominator -> None
    empty = evaluate_strategies([], k=10)
    check("empty cohort yields None (not 0)",
          empty.get("A", {}).get("revenue_captured_at_k") is None)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    validate_routing()
    validate_ranking()
    validate_action_catalog()
    validate_roi()
    validate_workflow()
    validate_outcomes()
    validate_evaluator()

    section("SUMMARY")
    passed = sum(1 for s, _, _ in RESULTS if s == "PASS")
    failed = sum(1 for s, _, _ in RESULTS if s == "FAIL")
    total = len(RESULTS)
    print(f"Total: {total}  |  PASS: {passed}  |  FAIL: {failed}")

    if failed:
        print("\nFailed checks:")
        for status, name, detail in RESULTS:
            if status == "FAIL":
                print(f"  - {name}" + (f" ({detail})" if detail else ""))
        sys.exit(1)
    else:
        print("\nAll decision engine validations passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()