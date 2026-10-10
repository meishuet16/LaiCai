from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    ActionApprovalState,
    ActionFeedbackCompatibilityRecord,
    ChurnLabel,
    DataFreshness,
    FeedbackProvenanceStatus,
    FeedbackReconciliationRequest,
    FeedbackStatus,
    InMemoryOutcomeReconciliationStore,
    InterventionExposureStatus,
    LearningEligibilityStatus,
    OutcomeEvidence,
    OutcomeReasonCode,
    PredictionOutput,
    PredictionStatus,
    Reliability,
    Uncertainty,
    assess_learning_eligibility,
    feedback_labels_for_historical_evaluation,
)
from retainiq_prediction.label_builder import LabelReasonCode, LabelStatus


UTC = timezone.utc
BASE = datetime(2026, 1, 1, tzinfo=UTC)


def at(day: int) -> datetime:
    return BASE + timedelta(days=day)


def make_prediction(
    *,
    prediction_id: str = "prediction-1",
    prediction_run_id: str = "run-shared",
    tenant_id: str = "tenant-1",
    customer_id: str = "customer-1",
    as_of: datetime = BASE,
    status: PredictionStatus = PredictionStatus.SCORED,
) -> PredictionOutput:
    scored = status is PredictionStatus.SCORED
    return PredictionOutput(
        tenant_id=tenant_id,
        customer_id=customer_id,
        prediction_id=prediction_id,
        prediction_run_id=prediction_run_id,
        as_of=as_of,
        generated_at=as_of + timedelta(hours=1),
        status=status,
        p_churn_7d=0.10 if scored else None,
        p_churn_14d=0.25 if scored else None,
        p_churn_30d=0.50 if scored else None,
        feature_version="features-v1",
        model_version="model-v1",
        calibration_version="calibration-v1",
        label_policy_version="labels-v1",
        reliability=Reliability(status="sufficient_evidence"),
        data_freshness=DataFreshness(status="fresh", input_data_as_of=as_of),
        uncertainty=Uncertainty(),
        explanations_by_horizon={},
    )


def make_label(
    *,
    as_of: datetime = BASE,
    horizon: int = 30,
    status: LabelStatus = LabelStatus.UNKNOWN,
    evaluation_as_of: datetime | None = None,
    observed_through: datetime | None = None,
    churn_effective_at: datetime | None = None,
    reason_codes: tuple[LabelReasonCode, ...] = (),
    refs: tuple[str, ...] = ("source-1",),
) -> ChurnLabel:
    evaluation = evaluation_as_of or as_of
    observed = observed_through or evaluation
    value = 1 if status is LabelStatus.POSITIVE else 0 if status is LabelStatus.NEGATIVE else None
    return ChurnLabel(
        tenant_id="tenant-1",
        customer_id="customer-1",
        as_of=as_of,
        evaluation_as_of=evaluation,
        horizon_days=horizon,
        label=value,
        label_status=status,
        churn_type=("voluntary_cancellation" if status is LabelStatus.POSITIVE else None),
        churn_effective_at=churn_effective_at,
        label_observed_through=observed,
        label_policy_version="labels-v1",
        source_evidence_refs=refs,
        label_generated_at=evaluation,
        reason_codes=reason_codes,
    )


def make_evidence(
    *,
    as_of: datetime = BASE,
    evaluation_as_of: datetime,
    observed_through: datetime,
    complete: bool,
    provenance: FeedbackProvenanceStatus = FeedbackProvenanceStatus.SYNTHETIC_TEST_ONLY,
    verified: bool = True,
    refs: tuple[str, ...] = ("source-1",),
    unresolved_multi_subscription_policy: bool = False,
    conflicting_evidence: bool = False,
) -> OutcomeEvidence:
    return OutcomeEvidence(
        provenance_status=provenance,
        source_evidence_refs=refs,
        source_available_at=evaluation_as_of,
        observed_from=as_of,
        observed_through=observed_through,
        complete_through=observed_through if complete else None,
        verified=verified,
        coverage_complete=complete,
        conflicting_evidence=conflicting_evidence,
        unresolved_multi_subscription_policy=unresolved_multi_subscription_policy,
    )


