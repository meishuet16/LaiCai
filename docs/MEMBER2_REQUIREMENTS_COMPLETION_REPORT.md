# Member 2 — Prediction Engine Requirements Completion Report

**Assessment date:** 2026-10-11
**Branch:** `integration/member2-main-sqlite`
**Canonical sources:** `RetainIQ_v2_Complete_Requirements.md` and
`docs/RetainIQ_v2_Part2_Prediction_Engine_Requirements.md`
**Evidence classification:** implementation/tests are repository evidence;
the available STANDARD dataset and previously reported metrics are synthetic
and tenant-01 scoped. This report does not claim real-world validation.

## Executive status

Most Part 2 code paths are implemented and covered by unit/integration tests:
point-in-time features, lifecycle labels, chronological splits, rule/logistic
baselines, LightGBM candidate fitting, calibration/coherence, model-backed
explanation interfaces, reliability/freshness, evaluation, governance gates,
and now batch/event/replay orchestration around the canonical pipeline.

**The end-to-end prediction engine is not production-ready.** There is no
authorized real longitudinal dataset or deployable calibrated 7/14/30 bundle.
The local synthetic STANDARD evidence is tenant-01 only. Seven-day model and
calibration support fail; the synthetic 14/30-day comparisons are weak and do
not support using their raw demo scores as forecasts. Member 1 also needs to
expose authenticated prediction lookup/history for idempotent persistence and
replay. Until those gates are resolved, production should remain
`MODEL_BUNDLE_NOT_READY` (or the existing safe abstention/non-predictive
statuses).

No TEST or CALIBRATION outcome rows were opened in this task. No training,
calibration fit, threshold selection, or model evaluation was performed for
this task.

## Traceability matrix

Status meanings: **Implemented** = implementation and tests exist;
**Partial** = code exists but an integration/evidence gate remains;
**Blocked** = acceptance requires data, policy, or runtime evidence not
available here. A test pass is structural evidence, not proof of predictive
skill.

### Part 2 specification

| Requirement | Implementation and evidence | Status |
|---|---|---|
| §2 prediction unit, cutoff, eligibility and cancellation | Account-level tenant-scoped contracts; point-in-time adapter and eligibility state machine; known cancellation is non-predictive; payment failure is not churn. Tests cover late availability, scope and lifecycle edge cases. | Implemented in code; source-policy details still depend on Member 1. |
| §3 data inputs and dataset gate | SQLite adapter calls authenticated Member 1 APIs; provenance/readiness checks and preparation manifests exist. Local source is synthetic STANDARD, tenant-01. | Partial; no authorized real dataset. |
| §4.1 point-in-time features | Usage, coverage/missingness, feature versions and personalized historical baseline features are implemented and tested. | Implemented; source coverage/baseline-policy reconciliation remains open. |
| §4.2 7/14/30 labels | Versioned positive/negative/unknown/excluded labels, evidence availability, censoring and effective-account churn semantics are implemented. | Implemented for supported documented policies; real account-level multi-subscription policy remains unresolved. |
| §4.3 rule/logistic/LightGBM | Rule and logistic baselines, LightGBM models and candidate trainer are implemented; same-split comparison/diagnostics exist. | Partial; evidence is synthetic and predictive value is weak. |
| §4.4 calibration and cumulative coherence | Horizon calibrators, bundle readiness checks, monotonic correction and post-correction diagnostics are implemented/tested. | Partial; frozen synthetic calibration gates fail, so no deployable calibrated bundle. |
| §4.5 model-backed horizon explanations | SHAP-backed explainer, signed feature contributions and safe unavailable states exist; persisted field is the canonical per-horizon explanation map. | Partial; no ready production bundle/explanation run. |
| §4.6 reliability/freshness | Reason-coded reliability and freshness assessments, abstention and status mapping exist. | Partial; source heartbeat/coverage quality and held-out subgroup validation are not established. |
| §4.7 daily batch, event refresh, risk evolution and policy | New `operational_inference.py` composes daily eligible-account scoring, availability-gated event triggers, historical risk changes, versioned threshold/trend/reliability/freshness/cooldown/budget decisions, and chronological replay. Structural tests added. | Partial; no scheduler, durable event deduplication, persisted alert decisions or live model bundle. |
| §5 temporal splits and evaluation | TRAIN/VALIDATION/CALIBRATION/TEST assignments, maturity controls and evaluator metrics/ranking/lead-time interfaces are implemented. Prompt 32 diagnostics used TRAIN/VALIDATION only. | Partial; TEST remains sealed and is not reported as a result. |
| §6 replay demo | New replay runner uses the same point-in-time inference path and persisted outputs, without accepting outcomes. | Partial; no available deployable bundle and no Part 1 Push API replay integration. |
| §7 canonical output | Existing `PredictionOutput` preserves flat p7/p14/p30, both IDs, versions, reliability/freshness/uncertainty and explanations; persistence mapping uses authenticated principal for tenant. | Implemented; Member 1 reader/history API is missing. |
| §8 implementation deliverables | Feature/label/train/calibrate/explain/reliability/evaluate/predict modules exist; report and provenance docs exist. | Partial at integrated-runtime/data gates. |
| §9 acceptance criteria | See rows above and integrated matrix below. | Not fully accepted while production/data gates are blocked. |

