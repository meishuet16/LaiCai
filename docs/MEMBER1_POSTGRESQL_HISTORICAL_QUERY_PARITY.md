# Member 1 PostgreSQL historical-query parity — Prompt 06D-2

## Implementation boundary and verification status

This change ports the existing `get_events_as_of()`,
`get_subscriptions_as_of()`, `get_account_snapshot_as_of()`, and
`get_observation_coverage_as_of()` reads to PostgreSQL, and enables the
existing `record_observation_coverage()` write. It reuses the established
principal checks, event normalizer, subscription fold, valuation functions,
result shapes, and error codes. It does not claim full PostgreSQL Data
Foundation parity or production readiness.

The implementation is live-verified against a task-owned, disposable
PostgreSQL **16.15** cluster and database. The original startup attempt was
denied while PostgreSQL tried to bind both `::1` and `127.0.0.1`; port 62534
was free and no listener owned it. Starting the same verified cluster with
explicit IPv4-only `-h 127.0.0.1 -p 62534` succeeded. Docker was unavailable
(no Docker Desktop engine pipe); the unrelated Windows PostgreSQL service was
not used. A psycopg 3.3.6 smoke verified `SELECT 1`, current database and
server identity, transaction commit and rollback, and connection closure.

The guarded live suites passed: **5** migration integration tests, **11**
ingestion/concurrency tests, and **11** historical-query/coverage tests (**27
unique live PostgreSQL integration tests**). The 11 shared historical
fixtures also passed on SQLite with the same normalized expectations. Full
discovery ran **138 tests: 138 passed, 0 failed, 0 errors, 0 skipped**, in
**42.118 seconds**. The three focused runs took 1.912, 13.590, and 13.654
seconds, respectively. Python **3.12.14**, psycopg **3.3.6**, and PostgreSQL
**16.15** were used. No Python warnings were reported; expected unauthorized
request log lines appeared in the full suite. `compileall`, package imports,
and `git diff --check` passed. No live test skip remains.

The disposable database was named `retaniq_test_06d2v_20261010`, created
only after confirming it did not exist, then dropped after verification. The
task-owned cluster was stopped; the separate Windows service was left
untouched. No credentials or customer data were used or recorded. No
PostgreSQL-specific defect was confirmed, so no additional code fix was
needed. The live and SQLite contracts matched for the cases below.

## Event time, availability, and output contract

Historical event and subscription queries preserve the existing SQLite
predicate exactly:

```text
occurred_at <= as_of
AND COALESCE(source_available_at, received_at) <= as_of
```

Both comparisons are inclusive. `source_available_at` wins when populated;
`received_at` is the existing fallback. Imported first-availability times
remain separate from receipt/ingestion time. The implementation does not
count excluded rows or fabricate exclusion statistics. PostgreSQL cutoffs
are bound as aware UTC `datetime` objects against `TIMESTAMPTZ`; results are
serialized to the existing UTC ISO-8601 `Z` strings. SQLite retains its
normalized UTC text representation. Query ordering remains occurrence time,
effective availability time, then canonical `event_id` as a deterministic
tie-breaker.

The event result retains tenant/customer identity, source provenance, source
event ID, occurrence/receipt/availability times, mapping/schema versions,
usage quantities and units, billing status, and subscription changes. Source
authorization is validated from stored principal grants on every read, and
historical rows are constrained by the current source/category grants (service
principals use the category grants configured for each authorized source).
Billing amount/currency and subscription price/interval fields are included
only for a principal granted `billing_valuation`; restricted attributes are
not placed in errors or debug output. Application authorization is not RLS.

## Subscription reconstruction and valuation

`get_subscriptions_as_of()` folds append-only dated subscription events
visible at the cutoff; it does not read the latest mutable `subscriptions`
projection as historical truth. Lifecycle event meaning remains shared with
SQLite: payment failure is billing risk, cancellation request is
`pending_cancel`/known cancellation rather than termination, and effective
cancellation/non-renewal/involuntary termination ends that subscription.
Plan, price, discount, interval, and status changes are point-in-time. A
future start or future event cannot make an earlier account eligible. A late
arriving event is excluded until its historical availability (or receipt
fallback) is at or before the cutoff. Multiple subscriptions are retained;
partial termination leaves the account eligible while another qualifying
subscription remains active. Reactivation is represented by later dated
events. Same-time lifecycle changes follow the existing ordering by
occurrence, availability, and `event_id`.

The existing valuation policy is reused unchanged (`mrr-monthly-v1`): integer
minor units, existing `Decimal` half-up monthly normalization, interval/count
and recurring discount handling, ISO currency validation, and no FX
conversion. Active subscriptions aggregate only in one currency. Missing
price, mixed currency, missing state, and no-active-subscription statuses
remain explicit; unavailable MRR is not converted to zero. Inactive
subscriptions do not contribute. Account snapshots expose valuation only
when `billing_valuation` is authorized; subscription reads likewise omit
valuation/pricing fields for principals without that purpose. The
synthetic-v1.2 final-paid-entitlement-loss interpretation remains synthetic
label evidence, not a new real-data churn definition. Real-data account-level
multi-subscription label policy remains a team decision.

## Observation coverage

