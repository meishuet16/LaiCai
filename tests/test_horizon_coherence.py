import math

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    BaselineStatus,
    CalibrationBundleReadiness,
    CalibratedHorizonBundle,
    CalibratedProbability,
    CoherenceMethod,
    DatasetStatus,
    HorizonProbabilities,
    assess_calibrated_bundle_readiness,
    calibrated_bundle_from_outputs,
    enforce_horizon_coherence,
)


def output(
    horizon: int,
    probability: float,
    *,
    model_version: str = "lightgbm_baseline_v1",
    calibration_version: str = "calibration_sigmoid_v1",
    feature_version: str = "features_personalized_baseline_v1",
    label_policy_version: str = "labels_test_v1",
    status: DatasetStatus = DatasetStatus.BLOCKED,
) -> CalibratedProbability:
    return CalibratedProbability(
        horizon_days=horizon,  # type: ignore[arg-type]
        raw_probability=probability,
        calibrated_probability=probability,
        calibration_version=calibration_version,
        model_version=model_version,
        feature_version=feature_version,
        label_policy_version=label_policy_version,
        empirical_validation_status=status,
    )


def complete_outputs(*, status: DatasetStatus = DatasetStatus.BLOCKED):
    return [output(7, 0.2, status=status), output(14, 0.4, status=status), output(30, 0.8, status=status)]


def test_already_monotonic_probabilities_are_unchanged():
    probabilities = HorizonProbabilities(p7=0.2, p14=0.4, p30=0.8)

    result = enforce_horizon_coherence(probabilities)

    assert result.adjustment_applied is False
    assert result.adjusted == probabilities
    assert result.adjustment_method is None


def test_ordering_violations_are_detected():
    probabilities = HorizonProbabilities(p7=0.65, p14=0.42, p30=0.78)

    assert probabilities.is_monotonic is False
    result = enforce_horizon_coherence(probabilities)
    assert result.adjustment_applied is True


def test_cumulative_max_adjustment_is_explicit_and_ordered():
    result = enforce_horizon_coherence(
        HorizonProbabilities(p7=0.65, p14=0.42, p30=0.78)
    )

    assert result.adjusted.p7 == 0.65
    assert result.adjusted.p14 == 0.65
    assert result.adjusted.p30 == 0.78
    assert result.adjusted.is_monotonic is True
    assert result.adjustment_method is CoherenceMethod.CUMULATIVE_MAX
    assert "calibration properties may change" in result.metadata["limitation"]


def test_nan_and_infinity_are_rejected():
    with pytest.raises((ValidationError, ValueError)):
        HorizonProbabilities(p7=math.nan, p14=0.2, p30=0.3)
    with pytest.raises((ValidationError, ValueError)):
        HorizonProbabilities(p7=0.1, p14=math.inf, p30=0.3)


def test_out_of_range_probabilities_are_rejected():
    with pytest.raises(ValidationError):
        HorizonProbabilities(p7=-0.1, p14=0.2, p30=0.3)
    with pytest.raises(ValidationError):
        HorizonProbabilities(p7=0.1, p14=0.2, p30=1.1)


def test_missing_horizon_probabilities_are_rejected():
    with pytest.raises(ValidationError):
        HorizonProbabilities(p7=0.1, p14=0.2)  # type: ignore[call-arg]


def test_calibrated_bundle_requires_all_horizons():
    with pytest.raises(ValueError, match="missing calibrated horizons"):
        calibrated_bundle_from_outputs([output(7, 0.2), output(14, 0.4)])


def test_calibrated_bundle_rejects_incompatible_metadata():
    with pytest.raises(ValueError, match="incompatible metadata"):
        calibrated_bundle_from_outputs(
            [output(7, 0.2), output(14, 0.4), output(30, 0.8, model_version="other")]
        )


def test_bundle_metadata_is_preserved_through_adjustment():
    bundle = calibrated_bundle_from_outputs(complete_outputs())
    result = enforce_horizon_coherence(bundle)

    assert result.metadata["model_version"] == "lightgbm_baseline_v1"
    assert result.metadata["calibration_version"] == "calibration_sigmoid_v1"
    assert result.metadata["empirical_validation_status"] == DatasetStatus.BLOCKED.value


def test_missing_calibrator_prevents_production_readiness():
    readiness = assess_calibrated_bundle_readiness({}, {})

    assert readiness.status is BaselineStatus.NOT_READY
    assert readiness.missing_horizons == (7, 14, 30)


def test_synthetic_ready_models_remain_not_ready_for_production_data_gate():
    from test_calibration import fitted_model, split_with_four_calibration_rows
    from retainiq_prediction import ProbabilityCalibrator

    split = split_with_four_calibration_rows()
    models = {}
    calibrators = {}
    for horizon in (7, 14, 30):
        fitted = fitted_model(horizon)
        calibrator = ProbabilityCalibrator()
        fitted_result = calibrator.fit(fitted, split, horizon_days=horizon)
        assert fitted_result.status is BaselineStatus.READY
        models[horizon] = fitted
        calibrators[horizon] = calibrator

    readiness = assess_calibrated_bundle_readiness(models, calibrators)

    assert readiness.status is BaselineStatus.NOT_READY
    assert any("blocked" in reason for reason in readiness.reasons)


def test_complete_real_data_gate_can_be_represented_without_changing_predictionoutput():
    bundle = CalibratedHorizonBundle(
        probabilities=HorizonProbabilities(p7=0.1, p14=0.2, p30=0.3),
        model_version="model_v1",
        calibration_version="calibration_v1",
        feature_version="features_v1",
        label_policy_version="labels_v1",
        empirical_validation_status=DatasetStatus.PASS,
    )

    result = enforce_horizon_coherence(bundle)

    assert result.adjustment_applied is False
    assert result.metadata["empirical_validation_status"] == DatasetStatus.PASS.value
