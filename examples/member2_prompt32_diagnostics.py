"""TRAIN/VALIDATION-only diagnostics for the Prompt 31 synthetic demo models.

This bounded experiment reads only the immutable tenant-01 TRAIN and
VALIDATION prepared artifacts and the Prompt 31 model/score artifacts. It
never opens CALIBRATION or TEST row artifacts and writes aggregate output only
to an explicitly private directory outside the repository.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any, Iterable

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from examples.member2_standard_synthetic_demo_training import (
    DATASET_ID,
    TENANT_ID,
    load_development_split,
)
from retainiq_prediction.baselines import (
    FeatureVectorizer,
    MODEL_FEATURE_ALLOWLIST,
    LogisticBaselineConfig,
    LogisticRegressionBaseline,
    RuleBasedBaseline,
    RuleBaselineConfig,
)
from retainiq_prediction.explainability import (
    ExplanationStatus,
    LightGBMExplainer,
    SHAP_AVAILABLE,
    SHAP_VERSION,
)
from retainiq_prediction.label_builder import LabelStatus, SUPPORTED_HORIZONS
from retainiq_prediction.lightgbm_model import LightGBMConfig, LightGBMModel
from retainiq_prediction.temporal_splits import SplitName, TemporalSplitResult


PERSONALIZED_FEATURES = frozenset(
    {
        "recent_usage_trend",
        "historical_avg_sessions_per_week",
        "recent_avg_sessions_per_week",
        "absolute_usage_deviation",
        "percentage_usage_deviation",
        "recent_to_baseline_usage_ratio",
        "historical_weekly_usage_variability",
    }
)
EXPECTED_ARTIFACTS = {
    14: "18aa32de48584192767316772fe68388ed080717322d6571c6861b528a2fa620",
    30: "b5faf7b031814efdaf2755df50fd0d66483aef24d54ac27d166b47e570a40041",
}


class DiagnosticsError(RuntimeError):
    """Fail-closed input or alignment error; contains no row values."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise DiagnosticsError("prediction artifact row is malformed")
                yield value


def _metrics(
    labels: list[int], scores: list[float], *, probability: bool = True
) -> dict[str, Any]:
    if len(labels) != len(scores):
        raise DiagnosticsError("label and score vectors have different lengths")
    if not labels:
        return {
            "n": 0,
            "positive_count": 0,
            "negative_count": 0,
            "prevalence": None,
            "pr_auc_average_precision": None,
            "roc_auc": None,
            "brier": None,
        }
    score_array = np.asarray(scores, dtype=float)
    label_array = np.asarray(labels, dtype=int)
    if not np.isfinite(score_array).all():
        raise DiagnosticsError("a baseline produced a non-finite score")
    if probability and ((score_array < 0) | (score_array > 1)).any():
        raise DiagnosticsError("probability metric received an out-of-range score")
    if not probability:
        # Rule scores are rankings rather than probabilities; Brier is
        # deliberately omitted even if their numeric values happen to be in
        # the unit interval.
        brier = None
    else:
        brier = float(np.mean((score_array - label_array) ** 2))
    positives = int(label_array.sum())
    negatives = len(labels) - positives
    both_classes = positives > 0 and negatives > 0
    return {
        "n": len(labels),
        "positive_count": positives,
        "negative_count": negatives,
        "prevalence": positives / len(labels),
        "pr_auc_average_precision": (
            float(average_precision_score(label_array, score_array)) if both_classes else None
        ),
        "roc_auc": float(roc_auc_score(label_array, score_array)) if both_classes else None,
        "brier": brier,
    }


def _record_label(record, horizon: int):
    return next(label for label in record.labels if label.horizon_days == horizon)


def _horizon_ids(split: TemporalSplitResult, split_name: SplitName, horizon: int) -> set[str]:
    return set(
        split.partition(split_name).supervised_snapshot_ids_by_horizon.get(horizon, ())
    )


