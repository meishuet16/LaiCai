from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction import (
    AsOfMRR,
    CalibrationBin,
    DataFreshness,
    DatasetProvenanceStatus,
    EvaluationPrediction,
    EvaluationReasonCode,
    EvaluationStatus,
    HistoricalAlert,
    HistoricalEvaluationConfig,
    HistoricalEvaluator,
    LabelStatus,
    MetricStatus,
    PredictionOutput,
    PredictionStatus,
    Reliability,
    RevenueCaptureStatus,
    SnapshotRecord,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitter,
    Uncertainty,
)

from test_lightgbm_model import BOUNDARIES, at, row


UTC = timezone.utc
EVALUATION_CUTOFF = at(100)


def mature_row(day: int, value: int, *, customer_id: str) -> SnapshotRecord:
    record = row(day, value, customer_id=customer_id)
    labels = tuple(
        label.model_copy(
            update={
                "evaluation_as_of": at(day + label.horizon_days),
                "label_observed_through": at(day + label.horizon_days),
                "label_generated_at": at(day + label.horizon_days),
            }
        )
        for label in record.labels
    )
    return record.model_copy(update={"labels": labels})


def split_for_evaluation(records=None):
    records = records or [
        mature_row(41, 1, customer_id="customer-positive"),
        mature_row(42, 0, customer_id="customer-negative"),
    ]
    return TemporalSplitter(
        TemporalSplitConfig(
            boundaries=BOUNDARIES,
            dataset_identifier="synthetic-evaluation-fixture",
            authorized_dataset=False,
            minimum_samples_per_horizon=1,
        )
    ).split(records)


def output_for(record: SnapshotRecord, *, p7: float, p14: float, p30: float, status=PredictionStatus.SCORED):
    return PredictionOutput(
        tenant_id=record.feature_snapshot.tenant_id,
        customer_id=record.feature_snapshot.customer_id,
        prediction_id=f"prediction-{record.feature_snapshot.customer_id}-{record.feature_snapshot.as_of.day}",
        prediction_run_id="run-evaluation-1",
        as_of=record.feature_snapshot.as_of,
        generated_at=at(99),
        status=status,
        p_churn_7d=p7 if status is PredictionStatus.SCORED else None,
        p_churn_14d=p14 if status is PredictionStatus.SCORED else None,
        p_churn_30d=p30 if status is PredictionStatus.SCORED else None,
        feature_version="features_personalized_baseline_v1",
        model_version="model_evaluation_v1",
        calibration_version="calibration_evaluation_v1",
        label_policy_version="labels_test_v1",
        reliability=Reliability(status="sufficient_evidence"),
        data_freshness=DataFreshness(status="fresh", input_data_as_of=record.feature_snapshot.as_of),
        uncertainty=Uncertainty(),
    )


def config(**kwargs):
    values = {
        "evaluation_cutoff": EVALUATION_CUTOFF,
        "dataset_provenance_status": DatasetProvenanceStatus.SYNTHETIC,
        "partition": "TEST",
        "review_capacity_k": 1,
        "calibration_bin_count": 5,
        "revenue_deduplication_policy": "earliest_churn_event_per_account",
    }
    values.update(kwargs)
    return HistoricalEvaluationConfig(**values)


def test_correct_identity_join_and_horizon_metrics():
    split = split_for_evaluation()
    records = split.partition("TEST").snapshots
    predictions = [
        output_for(records[0], p7=0.9, p14=0.9, p30=0.9),
        output_for(records[1], p7=0.1, p14=0.1, p30=0.1),
    ]

    report = HistoricalEvaluator().evaluate(
        predictions,
        [label for record in records for label in record.labels],
        split,
        config=config(),
    )
    metric = report.horizon_metrics[0]

    assert report.evaluation_status is EvaluationStatus.SYNTHETIC_ONLY
    assert metric.pr_auc.value == pytest.approx(1.0)
    assert metric.roc_auc.value == pytest.approx(1.0)
    assert metric.brier_score.value == pytest.approx(0.01)
    assert metric.precision_at_k.value == pytest.approx(1.0)
    assert metric.recall_at_k.value == pytest.approx(1.0)
    assert metric.calibration_bins
    assert sum(item.sample_count for item in metric.calibration_bins) == 2
    assert report.horizon_ordering_audits[0].violation_count == 0


