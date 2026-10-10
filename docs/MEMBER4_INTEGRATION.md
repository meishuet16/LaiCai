# Member 4 integration plan

## Scope

This repository is being used as the dashboard and integration shell for RetainIQ. The frontend is intentionally honest about the current status: it demonstrates the risk-review workflow and dashboard layout using clearly labeled mock data while the prediction and decision modules are treated as integration boundaries rather than fabricated results.

## Current architecture

1. Dataset ingestion layer
   - Handles CSV validation, schema checks, and normalized customer records.
   - Produces consistent error responses for missing columns and malformed values.

2. Feature-builder boundary
   - Accepts normalized customer data and emits point-in-time features.
   - This boundary should reject late-arriving data after `as_of` and preserve `tenant_id`/customer identity.

3. Prediction boundary
   - Receives feature snapshots and emits `prediction_id`, `status`, `p_churn_7d`, `p_churn_14d`, and `p_churn_30d` with reliability and freshness metadata.
   - The frontend must not imply certainty unless the model actually provides scored values.

4. Decision boundary
   - Consumes predictions and produces route decisions such as `PRIORITY_REVIEW`, `HUMAN_REVIEW`, or `OBSERVE`.
   - ROI values stay scenario-based and must be labeled as assumption-only.

5. Dashboard boundary
   - Presents summary metrics, high-risk customer counts, risk distribution, and customer-level detail cards.
   - Surfaces blocked or unavailable states instead of inventing metrics.

## Run locally

```bash
npm install
npm run dev -- --host 0.0.0.0
```

Then open the local Vite URL shown in the terminal.

## Mock mode behavior

The current frontend uses fixture data instead of a live backend. That is intentional and clearly labeled as:

- `synthetic` for demo-friendly generated records
- `assumption` where business ROI or inactive states are not backed by source data

The frontend must never present mock outputs as real model results.

## Example data contract

```json
{
  "customerId": "CUST-2041",
  "company": "Northwind Labs",
  "segment": "Mid-market SaaS",
  "risk": 0.81,
  "score": 81,
  "route": "PRIORITY_REVIEW",
  "status": "scored",
  "mrr": 18200,
  "reliability": "sufficient_evidence",
  "freshness": "fresh",
  "action": "ACCOUNT_CHECK_IN",
  "evidence": "synthetic"
}
```

## Known limitations

- No backend API is registered yet.
- No production model or decision engine is connected.
- Data is fixture-level only for UI validation and demo flow.
- The dashboard is intentionally a thin integration front-end and will need actual module contracts before production use.

## Next implementation steps

1. Add a CSV upload form and validation logic.
2. Add a lightweight API layer with mocked module adapters.
3. Wire summary cards to actual normalized data.
4. Add customer filters and detail panels.
5. Replace mock data with the real integration contract once the prediction/decision modules are connected.
