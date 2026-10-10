"""
test_action_catalog.py — Unit tests for fact-based Next Best Action catalog (§7.4).

Verifies:
  - Fact-based candidate proposal generation (no SHAP as causal trigger)
  - Eligibility and contraindication enforcement
  - Cooldown and open-action suppression
  - Conditional action rules (PRODUCT_WALKTHROUGH requires feature events)
  - Data investigation routing when evidence is missing/stale (no fabricated incentives)
  - Strict exclusion of disabled and simulation-only actions from live proposals
  - Supporting fact references attachment
"""

from datetime import datetime, timezone
import pytest

from backend.decision.action_catalog import (
    ACTION_CATALOG, generate_candidate_proposals, get_disabled_actions_list,
)
from backend.decision.enums import ActionCode, ActionMode
from backend.decision.models import CustomerFacts


@pytest.fixture
def base_facts():
    """Default valid facts at cutoff."""
    return CustomerFacts(
        tenant_id="tenant_abc",
        customer_id="cust_001",
        as_of=datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc),
    )


class TestCatalogIntegrity:
    """Verifies static catalog definitions comply with §7.4."""

    def test_all_canonical_action_codes_present(self):
        for code in ActionCode:
            assert code in ACTION_CATALOG

    def test_operational_modes(self):
        assert ACTION_CATALOG[ActionCode.ACCOUNT_CHECK_IN].mode == ActionMode.OPERATIONAL
        assert ACTION_CATALOG[ActionCode.PAYMENT_RECOVERY].mode == ActionMode.OPERATIONAL
        assert ACTION_CATALOG[ActionCode.DATA_INVESTIGATION].mode == ActionMode.OPERATIONAL
        assert ACTION_CATALOG[ActionCode.NO_INTERVENTION].mode == ActionMode.OPERATIONAL
        assert ACTION_CATALOG[ActionCode.PRODUCT_WALKTHROUGH].mode == ActionMode.CONDITIONAL
        assert ACTION_CATALOG[ActionCode.TECH_SUPPORT_ESCALATION].mode == ActionMode.DISABLED
        assert ACTION_CATALOG[ActionCode.PLAN_REVIEW].mode == ActionMode.SIMULATION_ONLY
        assert ACTION_CATALOG[ActionCode.PAUSE].mode == ActionMode.SIMULATION_ONLY
        assert ACTION_CATALOG[ActionCode.DOWNGRADE].mode == ActionMode.SIMULATION_ONLY
        assert ACTION_CATALOG[ActionCode.CONDITIONAL_DISCOUNT].mode == ActionMode.SIMULATION_ONLY

    def test_disabled_actions_never_in_proposals(self, base_facts):
        """Simulation-only and disabled actions must NEVER enter live executable proposals."""
        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]

        non_operational = [
            ActionCode.TECH_SUPPORT_ESCALATION,
            ActionCode.PLAN_REVIEW,
            ActionCode.PAUSE,
            ActionCode.DOWNGRADE,
            ActionCode.CONDITIONAL_DISCOUNT,
        ]
        for code in non_operational:
            assert code not in proposed_codes

    def test_disabled_actions_reported_in_disabled_list(self, base_facts):
        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        disabled_codes = [d.action_code for d in resp.disabled_actions]
        assert ActionCode.TECH_SUPPORT_ESCALATION in disabled_codes
        assert ActionCode.CONDITIONAL_DISCOUNT in disabled_codes
        assert ActionCode.PLAN_REVIEW in disabled_codes


class TestAccountCheckIn:
    """Tests for ACCOUNT_CHECK_IN generation and contraindications."""

    def test_eligible_with_usage_deviation(self, base_facts):
        base_facts.has_usage_deviation = True
        base_facts.usage_event_id = "ue_4421"
        base_facts.usage_deviation_detail = "session count dropped 62%"

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        check_in_proposals = [p for p in resp.proposals if p.action_code == ActionCode.ACCOUNT_CHECK_IN]

        assert len(check_in_proposals) == 1
        prop = check_in_proposals[0]
        assert prop.mode == ActionMode.OPERATIONAL
        assert len(prop.supporting_fact_refs) == 1
        assert prop.supporting_fact_refs[0].table == "usage_events"
        assert prop.supporting_fact_refs[0].id == "ue_4421"

    def test_disqualified_by_contradictory_status(self, base_facts):
        """Contraindication: contradictory account status blocks check-in."""
        base_facts.has_usage_deviation = True
        base_facts.usage_event_id = "ue_4421"
        base_facts.contradictory_status = True

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]
        assert ActionCode.ACCOUNT_CHECK_IN not in proposed_codes

    def test_disqualified_by_active_cooldown(self, base_facts):
        """Cooldown active for ACCOUNT_CHECK_IN suppresses proposal."""
        base_facts.has_usage_deviation = True
        base_facts.usage_event_id = "ue_4421"
        base_facts.active_cooldown_actions = [ActionCode.ACCOUNT_CHECK_IN]

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]
        assert ActionCode.ACCOUNT_CHECK_IN not in proposed_codes


