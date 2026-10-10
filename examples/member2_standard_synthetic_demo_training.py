"""Train explicitly synthetic-only, uncalibrated STANDARD horizon demos.

Reads only the frozen tenant-01 TRAIN and VALIDATION prepared artifacts. It
does not open CALIBRATION or TEST label/features, change the prepared dataset,
or produce canonical PredictionOutput records. Models and customer-level
validation scores must be written outside the Git repository.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Iterable

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from retainiq_prediction.dataset_readiness import DatasetStatus
from retainiq_prediction.feature_builder import FeatureSnapshot
from retainiq_prediction.label_builder import ChurnLabel, SUPPORTED_HORIZONS
from retainiq_prediction.lightgbm_model import (
    LIGHTGBM_AVAILABLE,
    LIGHTGBM_VERSION,
    LightGBMConfig,
    LightGBMModel,
)
from retainiq_prediction.temporal_splits import (
    SnapshotRecord,
    SplitName,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitResult,
    TemporalSplitter,
)


DATASET_ID = "synthetic-saas-v1-2-standard-s2026-970a9d231e68"
SOURCE_MANIFEST_SHA256 = "7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d"
PREPARATION_MANIFEST_SHA256 = "1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a"
TENANT_ID = "tenant-01"
MINIMUM_CLASS_SUPPORT = {
    "minimum_positive_samples": 50,
    "minimum_negative_samples": 50,
    "minimum_unique_positive_accounts": 20,
    "minimum_unique_negative_accounts": 20,
}
DEVELOPMENT_FILES = tuple(
    f"{stage}_{kind}.jsonl.gz"
    for stage in ("train", "validation")
    for kind in ("features", "labels")
)


class DemoTrainingError(RuntimeError):
    """Fail-closed validation error; callers must not print record contents."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl_gzip(path: Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise DemoTrainingError("development artifact row is not an object")
                yield value


def _verify_prepared_inputs(prepared_dir: Path) -> dict[str, Any]:
    manifest_path = prepared_dir / "preparation_manifest.json"
    manifest_hash_path = prepared_dir / "preparation_manifest.sha256"
    if not manifest_path.is_file() or not manifest_hash_path.is_file():
        raise DemoTrainingError("prepared-data manifest is missing")
    manifest_bytes = manifest_path.read_bytes()
    actual_manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    recorded_hash = manifest_hash_path.read_text(encoding="ascii").split()[0]
    if (
        actual_manifest_hash != recorded_hash
        or actual_manifest_hash != PREPARATION_MANIFEST_SHA256
    ):
        raise DemoTrainingError("prepared-data manifest checksum mismatch")

    manifest = json.loads(manifest_bytes)
    identity = manifest.get("dataset_identity", {})
    scope = manifest.get("tenant_scope", {})
    if (
        manifest.get("evidence_provenance") != "SYNTHETIC_ONLY"
        or identity.get("dataset_id") != DATASET_ID
        or identity.get("dataset_manifest_sha256") != SOURCE_MANIFEST_SHA256
        or identity.get("seed") != 2026
        or scope.get("tenant_id_from_authenticated_principal") != TENANT_ID
        or scope.get("authorized_tenant_count") != 1
        or scope.get("other_dataset_tenants_accessed") is not False
        or identity.get("target_policy_version") != "effective-account-churn-v1.2"
    ):
        raise DemoTrainingError("prepared dataset identity or tenant scope mismatch")

    checksums = manifest.get("artifact_checksums", {})
    verified: dict[str, str] = {}
    for name in DEVELOPMENT_FILES:
        expected = checksums.get(name, {}).get("sha256")
        path = prepared_dir / name
        if not path.is_file() or not isinstance(expected, str):
            raise DemoTrainingError("TRAIN/VALIDATION artifact is missing from the manifest")
        actual = _sha256(path)
        if actual != expected:
            raise DemoTrainingError("TRAIN/VALIDATION artifact checksum mismatch")
        verified[name] = actual
    return {"manifest": manifest, "preparation_manifest_sha256": actual_manifest_hash,
            "development_artifact_sha256": verified}