def test_cross_tenant_prediction_is_rejected():
    split = split_for_evaluation()
    record = split.partition("TEST").snapshots[0]
    prediction = output_for(record, p7=0.9, p14=0.9, p30=0.9).model_copy(
        update={"tenant_id": "other-tenant"}
    )

    report = HistoricalEvaluator().evaluate(
        [prediction],
        list(record.labels),
        split,
        config=config(),
    )

    assert report.evaluation_status is EvaluationStatus.BLOCKED
    assert EvaluationReasonCode.PREDICTION_OUTSIDE_PARTITION in report.reason_codes


def test_duplicate_prediction_snapshot_is_rejected():
    split = split_for_evaluation()
    record = split.partition("TEST").snapshots[0]
    prediction = output_for(record, p7=0.9, p14=0.9, p30=0.9)

    with pytest.raises(ValueError, match="duplicate prediction"):
        HistoricalEvaluator().evaluate(
            [prediction, prediction], list(record.labels), split, config=config()
        )


def test_horizons_join_independently_without_cross_horizon_fallback():
    split = split_for_evaluation()
    record = split.partition("TEST").snapshots[0]
    candidate = EvaluationPrediction(
        model_name="candidate",
        tenant_id=record.feature_snapshot.tenant_id,
        customer_id=record.feature_snapshot.customer_id,
        prediction_id="candidate-prediction",
        as_of=record.feature_snapshot.as_of,
        horizon_days=7,
        probability=0.8,
        status=PredictionStatus.SCORED,
        model_version="model_evaluation_v1",
        feature_version="features_personalized_baseline_v1",
        calibration_version="calibration_evaluation_v1",
        label_policy_version="labels_test_v1",
    )
    horizon_14_label = next(label for label in record.labels if label.horizon_days == 14)

    report = HistoricalEvaluator().evaluate(
        [candidate], [horizon_14_label], split, config=config()
    )

    assert report.horizon_metrics[0].scored_population_count == 0
    assert report.horizon_metrics[0].exclusion_counts["missing"] == 1


def test_pending_unknown_and_incomplete_outcomes_are_not_negative():
    split = split_for_evaluation()
    records = split.partition("TEST").snapshots
    pending = records[0].labels[0].model_copy(
        update={"evaluation_as_of": at(101), "label_generated_at": at(101)}
    )
    unknown = records[1].labels[0].model_copy(
        update={"label": None, "label_status": LabelStatus.UNKNOWN, "churn_type": None, "churn_effective_at": None}
    )
    predictions = [
        output_for(records[0], p7=0.9, p14=0.9, p30=0.9),
        output_for(records[1], p7=0.1, p14=0.1, p30=0.1),
    ]
    report = HistoricalEvaluator().evaluate(
        predictions,
        [pending, unknown],
        split,
        config=config(),
    )
    metric = report.horizon_metrics[0]

    assert metric.mature_labeled_population_count == 0
    assert metric.pr_auc.status is MetricStatus.UNAVAILABLE
    assert metric.brier_score.status is MetricStatus.UNAVAILABLE
    assert metric.exclusion_counts["pending"] == 1
    assert metric.exclusion_counts["unknown"] == 1


def test_abstained_predictions_are_excluded_but_coverage_is_reported():
    split = split_for_evaluation()
    records = split.partition("TEST").snapshots
    predictions = [
        output_for(records[0], p7=0.9, p14=0.9, p30=0.9),
        output_for(records[1], p7=0.0, p14=0.0, p30=0.0, status=PredictionStatus.ABSTAINED),
    ]
    report = HistoricalEvaluator().evaluate(
        predictions,
        [label for record in records for label in record.labels],
        split,
        config=config(),
    )
    metric = report.horizon_metrics[0]

    assert metric.scored_population_count == 1
    assert metric.eligible_population_count == 2
    assert metric.evaluation_population_coverage == pytest.approx(0.5)
    assert metric.exclusion_counts["abstained"] == 1


