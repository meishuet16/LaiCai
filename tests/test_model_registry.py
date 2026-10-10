from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction.model_registry import (
    HorizonVersion,
    HumanApproval,
    ModelBundleMetadata,
    ModelLifecycleStatus,
    ModelRegistry,
    RegistryProvenanceStatus,
)
from retainiq_prediction.retraining_readiness import (
    RetrainingReadinessReport,
    RetrainingReadinessStatus,
)


UTC = timezone.utc
FREEZE = datetime(2026, 1, 1, tzinfo=UTC)


def ready_report() -> RetrainingReadinessReport:
    return RetrainingReadinessReport(
        readiness_status=RetrainingReadinessStatus.READY_FOR_CANDIDATE_TRAINING,
        readiness_policy_version="retraining_readiness_v1",
        dataset_identifier="authorized-dataset",
        training_freeze_cutoff=FREEZE,
        temporal_split_policy_version="split-v1",
        expected_feature_version="feature-v1",
        expected_label_policy_version="label-v1",
        account_churn_policy_version="account-churn-v1",
        tenant_count=1,
        customer_count=2,
        repeated_account_snapshot_count=0,
        source_correction_count=0,
    )


def metadata(
    *,
    candidate_id: str = "candidate-1",
    status: ModelLifecycleStatus = ModelLifecycleStatus.PROPOSED,
    provenance: RegistryProvenanceStatus = RegistryProvenanceStatus.AUTHORIZED_REAL,
    synthetic: bool = False,
    artifacts: tuple[str, ...] = (),
) -> ModelBundleMetadata:
    versions = tuple(HorizonVersion(horizon_days=h, version=f"model-{h}") for h in (7, 14, 30))
    calibrations = tuple(HorizonVersion(horizon_days=h, version=f"cal-{h}") for h in (7, 14, 30))
    return ModelBundleMetadata(
        bundle_id=f"bundle-{candidate_id}",
        candidate_id=candidate_id,
        model_family="logistic_regression",
        model_versions=versions,
        calibration_versions=calibrations,
        feature_version="feature-v1",
        label_policy_version="label-v1",
        training_configuration_version="training-config-v1",
        dataset_provenance_reference="authorized-dataset",
        temporal_split_policy_version="split-v1",
        training_freeze_cutoff=FREEZE,
        evaluation_policy_version="evaluation-v1",
        artifact_references=artifacts,
        created_at=FREEZE + timedelta(days=1),
        status=status,
        provenance_status=provenance,
        synthetic_test_only=synthetic,
    )


def approval(*, independent: bool = True) -> HumanApproval:
    return HumanApproval(
        actor_id="reviewer-1",
        approved_at=FREEZE + timedelta(days=2),
        reason="Independent historical evaluation reviewed.",
        independent_test_evaluated=independent,
        evaluation_run_id="evaluation-1",
        rollback_plan_reference="rollback-plan-1",
    )


def test_metadata_requires_all_three_horizons_and_approved_artifacts():
    with pytest.raises(ValidationError):
        ModelBundleMetadata(
            **metadata().model_dump(exclude={"model_versions"}),
            model_versions=(HorizonVersion(horizon_days=7, version="only-one"),),
        )

    with pytest.raises(ValidationError):
        metadata(status=ModelLifecycleStatus.APPROVED)


def test_candidate_registration_is_idempotent_but_conflicts_are_rejected():
    registry = ModelRegistry()
    original = metadata()
    assert registry.register_candidate(original) == original
    assert registry.register_candidate(original) == original

    conflicting = metadata()
    conflicting = conflicting.model_copy(update={"feature_version": "feature-v2"})
    with pytest.raises(ValueError, match="DUPLICATE_VERSION_CONFLICT"):
        registry.register_candidate(conflicting)


def test_registry_returns_immutable_copies_and_does_not_load_artifacts():
    registry = ModelRegistry()
    registry.register_candidate(metadata(artifacts=("artifact://candidate-1",)))
    returned = registry.candidate_for("candidate-1")
    with pytest.raises(ValidationError):
        returned.feature_version = "mutated"  # type: ignore[misc]
    assert registry.active_bundle() is None


