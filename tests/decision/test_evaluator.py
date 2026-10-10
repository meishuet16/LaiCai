"""
test_evaluator.py — Unit tests for RevenueCaptured@K decision-quality evaluation (§7.8).

Verifies:
  - Strategy A (p30 descending baseline)
  - Strategy B (p30 * MRR exposure baseline)
  - Strategy C (RetainIQ gated planning: reliability gate + cooldown + p30*MRR + p7 tie-break)
  - RevenueCaptured@K exact ratio computation
  - Zero denominator produces None / N/A
  - Mandatory labeling: 'Subsequently Churned MRR Identified@K' and 'historical_identification_coverage'
"""

from datetime import datetime, timezone
import pytest

from backend.decision.evaluator import evaluate_decision_strategy
from backend.decision.models import EvaluationCohortAccount


@pytest.fixture
def spec_eval_cohort():
    """
    Cohort based on §7.3 and §7.8 accounts:
      Bob:     MRR=RM1,200 (120,000 minor), p30=0.65, p7=0.22, churned=True, sufficient
      Charlie: MRR=RM500   (50,000 minor),  p30=0.78, p7=0.55, churned=False, sufficient
      Alice:   MRR=RM100   (10,000 minor),  p30=0.85, p7=0.12, churned=True, sufficient
      Dana:    MRR=RM900   (90,000 minor),  p30=0.45, p7=0.08, churned=True, limited (reliability gate)
      Edward:  MRR=RM300   (30,000 minor),  p30=0.52, p7=0.10, churned=True, cooldown=True (cooldown gate)

    Total churned MRR in cohort = Bob (120k) + Alice (10k) + Dana (90k) + Edward (30k) = 250,000 minor
    """
    return [
        EvaluationCohortAccount(
            customer_id="cust_bob",
            as_of_mrr_minor=120000,
            p_churn_30d=0.65,
            p_churn_7d=0.22,
            reliability_status="sufficient_evidence",
            cooldown_active=False,
            actually_churned_30d=True,
        ),
        EvaluationCohortAccount(
            customer_id="cust_charlie",
            as_of_mrr_minor=50000,
            p_churn_30d=0.78,
            p_churn_7d=0.55,
            reliability_status="sufficient_evidence",
            cooldown_active=False,
            actually_churned_30d=False,
        ),
        EvaluationCohortAccount(
            customer_id="cust_alice",
            as_of_mrr_minor=10000,
            p_churn_30d=0.85,
            p_churn_7d=0.12,
            reliability_status="sufficient_evidence",
            cooldown_active=False,
            actually_churned_30d=True,
        ),
        EvaluationCohortAccount(
            customer_id="cust_dana",
            as_of_mrr_minor=90000,
            p_churn_30d=0.45,
            p_churn_7d=0.08,
            reliability_status="limited_evidence",
            cooldown_active=False,
            actually_churned_30d=True,
        ),
        EvaluationCohortAccount(
            customer_id="cust_edward",
            as_of_mrr_minor=30000,
            p_churn_30d=0.52,
            p_churn_7d=0.10,
            reliability_status="sufficient_evidence",
            cooldown_active=True,
            actually_churned_30d=True,
        ),
    ]


class TestStrategyEvaluationMechanics:
    """Verifies strategies A, B, and C mechanics."""

    def test_strategy_a_risk_only(self, spec_eval_cohort):
        """Strategy A ranks strictly by p30: Alice (0.85), Charlie (0.78), Bob (0.65)."""
        # For K=2: selected = Alice (10k, churned) + Charlie (50k, not churned)
        # Captured churned MRR = 10,000
        # Total churned MRR = 250,000
        # RevenueCaptured@2 = 10,000 / 250,000 = 0.04 (4.0%)
        resp = evaluate_decision_strategy(
            cohort=spec_eval_cohort,
            strategy="A",
            k=2,
            currency="MYR",
        )

        assert resp.strategy == "A"
        assert resp.total_churned_mrr_cohort_minor == 250000
        assert resp.subsequently_churned_mrr_identified_minor == 10000
        assert resp.revenue_captured_at_k == 0.04
        assert resp.revenue_captured_label == "Subsequently Churned MRR Identified@K"
        assert "historical_identification_coverage" in resp.evaluation_label

    def test_strategy_b_exposure_only(self, spec_eval_cohort):
        """
        Strategy B ranks by p30 * MRR:
          Bob:     0.65 * 120,000 = 78,000
          Dana:    0.45 * 90,000  = 40,500
          Charlie: 0.78 * 50,000  = 39,000
          Edward:  0.52 * 30,000  = 15,600
          Alice:   0.85 * 10,000  = 8,500
        For K=2: selected = Bob (120k, churned) + Dana (90k, churned)
        Captured = 120k + 90k = 210,000
        RevenueCaptured@2 = 210,000 / 250,000 = 0.84 (84.0%)
        """
        resp = evaluate_decision_strategy(
            cohort=spec_eval_cohort,
            strategy="B",
            k=2,
            currency="MYR",
        )

        assert resp.strategy == "B"
        assert resp.subsequently_churned_mrr_identified_minor == 210000
        assert resp.revenue_captured_at_k == 0.84

    def test_strategy_c_retainiq_planning(self, spec_eval_cohort):
        """
        Strategy C (RetainIQ):
          - Gates out Dana (limited evidence -> routed to investigation queue, not priority slots)
          - Gates out Edward (active cooldown)
          Eligible ranked: Bob (78k), Charlie (39k), Alice (8.5k)
        For K=2: selected = Bob (120k, churned) + Charlie (50k, not churned)
        Captured = 120,000
        RevenueCaptured@2 = 120,000 / 250,000 = 0.48 (48.0%)
        """
        resp = evaluate_decision_strategy(
            cohort=spec_eval_cohort,
            strategy="C",
            k=2,
            currency="MYR",
        )

        assert resp.strategy == "C"
        assert resp.subsequently_churned_mrr_identified_minor == 120000
        assert resp.revenue_captured_at_k == 0.48
        assert resp.recall_at_k == 0.25  # 1 churned account out of 4 total churned accounts


class TestEvaluationEdgeCases:
    """Verifies edge cases per §7.8."""

    def test_zero_churned_cohort_returns_none(self):
        """Zero denominator produces N/A per §7.8."""
        cohort = [
            EvaluationCohortAccount(
                customer_id="cust_healthy",
                as_of_mrr_minor=100000,
                p_churn_30d=0.20,
                actually_churned_30d=False,  # No churn
            )
        ]

        resp = evaluate_decision_strategy(cohort=cohort, strategy="C", k=5)
        assert resp.revenue_captured_at_k is None
        assert "N/A" in resp.note

    def test_invalid_strategy_raises_error(self, spec_eval_cohort):
        with pytest.raises(ValueError, match="Strategy must be 'A', 'B', or 'C'"):
            evaluate_decision_strategy(cohort=spec_eval_cohort, strategy="D")