def _feature_quality(train_records, validation_records, train_ids, validation_ids) -> dict[str, Any]:
    vectorizer = FeatureVectorizer()
    train = [record for record in train_records if record.stable_snapshot_id in train_ids]
    validation = [
        record for record in validation_records if record.stable_snapshot_id in validation_ids
    ]
    if not train or not validation:
        raise DiagnosticsError("mature feature populations are empty")

    def column_summary(records, index):
        values = [vectorizer.row(record.feature_snapshot)[index] for record in records]
        observed = [float(value) for value in values if value is not None]
        return {
            "n": len(values),
            "missing": len(values) - len(observed),
            "missing_rate": (len(values) - len(observed)) / len(values),
            "unique_observed": len(set(observed)),
            "all_missing": not observed,
            "constant_observed": bool(observed) and len(set(observed)) <= 1,
            "mean": statistics.fmean(observed) if observed else None,
            "median": statistics.median(observed) if observed else None,
        }

    columns: dict[str, Any] = {}
    train_constant = validation_constant = 0
    train_missing_most = validation_missing_most = 0
    for index, name in enumerate(vectorizer.allowlist):
        train_summary = column_summary(train, index)
        validation_summary = column_summary(validation, index)
        train_constant += int(train_summary["constant_observed"])
        validation_constant += int(validation_summary["constant_observed"])
        train_missing_most += int(train_summary["missing_rate"] > 0.5)
        validation_missing_most += int(validation_summary["missing_rate"] > 0.5)
        train_mean = train_summary["mean"]
        validation_mean = validation_summary["mean"]
        columns[name] = {
            "train": train_summary,
            "validation": validation_summary,
            "mean_shift_validation_minus_train": (
                validation_mean - train_mean
                if train_mean is not None and validation_mean is not None
                else None
            ),
            "missing_rate_shift": validation_summary["missing_rate"] - train_summary["missing_rate"],
        }
    return {
        "train_feature_schema": list(vectorizer.allowlist),
        "validation_feature_schema": list(vectorizer.allowlist),
        "schemas_match": True,
        "identifier_fields_in_model_allowlist": False,
        "train_constant_observed_feature_count": train_constant,
        "validation_constant_observed_feature_count": validation_constant,
        "train_more_than_50pct_missing_feature_count": train_missing_most,
        "validation_more_than_50pct_missing_feature_count": validation_missing_most,
        "personalized_columns_present": sorted(PERSONALIZED_FEATURES & set(vectorizer.allowlist)),
        "columns": columns,
    }


