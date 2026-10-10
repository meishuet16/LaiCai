# Member 2 Outcome Reconciliation and Prediction Feedback

## Scope and evidence boundary

`outcome_reconciliation.py` is the Part 4 feedback boundary for Member 2. It
links an immutable canonical `PredictionOutput` snapshot to the existing
`ChurnLabel` produced by the shared Part 2 label builder. It does not define a
second churn policy, create a database or API, retrain a model, promote a
model, recommend an action, or estimate intervention causality.

The current repository has no authorized real longitudinal dataset. Synthetic
feedback is structural test evidence only and is never admissible for real
supervised learning. Real outcome feedback remains blocked until Member 1
provides authorized source provenance and complete lifecycle coverage.

## Prediction linkage and immutability

Every reconciliation request must provide:

```text
tenant_id, customer_id, prediction_id, prediction_run_id,
prediction_as_of, horizon_days, churn_label, evaluation_as_of,
evidence, reconciliation_policy_version, reconciled_at
```

The lookup identity is the tenant-scoped `prediction_id`. `prediction_run_id`
is copied for audit context and may be shared by many accounts; it is never
used as the prediction identity. Tenant, customer, customer cutoff, horizon,
prediction-run and label identity must all agree. Unknown IDs, cross-tenant
records, cross-customer labels, and mismatched runs are rejected.

The resulting `PredictionFeedback` stores a deep copy of the original
`PredictionOutput`, including probabilities, reliability, freshness,
uncertainty, explanations and model/feature/calibration versions. Reconciliation
adds outcome fields; it never edits the original forecast. Callers receive
copies from the in-memory ledger.

## Outcome lifecycle

The five feedback states represent outcome maturity, not predicted risk:

| State | Rule | Eligible for future supervised learning? |
|---|---|---|
| `PENDING` | The horizon has not matured, or ordinary outcome evidence is not yet available by the requested cutoff. | No |
| `MATURE_POSITIVE` | Existing `ChurnLabel` is positive; qualifying churn effective time is inside `(as_of, as_of + horizon]`; verified evidence was available by `evaluation_as_of`. Full horizon completion is not required. | Yes only after all later learning gates |
| `MATURE_NEGATIVE` | Existing label is negative; the complete horizon has elapsed; trusted lifecycle coverage reaches the horizon end; no qualifying churn occurred. | Yes only after all later learning gates |
| `INCOMPLETE` | The horizon passed but coverage/provenance is insufficient, evidence conflicts, or the multi-subscription policy is unresolved/unsupported. | No |
| `INELIGIBLE` | The original forecast was `known_cancellation`/`not_eligible`, or the existing label was explicitly excluded by the eligibility policy. | No |

The inclusive boundary is inherited from `ChurnLabel`: a qualifying event at
exactly `as_of + horizon` is positive; an event at exactly `as_of` is not in
the future window. Payment failure alone, inactivity alone and a cancellation
request date alone do not create a positive outcome.

The mapping is deliberately thin:

- `LabelStatus.POSITIVE` maps to `MATURE_POSITIVE` only after verified,
  available evidence checks.
- `LabelStatus.NEGATIVE` maps to `MATURE_NEGATIVE` only with complete coverage
  through the full horizon.
- `LabelStatus.UNKNOWN` maps to `PENDING` before maturity and `INCOMPLETE`
  after an unproven horizon.
- `LabelStatus.UNSUPPORTED` maps to `INCOMPLETE`.
- `LabelStatus.EXCLUDED` and known-cancellation/not-eligible prediction states
  map to `INELIGIBLE`.

Unresolved multi-subscription semantics, conflicting lifecycle evidence and
unverified provenance are hard blockers for mature feedback. They do not
become a negative label merely because time has passed.

## Evidence, availability and revisions

`OutcomeEvidence` records source references, provenance, source availability,
observed coverage, verification, conflicts and multi-subscription-policy
resolution. Missing `source_available_at` is not substituted with event time.
Evidence available after an earlier `evaluation_as_of` cannot mature that
earlier view.

