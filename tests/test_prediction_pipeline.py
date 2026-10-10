from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    CalibrationConfig,
    ExplanationReasonCode,
    ExplanationStatus,
    FeatureBuilder,
    FeatureBuilderConfig,
    InMemoryPointInTimeAdapter,
    LightGBMExplainer,
    PipelineExecutionMode,
    PipelineReasonCode,
    PipelineStatus,
    PredictionOutput,
    PredictionPipeline,
    PredictionPipelineConfig,
    PredictionRequest,
    PredictionStatus,
    ProbabilityCalibrator,
    SourceFreshnessEvidence,
    SubscriptionFact,
    UsageCoverage,
    UsageFact,
)

from test_calibration import fitted_model, split_with_four_calibration_rows


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)
CUTOFF = BASE + timedelta(days=70)
GENERATED = CUTOFF + timedelta(minutes=1)


def at(day: int) -> datetime:
    return BASE + timedelta(days=day)


def subscription(
    *,
    customer_id: str = "customer-a",
    tenant_id: str = "tenant-a",
    status: str = "active",
    is_paying: bool | None = True,
    cancellation_requested_at: datetime | None = None,
    record_id: str = "subscription-1",
) -> SubscriptionFact:
    return SubscriptionFact(
        record_id=record_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        source="synthetic_billing",
        occurred_at=at(1),
        source_available_at=CUTOFF,
        received_at=CUTOFF,
        subscription_id=record_id,
        status=status,
        is_paying=is_paying,
        cancellation_requested_at=cancellation_requested_at,
    )


def usage(record_id: str, day: int, *, tenant_id: str = "tenant-a") -> UsageFact:
    return UsageFact(
        record_id=record_id,
        tenant_id=tenant_id,
        customer_id="customer-a",
        source="synthetic_usage",
        event_type="session_started",
        occurred_at=at(day),
        source_available_at=CUTOFF,
        received_at=CUTOFF,
    )


def coverage() -> UsageCoverage:
    return UsageCoverage(
        coverage_id="usage-coverage-1",
        source="synthetic_usage",
        observed_from=CUTOFF - timedelta(days=35),
        observed_to=CUTOFF,
        available_at=CUTOFF,
        complete=True,
    )


def source_evidence(*, stale_lifecycle: bool = False, include_billing: bool = True):
    watermark = CUTOFF - timedelta(days=3) if stale_lifecycle else CUTOFF
    evidence = [
        SourceFreshnessEvidence(
            tenant_id="tenant-a",
            customer_id="customer-a",
            source="subscription_lifecycle",
            source_available_at=CUTOFF,
            received_at=CUTOFF,
            watermark_at=watermark,
            complete=True,
            source_record_refs=("subscription-1",),
        ),
        SourceFreshnessEvidence(
            tenant_id="tenant-a",
            customer_id="customer-a",
            source="usage_coverage",
            source_available_at=CUTOFF,
            received_at=CUTOFF,
            watermark_at=CUTOFF,
            complete=True,
            source_record_refs=("usage-coverage-1",),
        ),
    ]
    if include_billing:
        evidence.append(
            SourceFreshnessEvidence(
                tenant_id="tenant-a",
                customer_id="customer-a",
                source="billing_events",
                source_available_at=CUTOFF,
                received_at=CUTOFF,
                watermark_at=CUTOFF,
                complete=True,
            )
        )
    return tuple(evidence)


def facts(*, active: SubscriptionFact | None = None) -> list:
    items = [active or subscription()]
    for week, count in enumerate((2, 4, 6, 8)):
        items.extend(usage(f"baseline-{week}-{index}", 35 + week * 7 + index) for index in range(count))
    items.append(usage("recent", 66))
    return items


@pytest.fixture(scope="module")
def fitted_bundle():
    split = split_with_four_calibration_rows()
    models = {}
    calibrators = {}
    for horizon in (7, 14, 30):
        model = fitted_model(horizon)
        calibrator = ProbabilityCalibrator(CalibrationConfig(minimum_samples=4))
        assert calibrator.fit(model, split, horizon_days=horizon).status.value == "ready"
        models[horizon] = model
        calibrators[horizon] = calibrator
    return models, calibrators


