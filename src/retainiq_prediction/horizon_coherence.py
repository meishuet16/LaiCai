"""Validation and explicit monotonic correction for cumulative horizons."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .baselines import BaselineStatus
from .calibration import CalibratedProbability, ProbabilityCalibrator
from .dataset_readiness import DatasetStatus
from .lightgbm_model import LightGBMModel


class _CoherenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoherenceMethod(str, Enum):
    CUMULATIVE_MAX = "cumulative_max_v1"


class HorizonProbabilities(_CoherenceModel):
    p7: float = Field(ge=0.0, le=1.0)
    p14: float = Field(ge=0.0, le=1.0)
    p30: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def require_finite(self) -> "HorizonProbabilities":
        if not all(math.isfinite(value) for value in (self.p7, self.p14, self.p30)):
            raise ValueError("horizon probabilities must be finite")
        return self

    @property
    def is_monotonic(self) -> bool:
        return self.p7 <= self.p14 <= self.p30


class CalibratedHorizonBundle(_CoherenceModel):
    probabilities: HorizonProbabilities
    model_version: str = Field(min_length=1)
    calibration_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    empirical_validation_status: DatasetStatus


class HorizonCoherenceResult(_CoherenceModel):
    original: HorizonProbabilities
    adjusted: HorizonProbabilities
    adjustment_applied: bool
    adjustment_method: CoherenceMethod | None = None
    metadata: dict[str, Any]


class CalibrationBundleReadiness(_CoherenceModel):
    status: BaselineStatus
    required_horizons: tuple[int, ...] = (7, 14, 30)
    ready_horizons: tuple[int, ...] = ()
    missing_horizons: tuple[int, ...] = ()
    reasons: tuple[str, ...] = ()
    model_versions: dict[int, str] = Field(default_factory=dict)
    calibration_versions: dict[int, str] = Field(default_factory=dict)
    dataset_statuses: dict[int, DatasetStatus] = Field(default_factory=dict)


def calibrated_bundle_from_outputs(
    outputs: Sequence[CalibratedProbability],
) -> CalibratedHorizonBundle:
    """Build a complete three-horizon bundle or reject incompatible outputs."""

    if len({output.horizon_days for output in outputs}) != len(outputs):
        raise ValueError("duplicate calibrated horizon outputs are not allowed")
    by_horizon = {output.horizon_days: output for output in outputs}
    missing = set((7, 14, 30)) - set(by_horizon)
    if missing:
        raise ValueError(f"missing calibrated horizons: {sorted(missing)}")
    selected = [by_horizon[horizon] for horizon in (7, 14, 30)]
    compatibility = {
        (
            item.model_version,
            item.calibration_version,
            item.feature_version,
            item.label_policy_version,
        )
        for item in selected
    }
    if len(compatibility) != 1:
        raise ValueError("calibrated horizons have incompatible metadata")
    first = selected[0]
    return CalibratedHorizonBundle(
        probabilities=HorizonProbabilities(
            p7=by_horizon[7].calibrated_probability,
            p14=by_horizon[14].calibrated_probability,
            p30=by_horizon[30].calibrated_probability,
        ),
        model_version=first.model_version,
        calibration_version=first.calibration_version,
        feature_version=first.feature_version,
        label_policy_version=first.label_policy_version,
        empirical_validation_status=(
            DatasetStatus.PASS
            if all(item.empirical_validation_status is DatasetStatus.PASS for item in selected)
            else DatasetStatus.BLOCKED
        ),
    )


def enforce_horizon_coherence(
    probabilities: HorizonProbabilities | CalibratedHorizonBundle,
    *,
    method: CoherenceMethod = CoherenceMethod.CUMULATIVE_MAX,
) -> HorizonCoherenceResult:
    """Return original values and an explicit cumulative-max adjustment."""

    if method is not CoherenceMethod.CUMULATIVE_MAX:
        raise ValueError(f"unsupported coherence method: {method}")
    if isinstance(probabilities, CalibratedHorizonBundle):
        original = probabilities.probabilities
        metadata: dict[str, Any] = {
            "model_version": probabilities.model_version,
            "calibration_version": probabilities.calibration_version,
            "feature_version": probabilities.feature_version,
            "label_policy_version": probabilities.label_policy_version,
            "empirical_validation_status": probabilities.empirical_validation_status.value,
        }
    else:
        original = probabilities
        metadata = {}
    if original.is_monotonic:
        return HorizonCoherenceResult(
            original=original,
            adjusted=original,
            adjustment_applied=False,
            adjustment_method=None,
            metadata={
                **metadata,
                "policy": "already_monotonic; no value changed",
            },
        )
    adjusted = HorizonProbabilities(
        p7=original.p7,
        p14=max(original.p7, original.p14),
        p30=max(original.p7, original.p14, original.p30),
    )
    return HorizonCoherenceResult(
        original=original,
        adjusted=adjusted,
        adjustment_applied=True,
        adjustment_method=method,
        metadata={
            **metadata,
            "policy": "cumulative maximum over independently calibrated probabilities",
            "limitation": "ordering is enforced; calibration properties may change and must be reassessed",
        },
    )


def assess_calibrated_bundle_readiness(
    models: Mapping[int, LightGBMModel],
    calibrators: Mapping[int, ProbabilityCalibrator],
) -> CalibrationBundleReadiness:
    """Require all model/calibrator pairs and real evidence for production use."""

    ready: list[int] = []
    missing: list[int] = []
    reasons: list[str] = []
    model_versions: dict[int, str] = {}
    calibration_versions: dict[int, str] = {}
    dataset_statuses: dict[int, DatasetStatus] = {}
    for horizon in (7, 14, 30):
        model = models.get(horizon)
        calibrator = calibrators.get(horizon)
        if model is None or calibrator is None:
            missing.append(horizon)
            reasons.append(f"horizon {horizon} is missing its model or calibrator")
            continue
        model_metadata = model.metadata
        calibration_metadata = calibrator.metadata
        if model.fit_result is None or model.fit_result.status is not BaselineStatus.READY:
            missing.append(horizon)
            reasons.append(f"horizon {horizon} model is not ready")
            continue
        if calibrator.fit_result is None or calibrator.fit_result.status is not BaselineStatus.READY:
            missing.append(horizon)
            reasons.append(f"horizon {horizon} calibrator is not ready")
            continue
        if model_metadata is None or calibration_metadata is None:
            missing.append(horizon)
            reasons.append(f"horizon {horizon} metadata is incomplete")
            continue
        if (
            model_metadata.model_version != calibration_metadata.model_version
            or model_metadata.feature_version != calibration_metadata.feature_version
            or model_metadata.label_policy_version != calibration_metadata.label_policy_version
            or model_metadata.prediction_horizon_days != calibration_metadata.prediction_horizon_days
        ):
            missing.append(horizon)
            reasons.append(f"horizon {horizon} model/calibrator metadata is incompatible")
            continue
        ready.append(horizon)
        model_versions[horizon] = model_metadata.model_version
        calibration_versions[horizon] = calibration_metadata.calibration_version
        dataset_statuses[horizon] = calibration_metadata.training_dataset_status
        if calibration_metadata.training_dataset_status is not DatasetStatus.PASS:
            reasons.append(
                f"horizon {horizon} calibration dataset status is "
                f"{calibration_metadata.training_dataset_status.value.lower()}, not pass"
            )
    if missing or len(ready) != 3 or any(status is not DatasetStatus.PASS for status in dataset_statuses.values()):
        return CalibrationBundleReadiness(
            status=BaselineStatus.NOT_READY,
            ready_horizons=tuple(ready),
            missing_horizons=tuple(missing),
            reasons=tuple(dict.fromkeys(reasons)),
            model_versions=model_versions,
            calibration_versions=calibration_versions,
            dataset_statuses=dataset_statuses,
        )
    return CalibrationBundleReadiness(
        status=BaselineStatus.READY,
        ready_horizons=tuple(ready),
        model_versions=model_versions,
        calibration_versions=calibration_versions,
        dataset_statuses=dataset_statuses,
    )


__all__ = [
    "CalibrationBundleReadiness",
    "CalibratedHorizonBundle",
    "CoherenceMethod",
    "HorizonCoherenceResult",
    "HorizonProbabilities",
    "assess_calibrated_bundle_readiness",
    "calibrated_bundle_from_outputs",
    "enforce_horizon_coherence",
]
