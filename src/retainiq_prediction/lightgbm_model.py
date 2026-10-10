"""Optional CPU LightGBM training for independent churn horizons.

This module is a training candidate only.  It returns explicitly uncalibrated
probabilities and never constructs the canonical production PredictionOutput.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os
from pathlib import Path
import pickle
import platform
import sys
import tempfile
from typing import Any, Literal, Mapping

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .baselines import (
    BaselinePrediction,
    BaselineScoreKind,
    BaselineStatus,
    FeatureVectorizer,
    MODEL_FEATURE_ALLOWLIST,
)
from .dataset_readiness import DatasetStatus
from .label_builder import LabelStatus, SUPPORTED_HORIZONS
from .temporal_splits import SnapshotRecord, SplitName, TemporalSplitResult


HorizonDays = Literal[7, 14, 30]


class _LightGBMModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LightGBMModelMetadata(_LightGBMModel):
    """Metadata required to identify and audit a trusted internal artifact."""

    model_version: str = Field(min_length=1)
    model_family: Literal["lightgbm"] = "lightgbm"
    prediction_horizon_days: HorizonDays
    feature_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    feature_names: tuple[str, ...] = ()
    training_configuration: dict[str, Any]
    training_cutoff: AwareDatetime
    training_dataset_provenance: str | None = None
    training_dataset_status: DatasetStatus
    dependency_versions: dict[str, str]
    preprocessing_metadata: dict[str, Any]
    random_seed: int
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    tenant_scope: str | None = None


class LightGBMFitResult(_LightGBMModel):
    horizon_days: HorizonDays
    status: BaselineStatus
    training_snapshot_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    metadata: LightGBMModelMetadata | None = None
    reason: str | None = None


@dataclass(frozen=True)
class LightGBMConfig:
    """Conservative CPU configuration for small development datasets."""

    model_version: str = "lightgbm_baseline_v1"
    feature_version: str = "features_personalized_baseline_v1"
    label_policy_version: str | None = None
    dataset_provenance: str | None = None
    tenant_id: str | None = None
    random_seed: int = 42
    n_estimators: int = 40
    learning_rate: float = 0.05
    num_leaves: int = 7
    max_depth: int = 3
    min_child_samples: int = 5
    subsample: float = 0.9
    colsample_bytree: float = 0.9
    class_weight: str | None = None
    minimum_samples_per_horizon: int = 2
    use_validation_early_stopping: bool = False
    early_stopping_rounds: int = 10
    allowlist: tuple[str, ...] = MODEL_FEATURE_ALLOWLIST

    def __post_init__(self) -> None:
        if not self.model_version.strip() or not self.feature_version.strip():
            raise ValueError("model and feature versions must be non-empty")
        if self.label_policy_version is not None and not self.label_policy_version.strip():
            raise ValueError("label_policy_version must be non-empty when supplied")
        if self.n_estimators < 1 or self.max_depth < 1 or self.num_leaves < 2:
            raise ValueError("LightGBM complexity settings are invalid")
        if self.min_child_samples < 1 or self.minimum_samples_per_horizon < 2:
            raise ValueError("sample settings must be positive")
        if not 0 < self.learning_rate <= 1:
            raise ValueError("learning_rate must be in (0, 1]")
        if not 0 < self.subsample <= 1 or not 0 < self.colsample_bytree <= 1:
            raise ValueError("subsample and colsample_bytree must be in (0, 1]")
        if self.class_weight not in {None, "balanced"}:
            raise ValueError("class_weight must be None or 'balanced'")
        if self.early_stopping_rounds < 1:
            raise ValueError("early_stopping_rounds must be positive")


try:  # Optional import keeps the package usable without LightGBM.
    import lightgbm
    from lightgbm import LGBMClassifier

    LIGHTGBM_AVAILABLE = True
    LIGHTGBM_VERSION: str | None = lightgbm.__version__
    _LIGHTGBM_IMPORT_ERROR: str | None = None
except ImportError as exc:  # pragma: no cover - environment-dependent branch
    LIGHTGBM_AVAILABLE = False
    LIGHTGBM_VERSION = None
    _LIGHTGBM_IMPORT_ERROR = str(exc)
    LGBMClassifier = None  # type: ignore[assignment,misc]


class LightGBMModel:
    """Train and serve one trusted internal LightGBM model per horizon."""

    def __init__(
        self,
        config: LightGBMConfig | None = None,
        *,
        vectorizer: FeatureVectorizer | None = None,
    ) -> None:
        self.config = config or LightGBMConfig()
        self.vectorizer = vectorizer or FeatureVectorizer(self.config.allowlist)
        self._model: Any = None
        self._fit_result: LightGBMFitResult | None = None
        self._horizon_days: HorizonDays | None = None

    @property
    def fit_result(self) -> LightGBMFitResult | None:
        return self._fit_result

    @property
    def metadata(self) -> LightGBMModelMetadata | None:
        return self._fit_result.metadata if self._fit_result is not None else None

    def fit(
        self,
        split_result: TemporalSplitResult,
        *,
        horizon_days: HorizonDays,
    ) -> LightGBMFitResult:
        """Fit only from the TRAIN horizon mask.

        Validation can be passed to LightGBM solely for optional development
        early stopping.  Calibration and TEST are never read by this method.
        """

        _validate_horizon(horizon_days)
        train = split_result.partition(SplitName.TRAIN)
        supervised_ids = set(train.supervised_snapshot_ids_by_horizon.get(horizon_days, ()))
        records = tuple(
            record
            for record in train.snapshots
            if record.stable_snapshot_id in supervised_ids
            and record.prediction_eligible
            and (
                self.config.tenant_id is None
                or record.feature_snapshot.tenant_id == self.config.tenant_id
            )
        )
        labels = {
            record.stable_snapshot_id: next(
                label for label in record.labels if label.horizon_days == horizon_days
            )
            for record in records
        }
        positive_count = sum(labels[item.stable_snapshot_id].label == 1 for item in records)
        negative_count = sum(labels[item.stable_snapshot_id].label == 0 for item in records)
        policy_versions = {
            labels[item.stable_snapshot_id].label_policy_version for item in records
        }

        self._model = None
        self._horizon_days = horizon_days

        def result(
            status: BaselineStatus,
            reason: str | None = None,
            metadata: LightGBMModelMetadata | None = None,
        ) -> LightGBMFitResult:
            return LightGBMFitResult(
                horizon_days=horizon_days,
                status=status,
                training_snapshot_count=len(records),
                positive_count=positive_count,
                negative_count=negative_count,
                metadata=metadata,
                reason=reason,
            )

        if len(records) < self.config.minimum_samples_per_horizon:
            self._fit_result = result(
                BaselineStatus.NOT_READY,
                "insufficient mature supervised training snapshots",
            )
            return self._fit_result
        if positive_count == 0 or negative_count == 0:
            self._fit_result = result(
                BaselineStatus.NOT_READY,
                "training labels contain only one class",
            )
            return self._fit_result
        if len(policy_versions) != 1:
            self._fit_result = result(
                BaselineStatus.NOT_READY,
                "training labels contain conflicting label policy versions",
            )
            return self._fit_result
        if self.config.label_policy_version is not None and policy_versions != {
            self.config.label_policy_version
        }:
            self._fit_result = result(
                BaselineStatus.NOT_READY,
                "training label policy does not match model configuration",
            )
            return self._fit_result
        if not LIGHTGBM_AVAILABLE:
            self._fit_result = result(
                BaselineStatus.NOT_READY,
                f"LightGBM is unavailable: {_LIGHTGBM_IMPORT_ERROR}",
            )
            return self._fit_result

        import numpy as np

        feature_rows = np.asarray(
            [_numeric_row(self.vectorizer.row(record.feature_snapshot)) for record in records],
            dtype=float,
        )
        target = np.asarray(
            [int(labels[record.stable_snapshot_id].label) for record in records],
            dtype=int,
        )
        train_cutoff = split_result.manifest.boundaries.train_end
        label_policy_version = next(iter(policy_versions))
        training_config = {
            "n_estimators": self.config.n_estimators,
            "learning_rate": self.config.learning_rate,
            "num_leaves": self.config.num_leaves,
            "max_depth": self.config.max_depth,
            "min_child_samples": self.config.min_child_samples,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "class_weight": self.config.class_weight,
            "device_type": "cpu",
            "n_jobs": 1,
            "validation_early_stopping": self.config.use_validation_early_stopping,
        }
        metadata = LightGBMModelMetadata(
            model_version=self.config.model_version,
            prediction_horizon_days=horizon_days,
            feature_version=self.config.feature_version,
            label_policy_version=label_policy_version,
            feature_names=self.vectorizer.allowlist,
            training_configuration=training_config,
            training_cutoff=train_cutoff,
            training_dataset_provenance=(
                self.config.dataset_provenance or split_result.manifest.dataset_identifier
            ),
            training_dataset_status=split_result.manifest.dataset_readiness_status,
            dependency_versions={
                "python": platform.python_version(),
                "lightgbm": LIGHTGBM_VERSION or "unknown",
            },
            preprocessing_metadata={
                "strategy": "none",
                "missing_value_handling": "native_lightgbm",
                "feature_order_locked": True,
            },
            random_seed=self.config.random_seed,
            tenant_scope=self.config.tenant_id,
        )

        assert LGBMClassifier is not None
        try:
            model = LGBMClassifier(
                objective="binary",
                n_estimators=self.config.n_estimators,
                learning_rate=self.config.learning_rate,
                num_leaves=self.config.num_leaves,
                max_depth=self.config.max_depth,
                min_child_samples=self.config.min_child_samples,
                subsample=self.config.subsample,
                colsample_bytree=self.config.colsample_bytree,
                class_weight=self.config.class_weight,
                random_state=self.config.random_seed,
                n_jobs=1,
                device_type="cpu",
                verbosity=-1,
            )
            fit_kwargs: dict[str, Any] = {}
            if self.config.use_validation_early_stopping:
                validation = self._development_validation_rows(split_result, horizon_days)
                if validation is not None:
                    validation_x, validation_y = validation
                    fit_kwargs["eval_X"] = np.asarray(validation_x, dtype=float)
                    fit_kwargs["eval_y"] = np.asarray(validation_y, dtype=int)
                    fit_kwargs["callbacks"] = [
                        lightgbm.early_stopping(
                            self.config.early_stopping_rounds,
                            verbose=False,
                        )
                    ]
            model.fit(feature_rows, target, **fit_kwargs)
        except (TypeError, ValueError, RuntimeError) as exc:
            self._fit_result = result(BaselineStatus.NOT_READY, f"fit failed: {exc}")
            return self._fit_result

        self._model = model
        self._fit_result = result(BaselineStatus.READY, metadata=metadata)
        return self._fit_result

    def _development_validation_rows(
        self, split_result: TemporalSplitResult, horizon_days: HorizonDays
    ) -> tuple[list[list[float]], list[int]] | None:
        validation = split_result.partition(SplitName.VALIDATION)
        usable_ids = set(
            validation.supervised_snapshot_ids_by_horizon.get(horizon_days, ())
        )
        records = tuple(
            record for record in validation.snapshots if record.stable_snapshot_id in usable_ids
        )
        if not records:
            return None
        labels = {
            record.stable_snapshot_id: next(
                label for label in record.labels if label.horizon_days == horizon_days
            )
            for record in records
        }
        return (
            [_numeric_row(self.vectorizer.row(record.feature_snapshot)) for record in records],
            [int(labels[record.stable_snapshot_id].label) for record in records],
        )

    def predict(
        self,
        snapshot: Any,
        *,
        horizon_days: HorizonDays | None = None,
    ) -> BaselinePrediction:
        """Return a raw, explicitly uncalibrated probability."""

        selected_horizon = horizon_days or self._horizon_days or 30
        _validate_horizon(selected_horizon)
        if self._fit_result is None:
            status = BaselineStatus.UNFITTED
            reason = "a successful horizon-specific fit is required"
        elif self._fit_result.status is not BaselineStatus.READY:
            status = BaselineStatus.NOT_READY
            reason = self._fit_result.reason or "model is not ready"
        else:
            status = BaselineStatus.READY
            reason = None
        if status is not BaselineStatus.READY:
            return BaselinePrediction(
                horizon_days=selected_horizon,
                status=status,
                baseline_version=self.config.model_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.model_version,
                reasons=(reason,),
            )
        metadata = self.metadata
        if metadata is None or selected_horizon != metadata.prediction_horizon_days:
            return BaselinePrediction(
                horizon_days=selected_horizon,
                status=BaselineStatus.NOT_READY,
                baseline_version=self.config.model_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.model_version,
                reasons=("model horizon metadata does not match requested horizon",),
            )
        if snapshot.feature_version != metadata.feature_version:
            return BaselinePrediction(
                horizon_days=selected_horizon,
                status=BaselineStatus.NOT_READY,
                baseline_version=self.config.model_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.model_version,
                reasons=("snapshot feature_version does not match model metadata",),
            )
        if metadata.tenant_scope is not None and snapshot.tenant_id != metadata.tenant_scope:
            return BaselinePrediction(
                horizon_days=selected_horizon,
                status=BaselineStatus.NOT_READY,
                baseline_version=self.config.model_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.model_version,
                reasons=("snapshot tenant is outside the fitted model tenant scope",),
            )
        assert self._model is not None
        import numpy as np

        probability = float(
            self._model.predict_proba(
                np.asarray([_numeric_row(self.vectorizer.row(snapshot))], dtype=float),
            )[0][1]
        )
        return BaselinePrediction(
            horizon_days=selected_horizon,
            status=BaselineStatus.READY,
            score=probability,
            score_kind=BaselineScoreKind.UNCALIBRATED_PROBABILITY,
            baseline_version=self.config.model_version,
            feature_version=snapshot.feature_version,
            model_version=self.config.model_version,
            reasons=("raw LightGBM probability; calibration has not been applied",),
        )

    def save(self, path: str | Path) -> None:
        """Atomically save a trusted internal artifact."""

        if self._model is None or self._fit_result is None or self._fit_result.status is not BaselineStatus.READY:
            raise RuntimeError("only a successfully fitted model can be saved")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "artifact_type": "retainiq_lightgbm_model",
            "artifact_version": 1,
            "config": self.config,
            "vectorizer": self.vectorizer,
            "model": self._model,
            "fit_result": self._fit_result,
            "horizon_days": self._horizon_days,
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
    def load(
        cls, path: str | Path, *, trusted_root: str | Path
    ) -> "LightGBMModel":
        """Load only a validated trusted internal ``.pkl`` artifact."""

        root = Path(trusted_root).resolve()
        candidate = Path(path).resolve()
        if candidate.suffix.lower() != ".pkl":
            raise ValueError("LightGBM artifacts must use the .pkl extension")
        if not candidate.is_file() or root not in candidate.parents:
            raise ValueError("artifact path is outside the validated trusted root")
        with candidate.open("rb") as handle:
            artifact = pickle.load(handle)
        if not isinstance(artifact, Mapping):
            raise ValueError("malformed LightGBM artifact")
        if artifact.get("artifact_type") != "retainiq_lightgbm_model":
            raise ValueError("unsupported LightGBM artifact type")
        if artifact.get("artifact_version") != 1:
            raise ValueError("unsupported LightGBM artifact version")
        required = {"config", "vectorizer", "model", "fit_result", "horizon_days"}
        if not required.issubset(artifact):
            raise ValueError("LightGBM artifact is missing required metadata")
        fit_result = artifact["fit_result"]
        if not isinstance(fit_result, LightGBMFitResult) or fit_result.metadata is None:
            raise ValueError("LightGBM artifact has incompatible fit metadata")
        if fit_result.status is not BaselineStatus.READY:
            raise ValueError("LightGBM artifact does not contain a ready fit")
        if fit_result.metadata.model_family != "lightgbm":
            raise ValueError("LightGBM artifact has incompatible model family")
        if fit_result.metadata.calibration_status != "not_calibrated":
            raise ValueError("LightGBM artifact has unsupported calibration status")

        config = artifact["config"]
        vectorizer = artifact["vectorizer"]
        estimator = artifact["model"]
        horizon = artifact["horizon_days"]
        metadata = fit_result.metadata
        if not isinstance(config, LightGBMConfig):
            raise ValueError("LightGBM artifact has incompatible configuration")
        if not isinstance(vectorizer, FeatureVectorizer):
            raise ValueError("LightGBM artifact has incompatible vectorizer")
        if not callable(getattr(estimator, "predict_proba", None)):
            raise ValueError("LightGBM artifact has incompatible estimator")
        if horizon not in SUPPORTED_HORIZONS or horizon != fit_result.horizon_days:
            raise ValueError("LightGBM artifact horizon does not match fit metadata")
        if metadata.prediction_horizon_days != horizon:
            raise ValueError("LightGBM artifact horizon does not match model metadata")
        if (
            metadata.model_version != config.model_version
            or metadata.feature_version != config.feature_version
            or metadata.tenant_scope != config.tenant_id
            or metadata.feature_names != vectorizer.allowlist
            or vectorizer.allowlist != config.allowlist
        ):
            raise ValueError("LightGBM artifact configuration does not match fit metadata")
        if (
            config.label_policy_version is not None
            and metadata.label_policy_version != config.label_policy_version
        ):
            raise ValueError("LightGBM artifact label policy does not match configuration")
        if (
            config.dataset_provenance is not None
            and metadata.training_dataset_provenance != config.dataset_provenance
        ):
            raise ValueError("LightGBM artifact dataset provenance does not match configuration")
        fitted_feature_count = getattr(estimator, "n_features_in_", len(metadata.feature_names))
        if fitted_feature_count != len(metadata.feature_names):
            raise ValueError("LightGBM artifact estimator feature count does not match metadata")

        model = cls(config, vectorizer=vectorizer)
        model._model = estimator
        model._fit_result = fit_result
        model._horizon_days = horizon
        return model


def _numeric_row(row: tuple[float | None, ...]) -> list[float]:
    return [float("nan") if value is None else float(value) for value in row]


def _validate_horizon(horizon_days: int) -> None:
    if horizon_days not in SUPPORTED_HORIZONS:
        raise ValueError(f"unsupported horizon: {horizon_days}")


__all__ = [
    "LIGHTGBM_AVAILABLE",
    "LIGHTGBM_VERSION",
    "LightGBMConfig",
    "LightGBMFitResult",
    "LightGBMModel",
    "LightGBMModelMetadata",
]
