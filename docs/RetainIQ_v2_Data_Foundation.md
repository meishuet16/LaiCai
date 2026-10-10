# RetainIQ v2 — Data Foundation (Final MVP Specification)

**Track 1: Predict Early, Decide Better**  
**Status:** Proposed MVP architecture, not a claim of implemented capabilities.

## 1. Objective and Boundaries

Build a small, secure, repeatable data foundation that turns historical and incoming subscription events into **point-in-time-correct customer features** for a **30-day churn model**, then supplies prediction and revenue inputs to the decision layer.

The four distinguishing capabilities are:

1. **Automated integration:** initial historical import plus one authenticated Push API; a Stripe Test Mode webhook is an optional second demonstration connector.
2. **Security-aware classification:** distinguish source provenance from sensitivity; minimize data before persistence.
3. **Practical freshness:** daily customer refresh plus meaningful event-triggered refresh, with nonurgent notifications in business hours.
4. **Unified history:** normalized customers, subscriptions, billing and usage events, reproducible labels, versioned features and predictions.

**Out of scope for MVP:** generic connector marketplace, advanced adaptive scheduling, multi-source fuzzy identity matching, complex streaming infrastructure and claiming real business retention uplift.

## 2. End-to-End Flow

```text
Timestamped historical dataset (events + outcomes)
       |     [chronological replay through same Push API for demo]
       v
Authenticated Push API <---- optional Stripe Test Mode webhook
       |
       v
Source authorization -> schema validation -> field classification
       -> data minimization -> deduplication
       |
       v
Normalize events + map source IDs to internal customer/account IDs
       |
       v
PostgreSQL canonical tables (historical events and subscriptions)
       |
       +--> Label builder: observed churn within next 30 days
       |
       +--> Feature builder: facts available as of prediction cutoff
                 |
                 v
          Daily refresh / material-event trigger
                 |
                 v
          30-day churn model (Part 2)
                 |
                 v
          Versioned predictions + monetary inputs (Part 3)
                 |
                 v
          Revenue at risk -> recommended action -> human review
```

Security and tenant authorization apply at ingestion **and** on every read, training job and prediction lookup.

## 3. Data Sources and Demonstration Strategy

### 3.1 Historical source is mandatory

Choose a legitimately usable, timestamped subscription dataset with **subscription effective/end dates**, behavioral or billing events, and outcomes. Record its name, license, coverage, limitations and schema mappings in `DATASET_CARD.md`. Do **not** assume a snapshot dataset with only `Churn = Yes/No` supports 30-day prediction.

- Build a chronological **training window, validation window and held-out test window** separated by prediction cutoff dates.
- Only create negative labels when a **full 30-day follow-up** is observable.
- If no suitable real dataset is available, synthetic data may verify the pipeline and demo, but its model scores must be labelled **synthetic demonstration only**, not real-world model performance.
- Stripe Test Mode supplies **integration demonstration events**, not independent evidence of real churn prediction accuracy.

### 3.2 Reconcile training, evaluation and live demo schema

Convert the selected historical dataset to the **same canonical event contract** used by the Push API. Reuse dataset records in chronological order for an **event replay** demo:

1. Train on the training split and freeze the model.
2. Evaluate on the held-out chronological test split; do not tune on it.
3. Choose a previously held-out replay segment (or a separately reserved demo segment), replay its events chronologically through the real Push API.
4. Generate feature snapshots only from events available at each simulated cutoff and run the frozen model.
5. Reveal later outcomes **after** predictions as evidence of what happened, never as pre-cutoff features.

This removes the avoidable schema mismatch between a public training dataset and fabricated Stripe/Alice demo data. Live Stripe tests can separately prove webhook connectivity; they need not be used as primary churn-model evidence.

## 4. Automated Integration

