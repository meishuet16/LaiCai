# Member 2 Offline Historical Evaluation

## Scope and evidence boundary

`historical_evaluation.py` evaluates immutable historical prediction snapshots
against already-built `ChurnLabel` outcomes. It does not run live inference,
fit estimators, fit calibrators, select thresholds, alter historical
predictions, or persist results. It consumes the existing `TemporalSplitResult`
and its split manifest.

The current repository has no authorized longitudinal dataset. Reports created
from the synthetic fixtures use `evaluation_status=synthetic_only` and
`synthetic_test_only=true`; they are structural arithmetic checks, not
real-world performance evidence. Real evaluation remains `blocked` until
authorized provenance, complete maturity coverage, and a PASS readiness gate
are available.

## Input contracts

The evaluator accepts either:

- canonical `PredictionOutput` records, expanded into independent 7/14/30-day
  `EvaluationPrediction` scores; or
- explicitly typed candidate scores containing model name, tenant/customer,
  optional `prediction_id`, `as_of`, horizon, probability, status, model/
  feature/calibration/label-policy versions.

It also requires `ChurnLabel` records, a `TemporalSplitResult`, a frozen
evaluation cutoff, dataset provenance status, and a review capacity `K`.
Optional inputs are typed as-of MRR records and frozen historical alerts.

The immutable join key is:

```text
(tenant_id, customer_id, prediction.as_of, horizon_days)
```

`prediction_id` is retained when present but is not substituted for tenant,
customer, cutoff, or horizon matching. Duplicate prediction or label joins are
rejected. Cross-tenant and cross-customer records cannot be joined.

## Chronology and maturity

Evaluation is partitioned by the existing split manifest. The default final
partition is TEST. The evaluator requires a frozen selection policy and records
`evaluation_cutoff`; TEST outcomes cannot influence model selection, threshold
selection, calibration, feature selection, or preprocessing.

A label is usable only when its supporting information is mature and available
by the evaluation cutoff:

- positive: `label_status=positive`, `label=1`, qualifying effective churn,
  and evaluation/generated timestamps at or before the cutoff;
- negative: `label_status=negative`, `label=0`, no churn event, and
  `label_observed_through` reaches the entire horizon;
- pending: evidence or label generation becomes available after the cutoff,
  or a negative observation window has not matured;
- unknown, excluded, unsupported, or missing: excluded from metric
  denominators and reported separately.

Unknown is never converted to zero. Historical predictions are not rewritten
after outcomes are observed.

## Population coverage and metrics

For each model and horizon, the report includes the complete eligible snapshot
population, scored count, mature labeled count, evaluation coverage, abstention
rate, and exclusion counts. Scored metric denominators contain only eligible,
scored predictions joined to mature positive or negative labels.

Available metrics are independent by horizon:

- PR-AUC / average precision;
- ROC-AUC;
- Brier score;
- Precision@K and Recall@K using explicit configured review capacity `K`;
- calibration bins containing sample count, mean predicted probability, and
  observed positive rate; and
- horizon-ordering violation frequency for complete three-horizon snapshots.

PR-AUC, ROC-AUC, and Recall@K are explicitly unavailable for empty or
single-class samples. Brier score remains computable for a non-empty single
class because it is a probability-error metric, but it is not a substitute for
class-discriminating metrics. No undefined metric is replaced with zero.

Ranking uses the documented probability for the requested horizon, excludes
non-scored predictions, and breaks ties deterministically by tenant, customer,
cutoff, and prediction ID. Competing models report their scored mature cohort
and coverage separately; a warning is emitted when those cohorts differ.

## Revenue Captured@K handoff

`evaluate_revenue_captured_at_k` is available only when reliable as-of MRR,
one comparable currency, and an explicit account/snapshot deduplication policy
are supplied. It deduplicates overlapping snapshots for the same account and
qualifying churn-effective event before ranking and denominator calculation.

Different currencies are never summed or directly compared; the result is
explicitly unavailable when multiple currencies are supplied. The metric is:

```text
churned as-of MRR represented in selected top K
-----------------------------------------------
total churned as-of MRR in eligible evaluation cohort
```

