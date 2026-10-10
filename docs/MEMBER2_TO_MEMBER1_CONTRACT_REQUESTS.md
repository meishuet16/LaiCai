# Member 2 → Member 1 Contract Requests

Prompt 26 audit, branch `integration/member2-main-sqlite`. These are requests
for agreement and backward-compatible extensions—not implemented APIs. No
Member 1 files or schemas are changed here. Decision owner names are absent
from the repository; the project lead must name the accountable domain-policy
approver before P0 policy is treated as authoritative.

## P0 — Policy decision required

### Known cancellation and account churn policy

**Current behavior (confirmed in code):** `retaniq.data_foundation.get_account_snapshot_as_of`
folds subscription events visible by the cutoff, defines active entitlement as
`active`, `past_due`, or `pending_cancel`, then emits `known_cancellation` only
when every active entitlement has `pending_cancel` or a current
`cancellation_requested_at`. Member 2's eligibility helper instead scans the
visible facts for any request/scheduled date at or before `as_of`; the
SQLite/Synthetic v1.2 adapter explicitly enables the synthetic account policy
and may therefore route an account to `KNOWN_CANCELLATION` when only one of
several active subscriptions has a request. Without an explicit account policy,
multiple active subscriptions can be `INSUFFICIENT_DATA` before cancellation
routing. Member 2 also sees a historical request on an ended subscription, or
a request later cleared by an update, because the historical fact remains.
Member 1's latest-state fold can represent a cleared request when an update
changes `cancellation_requested_at` to null and returns the subscription to an
active status.

The canonical requirement freezes the rule that a cancellation request known
at/before the prediction cutoff excludes prospective scoring and that the
prediction unit is a paying subscription account. It does not explicitly
specify aggregation across multiple subscriptions, whether ended-subscription
requests still count, or how a reversal changes current intent. Those details
require a shared decision; do not silently choose either implementation.

| State at cutoff | Member 1 current account status | Member 2 current path | Contract status |
|---|---|---|---|
| One active paid subscription, no request | `eligible` | `ELIGIBLE` | Frozen rule; aligned |
| One active subscription, request visible | `known_cancellation` | `KNOWN_CANCELLATION` | Frozen rule; aligned |
| Two active, one request | `eligible` (all-active test is false) | `KNOWN_CANCELLATION` with explicit synthetic policy; otherwise may be insufficient without a policy | Aggregation unresolved; denominator divergence confirmed |
| Two active, both requests | `known_cancellation` | `KNOWN_CANCELLATION` with explicit policy | Same result, although multi-subscription rule still needs approval |
| One subscription ended, another active | `eligible` if no remaining active sub has a request | `ELIGIBLE` without a visible request on ended history; `KNOWN_CANCELLATION` if that ended subscription's request remains in the facts | Account still has paid entitlement; whether old request counts is unresolved |
| Final paid entitlement ended before cutoff | `not_eligible` | `NOT_ELIGIBLE` when dated terminal history is complete | Frozen paying-account population rule |
| Cancellation request later reversed | Latest-state fold can return `eligible` after a visible active/null update | Historical request scan can still return `KNOWN_CANCELLATION` | Reversal event semantics and policy unresolved |
| Reactivation after prior final loss | Current paid state can be `eligible` | Current state can be eligible, subject to retained request history | Synthetic v1.2 treats a later active entitlement as a later episode; real episode semantics need approval |
| Missing, late, contradictory lifecycle evidence | May omit the account or fail to establish state | `INSUFFICIENT_DATA` / abstention when evidence is missing or ambiguous | Frozen evidence-quality rule; API needs explicit completeness evidence |

Member 1's `list_eligible_accounts_as_of` returns only accounts whose folded
account status is `eligible`; Member 2's historical preparation then applies
its own eligibility logic to enumerated customers. The confirmed any/all
divergence can conservatively remove one-pending/multi-active snapshots from
Member 2's eligible denominator (rather than incorrectly score them). A stale
request on an ended/reversed subscription can similarly cause a false
known-cancellation route. Effective final-entitlement loss is a separate
outcome-label concern: Member 1 emits `ended` on effective cancellation,
non-renewal, and involuntary termination; Member 2's synthetic v1.2 label
policy reconstructs whether any paid entitlement remains. Do not conflate
either with request-time routing.

Member 3 should receive the canonical prediction route/status and must not
independently reinterpret subscription requests. Member 4 should preserve
`prediction_id`, source-backed lifecycle evidence, and any policy version used
for feedback/timeline reconciliation. No actual cross-member timeline or
Decision Engine integration was found in this local repository state; impact
is a contract handoff, not a claim of deployed behavior.

**Proposed versioned contract for review (not adopted):**
`account-lifecycle-policy-v1`, with separate, named decisions for (a) paying
account aggregation, (b) cancellation intent aggregation/reversal, and (c)
effective churn as final paid-entitlement loss. Alternatives are: (1) *any
active subscription request excludes account*—matches the broad reading of
the canonical known-request exclusion, but can suppress risk of remaining
entitlements; (2) *all active subscriptions must be pending*—matches Member 1
today, but can score an account with an already-known cancellation; or (3)
route/track subscription-level intents and derive an account route only under
an approved account policy—more expressive, but requires compatible API and
Part 3 routing. For reversals, choose between current-state intent (a verified
reversal clears the route) and irrevocable known-request history (route remains
excluded). The designated product/domain owner must approve; Member 1 owns the
canonical fold/API, and Members 2/3/4 must sign off on training, routing, and
feedback consequences. Keep existing tested behavior until approval.

