"""Explicit candidate promotion checks and a development-only active pointer.

Promotion is intentionally separate from approval.  This module validates
metadata and evidence, then performs a compare-and-swap only through a
replaceable active-bundle store.  The included store is process-local and
never claims to be a production deployment backend.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Protocol, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .candidate_evaluation import CandidateEvaluationGateStatus, CandidateEvaluationReport
from .model_approval import (
    ApprovalDecision,
    AuthorizationEvidence,
    AuthorizationStatus,
    AuditEventType,
    GovernanceAuditEvent,
    InMemoryGovernanceAuditLog,
    ModelApprovalRecord,
)
from .model_registry import ModelBundleMetadata, ModelLifecycleStatus, RegistryProvenanceStatus


class PromotionStatus(str, Enum):
    APPROVED_FOR_CONSIDERATION = "APPROVED_FOR_CONSIDERATION"
    TECHNICALLY_ELIGIBLE = "TECHNICALLY_ELIGIBLE"
    SIMULATION_ELIGIBLE = "SIMULATION_ELIGIBLE"
    ACTIVATION_BLOCKED = "ACTIVATION_BLOCKED"
    ACTIVATED = "ACTIVATED"
    DENIED = "DENIED"


class PromotionReasonCode(str, Enum):
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_NOT_TRUSTED = "APPROVAL_NOT_TRUSTED"
    APPROVAL_IDENTITY_MISMATCH = "APPROVAL_IDENTITY_MISMATCH"
    EVALUATION_REQUIRED = "EVALUATION_REQUIRED"
    EVALUATION_NOT_FROZEN = "EVALUATION_NOT_FROZEN"
    EVALUATION_CHANGED = "EVALUATION_CHANGED"
    REAL_PROVENANCE_REQUIRED = "REAL_PROVENANCE_REQUIRED"
    ARTIFACTS_REQUIRED = "ARTIFACTS_REQUIRED"
    HORIZON_ARTIFACTS_REQUIRED = "HORIZON_ARTIFACTS_REQUIRED"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    LABEL_POLICY_VERSION_MISMATCH = "LABEL_POLICY_VERSION_MISMATCH"
    MODEL_VERSION_MISMATCH = "MODEL_VERSION_MISMATCH"
    CALIBRATION_VERSION_MISMATCH = "CALIBRATION_VERSION_MISMATCH"
    DEPLOYMENT_COMPATIBILITY_REQUIRED = "DEPLOYMENT_COMPATIBILITY_REQUIRED"
    ROLLBACK_TARGET_REQUIRED = "ROLLBACK_TARGET_REQUIRED"
    DURABLE_BACKEND_REQUIRED = "DURABLE_BACKEND_REQUIRED"
    ACTIVATION_AUTH_REQUIRED = "ACTIVATION_AUTH_REQUIRED"
    STALE_ACTIVE_GENERATION = "STALE_ACTIVE_GENERATION"
    SYNTHETIC_NOT_PRODUCTION = "SYNTHETIC_NOT_PRODUCTION"
    ACTIVE_POINTER_CONFLICT = "ACTIVE_POINTER_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


class _PromotionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActiveBundleReference(_PromotionModel):
    bundle_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    model_version_references: tuple[str, ...]
    calibration_version_references: tuple[str, ...]
    feature_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    provenance_reference: str = Field(min_length=1)
    artifact_references: tuple[str, ...]
    synthetic_test_only: bool = False
    previous_bundle_id: str | None = None
    activated_at: AwareDatetime


class PromotionRequest(_PromotionModel):
    request_id: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_version: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    evaluation_manifest_id: str = Field(min_length=1)
    expected_active_bundle_id: str | None = None
    expected_active_generation: int | None = Field(default=None, ge=1)
    rollback_target_bundle_id: str | None = None
    deployment_compatibility_reference: str | None = None
    requested_at: AwareDatetime
    policy_version: str = Field(min_length=1)
    actor_reference: str = Field(default="unspecified", min_length=1)
    authorization_scope: str = Field(default="model.activate", min_length=1)
    audit_evidence_references: tuple[str, ...] = ()


class PromotionCheck(_PromotionModel):
    request_id: str = Field(min_length=1)
    status: PromotionStatus
    reason_codes: tuple[PromotionReasonCode, ...] = ()
    candidate_bundle_id: str = Field(min_length=1)
    active_before: ActiveBundleReference | None = None
    audit_event_id: str = Field(min_length=1)


class ActivationResult(_PromotionModel):
    request_id: str = Field(min_length=1)
    status: PromotionStatus
    active_reference: ActiveBundleReference | None = None
    reason_codes: tuple[PromotionReasonCode, ...] = ()
    audit_event_id: str = Field(min_length=1)


class ActiveBundleStore(Protocol):
    durable: bool
    production_capable: bool

    def active(self) -> ActiveBundleReference | None: ...

    def compare_and_swap(
        self,
        *,
        expected_bundle_id: str | None,
        expected_generation: int | None,
        new_reference: ActiveBundleReference,
        request_id: str,
    ) -> ActiveBundleReference: ...


def active_reference_from_metadata(
    metadata: ModelBundleMetadata, *, generation: int, previous_bundle_id: str | None = None,
    activated_at: datetime | None = None,
) -> ActiveBundleReference:
    when = activated_at or datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("activated_at must be timezone-aware")
    return ActiveBundleReference(
        bundle_id=metadata.bundle_id,
        generation=generation,
        model_version_references=tuple(item.version for item in sorted(metadata.model_versions, key=lambda item: item.horizon_days)),
        calibration_version_references=tuple(item.version for item in sorted(metadata.calibration_versions, key=lambda item: item.horizon_days)),
        feature_version=metadata.feature_version,
        label_policy_version=metadata.label_policy_version,
        provenance_reference=metadata.dataset_provenance_reference,
        artifact_references=metadata.artifact_references,
        synthetic_test_only=metadata.synthetic_test_only,
        previous_bundle_id=previous_bundle_id,
        activated_at=when,
    )


class InMemoryActiveBundleStore:
    """Development-only active pointer with local CAS and transition history."""

    durable = False
    production_capable = False

    def __init__(self, *, initial: ActiveBundleReference | None = None, audit_log: InMemoryGovernanceAuditLog | None = None) -> None:
        self._active = deepcopy(initial)
        self._history: list[ActiveBundleReference] = [deepcopy(initial)] if initial else []
        self._requests: dict[str, ActiveBundleReference] = {}
        self._request_digests: dict[str, str] = {}
        self.audit_log = audit_log or InMemoryGovernanceAuditLog()

    def active(self) -> ActiveBundleReference | None:
        return deepcopy(self._active)

    def history(self) -> tuple[ActiveBundleReference, ...]:
        return tuple(deepcopy(item) for item in self._history)

    def compare_and_swap(
        self,
        *,
        expected_bundle_id: str | None,
        expected_generation: int | None,
        new_reference: ActiveBundleReference,
        request_id: str,
    ) -> ActiveBundleReference:
        digest = hashlib.sha256(new_reference.model_dump_json().encode()).hexdigest()
        if request_id in self._requests:
            if self._request_digests[request_id] != digest:
                raise ValueError(PromotionReasonCode.IDEMPOTENCY_CONFLICT.value)
            return deepcopy(self._requests[request_id])
        current = self._active
        current_id = current.bundle_id if current else None
        current_generation = current.generation if current else None
        if current_id != expected_bundle_id or current_generation != expected_generation:
            raise ValueError(PromotionReasonCode.STALE_ACTIVE_GENERATION.value)
        if new_reference.generation != (current_generation or 0) + 1:
            raise ValueError(PromotionReasonCode.ACTIVE_POINTER_CONFLICT.value)
        self._active = deepcopy(new_reference)
        self._history.append(deepcopy(new_reference))
        self._requests[request_id] = deepcopy(new_reference)
        self._request_digests[request_id] = digest
        return deepcopy(new_reference)


def _version_sets_match(metadata: ModelBundleMetadata, report: CandidateEvaluationReport) -> bool:
    manifest = report.test_manifest
    if manifest is None:
        return False
    models = tuple(item.version for item in sorted(metadata.model_versions, key=lambda item: item.horizon_days))
    calibrators = tuple(item.version for item in sorted(metadata.calibration_versions, key=lambda item: item.horizon_days))
    return (
        models == manifest.model_version_references
        and calibrators == manifest.calibration_version_references
        and metadata.feature_version == manifest.feature_version
        and metadata.label_policy_version == manifest.label_policy_version
        and metadata.temporal_split_policy_version == manifest.temporal_split_policy_version
    )


def _base_reasons(
    request: PromotionRequest,
    metadata: ModelBundleMetadata,
    report: CandidateEvaluationReport | None,
    approval: ModelApprovalRecord | None,
    *,
    deployment_compatibility_verified: bool,
    rollback_target_available: bool,
    activation_authorization: AuthorizationEvidence | None,
    store: ActiveBundleStore,
) -> list[PromotionReasonCode]:
    reasons: list[PromotionReasonCode] = []
    if metadata.status is not ModelLifecycleStatus.APPROVED:
        reasons.append(PromotionReasonCode.APPROVAL_REQUIRED)
    if approval is None or approval.decision is not ApprovalDecision.APPROVE:
        reasons.append(PromotionReasonCode.APPROVAL_REQUIRED)
    elif not approval.production_valid:
        reasons.append(PromotionReasonCode.APPROVAL_NOT_TRUSTED)
    elif approval.candidate_bundle_id != request.candidate_bundle_id or approval.approval_id != request.approval_id:
        reasons.append(PromotionReasonCode.APPROVAL_IDENTITY_MISMATCH)
    if report is None or report.test_manifest is None:
        reasons.append(PromotionReasonCode.EVALUATION_REQUIRED)
    else:
        if report.gate_status is not CandidateEvaluationGateStatus.ELIGIBLE_FOR_HUMAN_REVIEW or not report.test_accessed:
            reasons.append(PromotionReasonCode.EVALUATION_NOT_FROZEN)
        if report.test_manifest.manifest_id != request.evaluation_manifest_id:
            reasons.append(PromotionReasonCode.EVALUATION_CHANGED)
        if not _version_sets_match(metadata, report):
            reasons.append(PromotionReasonCode.EVALUATION_CHANGED)
    if metadata.provenance_status is not RegistryProvenanceStatus.AUTHORIZED_REAL or metadata.synthetic_test_only:
        reasons.append(PromotionReasonCode.REAL_PROVENANCE_REQUIRED)
    if not metadata.artifact_references:
        reasons.append(PromotionReasonCode.ARTIFACTS_REQUIRED)
    if {item.horizon_days for item in metadata.model_versions} != {7, 14, 30} or {item.horizon_days for item in metadata.calibration_versions} != {7, 14, 30}:
        reasons.append(PromotionReasonCode.HORIZON_ARTIFACTS_REQUIRED)
    if not deployment_compatibility_verified:
        reasons.append(PromotionReasonCode.DEPLOYMENT_COMPATIBILITY_REQUIRED)
    if not rollback_target_available and store.active() is not None:
        reasons.append(PromotionReasonCode.ROLLBACK_TARGET_REQUIRED)
    if not store.durable or not store.production_capable:
        reasons.append(PromotionReasonCode.DURABLE_BACKEND_REQUIRED)
    if activation_authorization is None or not activation_authorization.valid_for_production:
        reasons.append(PromotionReasonCode.ACTIVATION_AUTH_REQUIRED)
    current = store.active()
    if current and (current.bundle_id != request.expected_active_bundle_id or current.generation != request.expected_active_generation):
        reasons.append(PromotionReasonCode.STALE_ACTIVE_GENERATION)
    if not current and (request.expected_active_bundle_id is not None or request.expected_active_generation is not None):
        reasons.append(PromotionReasonCode.STALE_ACTIVE_GENERATION)
    return list(dict.fromkeys(reasons))


class ModelPromotionService:
    """Separate consideration, eligibility, and activation operations."""

    def __init__(self, *, audit_log: InMemoryGovernanceAuditLog | None = None) -> None:
        self.audit_log = audit_log or InMemoryGovernanceAuditLog()

    def check(
        self,
        request: PromotionRequest,
        *,
        metadata: ModelBundleMetadata,
        evaluation_report: CandidateEvaluationReport | None,
        approval: ModelApprovalRecord | None,
        store: ActiveBundleStore,
        deployment_compatibility_verified: bool,
        rollback_target_available: bool,
        activation_authorization: AuthorizationEvidence | None,
    ) -> PromotionCheck:
        reasons = _base_reasons(
            request, metadata, evaluation_report, approval,
            deployment_compatibility_verified=deployment_compatibility_verified,
            rollback_target_available=rollback_target_available,
            activation_authorization=activation_authorization,
            store=store,
        )
        consideration_reasons = [reason for reason in reasons if reason not in {
            PromotionReasonCode.DURABLE_BACKEND_REQUIRED,
            PromotionReasonCode.ACTIVATION_AUTH_REQUIRED,
        }]
        if consideration_reasons:
            status = PromotionStatus.DENIED
        elif reasons:
            status = PromotionStatus.APPROVED_FOR_CONSIDERATION
        else:
            status = PromotionStatus.TECHNICALLY_ELIGIBLE
        event = self._audit(request, AuditEventType.PROMOTION_CHECK, not reasons, reasons, store=store)
        return PromotionCheck(
            request_id=request.request_id,
            status=status,
            reason_codes=tuple(reasons),
            candidate_bundle_id=request.candidate_bundle_id,
            active_before=store.active(),
            audit_event_id=event.event_id,
        )

    def activate(
        self,
        request: PromotionRequest,
        check: PromotionCheck,
        *,
        metadata: ModelBundleMetadata,
        store: ActiveBundleStore,
        activation_authorization: AuthorizationEvidence,
        simulation: bool = False,
    ) -> ActivationResult:
        reasons: list[PromotionReasonCode] = []
        if check.status is not PromotionStatus.TECHNICALLY_ELIGIBLE:
            reasons.extend(check.reason_codes or (PromotionReasonCode.DURABLE_BACKEND_REQUIRED,))
        if not activation_authorization.valid_for_production and not simulation:
            reasons.append(PromotionReasonCode.ACTIVATION_AUTH_REQUIRED)
        if metadata.synthetic_test_only and not simulation:
            reasons.append(PromotionReasonCode.SYNTHETIC_NOT_PRODUCTION)
        if not simulation and (not store.durable or not store.production_capable):
            reasons.append(PromotionReasonCode.DURABLE_BACKEND_REQUIRED)
        if reasons:
            event = self._audit(request, AuditEventType.ACTIVATION_ATTEMPT, False, tuple(dict.fromkeys(reasons)), store=store)
            return ActivationResult(request_id=request.request_id, status=PromotionStatus.ACTIVATION_BLOCKED, reason_codes=tuple(dict.fromkeys(reasons)), audit_event_id=event.event_id)
        current = store.active()
        generation = (current.generation if current else 0) + 1
        reference = active_reference_from_metadata(metadata, generation=generation, previous_bundle_id=current.bundle_id if current else None)
        try:
            active = store.compare_and_swap(
                expected_bundle_id=request.expected_active_bundle_id,
                expected_generation=request.expected_active_generation,
                new_reference=reference,
                request_id=request.request_id,
            )
        except ValueError as exc:
            reason = PromotionReasonCode.STALE_ACTIVE_GENERATION if "STALE" in str(exc) else PromotionReasonCode.ACTIVE_POINTER_CONFLICT
            event = self._audit(request, AuditEventType.ACTIVATION_ATTEMPT, False, (reason,), store=store)
            return ActivationResult(request_id=request.request_id, status=PromotionStatus.DENIED, reason_codes=(reason,), audit_event_id=event.event_id)
        event = self._audit(request, AuditEventType.ACTIVATION_RECORDED, True, (), store=store, active_bundle_id=active.bundle_id)
        return ActivationResult(request_id=request.request_id, status=PromotionStatus.ACTIVATED, active_reference=active, audit_event_id=event.event_id)

    def _audit(self, request: PromotionRequest, event_type: AuditEventType, success: bool, reasons: Sequence[PromotionReasonCode], *, store: ActiveBundleStore, active_bundle_id: str | None = None) -> GovernanceAuditEvent:
        event = GovernanceAuditEvent(
            event_id=f"{event_type.value.lower()}:{request.request_id}:{len(self.audit_log.events())}",
            event_type=event_type,
            request_id=request.request_id,
            occurred_at=request.requested_at,
            candidate_bundle_id=request.candidate_bundle_id,
            active_bundle_id=active_bundle_id or (store.active().bundle_id if store.active() else None),
            actor_reference=request.actor_reference,
            success=success,
            reason_codes=tuple(item.value for item in reasons),
            evidence_references=request.audit_evidence_references,
        )
        return self.audit_log.append(event)


__all__ = [
    "ActiveBundleReference",
    "ActiveBundleStore",
    "ActivationResult",
    "InMemoryActiveBundleStore",
    "ModelPromotionService",
    "PromotionCheck",
    "PromotionReasonCode",
    "PromotionRequest",
    "PromotionStatus",
    "active_reference_from_metadata",
]
