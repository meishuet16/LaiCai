# RetainIQ v2 — Part 1 data foundation

This checkout had no application framework, database layer, migrations, tests, or source dataset. Part 1 is implemented with Python's standard library, WSGI, and SQLite so the data contracts can be exercised without adding dependencies. The SQL file is a SQLite migration for this local MVP; it is not a production PostgreSQL migration.

The implementation provides authenticated, tenant-scoped event ingestion; explicit account identity mapping; allowlisted usage, billing, and subscription normalization; append-only subscription history; point-in-time queries; account MRR; CSV import/replay; integration health; and shared feature, label, and prediction storage contracts. It does not implement Member 2's feature engineering, label builder, or model, or Member 3's routing and ROI logic.

See [DATASET_CARD.md](DATASET_CARD.md) for the evidence gate. No empirical customer data or model-performance claims are included.

## Requirements and local setup

- Python 3.10 or newer (verified here with Python 3.14.3).
- No third-party Python packages.

Run commands from this directory:

```powershell
python -m retaniq init-db --db .\data\retaniq.sqlite3
python -m retaniq create-tenant --db .\data\retaniq.sqlite3 --tenant-id tenant_demo
python -m retaniq create-integration --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --source product_app --purpose retention_inference --purpose billing_valuation
python -m retaniq create-customer --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --customer-id customer_001
python -m retaniq map-customer --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --source product_app --external-customer-id acct_001 --customer-id customer_001
python -m retaniq serve --db .\data\retaniq.sqlite3
```

`create-integration` prints a newly generated bearer token once. Save it in an approved secret store; the database keeps only its SHA-256 digest. The default local HTTP server listens on `127.0.0.1:8000`. It does not provide TLS; deployments need a trusted TLS-terminating proxy and restrictive operating-system access to the SQLite file. The CLI provisioning commands are trusted local-operator actions and are not public APIs.

The local SQLite database is not encrypted at rest by this implementation. Do not put contact identity, payment credentials, or unrestricted source payloads in it. A production deployment needs managed encrypted storage and a reviewed service/database boundary.

## Public API

Every endpoint requires `Authorization: Bearer <integration-token>`. A token is scoped to one tenant, one source, and its configured purposes. The server derives `tenant_id` from the token. Request bodies containing `tenant_id` or `source_available_at` are rejected.

### `POST /v1/ingest/events`

Accepted envelope:

```json
{
  "source": "product_app",
  "source_event_id": "evt_1029",
  "external_customer_id": "acct_001",
  "event_type": "session_started",
  "occurred_at": "2026-10-10T09:00:00Z",
  "attributes": { "feature": "analytics" },
  "schema_version": "1.0"
}
```

The event is stored only when `(tenant_id, source, external_customer_id)` has an explicit mapping. Unknown IDs are rejected; there is no email matching or fuzzy merge. The same `(tenant_id, source, source_event_id)` with the same normalized content returns an idempotent duplicate result. Reusing that key with different content returns `409`.

Live ingestion records server `received_at` and does not accept a client-supplied historical availability time. As-of queries use `source_available_at` when imported from an explicitly trusted mapping; otherwise they use `received_at`. A record is visible at cutoff `T` only if both `occurred_at <= T` and its availability time is `<= T`.

Allowlisted event types and attributes:

| Category | Event types | Allowed attributes |
|---|---|---|
| Usage | `session_started`, `feature_used`, `usage_aggregate_updated` | `feature`; optional integer `quantity` plus `unit` |
| Billing | `payment_failed`, `payment_succeeded`, `invoice_payment_failed`, `invoice_paid` | Optional `subscription_id`; `amount_minor` and ISO-shaped `currency` together |
| Subscription | `subscription_created`, `subscription_updated` | `subscription_id`, status, plan ID, lifecycle timestamps, interval/count, price/discount minor units, currency |
| Subscription | `cancellation_requested` | `subscription_id`; optional `current_period_end` |
| Subscription | `subscription_cancelled_effective`, `subscription_non_renewed_effective`, `subscription_involuntary_terminated` | `subscription_id` |

Unknown event types, extra fields, raw contact/card data, malformed timestamps, non-allowlisted attributes, and schema versions other than `1.0` are rejected. Logs and errors expose stable error codes only. A generic login is not translated into `session_started` unless a source mapping explicitly defines that meaning.

### `GET /v1/integrations`

Returns only the authenticated integration's tenant/source, authorized purposes, schema/mapping versions, last successful ingestion, last safe failure code, and an evidence-based availability state. Freshness is reported as `unknown` until a source-specific freshness policy exists. Tokens and token digests are never returned.

## Historical CSV import and replay

The importer uses the same canonical validator, identity map, idempotency key, event tables, and normalization path as live ingestion. It accepts CSV plus a versioned JSON mapping such as:

```json
{
  "mapping_version": "vendor-export-v1",
  "columns": {
    "source_event_id": "event_id",
    "external_customer_id": "account_id",
    "event_type": "event_type",
    "occurred_at": "event_time",
    "attributes": "attributes_json",
    "source_available_at": "first_available_at"
  }
}
```

