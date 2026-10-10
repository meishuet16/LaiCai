"""
evaluator.py — Decision-quality evaluation & RevenueCaptured@K (§7.8).

Evaluates historical identification coverage across strategy baselines:
  - Strategy A: Descending calibrated p30 only
  - Strategy B: Descending p30 × MRR (exposure proxy only)
  - Strategy C: Full RetainIQ planning (reliability gating + cooldown + p30×MRR + p7 tie-break)

METRIC FORMULA (§7.8):
  RevenueCaptured@K(t) =
    sum(as_of_MRR of selected eligible accounts that actually churn in next 30d)
    / sum(as_of_MRR of all evaluation-eligible accounts that actually churn in next 30d)

CRITICAL RULES:
  - Label: 'Subsequently Churned MRR Identified@K' / 'historical_identification_coverage'.
  - NOT money saved, NOT causal uplift, NOT actual saved customers.
  - Zero denominator produces None / N/A.
  - Compares identical historical cohort, cutoffs, currency, and slot constraints.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from .models import EvaluationCohortAccount, EvaluationResponse


def evaluate_decision_strategy(
    cohort: list[EvaluationCohortAccount],
    strategy: str = "C",
    k: int = 10,
    currency: str = "MYR",
    as_of: Optional[datetime] = None,
) -> EvaluationResponse:
    """
    Run frozen historical replay evaluation for a given selection strategy.

    Args:
        cohort: List of historical account records with ground truth actually_churned_30d.
        strategy: "A" (Risk only), "B" (Risk x MRR), or "C" (RetainIQ gated planning).
        k: Reviewer capacity constraint (number of slots).
        currency: Evaluation currency.
        as_of: Cutoff timestamp.
    """
    strat = strategy.upper().strip()
    if strat not in ("A", "B", "C"):
        raise ValueError(f"Strategy must be 'A', 'B', or 'C'; received '{strategy}'")

    if as_of is None:
        as_of = datetime.now(timezone.utc)

    strat_descriptions = {
        "A": "Descending calibrated p30 only (basic churn risk ranking)",
        "B": "Descending p30 × MRR (pure revenue exposure ranking)",
        "C": "RetainIQ planning: reliability gating + cooldown + K slots + p30×MRR + p7 urgency tie-break",
    }

    # Denominator: total MRR of accounts that actually churned in next 30 days
    total_churned_mrr = sum(acc.as_of_mrr_minor for acc in cohort if acc.actually_churned_30d)
    total_churned_count = sum(1 for acc in cohort if acc.actually_churned_30d)

    # ------------------------------------------------------------------
    # Strategy Selection Mechanics
    # ------------------------------------------------------------------
    if strat == "A":
        # Strategy A: sort by p30 DESC, customer_id ASC
        sorted_cohort = sorted(
            cohort,
            key=lambda x: (-x.p_churn_30d, x.customer_id),
        )
        selected = sorted_cohort[:k]

    elif strat == "B":
        # Strategy B: sort by (p30 * MRR) DESC, customer_id ASC
        sorted_cohort = sorted(
            cohort,
            key=lambda x: (
                -round(x.p_churn_30d * x.as_of_mrr_minor),
                x.customer_id,
            ),
        )
        selected = sorted_cohort[:k]

    else:
        # Strategy C (RetainIQ Full Planning):
        # 1. Gate out insufficient/limited evidence (investigation queue)
        # 2. Gate out accounts with active cooldown
        eligible = [
            acc for acc in cohort
            if acc.reliability_status == "sufficient_evidence"
            and not acc.cooldown_active
        ]

        # 3. Deterministic 4-level Top-K sort:
        #    exposure DESC, p7 DESC, opened_at ASC, customer_id ASC
        sorted_cohort = sorted(
            eligible,
            key=lambda x: (
                -round(x.p_churn_30d * x.as_of_mrr_minor),
                -x.p_churn_7d,
                x.case_opened_at or datetime.min.replace(tzinfo=timezone.utc),
                x.customer_id,
            ),
        )
        selected = sorted_cohort[:k]

    # Numerator: churned MRR captured within selected top-K
    captured_churned_mrr = sum(acc.as_of_mrr_minor for acc in selected if acc.actually_churned_30d)
    captured_churned_count = sum(1 for acc in selected if acc.actually_churned_30d)

    notes = [
        "Historical identification coverage — NOT saved revenue or causal retention",
        "Zero causal claim made without randomized intervention trials",
    ]

    revenue_captured = None
    recall = None
    note_text = None

    if total_churned_mrr > 0:
        revenue_captured = round(captured_churned_mrr / total_churned_mrr, 4)
    else:
        note_text = "N/A — zero churned MRR observed in this evaluation cohort."

    if total_churned_count > 0:
        recall = round(captured_churned_count / total_churned_count, 4)

    return EvaluationResponse(
        strategy=strat,
        strategy_description=strat_descriptions[strat],
        currency=currency,
        as_of=as_of,
        k_slots=k,
        revenue_captured_at_k=revenue_captured,
        subsequently_churned_mrr_identified_minor=captured_churned_mrr,
        total_churned_mrr_cohort_minor=total_churned_mrr,
        recall_at_k=recall,
        revenue_captured_label="Subsequently Churned MRR Identified@K",
        evaluation_label="historical_identification_coverage — NOT saved revenue",
        note=note_text,
        notes=notes,
    )


def evaluate_strategies(cohort: list, k: int = 10) -> dict[str, dict]:
    """
    Adapter convenience function to evaluate strategies A, B, and C against a cohort.
    Strictly follows §7.8 evaluation rules.
    """
    typed_cohort: list[EvaluationCohortAccount] = []
    for item in cohort:
        if isinstance(item, EvaluationCohortAccount):
            typed_cohort.append(item)
        elif isinstance(item, dict):
            typed_cohort.append(
                EvaluationCohortAccount(
                    customer_id=item.get("customer_id", ""),
                    as_of_mrr_minor=item.get("as_of_mrr_minor") or item.get("mrr_minor", 0),
                    p_churn_30d=item.get("p_churn_30d", 0.0),
                    p_churn_7d=item.get("p_churn_7d", 0.0),
                    reliability_status=item.get("reliability_status", "sufficient_evidence"),
                    cooldown_active=item.get("cooldown_active", False),
                    actually_churned_30d=item.get("actually_churned_30d", False),
                )
            )

    results = {}
    for strat in ("A", "B", "C"):
        if not typed_cohort:
            results[strat] = {
                "strategy": strat,
                "revenue_captured_at_k": None,
                "recall_at_k": None,
                "k_slots": k,
            }
        else:
            resp = evaluate_decision_strategy(typed_cohort, strategy=strat, k=k)
            results[strat] = {
                "strategy": strat,
                "revenue_captured_at_k": resp.revenue_captured_at_k,
                "recall_at_k": resp.recall_at_k,
                "subsequently_churned_mrr_identified_minor": resp.subsequently_churned_mrr_identified_minor,
                "total_churned_mrr_cohort_minor": resp.total_churned_mrr_cohort_minor,
                "k_slots": k,
            }

    return results
