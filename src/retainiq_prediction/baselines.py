"""Transparent and logistic-regression baseline prediction components.

The rule baseline produces a deterministic ranking score, not a probability.
The logistic baseline is an optional scikit-learn implementation and produces
an explicitly uncalibrated probability.  Neither baseline populates the
canonical production ``PredictionOutput`` contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
import pickle
import tempfile
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .feature_builder import FeatureSnapshot
from .label_builder import SUPPORTED_HORIZONS
from .temporal_splits import SnapshotRecord, SplitName, TemporalSplitResult


HorizonDays = Literal[7, 14, 30]


class BaselineStatus(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"
    UNFITTED = "unfitted"


class BaselineScoreKind(str, Enum):
    RANKING_SCORE = "ranking_score"
    UNCALIBRATED_PROBABILITY = "uncalibrated_probability"


class _BaselineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BaselinePrediction(_BaselineModel):
    """A baseline result, deliberately separate from ``PredictionOutput``."""

    horizon_days: HorizonDays
    status: BaselineStatus
    score: float | None = None
    score_kind: BaselineScoreKind | None = None
    alert: bool | None = None
    baseline_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_score_state(self) -> "BaselinePrediction":
        if self.score is None and self.score_kind is not None:
            raise ValueError("score_kind requires a score")
        if self.score is not None and self.score_kind is None:
            raise ValueError("score requires score_kind")
        if self.status is not BaselineStatus.READY and self.score is not None:
            raise ValueError("not-ready predictions cannot expose a score")
        return self


class BaselineFitResult(_BaselineModel):
    """Auditable status and metadata from a horizon-specific fit attempt."""

    horizon_days: HorizonDays
    status: BaselineStatus
    training_snapshot_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    baseline_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    feature_names: tuple[str, ...] = ()
    preprocessing_feature_names: tuple[str, ...] = ()
    reason: str | None = None
    dependency_version: str | None = None


@dataclass(frozen=True)
class RuleBaselineConfig:
    """Operational heuristic settings, not scientifically validated values."""

    baseline_version: str = "rule_baseline_v1"
    feature_version: str = "features_personalized_baseline_v1"
    days_since_last_session_threshold: int = 14
    usage_decline_ratio_threshold: float = 0.5
    payment_failures_threshold: int = 1
    inactivity_weight: float = 40.0
    usage_decline_weight: float = 35.0
    payment_failure_weight: float = 15.0
    alert_score_threshold: float = 50.0
    require_usage_evidence_for_alert: bool = True

    def __post_init__(self) -> None:
        if not self.baseline_version.strip() or not self.feature_version.strip():
            raise ValueError("baseline and feature versions must be non-empty")
        if self.days_since_last_session_threshold < 0:
            raise ValueError("days_since_last_session_threshold must not be negative")
        if not 0 <= self.usage_decline_ratio_threshold <= 1:
            raise ValueError("usage_decline_ratio_threshold must be between 0 and 1")
        if self.payment_failures_threshold < 1:
            raise ValueError("payment_failures_threshold must be positive")
        if any(
            weight < 0
            for weight in (
                self.inactivity_weight,
                self.usage_decline_weight,
                self.payment_failure_weight,
            )
        ):
            raise ValueError("rule weights must not be negative")
        if self.alert_score_threshold < 0:
            raise ValueError("alert_score_threshold must not be negative")


class RuleBasedBaseline:
    """Return a transparent point-in-time ranking score and optional alert."""

    def __init__(self, config: RuleBaselineConfig | None = None) -> None:
        self.config = config or RuleBaselineConfig()

    def fit(self, *, horizon_days: HorizonDays = 30) -> BaselineFitResult:
        """Return ready metadata; the rule baseline has no fitted parameters."""

        _validate_horizon(horizon_days)
        return BaselineFitResult(
            horizon_days=horizon_days,
            status=BaselineStatus.READY,
            training_snapshot_count=0,
            positive_count=0,
            negative_count=0,
            baseline_version=self.config.baseline_version,
            feature_version=self.config.feature_version,
            reason="Deterministic heuristic; no training data or fitted parameters used.",
        )

    def predict(
        self,
        snapshot: FeatureSnapshot,
        *,
        horizon_days: HorizonDays = 30,
        payment_failures: int | None = None,
    ) -> BaselinePrediction:
        """Score only cutoff-safe values already present in ``snapshot``.

        ``payment_failures`` is an optional point-in-time billing feature from
        the caller's canonical adapter.  It is a risk signal only and never a
        churn label.  ``None`` means unknown, not zero.
        """

        _validate_horizon(horizon_days)
        if payment_failures is not None and payment_failures < 0:
            raise ValueError("payment_failures must not be negative")

        values = snapshot.feature_values
        score = 0.0
        reasons: list[str] = []
        usage_evidence = False

        if values.days_since_last_observed_session is not None:
            usage_evidence = True
            if (
                values.days_since_last_observed_session
                >= self.config.days_since_last_session_threshold
            ):
                score += self.config.inactivity_weight
                reasons.append("inactivity threshold reached")
        else:
            reasons.append("days since last session is unknown")

        if values.recent_to_baseline_usage_ratio is not None:
            usage_evidence = True
            if (
                values.recent_to_baseline_usage_ratio
                <= self.config.usage_decline_ratio_threshold
            ):
                score += self.config.usage_decline_weight
                reasons.append("recent usage decline threshold reached")
        else:
            reasons.append("personal usage baseline is unavailable")

        if payment_failures is not None:
            if payment_failures >= self.config.payment_failures_threshold:
                score += self.config.payment_failure_weight
                reasons.append("point-in-time payment-failure threshold reached")
            else:
                reasons.append("point-in-time payment failures below threshold")
        else:
            reasons.append("payment-failure count is unknown")

        known_signal = usage_evidence or payment_failures is not None
        if not known_signal:
            return BaselinePrediction(
                horizon_days=horizon_days,
                status=BaselineStatus.NOT_READY,
                baseline_version=self.config.baseline_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.baseline_version,
                reasons=tuple(reasons + ["no point-in-time risk signal is available"]),
            )

        alert = score >= self.config.alert_score_threshold
        if self.config.require_usage_evidence_for_alert and not usage_evidence:
            alert = False
            reasons.append("alert suppressed because usage evidence is unavailable")

        if not usage_evidence:
            reasons.append("missing usage is not treated as zero usage or confirmed inactivity")

        return BaselinePrediction(
            horizon_days=horizon_days,
            status=BaselineStatus.READY,
            score=score,
            score_kind=BaselineScoreKind.RANKING_SCORE,
            alert=alert,
            baseline_version=self.config.baseline_version,
            feature_version=snapshot.feature_version,
            model_version=self.config.baseline_version,
            reasons=tuple(reasons),
        )


MODEL_FEATURE_ALLOWLIST: tuple[str, ...] = (
    "sessions_prev_7d",
    "sessions_prev_30d",
    "days_since_last_observed_session",
    "recent_usage_trend",
    "observed_weeks",
    "valid_usage_history",
    "historical_avg_sessions_per_week",
    "recent_avg_sessions_per_week",
    "absolute_usage_deviation",
    "percentage_usage_deviation",
    "recent_to_baseline_usage_ratio",
    "historical_weekly_usage_variability",
)


@dataclass(frozen=True)
class FeatureVectorizer:
    """Explicit numeric allowlist shared by each horizon model."""

    allowlist: tuple[str, ...] = MODEL_FEATURE_ALLOWLIST

    def __post_init__(self) -> None:
        if not self.allowlist:
            raise ValueError("feature allowlist must not be empty")
        unknown = set(self.allowlist) - set(MODEL_FEATURE_ALLOWLIST)
        if unknown:
            raise ValueError(f"unsupported modeling features: {sorted(unknown)}")
        if len(set(self.allowlist)) != len(self.allowlist):
            raise ValueError("feature allowlist must not contain duplicates")

    def row(self, snapshot: FeatureSnapshot) -> tuple[float | None, ...]:
        values = snapshot.feature_values
        result: list[float | None] = []
        for name in self.allowlist:
            value = getattr(values, name)
            if isinstance(value, bool):
                result.append(float(value))
            elif value is None:
                result.append(None)
            elif isinstance(value, (int, float)):
                result.append(float(value))
            else:
                raise TypeError(f"model feature {name} is not numeric")
        return tuple(result)


@dataclass(frozen=True)
class LogisticBaselineConfig:
    baseline_version: str = "logistic_baseline_v1"
    feature_version: str = "features_personalized_baseline_v1"
    random_state: int = 42
    max_iter: int = 1000
    class_weight: str | None = None
    minimum_samples_per_horizon: int = 2
    allowlist: tuple[str, ...] = MODEL_FEATURE_ALLOWLIST

    def __post_init__(self) -> None:
        if not self.baseline_version.strip() or not self.feature_version.strip():
            raise ValueError("baseline and feature versions must be non-empty")
        if self.max_iter < 1:
            raise ValueError("max_iter must be positive")
        if self.class_weight not in {None, "balanced"}:
            raise ValueError("class_weight must be None or 'balanced'")
        if self.minimum_samples_per_horizon < 2:
            raise ValueError("minimum_samples_per_horizon must be at least 2")


try:  # Optional dependency: package import must work without scikit-learn.
    import sklearn
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
    SKLEARN_VERSION: str | None = sklearn.__version__
    _SKLEARN_IMPORT_ERROR: str | None = None
except ImportError as exc:  # pragma: no cover - environment-dependent branch
    SKLEARN_AVAILABLE = False
    SKLEARN_VERSION = None
    _SKLEARN_IMPORT_ERROR = str(exc)
    SimpleImputer = None  # type: ignore[assignment,misc]
    LogisticRegression = None  # type: ignore[assignment,misc]
    Pipeline = None  # type: ignore[assignment,misc]
    StandardScaler = None  # type: ignore[assignment,misc]


class LogisticRegressionBaseline:
    """Independent horizon model using train-fitted imputation and scaling."""

    def __init__(
        self,
        config: LogisticBaselineConfig | None = None,
        *,
        vectorizer: FeatureVectorizer | None = None,
    ) -> None:
        self.config = config or LogisticBaselineConfig()
        self.vectorizer = vectorizer or FeatureVectorizer(self.config.allowlist)
        self._pipeline: Any = None
        self._fit_result: BaselineFitResult | None = None
        self._horizon_days: HorizonDays | None = None

    @property
    def fit_result(self) -> BaselineFitResult | None:
        return self._fit_result

    def fit(
        self,
        split_result: TemporalSplitResult,
        *,
        horizon_days: HorizonDays,
    ) -> BaselineFitResult:
        """Fit from the splitter's TRAIN mask only.

        Validation, calibration, and test snapshots are intentionally not
        inspected by this method.  The splitter has already applied label
        maturity, eligibility, and horizon-specific inclusion rules.
        """

        _validate_horizon(horizon_days)
        train = split_result.partition(SplitName.TRAIN)
        supervised_ids = set(train.supervised_snapshot_ids_by_horizon.get(horizon_days, ()))
        records = tuple(
            record for record in train.snapshots if record.stable_snapshot_id in supervised_ids
        )
        labels = {
            record.stable_snapshot_id: next(
                label for label in record.labels if label.horizon_days == horizon_days
            )
            for record in records
        }
        positive_count = sum(labels[item.stable_snapshot_id].label == 1 for item in records)
        negative_count = sum(labels[item.stable_snapshot_id].label == 0 for item in records)

        def result(status: BaselineStatus, reason: str | None = None) -> BaselineFitResult:
            return BaselineFitResult(
                horizon_days=horizon_days,
                status=status,
                training_snapshot_count=len(records),
                positive_count=positive_count,
                negative_count=negative_count,
                baseline_version=self.config.baseline_version,
                feature_version=self.config.feature_version,
                feature_names=self.vectorizer.allowlist,
                reason=reason,
                dependency_version=SKLEARN_VERSION,
            )

        self._pipeline = None
        self._horizon_days = horizon_days
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
        if not SKLEARN_AVAILABLE:
            self._fit_result = result(
                BaselineStatus.NOT_READY,
                f"scikit-learn is unavailable: {_SKLEARN_IMPORT_ERROR}",
            )
            return self._fit_result

        x = [self.vectorizer.row(record.feature_snapshot) for record in records]
        y = [int(labels[record.stable_snapshot_id].label) for record in records]
        assert SimpleImputer is not None
        assert LogisticRegression is not None
        assert Pipeline is not None
        assert StandardScaler is not None
        try:
            pipeline = Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median",
                            add_indicator=True,
                            keep_empty_features=True,
                        ),
                    ),
                    ("scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(
                            class_weight=self.config.class_weight,
                            max_iter=self.config.max_iter,
                            random_state=self.config.random_state,
                        ),
                    ),
                ]
            )
            pipeline.fit(x, y)
        except (TypeError, ValueError) as exc:
            self._fit_result = result(BaselineStatus.NOT_READY, f"fit failed: {exc}")
            return self._fit_result

        preprocessing_names: tuple[str, ...] = ()
        try:
            names = pipeline[:-1].get_feature_names_out(self.vectorizer.allowlist)
            preprocessing_names = tuple(str(name) for name in names)
        except (AttributeError, TypeError):
            preprocessing_names = self.vectorizer.allowlist
        self._pipeline = pipeline
        self._fit_result = result(BaselineStatus.READY)
        self._fit_result = self._fit_result.model_copy(
            update={"preprocessing_feature_names": preprocessing_names}
        )
        return self._fit_result

    def predict(
        self,
        snapshot: FeatureSnapshot,
        *,
        horizon_days: HorizonDays | None = None,
    ) -> BaselinePrediction:
        """Return an uncalibrated probability after a successful fit."""

        selected_horizon = horizon_days or self._horizon_days
        if selected_horizon is None:
            selected_horizon = 30
        _validate_horizon(selected_horizon)
        fit_result = self._fit_result
        if fit_result is None or fit_result.status is not BaselineStatus.READY:
            return BaselinePrediction(
                horizon_days=selected_horizon,
                status=BaselineStatus.UNFITTED,
                baseline_version=self.config.baseline_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.baseline_version,
                reasons=("a successful horizon-specific fit is required",),
            )
        if snapshot.feature_version != self.config.feature_version:
            return BaselinePrediction(
                horizon_days=selected_horizon,
                status=BaselineStatus.NOT_READY,
                baseline_version=self.config.baseline_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.baseline_version,
                reasons=("snapshot feature_version does not match fitted model",),
            )
        if selected_horizon != self._horizon_days:
            return BaselinePrediction(
                horizon_days=selected_horizon,
                status=BaselineStatus.NOT_READY,
                baseline_version=self.config.baseline_version,
                feature_version=snapshot.feature_version,
                model_version=self.config.baseline_version,
                reasons=("model was fitted for a different horizon",),
            )
        assert self._pipeline is not None
        probability = float(self._pipeline.predict_proba([self.vectorizer.row(snapshot)])[0][1])
        return BaselinePrediction(
            horizon_days=selected_horizon,
            status=BaselineStatus.READY,
            score=probability,
            score_kind=BaselineScoreKind.UNCALIBRATED_PROBABILITY,
            baseline_version=self.config.baseline_version,
            feature_version=snapshot.feature_version,
            model_version=self.config.baseline_version,
            reasons=("raw logistic probability; calibration has not been applied",),
        )

    def save(self, path: str | Path) -> None:
        """Atomically save a fitted artifact for local trusted use only."""

        if self._pipeline is None or self._fit_result is None or self._fit_result.status is not BaselineStatus.READY:
            raise RuntimeError("only a successfully fitted baseline can be saved")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "artifact_type": "retainiq_logistic_baseline",
            "artifact_version": 1,
            "config": self.config,
            "vectorizer": self.vectorizer,
            "pipeline": self._pipeline,
            "fit_result": self._fit_result,
            "horizon_days": self._horizon_days,
        }
        handle = tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False
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
    ) -> "LogisticRegressionBaseline":
        """Load an artifact previously saved by this package.

        Pickle is executable serialization.  Callers must load only trusted
        local artifacts produced by this implementation.  ``trusted_root`` is
        mandatory so a caller cannot pass an arbitrary path without first
        selecting and validating a trusted artifact directory.  This is not a
        public untrusted-upload or model-registry endpoint.
        """

        root = Path(trusted_root).resolve()
        candidate = Path(path).resolve()
        if candidate.suffix.lower() != ".pkl":
            raise ValueError("baseline artifacts must use the .pkl extension")
        if not candidate.is_file() or root not in candidate.parents:
            raise ValueError("artifact path is outside the validated trusted root")
        with candidate.open("rb") as handle:
            artifact = pickle.load(handle)
        if not isinstance(artifact, Mapping) or artifact.get("artifact_type") != "retainiq_logistic_baseline":
            raise ValueError("unsupported logistic baseline artifact")
        if artifact.get("artifact_version") != 1:
            raise ValueError("unsupported logistic baseline artifact version")
        model = cls(artifact["config"], vectorizer=artifact["vectorizer"])
        model._pipeline = artifact["pipeline"]
        model._fit_result = artifact["fit_result"]
        model._horizon_days = artifact["horizon_days"]
        return model


def _validate_horizon(horizon_days: int) -> None:
    if horizon_days not in SUPPORTED_HORIZONS:
        raise ValueError(f"unsupported horizon: {horizon_days}")


__all__ = [
    "BaselineFitResult",
    "BaselinePrediction",
    "BaselineScoreKind",
    "BaselineStatus",
    "FeatureVectorizer",
    "LogisticBaselineConfig",
    "LogisticRegressionBaseline",
    "MODEL_FEATURE_ALLOWLIST",
    "RuleBasedBaseline",
    "RuleBaselineConfig",
    "SKLEARN_AVAILABLE",
    "SKLEARN_VERSION",
]