**Required:**
- Historical CSV/parquet importer using the canonical mapping and timestamp validation.
- `POST /v1/ingest/events` authenticated Push API, accepting usage, billing and subscription events via an allowlisted versioned schema.
- Idempotency via `(tenant_id, source, source_event_id)` uniqueness.
- Basic error reporting for rejected/unknown records and import summaries.

**Optional:** Stripe Test Mode connector with signed webhook verification, a small mapping adapter, and an explicit disclaimer that test events prove plumbing only.

Connection configuration exposes source, authorized purpose, mapping version, last-successful sync and error status. No arbitrary URLs or untrusted redirect-based pull connector in MVP.

Example canonical input (server derives `tenant_id` from auth, never trusts the submitted value):

```json
{
  "source": "product_app",
  "source_event_id": "evt_1029",
  "external_customer_id": "acct_102",
  "event_type": "session_started",
  "occurred_at": "2026-10-10T09:00:00Z",
  "attributes": {"feature": "analytics"},
  "schema_version": "1.0"
}
```

## 5. Security and Classification

Classify **separately** by:

- **Origin:** internal, authorized external, or unverified.
- **Sensitivity:** public, internal, confidential or restricted.
- **Allowed purpose:** identity matching, retention inference, billing valuation or operational contact.

**Enforcement order:** authenticate connection -> verify source/schema -> classify fields -> drop/reject unneeded restricted fields -> validate and normalize -> store approved minimum data. Keep rejected-payload logs redacted (no raw secrets or unnecessary PII).

MVP controls: HTTPS, integration-token or webhook-signature verification, token secrecy, minimal scopes, field allowlists, tenant-scoped authorization and tests, encryption-at-rest through managed storage, basic role separation, and retained error/audit metadata. The database and application queries must scope data to `tenant_id`; sensitive credentials stay in deployment secrets, never front-end code.

For identity matching, `customer_identities` is the **minimal protected identity registry**: map `(tenant_id, source, external_customer_id)` to `customer_id`; if email is essential, store an encrypted contact value separately from modeling columns. Prefer explicit account-ID mappings; **never fuzzy-merge accounts based solely on email**. Do not forward emails into feature snapshots.

## 6. Canonical PostgreSQL Schema

All customer-bearing tables carry `tenant_id`, with tenant-aware uniqueness/foreign keys and server-enforced access rules. The following is a **logical contract**; implement indexes and migrations in SQL.

| Table | Essential columns | Purpose |
|---|---|---|
| `customers` | `tenant_id`, `customer_id`, `account_status`, `created_at` | Canonical paying account |
| `customer_identities` | `tenant_id`, `customer_id`, `source`, `external_customer_id`, `protected_email?` | Explicit source-ID mapping / protected identity registry |
| `subscriptions` | `tenant_id`, `subscription_id`, `customer_id`, `plan_id`, `status`, `started_at`, `current_period_end`, `ended_at?`, `cancellation_requested_at?`, `billing_interval`, `billing_interval_count`, `amount_minor`, `currency`, `discount_minor?` | Lifecycle and contract value with dated status |
| `billing_events` | `tenant_id`, `event_id`, `customer_id`, `subscription_id?`, `event_type`, `occurred_at`, `amount_minor?`, `currency?`, `payment_status?` | Payment history, not churn by itself |
| `usage_events` | `tenant_id`, `event_id`, `customer_id`, `event_type`, `occurred_at`, `received_at` | Timestamped behavior and inactivity |
| `feature_snapshots` | `tenant_id`, `customer_id`, `as_of`, `feature_version`, `data_cutoff_at`, `features_json`, `data_quality_status` | Reproducible point-in-time ML inputs |
| `churn_labels` | `tenant_id`, `customer_id`, `as_of`, `horizon_days`, `label`, `churn_type?`, `outcome_at?`, `label_observed_through` | Training/evaluation target, not online model input |
| `predictions` | `tenant_id`, `prediction_id`, `customer_id`, `as_of`, `horizon_days`, `model_version`, `feature_version`, `churn_probability`, `generated_at`, `data_quality_status` | Auditable Part 2 output / Part 3 handoff |

