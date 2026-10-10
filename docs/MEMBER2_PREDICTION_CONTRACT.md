# Member 2 — Canonical Prediction Contract

Status: minimal validated schema foundation. This document defines transport and validation semantics; it does not claim a trained model, predictive performance, or an implemented API.

## Canonical output

`PredictionOutput` is one immutable account-level forecast snapshot. It contains:

| Field | Meaning |
|---|---|
| `tenant_id` | Authenticated tenant scope; never trusted from an unverified client body. |
| `customer_id` | Stable paying subscription account identity. |
| `prediction_id` | Unique identity of this account forecast snapshot; used for downstream case and feedback linkage. |
| `prediction_run_id` | Batch/job identity shared by forecasts produced in one inference run. |
| `as_of` | Point-in-time cutoff for facts allowed in the forecast. |
| `generated_at` | Time the forecast record was generated. |
| `status` | `scored`, `abstained`, `known_cancellation`, or `not_eligible`. |
| `p_churn_7d` | Calibrated cumulative probability through 7 days, or `null` when not scored. |
| `p_churn_14d` | Calibrated cumulative probability through 14 days, or `null` when not scored. |
| `p_churn_30d` | Calibrated cumulative probability through 30 days, or `null` when not scored. |
| `feature_version` | Version of the feature definition/snapshot used. |
| `model_version` | Version of the fitted model used. |
| `calibration_version` | Version of the probability calibration used. |
| `label_policy_version` | Version of the churn-label policy used for training/evaluation. |
| `reliability` | Applicability and evidence-quality status with reasons. |
| `data_freshness` | Source freshness status and optional input cutoff/stale-source details. |
| `uncertainty` | Explicitly non-quantified uncertainty until validated intervals exist. |
| `explanations_by_horizon` | Horizon-keyed model-attribution payload; currently extensible pending team agreement on attribution detail shape. |

All IDs and version strings must be non-empty. `as_of`, `generated_at`, and any supplied source cutoff timestamps must be timezone-aware.

## Validation rules

- Every probability is constrained to `[0, 1]`.
- `scored` requires all three probabilities and enforces `p_churn_7d <= p_churn_14d <= p_churn_30d`.
- `abstained`, `known_cancellation`, and `not_eligible` require all probabilities to be `null`.
- `prediction_id` and `prediction_run_id` are separate, non-empty identities and cannot be conflated in the schema.
- Reliability values are limited to `sufficient_evidence`, `limited_evidence`, and `insufficient_evidence`.
- Freshness values are limited to `fresh`, `partially_stale`, `stale`, and `unknown`.
- Uncertainty currently accepts only:

  ```json
  {"status": "not_quantified", "method": "none", "intervals": null}
  ```

  No numerical confidence estimate or interval is implied.

## Status semantics

- `scored`: eligible and sufficiently applicable for numeric probabilities.
- `abstained`: the system cannot establish sufficient eligibility, critical data, or model applicability; probabilities are null.
- `known_cancellation`: a cancellation request or scheduled termination was known by `as_of`; this is not prospective churn scoring.
- `not_eligible`: the account is outside the prospective prediction population for another documented eligibility reason.

Reliability is a data/applicability quality status, not a per-customer confidence percentage. Freshness reports source coverage and staleness; it does not change the point-in-time rule that no fact available after `as_of` may enter the forecast.

## Synthetic JSON fixture

The following is a **synthetic contract fixture only**. Its probabilities and IDs are not model outputs or performance evidence.

```json
{
  "tenant_id": "tenant_synthetic",
  "customer_id": "customer_synthetic_001",
  "prediction_id": "prediction_synthetic_001",
  "prediction_run_id": "run_synthetic_001",
  "as_of": "2026-10-10T00:00:00Z",
  "generated_at": "2026-10-10T00:00:10Z",
  "status": "scored",
  "p_churn_7d": 0.12,
  "p_churn_14d": 0.38,
  "p_churn_30d": 0.81,
  "feature_version": "features_synthetic_v1",
  "model_version": "model_synthetic_v1",
  "calibration_version": "calibration_synthetic_v1",
  "label_policy_version": "labels_synthetic_v1",
  "reliability": {
    "status": "sufficient_evidence",
    "reasons": []
  },
  "data_freshness": {
    "status": "fresh",
    "input_data_as_of": "2026-10-10T00:00:00Z",
    "stale_sources": []
  },
  "uncertainty": {
    "status": "not_quantified",
    "method": "none",
    "intervals": null
  },
  "explanations_by_horizon": {}
}
```

## Cross-part dependencies

### Member 1 provides

- Tenant-scoped account/subscription identity and authenticated context.
- Point-in-time-safe usage, billing, and subscription lifecycle records.
- `occurred_at` plus `received_at` or trusted source-availability timestamps.
- Versioned feature snapshots, churn labels, label policy, data coverage, and eligibility inputs.
- Historical replay using the same canonical event semantics as live ingestion.

### Member 3 consumes

Member 3 consumes the immutable prediction snapshot, its reliability/freshness metadata, versions, `as_of`, and calibrated probabilities. It joins MRR and business constraints from Part 1. Member 2 does not own routing, action selection, budget, ROI, or approval logic.

### Member 4 consumes

Member 4 links `prediction_id` to mature per-horizon feedback, evaluation runs, candidate model governance, and customer timelines. Feedback is anchored at prediction `as_of`; operational action follow-up uses a separate action/follow-up anchor.

## Unresolved integration questions

- Account-level churn semantics for accounts with multiple subscriptions.
- Canonical precedence and naming for source availability timestamps.
- Exact uniqueness/persistence constraint for repeated predictions at the same account/cutoff.
- Detailed attribution shape inside `explanations_by_horizon`.
- Reliability/freshness thresholds and policy-version ownership.
- Minimum evidence gates for evaluation and candidate retraining.
- Part 4’s older feedback example uses `prediction_run_id`; the integrated contract requires exact `prediction_id` linkage.

These questions remain coordination items and are not silently resolved by this schema foundation.