def test_real_candidate_requires_readiness_then_evidence_for_lifecycle_progression():
    registry = ModelRegistry()
    registry.register_candidate(metadata(artifacts=("artifact://candidate-1",)))

    eligible = registry.transition_candidate(
        "candidate-1",
        ModelLifecycleStatus.ELIGIBLE_FOR_TRAINING,
        readiness_report=ready_report(),
    )
    assert eligible.status is ModelLifecycleStatus.ELIGIBLE_FOR_TRAINING

    with pytest.raises(ValueError, match="evidence_note"):
        registry.transition_candidate("candidate-1", ModelLifecycleStatus.TRAINED_PENDING_EVALUATION)

    trained = registry.transition_candidate(
        "candidate-1",
        ModelLifecycleStatus.TRAINED_PENDING_EVALUATION,
        evidence_note="Candidate artifacts were produced in the isolated training environment.",
    )
    assert trained.status is ModelLifecycleStatus.TRAINED_PENDING_EVALUATION
    evaluated = registry.transition_candidate(
        "candidate-1",
        ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL,
        evidence_note="Independent historical evaluation completed.",
    )
    assert evaluated.status is ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL


def test_candidate_cannot_be_approved_without_independent_human_review():
    registry = ModelRegistry()
    registry.register_candidate(metadata(artifacts=("artifact://candidate-1",)))
    registry.transition_candidate(
        "candidate-1",
        ModelLifecycleStatus.ELIGIBLE_FOR_TRAINING,
        readiness_report=ready_report(),
    )
    registry.transition_candidate(
        "candidate-1",
        ModelLifecycleStatus.TRAINED_PENDING_EVALUATION,
        evidence_note="Training evidence.",
    )
    registry.transition_candidate(
        "candidate-1",
        ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL,
        evidence_note="Evaluation evidence.",
    )

    with pytest.raises(ValueError, match="INDEPENDENT_EVALUATION_REQUIRED"):
        registry.promote_candidate("candidate-1", approval=approval(independent=False))

    promoted = registry.promote_candidate("candidate-1", approval=approval())
    assert promoted.status is ModelLifecycleStatus.APPROVED
    assert registry.active_bundle() is None


def test_synthetic_candidates_are_not_training_or_approval_eligible():
    registry = ModelRegistry()
    registry.register_candidate(
        metadata(
            candidate_id="synthetic",
            provenance=RegistryProvenanceStatus.SYNTHETIC_TEST_ONLY,
            synthetic=True,
        )
    )

    with pytest.raises(ValueError, match="PROVENANCE_NOT_AUTHORIZED"):
        registry.transition_candidate(
            "synthetic",
            ModelLifecycleStatus.ELIGIBLE_FOR_TRAINING,
            readiness_report=ready_report(),
        )

    with pytest.raises(ValidationError):
        metadata(
            candidate_id="synthetic-approved",
            status=ModelLifecycleStatus.APPROVED,
            provenance=RegistryProvenanceStatus.SYNTHETIC_TEST_ONLY,
            synthetic=True,
            artifacts=("artifact://synthetic",),
        )


def test_active_bundle_requires_approval_and_is_immutable():
    bundle = metadata(
        candidate_id="active",
        status=ModelLifecycleStatus.APPROVED,
        artifacts=("artifact://active",),
    )
    registry = ModelRegistry()
    with pytest.raises(ValueError, match="APPROVAL_REQUIRED"):
        registry.register_active_bundle(bundle)

    registered = registry.register_active_bundle(bundle, approval=approval())
    assert registered.status is ModelLifecycleStatus.APPROVED
    assert registry.active_bundle() == bundle

    with pytest.raises(ValueError, match="ACTIVE_BUNDLE_IMMUTABLE"):
        registry.register_active_bundle(bundle, approval=approval())


def test_invalid_lifecycle_transition_is_rejected():
    registry = ModelRegistry()
    registry.register_candidate(metadata())
    with pytest.raises(ValueError, match="INVALID_TRANSITION"):
        registry.transition_candidate("candidate-1", ModelLifecycleStatus.APPROVED, approval=approval())
