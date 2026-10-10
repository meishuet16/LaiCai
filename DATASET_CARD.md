# RetainIQ v2 dataset card

**Gate status: `NOT_READY`**

## Source and provenance

- **Dataset/source name:** No historical customer dataset is present in this checkout.
- **Provenance:** UNKNOWN / NOT YET VERIFIED.
- **License or permission to use:** UNKNOWN / NOT YET VERIFIED. No records were imported.
- **Source documentation or configured dataset path:** None found in the repository.

## Coverage observed in the repository

There are no CSV, Parquet, database, fixture, or other customer-data files in the checkout. Therefore the following are **UNKNOWN / NOT YET VERIFIED**:

- Available event, source-availability, and observation-window timestamps.
- Paying-account and subscription identifier coverage.
- Dated usage and billing history.
- Subscription start, cancellation request, entitlement end, and churn-effective outcome coverage.
- Source availability timestamps and late-arrival coverage.
- Duplicate, missing, or censored follow-up rates.

## Prediction feasibility

Genuine 7-, 14-, and 30-day labels and early-warning evaluation are **not feasible to verify** without authorized longitudinal events, effective churn times, and complete per-horizon observation coverage. The dataset gate remains `NOT_READY`; no training or model evaluation was run.

The unit tests create synthetic temporary SQLite records to check ingestion, tenant scoping, idempotency, history reconstruction, valuation, and availability filters. These fixtures are engineering evidence only. They are not real customer data, churn outcomes, model predictions, or performance evidence.

## Known data gaps

- No source mapping or dataset license has been verified.
- No support-ticket, entitlement, or historical intervention data is present.
- If an imported source lacks its original availability timestamp, the importer uses actual import `received_at` as the availability fallback. Such rows cannot establish that the source fact was known at an earlier historical cutoff, and replay will exclude them from those earlier cutoffs.
- No dated foreign-exchange source or policy exists; mixed currencies remain unaggregated.
