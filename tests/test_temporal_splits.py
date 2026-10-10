from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from retainiq_prediction import (
    ChurnLabel,
    ChurnType,
    FeatureQuality,
    FeatureSnapshot,
    FeatureValues,
    LabelStatus,
    PersonalBaselineStatus,
    SnapshotRecord,
    SplitName,
    TemporalSplitBoundaries,
    TemporalSplitConfig,
    TemporalSplitter,
    UsageCoverageStatus,
)
from retainiq_prediction.dataset_readiness import DatasetStatus


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


BOUNDARIES = TemporalSplitBoundaries(
    train_start=at(0),
    train_end=at(10),
    validation_end=at(20),
    calibration_end=at(30),
    test_end=at(40),
)


def feature_snapshot(day: int, customer_id: str = "customer-a") -> FeatureSnapshot:
    cutoff = at(day)
    return FeatureSnapshot(
        tenant_id="tenant-a",
        customer_id=customer_id,
        as_of=cutoff,
        feature_version="features_test_v1",
        data_cutoff_at=cutoff,
        feature_values=FeatureValues(
            personal_baseline_availability_status=PersonalBaselineStatus.UNAVAILABLE
        ),
        data_quality=FeatureQuality(
            usage_coverage_status=UsageCoverageStatus.UNKNOWN,
            personal_baseline_status=PersonalBaselineStatus.UNAVAILABLE,
            baseline_weeks_requested=4,
        ),
    )


def label(
    as_of_day: int,
    horizon: int,
    *,
    value: int | None,
    evaluation_day: int,
    status: LabelStatus | None = None,
    customer_id: str = "customer-a",
) -> ChurnLabel:
    label_status = status or (
        LabelStatus.POSITIVE if value == 1 else LabelStatus.NEGATIVE
        if value == 0
        else LabelStatus.UNKNOWN
    )
    churn_type = ChurnType.VOLUNTARY_CANCELLATION if value == 1 else None
    churn_at = at(as_of_day + 1) if value == 1 else None
    return ChurnLabel(
        tenant_id="tenant-a",
        customer_id=customer_id,
        as_of=at(as_of_day),
        evaluation_as_of=at(evaluation_day),
        horizon_days=horizon,  # type: ignore[arg-type]
        label=value,  # type: ignore[arg-type]
        label_status=label_status,
        churn_type=churn_type,
        churn_effective_at=churn_at,
        label_observed_through=at(evaluation_day),
        label_policy_version="labels_test_v1",
        source_evidence_refs=(f"evidence-{as_of_day}-{horizon}",),
        label_generated_at=at(evaluation_day),
    )


def record(
    as_of_day: int,
    *,
    customer_id: str = "customer-a",
    evaluation_day: int | None = None,
    values: tuple[int | None, int | None, int | None] = (0, 0, 0),
    statuses: tuple[LabelStatus | None, LabelStatus | None, LabelStatus | None] = (
        None,
        None,
        None,
    ),
    snapshot_id: str | None = None,
    prediction_eligible: bool = True,
) -> SnapshotRecord:
    resolved_evaluation_day = (
        as_of_day + 5 if evaluation_day is None else evaluation_day
    )
    labels = tuple(
        label(
            as_of_day,
            horizon,
            value=value,
            evaluation_day=resolved_evaluation_day,
            status=status,
            customer_id=customer_id,
        )
        for horizon, value, status in zip((7, 14, 30), values, statuses)
    )
    return SnapshotRecord(
        snapshot_id=snapshot_id,
        feature_snapshot=feature_snapshot(as_of_day, customer_id),
        labels=labels,
        prediction_eligible=prediction_eligible,
    )


def splitter(*, authorized_dataset: bool = False, minimum_samples: int = 2):
    return TemporalSplitter(
        TemporalSplitConfig(
            boundaries=BOUNDARIES,
            dataset_identifier="synthetic-fixture",
            authorized_dataset=authorized_dataset,
            minimum_samples_per_horizon=minimum_samples,
        )
    )


def test_correct_chronological_assignment_and_boundary_semantics():
    records = [
        record(0),
        record(9),
        record(10),
        record(19),
        record(20),
        record(29),
        record(30),
        record(39),
    ]
    result = splitter().split(records)

    assert [row.feature_snapshot.as_of for row in result.partition(SplitName.TRAIN).snapshots] == [
        at(0),
        at(9),
    ]
    assert [row.feature_snapshot.as_of for row in result.partition(SplitName.VALIDATION).snapshots] == [
        at(10),
        at(19),
    ]
    assert [row.feature_snapshot.as_of for row in result.partition(SplitName.CALIBRATION).snapshots] == [
        at(20),
        at(29),
    ]
    assert [row.feature_snapshot.as_of for row in result.partition(SplitName.TEST).snapshots] == [
        at(30),
        at(39),
    ]


def test_boundaries_are_non_overlapping_and_timezone_aware():
    with pytest.raises(ValidationError):
        TemporalSplitBoundaries(
            train_end=datetime(2026, 10, 11),
            validation_end=at(20),
            calibration_end=at(30),
        )
    with pytest.raises(ValidationError):
        TemporalSplitBoundaries(
            train_end=at(20),
            validation_end=at(10),
            calibration_end=at(30),
        )


