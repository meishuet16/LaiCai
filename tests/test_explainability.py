from datetime import timedelta

import pytest

from retainiq_prediction import (
    ContributionDirection,
    ExplanationFormatter,
    ExplanationReasonCode,
    ExplanationStatus,
    ExplainedOutputSpace,
    LightGBMExplainer,
    PredictionStatus,
    SHAP_AVAILABLE,
)

from test_lightgbm_model import BOUNDARIES, feature, model, split_for_training


pytestmark = pytest.mark.skipif(not SHAP_AVAILABLE, reason="SHAP optional dependency is unavailable")


@pytest.fixture(scope="module")
def fitted_models():
    split = split_for_training()
    return {
        horizon: _fit_model(horizon, split)
        for horizon in (7, 14, 30)
    }


def _fit_model(horizon, split):
    fitted = model()
    result = fitted.fit(split, horizon_days=horizon)
    assert result.status.value == "ready"
    return fitted


def test_real_treeexplainer_is_available_and_explains_raw_margin(fitted_models):
    result = LightGBMExplainer().explain(
        fitted_models[7],
        feature(5, ratio=0.3),
        horizon_days=7,
    )

    assert result.explanation_status is ExplanationStatus.AVAILABLE
    assert result.explained_output_space is ExplainedOutputSpace.RAW_LIGHTGBM_MARGIN_LOG_ODDS
    assert result.explanation_method == "shap_tree_explainer"
    assert result.model_version == "lightgbm_baseline_v1"
    assert result.feature_contributions
    assert len(result.feature_contributions) == 12
    assert result.additivity_error <= result.additivity_tolerance
    assert result.actual_explained_model_output == pytest.approx(
        result.expected_base_value
        + sum(item.shap_value for item in result.feature_contributions),
        abs=result.additivity_tolerance,
    )
    assert "calibrated" in " ".join(result.limitations)
    assert "causes" in " ".join(result.limitations)


def test_independent_models_are_explainable_for_all_horizons(fitted_models):
    explainer = LightGBMExplainer()
    results = [
        explainer.explain(fitted_models[horizon], feature(5, ratio=0.3), horizon_days=horizon)
        for horizon in (7, 14, 30)
    ]

    assert [result.horizon_days for result in results] == [7, 14, 30]
    assert all(result.explanation_status is ExplanationStatus.AVAILABLE for result in results)
    assert all(
        {item.feature_name for item in result.feature_contributions}
        == set(fitted_models[7].metadata.feature_names)
        for result in results
    )


def test_horizon_mismatch_and_version_mismatch_fail_closed(fitted_models):
    explainer = LightGBMExplainer()
    wrong_horizon = explainer.explain(
        fitted_models[7], feature(5, ratio=0.3), horizon_days=14
    )
    wrong_model_version = explainer.explain(
        fitted_models[7],
        feature(5, ratio=0.3),
        horizon_days=7,
        expected_model_version="different-model",
    )

    assert wrong_horizon.explanation_status is ExplanationStatus.UNAVAILABLE
    assert ExplanationReasonCode.MODEL_ARTIFACT_INCOMPATIBLE in wrong_horizon.reason_codes
    assert wrong_model_version.explanation_status is ExplanationStatus.UNAVAILABLE
    assert ExplanationReasonCode.MODEL_VERSION_MISMATCH in wrong_model_version.reason_codes


@pytest.mark.parametrize(
    "status",
    [
        PredictionStatus.ABSTAINED,
        PredictionStatus.KNOWN_CANCELLATION,
        PredictionStatus.NOT_ELIGIBLE,
    ],
)
def test_non_scored_statuses_never_receive_normal_explanations(fitted_models, status):
    result = LightGBMExplainer().explain(
        fitted_models[7], feature(5, ratio=0.3), horizon_days=7, prediction_status=status
    )

    assert result.explanation_status is ExplanationStatus.UNAVAILABLE
    assert ExplanationReasonCode.PREDICTION_NOT_SCORABLE in result.reason_codes
    assert result.feature_contributions == ()