def request(**kwargs) -> PredictionRequest:
    values = {
        "tenant_id": "tenant-a",
        "customer_id": "customer-a",
        "as_of": CUTOFF,
        "prediction_run_id": "run-synthetic-001",
        "usage_coverage": (coverage(),),
        "freshness_evidence": source_evidence(),
    }
    values.update(kwargs)
    return PredictionRequest(**values)


def pipeline(
    fitted_bundle,
    *,
    mode=PipelineExecutionMode.SYNTHETIC_TEST_ONLY,
    facts_override=None,
    explainer=None,
    **kwargs,
):
    models, calibrators = fitted_bundle
    adapter = InMemoryPointInTimeAdapter(facts_override or facts())
    return PredictionPipeline(
        adapter,
        models=models,
        calibrators=calibrators,
        explainer=explainer,
        config=PredictionPipelineConfig(execution_mode=mode, **kwargs),
        clock=lambda: GENERATED,
    )


def test_fully_integrated_synthetic_scoring_path_is_non_deployable(fitted_bundle):
    result = pipeline(fitted_bundle).run(request())

    assert result.pipeline_status is PipelineStatus.COMPLETED
    assert result.prediction is not None
    assert result.prediction.status is PredictionStatus.SCORED
    assert result.synthetic_test_only is True
    assert result.deployable is False
    assert result.prediction.prediction_id != result.prediction.prediction_run_id
    assert 0 <= result.prediction.p_churn_7d <= result.prediction.p_churn_14d <= result.prediction.p_churn_30d <= 1
    assert result.prediction.uncertainty.model_dump() == {
        "status": "not_quantified",
        "method": "none",
        "intervals": None,
    }


def test_all_models_and_matching_calibrators_are_invoked(fitted_bundle):
    models, calibrators = fitted_bundle
    model_spies = {}
    for horizon, model in models.items():
        model.predict = Mock(wraps=model.predict)
        model_spies[horizon] = model
    calibrator_spies = {}
    for horizon, calibrator in calibrators.items():
        calibrator.calibrate_prediction = Mock(wraps=calibrator.calibrate_prediction)
        calibrator_spies[horizon] = calibrator
    pipe = pipeline((model_spies, calibrator_spies))

    result = pipe.run(request())

    assert result.pipeline_status is PipelineStatus.COMPLETED
    assert all(spy.predict.call_count == 1 for spy in model_spies.values())
    assert all(spy.calibrate_prediction.call_count == 1 for spy in calibrator_spies.values())
    assert result.safe_diagnostics["raw_probabilities"].keys() == {"7", "14", "30"}
    assert result.safe_diagnostics["calibrated_probabilities"].keys() == {"7", "14", "30"}


def test_shap_uses_each_matching_model_and_preserves_raw_output_limitations(fitted_bundle):
    explainer = Mock(wraps=LightGBMExplainer())
    result = pipeline(fitted_bundle, explainer=explainer).run(request())

    assert result.pipeline_status is PipelineStatus.COMPLETED
    assert explainer.explain.call_count == 3
    assert set(result.prediction.explanations_by_horizon) == {"7", "14", "30"}
    for values in result.prediction.explanations_by_horizon.values():
        explanation = values[0]
        assert explanation["explained_output_space"] == "raw_lightgbm_margin_log_odds"
        assert any("calibrated" in item for item in explanation["limitations"])


def test_known_cancellation_bypasses_all_risk_models(fitted_bundle):
    models, calibrators = fitted_bundle
    model_spies = {}
    for horizon, model in models.items():
        model.predict = Mock(wraps=model.predict)
        model_spies[horizon] = model
    calibrator_spies = {}
    for horizon, calibrator in calibrators.items():
        calibrator.calibrate_prediction = Mock(wraps=calibrator.calibrate_prediction)
        calibrator_spies[horizon] = calibrator
    cancelled = subscription(cancellation_requested_at=CUTOFF - timedelta(hours=1))
    result = pipeline((model_spies, calibrator_spies), facts_override=facts(active=cancelled)).run(request())

    assert result.pipeline_status is PipelineStatus.KNOWN_CANCELLATION
    assert result.prediction.status is PredictionStatus.KNOWN_CANCELLATION
    assert all(spy.predict.call_count == 0 for spy in model_spies.values())
    assert all(spy.calibrate_prediction.call_count == 0 for spy in calibrator_spies.values())


