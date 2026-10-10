from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction import (
    CandidateEvaluationConfig,
    CandidateEvaluationGate,
    CandidateEvaluationGateStatus,
    CandidateEvaluationReasonCode,
    CandidateHorizonEvaluationStatus,
    DatasetProvenanceStatus,
    EvaluationPrediction,
    ModelBundleMetadata,
    ModelLifecycleStatus,
    ModelRegistry,
    PredictionStatus,
    RegistryProvenanceStatus,
    record_candidate_evaluation,
)
from retainiq_prediction.model_registry import HorizonVersion

from test_calibration import split_with_four_calibration_rows
from test_lightgbm_model import BOUNDARIES, at


UTC = timezone.utc
FEATURE_VERSION = "features_personalized_baseline_v1"
LABEL_POLICY = "labels_test_v1"


def metadata(
    *,
    bundle_id: str,
    candidate_id: str,
    model_prefix: str,
    status: ModelLifecycleStatus = ModelLifecycleStatus.TRAINED_PENDING_EVALUATION,
    provenance: RegistryProvenanceStatus = RegistryProvenanceStatus.SYNTHETIC_TEST_ONLY,
    synthetic: bool = True,
) -> ModelBundleMetadata:
    return ModelBundleMetadata(
        bundle_id=bundle_id,
        candidate_id=candidate_id,
        model_family="lightgbm",
        model_versions=tuple(
            HorizonVersion(horizon_days=horizon, version=f"{model_prefix}-{horizon}")
            for horizon in (7, 14, 30)
        ),
        calibration_versions=tuple(
            HorizonVersion(horizon_days=horizon, version=f"{model_prefix}-cal-{horizon}")
            for horizon in (7, 14, 30)
        ),
        feature_version=FEATURE_VERSION,
        label_policy_version=LABEL_POLICY,
        training_configuration_version="training-config-v1",
        dataset_provenance_reference="synthetic-lightgbm-fixture",
        temporal_split_policy_version="temporal_splits_v1",
        training_freeze_cutoff=BOUNDARIES.train_end,
        evaluation_policy_version="evaluation-policy-v1",
        created_at=BOUNDARIES.calibration_end + timedelta(days=1),
        status=status,
        provenance_status=provenance,
        synthetic_test_only=synthetic,
    )


def predictions(metadata: ModelBundleMetadata, *, positive_probability: float = 0.8):
    split = split_with_four_calibration_rows()
    test_records = split.partition("TEST").snapshots
    model_versions = {item.horizon_days: item.version for item in metadata.model_versions}
    calibration_versions = {item.horizon_days: item.version for item in metadata.calibration_versions}
    result = []
    for record in test_records:
        positive = record.feature_snapshot.customer_id.endswith("42")
        for horizon in (7, 14, 30):
            result.append(
                EvaluationPrediction(
                    model_name="ignored-by-gate",
                    tenant_id=record.feature_snapshot.tenant_id,
                    customer_id=record.feature_snapshot.customer_id,
                    prediction_id=f"prediction-{record.stable_snapshot_id}-{horizon}",
                    prediction_run_id="run-test",
                    as_of=record.feature_snapshot.as_of,
                    horizon_days=horizon,
                    probability=positive_probability if positive else 0.2,
                    status=PredictionStatus.SCORED,
                    model_version=model_versions[horizon],
                    feature_version=metadata.feature_version,
                    calibration_version=calibration_versions[horizon],
                    label_policy_version=metadata.label_policy_version,
                )
            )
    return tuple(result)


def matured_test_labels(split):
    return [
        label.model_copy(
            update={
                "evaluation_as_of": label.as_of + timedelta(days=label.horizon_days),
                "label_observed_through": label.as_of + timedelta(days=label.horizon_days),
                "label_generated_at": label.as_of + timedelta(days=label.horizon_days),
            }
        )
        for record in split.partition("TEST").snapshots
        for label in record.labels
    ]


