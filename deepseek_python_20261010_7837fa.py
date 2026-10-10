"""
Spec-compliance tests for Part 3 Decision Engine.
Run: pytest tests/decision/test_spec_compliance.py -v
"""

import pytest
from backend.decision.router_engine import route_account
from backend.decision.ranker import rank_top_k
from backend.decision.roi_calculator import break_even_card
from backend.decision.enums import Route


class TestRoutingSpec:
    """Spec §7.2 — routing order: eligibility -> reliability -> freshness -> threshold -> cooldown."""

    def test_known_cancellation_wins(self):
        case = {"status": "known_cancellation", "p_churn_30d": 0.99,
                "reliability": {"status": "sufficient_evidence"}, "mrr_minor": 100000}
        assert route_account(case) == Route.KNOWN_CANCELLATION

    def test_high_risk_does_not_override_limited_evidence(self):
        case = {"status": "scored", "p_churn_30d": 0.99,
                "reliability": {"status": "limited_evidence"}, "mrr_minor": 100000}
        assert route_account(case) == Route.HUMAN_REVIEW

    def test_missing_mrr_routes_human_review(self):
        case = {"status": "scored", "p_churn_30d": 0.9,
                "reliability": {"status": "sufficient_evidence"}, "mrr_minor": None}
        assert route_account(case) == Route.HUMAN_REVIEW


class TestRankingSpec:
    """Spec §7.3 — p30 × MRR desc, p7 tie-break, stable ordering."""

    def test_spec_example_order(self):
        accounts = [
            {"customer_id": "Alice",   "p_churn_30d": 0.85, "p_churn_7d": 0.50, "mrr_minor": 10000},
            {"customer_id": "Bob",     "p_churn_30d": 0.65, "p_churn_7d": 0.20, "mrr_minor": 120000},
            {"customer_id": "Charlie", "p_churn_30d": 0.78, "p_churn_7d": 0.30, "mrr_minor": 50000},
            {"customer_id": "Dana",    "p_churn_30d": 0.45, "p_churn_7d": 0.15, "mrr_minor": 90000},
        ]
        ranked = rank_top_k(accounts, k=4)
        assert [a["customer_id"] for a in ranked] == ["Bob", "Dana", "Charlie", "Alice"]

    def test_deterministic_across_runs(self):
        accounts = [{"customer_id": f"C{i}", "p_churn_30d": 0.5, "p_churn_7d": 0.2,
                     "mrr_minor": 10000} for i in range(20)]
        r1 = [a["customer_id"] for a in rank_top_k(accounts, k=5)]
        r2 = [a["customer_id"] for a in rank_top_k(accounts, k=5)]
        assert r1 == r2


class TestROISpec:
    """Spec §7.6 — verified arithmetic example."""

    def test_spec_verified_example(self):
        card = break_even_card(mrr_minor=120000, contribution_margin=0.70,
                               p30=0.65, action_cost_minor=15000,
                               assumed_abs_reduction=0.10)
        assert card["contribution_value_minor"] == 84000
        assert abs(card["break_even_abs_reduction"] - 0.178571) < 1e-5
        assert abs(card["break_even_share"] - 0.274725) < 1e-5
        assert card["scenario_gross_minor"] == 8400
        assert card["scenario_net_minor"] == -6600
        assert abs(card["scenario_roi"] - (-0.44)) < 1e-5
        assert card["evidence_label"] == "SCENARIO_ONLY"

    def test_zero_cost_roi_is_none(self):
        card = break_even_card(mrr_minor=120000, contribution_margin=0.7,
                               p30=0.65, action_cost_minor=0,
                               assumed_abs_reduction=0.1)
        assert card["scenario_roi"] is None

    def test_impossible_break_even_flagged(self):
        card = break_even_card(mrr_minor=1000, contribution_margin=0.1,
                               p30=0.05, action_cost_minor=100000,
                               assumed_abs_reduction=0.01)
        assert card.get("break_even_achievable") is False


class TestGuardrails:
    """Spec §10.3 — forbidden claims must not appear in output."""

    @pytest.mark.parametrize("forbidden", [
        "revenue_saved",
        "customers_saved",
        "causal_uplift",
        "validated_incremental_roi",
    ])
    def test_no_forbidden_output_keys(self, forbidden):
        card = break_even_card(mrr_minor=120000, contribution_margin=0.7,
                               p30=0.65, action_cost_minor=15000,
                               assumed_abs_reduction=0.1)
        assert forbidden not in card

    def test_scenario_label_always_present(self):
        card = break_even_card(mrr_minor=120000, contribution_margin=0.7,
                               p30=0.65, action_cost_minor=15000,
                               assumed_abs_reduction=0.1)
        assert card["evidence_label"] == "SCENARIO_ONLY"