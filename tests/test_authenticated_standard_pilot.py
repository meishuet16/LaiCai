"""Offline structural tests for the authenticated STANDARD pilot runner.

All records here are synthetic fixtures. Live DPAPI authentication is exercised
only by the explicitly wrapped local pilot, never during ordinary test collection.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.member2_authenticated_standard_pilot import (
    EXPECTED_SOURCE_CATEGORIES,
    PilotError,
    TimedReaderAPI,
    _assert_no_unauthorized_valuation,
    _connection_state,
    assert_facts_available_by,
    authenticate_reader,
    require_reader_token,
    run_bounded_pilot,
    select_development_cutoffs,
    select_tenant_customer_ids,
    validate_dataset_files,
    validate_reader_principal,
)
from retainiq_prediction.data_freshness import FreshnessSource, SourceFreshnessEvidence
from retainiq_prediction.eligibility import EligibilityPolicy, evaluate_prediction_eligibility
from retainiq_prediction.feature_builder import FeatureBuilderConfig
from retainiq_prediction.historical_dataset_preparation import Cutoff
from retainiq_prediction.label_builder import LifecycleOutcomeSnapshot
from retainiq_prediction.point_in_time import (
    AvailabilityPolicy,
    PointInTimeSnapshot,
    SubscriptionFact,
)


UTC = timezone.utc
FIXTURE_DATASET_ID = "synthetic-pilot-fixture"


def _fixture_files(root: Path) -> tuple[dict, dict, str]:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset_id": FIXTURE_DATASET_ID,
        "dataset_type": "synthetic_saas",
        "dataset_version": "1.2.0",
        "generator_code_version": "synthetic-test",
        "target_policy_version": "effective-account-churn-v1.2",
        "no_real_customer_data": True,
        "start_date": "2024-10-01",
        "end_date": "2025-12-01",
        "end_date_exclusive": True,
    }
    split_manifest = {
        "dataset_id": FIXTURE_DATASET_ID,
        "label_maturity_lag_days": 8,
        "maximum_horizon_days": 30,
        "sampling_policy": {
            "frequency": "weekly",
            "cutoff_utc": "Monday 12:00:00Z",
            "warmup_days": 63,
        },
        "stages": {
            "train": {"cutoff_start": "2024-12-01", "cutoff_end": "2024-12-22", "mature_before": "2025-02-01"},
            "development": {"cutoff_start": "2025-03-01", "cutoff_end": "2025-03-16", "mature_before": "2025-05-01"},
            "calibration": {"cutoff_start": "2025-06-01", "cutoff_end": "2025-06-15", "mature_before": "2025-08-01"},
            "untouched_test": {"cutoff_start": "2025-09-01", "cutoff_end": "2025-09-16", "mature_before": "2025-11-01"},
        },
    }
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    (root / "dataset_manifest.json").write_bytes(raw)
    (root / "split_manifest.json").write_text(json.dumps(split_manifest), encoding="utf-8")
    (root / "customers.csv").write_text(
        "tenant_id,customer_id\n"
        "tenant-01,customer-a\n"
        "tenant-01,customer-b\n"
        "tenant-01,customer-c\n"
        "tenant-01,customer-d\n"
        "tenant-02,customer-other\n",
        encoding="utf-8",
    )
    return manifest, split_manifest, hashlib.sha256(raw).hexdigest()


class _FakeAdapter:
    tenant_id = "tenant-01"
    availability_policy = AvailabilityPolicy.SOURCE_THEN_RECEIVED

    def __init__(self, dataset_id: str, manifest_sha256: str):
        self.provenance = SimpleNamespace(dataset_id=dataset_id, manifest_sha256=manifest_sha256)
        self.database_path = Path("synthetic-read-only.sqlite3")
        self.snapshots_seen = []
        self.outcome_cutoffs = []

    @staticmethod
    def _fact(customer_id: str, as_of: datetime) -> SubscriptionFact | None:
        start = as_of - timedelta(days=90)
        common = {
            "tenant_id": "tenant-01",
            "customer_id": customer_id,
            "source": "tenant-01-synthetic-subscription-v1-2",
            "subscription_id": "synthetic-subscription",
            "occurred_at": start,
            "source_available_at": start,
            "received_at": start,
            "is_paying": True,
        }
        if customer_id == "customer-d":
            return None
        if customer_id == "customer-b":
            return SubscriptionFact(
                record_id="synthetic-known-cancel", event_type="cancellation_requested",
                status="pending_cancel", cancellation_requested_at=as_of - timedelta(days=1),
                **common,
            )
        if customer_id == "customer-c":
            ended = as_of - timedelta(days=2)
            return SubscriptionFact(
                record_id="synthetic-ended", event_type="subscription_cancelled_effective",
                status="ended", is_paying=False, occurred_at=ended,
                effective_at=ended, source_available_at=ended, received_at=ended,
                tenant_id="tenant-01", customer_id=customer_id,
                source="tenant-01-synthetic-subscription-v1-2",
                subscription_id="synthetic-subscription",
            )
        return SubscriptionFact(
            record_id="synthetic-active", event_type="subscription_created",
            status="active", **common,
        )

    def snapshot_for(self, tenant_id: str, customer_id: str, as_of: datetime):
        self.snapshots_seen.append((customer_id, as_of))
        fact = self._fact(customer_id, as_of)
        return PointInTimeSnapshot(
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=as_of,
            availability_policy=self.availability_policy,
            subscriptions=(fact,) if fact is not None else (),
        )

    @staticmethod
    def synthetic_eligibility_policy():
        return EligibilityPolicy(
            active_statuses=frozenset({"active", "past_due", "pending_cancel"}),
            terminal_statuses=frozenset({"ended", "cancelled", "terminated", "expired"}),
            account_churn_policy="effective-account-churn-v1.2-synthetic-only",
        )

    def eligibility_from_snapshot(self, snapshot, *, policy=None):
        return evaluate_prediction_eligibility(snapshot, policy=policy)

    @staticmethod
    def feature_builder_config():
        return FeatureBuilderConfig()

    @staticmethod
    def coverage_records_for(tenant_id, customer_id, as_of):
        return ()

    @staticmethod
    def freshness_evidence_from(snapshot, coverage):
        return tuple(
            SourceFreshnessEvidence(
                tenant_id=snapshot.tenant_id,
                customer_id=snapshot.customer_id,
                source=source,
                connected=None,
                complete=None,
            )
            for source in (
                FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
                FreshnessSource.BILLING_EVENTS.value,
                FreshnessSource.USAGE_COVERAGE.value,
            )
        )

    def outcome_snapshot_for(self, tenant_id, customer_id, prediction_as_of, evaluation_as_of):
        self.outcome_cutoffs.append(evaluation_as_of)
        fact = self._fact(customer_id, prediction_as_of)
        return LifecycleOutcomeSnapshot(
            tenant_id=tenant_id,
            customer_id=customer_id,
            prediction_as_of=prediction_as_of,
            evaluation_as_of=evaluation_as_of,
            subscription_facts=(fact,) if fact is not None else (),
        )


def test_missing_and_invalid_credentials_are_rejected_without_reflection():
    with pytest.raises(PilotError, match="DPAPI wrapper"):
        require_reader_token({})

    class BadAuth:
        @staticmethod
        def authenticate_service_principal(_path, token):
            assert token == "private-synthetic-test-token"
            raise RuntimeError("failure contained a secret=private-synthetic-test-token")

    with pytest.raises(PilotError) as caught:
        authenticate_reader(BadAuth, "unused.sqlite3", {"RETAINIQ_MODEL_TOKEN": "private-synthetic-test-token"})
    assert "private-synthetic-test-token" not in str(caught.value)
    assert "failure contained" not in str(caught.value)


def test_wrong_principal_grants_fail_closed_and_do_not_require_private_credentials():
    valid = SimpleNamespace(
        tenant_id="tenant-01", role="analyst",
        authorized_purposes=("retention_inference",),
        authorized_sources=tuple(EXPECTED_SOURCE_CATEGORIES),
    )
    validate_reader_principal(valid)
    for invalid in (
        SimpleNamespace(**{**vars(valid), "tenant_id": "tenant-02"}),
        SimpleNamespace(**{**vars(valid), "authorized_purposes": ("retention_inference", "model_artifact_write")}),
        SimpleNamespace(**{**vars(valid), "authorized_sources": ("unapproved-source",)}),
    ):
        with pytest.raises(PilotError, match="grants"):
            validate_reader_principal(invalid)


def test_dataset_identity_mismatch_is_rejected(tmp_path):
    _manifest, _split, digest = _fixture_files(tmp_path)
    with pytest.raises(PilotError, match="identity"):
        validate_dataset_files(
            tmp_path,
            expected_dataset_id="wrong-dataset",
            expected_manifest_sha256=digest,
        )


def test_customer_cohort_and_development_cutoffs_are_deterministic_and_exclude_test(tmp_path):
    manifest, split, digest = _fixture_files(tmp_path)
    first = select_tenant_customer_ids(tmp_path, dataset_id=manifest["dataset_id"], limit=30)
    second = select_tenant_customer_ids(tmp_path, dataset_id=manifest["dataset_id"], limit=30)
    assert first == second
    assert len(first) == 4
    assert "customer-other" not in first
    assert select_tenant_customer_ids(
        tmp_path, dataset_id=manifest["dataset_id"], limit=2
    ) == first[:2]

    selected = select_development_cutoffs(manifest, split)
    assert [item.split.value for item in selected] == ["TRAIN", "TRAIN", "VALIDATION"]
    assert len({item.as_of for item in selected}) == 3
    assert all(item.as_of.tzinfo is UTC and item.as_of.hour == 12 for item in selected)
    assert all(item.split.value != "TEST" for item in selected)
    assert validate_dataset_files(
        tmp_path,
        expected_dataset_id=manifest["dataset_id"],
        expected_manifest_sha256=digest,
    )[2] == digest


def test_runner_preserves_eligibility_labels_and_aggregate_only_output(tmp_path):
    manifest, _split, digest = _fixture_files(tmp_path)
    adapter = _FakeAdapter(manifest["dataset_id"], digest)
    report = run_bounded_pilot(
        adapter,
        tmp_path,
        expected_dataset_id=manifest["dataset_id"],
        expected_manifest_sha256=digest,
    )

    assert report["sampling"]["candidate_account_cutoff_pairs"] == 12
    assert report["sampling"]["unique_accounts"] == 4
    assert report["sampling"]["repeated_account_snapshot_rows"] == 8
    assert report["sampling"]["test_cutoffs_selected"] == 0
    assert report["eligibility"]["states"] == {
        "ELIGIBLE": 3,
        "INSUFFICIENT_DATA": 3,
        "KNOWN_CANCELLATION": 3,
        "NOT_ELIGIBLE": 3,
    }
    for horizon in ("7", "14", "30"):
        labels = report["labels"][horizon]
        assert labels["positive"] == 0
        assert labels["negative"] == 0
        assert labels["unknown"] == 3
        assert labels["excluded"] == 6
        assert labels["unsupported"] == 3
    assert report["source_state"]["connectivity_by_candidate_pair"] == {"unknown": 12}
    assert report["source_state"]["source_not_connected_reason_occurrences"] == 0
    assert report["authorization"]["cross_tenant_denial_probe"] == "NOT_RUN"
    assert all(cutoff <= max(adapter.outcome_cutoffs) for cutoff in adapter.outcome_cutoffs)
    encoded = json.dumps(report, sort_keys=True)
    for private_id in ("customer-a", "customer-b", "customer-c", "customer-d", "customer-other"):
        assert private_id not in encoded


def test_point_in_time_facts_require_occurrence_and_availability_cutoffs():
    cutoff = datetime(2025, 3, 10, 12, tzinfo=UTC)
    valid = SimpleNamespace(
        occurred_at=cutoff - timedelta(days=1),
        source_available_at=cutoff - timedelta(hours=1),
        received_at=cutoff,
    )
    assert_facts_available_by((valid,), cutoff, context="test")
    late = SimpleNamespace(
        occurred_at=cutoff - timedelta(days=1),
        source_available_at=cutoff + timedelta(days=1),
        received_at=cutoff + timedelta(days=1),
    )
    with pytest.raises(PilotError, match="not demonstrably available"):
        assert_facts_available_by((late,), cutoff, context="test")
    unknown = SimpleNamespace(occurred_at=cutoff - timedelta(days=1), source_available_at=None, received_at=None)
    with pytest.raises(PilotError, match="not demonstrably available"):
        assert_facts_available_by((unknown,), cutoff, context="test")
    future = SimpleNamespace(occurred_at=cutoff + timedelta(seconds=1), source_available_at=cutoff, received_at=cutoff)
    with pytest.raises(PilotError, match="not demonstrably available"):
        assert_facts_available_by((future,), cutoff, context="test")


def test_silent_source_is_unknown_not_disconnected_and_timed_reader_counts_calls():
    assert _connection_state((SimpleNamespace(connected=None),)) == "unknown"
    assert _connection_state((SimpleNamespace(connected=False),)) == "explicitly_disconnected"
    assert _connection_state((SimpleNamespace(connected=True),)) == "connected"

    class FakeReader:
        @staticmethod
        def get_dataset_identity(*_args):
            return {"dataset_id": "fixture"}

    reader = TimedReaderAPI(FakeReader)
    assert reader.get_dataset_identity("unused", object()) == {"dataset_id": "fixture"}
    assert reader.counts["get_dataset_identity"] == 1
    assert reader.seconds["get_dataset_identity"] >= 0


def test_billing_valuation_fields_are_rejected_from_unprivileged_responses():
    _assert_no_unauthorized_valuation("get_account_snapshot_as_of", {"valuation": None})
    _assert_no_unauthorized_valuation(
        "get_events_as_of", [{"category": "billing", "attributes": {"payment_status": "failed"}}]
    )
    with pytest.raises(PilotError, match="valuation"):
        _assert_no_unauthorized_valuation(
            "get_events_as_of", [{"category": "billing", "attributes": {"currency": "USD"}}]
        )
    with pytest.raises(PilotError, match="valuation"):
        _assert_no_unauthorized_valuation(
            "get_subscriptions_as_of", [{"subscription_id": "synthetic", "mrr_minor": 100}]
        )


def test_pilot_rejects_more_than_thirty_accounts_or_three_development_cutoffs(tmp_path):
    manifest, split, digest = _fixture_files(tmp_path)
    adapter = _FakeAdapter(manifest["dataset_id"], digest)
    with pytest.raises(PilotError, match="1-30"):
        run_bounded_pilot(
            adapter, tmp_path, customer_ids=tuple(f"id-{index}" for index in range(31)),
            expected_dataset_id=manifest["dataset_id"], expected_manifest_sha256=digest,
        )
    valid = select_development_cutoffs(manifest, split)
    four = (*valid, Cutoff(as_of=datetime(2025, 6, 2, 12, tzinfo=UTC), split=valid[0].split, label_freeze=valid[0].label_freeze))
    with pytest.raises(PilotError, match="unique TRAIN/VALIDATION"):
        run_bounded_pilot(
            adapter, tmp_path, customer_ids=("customer-a",), cutoffs=four,
            expected_dataset_id=manifest["dataset_id"], expected_manifest_sha256=digest,
        )
