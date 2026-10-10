"""Point-in-time-safe orchestration for the RetainIQ prediction components.

This module composes existing Member 2 contracts.  It does not train models,
fit calibrators, persist records, authenticate callers, or expose an API.
Production scoring remains unavailable until artifact provenance and real-data
readiness are established.  Synthetic execution is deliberately non-deployable
and requires artifact provenance checks in addition to its explicit test mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import math
from typing import Any, Callable, Mapping, Protocol, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .baselines import BaselineStatus, MODEL_FEATURE_ALLOWLIST
from .calibration import (
    CalibratedProbability,
    ProbabilityCalibrator,
)
from .contracts import (
    DataFreshness,
    PredictionOutput,
    PredictionStatus,
    Reliability,
    Uncertainty,
)
from .data_freshness import (
    DataFreshnessAssessment,
    FreshnessPolicy,
    SourceFreshnessEvidence,
    assess_data_freshness,
)
from .dataset_readiness import DatasetStatus
from .eligibility import (
    EligibilityPolicy,
    EligibilityReasonCode,
    EligibilityResult,
    EligibilityState,
    evaluate_prediction_eligibility,
)
from .explainability import ExplanationResult, ExplanationStatus, LightGBMExplainer
from .feature_builder import FeatureBuilder, FeatureSnapshot, UsageCoverage
from .horizon_coherence import (
    CalibrationBundleReadiness,
    HorizonCoherenceResult,
    assess_calibrated_bundle_readiness,
    calibrated_bundle_from_outputs,
    enforce_horizon_coherence,
)
from .lightgbm_model import LightGBMModel
from .point_in_time import PointInTimeDataAdapter, PointInTimeSnapshot
from .reliability import (
    PredictionReadinessAssessment,
    ReliabilityPolicy,
    assess_prediction_readiness,
    assess_reliability,
)


HORIZONS = (7, 14, 30)


class PipelineStatus(str, Enum):
    COMPLETED = "completed"
    ABSTAINED_DUE_TO_INSUFFICIENT_EVIDENCE = "abstained_due_to_insufficient_evidence"
    KNOWN_CANCELLATION = "known_cancellation"
    NOT_ELIGIBLE = "not_eligible"
    MODEL_BUNDLE_NOT_READY = "model_bundle_not_ready"
    INTEGRATION_OR_CONTRACT_ERROR = "integration_or_contract_error"


class PipelineReasonCode(str, Enum):
    ADAPTER_ERROR = "ADAPTER_ERROR"
    FEATURE_BUILD_ERROR = "FEATURE_BUILD_ERROR"
    FRESHNESS_ASSESSMENT_ERROR = "FRESHNESS_ASSESSMENT_ERROR"
    FEATURE_IDENTITY_MISMATCH = "FEATURE_IDENTITY_MISMATCH"
    ELIGIBILITY_INSUFFICIENT = "ELIGIBILITY_INSUFFICIENT"
    ESSENTIAL_DATA_NOT_FRESH = "ESSENTIAL_DATA_NOT_FRESH"
    MODEL_BUNDLE_NOT_READY = "MODEL_BUNDLE_NOT_READY"
    MODEL_METADATA_MISSING = "MODEL_METADATA_MISSING"
    MODEL_CALIBRATION_MISMATCH = "MODEL_CALIBRATION_MISMATCH"
    FEATURE_ORDER_MISMATCH = "FEATURE_ORDER_MISMATCH"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    LABEL_POLICY_MISMATCH = "LABEL_POLICY_MISMATCH"
    MODEL_PREDICTION_FAILED = "MODEL_PREDICTION_FAILED"
    CALIBRATION_FAILED = "CALIBRATION_FAILED"
    COHERENCE_FAILED = "COHERENCE_FAILED"
    EXPLANATION_UNAVAILABLE = "EXPLANATION_UNAVAILABLE"
    CONTRACT_METADATA_UNAVAILABLE = "CONTRACT_METADATA_UNAVAILABLE"
    PRODUCTION_DATASET_NOT_READY = "PRODUCTION_DATASET_NOT_READY"
    SYNTHETIC_PROVENANCE_INVALID = "SYNTHETIC_PROVENANCE_INVALID"
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"


class PipelineExecutionMode(str, Enum):
    PRODUCTION = "production"
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"


class _PipelineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PredictionRequest(_PipelineModel):
    """Immutable input to one account/cutoff inference attempt."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    prediction_run_id: str = Field(min_length=1)
    usage_coverage: tuple[UsageCoverage, ...] | None = None
    freshness_evidence: tuple[SourceFreshnessEvidence, ...] = ()