The in-memory `InMemoryOutcomeReconciliationStore` is append-only:

- Repeating the same `feedback_id` with identical inputs is idempotent.
- Reusing a `feedback_id` with different inputs raises a conflict.
- A correction uses a new feedback ID, points to the prior ID with
  `supersedes_feedback_id`, requires a correction reason and receives a new
  revision number.
- Prior revisions remain readable.
- `latest_feedback_as_of` filters both reconciliation time and evidence
  evaluation cutoff, so a later correction cannot appear in an earlier view.

The store is a replaceable test implementation, not a production persistence
or event-queue design. A Member 1/backend implementation should preserve the
same append-only and tenant-scoped behavior.

## Historical evaluation integration

`feedback_labels_for_historical_evaluation(...)` is the narrow integration
boundary to the existing historical evaluator. It returns only mature
`ChurnLabel` records visible at a requested evaluation cutoff. The existing
evaluator remains responsible for metric arithmetic, chronological partitions,
coverage denominators and untouched-test safeguards; reconciliation does not
duplicate those metrics.

Prediction labels remain anchored to prediction `as_of`. Operational action
follow-up uses its own action/execution anchor and must not be mixed into these
feedback labels.

## Future learning admissibility

`assess_learning_eligibility(...)` only returns an admissibility decision. It
does not train or promote anything. Admission requires:

- mature positive or negative status for the exact tenant/customer/prediction
  and horizon;
- an eligible original prediction context;
- matching label policy versions;
- verified authorized-real provenance and source evidence;
- sufficient coverage, with no conflicts or unresolved subscription policy;
- evidence, evaluation, reconciliation and prediction timestamps no later
  than the intended training cutoff.

Pending, incomplete, ineligible, unsupported, unresolved, unverified and
synthetic/test-only feedback is rejected. The function does not inject future
outcomes into feature snapshots; the original point-in-time feature pipeline
remains authoritative.

## Part 3 compatibility handoff

`ActionFeedbackCompatibilityRecord` is a read-only shape for Member 3 to
expose, when available:

```text
tenant_id, customer_id, prediction_id,
action_id?, action_type, approval_state,
actual_execution_at?, outcome_observation_at?, evidence_refs
```

It intentionally includes `causal_effect_established=False`. Member 2 does not
recommend, approve, reject or execute actions, create an intervention store,
or infer that a later subscription outcome was caused by an action. Member 3
must keep action history distinguishable from source-backed churn truth.

## Part 4 dashboard handoff

Member 4 can serialize `PredictionFeedback` for pending/mature/incomplete/
ineligible views, prediction timelines, evidence references, policy/version
tracking and historical prediction-versus-outcome comparisons. The dashboard
must show source availability, evaluation cutoff and synthetic/test-only
provenance, and must not display an observed subscription outcome as “saved
revenue” or causal retention.

## Member 1 requirements and blockers

The real adapter must provide, tenant-scoped and correction-audited:

- stable account/subscription identity;
- the canonical lifecycle facts already consumed by `ChurnLabelBuilder`;
- qualifying churn effective timestamps and event/source IDs;
- source availability or received timestamps with a documented precedence;
- observation coverage through each horizon;
- authoritative account-level multi-subscription policy;
- provenance/authorization and correction semantics; and
- intervention exposure/action records separately from churn outcomes.

Current blockers are the absent authorized longitudinal dataset, unresolved
account-level multi-subscription churn policy, source availability/correction
semantics, and production storage/API ownership. No real performance,
retention, causal or ROI claim is made here.

## Improvement backlog

`IMPROVEMENT-001` Personalized Baseline Ablation Study,
`IMPROVEMENT-002` Multi-Subscription Churn Definition,
`IMPROVEMENT-003` Rule-Based Alert Threshold Validation, and
`IMPROVEMENT-004` Post-Adjustment Calibration Validation remain pending or
team decisions in `docs/MEMBER2_IMPROVEMENT_BACKLOG.md`. None is implemented
or marked complete by this task.