Coverage write/read uses the existing row contract: tenant/source/category,
coverage ID, interval `[covered_from, covered_through)`, status, completeness,
availability time, policy version, and normalized idempotency digest. Writes
require the existing integration identity-mapping purpose, stored principal
revalidation, a customer identity mapped to that source, and the existing
dataset-identity guard. PostgreSQL uniqueness uses
`(tenant_id, source, coverage_id)`; matching repeats return duplicate and a
changed payload returns `idempotency_conflict`. Coverage reads use only the
principal's authorized sources and rows whose `coverage_available_at <=
as_of`, then serialize the three timestamp fields to the existing UTC string
contract. Existing rows are returned as intervals and are not reinterpreted
or silently merged.

No coverage row means unknown, not verified zero activity. A complete
coverage interval with no usage events is distinct from missing, partial,
outage, delayed, missing-backfill, censored, not-created, and entitlement-ended
coverage. This change does not add an independent lifecycle/billing
heartbeat, infer source freshness from the latest event, change overlapping
interval semantics, or backdate coverage availability. Historical evaluation
must continue to treat unknown/incomplete horizons as unknown, not mature
negative outcomes.

## Backend comparison and scenario map

The implementation uses `DatabaseConnection` and the existing safe qmark
adapter. Only timestamps are explicitly adapted at the repository boundary;
PostgreSQL-specific conflict handling for coverage remains visible at the
write call site. There is no SQLite fallback. Read operations use one
connection and do not write projections or events.

| Scenario group | Shared SQLite/PostgreSQL fixture methods | Existing SQLite regression contracts |
|---|---|---|
| Event cutoff, availability fallback, equality, timezone offsets, deterministic ties, usage quantities | `test_event_cutoff_uses_occurrence_and_existing_availability_fallback`, `test_time_offset_equivalence_and_stable_same_timestamp_order` | `test_event_with_late_source_availability_is_excluded_at_cutoff`, `test_live_event_received_after_cutoff_cannot_retroactively_appear` |
| Tenant/source/purpose/category auth, billing redaction, read-only queries | `test_authorization_redaction_and_cross_tenant_isolation`, `test_stored_category_grants_filter_historical_reads`, `test_historical_queries_do_not_mutate_event_history` | `test_tenant_scopes_event_reads_and_identity_writes`, `test_source_authorization_enforces_configured_purposes`, `test_retention_only_reader_can_read_usage_but_not_valuation_data` |
| Subscription start, future visibility, request vs effective end, late price, payment failure, partial termination, reactivation, multiple subs | `test_historical_subscription_lifecycle_and_cutoff_valuation`, `test_payment_failure_does_not_end_entitlement_and_unauthorized_mrr_is_absent`, `test_multiple_subscriptions_partial_termination_and_reactivation` | `test_subscription_state_reconstructs_by_cutoff_and_pending_cancel_is_known`, `test_known_future_start_does_not_make_account_eligible_early`, `test_effective_subscription_event_ends_entitlement_in_as_of_projection`, `test_payment_failure_is_billing_risk_not_subscription_termination`, `test_partial_subscription_cancellation_keeps_account_eligible` |
| MRR annual normalization, price changes, missing and mixed currencies, zero-decimal values | `test_historical_subscription_lifecycle_and_cutoff_valuation`, `test_missing_and_mixed_currency_valuation_remain_unavailable` | `test_as_of_mrr_normalizes_intervals_discounts_and_missing_prices`, `test_account_mrr_does_not_sum_mixed_currencies_or_missing_values`, `test_multiple_subscriptions_sum_only_when_currency_matches`, `test_zero_decimal_currency_keeps_source_minor_units`, `test_price_change_is_reconstructed_at_historical_cutoff` |
| Coverage complete/partial, missing-vs-zero, delayed availability, attribution, source scope, idempotency | `test_coverage_as_of_idempotency_and_missing_is_not_zero`, `test_coverage_partial_and_tenant_source_scope` | `test_coverage_and_dataset_identity_are_available_only_to_authorized_as_of_readers` |

The live PostgreSQL subclass reuses the same logical fixtures and expected
outputs. Tests require both `RETAINIQ_POSTGRES_TEST_DSN` and
`RETAINIQ_POSTGRES_TEST_DISPOSABLE=1`, plus a loopback host and a database
whose name begins `retaniq_test_`; they do not authorize arbitrary targets.
The migration suite uses a unique temporary schema and drops that schema in
`tearDownClass`; ingestion and historical contracts use unique synthetic
tenant/customer/source IDs in the disposable database. The verification
operator created the exact disposable database above, ran the guarded suites,
then dropped only that exact database and stopped only the task-owned cluster.
The full discovery run had no PostgreSQL skips.

## Member 2 handoff and remaining work

The read shapes and permission rules remain the established interfaces
documented in
[`MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`](MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md):
event list, subscription list, account snapshot, and source-attributed
coverage list. The tested cases provide equivalent authenticated values on
SQLite and PostgreSQL. No Member 2 code or separate integration worktree was
changed. The synthetic data handoff's account/day usage quantity, evidence
classification, and unknown-coverage rules remain authoritative. Member 2's
reported blockers remain unresolved and are not fixed by this query parity:
zero mature positive/negative labels across 7/14/30-day preparation,
insufficient authorized outcome-observation coverage, 97.21% stale or
insufficient historical snapshots, and no independent lifecycle/billing
freshness heartbeat. Keep these in the cross-member backlog; do not infer
coverage or readiness from this verification.

06D-3 still owns feature snapshot, churn label, and prediction persistence
parity, plus any required import/checkpoint/replay or dataset provisioning
parity not already included in 06D-1. Full synthetic STANDARD PostgreSQL
import, end-to-end Member 2 connection, and WSGI API startup remain outside
this scope. Supabase, RLS, Supabase Auth, production deployment, and
cross-member integration are also unimplemented. PostgreSQL historical-query
parity is verified for this scope; this does not make the PostgreSQL Data
Foundation production-ready or clear the separate Member 2 blockers.