def _feature_snapshot(row: dict[str, Any]) -> FeatureSnapshot:
    if row.get("tenant_id") != TENANT_ID or row.get("prediction_eligibility") != "ELIGIBLE":
        raise DemoTrainingError("feature row has an unexpected tenant or eligibility state")
    as_of = row.get("as_of")
    return FeatureSnapshot.model_validate(
        {
            "tenant_id": row["tenant_id"],
            "customer_id": row["customer_id"],
            "as_of": as_of,
            # The preparation serializes features created by FeatureBuilder,
            # whose data_cutoff_at is exactly the prediction as_of.
            "data_cutoff_at": as_of,
            "feature_version": row["feature_version"],
            "feature_values": row["feature_values"],
            "data_quality": row["feature_quality"],
            "source_evidence_refs": row["feature_source_evidence_refs"],
        }
    )


def _label(row: dict[str, Any]) -> ChurnLabel:
    if row.get("tenant_id") != TENANT_ID or row.get("test_labels_evaluation_only") is not False:
        raise DemoTrainingError("development label has an unexpected tenant or split marker")
    fields = ChurnLabel.model_fields
    return ChurnLabel.model_validate({key: value for key, value in row.items() if key in fields})


def _load_stage(prepared_dir: Path, stage: str) -> tuple[SnapshotRecord, ...]:
    if stage not in {"train", "validation"}:
        raise DemoTrainingError("only TRAIN and VALIDATION may be loaded")
    feature_rows: dict[str, tuple[FeatureSnapshot, dict[str, Any]]] = {}
    for row in _jsonl_gzip(prepared_dir / f"{stage}_features.jsonl.gz"):
        if row.get("split") != stage.upper():
            raise DemoTrainingError("feature row is outside its declared development stage")
        snapshot_id = row.get("snapshot_id")
        if not isinstance(snapshot_id, str) or snapshot_id in feature_rows:
            raise DemoTrainingError("feature snapshot identity is missing or duplicated")
        feature_rows[snapshot_id] = (_feature_snapshot(row), row)

    labels_by_snapshot: dict[str, list[ChurnLabel]] = defaultdict(list)
    for row in _jsonl_gzip(prepared_dir / f"{stage}_labels.jsonl.gz"):
        snapshot_id = row.get("snapshot_id")
        if not isinstance(snapshot_id, str) or snapshot_id not in feature_rows:
            raise DemoTrainingError("label does not match a loaded development snapshot")
        labels_by_snapshot[snapshot_id].append(_label(row))

    records: list[SnapshotRecord] = []
    for snapshot_id, (feature, _) in feature_rows.items():
        labels = sorted(labels_by_snapshot.get(snapshot_id, ()), key=lambda item: item.horizon_days)
        if tuple(item.horizon_days for item in labels) != SUPPORTED_HORIZONS:
            raise DemoTrainingError("snapshot does not have exactly one label per supported horizon")
        if any(
            label.customer_id != feature.customer_id or label.as_of != feature.as_of
            for label in labels
        ):
            raise DemoTrainingError("feature and label snapshot identities do not agree")
        records.append(
            SnapshotRecord(
                snapshot_id=snapshot_id,
                feature_snapshot=feature,
                labels=tuple(labels),
                prediction_eligible=True,
            )
        )
    if set(labels_by_snapshot) != set(feature_rows):
        raise DemoTrainingError("development feature/label snapshot sets differ")
    return tuple(records)


