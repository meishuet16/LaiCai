"""Authorized, version-preserving rollback checks over active bundle refs."""

from __future__ import annotations

from datetime import timezone
from enum import Enum
from typing import Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .model_approval import (
    AuthorizationEvidence,
    AuthorizationStatus,
    AuditEventType,
    GovernanceAuditEvent,
    InMemoryGovernanceAuditLog,
)
from .model_promotion import ActiveBundleReference, ActiveBundleStore, active_reference_from_metadata
from .model_registry import ModelBundleMetadata, ModelLifecycleStatus, RegistryProvenanceStatus


class RollbackStatus(str, Enum):
    ELIGIBLE_FOR_SIMULATION = "ELIGIBLE_FOR_SIMULATION"
    ELIGIBLE_FOR_PRODUCTION = "ELIGIBLE_FOR_PRODUCTION"
    ACTIVATION_BLOCKED = "ACTIVATION_BLOCKED"
    DENIED = "DENIED"
    ROLLED_BACK = "ROLLED_BACK"


class RollbackReasonCode(str, Enum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    TARGET_UNKNOWN = "TARGET_UNKNOWN"
    TARGET_NOT_APPROVED = "TARGET_NOT_APPROVED"
    TARGET_SYNTHETIC = "TARGET_SYNTHETIC"
    TARGET_ARTIFACTS_MISSING = "TARGET_ARTIFACTS_MISSING"
    TARGET_HORIZONS_INCOMPLETE = "TARGET_HORIZONS_INCOMPLETE"
    STALE_ACTIVE_GENERATION = "STALE_ACTIVE_GENERATION"
    DURABLE_BACKEND_REQUIRED = "DURABLE_BACKEND_REQUIRED"
    REASON_REQUIRED = "REASON_REQUIRED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


class _RollbackModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RollbackRequest(_RollbackModel):
    request_id: str = Field(min_length=1)
    active_bundle_id: str = Field(min_length=1)
    active_generation: int = Field(ge=1)
    previous_known_good_bundle_id: str = Field(min_length=1)
    actor_reference: str = Field(min_length=1)
    authorization_scope: str = Field(min_length=1)
    auth_evidence_reference: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    request_timestamp: AwareDatetime
    policy_version: str = Field(min_length=1)
    audit_evidence_references: tuple[str, ...] = ()
    production_requested: bool = False


class RollbackCheck(_RollbackModel):
    request_id: str = Field(min_length=1)
    status: RollbackStatus
    reason_codes: tuple[RollbackReasonCode, ...] = ()
    audit_event_id: str = Field(min_length=1)


class RollbackResult(_RollbackModel):
    request_id: str = Field(min_length=1)
    status: RollbackStatus
    active_reference: ActiveBundleReference | None = None
    reason_codes: tuple[RollbackReasonCode, ...] = ()
    audit_event_id: str = Field(min_length=1)


class ModelRollbackService:
    def __init__(self, *, audit_log: InMemoryGovernanceAuditLog | None = None) -> None:
        self.audit_log = audit_log or InMemoryGovernanceAuditLog()

    def check(
        self,
        request: RollbackRequest,
        *,
        store: ActiveBundleStore,
        target: ModelBundleMetadata | None,
        authorization: AuthorizationEvidence | None,
    ) -> RollbackCheck:
        reasons: list[RollbackReasonCode] = []
        current = store.active()
        if authorization is None or authorization.status is not AuthorizationStatus.VERIFIED or not authorization.valid_for_production:
            reasons.append(RollbackReasonCode.AUTHORIZATION_REQUIRED)
        if not request.reason.strip():
            reasons.append(RollbackReasonCode.REASON_REQUIRED)
        if target is None or target.bundle_id != request.previous_known_good_bundle_id:
            reasons.append(RollbackReasonCode.TARGET_UNKNOWN)
        else:
            if target.status is not ModelLifecycleStatus.APPROVED:
                reasons.append(RollbackReasonCode.TARGET_NOT_APPROVED)
            if target.provenance_status is not RegistryProvenanceStatus.AUTHORIZED_REAL or target.synthetic_test_only:
                reasons.append(RollbackReasonCode.TARGET_SYNTHETIC)
            if not target.artifact_references:
                reasons.append(RollbackReasonCode.TARGET_ARTIFACTS_MISSING)
            if {item.horizon_days for item in target.model_versions} != {7, 14, 30} or {item.horizon_days for item in target.calibration_versions} != {7, 14, 30}:
                reasons.append(RollbackReasonCode.TARGET_HORIZONS_INCOMPLETE)
        if current is None or current.bundle_id != request.active_bundle_id or current.generation != request.active_generation:
            reasons.append(RollbackReasonCode.STALE_ACTIVE_GENERATION)
        if request.production_requested and (not store.durable or not store.production_capable):
            reasons.append(RollbackReasonCode.DURABLE_BACKEND_REQUIRED)
        reasons = list(dict.fromkeys(reasons))
        if reasons:
            status = RollbackStatus.ACTIVATION_BLOCKED if RollbackReasonCode.DURABLE_BACKEND_REQUIRED in reasons and len(reasons) == 1 else RollbackStatus.DENIED
        elif request.production_requested:
            status = RollbackStatus.ELIGIBLE_FOR_PRODUCTION
        else:
            status = RollbackStatus.ELIGIBLE_FOR_SIMULATION
        event = self._audit(request, AuditEventType.ROLLBACK_CHECK, not reasons, reasons, active_bundle_id=current.bundle_id if current else None, authorization=authorization)
        return RollbackCheck(request_id=request.request_id, status=status, reason_codes=tuple(reasons), audit_event_id=event.event_id)

    def execute(
        self,
        request: RollbackRequest,
        check: RollbackCheck,
        *,
        store: ActiveBundleStore,
        target: ModelBundleMetadata,
        simulation: bool = False,
    ) -> RollbackResult:
        reasons: list[RollbackReasonCode] = []
        if check.status not in {RollbackStatus.ELIGIBLE_FOR_SIMULATION, RollbackStatus.ELIGIBLE_FOR_PRODUCTION}:
            reasons.extend(check.reason_codes or (RollbackReasonCode.TARGET_UNKNOWN,))
        if request.production_requested and not store.production_capable and not simulation:
            reasons.append(RollbackReasonCode.DURABLE_BACKEND_REQUIRED)
        if not simulation and not store.durable:
            reasons.append(RollbackReasonCode.DURABLE_BACKEND_REQUIRED)
        if reasons:
            event = self._audit(request, AuditEventType.ROLLBACK_DENIED, False, tuple(dict.fromkeys(reasons)), active_bundle_id=request.active_bundle_id, authorization=None)
            return RollbackResult(request_id=request.request_id, status=RollbackStatus.ACTIVATION_BLOCKED, reason_codes=tuple(dict.fromkeys(reasons)), audit_event_id=event.event_id)
        current = store.active()
        reference = active_reference_from_metadata(target, generation=request.active_generation + 1, previous_bundle_id=current.bundle_id if current else None)
        try:
            active = store.compare_and_swap(
                expected_bundle_id=request.active_bundle_id,
                expected_generation=request.active_generation,
                new_reference=reference,
                request_id=request.request_id,
            )
        except ValueError:
            event = self._audit(request, AuditEventType.ROLLBACK_DENIED, False, (RollbackReasonCode.STALE_ACTIVE_GENERATION,), active_bundle_id=request.active_bundle_id, authorization=None)
            return RollbackResult(request_id=request.request_id, status=RollbackStatus.DENIED, reason_codes=(RollbackReasonCode.STALE_ACTIVE_GENERATION,), audit_event_id=event.event_id)
        event = self._audit(request, AuditEventType.ROLLBACK_RECORDED, True, (), active_bundle_id=active.bundle_id, authorization=None)
        return RollbackResult(request_id=request.request_id, status=RollbackStatus.ROLLED_BACK, active_reference=active, audit_event_id=event.event_id)

    def _audit(self, request: RollbackRequest, event_type: AuditEventType, success: bool, reasons: Sequence[RollbackReasonCode], *, active_bundle_id: str | None, authorization: AuthorizationEvidence | None) -> GovernanceAuditEvent:
        event = GovernanceAuditEvent(
            event_id=f"{event_type.value.lower()}:{request.request_id}:{len(self.audit_log.events())}",
            event_type=event_type,
            request_id=request.request_id,
            occurred_at=request.request_timestamp,
            active_bundle_id=active_bundle_id,
            actor_reference=request.actor_reference,
            authorization_status=authorization.status if authorization else None,
            success=success,
            reason_codes=tuple(item.value for item in reasons),
            evidence_references=request.audit_evidence_references,
        )
        return self.audit_log.append(event)


__all__ = [
    "ModelRollbackService",
    "RollbackCheck",
    "RollbackReasonCode",
    "RollbackRequest",
    "RollbackResult",
    "RollbackStatus",
]
