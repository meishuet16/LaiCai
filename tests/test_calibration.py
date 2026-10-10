from datetime import timedelta
import math
import pickle

import pytest

from retainiq_prediction import (
    BaselineStatus,
    CalibrationConfig,
    CalibratedProbability,
    DatasetStatus,
    LabelStatus,
    ProbabilityCalibrator,
    evaluate_probability_diagnostics,
)

from test_lightgbm_model import BOUNDARIES, at, feature, model, row, split_for_training


def split_with_four_calibration_rows():
    return split_for_training(
        [
            row(1, 0),
            row(2, 1),
            row(3, 0),
            row(4, 1),
            row(21, 0),
            row(22, 1),
            row(31, 0),
            row(32, 1),
            row(33, 0),
            row(34, 1),
            row(41, 0),
            row(42, 1),
        ]
    )


def fitted_model(horizon: int = 7):
    fitted = model()
    result = fitted.fit(split_with_four_calibration_rows(), horizon_days=horizon)
    assert result.status is BaselineStatus.READY
    return fitted


def test_valid_sigmoid_calibrator_fits_on_calibration_partition():
    split = split_with_four_calibration_rows()
    fitted = fitted_model()
    calibrator = ProbabilityCalibrator()

    result = calibrator.fit(fitted, split, horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.metadata.calibration_method == "sigmoid"
    assert result.metadata.calibration_sample_count == 4
    assert result.metadata.fitting_cutoff == BOUNDARIES.calibration_end


def test_independent_calibrators_support_all_horizons():
    split = split_with_four_calibration_rows()
    results = []
    for horizon in (7, 14, 30):
        fitted = fitted_model(horizon)
        results.append(ProbabilityCalibrator().fit(fitted, split, horizon_days=horizon))

    assert [item.horizon_days for item in results] == [7, 14, 30]
    assert all(item.status is BaselineStatus.READY for item in results)
    assert all(item.metadata.prediction_horizon_days == item.horizon_days for item in results)


def test_train_and_validation_rows_are_not_used_for_calibration():
    split = split_with_four_calibration_rows()
    result = ProbabilityCalibrator().fit(fitted_model(), split, horizon_days=7)

    assert result.metadata.calibration_sample_count == 4
    assert result.metadata.training_dataset_status is DatasetStatus.BLOCKED


def test_test_rows_are_not_used_for_calibration():
    result = ProbabilityCalibrator().fit(
        fitted_model(14), split_with_four_calibration_rows(), horizon_days=14
    )

    assert result.metadata.calibration_sample_count == 4
    assert result.metadata.fitting_cutoff == BOUNDARIES.calibration_end


def test_unknown_calibration_labels_are_excluded():
    rows = [
        row(1, 0),
        row(2, 1),
        row(3, 0),
        row(4, 1),
        row(21, 0),
        row(22, 1),
        row(31, 0),
        row(32, 1),
        row(33, 0),
        row(34, 1),
    ]
    unknown = tuple(
        item.model_copy(
            update={
                "label": None,
                "label_status": LabelStatus.UNKNOWN,
                "churn_type": None,
                "churn_effective_at": None,
            }
        )
        if item.horizon_days == 7
        else item
        for item in rows[6].labels
    )
    rows[6] = rows[6].model_copy(update={"labels": unknown})
    split = split_for_training(rows)
    result = ProbabilityCalibrator().fit(fitted_model(), split, horizon_days=7)

    assert result.status is BaselineStatus.NOT_READY
    assert "insufficient" in (result.reason or "")


def test_immature_calibration_labels_are_excluded():
    rows = [
        row(1, 0), row(2, 1), row(3, 0), row(4, 1),
        row(31, 0, evaluation_day=41), row(32, 1), row(33, 0), row(34, 1),
    ]
    result = ProbabilityCalibrator().fit(
        fitted_model(), split_for_training(rows), horizon_days=7
    )

    assert result.status is BaselineStatus.NOT_READY
    assert "insufficient" in (result.reason or "")


def test_insufficient_and_single_class_calibration_return_not_ready():
    short_config = CalibrationConfig(minimum_samples=5)
    short = ProbabilityCalibrator(short_config).fit(
        fitted_model(), split_with_four_calibration_rows(), horizon_days=7
    )
    assert short.status is BaselineStatus.NOT_READY

    all_negative = split_for_training(
        [row(1, 0), row(2, 0), row(3, 0), row(4, 0), row(31, 0), row(32, 0), row(33, 0), row(34, 0)]
    )
    one_class = ProbabilityCalibrator().fit(fitted_model(), all_negative, horizon_days=7)
    assert one_class.status is BaselineStatus.NOT_READY
    assert "positive" in (one_class.reason or "")


def test_calibrated_probability_is_finite_and_bounded():
    split = split_with_four_calibration_rows()
    fitted = fitted_model()
    calibrator = ProbabilityCalibrator()
    result = calibrator.fit(fitted, split, horizon_days=7)
    raw = fitted.predict(feature(5, ratio=0.3), horizon_days=7)
    calibrated = calibrator.calibrate_prediction(raw, fitted.metadata)

    assert result.status is BaselineStatus.READY
    assert 0 <= calibrated.calibrated_probability <= 1
    assert math.isfinite(calibrated.calibrated_probability)
    assert calibrated.empirical_validation_status is DatasetStatus.BLOCKED


def test_calibration_inputs_are_not_logit_transformed_twice():
    split = split_with_four_calibration_rows()
    fitted = fitted_model()
    calibrator = ProbabilityCalibrator()
    calibrator.fit(fitted, split, horizon_days=7)
    raw = fitted.predict(feature(5, ratio=0.3), horizon_days=7)

    calibrated = calibrator.calibrate_prediction(raw, fitted.metadata)

    assert calibrated.raw_probability == raw.score
    assert calibrator.metadata.input_semantics == "raw_probability_logit_once"


def test_calibrator_rejects_mismatched_model_metadata():
    split = split_with_four_calibration_rows()
    fitted = fitted_model()
    calibrator = ProbabilityCalibrator()
    calibrator.fit(fitted, split, horizon_days=7)
    raw = fitted.predict(feature(5, ratio=0.3), horizon_days=7)
    mismatched = fitted.metadata.model_copy(update={"model_version": "other_model"})

    with pytest.raises(ValueError, match="versions"):
        calibrator.calibrate_prediction(raw, mismatched)


def test_calibrator_artifact_round_trip_preserves_metadata_and_output(tmp_path):
    split = split_with_four_calibration_rows()
    fitted = fitted_model()
    calibrator = ProbabilityCalibrator()
    original = calibrator.fit(fitted, split, horizon_days=7)
    raw = fitted.predict(feature(5, ratio=0.3), horizon_days=7)
    before = calibrator.calibrate_prediction(raw, fitted.metadata)
    path = tmp_path / "calibrator.pkl"
    calibrator.save(path)
    restored = ProbabilityCalibrator.load(path, trusted_root=tmp_path)
    after = restored.calibrate_prediction(raw, fitted.metadata)

    assert restored.fit_result == original
    assert after == before


def test_calibrator_artifact_rejects_missing_or_incompatible_files(tmp_path):
    with pytest.raises(ValueError, match="trusted root"):
        ProbabilityCalibrator.load(tmp_path / "missing.pkl", trusted_root=tmp_path)
    bad = tmp_path / "bad.pkl"
    with bad.open("wb") as handle:
        pickle.dump({"artifact_type": "wrong"}, handle)
    with pytest.raises(ValueError, match="unsupported calibrator"):
        ProbabilityCalibrator.load(bad, trusted_root=tmp_path)


def test_post_adjustment_diagnostics_compare_raw_calibrated_and_adjusted_inputs():
    labels = [
        row(31, 0).labels[0],
        row(32, 1).labels[0],
        row(33, 0).labels[0],
        row(34, 1).labels[0],
    ]
    diagnostics = evaluate_probability_diagnostics(
        labels,
        [0.1, 0.2, 0.8, 0.9],
        [0.2, 0.4, 0.7, 0.8],
        horizon_days=7,
        adjusted_probabilities=[0.3, 0.5, 0.7, 0.9],
    )

    assert diagnostics.sample_count == 4
    assert diagnostics.adjusted_brier_score is not None
    assert diagnostics.raw_brier_score != diagnostics.calibrated_brier_score
    assert len(diagnostics.calibration_table) == 5
    assert diagnostics.empirical_validation_status is DatasetStatus.BLOCKED