def load_development_split(prepared_dir: Path) -> tuple[dict[str, Any], TemporalSplitResult]:
    verified = _verify_prepared_inputs(prepared_dir)
    manifest = verified["manifest"]
    train_records = _load_stage(prepared_dir, "train")
    validation_records = _load_stage(prepared_dir, "validation")
    if not train_records or not validation_records:
        raise DemoTrainingError("TRAIN and VALIDATION must both contain snapshots")

    split_data = manifest["temporal_split_manifest"]
    boundaries = TemporalSplitBoundaries.model_validate(split_data["boundaries"])
    split_config = TemporalSplitConfig(
        boundaries=boundaries,
        split_policy_version=split_data["split_policy_version"],
        dataset_identifier=DATASET_ID,
        authorized_dataset=False,
        maturity_gap=timedelta(seconds=int(split_data["configuration"]["maturity_gap_seconds"])),
        minimum_samples_per_horizon=2,
    )
    result = TemporalSplitter(split_config).split((*train_records, *validation_records))
    if result.partition(SplitName.CALIBRATION).snapshots or result.partition(SplitName.TEST).snapshots:
        raise DemoTrainingError("CALIBRATION/TEST rows unexpectedly entered the development load")
    if result.manifest.dataset_readiness_status is not DatasetStatus.BLOCKED:
        raise DemoTrainingError("synthetic demo must retain blocked dataset readiness")

    for stage, end in (
        (SplitName.TRAIN, boundaries.train_end),
        (SplitName.VALIDATION, boundaries.validation_end),
    ):
        partition = result.partition(stage)
        for horizon in SUPPORTED_HORIZONS:
            ids = set(partition.supervised_snapshot_ids_by_horizon.get(horizon, ()))
            for record in partition.snapshots:
                if record.stable_snapshot_id not in ids:
                    continue
                label = next(item for item in record.labels if item.horizon_days == horizon)
                if not (
                    label.evaluation_as_of <= end
                    and label.label_observed_through <= end
                    and label.label_generated_at <= end
                ):
                    raise DemoTrainingError("mature-label cutoff validation failed")

    return verified, result


def _quality_summary(records: tuple[SnapshotRecord, ...]) -> dict[str, Any]:
    coverage = Counter(
        record.feature_snapshot.data_quality.usage_coverage_status.value for record in records
    )
    baseline = Counter(
        record.feature_snapshot.data_quality.personal_baseline_status.value for record in records
    )
    # Reliability/freshness are aggregated directly from prepared metadata by
    # the caller; this function handles the typed feature-quality fields.
    history_days = [
        record.feature_snapshot.data_quality.observed_history_days for record in records
    ]
    return {
        "snapshots": len(records),
        "unique_accounts": len({record.account_key for record in records}),
        "repeated_account_snapshots": len(records) - len({record.account_key for record in records}),
        "usage_coverage_status_counts": dict(sorted(coverage.items())),
        "personal_baseline_status_counts": dict(sorted(baseline.items())),
        "recent_window_covered": sum(
            record.feature_snapshot.data_quality.recent_window_covered for record in records
        ),
        "baseline_window_covered": sum(
            record.feature_snapshot.data_quality.baseline_window_covered for record in records
        ),
        "observed_history_days_min_median_max": [
            min(history_days), statistics.median(history_days), max(history_days)
        ] if history_days else [],
    }


def _stage_quality_from_rows(prepared_dir: Path, stage: str) -> dict[str, Any]:
    reliability: Counter[str] = Counter()
    freshness: Counter[str] = Counter()
    for row in _jsonl_gzip(prepared_dir / f"{stage}_features.jsonl.gz"):
        reliability[str(row.get("reliability", {}).get("status", "unknown"))] += 1
        freshness[str(row.get("freshness", {}).get("status", "unknown"))] += 1
    return {"reliability_status_counts_pre_correction_artifact": dict(sorted(reliability.items())),
            "freshness_status_counts_pre_correction_artifact": dict(sorted(freshness.items()))}


