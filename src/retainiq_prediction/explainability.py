"""Horizon-specific SHAP explanations for the internal LightGBM candidates.

The explanations in this module describe the fitted LightGBM raw margin
(binary log-odds).  They do not explain calibrated or horizon-coherence-
adjusted probabilities and do not make causal or treatment-effect claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from typing import Any, Iterable, Literal, Sequence, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from .baselines import BaselineStatus, MODEL_FEATURE_ALLOWLIST
from .contracts import PredictionStatus
from .feature_builder import FeatureSnapshot
from .lightgbm_model import LightGBMModel
from .reliability import PredictionReadinessAssessment


HorizonDays = Literal[7, 14, 30]


class ExplanationStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class ExplanationReasonCode(str, Enum):
    SHAP_DEPENDENCY_UNAVAILABLE = "SHAP_DEPENDENCY_UNAVAILABLE"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    MODEL_METADATA_MISSING = "MODEL_METADATA_MISSING"
    MODEL_ARTIFACT_INCOMPATIBLE = "MODEL_ARTIFACT_INCOMPATIBLE"
    MODEL_VERSION_MISMATCH = "MODEL_VERSION_MISMATCH"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    FEATURE_ORDER_MISMATCH = "FEATURE_ORDER_MISMATCH"
    FEATURE_INPUT_MISSING = "FEATURE_INPUT_MISSING"
    FEATURE_INPUT_INVALID = "FEATURE_INPUT_INVALID"
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"
    CUSTOMER_SCOPE_MISMATCH = "CUSTOMER_SCOPE_MISMATCH"
    PREDICTION_NOT_SCORABLE = "PREDICTION_NOT_SCORABLE"
    READINESS_NOT_CONFIRMED = "READINESS_NOT_CONFIRMED"
    SHAP_OUTPUT_UNSUPPORTED = "SHAP_OUTPUT_UNSUPPORTED"
    SHAP_ADDITIVITY_FAILED = "SHAP_ADDITIVITY_FAILED"
    NO_INFORMATIVE_CONTRIBUTIONS = "NO_INFORMATIVE_CONTRIBUTIONS"


class ContributionDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ExplainedOutputSpace(str, Enum):
    RAW_LIGHTGBM_MARGIN_LOG_ODDS = "raw_lightgbm_margin_log_odds"


class _ExplanationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeatureContribution(_ExplanationModel):
    """One full-fidelity signed contribution in model feature order."""

    feature_name: str = Field(min_length=1)
    original_value: float | int | bool | None = None
    model_input_value: float | None = None
    was_missing: bool = False
    missingness_indicator: float | None = None
    shap_value: float
    direction: ContributionDirection
    magnitude: float = Field(ge=0.0)
    source_feature_refs: tuple[str, ...] = ()

    @field_validator("shap_value", "magnitude", "model_input_value", "missingness_indicator")
    @classmethod
    def require_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("explanation values must be finite")
        return value


class ExplanationResult(_ExplanationModel):
    """Versioned explanation result, including unavailable outcomes."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    horizon_days: HorizonDays
    model_version: str | None = Field(default=None, min_length=1)
    feature_version: str | None = Field(default=None, min_length=1)
    explanation_method: str = Field(min_length=1)
    explanation_version: str = Field(min_length=1)
    explanation_status: ExplanationStatus
    explained_output_space: ExplainedOutputSpace | None = None
    expected_base_value: float | None = None
    actual_explained_model_output: float | None = None
    raw_model_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    additivity_error: float | None = Field(default=None, ge=0.0)
    additivity_tolerance: float | None = Field(default=None, gt=0.0)
    feature_contributions: tuple[FeatureContribution, ...] = ()
    positive_contributors: tuple[FeatureContribution, ...] = ()
    negative_contributors: tuple[FeatureContribution, ...] = ()
    human_readable_explanations: tuple[str, ...] = ()
    prediction_status: PredictionStatus | None = None
    limitations: tuple[str, ...] = ()
    reason_codes: tuple[ExplanationReasonCode, ...] = ()

    @field_validator(
        "expected_base_value",
        "actual_explained_model_output",
        "additivity_error",
        "additivity_tolerance",
    )
    @classmethod
    def require_finite_optional(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("explanation outputs must be finite")
        return value


@dataclass(frozen=True)
class ExplainabilityConfig:
    explanation_version: str = "shap_tree_v1"
    top_k: int = 3
    additivity_tolerance: float = 1e-5

    def __post_init__(self) -> None:
        if not self.explanation_version.strip():
            raise ValueError("explanation_version must be non-empty")
        if self.top_k < 1:
            raise ValueError("top_k must be positive")
        if not math.isfinite(self.additivity_tolerance) or self.additivity_tolerance <= 0:
            raise ValueError("additivity_tolerance must be finite and positive")


try:  # Optional dependency; the package remains importable without SHAP.
    import numpy as np
    import shap

    SHAP_AVAILABLE = True
    SHAP_VERSION: str | None = shap.__version__
    _SHAP_IMPORT_ERROR: str | None = None
except ImportError as exc:  # pragma: no cover - environment-dependent branch
    SHAP_AVAILABLE = False
    SHAP_VERSION = None
    _SHAP_IMPORT_ERROR = str(exc)
    np = None  # type: ignore[assignment]
    shap = None  # type: ignore[assignment]


T = TypeVar("T")


def _unique(values: Iterable[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(values))


def _finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _direction(value: float) -> ContributionDirection:
    if value > 0:
        return ContributionDirection.POSITIVE
    if value < 0:
        return ContributionDirection.NEGATIVE
    return ContributionDirection.NEUTRAL


def _select_class_values(values: Any, feature_count: int) -> Any:
    """Normalize SHAP's version-dependent binary output to class 1, one row."""

    assert np is not None
    if isinstance(values, list):
        if len(values) == 2:
            values = values[1]
        elif len(values) == 1:
            values = values[0]
        else:
            raise ValueError("unsupported SHAP class output shape")
    array = np.asarray(values, dtype=float)
    if array.ndim == 1 and array.shape[0] == feature_count:
        return array
    if array.ndim == 2 and array.shape == (1, feature_count):
        return array[0]
    if array.ndim == 3:
        if array.shape[0] == 1 and array.shape[1] == feature_count and array.shape[2] >= 2:
            return array[0, :, 1]
        if array.shape[0] == 1 and array.shape[2] == feature_count and array.shape[1] >= 2:
            return array[0, 1, :]
        if array.shape[0] >= 2 and array.shape[1] == 1 and array.shape[2] == feature_count:
            return array[1, 0, :]
        if array.shape[0] >= 2 and array.shape[1] == feature_count and array.shape[2] == 1:
            return array[1, :, 0]
    raise ValueError(f"unsupported SHAP output shape: {array.shape}")


def _select_expected_value(value: Any) -> float:
    assert np is not None
    if isinstance(value, list):
        if len(value) == 2:
            value = value[1]
        elif len(value) == 1:
            value = value[0]
    array = np.asarray(value, dtype=float).reshape(-1)
    if array.size == 1:
        return _finite(float(array[0]), "expected base value")
    if array.size == 2:
        return _finite(float(array[1]), "expected base value")
    raise ValueError("unsupported SHAP expected-value shape")


def _raw_model_probability(trained_model: Any, model_input: Any) -> float:
    probability = float(trained_model.predict_proba(model_input)[0][1])
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("LightGBM returned an invalid raw probability")
    return probability


class LightGBMExplainer:
    """Explain one fitted LightGBM horizon at a time."""

    def __init__(self, config: ExplainabilityConfig | None = None) -> None:
        self.config = config or ExplainabilityConfig()

    def explain(
        self,
        model: LightGBMModel,
        snapshot: FeatureSnapshot,
        *,
        horizon_days: HorizonDays | None = None,
        prediction_status: PredictionStatus = PredictionStatus.SCORED,
        expected_model_version: str | None = None,
        expected_feature_version: str | None = None,
        expected_tenant_id: str | None = None,
        expected_customer_id: str | None = None,
        readiness: PredictionReadinessAssessment | None = None,
        top_k: int | None = None,
    ) -> ExplanationResult:
        selected_horizon = horizon_days or (
            model.metadata.prediction_horizon_days if model.metadata is not None else 30
        )
        if selected_horizon not in (7, 14, 30):
            raise ValueError(f"unsupported horizon: {selected_horizon}")
        metadata = model.metadata
        common = {
            "tenant_id": snapshot.tenant_id,
            "customer_id": snapshot.customer_id,
            "as_of": snapshot.as_of,
            "horizon_days": selected_horizon,
            "model_version": metadata.model_version if metadata else None,
            "feature_version": metadata.feature_version if metadata else snapshot.feature_version,
            "explanation_method": "shap_tree_explainer",
            "explanation_version": self.config.explanation_version,
            "prediction_status": prediction_status,
        }
        if prediction_status is not PredictionStatus.SCORED:
            return self._unavailable(
                common,
                ExplanationReasonCode.PREDICTION_NOT_SCORABLE,
                "Explanations are unavailable for abstained or non-eligible predictions.",
            )
        if readiness is not None and (
            not readiness.scoring_allowed
            or not readiness.model_artifacts_ready
            or readiness.prediction_status not in (None, PredictionStatus.SCORED)
        ):
            return self._unavailable(
                common,
                ExplanationReasonCode.READINESS_NOT_CONFIRMED,
                "Production explanations require a scoring-allowed readiness assessment with ready model artifacts.",
            )
        if not SHAP_AVAILABLE:
            return self._unavailable(
                common,
                ExplanationReasonCode.SHAP_DEPENDENCY_UNAVAILABLE,
                f"SHAP is unavailable: {_SHAP_IMPORT_ERROR}",
            )
        if not isinstance(model, LightGBMModel):
            return self._unavailable(
                common,
                ExplanationReasonCode.MODEL_ARTIFACT_INCOMPATIBLE,
                "A compatible LightGBMModel artifact is required.",
            )
        if model.fit_result is None or model.fit_result.status is not BaselineStatus.READY:
            return self._unavailable(
                common,
                ExplanationReasonCode.MODEL_NOT_READY,
                "A successful fitted LightGBM model is required.",
            )
        if metadata is None:
            return self._unavailable(
                common,
                ExplanationReasonCode.MODEL_METADATA_MISSING,
                "The fitted model is missing compatibility metadata.",
            )
        if selected_horizon != metadata.prediction_horizon_days:
            return self._unavailable(
                common,
                ExplanationReasonCode.MODEL_ARTIFACT_INCOMPATIBLE,
                "The selected horizon does not match the fitted model metadata.",
            )
        if expected_model_version is not None and metadata.model_version != expected_model_version:
            return self._unavailable(
                common,
                ExplanationReasonCode.MODEL_VERSION_MISMATCH,
                "The requested model version does not match the fitted artifact.",
            )
        if expected_feature_version is not None and metadata.feature_version != expected_feature_version:
            return self._unavailable(
                common,
                ExplanationReasonCode.FEATURE_VERSION_MISMATCH,
                "The requested feature version does not match the fitted artifact.",
            )
        if snapshot.feature_version != metadata.feature_version:
            return self._unavailable(
                common,
                ExplanationReasonCode.FEATURE_VERSION_MISMATCH,
                "The snapshot feature version does not match the fitted artifact.",
            )
        if expected_tenant_id is not None and snapshot.tenant_id != expected_tenant_id:
            return self._unavailable(
                common,
                ExplanationReasonCode.TENANT_SCOPE_MISMATCH,
                "The snapshot tenant does not match the requested tenant scope.",
            )
        if expected_customer_id is not None and snapshot.customer_id != expected_customer_id:
            return self._unavailable(
                common,
                ExplanationReasonCode.CUSTOMER_SCOPE_MISMATCH,
                "The snapshot customer does not match the requested customer scope.",
            )
        if metadata.tenant_scope is not None and snapshot.tenant_id != metadata.tenant_scope:
            return self._unavailable(
                common,
                ExplanationReasonCode.TENANT_SCOPE_MISMATCH,
                "The snapshot tenant is outside the fitted model scope.",
            )

        allowlist = tuple(model.vectorizer.allowlist)
        if not allowlist or any(name not in MODEL_FEATURE_ALLOWLIST for name in allowlist):
            return self._unavailable(
                common,
                ExplanationReasonCode.FEATURE_ORDER_MISMATCH,
                "The vectorizer uses a feature outside the approved model allowlist.",
            )
        if tuple(metadata.feature_names) != allowlist:
            return self._unavailable(
                common,
                ExplanationReasonCode.FEATURE_ORDER_MISMATCH,
                "Artifact feature names do not match the inference vectorizer order.",
            )
        model_row = model.vectorizer.row(snapshot)
        if any(value is None for value in model_row):
            return self._unavailable(
                common,
                ExplanationReasonCode.FEATURE_INPUT_MISSING,
                "A required model feature is missing; no explanation was fabricated.",
            )
        if any(not math.isfinite(float(value)) for value in model_row if value is not None):
            return self._unavailable(
                common,
                ExplanationReasonCode.FEATURE_INPUT_INVALID,
                "A model feature input is non-finite.",
            )
        assert np is not None
        model_input = np.asarray([[float(value) for value in model_row]], dtype=float)
        trained_model = getattr(model, "_model", None)
        if trained_model is None:
            return self._unavailable(
                common,
                ExplanationReasonCode.MODEL_ARTIFACT_INCOMPATIBLE,
                "The fitted LightGBM estimator is unavailable.",
            )
        try:
            actual_output = float(trained_model.predict(model_input, raw_score=True)[0])
            raw_probability = _raw_model_probability(trained_model, model_input)
            explainer = shap.TreeExplainer(trained_model, model_output="raw")
            shap_output = explainer.shap_values(model_input, check_additivity=False)
            values = _select_class_values(shap_output, len(allowlist))
            expected = _select_expected_value(explainer.expected_value)
        except (TypeError, ValueError, RuntimeError, AttributeError, IndexError) as exc:
            return self._unavailable(
                common,
                ExplanationReasonCode.SHAP_OUTPUT_UNSUPPORTED,
                f"SHAP could not explain this fitted artifact: {exc}",
            )
        values = [
            _finite(float(value), "SHAP contribution")
            for value in values
        ]
        actual_output = _finite(actual_output, "raw LightGBM margin")
        additivity_error = abs(expected + sum(values) - actual_output)
        if additivity_error > self.config.additivity_tolerance:
            return self._unavailable(
                common,
                ExplanationReasonCode.SHAP_ADDITIVITY_FAILED,
                "SHAP contributions did not reproduce the raw LightGBM margin within tolerance.",
                extra={
                    "expected_base_value": expected,
                    "actual_explained_model_output": actual_output,
                    "raw_model_probability": raw_probability,
                    "additivity_error": additivity_error,
                    "additivity_tolerance": self.config.additivity_tolerance,
                },
            )

        original_values = snapshot.feature_values.model_dump()
        contributions = tuple(
            FeatureContribution(
                feature_name=name,
                original_value=original_values.get(name),
                model_input_value=float(model_row[index]),
                was_missing=False,
                missingness_indicator=None,
                shap_value=values[index],
                direction=_direction(values[index]),
                magnitude=abs(values[index]),
                source_feature_refs=snapshot.source_evidence_refs,
            )
            for index, name in enumerate(allowlist)
        )
        limit = self.config.top_k if top_k is None else top_k
        if limit < 1:
            raise ValueError("top_k must be positive")
        ordered = sorted(
            contributions,
            key=lambda item: (-item.magnitude, allowlist.index(item.feature_name)),
        )
        positive = tuple(
            item for item in ordered if item.shap_value > 0
        )[:limit]
        negative = tuple(
            item for item in ordered if item.shap_value < 0
        )[:limit]
        codes: tuple[ExplanationReasonCode, ...] = ()
        limitations = (
            "SHAP contributions explain the raw LightGBM margin/log-odds only.",
            "They do not explain calibrated or horizon-coherence-adjusted probabilities.",
            "SHAP values describe model associations, not causes or treatment effects.",
            "Production callers must gate this result with the canonical reliability, freshness, eligibility, and calibration checks.",
        )
        if not any(item.shap_value != 0 for item in contributions):
            codes = (ExplanationReasonCode.NO_INFORMATIVE_CONTRIBUTIONS,)
            limitations += ("All computed feature contributions are zero.",)
        return ExplanationResult(
            **common,
            explanation_status=ExplanationStatus.AVAILABLE,
            explained_output_space=ExplainedOutputSpace.RAW_LIGHTGBM_MARGIN_LOG_ODDS,
            expected_base_value=expected,
            actual_explained_model_output=actual_output,
            raw_model_probability=raw_probability,
            additivity_error=additivity_error,
            additivity_tolerance=self.config.additivity_tolerance,
            feature_contributions=contributions,
            positive_contributors=positive,
            negative_contributors=negative,
            human_readable_explanations=ExplanationFormatter.format_contributions(positive, negative),
            limitations=limitations,
            reason_codes=codes,
        )

    def _unavailable(
        self,
        common: dict[str, Any],
        reason: ExplanationReasonCode,
        limitation: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> ExplanationResult:
        payload = {
            **common,
            "explanation_status": ExplanationStatus.UNAVAILABLE,
            "reason_codes": (reason,),
            "limitations": (limitation,),
        }
        if extra:
            payload.update(extra)
        return ExplanationResult(**payload)


class ExplanationFormatter:
    """Deterministic, non-causal wording for computed signed contributions."""

    @staticmethod
    def format_contributions(
        positive: Sequence[FeatureContribution],
        negative: Sequence[FeatureContribution],
    ) -> tuple[str, ...]:
        phrases = [
            f"{item.feature_name} was associated with a higher raw model score."
            for item in positive
        ]
        phrases.extend(
            f"{item.feature_name} was associated with a lower raw model score."
            for item in negative
        )
        return tuple(phrases)

    @staticmethod
    def format(result: ExplanationResult) -> tuple[str, ...]:
        if result.explanation_status is not ExplanationStatus.AVAILABLE:
            return ()
        return ExplanationFormatter.format_contributions(
            result.positive_contributors,
            result.negative_contributors,
        )


__all__ = [
    "ContributionDirection",
    "ExplainabilityConfig",
    "ExplainedOutputSpace",
    "ExplanationFormatter",
    "ExplanationReasonCode",
    "ExplanationResult",
    "ExplanationStatus",
    "FeatureContribution",
    "LightGBMExplainer",
    "SHAP_AVAILABLE",
    "SHAP_VERSION",
]
