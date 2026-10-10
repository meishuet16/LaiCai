# Member 1 → Member 2 data handoff

**Status:** Canonical query/API contract is available; real historical dataset is **NOT_READY**.
**Purpose:** Retention inference.
**Database in this checkout:** Local SQLite prototype, not the production PostgreSQL requirement.

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

`subscription_id` identifies a subscription under a tenant, not a person or seat. `customer_id` is the internal canonical paying-account key. `external_customer_id` is a source-specific account key and must be mapped explicitly; there is no fuzzy or email merge. Source event idempotency uses `(tenant_id, source, source_event_id)`.

## 4. Time and point-in-time semantics

- `occurred_at`: when the source fact happened, normalized to UTC.
- `received_at`: actual time RetainIQ received/imported the record. Live API ingestion sets it server-side. Do not backdate it.
- `source_available_at`: optional first-known/available time in the original source. The importer accepts it only through an operator-approved mapping plus `--trust-source-availability`; a source export date or event occurrence date is not automatically equivalent.
- `as_of`: the feature/prediction cutoff selected by Member 2. A record is visible only when both `occurred_at <= as_of` and `COALESCE(source_available_at, received_at) <= as_of`.

For a tenant-authorized `IntegrationPrincipal`, Member 2 can use:

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

The executable version is [`examples/member2_as_of_history.py`](../examples/member2_as_of_history.py). It demonstrates the current API using a temporary synthetic tenant and no labels or scores. Query helpers enforce tenant and purpose scope from the authenticated principal. A retention-only principal can read usage, billing status and subscription lifecycle; financial amounts, pricing fields and valuation are omitted unless the principal also has `billing_valuation`.

## 5. Churn outcomes, censoring and personal-history features

The canonical event model can represent verified effective end events as `subscription_cancelled_effective`, `subscription_non_renewed_effective`, or `subscription_involuntary_terminated`. Member 2 must define the multi-subscription account churn policy consistently; the current snapshot's eligibility is account-level and pending cancellation is a separate known-cancellation state. A failure, cancellation request, static churn class, or source competition label must not be recast as an effective end without verified semantics.

No acquired source provides measured observation-through dates here. Member 2 therefore cannot distinguish mature 7/14/30 negatives from right-censored outcomes on actual records, compute actual positive coverage, or claim any horizon's feasibility. Incomplete outcomes remain `unknown` under the shared storage contract; this repository supplies storage validation, not a label builder.

If authorized records are later mapped with verified semantics, personalized as-of features may be derived from a tenant's own dated usage events, payment outcomes and subscription changes, plus freshness/availability timestamps. The implementation provides these point-in-time facts; it does not engineer rolling windows, cohort baselines, labels, model features, temporal splits, or predictions. Source-specific support tickets, intervention exposure and causal treatment effects are not present or implied.

## 6. Valuation contract for Member 3

When an integration has both `retention_inference` and `billing_valuation`, `get_account_snapshot_as_of` may return as-of `mrr_minor`, `currency`, `valuation_as_of`, `valuation_policy_version`, and a status. MRR uses source integer minor units and documented billing interval normalization/discount policy. Mixed currencies or missing active-subscription prices return no aggregate MRR; no FX conversion is performed. Retention-only reads omit monetary fields. No real prices or account MRR are currently available, and Member 1 does not claim value at risk or retention savings.

## 7. Verification evidence and boundaries

- `python -m examples.member2_as_of_history` — successful; output shows one synthetic eligible account, a prior usage event and no post-cutoff event.
- `python -m unittest discover -s tests -p test_member2_handoff.py -v` — passed the synthetic example's eligibility and cutoff assertions.
- `tests/test_data_foundation.py` exercises synthetic API authentication/idempotency, tenant and purpose scope, late availability, subscription cutoff reconstruction, payment failure handling, MRR/currency, label/prediction storage, CSV normalization, availability trust gating, and replay ordering/visibility.
- No real-source mapping, real-data import, actual candidate coverage report, label generation, temporal split, model fit, or predictive evaluation has been executed. These require a legitimately authorized source and reviewed adapter.
