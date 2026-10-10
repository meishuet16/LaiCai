from datetime import datetime, timezone

from retainiq_prediction.model_approval import AuthorizationEvidence, AuthorizationStatus
from retainiq_prediction.model_promotion import InMemoryActiveBundleStore, active_reference_from_metadata
from retainiq_prediction.model_registry import ModelLifecycleStatus
from retainiq_prediction.model_rollback import (
    ModelRollbackService,
    RollbackReasonCode,
    RollbackRequest,
    RollbackStatus,
)
from test_model_approval import candidate


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def auth():
    return AuthorizationEvidence(
        verification_id="rollback-auth",
        actor_reference="operator-1",
        actor_role="release_operator",
        authorization_scope="model.rollback",
        verified_at=NOW,
        verifier_reference="external-rbac",
        status=AuthorizationStatus.VERIFIED,
        production_trusted=True,
    )


def request(**updates):
    values = dict(
        request_id="rollback-1",
        active_bundle_id="bundle-current",
        active_generation=2,
        previous_known_good_bundle_id="bundle-known-good",
        actor_reference="operator-1",
        authorization_scope="model.rollback",
        auth_evidence_reference="rollback-auth",
        reason="Restore known-good release.",
        request_timestamp=NOW,
        policy_version="rollback-v1",
    )
    values.update(updates)
    return RollbackRequest(**values)


def setup():
    current = candidate(status=ModelLifecycleStatus.APPROVED).model_copy(update={"bundle_id": "bundle-current"})
    target = candidate(status=ModelLifecycleStatus.APPROVED).model_copy(update={"bundle_id": "bundle-known-good"})
    store = InMemoryActiveBundleStore(initial=active_reference_from_metadata(current, generation=2, activated_at=NOW))
    return current, target, store


def test_rollback_requires_authenticated_human():
    _, target, store = setup()
    check = ModelRollbackService().check(request(), store=store, target=target, authorization=None)
    assert check.status is RollbackStatus.DENIED
    assert RollbackReasonCode.AUTHORIZATION_REQUIRED in check.reason_codes


def test_unknown_target_is_denied():
    _, _, store = setup()
    check = ModelRollbackService().check(request(), store=store, target=None, authorization=auth())
    assert check.status is RollbackStatus.DENIED
    assert RollbackReasonCode.TARGET_UNKNOWN in check.reason_codes


def test_incompatible_or_synthetic_target_is_denied():
    _, target, store = setup()
    target = target.model_copy(update={"synthetic_test_only": True})
    check = ModelRollbackService().check(request(), store=store, target=target, authorization=auth())
    assert RollbackReasonCode.TARGET_SYNTHETIC in check.reason_codes


def test_stale_active_state_is_rejected():
    _, target, store = setup()
    check = ModelRollbackService().check(request(active_generation=1), store=store, target=target, authorization=auth())
    assert RollbackReasonCode.STALE_ACTIVE_GENERATION in check.reason_codes
    assert store.active().bundle_id == "bundle-current"


def test_production_rollback_is_blocked_by_process_local_store():
    _, target, store = setup()
    check = ModelRollbackService().check(request(production_requested=True), store=store, target=target, authorization=auth())
    assert check.status is RollbackStatus.ACTIVATION_BLOCKED
    assert RollbackReasonCode.DURABLE_BACKEND_REQUIRED in check.reason_codes


def test_development_rollback_preserves_chain_and_metadata():
    _, target, store = setup()
    service = ModelRollbackService()
    check = service.check(request(), store=store, target=target, authorization=auth())
    result = service.execute(request(), check, store=store, target=target, simulation=True)
    assert result.status is RollbackStatus.ROLLED_BACK
    assert result.active_reference.bundle_id == "bundle-known-good"
    assert result.active_reference.generation == 3
    assert result.active_reference.previous_bundle_id == "bundle-current"
    assert len(store.history()) == 2


def test_denied_rollback_does_not_mutate_active_reference():
    _, target, store = setup()
    service = ModelRollbackService()
    check = service.check(request(active_generation=1), store=store, target=target, authorization=auth())
    result = service.execute(request(active_generation=1), check, store=store, target=target, simulation=True)
    assert result.status is RollbackStatus.ACTIVATION_BLOCKED
    assert store.active().bundle_id == "bundle-current"


def test_rollback_is_audited_without_prediction_history_mutation():
    _, target, store = setup()
    service = ModelRollbackService()
    req = request()
    check = service.check(req, store=store, target=target, authorization=auth())
    service.execute(req, check, store=store, target=target, simulation=True)
    events = service.audit_log.events()
    assert {event.event_type for event in events} == {event.event_type for event in events}
    assert any(event.event_type.value == "ROLLBACK_RECORDED" for event in events)


def test_missing_target_artifacts_are_denied():
    _, target, store = setup()
    target = target.model_copy(update={"artifact_references": ()})
    check = ModelRollbackService().check(request(), store=store, target=target, authorization=auth())
    assert RollbackReasonCode.TARGET_ARTIFACTS_MISSING in check.reason_codes


def test_naive_rollback_timestamp_is_rejected():
    values = dict(request().model_dump())
    values["request_timestamp"] = datetime(2026, 1, 1)
    try:
        RollbackRequest(**values)
    except Exception:
        return
    raise AssertionError("naive timestamps must not be accepted")
