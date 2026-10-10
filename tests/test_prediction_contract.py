from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    DataFreshness,
    FreshnessStatus,
    PredictionOutput,
    PredictionStatus,
    Reliability,
    ReliabilityStatus,
    Uncertainty,
)


UTC = timezone.utc


def make_payload(**overrides):
    as_of = datetime(2026, 10, 10, 0, 0, tzinfo=UTC)
    payload = {
        "tenant_id": "tenant_synthetic",
        "customer_id": "customer_synthetic_001",
        "prediction_id": "prediction_synthetic_001",
        "prediction_run_id": "run_synthetic_001",
        "as_of": as_of,
        "generated_at": as_of + timedelta(seconds=10),
        "status": "scored",
        "p_churn_7d": 0.12,
        "p_churn_14d": 0.38,
        "p_churn_30d": 0.81,
        "feature_version": "features_synthetic_v1",
        "model_version": "model_synthetic_v1",
        "calibration_version": "calibration_synthetic_v1",
        "label_policy_version": "labels_synthetic_v1",
        "reliability": {"status": "sufficient_evidence", "reasons": []},
        "data_freshness": {
            "status": "fresh",
            "input_data_as_of": as_of,
            "stale_sources": [],
        },
        "uncertainty": {
            "status": "not_quantified",
            "method": "none",
            "intervals": None,
        },
        "explanations_by_horizon": {},
    }
    payload.update(overrides)
    return payload


def test_valid_scored_prediction():
    output = PredictionOutput.model_validate(make_payload())

    assert output.status is PredictionStatus.SCORED
    assert output.prediction_id != output.prediction_run_id
    assert output.p_churn_7d <= output.p_churn_14d <= output.p_churn_30d


@pytest.mark.parametrize(
    "status",
    [
        PredictionStatus.ABSTAINED,
        PredictionStatus.KNOWN_CANCELLATION,
        PredictionStatus.NOT_ELIGIBLE,
    ],
)
def test_valid_non_scored_predictions_have_null_probabilities(status):
    output = PredictionOutput.model_validate(
        make_payload(
            status=status,
            p_churn_7d=None,
            p_churn_14d=None,
            p_churn_30d=None,
        )
    )

    assert output.status is status
    assert output.p_churn_7d is None
    assert output.p_churn_14d is None
    assert output.p_churn_30d is None


@pytest.mark.parametrize("field,value", [("p_churn_7d", -0.01), ("p_churn_30d", 1.01)])
def test_probability_must_be_between_zero_and_one(field, value):
    with pytest.raises(ValidationError):
        PredictionOutput.model_validate(make_payload(**{field: value}))


def test_invalid_horizon_ordering_is_rejected():
    with pytest.raises(ValidationError, match="p_churn_7d"):
        PredictionOutput.model_validate(
            make_payload(p_churn_7d=0.50, p_churn_14d=0.40, p_churn_30d=0.80)
        )


def test_scored_prediction_requires_all_probabilities():
    with pytest.raises(ValidationError, match="require"):
        PredictionOutput.model_validate(make_payload(p_churn_14d=None))


def test_non_scored_prediction_rejects_non_null_probability():
    with pytest.raises(ValidationError, match="must have null"):
        PredictionOutput.model_validate(
            make_payload(
                status=PredictionStatus.ABSTAINED,
                p_churn_7d=None,
                p_churn_14d=None,
                p_churn_30d=0.10,
            )
        )


def test_invalid_reliability_status_is_rejected():
    with pytest.raises(ValidationError):
        PredictionOutput.model_validate(
            make_payload(reliability={"status": "confidence_90_percent"})
        )


def test_invalid_freshness_status_is_rejected():
    with pytest.raises(ValidationError):
        PredictionOutput.model_validate(
            make_payload(data_freshness={"status": "probably_fresh"})
        )


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "customer_id", "prediction_id", "prediction_run_id", "feature_version"],
)
def test_empty_ids_are_rejected(field):
    with pytest.raises(ValidationError):
        PredictionOutput.model_validate(make_payload(**{field: "   "}))


def test_prediction_and_run_ids_cannot_be_conflated():
    with pytest.raises(ValidationError, match="distinct identities"):
        PredictionOutput.model_validate(
            make_payload(prediction_run_id="prediction_synthetic_001")
        )


def test_timestamps_must_be_timezone_aware():
    with pytest.raises(ValidationError):
        PredictionOutput.model_validate(
            make_payload(as_of=datetime(2026, 10, 10), generated_at=datetime(2026, 10, 10))
        )


def test_uncertainty_rejects_unsupported_values():
    with pytest.raises(ValidationError):
        PredictionOutput.model_validate(
            make_payload(
                uncertainty={
                    "status": "validated_interval",
                    "method": "bootstrap",
                    "intervals": {"low": 0.1, "high": 0.2},
                }
            )
        )


def test_json_serialization_and_deserialization_preserve_contract_fields():
    output = PredictionOutput.model_validate(make_payload())
    encoded = output.model_dump_json()
    decoded = PredictionOutput.model_validate_json(encoded)
    json_payload = output.model_dump(mode="json")

    assert decoded == output
    assert json_payload["prediction_id"] == "prediction_synthetic_001"
    assert json_payload["prediction_run_id"] == "run_synthetic_001"
    assert json_payload["p_churn_7d"] == 0.12
    assert json_payload["p_churn_14d"] == 0.38
    assert json_payload["p_churn_30d"] == 0.81
    assert json_payload["explanations_by_horizon"] == {}
    assert json_payload["uncertainty"] == {
        "status": "not_quantified",
        "method": "none",
        "intervals": None,
    }


def test_nested_contract_models_use_canonical_status_values():
    reliability = Reliability(status=ReliabilityStatus.LIMITED_EVIDENCE)
    freshness = DataFreshness(status=FreshnessStatus.PARTIALLY_STALE)
    uncertainty = Uncertainty()

    assert reliability.model_dump(mode="json")["status"] == "limited_evidence"
    assert freshness.model_dump(mode="json")["status"] == "partially_stale"
    assert uncertainty.model_dump(mode="json") == {
        "status": "not_quantified",
        "method": "none",
        "intervals": None,
    }