def config(**overrides) -> CandidateEvaluationConfig:
    base = CandidateEvaluationConfig(
        evaluation_policy_version="evaluation-policy-v1",
        evaluation_cutoff=at(90),
        split_policy_version="temporal_splits_v1",
        test_authorization_reference="synthetic-test-authorization",
        review_capacity_k=1,
        dataset_provenance_status=DatasetProvenanceStatus.SYNTHETIC,
        expected_feature_version=FEATURE_VERSION,
        expected_label_policy_version=LABEL_POLICY,
        minimum_mature_samples_per_horizon=2,
    )
    values = {field: getattr(base, field) for field in base.__dataclass_fields__}
    values.update(overrides)
    return CandidateEvaluationConfig(**values)


def test_final_test_requires_a_frozen_candidate():
    candidate = metadata(bundle_id="candidate-bundle", candidate_id="candidate-1", model_prefix="candidate")
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    report = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        list(split_with_four_calibration_rows().partition("TEST").snapshots[0].labels),
        split_with_four_calibration_rows(),
        config=config(),
        evaluation_run_id="evaluation-1",
    )

    assert report.gate_status is CandidateEvaluationGateStatus.BLOCKED
    assert CandidateEvaluationReasonCode.CANDIDATE_NOT_FROZEN in report.reason_codes
    assert report.test_accessed is False


def test_synthetic_test_evaluation_runs_but_is_not_approvable_and_records_all_horizons():
    candidate = metadata(bundle_id="candidate-bundle", candidate_id="candidate-1", model_prefix="candidate")
    champion = metadata(bundle_id="champion-bundle", candidate_id="champion-1", model_prefix="champion")
    split = split_with_four_calibration_rows()
    labels = matured_test_labels(split)
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    manifest = gate.freeze_candidate(candidate, config=config())
    report = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        labels,
        split,
        config=config(),
        evaluation_run_id="evaluation-1",
        champion=champion,
        champion_predictions=predictions(champion),
    )

    assert manifest.test_usage_status == "SEALED"
    assert report.gate_status is CandidateEvaluationGateStatus.EVALUATED_NOT_APPROVABLE
    assert report.evaluation_status.value == "synthetic_only"
    assert CandidateEvaluationReasonCode.SYNTHETIC_ONLY in report.reason_codes
    assert all(
        report.horizon_status[horizon] is CandidateHorizonEvaluationStatus.READY
        for horizon in (7, 14, 30)
    )
    assert set(report.coverage_by_horizon) == {7, 14, 30}
    assert report.historical_report.configuration["model_selection_used_test"] is False


def test_missing_champion_prevents_comparative_claim_but_does_not_hide_candidate_metrics():
    candidate = metadata(bundle_id="candidate-bundle", candidate_id="candidate-1", model_prefix="candidate")
    split = split_with_four_calibration_rows()
    labels = matured_test_labels(split)
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    gate.freeze_candidate(candidate, config=config())
    report = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        labels,
        split,
        config=config(),
        evaluation_run_id="evaluation-no-champion",
    )

    assert report.gate_status is CandidateEvaluationGateStatus.EVALUATED_NOT_APPROVABLE
    assert CandidateEvaluationReasonCode.CHAMPION_MISSING in report.reason_codes
    assert report.historical_report is not None
    assert len(report.historical_report.horizon_metrics) == 3


def test_candidate_parameter_change_after_freeze_is_blocked():
    candidate = metadata(bundle_id="candidate-bundle", candidate_id="candidate-1", model_prefix="candidate")
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    gate.freeze_candidate(candidate, config=config())
    changed = candidate.model_copy(update={"feature_version": "feature-v2"})
    report = gate.evaluate_final_test(
        changed,
        predictions(candidate),
        (),
        split_with_four_calibration_rows(),
        config=config(),
        evaluation_run_id="evaluation-changed",
    )

    assert report.gate_status is CandidateEvaluationGateStatus.BLOCKED
    assert CandidateEvaluationReasonCode.CANDIDATE_CHANGED_AFTER_FREEZE in report.reason_codes