def test_not_eligible_bypasses_risk_models(fitted_bundle):
    models, calibrators = fitted_bundle
    model_spies = {}
    for horizon, model in models.items():
        model.predict = Mock(wraps=model.predict)
        model_spies[horizon] = model
    terminal = subscription(status="terminated", is_paying=False)
    result = pipeline((model_spies, calibrators), facts_override=facts(active=terminal)).run(request())

    assert result.pipeline_status is PipelineStatus.NOT_ELIGIBLE
    assert result.prediction.status is PredictionStatus.NOT_ELIGIBLE
    assert all(spy.predict.call_count == 0 for spy in model_spies.values())


def test_insufficient_evidence_abstains_with_null_probabilities(fitted_bundle):
    result = pipeline(fitted_bundle, facts_override=[subscription()]).run(
        request(usage_coverage=None)
    )

    assert result.pipeline_status is PipelineStatus.ABSTAINED_DUE_TO_INSUFFICIENT_EVIDENCE
    assert result.prediction.status is PredictionStatus.ABSTAINED
    assert result.prediction.p_churn_7d is None
    assert result.prediction.p_churn_14d is None
    assert result.prediction.p_churn_30d is None


def test_limited_evidence_preserves_warnings_and_can_score_under_policy(fitted_bundle):
    result = pipeline(fitted_bundle).run(request(freshness_evidence=source_evidence(include_billing=False)))

    assert result.pipeline_status is PipelineStatus.COMPLETED
    assert result.prediction.reliability.status.value == "limited_evidence"
    assert result.prediction.reliability.reasons


def test_missing_model_or_calibrator_never_falls_back_to_raw_score(fitted_bundle):
    models, calibrators = fitted_bundle
    missing_model = pipeline((dict(list(models.items())[:2]), calibrators)).run(request())
    missing_calibrator = pipeline((models, dict(list(calibrators.items())[:2]))).run(request())

    assert missing_model.pipeline_status is PipelineStatus.MODEL_BUNDLE_NOT_READY
    assert missing_model.prediction is None
    assert missing_calibrator.pipeline_status is PipelineStatus.MODEL_BUNDLE_NOT_READY
    assert missing_calibrator.prediction is None


def test_feature_and_model_calibration_metadata_mismatches_are_rejected(fitted_bundle):
    models, calibrators = fitted_bundle
    mismatched_builder = FeatureBuilder(
        InMemoryPointInTimeAdapter(facts()),
        config=FeatureBuilderConfig(feature_version="different_feature_version"),
    )
    feature_mismatch = PredictionPipeline(
        InMemoryPointInTimeAdapter(facts()),
        models=models,
        calibrators=calibrators,
        feature_builder=mismatched_builder,
        config=PredictionPipelineConfig(execution_mode=PipelineExecutionMode.SYNTHETIC_TEST_ONLY),
        clock=lambda: GENERATED,
    ).run(request())
    calibration_mismatch = pipeline((models, {**calibrators, 14: calibrators[7]})).run(request())

    assert feature_mismatch.pipeline_status is PipelineStatus.ABSTAINED_DUE_TO_INSUFFICIENT_EVIDENCE
    assert PipelineReasonCode.FEATURE_VERSION_MISMATCH in feature_mismatch.reason_codes
    assert calibration_mismatch.pipeline_status is PipelineStatus.MODEL_BUNDLE_NOT_READY
    assert PipelineReasonCode.MODEL_CALIBRATION_MISMATCH in calibration_mismatch.reason_codes


def test_stale_essential_data_blocks_scoring(fitted_bundle):
    result = pipeline(fitted_bundle).run(
        request(freshness_evidence=source_evidence(stale_lifecycle=True))
    )

    assert result.pipeline_status is PipelineStatus.ABSTAINED_DUE_TO_INSUFFICIENT_EVIDENCE
    assert result.prediction.status is PredictionStatus.ABSTAINED
    assert PipelineReasonCode.ESSENTIAL_DATA_NOT_FRESH in result.reason_codes


