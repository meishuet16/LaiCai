from datetime import timedelta, timezone

import pytest

from retainiq_prediction import (
    ChurnLabel,
    DatasetProvenance,
    DatasetReadinessReport,
    DatasetStatus,
    FeatureQuality,
    FeatureSnapshot,
    FeatureValues,
    FeedbackProvenanceStatus,
    FeedbackStatus,
    InMemoryOutcomeReconciliationStore,
    LabelStatus,
    OutcomeEvidence,
    PredictionOutput,
    RetrainingReasonCode,
    RetrainingReadinessConfig,
    RetrainingReadinessStatus,
    SnapshotRecord,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitter,
    UsageCoverageStatus,
    PersonalBaselineStatus,
    assess_retraining_readiness,
)
from retainiq_prediction.dataset_readiness import ProvenanceEvidenceType
from retainiq_prediction.label_builder import ChurnType

from test_outcome_reconciliation import at, make_evidence, make_label, make_prediction, request


def dataset_report(*, provenance: ProvenanceEvidenceType = ProvenanceEvidenceType.REAL_AUTHORIZED) -> DatasetReadinessReport:
    return DatasetReadinessReport(
        status=DatasetStatus.PASS,
        eligible_for_genuine_training=True,
        available_data_categories=["accounts", "subscriptions", "usage", "outcomes"],
        supported_horizons=[7, 14, 30],
        dataset_source=DatasetProvenance(
            source_name="authorized-structural-fixture",
            license_or_authorization="synthetic-test-contract",
            evidence_type=provenance,
        ),
    )


def feature_snapshot(day: int, customer_id: str) -> FeatureSnapshot:
    cutoff = at(day)
    return FeatureSnapshot(
        tenant_id="tenant-1",
        customer_id=customer_id,
        as_of=cutoff,
        feature_version="features-v1",
        data_cutoff_at=cutoff,
        feature_values=FeatureValues(
            personal_baseline_availability_status=PersonalBaselineStatus.UNAVAILABLE,
        ),
        data_quality=FeatureQuality(
            usage_coverage_status=UsageCoverageStatus.UNKNOWN,
            personal_baseline_status=PersonalBaselineStatus.UNAVAILABLE,
            baseline_weeks_requested=4,
        ),
    )


def make_training_fixture(*, include_second_customer: bool = True):
    predictions = [make_prediction(prediction_id="prediction-a", customer_id="customer-1", as_of=at(1))]
    if include_second_customer:
        predictions.append(make_prediction(prediction_id="prediction-b", customer_id="customer-2", as_of=at(2)))
    store = InMemoryOutcomeReconciliationStore(predictions)
    all_labels: dict[str, list[ChurnLabel]] = {prediction.customer_id: [] for prediction in predictions}
    feedback = []
    for prediction in predictions:
        for horizon in (7, 14, 30):
            if prediction.customer_id == "customer-1":
                label = make_label(
                    as_of=prediction.as_of,
                    horizon=horizon,
                    status=LabelStatus.POSITIVE,
                    evaluation_as_of=prediction.as_of + timedelta(days=horizon),
                    observed_through=prediction.as_of + timedelta(days=horizon),
                    churn_effective_at=prediction.as_of + timedelta(days=1),
                ).model_copy(update={"customer_id": prediction.customer_id})
                evidence = make_evidence(
                    as_of=prediction.as_of,
                    evaluation_as_of=prediction.as_of + timedelta(days=horizon),
                    observed_through=prediction.as_of + timedelta(days=horizon),
                    complete=False,
                    provenance=FeedbackProvenanceStatus.AUTHORIZED_REAL,
                )
            else:
                label = make_label(
                    as_of=prediction.as_of,
                    horizon=horizon,
                    status=LabelStatus.NEGATIVE,
                    evaluation_as_of=prediction.as_of + timedelta(days=horizon),
                    observed_through=prediction.as_of + timedelta(days=horizon),
                ).model_copy(update={"customer_id": prediction.customer_id})
                evidence = make_evidence(
                    as_of=prediction.as_of,
                    evaluation_as_of=prediction.as_of + timedelta(days=horizon),
                    observed_through=prediction.as_of + timedelta(days=horizon),
                    complete=True,
                    provenance=FeedbackProvenanceStatus.AUTHORIZED_REAL,
                )
            all_labels[prediction.customer_id].append(label)
            feedback.append(
                store.reconcile(
                    request(
                        prediction,
                        label,
                        evidence,
                        feedback_id=f"feedback-{prediction.customer_id}-{horizon}",
                        evaluation_as_of=prediction.as_of + timedelta(days=horizon),
                    )
                )
            )
    records = [
        SnapshotRecord(
            snapshot_id=f"snapshot-{customer_id}",
            feature_snapshot=feature_snapshot(
                1 if customer_id == "customer-1" else 2,
                customer_id,
            ),
            labels=tuple(labels),
        )
        for customer_id, labels in all_labels.items()
    ]
    split = TemporalSplitter(
        TemporalSplitConfig(
            boundaries=TemporalSplitBoundaries(
                train_start=at(0),
                train_end=at(40),
                validation_end=at(50),
                calibration_end=at(60),
                test_end=at(70),
            ),
            split_policy_version="split-v1",
            dataset_identifier="authorized-structural-fixture",
            authorized_dataset=True,
            minimum_samples_per_horizon=2,
        )
    ).split(records)
    return predictions, feedback, split


