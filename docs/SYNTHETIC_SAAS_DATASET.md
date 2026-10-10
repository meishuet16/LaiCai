# Synthetic SaaS dataset

## Purpose and status

The generator produces an explicitly synthetic, tenant-isolated longitudinal SaaS dataset for RetainIQ's operational demonstration. It does not contain KKBox records or real customer data. Generation does not constitute model training, real-world validation, causal uplift evidence, or saved revenue.

Profiles use the same 24-month default period, 2024-10-01 through 2026-09-30:

| Profile | Accounts | Intended use |
|---|---:|---|
| QUICK | 200 | Smoke and canonical integration checks |
| STANDARD | 3,000 | Local development and integration |
| FULL | 20,000 | Final comprehensive synthetic demonstration |
| STRESS | 50,000 | Optional scalability work |

Each generation creates a new immutable directory under `<output>/<profile>/<dataset_id>`. Existing datasets are never overwritten. A failed run cleans only its staging directory.

## Generated family

- `customers.csv`: one synthetic paying account per row.
- `customer_identities.csv`: explicit source-specific identity mapping.
- `plan_catalog.csv`: tenant-scoped plans and integer minor-unit prices.
- `subscription_events.csv`, `billing_events.csv`, `usage_events.csv`: category-specific canonical events.
- `canonical_events.csv`: the exact input used by the synthetic canonical adapter.
- `observation_coverage.csv`: complete, partial, and outage periods.
- `scenario_coverage.json`: measured overlapping scenario counts.
- `quality_report.json`: generator disclosures and measured censoring count.
- `label_oracle_fixtures.json`: isolated examples for future Member 2 label tests.
- `adversarial_fixtures.json`: isolated rejection expectations.
- `split_manifest.json`: chronological split proposal.
- `dataset_manifest.json`: stable configuration, counts, byte sizes, and SHA-256 hashes.

Generator-only latent state drives the stochastic lifecycle and is discarded. It is absent from canonical payloads, model features, and ordinary scenario rows.

## Commands

```powershell
python -m retaniq.synthetic generate --profile quick --seed 2026
python -m retaniq.synthetic validate --profile quick
python -m retaniq.synthetic import --profile quick --db "$HOME\RetainIQ-private\synthetic_saas_v1\quick.sqlite3" --verify-idempotency

python -m retaniq.synthetic generate --profile standard --seed 2026
python -m retaniq.synthetic validate --profile standard

python -m retaniq.synthetic generate --profile full --seed 2026
python -m retaniq.synthetic validate --profile full
```

The default output is derived from the current home directory: `~/RetainIQ-private/synthetic_saas_v1`. Use `--output` to choose another private location. `--accounts`, `--tenants`, `--start-date`, `--end-date`, `--event-density`, `--usage-frequency`, `--source-outage-frequency`, `--billing-failure-frequency`, and `--churn-hazard-multiplier` override profile settings.

## Canonical compatibility

The adapter creates separate usage, billing, and subscription integrations for each tenant, grants only the matching event category, creates exact identity mappings, and sends every row through `retaniq.data_foundation.ingest_event`. Generated credentials stay in process memory. It provisions one tenant-scoped analyst principal per tenant for verification, but does not persist or return its credential. Provision a Member 2 credential explicitly with the existing `create-service-principal` operator command.

The implementation uses only canonical event types and attribute allowlists. A failed payment remains billing evidence. Effective subscription termination remains a separate event. Loss of one subscription does not imply account churn while another paid entitlement remains active.
