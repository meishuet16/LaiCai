"""Prepare deterministic, tenant-scoped historical data without model fitting.

The command writes customer-level synthetic features and labels outside the
repository. All source reads go through Member 1's authenticated reader APIs.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import time as time_module
from typing import Any, Iterable, Mapping, Sequence

from retaniq.data_foundation import (
    DataFoundationError,
    ServicePrincipal,
    authenticate_service_principal,
)

from .data_freshness import FreshnessStatus, assess_data_freshness
from .eligibility import EligibilityState
from .feature_builder import FeatureBuilder, FeatureSnapshot
from .label_builder import (
    ChurnLabel,
    ChurnLabelBuilder,
    LabelBuilderConfig,
    LabelStatus,
    LifecycleOutcomeSnapshot,
    OutcomeObservation,
)
from .reliability import ReliabilityStatus, assess_reliability
from .sqlite_data_adapter import SQLiteDataAdapter
from .temporal_splits import (
    SnapshotRecord,
    SplitName,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitResult,
    TemporalSplitter,
)


UTC = timezone.utc
STAGE_NAMES = {
    "train": SplitName.TRAIN,
    "development": SplitName.VALIDATION,
    "calibration": SplitName.CALIBRATION,
    "untouched_test": SplitName.TEST,
}
SPLIT_STAGE_KEY = {
    SplitName.TRAIN: "train",
    SplitName.VALIDATION: "development",
    SplitName.CALIBRATION: "calibration",
    SplitName.TEST: "untouched_test",
}


@dataclass(frozen=True)
class Cutoff:
    as_of: datetime
    split: SplitName
    label_freeze: datetime


def _utc_midnight(value: str, field_name: str) -> datetime:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO calendar date") from exc
    return datetime.combine(parsed, time.min, tzinfo=UTC)


def build_cutoff_schedule(
    dataset_manifest: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
) -> tuple[Cutoff, ...]:
    """Use the dataset's real weekly schedule and frozen stage maturity dates."""

    if split_manifest.get("sampling_policy", {}).get("frequency") != "weekly":
        raise ValueError("the dataset split manifest does not define weekly cutoffs")
    if split_manifest.get("sampling_policy", {}).get("cutoff_utc") != "Monday 12:00:00Z":
        raise ValueError("unsupported cutoff policy; expected Monday 12:00:00Z")
    start = date.fromisoformat(dataset_manifest["start_date"])
    end = date.fromisoformat(dataset_manifest["end_date"])
    if not dataset_manifest.get("end_date_exclusive"):
        raise ValueError("dataset end date must be explicitly end-exclusive")
    warmup_days = int(split_manifest["sampling_policy"]["warmup_days"])
    first_eligible_date = start + timedelta(days=warmup_days)
    first_monday = first_eligible_date + timedelta(days=(-first_eligible_date.weekday()) % 7)
    stages = split_manifest["stages"]
    stage_ranges: list[tuple[date, date, datetime, SplitName]] = []
    for key, split_name in STAGE_NAMES.items():
        stage = stages[key]
        left = date.fromisoformat(stage["cutoff_start"])
        right_exclusive = date.fromisoformat(stage["cutoff_end"])
        freeze = _utc_midnight(stage["mature_before"], f"{key}.mature_before")
        if right_exclusive <= left or freeze <= datetime.combine(right_exclusive, time.min, tzinfo=UTC):
            raise ValueError(f"invalid date window in split stage {key}")
        stage_ranges.append((left, right_exclusive, freeze, split_name))

    schedule: list[Cutoff] = []
    day = first_monday
    while day < end:
        matches = [stage for stage in stage_ranges if stage[0] <= day < stage[1]]
        if len(matches) > 1:
            raise ValueError(f"cutoff date {day.isoformat()} belongs to multiple stages")
        if matches:
            _, _, freeze, split_name = matches[0]
            schedule.append(Cutoff(
                as_of=datetime.combine(day, time(12), tzinfo=UTC),
                split=split_name,
                label_freeze=freeze,
            ))
        day += timedelta(days=7)
    if not schedule or {item.split for item in schedule} != set(SplitName):
        raise ValueError("the dataset dates do not support all four frozen split windows")
    return tuple(schedule)


def label_evaluation_cutoff(
    as_of: datetime,
    horizon_days: int,
    stage_freeze: datetime,
    maturity_lag_days: int,
) -> datetime:
    """Cap label knowledge at the stage freeze and synthetic maturity lag."""

    for name, value in (("as_of", as_of), ("stage_freeze", stage_freeze)):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
    if horizon_days not in {7, 14, 30} or maturity_lag_days < 0:
        raise ValueError("unsupported horizon or negative maturity lag")
    return min(
        stage_freeze,
        as_of + timedelta(days=horizon_days + maturity_lag_days),
    )