def config(**overrides) -> RetrainingReadinessConfig:
    values = {
        "training_freeze_cutoff": at(40),
        "expected_feature_version": "features-v1",
        "expected_label_policy_version": "labels-v1",
        "expected_split_policy_version": "split-v1",
        "account_churn_policy_version": "account-last-subscription-v1",
        "minimum_samples_per_horizon": 2,
        "minimum_positive_per_horizon": 1,
        "minimum_negative_per_horizon": 1,
        "selection_coverage_verified": True,
    }
    values.update(overrides)
    return RetrainingReadinessConfig(**values)


def test_missing_real_dataset_is_blocked():
    _, feedback, split = make_training_fixture()
    report = assess_retraining_readiness(feedback, dataset_readiness=None, split_result=split, config=config())
    assert report.readiness_status is RetrainingReadinessStatus.BLOCKED
    assert RetrainingReasonCode.DATASET_READINESS_MISSING in report.blockers


def test_synthetic_only_provenance_is_blocked():
    _, feedback, split = make_training_fixture()
    report = assess_retraining_readiness(
        feedback,
        dataset_readiness=dataset_report(provenance=ProvenanceEvidenceType.SYNTHETIC),
        split_result=split,
        config=config(),
    )
    assert report.readiness_status is RetrainingReadinessStatus.BLOCKED
    assert RetrainingReasonCode.SYNTHETIC_ONLY in report.blockers


def test_verified_mature_outcomes_are_admitted_per_horizon_with_deterministic_fingerprint():
    _, feedback, split = make_training_fixture()
    first = assess_retraining_readiness(feedback, dataset_readiness=dataset_report(), split_result=split, config=config())
    second = assess_retraining_readiness(feedback, dataset_readiness=dataset_report(), split_result=split, config=config())
    assert first.readiness_status is RetrainingReadinessStatus.READY_FOR_CANDIDATE_TRAINING
    assert all(item.status.value == "READY" for item in first.horizon_readiness)
    assert first.eligible_feedback_ids_by_horizon[7]
    assert first.fingerprint() == second.fingerprint()


@pytest.mark.parametrize("status", [FeedbackStatus.PENDING, FeedbackStatus.INCOMPLETE, FeedbackStatus.INELIGIBLE])
def test_non_mature_feedback_is_rejected(status):
    prediction = make_prediction()
    store = InMemoryOutcomeReconciliationStore([prediction])
    if status is FeedbackStatus.PENDING:
        label = make_label(status=LabelStatus.UNKNOWN, evaluation_as_of=at(3), observed_through=at(3))
        evidence = make_evidence(evaluation_as_of=at(3), observed_through=at(3), complete=False, provenance=FeedbackProvenanceStatus.AUTHORIZED_REAL)
    elif status is FeedbackStatus.INCOMPLETE:
        label = make_label(status=LabelStatus.NEGATIVE, evaluation_as_of=at(30), observed_through=at(10))
        evidence = make_evidence(evaluation_as_of=at(30), observed_through=at(10), complete=False, provenance=FeedbackProvenanceStatus.AUTHORIZED_REAL)
    else:
        prediction = make_prediction(status="not_eligible")
        store = InMemoryOutcomeReconciliationStore([prediction])
        label = make_label(status=LabelStatus.EXCLUDED, evaluation_as_of=at(1), observed_through=at(1), refs=())
        evidence = make_evidence(evaluation_as_of=at(1), observed_through=at(1), complete=False, refs=(), provenance=FeedbackProvenanceStatus.AUTHORIZED_REAL)
    feedback = store.reconcile(request(prediction, label, evidence, evaluation_as_of=label.evaluation_as_of))
    _, _, split = make_training_fixture()
    report = assess_retraining_readiness(feedback=(feedback,), dataset_readiness=dataset_report(), split_result=split, config=config())
    assert report.readiness_status is RetrainingReadinessStatus.NOT_READY


