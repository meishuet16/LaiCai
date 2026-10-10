"""
test_roi_calculator.py — Unit tests for One-month break-even ROI calculation (§7.6).

Verifies exact arithmetic from spec, edge cases, percentage points vs percentage
formatting rules, and strict SCENARIO_ONLY labeling.
"""

import pytest

from backend.decision.enums import ScenarioLabel
from backend.decision.roi_calculator import calculate_break_even_roi


class TestSpecVerifiedArithmetic:
    """
    Verifies the illustrative example given in §7.6:
      MRR = RM 1,200 (120,000 minor units)
      contribution_margin = 70% (0.70)
      p30 = 65% (0.65)
      cost = RM 150 (15,000 minor units)
      assumed_reduction = 10 pp (0.10)

      contribution_value = 1200 * 0.70 = RM 840 (84,000 minor)
      break_even_abs_reduction = 150 / 840 = 0.178571 = 17.86 pp
      break_even_share = 0.178571 / 0.65 = 27.47%
      scenario_gross = 0.10 * 840 = RM 84 (8,400 minor)
      scenario_net = 84 - 150 = -RM 66 (-6,600 minor)
      scenario_roi = -66 / 150 = -44.0%
    """

    def test_spec_verified_example(self):
        card = calculate_break_even_roi(
            case_id="case_002",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.65,
            action_cost_minor=15000,
            contribution_margin=0.70,
            assumed_abs_reduction=0.10,
        )

        assert card.contribution_value_minor == 84000
        assert card.break_even_abs_reduction_pp == 17.86
        assert card.break_even_share_of_baseline_pct == 27.47
        assert card.scenario_gross_value_minor == 8400
        assert card.scenario_net_value_minor == -6600
        assert card.scenario_roi_pct == -44.0
        assert card.break_even_achievable is True
        assert card.scenario_label == ScenarioLabel.SCENARIO_ONLY
        assert card.unavailable_reason is None

    def test_positive_roi_scenario(self):
        """When assumed reduction exceeds break-even reduction, net and ROI are positive."""
        card = calculate_break_even_roi(
            case_id="case_002",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.65,
            action_cost_minor=15000,
            contribution_margin=0.70,
            assumed_abs_reduction=0.25,  # 25 pp reduction > 17.86 pp
        )

        # gross = 0.25 * 84000 = 21000
        # net = 21000 - 15000 = 6000
        # roi = 6000 / 15000 = 40.0%
        assert card.scenario_gross_value_minor == 21000
        assert card.scenario_net_value_minor == 6000
        assert card.scenario_roi_pct == 40.0
        assert card.break_even_achievable is True


class TestEdgeCasesAndGuardrails:
    """Verifies edge cases per §7.6 non-negotiable rules."""

    def test_zero_action_cost_produces_roi_none(self):
        """Spec: 'zero cost produces ROI N/A'."""
        card = calculate_break_even_roi(
            case_id="case_free",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.65,
            action_cost_minor=0,
            contribution_margin=0.70,
            assumed_abs_reduction=0.05,
        )

        assert card.break_even_abs_reduction_pp == 0.0
        assert card.break_even_share_of_baseline_pct == 0.0
        assert card.scenario_roi_pct is None
        assert card.break_even_achievable is True
        assert card.scenario_gross_value_minor == round(0.05 * 84000)
        assert card.scenario_net_value_minor == card.scenario_gross_value_minor

    def test_break_even_exceeds_p30_marked_not_achievable(self):
        """Spec: 'if break-even reduction exceeds p30, mark not achievable in this simplified scenario'."""
        # cost = 60000 minor; contribution = 84000 -> break_even = 60000/84000 = 71.43 pp
        # p30 = 0.50 (50 pp) -> 71.43 pp > 50 pp
        card = calculate_break_even_roi(
            case_id="case_expensive",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.50,
            action_cost_minor=60000,
            contribution_margin=0.70,
            assumed_abs_reduction=0.10,
        )

        assert card.break_even_abs_reduction_pp == 71.43
        assert card.break_even_achievable is False
        assert any("not achievable" in note for note in card.notes)

    def test_missing_mrr_returns_unavailable(self):
        """Spec: 'If baseline unknown, show N/A'."""
        card = calculate_break_even_roi(
            case_id="case_no_mrr",
            as_of_mrr_minor=None,
            currency="MYR",
            p_churn_30d=0.65,
            action_cost_minor=15000,
            contribution_margin=0.70,
        )

        assert card.unavailable_reason == "mrr_missing_or_stale"
        assert card.contribution_value_minor is None
        assert card.break_even_abs_reduction_pp is None
        assert card.scenario_roi_pct is None

    def test_missing_p30_returns_unavailable(self):
        """Missing baseline probability cannot compute break-even share."""
        card = calculate_break_even_roi(
            case_id="case_no_p30",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=None,
            action_cost_minor=15000,
            contribution_margin=0.70,
        )

        assert card.unavailable_reason == "p_churn_30d_missing_or_non_positive"
        assert card.break_even_share_of_baseline_pct is None

    def test_zero_or_negative_p30_returns_unavailable(self):
        card = calculate_break_even_roi(
            case_id="case_zero_p30",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.0,
            action_cost_minor=15000,
            contribution_margin=0.70,
        )

        assert card.unavailable_reason == "p_churn_30d_missing_or_non_positive"

    def test_invalid_contribution_margin(self):
        card = calculate_break_even_roi(
            case_id="case_bad_margin",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.65,
            action_cost_minor=15000,
            contribution_margin=0.0,
        )

        assert card.unavailable_reason == "invalid_contribution_margin"

    def test_assumed_reduction_clamped_to_baseline(self):
        """Assumed reduction cannot exceed baseline churn risk."""
        card = calculate_break_even_roi(
            case_id="case_clamp",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.40,
            action_cost_minor=15000,
            contribution_margin=0.70,
            assumed_abs_reduction=0.60,  # 60 pp > 40 pp baseline
        )

        # Clamped to 0.40: gross = round(0.40 * 84000) = 33600
        assert card.scenario_gross_value_minor == 33600
        assert any("clamped" in note for note in card.notes)

    def test_scenario_only_label_strictly_enforced(self):
        """Card must always have SCENARIO_ONLY label."""
        card = calculate_break_even_roi(
            case_id="case_label_check",
            as_of_mrr_minor=120000,
            currency="MYR",
            p_churn_30d=0.65,
            action_cost_minor=15000,
        )

        assert card.scenario_label == ScenarioLabel.SCENARIO_ONLY
        assert any("percentage points (pp)" in n for n in card.notes)
        assert any("percentage (%)" in n for n in card.notes)
