import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from retaniq.data_foundation import (
    DataFoundationError, authenticate_integration, authenticate_service_principal,
    bind_dataset_identity, create_customer, create_integration, create_service_principal,
    create_tenant, get_dataset_identity, get_events_as_of, get_account_snapshot_as_of,
    initialize_database, ingest_event, map_customer_identity, record_observation_coverage,
)
from retainiq_prediction.data_freshness import assess_data_freshness
from retainiq_prediction.eligibility import EligibilityState
from retainiq_prediction.feature_builder import FeatureBuilder
from retainiq_prediction.sqlite_data_adapter import SQLiteDataAdapter


UTC = timezone.utc
AS_OF = datetime(2026, 10, 10, tzinfo=UTC)


class DataFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.dataset = root / "dataset"
        self.dataset.mkdir()
        self.db = root / "events.sqlite3"
        self.manifest = {
            "dataset_id": "synthetic-saas-v1-2-quick-s2026-fixture",
            "dataset_version": "1.2.0",
            "dataset_type": "synthetic_saas",
            "target_policy_version": "effective-account-churn-v1.2",
            "generator_code_version": "synthetic-saas-v1.2",
        }
        manifest_bytes = (json.dumps(self.manifest, sort_keys=True) + "\n").encode()
        (self.dataset / "dataset_manifest.json").write_bytes(manifest_bytes)
        initialize_database(self.db)
        bind_dataset_identity(
            self.db, dataset_id=self.manifest["dataset_id"],
            dataset_version=self.manifest["dataset_version"],
            dataset_type=self.manifest["dataset_type"],
            target_policy_version=self.manifest["target_policy_version"],
            generator_version=self.manifest["generator_code_version"],
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        )
        create_tenant(self.db, "tenant-a")
        create_tenant(self.db, "tenant-b")
        create_customer(self.db, "tenant-a", "account-a")
        create_customer(self.db, "tenant-b", "account-b")
        token = create_integration(
            self.db, "tenant-a", "source-a",
            authorized_categories=("usage", "billing", "subscription"),
            authorized_purposes=("retention_inference", "billing_valuation", "identity_mapping"),
        )
        token_b = create_integration(
            self.db, "tenant-b", "source-b",
            authorized_categories=("usage", "billing", "subscription"),
            authorized_purposes=("retention_inference", "billing_valuation", "identity_mapping"),
        )
        map_customer_identity(self.db, "tenant-a", "source-a", "external-a", "account-a")
        map_customer_identity(self.db, "tenant-b", "source-b", "external-b", "account-b")
        self.integration = authenticate_integration(self.db, token)
        self.integration_b = authenticate_integration(self.db, token_b)
        self._event(
            "subscription_created", "sub-create", "2026-10-01T00:00:00Z",
            {"subscription_id": "sub-a", "status": "active", "started_at": "2026-10-01T00:00:00Z"},
        )
        self._event(
            "usage_aggregate_updated", "usage-1", "2026-10-09T00:00:00Z",
            {"feature": "reports", "quantity": 5, "unit": "sessions"},
        )
        self._event(
            "payment_failed", "payment-fail", "2026-10-08T00:00:00Z",
            {"subscription_id": "sub-a"},
        )
        self._event(
            "usage_aggregate_updated", "late-usage", "2026-10-08T00:00:00Z",
            {"feature": "reports", "quantity": 9, "unit": "sessions"},
            available="2026-10-12T00:00:00Z",
        )
        self._event(
            "usage_aggregate_updated", "future-usage", "2026-10-11T00:00:00Z",
            {"feature": "reports", "quantity": 13, "unit": "sessions"},
        )
        self._event(
            "cancellation_requested", "cancel-request", "2026-10-09T00:00:00Z",
            {"subscription_id": "sub-a", "current_period_end": "2026-10-20T00:00:00Z"},
        )
        self._event(
            "subscription_updated", "scheduled-end", "2026-10-09T12:00:00Z",
            {"subscription_id": "sub-a", "status": "pending_cancel", "ended_at": "2026-10-20T00:00:00Z"},
        )
        record_observation_coverage(
            self.db, self.integration, {
                "coverage_id": "usage-coverage",
                "customer_id": "account-a", "source_category": "usage",
                "covered_from": "2026-08-01T00:00:00Z",
                "covered_through": "2026-10-10T00:00:00Z",
                "coverage_status": "complete", "coverage_completeness": 1.0,
                "coverage_available_at": "2026-10-10T00:00:00Z",
                "observation_policy_version": "coverage-v1",
            },
        )
        reader_token = create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("source-a",),
            authorized_purposes=("retention_inference", "model_artifact_write"),
        )
        self.reader = authenticate_service_principal(self.db, reader_token)
        self.adapter = SQLiteDataAdapter(self.db, self.dataset, self.reader)

    def _event(self, event_type, event_id, occurred, attributes, available=None):
        payload = {
            "source": "source-a", "source_event_id": event_id,
            "external_customer_id": "external-a", "event_type": event_type,
            "occurred_at": occurred, "attributes": attributes, "schema_version": "1.0",
        }
        return ingest_event(
            self.db, self.integration, payload,
            received_at=available or occurred,
            trusted_source_available_at=available or occurred,
        )

    def close(self):
        self.temp.cleanup()


