"""Gated candidate-versus-champion evaluation over a sealed TEST partition.

The evaluator delegates metric calculation to :mod:`historical_evaluation`.
This module adds candidate identity, freeze, provenance, cohort and release
governance.  It never promotes a bundle or mutates the active champion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Literal, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .contracts import PredictionOutput
from .historical_evaluation import (
    DatasetProvenanceStatus,
    EvaluationPrediction,
    EvaluationStatus,
    HistoricalEvaluationConfig,
    HistoricalEvaluationReport,
    HistoricalEvaluator,
    HorizonMetrics,
)
from .label_builder import ChurnLabel, SUPPORTED_HORIZONS
from .model_registry import (
    ModelBundleMetadata,
    ModelLifecycleStatus,
    ModelRegistry,
)
from .temporal_splits import SplitName, TemporalSplitResult


class CandidateEvaluationGateStatus(str, Enum):
    BLOCKED = "BLOCKED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EVALUATED_NOT_APPROVABLE = "EVALUATED_NOT_APPROVABLE"
    ELIGIBLE_FOR_HUMAN_REVIEW = "ELIGIBLE_FOR_HUMAN_REVIEW"


class CandidateHorizonEvaluationStatus(str, Enum):
    READY = "READY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"


class CandidateEvaluationReasonCode(str, Enum):
    CANDIDATE_NOT_FROZEN = "CANDIDATE_NOT_FROZEN"
    CANDIDATE_CHANGED_AFTER_FREEZE = "CANDIDATE_CHANGED_AFTER_FREEZE"
    EVALUATION_CONFIGURATION_CHANGED = "EVALUATION_CONFIGURATION_CHANGED"
    TEST_AUTHORIZATION_REQUIRED = "TEST_AUTHORIZATION_REQUIRED"
    TEST_NOT_UNTOUCHED = "TEST_NOT_UNTOUCHED"
    TEST_SELECTION_NOT_FROZEN = "TEST_SELECTION_NOT_FROZEN"
    TEST_REUSE_FOR_SELECTION = "TEST_REUSE_FOR_SELECTION"
    TEST_ALREADY_CONSUMED = "TEST_ALREADY_CONSUMED"
    TEST_PARTITION_REQUIRED = "TEST_PARTITION_REQUIRED"
    DATASET_PROVENANCE_BLOCKED = "DATASET_PROVENANCE_BLOCKED"
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    CHAMPION_MISSING = "CHAMPION_MISSING"
    CHAMPION_PREDICTIONS_MISSING = "CHAMPION_PREDICTIONS_MISSING"
    COHORT_MISMATCH = "COHORT_MISMATCH"
    METRIC_UNDEFINED = "METRIC_UNDEFINED"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    MODEL_VERSION_MISMATCH = "MODEL_VERSION_MISMATCH"
    CALIBRATION_VERSION_MISMATCH = "CALIBRATION_VERSION_MISMATCH"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    LABEL_POLICY_VERSION_MISMATCH = "LABEL_POLICY_VERSION_MISMATCH"
    INVALID_CANDIDATE_LIFECYCLE = "INVALID_CANDIDATE_LIFECYCLE"


class _EvaluationGateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class CandidateEvaluationConfig:
    """Versioned, immutable policy for one final TEST evaluation."""

    evaluation_policy_version: str
    evaluation_cutoff: datetime
    split_policy_version: str
    test_authorization_reference: str
    review_capacity_k: int = 10
    dataset_provenance_status: DatasetProvenanceStatus = DatasetProvenanceStatus.UNVERIFIED
    expected_feature_version: str | None = None
    expected_label_policy_version: str | None = None
    minimum_mature_samples_per_horizon: int = 2
    required_metric_names: tuple[str, ...] = ("pr_auc", "brier_score", "recall_at_k")
    require_champion_comparison: bool = True
    require_same_cohort: bool = True
    test_selection_frozen: bool = True
    test_set_untouched: bool = True

    def __post_init__(self) -> None:
        if not self.evaluation_policy_version.strip():
            raise ValueError("evaluation_policy_version must be non-empty")
        if not self.split_policy_version.strip():
            raise ValueError("split_policy_version must be non-empty")
        if not self.test_authorization_reference.strip():
            raise ValueError("test_authorization_reference must be non-empty")
        if self.evaluation_cutoff.tzinfo is None or self.evaluation_cutoff.utcoffset() is None:
            raise ValueError("evaluation_cutoff must be timezone-aware")
        if self.review_capacity_k < 1 or self.minimum_mature_samples_per_horizon < 1:
            raise ValueError("review capacity and sample minimum must be positive")

    def fingerprint(self) -> str:
        payload = {
            "evaluation_policy_version": self.evaluation_policy_version,
            "evaluation_cutoff": self.evaluation_cutoff.isoformat(),
            "split_policy_version": self.split_policy_version,
            "test_authorization_reference": self.test_authorization_reference,
            "review_capacity_k": self.review_capacity_k,
            "dataset_provenance_status": self.dataset_provenance_status.value,
            "expected_feature_version": self.expected_feature_version,
            "expected_label_policy_version": self.expected_label_policy_version,
            "minimum_mature_samples_per_horizon": self.minimum_mature_samples_per_horizon,
            "required_metric_names": self.required_metric_names,
            "require_champion_comparison": self.require_champion_comparison,
            "require_same_cohort": self.require_same_cohort,
            "test_selection_frozen": self.test_selection_frozen,
            "test_set_untouched": self.test_set_untouched,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class FrozenTestEvaluationManifest(_EvaluationGateModel):
    manifest_id: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    candidate_metadata_fingerprint: str = Field(min_length=64, max_length=64)
    model_version_references: tuple[str, ...]
    calibration_version_references: tuple[str, ...]
    feature_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    dataset_provenance_reference: str = Field(min_length=1)
    temporal_split_policy_version: str = Field(min_length=1)
    training_freeze_cutoff: AwareDatetime
    evaluation_policy_version: str = Field(min_length=1)
    evaluation_configuration_fingerprint: str = Field(min_length=64, max_length=64)
    test_authorization_reference: str = Field(min_length=1)
    test_usage_status: Literal["SEALED"] = "SEALED"
    frozen_at: AwareDatetime


class CandidateEvaluationReport(_EvaluationGateModel):
    gate_status: CandidateEvaluationGateStatus
    candidate_bundle_id: str = Field(min_length=1)
    champion_bundle_id: str | None = None
    evaluation_run_id: str = Field(min_length=1)
    evaluation_status: EvaluationStatus | None = None
    dataset_provenance_status: DatasetProvenanceStatus
    synthetic_test_only: bool
    split_policy_version: str
    evaluation_cutoff: AwareDatetime
    test_manifest: FrozenTestEvaluationManifest | None = None
    test_accessed: bool = False
    horizon_status: dict[int, CandidateHorizonEvaluationStatus] = Field(default_factory=dict)
    coverage_by_horizon: dict[int, float | None] = Field(default_factory=dict)
    abstention_by_horizon: dict[int, float | None] = Field(default_factory=dict)
    historical_report: HistoricalEvaluationReport | None = None
    reason_codes: tuple[CandidateEvaluationReasonCode, ...] = ()
    warnings: tuple[str, ...] = ()
    configuration: dict[str, Any] = Field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint_metadata(metadata: ModelBundleMetadata) -> str:
    payload = metadata.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _unique(values: Sequence[CandidateEvaluationReasonCode]) -> tuple[CandidateEvaluationReasonCode, ...]:
    return tuple(dict.fromkeys(values))


def _blocked_report(
    candidate: ModelBundleMetadata,
    config: CandidateEvaluationConfig,
    *,
    reasons: Sequence[CandidateEvaluationReasonCode],
    evaluation_run_id: str,
    manifest: FrozenTestEvaluationManifest | None = None,
    test_accessed: bool = False,
    historical_report: HistoricalEvaluationReport | None = None,
    warnings: Sequence[str] = (),
) -> CandidateEvaluationReport:
    return CandidateEvaluationReport(
        gate_status=CandidateEvaluationGateStatus.BLOCKED,
        candidate_bundle_id=candidate.bundle_id,
        evaluation_run_id=evaluation_run_id,
        evaluation_status=(historical_report.evaluation_status if historical_report else None),
        dataset_provenance_status=config.dataset_provenance_status,
        synthetic_test_only=config.dataset_provenance_status is DatasetProvenanceStatus.SYNTHETIC,
        split_policy_version=config.split_policy_version,
        evaluation_cutoff=config.evaluation_cutoff,
        test_manifest=manifest,
        test_accessed=test_accessed,
        historical_report=historical_report,
        reason_codes=_unique(tuple(reasons)),
        warnings=tuple(warnings),
        configuration={
            "evaluation_policy_version": config.evaluation_policy_version,
            "review_capacity_k": config.review_capacity_k,
            "test_selection_frozen": config.test_selection_frozen,
            "test_set_untouched": config.test_set_untouched,
        },
    )


def _normalise_predictions(
    predictions: Sequence[PredictionOutput | EvaluationPrediction],
    *,
    model_name: str,
) -> tuple[EvaluationPrediction, ...]:
    normalised: list[EvaluationPrediction] = []
    for item in predictions:
        if isinstance(item, PredictionOutput):
            normalised.extend(
                EvaluationPrediction.from_prediction_output(item, model_name=model_name)
            )
        elif isinstance(item, EvaluationPrediction):
            normalised.append(item.model_copy(update={"model_name": model_name}))
        else:
            raise TypeError("predictions must be PredictionOutput or EvaluationPrediction")
    return tuple(normalised)


def _validate_prediction_versions(
    predictions: Sequence[EvaluationPrediction],
    metadata: ModelBundleMetadata,
) -> tuple[CandidateEvaluationReasonCode, ...]:
    model_versions = {item.horizon_days: item.version for item in metadata.model_versions}
    calibration_versions = {item.horizon_days: item.version for item in metadata.calibration_versions}
    reasons: list[CandidateEvaluationReasonCode] = []
    for prediction in predictions:
        if prediction.model_version != model_versions.get(prediction.horizon_days):
            reasons.append(CandidateEvaluationReasonCode.MODEL_VERSION_MISMATCH)
        if prediction.calibration_version != calibration_versions.get(prediction.horizon_days):
            reasons.append(CandidateEvaluationReasonCode.CALIBRATION_VERSION_MISMATCH)
        if prediction.feature_version != metadata.feature_version:
            reasons.append(CandidateEvaluationReasonCode.FEATURE_VERSION_MISMATCH)
        if prediction.label_policy_version != metadata.label_policy_version:
            reasons.append(CandidateEvaluationReasonCode.LABEL_POLICY_VERSION_MISMATCH)
    return _unique(reasons)


def _metric_for(
    report: HistoricalEvaluationReport,
    model_name: str,
    horizon: int,
) -> HorizonMetrics | None:
    return next(
        (
            metric
            for metric in report.horizon_metrics
            if metric.model_name == model_name and metric.horizon_days == horizon
        ),
        None,
    )


class CandidateEvaluationGate:
    """Freeze candidates and permit at most one final TEST evaluation."""

    def __init__(self, *, clock: Callable[[], datetime] = _now) -> None:
        self._clock = clock
        self._manifest: FrozenTestEvaluationManifest | None = None
        self._test_consumed = False

    @property
    def manifest(self) -> FrozenTestEvaluationManifest | None:
        return self._manifest

    def freeze_candidate(
        self,
        candidate: ModelBundleMetadata,
        *,
        config: CandidateEvaluationConfig,
    ) -> FrozenTestEvaluationManifest:
        if candidate.status is not ModelLifecycleStatus.TRAINED_PENDING_EVALUATION:
            raise ValueError(CandidateEvaluationReasonCode.INVALID_CANDIDATE_LIFECYCLE.value)
        if not config.test_authorization_reference.strip():
            raise ValueError(CandidateEvaluationReasonCode.TEST_AUTHORIZATION_REQUIRED.value)
        if not config.test_selection_frozen:
            raise ValueError(CandidateEvaluationReasonCode.TEST_SELECTION_NOT_FROZEN.value)
        if not config.test_set_untouched:
            raise ValueError(CandidateEvaluationReasonCode.TEST_NOT_UNTOUCHED.value)
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("evaluation clock must return a timezone-aware timestamp")
        metadata_fingerprint = _fingerprint_metadata(candidate)
        config_fingerprint = config.fingerprint()
        if self._manifest is not None:
            if (
                self._manifest.candidate_metadata_fingerprint != metadata_fingerprint
                or self._manifest.evaluation_configuration_fingerprint != config_fingerprint
            ):
                raise ValueError(CandidateEvaluationReasonCode.CANDIDATE_CHANGED_AFTER_FREEZE.value)
            return self._manifest
        manifest_id = hashlib.sha256(
            f"{candidate.bundle_id}:{metadata_fingerprint}:{config_fingerprint}".encode()
        ).hexdigest()
        model_versions = tuple(
            item.version for item in sorted(candidate.model_versions, key=lambda item: item.horizon_days)
        )
        calibration_versions = tuple(
            item.version for item in sorted(candidate.calibration_versions, key=lambda item: item.horizon_days)
        )
        self._manifest = FrozenTestEvaluationManifest(
            manifest_id=manifest_id,
            candidate_bundle_id=candidate.bundle_id,
            candidate_id=candidate.candidate_id,
            candidate_metadata_fingerprint=metadata_fingerprint,
            model_version_references=model_versions,
            calibration_version_references=calibration_versions,
            feature_version=candidate.feature_version,
            label_policy_version=candidate.label_policy_version,
            dataset_provenance_reference=candidate.dataset_provenance_reference,
            temporal_split_policy_version=candidate.temporal_split_policy_version,
            training_freeze_cutoff=candidate.training_freeze_cutoff,
            evaluation_policy_version=config.evaluation_policy_version,
            evaluation_configuration_fingerprint=config_fingerprint,
            test_authorization_reference=config.test_authorization_reference,
            frozen_at=now,
        )
        return self._manifest

    def evaluate_final_test(
        self,
        candidate: ModelBundleMetadata,
        predictions: Sequence[PredictionOutput | EvaluationPrediction],
        labels: Sequence[ChurnLabel],
        split_result: TemporalSplitResult,
        *,
        config: CandidateEvaluationConfig,
        evaluation_run_id: str,
        champion: ModelBundleMetadata | None = None,
        champion_predictions: Sequence[PredictionOutput | EvaluationPrediction] = (),
        purpose: str = "independent_final_evaluation",
    ) -> CandidateEvaluationReport:
        manifest = self._manifest
        if manifest is None:
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.CANDIDATE_NOT_FROZEN,),
                evaluation_run_id=evaluation_run_id,
            )
        if self._test_consumed:
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.TEST_ALREADY_CONSUMED,),
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )
        if purpose != "independent_final_evaluation":
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.TEST_REUSE_FOR_SELECTION,),
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )
        if _fingerprint_metadata(candidate) != manifest.candidate_metadata_fingerprint:
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.CANDIDATE_CHANGED_AFTER_FREEZE,),
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )
        if config.fingerprint() != manifest.evaluation_configuration_fingerprint:
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.EVALUATION_CONFIGURATION_CHANGED,),
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )
        if not config.test_selection_frozen:
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.TEST_SELECTION_NOT_FROZEN,),
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )
        if not config.test_set_untouched:
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.TEST_NOT_UNTOUCHED,),
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )
        if split_result.manifest.split_policy_version != config.split_policy_version:
            return _blocked_report(
                candidate,
                config,
                reasons=(CandidateEvaluationReasonCode.EVALUATION_CONFIGURATION_CHANGED,),
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )
        candidate_predictions = _normalise_predictions(
            predictions, model_name="candidate"
        )
        version_reasons = list(_validate_prediction_versions(candidate_predictions, candidate))
        comparison_reasons: list[CandidateEvaluationReasonCode] = []
        all_predictions = list(candidate_predictions)
        champion_bundle_id = champion.bundle_id if champion else None
        if champion is not None:
            if not champion_predictions:
                comparison_reasons.append(CandidateEvaluationReasonCode.CHAMPION_PREDICTIONS_MISSING)
            else:
                normalised_champion = _normalise_predictions(
                    champion_predictions, model_name="champion"
                )
                all_predictions.extend(normalised_champion)
                version_reasons.extend(
                    _validate_prediction_versions(normalised_champion, champion)
                )
        elif config.require_champion_comparison:
            comparison_reasons.append(CandidateEvaluationReasonCode.CHAMPION_MISSING)
        if version_reasons:
            return _blocked_report(
                candidate,
                config,
                reasons=version_reasons,
                evaluation_run_id=evaluation_run_id,
                manifest=manifest,
            )

        self._test_consumed = True
        evaluation_config = HistoricalEvaluationConfig(
            evaluation_cutoff=config.evaluation_cutoff,
            dataset_provenance_status=config.dataset_provenance_status,
            partition=SplitName.TEST,
            cohort="candidate_final_test",
            review_capacity_k=config.review_capacity_k,
            expected_feature_version=config.expected_feature_version or candidate.feature_version,
            expected_label_policy_version=config.expected_label_policy_version or candidate.label_policy_version,
            split_policy_version=config.split_policy_version,
            test_selection_frozen=config.test_selection_frozen,
        )
        historical_report = HistoricalEvaluator().evaluate(
            all_predictions,
            labels,
            split_result,
            config=evaluation_config,
        )
        reasons: list[CandidateEvaluationReasonCode] = list(comparison_reasons)
        if historical_report.evaluation_status is EvaluationStatus.BLOCKED:
            reasons.append(CandidateEvaluationReasonCode.DATASET_PROVENANCE_BLOCKED)
        if historical_report.evaluation_status is EvaluationStatus.SYNTHETIC_ONLY:
            reasons.append(CandidateEvaluationReasonCode.SYNTHETIC_ONLY)

        horizon_status: dict[int, CandidateHorizonEvaluationStatus] = {}
        coverage: dict[int, float | None] = {}
        abstention: dict[int, float | None] = {}
        for horizon in SUPPORTED_HORIZONS:
            metric = _metric_for(historical_report, "candidate", horizon)
            if metric is None:
                horizon_status[horizon] = CandidateHorizonEvaluationStatus.BLOCKED
                reasons.append(CandidateEvaluationReasonCode.INSUFFICIENT_SAMPLES)
                continue
            coverage[horizon] = metric.evaluation_population_coverage
            abstention[horizon] = metric.abstention_rate
            if metric.mature_labeled_population_count < config.minimum_mature_samples_per_horizon:
                horizon_status[horizon] = CandidateHorizonEvaluationStatus.INSUFFICIENT_EVIDENCE
                reasons.append(CandidateEvaluationReasonCode.INSUFFICIENT_SAMPLES)
                continue
            unavailable = [
                name
                for name in config.required_metric_names
                if getattr(metric, name).value is None
            ]
            if unavailable:
                horizon_status[horizon] = CandidateHorizonEvaluationStatus.INSUFFICIENT_EVIDENCE
                reasons.append(CandidateEvaluationReasonCode.METRIC_UNDEFINED)
            else:
                horizon_status[horizon] = CandidateHorizonEvaluationStatus.READY

        comparisons = {
            item.horizon_days: item
            for item in historical_report.model_comparisons
            if item.model_name == "candidate"
        }
        if champion is not None and config.require_same_cohort:
            if any(not item.same_mature_cohort_as_peers for item in comparisons.values()):
                reasons.append(CandidateEvaluationReasonCode.COHORT_MISMATCH)

        unique_reasons = _unique(reasons)
        hard_block = historical_report.evaluation_status is EvaluationStatus.BLOCKED
        insufficient = any(
            reason
            in {
                CandidateEvaluationReasonCode.INSUFFICIENT_SAMPLES,
                CandidateEvaluationReasonCode.METRIC_UNDEFINED,
            }
            for reason in unique_reasons
        )
        not_approvable = any(
            reason
            in {
                CandidateEvaluationReasonCode.SYNTHETIC_ONLY,
                CandidateEvaluationReasonCode.CHAMPION_MISSING,
                CandidateEvaluationReasonCode.CHAMPION_PREDICTIONS_MISSING,
                CandidateEvaluationReasonCode.COHORT_MISMATCH,
            }
            for reason in unique_reasons
        )
        if hard_block:
            gate_status = CandidateEvaluationGateStatus.BLOCKED
        elif insufficient:
            gate_status = CandidateEvaluationGateStatus.INSUFFICIENT_EVIDENCE
        elif not_approvable:
            gate_status = CandidateEvaluationGateStatus.EVALUATED_NOT_APPROVABLE
        else:
            gate_status = CandidateEvaluationGateStatus.ELIGIBLE_FOR_HUMAN_REVIEW
        return CandidateEvaluationReport(
            gate_status=gate_status,
            candidate_bundle_id=candidate.bundle_id,
            champion_bundle_id=champion_bundle_id,
            evaluation_run_id=evaluation_run_id,
            evaluation_status=historical_report.evaluation_status,
            dataset_provenance_status=config.dataset_provenance_status,
            synthetic_test_only=config.dataset_provenance_status is DatasetProvenanceStatus.SYNTHETIC,
            split_policy_version=config.split_policy_version,
            evaluation_cutoff=config.evaluation_cutoff,
            test_manifest=manifest,
            test_accessed=True,
            horizon_status=horizon_status,
            coverage_by_horizon=coverage,
            abstention_by_horizon=abstention,
            historical_report=historical_report,
            reason_codes=unique_reasons,
            warnings=tuple(historical_report.warnings),
            configuration={
                "evaluation_policy_version": config.evaluation_policy_version,
                "review_capacity_k": config.review_capacity_k,
                "model_selection_used_test": False,
                "candidate_model_name": "candidate",
                "champion_model_name": "champion" if champion else None,
            },
        )


def record_candidate_evaluation(
    registry: ModelRegistry,
    candidate_id: str,
    report: CandidateEvaluationReport,
    *,
    evidence_note: str,
) -> ModelBundleMetadata:
    """Record a completed evaluation without approving or promoting it."""

    if report.gate_status in {
        CandidateEvaluationGateStatus.BLOCKED,
        CandidateEvaluationGateStatus.INSUFFICIENT_EVIDENCE,
    }:
        raise ValueError(CandidateEvaluationReasonCode.INVALID_CANDIDATE_LIFECYCLE.value)
    return registry.transition_candidate(
        candidate_id,
        ModelLifecycleStatus.EVALUATED_PENDING_APPROVAL,
        evidence_note=evidence_note,
    )


__all__ = [
    "CandidateEvaluationConfig",
    "CandidateEvaluationGate",
    "CandidateEvaluationGateStatus",
    "CandidateEvaluationReasonCode",
    "CandidateEvaluationReport",
    "CandidateHorizonEvaluationStatus",
    "FrozenTestEvaluationManifest",
    "record_candidate_evaluation",
]
