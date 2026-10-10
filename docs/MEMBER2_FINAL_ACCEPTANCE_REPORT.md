# Member 2 — Final Prediction Engine Acceptance Report

**Prompt:** 32 — final audit, diagnostics, baseline comparison and stress tests
**Branch:** `integration/member2-main-sqlite`
**Evidence:** synthetic-only STANDARD v1.2, tenant-01, TRAIN and VALIDATION only
**Production forecast readiness:** **BLOCKED**

## A. Executive readiness summary

| Readiness dimension | Decision | Evidence |
|---|---|---|
| Engineering readiness | **PARTIAL** | Point-in-time/tenant/contract safeguards and saved-model inference have passing evidence; no complete calibrated three-horizon bundle or production scoring endpoint exists. |
| Development model readiness | **BLOCKED** | Only 14d and 30d uncalibrated development models exist. Their validation discrimination is weak; both underperform a constant TRAIN-prevalence reference on Brier score. |
| Synthetic demo readiness | **PARTIAL** | The two models can be loaded and run through a private, clearly demo-only path. The 7d horizon is absent, the scores are raw/uncalibrated, and they must not be represented as canonical forecasts. |
| Independent evaluation readiness | **NOT RUN** | `INDEPENDENT_HELD_OUT_TEST_NOT_RUN`. TEST row/outcome artifacts were not accessed; VALIDATION is already development evidence. |
| Production forecast readiness | **NO / BLOCKED** | No calibrated 7/14/30 bundle, no adequate calibration support, synthetic-only evidence, weak validation results and source-coverage limitations. |

All findings below are engineering or synthetic-development evidence. They do not establish real-world churn performance, retention impact, causal uplift, saved revenue or ROI.

## B. Improvement audit

| Area | Status | Evidence and remaining issue |
|---|---|---|
| Customer-relative features | `IMPLEMENTED_AND_VERIFIED` | `src/retainiq_prediction/feature_builder.py`; baseline/deviation/ratio, variability, inactivity, cold-start, zero-baseline and missing-history tests in `tests/test_feature_builder.py`. The fitted 14d/30d models include the seven baseline-derived columns. |
| Baseline window policy | `PARTIALLY_IMPLEMENTED` | The feature builder uses a four-week baseline immediately before the recent 7-day window, `[t-35d,t-7d)`. This avoids the recent 7d window but overlaps `sessions_prev_30d` on `[t-30d,t-7d)`. The synthetic handoff describes `[t-58d,t-30d)` instead. Reconcile with the owners before treating these windows as a settled shared policy. |
| Separate horizon labels/models | `IMPLEMENTED_AND_VERIFIED` for labels and 14d/30d; `BLOCKED_BY_DATA` for 7d | Existing label and candidate-training modules/tests preserve positive, mature-negative and unknown labels and frozen support gates. 14d/30d were fit independently; 7d did not pass its frozen positive support gate and was not fit. |
| Cumulative 7/14/30 output | `BLOCKED_BY_DATA` | No full three-horizon calibrated output was created. Do not synthesize p7 or post-process raw scores into a purported calibrated cumulative contract. |
| Reliability/freshness/abstention | `IMPLEMENTED_NOT_EMPIRICALLY_VALIDATED` | `src/retainiq_prediction/reliability.py`, `data_freshness.py`, `prediction_pipeline.py` and their tests cover statuses, reason codes, unknown source health, cancellation and null-probability abstention. Prompt 24 stored assessments predate the unknown-connectivity correction; this audit did not treat those stored aggregate statuses as current source-health evidence. |
| Explainability | `IMPLEMENTED_AND_VERIFIED` on available models | Actual saved-model TreeSHAP probes returned 12 named contributions per model, finite values, signed-direction consistency and additivity error below `1e-5`. Output is raw LightGBM margin/log-odds, not causal evidence. SHAP’s output-shape warning was left visible and reviewed. |
| Operational prediction | `PARTIALLY_IMPLEMENTED` | `PredictionPipeline.run(PredictionRequest)` returns internal `MODEL_BUNDLE_NOT_READY` with no prediction when required models/calibrators are absent. No production API, persisted predictions, or complete daily scoring service was verified. The bounded batch below is model-only experimental inference. |