def request(
    prediction: PredictionOutput,
    label: ChurnLabel,
    evidence: OutcomeEvidence,
    *,
    feedback_id: str = "feedback-1",
    evaluation_as_of: datetime,
    reconciled_at: datetime | None = None,
    supersedes_feedback_id: str | None = None,
    correction_reason: str | None = None,
) -> FeedbackReconciliationRequest:
    return FeedbackReconciliationRequest(
        feedback_id=feedback_id,
        prediction_id=prediction.prediction_id,
        prediction_run_id=prediction.prediction_run_id,
        tenant_id=prediction.tenant_id,
        customer_id=prediction.customer_id,
        prediction_as_of=prediction.as_of,
        horizon_days=label.horizon_days,
        churn_label=label,
        evaluation_as_of=evaluation_as_of,
        evidence=evidence,
        reconciliation_policy_version="feedback-v1",
        reconciled_at=reconciled_at or evaluation_as_of,
        supersedes_feedback_id=supersedes_feedback_id,
        correction_reason=correction_reason,
    )


def test_prediction_id_linkage_and_run_id_is_not_identity():
    first = make_prediction(prediction_id="prediction-1")
    second = make_prediction(prediction_id="prediction-2", customer_id="customer-2")
    store = InMemoryOutcomeReconciliationStore([first, second])
    first_label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    first_evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(30), complete=True)
    second_label = make_label(status=LabelStatus.POSITIVE, evaluation_as_of=at(5), observed_through=at(5), churn_effective_at=at(3))
    second_label = second_label.model_copy(update={"tenant_id": "tenant-1", "customer_id": "customer-2"})
    second_evidence = make_evidence(evaluation_as_of=at(5), observed_through=at(5), complete=False)

    first_feedback = store.reconcile(request(first, first_label, first_evidence, evaluation_as_of=at(30)))
    second_feedback = store.reconcile(
        request(second, second_label, second_evidence, feedback_id="feedback-2", evaluation_as_of=at(5))
    )

    assert first_feedback.prediction_id == "prediction-1"
    assert second_feedback.prediction_id == "prediction-2"
    assert first_feedback.prediction_run_id == second_feedback.prediction_run_id == "run-shared"
    assert first_feedback.customer_id != second_feedback.customer_id


def test_unknown_prediction_and_cross_tenant_or_customer_feedback_are_rejected():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(30), complete=True)

    unknown = request(prediction, label, evidence, evaluation_as_of=at(30)).model_copy(
        update={"prediction_id": "unknown-prediction"}
    )
    with pytest.raises(ValueError, match="not registered"):
        store.reconcile(unknown)

    wrong_tenant = request(prediction, label, evidence, evaluation_as_of=at(30)).model_copy(
        update={"tenant_id": "tenant-other"}
    )
    with pytest.raises(ValueError, match="different tenant"):
        store.reconcile(wrong_tenant)

    wrong_customer = request(prediction, label, evidence, evaluation_as_of=at(30)).model_copy(
        update={"customer_id": "customer-other"}
    )
    with pytest.raises(ValueError, match="customer_id"):
        store.reconcile(wrong_customer)


