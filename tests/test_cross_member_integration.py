"""Synthetic cross-member contract tests.

These tests verify existing typed boundaries only. They do not stand in for a
Member 1 backend, a Member 3 decision engine, or a Member 4 frontend.
"""

from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction.contracts import (
    DataFreshness,
    FreshnessStatus,
    PredictionOutput,
    PredictionStatus,
    Reliability,
    ReliabilityStatus,
    Uncertainty,
)
from retainiq_prediction.label_builder import ChurnLabel, ChurnType, LabelStatus
from retainiq_prediction.outcome_reconciliation import (
    ActionApprovalState,
    ActionFeedbackCompatibilityRecord,
    FeedbackProvenanceStatus,
    FeedbackReconciliationRequest,
    FeedbackScopeError,
    FeedbackStatus,
    InMemoryOutcomeReconciliationStore,
    InterventionExposureStatus,
    OutcomeEvidence,
)
from retainiq_prediction.prediction_pipeline import PipelineReasonCode, PipelineResult, PipelineStatus


UTC = timezone.utc
BASE = datetime(2026, 1, 1, tzinfo=UTC)


def prediction(
    *,
    status: PredictionStatus = PredictionStatus.SCORED,
    tenant_id: str = "tenant-a",
    customer_id: str = "account-1",
    prediction_id: str = "prediction-1",
    prediction_run_id: str = "run-1",
    reliability: ReliabilityStatus = ReliabilityStatus.SUFFICIENT_EVIDENCE,
    freshness: FreshnessStatus = FreshnessStatus.FRESH,
    explanations: dict[str, list[dict]] | None = None,
) -> PredictionOutput:
    scored = status is PredictionStatus.SCORED
    return PredictionOutput(
        tenant_id=tenant_id,
        customer_id=customer_id,
        prediction_id=prediction_id,
        prediction_run_id=prediction_run_id,
        as_of=BASE,
        generated_at=BASE + timedelta(minutes=1),
        status=status,
        p_churn_7d=0.10 if scored else None,
        p_churn_14d=0.20 if scored else None,
        p_churn_30d=0.30 if scored else None,
        feature_version="features-v1",
        model_version="model-v1",
        calibration_version="calibration-v1",
        label_policy_version="labels-v1",
        reliability=Reliability(status=reliability, reasons=[]),
        data_freshness=DataFreshness(status=freshness, input_data_as_of=BASE, stale_sources=[]),
        uncertainty=Uncertainty(),
        explanations_by_horizon=explanations or {},
    )


def label_for(prediction_snapshot: PredictionOutput, *, status: LabelStatus, horizon: int = 7, positive: bool = False) -> ChurnLabel:
    horizon_end = BASE + timedelta(days=horizon)
    effective = BASE + timedelta(days=3) if positive else None
    observed_through = effective or horizon_end
    return ChurnLabel(
        tenant_id=prediction_snapshot.tenant_id,
        customer_id=prediction_snapshot.customer_id,
        as_of=BASE,
        evaluation_as_of=observed_through,
        horizon_days=horizon,
        label=1 if positive else (0 if status is LabelStatus.NEGATIVE else None),
        label_status=status,
        churn_type=ChurnType.VOLUNTARY_CANCELLATION if positive else None,
        churn_effective_at=effective,
        label_observed_through=observed_through,
        label_policy_version="labels-v1",
        source_evidence_refs=("source-label-1",),
        label_generated_at=observed_through,
    )


def feedback_request(prediction_snapshot: PredictionOutput, label: ChurnLabel, *, feedback_id: str, evaluation_as_of: datetime, evidence: OutcomeEvidence, supersedes: str | None = None, correction_reason: str | None = None) -> FeedbackReconciliationRequest:
    return FeedbackReconciliationRequest(
        feedback_id=feedback_id,
        prediction_id=prediction_snapshot.prediction_id,
        prediction_run_id=prediction_snapshot.prediction_run_id,
        tenant_id=prediction_snapshot.tenant_id,
        customer_id=prediction_snapshot.customer_id,
        prediction_as_of=prediction_snapshot.as_of,
        horizon_days=label.horizon_days,
        churn_label=label,
        evaluation_as_of=evaluation_as_of,
        evidence=evidence,
        reconciliation_policy_version="reconcile-v1",
        reconciled_at=evaluation_as_of,
        supersedes_feedback_id=supersedes,
        correction_reason=correction_reason,
    )


def evidence(*, through: datetime, complete: bool, source_at: datetime | None = None, unresolved: bool = False, conflicting: bool = False) -> OutcomeEvidence:
    return OutcomeEvidence(
        provenance_status=FeedbackProvenanceStatus.SYNTHETIC_TEST_ONLY,
        source_evidence_refs=("source-event-1",),
        source_available_at=source_at or through,
        observed_from=BASE,
        observed_through=through,
        complete_through=through if complete else None,
        verified=True,
        coverage_complete=complete,
        conflicting_evidence=conflicting,
        unresolved_multi_subscription_policy=unresolved,
        intervention_exposure=InterventionExposureStatus.UNKNOWN,
    )