### Diagnostic conclusion

The observed weak discrimination is not explained by a verified score reversal or row-order join defect. Label `1` means confirmed effective account churn; the loaded estimators expose classes `[0, 1]`; the selected probability column is class 1; saved outputs reproduce after reload and align by `(snapshot_id, horizon)` rather than row position. Feature schemas match and omit identity fields.

The available validation signal is sparse: 14d has 54 positive labels across 30 accounts and 30d has 113 across 33 accounts, repeated across cutoff snapshots. These are not independent customer counts, so row-level metrics are statistically fragile. Baseline-derived features have roughly 20 percentage points more missingness in TRAIN than VALIDATION. `valid_usage_history` is constant false across the audited mature samples, and every prepared usage snapshot has partial coverage. The observed dataset may therefore be a weak/shifted feature substrate.

The dataset documentation describes behavioral proxies and unusually predictive billing outcomes in the simulation, while the fitted feature allowlist contains usage features only; omission of billing signal is a plausible explanation, not a proven cause. The underlying generator mechanism was not independently inspected. No data generator, frozen labels, or fitted Prompt 31 model was changed or retrained.

The only implementation fix in this audit is defensive in-memory adapter handling: exact duplicate source facts are counted once; conflicting facts that reuse a scoped source identity fail closed. This does not modify the prepared dataset or Prompt 31 model artifacts.

## C. Evaluation integrity and model diagnostics

TRAIN and VALIDATION counts below preserve unknown labels in the snapshot denominator. “Mature” means only positive/negative rows used in the corresponding horizon model. Metrics use mature VALIDATION labels only.

| Horizon | TRAIN snapshots; eligible accounts | TRAIN positive / negative / unknown | VALIDATION snapshots; eligible accounts | VALIDATION positive / negative / unknown | Mature validation rows; unique positive accounts |
|---|---:|---:|---:|---:|---:|
| 14d | 7,157; 324 | 55 / 6,014 / 1,088 | 5,859; 435 | 54 / 4,775 / 1,030 | 4,829; 30 |
| 30d | 7,157; 324 | 131 / 5,297 / 1,729 | 5,859; 435 | 113 / 4,084 / 1,662 | 4,197; 33 |

TRAIN and VALIDATION share 292 accounts. TRAIN has 6,833 repeated snapshots; VALIDATION has 5,424. VALIDATION also has 435 unique accounts and 33 unique positive accounts at most for 30d; it is a time-forward existing-account evaluation, not a cold-start/unseen-account test. Prepared feature cohorts are eligible snapshots; there were no known-cancellation/not-eligible rows in those exported feature cohorts. The upstream all-cutoff preparation had separate exclusion counts, documented in the Prompt 24 preparation report.

| Horizon | Candidate validation AP (PR-AUC) | Validation prevalence / PR reference | ROC-AUC | Candidate Brier | Constant TRAIN-prevalence Brier | Candidate minus constant Brier |
|---|---:|---:|---:|---:|---:|---:|
| 14d | 0.011252 | 0.011182 | 0.430971 | 0.011158 | 0.011062 | +0.000096 |
| 30d | 0.025993 | 0.026924 | 0.498498 | 0.026834 | 0.026207 | +0.000627 |

Average precision is approximately the validation positive prevalence for both horizons, and ROC-AUC is below chance for 14d and approximately chance for 30d. The constant baseline's Brier score is lower (better) at both horizons. Low Brier values here mostly reflect rare positives and do not establish model quality.

Feature diagnostics: the 12-column train/validation schemas match; one observed feature is constant (`valid_usage_history=False`); no feature is more than 50% missing in mature rows. Personal-baseline field missingness is approximately 45.7–48.0% in 14d TRAIN versus 25.3–27.8% in VALIDATION; for 30d it is 41.3–43.8% versus 20.8–23.3%. This roughly 20-point shift is material. `sessions_prev_7d` is missing about 29–34%; days-since-last-activity is missing about 2–4%. Missingness was not imputed as customer inactivity.

