"""Offline, chronological evaluation of RetainIQ prediction snapshots.

The evaluator consumes already-produced predictions and already-built labels. It
never fits an estimator, calibrator, threshold, or feature transformer. Real
evaluation remains blocked until authorized provenance and a complete dataset
readiness gate are available; synthetic reports are explicitly non-production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from typing import Any, Iterable, Mapping, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .contracts import PredictionOutput, PredictionStatus
from .dataset_readiness import DatasetStatus
from .label_builder import ChurnLabel, LabelStatus, SUPPORTED_HORIZONS
from .temporal_splits import SplitName, TemporalSplitResult


class EvaluationStatus(str, Enum):
    AVAILABLE = "available"
    SYNTHETIC_ONLY = "synthetic_only"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class DatasetProvenanceStatus(str, Enum):
    REAL_AUTHORIZED = "real_authorized"
    SYNTHETIC = "synthetic"
    UNVERIFIED = "unverified"


class EvaluationReasonCode(str, Enum):
    NO_AUTHORIZED_DATASET = "NO_AUTHORIZED_DATASET"
    PROVENANCE_UNVERIFIED = "PROVENANCE_UNVERIFIED"
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    TEST_SELECTION_NOT_FROZEN = "TEST_SELECTION_NOT_FROZEN"
    NO_MATURE_OUTCOMES = "NO_MATURE_OUTCOMES"
    PREDICTION_OUTSIDE_PARTITION = "PREDICTION_OUTSIDE_PARTITION"
    MODEL_VERSION_MISMATCH = "MODEL_VERSION_MISMATCH"
    FEATURE_VERSION_MISMATCH = "FEATURE_VERSION_MISMATCH"
    LABEL_POLICY_VERSION_MISMATCH = "LABEL_POLICY_VERSION_MISMATCH"
    PENDING_OUTCOME = "PENDING_OUTCOME"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    EXCLUDED_OUTCOME = "EXCLUDED_OUTCOME"
    UNSUPPORTED_OUTCOME = "UNSUPPORTED_OUTCOME"
    ABSTAINED_PREDICTION = "ABSTAINED_PREDICTION"
    KNOWN_CANCELLATION_PREDICTION = "KNOWN_CANCELLATION_PREDICTION"
    NOT_ELIGIBLE_PREDICTION = "NOT_ELIGIBLE_PREDICTION"
    SINGLE_CLASS = "SINGLE_CLASS"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    METRIC_UNDEFINED = "METRIC_UNDEFINED"
    MULTIPLE_CURRENCIES_NOT_COMBINED = "MULTIPLE_CURRENCIES_NOT_COMBINED"
    MRR_UNAVAILABLE = "MRR_UNAVAILABLE"
    REVENUE_DEDUPLICATION_POLICY_REQUIRED = "REVENUE_DEDUPLICATION_POLICY_REQUIRED"
    LEAD_TIME_NOT_READY = "LEAD_TIME_NOT_READY"
    RIGHT_CENSORED_OUTCOME = "RIGHT_CENSORED_OUTCOME"


class OutcomeState(str, Enum):
    MATURE_POSITIVE = "mature_positive"
    MATURE_NEGATIVE = "mature_negative"
    PENDING = "pending"
    UNKNOWN = "unknown"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"
    MISSING = "missing"


class MetricStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class LeadTimeStatus(str, Enum):
    AVAILABLE = "available"
    NOT_READY = "not_ready"
    UNAVAILABLE = "unavailable"


class RevenueCaptureStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluationPrediction(_EvaluationModel):
    """One candidate score for one immutable account/cutoff/horizon."""

    model_name: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    prediction_id: str | None = Field(default=None, min_length=1)
    prediction_run_id: str | None = Field(default=None, min_length=1)
    as_of: AwareDatetime
    horizon_days: int = Field(ge=1)
    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    status: PredictionStatus
    model_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    calibration_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_score_state(self) -> "EvaluationPrediction":
        if self.horizon_days not in SUPPORTED_HORIZONS:
            raise ValueError("unsupported evaluation horizon")
        if self.status is PredictionStatus.SCORED and self.probability is None:
            raise ValueError("scored evaluation predictions require a probability")
        if self.status is not PredictionStatus.SCORED and self.probability is not None:
            raise ValueError("non-scored evaluation predictions require null probability")
        return self

    @classmethod
    def from_prediction_output(
        cls, output: PredictionOutput, *, model_name: str = "prediction_output"
    ) -> tuple["EvaluationPrediction", ...]:
        probabilities = {
            7: output.p_churn_7d,
            14: output.p_churn_14d,
            30: output.p_churn_30d,
        }
        return tuple(
            cls(
                model_name=model_name,
                tenant_id=output.tenant_id,
                customer_id=output.customer_id,
                prediction_id=output.prediction_id,
                prediction_run_id=output.prediction_run_id,
                as_of=output.as_of,
                horizon_days=horizon,
                probability=probabilities[horizon],
                status=output.status,
                model_version=output.model_version,
                feature_version=output.feature_version,
                calibration_version=output.calibration_version,
                label_policy_version=output.label_policy_version,
            )
            for horizon in SUPPORTED_HORIZONS
        )


class MetricValue(_EvaluationModel):
    name: str = Field(min_length=1)
    horizon_days: int
    model_name: str = Field(min_length=1)
    partition: SplitName
    cohort: str = Field(min_length=1)
    sample_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    definition: str = Field(min_length=1)
    status: MetricStatus
    value: float | None = None
    reason_codes: tuple[EvaluationReasonCode, ...] = ()

    @model_validator(mode="after")
    def validate_value_state(self) -> "MetricValue":
        if self.status is MetricStatus.AVAILABLE:
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("available metrics require finite values")
        elif self.value is not None:
            raise ValueError("unavailable metrics must not contain a value")
        return self


class CalibrationBin(_EvaluationModel):
    lower_bound: float = Field(ge=0.0, le=1.0)
    upper_bound: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    mean_predicted_probability: float | None = None
    observed_positive_rate: float | None = None


class HorizonMetrics(_EvaluationModel):
    model_name: str = Field(min_length=1)
    horizon_days: int
    partition: SplitName
    cohort: str = Field(min_length=1)
    eligible_population_count: int = Field(ge=0)
    scored_population_count: int = Field(ge=0)
    mature_labeled_population_count: int = Field(ge=0)
    evaluation_population_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    abstention_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    exclusion_counts: dict[str, int] = Field(default_factory=dict)
    pr_auc: MetricValue
    roc_auc: MetricValue
    brier_score: MetricValue
    precision_at_k: MetricValue
    recall_at_k: MetricValue
    review_capacity_k: int = Field(gt=0)
    calibration_bins: tuple[CalibrationBin, ...] = ()


class HorizonOrderingAudit(_EvaluationModel):
    model_name: str = Field(min_length=1)
    partition: SplitName
    evaluated_snapshot_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)
    violation_frequency: float | None = Field(default=None, ge=0.0, le=1.0)
    status: MetricStatus


class ModelComparisonSummary(_EvaluationModel):
    model_name: str = Field(min_length=1)
    horizon_days: int
    mature_eligible_cohort_count: int = Field(ge=0)
    scored_mature_count: int = Field(ge=0)
    scoring_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    same_mature_cohort_as_peers: bool
    warning: str | None = None


class HistoricalAlert(_EvaluationModel):
    """A frozen historical alert/selection record for lead-time analysis."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    alert_at: AwareDatetime
    prediction_id: str | None = Field(default=None, min_length=1)
    horizon_days: int = Field(ge=1)
    selected: bool = True
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class LeadTimeEvaluation(_EvaluationModel):
    status: LeadTimeStatus
    alert_policy_version: str | None = None
    qualifying_alert_count: int = Field(ge=0)
    false_alert_count: int = Field(ge=0)
    right_censored_count: int = Field(ge=0)
    lead_times_days: tuple[float, ...] = ()
    earliest_lead_time_days: float | None = None
    reason_codes: tuple[EvaluationReasonCode, ...] = ()


