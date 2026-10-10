from dataclasses import replace
from datetime import timedelta

import pytest

from retainiq_prediction import (
    CandidateTrainingConfig,
    CandidateTrainingMode,
    CandidateTrainingReasonCode,
    CandidateTrainingStatus,
    DatasetProvenance,
    DatasetReadinessReport,
    DatasetStatus,
    LightGBMConfig,
    ProvenanceEvidenceType,
    train_candidate,
)

from test_lightgbm_model import BOUNDARIES, row, split_for_training
from test_calibration import split_with_four_calibration_rows


FEATURE_VERSION = "features_personalized_baseline_v1"
LABEL_POLICY = "labels_test_v1"


def synthetic_readiness() -> DatasetReadinessReport:
    return DatasetReadinessReport(
        status=DatasetStatus.BLOCKED,
        eligible_for_genuine_training=False,
        supported_horizons=[7, 14, 30],
        dataset_source=DatasetProvenance(
            source_name="synthetic-lightgbm-fixture",
            evidence_type=ProvenanceEvidenceType.SYNTHETIC,
            availability_assumption="synthetic fixture only",
        ),
    )


def config(**overrides) -> CandidateTrainingConfig:
    base = CandidateTrainingConfig(
        candidate_id="candidate-synthetic-1",
        bundle_id="bundle-synthetic-1",
        training_freeze_cutoff=BOUNDARIES.train_end,
        dataset_provenance_reference="synthetic-lightgbm-fixture",
        feature_version=FEATURE_VERSION,
        label_policy_version=LABEL_POLICY,
        training_configuration_version="training-config-test-v1",
        evaluation_policy_version="evaluation-test-v1",
        mode=CandidateTrainingMode.SYNTHETIC_TEST_ONLY,
        lightgbm_config=LightGBMConfig(
            n_estimators=10,
            num_leaves=3,
            max_depth=2,
            min_child_samples=1,
        ),
        created_at=BOUNDARIES.calibration_end + timedelta(days=1),
    )
    return replace(base, **overrides)


def test_missing_real_dataset_blocks_production_candidate_training():
    result = train_candidate(
        split_for_training(),
        dataset_readiness=None,
        config=config(mode=CandidateTrainingMode.REAL_CANDIDATE),
    )

    assert result.status is CandidateTrainingStatus.BLOCKED
    assert CandidateTrainingReasonCode.DATASET_READINESS_REQUIRED in result.reason_codes
    assert result.candidate_metadata is None


def test_synthetic_path_runs_real_model_and_calibration_fits_but_is_not_production_eligible():
    result = train_candidate(
        split_with_four_calibration_rows(),
        dataset_readiness=synthetic_readiness(),
        config=config(),
    )

    assert result.status is CandidateTrainingStatus.SYNTHETIC_ONLY
    assert result.successful is True
    assert result.production_eligible is False
    assert result.test_partition_accessed is False
    assert result.candidate_metadata.synthetic_test_only is True
    assert len(result.horizon_results) == 3
    assert all(item.model_fit.status.value == "ready" for item in result.horizon_results)
    assert all(item.calibration_fit.status.value == "ready" for item in result.horizon_results)
    assert len({id(item.model) for item in result.horizon_results}) == 3
    assert len({id(item.calibrator) for item in result.horizon_results}) == 3
    assert all(
        set(item.training_snapshot_ids).isdisjoint(item.calibration_snapshot_ids)
        for item in result.horizon_results
    )


def test_synthetic_provenance_cannot_be_used_on_real_candidate_path():
    result = train_candidate(
        split_for_training(),
        dataset_readiness=synthetic_readiness(),
        config=config(mode=CandidateTrainingMode.REAL_CANDIDATE),
    )

    assert result.status is CandidateTrainingStatus.BLOCKED
    assert CandidateTrainingReasonCode.SYNTHETIC_PROVENANCE_REQUIRED in result.reason_codes


def test_training_freeze_must_match_train_boundary():
    result = train_candidate(
        split_with_four_calibration_rows(),
        dataset_readiness=synthetic_readiness(),
        config=config(training_freeze_cutoff=BOUNDARIES.train_end - timedelta(days=1)),
    )

    assert result.status is CandidateTrainingStatus.NOT_READY
    assert CandidateTrainingReasonCode.TRAINING_FREEZE_MISMATCH in result.reason_codes


def test_unknown_training_labels_are_not_fitted_as_zero():
    rows = [
        row(day, value)
        for day, value in (
            (1, 0),
            (2, 1),
            (3, 0),
            (4, 1),
            (21, 0),
            (22, 1),
            (31, 0),
            (32, 1),
            (33, 0),
            (34, 1),
            (41, 0),
            (42, 1),
        )
    ]
    unknown = tuple(
        item.model_copy(
            update={
                "label": None,
                "label_status": "unknown",
                "churn_type": None,
                "churn_effective_at": None,
            }
        )
        if item.horizon_days == 7
        else item
        for item in rows[0].labels
    )
    rows[0] = rows[0].model_copy(update={"labels": unknown})
    result = train_candidate(
        split_for_training(rows),
        dataset_readiness=synthetic_readiness(),
        config=config(),
    )

    assert result.status is CandidateTrainingStatus.SYNTHETIC_ONLY
    horizon = result.horizon(7)
    assert horizon.model_fit.training_snapshot_count == 3


def test_single_class_training_returns_not_ready():
    result = train_candidate(
        split_for_training([row(1, 0), row(2, 0), row(3, 0), row(4, 0)]),
        dataset_readiness=synthetic_readiness(),
        config=config(),
    )

    assert result.status is CandidateTrainingStatus.NOT_READY
    assert CandidateTrainingReasonCode.LIGHTGBM_NOT_READY in result.reason_codes


def test_feature_and_label_policy_mismatch_is_rejected_before_fit():
    result = train_candidate(
        split_with_four_calibration_rows(),
        dataset_readiness=synthetic_readiness(),
        config=config(feature_version="different-features"),
    )

    assert result.status is CandidateTrainingStatus.NOT_READY
    assert CandidateTrainingReasonCode.FEATURE_VERSION_MISMATCH in result.reason_codes


def test_validation_and_calibration_are_separate_from_test():
    result = train_candidate(
        split_with_four_calibration_rows(),
        dataset_readiness=synthetic_readiness(),
        config=config(use_validation_early_stopping=True),
    )

    assert result.status is CandidateTrainingStatus.SYNTHETIC_ONLY
    test_ids = {
        record.stable_snapshot_id
        for record in split_with_four_calibration_rows().partition("TEST").snapshots
    }
    assert all(set(item.training_snapshot_ids).isdisjoint(test_ids) for item in result.horizon_results)
    assert all(set(item.calibration_snapshot_ids).isdisjoint(test_ids) for item in result.horizon_results)
    assert all(
        item.model_fit.metadata.training_configuration["validation_early_stopping"] is True
        for item in result.horizon_results
    )


def test_candidate_config_is_immutable_and_does_not_create_production_state():
    candidate_config = config()
    with pytest.raises((AttributeError, TypeError)):
        candidate_config.candidate_id = "changed"  # type: ignore[misc]
    result = train_candidate(
        split_with_four_calibration_rows(),
        dataset_readiness=synthetic_readiness(),
        config=candidate_config,
    )
    assert result.candidate_metadata.status.value == "PROPOSED"