class PipelineResult(_PipelineModel):
    """Safe orchestration result; internal statuses are not PredictionStatus."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    prediction_run_id: str = Field(min_length=1)
    pipeline_status: PipelineStatus
    prediction: PredictionOutput | None = None
    reason_codes: tuple[PipelineReasonCode, ...] = ()
    version_references: dict[str, str] = Field(default_factory=dict)
    safe_diagnostics: dict[str, Any] = Field(default_factory=dict)
    synthetic_test_only: bool = False
    deployable: bool = False


class PredictionIdFactory(Protocol):
    def __call__(self, request: PredictionRequest) -> str:
        """Return a stable per-customer prediction identity."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_prediction_id(request: PredictionRequest) -> str:
    value = "|".join(
        (request.tenant_id, request.customer_id, request.as_of.isoformat())
    ).encode("utf-8")
    return f"prediction_{hashlib.sha256(value).hexdigest()}"


def _unique(values: Sequence[PipelineReasonCode]) -> tuple[PipelineReasonCode, ...]:
    return tuple(dict.fromkeys(values))


def _safe_float(value: float, name: str) -> float:
    converted = float(value)
    if not math.isfinite(converted) or not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return converted


def _provenance_is_synthetic(value: str | None) -> bool:
    return bool(value and value.lower().startswith("synthetic"))


@dataclass(frozen=True)
class PredictionPipelineConfig:
    """Policies and execution mode for the orchestration boundary."""

    execution_mode: PipelineExecutionMode = PipelineExecutionMode.PRODUCTION
    eligibility_policy: EligibilityPolicy = field(default_factory=EligibilityPolicy)
    freshness_policy: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    reliability_policy: ReliabilityPolicy = field(default_factory=ReliabilityPolicy)


@dataclass(frozen=True)
class _BundleVerification:
    structural_ready: bool
    production_ready: bool
    synthetic_ready: bool
    reasons: tuple[PipelineReasonCode, ...]
    version_references: dict[str, str]
    calibration_readiness: CalibrationBundleReadiness