class AsOfMRR(_EvaluationModel):
    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)


class RevenueCaptureResult(_EvaluationModel):
    status: RevenueCaptureStatus
    review_capacity_k: int = Field(gt=0)
    deduplication_policy: str | None = None
    currency: str | None = None
    captured_mrr_minor: int | None = None
    total_churned_mrr_minor: int | None = None
    revenue_captured_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    eligible_churn_event_count: int = Field(ge=0)
    selected_churn_event_count: int = Field(ge=0)
    reason_codes: tuple[EvaluationReasonCode, ...] = ()
    limitation: str = "Historical churned MRR exposure is not revenue saved by an intervention."


class HistoricalEvaluationReport(_EvaluationModel):
    evaluation_status: EvaluationStatus
    dataset_provenance_status: DatasetProvenanceStatus
    synthetic_test_only: bool
    split_policy_version: str
    model_version: str | None = None
    calibration_version: str | None = None
    label_policy_version: str | None = None
    evaluation_cutoff: AwareDatetime
    partition: SplitName
    cohort_sizes: dict[str, int] = Field(default_factory=dict)
    horizon_metrics: tuple[HorizonMetrics, ...] = ()
    horizon_ordering_audits: tuple[HorizonOrderingAudit, ...] = ()
    model_comparisons: tuple[ModelComparisonSummary, ...] = ()
    exclusion_counts: dict[str, int] = Field(default_factory=dict)
    lead_time: LeadTimeEvaluation
    revenue_captured_at_k: RevenueCaptureResult
    reason_codes: tuple[EvaluationReasonCode, ...] = ()
    warnings: tuple[str, ...] = ()
    configuration: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class HistoricalEvaluationConfig:
    evaluation_cutoff: datetime
    dataset_provenance_status: DatasetProvenanceStatus = DatasetProvenanceStatus.UNVERIFIED
    partition: SplitName = SplitName.TEST
    cohort: str = "eligible_mature_test"
    review_capacity_k: int = 10
    calibration_bin_count: int = 10
    expected_model_version: str | None = None
    expected_feature_version: str | None = None
    expected_label_policy_version: str | None = None
    split_policy_version: str | None = None
    test_selection_frozen: bool = True
    revenue_deduplication_policy: str | None = None
    alert_policy_version: str | None = None

    def __post_init__(self) -> None:
        if self.evaluation_cutoff.tzinfo is None or self.evaluation_cutoff.utcoffset() is None:
            raise ValueError("evaluation_cutoff must be timezone-aware")
        if self.review_capacity_k < 1:
            raise ValueError("review_capacity_k must be positive")
        if self.calibration_bin_count < 1:
            raise ValueError("calibration_bin_count must be positive")
        if self.split_policy_version is not None and not self.split_policy_version.strip():
            raise ValueError("split_policy_version must be non-empty")


@dataclass(frozen=True)
class _JoinedRow:
    prediction: EvaluationPrediction
    label: ChurnLabel
    outcome_state: OutcomeState


