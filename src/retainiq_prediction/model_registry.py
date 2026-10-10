"""Minimal metadata-only registry for future model bundle governance.

The registry is deliberately local and replaceable.  It stores immutable
metadata, never loads artifacts, never changes the active prediction pipeline
bundle, and never promotes a candidate automatically.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import Iterable

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .retraining_readiness import (
    RetrainingReadinessReport,
    RetrainingReadinessStatus,
)


class ModelLifecycleStatus(str, Enum):
    PROPOSED = "PROPOSED"
    BLOCKED = "BLOCKED"
    ELIGIBLE_FOR_TRAINING = "ELIGIBLE_FOR_TRAINING"
    TRAINED_PENDING_EVALUATION = "TRAINED_PENDING_EVALUATION"
    EVALUATED_PENDING_APPROVAL = "EVALUATED_PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class RegistryProvenanceStatus(str, Enum):
    AUTHORIZED_REAL = "authorized_real"
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"
    UNVERIFIED = "unverified"


class RegistryReasonCode(str, Enum):
    SYNTHETIC_NOT_APPROVABLE = "SYNTHETIC_NOT_APPROVABLE"
    PROVENANCE_NOT_AUTHORIZED = "PROVENANCE_NOT_AUTHORIZED"
    READINESS_REQUIRED = "READINESS_REQUIRED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INDEPENDENT_EVALUATION_REQUIRED = "INDEPENDENT_EVALUATION_REQUIRED"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    DUPLICATE_VERSION_CONFLICT = "DUPLICATE_VERSION_CONFLICT"
    ACTIVE_BUNDLE_IMMUTABLE = "ACTIVE_BUNDLE_IMMUTABLE"
    ARTIFACT_NOT_LOADED = "ARTIFACT_NOT_LOADED"


class _RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HorizonVersion(_RegistryModel):
    horizon_days: int
    version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_horizon(self) -> "HorizonVersion":
        if self.horizon_days not in (7, 14, 30):
            raise ValueError("horizon_days must be one of 7, 14, or 30")
        return self


class HumanApproval(_RegistryModel):
    actor_id: str = Field(min_length=1)
    approved_at: AwareDatetime
    reason: str = Field(min_length=1)
    independent_test_evaluated: bool = False
    evaluation_run_id: str | None = Field(default=None, min_length=1)
    rollback_plan_reference: str | None = Field(default=None, min_length=1)


class ModelBundleMetadata(_RegistryModel):
    """Immutable identity and provenance metadata for one bundle candidate."""

    bundle_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    model_versions: tuple[HorizonVersion, ...]
    calibration_versions: tuple[HorizonVersion, ...]
    feature_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    training_configuration_version: str = Field(min_length=1)
    dataset_provenance_reference: str = Field(min_length=1)
    temporal_split_policy_version: str = Field(min_length=1)
    training_freeze_cutoff: AwareDatetime
    evaluation_policy_version: str = Field(min_length=1)
    artifact_references: tuple[str, ...] = ()
    created_at: AwareDatetime
    status: ModelLifecycleStatus = ModelLifecycleStatus.PROPOSED
    reason_codes: tuple[RegistryReasonCode, ...] = ()
    provenance_status: RegistryProvenanceStatus
    synthetic_test_only: bool
    tenant_scope: str | None = None
    readiness_report_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_metadata(self) -> "ModelBundleMetadata":
        horizons = tuple(item.horizon_days for item in self.model_versions)
        calibration_horizons = tuple(item.horizon_days for item in self.calibration_versions)
        if set(horizons) != {7, 14, 30} or len(horizons) != 3:
            raise ValueError("model_versions must contain exactly one 7/14/30-day version")
        if set(calibration_horizons) != {7, 14, 30} or len(calibration_horizons) != 3:
            raise ValueError("calibration_versions must contain exactly one 7/14/30-day version")
        if len(set(horizons)) != len(horizons) or len(set(calibration_horizons)) != len(calibration_horizons):
            raise ValueError("horizon version entries must be unique")
        if self.training_freeze_cutoff > self.created_at:
            raise ValueError("training_freeze_cutoff must not follow created_at")
        if self.provenance_status is RegistryProvenanceStatus.SYNTHETIC_TEST_ONLY and not self.synthetic_test_only:
            raise ValueError("synthetic provenance requires synthetic_test_only")
        if self.provenance_status is RegistryProvenanceStatus.AUTHORIZED_REAL and self.synthetic_test_only:
            raise ValueError("authorized real metadata cannot be synthetic_test_only")
        if self.status is ModelLifecycleStatus.APPROVED:
            if self.provenance_status is not RegistryProvenanceStatus.AUTHORIZED_REAL or self.synthetic_test_only:
                raise ValueError("synthetic or unauthorized metadata cannot be APPROVED")
            if not self.artifact_references:
                raise ValueError("APPROVED metadata requires artifact references")
        return self


class ModelRegistry:
    """In-memory metadata registry with explicit, non-automatic transitions."""

    _allowed_transitions = {
        ModelLifecycleStatus.PROPOSED: {
            ModelLifecycleStatus.BLOCKED,
            ModelLifecycleStatus.ELIGIBLE_FOR_TRAINING,
            ModelLifecycleStatus.REJECTED,
        },
        ModelLifecycleStatus.BLOCKED: {
            ModelLifecycleStatus.PROPOSED,
            ModelLifecycleStatus.REJECTED,
        },
        ModelLifecycleStatus.ELIGIBLE_FOR_TRAINING: {
            ModelLifecycleStatus.BLOCKED,
            ModelLifecycleStatus.TRAINED_PENDING_EVALUATION,
            ModelLifecycleStatus.REJECTED,
        },
        ModelLifecycleStatus.TRAINED_PENDING_EVALUATION: {
            ModelLifecycleStatus.BLOCKED,
            ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL,
            ModelLifecycleStatus.REJECTED,
        },
        ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL: {
            ModelLifecycleStatus.APPROVED,
            ModelLifecycleStatus.BLOCKED,
            ModelLifecycleStatus.REJECTED,
        },
        ModelLifecycleStatus.APPROVED: {ModelLifecycleStatus.RETIRED},
        ModelLifecycleStatus.REJECTED: set(),
        ModelLifecycleStatus.RETIRED: set(),
    }

    def __init__(self, active_bundle: ModelBundleMetadata | None = None) -> None:
        self._candidates: dict[str, ModelBundleMetadata] = {}
        self._active_bundle: ModelBundleMetadata | None = None
        if active_bundle is not None:
            self.register_active_bundle(active_bundle)

    def register_candidate(self, metadata: ModelBundleMetadata) -> ModelBundleMetadata:
        if metadata.status is ModelLifecycleStatus.APPROVED:
            raise ValueError("register_candidate cannot register APPROVED metadata")
        if metadata.candidate_id in self._candidates:
            existing = self._candidates[metadata.candidate_id]
            if existing.model_dump(mode="json") != metadata.model_dump(mode="json"):
                raise ValueError(RegistryReasonCode.DUPLICATE_VERSION_CONFLICT.value)
            return deepcopy(existing)
        if self._active_bundle is not None and metadata.bundle_id == self._active_bundle.bundle_id:
            raise ValueError("bundle_id conflicts with the active bundle")
        if any(item.bundle_id == metadata.bundle_id for item in self._candidates.values()):
            raise ValueError("bundle_id is already registered")
        self._candidates[metadata.candidate_id] = deepcopy(metadata)
        return deepcopy(metadata)

    def candidate_for(self, candidate_id: str) -> ModelBundleMetadata:
        try:
            return deepcopy(self._candidates[candidate_id])
        except KeyError as exc:
            raise KeyError("unknown candidate_id") from exc

    def candidates(self) -> tuple[ModelBundleMetadata, ...]:
        return tuple(deepcopy(item) for item in self._candidates.values())

    def active_bundle(self) -> ModelBundleMetadata | None:
        return deepcopy(self._active_bundle)

    def register_active_bundle(
        self,
        metadata: ModelBundleMetadata,
        *,
        approval: HumanApproval | None = None,
    ) -> ModelBundleMetadata:
        if self._active_bundle is not None:
            raise ValueError(RegistryReasonCode.ACTIVE_BUNDLE_IMMUTABLE.value)
        if metadata.status is not ModelLifecycleStatus.APPROVED:
            raise ValueError("active metadata must have APPROVED status")
        if approval is None or not approval.independent_test_evaluated:
            raise ValueError(RegistryReasonCode.APPROVAL_REQUIRED.value)
        self._active_bundle = deepcopy(metadata)
        return deepcopy(metadata)

    def transition_candidate(
        self,
        candidate_id: str,
        target_status: ModelLifecycleStatus,
        *,
        readiness_report: RetrainingReadinessReport | None = None,
        evidence_note: str | None = None,
        approval: HumanApproval | None = None,
    ) -> ModelBundleMetadata:
        current = self.candidate_for(candidate_id)
        if target_status not in self._allowed_transitions[current.status]:
            raise ValueError(
                f"{RegistryReasonCode.INVALID_TRANSITION.value}: "
                f"{current.status.value}->{target_status.value}"
            )
        if target_status is ModelLifecycleStatus.ELIGIBLE_FOR_TRAINING:
            if readiness_report is None or readiness_report.readiness_status is not RetrainingReadinessStatus.READY_FOR_CANDIDATE_TRAINING:
                raise ValueError(RegistryReasonCode.READINESS_REQUIRED.value)
            if current.synthetic_test_only or current.provenance_status is not RegistryProvenanceStatus.AUTHORIZED_REAL:
                raise ValueError(RegistryReasonCode.PROVENANCE_NOT_AUTHORIZED.value)
            if current.readiness_report_fingerprint and current.readiness_report_fingerprint != readiness_report.fingerprint():
                raise ValueError("readiness report fingerprint does not match candidate metadata")
        if target_status in {
            ModelLifecycleStatus.TRAINED_PENDING_EVALUATION,
            ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL,
        } and not (evidence_note or "").strip():
            raise ValueError("evidence_note is required for this lifecycle transition")
        if target_status is ModelLifecycleStatus.APPROVED:
            if approval is None:
                raise ValueError(RegistryReasonCode.APPROVAL_REQUIRED.value)
            if not approval.independent_test_evaluated:
                raise ValueError(RegistryReasonCode.INDEPENDENT_EVALUATION_REQUIRED.value)
            if current.synthetic_test_only or current.provenance_status is not RegistryProvenanceStatus.AUTHORIZED_REAL:
                raise ValueError(RegistryReasonCode.SYNTHETIC_NOT_APPROVABLE.value)
            if not current.artifact_references:
                raise ValueError("artifact references are required before approval")
        reasons = list(current.reason_codes)
        if target_status is ModelLifecycleStatus.BLOCKED:
            reasons.append(RegistryReasonCode.READINESS_REQUIRED)
        updated = current.model_copy(
            update={
                "status": target_status,
                "reason_codes": tuple(dict.fromkeys(reasons)),
            }
        )
        self._candidates[candidate_id] = updated
        return deepcopy(updated)

    def promote_candidate(
        self,
        candidate_id: str,
        *,
        approval: HumanApproval | None = None,
    ) -> ModelBundleMetadata:
        """Record explicit candidate approval; do not alter active production state."""

        return self.transition_candidate(
            candidate_id,
            ModelLifecycleStatus.APPROVED,
            approval=approval,
        )


__all__ = [
    "HorizonVersion",
    "HumanApproval",
    "ModelBundleMetadata",
    "ModelLifecycleStatus",
    "ModelRegistry",
    "RegistryProvenanceStatus",
    "RegistryReasonCode",
]
