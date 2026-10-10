# Member 2 outcome and coverage reconciliation

## Finding and scope

Prompt 25 investigated why the tenant-01 STANDARD v1.2 preparation reported no
mature labels. The evidence came from Member 1's authenticated, tenant-scoped
reader APIs using the existing tenant-01 analyst principal (retention-inference
purpose; authorized subscription, billing, and usage sources). Reads succeeded;
no source permission failure or tenant bypass was observed. The principal also
held `model_artifact_write`, which read-only preparation did not use; the
as-of reader APIs inspected require `retention_inference` and explicit source
authorization. No grant was expanded. Only tenant-01 was audited. The dataset
remains **SYNTHETIC_ONLY**; no model was trained.

The zero-label result had two Member 2 interpretation defects, not a missing
dataset or failed API read:

1. Member 1's canonical effective lifecycle fold emits qualifying termination
   facts with status `ended`. Member 2's `ChurnEventSemantics.terminal_statuses`
   did not recognize that status. The event type and effective timestamp were
   present, but the label builder would not accept the terminal fact.
2. Subscription outcome coverage is emitted as weekly/segmented intervals.
   The label builder previously required one interval to span an entire
   prediction horizon. It failed to join exactly adjacent complete intervals,
   so a fully covered horizon could remain unknown. The correction joins only
   continuous, complete subscription intervals; any gap, outage/partial segment,
   or missing coverage remains unknown. Usage coverage cannot prove paid
   subscription retention.

A further synthetic lifecycle review found that a reactivation followed by a
later termination could be treated as conflicting evidence, and the multi-
subscription selector could report the first subscription end rather than the
instant the final paid entitlement ended. Member 2 now reconstructs subscription
state at candidate termination times under the synthetic-only final-entitlement
policy: it preserves the first observed churn episode after reactivation,
requires no paying subscription at account churn, and records the final-loss
timestamp with evidence refs for the ending entitlements. This is not a real
customer policy.

The SQLite adapter already requested subscription lifecycle facts and
subscription-only coverage at each `evaluation_as_of`. The Member 1 API
filters facts by occurrence and source availability/receipt at that evaluation
cutoff. Prediction feature reads remain separate at original `as_of`; outcome
facts are not added to `FeatureSnapshot`. The earlier audit found no evidence
that outcomes were being evaluated at the wrong cutoff.

The inspected call paths are:

- Feature snapshot: `get_account_snapshot_as_of(db, principal, customer_id,
  as_of=T)`, `get_events_as_of(db, principal, customer_id, as_of=T)` for
  authorized categories, and `get_subscriptions_as_of(db, principal,
  customer_id, as_of=T)` for historical lifecycle cross-check. Event reads
  require `occurred_at <= T` and `COALESCE(source_available_at, received_at)
  <= T`.
- Outcome snapshot: `get_events_as_of(db, principal, customer_id,
  as_of=evaluation_as_of, category="subscription")`, then
  `get_observation_coverage_as_of(db, principal, customer_id,
  as_of=evaluation_as_of, source_category="subscription")`. Coverage is
  filtered by `coverage_available_at <= evaluation_as_of` and carries covered
  interval, status, completeness, and policy version. Outcome reads do not
  query the prediction cutoff as a substitute for the later evaluation cutoff.

## Authorized source evidence

Across tenant-01, the authorized lifecycle reader returned 160 terminal
records across 155 accounts: 147 involuntary terminations, 5 non-renewals,
and 8 voluntary cancellations. Effective dates ranged from 2024-12-10 to
2026-09-28. The coverage API returned 39,824 subscription outcome rows:
37,099 complete, 1,162 outage, 63 partial, 750 censored, and 750 not-created.
These are source rows, not independent customers or churn labels.

Matching those returned outcomes to the existing weekly cutoff/horizon
schedule found 119 7-day, 241 14-day, and 520 30-day qualifying event/cutoff
candidates; each was available by its relevant label evaluation cutoff. A
bounded tenant-01 cutoff smoke produced positive and negative labels after the
two corrections (7d 1/295, 14d 2/294, 30d 7/289 positive/negative, with one
enumerated account routed to known-cancellation by Member 2). This is a
diagnostic of label mechanics, not a full-dataset distribution or model result.

The 39,824 coverage-row API total is a unique source-row audit count. In the
prepared manifest, coverage status counts are repeated observation records
across account-cutoff/horizon evaluations and therefore are not unique source
rows. The full run's horizon outcome totals are separately reported as
positive/negative/unknown over eligible prediction snapshots.