def _prediction_key(item: EvaluationPrediction | ChurnLabel) -> tuple[str, str, datetime, int]:
    return item.tenant_id, item.customer_id, item.as_of, item.horizon_days


def _prediction_identity_key(item: EvaluationPrediction) -> tuple[str, str, datetime, int, str]:
    return (*_prediction_key(item), item.model_name)


def _unique_reasons(values: Iterable[EvaluationReasonCode]) -> tuple[EvaluationReasonCode, ...]:
    return tuple(dict.fromkeys(values))


def _mature_state(label: ChurnLabel, cutoff: datetime) -> OutcomeState:
    if label.evaluation_as_of > cutoff or label.label_generated_at > cutoff:
        return OutcomeState.PENDING
    if label.label_status is LabelStatus.POSITIVE and label.label == 1:
        return OutcomeState.MATURE_POSITIVE
    if label.label_status is LabelStatus.NEGATIVE and label.label == 0:
        horizon_end = label.as_of + timedelta(days=label.horizon_days)
        if label.label_observed_through >= horizon_end:
            return OutcomeState.MATURE_NEGATIVE
        return OutcomeState.PENDING
    if label.label_status is LabelStatus.EXCLUDED:
        return OutcomeState.EXCLUDED
    if label.label_status is LabelStatus.UNSUPPORTED:
        return OutcomeState.UNSUPPORTED
    return OutcomeState.UNKNOWN


def _metric(
    name: str,
    *,
    model_name: str,
    horizon: int,
    partition: SplitName,
    cohort: str,
    sample_count: int,
    positive_count: int,
    negative_count: int,
    definition: str,
    value: float | None,
    reason: EvaluationReasonCode | None = None,
) -> MetricValue:
    status = MetricStatus.AVAILABLE if value is not None else MetricStatus.UNAVAILABLE
    return MetricValue(
        name=name,
        horizon_days=horizon,
        model_name=model_name,
        partition=partition,
        cohort=cohort,
        sample_count=sample_count,
        positive_count=positive_count,
        negative_count=negative_count,
        definition=definition,
        status=status,
        value=value,
        reason_codes=(reason,) if reason is not None else (),
    )


def _calibration_bins(
    probabilities: Sequence[float], labels: Sequence[int], bin_count: int
) -> tuple[CalibrationBin, ...]:
    bins: list[CalibrationBin] = []
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        selected = [
            (probability, label)
            for probability, label in zip(probabilities, labels)
            if (lower <= probability < upper) or (
                index == bin_count - 1 and lower <= probability <= upper
            )
        ]
        bins.append(
            CalibrationBin(
                lower_bound=lower,
                upper_bound=upper,
                sample_count=len(selected),
                mean_predicted_probability=(
                    sum(probability for probability, _ in selected) / len(selected)
                    if selected
                    else None
                ),
                observed_positive_rate=(
                    sum(label for _, label in selected) / len(selected)
                    if selected
                    else None
                ),
            )
        )
    return tuple(bins)