Both reloaded artifact digests, feature order, positive class and saved prediction rows were verified. Saved scores matched by snapshot/horizon; no row-order join was used. SHAP probes were available for both models; additivity errors were approximately `2.66e-15` (14d) and `1.33e-15` (30d). The two unsuppressed LightGBM/SHAP output-shape warnings were reviewed; contribution normalization, names, direction and additivity checks succeeded.

## D. Fair baseline comparison

The paired comparison uses only rows scoreable by the existing inactivity/usage rule, then evaluates every method on exactly that shared population and mature-label set. Rule coverage is 97.76% for 14d and 98.00% for 30d. There is no point-in-time billing-failure input in these prepared model snapshots, so the rule comparator is an inactivity/usage ranking only. It returns a ranking score, not a probability; rule Brier is therefore N/A.

| Horizon | Method | N (positive) | Prevalence | AP / PR-AUC | ROC-AUC | Brier | Provenance / calibration |
|---|---|---:|---:|---:|---:|---:|---|
| 14d | Usage inactivity/decline rule | 4,721 (54) | 1.144% | 0.011704 | 0.506446 | N/A — ranking only | Existing rule; no calibration |
| 14d | Logistic regression | 4,721 (54) | 1.144% | 0.008521 | 0.365575 | 0.011428 | TRAIN-only preprocessing/fit; uncalibrated |
| 14d | LightGBM | 4,721 (54) | 1.144% | 0.011263 | 0.418629 | 0.011413 | Prompt 31 synthetic model; uncalibrated |
| 14d | Constant TRAIN prevalence | 4,721 (54) | 1.144% | 0.011438 | 0.500000 | 0.011313 | Reference score is TRAIN prevalence; not calibrated model |
| 30d | Usage inactivity/decline rule | 4,113 (113) | 2.747% | 0.027664 | 0.486591 | N/A — ranking only | Existing rule; no calibration |
| 30d | Logistic regression | 4,113 (113) | 2.747% | 0.021416 | 0.390252 | 0.027073 | TRAIN-only preprocessing/fit; uncalibrated |
| 30d | LightGBM | 4,113 (113) | 2.747% | 0.026723 | 0.502598 | 0.027367 | Prompt 31 synthetic model; uncalibrated |
| 30d | Constant TRAIN prevalence | 4,113 (113) | 2.747% | 0.027474 | 0.500000 | 0.026730 | Reference score is TRAIN prevalence; not calibrated model |

LightGBM does **not** outperform the simpler comparators overall: rule AP is slightly higher at both horizons; at 14d the rule also has higher ROC-AUC, and at 30d LightGBM ROC-AUC is only marginally above chance. The constant TRAIN-prevalence score has higher paired AP and better Brier at both horizons. These are small, rare-event synthetic development cohorts, not grounds for a model selection claim.

## E. Personalization ablation

A same-seed, same-fixed-hyperparameter LightGBM ablation used the same TRAIN rows and full mature VALIDATION population, removing the seven customer-relative columns while retaining recent-window, history-length and validity fields.

| Horizon | Model | N | AP / PR-AUC | ROC-AUC | Brier |
|---|---|---:|---:|---:|---:|
| 14d | With personalized baseline | 4,829 | 0.011252 | 0.430971 | 0.011158 |
| 14d | Without personalized baseline | 4,829 | 0.014537 | 0.476837 | 0.011078 |
| 30d | With personalized baseline | 4,197 | 0.025993 | 0.498498 | 0.026834 |
| 30d | Without personalized baseline | 4,197 | 0.031521 | 0.487579 | 0.026283 |

Removing the personalized features improved AP and Brier at both horizons on this synthetic validation slice; ROC-AUC improved at 14d and fell slightly at 30d. Subgroups by baseline availability have small positive counts and mixed directions. This does not prove personalization is harmful or beneficial generally; the backlog ablation on an authorized longitudinal dataset remains pending. No claim of personalization lift is made.

