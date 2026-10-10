# Member 2 — Final Prediction Readiness Handoff

## Delivery decision

**Model state: `NOT_READY`; do not emit scored forecasts.** No complete 7/14/30-day candidate was trained, calibrated, evaluated, or written as a model artifact. The frozen tenant-01 development evidence fails the predeclared class-support gates, the dataset is synthetic-only, and the bounded live pilot shows severe evidence/freshness limitations. There are no prediction probabilities or performance metrics to hand off.

The existing integration boundary is the Python entry point `PredictionPipeline.run(PredictionRequest)` in `src/retainiq_prediction/prediction_pipeline.py`. It requires a point-in-time adapter plus horizon models and calibrators. When a complete bundle is not ready, it returns an internal `PipelineResult` with `pipeline_status=MODEL_BUNDLE_NOT_READY` and `prediction=null`. This is an internal pipeline state, **not** a new `PredictionOutput.status`; no HTTP endpoint is implemented here.

## Evidence and training gate

- Evidence is **SYNTHETIC_ONLY**: dataset `synthetic-saas-v1-2-standard-s2026-970a9d231e68`, seed 2026, tenant-01 only. Source manifest SHA-256: `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- The existing prepared artifact is outside Git (`member2-prep-v4`); its manifest SHA-256 is `1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a`.
- The declared stage/horizon gate requires at least 50 positive rows, 50 negative rows, 20 unique positive accounts, and 20 unique negative accounts per stage. CALIBRATION fails for every horizon: 7d has 13 positives / 13 positive accounts; 14d has 27 / 14; 30d has 59 / 17. Thus no complete calibrated three-horizon candidate is ready. TRAIN/VALIDATION also fail the 7d positive-row minimum (27 and 28 positives respectively). These are the dataset's frozen engineering gates, not universal statistical sufficiency claims. TEST outcomes were not queried for this handoff.
- The separate 30-account × three-cutoff authenticated pilot had 90 candidate snapshots; for each horizon it observed 1 positive, 27 negative, 0 unknown, 2 excluded, and 60 unsupported. TRAIN had zero positives in this pilot. This small pilot is not a training cohort or population estimate.
- No model was trained on the STANDARD dataset; no candidate artifact, calibrated probabilities, held-out metrics, or TEST-based selection was produced in Prompt 29/30. Do not use the synthetic evidence as real-world churn validation.

See [the authenticated pilot report](MEMBER2_AUTHENTICATED_STANDARD_PILOT_RESULTS.md) and [the frozen training-readiness decision](MEMBER2_TRAINING_READINESS_DECISION.md) for detailed provenance and limitations.

## Eligibility contract mismatch for Member 1

The aggregate diagnostic over the same label-blind 90 tenant-01 account/cutoff pairs found:

| Member 1 snapshot | Member 2 eligibility | Pairs | Evidence |
|---|---|---:|---|
| `eligible` | `ELIGIBLE` | 28 | Active paying lifecycle facts were available |
| `not_eligible` | `NOT_ELIGIBLE` | 2 | Dated terminal lifecycle evidence was available |
| `not_eligible` | `INSUFFICIENT_DATA` | 60 | No Member 1 subscription projection rows, no Member 2 subscription facts, and no subscription-coverage rows; Member 2 reason `MISSING_SUBSCRIPTION_HISTORY` |

The 60 cases do **not** establish that an account was outside the active paying population at the historical cutoff. The canonical eligibility policy requires evidence for that conclusion; missing history stays `INSUFFICIENT_DATA`. No adapter remapping is safe, and no Member 1 code or source data was changed. Member 1 should distinguish confirmed terminal/nonpaying history from missing or unverifiable historical subscription state in its as-of response (or provide equivalent dated lifecycle/coverage evidence). Until the owners agree, preserve the conservative Member 2 result and treat cross-member eligibility compatibility as **PARTIAL**.

The pilot observed no known-cancellation cases, so that routing path was not empirically exercised in this cohort. The account-level multiple-subscription policy remains scoped to the dataset's explicit synthetic `effective-account-churn-v1.2` rule; it is not a universal real-customer policy.

## Member 3/4 payload and meanings

The canonical `PredictionOutput` in `src/retainiq_prediction/contracts.py` remains unchanged:

- Identity/time: `tenant_id`, `customer_id`, `prediction_id`, `prediction_run_id`, `as_of`, `generated_at`.
- State and forecasts: `status` (`scored`, `abstained`, `known_cancellation`, `not_eligible`), and the exact fields `p_churn_7d`, `p_churn_14d`, `p_churn_30d`. `scored` carries all three calibrated cumulative probabilities; `abstained` carries null probabilities when evidence/reliability gates prevent scoring; `known_cancellation` routes an already-known cancellation nonpredictively; `not_eligible` means evidence confirms the account is outside the active paying population.
- Traceability: `feature_version`, `model_version`, `calibration_version`, `label_policy_version`.
- Evidence: `reliability.status`, `data_freshness.status`, fixed `uncertainty` (`not_quantified` / `none` / `null` intervals), and `explanations_by_horizon` when actual model attributions exist.

`prediction_id` identifies one account/cutoff snapshot and is the downstream feedback/case join key. `prediction_run_id` identifies an inference job and must not replace it.

Reliability values (`sufficient_evidence`, `limited_evidence`, `insufficient_evidence`) describe input applicability/evidence, **not** confidence in a probability. Freshness values are `fresh`, `partially_stale`, `stale`, and `unknown`. Unknown source health remains unknown; missing data is not evidence of disconnection. These statuses and the canonical prediction states are already encoded in the shared contract; this handoff does not add statuses.

**Current use by downstream owners:** the schema and Python pipeline seam are available for contract integration, but there is no production-ready model bundle and no scored payload to rank or learn from. Member 3 must not rank or route on fabricated probabilities; represent model unavailability through the consuming application's existing not-ready path. Member 4 should link any future feedback to `prediction_id`, preserve `as_of` and model/version references, and keep prediction-horizon outcomes separate from post-action follow-up. Synthetic unit-test fixtures in `tests/test_prediction_pipeline.py` and `tests/test_candidate_training.py` demonstrate mechanics only.

## Verification and remaining work

- Prompt 30 focused tests: authenticated pilot structure, eligibility, prediction pipeline, candidate training gates, dataset readiness, and retraining readiness. Result: **65 passed**; 15 existing SHAP/LightGBM output-shape warnings, unsuppressed.
- Package import check: **PASS** for contracts, prediction pipeline, candidate trainer, and eligibility; canonical status enums resolved as documented.
- The preceding Prompt 29 authorized one-account/one-cutoff authenticated API smoke passed its four scoped reads and valuation-redaction checks; this documentation-only handoff did not repeat the API read. The same Prompt 29 record documents the bounded 90-pair integration evidence, integrity checks, and full-suite result (463 passed, no failures/errors/skips, 24 known SHAP warnings).
- `git diff --check` — PASS after the final documentation edits.

**Member 1 unblockers:** resolve missing-versus-terminal historical eligibility semantics; supply reliable dated lifecycle history, outcome coverage and availability/correction fields; define source-health/heartbeat evidence; and agree real account-level multi-subscription churn semantics. Preserve tenant-scoped authenticated access.

**Before any candidate training:** obtain an authorized dataset appropriate to the intended claim; preserve the frozen split and sealed TEST; meet the declared per-stage/per-horizon support gates (especially CALIBRATION); verify mature labels and feature coverage; and reassess reliability/freshness without weakening policy. Synthetic data can support a clearly labeled engineering demonstration only. Operational scoring remains blocked until a complete, calibrated, appropriately authorized bundle and acceptable evidence gates exist.