## P0 — Source evidence needed

### Historical lifecycle observation and operational health

**Available today:** the tenant-scoped authenticated Member 1 event API returns
`tenant_id`, `customer_id`, source/event identity, category/type,
`occurred_at`, `received_at`, optional `source_available_at`, and mapped
subscription changes. It filters to `occurred_at <= as_of` and
`COALESCE(source_available_at, received_at) <= as_of`. Subscription coverage
is separately read through `get_observation_coverage_as_of`; it is scoped by
tenant/account and authorized sources and includes source/category, coverage
ID, covered interval, status, completeness, `coverage_available_at`, and
`observation_policy_version`, filtered by availability at the requested
cutoff. The existing coverage write/read contract is account-scoped; it has no
subscription ID, so it cannot prove per-subscription coverage independently.

Member 1's integration-health functions expose integration/source-level
`last_successful_ingestion_at`, `last_failure_at`, failure code,
`availability_status` (`unknown`, `degraded`, or `observed`), and
`freshness_status` (currently always `unknown`). Operator health requires an
authorized service principal and `integration_health`; integration health is
scoped to the caller's integration. This is operational sync telemetry, not a
historical source watermark or proof that every lifecycle/billing account was
observed. The Member 2 SQLite adapter does not consume this health API: it
derives freshness from latest account event times and usage coverage. Prompt 27
confirmed a source-state attribution bug: absence of account-scoped lifecycle,
billing, or usage-coverage rows was mapped to `connected=False`, emitting
`SOURCE_NOT_CONNECTED` without operational health evidence. Member 2 now maps
missing connection evidence to `null`/unknown; explicit `connected=False`
remains stale and blocking. Silence is not inferred healthy, and no thresholds
changed. Existing prepared aggregate counts have not been recomputed under
this fix. No explicit expected cadence, completeness heartbeat, historical
`observed_through`, or versioned source-health history is supplied.

**Request:** provide a backward-compatible, authenticated read (or append-only
versioned health facts) with proposed fields:

```text
tenant_id (backend-derived), source, category,
observed_at, source_available_at?, received_at,
status: healthy | partial | outage | unknown,
last_successful_sync_at?, observed_through?, expected_cadence?,
policy_version, provenance, completeness?/limitations?
```

Treat sync success as operational health only; `observed_through` and coverage
status must separately establish source completeness. Include scope (tenant /,
where supported, customer or subscription) explicitly. Every timestamp must
preserve its actual meaning and be timezone-aware. The read must return only
facts available by requested `as_of`; do not synthesize a heartbeat from event
silence or current-state projections. A migration/new endpoint may be needed;
field names above are proposals, not current API.

- **Authorization:** tenant derived from authenticated context; existing
  `retention_inference` purpose and explicit source/category grants for model
  reads. Operational health may require the existing operator
  `integration_health` scope; no cross-tenant aggregates by default.
- **Time:** retain observed/source-available/received/sync/watermark timestamps
  independently; exclude metadata unavailable at the historical cutoff.
- **Acceptance:** quiet-but-healthy source is distinguishable from missing
  heartbeat; outage/partial/unknown remain explicit; future heartbeat is
  excluded at earlier cutoff; a sync timestamp alone does not assert complete
  lifecycle or billing follow-up; unauthorized tenant/source is denied.
- **Compatibility / owner / impact:** additive response or separately versioned
  health endpoint; Member 1 owns implementation, team approves policy. **P0
  blocked** for defensible operational scoring freshness and source-complete
  negatives.

## P1 — Diagnostics and efficiency

### Authorized late-arrival aggregates

**Current behavior:** authorized as-of event reads filter unavailable/late
rows before returning them. Member 2 cannot count filtered rows and must not
infer that the count is zero.

**Proposed aggregate-only response:** tenant derived server-side; authorized
source/category; observation window and `as_of`; `events_examined`,
`excluded_by_occurrence_cutoff`, `excluded_by_availability_cutoff`, plus
`statistics_status: measured | unavailable` and completeness/limitations.
Unavailable counts are null, while measured zero is numeric zero. No event
IDs, payloads, customer IDs, or other tenant data. Do not change the feature
visibility filter. Access requires authorized operator/analyst purpose and
exact source grants; no unrestricted SQL or raw event endpoint. Test measured
zero vs unavailable, late vs future-occurrence counts, tenant/source denial,
and payload non-disclosure. Additive endpoint; Member 1 owns it. **P1
nonblocking** for point-in-time correctness, blocking for quantified late-row
diagnostics.

### Coverage reporting and bounded reads

Coverage APIs already expose interval/status/completeness/availability/policy
version, but only per customer and only rows available at cutoff. Aggregate
coverage reporting should count complete/partial/outage/delayed/not-created/
censored/gapped intervals within tenant/source grants and never equate absent
events with zero activity. The coverage contract currently has no
`subscription_id`; add it only if source systems can prove it and downstream
policy requires it. Prompt 27's bounded STANDARD pilot could not run because
the tenant-scoped reader credential was not present in the process
environment; the previous run's aggregate counts remain the only measured
baseline. The measured 234,495 calls/950.910 seconds are dominated by
point-in-time reads (572.882s) and outcome reads (120.845s). A bounded,
tenant-derived batch read for account snapshots, subscriptions, events and
coverage is requested; batching must preserve per-account authorization and
both event/availability-time filters. No cache or alternate reader was
introduced. Member 1 owns API/query optimization. **P1 nonblocking** for frozen
tenant-01 artifacts; needed for scale/coverage diagnostics.