Without a `source_available_at` mapping, the importer preserves no invented availability timestamp; the true import `received_at` is the fallback and earlier historical cutoffs will exclude the record. Use `--trust-source-availability` only after verifying that the mapped column represents the original source availability time:

```powershell
$env:RETAINIQ_IMPORT_TOKEN = '<integration-token>'
python -m retaniq import-csv --db .\data\retaniq.sqlite3 --csv .\history.csv --mapping .\mapping.json --trust-source-availability
python -m retaniq replay --db .\data\retaniq.sqlite3 --available-from 2026-01-01T00:00:00Z --available-through 2026-02-01T00:00:00Z
```

The command reports accepted, duplicate, and rejected row counts and rejection codes. It does not print rejected payload contents. Replay is ordered by original availability, then occurrence time, and includes only events that pass both cutoff predicates. CSV is supported because no Parquet dependency exists in this repository; add another format only with a reviewed mapping into the same event service.

## Part 2 data handoff

Authenticated internal data helpers take an `IntegrationPrincipal` produced by token authentication and always use its tenant scope:

- `get_account_snapshot_as_of(db, principal, customer_id, as_of)` returns tenant/customer IDs, cutoff, eligibility state, point-in-time subscription state, usage and billing event references, valuation, and the latest availability time actually used.
- `get_events_as_of(...)` returns typed facts satisfying occurrence and availability cutoffs.
- `get_subscriptions_as_of(...)` folds append-only subscription changes available by the cutoff.
- `list_eligible_accounts_as_of(db, principal, as_of)` enumerates active eligible accounts, including accounts with no recent usage events.
- `feature_snapshots` stores `tenant_id`, `customer_id`, `as_of`, feature version, data cutoff, minimized feature values, and data-quality status. The writer rejects common contact/secret fields.
- `churn_labels` stores the shared 7/14/30 horizon contract (`0`, `1`, or `unknown`), observation-through time, outcome, and label-policy version. A negative must have a fully observed horizon. This repository does not generate labels.

Known cancellation is separate from predictive features. The account policy in this implementation defines churn as loss of the last active paid subscription. An account is `known_cancellation` only when every currently active entitlement subscription has a known cancellation request; cancellation of one subscription while another remains active leaves the account eligible. Member 2 must not use cancellation-request time/status as a predictive feature.

## Part 3 valuation handoff

`get_account_snapshot_as_of` supplies `valuation.mrr_minor`, `currency`, `valuation_as_of`, `valuation_policy_version`, and a status. MRR is available only when all active entitlement subscriptions have known pricing and a common currency. Mixed currencies or any missing price return `mrr_minor: null`; no cross-currency conversion is performed. The event references include source event IDs and timestamps for factual billing/usage context. Part 3 owns all routing, ranking, action, and ROI rules.

### MRR policy `mrr-monthly-v1`

Source prices and discounts are integer minor units. The recurring discount is a fixed amount in the same minor-unit currency. MRR is calculated per active subscription after discount, rounded to the nearest minor unit using `ROUND_HALF_UP`, then summed only within one currency:

- day: `net_minor × 365 / (12 × interval_count)`
- week: `net_minor × 52 / (12 × interval_count)`
- month: `net_minor / interval_count`
- quarter: `net_minor / (3 × interval_count)`
- year: `net_minor / (12 × interval_count)`

The 52-week and 365-day factors define the v1 average-month convention. `amount_minor`, currency, interval, or interval count missing from an active subscription makes account MRR unavailable. A payment failure does not end an entitlement. Zero-decimal currencies remain in their source minor units; no major-unit conversion is performed. Currency syntax is checked as three uppercase letters, but this prototype does not verify membership against a complete ISO 4217 registry.

## Storage and implementation boundary

`migrations/001_data_foundation.sql` creates tenant-aware tables for customers, identities, integrations, the idempotent canonical event ledger, usage/billing/subscription records, append-only subscription events, feature snapshots, churn labels, and unified predictions. Subscription current state is a projection; historical state and price are rebuilt from available subscription events. Prediction storage uses one `prediction_id` per account/cutoff plus a separate `prediction_run_id` and flat `p_churn_7d`, `p_churn_14d`, and `p_churn_30d` fields.

This is a local reference implementation, not a deployed service. It has no scheduled daily worker, external identity provider, managed database, encryption-at-rest integration, production TLS, or PostgreSQL adapter. Those infrastructure capabilities remain unverified. No real dataset exists in this checkout, so imports/replay and tests can demonstrate engineering behavior only.

## Verification

```powershell
python -m unittest discover -s tests -v
python -m compileall retaniq tests
python -m retaniq --help
```

The repository has no configured linter, formatter, type checker, frontend build, or PostgreSQL integration-test command. The test suite uses only clearly synthetic fixtures and makes no model-performance claim.
