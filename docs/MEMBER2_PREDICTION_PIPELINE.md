# Member 2 End-to-End Prediction Pipeline

## Scope

`prediction_pipeline.py` is an internal orchestration layer for one
tenant/account/prediction-cutoff request. It composes the existing point-in-time
adapter, eligibility evaluator, feature builder, freshness and reliability
assessments, independent LightGBM models, horizon-specific calibrators, horizon
coherence, and SHAP explanations.

It does not create a database, API, authentication service, model trainer,
calibrator fitter, dashboard, decision route, or retraining workflow. The
canonical `PredictionOutput` contract is unchanged.

## Execution flow

```text
PredictionRequest
  -> PointInTimeDataAdapter.snapshot_for(tenant, customer, as_of)
  -> evaluate_prediction_eligibility
  -> FeatureBuilder.build(..., usage_coverage)
  -> assess_data_freshness
  -> assess_reliability
  -> verify all model/calibrator artifacts
  -> raw LightGBM predictions for 7/14/30
  -> matching sigmoid calibration for each horizon
  -> cumulative-max horizon coherence
  -> matching TreeSHAP explanations
  -> canonical PredictionOutput
```

The pipeline never trains a model or fits a calibrator during `run`. It passes
the same immutable `FeatureSnapshot` to all three horizon models and their
corresponding explainers.

## Input and internal output contracts

`PredictionRequest` requires:

- `tenant_id` and `customer_id`;
- timezone-aware prediction `as_of`;
- a separate non-empty `prediction_run_id`;
- optional point-in-time usage coverage evidence; and
- source freshness evidence for the requested cutoff.

Naive timestamps are rejected by Pydantic. The adapter remains responsible for
tenant/account-scoped historical reads and availability filtering. The pipeline
checks that returned snapshot and feature identities match the request.

`PipelineResult` contains an internal `PipelineStatus`, optional canonical
`PredictionOutput`, machine-readable reason codes, safe diagnostics, version
references, and an explicit `synthetic_test_only`/`deployable` boundary.
Pipeline statuses are orchestration states, not additions to the canonical
prediction status enum.

## Routing and abstention

| Condition | Internal result | Canonical output |
|---|---|---|
| Eligible, gates pass, compatible ready bundle | `completed` | `scored` with calibrated/coherent probabilities |
| Eligible, limited evidence allowed by policy | `completed` | `scored`, reliability warnings preserved |
| Insufficient eligibility/data or stale essential source | `abstained_due_to_insufficient_evidence` | `abstained` with null probabilities when metadata permits |
| Known cancellation at cutoff | `known_cancellation` | `known_cancellation`, no model/calibrator calls |
| Outside active paying population | `not_eligible` | `not_eligible`, no model/calibrator calls |
| Missing/incompatible/unready model bundle | `model_bundle_not_ready` | no fabricated low-risk output |
| Technical adapter, inference, calibration, or contract failure | `integration_or_contract_error` | no misleading customer-risk status |

Missing coverage is never converted to zero usage. A failed payment or recent
silence is not independently treated as churn. Future and late-arriving facts
are excluded by the existing adapter before feature construction.

## Bundle compatibility and score provenance

Before inference, all three model/calibrator pairs must exist and be ready. The
pipeline verifies horizon identity, model/calibration versions, feature version,
label policy version, exact approved feature ordering, tenant scope, and required
artifact metadata. It does not substitute another horizon, raw probabilities,
rule scores, or logistic scores when a calibrated pair is unavailable.

The result diagnostics keep these separate:

- raw uncalibrated LightGBM probabilities;
- independently calibrated probabilities;
- original calibrated horizon values;
- coherence-adjusted final values; and
- whether cumulative-max adjustment changed any value.

Only the final coherent calibrated values populate `p_churn_7d`,
`p_churn_14d`, and `p_churn_30d`. The canonical uncertainty remains exactly:

```json
{"status": "not_quantified", "method": "none", "intervals": null}
```

## SHAP mapping proposal

The pipeline calls `LightGBMExplainer` with the exact model and feature snapshot
used for each horizon. Each result retains the raw-margin/log-odds output space,
full contributions, additivity audit, versions, cutoff, identity, and
limitations. SHAP does not explain calibrated or coherence-adjusted
probabilities and is not causal evidence.

For the current additive `PredictionOutput.explanations_by_horizon` field, the
pipeline proposes one serialized `ExplanationResult` object in a list under
each string horizon key (`"7"`, `"14"`, and `"30"`). An unavailable explanation
is retained as an explicit unavailable result with reason codes; it is never
replaced by hardcoded feature descriptions. The exact shared persistence shape,
privacy/retention policy, and whether Member 3 may display raw contributions
remain unresolved team decisions.

Explanation failure is non-blocking for a valid scored result under the current
policy, but it is visible in `PipelineResult.reason_codes`, diagnostics, and
the horizon payload. A future strict policy could make it blocking without
changing model or prediction semantics.

## Synthetic versus production readiness

The repository has no authorized longitudinal dataset. Current model and
calibrator fixtures carry synthetic provenance and `DatasetStatus.BLOCKED`.

`PipelineExecutionMode.SYNTHETIC_TEST_ONLY` may execute the complete
mathematical path only when every artifact has explicit synthetic provenance,
consistent metadata, blocked dataset status, and blocked empirical validation.
The resulting `PipelineResult` is marked `synthetic_test_only=true` and
`deployable=false`; it is not a production customer record.

Production mode requires structurally compatible artifacts, real non-synthetic
provenance, `DatasetStatus.PASS` training evidence, PASS empirical calibration
validation, and the existing complete three-horizon readiness gate. With the
current repository evidence, production mode remains `model_bundle_not_ready`.
A caller flag cannot turn blocked or unknown artifact provenance into production
readiness.

## Member 1 integration mapping

Member 1 must connect the replaceable `PointInTimeDataAdapter` to canonical
tenant-authorized storage and provide:

- historical subscription lifecycle facts and account identity;
- usage and billing facts with occurrence/effective timestamps;
- source availability or `received_at` evidence and correction semantics;
- usage coverage/completeness evidence;
- source watermarks and freshness evidence;
- agreed account-level multi-subscription churn policy; and
- authorized real dataset provenance and model artifact registry metadata.

Authentication and authorization remain backend responsibilities. This module
does not trust a client tenant ID as authorization proof and does not persist
any records.

## Handoffs

Member 3 can consume only the canonical prediction snapshot and its explicit
reliability/freshness/SHAP limitations. SHAP associations must not become action
recommendations or causal claims.

Member 4 can consume `prediction_id`, `prediction_run_id`, versions, readiness
diagnostics, per-horizon explanation status, and future mature outcome linkage.
Synthetic results must remain excluded from business-facing feedback,
evaluation, promotion, and dashboard records.

## Open questions and blockers

- No authorized longitudinal dataset exists, so production scoring is blocked.
- The final `explanations_by_horizon` persistence/display schema is not yet a
  shared team decision.
- Member 1 must finalize availability precedence, source correction handling,
  watermarks, and account-level multi-subscription semantics.
- Production model registry identity, artifact approval, and calibration/
  coherence release gates remain outside this module.
- No empirical calibration, coherence, predictive, retention, or ROI claim is
  made by the synthetic tests.
