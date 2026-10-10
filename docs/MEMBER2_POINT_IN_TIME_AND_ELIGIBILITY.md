# Member 2 — Point-in-Time Adapter and Prediction Eligibility

Status: implemented in-memory adapter and eligibility foundation. No database, ingestion API, feature engineering, label generation, or model inference is included.

## Adapter interface

`PointInTimeDataAdapter` defines the replaceable read boundary:

```python
snapshot = adapter.snapshot_for(
    tenant_id="tenant_abc",
    customer_id="customer_123",
    as_of=timezone_aware_cutoff,
)
```

The current `InMemoryPointInTimeAdapter` accepts typed `SubscriptionFact`, `UsageFact`, and `BillingFact` records for synthetic tests. Member 1 can later implement the same interface against the canonical database or replay layer.

The adapter is not a database schema. It preserves the following provenance on every returned fact:

- `record_id`
- `tenant_id`
- `customer_id`
- `occurred_at` and/or `effective_at`
- `source_available_at`, when supplied
- `received_at`, when applicable
- `source`
- event `category`
- category-specific event/status fields

The adapter returns only exact tenant/account matches. It never returns another tenant’s or customer’s records.

## Historical availability policy

A fact is included only when:

1. Its applicable event/effective timestamp is at or before `as_of`.
2. Its selected historical availability timestamp is at or before `as_of`.

An earlier `occurred_at` cannot make a late-arriving fact usable. A fact that occurred on October 8 but was received on October 12 is excluded from an October 10 snapshot.

Facts with neither source availability nor `received_at` are excluded and reported as `historical_availability_unknown`. The adapter never substitutes `occurred_at` for availability.

Availability precedence is configurable because Member 1 has not finalized the cross-part contract:

- `SOURCE_THEN_RECEIVED` — provisional local default; prefer `source_available_at`, otherwise use `received_at`.
- `SOURCE_ONLY` — require `source_available_at`.
- `RECEIVED_ONLY` — use `received_at`.

This is an adapter assumption, not a new team-wide policy. Source-provided availability wins when both timestamps exist; an earlier `received_at` does not override a later source-availability timestamp.

All timestamps must be timezone-aware. Naive timestamps are rejected rather than assigned a guessed timezone.

## Eligibility states

Eligibility is separate from `PredictionOutput` and returns machine-readable reason codes.

| State | Meaning |
|---|---|
| `ELIGIBLE` | Dated evidence establishes an active paying subscription at `as_of`, with no known cancellation available by the cutoff. |
| `KNOWN_CANCELLATION` | A cancellation request or scheduled termination was both dated and available by `as_of`; no prospective first-churn forecast should be produced. |
| `NOT_ELIGIBLE` | Dated evidence establishes that no active paying subscription remains at `as_of`, such as confirmed termination. |
| `INSUFFICIENT_DATA` | History is missing, unavailable, contradictory, stale for the cutoff, or otherwise cannot establish eligibility. |

Current reason codes include:

- `ACTIVE_PAYING_SUBSCRIPTION`
- `KNOWN_CANCELLATION_AT_CUTOFF`
- `NO_ACTIVE_PAYING_SUBSCRIPTION`
- `TERMINATED_BEFORE_CUTOFF`
- `MISSING_SUBSCRIPTION_HISTORY`
- `SUBSCRIPTION_STATUS_UNRESOLVED`
- `CONTRADICTORY_LIFECYCLE`
- `UNRESOLVED_MULTI_SUBSCRIPTION_POLICY`
- `HISTORICAL_AVAILABILITY_LIMITED`

Mapping to the existing prediction contract is intentionally limited:

- `KNOWN_CANCELLATION` -> `PredictionStatus.KNOWN_CANCELLATION`
- `NOT_ELIGIBLE` -> `PredictionStatus.NOT_ELIGIBLE`
- `INSUFFICIENT_DATA` -> `PredictionStatus.ABSTAINED`
- `ELIGIBLE` -> no prediction status yet; eligibility does not itself create a scored forecast

No undocumented `PredictionOutput` status was added.

Failed payment events are retained as billing facts but do not by themselves terminate eligibility or imply churn.

`cancellation_requested_at` is used only for eligibility routing. It is not a feature input for future model training.

## Historical state reconstruction

Eligibility sorts dated subscription facts by their effective/occurrence timestamp and evaluates the latest usable state at the requested cutoff. A future termination record is excluded even if a current-state row contains it. This prevents a later database state from overwriting the historical `as_of` state.

Member 1 must provide dated lifecycle events or equivalent time-aware records. A current subscription snapshot without historical effective timestamps is insufficient for point-in-time eligibility.

## Multiple subscriptions

If more than one active subscription exists and no explicit account-level churn policy is supplied, the result is `INSUFFICIENT_DATA` with `UNRESOLVED_MULTI_SUBSCRIPTION_POLICY`. The adapter does not silently choose “last subscription” or “any subscription.”

An explicit policy can be passed to `EligibilityPolicy`, but the business meaning and label policy still require team agreement before model training.

## Required Member 1 inputs

Member 1’s real adapter must provide:

- Tenant/account identity and authorization-scoped reads.
- Subscription ID, account ID, dated lifecycle/effective timestamp, status, and paying/entitlement state.
- Dated cancellation request or scheduled termination events.
- Usage and billing event IDs, event categories/types, occurrence timestamps, and availability/received timestamps.
- Source identifiers and provenance.
- Historical records sufficient to reconstruct state at arbitrary cutoffs.

The backend remains responsible for authentication and database tenant isolation. The in-memory adapter enforces exact tenant/account filtering for this local module but is not an authorization service.

## Limitations and blockers

- No Member 1 database/API implementation exists yet.
- Account-level multi-subscription churn semantics are unresolved.
- Availability precedence is provisional and configurable.
- The module does not build features, labels, model inputs, or predictions.
- It does not infer event meaning from arbitrary raw source data.
- It does not replace the dataset readiness gate or provenance/license review.
