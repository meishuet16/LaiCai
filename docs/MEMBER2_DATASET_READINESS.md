# Member 2 — Historical Dataset Readiness Gate

Status: implemented validator, with no real dataset currently supplied.

The readiness gate answers whether an adapted historical dataset contains enough trustworthy evidence for genuine 7/14/30-day churn forecasting. It does not train a model, compute performance metrics, or replace Member 1’s canonical ingestion/database schema.

## Current status

The repository currently has no historical dataset, `DATASET_CARD.md`, or Member 1 data adapter. The actual project readiness status is therefore:

```text
BLOCKED — no historical dataset supplied
```

The included test fixtures are synthetic structural fixtures only. They are not authorized customer data and do not establish predictive performance.

## Minimum evidence required

A real dataset must provide, or defensibly reconstruct:

- Stable paying subscription-account identifiers and tenant/account mapping.
- Timestamped usage and/or billing events.
- Subscription lifecycle history, preferably including append-only lifecycle events.
- Actual churn-effective timestamps, not only a final `Churn=Yes/No` field.
- Known cancellation-request timestamps where available.
- Original event occurrence timestamps.
- Original source-availability timestamps, or a documented defensible availability assumption.
- Observation coverage sufficient to establish positive churn outcomes and complete negative follow-up for 7, 14, and 30 days.
- Enough earlier account behavior to support a personalized baseline, without using the recent comparison window.
- Provenance, authorization/license, schema mapping, and known limitations.

## Adapter boundary

Member 1 remains the owner of canonical ingestion and storage. The validator accepts a read-only `HistoricalDatasetAdapter` containing mapped collections:

```text
accounts
subscriptions
subscription_events
usage_events
billing_events
outcomes
```

`DatasetFieldMapping` maps source field names to the readiness concepts. This is an adapter boundary, not a new database schema. Member 1 can map canonical tables or an authorized import into this view without changing ownership of ingestion.

Example use:

```python
from retainiq_prediction import (
    DatasetProvenance,
    HistoricalDatasetAdapter,
    ProvenanceEvidenceType,
    assess_dataset_readiness,
)

report = assess_dataset_readiness(
    HistoricalDatasetAdapter(
        accounts=account_rows,
        subscriptions=subscription_rows,
        subscription_events=subscription_event_rows,
        usage_events=usage_rows,
        billing_events=billing_rows,
        outcomes=outcome_rows,
    ),
    provenance=DatasetProvenance(
        source_name="authorized source name",
        license_or_authorization="documented license or authorization reference",
        evidence_type=ProvenanceEvidenceType.REAL_AUTHORIZED,
    ),
)
```

The report contains row counts, field states, categories, and issue descriptions only. It does not log raw rows, customer identifiers, emails, or other PII.

## What the validator checks

The report distinguishes:

1. **Schema presence:** whether a mapped field appears in the supplied rows.
2. **Usable values:** whether values are non-empty and parseable, including timezone-aware timestamps.
3. **Temporal/outcome evidence:** whether the rows establish usable positive and complete negative observations for each horizon.

It checks:

- Stable account IDs and tenant/account references.
- Duplicate account, subscription, event, and outcome records.
- Usage/billing event timestamps and lifecycle-event timestamps.
- Subscription history and outcome cutoffs.
- Churn-effective timestamps.
- Known cancellation timestamps when present.
- Source availability timestamps and explicit availability assumptions.
- 7/14/30-day positive and negative observation coverage.
- Pre-cutoff usage history for personalized-baseline evidence.
- Provenance and authorization/license evidence.

## Result semantics

| Result | Meaning |
|---|---|
| `PASS` | All configured horizons have positive and complete-negative evidence, baseline evidence exists, provenance is real/authorized, and required temporal checks pass. This is a readiness result, not a performance claim. |
| `PARTIAL` | Some structural or horizon evidence is usable, but a horizon, source-availability proof, baseline requirement, or real-data provenance remains incomplete. |
| `BLOCKED` | No dataset, required temporal/outcome fields, valid timestamps, account mapping, event evidence, or churn-effective evidence prevents genuine training readiness. |

Supported horizons are listed only when the supplied evidence includes both an observed positive and a fully observed negative for that horizon. A missing or censored follow-up is not converted to a negative.

Synthetic fixtures can receive `PARTIAL` with supported structural horizons, but never `eligible_for_genuine_training=True` or a real-world performance claim.

## Before model training is permitted

Member 1 must provide:

- An authorized longitudinal dataset and completed `DATASET_CARD.md`.
- Canonical field mappings and tenant/account identity guarantees.
- Subscription churn semantics for multi-subscription accounts.
- Occurrence and source-availability timestamp semantics.
- Sufficient 7/14/30-day outcome coverage and documented censoring.
- A reproducible replay path using the canonical event contract.

Only after the gate passes should Member 2 proceed to point-in-time feature building, labels, baselines, calibration, or model training. Passing this gate alone does not prove model quality.

## Known limitations

- The default 28-day personalized-baseline span is an explicit readiness heuristic and requires confirmation using development data.
- The adapter does not infer event semantics from arbitrary source labels.
- It does not implement label generation, leakage-safe splits, model training, calibration, or evaluation metrics.
- It does not validate database constraints, authentication, or Member 1 ingestion behavior.
- Source availability may be documented as an assumption when absent, but robustness to late-arriving data remains unverified.