def test_pending_before_full_horizon_and_positive_can_mature_early():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    pending_label = make_label(status=LabelStatus.UNKNOWN, evaluation_as_of=at(5), observed_through=at(5))
    pending_evidence = make_evidence(evaluation_as_of=at(5), observed_through=at(5), complete=False)
    pending = store.reconcile(request(prediction, pending_label, pending_evidence, evaluation_as_of=at(5)))
    assert pending.feedback_status is FeedbackStatus.PENDING
    assert pending.label is None

    positive_label = make_label(
        status=LabelStatus.POSITIVE,
        evaluation_as_of=at(10),
        observed_through=at(10),
        churn_effective_at=at(10),
    )
    positive_evidence = make_evidence(evaluation_as_of=at(10), observed_through=at(10), complete=False)
    positive = store.reconcile(
        request(
            prediction,
            positive_label,
            positive_evidence,
            feedback_id="feedback-positive",
            evaluation_as_of=at(10),
        )
    )
    assert positive.feedback_status is FeedbackStatus.MATURE_POSITIVE
    assert positive.label == 1


def test_negative_requires_complete_trusted_observation_and_payment_failure_is_not_churn():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    incomplete_label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(10))
    incomplete_evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(10), complete=False)
    incomplete = store.reconcile(request(prediction, incomplete_label, incomplete_evidence, evaluation_as_of=at(30)))
    assert incomplete.feedback_status is FeedbackStatus.INCOMPLETE

    negative_label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    negative_evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(30), complete=True)
    negative = store.reconcile(
        request(prediction, negative_label, negative_evidence, feedback_id="feedback-negative", evaluation_as_of=at(30))
    )
    assert negative.feedback_status is FeedbackStatus.MATURE_NEGATIVE
    assert negative.label == 0
    assert negative.churn_effective_at is None


def test_known_cancellation_at_cutoff_is_ineligible():
    prediction = make_prediction(status=PredictionStatus.KNOWN_CANCELLATION)
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(
        status=LabelStatus.EXCLUDED,
        evaluation_as_of=at(1),
        observed_through=at(1),
        refs=(),
        reason_codes=(LabelReasonCode.KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF,),
    )
    evidence = make_evidence(evaluation_as_of=at(1), observed_through=at(1), complete=False, refs=())
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(1)))
    assert feedback.feedback_status is FeedbackStatus.INELIGIBLE
    assert OutcomeReasonCode.KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF in feedback.reason_codes


def test_not_eligible_prediction_and_already_terminated_label_are_ineligible():
    prediction = make_prediction(status=PredictionStatus.NOT_ELIGIBLE)
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(
        status=LabelStatus.EXCLUDED,
        evaluation_as_of=at(1),
        observed_through=at(1),
        refs=(),
        reason_codes=(LabelReasonCode.ALREADY_TERMINATED_AT_PREDICTION_CUTOFF,),
    )
    evidence = make_evidence(evaluation_as_of=at(1), observed_through=at(1), complete=False, refs=())
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(1)))
    assert feedback.feedback_status is FeedbackStatus.INELIGIBLE
    assert OutcomeReasonCode.NOT_ELIGIBLE_AT_PREDICTION_CUTOFF in feedback.reason_codes


def test_label_identity_cannot_cross_tenant_or_customer():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    foreign_label = label.model_copy(update={"customer_id": "customer-other"})
    evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(30), complete=True)
    with pytest.raises(ValueError, match="customer_id"):
        store.reconcile(request(prediction, foreign_label, evidence, evaluation_as_of=at(30)))


def test_later_cancellation_does_not_retroactively_exclude_eligible_prediction():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(
        status=LabelStatus.POSITIVE,
        evaluation_as_of=at(5),
        observed_through=at(5),
        churn_effective_at=at(5),
    )
    evidence = make_evidence(evaluation_as_of=at(5), observed_through=at(5), complete=False)
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(5)))
    assert feedback.feedback_status is FeedbackStatus.MATURE_POSITIVE
    assert feedback.prediction_snapshot.status is PredictionStatus.SCORED


