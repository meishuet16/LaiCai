"""
roi_calculator.py — One-month What-If / break-even ROI calculation (§7.6).

Sensitivity analysis engine for proposed retention actions.
Ref: RetainIQ_v2_Complete_Requirements.md §7.6:
  "Question: 'How much would this proposed action need to reduce 30-day churn risk
   to cover its estimated cost?' This is a sensitivity analysis, not an effect prediction."

NON-NEGOTIABLE RULES:
  - ALWAYS label output SCENARIO_ONLY. Never claim causal uplift or real retention savings.
  - Absolute reduction must be displayed in percentage points (pp).
  - Relative reduction must be displayed as percentage of baseline risk (%).
  - Never interchange pp and %.
  - If denominator <= 0 or baseline unknown, show N/A.
  - Zero action cost produces ROI N/A.
  - If break-even reduction exceeds p30, mark break_even_achievable = False
    ("not achievable in this simplified scenario").
  - Valuation window is strictly one month (no unbacked multi-month compounding).
"""

from __future__ import annotations
from typing import Optional

from .enums import ScenarioLabel
from .models import ROICard


def calculate_break_even_roi(
    case_id: str,
    as_of_mrr_minor: Optional[int],
    currency: str,
    p_churn_30d: Optional[float],
    action_cost_minor: int,
    contribution_margin: float = 0.70,
    assumed_abs_reduction: Optional[float] = None,
) -> ROICard:
    """
    Compute deterministic break-even sensitivity and scenario ROI.

    Args:
        case_id: Identifier of the decision case.
        as_of_mrr_minor: Point-in-time MRR in minor currency units (e.g. cents).
                         None if MRR is missing/stale.
        currency: ISO-4217 currency code.
        p_churn_30d: Calibrated 30-day churn probability (0.0 to 1.0).
        action_cost_minor: Estimated action cost in minor currency units (>= 0).
        contribution_margin: Admin-configured profit margin (0.0 < margin <= 1.0). Default 0.70.
        assumed_abs_reduction: User-set assumed 30-day absolute churn risk reduction
                               (e.g., 0.10 = 10 pp). Clamped within [0, p30].

    Returns:
        ROICard with all calculated sensitivity metrics and strict guardrail labels.
    """
    notes: list[str] = [
        "Absolute reduction displayed in percentage points (pp)",
        "Relative risk share displayed as percentage (%)",
        "VALIDATED_INCREMENTAL_ROI unavailable in MVP — no causal evidence",
    ]

    base_card = ROICard(
        case_id=case_id,
        as_of_mrr_minor=as_of_mrr_minor,
        currency=currency,
        p_churn_30d=p_churn_30d,
        contribution_margin=contribution_margin,
        action_cost_minor=action_cost_minor,
        assumed_abs_reduction=assumed_abs_reduction,
        scenario_label=ScenarioLabel.SCENARIO_ONLY,
        notes=notes,
    )

    # ------------------------------------------------------------------
    # Guard 1: Missing or non-positive MRR
    # ------------------------------------------------------------------
    if as_of_mrr_minor is None:
        base_card.unavailable_reason = "mrr_missing_or_stale"
        return base_card

    if as_of_mrr_minor <= 0:
        base_card.unavailable_reason = "mrr_non_positive"
        return base_card

    # ------------------------------------------------------------------
    # Guard 2: Missing or invalid baseline risk p30
    # ------------------------------------------------------------------
    if p_churn_30d is None or p_churn_30d <= 0.0:
        base_card.unavailable_reason = "p_churn_30d_missing_or_non_positive"
        return base_card

    # ------------------------------------------------------------------
    # Guard 3: Invalid contribution margin
    # ------------------------------------------------------------------
    if contribution_margin <= 0.0 or contribution_margin > 1.0:
        base_card.unavailable_reason = "invalid_contribution_margin"
        return base_card

    # ------------------------------------------------------------------
    # Step 1: Contribution value (one month)
    # contribution_value = MRR * contribution_margin
    # ------------------------------------------------------------------
    contribution_value_minor = round(as_of_mrr_minor * contribution_margin)
    base_card.contribution_value_minor = contribution_value_minor

    if contribution_value_minor <= 0:
        base_card.unavailable_reason = "contribution_value_zero"
        return base_card

    # ------------------------------------------------------------------
    # Step 2: Break-even absolute reduction and share of baseline
    # break_even_abs_reduction = action_cost / contribution_value
    # break_even_share_of_baseline = break_even_abs_reduction / p30
    # ------------------------------------------------------------------
    if action_cost_minor == 0:
        # Zero cost action: covers itself without needing any reduction
        base_card.break_even_abs_reduction_pp = 0.0
        base_card.break_even_share_of_baseline_pct = 0.0
        base_card.break_even_achievable = True
        base_card.notes.append("Zero action cost: break-even reduction is 0.0 pp; scenario ROI is N/A.")
    else:
        break_even_abs = action_cost_minor / contribution_value_minor
        base_card.break_even_abs_reduction_pp = round(break_even_abs * 100.0, 2)

        break_even_share = break_even_abs / p_churn_30d
        base_card.break_even_share_of_baseline_pct = round(break_even_share * 100.0, 2)

        # Check achievable status: if break_even > p30, cannot be achieved within baseline
        if break_even_abs > p_churn_30d:
            base_card.break_even_achievable = False
            base_card.notes.append(
                f"Break-even reduction ({base_card.break_even_abs_reduction_pp} pp) "
                f"exceeds baseline risk ({round(p_churn_30d * 100.0, 2)} pp) — "
                "not achievable in this simplified scenario."
            )
        else:
            base_card.break_even_achievable = True

    # ------------------------------------------------------------------
    # Step 3: What-if Scenario calculation (if assumed reduction given)
    # scenario_gross = assumed_abs_reduction * contribution_value
    # scenario_net = scenario_gross - action_cost
    # scenario_roi = scenario_net / action_cost
    # ------------------------------------------------------------------
    if assumed_abs_reduction is not None and assumed_abs_reduction >= 0.0:
        # Clamp assumed reduction to baseline p30
        effective_reduction = min(assumed_abs_reduction, p_churn_30d)
        if effective_reduction < assumed_abs_reduction:
            base_card.notes.append(
                f"Assumed reduction ({round(assumed_abs_reduction * 100.0, 2)} pp) "
                f"clamped to baseline risk ({round(p_churn_30d * 100.0, 2)} pp)."
            )

        scenario_gross_minor = round(effective_reduction * contribution_value_minor)
        scenario_net_minor = scenario_gross_minor - action_cost_minor

        base_card.scenario_gross_value_minor = scenario_gross_minor
        base_card.scenario_net_value_minor = scenario_net_minor

        if action_cost_minor > 0:
            roi_fraction = scenario_net_minor / action_cost_minor
            base_card.scenario_roi_pct = round(roi_fraction * 100.0, 1)
        else:
            # Spec: "zero cost produces ROI N/A"
            base_card.scenario_roi_pct = None

    return base_card