def test_outcome_after_training_cutoff_is_excluded():
    predictions, feedback, split = make_training_fixture()
    late = feedback[0].model_copy(update={"evaluation_as_of": at(50), "reconciliation_timestamp": at(50)})
    report = assess_retraining_readiness(
        (late, *feedback[1:]), dataset_readiness=dataset_report(), split_result=split, config=config()
    )
    assert report.excluded_feedback_counts[RetrainingReasonCode.OUTCOME_AFTER_TRAINING_CUTOFF.value] == 1


def test_separate_horizon_masks_report_missing_horizons_and_single_class():
    predictions, feedback, split = make_training_fixture()
    only_7 = tuple(item for item in feedback if item.horizon_days == 7 and item.customer_id == "customer-1")
    report = assess_retraining_readiness(only_7, dataset_readiness=dataset_report(), split_result=split, config=config())
    by_horizon = {item.horizon_days: item for item in report.horizon_readiness}
    assert by_horizon[7].positive_count == 1
    assert RetrainingReasonCode.SINGLE_CLASS in by_horizon[7].reason_codes
    assert RetrainingReasonCode.INSUFFICIENT_SAMPLES in by_horizon[14].reason_codes
    assert RetrainingReasonCode.INSUFFICIENT_SAMPLES in by_horizon[30].reason_codes


def test_version_and_account_policy_mismatches_are_reported():
    _, feedback, split = make_training_fixture()
    policy_report = assess_retraining_readiness(
        feedback,
        dataset_readiness=dataset_report(),
        split_result=split,
        config=config(expected_label_policy_version="labels-other"),
    )
    assert policy_report.readiness_status is RetrainingReadinessStatus.NOT_READY
    assert any(
        RetrainingReasonCode.LABEL_POLICY_MISMATCH in item.reason_codes
        for item in policy_report.horizon_readiness
    )
    unresolved = assess_retraining_readiness(
        feedback,
        dataset_readiness=dataset_report(),
        split_result=split,
        config=config(account_churn_policy_version=None),
    )
    assert RetrainingReasonCode.ACCOUNT_CHURN_POLICY_UNRESOLVED in unresolved.blockers


def test_repeated_snapshots_are_retained_and_selection_limitations_warn():
    _, feedback, split = make_training_fixture()
    duplicate = feedback[0]
    report = assess_retraining_readiness(
        (*feedback, duplicate),
        dataset_readiness=dataset_report(),
        split_result=split,
        config=config(selection_coverage_verified=False),
    )
    assert RetrainingReasonCode.DUPLICATE_SNAPSHOT.value in report.excluded_feedback_counts
    assert RetrainingReasonCode.SELECTION_COVERAGE_WARNING in report.selection_warnings
    assert RetrainingReasonCode.ABSTAINED_COVERAGE_WARNING in report.selection_warnings


def test_tenant_scope_mismatch_is_rejected():
    _, feedback, split = make_training_fixture()
    report = assess_retraining_readiness(
        feedback,
        dataset_readiness=dataset_report(),
        split_result=split,
        config=config(tenant_scope="tenant-other"),
    )
    assert report.readiness_status is RetrainingReadinessStatus.NOT_READY
    assert RetrainingReasonCode.TENANT_SCOPE_MISMATCH in report.blockers


def test_missing_temporal_split_blocks_readiness():
    _, feedback, _ = make_training_fixture()
    report = assess_retraining_readiness(feedback, dataset_readiness=dataset_report(), split_result=None, config=config())
    assert report.readiness_status is RetrainingReadinessStatus.BLOCKED
    assert RetrainingReasonCode.TEMPORAL_SPLIT_MISSING in report.blockers