## F. Stress test matrix

“PASS” below means the scoped synthetic/unit or existing integration check passed; it is not a production-scale guarantee. The consolidated focused test run initially had one test-only floating-point exact-equality failure; after changing that assertion to approximate comparison, the affected five-test module passed. Other initially passing tests were not rerun. Details are in Section L / the team log.

| Stress case | Expected | Actual result | Status and evidence |
|---|---|---|---|
| Missing/sparse usage | Preserve missingness; conservative evidence; no fabricated zero | Missing coverage remains distinct from observed zero; reliability tests reject treating incomplete coverage as confirmed inactivity | PASS — `tests/test_feature_builder.py`, `tests/test_reliability.py` |
| Duplicates, large outlier, irregular use | Deduplicate or fail closed; deterministic finite behavior | Exact duplicate facts counted once; conflicting same-source identity rejected; billion-unit synthetic quantity deterministic; isolated raw model score finite/bounded. A broad irregular-event distribution sweep was not run. | PARTIAL — `tests/test_point_in_time.py`, `tests/test_feature_builder.py`, aggregate outlier probe |
| Cold start / zero history | No divide-by-zero or false personal baseline | Zero baseline protected; cold start and missing-history states explicit | PASS — `tests/test_feature_builder.py`, `tests/test_reliability.py` |
| Silent accounts | Consider eligible silence; distinguish silence from source outage | Confirmed zero usage with healthy coverage and event silence with unknown connectivity have separate paths | PASS — `tests/test_feature_builder.py`, `tests/test_data_freshness.py`, `tests/test_reliability.py` |
| Source freshness | Fresh/partial/stale/unknown remain distinct; unknown is not disconnection | Status and abstention policy cases are tested. Stored Prompt 24 aggregate metadata is stale by version and was not presented as a fresh reassessment. | PARTIAL — `tests/test_data_freshness.py`, `tests/test_reliability.py` |
| Future/late data leakage | Exclude facts unavailable at cutoff; preserve later label availability | Future and late facts are excluded; future cancellation does not alter earlier eligibility; label maturity remains separate from features | PASS — `tests/test_point_in_time.py`, `tests/test_feature_builder.py`, `tests/test_label_builder.py`, `tests/test_prediction_pipeline.py` |
| Multi-horizon consistency | Canonical scored output only with all supported calibrated horizons | 7d unavailable; no synthetic p7 or fake cumulative output; missing model/calibrator returns not-ready/null prediction | BLOCKED for scored 3-horizon output; safety PASS — `tests/test_prediction_pipeline.py`, `tests/test_reliability.py` |
| Tenant isolation | No cross-tenant feature/label/prediction leakage | In-memory scoping and pipeline rejection covered; prior authenticated pilot used approved tenant-scoped reader and logged no secrets | PASS for tested boundaries — `tests/test_point_in_time.py`, `tests/test_prediction_pipeline.py`; authenticated evidence from Prompt 29 |
| Model persistence | Same artifact/features produce same scores and feature order | Both private model digests verified; reload score vectors reproduced and matched saved validation rows by snapshot/horizon | PASS — actual diagnostic run; `tests/test_lightgbm_model.py` historical/focused evidence |
| Bounded batch inference | Report row count, failures and model-only time | 9,026 raw scores, zero failed rows: 4,829 14d in 2.4732s (~1,952.6 rows/s), 4,197 30d in 3.9671s (~1,058.0 rows/s). This excludes data extraction and feature building. 7d had no model. | PASS — actual diagnostic run; not production throughput |
| Severe imbalance / one class | No crash; undefined rank metrics explicit | Constant baseline reports prevalence; AP/ROC are undefined for single-class fixtures; probability metrics reject out-of-range values | PASS — `tests/test_member2_prompt32_diagnostics.py` |
| Downstream safety | Raw outputs never become canonical production forecasts | Pipeline preserves `MODEL_BUNDLE_NOT_READY`, no p7, no raw fallback; canonical abstentions retain null probabilities | PASS — `tests/test_prediction_pipeline.py`, `tests/test_reliability.py`, existing handoff docs |