class HistoricalEvaluator:
    """Evaluate immutable historical predictions without fitting anything."""

    def evaluate(
        self,
        predictions: Sequence[PredictionOutput | EvaluationPrediction],
        labels: Sequence[ChurnLabel],
        split_result: TemporalSplitResult,
        *,
        config: HistoricalEvaluationConfig,
        mrr_records: Sequence[AsOfMRR] = (),
        alerts: Sequence[HistoricalAlert] = (),
    ) -> HistoricalEvaluationReport:
        """Return a reproducible report for one frozen chronological partition."""

        if not hasattr(split_result, "manifest") or not hasattr(split_result, "partition"):
            raise TypeError("split_result must be a TemporalSplitResult")
        if config.split_policy_version is not None and split_result.manifest.split_policy_version != config.split_policy_version:
            return self._blocked_report(
                split_result,
                config,
                EvaluationReasonCode.PROVENANCE_UNVERIFIED,
                "split policy version does not match the evaluation configuration",
            )
        if not config.test_selection_frozen:
            return self._blocked_report(
                split_result,
                config,
                EvaluationReasonCode.TEST_SELECTION_NOT_FROZEN,
                "TEST evaluation requires frozen model-selection and threshold policy",
            )
        provenance_block = self._provenance_block(split_result, config)
        if provenance_block is not None:
            return self._blocked_report(split_result, config, *provenance_block)

        expanded = self._expand_predictions(predictions)
        self._reject_duplicate_predictions(expanded)
        label_by_key = self._index_labels(labels)
        partition = split_result.partition(config.partition)
        partition_records = {record.stable_snapshot_id: record for record in partition.snapshots}
        partition_keys = {
            (
                record.feature_snapshot.tenant_id,
                record.feature_snapshot.customer_id,
                record.feature_snapshot.as_of,
            )
            for record in partition.snapshots
        }
        outside = [item for item in expanded if (item.tenant_id, item.customer_id, item.as_of) not in partition_keys]
        if outside:
            return self._blocked_report(
                split_result,
                config,
                EvaluationReasonCode.PREDICTION_OUTSIDE_PARTITION,
                "a prediction does not belong to the selected chronological partition",
            )

        version_reasons = self._validate_versions(expanded, labels, config)
        if version_reasons:
            return self._blocked_report(
                split_result,
                config,
                version_reasons[0],
                "prediction, feature, or label-policy metadata is incompatible",
                extra_reasons=version_reasons,
            )

        model_names = tuple(dict.fromkeys(item.model_name for item in expanded))
        metrics: list[HorizonMetrics] = []
        ordering: list[HorizonOrderingAudit] = []
        comparisons: list[ModelComparisonSummary] = []
        cohort_keys_by_model_horizon: dict[tuple[str, int], set[tuple[str, str, datetime]]] = {}
        all_exclusions: dict[str, int] = {}
        warnings: list[str] = []
        eligible_population_keys: dict[int, set[tuple[str, str, datetime]]] = {
            horizon: {
                (
                    record.feature_snapshot.tenant_id,
                    record.feature_snapshot.customer_id,
                    record.feature_snapshot.as_of,
                )
                for record in partition.snapshots
                if record.prediction_eligible
            }
            for horizon in SUPPORTED_HORIZONS
        }
        mature_eligible_keys: dict[int, set[tuple[str, str, datetime]]] = {
            horizon: set() for horizon in SUPPORTED_HORIZONS
        }

        for horizon in SUPPORTED_HORIZONS:
            for record in partition.snapshots:
                label = label_by_key.get(
                    (
                        record.feature_snapshot.tenant_id,
                        record.feature_snapshot.customer_id,
                        record.feature_snapshot.as_of,
                        horizon,
                    )
                )
                if record.prediction_eligible and label is not None and _mature_state(label, config.evaluation_cutoff) in {
                    OutcomeState.MATURE_POSITIVE,
                    OutcomeState.MATURE_NEGATIVE,
                }:
                    mature_eligible_keys[horizon].add(
                        (record.feature_snapshot.tenant_id, record.feature_snapshot.customer_id, record.feature_snapshot.as_of)
                    )

            for model_name in model_names:
                rows, exclusions = self._joined_rows(
                    expanded,
                    label_by_key,
                    partition_records,
                    model_name=model_name,
                    horizon=horizon,
                    cutoff=config.evaluation_cutoff,
                )
                for key, count in exclusions.items():
                    all_exclusions[key] = all_exclusions.get(key, 0) + count
                model_metrics = self._metrics_for_rows(
                    rows,
                    exclusions,
                    model_name,
                    horizon,
                    config,
                    eligible_population_count=len(eligible_population_keys[horizon]),
                )
                cohort_keys_by_model_horizon[(model_name, horizon)] = {
                    (row.prediction.tenant_id, row.prediction.customer_id, row.prediction.as_of)
                    for row in rows
                }
                metrics.append(model_metrics)
                cohort_count = len(mature_eligible_keys[horizon])
                comparisons.append(
                    ModelComparisonSummary(
                        model_name=model_name,
                        horizon_days=horizon,
                        mature_eligible_cohort_count=cohort_count,
                        scored_mature_count=len(rows),
                        scoring_coverage=(len(rows) / cohort_count if cohort_count else None),
                        same_mature_cohort_as_peers=True,
                        warning=(
                            "Scored coverage differs from the complete mature eligible cohort."
                            if len(rows) < cohort_count
                            else None
                        ),
                    )
                )

        if len(model_names) > 1:
            for index, comparison in enumerate(comparisons):
                peer_sets = [
                    cohort_keys_by_model_horizon[(model_name, comparison.horizon_days)]
                    for model_name in model_names
                ]
                same = all(peer_set == peer_sets[0] for peer_set in peer_sets[1:])
                warning = comparison.warning
                if not same:
                    warning = (
                        "Models do not share the same mature scored cohort; compare coverage separately."
                        if warning is None
                        else warning + " Models also do not share the same mature scored cohort."
                    )
                comparisons[index] = comparison.model_copy(
                    update={"same_mature_cohort_as_peers": same, "warning": warning}
                )

        ordering = list(self._ordering_audits(expanded, config))
        lead_time = self.evaluate_lead_time(alerts, labels, config=config)
        revenue = self.evaluate_revenue_captured_at_k(
            expanded, labels, mrr_records, config=config
        )
        report_status = (
            EvaluationStatus.SYNTHETIC_ONLY
            if config.dataset_provenance_status is DatasetProvenanceStatus.SYNTHETIC
            else EvaluationStatus.AVAILABLE
        )
        if not any(metric.mature_labeled_population_count for metric in metrics):
            warnings.append("No mature outcomes were available by the evaluation cutoff.")
        warnings.extend(split_result.manifest.missing_data_warnings)
        return HistoricalEvaluationReport(
            evaluation_status=report_status,
            dataset_provenance_status=config.dataset_provenance_status,
            synthetic_test_only=config.dataset_provenance_status is DatasetProvenanceStatus.SYNTHETIC,
            split_policy_version=split_result.manifest.split_policy_version,
            model_version=self._single_version(expanded, "model_version"),
            calibration_version=self._single_version(expanded, "calibration_version"),
            label_policy_version=self._single_version(expanded, "label_policy_version"),
            evaluation_cutoff=config.evaluation_cutoff,
            partition=config.partition,
            cohort_sizes={
                "partition_snapshots": len(partition.snapshots),
                "eligible_snapshots": sum(1 for record in partition.snapshots if record.prediction_eligible),
                "candidate_predictions": len(expanded),
            },
            horizon_metrics=tuple(metrics),
            horizon_ordering_audits=tuple(ordering),
            model_comparisons=tuple(comparisons),
            exclusion_counts=all_exclusions,
            lead_time=lead_time,
            revenue_captured_at_k=revenue,
            reason_codes=(EvaluationReasonCode.SYNTHETIC_ONLY,)
            if config.dataset_provenance_status is DatasetProvenanceStatus.SYNTHETIC
            else (),
            warnings=tuple(dict.fromkeys(warnings)),
            configuration={
                "cohort": config.cohort,
                "review_capacity_k": config.review_capacity_k,
                "calibration_bin_count": config.calibration_bin_count,
                "test_selection_frozen": config.test_selection_frozen,
                "evaluation_cutoff": config.evaluation_cutoff.isoformat(),
                "model_selection_used_test": False,
            },
        )

    def evaluate_lead_time(
        self,
        alerts: Sequence[HistoricalAlert],
        labels: Sequence[ChurnLabel],
        *,
        config: HistoricalEvaluationConfig,
    ) -> LeadTimeEvaluation:
        if not config.alert_policy_version:
            return LeadTimeEvaluation(
                status=LeadTimeStatus.NOT_READY,
                qualifying_alert_count=0,
                false_alert_count=0,
                right_censored_count=0,
                reason_codes=(EvaluationReasonCode.LEAD_TIME_NOT_READY,),
            )
        if not alerts:
            return LeadTimeEvaluation(
                status=LeadTimeStatus.NOT_READY,
                alert_policy_version=config.alert_policy_version,
                qualifying_alert_count=0,
                false_alert_count=0,
                right_censored_count=0,
                reason_codes=(EvaluationReasonCode.LEAD_TIME_NOT_READY,),
            )
        label_by_account: dict[tuple[str, str], list[ChurnLabel]] = {}
        all_label_by_account: dict[tuple[str, str], list[ChurnLabel]] = {}
        for label in labels:
            all_label_by_account.setdefault((label.tenant_id, label.customer_id), []).append(label)
            if _mature_state(label, config.evaluation_cutoff) is OutcomeState.MATURE_POSITIVE:
                label_by_account.setdefault((label.tenant_id, label.customer_id), []).append(label)
        lead_times: list[float] = []
        false_alerts = 0
        censored = 0
        for alert in alerts:
            if not alert.selected:
                continue
            qualifying = [
                label
                for label in label_by_account.get((alert.tenant_id, alert.customer_id), ())
                if label.horizon_days == alert.horizon_days
                and alert.alert_at < label.churn_effective_at
                and alert.alert_at >= label.as_of
            ]
            if not qualifying:
                if any(
                    label.horizon_days == alert.horizon_days
                    and label.label_status is LabelStatus.POSITIVE
                    for label in all_label_by_account.get((alert.tenant_id, alert.customer_id), ())
                ):
                    censored += 1
                else:
                    false_alerts += 1
                continue
            selected = min(qualifying, key=lambda label: label.churn_effective_at)
            lead_times.append(
                (selected.churn_effective_at - alert.alert_at).total_seconds() / 86400.0
            )
        return LeadTimeEvaluation(
            status=LeadTimeStatus.AVAILABLE,
            alert_policy_version=config.alert_policy_version,
            qualifying_alert_count=len(lead_times),
            false_alert_count=false_alerts,
            right_censored_count=censored,
            lead_times_days=tuple(lead_times),
            earliest_lead_time_days=min(lead_times) if lead_times else None,
        )

    def evaluate_revenue_captured_at_k(
        self,
        predictions: Sequence[PredictionOutput | EvaluationPrediction],
        labels: Sequence[ChurnLabel],
        mrr_records: Sequence[AsOfMRR],
        *,
        config: HistoricalEvaluationConfig,
    ) -> RevenueCaptureResult:
        if not config.revenue_deduplication_policy:
            return RevenueCaptureResult(
                status=RevenueCaptureStatus.UNAVAILABLE,
                review_capacity_k=config.review_capacity_k,
                eligible_churn_event_count=0,
                selected_churn_event_count=0,
                reason_codes=(EvaluationReasonCode.REVENUE_DEDUPLICATION_POLICY_REQUIRED,),
            )
        if not mrr_records:
            return RevenueCaptureResult(
                status=RevenueCaptureStatus.UNAVAILABLE,
                review_capacity_k=config.review_capacity_k,
                deduplication_policy=config.revenue_deduplication_policy,
                eligible_churn_event_count=0,
                selected_churn_event_count=0,
                reason_codes=(EvaluationReasonCode.MRR_UNAVAILABLE,),
            )
        currencies = {record.currency.upper() for record in mrr_records}
        if len(currencies) != 1:
            return RevenueCaptureResult(
                status=RevenueCaptureStatus.UNAVAILABLE,
                review_capacity_k=config.review_capacity_k,
                deduplication_policy=config.revenue_deduplication_policy,
                eligible_churn_event_count=0,
                selected_churn_event_count=0,
                reason_codes=(EvaluationReasonCode.MULTIPLE_CURRENCIES_NOT_COMBINED,),
            )
        expanded = self._expand_predictions(predictions)
        self._reject_duplicate_predictions(expanded)
        label_by_key = self._index_labels(labels)
        mrr_by_key = {
            (record.tenant_id, record.customer_id, record.as_of): record
            for record in mrr_records
        }
        events: dict[tuple[str, str, datetime], tuple[EvaluationPrediction, ChurnLabel, AsOfMRR]] = {}
        for prediction in expanded:
            if prediction.status is not PredictionStatus.SCORED or prediction.horizon_days != 30:
                continue
            label = label_by_key.get(_prediction_key(prediction))
            if label is None or _mature_state(label, config.evaluation_cutoff) is not OutcomeState.MATURE_POSITIVE:
                continue
            mrr = mrr_by_key.get((prediction.tenant_id, prediction.customer_id, prediction.as_of))
            if mrr is None:
                continue
            if label.churn_effective_at is None:
                continue
            event_key = (prediction.tenant_id, prediction.customer_id, label.churn_effective_at)
            current = events.get(event_key)
            if current is None or prediction.as_of < current[0].as_of:
                events[event_key] = (prediction, label, mrr)
        if not events:
            return RevenueCaptureResult(
                status=RevenueCaptureStatus.UNAVAILABLE,
                review_capacity_k=config.review_capacity_k,
                deduplication_policy=config.revenue_deduplication_policy,
                currency=next(iter(currencies)),
                eligible_churn_event_count=0,
                selected_churn_event_count=0,
                reason_codes=(EvaluationReasonCode.MRR_UNAVAILABLE,),
            )
        ranked = sorted(
            events.values(),
            key=lambda item: (
                -(item[0].probability or 0.0),
                item[0].tenant_id,
                item[0].customer_id,
                item[0].as_of,
                item[0].prediction_id or "",
            ),
        )
        selected = ranked[: config.review_capacity_k]
        total = sum(item[2].amount_minor for item in ranked)
        captured = sum(item[2].amount_minor for item in selected)
        return RevenueCaptureResult(
            status=RevenueCaptureStatus.AVAILABLE,
            review_capacity_k=config.review_capacity_k,
            deduplication_policy=config.revenue_deduplication_policy,
            currency=next(iter(currencies)),
            captured_mrr_minor=captured,
            total_churned_mrr_minor=total,
            revenue_captured_at_k=(captured / total if total else None),
            eligible_churn_event_count=len(ranked),
            selected_churn_event_count=len(selected),
            reason_codes=() if total else (EvaluationReasonCode.MRR_UNAVAILABLE,),
        )

    @staticmethod
    def rank_for_review(
        predictions: Sequence[PredictionOutput | EvaluationPrediction],
        *,
        horizon_days: int = 30,
        review_capacity_k: int,
    ) -> tuple[EvaluationPrediction, ...]:
        """Rank only scored predictions with deterministic identity tie-breaking."""

        if horizon_days not in SUPPORTED_HORIZONS:
            raise ValueError("unsupported ranking horizon")
        if review_capacity_k < 1:
            raise ValueError("review_capacity_k must be positive")
        expanded = HistoricalEvaluator._expand_predictions(predictions)
        HistoricalEvaluator._reject_duplicate_predictions(expanded)
        eligible = [
            item
            for item in expanded
            if item.horizon_days == horizon_days
            and item.status is PredictionStatus.SCORED
            and item.probability is not None
        ]
        return tuple(
            sorted(
                eligible,
                key=lambda item: (
                    -float(item.probability),
                    item.tenant_id,
                    item.customer_id,
                    item.as_of,
                    item.prediction_id or "",
                ),
            )[:review_capacity_k]
        )

    @staticmethod
    def _expand_predictions(
        predictions: Sequence[PredictionOutput | EvaluationPrediction],
    ) -> tuple[EvaluationPrediction, ...]:
        expanded: list[EvaluationPrediction] = []
        for item in predictions:
            if isinstance(item, PredictionOutput):
                expanded.extend(EvaluationPrediction.from_prediction_output(item))
            elif isinstance(item, EvaluationPrediction):
                expanded.append(item)
            else:
                raise TypeError("predictions must be PredictionOutput or EvaluationPrediction")
        return tuple(expanded)

    @staticmethod
    def _reject_duplicate_predictions(predictions: Sequence[EvaluationPrediction]) -> None:
        seen: set[tuple[str, str, datetime, int, str]] = set()
        for item in predictions:
            key = _prediction_identity_key(item)
            if key in seen:
                raise ValueError(f"duplicate prediction snapshot join: {key}")
            seen.add(key)

    @staticmethod
    def _index_labels(labels: Sequence[ChurnLabel]) -> dict[tuple[str, str, datetime, int], ChurnLabel]:
        indexed: dict[tuple[str, str, datetime, int], ChurnLabel] = {}
        for label in labels:
            key = _prediction_key(label)
            if key in indexed:
                raise ValueError(f"ambiguous duplicate label join: {key}")
            indexed[key] = label
        return indexed

    @staticmethod
    def _validate_versions(
        predictions: Sequence[EvaluationPrediction],
        labels: Sequence[ChurnLabel],
        config: HistoricalEvaluationConfig,
    ) -> tuple[EvaluationReasonCode, ...]:
        reasons: list[EvaluationReasonCode] = []
        for item in predictions:
            if config.expected_model_version and item.model_version != config.expected_model_version:
                reasons.append(EvaluationReasonCode.MODEL_VERSION_MISMATCH)
            if config.expected_feature_version and item.feature_version != config.expected_feature_version:
                reasons.append(EvaluationReasonCode.FEATURE_VERSION_MISMATCH)
            if config.expected_label_policy_version and item.label_policy_version != config.expected_label_policy_version:
                reasons.append(EvaluationReasonCode.LABEL_POLICY_VERSION_MISMATCH)
        if config.expected_label_policy_version:
            if any(label.label_policy_version != config.expected_label_policy_version for label in labels):
                reasons.append(EvaluationReasonCode.LABEL_POLICY_VERSION_MISMATCH)
        return _unique_reasons(reasons)

    @staticmethod
    def _joined_rows(
        predictions: Sequence[EvaluationPrediction],
        labels: Mapping[tuple[str, str, datetime, int], ChurnLabel],
        partition_records: Mapping[str, Any],
        *,
        model_name: str,
        horizon: int,
        cutoff: datetime,
    ) -> tuple[list[_JoinedRow], dict[str, int]]:
        rows: list[_JoinedRow] = []
        exclusions: dict[str, int] = {}
        candidates = [
            item for item in predictions
            if item.model_name == model_name and item.horizon_days == horizon
        ]
        for item in candidates:
            record = next(
                (
                    record
                    for record in partition_records.values()
                    if record.feature_snapshot.tenant_id == item.tenant_id
                    and record.feature_snapshot.customer_id == item.customer_id
                    and record.feature_snapshot.as_of == item.as_of
                ),
                None,
            )
            if record is None or not record.prediction_eligible:
                exclusions["ineligible_population"] = exclusions.get("ineligible_population", 0) + 1
                continue
            if item.status is not PredictionStatus.SCORED:
                key = item.status.value
                exclusions[key] = exclusions.get(key, 0) + 1
                continue
            label = labels.get(_prediction_key(item))
            if label is None:
                exclusions[OutcomeState.MISSING.value] = exclusions.get(OutcomeState.MISSING.value, 0) + 1
                continue
            state = _mature_state(label, cutoff)
            if state in {OutcomeState.MATURE_POSITIVE, OutcomeState.MATURE_NEGATIVE}:
                rows.append(_JoinedRow(item, label, state))
            else:
                exclusions[state.value] = exclusions.get(state.value, 0) + 1
        return rows, exclusions

    def _metrics_for_rows(
        self,
        rows: Sequence[_JoinedRow],
        exclusions: Mapping[str, int],
        model_name: str,
        horizon: int,
        config: HistoricalEvaluationConfig,
        *,
        eligible_population_count: int,
    ) -> HorizonMetrics:
        probabilities = [float(row.prediction.probability) for row in rows]
        targets = [1 if row.outcome_state is OutcomeState.MATURE_POSITIVE else 0 for row in rows]
        sample_count = len(rows)
        positive_count = sum(targets)
        negative_count = sample_count - positive_count
        if sample_count and positive_count and negative_count:
            from sklearn.metrics import average_precision_score, roc_auc_score

            pr_auc_value = float(average_precision_score(targets, probabilities))
            roc_auc_value = float(roc_auc_score(targets, probabilities))
            reason = None
        else:
            pr_auc_value = None
            roc_auc_value = None
            reason = EvaluationReasonCode.SINGLE_CLASS if sample_count else EvaluationReasonCode.INSUFFICIENT_SAMPLES
        brier_value = (
            sum((probability - target) ** 2 for probability, target in zip(probabilities, targets)) / sample_count
            if sample_count
            else None
        )
        ranked = sorted(
            rows,
            key=lambda row: (
                -float(row.prediction.probability),
                row.prediction.tenant_id,
                row.prediction.customer_id,
                row.prediction.as_of,
                row.prediction.prediction_id or "",
            ),
        )
        top = ranked[: min(config.review_capacity_k, len(ranked))]
        top_positive = sum(row.outcome_state is OutcomeState.MATURE_POSITIVE for row in top)
        precision = top_positive / len(top) if top else None
        recall = top_positive / positive_count if positive_count else None
        common = {
            "model_name": model_name,
            "horizon": horizon,
            "partition": config.partition,
            "cohort": config.cohort,
            "sample_count": sample_count,
            "positive_count": positive_count,
            "negative_count": negative_count,
        }
        return HorizonMetrics(
            model_name=model_name,
            horizon_days=horizon,
            partition=config.partition,
            cohort=config.cohort,
            eligible_population_count=eligible_population_count,
            scored_population_count=sample_count,
            mature_labeled_population_count=sample_count,
            evaluation_population_coverage=(
                sample_count / eligible_population_count
                if eligible_population_count
                else None
            ),
            abstention_rate=(
                exclusions.get(PredictionStatus.ABSTAINED.value, 0)
                / eligible_population_count
                if eligible_population_count
                else None
            ),
            exclusion_counts=dict(exclusions),
            pr_auc=_metric(
                "pr_auc", definition="Average precision over mature scored outcomes.", value=pr_auc_value,
                reason=reason, **common,
            ),
            roc_auc=_metric(
                "roc_auc", definition="ROC area over mature scored outcomes.", value=roc_auc_value,
                reason=reason, **common,
            ),
            brier_score=_metric(
                "brier_score", definition="Mean squared probability error over mature scored outcomes.", value=brier_value,
                reason=None if brier_value is not None else EvaluationReasonCode.INSUFFICIENT_SAMPLES,
                **common,
            ),
            precision_at_k=_metric(
                "precision_at_k", definition="Positive outcomes among the top K ranked scored snapshots.", value=precision,
                reason=None if precision is not None else EvaluationReasonCode.INSUFFICIENT_SAMPLES,
                **common,
            ),
            recall_at_k=_metric(
                "recall_at_k", definition="Top-K positive outcomes divided by all mature scored positives.", value=recall,
                reason=None if recall is not None else EvaluationReasonCode.SINGLE_CLASS,
                **common,
            ),
            review_capacity_k=config.review_capacity_k,
            calibration_bins=_calibration_bins(probabilities, targets, config.calibration_bin_count),
        )

    @staticmethod
    def _ordering_audits(
        predictions: Sequence[EvaluationPrediction], config: HistoricalEvaluationConfig
    ) -> tuple[HorizonOrderingAudit, ...]:
        grouped: dict[tuple[str, str, datetime, str], dict[int, EvaluationPrediction]] = {}
        for item in predictions:
            if item.status is PredictionStatus.SCORED:
                grouped.setdefault(
                    (item.tenant_id, item.customer_id, item.as_of, item.model_name), {}
                )[item.horizon_days] = item
        audits: list[HorizonOrderingAudit] = []
        for model_name in sorted({item.model_name for item in predictions}):
            complete = [
                values for values in grouped.values()
                if values and next(iter(values.values())).model_name == model_name
                and set(values) == set(SUPPORTED_HORIZONS)
            ]
            violations = sum(
                not (
                    values[7].probability <= values[14].probability <= values[30].probability
                )
                for values in complete
            )
            audits.append(
                HorizonOrderingAudit(
                    model_name=model_name,
                    partition=config.partition,
                    evaluated_snapshot_count=len(complete),
                    violation_count=violations,
                    violation_frequency=(violations / len(complete) if complete else None),
                    status=MetricStatus.AVAILABLE if complete else MetricStatus.UNAVAILABLE,
                )
            )
        return tuple(audits)

    @staticmethod
    def _single_version(predictions: Sequence[EvaluationPrediction], field_name: str) -> str | None:
        values = {getattr(item, field_name) for item in predictions}
        return next(iter(values)) if len(values) == 1 else None

    @staticmethod
    def _provenance_block(
        split_result: TemporalSplitResult, config: HistoricalEvaluationConfig
    ) -> tuple[EvaluationReasonCode, str] | None:
        if config.dataset_provenance_status is DatasetProvenanceStatus.UNVERIFIED:
            return EvaluationReasonCode.PROVENANCE_UNVERIFIED, "dataset provenance is unverified"
        if config.dataset_provenance_status is DatasetProvenanceStatus.REAL_AUTHORIZED:
            if split_result.manifest.dataset_readiness_status is not DatasetStatus.PASS:
                return EvaluationReasonCode.NO_AUTHORIZED_DATASET, "real dataset readiness is not PASS"
        elif config.dataset_provenance_status is DatasetProvenanceStatus.SYNTHETIC:
            identifier = split_result.manifest.dataset_identifier or ""
            if not identifier.lower().startswith("synthetic"):
                return EvaluationReasonCode.PROVENANCE_UNVERIFIED, "synthetic evaluation requires synthetic dataset provenance"
        return None

    @staticmethod
    def _blocked_report(
        split_result: TemporalSplitResult,
        config: HistoricalEvaluationConfig,
        reason: EvaluationReasonCode,
        message: str,
        *,
        extra_reasons: Sequence[EvaluationReasonCode] = (),
    ) -> HistoricalEvaluationReport:
        return HistoricalEvaluationReport(
            evaluation_status=EvaluationStatus.BLOCKED,
            dataset_provenance_status=config.dataset_provenance_status,
            synthetic_test_only=config.dataset_provenance_status is DatasetProvenanceStatus.SYNTHETIC,
            split_policy_version=split_result.manifest.split_policy_version,
            evaluation_cutoff=config.evaluation_cutoff,
            partition=config.partition,
            cohort_sizes={},
            horizon_metrics=(),
            horizon_ordering_audits=(),
            model_comparisons=(),
            exclusion_counts={},
            lead_time=LeadTimeEvaluation(
                status=LeadTimeStatus.NOT_READY,
                qualifying_alert_count=0,
                false_alert_count=0,
                right_censored_count=0,
                reason_codes=(EvaluationReasonCode.LEAD_TIME_NOT_READY,),
            ),
            revenue_captured_at_k=RevenueCaptureResult(
                status=RevenueCaptureStatus.UNAVAILABLE,
                review_capacity_k=config.review_capacity_k,
                eligible_churn_event_count=0,
                selected_churn_event_count=0,
                reason_codes=(EvaluationReasonCode.MRR_UNAVAILABLE,),
            ),
            reason_codes=_unique_reasons((reason, *extra_reasons)),
            warnings=(message,),
            configuration={"model_selection_used_test": False},
        )