def test_each_horizon_is_reconciled_independently_and_boundary_is_inclusive():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    labels = [
        make_label(horizon=7, status=LabelStatus.POSITIVE, evaluation_as_of=at(7), observed_through=at(7), churn_effective_at=at(7)),
        make_label(horizon=14, status=LabelStatus.NEGATIVE, evaluation_as_of=at(14), observed_through=at(14)),
        make_label(horizon=30, status=LabelStatus.UNKNOWN, evaluation_as_of=at(20), observed_through=at(20)),
    ]
    feedback = []
    for index, label in enumerate(labels):
        evidence = make_evidence(
            evaluation_as_of=label.evaluation_as_of,
            observed_through=label.label_observed_through,
            complete=label.label_status is LabelStatus.NEGATIVE,
        )
        feedback.append(
            store.reconcile(
                request(prediction, label, evidence, feedback_id=f"feedback-h{index}", evaluation_as_of=label.evaluation_as_of)
            )
        )
    assert [item.feedback_status for item in feedback] == [
        FeedbackStatus.MATURE_POSITIVE,
        FeedbackStatus.MATURE_NEGATIVE,
        FeedbackStatus.PENDING,
    ]


def test_late_evidence_cannot_change_earlier_view_and_correction_is_audited():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    pending_label = make_label(status=LabelStatus.UNKNOWN, evaluation_as_of=at(4), observed_through=at(4))
    pending_evidence = make_evidence(evaluation_as_of=at(4), observed_through=at(4), complete=False)
    pending = store.reconcile(
        request(prediction, pending_label, pending_evidence, evaluation_as_of=at(4), reconciled_at=at(4))
    )
    positive_label = make_label(status=LabelStatus.POSITIVE, evaluation_as_of=at(10), observed_through=at(10), churn_effective_at=at(5))
    late_evidence = make_evidence(evaluation_as_of=at(10), observed_through=at(10), complete=False)
    correction = store.reconcile(
        request(
            prediction,
            positive_label,
            late_evidence,
            feedback_id="feedback-correction",
            evaluation_as_of=at(10),
            reconciled_at=at(10),
            supersedes_feedback_id=pending.feedback_id,
            correction_reason="late lifecycle source correction",
        )
    )
    assert correction.revision_number == 2
    assert OutcomeReasonCode.SOURCE_CORRECTION in correction.reason_codes
    assert store.latest_feedback_as_of("tenant-1", prediction.prediction_id, 30, at(5)).feedback_status is FeedbackStatus.PENDING
    assert store.latest_feedback_as_of("tenant-1", prediction.prediction_id, 30, at(11)).feedback_status is FeedbackStatus.MATURE_POSITIVE
    assert len(store.history_for("tenant-1", prediction.prediction_id, 30)) == 2


def test_repeated_same_reconciliation_is_idempotent_and_conflicting_duplicate_rejected():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(30), complete=True)
    first_request = request(prediction, label, evidence, evaluation_as_of=at(30))
    first = store.reconcile(first_request)
    repeated = store.reconcile(first_request)
    assert repeated == first
    assert len(store.history_for("tenant-1", prediction.prediction_id, 30)) == 1
    changed = first_request.model_copy(update={"evaluation_as_of": at(31)})
    with pytest.raises(ValueError, match="different reconciliation inputs"):
        store.reconcile(changed)


def test_conflicting_source_evidence_is_incomplete_even_before_horizon_maturity():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.POSITIVE, evaluation_as_of=at(5), observed_through=at(5), churn_effective_at=at(5))
    evidence = make_evidence(
        evaluation_as_of=at(5), observed_through=at(5), complete=False, conflicting_evidence=True
    )
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(5)))
    assert feedback.feedback_status is FeedbackStatus.INCOMPLETE
    assert OutcomeReasonCode.CONFLICTING_OUTCOME_EVIDENCE in feedback.reason_codes


def test_unverified_provenance_does_not_create_a_mature_outcome():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    evidence = make_evidence(
        evaluation_as_of=at(30), observed_through=at(30), complete=True,
        provenance=FeedbackProvenanceStatus.UNVERIFIED,
        verified=False,
    )
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(30)))
    assert feedback.feedback_status is FeedbackStatus.INCOMPLETE
    assert OutcomeReasonCode.UNVERIFIED_PROVENANCE in feedback.reason_codes


