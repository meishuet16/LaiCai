"""Controlled candidate-training orchestration for future retraining runs.

This module coordinates the existing LightGBM and calibration components.  It
does not replace the active prediction bundle, promote a candidate, schedule a
run, or claim production readiness from synthetic data.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Literal

from .calibration import (
    CalibrationConfig,
    CalibrationFitResult,
    ProbabilityCalibrator,
)
from .dataset_readiness import (
    DatasetProvenance,
    DatasetReadinessReport,
    DatasetStatus,
    ProvenanceEvidenceType,
)
from .label_builder import LabelStatus, SUPPORTED_HORIZONS
from .lightgbm_model import (
    LightGBMConfig,
    LightGBMFitResult,
    LightGBMModel,
)
from .model_registry import (
    ModelBundleMetadata,
    ModelLifecycleStatus,
    ModelRegistry,
    RegistryProvenanceStatus,
)
from .retraining_readiness import (
    RetrainingReadinessReport,
    RetrainingReadinessStatus,
)
from .temporal_splits import SnapshotRecord, SplitName, TemporalSplitResult


HorizonDays = Literal[7, 14, 30]


class CandidateTrainingMode(str, Enum):
    REAL_CANDIDATE = "real_candidate"
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"


class CandidateTrainingStatus(str, Enum):
    TRAINED = "TRAINED"
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"


class CandidateTrainingReasonCode(str, Enum):
    DATASET_READINESS_REQUIRED = "DATASET_READINESS_REQUIRED"
    DATASET_NOT_PASS = "DATASET_NOT_PASS"
    DATASET_NOT_AUTHORIZED = "DATASET_NOT_AUTHORIZED"
    SYNTHETIC_PROVENANCE_REQUIRED = "SYNTHETIC_PROVENANCE_REQUIRED"
    SYNTHETIC_NOT_PRODUCTION_ELIGIBLE = "SYNTHETIC_NOT_PRODUCTION_ELIGIBLE"
    RETRAINING_READINESS_REQUIRED = "RETRAINING_READINESS_REQUIRED"
    RETRAINING_READINESS_NOT_READY = "RETRAINING_READINESS_NOT_READY"
    TRAINING_FREEZE_MISMATCH = "TRAINING_FREEZE_MISMATCH"
    DATASET_REFERENCE_MISMATCH = "DATASET_REFERENCE_MISMATCH"
    SPLIT_POLICY_MISMATCH = "SPLIT_POLICY_MISMATCH"
    POINT_IN_TIME_FEATURE_INVALID = "POINT_IN_TIME_FEATURE_INVALID"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    LABEL_POLICY_MISMATCH = "LABEL_POLICY_MISMATCH"
    LABEL_AFTER_TRAINING_FREEZE = "LABEL_AFTER_TRAINING_FREEZE"
    UNKNOWN_LABEL_EXCLUDED = "UNKNOWN_LABEL_EXCLUDED"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    SINGLE_CLASS = "SINGLE_CLASS"
    LIGHTGBM_NOT_READY = "LIGHTGBM_NOT_READY"
    CALIBRATION_NOT_READY = "CALIBRATION_NOT_READY"
    FEATURE_ALLOWLIST_MISMATCH = "FEATURE_ALLOWLIST_MISMATCH"
    REGISTRY_REGISTRATION_FAILED = "REGISTRY_REGISTRATION_FAILED"


@dataclass(frozen=True)
class CandidateTrainingConfig:
    """Explicit fixed configuration for one candidate-training attempt."""

    candidate_id: str
    bundle_id: str
    training_freeze_cutoff: datetime
    dataset_provenance_reference: str
    feature_version: str
    label_policy_version: str
    training_configuration_version: str
    evaluation_policy_version: str
    mode: CandidateTrainingMode = CandidateTrainingMode.REAL_CANDIDATE
    model_version_prefix: str = "candidate_lightgbm_v1"
    calibration_version_prefix: str = "candidate_sigmoid_v1"
    split_policy_version: str | None = None
    tenant_scope: str | None = None
    use_validation_early_stopping: bool = False
    lightgbm_config: LightGBMConfig | None = None
    calibration_config: CalibrationConfig = field(default_factory=CalibrationConfig)
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.training_freeze_cutoff.tzinfo is None or self.training_freeze_cutoff.utcoffset() is None:
            raise ValueError("training_freeze_cutoff must be timezone-aware")
        for field_name in (
            "candidate_id",
            "bundle_id",
            "dataset_provenance_reference",
            "feature_version",
            "label_policy_version",
            "training_configuration_version",
            "evaluation_policy_version",
            "model_version_prefix",
            "calibration_version_prefix",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must be non-empty")
        if self.created_at is not None and (
            self.created_at.tzinfo is None or self.created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware")
        if self.lightgbm_config is not None and self.lightgbm_config.n_estimators > 200:
            raise ValueError("candidate training configuration is not a small fixed configuration")


@dataclass(frozen=True)
class CandidateHorizonTraining:
    horizon_days: HorizonDays
    model: LightGBMModel
    calibrator: ProbabilityCalibrator
    model_fit: LightGBMFitResult
    calibration_fit: CalibrationFitResult
    training_snapshot_ids: tuple[str, ...]
    calibration_snapshot_ids: tuple[str, ...]


@dataclass(frozen=True)
class CandidateTrainingResult:
    status: CandidateTrainingStatus
    config: CandidateTrainingConfig
    candidate_metadata: ModelBundleMetadata | None = None
    horizon_results: tuple[CandidateHorizonTraining, ...] = ()
    readiness_report: RetrainingReadinessReport | None = None
    provenance: DatasetProvenance | None = None
    reason_codes: tuple[CandidateTrainingReasonCode, ...] = ()
    warnings: tuple[str, ...] = ()
    production_eligible: bool = False
    registry_candidate_registered: bool = False
    test_partition_accessed: bool = False

    @property
    def successful(self) -> bool:
        return self.status in {
            CandidateTrainingStatus.TRAINED,
            CandidateTrainingStatus.SYNTHETIC_ONLY,
        }

    def horizon(self, horizon_days: HorizonDays) -> CandidateHorizonTraining:
        for result in self.horizon_results:
            if result.horizon_days == horizon_days:
                return result
        raise KeyError(f"horizon {horizon_days} was not trained")


def _unique(values: list[CandidateTrainingReasonCode]) -> tuple[CandidateTrainingReasonCode, ...]:
    return tuple(dict.fromkeys(values))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _failed(
    config: CandidateTrainingConfig,
    status: CandidateTrainingStatus,
    reasons: list[CandidateTrainingReasonCode],
    *,
    readiness_report: RetrainingReadinessReport | None = None,
    provenance: DatasetProvenance | None = None,
    warnings: tuple[str, ...] = (),
) -> CandidateTrainingResult:
    return CandidateTrainingResult(
        status=status,
        config=config,
        readiness_report=readiness_report,
        provenance=provenance,
        reason_codes=_unique(reasons),
        warnings=warnings,
    )


def _selected_records(
    split_result: TemporalSplitResult,
    partition: SplitName,
    horizon_days: HorizonDays,
) -> tuple[SnapshotRecord, ...]:
    selected_ids = set(
        split_result.partition(partition).supervised_snapshot_ids_by_horizon.get(
            horizon_days, ()
        )
    )
    return tuple(
        record
        for record in split_result.partition(partition).snapshots
        if record.stable_snapshot_id in selected_ids and record.prediction_eligible
    )


def _preflight(
    split_result: TemporalSplitResult,
    dataset_readiness: DatasetReadinessReport | None,
    readiness_report: RetrainingReadinessReport | None,
    config: CandidateTrainingConfig,
) -> tuple[CandidateTrainingStatus | None, list[CandidateTrainingReasonCode], DatasetProvenance | None]:
    reasons: list[CandidateTrainingReasonCode] = []
    provenance = dataset_readiness.dataset_source if dataset_readiness else None

    if config.mode is CandidateTrainingMode.REAL_CANDIDATE:
        if dataset_readiness is None:
            return CandidateTrainingStatus.BLOCKED, [CandidateTrainingReasonCode.DATASET_READINESS_REQUIRED], provenance
        if dataset_readiness.status is not DatasetStatus.PASS or not dataset_readiness.eligible_for_genuine_training:
            reasons.append(CandidateTrainingReasonCode.DATASET_NOT_PASS)
        if provenance.evidence_type is ProvenanceEvidenceType.SYNTHETIC:
            reasons.append(CandidateTrainingReasonCode.SYNTHETIC_PROVENANCE_REQUIRED)
        elif provenance.evidence_type is not ProvenanceEvidenceType.REAL_AUTHORIZED:
            reasons.append(CandidateTrainingReasonCode.DATASET_NOT_AUTHORIZED)
        if readiness_report is None:
            reasons.append(CandidateTrainingReasonCode.RETRAINING_READINESS_REQUIRED)
        elif readiness_report.readiness_status is not RetrainingReadinessStatus.READY_FOR_CANDIDATE_TRAINING:
            reasons.append(CandidateTrainingReasonCode.RETRAINING_READINESS_NOT_READY)
        if reasons:
            status = (
                CandidateTrainingStatus.BLOCKED
                if any(
                    reason
                    in {
                        CandidateTrainingReasonCode.DATASET_READINESS_REQUIRED,
                        CandidateTrainingReasonCode.DATASET_NOT_AUTHORIZED,
                        CandidateTrainingReasonCode.SYNTHETIC_PROVENANCE_REQUIRED,
                    }
                    for reason in reasons
                )
                else CandidateTrainingStatus.NOT_READY
            )
            return status, reasons, provenance
    else:
        if dataset_readiness is None or provenance is None:
            return CandidateTrainingStatus.BLOCKED, [CandidateTrainingReasonCode.SYNTHETIC_PROVENANCE_REQUIRED], provenance
        identifier = dataset_readiness.dataset_source.source_name or ""
        reference = config.dataset_provenance_reference.lower()
        if provenance.evidence_type is not ProvenanceEvidenceType.SYNTHETIC or not (
            identifier.lower().startswith("synthetic") or reference.startswith("synthetic")
        ):
            return CandidateTrainingStatus.BLOCKED, [CandidateTrainingReasonCode.SYNTHETIC_PROVENANCE_REQUIRED], provenance

    boundaries = split_result.manifest.boundaries
    if config.training_freeze_cutoff != boundaries.train_end:
        reasons.append(CandidateTrainingReasonCode.TRAINING_FREEZE_MISMATCH)
    if config.split_policy_version and config.split_policy_version != split_result.manifest.split_policy_version:
        reasons.append(CandidateTrainingReasonCode.SPLIT_POLICY_MISMATCH)
    if (
        split_result.manifest.dataset_identifier
        and split_result.manifest.dataset_identifier != config.dataset_provenance_reference
    ):
        reasons.append(CandidateTrainingReasonCode.DATASET_REFERENCE_MISMATCH)
    if readiness_report is not None:
        if readiness_report.training_freeze_cutoff != config.training_freeze_cutoff:
            reasons.append(CandidateTrainingReasonCode.TRAINING_FREEZE_MISMATCH)
        if (
            readiness_report.temporal_split_policy_version
            and readiness_report.temporal_split_policy_version
            != split_result.manifest.split_policy_version
        ):
            reasons.append(CandidateTrainingReasonCode.SPLIT_POLICY_MISMATCH)
    if reasons and config.mode is CandidateTrainingMode.SYNTHETIC_TEST_ONLY:
        return CandidateTrainingStatus.NOT_READY, reasons, provenance
    return None, reasons, provenance


def _validate_selected_inputs(
    split_result: TemporalSplitResult,
    config: CandidateTrainingConfig,
) -> tuple[CandidateTrainingReasonCode, ...]:
    reasons: list[CandidateTrainingReasonCode] = []
    seen_feature_versions: set[str] = set()
    seen_label_versions: set[str] = set()
    for horizon in SUPPORTED_HORIZONS:
        records = _selected_records(split_result, SplitName.TRAIN, horizon)  # type: ignore[arg-type]
        for record in records:
            snapshot = record.feature_snapshot
            seen_feature_versions.add(snapshot.feature_version)
            if snapshot.feature_version != config.feature_version:
                reasons.append(CandidateTrainingReasonCode.FEATURE_VERSION_MISMATCH)
            if snapshot.data_cutoff_at > snapshot.as_of:
                reasons.append(CandidateTrainingReasonCode.POINT_IN_TIME_FEATURE_INVALID)
            label = next(item for item in record.labels if item.horizon_days == horizon)
            seen_label_versions.add(label.label_policy_version)
            if label.label_policy_version != config.label_policy_version:
                reasons.append(CandidateTrainingReasonCode.LABEL_POLICY_MISMATCH)
            if label.label_status not in {LabelStatus.POSITIVE, LabelStatus.NEGATIVE} or label.label not in {0, 1}:
                reasons.append(CandidateTrainingReasonCode.UNKNOWN_LABEL_EXCLUDED)
            if (
                label.evaluation_as_of > config.training_freeze_cutoff
                or label.label_observed_through > config.training_freeze_cutoff
                or label.label_generated_at > config.training_freeze_cutoff
            ):
                reasons.append(CandidateTrainingReasonCode.LABEL_AFTER_TRAINING_FREEZE)
    if len(seen_feature_versions) > 1:
        reasons.append(CandidateTrainingReasonCode.FEATURE_VERSION_MISMATCH)
    if len(seen_label_versions) > 1:
        reasons.append(CandidateTrainingReasonCode.LABEL_POLICY_MISMATCH)
    return _unique(reasons)


def _model_config(config: CandidateTrainingConfig, horizon_days: HorizonDays) -> LightGBMConfig:
    base = config.lightgbm_config or LightGBMConfig()
    if base.allowlist != LightGBMConfig().allowlist:
        raise ValueError(CandidateTrainingReasonCode.FEATURE_ALLOWLIST_MISMATCH.value)
    return replace(
        base,
        model_version=f"{config.model_version_prefix}_{horizon_days}d",
        feature_version=config.feature_version,
        label_policy_version=config.label_policy_version,
        dataset_provenance=config.dataset_provenance_reference,
        tenant_id=config.tenant_scope,
        use_validation_early_stopping=config.use_validation_early_stopping,
    )


def train_candidate(
    split_result: TemporalSplitResult,
    *,
    dataset_readiness: DatasetReadinessReport | None,
    config: CandidateTrainingConfig,
    readiness_report: RetrainingReadinessReport | None = None,
    registry: ModelRegistry | None = None,
    clock: Callable[[], datetime] = _now,
) -> CandidateTrainingResult:
    """Fit three independent candidate models and calibration layers.

    The real path requires a passing authorized dataset and a separate ready
    retraining report.  The synthetic path requires explicit synthetic
    provenance and returns a test-only result that cannot be made production
    eligible by this coordinator.
    """

    status, reasons, provenance = _preflight(
        split_result, dataset_readiness, readiness_report, config
    )
    if status is not None:
        return _failed(
            config,
            status,
            reasons,
            readiness_report=readiness_report,
            provenance=provenance,
            warnings=(
                ("Synthetic fixtures are structural test evidence only.",)
                if config.mode is CandidateTrainingMode.SYNTHETIC_TEST_ONLY
                else ()
            ),
        )

    input_reasons = list(_validate_selected_inputs(split_result, config))
    if input_reasons:
        return _failed(
            config,
            CandidateTrainingStatus.NOT_READY,
            input_reasons,
            readiness_report=readiness_report,
            provenance=provenance,
        )

    try:
        model_configs = {
            horizon: _model_config(config, horizon)  # type: ignore[arg-type]
            for horizon in SUPPORTED_HORIZONS
        }
    except ValueError as exc:
        reason = next(
            (
                item
                for item in CandidateTrainingReasonCode
                if item.value in str(exc)
            ),
            CandidateTrainingReasonCode.FEATURE_ALLOWLIST_MISMATCH,
        )
        return _failed(
            config,
            CandidateTrainingStatus.NOT_READY,
            [reason],
            readiness_report=readiness_report,
            provenance=provenance,
        )

    horizon_results: list[CandidateHorizonTraining] = []
    for horizon in SUPPORTED_HORIZONS:
        typed_horizon = horizon  # type: ignore[assignment]
        model = LightGBMModel(model_configs[horizon])
        model_fit = model.fit(split_result, horizon_days=typed_horizon)
        calibrator = ProbabilityCalibrator(config.calibration_config)
        calibration_fit = calibrator.fit(
            model,
            split_result,
            horizon_days=typed_horizon,
        )
        horizon_results.append(
            CandidateHorizonTraining(
                horizon_days=typed_horizon,
                model=model,
                calibrator=calibrator,
                model_fit=model_fit,
                calibration_fit=calibration_fit,
                training_snapshot_ids=tuple(
                    split_result.supervised_snapshot_ids(SplitName.TRAIN, typed_horizon)
                ),
                calibration_snapshot_ids=tuple(
                    split_result.partition(SplitName.CALIBRATION)
                    .supervised_snapshot_ids_by_horizon.get(horizon, ())
                ),
            )
        )

    failed_horizons = [
        item
        for item in horizon_results
        if item.model_fit.status.value != "ready"
        or item.calibration_fit.status.value != "ready"
    ]
    if failed_horizons:
        failure_reasons: list[CandidateTrainingReasonCode] = []
        for item in failed_horizons:
            if item.model_fit.status.value != "ready":
                failure_reasons.append(CandidateTrainingReasonCode.LIGHTGBM_NOT_READY)
            if item.calibration_fit.status.value != "ready":
                failure_reasons.append(CandidateTrainingReasonCode.CALIBRATION_NOT_READY)
            if item.model_fit.reason and "one class" in item.model_fit.reason:
                failure_reasons.append(CandidateTrainingReasonCode.SINGLE_CLASS)
            if item.model_fit.reason and "insufficient" in item.model_fit.reason:
                failure_reasons.append(CandidateTrainingReasonCode.INSUFFICIENT_SAMPLES)
        return CandidateTrainingResult(
            status=CandidateTrainingStatus.NOT_READY,
            config=config,
            horizon_results=tuple(horizon_results),
            readiness_report=readiness_report,
            provenance=provenance,
            reason_codes=_unique(failure_reasons),
            warnings=(
                "A candidate is not produced unless all three model and calibration fits are ready.",
            ),
        )

    created_at = config.created_at or clock()
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("candidate clock must return a timezone-aware timestamp")
    if created_at < config.training_freeze_cutoff:
        raise ValueError("candidate created_at must not precede training_freeze_cutoff")

    model_versions = tuple(
        item.model_fit.metadata.model_version  # type: ignore[union-attr]
        for item in horizon_results
    )
    calibration_versions = tuple(
        item.calibration_fit.metadata.calibration_version  # type: ignore[union-attr]
        for item in horizon_results
    )
    metadata = ModelBundleMetadata(
        bundle_id=config.bundle_id,
        candidate_id=config.candidate_id,
        model_family="lightgbm",
        model_versions=tuple(
            {"horizon_days": horizon, "version": version}
            for horizon, version in zip(SUPPORTED_HORIZONS, model_versions)
        ),
        calibration_versions=tuple(
            {"horizon_days": horizon, "version": version}
            for horizon, version in zip(SUPPORTED_HORIZONS, calibration_versions)
        ),
        feature_version=config.feature_version,
        label_policy_version=config.label_policy_version,
        training_configuration_version=config.training_configuration_version,
        dataset_provenance_reference=config.dataset_provenance_reference,
        temporal_split_policy_version=split_result.manifest.split_policy_version,
        training_freeze_cutoff=config.training_freeze_cutoff,
        evaluation_policy_version=config.evaluation_policy_version,
        created_at=created_at,
        status=ModelLifecycleStatus.PROPOSED,
        provenance_status=(
            RegistryProvenanceStatus.SYNTHETIC_TEST_ONLY
            if config.mode is CandidateTrainingMode.SYNTHETIC_TEST_ONLY
            else RegistryProvenanceStatus.AUTHORIZED_REAL
        ),
        synthetic_test_only=config.mode is CandidateTrainingMode.SYNTHETIC_TEST_ONLY,
        tenant_scope=config.tenant_scope,
        readiness_report_fingerprint=(
            readiness_report.fingerprint() if readiness_report is not None else None
        ),
    )

    registered = False
    if registry is not None:
        try:
            registry.register_candidate(metadata)
            registered = True
        except ValueError:
            return CandidateTrainingResult(
                status=CandidateTrainingStatus.NOT_READY,
                config=config,
                candidate_metadata=metadata,
                horizon_results=tuple(horizon_results),
                readiness_report=readiness_report,
                provenance=provenance,
                reason_codes=(CandidateTrainingReasonCode.REGISTRY_REGISTRATION_FAILED,),
            )

    result_status = (
        CandidateTrainingStatus.SYNTHETIC_ONLY
        if config.mode is CandidateTrainingMode.SYNTHETIC_TEST_ONLY
        else CandidateTrainingStatus.TRAINED
    )
    warning_list = [
        "Models and calibrators are in-memory candidate artifacts; no production bundle was changed.",
    ]
    if config.mode is CandidateTrainingMode.SYNTHETIC_TEST_ONLY:
        warning_list.append(
            "Synthetic model metrics and artifacts are test-only and cannot support production approval."
        )
    return CandidateTrainingResult(
        status=result_status,
        config=config,
        candidate_metadata=metadata,
        horizon_results=tuple(horizon_results),
        readiness_report=readiness_report,
        provenance=provenance,
        reason_codes=tuple(reasons),
        warnings=tuple(warning_list),
        production_eligible=config.mode is CandidateTrainingMode.REAL_CANDIDATE,
        registry_candidate_registered=registered,
        test_partition_accessed=False,
    )


__all__ = [
    "CandidateHorizonTraining",
    "CandidateTrainingConfig",
    "CandidateTrainingMode",
    "CandidateTrainingReasonCode",
    "CandidateTrainingResult",
    "CandidateTrainingStatus",
    "train_candidate",
]
