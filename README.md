# RetainIQ v2 — Part 1 data foundation

## Synthetic SaaS dataset

RetainIQ includes a deterministic, streamed synthetic SaaS lifecycle generator for tenant-safe end-to-end demonstration. See [the dataset guide](docs/SYNTHETIC_SAAS_DATASET.md), [hybrid isolation policy](docs/HYBRID_DATASET_STRATEGY.md), and [Member 2 synthetic handoff](docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md).

```powershell
python -m retaniq.synthetic validate --dataset 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\quick\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3'
python -m retaniq.synthetic import --dataset 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\quick\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3' --db 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3.sqlite3'
```

Generated files and local SQLite imports stay outside Git. To generate a fresh immutable profile, see the full v1.2 CLI options in [the dataset guide](docs/SYNTHETIC_SAAS_DATASET.md); use the resulting exact dataset ID and its separate database path. The v1.2 daily-window, account-level coverage, dataset identity, and Member 2 import/smoke commands are documented in [the synthetic handoff](docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md).

Part 1 uses Python's standard library, WSGI, and SQLite so the data contracts can be exercised without adding dependencies. The 06B database foundation adds typed backend configuration and optional psycopg 3 connection/transaction primitives. PostgreSQL-specific schema migrations are defined in 06C. Prompt 06D-1 adds PostgreSQL parity for tenant/integration setup, authentication/authorization, identity mapping, canonical single/batch ingestion, event subtypes, import checkpoints, and integration health; other repository operations remain explicitly unsupported on PostgreSQL.

The implementation provides authenticated, tenant-scoped event ingestion; explicit account identity mapping; allowlisted usage, billing, and subscription normalization; append-only subscription history; point-in-time, source-scoped queries; account MRR; CSV import/replay; source-scoped integration health; separately authorized tenant health; and shared feature, label, and prediction storage contracts. It does not implement Member 2's feature engineering, label builder, or model, or Member 3's routing and ROI logic.

See [DATASET_CARD.md](DATASET_CARD.md) for the evidence gate. No empirical customer data or model-performance claims are included.

## Requirements and local setup

- Python 3.10 or newer (verified here with Python 3.14.3).
- No third-party Python packages are required for SQLite mode. Optional PostgreSQL connection support is declared in [requirements-postgresql.txt](requirements-postgresql.txt).

Run commands from this directory:

```powershell
python -m retaniq init-db --db .\data\retaniq.sqlite3
python -m retaniq create-tenant --db .\data\retaniq.sqlite3 --tenant-id tenant_demo
python -m retaniq create-integration --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --source product_app --purpose retention_inference --category usage
python -m retaniq create-service-principal --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --role analyst --source product_app --purpose retention_inference
python -m retaniq create-customer --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --customer-id customer_001
python -m retaniq map-customer --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --source product_app --external-customer-id acct_001 --customer-id customer_001
python -m retaniq serve --db .\data\retaniq.sqlite3
```

`create-integration` and `create-service-principal` print a newly generated bearer token once. Save it in an approved secret store; the database keeps only its SHA-256 digest. Service principals are provisioned only by the trusted local CLI, never by an HTTP endpoint. Each service principal is bound to one tenant, one of `analyst`, `admin`, or `operator`, an exact list of existing source integrations, and explicit purposes. An `admin` or `operator` needs the `integration_health` purpose to read tenant integration health. The default local HTTP server listens on `127.0.0.1:8000`. It does not provide TLS; deployments need a trusted TLS-terminating proxy and restrictive operating-system access to the SQLite file. The CLI provisioning commands are trusted local-operator actions and are not public APIs.

The local SQLite database is not encrypted at rest by this implementation. Do not put contact identity, payment credentials, or unrestricted source payloads in it. A production deployment needs managed encrypted storage and a reviewed service/database boundary.

## Public API

The ingestion and source-health endpoints require `Authorization: Bearer <integration-token>`. Each integration token is scoped to one tenant, one source, and its configured purposes. The server derives `tenant_id` from the token. Request bodies containing `tenant_id` or `source_available_at` are rejected. Tenant-wide analytics must use a separately provisioned service principal; an integration token cannot widen its source access by holding `retention_inference`.

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