def test_missing_features_are_unavailable_without_fabrication(fitted_models):
    result = LightGBMExplainer().explain(
        fitted_models[7], feature(5, ratio=None), horizon_days=7
    )

    assert result.explanation_status is ExplanationStatus.UNAVAILABLE
    assert ExplanationReasonCode.FEATURE_INPUT_MISSING in result.reason_codes
    assert result.feature_contributions == ()


def test_tenant_customer_and_readiness_scope_are_enforced(fitted_models):
    explainer = LightGBMExplainer()
    tenant_mismatch = explainer.explain(
        fitted_models[7],
        feature(5, ratio=0.3),
        horizon_days=7,
        expected_tenant_id="other-tenant",
    )
    customer_mismatch = explainer.explain(
        fitted_models[7],
        feature(5, ratio=0.3),
        horizon_days=7,
        expected_customer_id="other-customer",
    )

    class NotReady:
        scoring_allowed = False
        model_artifacts_ready = False
        prediction_status = PredictionStatus.ABSTAINED

    not_ready = explainer.explain(
        fitted_models[7], feature(5, ratio=0.3), horizon_days=7, readiness=NotReady()
    )

    assert ExplanationReasonCode.TENANT_SCOPE_MISMATCH in tenant_mismatch.reason_codes
    assert ExplanationReasonCode.CUSTOMER_SCOPE_MISMATCH in customer_mismatch.reason_codes
    assert ExplanationReasonCode.READINESS_NOT_CONFIRMED in not_ready.reason_codes


def test_allowlist_excludes_identifiers_labels_and_cancellation_fields(fitted_models):
    result = LightGBMExplainer().explain(
        fitted_models[7], feature(5, ratio=0.3), horizon_days=7
    )
    names = {item.feature_name for item in result.feature_contributions}

    assert "tenant_id" not in names
    assert "customer_id" not in names
    assert "label" not in names
    assert "churn_effective_at" not in names
    assert "cancellation_requested_at" not in names


def test_contribution_signs_full_fidelity_and_deterministic_top_k(fitted_models):
    explainer = LightGBMExplainer()
    first = explainer.explain(
        fitted_models[7], feature(5, ratio=0.3), horizon_days=7, top_k=2
    )
    second = explainer.explain(
        fitted_models[7], feature(5, ratio=0.3), horizon_days=7, top_k=2
    )

    assert [(item.feature_name, item.shap_value) for item in first.feature_contributions] == [
        (item.feature_name, item.shap_value) for item in second.feature_contributions
    ]
    assert len(first.positive_contributors) <= 2
    assert len(first.negative_contributors) <= 2
    assert all(item.direction is ContributionDirection.POSITIVE for item in first.positive_contributors)
    assert all(item.direction is ContributionDirection.NEGATIVE for item in first.negative_contributors)
    assert first.human_readable_explanations == ExplanationFormatter.format(first)


def test_serialization_preserves_versions_units_and_non_causal_wording(fitted_models):
    result = LightGBMExplainer().explain(
        fitted_models[14], feature(5, ratio=0.3), horizon_days=14
    )
    restored = type(result).model_validate_json(result.model_dump_json())

    assert restored == result
    assert restored.explained_output_space.value == "raw_lightgbm_margin_log_odds"
    assert all("caused" not in phrase.lower() for phrase in restored.human_readable_explanations)
    assert all("prevent" not in phrase.lower() for phrase in restored.human_readable_explanations)


def test_source_refs_are_preserved_and_feature_snapshot_is_not_mutated(fitted_models):
    snapshot = feature(5, ratio=0.3).model_copy(
        update={"source_evidence_refs": ("usage-event-synthetic-1",)}
    )
    before = snapshot.model_dump_json()
    result = LightGBMExplainer().explain(fitted_models[30], snapshot, horizon_days=30)

    assert result.explanation_status is ExplanationStatus.AVAILABLE
    assert all(
        item.source_feature_refs == ("usage-event-synthetic-1",)
        for item in result.feature_contributions
    )
    assert snapshot.model_dump_json() == before


def test_boundary_fixture_uses_aware_prediction_time():
    snapshot = feature(5, ratio=0.3)
    assert snapshot.as_of.tzinfo is not None
    assert snapshot.as_of < BOUNDARIES.train_end + timedelta(days=1)
