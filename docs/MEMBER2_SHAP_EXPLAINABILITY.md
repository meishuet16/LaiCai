# Member 2 SHAP Explainability

## Scope and evidence boundary

This milestone adds an optional, horizon-specific explainability layer for the
internal LightGBM candidates. It uses the real `shap.TreeExplainer`
implementation against a fitted LightGBM artifact. The tests fit only
explicitly synthetic fixtures; they are structural contract tests and are not
predictive-performance evidence.

The optional dependency is pinned to the compatible minor range
`shap>=0.53,<0.54`. The local verification environment used SHAP 0.53.0,
LightGBM 4.7.0, NumPy 2.5.3, and Python 3.14.4. SHAP remains optional so the
package can still import when the dependency is not installed; explanation
requests then return `SHAP_DEPENDENCY_UNAVAILABLE`.

## What is explained

`LightGBMExplainer` explains one independent 7-, 14-, or 30-day LightGBM model
for one immutable `FeatureSnapshot`. It reuses the model's existing
`FeatureVectorizer` and requires the artifact feature order to equal the
approved `MODEL_FEATURE_ALLOWLIST`:

```text
sessions_prev_7d
sessions_prev_30d
days_since_last_observed_session
recent_usage_trend
observed_weeks
valid_usage_history
historical_avg_sessions_per_week
recent_avg_sessions_per_week
absolute_usage_deviation
percentage_usage_deviation
recent_to_baseline_usage_ratio
historical_weekly_usage_variability
```

Identifiers, labels, churn timestamps, cancellation-request fields, and other
protected or non-approved fields cannot enter this explanation vector. Missing
required feature values result in an unavailable explanation; they are not
fabricated or silently imputed by this module.

The explained output is the fitted LightGBM **raw margin/log-odds**. The result
stores the expected base value, actual raw margin, raw model probability,
signed contribution for every feature, magnitude, direction, and additivity
error. A successful result must satisfy:

```text
expected_base_value + sum(shap_value) ~= actual_explained_model_output
```

within the configured tolerance. Binary SHAP output variants are normalized to
the positive class and unsupported shapes fail closed.

Raw SHAP output is not the canonical calibrated cumulative probability. It does
not explain the later calibration or 7/14/30 horizon-coherence adjustment.
SHAP values describe model associations, not causes, treatment effects, or
evidence that an intervention will work.

## Result and failure semantics

`ExplanationResult` is a versioned typed record with:

- tenant, customer, prediction cutoff, horizon, model version, and feature version;
- method/version and `available`/`unavailable` status;
- raw output-space, base value, raw margin, raw probability, and additivity audit;
- full-fidelity contributions plus deterministic top-K positive and negative contributors;
- neutral human-readable association phrases;
- limitations and machine-readable reason codes.

The top-K selection sorts by absolute SHAP magnitude and breaks ties by the
locked allowlist order. The complete contribution tuple is always retained.

Normal explanations are not produced for `abstained`, `known_cancellation`,
or `not_eligible` prediction statuses. Missing or incompatible artifacts,
version/order mismatches, tenant/customer scope mismatches, unavailable input
features, missing SHAP, and failed additivity return an unavailable result.
When supplied, the existing `PredictionReadinessAssessment` must indicate
scoring is allowed and model artifacts are ready; otherwise the result is
unavailable. Production callers must still run the canonical eligibility,
reliability, freshness, calibration, and horizon-coherence gates before
exposing any explanation alongside a prediction.

## Synthetic structural fixture

The following is an explicitly synthetic shape example, not a real customer
output and not a performance claim. The complete `feature_contributions` array
contains all approved features in model order; only a small top-K subset is
shown here for readability.

```json
{
  "tenant_id": "tenant_synthetic",
  "customer_id": "customer_synthetic_001",
  "as_of": "2026-10-05T00:00:00Z",
  "horizon_days": 7,
  "model_version": "lightgbm_synthetic_v1",
  "feature_version": "features_synthetic_v1",
  "explanation_method": "shap_tree_explainer",
  "explanation_version": "shap_tree_v1",
  "explanation_status": "available",
  "explained_output_space": "raw_lightgbm_margin_log_odds",
  "expected_base_value": "<synthetic fixture value>",
  "actual_explained_model_output": "<synthetic fixture value>",
  "raw_model_probability": "<synthetic fixture value>",
  "additivity_error": "<synthetic fixture value>",
  "positive_contributors": [
    {"feature_name": "recent_usage_trend", "shap_value": "<synthetic value>"}
  ],
  "negative_contributors": [],
  "limitations": [
    "raw margin/log-odds only",
    "associations are not causes",
    "calibration and horizon coherence are not explained"
  ]
}
```

## Downstream mapping proposal

The canonical `PredictionOutput` remains unchanged. Once the team agrees on the
shared attribution shape, Member 2 can map each available `ExplanationResult`
under `explanations_by_horizon` using the prediction's immutable
`prediction_id`, model/feature versions, and raw-output limitations. The exact
persistence shape and whether raw contribution values are exposed to Members 3
and 4 remain unresolved integration questions.

Member 3 may consume the attribution as contextual model association only; it
must not treat a positive contributor as an action recommendation or causal
reason. Member 4 may retain the method/version, feature order, additivity audit,
limitations, and unavailable reason codes for traceability and governance.

## Member 1 dependencies and limitations

Member 1 must provide the tenant-authorized, point-in-time feature snapshot and
stable source evidence references already required by the existing feature
contract. The adapter must preserve `tenant_id`, `customer_id`, `as_of`,
`feature_version`, data cutoff, feature values, and source availability
semantics. The explainer does not create a database, infer missing history, or
perform authorization.

Open integration questions include the final `explanations_by_horizon` storage
shape, retention/privacy policy for attribution values, model-artifact registry
identity, the production calibration/coherence gate handoff, and Member 1's
canonical availability and correction semantics. No authorized longitudinal
dataset or production model evidence exists in this repository.