def test_scored_prediction_round_trips_canonical_fields_and_nested_metadata():
    item = prediction(explanations={"7": [{"feature": "usage_7d", "value": -0.2}]})
    restored = PredictionOutput.model_validate(item.model_dump(mode="json"))
    assert restored == item
    assert restored.model_dump(mode="json")["p_churn_30d"] == 0.3
    assert restored.explanations_by_horizon["7"][0]["feature"] == "usage_7d"


@pytest.mark.parametrize(
    "status",
    [PredictionStatus.ABSTAINED, PredictionStatus.KNOWN_CANCELLATION, PredictionStatus.NOT_ELIGIBLE],
)
def test_non_scored_statuses_preserve_null_probabilities(status):
    item = prediction(status=status)
    payload = item.model_dump(mode="json")
    assert payload["p_churn_7d"] is None
    assert PredictionOutput.model_validate(payload).status is status


def test_limited_evidence_and_unknown_freshness_are_not_lost():
    item = prediction(reliability=ReliabilityStatus.LIMITED_EVIDENCE, freshness=FreshnessStatus.UNKNOWN)
    assert item.reliability.status is ReliabilityStatus.LIMITED_EVIDENCE
    assert item.data_freshness.status is FreshnessStatus.UNKNOWN


def test_explanation_unavailable_is_an_empty_mapping_not_fake_attribution():
    item = prediction(explanations={})
    assert item.explanations_by_horizon == {}


def test_model_bundle_unavailable_is_pipeline_state_without_prediction():
    result = PipelineResult(
        tenant_id="tenant-a",
        customer_id="account-1",
        as_of=BASE,
        prediction_run_id="run-1",
        pipeline_status=PipelineStatus.MODEL_BUNDLE_NOT_READY,
        reason_codes=(PipelineReasonCode.MODEL_BUNDLE_NOT_READY,),
        deployable=False,
    )
    assert result.prediction is None
    assert result.reason_codes == (PipelineReasonCode.MODEL_BUNDLE_NOT_READY,)


def test_missing_subscription_evidence_is_machine_readable_abstention_reason():
    result = PipelineResult(
        tenant_id="tenant-a", customer_id="account-1", as_of=BASE,
        prediction_run_id="run-1",
        pipeline_status=PipelineStatus.ABSTAINED_DUE_TO_INSUFFICIENT_EVIDENCE,
        reason_codes=(PipelineReasonCode.ELIGIBILITY_INSUFFICIENT,),
    )
    assert result.reason_codes[0] is PipelineReasonCode.ELIGIBILITY_INSUFFICIENT


def test_synthetic_scoring_is_explicitly_separate_from_production_claims():
    result = PipelineResult(
        tenant_id="tenant-a", customer_id="account-1", as_of=BASE,
        prediction_run_id="synthetic-run",
        pipeline_status=PipelineStatus.COMPLETED,
        prediction=prediction(prediction_run_id="synthetic-run"),
        synthetic_test_only=True,
        deployable=False,
    )
    assert result.synthetic_test_only is True
    assert result.deployable is False


def test_feedback_pending_mature_positive_and_mature_negative_states():
    item = prediction()
    store = InMemoryOutcomeReconciliationStore([item])
    pending_label = label_for(item, status=LabelStatus.UNKNOWN)
    pending = store.reconcile(feedback_request(item, pending_label, feedback_id="fb-pending", evaluation_as_of=BASE + timedelta(days=2), evidence=evidence(through=BASE + timedelta(days=2), complete=False)))
    assert pending.feedback_status is FeedbackStatus.PENDING

    positive_label = label_for(item, status=LabelStatus.POSITIVE, positive=True)
    positive = store.reconcile(feedback_request(item, positive_label, feedback_id="fb-positive", evaluation_as_of=BASE + timedelta(days=3), evidence=evidence(through=BASE + timedelta(days=3), complete=False)))
    assert positive.feedback_status is FeedbackStatus.MATURE_POSITIVE

    negative_label = label_for(item, status=LabelStatus.NEGATIVE)
    negative = store.reconcile(feedback_request(item, negative_label, feedback_id="fb-negative", evaluation_as_of=BASE + timedelta(days=7), evidence=evidence(through=BASE + timedelta(days=7), complete=True)))
    assert negative.feedback_status is FeedbackStatus.MATURE_NEGATIVE


def test_incomplete_unknown_outcome_is_not_a_negative():
    item = prediction()
    store = InMemoryOutcomeReconciliationStore([item])
    label = label_for(item, status=LabelStatus.UNKNOWN)
    feedback = store.reconcile(feedback_request(item, label, feedback_id="fb-incomplete", evaluation_as_of=BASE + timedelta(days=8), evidence=evidence(through=BASE + timedelta(days=4), complete=False)))
    assert feedback.feedback_status is FeedbackStatus.INCOMPLETE
    assert feedback.label is None