def test_learning_policy_mismatch_is_rejected():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    evidence = make_evidence(
        evaluation_as_of=at(30), observed_through=at(30), complete=True,
        provenance=FeedbackProvenanceStatus.AUTHORIZED_REAL,
    )
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(30)))
    result = assess_learning_eligibility(
        feedback, training_cutoff=at(40), expected_label_policy_version="labels-other"
    )
    assert result.status is LearningEligibilityStatus.INELIGIBLE
    assert OutcomeReasonCode.LEARNING_POLICY_MISMATCH in result.reason_codes


def test_unresolved_multi_subscription_policy_is_incomplete():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.POSITIVE, evaluation_as_of=at(5), observed_through=at(5), churn_effective_at=at(5))
    evidence = make_evidence(
        evaluation_as_of=at(5),
        observed_through=at(5),
        complete=False,
        unresolved_multi_subscription_policy=True,
    )
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(5)))
    assert feedback.feedback_status is FeedbackStatus.INCOMPLETE
    assert OutcomeReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY in feedback.reason_codes


def test_learning_admissibility_rejects_pending_incomplete_ineligible_and_synthetic():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    cases = [
        (LabelStatus.UNKNOWN, at(5), at(5), False, "pending"),
        (LabelStatus.NEGATIVE, at(30), at(10), False, "incomplete"),
    ]
    for index, (status, evaluation, observed, complete, _) in enumerate(cases):
        label = make_label(status=status, evaluation_as_of=evaluation, observed_through=observed)
        evidence = make_evidence(evaluation_as_of=evaluation, observed_through=observed, complete=complete)
        feedback = store.reconcile(
            request(prediction, label, evidence, feedback_id=f"learning-{index}", evaluation_as_of=evaluation)
        )
        result = assess_learning_eligibility(feedback, training_cutoff=at(40))
        assert result.status is LearningEligibilityStatus.INELIGIBLE

    excluded_label = make_label(status=LabelStatus.EXCLUDED, evaluation_as_of=at(1), observed_through=at(1), refs=())
    excluded_evidence = make_evidence(evaluation_as_of=at(1), observed_through=at(1), complete=False, refs=())
    excluded = store.reconcile(
        request(prediction, excluded_label, excluded_evidence, feedback_id="learning-excluded", evaluation_as_of=at(1))
    )
    assert assess_learning_eligibility(excluded, training_cutoff=at(40)).status is LearningEligibilityStatus.INELIGIBLE

    mature_label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    mature_evidence = make_evidence(
        evaluation_as_of=at(30), observed_through=at(30), complete=True,
        provenance=FeedbackProvenanceStatus.SYNTHETIC_TEST_ONLY,
    )
    mature = store.reconcile(
        request(prediction, mature_label, mature_evidence, feedback_id="learning-synthetic", evaluation_as_of=at(30))
    )
    result = assess_learning_eligibility(mature, training_cutoff=at(40))
    assert result.status is LearningEligibilityStatus.INELIGIBLE
    assert OutcomeReasonCode.SYNTHETIC_FEEDBACK_NOT_AUTHORIZED_FOR_LEARNING in result.reason_codes


def test_authorized_real_mature_feedback_can_be_admitted_at_later_cutoff():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    evidence = make_evidence(
        evaluation_as_of=at(30), observed_through=at(30), complete=True,
        provenance=FeedbackProvenanceStatus.AUTHORIZED_REAL,
    )
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(30)))
    result = assess_learning_eligibility(
        feedback,
        training_cutoff=at(40),
        expected_label_policy_version="labels-v1",
    )
    assert result.status is LearningEligibilityStatus.ELIGIBLE

    late = assess_learning_eligibility(feedback, training_cutoff=at(20))
    assert late.status is LearningEligibilityStatus.INELIGIBLE
    assert OutcomeReasonCode.LEARNING_OUTCOME_RECORDED_AFTER_CUTOFF in late.reason_codes


