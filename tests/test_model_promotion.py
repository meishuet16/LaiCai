from datetime import datetime, timezone

import pytest

from retainiq_prediction.model_approval import (
    ApprovalDecision,
    AuthorizationEvidence,
    AuthorizationStatus,
    ModelApprovalLedger,
)
from retainiq_prediction.model_promotion import (
    InMemoryActiveBundleStore,
    ModelPromotionService,
    PromotionReasonCode,
    PromotionRequest,
    PromotionStatus,
    active_reference_from_metadata,
)
from retainiq_prediction.model_registry import ModelLifecycleStatus
from test_model_approval import TrustedVerifier, candidate, report_for, request


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def trusted():
    return AuthorizationEvidence(
        verification_id="activation-auth-1",
        actor_reference="operator-1",
        actor_role="release_operator",
        authorization_scope="model.activate",
        verified_at=NOW,
        verifier_reference="external-rbac",
        status=AuthorizationStatus.VERIFIED,
        production_trusted=True,
    )


def approved_setup():
    item = candidate(status=ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL)
    ledger = ModelApprovalLedger()
    approval = ledger.submit(request(), candidate=item, evaluation_report=report_for(item), verifier=TrustedVerifier()).record
    return item.model_copy(update={"status": ModelLifecycleStatus.APPROVED}), report_for(item), approval


def promotion_request(**updates):
    values = dict(
        request_id="promotion-1",
        candidate_bundle_id="bundle-candidate",
        candidate_version="candidate-v1",
        approval_id="approval:placeholder",
        evaluation_manifest_id="manifest-1",
        requested_at=NOW,
        policy_version="promotion-v1",
        deployment_compatibility_reference="compat-1",
    )
    values.update(updates)
    return PromotionRequest(**values)


def check_ready():
    item, report, approval = approved_setup()
    req = promotion_request(approval_id=approval.approval_id, expected_active_bundle_id=None, expected_active_generation=None)
    store = InMemoryActiveBundleStore()
    check = ModelPromotionService().check(
        req,
        metadata=item,
        evaluation_report=report,
        approval=approval,
        store=store,
        deployment_compatibility_verified=True,
        rollback_target_available=True,
        activation_authorization=trusted(),
    )
    return item, report, approval, req, store, check


def test_missing_approval_is_denied():
    item = candidate(status=ModelLifecycleStatus.APPROVED)
    req = promotion_request()
    check = ModelPromotionService().check(req, metadata=item, evaluation_report=report_for(item), approval=None, store=InMemoryActiveBundleStore(), deployment_compatibility_verified=True, rollback_target_available=True, activation_authorization=trusted())
    assert check.status is PromotionStatus.DENIED
    assert PromotionReasonCode.APPROVAL_REQUIRED in check.reason_codes


def test_missing_horizon_calibrator_or_artifact_is_denied():
    item, report, approval = approved_setup()
    item = item.model_copy(update={"artifact_references": ()})
    req = promotion_request(approval_id=approval.approval_id)
    check = ModelPromotionService().check(req, metadata=item, evaluation_report=report, approval=approval, store=InMemoryActiveBundleStore(), deployment_compatibility_verified=True, rollback_target_available=True, activation_authorization=trusted())
    assert PromotionReasonCode.ARTIFACTS_REQUIRED in check.reason_codes


def test_feature_or_evaluation_version_mismatch_is_denied():
    item, report, approval = approved_setup()
    report = report.model_copy(update={"test_manifest": report.test_manifest.model_copy(update={"feature_version": "features-old"})})
    req = promotion_request(approval_id=approval.approval_id)
    check = ModelPromotionService().check(req, metadata=item, evaluation_report=report, approval=approval, store=InMemoryActiveBundleStore(), deployment_compatibility_verified=True, rollback_target_available=True, activation_authorization=trusted())
    assert PromotionReasonCode.EVALUATION_CHANGED in check.reason_codes