Every integration is also scoped to explicit event categories. New integrations default to `usage`; set one or more categories with repeated `--category` options when creating the token, for example `--category usage --category billing --category subscription`. The normalized event type determines its category, and ingestion rejects an ungranted category with HTTP 403 `event_category_not_authorized` before inserting a canonical event. For an existing source, a trusted local operator can replace grants with `python -m retaniq set-integration-categories --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --source billing_app --category billing --category subscription`.

Purpose grants are checked at data access as well as ingestion. Usage reads and feature/label/prediction writes require `retention_inference`; billing status is available to retention readers with amount and currency redacted. Pricing fields and MRR are returned only when the principal also has `billing_valuation`. Account snapshot and subscription helpers keep the lifecycle fields available to retention readers and omit the valuation for them.

Multi-source Member 2 jobs use a dedicated service principal created by a trusted local operator with role `analyst`, only the exact source list, and both `retention_inference` and `model_artifact_write`. This separate purpose is required for service-principal writes; another analyst token without it and admin/operator tokens cannot persist features, labels, or predictions. A source integration may persist artifacts only for a customer explicitly mapped through its own source. It cannot write for an account mapped only through another source in the same tenant. Add `billing_valuation` to the internal principal only when monetary features or explanations are required.

As-of query helpers enforce both tenant and source grants. An integration principal sees events only from its own source. An internal service principal may combine multiple sources only when each is explicitly listed in that principal's tenant-scoped grants; purpose redaction still applies.

Account-specific snapshots and eligible-account enumeration also require an explicit customer identity mapping from at least one source granted to the principal. A caller cannot probe canonical customer IDs that are mapped only through another source in the same tenant. Silent accounts remain enumerable when their authorized source mapping exists and their dated subscription history establishes eligibility.

Feature snapshots and prediction explanations accept numeric, boolean, null, and bounded categorical values under approved categorical fields. Status, event type, direction/trend, currency, and tier fields have enums; categorical values with seven or more digits are rejected after punctuation normalization. Arbitrary strings, free-form source errors, notes, contact details, credential values, and payment-card values are rejected before persistence. Reliability reasons are predefined codes such as `short_personal_usage_history`, `stale_source_data`, and `unknown_observation_coverage`; a client must translate these codes to approved display text. Financial value fields still require `billing_valuation`. Prediction `input_data_as_of` must be at or before its `as_of` cutoff.

### `GET /v1/integrations`

Returns only the authenticated integration's tenant/source, authorized purposes, schema/mapping versions, last successful ingestion, last safe failure code, and an evidence-based availability state. Freshness is reported as `unknown` until a source-specific freshness policy exists. Tokens and token digests are never returned.

### `GET /v1/admin/integrations`

Accepts a service-principal token with `admin` or `operator` role and the `integration_health` purpose. The response contains only integrations from that principal's exact authorized source list in its tenant. An integration token, an `analyst` service principal, a service principal without the health purpose, or a token from another tenant cannot use this route. Provision an operator after the relevant integration sources exist:

```powershell
python -m retaniq create-service-principal --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --role operator --source product_app --purpose integration_health
```

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

Authenticated internal data helpers take an `IntegrationPrincipal` or a `ServicePrincipal` produced by token authentication and always use the authenticated tenant scope:

- `get_account_snapshot_as_of(db, principal, customer_id, as_of)` returns tenant/customer IDs, cutoff, eligibility state, point-in-time subscription state, usage and billing event references, valuation, and the latest availability time actually used.
- `get_events_as_of(...)` returns typed facts satisfying occurrence and availability cutoffs.
- `get_subscriptions_as_of(...)` folds append-only subscription changes available by the cutoff.
- `list_eligible_accounts_as_of(db, principal, as_of)` enumerates active eligible accounts, including accounts with no recent usage events.

The principal must have an identity mapping for the requested account through at least one authorized source; enumeration derives candidates from the principal's authorized source mappings. A same-tenant account mapped only through another source returns `not_found` to a source token.
- `feature_snapshots` stores `tenant_id`, `customer_id`, `as_of`, feature version, data cutoff, minimized feature values, and data-quality status. The writer rejects common contact/secret fields.
- `churn_labels` stores the shared 7/14/30 horizon contract (`0`, `1`, or `unknown`), observation-through time, outcome, and label-policy version. A negative must have a fully observed horizon. This repository does not generate labels.