def _label_support(partition, horizon: int) -> dict[str, Any]:
    all_labels = [
        next(item for item in record.labels if item.horizon_days == horizon)
        for record in partition.snapshots
    ]
    supervised_ids = set(partition.supervised_snapshot_ids_by_horizon.get(horizon, ()))
    usable = [
        (record, next(item for item in record.labels if item.horizon_days == horizon))
        for record in partition.snapshots
        if record.stable_snapshot_id in supervised_ids
    ]
    positives = [(record, label) for record, label in usable if label.label == 1]
    negatives = [(record, label) for record, label in usable if label.label == 0]
    statuses = Counter(label.label_status.value for label in all_labels)
    return {
        "snapshot_count": len(partition.snapshots),
        "label_status_counts": dict(sorted(statuses.items())),
        "mature_usable_rows": len(usable),
        "mature_positive_rows": len(positives),
        "mature_negative_rows": len(negatives),
        "mature_unique_positive_accounts": len({record.account_key for record, _ in positives}),
        "mature_unique_negative_accounts": len({record.account_key for record, _ in negatives}),
        "mature_unique_usable_accounts": len({record.account_key for record, _ in usable}),
        "passes_frozen_class_support": _passes_frozen_support(positives, negatives),
    }


def _passes_frozen_support(positives, negatives) -> bool:
    return (
        len(positives) >= MINIMUM_CLASS_SUPPORT["minimum_positive_samples"]
        and len(negatives) >= MINIMUM_CLASS_SUPPORT["minimum_negative_samples"]
        and len({record.account_key for record, _ in positives})
        >= MINIMUM_CLASS_SUPPORT["minimum_unique_positive_accounts"]
        and len({record.account_key for record, _ in negatives})
        >= MINIMUM_CLASS_SUPPORT["minimum_unique_negative_accounts"]
    )