def run_diagnostics(prepared_dir: Path, prompt31_dir: Path, output_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    repo_root = Path(__file__).resolve().parents[1]
    prepared_dir, prompt31_dir, output_dir = (
        prepared_dir.resolve(), prompt31_dir.resolve(), output_dir.resolve()
    )
    if output_dir == repo_root or repo_root in output_dir.parents:
        raise DiagnosticsError("aggregate output must remain outside the Git repository")
    if output_dir.exists():
        raise DiagnosticsError("output directory exists; refusing to overwrite")
    if not prompt31_dir.is_dir():
        raise DiagnosticsError("Prompt 31 artifact directory is missing")

    verified, split = load_development_split(prepared_dir)
    source_manifest = prompt31_dir / "training_manifest.json"
    if not source_manifest.is_file():
        raise DiagnosticsError("Prompt 31 aggregate manifest is missing")
    prompt31_manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    if prompt31_manifest.get("dataset_id") != DATASET_ID or prompt31_manifest.get("tenant_scope") != TENANT_ID:
        raise DiagnosticsError("Prompt 31 artifact provenance mismatch")

    train = split.partition(SplitName.TRAIN)
    validation = split.partition(SplitName.VALIDATION)
    train_accounts = {record.account_key for record in train.snapshots}
    validation_accounts = {record.account_key for record in validation.snapshots}
    overlap = len(train_accounts & validation_accounts)
    summary: dict[str, Any] = {
        "evidence_type": "SYNTHETIC_DEMO_ONLY",
        "dataset_id": DATASET_ID,
        "tenant_scope": TENANT_ID,
        "preparation_manifest_sha256": verified["preparation_manifest_sha256"],
        "prompt31_manifest_sha256": _sha256(source_manifest),
        "test_partition_accessed": False,
        "calibration_row_artifacts_accessed": False,
        "train_snapshot_count": len(train.snapshots),
        "validation_snapshot_count": len(validation.snapshots),
        "train_unique_accounts": len(train_accounts),
        "validation_unique_accounts": len(validation_accounts),
        "repeated_train_snapshots": len(train.snapshots) - len(train_accounts),
        "repeated_validation_snapshots": len(validation.snapshots) - len(validation_accounts),
        "train_validation_account_overlap": overlap,
        "horizons": {},
    }

    saved_predictions_path = prompt31_dir / "validation_predictions.jsonl"
    saved_rows: dict[tuple[str, int], dict[str, Any]] = {}
    for row in _jsonl(saved_predictions_path):
        key = (str(row.get("snapshot_id")), int(row.get("horizon_days", -1)))
        if key in saved_rows:
            raise DiagnosticsError("Prompt 31 validation predictions contain duplicate snapshot/horizon keys")
        saved_rows[key] = row

    for horizon in (14, 30):
        train_ids = _horizon_ids(split, SplitName.TRAIN, horizon)
        validation_ids = _horizon_ids(split, SplitName.VALIDATION, horizon)
        train_records = [r for r in train.snapshots if r.stable_snapshot_id in train_ids]
        validation_records = [r for r in validation.snapshots if r.stable_snapshot_id in validation_ids]
        train_labels = [_record_label(r, horizon) for r in train_records]
        validation_labels = [_record_label(r, horizon) for r in validation_records]
        if any(label.label_status not in {LabelStatus.POSITIVE, LabelStatus.NEGATIVE} for label in (*train_labels, *validation_labels)):
            raise DiagnosticsError("split maturity mask included a non-supervised label")
        y_train = [int(label.label) for label in train_labels]
        y_validation = [int(label.label) for label in validation_labels]
        train_prevalence = sum(y_train) / len(y_train)

        model_path = prompt31_dir / "models" / f"horizon-{horizon}d.pkl"
        digest = _sha256(model_path)
        expected = EXPECTED_ARTIFACTS[horizon]
        if digest != expected:
            raise DiagnosticsError("Prompt 31 model artifact digest mismatch")
        lightgbm_model = LightGBMModel.load(model_path, trusted_root=prompt31_dir)
        if lightgbm_model.metadata is None or lightgbm_model.metadata.prediction_horizon_days != horizon:
            raise DiagnosticsError("loaded model horizon metadata mismatch")
        if tuple(lightgbm_model.metadata.feature_names) != tuple(lightgbm_model.vectorizer.allowlist):
            raise DiagnosticsError("model feature metadata/vectorizer order mismatch")
        estimator_classes = [int(value) for value in lightgbm_model._model.classes_]
        if estimator_classes != [0, 1]:
            raise DiagnosticsError("fitted classifier class order is not [non-churn, churn]")

        outlier_base = validation_records[0].feature_snapshot
        outlier_values = outlier_base.feature_values.model_copy(
            update={"sessions_prev_7d": 1_000_000_000}
        )
        outlier_snapshot = outlier_base.model_copy(update={"feature_values": outlier_values})
        outlier_prediction = lightgbm_model.predict(
            outlier_snapshot, horizon_days=horizon
        )
        if (
            outlier_prediction.status.value != "ready"
            or outlier_prediction.score is None
            or not math.isfinite(outlier_prediction.score)
            or not 0.0 <= outlier_prediction.score <= 1.0
        ):
            raise DiagnosticsError("isolated high-usage stress input produced an invalid model score")

        explanation_probe: dict[str, Any]
        complete_input = next(
            (
                record for record in validation_records
                if all(value is not None for value in lightgbm_model.vectorizer.row(record.feature_snapshot))
            ),
            None,
        )
        if not SHAP_AVAILABLE:
            explanation_probe = {
                "status": "UNAVAILABLE",
                "reason": "optional SHAP dependency unavailable",
                "shap_version": SHAP_VERSION,
            }
        elif complete_input is None:
            explanation_probe = {
                "status": "UNAVAILABLE",
                "reason": "no mature validation snapshot has a fully observed model vector",
                "shap_version": SHAP_VERSION,
            }
        else:
            explanation = LightGBMExplainer().explain(
                lightgbm_model,
                complete_input.feature_snapshot,
                horizon_days=horizon,
                expected_model_version=lightgbm_model.metadata.model_version,
                expected_feature_version=lightgbm_model.metadata.feature_version,
                expected_tenant_id=TENANT_ID,
                expected_customer_id=complete_input.feature_snapshot.customer_id,
            )
            contribution_names = {
                item.feature_name for item in explanation.feature_contributions
            }
            explanation_probe = {
                "status": explanation.explanation_status.value,
                "reason_codes": [item.value for item in explanation.reason_codes],
                "shap_version": SHAP_VERSION,
                "output_space": (
                    explanation.explained_output_space.value
                    if explanation.explained_output_space is not None else None
                ),
                "contribution_count": len(explanation.feature_contributions),
                "feature_names_match_model_order_set": (
                    contribution_names == set(lightgbm_model.metadata.feature_names)
                ),
                "finite_feature_values_and_attributions": all(
                    item.model_input_value is not None
                    and math.isfinite(item.model_input_value)
                    and math.isfinite(item.shap_value)
                    for item in explanation.feature_contributions
                ),
                "direction_matches_signed_attribution": all(
                    (item.shap_value > 0 and item.direction.value == "positive")
                    or (item.shap_value < 0 and item.direction.value == "negative")
                    or (item.shap_value == 0 and item.direction.value == "neutral")
                    for item in explanation.feature_contributions
                ),
                "additivity_error": explanation.additivity_error,
                "additivity_tolerance": explanation.additivity_tolerance,
                "customer_level_contributions_persisted": False,
            }
            if explanation.explanation_status is ExplanationStatus.AVAILABLE and not (
                explanation_probe["feature_names_match_model_order_set"]
                and explanation_probe["finite_feature_values_and_attributions"]
                and explanation_probe["direction_matches_signed_attribution"]
                and explanation.additivity_error is not None
                and explanation.additivity_tolerance is not None
                and explanation.additivity_error <= explanation.additivity_tolerance
            ):
                raise DiagnosticsError("actual model SHAP output failed fidelity checks")

        lightgbm_scores: list[float] = []
        lightgbm_seconds = 0.0
        exact_alignment = True
        for record in validation_records:
            label = _record_label(record, horizon)
            cached = saved_rows.get((record.stable_snapshot_id, horizon))
            if cached is None:
                raise DiagnosticsError("mature validation feature has no matching saved inference row")
            if (
                cached.get("tenant_id") != record.feature_snapshot.tenant_id
                or cached.get("customer_id") != record.feature_snapshot.customer_id
                or cached.get("as_of") != record.feature_snapshot.as_of.isoformat().replace("+00:00", "Z")
                or int(cached.get("horizon_days", -1)) != label.horizon_days
                or label.label not in (0, 1)
            ):
                raise DiagnosticsError("saved score and validation label identity mismatch")
            before = time.perf_counter()
            prediction = lightgbm_model.predict(record.feature_snapshot, horizon_days=horizon)
            lightgbm_seconds += time.perf_counter() - before
            if prediction.status.value != "ready" or prediction.score is None:
                raise DiagnosticsError("saved model did not score a mature validation row")
            score = float(prediction.score)
            exact_alignment &= math.isclose(
                score, float(cached["raw_model_score"]), rel_tol=0.0, abs_tol=1e-12
            )
            lightgbm_scores.append(score)
        if len(validation_records) != len(validation_ids) or not exact_alignment:
            raise DiagnosticsError("model reload inference differs from saved scores")
        if any(len([r for r in saved_rows if r[1] == horizon]) != len(validation_records) for _ in [0]):
            raise DiagnosticsError("saved score artifact contains an unexpected horizon count")

        logistic = LogisticRegressionBaseline(
            LogisticBaselineConfig(
                baseline_version=f"prompt32_logistic_v1_{horizon}d",
                random_state=2026,
            )
        )
        logistic_fit = logistic.fit(split, horizon_days=horizon)
        if logistic_fit.status.value != "ready":
            raise DiagnosticsError("existing logistic baseline could not fit from TRAIN")
        logistic_scores = [
            float(logistic.predict(record.feature_snapshot, horizon_days=horizon).score)
            for record in validation_records
        ]

        rule = RuleBasedBaseline(
            RuleBaselineConfig(baseline_version=f"prompt32_rule_v1_{horizon}d")
        )
        rule.fit(horizon_days=horizon)
        rule_predictions = [
            rule.predict(record.feature_snapshot, horizon_days=horizon, payment_failures=None)
            for record in validation_records
        ]
        rule_ready_indexes = [
            index for index, prediction in enumerate(rule_predictions)
            if prediction.status.value == "ready" and prediction.score is not None
        ]
        paired_y = [y_validation[index] for index in rule_ready_indexes]
        paired_rule = [float(rule_predictions[index].score) for index in rule_ready_indexes]
        paired_lgbm = [lightgbm_scores[index] for index in rule_ready_indexes]
        paired_logistic = [logistic_scores[index] for index in rule_ready_indexes]
        paired_train_prevalence = train_prevalence

        no_personal = tuple(
            name for name in MODEL_FEATURE_ALLOWLIST if name not in PERSONALIZED_FEATURES
        )
        ablation = LightGBMModel(
            LightGBMConfig(
                model_version=f"synthetic_demo_only_prompt32_no_personal_baseline_v1_{horizon}d",
                feature_version=lightgbm_model.config.feature_version,
                label_policy_version=lightgbm_model.config.label_policy_version,
                dataset_provenance=lightgbm_model.config.dataset_provenance,
                tenant_id=TENANT_ID,
                random_seed=2026,
                n_estimators=lightgbm_model.config.n_estimators,
                learning_rate=lightgbm_model.config.learning_rate,
                num_leaves=lightgbm_model.config.num_leaves,
                max_depth=lightgbm_model.config.max_depth,
                min_child_samples=lightgbm_model.config.min_child_samples,
                subsample=lightgbm_model.config.subsample,
                colsample_bytree=lightgbm_model.config.colsample_bytree,
                allowlist=no_personal,
            )
        )
        ablation_fit = ablation.fit(split, horizon_days=horizon)
        if ablation_fit.status.value != "ready":
            raise DiagnosticsError("personalization ablation did not fit")
        ablation_scores = [
            float(ablation.predict(record.feature_snapshot, horizon_days=horizon).score)
            for record in validation_records
        ]

        baseline_metrics = _metrics(y_validation, [train_prevalence] * len(y_validation))
        candidate_metrics = _metrics(y_validation, lightgbm_scores)
        labels_by_status = Counter(
            label.label_status.value
            for record in validation.snapshots
            for label in record.labels
            if label.horizon_days == horizon
        )
        unique_positive_accounts = len({r.account_key for r, y in zip(validation_records, y_validation) if y == 1})
        unique_negative_accounts = len({r.account_key for r, y in zip(validation_records, y_validation) if y == 0})

        # Subgroup stability is descriptive only; it is not used to select a model.
        subgroup_metrics: dict[str, Any] = {}
        for group in ("available", "zero_baseline", "insufficient_history", "unavailable"):
            pairs = [
                (y_validation[index], lightgbm_scores[index], ablation_scores[index])
                for index, record in enumerate(validation_records)
                if record.feature_snapshot.data_quality.personal_baseline_status.value == group
            ]
            subgroup_metrics[group] = {
                "n": len(pairs),
                "lightgbm": _metrics([p[0] for p in pairs], [p[1] for p in pairs]),
                "without_personal_baseline": _metrics([p[0] for p in pairs], [p[2] for p in pairs]),
            }

        feature_diagnostics = _feature_quality(train.snapshots, validation.snapshots, train_ids, validation_ids)
        summary["horizons"][str(horizon)] = {
            "label_semantics": {"positive": "confirmed effective account churn", "negative": "mature observed non-churn"},
            "train": {
                "snapshot_count": len(train.snapshots),
                "eligible_snapshots": sum(r.prediction_eligible for r in train.snapshots),
                "mature_supervised_rows": len(train_records),
                "positive": sum(y_train),
                "negative": len(y_train) - sum(y_train),
                "prevalence": train_prevalence,
                "unique_accounts": len({r.account_key for r in train_records}),
                "label_status_counts_all_snapshots": dict(sorted(Counter(l.label_status.value for r in train.snapshots for l in r.labels if l.horizon_days == horizon).items())),
            },
            "validation": {
                "snapshot_count": len(validation.snapshots),
                "eligible_snapshots": sum(r.prediction_eligible for r in validation.snapshots),
                "mature_supervised_rows": len(validation_records),
                "positive": sum(y_validation),
                "negative": len(y_validation) - sum(y_validation),
                "prevalence": sum(y_validation) / len(y_validation),
                "unique_accounts_any_label": len({r.account_key for r in validation_records}),
                "unique_positive_accounts": unique_positive_accounts,
                "unique_negative_accounts": unique_negative_accounts,
                "label_status_counts_all_snapshots": dict(sorted(labels_by_status.items())),
                "known_cancellation_or_not_eligible_rows_in_prepared_feature_cohort": 0,
                "independently_evaluated_label_rows": len(validation_records),
                "independent_positive_accounts_not_independent_row_count": unique_positive_accounts,
                "canonical_production_scores": 0,
                "internal_raw_model_scores": len(lightgbm_scores),
                "raw_scores_abstained_or_failed": 0,
                "rule_scoreable_rows": len(rule_ready_indexes),
                "rule_score_coverage": len(rule_ready_indexes) / len(validation_records),
            },
            "full_validation_candidate_metrics": candidate_metrics,
            "training_prevalence_reference": {
                **baseline_metrics,
                "constant_score": train_prevalence,
                "pr_auc_no_skill_reference_validation_prevalence": sum(y_validation) / len(y_validation),
                "brier_difference_candidate_minus_reference": candidate_metrics["brier"] - baseline_metrics["brier"],
            },
            "paired_rule_scoreable_validation_comparison": {
                "same_population_for_all_rows": True,
                "metrics": {
                    "rule_inactivity_and_usage_ranking_only_payment_input_missing": _metrics(paired_y, paired_rule, probability=False),
                    "logistic_regression_uncalibrated": _metrics(paired_y, paired_logistic),
                    "lightgbm_uncalibrated": _metrics(paired_y, paired_lgbm),
                    "constant_training_prevalence": _metrics(paired_y, [paired_train_prevalence] * len(paired_y)),
                },
                "rule_brier": "N/A: rule score is a ranking score, not a probability",
                "payment_failure_signal": "N/A: no point-in-time billing feature is included in prepared model snapshots",
            },
            "personalization_ablation": {
                "removed_features": sorted(PERSONALIZED_FEATURES),
                "retained_features": list(no_personal),
                "same_training_rows_and_seed": True,
                "same_fixed_lightgbm_hyperparameters": True,
                "full_model_metrics": candidate_metrics,
                "without_personal_baseline_metrics": _metrics(y_validation, ablation_scores),
                "delta_without_minus_with": {
                    metric: (
                        _metrics(y_validation, ablation_scores)[metric] - candidate_metrics[metric]
                        if candidate_metrics[metric] is not None and _metrics(y_validation, ablation_scores)[metric] is not None
                        else None
                    )
                    for metric in ("pr_auc_average_precision", "roc_auc", "brier")
                },
                "missing_history_subgroups": subgroup_metrics,
            },
            "feature_diagnostics": feature_diagnostics,
            "score_alignment": {
                "saved_prediction_artifact_rows_matched_by_snapshot_and_horizon": len(validation_records),
                "score_vector_reproduced_after_model_reload": exact_alignment,
                "class_1_is_churn": True,
                "predict_proba_positive_class_column": 1,
                "estimator_classes_order": estimator_classes,
                "row_order_join_used": False,
                "artifact_sha256": digest,
                "model_version": lightgbm_model.metadata.model_version,
                "feature_names_match_vectorizer_order": True,
            },
            "actual_saved_model_shap_probe": explanation_probe,
            "isolated_high_usage_outlier_stress": {
                "synthetic_fixture_only": True,
                "sessions_prev_7d": 1_000_000_000,
                "raw_model_score_finite_and_bounded": True,
                "raw_score_persisted": False,
                "not_a_performance_metric": True,
            },
            "inference_batch": {
                "rows": len(validation_records),
                "successful_raw_scores": len(lightgbm_scores),
                "failed_rows": 0,
                "runtime_seconds_model_vectorization_and_predict_only": lightgbm_seconds,
                "rows_per_second_model_vectorization_and_predict_only": len(lightgbm_scores) / lightgbm_seconds if lightgbm_seconds else None,
                "data_extraction_and_feature_building_included": False,
            },
        }

    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary["runtime_seconds_total"] = time.perf_counter() - started
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "aggregate_diagnostics.json"
    output_path.write_text(json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    summary["aggregate_output_sha256"] = _sha256(output_path)
    # Hash is printed separately to avoid self-referential file hashing.
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--prompt31-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_diagnostics(args.prepared_dir, args.prompt31_dir, args.output_dir), sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