Known cancellation is separate from predictive features. The account policy in this implementation defines churn as loss of the last active paid subscription. An account is `known_cancellation` only when every currently active entitlement subscription has a known cancellation request; cancellation of one subscription while another remains active leaves the account eligible. Member 2 must not use cancellation-request time/status as a predictive feature.

Historical eligibility uses the dated subscription-event history as its authority. `customers.account_status` is currently an undated operational/provisioning field, so as-of queries intentionally ignore it; changing that current field cannot rewrite a prior eligibility cutoff. A future requirement for dated account-level suspension/closure semantics needs an append-only, source-backed account lifecycle event contract.

## Part 3 valuation handoff

`get_account_snapshot_as_of` supplies `valuation.mrr_minor`, `currency`, `valuation_as_of`, `valuation_policy_version`, and a status. MRR is available only when all active entitlement subscriptions have known pricing and a common currency. Mixed currencies or any missing price return `mrr_minor: null`; no cross-currency conversion is performed. The event references include source event IDs and timestamps for factual billing/usage context. Part 3 owns all routing, ranking, action, and ROI rules.

### MRR policy `mrr-monthly-v1`

Source prices and discounts are integer minor units. The recurring discount is a fixed amount in the same minor-unit currency. MRR is calculated per active subscription after discount, rounded to the nearest minor unit using `ROUND_HALF_UP`, then summed only within one currency:

- day: `net_minor × 365 / (12 × interval_count)`
- week: `net_minor × 52 / (12 × interval_count)`
- month: `net_minor / interval_count`
- quarter: `net_minor / (3 × interval_count)`
- year: `net_minor / (12 × interval_count)`

The 52-week and 365-day factors define the v1 average-month convention. `amount_minor`, currency, interval, or interval count missing from an active subscription makes account MRR unavailable. A payment failure does not end an entitlement. Zero-decimal currencies remain in their source minor units; no major-unit conversion is performed. Currency codes are checked against the bundled [SIX ISO 4217 List One currency-and-funds codes](https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html), snapshot published 2026-09-17 in `retaniq/currency_codes.py`; reserved test/no-currency codes `XTS` and `XXX` are excluded. Refresh the checked-in code set when the official list changes.

## Storage and implementation boundary

`migrations/001_data_foundation.sql` creates the initial tenant-aware data tables. `migrations/002_authorized_services_and_subscription_owners.sql` adds separately scoped service principals and a tenant-scoped subscription-owner registry with composite foreign keys from billing events, subscription history, and the current projection. `migrations/003_integration_event_categories.sql` stores per-integration usage, billing, and subscription category grants. It backfills categories present in legacy canonical events; legacy integrations with no event history receive only the safe `usage` grant. Existing integration tokens remain valid for categories granted by that migration. A legacy integration that needs a category not represented in its prior event history must be explicitly updated by a trusted local operator with `set-integration-categories`. Initialization backfills owner records from existing data and refuses to guess if a subscription ID is already associated with multiple customers. Subscription current state remains a projection; historical state and price are rebuilt from available subscription events. Prediction storage keeps one `prediction_id` per account/cutoff, a separate `prediction_run_id`, and flat `p_churn_7d`, `p_churn_14d`, and `p_churn_30d` fields.

This is a local reference implementation, not a deployed service. It has no scheduled daily worker, external identity provider, managed database, encryption-at-rest integration, production deployment, RLS, or Supabase integration. PostgreSQL schema migrations and a migration runner are defined in 06C; 06D-1 adds bounded ingestion/auth/identity parity, and 06D-2 adds historical event/subscription/account/coverage reads and single coverage writes, live-verified by the guarded suites against disposable PostgreSQL 16.15. Feature/label/prediction persistence, coverage batch import/replay, dataset provisioning parity, and WSGI API startup remain unsupported on PostgreSQL. These partial results do not establish full parity or production readiness. No real dataset exists in this checkout, so imports/replay and tests can demonstrate engineering behavior only.

## Verification

```powershell
python -m unittest discover -s tests -v
python -m compileall retaniq tests
python -m retaniq --help
```

The repository has no configured linter, formatter, type checker, or frontend build. PostgreSQL integration tests are guarded by an explicit disposable marker, loopback host, and `retaniq_test_*` database name. See [06D-2 historical-query parity](docs/MEMBER1_POSTGRESQL_HISTORICAL_QUERY_PARITY.md) for supported operations, scenario mapping, and live-verification status. The test suite uses synthetic fixtures and makes no model-performance claim.
