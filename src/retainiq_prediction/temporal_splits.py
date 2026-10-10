"""Deterministic chronological preparation for multi-horizon churn labels.

This module partitions complete prediction snapshots by ``as_of``.  It does
not randomize rows, fit preprocessing, train models, or select thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Iterable, Literal, Mapping

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .dataset_readiness import DatasetStatus
from .feature_builder import FeatureSnapshot
from .label_builder import ChurnLabel, LabelStatus, SUPPORTED_HORIZONS


class SplitName(str, Enum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    CALIBRATION = "CALIBRATION"
    TEST = "TEST"


class _SplitModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemporalSplitBoundaries(_SplitModel):
    """Half-open chronological boundaries: ``[start, end)``."""

    train_start: AwareDatetime | None = None
    train_end: AwareDatetime
    validation_end: AwareDatetime
    calibration_end: AwareDatetime
    test_end: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_order(self) -> "TemporalSplitBoundaries":
        if not self.train_end < self.validation_end < self.calibration_end:
            raise ValueError(
                "boundaries must satisfy train_end < validation_end < calibration_end"
            )
        if self.train_start is not None and self.train_start >= self.train_end:
            raise ValueError("train_start must precede train_end")
        if self.test_end is not None and self.test_end <= self.calibration_end:
            raise ValueError("test_end must follow calibration_end")
        return self


class SnapshotRecord(_SplitModel):
    """One immutable feature snapshot and all of its horizon labels."""

    snapshot_id: str | None = Field(default=None, min_length=1)
    feature_snapshot: FeatureSnapshot
    labels: tuple[ChurnLabel, ...]
    prediction_eligible: bool = True

    @model_validator(mode="after")
    def validate_identity(self) -> "SnapshotRecord":
        feature = self.feature_snapshot
        seen: set[int] = set()
        for label in self.labels:
            if (
                label.tenant_id != feature.tenant_id
                or label.customer_id != feature.customer_id
                or label.as_of != feature.as_of
            ):
                raise ValueError("feature snapshot and labels must share tenant, customer, and as_of")
            if label.horizon_days in seen:
                raise ValueError("one label per horizon is required")
            seen.add(label.horizon_days)
        return self

    @property
    def stable_snapshot_id(self) -> str:
        """Use an explicit ID when supplied, otherwise derive a stable key."""

        return self.snapshot_id or (
            f"{self.feature_snapshot.tenant_id}:"
            f"{self.feature_snapshot.customer_id}:"
            f"{self.feature_snapshot.as_of.isoformat()}"
        )

    @property
    def account_key(self) -> tuple[str, str]:
        return self.feature_snapshot.tenant_id, self.feature_snapshot.customer_id


class TemporalPartition(_SplitModel):
    name: SplitName
    snapshots: tuple[SnapshotRecord, ...] = ()
    supervised_snapshot_ids_by_horizon: dict[int, tuple[str, ...]] = Field(
        default_factory=dict
    )
    evaluation_snapshot_ids_by_horizon: dict[int, tuple[str, ...]] = Field(
        default_factory=dict
    )


class TemporalSplitManifest(_SplitModel):
    dataset_identifier: str | None = None
    split_policy_version: str
    boundaries: TemporalSplitBoundaries
    horizon_usable_label_counts: dict[str, dict[int, int]]
    horizon_evaluation_label_counts: dict[str, dict[int, int]]
    unknown_label_counts: dict[str, dict[int, int]]
    excluded_label_counts: dict[str, dict[int, int]]
    unsupported_label_counts: dict[str, dict[int, int]]
    label_maturity_exclusions: dict[str, dict[int, int]]
    test_labels_deferred_for_evaluation: dict[int, int]
    account_overlap_summary: dict[str, int]
    missing_data_warnings: tuple[str, ...] = ()
    insufficient_sample_warnings: tuple[str, ...] = ()
    dataset_readiness_status: DatasetStatus
    configuration: dict[str, Any]


@dataclass(frozen=True)
class TemporalSplitResult:
    """Partitions plus horizon-specific masks and a reproducible manifest."""

    partitions: Mapping[SplitName, TemporalPartition]
    manifest: TemporalSplitManifest

    def partition(self, name: SplitName | str) -> TemporalPartition:
        return self.partitions[SplitName(name)]

    def supervised_snapshot_ids(
        self, partition: SplitName | str, horizon_days: Literal[7, 14, 30]
    ) -> tuple[str, ...]:
        return self.partition(partition).supervised_snapshot_ids_by_horizon.get(
            horizon_days, ()
        )


@dataclass(frozen=True)
class TemporalSplitConfig:
    boundaries: TemporalSplitBoundaries
    split_policy_version: str = "temporal_splits_v1"
    dataset_identifier: str | None = None
    authorized_dataset: bool = False
    maturity_gap: timedelta = timedelta(0)
    minimum_samples_per_horizon: int = 2

    def __post_init__(self) -> None:
        if not self.split_policy_version.strip():
            raise ValueError("split_policy_version must be non-empty")
        if self.maturity_gap < timedelta(0):
            raise ValueError("maturity_gap must not be negative")
        if self.minimum_samples_per_horizon < 1:
            raise ValueError("minimum_samples_per_horizon must be positive")


def _partition_for(
    as_of: datetime, boundaries: TemporalSplitBoundaries
) -> SplitName:
    if boundaries.train_start is not None and as_of < boundaries.train_start:
        raise ValueError("snapshot as_of precedes train_start")
    if as_of < boundaries.train_end:
        return SplitName.TRAIN
    if as_of < boundaries.validation_end:
        return SplitName.VALIDATION
    if as_of < boundaries.calibration_end:
        return SplitName.CALIBRATION
    if boundaries.test_end is None or as_of < boundaries.test_end:
        return SplitName.TEST
    raise ValueError("snapshot as_of is outside the configured split boundaries")


def _maturity_cutoff(
    partition: SplitName, boundaries: TemporalSplitBoundaries, gap: timedelta
) -> datetime | None:
    if partition is SplitName.TRAIN:
        return boundaries.train_end - gap
    if partition is SplitName.VALIDATION:
        return boundaries.validation_end - gap
    if partition is SplitName.CALIBRATION:
        return boundaries.calibration_end - gap
    # Final test labels may be revealed after the test period, but are never
    # included in the supervised fitting masks.
    return None


def _confirmed(label: ChurnLabel) -> bool:
    return label.label_status in {LabelStatus.POSITIVE, LabelStatus.NEGATIVE} and label.label in {
        0,
        1,
    }


class TemporalSplitter:
    """Assign snapshots chronologically and enforce horizon maturity."""

    def __init__(self, config: TemporalSplitConfig) -> None:
        self.config = config

    def split(self, records: Iterable[SnapshotRecord]) -> TemporalSplitResult:
        records_tuple = tuple(records)
        keyed: dict[str, SnapshotRecord] = {}
        for record in records_tuple:
            snapshot_id = record.stable_snapshot_id
            if snapshot_id in keyed:
                raise ValueError(f"duplicate prediction snapshot assignment: {snapshot_id}")
            _partition_for(record.feature_snapshot.as_of, self.config.boundaries)
            keyed[snapshot_id] = record

        sorted_records = tuple(
            sorted(
                records_tuple,
                key=lambda record: (
                    record.feature_snapshot.as_of,
                    record.account_key,
                    record.stable_snapshot_id,
                ),
            )
        )
        rows_by_partition: dict[SplitName, list[SnapshotRecord]] = {
            name: [] for name in SplitName
        }
        for record in sorted_records:
            rows_by_partition[
                _partition_for(record.feature_snapshot.as_of, self.config.boundaries)
            ].append(record)

        partitions: dict[SplitName, TemporalPartition] = {}
        horizon_usable_counts: dict[str, dict[int, int]] = {}
        horizon_evaluation_counts: dict[str, dict[int, int]] = {}
        unknown_counts: dict[str, dict[int, int]] = {}
        excluded_counts: dict[str, dict[int, int]] = {}
        unsupported_counts: dict[str, dict[int, int]] = {}
        maturity_exclusions: dict[str, dict[int, int]] = {}
        test_deferred: dict[int, int] = {horizon: 0 for horizon in SUPPORTED_HORIZONS}
        missing_warnings: list[str] = []
        insufficient_warnings: list[str] = []

        for partition_name in SplitName:
            partition_records = tuple(rows_by_partition[partition_name])
            maturity_cutoff = _maturity_cutoff(
                partition_name,
                self.config.boundaries,
                self.config.maturity_gap,
            )
            supervised_ids: dict[int, tuple[str, ...]] = {}
            evaluation_ids: dict[int, tuple[str, ...]] = {}
            usable_counts: dict[int, int] = {}
            eval_counts: dict[int, int] = {}
            unknown: dict[int, int] = {}
            excluded: dict[int, int] = {}
            unsupported: dict[int, int] = {}
            mature_excluded: dict[int, int] = {}

            for horizon in SUPPORTED_HORIZONS:
                supervised: list[str] = []
                evaluation: list[str] = []
                unknown_count = 0
                excluded_count = 0
                unsupported_count = 0
                maturity_count = 0
                for record in partition_records:
                    label = next(
                        (item for item in record.labels if item.horizon_days == horizon),
                        None,
                    )
                    if label is None:
                        missing_warnings.append(
                            f"{record.stable_snapshot_id} is missing a {horizon}-day label."
                        )
                        continue
                    if label.label_status is LabelStatus.UNKNOWN:
                        unknown_count += 1
                    elif label.label_status is LabelStatus.EXCLUDED:
                        excluded_count += 1
                    elif label.label_status is LabelStatus.UNSUPPORTED:
                        unsupported_count += 1

                    if not record.prediction_eligible:
                        continue
                    if _confirmed(label):
                        if partition_name is SplitName.TEST:
                            evaluation.append(record.stable_snapshot_id)
                            if label.evaluation_as_of > record.feature_snapshot.as_of:
                                test_deferred[horizon] += 1
                        elif maturity_cutoff is not None and label.evaluation_as_of <= maturity_cutoff:
                            supervised.append(record.stable_snapshot_id)
                        else:
                            maturity_count += 1

                supervised_ids[horizon] = tuple(supervised)
                evaluation_ids[horizon] = tuple(evaluation if partition_name is SplitName.TEST else supervised)
                usable_counts[horizon] = len(supervised)
                eval_counts[horizon] = len(evaluation if partition_name is SplitName.TEST else supervised)
                unknown[horizon] = unknown_count
                excluded[horizon] = excluded_count
                unsupported[horizon] = unsupported_count
                mature_excluded[horizon] = maturity_count

                if partition_name is not SplitName.TEST:
                    if len(supervised) < self.config.minimum_samples_per_horizon:
                        insufficient_warnings.append(
                            f"{partition_name.value} horizon {horizon} has only "
                            f"{len(supervised)} usable matured label(s)."
                        )
                    classes = {
                        next(
                            item.label
                            for item in record.labels
                            if item.horizon_days == horizon
                        )
                        for record in partition_records
                        if record.stable_snapshot_id in supervised
                    }
                    if len(classes) < 2 and supervised:
                        insufficient_warnings.append(
                            f"{partition_name.value} horizon {horizon} has a single usable class."
                        )

            partitions[partition_name] = TemporalPartition(
                name=partition_name,
                snapshots=partition_records,
                supervised_snapshot_ids_by_horizon=supervised_ids,
                evaluation_snapshot_ids_by_horizon=evaluation_ids,
            )
            horizon_usable_counts[partition_name.value] = usable_counts
            horizon_evaluation_counts[partition_name.value] = eval_counts
            unknown_counts[partition_name.value] = unknown
            excluded_counts[partition_name.value] = excluded
            unsupported_counts[partition_name.value] = unsupported
            maturity_exclusions[partition_name.value] = mature_excluded

        if not records_tuple:
            missing_warnings.append("No dataset snapshots were supplied.")

        overlap_summary = self._account_overlap_summary(partitions)
        readiness = (
            DatasetStatus.BLOCKED
            if not records_tuple or not self.config.authorized_dataset
            else DatasetStatus.PARTIAL
        )
        if not self.config.authorized_dataset:
            missing_warnings.append(
                "No authorized real dataset was declared; training readiness remains BLOCKED."
            )
        else:
            missing_warnings.append(
                "Temporal splitting alone does not establish full dataset readiness."
            )

        manifest = TemporalSplitManifest(
            dataset_identifier=self.config.dataset_identifier,
            split_policy_version=self.config.split_policy_version,
            boundaries=self.config.boundaries,
            horizon_usable_label_counts=horizon_usable_counts,
            horizon_evaluation_label_counts=horizon_evaluation_counts,
            unknown_label_counts=unknown_counts,
            excluded_label_counts=excluded_counts,
            unsupported_label_counts=unsupported_counts,
            label_maturity_exclusions=maturity_exclusions,
            test_labels_deferred_for_evaluation=test_deferred,
            account_overlap_summary=overlap_summary,
            missing_data_warnings=tuple(dict.fromkeys(missing_warnings)),
            insufficient_sample_warnings=tuple(dict.fromkeys(insufficient_warnings)),
            dataset_readiness_status=readiness,
            configuration={
                "dataset_identifier": self.config.dataset_identifier,
                "authorized_dataset": self.config.authorized_dataset,
                "split_policy_version": self.config.split_policy_version,
                "maturity_gap_seconds": int(self.config.maturity_gap.total_seconds()),
                "minimum_samples_per_horizon": self.config.minimum_samples_per_horizon,
                "boundaries": self.config.boundaries.model_dump(mode="json"),
            },
        )
        return TemporalSplitResult(partitions=partitions, manifest=manifest)

    @staticmethod
    def _account_overlap_summary(
        partitions: Mapping[SplitName, TemporalPartition]
    ) -> dict[str, int]:
        account_sets = {
            name: {record.account_key for record in partition.snapshots}
            for name, partition in partitions.items()
        }
        summary: dict[str, int] = {}
        names = tuple(SplitName)
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                summary[f"{left.value.lower()}__{right.value.lower()}"] = len(
                    account_sets[left] & account_sets[right]
                )
        return summary


__all__ = [
    "SnapshotRecord",
    "SplitName",
    "TemporalPartition",
    "TemporalSplitBoundaries",
    "TemporalSplitConfig",
    "TemporalSplitManifest",
    "TemporalSplitResult",
    "TemporalSplitter",
]