At `2026-09-30T23:59:59Z` (the end-exclusive dataset's last included instant),
the tenant-scoped authenticated lifecycle audit covered 750 customer
identities: 629 had a paying entitlement (625 eligible, 4 known-cancellation
under Member 2's conservative rule), and 121 were not eligible. It found 155
accounts with qualifying termination evidence across 160 termination facts,
137 observed active-to-no-paying-entitlement transitions, 75 accounts with
multiple historical subscription IDs, 23 with a termination while another
entitlement remained active, and 154 with a later paid-active lifecycle fact
after an earlier qualifying termination. These are tenant-01 source-derived
aggregate counts, not generator scenario labels or supervised samples.

The complete corrected re-preparation's aggregate labels and artifact hashes
are recorded in `MEMBER2_SYNTHETIC_HISTORICAL_DATASET_PREPARATION.md`. Do not
interpret source-row event/candidate counts as full-run account labels.

The mismatch between Member 1's eligible-account enumerator and Member 2's
bounded sample is localized to cancellation semantics: Member 1's account
snapshot marks an account known-cancellation only when **all** active
subscriptions are pending cancellation; Member 2's eligibility helper marks
known-cancellation when **any** subscription fact has a request/scheduled
termination known by the cutoff. This is a confirmed contract divergence, not
a permission or timing failure. The conservative Member 2 routing was not
changed because the shared account-level known-cancellation rule and behavior
for partial multi-subscription cancellation require team agreement. It may
conservatively exclude accounts whose remaining subscription is still active.

## Corrections and guardrails

- Recognize Member 1's `ended` terminal status only alongside a supported
  effective churn event type and effective timestamp.
- Preserve source category, coverage status, completeness, and policy version
  on each typed `OutcomeObservation`; reject contradictory status/completeness.
- Join adjacent coverage intervals only when every point from `as_of` through
  the required horizon is covered by complete subscription outcome evidence.
  Subscription-specific coverage must cover every active entitlement.
- Keep `available_at <= evaluation_as_of` enforcement. A positive still
  requires an observed, available qualifying event; a negative still requires
  full-horizon elapsed time and complete trusted outcome coverage.
- Keep outcome evaluation and original prediction `as_of` distinct. No
  outcome evidence enters earlier features.
- For the synthetic final-entitlement policy, reconstruct lifecycle state at
  each candidate effective time, preserve reactivation episodes, and label
  account churn at the final entitlement-loss time. If lifecycle states at a
  point are contradictory, keep the result unknown.
- Do not change freshness thresholds or infer source health from the mere
  absence of an event. Independent lifecycle/billing completeness heartbeats
  remain unavailable.
- Member 1's as-of APIs filter late/unavailable rows before returning facts,
  but do not provide per-query counts for those filtered rows. Returned facts
  are time-safe; absence versus filtered-late evidence cannot be quantified
  from the API result alone.

## Coverage-to-test matrix

| Reconciliation scenario | Regression coverage |
|---|---|
| Member 1 `ended` effective event maps to positive; excluded from earlier feature view | `tests/test_outcome_coverage_reconciliation.py::test_member1_ended_status_maps_to_positive_without_feature_time_leakage` |
| Adjacent complete intervals mature negatives; gaps/outages/partial segments do not | `tests/test_outcome_coverage_reconciliation.py` interval/gap/outage cases; `tests/test_label_builder.py` full and incomplete observation cases |
| Usage-only coverage is not subscription retention evidence | `tests/test_outcome_coverage_reconciliation.py::test_usage_coverage_cannot_prove_subscription_retention` |
| Each active subscription needs outcome coverage; partial termination is not final account churn | reconciliation subscription-specific case; `tests/test_label_builder.py::test_unresolved_multi_subscription_policy_is_unsupported`; Data Foundation partial-cancellation case |
| Future/late facts remain unavailable before source availability | `tests/test_label_builder.py` future and late-arrival cases; `tests/test_sqlite_data_adapter.py::test_adapter_defense_excludes_late_and_unknown_availability`; Data Foundation late-source cases |
| Known cancellation and payment failure semantics | `tests/test_label_builder.py` cancellation/payment cases; `tests/test_sqlite_data_adapter.py::test_payment_failure_is_billing_evidence_not_churn` |
| Tenant/source authorization, dataset identity, and no database mutation | `tests/test_sqlite_data_adapter.py` authorization, identity, source filters, and unchanged database cases; `tests/test_data_foundation.py` purpose/tenant/source authorization cases |
| Prediction cutoff is not outcome observation cutoff | `tests/test_outcome_coverage_reconciliation.py::test_prediction_and_outcome_cutoffs_remain_distinct_and_timezone_aware`; `tests/test_sqlite_data_adapter.py::test_outcome_adapter_keeps_prediction_and_evaluation_cutoffs_separate` |
| Partial cancellation and account enumeration | `tests/test_data_foundation.py::test_partial_subscription_cancellation_keeps_account_eligible`; existing eligibility cancellation/multiple-subscription tests; live mismatch is reported only as an aggregate, not by ID |
| Reactivation, episode boundaries, label maturity, conflicting lifecycle evidence | `tests/test_label_builder.py` boundary, late-arrival, already-terminated, cross-tenant, and conflict tests; temporal split maturity and TEST-isolation tests |
| Reactivation followed by another termination; final loss after multiple subscriptions; partial loss with reactivation | `tests/test_outcome_coverage_reconciliation.py::test_reactivation_keeps_first_effective_churn_episode_as_positive`, `::test_multi_subscription_churn_effective_time_is_final_entitlement_loss`, and `::test_reactivated_entitlement_prevents_false_final_account_churn` |

The exact final focused and full-suite results are recorded in the preparation
report and `TEAM_LOG.md`.

## Member 1 integration requirements

The real adapter needs the following source-backed fields, exposed through the
existing authenticated APIs (not a new schema):

- Stable tenant, customer/account, subscription, source, and event/coverage
  identifiers.
- Lifecycle event type, lifecycle status, occurred/effective timestamps,
  source-provided availability timestamp and/or actual `received_at`, and
  paying-entitlement semantics sufficient to reconstruct state as-of a cutoff.
- Coverage interval start/end, `coverage_available_at`, source category,
  coverage status, completeness, observation policy version, and subscription
  identity when coverage is subscription-specific.
- Explicit source correction/supersession semantics and a trusted completeness
  watermark/heartbeat for lifecycle and billing sources.
- Read diagnostics that distinguish absent records from rows excluded because
  they were late, unavailable, or out of scope, without exposing other tenants.

Availability precedence still follows the adapter's configured conservative
source-availability/receipt policy; this task does not establish a new
team-wide policy. Current-state subscription projections must not replace
dated historical lifecycle evidence. Production authorization remains the
backend's responsibility.

The least-privilege functional access needed by this preparation is the analyst
role, `retention_inference` purpose, and explicit tenant-scoped grants for the
authorized subscription, billing, and usage sources. No billing-valuation
permission is needed. The provisioned service principal also had
`model_artifact_write`; this task did not use artifact-writing APIs. The
purpose is not required by the inspected as-of reader functions; it is an
additional grant carried by the provisioned principal, not a reason to expand
access.

### Proposed Member 1 acceptance tests

1. At evaluation cutoff `E`, return only lifecycle facts whose occurrence and
   agreed availability/receipt timestamps are no later than `E`; prove a late
   received event is absent at earlier `E` and available afterward.
2. Return coverage with stable tenant/account/subscription/source identifiers,
   category, interval boundaries, status, completeness, policy version, and
   availability timestamp. Adjacent complete intervals are joinable; a gap,
   outage, partial, or not-created interval remains distinguishable.
3. Demonstrate that loss of one of multiple paid subscriptions is not account
   churn while another qualifying entitlement remains, and that final
   entitlement loss is dated at its actual effective time.
4. Verify source/purpose authorization, cross-tenant denial, and safe aggregate
   counts for late/unknown-availability records without leaking their IDs.
5. Keep operational heartbeat/completeness separate from latest event time;
   test stale, quiet-but-healthy, and missing-heartbeat cases.
6. Resolve and test the `any` versus `all` known-cancellation rule for
   multi-subscription accounts in both Member 1 enumeration and Member 2
   eligibility.

## Remaining blockers

- Full synthetic label/split class support is not inferred from aggregate
  dataset episode counts; use only the completed corrected preparation output.
- One bounded-cutoff eligibility mismatch was localized to Member 1's `all`
  versus Member 2's `any` known-cancellation semantics. Team agreement is
  required before changing either contract; the diagnostic account ID is not
  present in logs or documentation.
- Lifecycle and billing lack independent completeness heartbeats, so stale
  event watermarks cannot distinguish a quiet source from an ingestion gap.
- Real account-level multi-subscription churn semantics and source correction
  policy remain unresolved; the effective-account-churn-v1.2 rule is
  synthetic-dataset-only.
- Synthetic training readiness is determined per horizon and per frozen
  partition in the full-run report. Real-world readiness remains blocked.