class TestPaymentRecovery:
    """Tests for PAYMENT_RECOVERY generation and cooldown."""

    def test_eligible_with_failed_billing_event(self, base_facts):
        base_facts.has_failed_billing = True
        base_facts.billing_event_id = "be_8812"
        base_facts.billing_detail = "payment failed 2026-10-04"

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        recovery_proposals = [p for p in resp.proposals if p.action_code == ActionCode.PAYMENT_RECOVERY]

        assert len(recovery_proposals) == 1
        prop = recovery_proposals[0]
        assert prop.mode == ActionMode.OPERATIONAL
        assert len(prop.supporting_fact_refs) == 1
        assert prop.supporting_fact_refs[0].table == "billing_events"
        assert prop.supporting_fact_refs[0].id == "be_8812"

    def test_disqualified_by_cooldown(self, base_facts):
        base_facts.has_failed_billing = True
        base_facts.billing_event_id = "be_8812"
        base_facts.active_cooldown_actions = [ActionCode.PAYMENT_RECOVERY]

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]
        assert ActionCode.PAYMENT_RECOVERY not in proposed_codes


class TestProductWalkthrough:
    """Tests conditional action PRODUCT_WALKTHROUGH."""

    def test_generated_when_feature_gap_exists(self, base_facts):
        base_facts.has_feature_gap = True
        base_facts.feature_event_id = "fe_101"
        base_facts.feature_gap_detail = "Onboarding step 3 incomplete"

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        walkthrough_props = [p for p in resp.proposals if p.action_code == ActionCode.PRODUCT_WALKTHROUGH]

        assert len(walkthrough_props) == 1
        prop = walkthrough_props[0]
        assert prop.mode == ActionMode.CONDITIONAL
        assert prop.supporting_fact_refs[0].table == "feature_events"

    def test_not_generated_without_feature_event(self, base_facts):
        base_facts.has_feature_gap = False
        base_facts.feature_event_id = None

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]
        assert ActionCode.PRODUCT_WALKTHROUGH not in proposed_codes


class TestDataInvestigationAndEvidenceIntegrity:
    """
    Spec: 'If evidence is missing, route to investigation instead of
    pretending to know the right incentive.'
    """

    def test_insufficient_evidence_generates_data_investigation(self, base_facts):
        base_facts.is_evidence_insufficient = True
        # Even if usage deviation is also asserted, missing evidence must prioritize investigation
        base_facts.has_usage_deviation = True
        base_facts.usage_event_id = "ue_123"

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]

        assert ActionCode.DATA_INVESTIGATION in proposed_codes
        # Discretionary incentive NOT fabricated
        assert ActionCode.ACCOUNT_CHECK_IN not in proposed_codes
        # NO_INTERVENTION is always an allowed option
        assert ActionCode.NO_INTERVENTION in proposed_codes

    def test_data_quality_issues_generates_investigation(self, base_facts):
        base_facts.data_quality_issues = ["usage_events_partially_stale", "mrr_basis_unverified"]

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        investigation_props = [p for p in resp.proposals if p.action_code == ActionCode.DATA_INVESTIGATION]

        assert len(investigation_props) == 1
        prop = investigation_props[0]
        assert len(prop.supporting_fact_refs) == 2
        assert prop.supporting_fact_refs[0].table == "data_quality_log"


class TestSuppressionAndAlwaysAvailableActions:
    """Tests suppression rules and NO_INTERVENTION guarantee."""

    def test_open_action_suppresses_discretionary_proposals(self, base_facts):
        """Spec §7.3: Account with open action must not repeatedly receive proposals."""
        base_facts.has_open_action = True
        base_facts.has_usage_deviation = True
        base_facts.usage_event_id = "ue_4421"
        base_facts.has_failed_billing = True
        base_facts.billing_event_id = "be_8812"

        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]

        assert ActionCode.ACCOUNT_CHECK_IN not in proposed_codes
        assert ActionCode.PAYMENT_RECOVERY not in proposed_codes
        assert proposed_codes == [ActionCode.NO_INTERVENTION]

    def test_no_intervention_is_always_present(self, base_facts):
        """NO_INTERVENTION must be included in all proposals."""
        resp = generate_candidate_proposals(case_id="case_001", facts=base_facts)
        proposed_codes = [p.action_code for p in resp.proposals]
        assert ActionCode.NO_INTERVENTION in proposed_codes