def test_single_class_metrics_are_explicitly_unavailable():
    split = split_for_evaluation([mature_row(41, 1, customer_id="only-positive")])
    record = split.partition("TEST").snapshots[0]
    report = HistoricalEvaluator().evaluate(
        [output_for(record, p7=0.7, p14=0.7, p30=0.7)],
        list(record.labels),
        split,
        config=config(),
    )

    metric = report.horizon_metrics[0]
    assert metric.pr_auc.status is MetricStatus.UNAVAILABLE
    assert metric.roc_auc.status is MetricStatus.UNAVAILABLE
    assert metric.recall_at_k.status is MetricStatus.AVAILABLE
    assert metric.pr_auc.reason_codes == (EvaluationReasonCode.SINGLE_CLASS,)


def test_test_selection_must_be_frozen():
    split = split_for_evaluation()
    report = HistoricalEvaluator().evaluate(
        [], [], split, config=config(test_selection_frozen=False)
    )

    assert report.evaluation_status is EvaluationStatus.BLOCKED
    assert EvaluationReasonCode.TEST_SELECTION_NOT_FROZEN in report.reason_codes


def test_model_comparison_reports_different_scoring_cohorts():
    split = split_for_evaluation()
    records = split.partition("TEST").snapshots
    labels = [label for record in records for label in record.labels]
    predictions = [
        EvaluationPrediction.from_prediction_output(output_for(records[0], p7=0.9, p14=0.9, p30=0.9), model_name="model-a")[0],
        EvaluationPrediction.from_prediction_output(output_for(records[1], p7=0.1, p14=0.1, p30=0.1), model_name="model-a")[0],
        EvaluationPrediction.from_prediction_output(output_for(records[0], p7=0.8, p14=0.8, p30=0.8), model_name="model-b")[0],
    ]
    report = HistoricalEvaluator().evaluate(predictions, labels, split, config=config())

    summaries = [item for item in report.model_comparisons if item.horizon_days == 7]
    assert len(summaries) == 2
    assert summaries[1].same_mature_cohort_as_peers is False
    assert summaries[1].warning


def test_rank_ties_use_deterministic_identity_order():
    split = split_for_evaluation()
    records = split.partition("TEST").snapshots
    candidates = [
        EvaluationPrediction.from_prediction_output(output_for(records[1], p7=0.5, p14=0.5, p30=0.5), model_name="candidate")[2],
        EvaluationPrediction.from_prediction_output(output_for(records[0], p7=0.5, p14=0.5, p30=0.5), model_name="candidate")[2],
    ]

    ranked = HistoricalEvaluator.rank_for_review(candidates, horizon_days=30, review_capacity_k=2)

    assert [item.customer_id for item in ranked] == ["customer-negative", "customer-positive"]


def test_revenue_capture_does_not_combine_currencies_or_double_count_snapshots():
    first = mature_row(41, 1, customer_id="repeat-customer")
    second = mature_row(42, 1, customer_id="repeat-customer")
    same_event = at(50)
    updated = []
    for record in (first, second):
        labels = tuple(
            label.model_copy(update={"churn_effective_at": same_event})
            for label in record.labels
        )
        updated.append(record.model_copy(update={"labels": labels}))
    split = split_for_evaluation(updated)
    records = split.partition("TEST").snapshots
    predictions = [
        EvaluationPrediction.from_prediction_output(output_for(records[0], p7=0.9, p14=0.9, p30=0.9), model_name="candidate")[2],
        EvaluationPrediction.from_prediction_output(output_for(records[1], p7=0.8, p14=0.8, p30=0.8), model_name="candidate")[2],
    ]
    mrr = [
        AsOfMRR(tenant_id="tenant-a", customer_id="repeat-customer", as_of=records[0].feature_snapshot.as_of, amount_minor=100, currency="USD"),
        AsOfMRR(tenant_id="tenant-a", customer_id="repeat-customer", as_of=records[1].feature_snapshot.as_of, amount_minor=100, currency="USD"),
    ]
    evaluator = HistoricalEvaluator()
    result = evaluator.evaluate_revenue_captured_at_k(
        predictions,
        [label for record in records for label in record.labels],
        mrr,
        config=config(review_capacity_k=1),
    )
    mixed = evaluator.evaluate_revenue_captured_at_k(
        predictions,
        [label for record in records for label in record.labels],
        [mrr[0], mrr[1].model_copy(update={"currency": "SGD"})],
        config=config(review_capacity_k=1),
    )

    assert result.status is RevenueCaptureStatus.AVAILABLE
    assert result.total_churned_mrr_minor == 100
    assert result.captured_mrr_minor == 100
    assert mixed.status is RevenueCaptureStatus.UNAVAILABLE
    assert EvaluationReasonCode.MULTIPLE_CURRENCIES_NOT_COMBINED in mixed.reason_codes