def test_partitioning_is_deterministic():
    records = [record(9, customer_id="customer-b"), record(1), record(15)]
    first = splitter().split(records)
    second = splitter().split(list(reversed(records)))

    for partition in SplitName:
        assert [item.stable_snapshot_id for item in first.partition(partition).snapshots] == [
            item.stable_snapshot_id for item in second.partition(partition).snapshots
        ]
    assert first.manifest.model_dump(mode="json") == second.manifest.model_dump(mode="json")


def test_all_horizons_for_one_snapshot_stay_in_one_partition():
    row = record(5)
    result = splitter().split([row])
    train = result.partition(SplitName.TRAIN)

    assert len(train.snapshots) == 1
    assert result.partition(SplitName.VALIDATION).snapshots == ()
    assert train.supervised_snapshot_ids_by_horizon[7] == (row.stable_snapshot_id,)
    assert train.supervised_snapshot_ids_by_horizon[14] == (row.stable_snapshot_id,)
    assert train.supervised_snapshot_ids_by_horizon[30] == (row.stable_snapshot_id,)


def test_unknown_labels_are_excluded_per_horizon_without_becoming_zero():
    row = record(
        5,
        values=(1, None, 0),
        statuses=(LabelStatus.POSITIVE, LabelStatus.UNKNOWN, LabelStatus.NEGATIVE),
        evaluation_day=6,
    )
    result = splitter().split([row])
    train = result.partition(SplitName.TRAIN)

    assert train.supervised_snapshot_ids_by_horizon[7] == (row.stable_snapshot_id,)
    assert train.supervised_snapshot_ids_by_horizon[14] == ()
    assert train.supervised_snapshot_ids_by_horizon[30] == (row.stable_snapshot_id,)
    assert result.manifest.unknown_label_counts[SplitName.TRAIN.value][14] == 1


def test_labels_maturing_after_training_freeze_are_excluded():
    row = record(9, evaluation_day=11, values=(1, 1, 1))
    result = splitter().split([row])

    assert result.supervised_snapshot_ids(SplitName.TRAIN, 7) == ()
    assert result.manifest.label_maturity_exclusions[SplitName.TRAIN.value][7] == 1


def test_negative_labels_require_maturity_for_their_own_horizon():
    row = record(5, evaluation_day=12, values=(0, 0, 0))
    result = splitter().split([row])

    assert result.supervised_snapshot_ids(SplitName.TRAIN, 7) == ()
    assert result.supervised_snapshot_ids(SplitName.TRAIN, 14) == ()
    assert result.supervised_snapshot_ids(SplitName.TRAIN, 30) == ()
    assert result.manifest.label_maturity_exclusions[SplitName.TRAIN.value] == {
        7: 1,
        14: 1,
        30: 1,
    }


def test_test_labels_are_evaluation_only_and_never_training_labels():
    row = record(35, evaluation_day=70, values=(1, 1, 1))
    result = splitter().split([row])

    assert result.partition(SplitName.TEST).evaluation_snapshot_ids_by_horizon[30] == (
        row.stable_snapshot_id,
    )
    assert result.partition(SplitName.TEST).supervised_snapshot_ids_by_horizon[30] == ()
    assert result.manifest.test_labels_deferred_for_evaluation[30] == 1
    assert all(
        row.stable_snapshot_id
        not in result.partition(partition).supervised_snapshot_ids_by_horizon[30]
        for partition in (SplitName.TRAIN, SplitName.VALIDATION, SplitName.CALIBRATION)
    )


def test_repeated_customer_snapshots_are_allowed_and_reported_as_overlap():
    records = [record(5), record(15), record(25), record(35)]
    result = splitter().split(records)

    assert result.manifest.account_overlap_summary["train__validation"] == 1
    assert result.manifest.account_overlap_summary["validation__calibration"] == 1
    assert result.manifest.account_overlap_summary["calibration__test"] == 1


def test_duplicate_snapshot_assignments_are_rejected():
    row = record(5, snapshot_id="duplicate")
    with pytest.raises(ValueError, match="duplicate prediction snapshot"):
        splitter().split([row, row])


def test_insufficient_samples_and_single_class_are_reported():
    result = splitter().split([record(5, values=(1, 1, 1))])
    warnings = result.manifest.insufficient_sample_warnings

    assert any("horizon 7" in warning for warning in warnings)
    assert any("single usable class" in warning for warning in warnings)


def test_missing_dataset_keeps_real_readiness_blocked():
    result = splitter().split([])

    assert result.manifest.dataset_readiness_status is DatasetStatus.BLOCKED
    assert any("No dataset snapshots" in warning for warning in result.manifest.missing_data_warnings)


def test_manifest_contains_reproducible_configuration_and_policy_version():
    result = splitter().split([record(5)])
    manifest = result.manifest

    assert manifest.split_policy_version == "temporal_splits_v1"
    assert manifest.configuration["boundaries"]["train_end"] == at(10).isoformat().replace("+00:00", "Z")
    assert manifest.configuration["maturity_gap_seconds"] == 0
    assert manifest.dataset_readiness_status is DatasetStatus.BLOCKED


def test_maturity_gap_can_make_a_previously_mature_label_unusable():
    config = TemporalSplitConfig(
        boundaries=BOUNDARIES,
        maturity_gap=timedelta(days=2),
        minimum_samples_per_horizon=1,
    )
    row = record(5, evaluation_day=9, values=(1, 1, 1))
    result = TemporalSplitter(config).split([row])

    assert result.supervised_snapshot_ids(SplitName.TRAIN, 7) == ()
    assert result.manifest.label_maturity_exclusions[SplitName.TRAIN.value][7] == 1
