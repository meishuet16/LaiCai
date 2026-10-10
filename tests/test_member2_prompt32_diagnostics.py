import pytest

from examples.member2_prompt32_diagnostics import (
    DiagnosticsError,
    PERSONALIZED_FEATURES,
    _metrics,
)


def test_constant_prevalence_metric_handles_extreme_imbalance_without_accuracy_claims():
    labels = [1] + [0] * 999
    metrics = _metrics(labels, [0.001] * len(labels))

    assert metrics["n"] == 1000
    assert metrics["positive_count"] == 1
    assert metrics["negative_count"] == 999
    assert metrics["prevalence"] == 0.001
    assert metrics["pr_auc_average_precision"] == 0.001
    assert metrics["roc_auc"] == 0.5
    assert metrics["brier"] == pytest.approx(0.000999)


def test_single_class_metrics_mark_ranking_measures_undefined():
    metrics = _metrics([0, 0, 0], [0.1, 0.2, 0.3])

    assert metrics["positive_count"] == 0
    assert metrics["pr_auc_average_precision"] is None
    assert metrics["roc_auc"] is None
    assert metrics["brier"] == (0.1**2 + 0.2**2 + 0.3**2) / 3


def test_rule_ranking_score_never_receives_probability_brier_interpretation():
    metrics = _metrics([1, 0, 0], [1.0, 0.0, 0.0], probability=False)

    assert metrics["pr_auc_average_precision"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["brier"] is None


def test_probability_metrics_reject_out_of_range_scores():
    with pytest.raises(DiagnosticsError, match="out-of-range"):
        _metrics([1, 0], [1.2, 0.1])


def test_personalization_ablation_targets_only_relative_baseline_derived_features():
    assert PERSONALIZED_FEATURES == {
        "recent_usage_trend",
        "historical_avg_sessions_per_week",
        "recent_avg_sessions_per_week",
        "absolute_usage_deviation",
        "percentage_usage_deviation",
        "recent_to_baseline_usage_ratio",
        "historical_weekly_usage_variability",
    }
