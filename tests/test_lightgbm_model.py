from datetime import datetime, timedelta, timezone
import pickle

import pytest

from retainiq_prediction import (
    BaselineScoreKind,
    BaselineStatus,
    ChurnLabel,
    ChurnType,
    FeatureQuality,
    FeatureSnapshot,
    FeatureValues,
    LIGHTGBM_AVAILABLE,
    LIGHTGBM_VERSION,
    LabelStatus,
    LightGBMConfig,
    LightGBMModel,
    MODEL_FEATURE_ALLOWLIST,
    PersonalBaselineStatus,
    SnapshotRecord,
    SplitName,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitter,
    UsageCoverageStatus,
)
from retainiq_prediction.baselines import FeatureVectorizer
from retainiq_prediction.dataset_readiness import DatasetStatus


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)
BOUNDARIES = TemporalSplitBoundaries(
    train_start=BASE,
    train_end=BASE + timedelta(days=20),
    validation_end=BASE + timedelta(days=30),
    calibration_end=BASE + timedelta(days=40),
    test_end=BASE + timedelta(days=50),
)


def at(day: int) -> datetime:
    return BASE + timedelta(days=day)


def feature(
    day: int,
    *,
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    ratio: float | None = 0.8,
) -> FeatureSnapshot:
    cutoff = at(day)
    available = ratio is not None
    return FeatureSnapshot(
        tenant_id=tenant_id,
        customer_id=customer_id,
        as_of=cutoff,
        feature_version="features_personalized_baseline_v1",
        data_cutoff_at=cutoff,
        feature_values=FeatureValues(
            sessions_prev_7d=4 if available else None,
            sessions_prev_30d=16 if available else None,
            days_since_last_observed_session=2 if available else None,
            recent_usage_trend=-0.5 if available else None,
            observed_weeks=4 if available else 0,
            valid_usage_history=available,
            historical_avg_sessions_per_week=5.0 if available else None,
            recent_avg_sessions_per_week=4.0 if available else None,
            absolute_usage_deviation=-1.0 if available else None,
            percentage_usage_deviation=-0.2 if available else None,
            recent_to_baseline_usage_ratio=ratio,
            historical_weekly_usage_variability=1.0 if available else None,
            personal_baseline_availability_status=(
                PersonalBaselineStatus.AVAILABLE
                if available
                else PersonalBaselineStatus.UNAVAILABLE
            ),
        ),
        data_quality=FeatureQuality(
            usage_coverage_status=(
                UsageCoverageStatus.COMPLETE
                if available
                else UsageCoverageStatus.UNKNOWN
            ),
            personal_baseline_status=(
                PersonalBaselineStatus.AVAILABLE
                if available
                else PersonalBaselineStatus.UNAVAILABLE
            ),
            observed_history_days=35 if available else 0,
            observed_weeks=4 if available else 0,
            baseline_weeks_requested=4,
            baseline_weeks_available=4 if available else 0,
            recent_window_covered=available,
            baseline_window_covered=available,
        ),
    )


def churn_label(
    day: int,
    horizon: int,
    value: int,
    *,
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    evaluation_day: int | None = None,
    policy: str = "labels_test_v1",
) -> ChurnLabel:
    evaluation = day + 1 if evaluation_day is None else evaluation_day
    return ChurnLabel(
        tenant_id=tenant_id,
        customer_id=customer_id,
        as_of=at(day),
        evaluation_as_of=at(evaluation),
        horizon_days=horizon,  # type: ignore[arg-type]
        label=value,  # type: ignore[arg-type]
        label_status=LabelStatus.POSITIVE if value else LabelStatus.NEGATIVE,
        churn_type=ChurnType.VOLUNTARY_CANCELLATION if value else None,
        churn_effective_at=at(day + 1) if value else None,
        label_observed_through=at(evaluation),
        label_policy_version=policy,
        source_evidence_refs=(f"evidence-{tenant_id}-{customer_id}-{day}-{horizon}",),
        label_generated_at=at(evaluation),
    )


def row(
    day: int,
    value: int,
    *,
    tenant_id: str = "tenant-a",
    customer_id: str | None = None,
    evaluation_day: int | None = None,
) -> SnapshotRecord:
    account = customer_id or f"customer-{tenant_id}-{day}"
    snapshot = feature(
        day,
        tenant_id=tenant_id,
        customer_id=account,
        ratio=0.2 if value else 0.8,
    )
    return SnapshotRecord(
        feature_snapshot=snapshot,
        labels=tuple(
            churn_label(
                day,
                horizon,
                value,
                tenant_id=tenant_id,
                customer_id=account,
                evaluation_day=evaluation_day,
            )
            for horizon in (7, 14, 30)
        ),
    )