def _score_metrics(labels: list[int], scores: list[float]) -> dict[str, float]:
    if len(set(labels)) != 2:
        raise DemoTrainingError("validation sample does not contain both outcome classes")
    y = np.asarray(labels, dtype=int)
    p = np.asarray(scores, dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise DemoTrainingError("inference returned an invalid score")
    return {
        "average_precision_pr_auc": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "brier_score_uncalibrated": float(np.mean((p - y) ** 2)),
    }


def run_demo(prepared_dir: Path, output_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    repo_root = Path(__file__).resolve().parents[1]
    prepared_dir = prepared_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir == repo_root or repo_root in output_dir.parents:
        raise DemoTrainingError("model/prediction outputs must remain outside the Git repository")
    if output_dir.exists():
        raise DemoTrainingError("output directory already exists; refusing to overwrite")
    if not LIGHTGBM_AVAILABLE:
        raise DemoTrainingError("LightGBM is not installed in the repository environment")

    verified, split_result = load_development_split(prepared_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    models_dir = output_dir / "models"
    models_dir.mkdir()
    train = split_result.partition(SplitName.TRAIN)
    validation = split_result.partition(SplitName.VALIDATION)
    train_support = {h: _label_support(train, h) for h in SUPPORTED_HORIZONS}
    validation_support = {h: _label_support(validation, h) for h in SUPPORTED_HORIZONS}
    trained: dict[int, dict[str, Any]] = {}

    for horizon in SUPPORTED_HORIZONS:
        if not (
            train_support[horizon]["passes_frozen_class_support"]
            and validation_support[horizon]["passes_frozen_class_support"]
        ):
            trained[horizon] = {
                "status": "NOT_TRAINED_FROZEN_STAGE_SUPPORT_BLOCKED",
                "train": train_support[horizon],
                "validation": validation_support[horizon],
            }
            continue

        feature_versions = {r.feature_snapshot.feature_version for r in train.snapshots}
        label_versions = {
            next(label.label_policy_version for label in r.labels if label.horizon_days == horizon)
            for r in train.snapshots
            if r.stable_snapshot_id in set(train.supervised_snapshot_ids_by_horizon.get(horizon, ()))
        }
        if len(feature_versions) != 1 or len(label_versions) != 1:
            raise DemoTrainingError("training feature or label versions are inconsistent")
        feature_version = next(iter(feature_versions))
        label_policy_version = next(iter(label_versions))
        model_version = f"synthetic_demo_only_standard_tenant01_lightgbm_v1_{horizon}d"
        config = LightGBMConfig(
            model_version=model_version,
            feature_version=feature_version,
            label_policy_version=label_policy_version,
            dataset_provenance=(
                f"SYNTHETIC_DEMO_ONLY:{DATASET_ID}:tenant-01:"
                f"preparation_manifest_sha256={verified['preparation_manifest_sha256']}"
            ),
            tenant_id=TENANT_ID,
            random_seed=2026,
            use_validation_early_stopping=False,
        )
        model = LightGBMModel(config)
        fit = model.fit(split_result, horizon_days=horizon)  # TRAIN mask only
        if fit.status.value != "ready" or fit.metadata is None:
            raise DemoTrainingError("supported development horizon did not fit successfully")
        artifact_path = models_dir / f"horizon-{horizon}d.pkl"
        model.save(artifact_path)
        loaded = LightGBMModel.load(artifact_path, trusted_root=output_dir)

        validation_ids = set(validation.supervised_snapshot_ids_by_horizon.get(horizon, ()))
        prediction_rows: list[dict[str, Any]] = []
        eval_labels: list[int] = []
        eval_scores: list[float] = []
        for record in validation.snapshots:
            if record.stable_snapshot_id not in validation_ids:
                continue
            prediction = loaded.predict(record.feature_snapshot, horizon_days=horizon)
            if prediction.status.value != "ready" or prediction.score is None:
                raise DemoTrainingError("saved model inference smoke did not return a score")
            # Keep row-level scores private; this file is written only beneath
            # the validated outside-repository experiment directory.
            prediction_rows.append({
                "evidence_type": "SYNTHETIC_DEMO_ONLY",
                "dataset_id": DATASET_ID,
                "tenant_id": TENANT_ID,
                "customer_id": record.feature_snapshot.customer_id,
                "snapshot_id": record.stable_snapshot_id,
                "as_of": record.feature_snapshot.as_of.isoformat().replace("+00:00", "Z"),
                "horizon_days": horizon,
                "feature_version": feature_version,
                "model_version": model_version,
                "label_policy_version": label_policy_version,
                "score_kind": prediction.score_kind.value,
                "raw_model_score": float(prediction.score),
                "calibration_status": "NOT_CALIBRATED",
                "production_eligible": False,
            })
            label = next(item for item in record.labels if item.horizon_days == horizon)
            eval_labels.append(int(label.label))
            eval_scores.append(float(prediction.score))

        trained[horizon] = {
            "status": "FITTED_UNCALIBRATED_SYNTHETIC_DEMO_ONLY",
            "model_version": model_version,
            "feature_version": feature_version,
            "label_policy_version": label_policy_version,
            "fit_counts": {
                "training_rows": fit.training_snapshot_count,
                "positive_rows": fit.positive_count,
                "negative_rows": fit.negative_count,
                "unique_training_accounts": train_support[horizon]["mature_unique_usable_accounts"],
            },
            "train_support": train_support[horizon],
            "validation_support": validation_support[horizon],
            "validation_metrics_uncalibrated_synthetic_only": _score_metrics(eval_labels, eval_scores),
            "validation_inference_rows": len(prediction_rows),
            "model_artifact_path": str(artifact_path),
            "model_artifact_sha256": _sha256(artifact_path),
            "model_load_and_inference_smoke": "PASS",
            "calibration": "NOT_PERFORMED_FROZEN_CALIBRATION_SUPPORT_GATE_BLOCKED",
            "validation_prediction_rows": prediction_rows,
        }

    # Keep customer-level predictions in one private file and remove them from
    # the aggregate report/manifest below.
    all_predictions: list[dict[str, Any]] = []
    for horizon_data in trained.values():
        all_predictions.extend(horizon_data.pop("validation_prediction_rows", []))
    all_predictions.sort(key=lambda row: (row["as_of"], row["customer_id"], row["horizon_days"]))
    predictions_path = output_dir / "validation_predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in all_predictions:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

    account_overlap = len(
        {record.account_key for record in train.snapshots}
        & {record.account_key for record in validation.snapshots}
    )
    feature_versions = sorted({r.feature_snapshot.feature_version for r in (*train.snapshots, *validation.snapshots)})
    manifest = {
        "experiment_id": "prompt31-standard-tenant01-synthetic-demo-v1",
        "status": "TRAINED_SYNTHETIC_DEMO_ONLY",
        "evidence_type": "SYNTHETIC_DEMO_ONLY",
        "dataset_id": DATASET_ID,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "preparation_manifest_sha256": verified["preparation_manifest_sha256"],
        "preparation_artifact_sha256": verified["development_artifact_sha256"],
        "tenant_scope": TENANT_ID,
        "generator_seed": 2026,
        "label_policy_version": "effective-account-churn-v1.2",
        "feature_versions": feature_versions,
        "split_policy_version": split_result.manifest.split_policy_version,
        "frozen_boundaries": split_result.manifest.boundaries.model_dump(mode="json"),
        "frozen_class_support_minimums": MINIMUM_CLASS_SUPPORT,
        "train_summary": {
            **_quality_summary(train.snapshots),
            **_stage_quality_from_rows(prepared_dir, "train"),
        },
        "validation_summary": {
            **_quality_summary(validation.snapshots),
            **_stage_quality_from_rows(prepared_dir, "validation"),
        },
        "train_validation_unique_account_overlap": account_overlap,
        "horizons": {str(h): trained[h] for h in SUPPORTED_HORIZONS},
        "calibration_status": "NOT_PERFORMED; FROZEN CALIBRATION SUPPORT GATE BLOCKS A COMPLETE BUNDLE",
        "canonical_prediction_output_created": False,
        "production_readiness": "BLOCKED",
        "test_partition_accessed": False,
        "test_label_artifact_opened": False,
        "calibration_label_artifact_opened": False,
        "hyperparameter_tuning": "NONE; fixed existing LightGBM defaults and seed",
        "validation_is_development_evidence_only": True,
        "warning": "Temporal evaluation covers repeat accounts; it does not establish unseen-account generalization or real-world performance.",
        "runtime": {
            "python": sys.version.split()[0],
            "lightgbm": LIGHTGBM_VERSION,
            "numpy": importlib.metadata.version("numpy"),
            "scikit_learn": importlib.metadata.version("scikit-learn"),
        },
        "preparation_seconds": round(time.perf_counter() - started, 3),
        "validation_predictions_path": str(predictions_path),
        "validation_predictions_sha256": _sha256(predictions_path),
    }
    manifest_path = output_dir / "training_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_hash = _sha256(manifest_path)
    (output_dir / "training_manifest.sha256").write_text(
        f"{manifest_hash}  training_manifest.json\n", encoding="ascii", newline="\n"
    )
    return {
        "status": manifest["status"],
        "experiment_id": manifest["experiment_id"],
        "dataset_id": DATASET_ID,
        "tenant_scope": TENANT_ID,
        "horizons": {
            key: {
                "status": value["status"],
                "training_rows": value.get("fit_counts", {}).get("training_rows"),
                "validation_rows": value.get("validation_inference_rows"),
                "metrics": value.get("validation_metrics_uncalibrated_synthetic_only"),
            }
            for key, value in manifest["horizons"].items()
        },
        "production_readiness": manifest["production_readiness"],
        "test_partition_accessed": manifest["test_partition_accessed"],
        "training_manifest_sha256": manifest_hash,
        "preparation_seconds": manifest["preparation_seconds"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_demo(args.prepared_dir, args.output_dir), sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # Do not print exception reprs or validation payloads that may contain
        # customer identifiers from the private development artifacts.
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
