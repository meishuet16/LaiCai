"""
ranker.py — Top-K prioritization for the Decision Engine.

Sorts PRIORITY_REVIEW cases by exposure proxy and selects the top-K
reviewer slots. K is the number of available human reviewer slots,
NOT the number of customers saved.

Sort order (Ref: §7.3):
  1. exposure_proxy_30d DESC   — primary financial ranking
  2. p_churn_7d DESC           — urgency tie-break only
  3. opened_at ASC             — oldest pending case wins ties
  4. customer_id ASC           — stable deterministic final tie-break

Critical rules:
  - NEVER mix accounts from different currencies in the same ranking.
  - exposure_proxy_30d is a ranking proxy, NOT exact cash loss.
  - K = reviewer slots; do NOT claim K = customers saved.
  - HUMAN_REVIEW cases are reported separately (investigation queue),
    their workload must be deducted from shared staff capacity.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from .models import RouteResult
from .enums import RouteEnum


def compute_exposure_proxy(p_churn_30d: float, mrr_minor: int) -> int:
    """
    exposure_proxy_30d = calibrated_p_churn_30d × as_of_MRR (minor units).

    This is a ranking signal only — not a prediction of exact cash loss.
    Both inputs must be from the same point-in-time as_of snapshot.
    """
    return round(p_churn_30d * mrr_minor)


def _sort_key(result: RouteResult) -> tuple:
    """
    Deterministic sort key for PRIORITY_REVIEW accounts.
    Returns a tuple suitable for sorted() — descending values are negated.
    """
    # Negate for descending sort; use sentinel for None values
    proxy = -(result.exposure_proxy_30d_minor or 0)
    p7 = -(result.p_churn_7d or 0.0)

    # opened_at ascending — convert to timestamp for comparison
    # (RouteResult does not carry opened_at directly; caller sets it or uses as_of)
    opened = result.as_of  # fallback; replace with actual opened_at when stored

    # customer_id ascending for stable final tie-break
    cid = result.customer_id

    return (proxy, p7, opened, cid)


def rank_priority_cases(
    results: list[RouteResult],
    k: int,
    currency: Optional[str] = None,
) -> tuple[list[RouteResult], list[RouteResult]]:
    """
    Sort PRIORITY_REVIEW accounts and return (top_k, remainder).

    Args:
        results:  List of RouteResult objects — may include any route.
        k:        Number of reviewer slots (admin-configured).
        currency: If provided, only rank accounts in this currency.
                  Accounts in other currencies are returned as remainder.
                  NEVER silently aggregate different currencies.

    Returns:
        (top_k, remainder) — two lists of RouteResult.
        top_k has len <= k; remainder contains the rest.
    """
    if k <= 0:
        return [], results

    # Filter to PRIORITY_REVIEW only
    priority = [r for r in results if r.route == RouteEnum.PRIORITY_REVIEW]
    non_priority = [r for r in results if r.route != RouteEnum.PRIORITY_REVIEW]

    # Currency filter — never mix currencies in ranking
    if currency is not None:
        in_currency = [r for r in priority if r.currency == currency]
        wrong_currency = [r for r in priority if r.currency != currency]
        priority = in_currency
        non_priority = non_priority + wrong_currency

    # Sort deterministically
    sorted_priority = sorted(priority, key=_sort_key)

    top_k = sorted_priority[:k]
    remainder = sorted_priority[k:] + non_priority

    return top_k, remainder


def add_ranks(cases: list[RouteResult]) -> list[dict]:
    """
    Add a 1-based rank to each case dict for API response.
    Rank 1 = highest exposure proxy (most financially urgent to review).
    """
    return [
        {**case.model_dump(), "rank": i + 1}
        for i, case in enumerate(cases)
    ]


def compute_budget_slots_remaining(
    k_configured: int,
    open_cases_in_period: int,
) -> int:
    """
    How many reviewer slots remain in the current period.
    Deducts already-open PRIORITY_REVIEW cases from the configured K.
    Returns 0 if fully occupied.
    """
    remaining = k_configured - open_cases_in_period
    return max(remaining, 0)


def rank_top_k(accounts: list[dict], k: int = 10) -> list[dict]:
    """
    Convenience adapter for validation harnesses.
    Ranks account dictionaries by exposure (p30 * MRR) DESC, p7 DESC, customer_id ASC.
    """
    def key_fn(a: dict):
        p30 = a.get("p_churn_30d") or 0.0
        mrr = a.get("mrr_minor") or 0
        exposure = round(p30 * mrr)
        p7 = a.get("p_churn_7d") or 0.0
        cid = str(a.get("customer_id", ""))
        return (-exposure, -p7, cid)

    sorted_accs = sorted(accounts, key=key_fn)
    return sorted_accs[:k]