def test_original_prediction_is_unchanged_and_action_handoff_makes_no_causal_claim():
    prediction = make_prediction()
    before = prediction.model_dump(mode="json")
    store = InMemoryOutcomeReconciliationStore([prediction])
    label = make_label(status=LabelStatus.POSITIVE, evaluation_as_of=at(5), observed_through=at(5), churn_effective_at=at(5))
    evidence = make_evidence(evaluation_as_of=at(5), observed_through=at(5), complete=False)
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=at(5)))
    assert prediction.model_dump(mode="json") == before
    assert feedback.prediction_snapshot.model_dump(mode="json") == before
    assert feedback.original_prediction().model_dump(mode="json") == before

    action = ActionFeedbackCompatibilityRecord(
        tenant_id="tenant-1",
        customer_id="customer-1",
        prediction_id=prediction.prediction_id,
        action_id="action-1",
        action_type="ACCOUNT_CHECK_IN",
        approval_state=ActionApprovalState.APPROVED,
        actual_execution_at=at(2),
        outcome_observation_at=at(5),
        intervention_exposure=InterventionExposureStatus.KNOWN,
    )
    assert action.causal_effect_established is False
    with pytest.raises(ValidationError):
        ActionFeedbackCompatibilityRecord(
            tenant_id="tenant-1",
            customer_id="customer-1",
            prediction_id=prediction.prediction_id,
            action_type="ACCOUNT_CHECK_IN",
            approval_state=ActionApprovalState.APPROVED,
            causal_effect_established=True,
        )


def test_feedback_labels_form_historical_evaluation_boundary():
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    pending_label = make_label(status=LabelStatus.UNKNOWN, evaluation_as_of=at(5), observed_through=at(5))
    pending_evidence = make_evidence(evaluation_as_of=at(5), observed_through=at(5), complete=False)
    pending = store.reconcile(request(prediction, pending_label, pending_evidence, evaluation_as_of=at(5)))
    mature_label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(30))
    mature_evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(30), complete=True)
    mature = store.reconcile(
        request(prediction, mature_label, mature_evidence, feedback_id="mature", evaluation_as_of=at(30), reconciled_at=at(30))
    )
    labels_at_10 = feedback_labels_for_historical_evaluation([pending, mature], evaluation_as_of=at(10))
    labels_at_40 = feedback_labels_for_historical_evaluation([pending, mature], evaluation_as_of=at(40))
    assert labels_at_10 == ()
    assert labels_at_40 == (mature_label,)


def test_invalid_or_timezone_naive_timestamps_are_rejected():
    prediction = make_prediction()
    label = make_label(status=LabelStatus.UNKNOWN, evaluation_as_of=at(1), observed_through=at(1))
    with pytest.raises(ValidationError):
        OutcomeEvidence(
            provenance_status=FeedbackProvenanceStatus.SYNTHETIC_TEST_ONLY,
            observed_from=at(0),
            observed_through=datetime(2026, 1, 2),
        )
    with pytest.raises(ValidationError):
        FeedbackReconciliationRequest(
            feedback_id="feedback-naive",
            prediction_id=prediction.prediction_id,
            prediction_run_id=prediction.prediction_run_id,
            tenant_id=prediction.tenant_id,
            customer_id=prediction.customer_id,
            prediction_as_of=prediction.as_of,
            horizon_days=7,
            churn_label=label.model_copy(update={"horizon_days": 7}),
            evaluation_as_of=datetime(2026, 1, 2),
            evidence=make_evidence(evaluation_as_of=at(1), observed_through=at(1), complete=False),
            reconciliation_policy_version="feedback-v1",
            reconciled_at=at(1),
        )