## G. Data splits and held-out evaluation

- **TRAIN:** 7,157 snapshots, 324 accounts; used for the Prompt 31 14d/30d fits and the diagnostic logistic/ablation fits.
- **VALIDATION:** 5,859 candidate snapshots; 4,829 mature 14d labels and 4,197 mature 30d labels. Used for development diagnostics and comparison, so it is not final test evidence.
- **CALIBRATION:** not read for this audit; no calibrator was fit. Frozen support is insufficient (prior approved aggregate: 7d 13 positive rows/13 accounts, 14d 27/14, 30d 59/17; the 30d case also misses the 20-positive-account minimum).
- **UNTOUCHED TEST:** no TEST rows or outcomes opened, queried or used. `INDEPENDENT_HELD_OUT_TEST_NOT_RUN`: no separate explicit authorization was provided, calibration/full-horizon readiness is blocked, and model choices were already examined on VALIDATION.

The TRAIN/VALIDATION boundaries and prepared split remain frozen; no split files were changed. The experiment is synthetic-only and repeated-account evaluation does not establish new-customer generalization.

## H. Business evaluation and calibration

Recall@K, precision@K, false-alert workload and missed-case counts are **NOT AVAILABLE**: no owner-approved review capacity `K`, alert-period rule or repeated-account deduplication policy was supplied. Choosing one after inspecting VALIDATION would be post-hoc threshold selection. Early warning lead time is **NOT AVAILABLE** because no qualifying historical repeated model-generated score series with an approved alert threshold was produced. A 30-day label horizon is not evidence of 30-day warning lead time.

Calibration was not run. The frozen CALIBRATION support gate fails for every horizon, and 7d is absent. Raw classifier outputs remain uncalibrated experimental scores; no calibrated probability or canonical `scored` PredictionOutput is available.

## I. Member 3/4 integration handoff

