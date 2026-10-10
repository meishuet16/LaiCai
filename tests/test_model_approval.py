from datetime import datetime, timezone

from retainiq_prediction.candidate_evaluation import (
    CandidateEvaluationGateStatus,
    CandidateEvaluationReport,
    FrozenTestEvaluationManifest,
)
from retainiq_prediction.historical_evaluation import DatasetProvenanceStatus
from retainiq_prediction.model_approval import (
    ApprovalDecision,
    ApprovalReasonCode,
    ApprovalRequest,
    AuthorizationEvidence,
    AuthorizationStatus,
    InMemoryGovernanceAuditLog,
    ModelApprovalLedger,
    SyntheticApprovalVerifier,
)
from retainiq_prediction.model_registry import (
    HorizonVersion,
    ModelBundleMetadata,
    ModelLifecycleStatus,
    RegistryProvenanceStatus,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TrustedVerifier:
    def verify(self, *, actor_reference, required_scope, request_id):
        return AuthorizationEvidence(
            verification_id=f"external:{request_id}",
            actor_reference=actor_reference,
            actor_role="release_operator",
            authorization_scope=required_scope,
            verified_at=NOW,
            verifier_reference="external-rbac",
            status=AuthorizationStatus.VERIFIED,
            production_trusted=True,
        )


class UntrustedAdminVerifier:
    def verify(self, *, actor_reference, required_scope, request_id):
        return AuthorizationEvidence(
            verification_id=f"caller:{request_id}",
            actor_reference=actor_reference,
            actor_role="admin",
            authorization_scope=required_scope,
            verified_at=NOW,
            verifier_reference="caller-claim",
            status=AuthorizationStatus.UNVERIFIED,
        )


def candidate(*, status=ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL, synthetic=False):
    provenance = RegistryProvenanceStatus.SYNTHETIC_TEST_ONLY if synthetic else RegistryProvenanceStatus.AUTHORIZED_REAL
    return ModelBundleMetadata(
        bundle_id="bundle-candidate",
        candidate_id="candidate-v1",
        model_family="lightgbm",
        model_versions=tuple(HorizonVersion(horizon_days=h, version=f"m-{h}-1") for h in (7, 14, 30)),
        calibration_versions=tuple(HorizonVersion(horizon_days=h, version=f"c-{h}-1") for h in (7, 14, 30)),
        feature_version="features-v1",
        label_policy_version="labels-v1",
        training_configuration_version="train-v1",
        dataset_provenance_reference="dataset-real" if not synthetic else "dataset-synthetic",
        temporal_split_policy_version="split-v1",
        training_freeze_cutoff=NOW,
        evaluation_policy_version="eval-v1",
        artifact_references=("artifact-7", "artifact-14", "artifact-30"),
        created_at=NOW,
        status=status,
        provenance_status=provenance,
        synthetic_test_only=synthetic,
    )


def report_for(item):
    manifest = FrozenTestEvaluationManifest(
        manifest_id="manifest-1",
        candidate_bundle_id=item.bundle_id,
        candidate_id=item.candidate_id,
        candidate_metadata_fingerprint="a" * 64,
        model_version_references=("m-7-1", "m-14-1", "m-30-1"),
        calibration_version_references=("c-7-1", "c-14-1", "c-30-1"),
        feature_version=item.feature_version,
        label_policy_version=item.label_policy_version,
        dataset_provenance_reference=item.dataset_provenance_reference,
        temporal_split_policy_version=item.temporal_split_policy_version,
        training_freeze_cutoff=NOW,
        evaluation_policy_version=item.evaluation_policy_version,
        evaluation_configuration_fingerprint="b" * 64,
        test_authorization_reference="test-auth",
        frozen_at=NOW,
    )
    return CandidateEvaluationReport(
        gate_status=CandidateEvaluationGateStatus.ELIGIBLE_FOR_HUMAN_REVIEW,
        candidate_bundle_id=item.bundle_id,
        champion_bundle_id="bundle-champion",
        evaluation_run_id="eval-run-1",
        evaluation_status="available",
        dataset_provenance_status=DatasetProvenanceStatus.REAL_AUTHORIZED,
        synthetic_test_only=False,
        split_policy_version=item.temporal_split_policy_version,
        evaluation_cutoff=NOW,
        test_manifest=manifest,
        test_accessed=True,
    )


def request(decision=ApprovalDecision.APPROVE, request_id="approval-request-1"):
    return ApprovalRequest(
        request_id=request_id,
        candidate_bundle_id="bundle-candidate",
        candidate_version="candidate-v1",
        evaluation_manifest_id="manifest-1",
        evaluation_evidence_reference="eval-evidence-1",
        decision=decision,
        actor_reference="operator-1",
        actor_role="release_operator",
        authorization_scope="model.release",
        decision_timestamp=NOW,
        rationale="Independent evaluation reviewed.",
        approval_policy_version="approval-v1",
        audit_evidence_references=("ticket-1",),
    )


def test_candidate_cannot_be_approved_without_evaluation():
    result = ModelApprovalLedger().submit(request(), candidate=candidate(), evaluation_report=None, verifier=TrustedVerifier())
    assert not result.accepted
    assert ApprovalReasonCode.EVALUATION_REQUIRED in result.reason_codes


def test_synthetic_candidate_cannot_receive_production_approval():
    result = ModelApprovalLedger().submit(request(), candidate=candidate(synthetic=True), evaluation_report=report_for(candidate(synthetic=True)), verifier=TrustedVerifier())
    assert not result.accepted
    assert ApprovalReasonCode.SYNTHETIC_NOT_APPROVABLE in result.reason_codes


def test_missing_external_authorization_fails_closed():
    result = ModelApprovalLedger().submit(request(), candidate=candidate(), evaluation_report=report_for(candidate()), verifier=UntrustedAdminVerifier())
    assert not result.accepted
    assert ApprovalReasonCode.AUTHORIZATION_REQUIRED in result.reason_codes


def test_caller_admin_string_is_not_authorization():
    result = ModelApprovalLedger().submit(request(), candidate=candidate(), evaluation_report=report_for(candidate()), verifier=SyntheticApprovalVerifier())
    assert not result.accepted
    assert ApprovalReasonCode.AUTHORIZATION_REQUIRED in result.reason_codes


def test_valid_external_approval_is_audited_and_not_activation():
    log = InMemoryGovernanceAuditLog()
    ledger = ModelApprovalLedger(audit_log=log)
    result = ledger.submit(request(), candidate=candidate(), evaluation_report=report_for(candidate()), verifier=TrustedVerifier())
    assert result.accepted and result.record is not None and result.record.production_valid
    assert len(log.events()) == 1
    assert result.record.decision is ApprovalDecision.APPROVE


def test_rejection_preserves_rationale_and_does_not_mutate_candidate():
    item = candidate()
    result = ModelApprovalLedger().submit(request(ApprovalDecision.REJECT), candidate=item, evaluation_report=None, verifier=TrustedVerifier())
    assert result.accepted and result.record is not None
    assert result.record.decision is ApprovalDecision.REJECT
    assert result.record.rationale == "Independent evaluation reviewed."
    assert item.status is ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL


def test_duplicate_request_is_idempotent():
    ledger = ModelApprovalLedger()
    first = ledger.submit(request(), candidate=candidate(), evaluation_report=report_for(candidate()), verifier=TrustedVerifier())
    second = ledger.submit(request(), candidate=candidate(), evaluation_report=report_for(candidate()), verifier=TrustedVerifier())
    assert first.record == second.record
    assert len(ledger.records()) == 1


def test_duplicate_request_conflict_is_denied():
    ledger = ModelApprovalLedger()
    ledger.submit(request(), candidate=candidate(), evaluation_report=report_for(candidate()), verifier=TrustedVerifier())
    conflict = ledger.submit(request(ApprovalDecision.REJECT), candidate=candidate(), evaluation_report=None, verifier=TrustedVerifier())
    assert not conflict.accepted
    assert ApprovalReasonCode.DUPLICATE_REQUEST_CONFLICT in conflict.reason_codes


def test_approval_record_is_immutable():
    result = ModelApprovalLedger().submit(request(), candidate=candidate(), evaluation_report=report_for(candidate()), verifier=TrustedVerifier())
    assert result.record is not None
    try:
        result.record.rationale = "changed"
    except Exception:
        pass
    assert result.record.rationale != "changed"