**Eight tables**, not seven: the `predictions` table is necessary. A `prediction_id` may be used to associate later intervention records with the actual prediction displayed.

### Monetary contract for Part 3

Store source money in **integer minor units**, along with ISO currency and billing interval. Monthly recurring revenue is a **derived, dated feature**, not guessed from plan labels:

```text
monthly_recurring_revenue_minor =
    normalized recurring contract amount per month,
    after applicable recurring discounts, excluding one-off charges/taxes
```

Normalize weekly, monthly, quarterly or annual plans using a documented method and month convention; handle zero-decimal currencies and missing pricing explicitly. Do not silently add different currencies. Either provide revenue-at-risk **per currency**, or convert using a recorded FX source, date and rate. Define whether MRR is measured for a single subscription or summed across active subscriptions for an account.

For the MVP, Part 3 may show **illustrative one-month expected revenue exposure** as:

```text
expected_1_month_exposure = P(churn within 30 days) × MRR
```

This is a **simplified prioritization proxy**, not a calibrated causal financial-loss forecast: churn timing, recoveries, upgrades, collection risk and intervention outcomes can change realized revenue. Label it accordingly; do not automatically describe it as revenue saved.

## 7. Churn Event and Label Definition

**Prediction population:** accounts with an active, at-risk subscription **and no known cancellation request as of cutoff**.

Define `churn_effective_at` as the effective time when the subscription/account actually loses paid entitlement under the chosen business policy. For multiple subscriptions, state whether churn means the **last active subscription ends** or a contract-specific churn event. Apply this consistently.

| Event | Label / handling |
|---|---|
| Voluntary cancellation effective within next 30 days | Positive (`voluntary`) |
| Contract expires with no renewal and entitlement ends | Positive (`non_renewal`) |
| Payment failures ultimately cause termination | Positive (`involuntary`) **only at actual termination**, not first failure |
| Payment failed but subscription remains active | Billing risk feature, not churn label |
| Cancellation requested before/as of cutoff, but service still active | **Exclude from prospective churn prediction population; classify as known/pending cancellation** |
| Already terminated before/as of cutoff | Exclude from active churn prediction population |
| No churn in a fully observed 30-day window | Negative (`0`) |
| Follow-up window incomplete or state uncertain | Unknown / censored: exclude from ordinary supervised binary labels |

**Leakage rule:** `cancellation_requested_at`, a pending-cancel flag and any direct equivalent **must not be ML features**. Accounts with a *known* cancellation request at cutoff enter a separate **Cancellation Recovery** workflow, not the early churn predictor. Requests occurring **after** cutoff are future outcomes/context and must not appear in earlier feature snapshots. Excluding known-pending customers changes the population being predicted and should be clearly stated in evaluation.

For a cutoff `t`, label is `1` if qualifying churn takes effect in `(t, t + 30 days]`; `0` only if the full outcome window is observed without qualifying churn. Ensure every predictive feature was known or received by `t`—not merely timestamped before `t` if it arrived later.

## 8. Freshness and Prediction Triggers

The target is **30-day churn**, so do not invent a five-minute freshness SLA without a demonstrated decision need.

| Function | MVP policy |
|---|---|
| Historical import | One-time/backfill, with reproducible cutoff |
| API ingestion | On each received event; store approved canonical record |
| CRM / billing reconciliation | Daily where the connector supports it |
| Global feature/prediction refresh | Daily for **all eligible active customers**, including silent/inactive accounts |
| Important payment/support signals | Update facts; enqueue affected accounts for priority re-evaluation |
| Usage events | Update aggregates; **if material change threshold is met**, enqueue a prediction refresh |
| Nonurgent staff notifications | Queue for next configured business hours; no suppression of data collection |

Minimal trigger logic:

```python
def on_event(event, customer):
    store_normalized_event(event)
    update_relevant_aggregates(customer)

    if event.type == "subscription_cancelled_effective":
        record_churn_outcome(customer)
        return "RECORD_OUTCOME"

    if event.type == "cancellation_requested":
        mark_pending_cancellation(customer)
        return "ROUTE_TO_CANCELLATION_RECOVERY"

    if event.type in {"payment_failed", "critical_support_issue"}:
        enqueue_prediction_if_eligible(customer)
        return "PRIORITY_REPREDICT"

    if event.type == "usage_event":
        if material_usage_change(customer):
            enqueue_prediction_if_eligible(customer)
            return "REPREDICT_AFTER_AGGREGATION"
        return "FEATURES_UPDATED"

    return "FEATURES_UPDATED"
```

Daily refresh also handles customers who generate **no new usage events**. Use deduplicated jobs, and report prediction age and missing source data rather than implying every record is fresh.

## 9. Explicit Part 1 → Part 2 → Part 3 Contracts

### Data Foundation → Predictive Model (Part 2)

A versioned `feature_snapshots` record provides `tenant_id`, `customer_id`, `as_of`, `feature_version`, `data_cutoff_at`, feature values and data quality. Training additionally joins eligible `churn_labels` by **the same account and cutoff**; serving does **not** expose labels or post-cutoff fields.

**Part 2 must return/store:** `prediction_id`, `customer_id`, `as_of`, `model_version`, `feature_version`, `horizon_days=30`, `churn_probability`, `generated_at`, `data_quality_status`. Include explanation factors separately if implemented; they must refer to eligible known features.

### Predictive Model → Decision System (Part 3)

Part 3 receives an auditable prediction plus subscription valuation (`MRR`, `currency`, price basis, as-of date), customer eligibility and quality/freshness indicators. It must not assume all actions reduce churn by a fixed learned percentage. If action uplift is unmeasured, recommend with a transparent rule/evidence level rather than fabricate saved-revenue forecasts.

## 10. Build Order and Acceptance Tests

**Step 1 — Dataset + labels:** select/document timestamped historical data, define event semantics and churn effective date, generate leakage-safe 30-day labels and chronological splits.

**Step 2 — Unified schema + money:** migrate the eight tables, source-ID mapping and MRR normalization; test currency, multi-subscription and missing-price behavior.

**Step 3 — Secure ingestion:** build import and Push API using the same canonical schema, source auth, field minimization, validation and idempotency.

**Step 4 — Replay + features:** replay held-out timestamped events, build versioned point-in-time features, enforce eligibility and daily refresh.

**Step 5 — Model and decision handoff:** persist versioned predictions, expose MRR and quality metadata to Part 3, and show a complete end-to-end demo.

**Step 6 — Optional Stripe connector:** demonstrate real provider webhook integration only if the core replay/prediction route is reliable.

### Required pass/fail checks

- Historical data contains timestamps and measurable cancellation/termination outcomes; its provenance and limitations are stated.
- The same canonical event contract works for historical import, replay and live Push API.
- Train/validation/test are chronological; model never sees events received after feature cutoff.
- Known pending cancellations are excluded from 30-day churn training/serving and routed separately; not used as features.
- Payment failure alone is not labelled churn; non-renewal is labelled only after the required follow-up is observable.
- `subscriptions` exposes price, currency and billing interval; Part 3 never sums mixed currencies blindly.
- `feature_snapshots` and `predictions` retain their versions and cutoff/model timestamps.
- Source IDs map deterministically; sensitive contact data is not present in ML feature JSON.
- Unauthorized or cross-tenant API access is denied; duplicate events do not duplicate state.
- Daily refresh detects inactive accounts, while aggregated material usage changes can also trigger re-prediction.
- Demo predictions are from a frozen trained model; later outcomes are revealed only afterward.

## 11. One-Sentence Pitch

> **RetainIQ securely unifies historical and live subscription events into fresh, auditable customer features, predicts 30-day churn before cancellation is known, and passes versioned risk and revenue context to evidence-based retention decisions.**