def test_late_and_future_events_do_not_change_earlier_feature_snapshot():
    base_facts = facts()
    contaminated = base_facts + [
        usage("late", 65),
        usage("future", 71),
    ]
    contaminated[-2] = contaminated[-2].model_copy(update={"source_available_at": at(71), "received_at": at(71)})
    earlier = FeatureBuilder(InMemoryPointInTimeAdapter(base_facts)).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )
    observed = FeatureBuilder(InMemoryPointInTimeAdapter(contaminated)).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )

    observed_values = observed.feature_values.model_dump()
    earlier_values = earlier.feature_values.model_dump()
    for name in (
        "sessions_prev_7d",
        "sessions_prev_30d",
        "days_since_last_observed_session",
        "recent_usage_trend",
        "historical_avg_sessions_per_week",
        "recent_avg_sessions_per_week",
        "absolute_usage_deviation",
        "percentage_usage_deviation",
        "recent_to_baseline_usage_ratio",
        "historical_weekly_usage_variability",
    ):
        assert observed_values[name] == earlier_values[name]
    assert "late" not in observed.source_evidence_refs
    assert "future" not in observed.source_evidence_refs


def test_cross_tenant_evidence_is_not_scored(fitted_bundle):
    result = pipeline(fitted_bundle).run(
        request(tenant_id="tenant-b", freshness_evidence=source_evidence())
    )

    assert result.pipeline_status is PipelineStatus.ABSTAINED_DUE_TO_INSUFFICIENT_EVIDENCE
    assert result.prediction.p_churn_7d is None


def test_explanation_failure_is_preserved_not_fabricated(fitted_bundle):
    class FailingExplainer:
        def explain(self, model, snapshot, **kwargs):
            return ExplanationResultUnavailable(snapshot, kwargs.get("horizon_days", 7))

    result = pipeline(fitted_bundle, explainer=FailingExplainer()).run(request())

    assert result.pipeline_status is PipelineStatus.COMPLETED
    assert PipelineReasonCode.EXPLANATION_UNAVAILABLE in result.reason_codes
    assert result.prediction.explanations_by_horizon["7"][0]["explanation_status"] == "unavailable"
    assert result.prediction.explanations_by_horizon["7"][0]["feature_contributions"] == []


def test_production_mode_remains_blocked_for_synthetic_artifacts(fitted_bundle):
    result = pipeline(fitted_bundle, mode=PipelineExecutionMode.PRODUCTION).run(request())

    assert result.pipeline_status is PipelineStatus.MODEL_BUNDLE_NOT_READY
    assert result.prediction is None
    assert result.deployable is False
    assert PipelineReasonCode.PRODUCTION_DATASET_NOT_READY in result.reason_codes


def test_request_rejects_naive_timestamp():
    with pytest.raises(ValidationError):
        PredictionRequest(
            tenant_id="tenant-a",
            customer_id="customer-a",
            as_of=datetime(2026, 12, 10),
            prediction_run_id="run-1",
        )


def test_canonical_prediction_round_trip_preserves_invariants(fitted_bundle):
    result = pipeline(fitted_bundle).run(request())
    restored = PredictionOutput.model_validate_json(result.prediction.model_dump_json())

    assert restored == result.prediction
    assert restored.prediction_id != restored.prediction_run_id


class ExplanationResultUnavailable:
    def __new__(cls, snapshot, horizon):
        from retainiq_prediction import ExplanationResult

        return ExplanationResult(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=snapshot.as_of,
            horizon_days=horizon,
            explanation_method="synthetic_failure_fixture",
            explanation_version="synthetic_failure_v1",
            explanation_status=ExplanationStatus.UNAVAILABLE,
            prediction_status=PredictionStatus.SCORED,
            reason_codes=(ExplanationReasonCode.SHAP_OUTPUT_UNSUPPORTED,),
            limitations=("Synthetic explanation failure fixture.",),
        )