def test_lead_time_requires_frozen_rule_and_handles_false_alerts():
    split = split_for_evaluation()
    records = split.partition("TEST").snapshots
    labels = [label for record in records for label in record.labels]
    alerts = [
        HistoricalAlert(
            tenant_id="tenant-a",
            customer_id="customer-positive",
            as_of=records[0].feature_snapshot.as_of,
            alert_at=records[0].feature_snapshot.as_of,
            horizon_days=7,
        ),
        HistoricalAlert(
            tenant_id="tenant-a",
            customer_id="customer-negative",
            as_of=records[1].feature_snapshot.as_of,
            alert_at=records[1].feature_snapshot.as_of,
            horizon_days=7,
        ),
    ]
    evaluator = HistoricalEvaluator()
    not_ready = evaluator.evaluate_lead_time(alerts, labels, config=config(alert_policy_version=None))
    ready = evaluator.evaluate_lead_time(
        alerts, labels, config=config(alert_policy_version="frozen_rule_v1")
    )

    assert not_ready.status.value == "not_ready"
    assert ready.qualifying_alert_count == 1
    assert ready.false_alert_count == 1
    assert ready.earliest_lead_time_days == pytest.approx(1.0)


def test_lead_time_right_censoring_does_not_create_early_warning():
    split = split_for_evaluation()
    record = split.partition("TEST").snapshots[0]
    pending = record.labels[0].model_copy(
        update={"evaluation_as_of": at(101), "label_generated_at": at(101)}
    )
    alert = HistoricalAlert(
        tenant_id=record.feature_snapshot.tenant_id,
        customer_id=record.feature_snapshot.customer_id,
        as_of=record.feature_snapshot.as_of,
        alert_at=record.feature_snapshot.as_of,
        horizon_days=7,
    )
    result = HistoricalEvaluator().evaluate_lead_time(
        [alert], [pending], config=config(alert_policy_version="frozen_rule_v1")
    )

    assert result.qualifying_alert_count == 0
    assert result.right_censored_count == 1


def test_version_mismatch_and_unverified_real_evaluation_are_blocked():
    split = split_for_evaluation()
    record = split.partition("TEST").snapshots[0]
    prediction = output_for(record, p7=0.5, p14=0.5, p30=0.5)
    mismatch = HistoricalEvaluator().evaluate(
        [prediction], list(record.labels), split,
        config=config(expected_model_version="different-model"),
    )
    real = HistoricalEvaluator().evaluate(
        [prediction], list(record.labels), split,
        config=config(dataset_provenance_status=DatasetProvenanceStatus.REAL_AUTHORIZED),
    )

    assert mismatch.evaluation_status is EvaluationStatus.BLOCKED
    assert EvaluationReasonCode.MODEL_VERSION_MISMATCH in mismatch.reason_codes
    assert real.evaluation_status is EvaluationStatus.BLOCKED
    assert EvaluationReasonCode.NO_AUTHORIZED_DATASET in real.reason_codes


def test_no_labels_by_cutoff_produces_no_authoritative_metric():
    split = split_for_evaluation()
    records = split.partition("TEST").snapshots
    late_labels = [
        label.model_copy(update={"evaluation_as_of": at(101), "label_generated_at": at(101)})
        for record in records
        for label in record.labels
    ]
    report = HistoricalEvaluator().evaluate(
        [output_for(records[0], p7=0.9, p14=0.9, p30=0.9)],
        late_labels,
        split,
        config=config(),
    )

    assert report.evaluation_status is EvaluationStatus.SYNTHETIC_ONLY
    assert report.horizon_metrics[0].pr_auc.status is MetricStatus.UNAVAILABLE
    assert any("No mature outcomes" in warning for warning in report.warnings)
