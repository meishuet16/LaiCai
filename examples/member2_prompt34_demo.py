"""Isolated synthetic-only three-horizon training and replay demonstration.

All generated source rows, prepared snapshots, fitted artifacts, and row-level
prediction outputs are written outside the repository. The demo never reads
the frozen STANDARD cohort. Run ``prepare`` once, then ``train``; ``replay``
loads the saved bundle and exercises the existing operational pipeline.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Iterable, Mapping

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from retaniq.data_foundation import authenticate_service_principal
from retaniq.synthetic.canonical_adapter import import_dataset, provision_member2_reader
from retaniq.synthetic.config import SyntheticConfig
from retaniq.synthetic.v12_generator import generate_dataset
from retainiq_prediction.baselines import (
    MODEL_FEATURE_ALLOWLIST,
    BaselineStatus,
    LogisticBaselineConfig,
    LogisticRegressionBaseline,
    RuleBaselineConfig,
    RuleBasedBaseline,
)
from retainiq_prediction.calibration import (
    CalibrationConfig,
    ProbabilityCalibrator,
)
from retainiq_prediction.contracts import (
    FreshnessStatus,
    PredictionOutput,
    PredictionStatus,
    ReliabilityStatus,
)
from retainiq_prediction.dataset_readiness import (
    DatasetProvenance,
    DatasetReadinessReport,
    DatasetStatus,
    ProvenanceEvidenceType,
)
from retainiq_prediction.eligibility import EligibilityPolicy
from retainiq_prediction.feature_builder import FeatureSnapshot
from retainiq_prediction.historical_dataset_preparation import (
    build_cutoff_schedule,
    prepare_historical_dataset,
    select_predeclared_cutoffs,
)
from retainiq_prediction.historical_evaluation import (
    DatasetProvenanceStatus,
    EvaluationPrediction,
    HistoricalEvaluationConfig,
    HistoricalEvaluator,
)
from retainiq_prediction.label_builder import ChurnLabel, SUPPORTED_HORIZONS
from retainiq_prediction.lightgbm_model import (
    LIGHTGBM_AVAILABLE,
    LIGHTGBM_VERSION,
    LightGBMConfig,
    LightGBMModel,
)
from retainiq_prediction.operational_inference import (
    AlertPolicy,
    BatchItemStatus,
    DataFoundationPredictionSnapshotStore,
    DailyPredictionBatch,
    HistoricalRiskAlert,
    InMemoryPredictionSnapshotStore,
    PointInTimeReplayRunner,
    PredictionPersistenceConflict,
    StoreDisposition,
    apply_alert_policy,
)
from retainiq_prediction.prediction_pipeline import (
    PipelineExecutionMode,
    PredictionPipeline,
    PredictionPipelineConfig,
    PredictionRequest,
)
from retainiq_prediction.reliability import ReliabilityPolicy
from retainiq_prediction.sqlite_data_adapter import SQLiteDataAdapter
from retainiq_prediction.temporal_splits import (
    SnapshotRecord,
    SplitName,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitResult,
    TemporalSplitter,
)
from retainiq_prediction.horizon_coherence import (
    HorizonProbabilities,
    calibrated_bundle_from_outputs,
    enforce_horizon_coherence,
)
from retaniq.data_foundation import store_prediction


UTC = timezone.utc
PROFILE = "prompt34_demo"
SEED = 2034
TENANT_ID = "tenant-01"
DATASET_ID_PREFIX = "synthetic-saas-v1-2-prompt34_demo-s2034-"
MODEL_VERSION = "retainiq-prompt34-lightgbm-bundle-v1"
CALIBRATION_VERSION = "retainiq-prompt34-sigmoid-bundle-v1"
ALERT_POLICY_VERSION = "prompt34-synthetic-demo-alert-v1"
REVIEW_CAPACITY_K = 50
CLASS_SUPPORT = {
    "minimum_positive_samples": 50,
    "minimum_negative_samples": 50,
    "minimum_unique_positive_accounts": 20,
    "minimum_unique_negative_accounts": 20,
}
PERSONALIZED_FEATURES = frozenset(
    {
        "historical_avg_sessions_per_week",
        "recent_avg_sessions_per_week",
        "absolute_usage_deviation",
        "percentage_usage_deviation",
        "recent_to_baseline_usage_ratio",
        "historical_weekly_usage_variability",
    }
)
NON_PERSONALIZED_ALLOWLIST = tuple(
    name for name in MODEL_FEATURE_ALLOWLIST if name not in PERSONALIZED_FEATURES
)
DEFAULT_ROOT = Path.home() / "RetainIQ-private" / "prompt34-three-horizon-demo-v1"
REDUCED_ROOT = Path.home() / "RetainIQ-private" / "prompt34-three-horizon-reduced-v1"
REDUCED_CUTOFF_COUNTS = {
    SplitName.TRAIN: 12,
    SplitName.VALIDATION: 5,
    SplitName.CALIBRATION: 4,
    SplitName.TEST: 4,
}
REDUCED_CUTOFF_POLICY_VERSION = "prompt34-predeclared-evenly-spaced-cutoffs-v1"


class DemoError(RuntimeError):
    """A safe, non-PII failure in the isolated demo workflow."""


class _ReaderCallCounter:
    """Count authenticated Member 1 read calls without logging arguments."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.counts: Counter[str] = Counter()

    def __getattr__(self, name: str):
        attribute = getattr(self._delegate, name)
        if not callable(attribute):
            return attribute

        def call(*args, **kwargs):
            self.counts[name] += 1
            return attribute(*args, **kwargs)

        return call


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonl_gzip(path: Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise DemoError("prepared JSONL contains a non-object row")
                yield value


def _write_jsonl_gzip(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
            import io

            with io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as text:
                for row in rows:
                    text.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False))
                    text.write("\n")
                    count += 1
    return count


def _safe_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if resolved == repo or repo in resolved.parents:
        raise DemoError("private data and fitted outputs must remain outside the repository")
    return resolved