class PredictionPipeline:
    """Compose point-in-time retrieval, gates, models, calibration, and SHAP."""

    def __init__(
        self,
        adapter: PointInTimeDataAdapter,
        *,
        models: Mapping[int, LightGBMModel],
        calibrators: Mapping[int, ProbabilityCalibrator],
        feature_builder: FeatureBuilder | None = None,
        explainer: LightGBMExplainer | None = None,
        config: PredictionPipelineConfig | None = None,
        clock: Callable[[], datetime] | None = None,
        prediction_id_factory: PredictionIdFactory | None = None,
    ) -> None:
        self.adapter = adapter
        self.models = dict(models)
        self.calibrators = dict(calibrators)
        self.feature_builder = feature_builder or FeatureBuilder(adapter)
        self.explainer = explainer or LightGBMExplainer()
        self.config = config or PredictionPipelineConfig()
        self.clock = clock or _utcnow
        self.prediction_id_factory = prediction_id_factory or _default_prediction_id

    def run(self, request: PredictionRequest) -> PipelineResult:
        """Execute one immutable account/cutoff attempt without training."""

        reasons: list[PipelineReasonCode] = []
        diagnostics: dict[str, Any] = {}
        synthetic_mode = self.config.execution_mode is PipelineExecutionMode.SYNTHETIC_TEST_ONLY

        try:
            point_in_time = self.adapter.snapshot_for(
                request.tenant_id, request.customer_id, request.as_of
            )
        except Exception as exc:
            return self._result(
                request,
                PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reasons=(PipelineReasonCode.ADAPTER_ERROR,),
                diagnostics={"stage": "point_in_time", "error_type": type(exc).__name__},
                synthetic_test_only=synthetic_mode,
            )
        if not self._snapshot_identity_matches(point_in_time, request):
            return self._result(
                request,
                PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reasons=(PipelineReasonCode.TENANT_SCOPE_MISMATCH,),
                diagnostics={"stage": "point_in_time_identity"},
                synthetic_test_only=synthetic_mode,
            )

        eligibility = evaluate_prediction_eligibility(
            point_in_time, policy=self.config.eligibility_policy
        )
        diagnostics.update(
            {
                "eligibility_state": eligibility.state.value,
                "eligibility_reason_codes": [code.value for code in eligibility.reason_codes],
                "point_in_time_excluded_record_counts": dict(point_in_time.excluded_record_counts),
            }
        )

        try:
            feature_snapshot = self.feature_builder.build(
                request.tenant_id,
                request.customer_id,
                request.as_of,
                usage_coverage=request.usage_coverage,
            )
        except Exception as exc:
            return self._result(
                request,
                PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reasons=(PipelineReasonCode.FEATURE_BUILD_ERROR,),
                diagnostics={**diagnostics, "stage": "feature_builder", "error_type": type(exc).__name__},
                synthetic_test_only=synthetic_mode,
            )
        if not self._feature_identity_matches(feature_snapshot, request):
            return self._result(
                request,
                PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reasons=(PipelineReasonCode.FEATURE_IDENTITY_MISMATCH,),
                diagnostics={**diagnostics, "stage": "feature_identity"},
                synthetic_test_only=synthetic_mode,
            )

        try:
            freshness = assess_data_freshness(
                request.tenant_id,
                request.customer_id,
                request.as_of,
                request.freshness_evidence,
                policy=self.config.freshness_policy,
                evaluated_at=self._now(),
            )
        except Exception as exc:
            return self._result(
                request,
                PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reasons=(PipelineReasonCode.FRESHNESS_ASSESSMENT_ERROR,),
                diagnostics={**diagnostics, "stage": "freshness", "error_type": type(exc).__name__},
                synthetic_test_only=synthetic_mode,
            )

        model_metadata = self.models.get(7).metadata if self.models.get(7) else None
        reliability = assess_reliability(
            eligibility,
            feature_snapshot,
            freshness,
            policy=self.config.reliability_policy,
            model_metadata=model_metadata,
            required_feature_names=MODEL_FEATURE_ALLOWLIST,
            evaluated_at=self._now(),
        )
        diagnostics.update(
            {
                "feature_version": feature_snapshot.feature_version,
                "freshness_status": freshness.status.value,
                "freshness_reason_codes": [code.value for code in freshness.reason_codes],
                "reliability_status": reliability.status.value,
                "reliability_reason_codes": [code.value for code in reliability.reason_codes],
                "reliability_warnings": list(reliability.human_readable_reasons),
            }
        )

        bundle = self._verify_bundle(request, feature_snapshot)
        diagnostics["model_bundle_reasons"] = [code.value for code in bundle.reasons]
        diagnostics["model_bundle_structural_ready"] = bundle.structural_ready
        diagnostics["model_bundle_production_ready"] = bundle.production_ready
        diagnostics["model_bundle_synthetic_ready"] = bundle.synthetic_ready
        diagnostics["model_bundle_calibration_readiness"] = bundle.calibration_readiness.model_dump(mode="json")
        diagnostics["synthetic_execution"] = synthetic_mode

        readiness = assess_prediction_readiness(
            eligibility,
            feature_snapshot,
            freshness,
            policy=self.config.reliability_policy,
            model_metadata=model_metadata,
            required_feature_names=MODEL_FEATURE_ALLOWLIST,
            calibration_readiness=bundle.calibration_readiness,
            evaluated_at=self._now(),
        )

        if eligibility.state is EligibilityState.KNOWN_CANCELLATION:
            return self._non_scored_result(
                request,
                PredictionStatus.KNOWN_CANCELLATION,
                eligibility,
                reliability,
                freshness,
                bundle.version_references,
                diagnostics,
                synthetic_mode,
            )
        if eligibility.state is EligibilityState.NOT_ELIGIBLE:
            return self._non_scored_result(
                request,
                PredictionStatus.NOT_ELIGIBLE,
                eligibility,
                reliability,
                freshness,
                bundle.version_references,
                diagnostics,
                synthetic_mode,
            )
        if eligibility.state is EligibilityState.INSUFFICIENT_DATA or reliability.abstention_required:
            reasons.extend(bundle.reasons)
            reasons.extend(
                self._reliability_reason_codes(readiness)
            )
            reasons.append(PipelineReasonCode.ELIGIBILITY_INSUFFICIENT)
            if freshness.status.value in {"stale", "unknown"}:
                reasons.append(PipelineReasonCode.ESSENTIAL_DATA_NOT_FRESH)
            return self._abstained_result(
                request,
                reasons=_unique(reasons),
                reliability=reliability,
                freshness=freshness,
                version_references=bundle.version_references,
                diagnostics=diagnostics,
                synthetic_test_only=synthetic_mode,
            )

        allowed_bundle = bundle.production_ready or (
            synthetic_mode and bundle.synthetic_ready
        )
        if not allowed_bundle:
            reasons.extend(bundle.reasons or (PipelineReasonCode.MODEL_BUNDLE_NOT_READY,))
            if not bundle.production_ready and not synthetic_mode:
                reasons.append(PipelineReasonCode.PRODUCTION_DATASET_NOT_READY)
            return self._result(
                request,
                PipelineStatus.MODEL_BUNDLE_NOT_READY,
                reasons=_unique(reasons),
                version_references=bundle.version_references,
                diagnostics=diagnostics,
                synthetic_test_only=synthetic_mode,
            )

        try:
            raw_predictions = {
                horizon: self.models[horizon].predict(
                    feature_snapshot, horizon_days=horizon  # type: ignore[arg-type]
                )
                for horizon in HORIZONS
            }
            if any(
                prediction.status is not BaselineStatus.READY or prediction.score is None
                for prediction in raw_predictions.values()
            ):
                raise RuntimeError("one or more horizon models returned no ready raw score")
            calibrated: list[CalibratedProbability] = []
            for horizon in HORIZONS:
                calibrated.append(
                    self.calibrators[horizon].calibrate_prediction(
                        raw_predictions[horizon], self.models[horizon].metadata  # type: ignore[arg-type]
                    )
                )
            calibrated_bundle = calibrated_bundle_from_outputs(calibrated)
            coherence = enforce_horizon_coherence(calibrated_bundle)
            probabilities = coherence.adjusted
            for name, value in {
                "p7": probabilities.p7,
                "p14": probabilities.p14,
                "p30": probabilities.p30,
            }.items():
                _safe_float(value, name)
            diagnostics["raw_probabilities"] = {
                str(horizon): _safe_float(raw_predictions[horizon].score, f"raw_{horizon}")
                for horizon in HORIZONS
            }
            diagnostics["calibrated_probabilities"] = {
                str(item.horizon_days): item.calibrated_probability for item in calibrated
            }
            diagnostics["coherence_original_probabilities"] = coherence.original.model_dump()
            diagnostics["coherence_adjusted_probabilities"] = coherence.adjusted.model_dump()
            diagnostics["coherence_adjustment_applied"] = coherence.adjustment_applied
        except Exception as exc:
            reasons.append(
                PipelineReasonCode.CALIBRATION_FAILED
                if "calibrat" in str(exc).lower()
                else PipelineReasonCode.MODEL_PREDICTION_FAILED
            )
            return self._result(
                request,
                PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reasons=_unique(reasons),
                version_references=bundle.version_references,
                diagnostics={**diagnostics, "stage": "model_or_calibration", "error_type": type(exc).__name__},
                synthetic_test_only=synthetic_mode,
            )

        explanation_payload: dict[str, list[dict[str, Any]]] = {}
        explanation_failures: list[str] = []
        for horizon in HORIZONS:
            explanation = self.explainer.explain(
                self.models[horizon],
                feature_snapshot,
                horizon_days=horizon,  # type: ignore[arg-type]
                prediction_status=PredictionStatus.SCORED,
                expected_model_version=bundle.version_references.get("model_version"),
                expected_feature_version=feature_snapshot.feature_version,
                expected_tenant_id=request.tenant_id,
                expected_customer_id=request.customer_id,
                readiness=None if synthetic_mode else readiness,
            )
            explanation_payload[str(horizon)] = [
                explanation.model_dump(mode="json")
            ]
            if explanation.explanation_status is not ExplanationStatus.AVAILABLE:
                explanation_failures.append(
                    f"{horizon}:{','.join(code.value for code in explanation.reason_codes)}"
                )
        if explanation_failures:
            reasons.append(PipelineReasonCode.EXPLANATION_UNAVAILABLE)
            diagnostics["explanation_failures"] = explanation_failures

        try:
            prediction = self._build_prediction(
                request,
                status=PredictionStatus.SCORED,
                probabilities=(probabilities.p7, probabilities.p14, probabilities.p30),
                reliability=reliability,
                freshness=freshness,
                version_references=bundle.version_references,
                explanations=explanation_payload,
            )
        except Exception as exc:
            return self._result(
                request,
                PipelineStatus.INTEGRATION_OR_CONTRACT_ERROR,
                reasons=_unique((*reasons, PipelineReasonCode.CONTRACT_METADATA_UNAVAILABLE)),
                version_references=bundle.version_references,
                diagnostics={**diagnostics, "stage": "prediction_contract", "error_type": type(exc).__name__},
                synthetic_test_only=synthetic_mode,
            )
        return self._result(
            request,
            PipelineStatus.COMPLETED,
            prediction=prediction,
            reasons=_unique(reasons),
            version_references=bundle.version_references,
            diagnostics=diagnostics,
            synthetic_test_only=synthetic_mode,
            deployable=bundle.production_ready and not synthetic_mode,
        )

    def _verify_bundle(
        self, request: PredictionRequest, feature_snapshot: FeatureSnapshot
    ) -> _BundleVerification:
        reasons: list[PipelineReasonCode] = []
        refs: dict[str, str] = {}
        pair_metadata: list[tuple[Any, Any]] = []
        for horizon in HORIZONS:
            model = self.models.get(horizon)
            calibrator = self.calibrators.get(horizon)
            if model is None or calibrator is None:
                reasons.append(PipelineReasonCode.MODEL_BUNDLE_NOT_READY)
                continue
            model_metadata = model.metadata
            calibration_metadata = calibrator.metadata
            if (
                model.fit_result is None
                or model.fit_result.status is not BaselineStatus.READY
                or calibrator.fit_result is None
                or calibrator.fit_result.status is not BaselineStatus.READY
            ):
                reasons.append(PipelineReasonCode.MODEL_BUNDLE_NOT_READY)
                continue
            if model_metadata is None or calibration_metadata is None:
                reasons.append(PipelineReasonCode.MODEL_METADATA_MISSING)
                continue
            pair_metadata.append((model_metadata, calibration_metadata))
            if model_metadata.prediction_horizon_days != horizon or calibration_metadata.prediction_horizon_days != horizon:
                reasons.append(PipelineReasonCode.MODEL_CALIBRATION_MISMATCH)
            if (
                model_metadata.model_version != calibration_metadata.model_version
                or model_metadata.feature_version != calibration_metadata.feature_version
                or model_metadata.label_policy_version != calibration_metadata.label_policy_version
            ):
                reasons.append(PipelineReasonCode.MODEL_CALIBRATION_MISMATCH)
            if feature_snapshot.feature_version != model_metadata.feature_version:
                reasons.append(PipelineReasonCode.FEATURE_VERSION_MISMATCH)
            if tuple(model_metadata.feature_names) != MODEL_FEATURE_ALLOWLIST or tuple(
                model.vectorizer.allowlist
            ) != MODEL_FEATURE_ALLOWLIST or tuple(model_metadata.feature_names) != tuple(
                model.vectorizer.allowlist
            ):
                reasons.append(PipelineReasonCode.FEATURE_ORDER_MISMATCH)
            if model_metadata.tenant_scope is not None and model_metadata.tenant_scope != request.tenant_id:
                reasons.append(PipelineReasonCode.TENANT_SCOPE_MISMATCH)

        if len(pair_metadata) == len(HORIZONS):
            models_metadata = [item[0] for item in pair_metadata]
            calibrations_metadata = [item[1] for item in pair_metadata]
            if len({item.model_version for item in models_metadata}) != 1:
                reasons.append(PipelineReasonCode.MODEL_CALIBRATION_MISMATCH)
            if len({item.feature_version for item in models_metadata}) != 1:
                reasons.append(PipelineReasonCode.FEATURE_VERSION_MISMATCH)
            if len({item.label_policy_version for item in models_metadata}) != 1:
                reasons.append(PipelineReasonCode.LABEL_POLICY_MISMATCH)
            if len({item.calibration_version for item in calibrations_metadata}) != 1:
                reasons.append(PipelineReasonCode.MODEL_CALIBRATION_MISMATCH)
            first_model = models_metadata[0]
            first_calibration = calibrations_metadata[0]
            refs = {
                "model_version": first_model.model_version,
                "calibration_version": first_calibration.calibration_version,
                "feature_version": first_model.feature_version,
                "label_policy_version": first_model.label_policy_version,
                "dataset_provenance": first_calibration.training_dataset_provenance or "",
            }

        readiness = assess_calibrated_bundle_readiness(self.models, self.calibrators)
        structural_ready = len(reasons) == 0 and len(pair_metadata) == len(HORIZONS)
        dataset_statuses = [
            item[0].training_dataset_status for item in pair_metadata
        ] + [item[1].training_dataset_status for item in pair_metadata]
        empirical_statuses = [item[1].empirical_validation_status for item in pair_metadata]
        provenances = [
            value
            for item in pair_metadata
            for value in (
                item[0].training_dataset_provenance,
                item[1].training_dataset_provenance,
            )
        ]
        synthetic_ready = (
            structural_ready
            and bool(provenances)
            and all(_provenance_is_synthetic(value) for value in provenances)
            and all(status is DatasetStatus.BLOCKED for status in dataset_statuses)
            and all(status is DatasetStatus.BLOCKED for status in empirical_statuses)
            and len(set(provenances)) == 1
        )
        production_ready = (
            structural_ready
            and readiness.status is BaselineStatus.READY
            and all(status is DatasetStatus.PASS for status in dataset_statuses)
            and all(status is DatasetStatus.PASS for status in empirical_statuses)
            and all(bool(value) and not _provenance_is_synthetic(value) for value in provenances)
        )
        if not production_ready and not synthetic_ready:
            if pair_metadata and any(status is not DatasetStatus.PASS for status in dataset_statuses):
                reasons.append(PipelineReasonCode.PRODUCTION_DATASET_NOT_READY)
            if pair_metadata and not all(bool(value) for value in provenances):
                reasons.append(PipelineReasonCode.MODEL_METADATA_MISSING)
        if not reasons and not structural_ready:
            reasons.append(PipelineReasonCode.MODEL_BUNDLE_NOT_READY)
        return _BundleVerification(
            structural_ready=structural_ready,
            production_ready=production_ready,
            synthetic_ready=synthetic_ready,
            reasons=_unique(reasons),
            version_references=refs,
            calibration_readiness=readiness,
        )

    def _non_scored_result(
        self,
        request: PredictionRequest,
        status: PredictionStatus,
        eligibility: EligibilityResult,
        reliability: Any,
        freshness: DataFreshnessAssessment,
        version_references: dict[str, str],
        diagnostics: dict[str, Any],
        synthetic_mode: bool,
    ) -> PipelineResult:
        prediction = None
        reasons: list[PipelineReasonCode] = []
        if not version_references.get("model_version"):
            reasons.append(PipelineReasonCode.CONTRACT_METADATA_UNAVAILABLE)
        else:
            try:
                prediction = self._build_prediction(
                    request,
                    status=status,
                    probabilities=(None, None, None),
                    reliability=reliability,
                    freshness=freshness,
                    version_references=version_references,
                    explanations={},
                )
            except Exception:
                reasons.append(PipelineReasonCode.CONTRACT_METADATA_UNAVAILABLE)
        pipeline_status = (
            PipelineStatus.KNOWN_CANCELLATION
            if status is PredictionStatus.KNOWN_CANCELLATION
            else PipelineStatus.NOT_ELIGIBLE
        )
        diagnostics = {
            **diagnostics,
            "eligibility_limitations": list(eligibility.limitations),
        }
        return self._result(
            request,
            pipeline_status,
            prediction=prediction,
            reasons=_unique(reasons),
            version_references=version_references,
            diagnostics=diagnostics,
            synthetic_test_only=synthetic_mode,
            deployable=False,
        )

    def _abstained_result(
        self,
        request: PredictionRequest,
        *,
        reasons: tuple[PipelineReasonCode, ...],
        reliability: Any,
        freshness: DataFreshnessAssessment,
        version_references: dict[str, str],
        diagnostics: dict[str, Any],
        synthetic_test_only: bool,
    ) -> PipelineResult:
        prediction = None
        final_reasons = list(reasons)
        if version_references.get("model_version"):
            try:
                prediction = self._build_prediction(
                    request,
                    status=PredictionStatus.ABSTAINED,
                    probabilities=(None, None, None),
                    reliability=reliability,
                    freshness=freshness,
                    version_references=version_references,
                    explanations={},
                )
            except Exception:
                final_reasons.append(PipelineReasonCode.CONTRACT_METADATA_UNAVAILABLE)
        else:
            final_reasons.append(PipelineReasonCode.CONTRACT_METADATA_UNAVAILABLE)
        return self._result(
            request,
            PipelineStatus.ABSTAINED_DUE_TO_INSUFFICIENT_EVIDENCE,
            prediction=prediction,
            reasons=_unique(final_reasons),
            version_references=version_references,
            diagnostics=diagnostics,
            synthetic_test_only=synthetic_test_only,
            deployable=False,
        )

    def _build_prediction(
        self,
        request: PredictionRequest,
        *,
        status: PredictionStatus,
        probabilities: tuple[float | None, float | None, float | None],
        reliability: Any,
        freshness: DataFreshnessAssessment,
        version_references: Mapping[str, str],
        explanations: dict[str, list[dict[str, Any]]],
    ) -> PredictionOutput:
        prediction_id = self.prediction_id_factory(request)
        if not isinstance(prediction_id, str) or not prediction_id.strip():
            raise ValueError("prediction_id factory returned an empty identity")
        generated_at = self._now()
        return PredictionOutput(
            tenant_id=request.tenant_id,
            customer_id=request.customer_id,
            prediction_id=prediction_id,
            prediction_run_id=request.prediction_run_id,
            as_of=request.as_of,
            generated_at=generated_at,
            status=status,
            p_churn_7d=probabilities[0],
            p_churn_14d=probabilities[1],
            p_churn_30d=probabilities[2],
            feature_version=version_references["feature_version"],
            model_version=version_references["model_version"],
            calibration_version=version_references["calibration_version"],
            label_policy_version=version_references["label_policy_version"],
            reliability=Reliability(
                status=reliability.status,
                reasons=list(reliability.human_readable_reasons),
            ),
            data_freshness=DataFreshness(
                status=freshness.status,
                input_data_as_of=freshness.input_data_as_of,
                stale_sources=[
                    assessment.source
                    for assessment in freshness.source_assessments
                    if assessment.status.value != "fresh"
                ],
            ),
            uncertainty=Uncertainty(),
            explanations_by_horizon=explanations,
        )

    def _result(
        self,
        request: PredictionRequest,
        status: PipelineStatus,
        *,
        prediction: PredictionOutput | None = None,
        reasons: Sequence[PipelineReasonCode] = (),
        version_references: Mapping[str, str] | None = None,
        diagnostics: Mapping[str, Any] | None = None,
        synthetic_test_only: bool = False,
        deployable: bool = False,
    ) -> PipelineResult:
        return PipelineResult(
            tenant_id=request.tenant_id,
            customer_id=request.customer_id,
            as_of=request.as_of,
            prediction_run_id=request.prediction_run_id,
            pipeline_status=status,
            prediction=prediction,
            reason_codes=_unique(tuple(reasons)),
            version_references=dict(version_references or {}),
            safe_diagnostics=dict(diagnostics or {}),
            synthetic_test_only=synthetic_test_only,
            deployable=deployable,
        )

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("injected clock must return a timezone-aware timestamp")
        return value

    @staticmethod
    def _snapshot_identity_matches(
        snapshot: PointInTimeSnapshot, request: PredictionRequest
    ) -> bool:
        return (
            snapshot.tenant_id == request.tenant_id
            and snapshot.customer_id == request.customer_id
            and snapshot.as_of == request.as_of
        )

    @staticmethod
    def _feature_identity_matches(
        snapshot: FeatureSnapshot, request: PredictionRequest
    ) -> bool:
        return (
            snapshot.tenant_id == request.tenant_id
            and snapshot.customer_id == request.customer_id
            and snapshot.as_of == request.as_of
            and snapshot.data_cutoff_at <= request.as_of
        )

    @staticmethod
    def _reliability_reason_codes(
        readiness: PredictionReadinessAssessment,
    ) -> tuple[PipelineReasonCode, ...]:
        codes: list[PipelineReasonCode] = []
        if readiness.reliability.status.value == "insufficient_evidence":
            codes.append(PipelineReasonCode.ELIGIBILITY_INSUFFICIENT)
        if readiness.freshness.status.value in {"stale", "unknown"}:
            codes.append(PipelineReasonCode.ESSENTIAL_DATA_NOT_FRESH)
        return tuple(codes)


__all__ = [
    "HORIZONS",
    "PipelineReasonCode",
    "PipelineResult",
    "PipelineExecutionMode",
    "PipelineStatus",
    "PredictionPipeline",
    "PredictionPipelineConfig",
    "PredictionRequest",
]