This measures historical churned-MRR exposure captured by a ranking. It is not
revenue saved, intervention uplift, ROI, or causal retention evidence. Member 3
must provide the final account/snapshot deduplication policy and currency/MRR
contract before using it in a decision workflow.

## Early-warning lead time

Lead-time evaluation is `not_ready` unless a frozen alert-policy version and
historical alert records are supplied. For a mature qualifying churn, the
earliest selected pre-churn alert is measured as:

```text
churn_effective_at - earliest qualifying alert_at
```

False alerts do not contribute lead time. Multiple snapshots are handled by
selecting the earliest qualifying alert for the event. Pending/right-censored
outcomes are counted as censored, not as successful early warnings. No average
lead-time claim is invented when the alert policy or qualifying outcome is
missing.

## Model-comparison safeguards

The interface can represent rule-based, logistic, ordinary LightGBM, and
personalized-baseline LightGBM candidates through the same typed score record.
It does not retrain any candidate or implement the pending personalized
baseline ablation. Fair comparison requires the same horizon, TEST boundary,
evaluation cutoff, mature-label population, review capacity, and explicit
treatment of abstentions. Coverage differences remain visible rather than
being hidden by a scored-only denominator.

## Prompt 14 coverage audit and SHAP warning investigation

The prior pipeline tests contain 16 tests covering the requested 26 scenarios:

| Prompt 14 scenarios | Coverage | Evidence |
|---|---|---|
| 1–5: integrated path, three models/calibrators, ordering, provenance diagnostics | Direct | `tests/test_prediction_pipeline.py` integrated/spies test |
| 6–7: actual-model SHAP and raw-output limitation | Direct | pipeline SHAP integration test plus existing SHAP suite |
| 8–11: cancellation, ineligible, insufficient, limited evidence routing | Direct | routing tests |
| 12–15: missing bundle, no raw fallback, feature/metadata mismatches | Direct | bundle compatibility tests |
| 16–19: late/future events, missing coverage, stale source, tenant isolation | Direct | point-in-time/freshness pipeline tests |
| 20–21: distinct IDs and timezone-aware inputs | Direct | contract/request tests |
| 22–23: SHAP failure and synthetic non-deployability | Direct | failure-preservation and synthetic-mode tests |
| 24–26: production blocked, uncertainty contract, PredictionOutput invariants | Direct | production/readiness/round-trip tests |

The SHAP/LightGBM warning comes from SHAP 0.53.0 at
`shap/explainers/_tree.py:579`: binary LightGBM SHAP output changed between
versions from an array to a list of class arrays. It is a compatibility notice,
not a model failure. `LightGBMExplainer` explicitly normalizes supported binary
array/list shapes to the positive class, and the tests verify that base value
plus all contributions reproduces the raw LightGBM margin within tolerance.
The warning is therefore documented rather than globally suppressed.

## Member 1 and Member 3 dependencies

Member 1 must provide authorized historical provenance, canonical lifecycle and
observation availability, stable tenant/account IDs, mature outcome coverage,
as-of MRR with currency, and correction semantics. A static final churn table
is insufficient for this evaluator.

Member 3 may consume ranking outputs and the explicitly limited Revenue
Captured@K handoff. It must not interpret historical churned MRR exposure as
saved revenue or bypass reliability, eligibility, capacity, approval, or
currency policies.

Member 4 may retain evaluation cutoff, split policy, provenance, version
references, maturity/exclusion counts, calibration bins, ordering audits,
lead-time readiness, and warnings for governance. Synthetic reports must not
enter production dashboards, model promotion, or feedback claims.

## Known limitations

- No authorized real evaluation has been performed.
- The current temporal splitter marks synthetic data BLOCKED and authorized
  data only PARTIAL; a separate real dataset gate is still required.
- Threshold selection, model promotion, retraining, intervention attribution,
  and dashboard presentation are outside this module.
- `explanations_by_horizon` and evaluation persistence remain shared contract
  questions rather than database schemas introduced here.
- `IMPROVEMENT-001` through `IMPROVEMENT-004` remain pending and are not
  claimed complete.
