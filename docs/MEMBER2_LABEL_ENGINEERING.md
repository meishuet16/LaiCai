# Member 2 — 7/14/30-Day Churn Labels

Status: first reproducible label-builder implementation. This module creates
training/evaluation targets from later observed lifecycle evidence. It does
not train models, split datasets, calibrate probabilities, or mutate feature
snapshots/predictions.

## Label structure

`ChurnLabelBuilder.build_labels(...)` returns one `ChurnLabel` for each
supported horizon: `7`, `14`, and `30` days. Each label contains:

- `tenant_id`, `customer_id`, and prediction cutoff `as_of`;
- `evaluation_as_of`, the cutoff through which outcome evidence was allowed;
- `horizon_days`;
- `label`: `1`, `0`, or `null`;
- explicit `label_status`;
- optional `churn_type` and `churn_effective_at`;
- `label_observed_through`;
- versioned `label_policy_version`;
- source evidence references;
- `label_generated_at`; and
- reason codes and limitations.

Statuses are:

- `positive`: confirmed qualifying churn, `label=1`;
- `negative`: complete trusted horizon observation with no qualifying churn,
  `label=0`;
- `unknown`: incomplete/censored or not-yet-available outcome evidence,
  `label=null`;
- `excluded`: known cancellation or already ineligible at prediction time,
  `label=null`; and
- `unsupported`: eligibility or account-level policy is unresolved,
  `label=null`.

Null is never interpreted as negative.

## Churn definition

The builder recognizes only explicitly mapped effective lifecycle event types:

- `voluntary_cancellation`;
- `non_renewal`; and
- `involuntary_termination` after collections.

The default event mapping includes `cancellation_effective`,
`voluntary_cancellation`, `cancelled`, `non_renewal`, `expired`,
`involuntary_termination`, and `collection_termination`, subject to a terminal
subscription status and a populated `effective_at` timestamp. Member 1 must
confirm the canonical event mapping before production use.

The following are not qualifying churn by themselves:

- a payment failure;
- a cancellation request or request timestamp;
- inactivity or missing usage;
- a predicted probability; or
- a current-state row without dated effective lifecycle evidence.

The effective churn timestamp is taken from `effective_at`, never from
`cancellation_requested_at`.

## Horizon rules and boundaries

For prediction cutoff `t` and horizon `h`, the exact event window is:

```text
(t, t + h]
```

Therefore:

- an event exactly at `t` is not a prospective positive and the account is
  excluded if reliable evidence establishes it was already terminated at the
  cutoff;
- an event exactly at `t+h` is positive for that horizon;
- an event at day 10 is outside the 7-day window but inside 14- and 30-day
  windows; and
- an event at day 20 is outside 7- and 14-day windows but inside the 30-day
  window.

A positive may be assigned before the full horizon matures when the qualifying
effective event and its availability are already reliably observed. A negative
requires trusted lifecycle observation through the entire horizon.

## Prediction time versus label observation time

`as_of` is the frozen prediction cutoff. It controls eligibility and is the
only cutoff relevant to the prospective population.

`evaluation_as_of` is a later outcome-evidence cutoff. The adapter includes an
outcome fact only when its applicable event/effective timestamp and trusted
availability timestamp are at or before `evaluation_as_of`. A late-arriving
outcome is not used before it becomes available.

`label_generated_at` records when the label result was produced and is
separate from both prediction time and outcome time. The label builder never
adds future outcome fields to `FeatureSnapshot` or changes `PredictionOutput`.

## Right censoring and missing coverage

An observation coverage record must be available by `evaluation_as_of` and
must establish complete lifecycle observation through the horizon. If coverage
ends at day 10, the 7-day label may be negative, while 14- and 30-day labels
remain unknown. Missing outcome coverage is unknown, not negative.

The in-memory adapter conservatively excludes facts with unknown availability
or availability after `evaluation_as_of`. When a late outcome is excluded,
the affected labels remain unknown rather than treating the outcome as absent.

## Known cancellations and ineligible accounts

If a cancellation request or scheduled termination was known and available at
prediction `as_of`, all three prospective labels are `excluded`. A request
after `as_of` does not retroactively exclude the earlier cutoff; a later
effective termination can still produce a positive label if it falls in the
window and is observed by `evaluation_as_of`.

Accounts already terminated or otherwise outside the active paying population
at `as_of` do not generate prospective labels. Failed payment events alone do
not change eligibility or produce churn labels.

## Multiple subscriptions and conflicting evidence

If more than one subscription is active and no explicit account policy is
provided, labels are `unsupported` with
`unresolved_multi_subscription_policy`. The builder never silently chooses
“any subscription” or “last subscription.” Optional explicit policies are:

- `any_subscription_end`; or
- `all_subscriptions_end`.

These policies still require team agreement before real training. Duplicate or
conflicting lifecycle evidence produces an unknown label with a conflict reason
instead of a definitive target.

## Member 1 adapter contract

Member 1 can implement `LifecycleOutcomeAdapter` against the canonical storage
without adopting a new database schema. It must provide:

- tenant/account-scoped prediction snapshots through the existing
  `PointInTimeDataAdapter` conventions;
- stable subscription/event IDs;
- subscription identity and account mapping;
- dated lifecycle event type, occurrence/effective timestamp, status, and
  paying entitlement state;
- source availability and/or received timestamps with the agreed precedence;
- explicit account-level observation coverage through future cutoffs;
- source correction/conflict information or a limitation when it cannot be
  reconciled; and
- authorization-scoped reads. Authentication and database authorization remain
  Member 1/backend responsibilities.

`InMemoryLifecycleOutcomeAdapter` is synthetic-only test infrastructure. It
does not create tables, an ingestion API, or a competing database model.

## Supervised-training eligibility

Only `positive` and `negative` labels with their required source evidence may
enter supervised training. `unknown`, `excluded`, and `unsupported` labels
must remain out of binary target fitting while being retained for coverage and
audit reporting. No real dataset is present in this repository, so these tests
demonstrate pipeline mechanics only and are not model-performance evidence.
