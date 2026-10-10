"""Fixture-only integration coverage for Prompt 34 model-backed replay."""

from datetime import timedelta

import pytest

from retainiq_prediction import (
    LIGHTGBM_AVAILABLE,
    PredictionStatus,
    ProbabilityCalibrator,
    LightGBMModel,
)
from retainiq_prediction.explainability import SHAP_AVAILABLE
from retainiq_prediction.operational_inference import (
    BatchItemStatus,
    DailyPredictionBatch,
    InMemoryPredictionSnapshotStore,
    PointInTimeReplayRunner,
)

from test_calibration import fitted_model, split_with_four_calibration_rows
from test_prediction_pipeline import (
    CUTOFF,
    coverage,
    facts,
    pipeline as build_pipeline,
    source_evidence,
)
from test_prediction_pipeline import PipelineExecutionMode


pytestmark = pytest.mark.skipif(
    not LIGHTGBM_AVAILABLE or not SHAP_AVAILABLE,
    reason="LightGBM and SHAP are required for the model-backed integration fixture",
)


class ReplaySourceFixture:
    """Two-cutoff source fixture with no outcome or label interface."""

    tenant_id = "tenant-a"

    def eligible_accounts_as_of(self, as_of):
        return ("customer-a",)

    def coverage_for(self, tenant_id, customer_id, as_of):
        assert (tenant_id, customer_id) == (self.tenant_id, "customer-a")
        return (coverage(),)

    def freshness_evidence_for(self, tenant_id, customer_id, as_of):
        assert (tenant_id, customer_id) == (self.tenant_id, "customer-a")
        return source_evidence()


def _save_and_reload_bundle(tmp_path):
    split = split_with_four_calibration_rows()
    models = {}
    calibrators = {}
    for horizon in (7, 14, 30):
        model = fitted_model(horizon)
        model_path = tmp_path / "models" / str(horizon) / "model.pkl"
        model.save(model_path)
        loaded_model = LightGBMModel.load(model_path, trusted_root=tmp_path)

        calibrator = ProbabilityCalibrator()
        fit_result = calibrator.fit(loaded_model, split, horizon_days=horizon)
        assert fit_result.status.value == "ready"
        calibration_path = tmp_path / "calibrators" / str(horizon) / "calibrator.pkl"
        calibrator.save(calibration_path)
        loaded_calibrator = ProbabilityCalibrator.load(
            calibration_path,
            trusted_root=tmp_path,
        )

        assert loaded_model.metadata == model.metadata
        assert loaded_calibrator.metadata == calibrator.metadata
        models[horizon] = loaded_model
        calibrators[horizon] = loaded_calibrator
    return models, calibrators


def test_saved_bundle_scores_monotonic_shap_predictions_at_t1_and_t2(tmp_path):
    models, calibrators = _save_and_reload_bundle(tmp_path)
    prediction_pipeline = build_pipeline(
        (models, calibrators),
        mode=PipelineExecutionMode.SYNTHETIC_TEST_ONLY,
        facts_override=facts(),
    )
    store = InMemoryPredictionSnapshotStore()
    batch = DailyPredictionBatch(ReplaySourceFixture(), prediction_pipeline, store)
    t1 = CUTOFF
    t2 = CUTOFF + timedelta(days=1)

    report = PointInTimeReplayRunner(batch).replay_customer(
        "customer-a",
        (t1, t2),
        prediction_run_prefix="prompt34-fixture",
    )

    assert report.cutoffs == (t1, t2)
    assert report.prediction_run_ids == (
        "prompt34-fixture_0001",
        "prompt34-fixture_0002",
    )
    assert all(item.status is BatchItemStatus.STORED for item in report.items)
    predictions = store.history_for("tenant-a", "customer-a")
    assert len(predictions) == 2
    assert tuple(item.as_of for item in predictions) == (t1, t2)
    assert all(item.status is PredictionStatus.SCORED for item in predictions)
    for prediction in predictions:
        assert (
            prediction.p_churn_7d
            <= prediction.p_churn_14d
            <= prediction.p_churn_30d
        )
        assert set(prediction.explanations_by_horizon) == {"7", "14", "30"}
        for horizon in ("7", "14", "30"):
            explanation = prediction.explanations_by_horizon[horizon][0]
            assert explanation["explanation_status"] == "available"
            assert explanation["explained_output_space"] == "raw_lightgbm_margin_log_odds"
    assert len(report.changes) == 1
    assert report.changes[0].comparable_model_versions
    assert "not a forecast trajectory" in report.changes[0].note