### Unified requirements and cross-part gates

| Canonical requirement | Member 2 implementation/evidence | Status |
|---|---|---|
| §4.3 canonical prediction contract | `contracts.py` flat, validated, versioned schema; DB writer mapping and tests preserve stable per-snapshot `prediction_id` distinct from `prediction_run_id`. | Implemented. |
| §6.1 calibrated multi-horizon forecast | 7/14/30 pipeline and calibrated bundle contract exist. Available local artifact is not a production-ready bundle. | Partial / production blocked. |
| §6.2 as-of features and missingness | Historical availability, usage coverage, personalization and leakage regression tests. | Implemented in code; data-source coverage is a remaining limit. |
| §6.3 labels, maturity and chronology | Label builder and temporal split maturity enforcement. | Implemented in code; no new data prepared in this task. |
| §6.4 baselines and candidate model | Rule/logistic/LightGBM training and comparison. | Implemented; useful performance not demonstrated. |
| §6.5 calibration and monotonic cumulative probabilities | Calibration and coherence modules/tests. | Implemented; availability gate fails for the local synthetic bundle. |
| §6.6 explanations and early warning | Actual explainer interface; new persisted-history comparison and versioned alert-policy evaluator. | Partial; alert thresholds are configured, not empirically selected in this task. |
| §6.7 evidence quality and abstention | Reliability/freshness enums, reason codes, abstention gates; uncertainty stays `not_quantified`. | Implemented; thresholds require owner/data validation. |
| §6.8 predictive value | Evaluation/diagnostic code computes appropriate metrics when data permits. Existing Prompt 32 synthetic VALIDATION report documents weak comparisons and a personalization ablation. | Partial; no authorized real TEST results. |
| §6.9 acceptance tests | Existing Part 2 tests plus new operational tests cover important scope, maturity, persistence, idempotency, availability and replay behavior. | Implemented structurally; cannot satisfy empirical acceptance. |
| §10.1 single dataset family and frozen test | Immutable synthetic dataset provenance, chronological artifacts and gates exist; test partition was not opened for this task. | Partial; no approved real source. |
| §10.2 metrics by layer | Historical evaluator and Prompt 32 development report include AP/ROC/Brier, ranking/alert and ablation capability/evidence. No new metrics calculated. | Partial; no final TEST evaluation. |
| §10.3 claims/data hygiene | Docs and pipeline clearly mark synthetic-only, uncalibrated and not-ready states; no generated score/performance claims added. | Implemented. |
| §16 predictive validity and tenant correctness | Tenant-scoped adapter, contract and leakage tests; no data or model claim expanded. | Partial at real-data gate. |
| §16 decision/feedback/dashboard gates | Outside Part 2 ownership. This work adds no Decision Engine or dashboard behavior. | Handoff only; no scope expansion. |

