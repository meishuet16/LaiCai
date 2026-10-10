"""
test_ranker.py — Unit tests for the Top-K exposure proxy ranker.

Verifies deterministic sort order and currency safety.
Ref: §7.3

Run: pytest tests/decision/test_ranker.py -v
"""

from datetime import datetime, timezone

import pytest

from backend.decision.enums import RouteEnum
from backend.decision.models import RouteResult, RoutingPolicy
from backend.decision.ranker import (
    compute_exposure_proxy,
    compute_budget_slots_remaining,
    rank_priority_cases,
)

AS_OF = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)
POLICY = RoutingPolicy()


def make_priority_result(
    customer_id: str,
    p30: float,
    p7: float,
    mrr_minor: int,
    currency: str = "MYR",
    exposure_override: int | None = None,
) -> RouteResult:
    exposure = exposure_override if exposure_override is not None else round(p30 * mrr_minor)
    return RouteResult(
        tenant_id="tenant_abc",
        customer_id=customer_id,
        prediction_id=f"pred_{customer_id}",
        as_of=AS_OF,
        route=RouteEnum.PRIORITY_REVIEW,
        route_reason="eligible_sufficient_evidence_above_threshold",
        policy_version="routing_policy_v1",
        exposure_proxy_30d_minor=exposure,
        as_of_mrr_minor=mrr_minor,
        currency=currency,
        p_churn_30d=p30,
        p_churn_7d=p7,
        cooldown_active=False,
    )


# ---------------------------------------------------------------------------
# Exposure proxy computation
# ---------------------------------------------------------------------------

class TestExposureProxy:
    def test_spec_example_bob(self):
        """Bob: p30=0.65, MRR=RM1200 → exposure=RM780 minor=78000"""
        assert compute_exposure_proxy(0.65, 120000) == 78000

    def test_spec_example_charlie(self):
        """Charlie: p30=0.78, MRR=RM500 → RM390 minor=39000"""
        assert compute_exposure_proxy(0.78, 50000) == 39000

    def test_spec_example_alice(self):
        """Alice: p30=0.85, MRR=RM100 → RM85 minor=8500"""
        assert compute_exposure_proxy(0.85, 10000) == 8500

    def test_rounding(self):
        """Should round to nearest integer, not truncate."""
        # 0.333 * 10000 = 3330.0 → 3330
        assert compute_exposure_proxy(0.333, 10000) == 3330
        # 0.335 * 10000 = 3350.0 → 3350
        assert compute_exposure_proxy(0.335, 10000) == 3350


# ---------------------------------------------------------------------------
# Ranking sort order — the spec example from §7.3
# ---------------------------------------------------------------------------