def prepare(root: Path, *, account_count: int = 5000, seed: int = SEED) -> dict[str, Any]:
    """Generate one new source family, import canonically, and prepare PIT rows."""

    root = _safe_root(root)
    if root.exists():
        raise FileExistsError("Prompt 34 output root already exists; refusing to overwrite it")
    if account_count < 1000:
        raise ValueError("the fixed class-support policy requires a longitudinal cohort; use >=1000 accounts")
    if seed != SEED:
        raise ValueError(f"this reproducible demo version is pinned to seed {SEED}")

    source_root = root / "source"
    config = SyntheticConfig(
        profile=PROFILE,
        seed=seed,
        account_count=account_count,
        tenant_count=1,
        start_date="2024-10-01",
        end_date="2026-10-01",
        generator_version="synthetic-saas-v1.2",
        generator_build_revision="r9",
        target_policy_version="effective-account-churn-v1.2",
    )
    generated = generate_dataset(config, source_root)
    dataset_path = Path(generated["dataset_path"]).resolve()
    database_path = root / "prompt34-demo.sqlite3"
    imported = import_dataset(dataset_path, database_path)
    if imported.get("status") != "VERIFIED":
        raise DemoError("authenticated canonical synthetic import did not verify")

    # The bearer token is created and consumed only in memory; it is never
    # serialized, logged, or placed in a command line or environment variable.
    provisioned = provision_member2_reader(dataset_path, database_path, TENANT_ID)
    token = provisioned.pop("token")
    principal = authenticate_service_principal(database_path, token)
    adapter = SQLiteDataAdapter(database_path, dataset_path, principal)
    prepared_path = root / "prepared"

    def progress(item: Mapping[str, Any]) -> None:
        index = int(item["cutoff_index"])
        count = int(item["cutoff_count"])
        if index == 1 or index == count or index % 5 == 0:
            print(json.dumps({"preparation_progress": item}, sort_keys=True), flush=True)

    preparation_manifest, preparation_metrics = prepare_historical_dataset(
        adapter, dataset_path, prepared_path, progress_callback=progress
    )
    output = {
        "evidence_type": "SYNTHETIC_DEMO_ONLY",
        "dataset_id": preparation_manifest["dataset_identity"]["dataset_id"],
        "dataset_manifest_sha256": preparation_manifest["dataset_identity"]["dataset_manifest_sha256"],
        "tenant_scope": TENANT_ID,
        "dataset_path": str(dataset_path),
        "database_path": str(database_path),
        "prepared_path": str(prepared_path),
        "generated_counts": generated["actual_counts"],
        "import_status": imported["status"],
        "preparation_metrics": preparation_metrics,
        "source_manifest_sha256": _sha256(dataset_path / "dataset_manifest.json"),
        "preparation_manifest_sha256": _sha256(prepared_path / "preparation_manifest.json"),
    }
    (root / "prompt34_run_config.json").write_text(
        json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def prepare_reduced_existing(root: Path = REDUCED_ROOT) -> dict[str, Any]:
    """Use fewer predeclared cutoffs from the existing cohort and SQLite import.

    This path never regenerates or reimports source rows. Cutoffs are selected
    evenly within frozen calendar stages before reading labels; the same
    per-horizon support gates remain mandatory downstream.
    """

    root = _safe_root(root)
    if root.exists():
        # The interrupted predeclared run may leave only its empty prepared
        # directory behind. Reuse that empty shell while refusing to overwrite
        # any source, manifest, or partial artifact.
        existing = {item.name for item in root.iterdir()}
        prepared_shell = root / "prepared"
        if (
            existing != {"prepared"}
            or not prepared_shell.is_dir()
            or any(prepared_shell.iterdir())
        ):
            raise FileExistsError("reduced Prompt 34 root contains artifacts; refusing to overwrite")
    source_root = _safe_root(DEFAULT_ROOT)
    dataset_parent = source_root / "source" / PROFILE
    candidates = sorted(
        item for item in dataset_parent.iterdir()
        if item.is_dir() and item.name.startswith(DATASET_ID_PREFIX)
    )
    if len(candidates) != 1:
        raise DemoError("expected exactly one existing Prompt 34 synthetic source dataset")
    dataset_path = candidates[0].resolve()
    database_path = (source_root / "prompt34-demo.sqlite3").resolve()
    if not database_path.is_file():
        raise DemoError("the existing authenticated SQLite import is missing")
    manifest = json.loads((dataset_path / "dataset_manifest.json").read_text(encoding="utf-8"))
    if (
        not str(manifest.get("dataset_id", "")).startswith(DATASET_ID_PREFIX)
        or manifest.get("random_seed") != SEED
        or manifest.get("profile") != PROFILE
        or manifest.get("no_real_customer_data") is not True
    ):
        raise DemoError("existing dataset identity or synthetic provenance does not match")
    split_spec = json.loads((dataset_path / "split_manifest.json").read_text(encoding="utf-8"))
    schedule = select_predeclared_cutoffs(
        build_cutoff_schedule(manifest, split_spec), REDUCED_CUTOFF_COUNTS
    )

    # The one-time service token exists only in memory and is never logged.
    provisioned = provision_member2_reader(dataset_path, database_path, TENANT_ID)
    token = provisioned.pop("token")
    principal = authenticate_service_principal(database_path, token)
    adapter = SQLiteDataAdapter(database_path, dataset_path, principal)
    reader_counter = _ReaderCallCounter(adapter.reader_api)
    adapter.reader_api = reader_counter
    prepared_path = root / "prepared"
    preparation_manifest, preparation_metrics = prepare_historical_dataset(
        adapter,
        dataset_path,
        prepared_path,
        reader_api_call_counts=reader_counter.counts,
        progress_callback=lambda item: print(
            json.dumps({"reduced_preparation_progress": item}, sort_keys=True), flush=True
        ),
        cutoff_schedule=schedule,
        cutoff_policy_version=REDUCED_CUTOFF_POLICY_VERSION,
    )
    output = {
        "evidence_type": "SYNTHETIC_DEMO_ONLY",
        "experiment_id": "prompt34-reduced-evenly-spaced-v1",
        "dataset_id": preparation_manifest["dataset_identity"]["dataset_id"],
        "dataset_manifest_sha256": preparation_manifest["dataset_identity"]["dataset_manifest_sha256"],
        "tenant_scope": TENANT_ID,
        "dataset_path": str(dataset_path),
        "database_path": str(database_path),
        "prepared_path": str(prepared_path),
        "cutoff_policy_version": REDUCED_CUTOFF_POLICY_VERSION,
        "selected_cutoff_counts": {key.value: value for key, value in REDUCED_CUTOFF_COUNTS.items()},
        "selected_cutoff_dates": [item.as_of.isoformat() for item in schedule],
        "preparation_metrics": preparation_metrics,
        "source_manifest_sha256": _sha256(dataset_path / "dataset_manifest.json"),
        "preparation_manifest_sha256": _sha256(prepared_path / "preparation_manifest.json"),
    }
    root.mkdir(parents=True, exist_ok=True)
    _save_json(root / "prompt34_run_config.json", output)
    return output


def _read_config(root: Path) -> dict[str, Any]:
    root = _safe_root(root)
    config_path = root / "prompt34_run_config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoError("private preparation configuration is missing or invalid") from exc
    if config.get("evidence_type") != "SYNTHETIC_DEMO_ONLY" or config.get("tenant_scope") != TENANT_ID:
        raise DemoError("dataset provenance or tenant scope mismatch")
    dataset_path = Path(config["dataset_path"]).resolve()
    prepared_path = Path(config["prepared_path"]).resolve()
    if _sha256(dataset_path / "dataset_manifest.json") != config.get("source_manifest_sha256"):
        raise DemoError("source dataset manifest hash mismatch")
    if _sha256(prepared_path / "preparation_manifest.json") != config.get("preparation_manifest_sha256"):
        raise DemoError("prepared-data manifest hash mismatch")
    return config


def _read_preparation_manifest(prepared_path: Path) -> dict[str, Any]:
    manifest = json.loads((prepared_path / "preparation_manifest.json").read_text(encoding="utf-8"))
    identity = manifest.get("dataset_identity", {})
    if (
        manifest.get("evidence_provenance") != "SYNTHETIC_ONLY"
        or identity.get("profile") != PROFILE
        or identity.get("seed") != SEED
        or identity.get("target_policy_version") != "effective-account-churn-v1.2"
        or manifest.get("tenant_scope", {}).get("tenant_id_from_authenticated_principal") != TENANT_ID
        or manifest.get("tenant_scope", {}).get("authorized_tenant_count") != 1
        or manifest.get("tenant_scope", {}).get("other_dataset_tenants_accessed") is not False
    ):
        raise DemoError("prepared data do not match the isolated Prompt 34 cohort")
    return manifest


def _feature_from_row(row: dict[str, Any]) -> FeatureSnapshot:
    if row.get("tenant_id") != TENANT_ID or row.get("prediction_eligibility") != "ELIGIBLE":
        raise DemoError("prepared feature row has an unexpected scope or eligibility")
    as_of = row.get("as_of")
    return FeatureSnapshot.model_validate(
        {
            "tenant_id": row["tenant_id"],
            "customer_id": row["customer_id"],
            "as_of": as_of,
            "data_cutoff_at": as_of,
            "feature_version": row["feature_version"],
            "feature_values": row["feature_values"],
            "data_quality": row["feature_quality"],
            "source_evidence_refs": row["feature_source_evidence_refs"],
        }
    )


def _label_from_row(row: dict[str, Any], *, stage: str) -> ChurnLabel:
    if row.get("tenant_id") != TENANT_ID:
        raise DemoError("prepared label crosses tenant scope")
    expected_marker = stage == "test"
    if row.get("test_labels_evaluation_only") is not expected_marker:
        raise DemoError("prepared label split marker is inconsistent")
    fields = ChurnLabel.model_fields
    return ChurnLabel.model_validate({key: value for key, value in row.items() if key in fields})


def _load_stage(
    prepared_path: Path,
    stage: str,
    *,
    include_labels: bool,
    test_predictions_persisted: bool = False,
) -> tuple[tuple[SnapshotRecord, ...], dict[str, dict[str, Any]]]:
    if stage not in {"train", "validation", "calibration", "test"}:
        raise ValueError("unsupported chronological stage")
    if stage == "test" and include_labels and not test_predictions_persisted:
        raise DemoError("TEST outcomes are locked until prediction evidence is persisted")
    manifest = _read_preparation_manifest(prepared_path)
    checksum_map = manifest.get("artifact_checksums", {})
    feature_path = prepared_path / f"{stage}_features.jsonl.gz"
    expected_feature = checksum_map.get(feature_path.name, {}).get("sha256")
    if not expected_feature or _sha256(feature_path) != expected_feature:
        raise DemoError(f"{stage} feature artifact checksum mismatch")
    feature_rows: dict[str, tuple[FeatureSnapshot, dict[str, Any]]] = {}
    for row in _jsonl_gzip(feature_path):
        if row.get("split") != stage.upper():
            raise DemoError(f"{stage} feature is outside its declared split")
        snapshot_id = row.get("snapshot_id")
        if not isinstance(snapshot_id, str) or snapshot_id in feature_rows:
            raise DemoError(f"{stage} feature identity is missing or duplicated")
        feature_rows[snapshot_id] = (_feature_from_row(row), row)
    labels_by_snapshot: dict[str, list[ChurnLabel]] = defaultdict(list)
    if include_labels:
        label_path = prepared_path / f"{stage}_labels.jsonl.gz"
        expected_label = checksum_map.get(label_path.name, {}).get("sha256")
        if not expected_label or _sha256(label_path) != expected_label:
            raise DemoError(f"{stage} label artifact checksum mismatch")
        for row in _jsonl_gzip(label_path):
            snapshot_id = row.get("snapshot_id")
            if snapshot_id not in feature_rows:
                raise DemoError(f"{stage} label does not match its feature snapshot")
            labels_by_snapshot[snapshot_id].append(_label_from_row(row, stage=stage))
    records: list[SnapshotRecord] = []
    for snapshot_id, (feature, _) in feature_rows.items():
        labels = tuple(sorted(labels_by_snapshot.get(snapshot_id, ()), key=lambda item: item.horizon_days))
        if include_labels and tuple(item.horizon_days for item in labels) != SUPPORTED_HORIZONS:
            raise DemoError(f"{stage} snapshot does not have all three horizon labels")
        records.append(
            SnapshotRecord(
                snapshot_id=snapshot_id,
                feature_snapshot=feature,
                labels=labels,
                prediction_eligible=True,
            )
        )
    if include_labels and set(labels_by_snapshot) != set(feature_rows):
        raise DemoError(f"{stage} feature and label populations differ")
    auxiliary_by_snapshot = {
        snapshot_id: {
            "reliability": raw.get("reliability", {}),
            "freshness": raw.get("freshness", {}),
            "feature_quality": raw.get("feature_quality", {}),
        }
        for snapshot_id, (_, raw) in feature_rows.items()
    }
    return tuple(records), auxiliary_by_snapshot


def _build_split(records: Iterable[SnapshotRecord], manifest: Mapping[str, Any]) -> TemporalSplitResult:
    split_data = manifest["temporal_split_manifest"]
    boundaries = TemporalSplitBoundaries.model_validate(split_data["boundaries"])
    config = TemporalSplitConfig(
        boundaries=boundaries,
        split_policy_version=split_data["split_policy_version"],
        dataset_identifier=manifest["dataset_identity"]["dataset_id"],
        authorized_dataset=False,
        maturity_gap=timedelta(seconds=int(split_data["configuration"]["maturity_gap_seconds"])),
        minimum_samples_per_horizon=2,
    )
    return TemporalSplitter(config).split(records)


def _support(partition, horizon: int) -> dict[str, Any]:
    ids = set(partition.supervised_snapshot_ids_by_horizon.get(horizon, ()))
    selected = [record for record in partition.snapshots if record.stable_snapshot_id in ids]
    labels = {
        record.stable_snapshot_id: next(item for item in record.labels if item.horizon_days == horizon)
        for record in selected
    }
    positives = [record for record in selected if labels[record.stable_snapshot_id].label == 1]
    negatives = [record for record in selected if labels[record.stable_snapshot_id].label == 0]
    return {
        "usable_rows": len(selected),
        "positive_rows": len(positives),
        "negative_rows": len(negatives),
        "unique_positive_accounts": len({record.account_key for record in positives}),
        "unique_negative_accounts": len({record.account_key for record in negatives}),
        "unknown_rows": sum(
            next(item for item in record.labels if item.horizon_days == horizon).label is None
            for record in partition.snapshots
        ),
    }


def _support_passes(value: Mapping[str, Any]) -> bool:
    return (
        value["positive_rows"] >= CLASS_SUPPORT["minimum_positive_samples"]
        and value["negative_rows"] >= CLASS_SUPPORT["minimum_negative_samples"]
        and value["unique_positive_accounts"] >= CLASS_SUPPORT["minimum_unique_positive_accounts"]
        and value["unique_negative_accounts"] >= CLASS_SUPPORT["minimum_unique_negative_accounts"]
    )


def _predict_probability(model: Any, snapshot: FeatureSnapshot, horizon: int) -> float:
    result = model.predict(snapshot, horizon_days=horizon)
    if result.status is not BaselineStatus.READY or result.score is None:
        raise DemoError("a fitted model did not produce an inference score")
    score = float(result.score)
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise DemoError("model output is outside the probability range")
    return score


def _raw_prediction(score: float, horizon: int, feature_version: str):
    from retainiq_prediction.baselines import BaselinePrediction, BaselineScoreKind

    return BaselinePrediction(
        horizon_days=horizon,
        status=BaselineStatus.READY,
        score=score,
        score_kind=BaselineScoreKind.UNCALIBRATED_PROBABILITY,
        baseline_version=MODEL_VERSION,
        feature_version=feature_version,
        model_version=MODEL_VERSION,
    )


def _member1_safe_prediction_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Conform to Member 1's current safe-tree storage limitation.

    Full reasons and explanations are preserved in the immutable private
    PredictionOutput artifact; this DB projection intentionally omits them.
    """

    return {
        **payload,
        "reliability_reasons": [],
        "explanations_by_horizon": {},
    }


def _metrics(y: list[int], ranking: list[float], *, probability: list[float] | None, k: int) -> dict[str, Any]:
    if not y:
        return {"sample_count": 0, "positive_count": 0, "negative_count": 0, "pr_auc": None, "roc_auc": None, "brier": None, "recall_at_k": None, "false_alerts_at_k": None}
    positives = sum(y)
    order = sorted(range(len(y)), key=lambda index: (-ranking[index], index))
    top = order[: min(k, len(order))]
    top_positive = sum(y[index] for index in top)
    both_classes = positives > 0 and positives < len(y)
    brier_value = None
    if probability is not None:
        brier_value = float(np.mean((np.asarray(probability) - np.asarray(y)) ** 2))
    return {
        "sample_count": len(y),
        "positive_count": positives,
        "negative_count": len(y) - positives,
        "positive_prevalence": positives / len(y),
        "pr_auc": float(average_precision_score(y, ranking)) if both_classes else None,
        "roc_auc": float(roc_auc_score(y, ranking)) if both_classes else None,
        "brier": brier_value,
        "brier_semantics": "mean_squared_probability_error" if probability is not None else "not_applicable_to_ranking_score",
        "recall_at_k": top_positive / positives if positives else None,
        "precision_at_k": top_positive / len(top) if top else None,
        "false_alerts_at_k": len(top) - top_positive,
        "review_capacity_k": k,
    }


def _select_development_candidate(comparison: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    candidates = (
        "lightgbm_uncalibrated_score",
        "logistic_uncalibrated_score",
        "lightgbm_without_personalized_baseline",
    )
    aggregate: dict[str, dict[str, float]] = {}
    for candidate in candidates:
        pr_values: list[float] = []
        brier_values: list[float] = []
        for horizon in ("7", "14", "30"):
            metrics = comparison[horizon].get(candidate, {})
            if metrics.get("pr_auc") is not None:
                pr_values.append(float(metrics["pr_auc"]))
            if metrics.get("brier") is not None:
                brier_values.append(float(metrics["brier"]))
        if len(pr_values) == 3 and len(brier_values) == 3:
            aggregate[candidate] = {
                "mean_pr_auc": float(np.mean(pr_values)),
                "mean_brier": float(np.mean(brier_values)),
            }
    if not aggregate:
        raise DemoError("development comparison lacks complete metrics for candidate selection")
    selected = min(
        aggregate,
        key=lambda name: (-aggregate[name]["mean_pr_auc"], aggregate[name]["mean_brier"], name),
    )
    return {
        "selected_candidate": selected,
        "development_metrics": aggregate,
        "selection_scope": "VALIDATION only; raw scores only; TEST outcomes were not read",
        "rule": "highest mean per-horizon PR-AUC; ties resolved by lower uncalibrated-score Brier then lexical candidate name",
        "promotion": "diagnostic ranking only; no model is promoted by this synthetic experiment",
    }


def _coherence_validation_diagnostics(
    validation_partition,
    *,
    models: Mapping[int, LightGBMModel],
    usable_ids: Mapping[int, set[str]],
) -> dict[str, Any]:
    common_ids = set.intersection(*(usable_ids[h] for h in SUPPORTED_HORIZONS))
    after_by_horizon: dict[int, list[float]] = {h: [] for h in SUPPORTED_HORIZONS}
    labels_by_horizon: dict[int, list[int]] = {h: [] for h in SUPPORTED_HORIZONS}
    violations_before = 0
    violations_after = 0
    for record in validation_partition.snapshots:
        if record.stable_snapshot_id not in common_ids:
            continue
        labels = {item.horizon_days: int(item.label) for item in record.labels}
        raw_scores = {
            horizon: _predict_probability(models[horizon], record.feature_snapshot, horizon)
            for horizon in SUPPORTED_HORIZONS
        }
        original = HorizonProbabilities(
            p7=raw_scores[7], p14=raw_scores[14], p30=raw_scores[30]
        )
        corrected = enforce_horizon_coherence(original)
        violations_before += int(not original.is_monotonic)
        violations_after += int(not corrected.adjusted.is_monotonic)
        for horizon, score in (
            (7, corrected.adjusted.p7),
            (14, corrected.adjusted.p14),
            (30, corrected.adjusted.p30),
        ):
            after_by_horizon[horizon].append(score)
            labels_by_horizon[horizon].append(labels[horizon])

    by_horizon: dict[str, Any] = {}
    for horizon in SUPPORTED_HORIZONS:
        y = labels_by_horizon[horizon]
        scores = after_by_horizon[horizon]
        both_classes = bool(y) and 0 < sum(y) < len(y)
        by_horizon[str(horizon)] = {
            "common_three_horizon_validation_count": len(y),
            "positive_count": sum(y),
            "negative_count": len(y) - sum(y),
            "brier_after_raw_score_monotonic_correction": float(np.mean((np.asarray(scores) - np.asarray(y)) ** 2)) if y else None,
            "pr_auc_after_raw_score_monotonic_correction": float(average_precision_score(y, scores)) if both_classes else None,
            "roc_auc_after_raw_score_monotonic_correction": float(roc_auc_score(y, scores)) if both_classes else None,
            "raw_score_bins_after_monotonic_correction": _reliability_bins(scores, y),
        }
    return {
        "common_three_horizon_validation_rows": len(labels_by_horizon[7]),
        "monotonicity_violations_before_correction": violations_before,
        "monotonicity_violations_after_correction": violations_after,
        "correction_policy": "existing cumulative_max_v1",
        "evidence_scope": "VALIDATION raw-model diagnostics; later CALIBRATION parameters and all TEST outcomes excluded",
        "per_horizon": by_horizon,
    }


def _reliability_bins(
    probabilities: list[float], labels: list[int], bins: int = 10
) -> list[dict[str, Any]]:
    result = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [
            (probability, label)
            for probability, label in zip(probabilities, labels)
            if lower <= probability < upper or (index == bins - 1 and probability == upper)
        ]
        result.append({
            "lower_bound": lower,
            "upper_bound": upper,
            "sample_count": len(selected),
            "mean_predicted_probability": float(np.mean([item[0] for item in selected])) if selected else None,
            "observed_positive_rate": float(np.mean([item[1] for item in selected])) if selected else None,
        })
    return result


def _save_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def train_and_evaluate(root: Path) -> dict[str, Any]:
    """Fit/reload models and calibrators, then persist test scores before labels."""

    if not LIGHTGBM_AVAILABLE:
        raise DemoError("LightGBM is not available in the repository environment")
    root = _safe_root(root)
    run_config = _read_config(root)
    prepared_path = Path(run_config["prepared_path"])
    preparation = _read_preparation_manifest(prepared_path)
    output_dir = root / "model_bundle"
    if output_dir.exists():
        raise FileExistsError("model bundle already exists; refusing to retrain or inspect TEST again")

    dev_records = tuple(
        record
        for stage in ("train", "validation", "calibration")
        for record in _load_stage(prepared_path, stage, include_labels=True)[0]
    )
    split = _build_split(dev_records, preparation)
    partitions = {
        stage: split.partition(stage)
        for stage in (SplitName.TRAIN, SplitName.VALIDATION, SplitName.CALIBRATION)
    }
    support = {
        stage.value: {h: _support(partitions[stage], h) for h in SUPPORTED_HORIZONS}
        for stage in partitions
    }
    failures = [
        f"{stage}:{h}"
        for stage in ("TRAIN", "VALIDATION", "CALIBRATION")
        for h in SUPPORTED_HORIZONS
        if not _support_passes(support[stage][h])
    ]
    if failures:
        raise DemoError("frozen 50/50-row and 20/20-account support gate failed: " + ",".join(failures))

    dataset_id = preparation["dataset_identity"]["dataset_id"]
    feature_versions = {r.feature_snapshot.feature_version for r in dev_records}
    label_versions = {label.label_policy_version for r in dev_records for label in r.labels}
    if len(feature_versions) != 1 or label_versions != {"effective-account-churn-v1.2"}:
        raise DemoError("feature or label policy versions are inconsistent")
    feature_version = next(iter(feature_versions))
    boundaries = split.manifest.boundaries
    readiness = DatasetReadinessReport(
        status=DatasetStatus.BLOCKED,
        eligible_for_genuine_training=False,
        supported_horizons=list(SUPPORTED_HORIZONS),
        dataset_source=DatasetProvenance(
            source_name=dataset_id,
            evidence_type=ProvenanceEvidenceType.SYNTHETIC,
            availability_assumption="generator-simulated source availability; synthetic only",
        ),
        blockers=["Synthetic demo provenance cannot satisfy real-data or production readiness."],
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    model_dir = output_dir / "models"
    calibration_dir = output_dir / "calibrators"
    baseline_dir = output_dir / "baselines"
    for path in (model_dir, calibration_dir, baseline_dir):
        path.mkdir()

    lightgbm_config = LightGBMConfig(
        model_version=MODEL_VERSION,
        feature_version=feature_version,
        label_policy_version="effective-account-churn-v1.2",
        dataset_provenance=f"SYNTHETIC_DEMO_ONLY:{dataset_id}:{TENANT_ID}",
        tenant_id=TENANT_ID,
        random_seed=SEED,
        n_estimators=50,
        learning_rate=0.05,
        num_leaves=7,
        max_depth=3,
        min_child_samples=10,
        class_weight="balanced",
        use_validation_early_stopping=False,
    )
    calibration_config = CalibrationConfig(
        calibration_version=CALIBRATION_VERSION,
        minimum_samples=CLASS_SUPPORT["minimum_positive_samples"] + CLASS_SUPPORT["minimum_negative_samples"],
        minimum_positive=CLASS_SUPPORT["minimum_positive_samples"],
        minimum_negative=CLASS_SUPPORT["minimum_negative_samples"],
        random_seed=SEED,
    )
    models: dict[int, LightGBMModel] = {}
    calibrators: dict[int, ProbabilityCalibrator] = {}
    model_artifacts: dict[str, Any] = {}
    calibration_artifacts: dict[str, Any] = {}
    train_partition = split.partition(SplitName.TRAIN)
    validation = split.partition(SplitName.VALIDATION)
    calibration = split.partition(SplitName.CALIBRATION)
    train_ids = {h: set(train_partition.supervised_snapshot_ids_by_horizon[h]) for h in SUPPORTED_HORIZONS}
    val_ids = {h: set(validation.supervised_snapshot_ids_by_horizon[h]) for h in SUPPORTED_HORIZONS}
    calibration_ids = {h: set(calibration.supervised_snapshot_ids_by_horizon[h]) for h in SUPPORTED_HORIZONS}
    calibration_diag: dict[str, Any] = {}
    validation_predictions: dict[int, dict[str, list[Any]]] = {h: defaultdict(list) for h in SUPPORTED_HORIZONS}
    validation_labels: dict[int, list[int]] = {h: [] for h in SUPPORTED_HORIZONS}
    training_prevalence: dict[int, float] = {}
    for horizon in SUPPORTED_HORIZONS:
        labels = [
            int(next(item.label for item in record.labels if item.horizon_days == horizon))
            for record in train_partition.snapshots
            if record.stable_snapshot_id in train_ids[horizon]
        ]
        training_prevalence[horizon] = float(np.mean(labels))
    start_training = time.perf_counter()

    for horizon in SUPPORTED_HORIZONS:
        model = LightGBMModel(lightgbm_config)
        fit = model.fit(split, horizon_days=horizon)
        if fit.status is not BaselineStatus.READY or fit.metadata is None:
            raise DemoError(f"LightGBM {horizon}d fit did not reach READY")
        model_path = model_dir / f"horizon-{horizon}d.pkl"
        model.save(model_path)
        loaded_model = LightGBMModel.load(model_path, trusted_root=output_dir)
        if loaded_model.fit_result is None or loaded_model.fit_result.status is not BaselineStatus.READY:
            raise DemoError(f"saved LightGBM {horizon}d artifact failed reload")

        calibrator = ProbabilityCalibrator(calibration_config)
        calibration_fit = calibrator.fit(loaded_model, split, horizon_days=horizon)
        if calibration_fit.status is not BaselineStatus.READY or calibration_fit.metadata is None:
            raise DemoError(f"sigmoid calibrator {horizon}d did not reach READY")
        calibration_path = calibration_dir / f"sigmoid-{horizon}d.pkl"
        calibrator.save(calibration_path)
        loaded_calibrator = ProbabilityCalibrator.load(calibration_path, trusted_root=output_dir)
        models[horizon] = loaded_model
        calibrators[horizon] = loaded_calibrator

        y_cal: list[int] = []
        raw_cal: list[float] = []
        calibrated_cal: list[float] = []
        for record in calibration.snapshots:
            if record.stable_snapshot_id not in calibration_ids[horizon]:
                continue
            label = next(item for item in record.labels if item.horizon_days == horizon)
            raw = _predict_probability(loaded_model, record.feature_snapshot, horizon)
            from retainiq_prediction.baselines import BaselinePrediction, BaselineScoreKind

            raw_item = BaselinePrediction(
                horizon_days=horizon,
                status=BaselineStatus.READY,
                score=raw,
                score_kind=BaselineScoreKind.UNCALIBRATED_PROBABILITY,
                baseline_version=MODEL_VERSION,
                feature_version=feature_version,
                model_version=MODEL_VERSION,
            )
            cal_item = loaded_calibrator.calibrate_prediction(raw_item, loaded_model.metadata)
            y_cal.append(int(label.label))
            raw_cal.append(raw)
            calibrated_cal.append(cal_item.calibrated_probability)

        calibration_diag[str(horizon)] = {
            "method": loaded_calibrator.metadata.calibration_method.value,
            "cohort_count": len(y_cal),
            "positive_count": sum(y_cal),
            "negative_count": len(y_cal) - sum(y_cal),
            "brier_before_calibration_fit_cohort": float(np.mean((np.asarray(raw_cal) - y_cal) ** 2)),
            "brier_after_calibration_fit_cohort": float(np.mean((np.asarray(calibrated_cal) - y_cal) ** 2)),
            "fit_cohort_metrics_are_in_sample": True,
            "brier_warning": "post-fit Brier on the calibrator fitting partition is optimistic and is diagnostic only",
            "reloaded_model_inference_count": len(y_cal),
        }
        model_artifacts[str(horizon)] = {
            "status": "TRAINED_AND_RELOADED",
            "artifact_path": str(model_path),
            "sha256": _sha256(model_path),
            "train_row_count": fit.training_snapshot_count,
            "train_positive_count": fit.positive_count,
            "train_negative_count": fit.negative_count,
            "feature_count": len(fit.metadata.feature_names),
            "feature_names": list(fit.metadata.feature_names),
            "model_version": fit.metadata.model_version,
            "feature_version": fit.metadata.feature_version,
            "training_cutoff": fit.metadata.training_cutoff.isoformat(),
            "validation_row_count": len(val_ids[horizon]),
            "reloaded_inference_smoke_count": len(y_cal),
        }
        calibration_artifacts[str(horizon)] = {
            "status": "FITTED_AND_RELOADED",
            "artifact_path": str(calibration_path),
            "sha256": _sha256(calibration_path),
            "metadata": loaded_calibrator.metadata.model_dump(mode="json"),
        }

    # Independent logistic baselines and the no-personalization ablation.
    logistic_models: dict[int, LogisticRegressionBaseline] = {}
    ablation_models: dict[int, LightGBMModel] = {}
    logistic_artifacts: dict[str, Any] = {}
    ablation_artifacts: dict[str, Any] = {}
    for horizon in SUPPORTED_HORIZONS:
        logistic = LogisticRegressionBaseline(
            LogisticBaselineConfig(
                baseline_version=f"prompt34-logistic-{horizon}d-v1",
                feature_version=feature_version,
                random_state=SEED,
                class_weight="balanced",
            )
        )
        logistic_fit = logistic.fit(split, horizon_days=horizon)
        if logistic_fit.status is not BaselineStatus.READY:
            raise DemoError(f"logistic baseline {horizon}d did not reach READY")
        logistic_path = baseline_dir / f"logistic-{horizon}d.pkl"
        logistic.save(logistic_path)
        logistic_models[horizon] = LogisticRegressionBaseline.load(logistic_path, trusted_root=output_dir)
        logistic_artifacts[str(horizon)] = {"path": str(logistic_path), "sha256": _sha256(logistic_path)}

        ablation_config = LightGBMConfig(
            model_version=f"prompt34-no-personalization-{horizon}d-v1",
            feature_version=feature_version,
            label_policy_version="effective-account-churn-v1.2",
            dataset_provenance=f"SYNTHETIC_DEMO_ONLY:{dataset_id}:{TENANT_ID}",
            tenant_id=TENANT_ID,
            random_seed=SEED,
            n_estimators=50,
            learning_rate=0.05,
            num_leaves=7,
            max_depth=3,
            min_child_samples=10,
            class_weight="balanced",
            allowlist=NON_PERSONALIZED_ALLOWLIST,
        )
        ablation = LightGBMModel(ablation_config)
        ablation_fit = ablation.fit(split, horizon_days=horizon)
        if ablation_fit.status is not BaselineStatus.READY:
            raise DemoError(f"no-personalization ablation {horizon}d did not reach READY")
        ablation_path = baseline_dir / f"lightgbm-no-personalization-{horizon}d.pkl"
        ablation.save(ablation_path)
        ablation_models[horizon] = LightGBMModel.load(ablation_path, trusted_root=output_dir)
        ablation_artifacts[str(horizon)] = {
            "path": str(ablation_path),
            "sha256": _sha256(ablation_path),
            "feature_count": len(ablation_fit.metadata.feature_names),
            "features_removed": sorted(PERSONALIZED_FEATURES),
        }

    # Development-only comparisons share the exact mature validation rows.
    validation_comparison: dict[str, Any] = {}
    rule_base = RuleBasedBaseline(RuleBaselineConfig())
    rule_scores_by_horizon: dict[int, list[tuple[SnapshotRecord, float]]] = {h: [] for h in SUPPORTED_HORIZONS}
    for horizon in SUPPORTED_HORIZONS:
        for record in validation.snapshots:
            if record.stable_snapshot_id not in val_ids[horizon]:
                continue
            label = next(item for item in record.labels if item.horizon_days == horizon)
            validation_labels[horizon].append(int(label.label))
            # Calibration is fitted on the later CALIBRATION partition. Keep
            # its future parameters out of earlier VALIDATION diagnostics.
            validation_predictions[horizon]["lightgbm"].append(
                _predict_probability(models[horizon], record.feature_snapshot, horizon)
            )
            validation_predictions[horizon]["logistic"].append(
                _predict_probability(logistic_models[horizon], record.feature_snapshot, horizon)
            )
            validation_predictions[horizon]["ablation"].append(
                _predict_probability(ablation_models[horizon], record.feature_snapshot, horizon)
            )
            rule_base.fit(horizon_days=horizon)
            rule_result = rule_base.predict(record.feature_snapshot, horizon_days=horizon)
            if rule_result.status is BaselineStatus.READY and rule_result.score is not None:
                rule_scores_by_horizon[horizon].append((record, float(rule_result.score)))
        y = validation_labels[horizon]
        validation_predictions[horizon]["constant"] = [training_prevalence[horizon]] * len(y)
        scores_for_rule = rule_scores_by_horizon[horizon]
        matched_rule_y = [int(next(label.label for label in record.labels if label.horizon_days == horizon)) for record, _ in scores_for_rule]
        matched_rule_scores = [score for _, score in scores_for_rule]
        thresholds = sorted(set(matched_rule_scores))
        best_rule = (float("-inf"), float("inf"), 50.0)
        for threshold in thresholds:
            predicted = [score >= threshold for score in matched_rule_scores]
            tp = sum(int(pred and actual) for pred, actual in zip(predicted, matched_rule_y))
            fp = sum(int(pred and not actual) for pred, actual in zip(predicted, matched_rule_y))
            fn = sum(int(not pred and actual) for pred, actual in zip(predicted, matched_rule_y))
            f1 = (2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) else 0.0
            candidate = (f1, -fp, threshold)
            if candidate > best_rule:
                best_rule = candidate

        y_rule = matched_rule_y
        prob_rule = [float(score >= best_rule[2]) for score in matched_rule_scores]
        rule_metrics = _metrics(
            y_rule,
            matched_rule_scores,
            probability=prob_rule,
            k=REVIEW_CAPACITY_K,
        )
        values: dict[str, Any] = {
            "lightgbm_uncalibrated_score": _metrics(
                y, validation_predictions[horizon]["lightgbm"],
                probability=validation_predictions[horizon]["lightgbm"], k=REVIEW_CAPACITY_K,
            ),
            "logistic_uncalibrated_score": _metrics(
                y, validation_predictions[horizon]["logistic"],
                probability=validation_predictions[horizon]["logistic"], k=REVIEW_CAPACITY_K,
            ),
            "constant_prevalence": _metrics(
                y, validation_predictions[horizon]["constant"],
                probability=validation_predictions[horizon]["constant"], k=REVIEW_CAPACITY_K,
            ),
            "rule_based": {
                **rule_metrics,
                "threshold_selected_on_validation": best_rule[2],
                "threshold_selection": "maximum_validation_F1_then_fewer_false_alerts",
                "metric_population_count": len(y_rule),
                "population_note": "Rule baseline is compared on its supported subset; ranking score is not a churn probability.",
            },
            "lightgbm_without_personalized_baseline": _metrics(
                y, validation_predictions[horizon]["ablation"],
                probability=validation_predictions[horizon]["ablation"], k=REVIEW_CAPACITY_K,
            ),
            "same_mature_validation_population_for_probability_models": True,
            "constant_prevalence_source": "TRAIN only",
        }
        validation_comparison[str(horizon)] = values

    validation_coherence = _coherence_validation_diagnostics(
        validation,
        models=models,
        usable_ids=val_ids,
    )

    # Select a raw p30 threshold on VALIDATION, then map that cut through the
    # later CALIBRATION-fitted monotonic sigmoid for downstream calibrated p30.
    alert_threshold, threshold_evidence = _select_alert_threshold(
        validation, models, calibrators, val_ids[30],
    )
    calibrator30 = calibrators[30]
    from retainiq_prediction.baselines import BaselinePrediction, BaselineScoreKind

    raw_threshold = BaselinePrediction(
        horizon_days=30,
        status=BaselineStatus.READY,
        score=alert_threshold,
        score_kind=BaselineScoreKind.UNCALIBRATED_PROBABILITY,
        baseline_version=MODEL_VERSION,
        feature_version=feature_version,
        model_version=MODEL_VERSION,
    )
    selected_alert_threshold = calibrator30.calibrate_prediction(raw_threshold, models[30].metadata).calibrated_probability

    trained_seconds = time.perf_counter() - start_training
    candidate_selection = _select_development_candidate(validation_comparison)
    bundle_manifest: dict[str, Any] = {
        "status": "SYNTHETIC_DEMO_ONLY_TRAINED_CALIBRATED",
        "evidence_type": "SYNTHETIC_DEMO_ONLY",
        "dataset_id": dataset_id,
        "source_manifest_sha256": run_config["source_manifest_sha256"],
        "preparation_manifest_sha256": run_config["preparation_manifest_sha256"],
        "tenant_scope": TENANT_ID,
        "generator_version": preparation["dataset_identity"]["generator_version"],
        "generator_seed": SEED,
        "label_policy_version": "effective-account-churn-v1.2",
        "feature_version": feature_version,
        "split_policy_version": split.manifest.split_policy_version,
        "split_boundaries": boundaries.model_dump(mode="json"),
        "class_support_policy": CLASS_SUPPORT,
        "stage_support": support,
        "train_validation_unique_account_overlap": split.manifest.account_overlap_summary,
        "model_version": MODEL_VERSION,
        "calibration_version": CALIBRATION_VERSION,
        "training_configuration": {
            "class_weight": "balanced",
            "n_estimators": 50,
            "learning_rate": 0.05,
            "num_leaves": 7,
            "max_depth": 3,
            "min_child_samples": 10,
            "random_seed": SEED,
            "early_stopping": False,
            "preprocessing_fit_partition": "TRAIN only; LightGBM numeric inputs use the existing vectorizer",
        },
        "training_command": f"python -B -m examples.member2_prompt34_demo train --root {root}",
        "lightgbm_version": LIGHTGBM_VERSION,
        "software_versions": {
            "python": sys.version.split()[0],
            "lightgbm": LIGHTGBM_VERSION,
            "scikit_learn": importlib.metadata.version("scikit-learn"),
            "shap": importlib.metadata.version("shap"),
            "numpy": importlib.metadata.version("numpy"),
            "pydantic": importlib.metadata.version("pydantic"),
        },
        "model_artifacts": model_artifacts,
        "calibration_artifacts": calibration_artifacts,
        "calibration_fit_cohort_diagnostics": calibration_diag,
        "logistic_artifacts": logistic_artifacts,
        "personalization_ablation_artifacts": ablation_artifacts,
        "validation_comparison": validation_comparison,
        "validation_monotonicity_and_post_correction_metrics": validation_coherence,
        "demonstration_candidate_rule": "mean horizon PR-AUC on the mature VALIDATION cohort; ties resolved by lower Brier; constant prevalence is reference only",
        "demonstration_candidate_selection": candidate_selection,
        "selected_alert_threshold_calibrated_p30": selected_alert_threshold,
        "selected_alert_threshold_development_evidence": threshold_evidence,
        "alert_policy": {
            "policy_version": ALERT_POLICY_VERSION,
            "probability_threshold": selected_alert_threshold,
            "review_capacity_k": REVIEW_CAPACITY_K,
            "period_days": 7,
            "cooldown_days": 7,
            "require_rising_risk": True,
            "minimum_reliability": "sufficient_evidence",
            "allowed_freshness": ["fresh", "partially_stale"],
        },
        "pre_test_status": "FROZEN_BEFORE_TEST_OUTCOME_ACCESS",
        "test_outcomes_read": False,
        "training_elapsed_seconds": trained_seconds,
        "production_readiness": "BLOCKED_SYNTHETIC_ONLY",
    }
    # All fitted models/calibrators and selection policy are frozen before the
    # held-out TEST feature predictions are generated.
    _save_json(output_dir / "bundle_manifest_pre_test.json", bundle_manifest)

    # Test feature rows are permitted now; TEST label files are not opened.
    test_records, test_auxiliary = _load_stage(prepared_path, "test", include_labels=False)
    test_predictions, test_inference_seconds = _score_test_features(
        test_records,
        models=models,
        calibrators=calibrators,
        logistic_models=logistic_models,
        ablation_models=ablation_models,
        training_records=dev_records,
        output_dir=output_dir,
        model_version=MODEL_VERSION,
        calibration_version=CALIBRATION_VERSION,
        feature_version=feature_version,
        preparation_manifest=preparation,
        auxiliary_by_snapshot=test_auxiliary,
    )
    prediction_file = output_dir / "heldout_test_predictions.jsonl.gz"
    prediction_rows = test_predictions["serialized_rows"]
    written = _write_jsonl_gzip(prediction_file, prediction_rows)
    bundle_manifest["heldout_test_predictions"] = {
        "path": str(prediction_file),
        "sha256": _sha256(prediction_file),
        "row_count": written,
        "snapshot_count": len(test_records),
        "inference_seconds": test_inference_seconds,
        "test_feature_input_is_model_selection_free": True,
        "prediction_artifact_persisted_before_test_labels_opened": True,
    }
    _save_json(output_dir / "bundle_manifest_pre_test.json", bundle_manifest)

    # This is the first point at which the TEST label artifact is opened.
    test_records_labeled = _load_stage(
        prepared_path, "test", include_labels=True, test_predictions_persisted=True
    )
    complete_records = (*dev_records, *test_records_labeled)
    full_split = _build_split(complete_records, preparation)
    test_predictions_eval = test_predictions["evaluation_predictions"]
    test_labels = [label for record in test_records_labeled for label in record.labels]
    # Test outcomes are revealed only after the independent prediction artifact
    # is persisted. The evaluation cutoff is the actual post-run observation
    # time, not the final TEST feature cutoff.
    evaluation_cutoff = datetime.now(UTC)
    evaluation = HistoricalEvaluator().evaluate(
        test_predictions_eval,
        test_labels,
        full_split,
        config=HistoricalEvaluationConfig(
            evaluation_cutoff=evaluation_cutoff,
            partition=SplitName.TEST,
            cohort="prompt34_synthetic_test",
            dataset_provenance_status=DatasetProvenanceStatus.SYNTHETIC,
            review_capacity_k=REVIEW_CAPACITY_K,
            expected_model_version=None,
            expected_feature_version=feature_version,
            expected_label_policy_version="effective-account-churn-v1.2",
            split_policy_version=full_split.manifest.split_policy_version,
            test_selection_frozen=True,
            alert_policy_version=ALERT_POLICY_VERSION,
        ),
    )
    test_manifest = {
        **bundle_manifest,
        "test_outcomes_read": True,
        "test_evaluation": evaluation.model_dump(mode="json"),
        "test_prediction_artifact_sha256": _sha256(prediction_file),
        "test_evaluation_run_count": 1,
        "test_metrics_used_for_selection_or_tuning": False,
        "test_support_by_horizon": {
            str(h): _test_support(test_records_labeled, h) for h in SUPPORTED_HORIZONS
        },
        "test_reliability_cohorts": _test_reliability_cohorts(
            test_predictions["serialized_rows"],
            test_records_labeled,
            test_auxiliary,
            evaluation_cutoff=evaluation_cutoff,
        ),
        "test_inference_elapsed_seconds": test_inference_seconds,
        "test_inference_predictions_per_second": (
            len(test_records) / test_inference_seconds if test_inference_seconds else None
        ),
        "test_status": "SYNTHETIC_ONLY_EVALUATED_ONCE",
    }
    _save_json(output_dir / "bundle_manifest.json", test_manifest)
    manifest_hash = _sha256(output_dir / "bundle_manifest.json")
    (output_dir / "bundle_manifest.sha256").write_text(
        f"{manifest_hash}  bundle_manifest.json\n", encoding="ascii", newline="\n"
    )
    return {
        "status": test_manifest["status"],
        "dataset_id": dataset_id,
        "bundle_manifest": str(output_dir / "bundle_manifest.json"),
        "bundle_manifest_sha256": manifest_hash,
        "model_artifacts": {
            h: {"path": model_artifacts[str(h)]["artifact_path"], "sha256": model_artifacts[str(h)]["sha256"], "training_rows": model_artifacts[str(h)]["train_row_count"], "validation_rows": model_artifacts[str(h)]["validation_row_count"]}
            for h in SUPPORTED_HORIZONS
        },
        "calibration": calibration_diag,
        "heldout_test_snapshot_count": len(test_records),
        "heldout_prediction_row_count": written,
        "predictions_by_model": test_predictions["prediction_counts"],
        "test_evaluation_status": evaluation.evaluation_status.value,
        "production_readiness": "BLOCKED_SYNTHETIC_ONLY",
    }


def run_replay(root: Path) -> dict[str, Any]:
    """Run two historical cutoffs through the existing pipeline and DB writer."""

    root = _safe_root(root)
    run_config = _read_config(root)
    prepared_path = Path(run_config["prepared_path"])
    preparation = _read_preparation_manifest(prepared_path)
    bundle_dir = root / "model_bundle"
    try:
        bundle = json.loads((bundle_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoError("frozen model bundle manifest is missing or invalid") from exc
    if bundle.get("status") != "SYNTHETIC_DEMO_ONLY_TRAINED_CALIBRATED":
        raise DemoError("frozen synthetic model bundle is not complete")
    models: dict[int, LightGBMModel] = {}
    calibrators: dict[int, ProbabilityCalibrator] = {}
    for horizon in SUPPORTED_HORIZONS:
        model_info = bundle["model_artifacts"][str(horizon)]
        calibration_info = bundle["calibration_artifacts"][str(horizon)]
        model_path = Path(model_info["artifact_path"]).resolve()
        calibration_path = Path(calibration_info["artifact_path"]).resolve()
        if _sha256(model_path) != model_info["sha256"] or _sha256(calibration_path) != calibration_info["sha256"]:
            raise DemoError(f"frozen horizon {horizon} artifact checksum mismatch")
        models[horizon] = LightGBMModel.load(model_path, trusted_root=bundle_dir)
        calibrators[horizon] = ProbabilityCalibrator.load(calibration_path, trusted_root=bundle_dir)
    if any(
        model.metadata is None or model.metadata.model_version != MODEL_VERSION
        or model.metadata.prediction_horizon_days != horizon
        for horizon, model in models.items()
    ):
        raise DemoError("reloaded model bundle metadata is inconsistent")

    # Select the first chronological validation pair using feature-only
    # metadata. A full schedule gives a seven-day gap; the reduced schedule
    # records the actual wider gap. Labels remain unopened until both writes.
    validation_records, validation_aux = _load_stage(
        prepared_path, "validation", include_labels=False
    )
    by_customer: dict[str, list[SnapshotRecord]] = defaultdict(list)
    for record in validation_records:
        auxiliary = validation_aux[record.stable_snapshot_id]
        reliability_status = auxiliary["reliability"].get("status")
        freshness_status = auxiliary["freshness"].get("status")
        if reliability_status in {"sufficient_evidence", "limited_evidence"} and freshness_status in {
            "fresh", "partially_stale"
        }:
            by_customer[record.feature_snapshot.customer_id].append(record)
    selected: tuple[str, datetime, datetime] | None = None
    for customer_id in sorted(by_customer):
        rows = sorted(by_customer[customer_id], key=lambda row: row.feature_snapshot.as_of)
        for left, right in zip(rows, rows[1:]):
            delta = right.feature_snapshot.as_of - left.feature_snapshot.as_of
            if delta > timedelta(0):
                selected = (customer_id, left.feature_snapshot.as_of, right.feature_snapshot.as_of)
                break
        if selected is not None:
            break
    if selected is None:
        raise DemoError("no consecutive feature-only eligible validation account pair is available")
    customer_id, t1, t2 = selected

    source_database_path = Path(run_config["database_path"]).resolve()
    database_path = (root / "prompt34-replay-database.sqlite3").resolve()
    if database_path.exists():
        raise FileExistsError("replay database already exists; refusing a second evaluation/replay")
    source_database_sha256 = _sha256(source_database_path)
    shutil.copy2(source_database_path, database_path)
    if _sha256(database_path) != source_database_sha256:
        raise DemoError("private replay database copy does not match the imported source database")
    dataset_path = Path(run_config["dataset_path"])
    provisioned = provision_member2_reader(dataset_path, database_path, TENANT_ID)
    token = provisioned.pop("token")
    principal = authenticate_service_principal(database_path, token)
    adapter = SQLiteDataAdapter(database_path, dataset_path, principal)
    pipeline = PredictionPipeline(
        adapter,
        models=models,
        calibrators=calibrators,
        config=PredictionPipelineConfig(
            execution_mode=PipelineExecutionMode.SYNTHETIC_TEST_ONLY,
        ),
    )

    # Prompt 33's canonical writer is used for durable isolated-SQLite writes.
    # Until Member 1 provides a history reader, the demo keeps a scoped process
    # mirror for read-after-write/idempotency and replay history only.
    prediction_cache: dict[tuple[str, str, datetime], PredictionOutput] = {}

    def read_one(_database_path, scoped_principal, requested_customer, as_of):
        if scoped_principal.tenant_id != TENANT_ID:
            raise PermissionError("replay store principal is out of tenant scope")
        return prediction_cache.get((scoped_principal.tenant_id, requested_customer, as_of))

    def read_history(_database_path, scoped_principal, requested_customer):
        if scoped_principal.tenant_id != TENANT_ID:
            raise PermissionError("replay history principal is out of tenant scope")
        return tuple(
            row for (tenant_id, customer, _), row in prediction_cache.items()
            if tenant_id == scoped_principal.tenant_id and customer == requested_customer
        )

    def write_prediction(path, scoped_principal, payload):
        # Member 1's current writer accepts only a restricted diagnostic subset
        # and rejects the existing human-readable reasons/full SHAP structure.
        # Preserve the full canonical output in the private immutable snapshot
        # artifact below; write only fields its established DB contract accepts.
        database_payload = _member1_safe_prediction_payload(payload)
        prediction_id = store_prediction(path, scoped_principal, database_payload)
        canonical_fields = {
            key: payload[key]
            for key in (
                "prediction_id", "prediction_run_id", "customer_id", "as_of",
                "generated_at", "status", "p_churn_7d", "p_churn_14d",
                "p_churn_30d", "feature_version", "model_version",
                "calibration_version", "label_policy_version",
            )
        }
        output = PredictionOutput.model_validate(
            {
                "tenant_id": scoped_principal.tenant_id,
                **canonical_fields,
                "reliability": {
                    "status": payload["reliability_status"],
                    "reasons": payload.get("reliability_reasons", []),
                },
                "data_freshness": {
                    "status": payload["data_freshness_status"],
                    "input_data_as_of": payload.get("input_data_as_of"),
                },
                "uncertainty": {"status": "not_quantified", "method": "none", "intervals": None},
                "explanations_by_horizon": payload.get("explanations_by_horizon", {}),
            }
        )
        prediction_cache[(output.tenant_id, output.customer_id, output.as_of)] = output
        return prediction_id

    store = DataFoundationPredictionSnapshotStore(
        database_path,
        principal,
        read_prediction=read_one,
        read_history=read_history,
        write_prediction=write_prediction,
    )
    batch = DailyPredictionBatch(adapter, pipeline, store)
    replay = PointInTimeReplayRunner(batch).replay_customer(
        customer_id,
        (t1, t2),
        prediction_run_prefix="p34-demo-replay",
    )
    stored = store.history_for(TENANT_ID, customer_id)
    replay_predictions = tuple(item for item in stored if item.as_of in {t1, t2})
    if len(replay_predictions) != 2:
        raise DemoError("both prediction snapshots did not reach the canonical writer and scoped mirror")
    if any(item.status not in {PredictionStatus.SCORED, PredictionStatus.ABSTAINED, PredictionStatus.KNOWN_CANCELLATION, PredictionStatus.NOT_ELIGIBLE} for item in replay_predictions):
        raise DemoError("replay returned an undocumented prediction state")
    if _sha256(source_database_path) != source_database_sha256:
        raise DemoError("replay mutated the immutable imported source database")

    replay_dir = root / "replay"
    replay_dir.mkdir(parents=True, exist_ok=False)
    snapshot_file = replay_dir / "immutable_t1_t2_prediction_snapshots.jsonl.gz"
    snapshot_rows = (
        {
            "evidence_type": "SYNTHETIC_DEMO_ONLY",
            "dataset_id": preparation["dataset_identity"]["dataset_id"],
            **item.model_dump(mode="json"),
        }
        for item in sorted(replay_predictions, key=lambda value: value.as_of)
    )
    snapshot_count = _write_jsonl_gzip(snapshot_file, snapshot_rows)
    snapshot_digest = _sha256(snapshot_file)

    policy_data = bundle["alert_policy"]
    policy = AlertPolicy(
        policy_version=policy_data["policy_version"],
        probability_threshold=policy_data["probability_threshold"],
        minimum_reliability=ReliabilityStatus(policy_data["minimum_reliability"]),
        allowed_freshness=frozenset(FreshnessStatus(item) for item in policy_data["allowed_freshness"]),
        require_rising_risk=True,
        allow_initial_threshold_alert=True,
        cooldown=timedelta(days=policy_data["cooldown_days"]),
        period_days=policy_data["period_days"],
        maximum_alerts_per_period=REVIEW_CAPACITY_K,
    )
    alert_decisions = []
    historical_alerts: list[HistoricalRiskAlert] = []
    for prediction in sorted(replay_predictions, key=lambda item: item.as_of):
        decision = apply_alert_policy(
            [prediction],
            prior_predictions=[item for item in replay_predictions if item.as_of < prediction.as_of],
            prior_alerts=historical_alerts,
            policy=policy,
        )[0]
        alert_decisions.append(decision)
        if decision.selected:
            historical_alerts.append(
                HistoricalRiskAlert(
                    tenant_id=prediction.tenant_id,
                    customer_id=prediction.customer_id,
                    prediction_id=prediction.prediction_id,
                    alerted_at=prediction.as_of,
                    policy_version=policy.policy_version,
                )
            )

    # Reveal the validation outcome only after persisted T1/T2 snapshots exist.
    labeled_validation, _ = _load_stage(prepared_path, "validation", include_labels=True)
    labels_by_cutoff = {
        record.feature_snapshot.as_of: record.labels
        for record in labeled_validation
        if record.feature_snapshot.customer_id == customer_id
        and record.feature_snapshot.as_of in {t1, t2}
    }
    future_effective_events = [
        label.churn_effective_at
        for labels in labels_by_cutoff.values()
        for label in labels
        if label.churn_effective_at is not None and label.label == 1
    ]
    warning_lead_time_days = None
    first_alert = next((alert for alert in historical_alerts), None)
    if future_effective_events and first_alert is not None:
        effective = min(future_effective_events)
        if effective > first_alert.alerted_at:
            warning_lead_time_days = (effective - first_alert.alerted_at).total_seconds() / 86400

    feature_builder = FeatureBuilder(adapter)
    feature_snapshots = {
        cutoff: feature_builder.build(
            TENANT_ID,
            customer_id,
            cutoff,
            usage_coverage=adapter.coverage_for(TENANT_ID, customer_id, cutoff),
        )
        for cutoff in (t1, t2)
    }
    t1_values = feature_snapshots[t1].feature_values.model_dump(mode="json")
    t2_values = feature_snapshots[t2].feature_values.model_dump(mode="json")
    changed_features = {
        name: {"t1": t1_values.get(name), "t2": t2_values.get(name)}
        for name in sorted(set(t1_values) | set(t2_values))
        if t1_values.get(name) != t2_values.get(name)
    }
    explanation_changes = {
        cutoff.isoformat(): _explanation_summary(
            prediction,
            feature_order={h: tuple(models[h].metadata.feature_names) for h in SUPPORTED_HORIZONS},
        )
        for cutoff, prediction in ((item.as_of, item) for item in replay_predictions)
    }
    replay_payload = {
        "evidence_type": "SYNTHETIC_DEMO_ONLY",
        "dataset_id": preparation["dataset_identity"]["dataset_id"],
        "tenant_scope": TENANT_ID,
        "customer_id": customer_id,
        "cutoffs": [t1.isoformat(), t2.isoformat()],
        "cutoff_gap_days": (t2 - t1).days,
        "persisted_predictions": [item.model_dump(mode="json") for item in replay_predictions],
        "immutable_full_prediction_snapshot_artifact": {
            "path": str(snapshot_file),
            "sha256": snapshot_digest,
            "snapshot_count": snapshot_count,
            "written_before_outcome_artifacts_were_opened": True,
        },
        "replay_items": [item.model_dump(mode="json") for item in replay.items],
        "risk_changes": [item.model_dump(mode="json") for item in replay.changes],
        "feature_changes": changed_features,
        "shap_explanations": explanation_changes,
        "alerts": [item.model_dump(mode="json") for item in alert_decisions],
        "revealed_outcome_statuses": {
            cutoff.isoformat(): {
                str(label.horizon_days): {
                    "label": label.label,
                    "label_status": label.label_status.value,
                    "churn_effective_at": label.churn_effective_at.isoformat() if label.churn_effective_at else None,
                }
                for label in labels
            }
            for cutoff, labels in labels_by_cutoff.items()
        },
        "warning_lead_time_days": warning_lead_time_days,
        "push_api_replay": "NOT_RUN: Member 1 Push API does not accept trusted source_available_at/received_at in its HTTP payload; events were imported through the authenticated canonical adapter and replayed from the tenant-scoped point-in-time reader.",
        "database_prediction_writer": "Member 1 canonical store_prediction on isolated demo SQLite database",
        "database_payload_limitations": "Member 1's writer stores canonical status, probabilities, model/calibration/feature versions and freshness/reliability status, but its safe-tree validator rejects full SHAP attribution payloads and free-form reliability reasons. Those fields are retained in the immutable private PredictionOutput snapshot artifact, not in the database row.",
        "source_database_unchanged": True,
        "source_database_sha256": source_database_sha256,
        "replay_database_path": str(database_path),
        "replay_database_sha256_after_writes": _sha256(database_path),
        "history_reader_limitation": "Member 1 has no authenticated prediction-history reader; same-process scoped read-after-write mirror was used for this replay session.",
    }
    report_path = replay_dir / "model_backed_t1_t2_replay.json"
    _save_json(report_path, replay_payload)
    return {
        "status": "SYNTHETIC_DEMO_ONLY_REPLAY_COMPLETED",
        "dataset_id": preparation["dataset_identity"]["dataset_id"],
        "prediction_statuses": [item.status.value for item in replay_predictions],
        "scored_snapshot_count": sum(item.status is PredictionStatus.SCORED for item in replay_predictions),
        "persisted_snapshot_count": len(replay_predictions),
        "risk_changes": [item.model_dump(mode="json") for item in replay.changes],
        "alert_selected": [item.selected for item in alert_decisions],
        "warning_lead_time_days": warning_lead_time_days,
        "replay_report_path": str(report_path),
        "push_api_replay": "NOT_RUN_SOURCE_AVAILABILITY_NOT_SUPPORTED_BY_HTTP_CONTRACT",
        "prediction_history_reader": "SAME_PROCESS_SCOPED_MIRROR_ONLY",
    }


def _explanation_summary(
    prediction: PredictionOutput,
    *,
    feature_order: Mapping[int, tuple[str, ...]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for horizon in ("7", "14", "30"):
        entries = prediction.explanations_by_horizon.get(horizon, [])
        explanation = entries[0] if entries else {}
        available = explanation.get("explanation_status") == "available"
        if explanation.get("model_version") not in {None, MODEL_VERSION}:
            raise DemoError("persisted explanation does not match the fitted model version")
        if available:
            if explanation.get("feature_version") != prediction.feature_version:
                raise DemoError("SHAP explanation feature version differs from the prediction")
            contributions = explanation.get("feature_contributions", [])
            contribution_names = tuple(item.get("feature_name") for item in contributions)
            horizon = int(horizon)
            if contribution_names != feature_order[horizon]:
                raise DemoError("SHAP feature order does not match the fitted model metadata")
            additivity_error = explanation.get("additivity_error")
            tolerance = explanation.get("additivity_tolerance")
            if additivity_error is None or tolerance is None or additivity_error > tolerance:
                raise DemoError("SHAP additive reconstruction check did not pass")
        summary[horizon] = {
            "explanation_status": explanation.get("explanation_status", "missing"),
            "output_space": explanation.get("explained_output_space"),
            "top_positive": explanation.get("positive_contributors", [])[:3] if available else [],
            "top_negative": explanation.get("negative_contributors", [])[:3] if available else [],
            "model_version": explanation.get("model_version"),
            "feature_version": explanation.get("feature_version"),
            "additivity_error": explanation.get("additivity_error"),
            "additivity_tolerance": explanation.get("additivity_tolerance"),
            "feature_order_matches_model": (
                tuple(item.get("feature_name") for item in explanation.get("feature_contributions", []))
                == feature_order[int(horizon)]
                if available else False
            ),
            "limitations": explanation.get("limitations", []),
        }
    return summary


def _select_alert_threshold(validation, models, calibrators, usable_ids: set[str]) -> tuple[float, dict[str, Any]]:
    """Select a raw p30 cut on VALIDATION with fixed per-week K."""

    by_cutoff: dict[datetime, list[tuple[float, int]]] = defaultdict(list)
    for record in validation.snapshots:
        if record.stable_snapshot_id not in usable_ids:
            continue
        label = next(item for item in record.labels if item.horizon_days == 30)
        if label.label not in {0, 1}:
            continue
        score = _predict_probability(models[30], record.feature_snapshot, 30)
        by_cutoff[record.feature_snapshot.as_of].append((score, int(label.label)))
    candidates = sorted({score for rows in by_cutoff.values() for score, _ in rows})
    if not candidates:
        raise DemoError("no mature validation p30 scores are available for alert threshold selection")
    best: tuple[float, float, float, int] = (-1.0, -1.0, float("inf"), -1)
    selected_threshold = candidates[0]
    best_details: dict[str, Any] = {}
    for threshold in candidates:
        tp = fp = fn = alerts = positives = 0
        for rows in by_cutoff.values():
            eligible = sorted((row for row in rows if row[0] >= threshold), key=lambda row: -row[0])[:REVIEW_CAPACITY_K]
            alerts += len(eligible)
            tp += sum(label for _, label in eligible)
            fp += sum(1 - label for _, label in eligible)
            positives += sum(label for _, label in rows)
        fn = positives - tp
        recall = tp / positives if positives else 0.0
        f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        key = (f1, recall, -fp, threshold)
        if key > best:
            best = key
            selected_threshold = threshold
            best_details = {
                "raw_probability_threshold": threshold,
                "validation_alert_count": alerts,
                "validation_true_alerts": tp,
                "validation_false_alerts": fp,
                "validation_recall": recall,
                "validation_f1": f1,
                "weekly_review_capacity_k": REVIEW_CAPACITY_K,
                "validation_cutoff_count": len(by_cutoff),
                "selection_rule": "maximize F1, then recall, then minimize false alerts, then prefer higher threshold",
            }
    return selected_threshold, best_details


def _score_test_features(
    records: tuple[SnapshotRecord, ...],
    *,
    models: Mapping[int, LightGBMModel],
    calibrators: Mapping[int, ProbabilityCalibrator],
    logistic_models: Mapping[int, LogisticRegressionBaseline],
    ablation_models: Mapping[int, LightGBMModel],
    training_records: tuple[SnapshotRecord, ...],
    output_dir: Path,
    model_version: str,
    calibration_version: str,
    feature_version: str,
    preparation_manifest: Mapping[str, Any],
    auxiliary_by_snapshot: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    train_prevalence: dict[int, float] = {}
    train_split = _build_split(training_records, preparation_manifest)
    train_partition = train_split.partition(SplitName.TRAIN)
    for horizon in SUPPORTED_HORIZONS:
        usable = set(train_partition.supervised_snapshot_ids_by_horizon[horizon])
        labels = [
            int(next(label.label for label in record.labels if label.horizon_days == horizon))
            for record in train_partition.snapshots
            if record.stable_snapshot_id in usable
        ]
        train_prevalence[horizon] = float(np.mean(labels))

    evaluation_predictions: list[EvaluationPrediction] = []
    serialized_rows: list[dict[str, Any]] = []
    prediction_count_by_model: Counter[str] = Counter()
    for record in records:
        # These two gates are copied from the authenticated preparation
        # artifact. Labels and outcome files are not consulted here.
        aux = auxiliary_by_snapshot.get(record.stable_snapshot_id, {})
        reliability_status = aux.get("reliability", {}).get("status", "insufficient_evidence")
        freshness_status = aux.get("freshness", {}).get("status", "unknown")
        abstention = bool(aux.get("reliability", {}).get("abstention_required", True))
        scorable = not abstention and reliability_status != "insufficient_evidence" and freshness_status not in {"stale", "unknown"}
        calibrated_outputs = []
        model_scores: dict[str, dict[int, float | None]] = {
            name: {} for name in ("lightgbm_calibrated", "logistic_uncalibrated", "lightgbm_no_personal_baseline", "constant_prevalence", "rule_binary")
        }
        raw_lightgbm: dict[int, float] = {}
        for horizon in SUPPORTED_HORIZONS:
            raw = _predict_probability(models[horizon], record.feature_snapshot, horizon)
            raw_lightgbm[horizon] = raw
            from retainiq_prediction.baselines import BaselinePrediction, BaselineScoreKind

            raw_item = BaselinePrediction(
                horizon_days=horizon,
                status=BaselineStatus.READY,
                score=raw,
                score_kind=BaselineScoreKind.UNCALIBRATED_PROBABILITY,
                baseline_version=MODEL_VERSION,
                feature_version=feature_version,
                model_version=MODEL_VERSION,
            )
            calibrated_outputs.append(calibrators[horizon].calibrate_prediction(raw_item, models[horizon].metadata))
            model_scores["logistic_uncalibrated"][horizon] = _predict_probability(logistic_models[horizon], record.feature_snapshot, horizon)
            model_scores["lightgbm_no_personal_baseline"][horizon] = _predict_probability(ablation_models[horizon], record.feature_snapshot, horizon)
            model_scores["constant_prevalence"][horizon] = train_prevalence[horizon]
            rule = RuleBasedBaseline(RuleBaselineConfig(alert_score_threshold=50.0))
            rule.fit(horizon_days=horizon)
            rule_prediction = rule.predict(record.feature_snapshot, horizon_days=horizon)
            model_scores["rule_binary"][horizon] = (
                float(rule_prediction.alert) if rule_prediction.status is BaselineStatus.READY and rule_prediction.alert is not None else None
            )
        coherent = enforce_horizon_coherence(calibrated_bundle_from_outputs(calibrated_outputs)).adjusted
        model_scores["lightgbm_calibrated"] = {7: coherent.p7, 14: coherent.p14, 30: coherent.p30}
        for horizon in SUPPORTED_HORIZONS:
            probability = model_scores["lightgbm_calibrated"][horizon] if scorable else None
            status = PredictionStatus.SCORED if probability is not None else PredictionStatus.ABSTAINED
            prediction_by_name = {
                "lightgbm_calibrated": (probability, MODEL_VERSION, CALIBRATION_VERSION),
                "logistic_uncalibrated": (model_scores["logistic_uncalibrated"][horizon] if scorable else None, f"prompt34-logistic-{horizon}d-v1", "uncalibrated"),
                "lightgbm_no_personal_baseline": (model_scores["lightgbm_no_personal_baseline"][horizon] if scorable else None, f"prompt34-no-personalization-{horizon}d-v1", "uncalibrated"),
                "constant_prevalence": (model_scores["constant_prevalence"][horizon] if scorable else None, "constant-prevalence-train-v1", "reference-only"),
                "rule_binary": (model_scores["rule_binary"][horizon] if scorable else None, "rule-baseline-v1", "deterministic-hard-decision"),
            }
            for model_name, (model_probability, version, cal_version) in prediction_by_name.items():
                eval_item = EvaluationPrediction(
                    model_name=model_name,
                    tenant_id=record.feature_snapshot.tenant_id,
                    customer_id=record.feature_snapshot.customer_id,
                    as_of=record.feature_snapshot.as_of,
                    horizon_days=horizon,
                    probability=model_probability,
                    status=PredictionStatus.SCORED if model_probability is not None else PredictionStatus.ABSTAINED,
                    model_version=version,
                    feature_version=feature_version,
                    calibration_version=cal_version,
                    label_policy_version="effective-account-churn-v1.2",
                )
                evaluation_predictions.append(eval_item)
                prediction_count_by_model[model_name] += 1
                serialized_rows.append(
                    {
                        "evidence_type": "SYNTHETIC_DEMO_ONLY",
                        "dataset_id": preparation_manifest["dataset_identity"]["dataset_id"],
                        "snapshot_id": record.stable_snapshot_id,
                        "tenant_id": record.feature_snapshot.tenant_id,
                        "customer_id": record.feature_snapshot.customer_id,
                        "as_of": record.feature_snapshot.as_of.isoformat(),
                        "model_name": model_name,
                        "horizon_days": horizon,
                        "status": eval_item.status.value,
                        "probability": eval_item.probability,
                        "model_version": version,
                        "calibration_version": cal_version,
                        "feature_version": feature_version,
                        "reliability_status": reliability_status,
                        "freshness_status": freshness_status,
                    }
                )
    elapsed = time.perf_counter() - started
    return {
        "evaluation_predictions": evaluation_predictions,
        "serialized_rows": serialized_rows,
        "prediction_counts": dict(prediction_count_by_model),
    }, elapsed


def _test_support(records: tuple[SnapshotRecord, ...], horizon: int) -> dict[str, Any]:
    labels = [next(label for label in record.labels if label.horizon_days == horizon) for record in records]
    counts = Counter(label.label_status.value for label in labels)
    return {
        "eligible_snapshots": len(records),
        "positive": sum(label.label == 1 for label in labels),
        "negative": sum(label.label == 0 for label in labels),
        "unknown": counts.get("unknown", 0),
        "excluded": counts.get("excluded", 0),
        "unsupported": counts.get("unsupported", 0),
        "unique_accounts": len({record.feature_snapshot.customer_id for record in records}),
        "unique_positive_accounts": len({
            record.feature_snapshot.customer_id
            for record in records
            if next(label for label in record.labels if label.horizon_days == horizon).label == 1
        }),
        "unique_negative_accounts": len({
            record.feature_snapshot.customer_id
            for record in records
            if next(label for label in record.labels if label.horizon_days == horizon).label == 0
        }),
    }


def _test_reliability_cohorts(
    serialized_rows: list[dict[str, Any]],
    records: tuple[SnapshotRecord, ...],
    auxiliary_by_snapshot: Mapping[str, Mapping[str, Any]],
    *,
    evaluation_cutoff: datetime,
) -> dict[str, Any]:
    main_rows = {
        (row["snapshot_id"], row["horizon_days"]): row
        for row in serialized_rows
        if row["model_name"] == "lightgbm_calibrated"
    }
    output: dict[str, Any] = {}
    statuses = ("sufficient_evidence", "limited_evidence", "insufficient_evidence")
    for horizon in SUPPORTED_HORIZONS:
        horizon_result = {}
        for reliability_status in statuses:
            group = [
                record for record in records
                if auxiliary_by_snapshot.get(record.stable_snapshot_id, {}).get("reliability", {}).get("status") == reliability_status
            ]
            mature = []
            scored_labels: list[int] = []
            scored_probabilities: list[float] = []
            for record in group:
                label = next(item for item in record.labels if item.horizon_days == horizon)
                row = main_rows.get((record.stable_snapshot_id, horizon), {})
                if (
                    label.label in {0, 1}
                    and label.label_status.value in {"positive", "negative"}
                    and label.evaluation_as_of <= evaluation_cutoff
                    and label.label_generated_at <= evaluation_cutoff
                ):
                    mature.append(record)
                    if row.get("status") == PredictionStatus.SCORED.value and row.get("probability") is not None:
                        scored_labels.append(int(label.label))
                        scored_probabilities.append(float(row["probability"]))
            horizon_result[reliability_status] = {
                "eligible_snapshot_count": len(group),
                "mature_labeled_count": len(mature),
                "scored_count": len(scored_probabilities),
                "abstention_share": (
                    1 - len(scored_probabilities) / len(mature) if mature else None
                ),
                "positive_count_scored": sum(scored_labels),
                "negative_count_scored": len(scored_labels) - sum(scored_labels),
                "pr_auc": (
                    float(average_precision_score(scored_labels, scored_probabilities))
                    if scored_labels and 0 < sum(scored_labels) < len(scored_labels) else None
                ),
                "brier": (
                    float(np.mean((np.asarray(scored_probabilities) - np.asarray(scored_labels)) ** 2))
                    if scored_labels else None
                ),
            }
        output[str(horizon)] = horizon_result
    return output


def _print_json(result: Mapping[str, Any]) -> None:
    print(json.dumps(result, sort_keys=True, allow_nan=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="generate/import/prepare a new isolated synthetic dataset")
    prepare_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    prepare_parser.add_argument("--accounts", type=int, default=5000)
    reduced_parser = commands.add_parser(
        "prepare-reduced",
        help="prepare fewer predeclared cutoffs from the existing import; never regenerate/reimport",
    )
    reduced_parser.add_argument("--root", type=Path, default=REDUCED_ROOT)
    train_parser = commands.add_parser("train", help="train, calibrate, reload, and evaluate one frozen synthetic demo")
    train_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    replay_parser = commands.add_parser("replay", help="load the bundle and run persisted T1/T2 model-backed replay")
    replay_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            _print_json(prepare(args.root, account_count=args.accounts))
        elif args.command == "prepare-reduced":
            _print_json(prepare_reduced_existing(args.root))
        elif args.command == "train":
            _print_json(train_and_evaluate(args.root))
        else:
            _print_json(run_replay(args.root))
        return 0
    except Exception as exc:
        # Do not print exception payloads, row values, or credential material.
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__, "message": str(exc)[:240]}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