## Operational integration added in this task

- `DailyPredictionBatch` obtains eligible accounts from a fixed tenant-scoped
  source, includes silent accounts returned by that eligibility query, passes
  source coverage/freshness into `PredictionPipeline`, and records explicit
  per-account outcomes.
- `DataFoundationPredictionSnapshotStore` maps the canonical flat prediction
  fields to Member 1's append-only `store_prediction` writer. It requires a
  tenant-authorized read callback before writing; it performs no direct SQL.
- Event triggers require both event occurrence and availability by `as_of`.
  Event identity reuse with different content is rejected; exact retries are
  suppressed in-process.
- Alert policy is versioned and applies p30 threshold, reliability, freshness,
  comparable/rising risk, cooldown and period budget. It produces internal
  risk-alert decisions only; it does not contact customers or replace Part 3.
- Replay requires strictly chronological aware cutoffs and has no future-label
  input. Risk evolution is computed only from persisted predictions and is
  explicitly not a future-risk curve.

The app/job owner still needs to schedule daily runs, provide durable event
idempotency and alert-decision persistence, and wire the Member 1 read/history
API. Member 1 currently exposes the prediction writer but not the authenticated
lookup/history callbacks required by the adapter.

## Evidence and readiness

- Dataset provenance: synthetic SaaS STANDARD v1.2, seed 2026, tenant-01;
  dataset ID `synthetic-saas-v1-2-standard-s2026-970a9d231e68`; source manifest
  SHA-256 `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- No dataset was regenerated/imported and no private customer-level files were
  added to Git in this task.
- The repository's existing frozen evidence has no supported 7-day fit and
  insufficient calibration support across horizons. The 14/30 synthetic
  validation metrics in `docs/MEMBER2_FINAL_ACCEPTANCE_REPORT.md` are weak;
  LightGBM does not beat the constant-prevalence Brier reference at either
  trained horizon. No scores from those demo artifacts may be served as
  calibrated probabilities.
- No new model fitting, calibration, threshold selection or performance
  evaluation occurred for this task. No TEST/CALIBRATION outcome rows were
  opened.
- Production readiness: **BLOCKED**. Demo scoring readiness is also **not
  established** as a complete 7/14/30 calibrated bundle; structural synthetic
  tests are not predictive evidence.

## Verification

The new focused module uses explicitly synthetic fixtures. The current change
passed 487 repository tests (0 failed, 0 errors, 0 skipped) with 24 existing,
unsuppressed SHAP output-shape warnings. The focused integration selection
passed 111 tests with 15 of those warnings. Repository-local package imports,
AST parsing of changed Python files, and `git diff --check` passed. Exact
commands are in the newest `TEAM_LOG.md` entry. These results are structural
verification and must not be interpreted as real-world performance evidence.

## Remaining actions

1. Member 1: expose tenant-authorized prediction lookup and bounded history
   reads; confirm append-only idempotency and prediction correction semantics.
2. Data owner: provide an authorized representative longitudinal dataset and
   source-coverage/availability evidence; reconcile account-level
   multi-subscription churn policy and historical availability precedence.
3. Member 2: after the data gate, prepare/freeze appropriate stages, establish
   adequately supported 7/14/30 models and calibration, select any alert policy
   only on development data, then request independent TEST evaluation.
4. App/job owner and Members 3/4: wire durable scheduling/event deduplication,
   alert audit storage, canonical prediction reads and safe `MODEL_BUNDLE_NOT_READY`
   handling. Part 3 remains owner of human review prioritization/actions.
