"""Deterministic reliability and prediction-readiness assessments.

Reliability is a data/applicability gate, not a probability that a model is
correct.  This module never creates churn probabilities and never changes the
canonical PredictionOutput or uncertainty contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Iterable, Sequence, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .baselines import BaselineStatus
from .contracts import FreshnessStatus, PredictionStatus, ReliabilityStatus
from .data_freshness import DataFreshnessAssessment, FreshnessSource
from .dataset_readiness import DatasetStatus
from .eligibility import (
    EligibilityReasonCode,
    EligibilityResult,
    EligibilityState,
)
from .feature_builder import (
    FeatureSnapshot,
    PersonalBaselineStatus,
    UsageCoverageStatus,
)
from .lightgbm_model import LightGBMModelMetadata
from .horizon_coherence import CalibrationBundleReadiness


class ReliabilityReasonCode(str, Enum):
    IDENTITY_CONFIRMED = "IDENTITY_CONFIRMED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    ELIGIBILITY_CONFIRMED = "ELIGIBILITY_CONFIRMED"
    ELIGIBILITY_NON_SCORABLE = "ELIGIBILITY_NON_SCORABLE"
    ELIGIBILITY_INSUFFICIENT = "ELIGIBILITY_INSUFFICIENT"
    CRITICAL_LIFECYCLE_CONTRADICTION = "CRITICAL_LIFECYCLE_CONTRADICTION"
    FEATURE_CUTOFF_INVALID = "FEATURE_CUTOFF_INVALID"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    FEATURE_LIMITATION_REPORTED = "FEATURE_LIMITATION_REPORTED"
    REQUIRED_FEATURE_MISSING = "REQUIRED_FEATURE_MISSING"
    INVALID_FEATURE_VALUE = "INVALID_FEATURE_VALUE"
    USAGE_COVERAGE_COMPLETE = "USAGE_COVERAGE_COMPLETE"
    USAGE_COVERAGE_LIMITED = "USAGE_COVERAGE_LIMITED"
    USAGE_COVERAGE_UNKNOWN = "USAGE_COVERAGE_UNKNOWN"
    PERSONAL_HISTORY_AVAILABLE = "PERSONAL_HISTORY_AVAILABLE"
    COLD_START_HISTORY = "COLD_START_HISTORY"
    ZERO_USAGE_WITH_COVERAGE = "ZERO_USAGE_WITH_COVERAGE"
    ESSENTIAL_FRESHNESS_STALE = "ESSENTIAL_FRESHNESS_STALE"
    ESSENTIAL_FRESHNESS_UNKNOWN = "ESSENTIAL_FRESHNESS_UNKNOWN"
    ESSENTIAL_FRESHNESS_LIMITED = "ESSENTIAL_FRESHNESS_LIMITED"
    OPTIONAL_FRESHNESS_LIMITED = "OPTIONAL_FRESHNESS_LIMITED"
    MODEL_ARTIFACT_NOT_READY = "MODEL_ARTIFACT_NOT_READY"
    MODEL_FEATURE_REQUIREMENTS_UNAVAILABLE = "MODEL_FEATURE_REQUIREMENTS_UNAVAILABLE"


class FeatureCompleteness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class _ReliabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceCoverageSummary(_ReliabilityModel):
    identity_integrity: bool
    eligibility_state: EligibilityState
    subscription_history_available: bool
    feature_completeness: FeatureCompleteness
    usage_coverage_status: UsageCoverageStatus
    personal_baseline_status: PersonalBaselineStatus
    observed_history_days: int = Field(ge=0)
    observed_weeks: int = Field(ge=0)
    required_features: tuple[str, ...] = ()
    missing_features: tuple[str, ...] = ()
    invalid_features: tuple[str, ...] = ()
    freshness_status: FreshnessStatus
    freshness_by_source: dict[str, FreshnessStatus] = Field(default_factory=dict)
    critical_issues: tuple[str, ...] = ()


class ReliabilityAssessment(_ReliabilityModel):
    """Explainable data/applicability result, with no confidence number."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    status: ReliabilityStatus
    reason_codes: tuple[ReliabilityReasonCode, ...] = ()
    human_readable_reasons: tuple[str, ...] = ()
    evaluated_at: AwareDatetime
    policy_version: str = Field(min_length=1)
    evidence_summary: EvidenceCoverageSummary
    data_sufficient_for_scoring: bool
    abstention_required: bool


