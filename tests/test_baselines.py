from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction import (
    BaselineScoreKind,
    BaselineStatus,
    ChurnLabel,
    ChurnType,
    FeatureQuality,
    FeatureSnapshot,
    FeatureValues,
    LabelStatus,
    LogisticRegressionBaseline,
    MODEL_FEATURE_ALLOWLIST,
    PersonalBaselineStatus,
    RuleBasedBaseline,
    RuleBaselineConfig,
    SKLEARN_AVAILABLE,
    SnapshotRecord,
    SplitName,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitter,
    UsageCoverageStatus,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


def snapshot(
    *,
    ratio: float | None = 0.9,
    days_since_last: int | None = 2,
    sessions_7d: int | None = 3,
    feature_version: str = "features_personalized_baseline_v1",
) -> FeatureSnapshot:
    cutoff = at(10)
    return FeatureSnapshot(
        tenant_id="tenant-a",
        customer_id="customer-a",
        as_of=cutoff,
        feature_version=feature_version,
        data_cutoff_at=cutoff,
        feature_values=FeatureValues(
            sessions_prev_7d=sessions_7d,
            sessions_prev_30d=12 if sessions_7d is not None else None,
            days_since_last_observed_session=days_since_last,
            recent_usage_trend=-1.0 if ratio is not None else None,
            observed_weeks=4 if ratio is not None else 0,
            valid_usage_history=ratio is not None,
            historical_avg_sessions_per_week=5.0 if ratio is not None else None,
            recent_avg_sessions_per_week=4.5 if ratio is not None else None,
            absolute_usage_deviation=-0.5 if ratio is not None else None,
            percentage_usage_deviation=-0.1 if ratio is not None else None,
            recent_to_baseline_usage_ratio=ratio,
            historical_weekly_usage_variability=1.0 if ratio is not None else None,
            personal_baseline_availability_status=(
                PersonalBaselineStatus.AVAILABLE
                if ratio is not None
                else PersonalBaselineStatus.UNAVAILABLE
            ),
        ),
        data_quality=FeatureQuality(
            usage_coverage_status=(
                UsageCoverageStatus.COMPLETE
                if ratio is not None
                else UsageCoverageStatus.UNKNOWN
            ),
            personal_baseline_status=(
                PersonalBaselineStatus.AVAILABLE
                if ratio is not None
                else PersonalBaselineStatus.UNAVAILABLE
            ),
            observed_history_days=35 if ratio is not None else 0,
            observed_weeks=4 if ratio is not None else 0,
            baseline_weeks_requested=4,
            baseline_weeks_available=4 if ratio is not None else 0,
            recent_window_covered=ratio is not None,
            baseline_window_covered=ratio is not None,
        ),
    )


def churn_label(
    as_of: datetime,
    horizon: int,
    value: int,
    *,
    evaluation_as_of: datetime | None = None,
    customer_id: str = "customer-a",
) -> ChurnLabel:
    effective = as_of + timedelta(days=1) if value else None
    return ChurnLabel(
        tenant_id="tenant-a",
        customer_id=customer_id,
        as_of=as_of,
        evaluation_as_of=evaluation_as_of or as_of + timedelta(days=1),
        horizon_days=horizon,  # type: ignore[arg-type]
        label=value,  # type: ignore[arg-type]
        label_status=LabelStatus.POSITIVE if value else LabelStatus.NEGATIVE,
        churn_type=ChurnType.VOLUNTARY_CANCELLATION if value else None,
        churn_effective_at=effective,
        label_observed_through=evaluation_as_of or as_of + timedelta(days=1),
        label_policy_version="labels_test_v1",
        source_evidence_refs=(f"label-{as_of.isoformat()}-{horizon}",),
        label_generated_at=evaluation_as_of or as_of + timedelta(days=1),
    )


def record(day: int, value: int, *, customer_id: str = "customer-a") -> SnapshotRecord:
    cutoff = at(day)
    feature = snapshot(ratio=0.8 if value == 0 else 0.2)
    feature = feature.model_copy(
        update={
            "customer_id": customer_id,
            "as_of": cutoff,
            "data_cutoff_at": cutoff,
        }
    )
    labels = tuple(churn_label(cutoff, horizon, value, customer_id=customer_id) for horizon in (7, 14, 30))
    return SnapshotRecord(feature_snapshot=feature, labels=labels)


def split_for_training(*, values: tuple[int, ...] = (0, 1, 0, 1)):
    boundaries = TemporalSplitBoundaries(
        train_start=at(0),
        train_end=at(20),
        validation_end=at(30),
        calibration_end=at(40),
        test_end=at(50),
    )
    rows = [record(day, value) for day, value in zip((1, 2, 3, 4), values)]
    rows.append(record(45, 1))
    return TemporalSplitter(
        TemporalSplitConfig(
            boundaries=boundaries,
            dataset_identifier="synthetic-baseline-fixture",
            minimum_samples_per_horizon=2,
        )
    ).split(rows)


def test_rule_baseline_returns_deterministic_ranking_score():
    model = RuleBasedBaseline()
    first = model.predict(snapshot(), payment_failures=0)
    second = model.predict(snapshot(), payment_failures=0)

    assert first == second
    assert first.status is BaselineStatus.READY
    assert first.score_kind is BaselineScoreKind.RANKING_SCORE
    assert first.score == 0
    assert first.alert is False


def test_usage_decline_changes_configured_heuristic_score():
    model = RuleBasedBaseline(
        RuleBaselineConfig(usage_decline_ratio_threshold=0.5, usage_decline_weight=35)
    )

    result = model.predict(snapshot(ratio=0.4, days_since_last=1), payment_failures=0)

    assert result.score == 35
    assert "recent usage decline threshold reached" in result.reasons


def test_missing_usage_is_not_treated_as_zero():
    result = RuleBasedBaseline().predict(snapshot(ratio=None, days_since_last=None))

    assert result.status is BaselineStatus.NOT_READY
    assert result.score is None
    assert any("unknown" in reason or "unavailable" in reason for reason in result.reasons)


def test_payment_failure_is_a_risk_signal_not_a_churn_outcome():
    result = RuleBasedBaseline().predict(
        snapshot(ratio=None, days_since_last=None), payment_failures=1
    )

    assert result.status is BaselineStatus.READY
    assert result.score == 15
    assert result.alert is False
    assert any("payment-failure" in reason for reason in result.reasons)


def test_rule_thresholds_are_versioned_and_reproducible():
    config = RuleBaselineConfig(
        baseline_version="rule_test_v2",
        days_since_last_session_threshold=3,
        inactivity_weight=20,
        alert_score_threshold=20,
    )
    result = RuleBasedBaseline(config).predict(snapshot(days_since_last=3), payment_failures=0)

    assert result.score == 20
    assert result.alert is True
    assert result.baseline_version == "rule_test_v2"


def test_feature_vectorizer_has_explicit_numeric_allowlist_without_identifiers():
    assert "tenant_id" not in MODEL_FEATURE_ALLOWLIST
    assert "customer_id" not in MODEL_FEATURE_ALLOWLIST
    assert "label" not in MODEL_FEATURE_ALLOWLIST
    assert "churn_effective_at" not in MODEL_FEATURE_ALLOWLIST


def test_logistic_baseline_excludes_unknown_and_immature_labels():
    boundaries = TemporalSplitBoundaries(
        train_start=at(0), train_end=at(20), validation_end=at(30), calibration_end=at(40)
    )
    row = record(10, 0)
    labels = tuple(
        item.model_copy(
            update={
                "label": None,
                "label_status": LabelStatus.UNKNOWN,
                "churn_type": None,
                "churn_effective_at": None,
            }
        )
        for item in row.labels
    )
    row = row.model_copy(update={"labels": labels})
    split = TemporalSplitter(TemporalSplitConfig(boundaries=boundaries)).split([row])

    result = LogisticRegressionBaseline().fit(split, horizon_days=7)

    assert result.status is BaselineStatus.NOT_READY
    assert result.training_snapshot_count == 0


def test_single_class_training_data_returns_not_ready():
    result = LogisticRegressionBaseline().fit(
        split_for_training(values=(1, 1, 1, 1)), horizon_days=14
    )

    assert result.status is BaselineStatus.NOT_READY
    assert result.positive_count == 4
    assert result.negative_count == 0
    assert "one class" in (result.reason or "")


def test_unfitted_logistic_baseline_cannot_produce_valid_prediction():
    result = LogisticRegressionBaseline().predict(snapshot(), horizon_days=30)

    assert result.status is BaselineStatus.UNFITTED
    assert result.score is None


def test_logistic_backend_reports_dependency_blocker_when_unavailable():
    result = LogisticRegressionBaseline().fit(split_for_training(), horizon_days=7)

    if SKLEARN_AVAILABLE:
        assert result.status is BaselineStatus.READY
    else:
        assert result.status is BaselineStatus.NOT_READY
        assert "scikit-learn" in (result.reason or "")


@pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn is not installed")
def test_logistic_regression_fits_valid_synthetic_training_data():
    result = LogisticRegressionBaseline().fit(split_for_training(), horizon_days=7)

    assert result.status is BaselineStatus.READY
    assert result.training_snapshot_count == 4
    assert result.positive_count == 2
    assert result.negative_count == 2
    assert result.feature_names


@pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn is not installed")
def test_separate_logistic_models_support_all_horizons():
    split = split_for_training()
    models = [LogisticRegressionBaseline() for _ in (7, 14, 30)]
    results = [model.fit(split, horizon_days=horizon) for model, horizon in zip(models, (7, 14, 30))]

    assert [result.horizon_days for result in results] == [7, 14, 30]
    assert all(result.status is BaselineStatus.READY for result in results)


@pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn is not installed")
def test_missing_features_are_imputed_using_training_pipeline():
    split = split_for_training()
    model = LogisticRegressionBaseline()
    fit_result = model.fit(split, horizon_days=30)
    prediction = model.predict(snapshot(ratio=None, days_since_last=None), horizon_days=30)

    assert fit_result.status is BaselineStatus.READY
    assert prediction.status is BaselineStatus.READY
    assert prediction.score_kind is BaselineScoreKind.UNCALIBRATED_PROBABILITY
    assert 0 <= prediction.score <= 1


@pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn is not installed")
def test_test_partition_is_not_used_during_fit():
    result = LogisticRegressionBaseline().fit(split_for_training(), horizon_days=7)

    assert result.training_snapshot_count == 4
    assert result.training_snapshot_count != 5


@pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn is not installed")
def test_trusted_artifact_save_and_load_preserves_metadata(tmp_path):
    model = LogisticRegressionBaseline()
    original = model.fit(split_for_training(), horizon_days=14)
    path = tmp_path / "logistic-baseline.pkl"
    model.save(path)
    restored = LogisticRegressionBaseline.load(path, trusted_root=tmp_path)
    prediction = restored.predict(snapshot(), horizon_days=14)

    assert restored.fit_result == original
    assert prediction.status is BaselineStatus.READY
    assert prediction.score_kind is BaselineScoreKind.UNCALIBRATED_PROBABILITY

    with pytest.raises(ValueError, match="trusted root"):
        LogisticRegressionBaseline.load(path, trusted_root=tmp_path / "not-trusted")