def test_unresolved_multi_subscription_policy_is_incomplete():
    item = prediction()
    store = InMemoryOutcomeReconciliationStore([item])
    label = label_for(item, status=LabelStatus.NEGATIVE)
    feedback = store.reconcile(feedback_request(item, label, feedback_id="fb-multi", evaluation_as_of=BASE + timedelta(days=7), evidence=evidence(through=BASE + timedelta(days=7), complete=True, unresolved=True)))
    assert feedback.feedback_status is FeedbackStatus.INCOMPLETE


def test_source_correction_is_append_only_and_preserves_original_prediction():
    item = prediction()
    store = InMemoryOutcomeReconciliationStore([item])
    label = label_for(item, status=LabelStatus.NEGATIVE)
    first = store.reconcile(feedback_request(item, label, feedback_id="fb-original", evaluation_as_of=BASE + timedelta(days=7), evidence=evidence(through=BASE + timedelta(days=7), complete=True)))
    corrected = store.reconcile(feedback_request(item, label, feedback_id="fb-correction", evaluation_as_of=BASE + timedelta(days=8), evidence=evidence(through=BASE + timedelta(days=7), complete=True, conflicting=True), supersedes=first.feedback_id, correction_reason="Source revision received."))
    assert corrected.supersedes_feedback_id == first.feedback_id
    assert len(store.history_for("tenant-a", item.prediction_id, 7)) == 2
    assert store.prediction_for("tenant-a", item.prediction_id) == item


def test_feedback_is_tenant_scoped_and_prediction_id_is_primary_link():
    item = prediction()
    store = InMemoryOutcomeReconciliationStore([item])
    with pytest.raises(FeedbackScopeError):
        store.prediction_for("tenant-b", item.prediction_id)
    action = ActionFeedbackCompatibilityRecord(
        tenant_id=item.tenant_id,
        customer_id=item.customer_id,
        prediction_id=item.prediction_id,
        action_id="action-1",
        action_type="DATA_INVESTIGATION",
        approval_state=ActionApprovalState.NOT_RECORDED,
        evidence_refs=("evidence-1",),
    )
    assert action.prediction_id == item.prediction_id
    assert action.causal_effect_established is False


def test_prediction_run_id_cannot_replace_prediction_id():
    item = prediction()
    with pytest.raises(ValueError):
        InMemoryOutcomeReconciliationStore([item]).reconcile(FeedbackReconciliationRequest(
            feedback_id="fb-bad-link",
            prediction_id=item.prediction_run_id,
            prediction_run_id=item.prediction_run_id,
            tenant_id=item.tenant_id,
            customer_id=item.customer_id,
            prediction_as_of=BASE,
            horizon_days=7,
            churn_label=label_for(item, status=LabelStatus.UNKNOWN),
            evaluation_as_of=BASE + timedelta(days=1),
            evidence=evidence(through=BASE + timedelta(days=1), complete=False),
            reconciliation_policy_version="reconcile-v1",
            reconciled_at=BASE + timedelta(days=1),
        ))


def test_invalid_or_incompatible_versions_are_rejected():
    item = prediction()
    label = label_for(item, status=LabelStatus.UNKNOWN)
    with pytest.raises(ValueError):
        FeedbackReconciliationRequest(
            feedback_id="fb-version",
            prediction_id=item.prediction_id,
            prediction_run_id=item.prediction_run_id,
            tenant_id=item.tenant_id,
            customer_id=item.customer_id,
            prediction_as_of=BASE,
            horizon_days=14,
            churn_label=label,
            evaluation_as_of=BASE + timedelta(days=1),
            evidence=evidence(through=BASE + timedelta(days=1), complete=False),
            reconciliation_policy_version="reconcile-v1",
            reconciled_at=BASE + timedelta(days=1),
        )


def test_late_outcome_is_not_visible_at_an_earlier_view_cutoff():
    item = prediction()
    store = InMemoryOutcomeReconciliationStore([item])
    label = label_for(item, status=LabelStatus.POSITIVE, positive=True)
    feedback = store.reconcile(feedback_request(item, label, feedback_id="fb-late", evaluation_as_of=BASE + timedelta(days=5), evidence=evidence(through=BASE + timedelta(days=3), complete=False, source_at=BASE + timedelta(days=5))))
    assert feedback.feedback_status is FeedbackStatus.MATURE_POSITIVE
    assert store.latest_feedback_as_of("tenant-a", item.prediction_id, 7, BASE + timedelta(days=4)) is None


def test_timezone_aware_json_roundtrip_and_naive_rejection():
    item = prediction()
    payload = item.model_dump(mode="json")
    assert payload["as_of"].endswith("Z")
    bad = dict(payload)
    bad["as_of"] = "2026-01-01T00:00:00"
    with pytest.raises(Exception):
        PredictionOutput.model_validate(bad)
