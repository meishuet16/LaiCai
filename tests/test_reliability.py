from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction import (
    BaselineStatus,
    CalibrationBundleReadiness,
    ChurnLabel,
    DataFreshnessAssessment,
    DatasetStatus,
    EligibilityReasonCode,
    EligibilityResult,
    EligibilityState,
    FeatureQuality,
    FeatureSnapshot,
    FeatureValues,
    FreshnessPolicy,
    FreshnessSource,
    FreshnessStatus,
    PersonalBaselineStatus,
    PredictionStatus,
    ReliabilityPolicy,
    ReliabilityReasonCode,
    ReliabilityStatus,
    SourceFreshnessEvidence,
    UsageCoverageStatus,
    assess_data_freshness,
    assess_prediction_readiness,
    assess_reliability,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def at(day: int) -> datetime:
    return BASE + timedelta(days=day)


def feature(
    *,
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    coverage: UsageCoverageStatus = UsageCoverageStatus.COMPLETE,
    history_days: int = 35,
    weeks: int = 4,
    baseline: PersonalBaselineStatus = PersonalBaselineStatus.AVAILABLE,
    zero_usage: bool = False,
    feature_version: str = "features_personalized_baseline_v1",
) -> FeatureSnapshot:
    value = 0 if zero_usage else 4
    return FeatureSnapshot(
        tenant_id=tenant_id,
        customer_id=customer_id,
        as_of=at(10),
        feature_version=feature_version,
        data_cutoff_at=at(10),
        feature_values=FeatureValues(
            sessions_prev_7d=value,
            sessions_prev_30d=value,
            days_since_last_observed_session=6 if zero_usage else 2,
            recent_usage_trend=0.0 if zero_usage else -0.5,
            observed_weeks=weeks,
            valid_usage_history=coverage is UsageCoverageStatus.COMPLETE,
            historical_avg_sessions_per_week=0.0 if zero_usage else 5.0,
            recent_avg_sessions_per_week=0.0 if zero_usage else 4.0,
            absolute_usage_deviation=0.0 if zero_usage else -1.0,
            percentage_usage_deviation=0.0 if zero_usage else -0.2,
            recent_to_baseline_usage_ratio=None if zero_usage else 0.8,
            historical_weekly_usage_variability=0.0 if zero_usage else 1.0,
            personal_baseline_availability_status=baseline,
        ),
        data_quality=FeatureQuality(
            usage_coverage_status=coverage,
            personal_baseline_status=baseline,
            observed_history_days=history_days,
            observed_weeks=weeks,
            baseline_weeks_requested=4,
            baseline_weeks_available=weeks,
            recent_window_covered=coverage is UsageCoverageStatus.COMPLETE,
            baseline_window_covered=coverage is UsageCoverageStatus.COMPLETE,
        ),
    )


def eligibility(
    state: EligibilityState = EligibilityState.ELIGIBLE,
    *,
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    reasons: tuple[EligibilityReasonCode, ...] = (
        EligibilityReasonCode.ACTIVE_PAYING_SUBSCRIPTION,
    ),
) -> EligibilityResult:
    return EligibilityResult(
        tenant_id=tenant_id,
        customer_id=customer_id,
        as_of=at(10),
        state=state,
        reason_codes=reasons,
        active_subscription_ids=("sub-a",) if state is EligibilityState.ELIGIBLE else (),
    )


def freshness(
    *,
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    stale_subscription: bool = False,
    unknown_subscription: bool = False,
    usage_complete: bool = True,
) -> DataFreshnessAssessment:
    sources = [
        SourceFreshnessEvidence(
            tenant_id=tenant_id,
            customer_id=customer_id,
            source=FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
            source_available_at=(
                None if unknown_subscription else at(9 if not stale_subscription else 1)
            ),
            last_sync_at=(
                None if unknown_subscription else at(9 if not stale_subscription else 1)
            ),
            watermark_at=(
                None if unknown_subscription else at(9 if not stale_subscription else 1)
            ),
            complete=True,
            connected=None if unknown_subscription else True,
        ),
        SourceFreshnessEvidence(
            tenant_id=tenant_id,
            customer_id=customer_id,
            source=FreshnessSource.USAGE_COVERAGE.value,
            source_available_at=at(9),
            last_sync_at=at(9),
            watermark_at=at(9),
            complete=usage_complete,
        ),
        SourceFreshnessEvidence(
            tenant_id=tenant_id,
            customer_id=customer_id,
            source=FreshnessSource.BILLING_EVENTS.value,
            source_available_at=at(9),
            last_sync_at=at(9),
            watermark_at=at(9),
            complete=True,
        ),
    ]
    return assess_data_freshness(tenant_id, customer_id, at(10), sources)


def ready_bundle() -> CalibrationBundleReadiness:
    return CalibrationBundleReadiness(
        status=BaselineStatus.READY,
        ready_horizons=(7, 14, 30),
        model_versions={7: "m", 14: "m", 30: "m"},
        calibration_versions={7: "c", 14: "c", 30: "c"},
        dataset_statuses={
            7: DatasetStatus.PASS,
            14: DatasetStatus.PASS,
            30: DatasetStatus.PASS,
        },
    )


def test_complete_valid_evidence_is_sufficient():
    result = assess_reliability(eligibility(), feature(), freshness())

    assert result.status is ReliabilityStatus.SUFFICIENT_EVIDENCE
    assert result.abstention_required is False
    assert ReliabilityReasonCode.IDENTITY_CONFIRMED in result.reason_codes


def test_essential_freshness_reason_order_is_deterministic():
    sources = frozenset({
        FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
        FreshnessSource.USAGE_COVERAGE.value,
    })
    policy = ReliabilityPolicy(essential_freshness_sources=sources)
    result = assess_reliability(
        eligibility(),
        feature(coverage=UsageCoverageStatus.PARTIAL),
        freshness(stale_subscription=True, usage_complete=False),
        policy=policy,
    )
    freshness_reasons = [
        reason.value
        for reason in result.reason_codes
        if reason in {
            ReliabilityReasonCode.ESSENTIAL_FRESHNESS_STALE,
            ReliabilityReasonCode.ESSENTIAL_FRESHNESS_LIMITED,
        }
    ]

    assert freshness_reasons == [
        ReliabilityReasonCode.ESSENTIAL_FRESHNESS_STALE.value,
        ReliabilityReasonCode.ESSENTIAL_FRESHNESS_LIMITED.value,
    ]


def test_missing_optional_billing_evidence_is_not_blocking():
    result = assess_reliability(eligibility(), feature(), freshness())

    assert result.status is ReliabilityStatus.SUFFICIENT_EVIDENCE


def test_missing_critical_eligibility_evidence_is_insufficient():
    result = assess_reliability(
        eligibility(EligibilityState.INSUFFICIENT_DATA), feature(), freshness()
    )

    assert result.status is ReliabilityStatus.INSUFFICIENT_EVIDENCE
    assert result.abstention_required is True
    assert ReliabilityReasonCode.ELIGIBILITY_INSUFFICIENT in result.reason_codes


def test_cold_start_is_explicitly_limited_by_default():
    result = assess_reliability(
        eligibility(),
        feature(history_days=3, weeks=1, baseline=PersonalBaselineStatus.UNAVAILABLE),
        freshness(),
    )

    assert result.status is ReliabilityStatus.LIMITED_EVIDENCE
    assert ReliabilityReasonCode.COLD_START_HISTORY in result.reason_codes


def test_cold_start_can_be_configured_as_insufficient():
    result = assess_reliability(
        eligibility(),
        feature(history_days=3, weeks=1, baseline=PersonalBaselineStatus.UNAVAILABLE),
        freshness(),
        policy=ReliabilityPolicy(
            cold_start_status=ReliabilityStatus.INSUFFICIENT_EVIDENCE
        ),
    )

    assert result.status is ReliabilityStatus.INSUFFICIENT_EVIDENCE


def test_incomplete_usage_is_not_confirmed_inactivity():
    result = assess_reliability(
        eligibility(),
        feature(coverage=UsageCoverageStatus.PARTIAL),
        freshness(usage_complete=False),
    )

    assert result.status is ReliabilityStatus.LIMITED_EVIDENCE
    assert ReliabilityReasonCode.USAGE_COVERAGE_LIMITED in result.reason_codes
    assert ReliabilityReasonCode.ZERO_USAGE_WITH_COVERAGE not in result.reason_codes


def test_confirmed_zero_usage_with_healthy_coverage_is_allowed():
    result = assess_reliability(
        eligibility(),
        feature(zero_usage=True, baseline=PersonalBaselineStatus.ZERO_BASELINE),
        freshness(),
    )

    assert result.status is ReliabilityStatus.SUFFICIENT_EVIDENCE
    assert ReliabilityReasonCode.ZERO_USAGE_WITH_COVERAGE in result.reason_codes


def test_stale_subscription_data_is_blocking():
    result = assess_reliability(eligibility(), feature(), freshness(stale_subscription=True))

    assert result.status is ReliabilityStatus.INSUFFICIENT_EVIDENCE
    assert ReliabilityReasonCode.ESSENTIAL_FRESHNESS_STALE in result.reason_codes


def test_unknown_lifecycle_health_remains_abstention_eligible():
    result = assess_reliability(
        eligibility(), feature(), freshness(unknown_subscription=True)
    )

    assert result.status is ReliabilityStatus.INSUFFICIENT_EVIDENCE
    assert result.abstention_required is True
    assert ReliabilityReasonCode.ESSENTIAL_FRESHNESS_UNKNOWN in result.reason_codes
    serialized = result.model_dump(mode="json")
    assert "ESSENTIAL_FRESHNESS_UNKNOWN" in serialized["reason_codes"]


def test_known_cancellation_is_preserved_and_not_scored():
    result = assess_prediction_readiness(
        eligibility(EligibilityState.KNOWN_CANCELLATION), feature(), freshness(),
        calibration_readiness=ready_bundle(),
    )

    assert result.prediction_status is PredictionStatus.KNOWN_CANCELLATION
    assert result.scoring_allowed is False
    assert result.abstention_required is False


def test_not_eligible_is_preserved_and_not_scored():
    result = assess_prediction_readiness(
        eligibility(EligibilityState.NOT_ELIGIBLE), feature(), freshness(),
        calibration_readiness=ready_bundle(),
    )

    assert result.prediction_status is PredictionStatus.NOT_ELIGIBLE
    assert result.scoring_allowed is False


def test_insufficient_eligibility_abstains_not_not_eligible():
    result = assess_prediction_readiness(
        eligibility(EligibilityState.INSUFFICIENT_DATA), feature(), freshness(),
        calibration_readiness=ready_bundle(),
    )

    assert result.prediction_status is PredictionStatus.ABSTAINED
    assert result.abstention_required is True
    assert result.prediction_status is not PredictionStatus.NOT_ELIGIBLE


def test_sufficient_data_does_not_bypass_missing_calibrated_bundle():
    result = assess_prediction_readiness(eligibility(), feature(), freshness())

    assert result.reliability.status is ReliabilityStatus.SUFFICIENT_EVIDENCE
    assert result.model_artifacts_ready is False
    assert result.prediction_status is PredictionStatus.ABSTAINED
    assert result.scoring_allowed is False
    assert ReliabilityReasonCode.MODEL_ARTIFACT_NOT_READY in result.reason_codes


def test_ready_model_bundle_allows_scoring_without_creating_a_probability():
    result = assess_prediction_readiness(
        eligibility(), feature(), freshness(), calibration_readiness=ready_bundle()
    )

    assert result.model_artifacts_ready is True
    assert result.scoring_allowed is True
    assert result.prediction_status is None


def test_limited_evidence_can_score_when_policy_allows_it():
    result = assess_prediction_readiness(
        eligibility(),
        feature(history_days=3, weeks=1, baseline=PersonalBaselineStatus.UNAVAILABLE),
        freshness(),
        calibration_readiness=ready_bundle(),
    )

    assert result.reliability.status is ReliabilityStatus.LIMITED_EVIDENCE
    assert result.scoring_allowed is True
    assert result.abstention_required is False


def test_identity_mismatch_cannot_influence_assessment():
    result = assess_reliability(
        eligibility(customer_id="customer-a"),
        feature(customer_id="customer-b"),
        freshness(customer_id="customer-b"),
    )

    assert result.status is ReliabilityStatus.INSUFFICIENT_EVIDENCE
    assert ReliabilityReasonCode.IDENTITY_MISMATCH in result.reason_codes


def test_model_feature_compatibility_and_missing_values_are_blocking():
    partial = feature(feature_version="features_old_v1")
    result = assess_reliability(
        eligibility(),
        partial,
        freshness(),
        required_feature_names=("sessions_prev_7d", "missing_feature"),
    )

    assert result.status is ReliabilityStatus.INSUFFICIENT_EVIDENCE
    assert "missing_feature" in result.evidence_summary.missing_features


def test_policy_version_and_evaluation_time_are_preserved():
    evaluated = at(20)
    result = assess_reliability(
        eligibility(),
        feature(),
        freshness(),
        policy=ReliabilityPolicy(policy_version="reliability_test_v2"),
        evaluated_at=evaluated,
    )

    assert result.policy_version == "reliability_test_v2"
    assert result.evaluated_at == evaluated
    assert not hasattr(result, "confidence")


def test_timezone_naive_evaluation_time_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        assess_reliability(
            eligibility(), feature(), freshness(), evaluated_at=datetime(2026, 10, 1)
        )
