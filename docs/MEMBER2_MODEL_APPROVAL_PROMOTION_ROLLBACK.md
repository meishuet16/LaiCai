# Member 2 — Model Approval, Promotion and Rollback Governance

## Scope

This milestone adds a fail-closed, typed governance boundary around the
candidate lifecycle. It is deliberately separate from the prediction pipeline,
the Part 1 database, and the existing metadata-only `ModelRegistry`.

The implementation is in:

- `src/retainiq_prediction/model_approval.py`
- `src/retainiq_prediction/model_promotion.py`
- `src/retainiq_prediction/model_rollback.py`

All inputs in the tests are explicitly synthetic fixtures. No real candidate,
production artifact, deployment, or customer data is claimed.

## Implemented

### Approval

`ModelApprovalLedger` records an immutable `ModelApprovalRecord` containing:

- approval ID and request/idempotency key;
- candidate bundle and candidate version;
- evaluation manifest and evidence references;
- `APPROVE` or `REJECT` decision and preserved rationale;
- actor reference, role, scope, decision time, policy version and audit refs;
- authorization status and verifier evidence ID;
- a derived `production_valid` flag.

An `ApprovalVerifier` is the replaceable boundary to an external identity and
RBAC/audit authority. A caller-provided role, boolean, signature-looking value,
or actor string is not authorization. Production approval requires verifier
evidence with `VERIFIED` status and `production_trusted=True`. The supplied
`SyntheticApprovalVerifier` is test-only and can never produce production-valid
approval evidence.

An approval request can be accepted only after an authorized real candidate has
all three model and calibration horizon versions, artifacts, an unchanged
sealed evaluation manifest, and an eligible real evaluation report. A reject
decision is recorded with its rationale and does not activate or mutate a
candidate. Duplicate identical request IDs are idempotent; conflicting reuse is
denied. Decisions and audit events are append-only in the local implementation.

Approval is not deployment.

### Promotion and active-bundle safety

`ModelPromotionService.check` keeps these states separate:

1. `APPROVED_FOR_CONSIDERATION` is the conceptual state after trusted approval
   (the check returns a denial if its required evidence is absent).
2. `TECHNICALLY_ELIGIBLE` requires compatible real provenance, all three
   model/calibration artifacts, matching candidate/evaluation fingerprints,
   deployment compatibility, rollback readiness, activation authorization, and
   a current active-bundle generation match.
3. `ACTIVATED` is returned only by an explicit compare-and-swap through an
   active-bundle store.

When approval is valid but the only remaining blockers are the missing durable
production backend or activation boundary, the check returns
`APPROVED_FOR_CONSIDERATION`; a later activation attempt returns
`ACTIVATION_BLOCKED`. This keeps approval, technical eligibility, and actual
activation distinct.

`InMemoryActiveBundleStore` is process-local, non-durable, and explicitly not
production-capable. It supports isolated pointer simulations, generation
checks, idempotency, transition history, and preservation of the prior bundle
reference. Production activation is blocked until Member 1/backend supplies a
durable atomic store and trusted activation boundary. No method changes
`PredictionPipeline` or loads an artifact.

Promotion checks reject synthetic provenance, missing or changed artifacts,
missing calibration/horizon entries, changed feature or label versions, stale
active generations, missing rollback targets, and missing trusted activation
authorization. No A/B traffic switch is implemented here.

### Rollback

`RollbackRequest` includes request ID, current active bundle/generation,
previous known-good bundle, actor and authorization evidence references,
reason, timestamp, policy version, and audit references.

Rollback requires an authenticated authorized human, a known compatible
approved real target with complete artifacts, and an expected-current match.
Production rollback is blocked by the process-local store. Development-only
simulation uses the same compare-and-swap boundary, increments the generation,
preserves the transition chain, and does not retrain, recalibrate, erase
history, or rewrite historical prediction metadata.

## Audit and security properties

`InMemoryGovernanceAuditLog` records approval decisions, promotion checks and
activation attempts, rollback checks and attempts, actor authorization status,
bundle IDs, timestamps, evidence references, outcomes, and reason codes. It
does not record customer PII or secrets. It is not durable, distributed, or a
production audit ledger; a trusted backend must replace it before production
use.

## Explicitly not implemented

- No production authentication/RBAC provider, durable audit database,
  deployment service, feature flag service, A/B router, or atomic distributed
  lock.
- No artifact loading, artifact signing/verification service, container
  rollout, health monitor, automated rollback, or external-service claim.
- No model training, calibration, threshold tuning, retraining, prediction
  pipeline mutation, API endpoint, dashboard, or decision-engine behavior.
- No automatic approval, automatic promotion, online self-modification, or
  rollback based only on metadata status.

## Integration contracts and dependencies

Member 1/backend must provide:

- a trusted actor identity and role/scope verifier that returns verifiable
  authorization evidence;
- a durable append-only audit store with request idempotency;
- a durable atomic active-bundle reference store with compare-and-swap,
  generation/versioning, prior-known-good retention, and deployment
  compatibility checks;
- authoritative artifact identity and integrity/provenance verification;
- canonical model/calibration/feature/label version records and a real
  deployment boundary.

Member 2 consumes the existing `ModelBundleMetadata`, frozen
`CandidateEvaluationReport`/`FrozenTestEvaluationManifest`, and registry
lifecycle. Members 3 and 4 should consume approval/promotion/rollback audit
references and preserve the model version attached to each historical
prediction. An approval record must not be interpreted as an active release.

The complete requirements remain preferred over older examples. The existing
registry's lightweight `HumanApproval` remains unchanged for compatibility;
the new module is the stricter external-verifier boundary for future release
integration.

## Verification

The focused governance suite contains 30 synthetic structural scenarios across
approval, promotion, active-pointer safety, and rollback. It checks fail-closed
authorization, candidate/champion separation, stale-generation rejection,
idempotency, audit records, no pipeline mutation, and process-local production
blocking.

The full pytest result and any Windows temporary-directory workaround are
recorded in `TEAM_LOG.md` for this milestone. Prompt 18's original 28-scenario
candidate-training/evaluation requirement still needs a final scenario-to-test
coverage review; that review is explicitly not performed by this milestone.