@pytest.fixture
def data():
    fixture = DataFixture()
    try:
        yield fixture
    finally:
        fixture.close()


def test_authenticated_tenant_scope_identity_and_synthetic_provenance(data):
    snapshot = data.adapter.snapshot_for("tenant-a", "account-a", AS_OF)
    assert snapshot.tenant_id == data.reader.tenant_id
    assert data.adapter.provenance.dataset_id == data.manifest["dataset_id"]
    assert data.adapter.provenance.evidence_status == "SYNTHETIC_ONLY"
    with pytest.raises(DataFoundationError):
        data.adapter.snapshot_for("tenant-b", "account-b", AS_OF)


def test_reader_without_retention_purpose_is_rejected(data):
    token = create_service_principal(
        data.db, "tenant-a", role="analyst", authorized_sources=("source-a",),
        authorized_purposes=("integration_health",),
    )
    reader = authenticate_service_principal(data.db, token)
    with pytest.raises(DataFoundationError):
        SQLiteDataAdapter(data.db, data.dataset, reader)


def test_dataset_manifest_database_identity_mismatch_is_rejected(data):
    manifest = json.loads((data.dataset / "dataset_manifest.json").read_text())
    manifest["dataset_version"] = "different"
    (data.dataset / "dataset_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="does not match"):
        SQLiteDataAdapter(data.db, data.dataset, data.reader)


def test_subscription_facts_reconstruct_historical_eligibility_and_cancellation(data):
    snapshot = data.adapter.snapshot_for("tenant-a", "account-a", AS_OF)
    assert len(snapshot.subscriptions) == 3
    scheduled = next(
        fact for fact in snapshot.subscriptions
        if fact.attributes["source_event_id"] == "scheduled-end"
    )
    assert scheduled.effective_at == datetime(2026, 10, 9, 12, tzinfo=UTC)
    assert scheduled.scheduled_termination_at == datetime(2026, 10, 20, tzinfo=UTC)
    assert scheduled.point_in_time() <= AS_OF
    result = data.adapter.eligibility_for("tenant-a", "account-a", AS_OF)
    assert result.state is EligibilityState.KNOWN_CANCELLATION
    earlier = data.adapter.eligibility_for(
        "tenant-a", "account-a", datetime(2026, 10, 5, tzinfo=UTC)
    )
    assert earlier.state is EligibilityState.ELIGIBLE


def test_payment_failure_is_billing_evidence_not_churn(data):
    snapshot = data.adapter.snapshot_for(
        "tenant-a", "account-a", datetime(2026, 10, 5, tzinfo=UTC)
    )
    assert [item.event_type for item in snapshot.billing_events] == []
    later = data.adapter.snapshot_for("tenant-a", "account-a", AS_OF)
    assert any(item.event_type == "payment_failed" for item in later.billing_events)
    assert all("amount_minor" not in item.attributes for item in later.billing_events)
    assert all("currency" not in item.attributes for item in later.billing_events)
    payment_time = datetime(2026, 10, 8, tzinfo=UTC)
    assert data.adapter.eligibility_for("tenant-a", "account-a", payment_time).state is EligibilityState.ELIGIBLE


def test_future_and_late_arriving_usage_are_excluded_at_cutoff(data):
    snapshot = data.adapter.snapshot_for("tenant-a", "account-a", AS_OF)
    assert {item.record_id for item in snapshot.usage_events} == {
        item.record_id for item in snapshot.usage_events
        if item.record_id not in {"late-usage", "future-usage"}
    }
    assert "late-usage" not in {item.record_id for item in snapshot.usage_events}
    assert "future-usage" not in {item.record_id for item in snapshot.usage_events}


def test_daily_aggregate_quantity_and_distinct_active_day_map_to_features(data):
    builder = FeatureBuilder(
        data.adapter, config=data.adapter.feature_builder_config(),
        coverage_provider=data.adapter,
    )
    features = builder.build("tenant-a", "account-a", AS_OF)
    assert features.feature_values.sessions_prev_7d == 5
    assert features.feature_values.active_days_prev_7d == 1
    assert "usage-coverage" in features.source_evidence_refs


def test_coverage_distinguishes_verified_activity_and_missing_records(data):
    records = data.adapter.coverage_for("tenant-a", "account-a", AS_OF)
    assert len(records) == 1
    assert records[0].complete is True
    assert records[0].status == "complete"
    assert records[0].completeness == 1.0
    assert data.adapter.coverage_for("tenant-a", "account-b", AS_OF) == ()
    builder = FeatureBuilder(data.adapter, config=data.adapter.feature_builder_config())
    window_start = datetime(2026, 10, 3, tzinfo=UTC)
    assert builder._active_days((), window_start, AS_OF, records) == 0
    assert builder._active_days((), window_start, AS_OF, ()) is None


def test_adapter_rejects_naive_cutoffs_and_exposes_freshness_limits(data):
    with pytest.raises(ValueError, match="timezone-aware"):
        data.adapter.snapshot_for("tenant-a", "account-a", datetime(2026, 10, 10))
    evidence = data.adapter.freshness_evidence_for("tenant-a", "account-a", AS_OF)
    assessment = assess_data_freshness("tenant-a", "account-a", AS_OF, evidence, evaluated_at=AS_OF)
    assert assessment.status.value in {"fresh", "partially_stale", "stale", "unknown"}
    lifecycle = next(row for row in evidence if row.source == "subscription_lifecycle")
    assert lifecycle.complete is None
    assert lifecycle.limitations


def test_event_silence_does_not_map_to_source_disconnected(data):
    create_customer(data.db, "tenant-a", "quiet-account")
    map_customer_identity(data.db, "tenant-a", "source-a", "external-quiet", "quiet-account")

    snapshot = data.adapter.snapshot_for("tenant-a", "quiet-account", AS_OF)
    evidence = data.adapter.freshness_evidence_from(snapshot, ())
    assessments = assess_data_freshness(
        "tenant-a", "quiet-account", AS_OF, evidence, evaluated_at=AS_OF
    )

    assert snapshot.subscriptions == ()
    assert snapshot.billing_events == ()
    assert snapshot.usage_events == ()
    assert all(item.connected is None for item in evidence)
    assert assessments.status.value == "unknown"
    assert all(
        "SOURCE_NOT_CONNECTED" not in {code.value for code in item.reason_codes}
        for item in assessments.source_assessments
    )
    assert all(item.status.value != "fresh" for item in assessments.source_assessments)


def test_complete_zero_usage_coverage_is_not_missing_or_disconnected(data):
    create_customer(data.db, "tenant-a", "zero-usage-account")
    map_customer_identity(data.db, "tenant-a", "source-a", "external-zero", "zero-usage-account")
    record_observation_coverage(
        data.db, data.integration, {
            "coverage_id": "zero-usage-coverage",
            "customer_id": "zero-usage-account",
            "source_category": "usage",
            "covered_from": "2026-09-01T00:00:00Z",
            "covered_through": "2026-10-10T00:00:00Z",
            "coverage_status": "complete",
            "coverage_completeness": 1.0,
            "coverage_available_at": "2026-10-10T00:00:00Z",
            "observation_policy_version": "coverage-v1",
        },
    )
    snapshot = data.adapter.snapshot_for("tenant-a", "zero-usage-account", AS_OF)
    assert snapshot.usage_events == ()
    coverage = data.adapter.coverage_records_for("tenant-a", "zero-usage-account", AS_OF)
    usage_evidence = next(
        item for item in data.adapter.freshness_evidence_from(snapshot, coverage)
        if item.source == "usage_coverage"
    )

    assert usage_evidence.connected is None
    assert usage_evidence.complete is True
    assert usage_evidence.watermark_at == AS_OF
    # Complete coverage with no activity establishes observed zero usage;
    # event silence alone does not.
    assessment = assess_data_freshness(
        "tenant-a", "zero-usage-account", AS_OF,
        data.adapter.freshness_evidence_from(snapshot, coverage),
        evaluated_at=AS_OF,
    )
    usage = next(item for item in assessment.source_assessments if item.source == "usage_coverage")
    assert usage.status.value == "fresh"


def test_adapter_defense_excludes_late_and_unknown_availability(data):
    base_api = data.adapter.reader_api

    class AdversarialReader:
        def __getattr__(self, name):
            return getattr(base_api, name)

        def get_events_as_of(self, path, principal, customer_id, as_of, *, category=None):
            rows = base_api.get_events_as_of(
                path, principal, customer_id, as_of, category=category
            )
            if category in {None, "usage"}:
                rows.extend([
                    {
                        "event_id": "injected-late", "source": "source-a",
                        "source_event_id": "fixture-late", "customer_id": customer_id,
                        "category": "usage", "event_type": "usage_aggregate_updated",
                        "occurred_at": "2026-10-08T00:00:00Z",
                        "received_at": "2026-10-12T00:00:00Z",
                        "source_available_at": "2026-10-12T00:00:00Z",
                        "attributes": {"quantity": 100},
                    },
                    {
                        "event_id": "injected-unknown", "source": "source-a",
                        "source_event_id": "fixture-unknown", "customer_id": customer_id,
                        "category": "usage", "event_type": "usage_aggregate_updated",
                        "occurred_at": "2026-10-08T00:00:00Z",
                        "received_at": None, "source_available_at": None,
                        "attributes": {"quantity": 100},
                    },
                ])
            return rows

    data.adapter.reader_api = AdversarialReader()
    snapshot = data.adapter.snapshot_for("tenant-a", "account-a", AS_OF)
    ids = {fact.record_id for fact in snapshot.usage_events}
    assert "injected-late" not in ids
    assert "injected-unknown" not in ids
    assert snapshot.excluded_record_counts["late_arriving_fact"] == 1
    assert snapshot.excluded_record_counts["historical_availability_unknown"] == 1
    assert snapshot.limitations


def test_outcome_adapter_keeps_prediction_and_evaluation_cutoffs_separate(data):
    outcome = data.adapter.outcome_snapshot_for(
        "tenant-a", "account-a",
        datetime(2026, 10, 5, tzinfo=UTC),
        datetime(2026, 10, 10, tzinfo=UTC),
    )
    assert outcome.prediction_as_of == datetime(2026, 10, 5, tzinfo=UTC)
    assert outcome.evaluation_as_of == AS_OF
    assert any(fact.event_type == "cancellation_requested" for fact in outcome.subscription_facts)


def test_read_adapter_does_not_mutate_sqlite_database(data):
    before = hashlib.sha256(data.db.read_bytes()).hexdigest()
    data.adapter.snapshot_for("tenant-a", "account-a", AS_OF)
    data.adapter.coverage_for("tenant-a", "account-a", AS_OF)
    after = hashlib.sha256(data.db.read_bytes()).hexdigest()
    assert after == before


def test_member1_api_enforces_source_and_customer_filters(data):
    rows = get_events_as_of(data.db, data.reader, "account-a", "2026-10-10T00:00:00Z")
    assert all(row["customer_id"] == "account-a" for row in rows)
    assert all(row["source"] in data.reader.authorized_sources for row in rows)
    with pytest.raises(DataFoundationError):
        get_account_snapshot_as_of(data.db, data.reader, "account-b", "2026-10-10T00:00:00Z")
