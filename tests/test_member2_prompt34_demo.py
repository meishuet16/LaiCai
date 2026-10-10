from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from examples.member2_prompt34_demo import (
    CLASS_SUPPORT,
    DemoError,
    REDUCED_CUTOFF_COUNTS,
    _metrics,
    _raw_prediction,
    _reliability_bins,
    _safe_root,
    _select_development_candidate,
    _support_passes,
    _load_stage,
    _member1_safe_prediction_payload,
)
from retainiq_prediction.baselines import BaselineScoreKind
from retainiq_prediction.historical_dataset_preparation import Cutoff, select_predeclared_cutoffs
from retainiq_prediction.temporal_splits import SplitName


def test_demo_rejects_repository_output_paths() -> None:
    repository = Path(__file__).resolve().parents[1]
    with pytest.raises(DemoError, match="outside the repository"):
        _safe_root(repository / "private-demo")


def test_test_outcome_artifact_is_locked_until_prediction_persistence() -> None:
    with pytest.raises(DemoError, match="locked"):
        _load_stage(Path("does-not-need-to-exist"), "test", include_labels=True)


def test_development_candidate_uses_only_complete_validation_metrics() -> None:
    comparison = {
        str(horizon): {
            "lightgbm_uncalibrated_score": {"pr_auc": 0.20, "brier": 0.10},
            "logistic_uncalibrated_score": {"pr_auc": 0.30, "brier": 0.12},
            "lightgbm_without_personalized_baseline": {"pr_auc": 0.25, "brier": 0.11},
        }
        for horizon in (7, 14, 30)
    }
    result = _select_development_candidate(comparison)
    assert result["selected_candidate"] == "logistic_uncalibrated_score"
    assert result["selection_scope"].startswith("VALIDATION only; raw scores only")
    assert result["promotion"].startswith("diagnostic ranking only")


def test_metrics_and_calibration_bins_report_real_fixture_counts() -> None:
    fixture_labels = [1, 0, 0, 1]
    fixture_scores = [0.8, 0.2, 0.1, 0.6]
    metrics = _metrics(
        fixture_labels,
        fixture_scores,
        probability=fixture_scores,
        k=2,
    )
    bins = _reliability_bins(fixture_scores, fixture_labels, bins=2)
    assert metrics["sample_count"] == 4
    assert metrics["positive_count"] == 2
    assert metrics["negative_count"] == 2
    assert metrics["recall_at_k"] == 1.0
    assert sum(item["sample_count"] for item in bins) == 4


def test_minimum_class_support_is_not_lowered() -> None:
    insufficient = {
        "positive_rows": CLASS_SUPPORT["minimum_positive_samples"] - 1,
        "negative_rows": CLASS_SUPPORT["minimum_negative_samples"],
        "unique_positive_accounts": CLASS_SUPPORT["minimum_unique_positive_accounts"],
        "unique_negative_accounts": CLASS_SUPPORT["minimum_unique_negative_accounts"],
    }
    sufficient = {
        "positive_rows": CLASS_SUPPORT["minimum_positive_samples"],
        "negative_rows": CLASS_SUPPORT["minimum_negative_samples"],
        "unique_positive_accounts": CLASS_SUPPORT["minimum_unique_positive_accounts"],
        "unique_negative_accounts": CLASS_SUPPORT["minimum_unique_negative_accounts"],
    }
    assert not _support_passes(insufficient)
    assert _support_passes(sufficient)


def test_calibrator_input_is_marked_uncalibrated() -> None:
    raw = _raw_prediction(0.37, 14, "feature-v1")
    assert raw.horizon_days == 14
    assert raw.score == 0.37
    assert raw.score_kind is BaselineScoreKind.UNCALIBRATED_PROBABILITY


def test_member1_database_projection_preserves_scores_but_omits_unsupported_details() -> None:
    source = {
        "prediction_id": "prediction-1",
        "p_churn_7d": 0.1,
        "p_churn_14d": 0.2,
        "p_churn_30d": 0.3,
        "reliability_reasons": ["free-form explanation"],
        "explanations_by_horizon": {"7": [{"unrestricted": "SHAP"}]},
    }
    projected = _member1_safe_prediction_payload(source)
    assert projected["p_churn_30d"] == 0.3
    assert projected["reliability_reasons"] == []
    assert projected["explanations_by_horizon"] == {}
    assert source["explanations_by_horizon"]


def test_reduced_cutoff_schedule_is_predeclared_deterministic_and_chronological() -> None:
    schedule = []
    for split, start, count in (
        (SplitName.TRAIN, datetime(2024, 10, 7, 12, tzinfo=timezone.utc), 37),
        (SplitName.VALIDATION, datetime(2025, 10, 6, 12, tzinfo=timezone.utc), 16),
        (SplitName.CALIBRATION, datetime(2026, 3, 2, 12, tzinfo=timezone.utc), 8),
        (SplitName.TEST, datetime(2026, 6, 1, 12, tzinfo=timezone.utc), 12),
    ):
        schedule.extend(
            Cutoff(
                as_of=start + timedelta(days=7 * index),
                split=split,
                label_freeze=datetime(2026, 10, 1, tzinfo=timezone.utc),
            )
            for index in range(count)
        )
    selected = select_predeclared_cutoffs(schedule, REDUCED_CUTOFF_COUNTS)
    assert selected == select_predeclared_cutoffs(schedule, REDUCED_CUTOFF_COUNTS)
    assert tuple(item.as_of for item in selected) == tuple(sorted(item.as_of for item in selected))
    assert {item.split for item in selected} == set(SplitName)
    assert len(selected) == sum(REDUCED_CUTOFF_COUNTS.values())
    assert len({item.as_of for item in selected}) == len(selected)


def test_reduced_cutoff_selection_requires_all_frozen_stages() -> None:
    schedule = (
        Cutoff(datetime(2025, 1, 6, 12, tzinfo=timezone.utc), SplitName.TRAIN,
               datetime(2025, 12, 1, tzinfo=timezone.utc)),
    )
    with pytest.raises(ValueError, match="all four"):
        select_predeclared_cutoffs(schedule, {SplitName.TRAIN: 1})