def split_for_training(rows: list[SnapshotRecord] | None = None):
    records = rows or [
        row(1, 0),
        row(2, 1),
        row(3, 0),
        row(4, 1),
        row(21, 0),
        row(22, 1),
        row(31, 0),
        row(32, 1),
        row(41, 0),
        row(42, 1),
    ]
    return TemporalSplitter(
        TemporalSplitConfig(
            boundaries=BOUNDARIES,
            dataset_identifier="synthetic-lightgbm-fixture",
            authorized_dataset=False,
            minimum_samples_per_horizon=2,
        )
    ).split(records)


def model(**kwargs) -> LightGBMModel:
    return LightGBMModel(
        LightGBMConfig(
            n_estimators=10,
            num_leaves=3,
            max_depth=2,
            min_child_samples=1,
            **kwargs,
        )
    )


def test_lightgbm_imports_successfully():
    assert LIGHTGBM_AVAILABLE is True
    assert LIGHTGBM_VERSION == "4.7.0"


def test_model_fits_valid_synthetic_training_data():
    result = model().fit(split_for_training(), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.training_snapshot_count == 4
    assert result.positive_count == 2
    assert result.negative_count == 2
    assert result.metadata is not None


def test_independent_models_support_all_horizons():
    split = split_for_training()
    results = [model().fit(split, horizon_days=horizon) for horizon in (7, 14, 30)]

    assert [result.horizon_days for result in results] == [7, 14, 30]
    assert all(result.status is BaselineStatus.READY for result in results)
    assert all(result.metadata.prediction_horizon_days == result.horizon_days for result in results)


def test_horizon_specific_masks_exclude_unknown_labels():
    rows = [row(1, 0), row(2, 1), row(3, 0), row(4, 1)]
    unknown_labels = tuple(
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
        for item in rows[0].labels
    )
    rows[0] = rows[0].model_copy(update={"labels": unknown_labels})
    result = model().fit(split_for_training(rows), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.training_snapshot_count == 3


def test_immature_labels_are_excluded_by_temporal_splitter():
    rows = [row(19, 0, evaluation_day=21), row(2, 1), row(3, 0), row(4, 1)]
    result = model().fit(split_for_training(rows), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.training_snapshot_count == 3


def test_single_class_data_returns_not_ready():
    result = model().fit(
        split_for_training([row(1, 1), row(2, 1), row(3, 1), row(4, 1)]),
        horizon_days=14,
    )

    assert result.status is BaselineStatus.NOT_READY
    assert "one class" in (result.reason or "")


def test_insufficient_samples_return_not_ready():
    result = model().fit(split_for_training([row(1, 0)]), horizon_days=30)

    assert result.status is BaselineStatus.NOT_READY
    assert result.training_snapshot_count == 1
    assert "insufficient" in (result.reason or "")


def test_train_only_preprocessing_metadata_is_preserved():
    result = model().fit(split_for_training(), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.metadata.preprocessing_metadata == {
        "strategy": "none",
        "missing_value_handling": "native_lightgbm",
        "feature_order_locked": True,
    }
    assert result.metadata.training_cutoff == BOUNDARIES.train_end


def test_validation_is_used_only_for_optional_early_stopping():
    result = model(use_validation_early_stopping=True).fit(
        split_for_training(), horizon_days=7
    )

    assert result.status is BaselineStatus.READY
    assert result.training_snapshot_count == 4
    assert result.metadata.training_configuration["validation_early_stopping"] is True


def test_calibration_and_test_partitions_are_not_used_for_fitting():
    result = model().fit(split_for_training(), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.training_snapshot_count == 4
    assert result.metadata.training_cutoff == BOUNDARIES.train_end
    assert result.metadata.training_configuration["validation_early_stopping"] is False


def test_feature_names_and_order_are_preserved():
    result = model().fit(split_for_training(), horizon_days=7)

    assert result.metadata.feature_names == MODEL_FEATURE_ALLOWLIST


def test_forbidden_features_cannot_enter_model_vectorizer():
    with pytest.raises(ValueError, match="unsupported modeling features"):
        FeatureVectorizer(("customer_id",))
    assert "tenant_id" not in MODEL_FEATURE_ALLOWLIST
    assert "label" not in MODEL_FEATURE_ALLOWLIST
    assert "churn_effective_at" not in MODEL_FEATURE_ALLOWLIST


def test_fixed_seed_and_configuration_are_reproducible():
    split = split_for_training()
    first_model = model()
    first = first_model.fit(split, horizon_days=7)
    second_model = model()
    second = second_model.fit(split, horizon_days=7)
    prediction_a = first_model.predict(feature(5, ratio=0.3), horizon_days=7)
    prediction_b = second_model.predict(feature(5, ratio=0.3), horizon_days=7)

    assert first.metadata == second.metadata
    assert prediction_a.status is BaselineStatus.READY
    assert prediction_a.score == prediction_b.score


def test_fitted_predictions_are_explicitly_uncalibrated():
    fitted = model()
    result = fitted.fit(split_for_training(), horizon_days=7)
    prediction = fitted.predict(feature(5, ratio=0.3), horizon_days=7)

    assert result.metadata.calibration_status == "not_calibrated"
    assert prediction.status is BaselineStatus.READY
    assert prediction.score_kind is BaselineScoreKind.UNCALIBRATED_PROBABILITY
    assert 0 <= prediction.score <= 1


def test_no_automatic_horizon_coherence_is_claimed():
    split = split_for_training()
    predictions = []
    for horizon in (7, 14, 30):
        fitted = model()
        fitted.fit(split, horizon_days=horizon)
        predictions.append(fitted.predict(feature(5, ratio=0.3), horizon_days=horizon))

    assert all(item.score_kind is BaselineScoreKind.UNCALIBRATED_PROBABILITY for item in predictions)
    assert not hasattr(predictions[0], "p_churn_7d")


def test_tenant_scoped_training_filters_records():
    rows = [
        row(1, 0, tenant_id="tenant-a"),
        row(2, 1, tenant_id="tenant-a"),
        row(3, 0, tenant_id="tenant-b"),
        row(4, 1, tenant_id="tenant-b"),
    ]
    result = model(tenant_id="tenant-a").fit(split_for_training(rows), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.training_snapshot_count == 2
    assert result.metadata.tenant_scope == "tenant-a"


def test_out_of_scope_tenant_cannot_be_scored():
    fitted = model(tenant_id="tenant-a")
    fitted.fit(split_for_training(), horizon_days=7)

    prediction = fitted.predict(
        feature(5, tenant_id="tenant-b", customer_id="customer-b", ratio=0.3),
        horizon_days=7,
    )

    assert prediction.status is BaselineStatus.NOT_READY
    assert "tenant scope" in prediction.reasons[0]


def test_synthetic_dataset_status_is_not_production_readiness():
    result = model().fit(split_for_training(), horizon_days=7)

    assert result.metadata.training_dataset_status is DatasetStatus.BLOCKED
    assert result.metadata.training_dataset_provenance == "synthetic-lightgbm-fixture"


def test_artifact_save_and_reload_preserves_metadata(tmp_path):
    fitted = model()
    original = fitted.fit(split_for_training(), horizon_days=14)
    path = tmp_path / "lightgbm-model.pkl"
    fitted.save(path)
    restored = LightGBMModel.load(path, trusted_root=tmp_path)
    prediction = restored.predict(feature(5, ratio=0.3), horizon_days=14)

    assert restored.fit_result == original
    assert restored.metadata == original.metadata
    assert prediction.status is BaselineStatus.READY


def test_artifact_reload_rejects_horizon_mismatch(tmp_path):
    fitted = model()
    fitted.fit(split_for_training(), horizon_days=14)
    path = tmp_path / "lightgbm-model.pkl"
    fitted.save(path)
    with path.open("rb") as handle:
        artifact = pickle.load(handle)
    artifact["horizon_days"] = 7
    with path.open("wb") as handle:
        pickle.dump(artifact, handle)

    with pytest.raises(ValueError, match="horizon does not match fit metadata"):
        LightGBMModel.load(path, trusted_root=tmp_path)


def test_missing_or_incompatible_artifacts_fail_safely(tmp_path):
    with pytest.raises(ValueError, match="trusted root"):
        LightGBMModel.load(tmp_path / "missing.pkl", trusted_root=tmp_path)

    malformed = tmp_path / "malformed.pkl"
    with malformed.open("wb") as handle:
        pickle.dump({"artifact_type": "wrong"}, handle)
    with pytest.raises(ValueError, match="unsupported LightGBM artifact type"):
        LightGBMModel.load(malformed, trusted_root=tmp_path)


def test_cpu_only_and_class_weight_configuration_are_recorded():
    result = model(class_weight="balanced").fit(split_for_training(), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.metadata.training_configuration["device_type"] == "cpu"
    assert result.metadata.training_configuration["n_jobs"] == 1
    assert result.metadata.training_configuration["class_weight"] == "balanced"
