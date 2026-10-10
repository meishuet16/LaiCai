# Member 1 → Member 2 data handoff

**Status:** Canonical query/API contract is available; real historical dataset is **NOT_READY**.
**Purpose:** Retention inference.
**Database in this checkout:** Local SQLite prototype, not the production PostgreSQL requirement. `python -m retaniq init-db --db ...` applies all recorded migrations through `003_integration_event_categories`.

## 1. Dataset, permission and limitations

No real dataset has been selected or imported. [`DATASET_CARD.md`](../DATASET_CARD.md) records the candidate review. The closest technical candidate is the KKBox WSDM churn challenge, but its official rules require participant access and limit use to competition participation, forum participation, academic research and education. This project has not accepted those terms or verified its eligibility; no files were downloaded. See the [official challenge](https://www.kaggle.com/c/kkbox-churn-prediction-challenge), [rules](https://www.kaggle.com/c/kkbox-churn-prediction-challenge/rules), and [WSDM task description](https://www.wsdm-conference.org/2018/call-for-participants.html). Static churn classifications and synthetic subscription examples were rejected as evidence for temporal early-warning evaluation.

Real rows in this database: **0**. No verified real account count, event count, date range, subscription ID mapping, source-availability coverage, churn-effective outcomes, observation coverage, censoring rate, repeated-cutoff population, or temporal split count exists.

**Current real dataset path:** None. If source access is later approved, the proposed local drop path is `./data/source/kkbox`; the repository's `.gitignore` excludes `data/`, but access terms still govern handling and redistribution.

If the project owner confirms eligibility and a participant accepts the terms, the gated acquisition command is:

```powershell
kaggle competitions download -c kkbox-churn-prediction-challenge -p .\data\source\kkbox
```

It was not run: local inspection found neither a Kaggle CLI nor Python package, and we did not accept restricted terms. Keep any authorized files at an approved local path and out of Git. No KKBox adapter or canonicalized file exists. Before importing, verify the acquired schema, license scope, stable account/subscription keys, lifecycle semantics, historical availability, and observation windows. A third-party mirror is not a substitute for source authorization.

## 2. Current acquisition/import commands

The runnable handoff check is a synthetic local demonstration:

```powershell
python -m examples.member2_as_of_history
python -m unittest discover -s tests -p test_member2_handoff.py -v
```

It builds a temporary SQLite database, inserts one explicitly synthetic eligible account, asks for its history at `2026-10-10T00:00:00Z`, and omits an event dated after that cutoff. It creates no labels, probabilities, or real-data evidence.

For a future source, after permission, schema review, and a reviewed adapter have produced a canonical event CSV, the existing importer command is:

```powershell
$env:RETAINIQ_IMPORT_TOKEN = '<authorized integration token>'
python -m retaniq import-csv --db .\data\retaniq.sqlite3 --csv .\data\normalized\canonical-events.csv --mapping .\data\normalized\mapping.json --trust-source-availability
```

Use `--trust-source-availability` only when the mapped field is verified to mean when that event was first available to the source, not its occurrence time, export time, or a guessed timestamp. If there is no reliable original availability field, omit that column and flag: actual import `received_at` becomes the fallback, so old cutoffs exclude those late-imported events. Do not backdate `received_at`.

A canonical mapping file has this shape (headers must match adapter output):

```json
{
  "mapping_version": "reviewed-source-adapter-v1",
  "columns": {
    "source_event_id": "source_event_id",
    "external_customer_id": "external_customer_id",
    "event_type": "event_type",
    "occurred_at": "occurred_at",
    "attributes": "attributes_json",
    "source_available_at": "source_available_at"
  }
}
```

This is a schema example, not a KKBox mapping. No adapter or import command for that restricted candidate is approved or implemented. Do not map a competition target into an event or treat an ambiguous cancel flag, payment failure, or non-renewal label as a verified termination event.

## 3. Canonical usage, billing and subscription contract

Schema source: `migrations/001_data_foundation.sql`; normalization source: `retaniq/data_foundation.py` (`EVENT_TYPES`, `_normalize_attributes`, `ingest_event`). Every canonical record is scoped by `tenant_id`; source identity resolves through `(tenant_id, source, external_customer_id)`.

| Category | Canonical event types | Canonical attributes / semantics |
|---|---|---|
| Usage | `session_started`, `feature_used`, `usage_aggregate_updated` | `feature`; optional integer `quantity` paired with `unit`. No unrestricted raw event body or free text. A generic login is not `session_started` unless the source contract defines that meaning. |
| Billing | `payment_failed`, `payment_succeeded`, `invoice_payment_failed`, `invoice_paid` | Optional `subscription_id`; `payment_status`; `amount_minor` and ISO code `currency` must appear together. A failed payment is billing risk, not churn. |
| Subscription | `subscription_created`, `subscription_updated` | Stable `subscription_id`; status, plan, lifecycle timestamps, billing interval/count and optional amount/discount/currency. These are append-only changes folded into an as-of state. |
| Subscription lifecycle | `cancellation_requested`, `subscription_cancelled_effective`, `subscription_non_renewed_effective`, `subscription_involuntary_terminated` | A request is pending, not effective churn. Explicit effective events set status `ended` and `ended_at` to event occurrence time. |

`subscription_id` identifies one subscription under a tenant, not a person or seat. Its owner is stable: a source may add events for that subscription only when it maps to the same canonical `customer_id`. A same-tenant cross-customer collision returns `contract_conflict` and rolls back the canonical event, subtype history, and projection update. Migration 002 backfills the owner registry and refuses to guess if existing records claim different owners. `customer_id` is the internal canonical paying-account key. `external_customer_id` is a source-specific account key and must be mapped explicitly; there is no fuzzy or email merge. Source event idempotency uses `(tenant_id, source, source_event_id)`.

## 4. Integration category grants

Every source integration has explicit `usage`, `billing`, and/or `subscription` event-category grants. New integrations default to `usage`. Set grants at provisioning with repeated `--category` options; a combined source must list every permitted category explicitly. Event type determines category, and ingestion rejects ungranted types as `event_category_not_authorized` before canonical event persistence.

Migration 003 preserves categories evidenced by existing canonical events. A legacy integration with no canonical events receives only the `usage` default; categories not previously observed require a trusted local operator to approve and apply the exact list:

```powershell
python -m retaniq set-integration-categories --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --source billing_app --category billing --category subscription
```

The CLI replaces the whole category list. Existing credentials remain valid, but ingestion outside the migrated grant list is denied until an operator explicitly expands it. The source token still has its existing purpose grants; category grants independently constrain which event families it may submit.

## 5. Time and point-in-time semantics

- `occurred_at`: when the source fact happened, normalized to UTC.
- `received_at`: actual time RetainIQ received/imported the record. Live API ingestion sets it server-side. Do not backdate it.
- `source_available_at`: optional first-known/available time in the original source. The importer accepts it only through an operator-approved mapping plus `--trust-source-availability`; a source export date or event occurrence date is not automatically equivalent.
- `as_of`: the feature/prediction cutoff selected by Member 2. A record is visible only when both `occurred_at <= as_of` and `COALESCE(source_available_at, received_at) <= as_of`.

An integration `IntegrationPrincipal` reads only events from that integration's source, even when it has `retention_inference`. For personalized features combining usage, billing, and subscriptions, provision a separate service principal with the exact source list and purpose grants:

```powershell
python -m retaniq create-service-principal --db .\data\retaniq.sqlite3 --tenant-id tenant_demo --role analyst --source product_app --source billing_app --source subscriptions_app --purpose retention_inference --purpose model_artifact_write
$env:RETAINIQ_M2_DATA_TOKEN = '<approved-service-token>'
```

Use this service principal when Member 2 must persist feature snapshots, labels, or predictions. It has the least-privilege writer contract: role `analyst`, the exact source list, `retention_inference`, and separate `model_artifact_write`. Another analyst principal without that purpose and admin/operator principals cannot persist those artifacts. It can write only for accounts explicitly mapped through at least one granted source. Add `billing_valuation` only when monetary feature values or explanations are required. All named sources must already have tenant-scoped integration records. The local provisioning command is trusted-operator only and is not exposed by HTTP. Authenticate that service token in Member 2's internal job:

```python
import os
from retaniq.data_foundation import authenticate_service_principal

principal = authenticate_service_principal(db_path, os.environ["RETAINIQ_M2_DATA_TOKEN"])
```

For a single source, Member 2 may use an integration principal as before:

```python
from retaniq.data_foundation import (
    get_account_snapshot_as_of,
    get_events_as_of,
    get_subscriptions_as_of,
    list_eligible_accounts_as_of,
)

eligible = list_eligible_accounts_as_of(db_path, principal, as_of)
account = get_account_snapshot_as_of(db_path, principal, customer_id, as_of)
events = get_events_as_of(db_path, principal, customer_id, as_of)
subscriptions = get_subscriptions_as_of(db_path, principal, customer_id, as_of)
```

When persistence is authorized, pass that same `ServicePrincipal` to the shared writers; this patch did not change shared feature, label, prediction, or ID fields:

```python
from retaniq.data_foundation import store_churn_label, store_feature_snapshot, store_prediction

feature_snapshot_id = store_feature_snapshot(
    db_path, principal, customer_id, as_of, feature_version,
    source_data_cutoff, engineered_features, data_quality_status,
)
store_churn_label(
    db_path, principal, customer_id, as_of, horizon_days, label,
    observation_through, label_policy_version, outcome_at=verified_outcome_at,
)
prediction_id = store_prediction(db_path, principal, prediction_contract)
```

`engineered_features`, labels, `verified_outcome_at`, and `prediction_contract` must come from Member 2's verified feature/label/model flow; the example intentionally supplies no fabricated values. Integration principals retain source-local artifact writing for customers mapped through that same source. A source token cannot write for a customer mapped only through another source.

The executable version is [`examples/member2_as_of_history.py`](../examples/member2_as_of_history.py). It demonstrates the current API using a temporary synthetic tenant and no labels or scores. Query helpers enforce tenant, exact source, and purpose scope from the authenticated principal. Account snapshots and eligibility enumeration additionally require an identity mapping from at least one authorized source; a token cannot probe a same-tenant customer mapped only through another source. A source integration can read usage, billing status and subscription lifecycle only from its own source. A service principal can aggregate its explicitly granted sources; a retention-only principal still receives billing status without financial amounts, pricing fields, or MRR unless it also has `billing_valuation`.

`GET /v1/integrations` remains the source-token self-health endpoint. `GET /v1/admin/integrations` is a separate tenant-health read for a service token with `admin` or `operator` role and `integration_health` purpose, restricted to that token's exact source grants. No dashboard frontend is included.

## 6. Churn outcomes, censoring and personal-history features

The canonical event model can represent verified effective end events as `subscription_cancelled_effective`, `subscription_non_renewed_effective`, or `subscription_involuntary_terminated`. Member 2 must define the multi-subscription account churn policy consistently; the current snapshot's eligibility is account-level and pending cancellation is a separate known-cancellation state. Eligibility is reconstructed from subscription events available at `as_of`; the undated current `customers.account_status` field is intentionally ignored by historical eligibility queries. A failure, cancellation request, static churn class, or source competition label must not be recast as an effective end without verified semantics.

No acquired source provides measured observation-through dates here. Member 2 therefore cannot distinguish mature 7/14/30 negatives from right-censored outcomes on actual records, compute actual positive coverage, or claim any horizon's feasibility. Incomplete outcomes remain `unknown` under the shared storage contract; this repository supplies storage validation, not a label builder.

Feature snapshot and explanation JSON keeps the same shared storage shape, but string values are accepted only in bounded categorical fields from `SAFE_CATEGORICAL_FIELDS` in `retaniq/data_foundation.py` (or `*_category` fields), with field-specific enums for statuses, directions/trends, currency, event types and a finite set of tier labels. Categorical values with seven or more digits are rejected after punctuation normalization; this blocks formatted payment-card and phone/account identifiers. Numeric/boolean model features and numeric fitted-model contributions remain supported. Reliability reasons remain a list of strings but must use one of these stable codes: `short_personal_usage_history`, `missing_usage_source`, `missing_billing_source`, `missing_subscription_source`, `insufficient_identity_mapping`, `stale_source_data`, `partial_source_coverage`, `unsupported_dataset`, `insufficient_event_history`, `unverified_source_availability`, `unknown_observation_coverage`, `feature_quality_limited`, or `model_applicability_limited`. Member 2 should map descriptive text such as “Short personal usage history” to `short_personal_usage_history`; display text belongs in the consuming UI, not source-derived stored strings.

If authorized records are later mapped with verified semantics, personalized as-of features may be derived from a tenant's own dated usage events, payment outcomes and subscription changes, plus freshness/availability timestamps. The implementation provides these point-in-time facts; it does not engineer rolling windows, cohort baselines, labels, model features, temporal splits, or predictions. Source-specific support tickets, intervention exposure and causal treatment effects are not present or implied.

## 7. Valuation contract for Member 3

When an integration has both `retention_inference` and `billing_valuation`, `get_account_snapshot_as_of` may return as-of `mrr_minor`, `currency`, `valuation_as_of`, `valuation_policy_version`, and a status. MRR uses source integer minor units and documented billing interval normalization/discount policy. Mixed currencies or missing active-subscription prices return no aggregate MRR; no FX conversion is performed. Retention-only reads omit monetary fields. No real prices or account MRR are currently available, and Member 1 does not claim value at risk or retention savings.

## 8. Verification evidence and boundaries

- `python -m examples.member2_as_of_history` — successful; output shows one synthetic eligible account, a prior usage event and no post-cutoff event.
- `python -m unittest discover -s tests -p test_member2_handoff.py -v` — passed the synthetic example's eligibility and cutoff assertions.
- `python -m unittest discover -s tests -p test_data_foundation.py -v` — PASS, 44 tests; covers the prior Prompt 03 source-scoped reads, service-principal grants, subscription ownership and migration upgrade, historical eligibility, operator health, and feature/label/prediction contracts, plus the new artifact-writer, event-category, and categorical-value regressions.
- `python -m unittest discover -s tests -v` — PASS, 45 tests; all fixtures are synthetic. Includes cross-source/cross-tenant reads and writes, explicit multi-source inference and persistence, denied event categories through direct and HTTP ingestion, formatted sensitive values, subscription-owner rollback, status-history cutoff behavior, and migration backfill/conflict refusal.
- `PRAGMA foreign_key_check` on a fresh database — PASS, 0 violations. The migration-upgrade test also checks foreign-key integrity after upgrading version-1 history through migration 003 and asserts migration records 001–003.
- `python -m compileall -q retaniq tests examples` — PASS. `python -m retaniq --help` — PASS and lists category provisioning. `git diff --check` — PASS; no configured linter or type checker exists in this checkout.
- `tests/test_data_foundation.py` also exercises synthetic API authentication/idempotency, tenant and purpose scope, late availability, subscription cutoff reconstruction, payment failure handling, MRR/currency, label/prediction storage, CSV normalization, availability trust gating, and replay ordering/visibility.
- No real-source mapping, real-data import, actual candidate coverage report, label generation, temporal split, model fit, or predictive evaluation has been executed. These require a legitimately authorized source and reviewed adapter.