def break_even_card(
    mrr_minor: int,
    contribution_margin: float,
    p30: float,
    action_cost_minor: int,
    assumed_abs_reduction: Optional[float] = None,
) -> dict:
    """
    Adapter convenience function returning a break-even card dictionary.
    Strictly follows §7.6 What-If sensitivity analysis rules and §10.3 guardrails.
    """
    contribution_value = round(mrr_minor * contribution_margin)

    if contribution_value > 0:
        be_abs = action_cost_minor / contribution_value
    else:
        be_abs = None

    if be_abs is not None and p30 > 0.0:
        be_share = be_abs / p30
    else:
        be_share = None

    be_achievable = None
    if be_abs is not None:
        be_achievable = (be_abs <= p30)

    scenario_gross = None
    scenario_net = None
    scenario_roi = None

    if assumed_abs_reduction is not None:
        eff_reduction = min(assumed_abs_reduction, p30)
        scenario_gross = round(eff_reduction * contribution_value)
        scenario_net = scenario_gross - action_cost_minor
        if action_cost_minor > 0:
            scenario_roi = scenario_net / action_cost_minor
        else:
            scenario_roi = None

    return {
        "contribution_value_minor": contribution_value,
        "break_even_abs_reduction": be_abs,
        "break_even_share": be_share,
        "break_even_achievable": be_achievable,
        "scenario_gross_minor": scenario_gross,
        "scenario_net_minor": scenario_net,
        "scenario_roi": scenario_roi,
        "evidence_label": "SCENARIO_ONLY",
    }
