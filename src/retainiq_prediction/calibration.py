"""Chronological sigmoid calibration for independent LightGBM horizons.

Calibration is fitted only on the reserved CALIBRATION partition.  It stores
raw and calibrated diagnostics separately and never changes the trained
LightGBM artifact or the canonical PredictionOutput contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
import os
from pathlib import Path
import pickle
import platform
import sys
import tempfile
from typing import Any, Literal, Mapping, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from .baselines import BaselinePrediction, BaselineScoreKind, BaselineStatus
from .dataset_readiness import DatasetStatus
from .label_builder import ChurnLabel, LabelStatus, SUPPORTED_HORIZONS
from .lightgbm_model import (
    LightGBMModel,
    LightGBMModelMetadata,
)
from .temporal_splits import SplitName, TemporalSplitResult


HorizonDays = Literal[7, 14, 30]


class _CalibrationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalibrationMethod(str, Enum):
    SIGMOID = "sigmoid"


class CalibrationMetadata(_CalibrationModel):
    calibration_version: str = Field(min_length=1)
    calibration_method: Literal["sigmoid"]
    model_version: str = Field(min_length=1)
    prediction_horizon_days: HorizonDays
    feature_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    fitting_cutoff: AwareDatetime
    calibration_sample_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    configuration: dict[str, Any]
    training_dataset_provenance: str | None = None
    training_dataset_status: DatasetStatus
    dependency_versions: dict[str, str]
    input_semantics: Literal["raw_probability_logit_once"]
    empirical_validation_status: DatasetStatus


class CalibratedProbability(_CalibrationModel):
    horizon_days: HorizonDays
    raw_probability: float = Field(ge=0.0, le=1.0)
    calibrated_probability: float = Field(ge=0.0, le=1.0)
    calibration_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    empirical_validation_status: DatasetStatus

    @field_validator("raw_probability", "calibrated_probability")
    @classmethod
    def require_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("probabilities must be finite")
        return value


class CalibrationFitResult(_CalibrationModel):
    horizon_days: HorizonDays
    status: BaselineStatus
    metadata: CalibrationMetadata | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CalibrationConfig:
    calibration_version: str = "calibration_sigmoid_v1"
    minimum_samples: int = 4
    minimum_positive: int = 2
    minimum_negative: int = 2
    epsilon: float = 1e-6
    random_seed: int = 42

    def __post_init__(self) -> None:
        if not self.calibration_version.strip():
            raise ValueError("calibration_version must be non-empty")
        if self.minimum_samples < 2 or self.minimum_positive < 1 or self.minimum_negative < 1:
            raise ValueError("calibration sample requirements must be positive")
        if not 0 < self.epsilon < 0.5:
            raise ValueError("epsilon must be between 0 and 0.5")


try:  # The project ML extra supplies scikit-learn.
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    CALIBRATION_AVAILABLE = True
    CALIBRATION_DEPENDENCY_VERSION = __import__("sklearn").__version__
    _CALIBRATION_IMPORT_ERROR: str | None = None
except ImportError as exc:  # pragma: no cover - environment-dependent branch
    CALIBRATION_AVAILABLE = False
    CALIBRATION_DEPENDENCY_VERSION = None
    _CALIBRATION_IMPORT_ERROR = str(exc)
    np = None  # type: ignore[assignment]
    LogisticRegression = None  # type: ignore[assignment,misc]


class ProbabilityCalibrator:
    """Fit one sigmoid calibrator against one horizon's CALIBRATION mask."""

    def __init__(self, config: CalibrationConfig | None = None) -> None:
        self.config = config or CalibrationConfig()
        self._calibrator: Any = None
        self._fit_result: CalibrationFitResult | None = None

    @property
    def fit_result(self) -> CalibrationFitResult | None:
        return self._fit_result

    @property
    def metadata(self) -> CalibrationMetadata | None:
        return self._fit_result.metadata if self._fit_result is not None else None

    def fit(
        self,
        model: LightGBMModel,
        split_result: TemporalSplitResult,
        *,
        horizon_days: HorizonDays,
    ) -> CalibrationFitResult:
        """Fit on confirmed mature CALIBRATION labels only."""

        _validate_horizon(horizon_days)
        model_metadata = model.metadata
        if model.fit_result is None or model.fit_result.status is not BaselineStatus.READY:
            self._fit_result = CalibrationFitResult(
                horizon_days=horizon_days,
                status=BaselineStatus.NOT_READY,
                reason="the LightGBM model must be fitted and ready before calibration",
            )
            return self._fit_result
        if model_metadata is None or model_metadata.prediction_horizon_days != horizon_days:
            self._fit_result = CalibrationFitResult(
                horizon_days=horizon_days,
                status=BaselineStatus.NOT_READY,
                reason="LightGBM model horizon metadata does not match calibrator horizon",
            )
            return self._fit_result

        calibration = split_result.partition(SplitName.CALIBRATION)
        usable_ids = set(
            calibration.supervised_snapshot_ids_by_horizon.get(horizon_days, ())
        )
        records = tuple(
            record for record in calibration.snapshots if record.stable_snapshot_id in usable_ids
        )
        labels = {
            record.stable_snapshot_id: next(
                label for label in record.labels if label.horizon_days == horizon_days
            )
            for record in records
        }
        raw_probabilities: list[float] = []
        target: list[int] = []
        policy_versions: set[str] = set()
        for record in records:
            label = labels[record.stable_snapshot_id]
            policy_versions.add(label.label_policy_version)
            raw = model.predict(record.feature_snapshot, horizon_days=horizon_days)
            if raw.status is not BaselineStatus.READY or raw.score is None:
                self._fit_result = CalibrationFitResult(
                    horizon_days=horizon_days,
                    status=BaselineStatus.NOT_READY,
                    reason="LightGBM could not produce a raw calibration score",
                )
                return self._fit_result
            if raw.score_kind is not BaselineScoreKind.UNCALIBRATED_PROBABILITY:
                self._fit_result = CalibrationFitResult(
                    horizon_days=horizon_days,
                    status=BaselineStatus.NOT_READY,
                    reason="calibration requires explicitly uncalibrated raw probabilities",
                )
                return self._fit_result
            raw_probabilities.append(raw.score)
            target.append(int(label.label))

        positive_count = sum(value == 1 for value in target)
        negative_count = sum(value == 0 for value in target)
        if len(records) < self.config.minimum_samples:
            return self._not_ready(
                horizon_days,
                "insufficient mature calibration samples",
            )
        if positive_count < self.config.minimum_positive or negative_count < self.config.minimum_negative:
            return self._not_ready(
                horizon_days,
                "calibration requires sufficient positive and negative examples",
            )
        if len(policy_versions) != 1 or next(iter(policy_versions)) != model_metadata.label_policy_version:
            return self._not_ready(
                horizon_days,
                "calibration label policy does not match the LightGBM model",
            )
        if not CALIBRATION_AVAILABLE:
            return self._not_ready(
                horizon_days,
                f"calibration dependency is unavailable: {_CALIBRATION_IMPORT_ERROR}",
            )

        assert np is not None
        assert LogisticRegression is not None
        logits = np.asarray(
            [[_logit(value, self.config.epsilon)] for value in raw_probabilities],
            dtype=float,
        )
        target_array = np.asarray(target, dtype=int)
        calibrator = LogisticRegression(
            random_state=self.config.random_seed,
            max_iter=1000,
        )
        try:
            calibrator.fit(logits, target_array)
        except (TypeError, ValueError, RuntimeError) as exc:
            return self._not_ready(horizon_days, f"sigmoid calibration fit failed: {exc}")

        metadata = CalibrationMetadata(
            calibration_version=self.config.calibration_version,
            calibration_method=CalibrationMethod.SIGMOID,
            model_version=model_metadata.model_version,
            prediction_horizon_days=horizon_days,
            feature_version=model_metadata.feature_version,
            label_policy_version=model_metadata.label_policy_version,
            fitting_cutoff=split_result.manifest.boundaries.calibration_end,
            calibration_sample_count=len(records),
            positive_count=positive_count,
            negative_count=negative_count,
            configuration={
                "epsilon": self.config.epsilon,
                "minimum_samples": self.config.minimum_samples,
                "minimum_positive": self.config.minimum_positive,
                "minimum_negative": self.config.minimum_negative,
                "random_seed": self.config.random_seed,
            },
            training_dataset_provenance=(
                model_metadata.training_dataset_provenance
                or split_result.manifest.dataset_identifier
            ),
            training_dataset_status=split_result.manifest.dataset_readiness_status,
            dependency_versions={
                "python": platform.python_version(),
                "scikit_learn": CALIBRATION_DEPENDENCY_VERSION or "unknown",
            },
            input_semantics="raw_probability_logit_once",
            empirical_validation_status=DatasetStatus.BLOCKED,
        )
        self._calibrator = calibrator
        self._fit_result = CalibrationFitResult(
            horizon_days=horizon_days,
            status=BaselineStatus.READY,
            metadata=metadata,
        )
        return self._fit_result

    def _not_ready(self, horizon_days: HorizonDays, reason: str) -> CalibrationFitResult:
        self._calibrator = None
        self._fit_result = CalibrationFitResult(
            horizon_days=horizon_days,
            status=BaselineStatus.NOT_READY,
            reason=reason,
        )
        return self._fit_result

    def calibrate_prediction(
        self,
        raw_prediction: BaselinePrediction,
        model_metadata: LIGHTGBMModelMetadata,
    ) -> CalibratedProbability:
        """Calibrate one raw model output after compatibility checks."""

        metadata = self.metadata
        if self._calibrator is None or metadata is None:
            raise RuntimeError("a ready calibrator is required")
        if raw_prediction.score is None or raw_prediction.score_kind is not BaselineScoreKind.UNCALIBRATED_PROBABILITY:
            raise ValueError("calibration requires an uncalibrated raw probability")
        if model_metadata.model_version != metadata.model_version:
            raise ValueError("model and calibrator versions do not match")
        if model_metadata.prediction_horizon_days != metadata.prediction_horizon_days:
            raise ValueError("model and calibrator horizons do not match")
        if model_metadata.feature_version != metadata.feature_version:
            raise ValueError("model and calibrator feature versions do not match")
        if model_metadata.label_policy_version != metadata.label_policy_version:
            raise ValueError("model and calibrator label policies do not match")
        if raw_prediction.horizon_days != metadata.prediction_horizon_days:
            raise ValueError("raw prediction horizon does not match calibrator")
        raw_probability = _finite_probability(raw_prediction.score)
        assert np is not None
        logit = _logit(raw_probability, self.config.epsilon)
        calibrated = float(self._calibrator.predict_proba(np.asarray([[logit]], dtype=float))[0][1])
        calibrated = _finite_probability(calibrated)
        return CalibratedProbability(
            horizon_days=metadata.prediction_horizon_days,
            raw_probability=raw_probability,
            calibrated_probability=calibrated,
            calibration_version=metadata.calibration_version,
            model_version=metadata.model_version,
            feature_version=metadata.feature_version,
            label_policy_version=metadata.label_policy_version,
            empirical_validation_status=metadata.empirical_validation_status,
        )

    def save(self, path: str | Path) -> None:
        if self._calibrator is None or self._fit_result is None or self._fit_result.status is not BaselineStatus.READY:
            raise RuntimeError("only a ready calibrator can be saved")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "artifact_type": "retainiq_sigmoid_calibrator",
            "artifact_version": 1,
            "config": self.config,
            "calibrator": self._calibrator,
            "fit_result": self._fit_result,
        }
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                pickle.dump(artifact, handle, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()

    @classmethod
    def load(cls, path: str | Path, *, trusted_root: str | Path) -> "ProbabilityCalibrator":
        root = Path(trusted_root).resolve()
        candidate = Path(path).resolve()
        if candidate.suffix.lower() != ".pkl":
            raise ValueError("calibrator artifacts must use the .pkl extension")
        if not candidate.is_file() or root not in candidate.parents:
            raise ValueError("artifact path is outside the validated trusted root")
        with candidate.open("rb") as handle:
            artifact = pickle.load(handle)
        if not isinstance(artifact, Mapping):
            raise ValueError("malformed calibrator artifact")
        if artifact.get("artifact_type") != "retainiq_sigmoid_calibrator":
            raise ValueError("unsupported calibrator artifact type")
        if artifact.get("artifact_version") != 1:
            raise ValueError("unsupported calibrator artifact version")
        config = artifact.get("config")
        if not isinstance(config, CalibrationConfig):
            raise ValueError("calibrator artifact is missing compatible configuration")
        fit_result = artifact.get("fit_result")
        if not isinstance(fit_result, CalibrationFitResult) or fit_result.metadata is None:
            raise ValueError("calibrator artifact is missing compatible metadata")
        metadata = fit_result.metadata
        if metadata.calibration_method != CalibrationMethod.SIGMOID:
            raise ValueError("unsupported calibration method")
        if metadata.input_semantics != "raw_probability_logit_once":
            raise ValueError("unsupported calibration input semantics")
        calibrator = cls(config)
        calibrator._calibrator = artifact.get("calibrator")
        if calibrator._calibrator is None or not hasattr(calibrator._calibrator, "predict_proba"):
            raise ValueError("calibrator artifact is missing fitted state")
        calibrator._fit_result = fit_result
        return calibrator


class CalibrationBin(_CalibrationModel):
    lower_bound: float = Field(ge=0.0, le=1.0)
    upper_bound: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    mean_predicted_probability: float | None = None
    observed_rate: float | None = None


class ProbabilityDiagnostics(_CalibrationModel):
    horizon_days: HorizonDays
    sample_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    raw_brier_score: float
    calibrated_brier_score: float
    adjusted_brier_score: float | None = None
    calibration_table: tuple[CalibrationBin, ...]
    empirical_validation_status: DatasetStatus


def evaluate_probability_diagnostics(
    labels: Sequence[ChurnLabel],
    raw_probabilities: Sequence[float],
    calibrated_probabilities: Sequence[float],
    *,
    horizon_days: HorizonDays,
    adjusted_probabilities: Sequence[float] | None = None,
    empirical_validation_status: DatasetStatus = DatasetStatus.BLOCKED,
) -> ProbabilityDiagnostics:
    """Compare raw/calibrated/adjusted Brier inputs without tuning anything."""

    _validate_horizon(horizon_days)
    if not len(labels) == len(raw_probabilities) == len(calibrated_probabilities):
        raise ValueError("labels and probability sequences must have equal lengths")
    if adjusted_probabilities is not None and len(adjusted_probabilities) != len(labels):
        raise ValueError("adjusted probabilities must match label length")
    usable: list[tuple[int, float, float, float | None]] = []
    for index, label in enumerate(labels):
        if label.horizon_days != horizon_days:
            raise ValueError("all diagnostics labels must match horizon_days")
        if label.label_status not in {LabelStatus.POSITIVE, LabelStatus.NEGATIVE} or label.label not in {0, 1}:
            continue
        raw = _finite_probability(raw_probabilities[index])
        calibrated = _finite_probability(calibrated_probabilities[index])
        adjusted = (
            _finite_probability(adjusted_probabilities[index])
            if adjusted_probabilities is not None
            else None
        )
        usable.append((int(label.label), raw, calibrated, adjusted))
    if not usable:
        raise ValueError("no confirmed mature labels are available for diagnostics")
    raw_brier = sum((prediction - outcome) ** 2 for outcome, prediction, _, _ in usable) / len(usable)
    calibrated_brier = sum(
        (prediction - outcome) ** 2 for outcome, _, prediction, _ in usable
    ) / len(usable)
    adjusted_values = [item[3] for item in usable]
    adjusted_brier = None
    if all(value is not None for value in adjusted_values):
        adjusted_brier = sum(
            (float(prediction) - outcome) ** 2
            for outcome, _, _, prediction in usable
        ) / len(usable)
    bins: list[CalibrationBin] = []
    for bin_index in range(5):
        lower = bin_index / 5
        upper = (bin_index + 1) / 5
        selected = [
            item
            for item in usable
            if (lower <= item[2] < upper) or (bin_index == 4 and item[2] == upper)
        ]
        bins.append(
            CalibrationBin(
                lower_bound=lower,
                upper_bound=upper,
                sample_count=len(selected),
                mean_predicted_probability=(
                    sum(item[2] for item in selected) / len(selected)
                    if selected
                    else None
                ),
                observed_rate=(
                    sum(item[0] for item in selected) / len(selected)
                    if selected
                    else None
                ),
            )
        )
    return ProbabilityDiagnostics(
        horizon_days=horizon_days,
        sample_count=len(usable),
        positive_count=sum(item[0] for item in usable),
        raw_brier_score=raw_brier,
        calibrated_brier_score=calibrated_brier,
        adjusted_brier_score=adjusted_brier,
        calibration_table=tuple(bins),
        empirical_validation_status=empirical_validation_status,
    )


def _logit(probability: float, epsilon: float) -> float:
    value = _finite_probability(probability)
    clipped = min(max(value, epsilon), 1 - epsilon)
    return math.log(clipped / (1 - clipped))


def _finite_probability(value: float) -> float:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("probability must be finite and within [0, 1]")
    return float(value)


def _validate_horizon(horizon_days: int) -> None:
    if horizon_days not in SUPPORTED_HORIZONS:
        raise ValueError(f"unsupported horizon: {horizon_days}")


__all__ = [
    "CALIBRATION_AVAILABLE",
    "CalibrationBin",
    "CalibrationConfig",
    "CalibrationFitResult",
    "CalibrationMetadata",
    "CalibrationMethod",
    "CalibratedProbability",
    "ProbabilityCalibrator",
    "ProbabilityDiagnostics",
    "evaluate_probability_diagnostics",
]