def test_test_selection_reuse_and_second_test_access_are_blocked():
    candidate = metadata(bundle_id="candidate-bundle", candidate_id="candidate-1", model_prefix="candidate")
    champion = metadata(bundle_id="champion-bundle", candidate_id="champion-1", model_prefix="champion")
    split = split_with_four_calibration_rows()
    labels = matured_test_labels(split)
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    gate.freeze_candidate(candidate, config=config())

    selection = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        labels,
        split,
        config=config(),
        evaluation_run_id="selection",
        champion=champion,
        champion_predictions=predictions(champion),
        purpose="model_selection",
    )
    assert CandidateEvaluationReasonCode.TEST_REUSE_FOR_SELECTION in selection.reason_codes

    final = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        labels,
        split,
        config=config(),
        evaluation_run_id="final",
        champion=champion,
        champion_predictions=predictions(champion),
    )
    assert final.test_accessed is True

    repeated = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        labels,
        split,
        config=config(),
        evaluation_run_id="repeated",
        champion=champion,
        champion_predictions=predictions(champion),
    )
    assert repeated.gate_status is CandidateEvaluationGateStatus.BLOCKED
    assert CandidateEvaluationReasonCode.TEST_ALREADY_CONSUMED in repeated.reason_codes


def test_version_mismatch_is_rejected_before_test_access():
    candidate = metadata(bundle_id="candidate-bundle", candidate_id="candidate-1", model_prefix="candidate")
    split = split_with_four_calibration_rows()
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    gate.freeze_candidate(candidate, config=config())
    mismatched = list(predictions(candidate))
    mismatched[0] = mismatched[0].model_copy(update={"calibration_version": "wrong-calibration"})
    report = gate.evaluate_final_test(
        candidate,
        mismatched,
        (),
        split,
        config=config(),
        evaluation_run_id="version-mismatch",
    )

    assert report.gate_status is CandidateEvaluationGateStatus.BLOCKED
    assert CandidateEvaluationReasonCode.CALIBRATION_VERSION_MISMATCH in report.reason_codes
    assert report.test_accessed is False


def test_current_repository_real_test_readiness_remains_blocked():
    candidate = metadata(
        bundle_id="real-candidate-bundle",
        candidate_id="real-candidate",
        model_prefix="real-candidate",
        provenance=RegistryProvenanceStatus.AUTHORIZED_REAL,
        synthetic=False,
    )
    champion = metadata(
        bundle_id="real-champion-bundle",
        candidate_id="real-champion",
        model_prefix="real-champion",
        provenance=RegistryProvenanceStatus.AUTHORIZED_REAL,
        synthetic=False,
    )
    split = split_with_four_calibration_rows()
    labels = matured_test_labels(split)
    real_config = config(dataset_provenance_status=DatasetProvenanceStatus.REAL_AUTHORIZED)
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    gate.freeze_candidate(candidate, config=real_config)
    report = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        labels,
        split,
        config=real_config,
        evaluation_run_id="real-blocked",
        champion=champion,
        champion_predictions=predictions(champion),
    )

    assert report.gate_status is CandidateEvaluationGateStatus.BLOCKED
    assert CandidateEvaluationReasonCode.DATASET_PROVENANCE_BLOCKED in report.reason_codes


def test_evaluation_can_record_pending_approval_without_promoting_candidate():
    candidate = metadata(bundle_id="candidate-bundle", candidate_id="candidate-1", model_prefix="candidate")
    champion = metadata(bundle_id="champion-bundle", candidate_id="champion-1", model_prefix="champion")
    registry = ModelRegistry()
    registry.register_candidate(candidate)
    split = split_with_four_calibration_rows()
    labels = matured_test_labels(split)
    gate = CandidateEvaluationGate(clock=lambda: at(45))
    gate.freeze_candidate(candidate, config=config())
    report = gate.evaluate_final_test(
        candidate,
        predictions(candidate),
        labels,
        split,
        config=config(),
        evaluation_run_id="evaluation-record",
        champion=champion,
        champion_predictions=predictions(champion),
    )
    updated = record_candidate_evaluation(
        registry,
        "candidate-1",
        report,
        evidence_note="Synthetic evaluation mechanics recorded; not approvable.",
    )

    assert updated.status is ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL
    assert registry.active_bundle() is None