def evaluate_historical_predictions(
    predictions: Sequence[PredictionOutput | EvaluationPrediction],
    labels: Sequence[ChurnLabel],
    split_result: TemporalSplitResult,
    *,
    config: HistoricalEvaluationConfig,
    mrr_records: Sequence[AsOfMRR] = (),
    alerts: Sequence[HistoricalAlert] = (),
) -> HistoricalEvaluationReport:
    """Functional convenience wrapper around :class:`HistoricalEvaluator`."""

    return HistoricalEvaluator().evaluate(
        predictions,
        labels,
        split_result,
        config=config,
        mrr_records=mrr_records,
        alerts=alerts,
    )


__all__ = [
    "AsOfMRR",
    "CalibrationBin",
    "DatasetProvenanceStatus",
    "EvaluationPrediction",
    "EvaluationReasonCode",
    "EvaluationStatus",
    "HistoricalAlert",
    "HistoricalEvaluationConfig",
    "HistoricalEvaluationReport",
    "HistoricalEvaluator",
    "HorizonMetrics",
    "HorizonOrderingAudit",
    "LeadTimeEvaluation",
    "LeadTimeStatus",
    "MetricStatus",
    "MetricValue",
    "ModelComparisonSummary",
    "OutcomeState",
    "RevenueCaptureResult",
    "RevenueCaptureStatus",
    "evaluate_historical_predictions",
]
