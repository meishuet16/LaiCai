"""Fail-closed human approval and governance audit primitives.

This module deliberately does not treat a caller supplied role, boolean, or
signature-looking string as authorization.  Production approval requires a
replaceable verifier to return trusted evidence from an external authority.
The in-memory ledger is suitable for isolated tests and local simulations only;
it is not a durable production audit store.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Protocol, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .candidate_evaluation import (
    CandidateEvaluationGateStatus,
    CandidateEvaluationReport,
)
from .historical_evaluation import DatasetProvenanceStatus
from .model_registry import ModelBundleMetadata, ModelLifecycleStatus, RegistryProvenanceStatus


class ApprovalDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class AuthorizationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"
    DENIED = "DENIED"


class ApprovalReasonCode(str, Enum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    AUTHORIZATION_NOT_TRUSTED = "AUTHORIZATION_NOT_TRUSTED"
    SYNTHETIC_NOT_APPROVABLE = "SYNTHETIC_NOT_APPROVABLE"
    EVALUATION_REQUIRED = "EVALUATION_REQUIRED"
    EVALUATION_NOT_ELIGIBLE = "EVALUATION_NOT_ELIGIBLE"
    EVALUATION_MANIFEST_MISMATCH = "EVALUATION_MANIFEST_MISMATCH"
    CANDIDATE_IDENTITY_MISMATCH = "CANDIDATE_IDENTITY_MISMATCH"
    CANDIDATE_NOT_EVALUATED = "CANDIDATE_NOT_EVALUATED"
    ARTIFACTS_REQUIRED = "ARTIFACTS_REQUIRED"
    HORIZON_VERSIONS_REQUIRED = "HORIZON_VERSIONS_REQUIRED"
    DUPLICATE_REQUEST_CONFLICT = "DUPLICATE_REQUEST_CONFLICT"
    IMMUTABLE_DECISION = "IMMUTABLE_DECISION"
    RATIONALE_REQUIRED = "RATIONALE_REQUIRED"


class AuditEventType(str, Enum):
    APPROVAL_ATTEMPT = "APPROVAL_ATTEMPT"
    APPROVAL_RECORDED = "APPROVAL_RECORDED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    PROMOTION_CHECK = "PROMOTION_CHECK"
    ACTIVATION_ATTEMPT = "ACTIVATION_ATTEMPT"
    ACTIVATION_RECORDED = "ACTIVATION_RECORDED"
    ROLLBACK_REQUEST = "ROLLBACK_REQUEST"
    ROLLBACK_CHECK = "ROLLBACK_CHECK"
    ROLLBACK_DENIED = "ROLLBACK_DENIED"
    ROLLBACK_RECORDED = "ROLLBACK_RECORDED"


class _GovernanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthorizationEvidence(_GovernanceModel):
    """Evidence returned by an external authorization verifier.

    ``production_trusted`` is an assertion made by the verifier adapter, not
    by an API caller.  The built-in synthetic verifier can never set it true.
    """

    verification_id: str = Field(min_length=1)
    actor_reference: str = Field(min_length=1)
    actor_role: str = Field(min_length=1)
    authorization_scope: str = Field(min_length=1)
    verified_at: AwareDatetime
    verifier_reference: str = Field(min_length=1)
    status: AuthorizationStatus
    production_trusted: bool = False

    @model_validator(mode="after")
    def validate_trust(self) -> "AuthorizationEvidence":
        if self.production_trusted and self.status is not AuthorizationStatus.VERIFIED:
            raise ValueError("production_trusted evidence must be VERIFIED")
        if self.status is AuthorizationStatus.SYNTHETIC_TEST_ONLY and self.production_trusted:
            raise ValueError("synthetic evidence can never be production trusted")
        return self

    @property
    def valid_for_production(self) -> bool:
        return self.status is AuthorizationStatus.VERIFIED and self.production_trusted


class ApprovalVerifier(Protocol):
    """Replaceable boundary to an external identity/RBAC/audit authority."""

    def verify(
        self, *, actor_reference: str, required_scope: str, request_id: str
    ) -> AuthorizationEvidence: ...


class SyntheticApprovalVerifier:
    """Test-only verifier.  Its evidence is never production-valid."""

    def __init__(self, *, actor_role: str = "synthetic_test_actor") -> None:
        self.actor_role = actor_role

    def verify(
        self, *, actor_reference: str, required_scope: str, request_id: str
    ) -> AuthorizationEvidence:
        return AuthorizationEvidence(
            verification_id=f"synthetic-verification:{request_id}",
            actor_reference=actor_reference,
            actor_role=self.actor_role,
            authorization_scope=required_scope,
            verified_at=datetime.now(timezone.utc),
            verifier_reference="synthetic-test-verifier",
            status=AuthorizationStatus.SYNTHETIC_TEST_ONLY,
            production_trusted=False,
        )


class ApprovalRequest(_GovernanceModel):
    request_id: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_version: str = Field(min_length=1)
    evaluation_manifest_id: str | None = Field(default=None, min_length=1)
    evaluation_evidence_reference: str | None = Field(default=None, min_length=1)
    decision: ApprovalDecision
    actor_reference: str = Field(min_length=1)
    actor_role: str = Field(min_length=1)
    authorization_scope: str = Field(min_length=1)
    decision_timestamp: AwareDatetime
    rationale: str = Field(min_length=1)
    approval_policy_version: str = Field(min_length=1)
    audit_evidence_references: tuple[str, ...] = ()


class ModelApprovalRecord(_GovernanceModel):
    approval_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_version: str = Field(min_length=1)
    evaluation_manifest_id: str | None = None
    evaluation_evidence_reference: str | None = None
    decision: ApprovalDecision
    actor_reference: str = Field(min_length=1)
    actor_role: str = Field(min_length=1)
    authorization_scope: str = Field(min_length=1)
    authorization_status: AuthorizationStatus
    authorization_verification_id: str = Field(min_length=1)
    decision_timestamp: AwareDatetime
    rationale: str = Field(min_length=1)
    approval_policy_version: str = Field(min_length=1)
    audit_evidence_references: tuple[str, ...] = ()
    production_valid: bool = False


class GovernanceAuditEvent(_GovernanceModel):
    event_id: str = Field(min_length=1)
    event_type: AuditEventType
    request_id: str = Field(min_length=1)
    occurred_at: AwareDatetime
    candidate_bundle_id: str | None = None
    active_bundle_id: str | None = None
    actor_reference: str | None = None
    authorization_status: AuthorizationStatus | None = None
    success: bool
    reason_codes: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()


class InMemoryGovernanceAuditLog:
    """Append-only, process-local audit evidence for tests and simulations."""

    durable = False

    def __init__(self) -> None:
        self._events: list[GovernanceAuditEvent] = []

    def append(self, event: GovernanceAuditEvent) -> GovernanceAuditEvent:
        if any(item.event_id == event.event_id for item in self._events):
            raise ValueError("audit event IDs are immutable and append-only")
        self._events.append(deepcopy(event))
        return deepcopy(event)

    def events(self) -> tuple[GovernanceAuditEvent, ...]:
        return tuple(deepcopy(item) for item in self._events)


class ApprovalOutcome(_GovernanceModel):
    accepted: bool
    record: ModelApprovalRecord | None = None
    reason_codes: tuple[ApprovalReasonCode, ...] = ()
    audit_event_id: str = Field(min_length=1)


def _candidate_ready_for_approval(
    candidate: ModelBundleMetadata,
    report: CandidateEvaluationReport | None,
    request: ApprovalRequest,
) -> tuple[ApprovalReasonCode, ...]:
    reasons: list[ApprovalReasonCode] = []
    if candidate.bundle_id != request.candidate_bundle_id:
        reasons.append(ApprovalReasonCode.CANDIDATE_IDENTITY_MISMATCH)
    if candidate.candidate_id != request.candidate_version:
        reasons.append(ApprovalReasonCode.CANDIDATE_IDENTITY_MISMATCH)
    if candidate.status is not ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL:
        reasons.append(ApprovalReasonCode.CANDIDATE_NOT_EVALUATED)
    if candidate.provenance_status is not RegistryProvenanceStatus.AUTHORIZED_REAL or candidate.synthetic_test_only:
        reasons.append(ApprovalReasonCode.SYNTHETIC_NOT_APPROVABLE)
    if not candidate.artifact_references:
        reasons.append(ApprovalReasonCode.ARTIFACTS_REQUIRED)
    if {item.horizon_days for item in candidate.model_versions} != {7, 14, 30}:
        reasons.append(ApprovalReasonCode.HORIZON_VERSIONS_REQUIRED)
    if {item.horizon_days for item in candidate.calibration_versions} != {7, 14, 30}:
        reasons.append(ApprovalReasonCode.HORIZON_VERSIONS_REQUIRED)
    if report is None:
        reasons.append(ApprovalReasonCode.EVALUATION_REQUIRED)
    else:
        if report.gate_status is not CandidateEvaluationGateStatus.ELIGIBLE_FOR_HUMAN_REVIEW:
            reasons.append(ApprovalReasonCode.EVALUATION_NOT_ELIGIBLE)
        if report.synthetic_test_only or report.dataset_provenance_status is not DatasetProvenanceStatus.REAL_AUTHORIZED:
            reasons.append(ApprovalReasonCode.SYNTHETIC_NOT_APPROVABLE)
        if report.candidate_bundle_id != candidate.bundle_id:
            reasons.append(ApprovalReasonCode.CANDIDATE_IDENTITY_MISMATCH)
        if report.test_manifest is None:
            reasons.append(ApprovalReasonCode.EVALUATION_REQUIRED)
        elif request.evaluation_manifest_id != report.test_manifest.manifest_id:
            reasons.append(ApprovalReasonCode.EVALUATION_MANIFEST_MISMATCH)
    return tuple(dict.fromkeys(reasons))


class ModelApprovalLedger:
    """Append-only approval decision boundary; it never activates a bundle."""

    def __init__(self, *, audit_log: InMemoryGovernanceAuditLog | None = None) -> None:
        self.audit_log = audit_log or InMemoryGovernanceAuditLog()
        self._records: dict[str, ModelApprovalRecord] = {}
        self._requests: dict[str, str] = {}

    def submit(
        self,
        request: ApprovalRequest,
        *,
        candidate: ModelBundleMetadata,
        evaluation_report: CandidateEvaluationReport | None,
        verifier: ApprovalVerifier,
    ) -> ApprovalOutcome:
        request_digest = hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        if request.request_id in self._requests:
            previous_digest = self._requests[request.request_id]
            existing = next(
                record for record in self._records.values()
                if record.request_id == request.request_id
            )
            event_id = f"approval-idempotent:{request.request_id}"
            if previous_digest != request_digest:
                event = self._audit(request, AuditEventType.APPROVAL_DENIED, False, (ApprovalReasonCode.DUPLICATE_REQUEST_CONFLICT,))
                return ApprovalOutcome(accepted=False, reason_codes=(ApprovalReasonCode.DUPLICATE_REQUEST_CONFLICT,), audit_event_id=event.event_id)
            event = self._audit(request, AuditEventType.APPROVAL_RECORDED, True, ())
            return ApprovalOutcome(accepted=True, record=existing, audit_event_id=event.event_id)

        evidence = verifier.verify(
            actor_reference=request.actor_reference,
            required_scope=request.authorization_scope,
            request_id=request.request_id,
        )
        if evidence.actor_reference != request.actor_reference or evidence.authorization_scope != request.authorization_scope:
            reasons = (ApprovalReasonCode.AUTHORIZATION_NOT_TRUSTED,)
        elif evidence.status is not AuthorizationStatus.VERIFIED and request.decision is ApprovalDecision.APPROVE:
            reasons = (ApprovalReasonCode.AUTHORIZATION_REQUIRED,)
        elif request.decision is ApprovalDecision.APPROVE and not evidence.valid_for_production:
            reasons = (ApprovalReasonCode.AUTHORIZATION_NOT_TRUSTED,)
        elif not request.rationale.strip():
            reasons = (ApprovalReasonCode.RATIONALE_REQUIRED,)
        else:
            reasons = ()

        if request.decision is ApprovalDecision.APPROVE and not reasons:
            reasons = _candidate_ready_for_approval(candidate, evaluation_report, request)
        if reasons:
            event = self._audit(request, AuditEventType.APPROVAL_DENIED, False, reasons, evidence=evidence)
            return ApprovalOutcome(accepted=False, reason_codes=reasons, audit_event_id=event.event_id)

        approval_id = "approval:" + hashlib.sha256(
            f"{request.request_id}:{request.candidate_bundle_id}:{request.decision.value}".encode()
        ).hexdigest()[:24]
        record = ModelApprovalRecord(
            approval_id=approval_id,
            request_id=request.request_id,
            candidate_bundle_id=request.candidate_bundle_id,
            candidate_version=request.candidate_version,
            evaluation_manifest_id=request.evaluation_manifest_id,
            evaluation_evidence_reference=request.evaluation_evidence_reference,
            decision=request.decision,
            actor_reference=request.actor_reference,
            actor_role=request.actor_role,
            authorization_scope=request.authorization_scope,
            authorization_status=evidence.status,
            authorization_verification_id=evidence.verification_id,
            decision_timestamp=request.decision_timestamp,
            rationale=request.rationale,
            approval_policy_version=request.approval_policy_version,
            audit_evidence_references=request.audit_evidence_references,
            production_valid=request.decision is ApprovalDecision.APPROVE and evidence.valid_for_production,
        )
        self._records[approval_id] = deepcopy(record)
        self._requests[request.request_id] = request_digest
        event = self._audit(request, AuditEventType.APPROVAL_RECORDED, True, (), evidence=evidence)
        return ApprovalOutcome(accepted=True, record=record, audit_event_id=event.event_id)

    def record_for_request(self, request_id: str) -> ModelApprovalRecord | None:
        for record in self._records.values():
            if record.request_id == request_id:
                return deepcopy(record)
        return None

    def records(self) -> tuple[ModelApprovalRecord, ...]:
        return tuple(deepcopy(item) for item in self._records.values())

    def _audit(
        self,
        request: ApprovalRequest,
        event_type: AuditEventType,
        success: bool,
        reasons: Sequence[ApprovalReasonCode],
        *,
        evidence: AuthorizationEvidence | None = None,
    ) -> GovernanceAuditEvent:
        event = GovernanceAuditEvent(
            event_id=f"{event_type.value.lower()}:{request.request_id}:{len(self.audit_log.events())}",
            event_type=event_type,
            request_id=request.request_id,
            occurred_at=request.decision_timestamp,
            candidate_bundle_id=request.candidate_bundle_id,
            actor_reference=request.actor_reference,
            authorization_status=evidence.status if evidence else None,
            success=success,
            reason_codes=tuple(item.value for item in reasons),
            evidence_references=request.audit_evidence_references,
        )
        return self.audit_log.append(event)


__all__ = [
    "ApprovalDecision",
    "ApprovalOutcome",
    "ApprovalReasonCode",
    "ApprovalRequest",
    "ApprovalVerifier",
    "AuditEventType",
    "AuthorizationEvidence",
    "AuthorizationStatus",
    "GovernanceAuditEvent",
    "InMemoryGovernanceAuditLog",
    "ModelApprovalRecord",
    "ModelApprovalLedger",
    "SyntheticApprovalVerifier",
]