def test_synthetic_pointer_cannot_be_production_activated():
    item, report, approval = approved_setup()
    req = promotion_request(approval_id=approval.approval_id)
    service = ModelPromotionService()
    store = InMemoryActiveBundleStore()
    check = service.check(req, metadata=item, evaluation_report=report, approval=approval, store=store, deployment_compatibility_verified=True, rollback_target_available=True, activation_authorization=trusted())
    result = service.activate(req, check, metadata=item.model_copy(update={"synthetic_test_only": True}), store=store, activation_authorization=trusted())
    assert result.status is PromotionStatus.ACTIVATION_BLOCKED
    assert store.active() is None


def test_process_local_store_blocks_production_activation():
    item, report, approval, req, store, check = check_ready()
    assert check.status is PromotionStatus.APPROVED_FOR_CONSIDERATION
    assert PromotionReasonCode.DURABLE_BACKEND_REQUIRED in check.reason_codes
    result = ModelPromotionService().activate(req, check, metadata=item, store=store, activation_authorization=trusted())
    assert result.status is PromotionStatus.ACTIVATION_BLOCKED
    assert not store.durable


def test_stale_generation_rejects_activation_without_mutation():
    item, report, approval = approved_setup()
    initial = active_reference_from_metadata(item, generation=1, activated_at=NOW)
    store = InMemoryActiveBundleStore(initial=initial)
    req = promotion_request(approval_id=approval.approval_id, expected_active_bundle_id=initial.bundle_id, expected_active_generation=99)
    check = ModelPromotionService().check(req, metadata=item, evaluation_report=report, approval=approval, store=store, deployment_compatibility_verified=True, rollback_target_available=True, activation_authorization=trusted())
    assert PromotionReasonCode.STALE_ACTIVE_GENERATION in check.reason_codes
    assert store.active().generation == 1


def test_no_training_or_pipeline_side_effect_from_promotion_check():
    item, report, approval, req, store, check = check_ready()
    assert check.status is PromotionStatus.APPROVED_FOR_CONSIDERATION
    assert store.history() == ()


def test_approval_alone_does_not_change_active_pointer():
    item, report, approval = approved_setup()
    assert approval.production_valid
    assert InMemoryActiveBundleStore().active() is None


def test_candidate_status_must_be_approved_for_activation():
    item, report, approval = approved_setup()
    pending = item.model_copy(update={"status": ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL})
    req = promotion_request(approval_id=approval.approval_id)
    check = ModelPromotionService().check(req, metadata=pending, evaluation_report=report, approval=approval, store=InMemoryActiveBundleStore(), deployment_compatibility_verified=True, rollback_target_available=True, activation_authorization=trusted())
    assert PromotionReasonCode.APPROVAL_REQUIRED in check.reason_codes


def test_artifact_version_change_after_evaluation_is_denied():
    item, report, approval = approved_setup()
    changed = item.model_copy(update={"model_versions": tuple(item.model_versions[:-1]) + (item.model_versions[-1].model_copy(update={"version": "m-30-new"}),)})
    req = promotion_request(approval_id=approval.approval_id)
    check = ModelPromotionService().check(req, metadata=changed, evaluation_report=report, approval=approval, store=InMemoryActiveBundleStore(), deployment_compatibility_verified=True, rollback_target_available=True, activation_authorization=trusted())
    assert PromotionReasonCode.EVALUATION_CHANGED in check.reason_codes


def test_development_cas_is_atomic_and_idempotent():
    item = candidate(status=ModelLifecycleStatus.APPROVED)
    store = InMemoryActiveBundleStore()
    ref = active_reference_from_metadata(item, generation=1, activated_at=NOW)
    assert store.compare_and_swap(expected_bundle_id=None, expected_generation=None, new_reference=ref, request_id="cas-1") == ref
    assert store.compare_and_swap(expected_bundle_id=None, expected_generation=None, new_reference=ref, request_id="cas-1") == ref
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        store.compare_and_swap(expected_bundle_id=None, expected_generation=None, new_reference=ref.model_copy(update={"generation": 2}), request_id="cas-1")