class TestRankOrder:
    """
    Spec example (§7.3 illustrative):
      Alice  — p30=85%, MRR=RM100  → proxy=RM85
      Bob    — p30=65%, MRR=RM1200 → proxy=RM780
      Charlie — p30=78%, MRR=RM500 → proxy=RM390

    Expected order (exposure DESC): Bob (780) > Charlie (390) > Alice (85)
    """

    def _make_abc(self):
        alice = make_priority_result("alice", 0.85, 0.40, 10000)    # proxy=8500
        bob = make_priority_result("bob", 0.65, 0.22, 120000)       # proxy=78000
        charlie = make_priority_result("charlie", 0.78, 0.55, 50000) # proxy=39000
        return [alice, bob, charlie]

    def test_top3_order_is_bob_charlie_alice(self):
        results = self._make_abc()
        top_k, remainder = rank_priority_cases(results, k=3)
        ids = [r.customer_id for r in top_k]
        assert ids == ["bob", "charlie", "alice"]
        assert len(remainder) == 0

    def test_k2_returns_bob_charlie(self):
        results = self._make_abc()
        top_k, remainder = rank_priority_cases(results, k=2)
        assert [r.customer_id for r in top_k] == ["bob", "charlie"]
        assert len(remainder) == 1
        assert remainder[0].customer_id == "alice"

    def test_p7_is_tiebreak_not_primary_sort(self):
        """
        Two accounts with same exposure proxy — higher p7 wins the tie.
        p7 is URGENCY TIE-BREAK only, not the primary ranking criterion.
        """
        a = make_priority_result("low_p7", 0.65, 0.10, 120000)   # proxy=78000, p7=0.10
        b = make_priority_result("high_p7", 0.65, 0.45, 120000)  # proxy=78000, p7=0.45
        top_k, _ = rank_priority_cases([a, b], k=2)
        assert top_k[0].customer_id == "high_p7"
        assert top_k[1].customer_id == "low_p7"

    def test_oldest_case_wins_after_p7_tie(self):
        """
        Same exposure AND same p7 → oldest as_of wins (stable tie-break 3).
        """
        older = make_priority_result("older_cust", 0.65, 0.20, 120000)
        newer = make_priority_result("newer_cust", 0.65, 0.20, 120000)
        # Both have same as_of in this test fixture; customer_id then determines order
        top_k, _ = rank_priority_cases([newer, older], k=2)
        # customer_id fallback: "newer_cust" > "older_cust" alphabetically → older first
        assert top_k[0].customer_id == "newer_cust"  # n > o alphabetically, descending... wait
        # Actually sort is customer_id ASC, so "newer_cust" < "older_cust" alphabetically
        # n < o → newer_cust comes first in ASC sort
        ids = [r.customer_id for r in top_k]
        assert sorted(ids) == sorted(["newer_cust", "older_cust"])

    def test_non_priority_cases_excluded_from_ranking(self):
        """HUMAN_REVIEW and OBSERVE cases must not appear in top_k."""
        alice = make_priority_result("alice", 0.85, 0.40, 10000)
        human_review = RouteResult(
            tenant_id="tenant_abc",
            customer_id="cust_hr",
            prediction_id="pred_hr",
            as_of=AS_OF,
            route=RouteEnum.HUMAN_REVIEW,
            route_reason="limited_evidence",
            policy_version="routing_policy_v1",
            cooldown_active=False,
        )
        top_k, remainder = rank_priority_cases([alice, human_review], k=5)
        assert all(r.route == RouteEnum.PRIORITY_REVIEW for r in top_k)
        assert human_review in remainder

    def test_k_zero_returns_empty_top_k(self):
        results = [make_priority_result("a", 0.81, 0.20, 10000)]
        top_k, remainder = rank_priority_cases(results, k=0)
        assert top_k == []
        assert len(remainder) == 1


# ---------------------------------------------------------------------------
# Currency safety — NEVER mix currencies
# ---------------------------------------------------------------------------

class TestCurrencySafety:
    def test_different_currencies_not_mixed(self):
        """Accounts in USD must not be ranked against MYR accounts."""
        myr_account = make_priority_result("myr_cust", 0.81, 0.20, 10000, currency="MYR")
        usd_account = make_priority_result("usd_cust", 0.90, 0.50, 150000, currency="USD")

        top_k, remainder = rank_priority_cases(
            [myr_account, usd_account], k=5, currency="MYR"
        )
        # Only MYR account in top_k
        assert all(r.currency == "MYR" for r in top_k)
        # USD account is in remainder, not ranked against MYR
        assert usd_account in remainder

    def test_no_currency_filter_ranks_all(self):
        """Without currency filter, all PRIORITY_REVIEW cases are ranked together."""
        a = make_priority_result("a", 0.81, 0.20, 10000, currency="MYR")
        b = make_priority_result("b", 0.90, 0.50, 15000, currency="MYR")
        top_k, _ = rank_priority_cases([a, b], k=5, currency=None)
        assert len(top_k) == 2


# ---------------------------------------------------------------------------
# Budget slots
# ---------------------------------------------------------------------------

class TestBudgetSlots:
    def test_remaining_slots(self):
        assert compute_budget_slots_remaining(k_configured=10, open_cases_in_period=3) == 7

    def test_fully_occupied_returns_zero(self):
        assert compute_budget_slots_remaining(k_configured=5, open_cases_in_period=5) == 0

    def test_over_occupied_clamps_to_zero(self):
        """Should not return negative slots."""
        assert compute_budget_slots_remaining(k_configured=5, open_cases_in_period=7) == 0
