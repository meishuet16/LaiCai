"""Governance checks before a future candidate model may be trained.

This module only assesses evidence.  It does not construct a training matrix,
fit a model, calibrate probabilities, select thresholds, or promote a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Sequence, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .contracts import PredictionStatus
from .dataset_readiness import (
    DatasetProvenance,
    DatasetReadinessReport,
    DatasetStatus,
    ProvenanceEvidenceType,
)
from .label_builder import LabelReasonCode, SUPPORTED_HORIZONS
from .outcome_reconciliation import (
    FeedbackProvenanceStatus,
    FeedbackStatus,
    OutcomeReasonCode,
    PredictionFeedback,
    assess_learning_eligibility,
)
from .temporal_splits import SplitName, TemporalSplitResult


class RetrainingReadinessStatus(str, Enum):
    READY_FOR_CANDIDATE_TRAINING = "READY_FOR_CANDIDATE_TRAINING"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"


class HorizonReadinessStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"


class RetrainingReasonCode(str, Enum):
    DATASET_READINESS_MISSING = "DATASET_READINESS_MISSING"
    DATASET_NOT_PASS = "DATASET_NOT_PASS"
    DATASET_NOT_AUTHORIZED = "DATASET_NOT_AUTHORIZED"
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    PROVENANCE_UNVERIFIED = "PROVENANCE_UNVERIFIED"
    TEMPORAL_SPLIT_MISSING = "TEMPORAL_SPLIT_MISSING"
    TEMPORAL_POLICY_MISMATCH = "TEMPORAL_POLICY_MISMATCH"
    TEMPORAL_BOUNDARIES_INCOMPLETE = "TEMPORAL_BOUNDARIES_INCOMPLETE"
    POINT_IN_TIME_FEATURE_INVALID = "POINT_IN_TIME_FEATURE_INVALID"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    LABEL_POLICY_MISMATCH = "LABEL_POLICY_MISMATCH"
    ACCOUNT_CHURN_POLICY_UNRESOLVED = "ACCOUNT_CHURN_POLICY_UNRESOLVED"
    PENDING_OUTCOME = "PENDING_OUTCOME"
    INCOMPLETE_OUTCOME = "INCOMPLETE_OUTCOME"
    INELIGIBLE_OUTCOME = "INELIGIBLE_OUTCOME"
    UNSUPPORTED_OUTCOME = "UNSUPPORTED_OUTCOME"
    OUTCOME_AFTER_TRAINING_CUTOFF = "OUTCOME_AFTER_TRAINING_CUTOFF"
    OUTCOME_PROVENANCE_INSUFFICIENT = "OUTCOME_PROVENANCE_INSUFFICIENT"
    OUTCOME_COVERAGE_INSUFFICIENT = "OUTCOME_COVERAGE_INSUFFICIENT"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    SINGLE_CLASS = "SINGLE_CLASS"
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"
    DUPLICATE_SNAPSHOT = "DUPLICATE_SNAPSHOT"
    TEST_PARTITION_NOT_TRAINING_DATA = "TEST_PARTITION_NOT_TRAINING_DATA"
    SELECTION_COVERAGE_WARNING = "SELECTION_COVERAGE_WARNING"
    ABSTAINED_COVERAGE_WARNING = "ABSTAINED_COVERAGE_WARNING"
    INTERVENTION_SELECTION_WARNING = "INTERVENTION_SELECTION_WARNING"
    REPEATED_SNAPSHOT_WARNING = "REPEATED_SNAPSHOT_WARNING"
    NON_CAUSAL_OUTCOME_LIMITATION = "NON_CAUSAL_OUTCOME_LIMITATION"


class _ReadinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class RetrainingReadinessConfig:
    """Explicit thresholds and policy inputs; no universal thresholds are assumed."""

    training_freeze_cutoff: datetime
    readiness_policy_version: str = "retraining_readiness_v1"
    expected_feature_version: str | None = None
    expected_label_policy_version: str | None = None
    expected_split_policy_version: str | None = None
    account_churn_policy_version: str | None = None
    tenant_scope: str | None = None
    minimum_samples_per_horizon: int = 2
    minimum_positive_per_horizon: int = 1
    minimum_negative_per_horizon: int = 1
    required_horizons: tuple[int, ...] = SUPPORTED_HORIZONS
    selection_coverage_verified: bool = False
    require_complete_selection_coverage: bool = False

    def __post_init__(self) -> None:
        if not self.readiness_policy_version.strip():
            raise ValueError("readiness_policy_version must be non-empty")
        if self.training_freeze_cutoff is None or self.training_freeze_cutoff.tzinfo is None or self.training_freeze_cutoff.utcoffset() is None:
            raise ValueError("training_freeze_cutoff must be timezone-aware")
        if not self.required_horizons or set(self.required_horizons) != set(SUPPORTED_HORIZONS):
            raise ValueError("required_horizons must contain exactly 7, 14, and 30")
        if self.minimum_samples_per_horizon < 1:
            raise ValueError("minimum_samples_per_horizon must be positive")
        if self.minimum_positive_per_horizon < 1 or self.minimum_negative_per_horizon < 1:
            raise ValueError("class minimums must be positive")


class HorizonReadiness(_ReadinessModel):
    horizon_days: int
    status: HorizonReadinessStatus
    candidate_feedback_count: int = Field(ge=0)
    mature_feedback_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    incomplete_count: int = Field(ge=0)
    ineligible_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    eligible_feedback_ids: tuple[str, ...] = ()
    supervised_snapshot_ids: tuple[str, ...] = ()
    reason_codes: tuple[RetrainingReasonCode, ...] = ()


class RetrainingReadinessReport(_ReadinessModel):
    readiness_status: RetrainingReadinessStatus
    readiness_policy_version: str = Field(min_length=1)
    dataset_identifier: str | None = None
    dataset_status: DatasetStatus | None = None
    dataset_provenance: DatasetProvenance | None = None
    training_freeze_cutoff: AwareDatetime
    temporal_split_policy_version: str | None = None
    expected_feature_version: str | None = None
    expected_label_policy_version: str | None = None
    account_churn_policy_version: str | None = None
    horizon_readiness: tuple[HorizonReadiness, ...] = ()
    eligible_feedback_ids_by_horizon: dict[int, tuple[str, ...]] = Field(default_factory=dict)
    excluded_feedback_counts: dict[str, int] = Field(default_factory=dict)
    tenant_count: int = Field(ge=0)
    customer_count: int = Field(ge=0)
    repeated_account_snapshot_count: int = Field(ge=0)
    source_correction_count: int = Field(ge=0)
    selection_warnings: tuple[RetrainingReasonCode, ...] = ()
    blockers: tuple[RetrainingReasonCode, ...] = ()
    warnings: tuple[str, ...] = ()
    configuration: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


_T = TypeVar("_T")


def _unique(values: Iterable[_T]) -> tuple[_T, ...]:
    return tuple(dict.fromkeys(values))


def _append_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


class RetrainingReadinessAssessor:
    """Evaluate whether evidence is sufficient to propose candidate training."""

    def assess(
        self,
        feedback: Sequence[PredictionFeedback],
        *,
        dataset_readiness: DatasetReadinessReport | None,
        split_result: TemporalSplitResult | None,
        config: RetrainingReadinessConfig,
    ) -> RetrainingReadinessReport:
        blockers: list[RetrainingReasonCode] = []
        warnings: list[str] = []
        selection_warnings: list[RetrainingReasonCode] = []
        excluded_counts: dict[str, int] = {}

        dataset_status = dataset_readiness.status if dataset_readiness else None
        provenance = dataset_readiness.dataset_source if dataset_readiness else None
        if dataset_readiness is None:
            blockers.append(RetrainingReasonCode.DATASET_READINESS_MISSING)
        elif dataset_readiness.status is not DatasetStatus.PASS or not dataset_readiness.eligible_for_genuine_training:
            blockers.append(RetrainingReasonCode.DATASET_NOT_PASS)
        if provenance is None:
            blockers.append(RetrainingReasonCode.PROVENANCE_UNVERIFIED)
        elif provenance.evidence_type is ProvenanceEvidenceType.SYNTHETIC:
            blockers.append(RetrainingReasonCode.SYNTHETIC_ONLY)
        elif provenance.evidence_type is not ProvenanceEvidenceType.REAL_AUTHORIZED:
            blockers.append(RetrainingReasonCode.DATASET_NOT_AUTHORIZED)

        train_records: dict[str, Any] = {}
        split_policy_version: str | None = None
        if split_result is None:
            blockers.append(RetrainingReasonCode.TEMPORAL_SPLIT_MISSING)
        else:
            split_policy_version = split_result.manifest.split_policy_version
            if config.expected_split_policy_version and split_policy_version != config.expected_split_policy_version:
                blockers.append(RetrainingReasonCode.TEMPORAL_POLICY_MISMATCH)
            boundaries = split_result.manifest.boundaries
            if boundaries.train_end is None or boundaries.validation_end is None or boundaries.calibration_end is None:
                blockers.append(RetrainingReasonCode.TEMPORAL_BOUNDARIES_INCOMPLETE)
            train_records = {
                record.stable_snapshot_id: record
                for record in split_result.partition(SplitName.TRAIN).snapshots
            }

        if config.account_churn_policy_version is None:
            blockers.append(RetrainingReasonCode.ACCOUNT_CHURN_POLICY_UNRESOLVED)

        selected_by_key: dict[tuple[str, str, datetime, int], PredictionFeedback] = {}
        for item in feedback:
            if config.tenant_scope is not None and item.tenant_id != config.tenant_scope:
                _append_count(excluded_counts, RetrainingReasonCode.TENANT_SCOPE_MISMATCH.value)
                blockers.append(RetrainingReasonCode.TENANT_SCOPE_MISMATCH)
                continue
            if item.reconciliation_timestamp > config.training_freeze_cutoff or item.evaluation_as_of > config.training_freeze_cutoff:
                _append_count(excluded_counts, RetrainingReasonCode.OUTCOME_AFTER_TRAINING_CUTOFF.value)
                continue
            key = (item.tenant_id, item.customer_id, item.prediction_as_of, item.horizon_days)
            previous = selected_by_key.get(key)
            if previous is not None:
                _append_count(excluded_counts, RetrainingReasonCode.DUPLICATE_SNAPSHOT.value)
                if item.revision_number > previous.revision_number:
                    selected_by_key[key] = item
                continue
            selected_by_key[key] = item

        horizon_reports: list[HorizonReadiness] = []
        eligible_by_horizon: dict[int, tuple[str, ...]] = {}
        all_tenants: set[str] = set()
        all_customers: set[tuple[str, str]] = set()
        selected_snapshot_accounts: dict[tuple[str, str], int] = {}

        for horizon in SUPPORTED_HORIZONS:
            candidates = [item for item in selected_by_key.values() if item.horizon_days == horizon]
            pending_count = sum(item.feedback_status is FeedbackStatus.PENDING for item in candidates)
            incomplete_count = sum(item.feedback_status is FeedbackStatus.INCOMPLETE for item in candidates)
            ineligible_count = sum(item.feedback_status is FeedbackStatus.INELIGIBLE for item in candidates)
            excluded_count = pending_count + incomplete_count + ineligible_count
            mature = [
                item
                for item in candidates
                if item.feedback_status in {FeedbackStatus.MATURE_POSITIVE, FeedbackStatus.MATURE_NEGATIVE}
            ]
            positive_count = sum(item.feedback_status is FeedbackStatus.MATURE_POSITIVE for item in mature)
            negative_count = sum(item.feedback_status is FeedbackStatus.MATURE_NEGATIVE for item in mature)
            horizon_reasons: list[RetrainingReasonCode] = []
            usable: list[PredictionFeedback] = []
            supervised_ids: list[str] = []

            for item in candidates:
                if item.feedback_status is FeedbackStatus.PENDING:
                    horizon_reasons.append(RetrainingReasonCode.PENDING_OUTCOME)
                elif item.feedback_status is FeedbackStatus.INCOMPLETE:
                    horizon_reasons.append(RetrainingReasonCode.INCOMPLETE_OUTCOME)
                elif item.feedback_status is FeedbackStatus.INELIGIBLE:
                    horizon_reasons.append(RetrainingReasonCode.INELIGIBLE_OUTCOME)
                if item.churn_label.label_status.value == "unsupported":
                    horizon_reasons.append(RetrainingReasonCode.UNSUPPORTED_OUTCOME)
                eligibility = assess_learning_eligibility(
                    item,
                    training_cutoff=config.training_freeze_cutoff,
                    expected_label_policy_version=config.expected_label_policy_version,
                )
                if not eligibility.admissible:
                    for reason in eligibility.reason_codes:
                        if reason in {
                            OutcomeReasonCode.LEARNING_POLICY_MISMATCH,
                            OutcomeReasonCode.LEARNING_OUTCOME_RECORDED_AFTER_CUTOFF,
                        }:
                            horizon_reasons.append(RetrainingReasonCode.LABEL_POLICY_MISMATCH)
                        elif reason in {
                            OutcomeReasonCode.LEARNING_PROVENANCE_INSUFFICIENT,
                            OutcomeReasonCode.SYNTHETIC_FEEDBACK_NOT_AUTHORIZED_FOR_LEARNING,
                        }:
                            horizon_reasons.append(RetrainingReasonCode.OUTCOME_PROVENANCE_INSUFFICIENT)
                        elif reason is OutcomeReasonCode.LEARNING_UNRESOLVED_POLICY:
                            horizon_reasons.append(RetrainingReasonCode.ACCOUNT_CHURN_POLICY_UNRESOLVED)
                        elif reason is OutcomeReasonCode.LEARNING_COVERAGE_INSUFFICIENT:
                            horizon_reasons.append(RetrainingReasonCode.OUTCOME_COVERAGE_INSUFFICIENT)
                    continue
                if split_result is None:
                    continue
                matching = [
                    (snapshot_id, record)
                    for snapshot_id, record in train_records.items()
                    if record.feature_snapshot.tenant_id == item.tenant_id
                    and record.feature_snapshot.customer_id == item.customer_id
                    and record.feature_snapshot.as_of == item.prediction_as_of
                ]
                if not matching:
                    horizon_reasons.append(RetrainingReasonCode.TEST_PARTITION_NOT_TRAINING_DATA)
                    continue
                snapshot_id, record = matching[0]
                if config.expected_feature_version and record.feature_snapshot.feature_version != config.expected_feature_version:
                    horizon_reasons.append(RetrainingReasonCode.FEATURE_VERSION_MISMATCH)
                    continue
                if record.feature_snapshot.data_cutoff_at > record.feature_snapshot.as_of:
                    horizon_reasons.append(RetrainingReasonCode.POINT_IN_TIME_FEATURE_INVALID)
                    continue
                if snapshot_id not in split_result.supervised_snapshot_ids(SplitName.TRAIN, horizon):
                    horizon_reasons.append(RetrainingReasonCode.OUTCOME_AFTER_TRAINING_CUTOFF)
                    continue
                usable.append(item)
                supervised_ids.append(snapshot_id)

            if len(usable) < config.minimum_samples_per_horizon:
                horizon_reasons.append(RetrainingReasonCode.INSUFFICIENT_SAMPLES)
            if len(usable) and len({item.label for item in usable}) < 2:
                horizon_reasons.append(RetrainingReasonCode.SINGLE_CLASS)
            if sum(item.label == 1 for item in usable) < config.minimum_positive_per_horizon:
                horizon_reasons.append(RetrainingReasonCode.INSUFFICIENT_SAMPLES)
            if sum(item.label == 0 for item in usable) < config.minimum_negative_per_horizon:
                horizon_reasons.append(RetrainingReasonCode.INSUFFICIENT_SAMPLES)

            for item in usable:
                all_tenants.add(item.tenant_id)
                all_customers.add((item.tenant_id, item.customer_id))
                selected_snapshot_accounts[(item.tenant_id, item.customer_id)] = selected_snapshot_accounts.get((item.tenant_id, item.customer_id), 0) + 1
            eligible_ids = tuple(item.feedback_id for item in usable)
            eligible_by_horizon[horizon] = eligible_ids
            clean_reasons = _unique(horizon_reasons)
            status = HorizonReadinessStatus.READY if not clean_reasons else HorizonReadinessStatus.NOT_READY
            if any(reason in blockers for reason in {
                RetrainingReasonCode.DATASET_READINESS_MISSING,
                RetrainingReasonCode.DATASET_NOT_PASS,
                RetrainingReasonCode.DATASET_NOT_AUTHORIZED,
                RetrainingReasonCode.SYNTHETIC_ONLY,
                RetrainingReasonCode.PROVENANCE_UNVERIFIED,
                RetrainingReasonCode.TEMPORAL_SPLIT_MISSING,
            }):
                status = HorizonReadinessStatus.BLOCKED
            horizon_reports.append(
                HorizonReadiness(
                    horizon_days=horizon,
                    status=status,
                    candidate_feedback_count=len(candidates),
                    mature_feedback_count=len(mature),
                    positive_count=positive_count,
                    negative_count=negative_count,
                    pending_count=pending_count,
                    incomplete_count=incomplete_count,
                    ineligible_count=ineligible_count,
                    excluded_count=excluded_count,
                    eligible_feedback_ids=eligible_ids,
                    supervised_snapshot_ids=tuple(supervised_ids),
                    reason_codes=clean_reasons,
                )
            )

        repeated_accounts = sum(count > 1 for count in selected_snapshot_accounts.values())
        if repeated_accounts:
            selection_warnings.append(RetrainingReasonCode.REPEATED_SNAPSHOT_WARNING)
            warnings.append("Repeated historical snapshots are retained as time-forward observations; unseen-account generalization is not established.")
        if not config.selection_coverage_verified:
            selection_warnings.append(RetrainingReasonCode.SELECTION_COVERAGE_WARNING)
            warnings.append("Feedback-linked records do not prove complete population coverage or absence of selection bias.")
        if config.require_complete_selection_coverage and not config.selection_coverage_verified:
            blockers.append(RetrainingReasonCode.SELECTION_COVERAGE_WARNING)
        abstained = sum(item.prediction_snapshot.status is PredictionStatus.ABSTAINED for item in selected_by_key.values())
        if abstained or not any(item.prediction_snapshot.status is PredictionStatus.ABSTAINED for item in selected_by_key.values()):
            selection_warnings.append(RetrainingReasonCode.ABSTAINED_COVERAGE_WARNING)
            warnings.append("Scored versus abstained representation must be verified against the complete eligible population.")
        known_intervention = sum(
            item.outcome_coverage.intervention_exposure.value == "known"
            for item in selected_by_key.values()
        )
        if known_intervention:
            selection_warnings.extend((RetrainingReasonCode.INTERVENTION_SELECTION_WARNING, RetrainingReasonCode.NON_CAUSAL_OUTCOME_LIMITATION))
            warnings.append("Intervention-exposed outcomes reflect the observed operating policy and are not causal treatment-effect labels.")

        if any(
            item.outcome_coverage.unresolved_multi_subscription_policy
            or LabelReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY in item.churn_label.reason_codes
            for item in selected_by_key.values()
        ):
            blockers.append(RetrainingReasonCode.ACCOUNT_CHURN_POLICY_UNRESOLVED)

        blockers = list(_unique(blockers))
        horizon_not_ready = any(item.status is not HorizonReadinessStatus.READY for item in horizon_reports)
        if any(reason in blockers for reason in {
            RetrainingReasonCode.DATASET_READINESS_MISSING,
            RetrainingReasonCode.DATASET_NOT_PASS,
            RetrainingReasonCode.DATASET_NOT_AUTHORIZED,
            RetrainingReasonCode.SYNTHETIC_ONLY,
            RetrainingReasonCode.PROVENANCE_UNVERIFIED,
            RetrainingReasonCode.TEMPORAL_SPLIT_MISSING,
        }):
            overall = RetrainingReadinessStatus.BLOCKED
        elif blockers or horizon_not_ready:
            overall = RetrainingReadinessStatus.NOT_READY
        else:
            overall = RetrainingReadinessStatus.READY_FOR_CANDIDATE_TRAINING

        return RetrainingReadinessReport(
            readiness_status=overall,
            readiness_policy_version=config.readiness_policy_version,
            dataset_identifier=(
                split_result.manifest.dataset_identifier if split_result is not None else None
            ),
            dataset_status=dataset_status,
            dataset_provenance=provenance,
            training_freeze_cutoff=config.training_freeze_cutoff,
            temporal_split_policy_version=split_policy_version,
            expected_feature_version=config.expected_feature_version,
            expected_label_policy_version=config.expected_label_policy_version,
            account_churn_policy_version=config.account_churn_policy_version,
            horizon_readiness=tuple(horizon_reports),
            eligible_feedback_ids_by_horizon=eligible_by_horizon,
            excluded_feedback_counts=excluded_counts,
            tenant_count=len(all_tenants),
            customer_count=len(all_customers),
            repeated_account_snapshot_count=repeated_accounts,
            source_correction_count=sum(item.supersedes_feedback_id is not None for item in feedback),
            selection_warnings=_unique(selection_warnings),
            blockers=tuple(blockers),
            warnings=tuple(_unique(warnings)),
            configuration={
                "minimum_samples_per_horizon": config.minimum_samples_per_horizon,
                "minimum_positive_per_horizon": config.minimum_positive_per_horizon,
                "minimum_negative_per_horizon": config.minimum_negative_per_horizon,
                "required_horizons": list(config.required_horizons),
                "selection_coverage_verified": config.selection_coverage_verified,
                "require_complete_selection_coverage": config.require_complete_selection_coverage,
                "model_training_allowed": overall is RetrainingReadinessStatus.READY_FOR_CANDIDATE_TRAINING,
                "automatic_training_triggered": False,
                "automatic_promotion_triggered": False,
            },
        )


def assess_retraining_readiness(
    feedback: Sequence[PredictionFeedback],
    *,
    dataset_readiness: DatasetReadinessReport | None,
    split_result: TemporalSplitResult | None,
    config: RetrainingReadinessConfig,
) -> RetrainingReadinessReport:
    return RetrainingReadinessAssessor().assess(
        feedback,
        dataset_readiness=dataset_readiness,
        split_result=split_result,
        config=config,
    )


__all__ = [
    "HorizonReadiness",
    "HorizonReadinessStatus",
    "RetrainingReasonCode",
    "RetrainingReadinessAssessor",
    "RetrainingReadinessConfig",
    "RetrainingReadinessReport",
    "RetrainingReadinessStatus",
    "assess_retraining_readiness",
]