class PredictionReadinessAssessment(_ReliabilityModel):
    """Combined routing recommendation before any model score is produced."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    reliability: ReliabilityAssessment
    freshness: DataFreshnessAssessment
    model_artifacts_ready: bool
    scoring_allowed: bool
    abstention_required: bool
    prediction_status: PredictionStatus | None = None
    reason_codes: tuple[ReliabilityReasonCode, ...] = ()
    human_readable_reasons: tuple[str, ...] = ()
    evaluated_at: AwareDatetime

    @property
    def canonical_prediction_status(self) -> PredictionStatus | None:
        """Expose the future contract status without adding a new enum value."""

        return self.prediction_status


@dataclass(frozen=True)
class ReliabilityPolicy:
    """Versioned, deterministic reliability rules.

    History thresholds are applicability heuristics until validated on real
    held-out data.  They are deliberately configurable and do not create a
    numerical confidence score.
    """

    policy_version: str = "reliability_v1"
    minimum_observed_history_days: int = 28
    minimum_observed_weeks: int = 4
    cold_start_status: ReliabilityStatus = ReliabilityStatus.LIMITED_EVIDENCE
    allow_limited_scoring: bool = True
    essential_freshness_sources: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
                FreshnessSource.USAGE_COVERAGE.value,
            }
        )
    )

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("policy_version must be non-empty")
        if self.minimum_observed_history_days < 0 or self.minimum_observed_weeks < 0:
            raise ValueError("history thresholds must not be negative")
        if self.cold_start_status is ReliabilityStatus.SUFFICIENT_EVIDENCE:
            raise ValueError("cold-start status cannot be sufficient_evidence")


_REASON_TEXT: dict[ReliabilityReasonCode, str] = {
    ReliabilityReasonCode.IDENTITY_CONFIRMED: "Tenant and account identity agree across inputs.",
    ReliabilityReasonCode.IDENTITY_MISMATCH: "Tenant or account identity disagrees across inputs.",
    ReliabilityReasonCode.ELIGIBILITY_CONFIRMED: "Point-in-time evidence establishes an eligible paying account.",
    ReliabilityReasonCode.ELIGIBILITY_NON_SCORABLE: "The account is not in the prospective scoring population.",
    ReliabilityReasonCode.ELIGIBILITY_INSUFFICIENT: "Eligibility evidence is missing, contradictory, or unresolved.",
    ReliabilityReasonCode.CRITICAL_LIFECYCLE_CONTRADICTION: "Critical subscription lifecycle evidence is contradictory.",
    ReliabilityReasonCode.FEATURE_CUTOFF_INVALID: "Feature data was not demonstrably available at the prediction cutoff.",
    ReliabilityReasonCode.FEATURE_VERSION_MISMATCH: "Feature version is incompatible with the trained model metadata.",
    ReliabilityReasonCode.FEATURE_LIMITATION_REPORTED: "The feature builder reported a data limitation.",
    ReliabilityReasonCode.REQUIRED_FEATURE_MISSING: "A model-required feature value is unavailable.",
    ReliabilityReasonCode.INVALID_FEATURE_VALUE: "A feature value is invalid or non-finite.",
    ReliabilityReasonCode.USAGE_COVERAGE_COMPLETE: "Usage coverage is complete for the assessed windows.",
    ReliabilityReasonCode.USAGE_COVERAGE_LIMITED: "Usage coverage is partial; recent activity is not interpreted as churn evidence.",
    ReliabilityReasonCode.USAGE_COVERAGE_UNKNOWN: "Usage coverage is unknown; absent events are not treated as zero usage.",
    ReliabilityReasonCode.PERSONAL_HISTORY_AVAILABLE: "Sufficient personal history is available for the configured policy.",
    ReliabilityReasonCode.COLD_START_HISTORY: "Personal history is sparse or cold-start and applicability is limited.",
    ReliabilityReasonCode.ZERO_USAGE_WITH_COVERAGE: "Zero observed usage is supported by healthy coverage and is not treated as missing data.",
    ReliabilityReasonCode.ESSENTIAL_FRESHNESS_STALE: "An essential source is stale at the prediction cutoff.",
    ReliabilityReasonCode.ESSENTIAL_FRESHNESS_UNKNOWN: "Freshness of an essential source cannot be established.",
    ReliabilityReasonCode.ESSENTIAL_FRESHNESS_LIMITED: "An essential source has incomplete freshness or coverage evidence.",
    ReliabilityReasonCode.OPTIONAL_FRESHNESS_LIMITED: "An optional source is missing or has limited freshness evidence.",
    ReliabilityReasonCode.MODEL_ARTIFACT_NOT_READY: "A complete validated calibrated model bundle is not ready.",
    ReliabilityReasonCode.MODEL_FEATURE_REQUIREMENTS_UNAVAILABLE: "Model feature requirements were not supplied; compatibility is only partially assessed.",
}


T = TypeVar("T")


def _unique(values: Iterable[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(values))


def _add(
    codes: list[ReliabilityReasonCode],
    code: ReliabilityReasonCode,
) -> None:
    if code not in codes:
        codes.append(code)


def _human_reasons(codes: Sequence[ReliabilityReasonCode]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_REASON_TEXT[code] for code in codes))


def assess_reliability(
    eligibility: EligibilityResult,
    feature_snapshot: FeatureSnapshot,
    freshness: DataFreshnessAssessment,
    *,
    policy: ReliabilityPolicy | None = None,
    model_metadata: LightGBMModelMetadata | None = None,
    required_feature_names: Sequence[str] | None = None,
    evaluated_at: datetime | None = None,
) -> ReliabilityAssessment:
    """Assess data applicability without producing a model score."""

    selected_policy = policy or ReliabilityPolicy()
    evaluated = evaluated_at or datetime.now(timezone.utc)
    for value, name in ((evaluated, "evaluated_at"),):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")

    identity_ok = (
        eligibility.tenant_id == feature_snapshot.tenant_id == freshness.tenant_id
        and eligibility.customer_id == feature_snapshot.customer_id == freshness.customer_id
        and eligibility.as_of == feature_snapshot.as_of == freshness.as_of
    )
    codes: list[ReliabilityReasonCode] = []
    if identity_ok:
        _add(codes, ReliabilityReasonCode.IDENTITY_CONFIRMED)
    else:
        _add(codes, ReliabilityReasonCode.IDENTITY_MISMATCH)

    if eligibility.state is EligibilityState.ELIGIBLE:
        _add(codes, ReliabilityReasonCode.ELIGIBILITY_CONFIRMED)
    elif eligibility.state is EligibilityState.INSUFFICIENT_DATA:
        _add(codes, ReliabilityReasonCode.ELIGIBILITY_INSUFFICIENT)
    else:
        _add(codes, ReliabilityReasonCode.ELIGIBILITY_NON_SCORABLE)
    if EligibilityReasonCode.CONTRADICTORY_LIFECYCLE in eligibility.reason_codes:
        _add(codes, ReliabilityReasonCode.CRITICAL_LIFECYCLE_CONTRADICTION)

    feature_values = feature_snapshot.feature_values.model_dump()
    requested_features = tuple(
        model_metadata.feature_names
        if model_metadata is not None and model_metadata.feature_names
        else required_feature_names or ()
    )
    missing_features = tuple(
        name for name in requested_features if name not in feature_values or feature_values[name] is None
    )
    invalid_features = tuple(
        name
        for name, value in feature_values.items()
        if isinstance(value, float) and not math.isfinite(value)
    )
    if missing_features:
        _add(codes, ReliabilityReasonCode.REQUIRED_FEATURE_MISSING)
    if invalid_features:
        _add(codes, ReliabilityReasonCode.INVALID_FEATURE_VALUE)
    if model_metadata is not None and feature_snapshot.feature_version != model_metadata.feature_version:
        _add(codes, ReliabilityReasonCode.FEATURE_VERSION_MISMATCH)
    if feature_snapshot.data_cutoff_at > feature_snapshot.as_of:
        _add(codes, ReliabilityReasonCode.FEATURE_CUTOFF_INVALID)
    quality = feature_snapshot.data_quality
    if quality.usage_coverage_status is UsageCoverageStatus.COMPLETE:
        _add(codes, ReliabilityReasonCode.USAGE_COVERAGE_COMPLETE)
    elif quality.usage_coverage_status is UsageCoverageStatus.PARTIAL:
        _add(codes, ReliabilityReasonCode.USAGE_COVERAGE_LIMITED)
    else:
        _add(codes, ReliabilityReasonCode.USAGE_COVERAGE_UNKNOWN)

    history_complete = (
        quality.observed_history_days >= selected_policy.minimum_observed_history_days
        and quality.observed_weeks >= selected_policy.minimum_observed_weeks
    )
    if history_complete and quality.personal_baseline_status not in {
        PersonalBaselineStatus.INSUFFICIENT_HISTORY,
        PersonalBaselineStatus.UNAVAILABLE,
    }:
        _add(codes, ReliabilityReasonCode.PERSONAL_HISTORY_AVAILABLE)
    else:
        _add(codes, ReliabilityReasonCode.COLD_START_HISTORY)
    if quality.limitations:
        _add(codes, ReliabilityReasonCode.FEATURE_LIMITATION_REPORTED)
    if (
        quality.usage_coverage_status is UsageCoverageStatus.COMPLETE
        and quality.personal_baseline_status is PersonalBaselineStatus.ZERO_BASELINE
    ):
        _add(codes, ReliabilityReasonCode.ZERO_USAGE_WITH_COVERAGE)

    freshness_by_source = {
        item.source: item.status for item in freshness.source_assessments
    }
    for source in selected_policy.essential_freshness_sources:
        status = freshness_by_source.get(source, FreshnessStatus.UNKNOWN)
        if status is FreshnessStatus.STALE:
            _add(codes, ReliabilityReasonCode.ESSENTIAL_FRESHNESS_STALE)
        elif status is FreshnessStatus.UNKNOWN:
            _add(codes, ReliabilityReasonCode.ESSENTIAL_FRESHNESS_UNKNOWN)
        elif status is FreshnessStatus.PARTIALLY_STALE:
            _add(codes, ReliabilityReasonCode.ESSENTIAL_FRESHNESS_LIMITED)
    for source, status in freshness_by_source.items():
        if source not in selected_policy.essential_freshness_sources and status is not FreshnessStatus.FRESH:
            _add(codes, ReliabilityReasonCode.OPTIONAL_FRESHNESS_LIMITED)

    blocking = {
        ReliabilityReasonCode.IDENTITY_MISMATCH,
        ReliabilityReasonCode.ELIGIBILITY_INSUFFICIENT,
        ReliabilityReasonCode.CRITICAL_LIFECYCLE_CONTRADICTION,
        ReliabilityReasonCode.FEATURE_CUTOFF_INVALID,
        ReliabilityReasonCode.FEATURE_VERSION_MISMATCH,
        ReliabilityReasonCode.FEATURE_LIMITATION_REPORTED,
        ReliabilityReasonCode.REQUIRED_FEATURE_MISSING,
        ReliabilityReasonCode.INVALID_FEATURE_VALUE,
        ReliabilityReasonCode.ESSENTIAL_FRESHNESS_STALE,
        ReliabilityReasonCode.ESSENTIAL_FRESHNESS_UNKNOWN,
    }
    limited = {
        ReliabilityReasonCode.USAGE_COVERAGE_LIMITED,
        ReliabilityReasonCode.USAGE_COVERAGE_UNKNOWN,
        ReliabilityReasonCode.COLD_START_HISTORY,
        ReliabilityReasonCode.ESSENTIAL_FRESHNESS_LIMITED,
        ReliabilityReasonCode.OPTIONAL_FRESHNESS_LIMITED,
    }
    if selected_policy.cold_start_status is ReliabilityStatus.INSUFFICIENT_EVIDENCE:
        blocking.add(ReliabilityReasonCode.COLD_START_HISTORY)
    if quality.usage_coverage_status is UsageCoverageStatus.UNKNOWN and missing_features:
        blocking.add(ReliabilityReasonCode.USAGE_COVERAGE_UNKNOWN)
    if quality.usage_coverage_status is UsageCoverageStatus.PARTIAL and missing_features:
        blocking.add(ReliabilityReasonCode.USAGE_COVERAGE_LIMITED)

    if any(code in blocking for code in codes):
        status = ReliabilityStatus.INSUFFICIENT_EVIDENCE
    elif any(code in limited for code in codes):
        status = ReliabilityStatus.LIMITED_EVIDENCE
    else:
        status = ReliabilityStatus.SUFFICIENT_EVIDENCE

    evidence_summary = EvidenceCoverageSummary(
        identity_integrity=identity_ok,
        eligibility_state=eligibility.state,
        subscription_history_available=EligibilityReasonCode.MISSING_SUBSCRIPTION_HISTORY not in eligibility.reason_codes,
        feature_completeness=(
            FeatureCompleteness.UNKNOWN
            if not feature_values
            or quality.usage_coverage_status is UsageCoverageStatus.UNKNOWN
            else FeatureCompleteness.PARTIAL
            if missing_features or quality.usage_coverage_status is UsageCoverageStatus.PARTIAL
            else FeatureCompleteness.COMPLETE
        ),
        usage_coverage_status=quality.usage_coverage_status,
        personal_baseline_status=quality.personal_baseline_status,
        observed_history_days=quality.observed_history_days,
        observed_weeks=quality.observed_weeks,
        required_features=requested_features,
        missing_features=missing_features,
        invalid_features=invalid_features,
        freshness_status=freshness.status,
        freshness_by_source=freshness_by_source,
        critical_issues=tuple(
            code.value for code in codes if code in blocking
        ),
    )
    return ReliabilityAssessment(
        tenant_id=feature_snapshot.tenant_id,
        customer_id=feature_snapshot.customer_id,
        as_of=feature_snapshot.as_of,
        status=status,
        reason_codes=tuple(codes),
        human_readable_reasons=_human_reasons(codes),
        evaluated_at=evaluated,
        policy_version=selected_policy.policy_version,
        evidence_summary=evidence_summary,
        data_sufficient_for_scoring=status is not ReliabilityStatus.INSUFFICIENT_EVIDENCE,
        abstention_required=status is ReliabilityStatus.INSUFFICIENT_EVIDENCE,
    )


def assess_prediction_readiness(
    eligibility: EligibilityResult,
    feature_snapshot: FeatureSnapshot,
    freshness: DataFreshnessAssessment,
    *,
    policy: ReliabilityPolicy | None = None,
    model_metadata: LightGBMModelMetadata | None = None,
    required_feature_names: Sequence[str] | None = None,
    calibration_readiness: CalibrationBundleReadiness | None = None,
    evaluated_at: datetime | None = None,
) -> PredictionReadinessAssessment:
    """Combine eligibility, data quality, freshness, and artifact readiness."""

    selected_policy = policy or ReliabilityPolicy()
    evaluated = evaluated_at or datetime.now(timezone.utc)
    reliability = assess_reliability(
        eligibility,
        feature_snapshot,
        freshness,
        policy=selected_policy,
        model_metadata=model_metadata,
        required_feature_names=required_feature_names,
        evaluated_at=evaluated,
    )
    codes = list(reliability.reason_codes)
    human = list(reliability.human_readable_reasons)
    required_horizons = {7, 14, 30}
    model_ready = bool(
        calibration_readiness is not None
        and calibration_readiness.status is BaselineStatus.READY
        and set(calibration_readiness.ready_horizons) == required_horizons
        and not calibration_readiness.missing_horizons
        and all(
            calibration_readiness.dataset_statuses.get(horizon) is DatasetStatus.PASS
            for horizon in required_horizons
        )
    )
    if not model_ready and eligibility.state is EligibilityState.ELIGIBLE:
        _add(codes, ReliabilityReasonCode.MODEL_ARTIFACT_NOT_READY)
        human.append(_REASON_TEXT[ReliabilityReasonCode.MODEL_ARTIFACT_NOT_READY])

    if eligibility.state in {
        EligibilityState.KNOWN_CANCELLATION,
        EligibilityState.NOT_ELIGIBLE,
    }:
        prediction_status = eligibility.canonical_prediction_status()
        scoring_allowed = False
        abstention_required = False
    elif eligibility.state is EligibilityState.INSUFFICIENT_DATA or reliability.abstention_required:
        prediction_status = PredictionStatus.ABSTAINED
        scoring_allowed = False
        abstention_required = True
    elif not model_ready:
        prediction_status = PredictionStatus.ABSTAINED
        scoring_allowed = False
        abstention_required = True
    elif reliability.status is ReliabilityStatus.LIMITED_EVIDENCE and not selected_policy.allow_limited_scoring:
        prediction_status = PredictionStatus.ABSTAINED
        scoring_allowed = False
        abstention_required = True
    else:
        prediction_status = None
        scoring_allowed = True
        abstention_required = False

    return PredictionReadinessAssessment(
        tenant_id=feature_snapshot.tenant_id,
        customer_id=feature_snapshot.customer_id,
        as_of=feature_snapshot.as_of,
        reliability=reliability,
        freshness=freshness,
        model_artifacts_ready=model_ready,
        scoring_allowed=scoring_allowed,
        abstention_required=abstention_required,
        prediction_status=prediction_status,
        reason_codes=_unique(codes),
        human_readable_reasons=_unique(human),
        evaluated_at=evaluated,
    )


__all__ = [
    "EvidenceCoverageSummary",
    "FeatureCompleteness",
    "PredictionReadinessAssessment",
    "ReliabilityAssessment",
    "ReliabilityPolicy",
    "ReliabilityReasonCode",
    "assess_prediction_readiness",
    "assess_reliability",
]