- Production consumers should use the existing pipeline’s safe `MODEL_BUNDLE_NOT_READY` state and no prediction payload; do not create a new `PredictionOutput.status` for model unavailability.
- Preserve existing `abstained`, `known_cancellation` and `not_eligible` contract semantics and null probabilities. A `scored` prediction requires all three calibrated cumulative horizon probabilities and the established evidence gates.
- Private experimental models exist only for 14d and 30d. Their model versions are `synthetic_demo_only_standard_tenant01_lightgbm_v1_14d` and `synthetic_demo_only_standard_tenant01_lightgbm_v1_30d`; feature version is `features_personalized_baseline_v1`. They are uncalibrated and synthetic-demo-only. Do not use them for financial prioritization, production risk, retraining feedback or ROI claims.
- The Prompt 31 training report documents the existing demo runner. The Prompt 32 diagnostic command, which reads TRAIN/VALIDATION and writes aggregate-only output outside Git, was:

  ```powershell
  & .\.venv\Scripts\python.exe -B -m examples.member2_prompt32_diagnostics `
    --prepared-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v4' `
    --prompt31-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\experiments\prompt31-standard-tenant01-demo-v1' `
    --output-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\experiments\prompt32-diagnostics-v3'
  ```

- Aggregate diagnostics are outside Git at `...prompt32-diagnostics-v3\aggregate_diagnostics.json`, SHA-256 `7fda46f721f0380aecf3def2d4fa7a4d22de53c9748864f78fdf738b31b65246`. No private model, customer-level score, attribution, database or credential is included in this repository.

## J. Known limitations

- Training/evaluation evidence is synthetic-only and tenant-01 only.
- 7d was not trained; all-horizon calibrated output is unavailable.
- Calibration is unsupported by frozen sample/account gates.
- 14d/30d validation discrimination is weak and positive cases are sparse/repeated by account.
- Both LightGBM Brier scores are worse than the TRAIN-prevalence constant reference.
- Personalized baseline features did not improve these synthetic validation metrics; missingness differs materially between TRAIN and VALIDATION.
- The usage-window definition differs between synthetic handoff and current feature implementation and needs team reconciliation.
- Prompt 24 stored reliability/freshness aggregates predate the unknown-connectivity correction; comprehensive current aggregate source-health reassessment is not available from this run.
- No independent TEST evaluation, business Recall@K, approved alert threshold, or lead-time evidence.
- No causal evidence that any intervention retains customers; no real-world retention, savings, or ROI claim.
- No production endpoint or persisted production prediction run was verified.

## K. Final verdict

| Classification | Result | Reason |
|---|---|---|
| `ENGINEERING_READY` | **PARTIAL** | Core isolated components and safety tests work; integration bundle, source-health evidence and production scoring operations remain incomplete. |
| `SYNTHETIC_DEMO_READY` | **YES, restricted** | Private 14d/30d raw model demos can be reproduced. They must be explicitly labeled synthetic, uncalibrated, validation-only and non-production; 7d is absent. |
| `OFFLINE_PREDICTIVE_VALUE_DEMONSTRATED` | **NO** | AP is at/below simple prevalence/rule references, ROC is weak, and LightGBM Brier is worse than the constant reference. No meaningful predictive advantage is established. |
| `PRODUCTION_MODEL_READY` | **NO** | Missing 7d and calibration, synthetic-only source, weak development evidence and incomplete operational gates. |

## L. Verification record

The consolidated focused batch covered 23 relevant test modules. Its first run reported **332 passed, 1 failed, 24 warnings** in 14.90s. The sole failure was a new extreme-imbalance test using exact float equality (`0.0009990000000000003` versus `0.000999`), not a model or application failure. The assertion was changed to approximate comparison; the affected file was rerun and reported **5 passed** in 3.54s. The other 332 tests were not rerun, and no complete repository-wide suite was run for Prompt 32. The 24 warnings (15 prediction-pipeline, 9 explainability) were existing LightGBM/SHAP output-shape warnings and were not suppressed. The actual diagnostic SHAP probes and additivity checks passed.

Actual focused rerun command:

```powershell
& .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p32-fix tests\test_member2_prompt32_diagnostics.py
```

The diagnostic command completed successfully; aggregate output runtime was 43.9381s, and its output digest is recorded above. The consolidated test run preceded the correction; the affected test module passed after correction. Package-import/syntax checks and `git diff --check` are recorded in the Prompt 32 `TEAM_LOG.md` entry after execution. Prompt 31’s historical 47-pass result is not claimed as rerun here.

## M. Reproducibility and artifact provenance

- Dataset ID: `synthetic-saas-v1-2-standard-s2026-970a9d231e68`; STANDARD v1.2; synthetic SaaS generator seed 2026/build `r9`; authorized prepared scope tenant-01.
- Source manifest SHA-256: `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- Prompt 24 prepared manifest SHA-256: `1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a`.
- Prompt 31 training manifest SHA-256: `cfbebcbc006f269121aed1fba56d7145af1425b517f2f5fd68c77f291ed6f93d`.
- Prompt 31 model SHA-256: 14d `18aa32de48584192767316772fe68388ed080717322d6571c6861b528a2fa620`; 30d `b5faf7b031814efdaf2755df50fd0d66483aef24d54ac27d166b47e570a40041`.
- Prompt 32 aggregate diagnostics SHA-256: `7fda46f721f0380aecf3def2d4fa7a4d22de53c9748864f78fdf738b31b65246`.
- Prompt 32 diagnostic runtime: 43.9381s, including aggregate diagnostics; batch timings above exclude extraction and feature construction. Runtime is local synthetic engineering evidence, not production throughput.
- Runtime versions recorded by the prior training environment: Python 3.14.4, LightGBM 4.7.0, scikit-learn 1.9.1, NumPy 2.5.3; SHAP probe reported 0.53.0.
