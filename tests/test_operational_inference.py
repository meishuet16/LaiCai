"""Structural operational-inference tests; all records are synthetic fixtures."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from retainiq_prediction.contracts import (
    DataFreshness,
    FreshnessStatus,
    PredictionOutput,
    PredictionStatus,
    Reliability,
    ReliabilityStatus,
    Uncertainty,
)
from retainiq_prediction.operational_inference import (
    AlertPolicy,
    BatchItemStatus,
    DataFoundationPredictionSnapshotStore,
    DailyPredictionBatch,
    EventTriggeredPrediction,
    EventTriggerStatus,
    HistoricalRiskAlert,
    InMemoryPredictionSnapshotStore,
    PointInTimeReplayRunner,
    PredictionPersistenceConflict,
    SourceChangeEvent,
    StoreDisposition,
    apply_alert_policy,
    risk_evolution,
)
from retainiq_prediction.prediction_pipeline import (
    PipelineResult,
    PipelineStatus,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)


def prediction(
    customer_id="account-a",
    *,
    as_of=BASE,
    run_id="run-1",
    prediction_id="prediction-1",
    p30=0.6,
    p7=0.1,
    p14=0.3,
    reliability=ReliabilityStatus.SUFFICIENT_EVIDENCE,
    freshness=FreshnessStatus.FRESH,
    feature_version="features-v1",
    model_version="model-v1",
    calibration_version="calibration-v1",
):
    return PredictionOutput(
        tenant_id="tenant-a",
        customer_id=customer_id,
        prediction_id=prediction_id,
        prediction_run_id=run_id,
        as_of=as_of,
        generated_at=as_of + timedelta(minutes=1),
        status=PredictionStatus.SCORED,
        p_churn_7d=p7,
        p_churn_14d=p14,
        p_churn_30d=p30,
        feature_version=feature_version,
        model_version=model_version,
        calibration_version=calibration_version,
        label_policy_version="labels-v1",
        reliability=Reliability(status=reliability),
        data_freshness=DataFreshness(status=freshness, input_data_as_of=as_of),
        uncertainty=Uncertainty(),
        explanations_by_horizon={"30": [{"feature": "sessions_prev_7d", "value": 2}]},
    )


class FakeSource:
    tenant_id = "tenant-a"

    def __init__(self, customers=("account-a", "account-silent")):
        self.customers = customers
        self.accounts_requested = []

    def eligible_accounts_as_of(self, as_of):
        self.accounts_requested.append(as_of)
        return self.customers

    def coverage_for(self, tenant_id, customer_id, as_of):
        assert tenant_id == self.tenant_id
        return ()

    def freshness_evidence_for(self, tenant_id, customer_id, as_of):
        assert tenant_id == self.tenant_id
        return ()


class FakePipeline:
    def __init__(self, *, synthetic=True, error=False):
        self.synthetic = synthetic
        self.error = error
        self.requests = []

    def run(self, request):
        if self.error:
            raise RuntimeError("synthetic pipeline failure")
        self.requests.append(request)
        output = prediction(
            request.customer_id,
            as_of=request.as_of,
            run_id=request.prediction_run_id,
            prediction_id=f"pred-{request.customer_id}-{request.as_of.date()}-{request.prediction_run_id}",
        )
        return PipelineResult(
            tenant_id=request.tenant_id,
            customer_id=request.customer_id,
            as_of=request.as_of,
            prediction_run_id=request.prediction_run_id,
            pipeline_status=PipelineStatus.COMPLETED,
            prediction=output,
            synthetic_test_only=self.synthetic,
            deployable=False,
        )


def batch(*, source=None, pipeline=None, store=None):
    source = source or FakeSource()
    pipeline = pipeline or FakePipeline()
    store = store or InMemoryPredictionSnapshotStore()
    return DailyPredictionBatch(source, pipeline, store), source, pipeline, store


def test_daily_batch_scores_all_eligible_accounts_including_silent_accounts():
    runner, source, model, store = batch()
    result = runner.run(BASE, "daily-run-1")

    assert result.candidate_account_count == 2
    assert {item.customer_id for item in result.items} == {"account-a", "account-silent"}
    assert result.stored_count == 2
    assert result.items[0].synthetic_test_only
    assert len(model.requests) == 2
    assert source.accounts_requested == [BASE]
    assert len(store.history_for("tenant-a", "account-silent")) == 1


def test_daily_batch_is_idempotent_for_exact_retry_and_rejects_conflicting_content():
    runner, _, model, store = batch(source=FakeSource(("account-a",)))
    first = runner.run(BASE, "daily-run-1")
    retry = runner.run(BASE, "daily-run-1")
    assert first.stored_count == 1
    assert retry.already_present_count == 1

    changed = prediction(run_id="daily-run-1", prediction_id="different-id")
    with pytest.raises(PredictionPersistenceConflict):
        store.append_if_absent(changed)
    assert len(model.requests) == 2


def test_daily_batch_fails_closed_on_source_store_tenant_mismatch():
    source = FakeSource()
    store = DataFoundationPredictionSnapshotStore(
        "ignored.sqlite",
        SimpleNamespace(tenant_id="tenant-b"),
        read_prediction=lambda *args: None,
        write_prediction=lambda *args: "unused",
    )
    with pytest.raises(PermissionError):
        DailyPredictionBatch(source, FakePipeline(), store)


def test_unexpected_pipeline_exception_is_an_account_level_failure():
    runner, _, _, _ = batch(source=FakeSource(("account-a",)), pipeline=FakePipeline(error=True))
    result = runner.run(BASE, "run-error")
    assert result.items[0].status is BatchItemStatus.PIPELINE_NOT_COMPLETED
    assert result.items[0].reason_codes == ("PIPELINE_RUNTIMEERROR",)


def test_member1_store_uses_authenticated_tenant_and_canonical_flat_payload():
    principal = SimpleNamespace(tenant_id="tenant-a")
    written = []
    output = prediction()
    store = DataFoundationPredictionSnapshotStore(
        "authenticated.sqlite",
        principal,
        read_prediction=lambda path, auth, customer_id, as_of: None,
        write_prediction=lambda path, auth, payload: written.append((path, auth, payload))
        or payload["prediction_id"],
    )

    assert store.append_if_absent(output) is StoreDisposition.INSERTED
    path, auth, payload = written[0]
    assert path == "authenticated.sqlite" and auth is principal
    assert "tenant_id" not in payload  # The writer derives tenant from its principal.
    assert payload["p_churn_7d"] == 0.1
    assert payload["p_churn_14d"] == 0.3
    assert payload["p_churn_30d"] == 0.6
    assert "cumulative_churn_probability" not in payload


def test_member1_store_accepts_exact_existing_snapshot_and_rejects_wrong_reader_identity():
    output = prediction()
    principal = SimpleNamespace(tenant_id="tenant-a")
    store = DataFoundationPredictionSnapshotStore(
        "ignored.sqlite",
        principal,
        read_prediction=lambda *args: output,
        write_prediction=lambda *args: pytest.fail("must not write an existing row"),
    )
    assert store.append_if_absent(output) is StoreDisposition.ALREADY_PRESENT

    out_of_scope = prediction(customer_id="other-account")
    bad_reader = DataFoundationPredictionSnapshotStore(
        "ignored.sqlite",
        principal,
        read_prediction=lambda *args: out_of_scope,
        write_prediction=lambda *args: "unused",
    )
    with pytest.raises(PermissionError, match="out-of-scope"):
        bad_reader.append_if_absent(output)


def test_event_trigger_rejects_future_and_late_available_events_without_scoring():
    runner, _, model, _ = batch(source=FakeSource(("account-a",)))
    trigger = EventTriggeredPrediction(runner)
    late = SourceChangeEvent(
        tenant_id="tenant-a",
        customer_id="account-a",
        source="billing",
        event_id="event-late",
        event_category="payment_failed",
        occurred_at=BASE - timedelta(days=1),
        available_at=BASE + timedelta(hours=1),
    )
    result = trigger.on_source_change(late, as_of=BASE, prediction_run_id="event-run")
    assert result.status is EventTriggerStatus.REJECTED_NOT_AVAILABLE
    assert not model.requests


def test_event_trigger_is_tenant_scoped_and_duplicate_delivery_is_idempotent():
    runner, _, model, _ = batch(source=FakeSource(("account-a",)))
    trigger = EventTriggeredPrediction(runner)
    valid = SourceChangeEvent(
        tenant_id="tenant-a",
        customer_id="account-a",
        source="billing",
        event_id="event-1",
        event_category="payment_failed",
        occurred_at=BASE - timedelta(hours=1),
        available_at=BASE - timedelta(minutes=30),
    )
    wrong_tenant = valid.model_copy(update={"tenant_id": "tenant-b", "event_id": "other"})
    assert trigger.on_source_change(
        wrong_tenant, as_of=BASE, prediction_run_id="run-0"
    ).status is EventTriggerStatus.REJECTED_SCOPE

    first = trigger.on_source_change(valid, as_of=BASE, prediction_run_id="run-1")
    retry = trigger.on_source_change(valid, as_of=BASE, prediction_run_id="run-2")
    assert first.status is EventTriggerStatus.TRIGGER_HANDLED
    assert retry.status is EventTriggerStatus.DUPLICATE_IGNORED
    assert len(model.requests) == 1


def test_risk_history_compares_only_compatible_scored_snapshots():
    first = prediction(as_of=BASE, prediction_id="p1", p7=0.05, p14=0.2, p30=0.4)
    second = prediction(
        as_of=BASE + timedelta(days=1), prediction_id="p2", run_id="run-2",
        p7=0.1, p14=0.25, p30=0.6,
    )
    incompatible = prediction(
        as_of=BASE + timedelta(days=2), prediction_id="p3", run_id="run-3",
        feature_version="features-v2",
    )
    changes = risk_evolution((second, incompatible, first))
    assert len(changes) == 2
    assert changes[0].p30_change == pytest.approx(0.2)
    assert changes[0].comparable_model_versions
    assert changes[1].p30_change is None
    assert "not a forecast trajectory" in changes[0].note
    with pytest.raises(ValueError, match="duplicate"):
        risk_evolution((first, first))


def test_alert_policy_applies_reliability_trend_cooldown_and_period_budget():
    current = (
        prediction("high", prediction_id="high-pred", p7=0.2, p14=0.5, p30=0.9),
        prediction("mid", prediction_id="mid-pred", p7=0.1, p14=0.4, p30=0.7),
        prediction(
            "limited", prediction_id="limited-pred", p7=0.2, p14=0.5, p30=0.95,
            reliability=ReliabilityStatus.LIMITED_EVIDENCE,
        ),
    )
    policy = AlertPolicy(
        policy_version="alert-policy-test-v1",
        probability_threshold=0.5,
        maximum_alerts_per_period=1,
        require_rising_risk=False,
    )
    decisions = apply_alert_policy(
        current,
        prior_predictions=(),
        prior_alerts=(),
        policy=policy,
    )
    by_id = {item.prediction_id: item for item in decisions}
    assert by_id["high-pred"].selected
    assert by_id["mid-pred"].reason_code == "PERIOD_BUDGET_EXHAUSTED"
    assert by_id["limited-pred"].reason_code == "RELIABILITY_BELOW_POLICY"

    prior_alert = HistoricalRiskAlert(
        tenant_id="tenant-a",
        customer_id="old-account",
        prediction_id="prior-alert",
        alerted_at=BASE - timedelta(days=1),
        policy_version=policy.policy_version,
    )
    consumed = apply_alert_policy(
        current[:1], prior_predictions=(), prior_alerts=(prior_alert,), policy=policy
    )
    assert not consumed[0].selected
    assert consumed[0].reason_code == "PERIOD_BUDGET_EXHAUSTED"


def test_alert_policy_rejects_incomparable_trend_and_honors_cooldown():
    current = prediction(as_of=BASE, prediction_id="current", p30=0.8)
    previous = prediction(
        as_of=BASE - timedelta(days=1), prediction_id="previous", p30=0.7,
        model_version="different-model",
    )
    policy = AlertPolicy(policy_version="policy-v1", probability_threshold=0.5)
    incomparable = apply_alert_policy(
        (current,), prior_predictions=(previous,), prior_alerts=(), policy=policy
    )
    assert incomparable[0].reason_code == "RISK_TREND_NOT_COMPARABLE"

    same_model = previous.model_copy(update={"model_version": "model-v1"})
    recent_alert = HistoricalRiskAlert(
        tenant_id="tenant-a", customer_id="account-a", prediction_id="old-alert",
        alerted_at=BASE - timedelta(days=1), policy_version="policy-v1",
    )
    cooling = apply_alert_policy(
        (current,), prior_predictions=(same_model,), prior_alerts=(recent_alert,), policy=policy
    )
    assert cooling[0].reason_code == "COOLDOWN_ACTIVE"


def test_replay_is_chronological_and_returns_persisted_risk_changes_without_outcomes():
    runner, _, model, store = batch(source=FakeSource(("account-a",)))
    replay = PointInTimeReplayRunner(runner).replay_customer(
        "account-a",
        (BASE, BASE + timedelta(days=1)),
        prediction_run_prefix="replay",
    )
    assert replay.cutoffs == (BASE, BASE + timedelta(days=1))
    assert replay.prediction_run_ids == ("replay_0001", "replay_0002")
    assert len(model.requests) == 2
    assert len(store.history_for("tenant-a", "account-a")) == 2
    assert len(replay.changes) == 1
    assert replay.synthetic_demo_only


def test_replay_rejects_naive_or_nonchronological_cutoffs():
    runner, _, _, _ = batch(source=FakeSource(("account-a",)))
    replay = PointInTimeReplayRunner(runner)
    with pytest.raises(ValueError, match="timezone-aware"):
        replay.replay_customer("account-a", (datetime(2026, 10, 1),), prediction_run_prefix="r")
    with pytest.raises(ValueError, match="chronological"):
        replay.replay_customer(
            "account-a", (BASE + timedelta(days=1), BASE), prediction_run_prefix="r"
        )