def select_predeclared_cutoffs(
    schedule: Sequence[Cutoff],
    counts_by_split: Mapping[SplitName, int],
) -> tuple[Cutoff, ...]:
    """Select evenly spaced real cutoffs per split, without inspecting outcomes."""

    if set(counts_by_split) != set(SplitName):
        raise ValueError("cutoff counts must explicitly cover all four chronological splits")
    selected: list[Cutoff] = []
    for split_name in SplitName:
        stage = tuple(item for item in schedule if item.split is split_name)
        count = counts_by_split[split_name]
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= len(stage):
            raise ValueError(f"invalid predeclared cutoff count for {split_name.value}")
        if count == 1:
            indexes = (len(stage) // 2,)
        else:
            indexes = tuple(round(index * (len(stage) - 1) / (count - 1)) for index in range(count))
        if len(set(indexes)) != count:
            raise ValueError(f"predeclared cutoff selection duplicated a date for {split_name.value}")
        selected.extend(stage[index] for index in indexes)
    result = tuple(sorted(selected, key=lambda item: item.as_of))
    if len({item.as_of for item in result}) != len(result):
        raise ValueError("predeclared cutoff schedule contains duplicate timestamps")
    return result


class _CachedLifecycleOutcomeAdapter:
    """Reuse point-in-time reads and filter later outcomes by each label cutoff."""

    def __init__(
        self,
        prediction_snapshot,
        outcome_snapshot: LifecycleOutcomeSnapshot | None,
        *,
        horizon_days: int,
        maturity_lag_days: int,
    ) -> None:
        self.prediction_snapshot = prediction_snapshot
        self.outcome_snapshot = outcome_snapshot
        self.horizon_days = horizon_days
        self.maturity_lag_days = maturity_lag_days

    def prediction_snapshot_for(self, tenant_id: str, customer_id: str, as_of: datetime):
        snapshot = self.prediction_snapshot
        if (snapshot.tenant_id, snapshot.customer_id, snapshot.as_of) != (tenant_id, customer_id, as_of):
            raise DataFoundationError("contract_conflict")
        return snapshot

    def outcome_snapshot_for(
        self,
        tenant_id: str,
        customer_id: str,
        prediction_as_of: datetime,
        evaluation_as_of: datetime,
    ) -> LifecycleOutcomeSnapshot:
        base = self.outcome_snapshot
        if base is None:
            return LifecycleOutcomeSnapshot(
                tenant_id=tenant_id,
                customer_id=customer_id,
                prediction_as_of=prediction_as_of,
                evaluation_as_of=evaluation_as_of,
            )
        if (base.tenant_id, base.customer_id, base.prediction_as_of) != (
            tenant_id, customer_id, prediction_as_of
        ):
            raise DataFoundationError("contract_conflict")
        horizon_end = prediction_as_of + timedelta(days=self.horizon_days)
        facts = []
        late_outcomes = 0
        for fact in base.subscription_facts:
            available_at = fact.source_available_at or fact.received_at
            if available_at is not None and available_at <= evaluation_as_of:
                if fact.occurred_at is None or fact.occurred_at <= evaluation_as_of:
                    facts.append(fact)
            elif (
                fact.effective_at is not None
                and prediction_as_of < fact.effective_at <= horizon_end
                and available_at is not None
                and available_at <= base.evaluation_as_of
            ):
                late_outcomes += 1
        observations = tuple(
            item for item in base.observations
            if item.available_at <= evaluation_as_of
            and item.observed_through <= evaluation_as_of
        )
        excluded = dict(base.excluded_record_counts)
        if late_outcomes:
            excluded["late_outcome_not_available"] = (
                excluded.get("late_outcome_not_available", 0) + late_outcomes
            )
        return LifecycleOutcomeSnapshot(
            tenant_id=tenant_id,
            customer_id=customer_id,
            prediction_as_of=prediction_as_of,
            evaluation_as_of=evaluation_as_of,
            subscription_facts=tuple(facts),
            observations=observations,
            excluded_record_counts=excluded,
            limitations=base.limitations,
        )


class _CountingReaderAPI:
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


def _available_at(item: Any) -> datetime | None:
    return getattr(item, "source_available_at", None) or getattr(item, "received_at", None)


def _evidence_availability(
    feature_snapshot: FeatureSnapshot,
    prediction_snapshot,
    usage_coverage: Sequence[Any],
    label_evidence: Sequence[ChurnLabel],
    outcome_snapshot: LifecycleOutcomeSnapshot | None,
) -> dict[str, dict[str, Any]]:
    provenance: dict[str, dict[str, Any]] = {}
    all_facts = (
        *prediction_snapshot.subscriptions,
        *prediction_snapshot.usage_events,
        *prediction_snapshot.billing_events,
    )
    for fact in all_facts:
        provenance[fact.record_id] = {
            "kind": fact.category.value,
            "source": fact.source,
            "occurred_at": fact.occurred_at.isoformat().replace("+00:00", "Z") if fact.occurred_at else None,
            "effective_at": fact.effective_at.isoformat().replace("+00:00", "Z") if fact.effective_at else None,
            "source_available_at": fact.source_available_at.isoformat().replace("+00:00", "Z") if fact.source_available_at else None,
            "received_at": fact.received_at.isoformat().replace("+00:00", "Z") if fact.received_at else None,
        }
    for item in usage_coverage:
        provenance[item.coverage_id] = {
            "kind": "usage_coverage",
            "source": item.source,
            "observed_from": item.observed_from.isoformat().replace("+00:00", "Z"),
            "observed_through": item.observed_to.isoformat().replace("+00:00", "Z"),
            "available_at": item.available_at.isoformat().replace("+00:00", "Z"),
            "complete": item.complete,
            "status": item.status,
        }
    if outcome_snapshot is not None:
        for fact in outcome_snapshot.subscription_facts:
            provenance[fact.record_id] = {
                "kind": "subscription_outcome",
                "source": fact.source,
                "occurred_at": fact.occurred_at.isoformat().replace("+00:00", "Z") if fact.occurred_at else None,
                "effective_at": fact.effective_at.isoformat().replace("+00:00", "Z") if fact.effective_at else None,
                "source_available_at": fact.source_available_at.isoformat().replace("+00:00", "Z") if fact.source_available_at else None,
                "received_at": fact.received_at.isoformat().replace("+00:00", "Z") if fact.received_at else None,
            }
        for item in outcome_snapshot.observations:
            provenance[item.observation_id] = {
                "kind": "subscription_outcome_coverage",
                "source": item.source,
                "observed_from": item.observed_from.isoformat().replace("+00:00", "Z"),
                "observed_through": item.observed_through.isoformat().replace("+00:00", "Z"),
                "available_at": item.available_at.isoformat().replace("+00:00", "Z"),
                "source_category": item.source_category,
                "complete": item.complete,
                "coverage_status": item.coverage_status,
                "coverage_completeness": item.coverage_completeness,
                "observation_policy_version": item.observation_policy_version,
            }
    used = set(feature_snapshot.source_evidence_refs)
    for label in label_evidence:
        used.update(label.source_evidence_refs)
    return {key: provenance[key] for key in sorted(used) if key in provenance}


def _status_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _enum_counts(counter: Counter) -> dict[str, int]:
    return dict(sorted((str(key), int(value)) for key, value in counter.items()))


def _partition_summary(
    split_result: TemporalSplitResult,
    auxiliary: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for split_name in SplitName:
        partition = split_result.partition(split_name)
        records = partition.snapshots
        unique_accounts = len({record.account_key for record in records})
        horizon_counts: dict[str, Any] = {}
        for horizon in (7, 14, 30):
            statuses = Counter(
                next(label.label_status.value for label in record.labels if label.horizon_days == horizon)
                for record in records
            )
            positive_accounts = len({
                record.feature_snapshot.customer_id
                for record in records
                if any(label.horizon_days == horizon and label.label_status is LabelStatus.POSITIVE for label in record.labels)
            })
            negative_accounts = len({
                record.feature_snapshot.customer_id
                for record in records
                if any(label.horizon_days == horizon and label.label_status is LabelStatus.NEGATIVE for label in record.labels)
            })
            horizon_counts[str(horizon)] = {
                "label_status_counts": _enum_counts(statuses),
                "confirmed_positive_accounts": positive_accounts,
                "confirmed_negative_accounts": negative_accounts,
                "usable_for_supervised_fit": len(partition.supervised_snapshot_ids_by_horizon.get(horizon, ())),
                "available_for_test_evaluation_only": len(partition.evaluation_snapshot_ids_by_horizon.get(horizon, ())) if split_name is SplitName.TEST else 0,
                "label_maturity_exclusions": split_result.manifest.label_maturity_exclusions[split_name.value][horizon],
            }
        reliability = Counter(
            auxiliary[record.stable_snapshot_id]["reliability"]["status"]
            for record in records
        )
        freshness = Counter(
            auxiliary[record.stable_snapshot_id]["freshness"]["status"]
            for record in records
        )
        coverage = Counter(
            auxiliary[record.stable_snapshot_id]["feature_quality"]["usage_coverage_status"]
            for record in records
        )
        baseline = Counter(
            auxiliary[record.stable_snapshot_id]["feature_quality"]["personal_baseline_status"]
            for record in records
        )
        dates = [record.feature_snapshot.as_of.date().isoformat() for record in records]
        summary[split_name.value] = {
            "first_cutoff_date": min(dates) if dates else None,
            "last_cutoff_date": max(dates) if dates else None,
            "snapshot_count": len(records),
            "unique_accounts": unique_accounts,
            "repeated_account_snapshots": len(records) - unique_accounts,
            "horizons": horizon_counts,
            "reliability_status_counts": _enum_counts(reliability),
            "freshness_status_counts": _enum_counts(freshness),
            "usage_coverage_status_counts": _enum_counts(coverage),
            "personal_baseline_status_counts": _enum_counts(baseline),
        }
    return summary


def _horizon_summary(
    records: Sequence[SnapshotRecord],
    all_snapshot_count: int,
    eligibility_counts: Mapping[str, Counter],
    split_result: TemporalSplitResult,
    minimums: Mapping[str, int],
    label_reasons: Mapping[str, Counter] | None = None,
    outcome_coverage: Mapping[str, Counter] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for horizon in (7, 14, 30):
        labels = [label for record in records for label in record.labels if label.horizon_days == horizon]
        status_counts = Counter(label.label_status.value for label in labels)
        confirmed = [label for label in labels if label.label_status in {LabelStatus.POSITIVE, LabelStatus.NEGATIVE}]
        positives = [label for label in confirmed if label.label == 1]
        negatives = [label for label in confirmed if label.label == 0]
        unique_accounts = {record.feature_snapshot.customer_id for record in records}
        stage_class: dict[str, Any] = {}
        stage_ready = True
        for split_name in SplitName:
            partition = split_result.partition(split_name)
            rows = [
                (record, next(label for label in record.labels if label.horizon_days == horizon))
                for record in partition.snapshots
            ]
            usable_ids = set(partition.evaluation_snapshot_ids_by_horizon.get(horizon, ()))
            usable = [(record, label) for record, label in rows if record.stable_snapshot_id in usable_ids]
            pos = [(record, label) for record, label in usable if label.label == 1]
            neg = [(record, label) for record, label in usable if label.label == 0]
            unique_pos = len({record.feature_snapshot.customer_id for record, _ in pos})
            unique_neg = len({record.feature_snapshot.customer_id for record, _ in neg})
            if split_name is SplitName.TEST:
                minimum_pos_key = "minimum_positive_samples"
                minimum_neg_key = "minimum_negative_samples"
            else:
                minimum_pos_key = "minimum_positive_samples"
                minimum_neg_key = "minimum_negative_samples"
            meets = (
                len(pos) >= minimums.get(minimum_pos_key, 50)
                and len(neg) >= minimums.get(minimum_neg_key, 50)
                and unique_pos >= minimums.get("minimum_unique_positive_accounts", 20)
                and unique_neg >= minimums.get("minimum_unique_negative_accounts", 20)
            )
            stage_ready = stage_ready and meets
            stage_class[split_name.value] = {
                "confirmed_positive_snapshots": len(pos),
                "confirmed_negative_snapshots": len(neg),
                "unique_positive_accounts": unique_pos,
                "unique_negative_accounts": unique_neg,
                "meets_dataset_declared_class_minimums": meets,
                "test_labels_are_evaluation_only": split_name is SplitName.TEST,
            }
        total_eligibility = Counter()
        for stage_counter in eligibility_counts.values():
            total_eligibility.update(stage_counter)
        result[str(horizon)] = {
            "total_historical_snapshots": all_snapshot_count,
            "eligible_snapshots": len(records),
            "known_cancellation_snapshots": total_eligibility.get(EligibilityState.KNOWN_CANCELLATION.value, 0),
            "not_eligible_snapshots": total_eligibility.get(EligibilityState.NOT_ELIGIBLE.value, 0),
            "insufficient_eligibility_snapshots": total_eligibility.get(EligibilityState.INSUFFICIENT_DATA.value, 0),
            "mature_positive": len(positives),
            "mature_negative": len(negatives),
            "unknown_or_incomplete": status_counts.get(LabelStatus.UNKNOWN.value, 0),
            "excluded_or_ineligible_labels": status_counts.get(LabelStatus.EXCLUDED.value, 0),
            "unsupported_labels": status_counts.get(LabelStatus.UNSUPPORTED.value, 0),
            "label_reason_counts": _enum_counts((label_reasons or {}).get(str(horizon), Counter())),
            "outcome_coverage_record_counts_by_source_and_status": _enum_counts(
                (outcome_coverage or {}).get(str(horizon), Counter())
            ),
            "usable_supervised_train_samples": len(split_result.partition(SplitName.TRAIN).supervised_snapshot_ids_by_horizon.get(horizon, ())),
            "confirmed_label_prevalence": len(positives) / len(confirmed) if confirmed else None,
            "unique_eligible_accounts_with_feature_snapshots": len(unique_accounts),
            "repeated_account_snapshots": max(0, len(records) - len(unique_accounts)),
            "date_range": {
                "first_cutoff": min((r.feature_snapshot.as_of for r in records), default=None).isoformat() if records else None,
                "last_cutoff": max((r.feature_snapshot.as_of for r in records), default=None).isoformat() if records else None,
            },
            "split_class_coverage": stage_class,
            "synthetic_training_readiness": "READY_FOR_SYNTHETIC_TRAINING" if stage_ready else "BLOCKED",
            "denominator_note": "Counts include every account-cutoff with lifecycle evidence; ineligible and insufficient-eligibility counts are shown separately. Unknown labels are retained, not recoded as zero.",
        }
    return result


def _write_jsonl_gzip(path: Path, rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text:
                for row in rows:
                    text.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
                    text.write("\n")
                    count += 1
    temporary.replace(path)
    digest = _sha256_file(path)
    return {"sha256": digest, "records": count, "bytes": path.stat().st_size}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_bytes() -> int | None:
    try:
        import psutil  # type: ignore[import-not-found]

        process = psutil.Process()
        info = process.memory_info()
        return int(getattr(info, "peak_wset", info.rss))
    except Exception:
        return None


class _PreparedRun:
    def __init__(self) -> None:
        self.records: list[SnapshotRecord] = []
        self.auxiliary: dict[str, dict[str, Any]] = {}
        self.cutoff_eligibility: dict[str, Counter] = defaultdict(Counter)
        self.overall_eligibility: Counter = Counter()
        self.label_statuses: dict[str, Counter] = {str(h): Counter() for h in (7, 14, 30)}
        self.label_reasons: dict[str, Counter] = {str(h): Counter() for h in (7, 14, 30)}
        self.outcome_coverage: dict[str, Counter] = {str(h): Counter() for h in (7, 14, 30)}
        self.reliability: Counter = Counter()
        self.freshness: Counter = Counter()
        self.freshness_by_source: Counter = Counter()
        self.freshness_reasons: Counter = Counter()
        self.coverage: Counter = Counter()
        self.baseline: Counter = Counter()
        self.reliability_reasons: Counter = Counter()
        self.feature_missingness: Counter = Counter()
        self.cutoffs_processed = 0
        self.candidate_pairs = 0
        self.lifecycle_snapshots = 0
        self.no_lifecycle_history = 0
        self.label_evidence_missingness: Counter = Counter()
        self.timings: Counter = Counter()


def prepare_historical_dataset(
    adapter: SQLiteDataAdapter,
    dataset_path: str | Path,
    output_dir: str | Path,
    *,
    reader_api_call_counts: Counter | None = None,
    progress_callback=None,
    cutoff_schedule: Sequence[Cutoff] | None = None,
    cutoff_policy_version: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read and freeze tenant-scoped synthetic training data."""

    started = time_module.perf_counter()
    dataset_path = Path(dataset_path).resolve()
    output_dir = Path(output_dir).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    if output_dir == repo_root or repo_root in output_dir.parents:
        raise ValueError("customer-level preparation output must be outside the Git repository")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be new and empty; existing data is preserved")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = dataset_path / "dataset_manifest.json"
    split_path = dataset_path / "split_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    split_spec = json.loads(split_path.read_text(encoding="utf-8"))
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if (manifest.get("dataset_id") != adapter.provenance.dataset_id
            or manifest_digest != adapter.provenance.manifest_sha256
            or manifest.get("target_policy_version") != adapter.provenance.target_policy_version
            or manifest.get("dataset_type") != "synthetic_saas"
            or manifest.get("no_real_customer_data") is not True):
        raise ValueError("dataset identity, manifest, target policy, or synthetic provenance mismatch")

    full_schedule = build_cutoff_schedule(manifest, split_spec)
    schedule = tuple(cutoff_schedule) if cutoff_schedule is not None else full_schedule
    full_by_timestamp = {item.as_of: item for item in full_schedule}
    if not schedule or any(
        item.as_of not in full_by_timestamp or full_by_timestamp[item.as_of] != item
        for item in schedule
    ):
        raise ValueError("selected cutoffs must be exact members of the canonical source schedule")
    if tuple(sorted(schedule, key=lambda item: item.as_of)) != schedule:
        raise ValueError("selected cutoffs must remain in chronological order")
    if {item.split for item in schedule} != set(SplitName):
        raise ValueError("selected cutoffs must include all four chronological splits")
    if cutoff_policy_version is not None and not cutoff_policy_version.strip():
        raise ValueError("cutoff policy version must be non-empty")
    first_cutoff = schedule[0].as_of
    freeze_by_split: dict[SplitName, datetime] = {}
    for item in schedule:
        freeze_by_split[item.split] = item.label_freeze
    boundaries = TemporalSplitBoundaries(
        train_start=first_cutoff,
        train_end=freeze_by_split[SplitName.TRAIN],
        validation_end=freeze_by_split[SplitName.VALIDATION],
        calibration_end=freeze_by_split[SplitName.CALIBRATION],
        test_end=_utc_midnight(manifest["end_date"], "dataset.end_date"),
    )
    if not (boundaries.train_end < boundaries.validation_end < boundaries.calibration_end < boundaries.test_end):
        raise ValueError("maturity freezes are not four ordered, non-overlapping chronological stages")

    tenant_id = adapter.tenant_id
    customers_path = dataset_path / "customers.csv"
    with customers_path.open(encoding="utf-8", newline="") as source:
        tenant_customers = sorted({
            row["customer_id"]
            for row in csv.DictReader(source)
            if row.get("tenant_id") == tenant_id and row.get("customer_id")
        })
    if not tenant_customers:
        raise ValueError("no tenant-scoped customer identities were present in the dataset artifact")

    run = _PreparedRun()
    feature_builder = FeatureBuilder(adapter, config=adapter.feature_builder_config())
    eligibility_policy = adapter.synthetic_eligibility_policy()
    maturity_lag = int(split_spec["label_maturity_lag_days"])
    label_config = LabelBuilderConfig(
        label_policy_version=str(manifest["target_policy_version"]),
        availability_policy=adapter.availability_policy,
    )
    source_db = adapter.database_path
    db_hash_before = _sha256_file(source_db)

    for cutoff_index, cutoff in enumerate(schedule, start=1):
        stage_key = SPLIT_STAGE_KEY[cutoff.split]
        cutoff_name = cutoff.as_of.date().isoformat()
        stage_eligibility = run.cutoff_eligibility[cutoff.split.value]
        for customer_id in tenant_customers:
            run.candidate_pairs += 1
            t0 = time_module.perf_counter()
            prediction_snapshot = adapter.snapshot_for(tenant_id, customer_id, cutoff.as_of)
            run.timings["point_in_time_snapshot_seconds"] += time_module.perf_counter() - t0
            if not prediction_snapshot.subscriptions:
                run.no_lifecycle_history += 1
                continue
            run.lifecycle_snapshots += 1
            eligibility = adapter.eligibility_from_snapshot(prediction_snapshot, policy=eligibility_policy)
            state = eligibility.state.value
            stage_eligibility[state] += 1
            run.overall_eligibility[state] += 1
            eval_cutoffs = {
                horizon: label_evaluation_cutoff(
                    cutoff.as_of, horizon, cutoff.label_freeze, maturity_lag
                )
                for horizon in (7, 14, 30)
            }

            outcome_snapshot = None
            feature_snapshot = None
            freshness = None
            reliability = None
            usage_coverage = ()
            if eligibility.state is EligibilityState.ELIGIBLE:
                t0 = time_module.perf_counter()
                usage_coverage = adapter.coverage_records_for(tenant_id, customer_id, cutoff.as_of)
                feature_snapshot = feature_builder.build_from_point_in_time(
                    prediction_snapshot, usage_coverage=usage_coverage
                )
                run.timings["feature_build_seconds"] += time_module.perf_counter() - t0

                t0 = time_module.perf_counter()
                evidence = adapter.freshness_evidence_from(prediction_snapshot, usage_coverage)
                freshness = assess_data_freshness(
                    tenant_id, customer_id, cutoff.as_of, evidence, evaluated_at=cutoff.as_of
                )
                reliability = assess_reliability(
                    eligibility, feature_snapshot, freshness, evaluated_at=cutoff.as_of
                )
                run.timings["quality_assessment_seconds"] += time_module.perf_counter() - t0
                run.reliability[reliability.status.value] += 1
                run.freshness[freshness.status.value] += 1
                for source_assessment in freshness.source_assessments:
                    run.freshness_by_source[
                        f"{source_assessment.source}:{source_assessment.status.value}"
                    ] += 1
                for reason in freshness.reason_codes:
                    run.freshness_reasons[reason.value] += 1
                for reason in reliability.reason_codes:
                    run.reliability_reasons[reason.value] += 1
                run.coverage[feature_snapshot.data_quality.usage_coverage_status.value] += 1
                run.baseline[feature_snapshot.data_quality.personal_baseline_status.value] += 1
                for feature_name, is_missing in feature_snapshot.data_quality.missingness.items():
                    if is_missing:
                        run.feature_missingness[feature_name] += 1

                t0 = time_module.perf_counter()
                outcome_snapshot = adapter.outcome_snapshot_for(
                    tenant_id, customer_id, cutoff.as_of, cutoff.label_freeze
                )
                run.timings["outcome_read_seconds"] += time_module.perf_counter() - t0

            labels: list[ChurnLabel] = []
            label_outcomes: list[LifecycleOutcomeSnapshot] = []
            for horizon in (7, 14, 30):
                cached = _CachedLifecycleOutcomeAdapter(
                    prediction_snapshot,
                    outcome_snapshot,
                    horizon_days=horizon,
                    maturity_lag_days=maturity_lag,
                )
                builder = ChurnLabelBuilder(
                    cached,
                    config=label_config,
                    eligibility_policy=eligibility_policy,
                )
                t0 = time_module.perf_counter()
                built = builder.build_labels(
                    tenant_id,
                    customer_id,
                    cutoff.as_of,
                    eval_cutoffs[horizon],
                    label_generated_at=eval_cutoffs[horizon],
                )
                run.timings["label_build_seconds"] += time_module.perf_counter() - t0
                selected = next(item for item in built if item.horizon_days == horizon)
                labels.append(selected)
                run.label_statuses[str(horizon)][selected.label_status.value] += 1
                for reason in selected.reason_codes:
                    run.label_reasons[str(horizon)][reason.value] += 1
                if selected.label_status is LabelStatus.UNKNOWN:
                    run.label_evidence_missingness[selected.reason_codes[0].value if selected.reason_codes else "unknown_reason"] += 1
                label_outcomes.append(cached.outcome_snapshot_for(
                    tenant_id, customer_id, cutoff.as_of, eval_cutoffs[horizon]
                ))
                for observation in label_outcomes[-1].observations:
                    run.outcome_coverage[str(horizon)][
                        f"{observation.source_category}:{observation.coverage_status}"
                    ] += 1

            if feature_snapshot is None:
                continue
            snapshot_id = f"{tenant_id}:{customer_id}:{cutoff.as_of.isoformat()}"
            record = SnapshotRecord(
                snapshot_id=snapshot_id,
                feature_snapshot=feature_snapshot,
                labels=tuple(labels),
                prediction_eligible=True,
            )
            run.records.append(record)
            all_label_outcomes = tuple(
                fact
                for outcome in label_outcomes
                for fact in (*outcome.subscription_facts,)
            )
            outcome_union = LifecycleOutcomeSnapshot(
                tenant_id=tenant_id,
                customer_id=customer_id,
                prediction_as_of=cutoff.as_of,
                evaluation_as_of=max(eval_cutoffs.values()),
                subscription_facts=tuple({fact.record_id: fact for fact in all_label_outcomes}.values()),
                observations=tuple({
                    observation.observation_id: observation
                    for outcome in label_outcomes for observation in outcome.observations
                }.values()),
            )
            run.auxiliary[record.stable_snapshot_id] = {
                "eligibility_state": state,
                "freshness": freshness.model_dump(mode="json"),
                "reliability": reliability.model_dump(mode="json"),
                "feature_quality": feature_snapshot.data_quality.model_dump(mode="json"),
                "feature_version": feature_snapshot.feature_version,
                "evidence_provenance_by_ref": _evidence_availability(
                    feature_snapshot,
                    prediction_snapshot,
                    usage_coverage,
                    labels,
                    outcome_union,
                ),
                "label_evaluation_as_of": {
                    str(h): eval_cutoffs[h].isoformat().replace("+00:00", "Z")
                    for h in (7, 14, 30)
                },
            }
        run.cutoffs_processed += 1
        if progress_callback is not None:
            progress_callback({
                "cutoff_index": cutoff_index,
                "cutoff_count": len(schedule),
                "as_of_date": cutoff_name,
                "stage": cutoff.split.value,
                "candidate_pairs_processed": run.candidate_pairs,
                "historical_snapshots": run.lifecycle_snapshots,
                "eligible_snapshots": len(run.records),
            })

    split_policy_version = (
        f"synthetic-saas-v1.2-{cutoff_policy_version}-maturity-v1"
        if cutoff_policy_version
        else "synthetic-saas-v1.2-weekly-maturity-v1"
    )
    split_config = TemporalSplitConfig(
        boundaries=boundaries,
        split_policy_version=split_policy_version,
        dataset_identifier=adapter.provenance.dataset_id,
        authorized_dataset=False,
        maturity_gap=timedelta(0),
        minimum_samples_per_horizon=2,
    )
    split_result = TemporalSplitter(split_config).split(run.records)
    partition_summary = _partition_summary(split_result, run.auxiliary)
    class_minimums = split_spec.get("cohort_label_audit", {}).get("minimum_class_coverage", {})
    horizon_summary = _horizon_summary(
        run.records,
        run.lifecycle_snapshots,
        run.cutoff_eligibility,
        split_result,
        class_minimums,
        run.label_reasons,
        run.outcome_coverage,
    )
    if any(run.overall_eligibility.get(key, 0) for key in (
        EligibilityState.KNOWN_CANCELLATION.value,
        EligibilityState.NOT_ELIGIBLE.value,
        EligibilityState.INSUFFICIENT_DATA.value,
    )):
        # The splitter sees only prospective eligible snapshots by design;
        # these counts preserve the full historical population denominator.
        pass

    artifact_stats: dict[str, Any] = {}
    for split_name in SplitName:
        partition = split_result.partition(split_name)
        def feature_rows():
            for record in partition.snapshots:
                aux = run.auxiliary[record.stable_snapshot_id]
                yield {
                    "snapshot_id": record.stable_snapshot_id,
                    "tenant_id": record.feature_snapshot.tenant_id,
                    "customer_id": record.feature_snapshot.customer_id,
                    "as_of": record.feature_snapshot.as_of.isoformat().replace("+00:00", "Z"),
                    "split": split_name.value,
                    "prediction_eligibility": aux["eligibility_state"],
                    "feature_version": record.feature_snapshot.feature_version,
                    "feature_values": record.feature_snapshot.feature_values.model_dump(mode="json"),
                    "feature_quality": aux["feature_quality"],
                    "feature_source_evidence_refs": list(record.feature_snapshot.source_evidence_refs),
                    "freshness": aux["freshness"],
                    "reliability": aux["reliability"],
                    "label_evaluation_as_of": aux["label_evaluation_as_of"],
                    "evidence_provenance_by_ref": aux["evidence_provenance_by_ref"],
                }

        def label_rows():
            for record in partition.snapshots:
                for label in record.labels:
                    yield {
                        "snapshot_id": record.stable_snapshot_id,
                        "tenant_id": label.tenant_id,
                        "customer_id": label.customer_id,
                        "as_of": label.as_of.isoformat().replace("+00:00", "Z"),
                        "horizon_days": label.horizon_days,
                        "label": label.label,
                        "label_status": label.label_status.value,
                        "churn_type": label.churn_type.value if label.churn_type else None,
                        "churn_effective_at": label.churn_effective_at.isoformat().replace("+00:00", "Z") if label.churn_effective_at else None,
                        "evaluation_as_of": label.evaluation_as_of.isoformat().replace("+00:00", "Z"),
                        "label_observed_through": label.label_observed_through.isoformat().replace("+00:00", "Z"),
                        "label_policy_version": label.label_policy_version,
                        "source_evidence_refs": list(label.source_evidence_refs),
                        "evidence_provenance_by_ref": {
                            key: value
                            for key, value in run.auxiliary[record.stable_snapshot_id]["evidence_provenance_by_ref"].items()
                            if key in set(label.source_evidence_refs)
                        },
                        "reason_codes": [code.value for code in label.reason_codes],
                        "limitations": list(label.limitations),
                        "label_generated_at": label.label_generated_at.isoformat().replace("+00:00", "Z"),
                        "test_labels_evaluation_only": split_name is SplitName.TEST,
                    }

        artifact_stats[f"{split_name.value.lower()}_features.jsonl.gz"] = _write_jsonl_gzip(
            output_dir / f"{split_name.value.lower()}_features.jsonl.gz", feature_rows()
        )
        artifact_stats[f"{split_name.value.lower()}_labels.jsonl.gz"] = _write_jsonl_gzip(
            output_dir / f"{split_name.value.lower()}_labels.jsonl.gz", label_rows()
        )

    db_hash_after = _sha256_file(source_db)
    db_unchanged = db_hash_before == db_hash_after
    if not db_unchanged:
        raise RuntimeError("source SQLite database checksum changed during read-only preparation")

    windows_by_stage: dict[str, Any] = {}
    for split_name in SplitName:
        source_stage = split_spec["stages"][SPLIT_STAGE_KEY[split_name]]
        items = [item for item in schedule if item.split is split_name]
        windows_by_stage[split_name.value] = {
            "source_cutoff_start_inclusive": source_stage["cutoff_start"],
            "source_cutoff_end_exclusive": source_stage["cutoff_end"],
            "first_scheduled_cutoff": items[0].as_of.isoformat().replace("+00:00", "Z") if items else None,
            "last_scheduled_cutoff": items[-1].as_of.isoformat().replace("+00:00", "Z") if items else None,
            "label_freeze_exclusive": items[0].label_freeze.isoformat().replace("+00:00", "Z") if items else None,
            "cutoff_count": len(items),
        }
    ordered_stages = list(SplitName)
    embargoes: dict[str, Any] = {}
    for left_name, right_name in zip(ordered_stages, ordered_stages[1:]):
        left_items = [item for item in schedule if item.split is left_name]
        right_items = [item for item in schedule if item.split is right_name]
        last_day = left_items[-1].as_of.date()
        first_day = right_items[0].as_of.date()
        interval_weeks = (first_day - last_day).days // 7
        embargoes[f"{left_name.value}_to_{right_name.value}"] = {
            "last_cutoff": last_day.isoformat(),
            "first_next_cutoff": first_day.isoformat(),
            "elapsed_days_between_cutoffs": (first_day - last_day).days,
            "omitted_weekly_cutoff_dates": max(0, interval_weeks - 1),
            "last_stage_label_freeze": left_items[0].label_freeze.isoformat().replace("+00:00", "Z"),
            "maximum_label_horizon_plus_maturity_days": 30 + maturity_lag,
        }
    manifest_out = {
        "preparation_schema_version": "member2-historical-preparation-v1",
        "evidence_provenance": "SYNTHETIC_ONLY",
        "dataset_identity": {
            "dataset_id": manifest["dataset_id"],
            "dataset_version": manifest["dataset_version"],
            "profile": manifest["profile"],
            "seed": manifest["random_seed"],
            "generator_version": manifest["generator_code_version"],
            "generator_build_revision": manifest["generator_build_revision"],
            "target_policy_version": manifest["target_policy_version"],
            "dataset_manifest_sha256": manifest_digest,
            "period_start_inclusive": manifest["start_date"],
            "period_end_exclusive": manifest["end_date"],
        },
        "tenant_scope": {
            "tenant_id_from_authenticated_principal": tenant_id,
            "customer_identity_count": len(tenant_customers),
            "authorized_tenant_count": 1,
            "other_dataset_tenants_accessed": False,
        },
        "feature_policy": {
            "feature_version": feature_builder.config.feature_version,
            "usage_quantity_semantics": "usage_aggregate_updated.quantity counts sessions; active days count distinct represented UTC dates",
            "baseline_window": split_spec["sampling_policy"]["personal_baseline"],
            "coverage_missingness": "unknown or incomplete coverage is retained; absence is never converted to zero activity",
            "feature_cutoff": "only records visible by occurred_at and source_available_at, falling back to received_at under Member 1 policy",
        },
        "label_policy": {
            "version": manifest["target_policy_version"],
            "definition": "source-backed effective loss of final paid entitlement; partial subscription termination is not account churn",
            "maturity_lag_days": maturity_lag,
            "evaluation_cutoffs": "per horizon, min(stage label freeze, as_of + horizon + maturity lag)",
            "negative_maturity": "horizon must have elapsed and complete subscription coverage must be available by the maturity cutoff",
            "unknown_labels_retained": True,
            "post_cutoff_outcomes_used_for_features": False,
        },
        "historical_cutoff_policy": {
            "frequency": "weekly" if len(schedule) == len(full_schedule) else "predeclared_subset_of_weekly",
            "cutoff_utc": "Monday 12:00:00Z",
            "warmup_days": split_spec["sampling_policy"]["warmup_days"],
            "policy_version": cutoff_policy_version or "source-weekly-schedule-v1",
            "source_schedule_cutoff_count": len(full_schedule),
            "selected_cutoff_count": len(schedule),
            "selection_rule": (
                "all source weekly cutoffs"
                if len(schedule) == len(full_schedule)
                else "evenly spaced by chronological index within each frozen split; no outcome values inspected"
            ),
            "cutoff_windows": windows_by_stage,
            "source_split_manifest_sha256": hashlib.sha256((dataset_path / "split_manifest.json").read_bytes()).hexdigest(),
        },
        "temporal_split": {
            "policy_version": split_config.split_policy_version,
            "boundary_semantics": "half-open chronological intervals; stage label freezes from dataset split manifest",
            "label_maturity_gap_days": 0,
            "explicit_embargo_gaps": embargoes,
            "maturity_freeze_boundaries": boundaries.model_dump(mode="json"),
            "account_overlap_summary": split_result.manifest.account_overlap_summary,
            "test_outcomes_used_for_fit_or_model_selection": False,
            "test_labels_available_for_evaluation_only": True,
        },
        "population_counts": {
            "candidate_customer_cutoff_pairs": run.candidate_pairs,
            "historical_snapshots_with_subscription_lifecycle_evidence": run.lifecycle_snapshots,
            "without_subscription_lifecycle_evidence": run.no_lifecycle_history,
            "eligible_snapshots_prepared": len(run.records),
            "eligibility_state_counts_by_stage": {
                stage: _enum_counts(counter) for stage, counter in sorted(run.cutoff_eligibility.items())
            },
            "eligibility_state_counts_total": _enum_counts(run.overall_eligibility),
        },
        "horizons": horizon_summary,
        "partitions": partition_summary,
        "feature_quality_counts": {
            "reliability_status": _enum_counts(run.reliability),
            "freshness_status": _enum_counts(run.freshness),
            "freshness_by_source_status": _enum_counts(run.freshness_by_source),
            "freshness_reason_counts": _enum_counts(run.freshness_reasons),
            "reliability_reason_counts": _enum_counts(run.reliability_reasons),
            "usage_coverage_status": _enum_counts(run.coverage),
            "personal_baseline_status": _enum_counts(run.baseline),
            "feature_missingness_true_counts": _enum_counts(run.feature_missingness),
            "unknown_label_reason_counts": _enum_counts(run.label_evidence_missingness),
            "abstention_eligible_count": sum(
                aux["reliability"]["abstention_required"] for aux in run.auxiliary.values()
            ),
            "abstention_eligible_percentage": (
                100 * sum(aux["reliability"]["abstention_required"] for aux in run.auxiliary.values()) / len(run.auxiliary)
                if run.auxiliary else None
            ),
        },
        "label_coverage_by_horizon_for_eligible_snapshots": {
            horizon: _enum_counts(counts) for horizon, counts in sorted(run.label_statuses.items())
        },
        "temporal_split_manifest": split_result.manifest.model_dump(mode="json"),
        "artifact_checksums": artifact_stats,
        "reproducibility": {
            "status": "DETERMINISTIC_ARTIFACTS_FOR_IDENTICAL_DATASET_CODE_AND_CONFIGURATION",
            "gzip_mtime_zero": True,
            "rows_sorted_by_as_of_tenant_customer_snapshot_and_horizon": True,
            "customer_level_artifacts_outside_repository": True,
            "source_sqlite_sha256_before": db_hash_before,
            "source_sqlite_sha256_after": db_hash_after,
            "source_database_unchanged": db_unchanged,
        },
        "readiness": {
            "real_dataset_readiness": "BLOCKED_SYNTHETIC_ONLY",
            "downstream_scoring_readiness": "BLOCKED_NO_MODEL_TRAINED",
            "synthetic_training_by_horizon": {
                horizon: details["synthetic_training_readiness"]
                for horizon, details in horizon_summary.items()
            },
            "dataset_declared_class_minimums": class_minimums,
        },
        "software": {
            "python": platform.python_version(),
            "retainiq_prediction_package": "0.1.0",
            "pydantic": importlib.metadata.version("pydantic"),
            "sqlite_library": sqlite3.sqlite_version,
            "platform": platform.platform(),
        },
    }
    manifest_file = output_dir / "preparation_manifest.json"
    manifest_file.write_text(
        json.dumps(manifest_out, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_hash = _sha256_file(manifest_file)
    (output_dir / "preparation_manifest.sha256").write_text(
        f"{manifest_hash}  preparation_manifest.json\n", encoding="ascii", newline="\n"
    )

    elapsed = time_module.perf_counter() - started
    api_counts = dict(sorted((reader_api_call_counts or {}).items()))
    label_count = len(run.records) * 3
    metrics = {
        "elapsed_seconds": round(elapsed, 3),
        "candidate_customer_cutoff_pairs": run.candidate_pairs,
        "historical_snapshots": run.lifecycle_snapshots,
        "eligible_feature_snapshots": len(run.records),
        "labels_constructed": label_count,
        "snapshot_pairs_per_second": round(run.candidate_pairs / elapsed, 3) if elapsed else None,
        "eligible_snapshots_per_second": round(len(run.records) / elapsed, 3) if elapsed else None,
        "labels_per_second": round(label_count / elapsed, 3) if elapsed else None,
        "peak_working_set_bytes": _peak_memory_bytes(),
        "member1_reader_api_calls": api_counts,
        "phase_seconds": {key: round(value, 3) for key, value in sorted(run.timings.items())},
    }
    (output_dir / "preparation_run_metrics.json").write_text(
        json.dumps(metrics, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest_out, metrics


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--token-env", default="RETAINIQ_MODEL_TOKEN")
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env)
    if not token:
        parser.error(f"environment variable {args.token_env} is required")
    try:
        principal = authenticate_service_principal(args.db, token)
        adapter = SQLiteDataAdapter(args.db, args.dataset, principal)
        counter = _CountingReaderAPI(adapter.reader_api)
        adapter.reader_api = counter

        def progress(item: Mapping[str, Any]) -> None:
            index = int(item["cutoff_index"])
            count = int(item["cutoff_count"])
            if index == 1 or index == count or index % 5 == 0:
                print(json.dumps({"progress": item}, sort_keys=True), flush=True)

        manifest, metrics = prepare_historical_dataset(
            adapter,
            args.dataset,
            args.output_dir,
            reader_api_call_counts=counter.counts,
            progress_callback=progress,
        )
        print(json.dumps({
            "status": "PASS",
            "dataset_id": manifest["dataset_identity"]["dataset_id"],
            "tenant_id": manifest["tenant_scope"]["tenant_id_from_authenticated_principal"],
            "snapshot_count": manifest["population_counts"]["historical_snapshots_with_subscription_lifecycle_evidence"],
            "eligible_snapshots": manifest["population_counts"]["eligible_snapshots_prepared"],
            "elapsed_seconds": metrics["elapsed_seconds"],
            "manifest_sha256": _sha256_file(args.output_dir / "preparation_manifest.json"),
        }, sort_keys=True), flush=True)
        return 0
    except (OSError, ValueError, DataFoundationError, KeyError, RuntimeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "Cutoff",
    "build_cutoff_schedule",
    "label_evaluation_cutoff",
    "prepare_historical_dataset",
    "select_predeclared_cutoffs",
]
