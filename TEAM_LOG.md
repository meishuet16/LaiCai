# RetainIQ v2 — Team Development & Commit Log

**Project:** Dormathon 2026 — RetainIQ v2  
**Purpose:** Give every team member a shared, truthful record of what changed in **every Git commit**.  
**Related documents:** `RetainIQ_v2_Complete_Requirements.md`, `AGENT.md`.

> **Team rule — mandatory:** **Every commit that changes project files must include an update to `TEAM_LOG.md` in that same commit.** This includes code, documentation, database migrations, model artifacts/configuration, dashboard work and agent-generated changes. A commit with only a log correction must still explain that correction.

## 1. How every member uses this log

1. Before committing, copy the **Commit Entry Template** below and insert a completed entry at the **top of Section 4**, newest first.
2. Write the date/time in **UTC (ISO 8601)**, actual member name or approved team handle, workstream, branch and intended commit subject.
3. State **what actually changed and why**, naming important files/API/schema contracts. “Fixed bugs” or “updated stuff” is not sufficient.
4. List the **tests/commands run and their real results**; if none, write `Not run` and why. Record any synthetic/demo-only inputs and evidence limitations.
5. Record known bugs/blockers, anything another teammate needs to know, and the next concrete task. Do **not** record secrets, credentials, customer PII or restricted datasets.
6. Stage the modified files **and this log together**. Check `git diff --cached --name-only` includes `TEAM_LOG.md` before `git commit`.
7. Commit. Do **not** require the new commit SHA inside the same commit, because the SHA does not exist until the commit is created. Use timestamp, author, branch and subject to identify the entry. A post-commit link/SHA may be added in a **later logged commit** if useful.
8. If several members edit the log simultaneously, keep all legitimate entries when resolving merge conflicts. Never overwrite someone else's work.

**Definition of a good log entry:** A different teammate can understand the change, run the appropriate verification and know whether any integration contract was affected.

## 2. Recommended commit subjects

Prefer informative messages using these prefixes:

| Prefix | Use for | Example subject (illustrative only) |
|---|---|---|
| `feat:` | New behavior | `feat: add tenant-scoped event ingestion` |
| `fix:` | Defect correction | `fix: exclude pending cancellations at cutoff` |
| `test:` | New/changed tests | `test: cover ROI zero-cost edge case` |
| `docs:` | Documentation | `docs: align prediction payload contract` |
| `refactor:` | Internal change without behavior change | `refactor: share snapshot cutoff validator` |
| `perf:` | Performance | `perf: batch daily feature refresh` |
| `chore:` | Maintenance, dependencies, migrations | `chore: add prediction feedback migration` |
| `revert:` | Revert | `revert: restore last approved model config` |

Examples are **templates, not claims that any of these commits happened**.

## 3. Commit entry template — copy into Section 4 each time

Copy the block below **for each commit** and replace every bracketed placeholder:

```markdown
### YYYY-MM-DDTHH:MM:SSZ — [Member / Handle] — [Short change title]

- **Workstream:** Part [1/2/3/4] / Frontend / QA / Integration / Docs
- **Branch:** `[feature/branch]`
- **Commit subject:** `[type: clear summary]`
- **Issue / task:** `[ticket link or short task reference; N/A if none]`
- **Files changed:** `[specific paths or directories]`
- **What changed:**
  - `[Concrete implementation/change 1]`
  - `[Concrete implementation/change 2]`
- **Why it changed:** `[Problem, requirement, or bug addressed]`
- **Contract / database / API impact:** `[None, or describe fields/endpoints/migration and downstream owners notified]`
- **Tests / verification:**
  - `[command or manual check]` — `[PASS / FAIL / NOT RUN]` — `[details or reason]`
- **Data / model / ROI evidence:** `[Real / synthetic / configured assumption / N/A; actual source if appropriate]`
- **Known issues / blockers:** `[Specific risks, or None known]`
- **Next action / handoff:** `[Concrete follow-up and who owns it]`
- **Reviewer / pairing:** `[optional handle or N/A]`
```

**Small commit?** Keep the headings, use concise content, and put `N/A` where a field truly does not apply. Do not silently delete the test, impact, or blocker fields.

## 4. Commit history — newest first

<!--
Insert the first real commit entry DIRECTLY BELOW this comment, then keep
newer entries above older ones. No Git commits have been assumed or fabricated
in this initial template. When first committed, this documentation change
itself also requires a filled-in commit entry.
-->

### 2026-10-10T20:53:46Z — Member 2 AI coding assistant — Emergency Prompt 34 reduced demo workflow and truthful handoff

- **Workstream:** Part 2 / ML / Integration / QA / Docs
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `feat(member2): add reduced synthetic training workflow`
- **Issue / task:** Member 2 Prompt 34 emergency continuation; no ticket
- **Files changed:** `examples/member2_prompt34_demo.py`, `src/retainiq_prediction/historical_dataset_preparation.py`, `tests/test_member2_prompt34_demo.py`, `docs/MEMBER2_PROMPT34_CALIBRATED_DEMO_REPORT.md`, and this log.
- **What changed:**
  - Added an opt-in reduced preparation workflow that reuses the existing synthetic Prompt 34 source dataset and authenticated SQLite import, selecting 25 fixed weekly cutoffs evenly within the four frozen stages before label reads; class-support thresholds remain unchanged.
  - Added model/calibration/comparison/SHAP/replay orchestration to the Prompt 34 example and changed VALIDATION comparison/coherence diagnostics to raw scores only, avoiding backward application of parameters fitted on the later CALIBRATION stage.
  - Changed replay to write through Member 1's existing prediction writer against a private SQLite copy, preserving the imported source copy for source-event reads; documented the in-memory prediction-history mirror and safe-payload limitations.
  - Added reduced-cutoff structural tests and an emergency report that clearly separates completed source artifacts, incomplete preparation progress, compatibility smoke checks, and unrun Prompt 34 training/evaluation.
- **Why it changed:** The exhaustive 5,000-account × 73-cutoff preparation was stopped at the user's direction. The reduced workflow makes a predeclared lower-cost attempt possible without regenerating/reimporting STANDARD data, using outcome-selected dates, or weakening support gates. The report prevents partial in-memory counts or unrelated prior models from being represented as Prompt 34 results.
- **Contract / database / API impact:** No shared PredictionOutput fields, database schema, migration, or API path changed. Preparation continues through the authenticated Member 1 reader and canonical tenant scope. The successful reduced preparation did not finalize, so no replay database clone or prediction row write was produced. Service-principal provisioning may update local authorization metadata in the imported SQLite file; no event/customer rows were intentionally changed. Member 1 still owns authenticated prediction history/readback and support for full SHAP/reliability-reason payloads.
- **Tests / verification:**
  - `& .\.venv\Scripts\python.exe -B -m py_compile examples\member2_prompt34_demo.py src\retainiq_prediction\historical_dataset_preparation.py tests\test_member2_prompt34_demo.py` — **PASS**.
  - `& .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p34-final tests\test_member2_prompt34_demo.py tests\test_calibration.py tests\test_explainability.py tests\test_prediction_pipeline.py tests\test_operational_inference.py tests\test_historical_evaluation.py` — **PASS** — 79 passed, 0 failed/errors/skipped; 24 existing SHAP output-shape warnings were not suppressed.
  - Prompt 34 focused test module — **PASS** — 9 passed. Repository-local imports — **PASS**. `git diff --check` — **PASS** (Git reported only an LF-to-CRLF conversion warning).
  - Private synthetic-fixture smoke loaded existing Prompt 31 STANDARD 14d/30d LightGBM artifacts, produced raw uncalibrated inference, and passed SHAP additivity (errors `5.329070518200751e-15` and `0.0`). This is artifact compatibility evidence only, not Prompt 34 training or performance evidence.
  - Full repository suite and Prompt 34 end-to-end train/calibrate/TEST/replay — **NOT RUN / BLOCKED** because neither exhaustive nor reduced historical preparation finalized any feature/label artifacts.
- **Data / model / ROI evidence:** Synthetic-only source: `synthetic-saas-v1-2-prompt34_demo-s2034-316bec2deb46`, seed 2034, manifest SHA-256 `75a687071f3fee639e3ce057b59404834accb2fc01ec39a7cb122cb9883e5aac`, one tenant, 5,000 fictional accounts, 363,562 canonical events, and 814,446 coverage records. No Prompt 34 model was trained/calibrated and no held-out metric, replay result, real-world performance, retention, revenue, or ROI claim is made. No private customer-level rows or model artifacts were added to Git.
- **Known issues / blockers:** Full preparation was stopped at 45/73 cutoffs; the predeclared reduced run ended at 7/25 and left zero prepared files. Its termination cause and exit diagnostic were not retained. No Prompt 34 model bundle, calibrators, held-out predictions, SHAP output, or replay exists. Read-after-write history in the replay example is process-mirrored until Member 1 exposes a reader. The local prediction bundle must remain not-ready for production.
- **Next action / handoff:** If further work is authorized, retry from the preserved imported source using a fresh versioned private output root and the reduced cutoff policy; keep all per-horizon support gates unchanged and stop if any stage is insufficient. Member 1: expose authenticated prediction history/readback and clarify writer payload support. Member 2: only fit/calibrate/evaluate after a complete preparation manifest and mature-label support are verified. Members 3/4 must keep `MODEL_BUNDLE_NOT_READY` until real-data, calibration, and operational gates pass.
- **Reviewer / pairing:** N/A

### 2026-10-10T19:21:18Z — Member 2 AI coding assistant — Operational inference and requirements traceability

- **Workstream:** Part 2 / Integration / Docs / QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `feat(member2): complete operational inference integration`
- **Issue / task:** Member 2 Prompt 33; no ticket
- **Files changed:** `src/retainiq_prediction/operational_inference.py`, `src/retainiq_prediction/__init__.py`, `tests/test_operational_inference.py`, `docs/MEMBER2_OPERATIONAL_INFERENCE.md`, `docs/MEMBER2_REQUIREMENTS_COMPLETION_REPORT.md`, and this log.
- **What changed:**
  - Added tenant-bound daily batch orchestration over all accounts returned by the existing eligible-account source (including silent accounts), with per-account evidence/pipeline/persistence states and an append-only adapter over Member 1's existing prediction writer.
  - Added availability- and tenant-gated event triggers, immutable retry/conflict behavior, same-version historical risk changes, configurable reliability/freshness/trend/cooldown/period-budget alert decisions, and chronological replay over persisted outputs.
  - Added 13 synthetic structural tests and documented requirement traceability, the operational integration seam, missing Member 1 read/history APIs, and the production readiness blockers.
- **Why it changed:** Prompt 33 requested the remaining Part 2 operational inference/replay/risk-policy integration plus a complete implementation-vs-evidence matrix, while retaining the canonical output contract and keeping unsupported production states explicit.
- **Contract / database / API impact:** No shared prediction fields, enums, database schema, migration, or API path changed. The adapter uses the existing `store_prediction` writer with tenant identity derived from the authenticated principal and requires an injected authenticated read callback for duplicate-safe writes. Member 1 owns the needed prediction lookup/history APIs; no direct SQL or Member 1 source changes were made. Alert decisions and event idempotency are in-process only and are not substitutes for durable Part 1/app-job storage.
- **Tests / verification:**
  - `& .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p33 tests\test_operational_inference.py tests\test_prediction_pipeline.py tests\test_historical_evaluation.py tests\test_cross_member_integration.py tests\test_data_foundation.py` — **PASS** — 111 passed; 15 unsuppressed SHAP output-shape warnings.
  - `& .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p33-full` — **PASS** — 487 passed, 0 failures, 0 errors, 0 skipped; 24 existing unsuppressed SHAP output-shape warnings.
  - Repository-local public package/module imports — **PASS**; AST syntax parse of all changed Python files — **PASS, 3 files**; `git diff --check` — **PASS**. Staged diff check is also required before commit.
- **Data / model / ROI evidence:** New tests use explicitly synthetic in-memory records only. No data was regenerated/imported, no model was trained/calibrated/evaluated, and no TEST/CALIBRATION outcome files were opened. Existing evidence remains synthetic STANDARD v1.2 tenant-01 only; 7d and calibration gates fail, while 14d/30d validation is weak. No real-world predictive performance, intervention or ROI claim.
- **Known issues / blockers:** No authorized real longitudinal dataset or deployable calibrated 7/14/30 model bundle. Member 1 needs to expose authenticated prediction read/history methods for actual duplicate-safe persistence and replay; deployment needs durable event idempotency, alert-decision persistence, and a scheduler/job retry policy. Full replay through Member 1's historical Push API and any real threshold selection remain undone. The local `MODEL_BUNDLE_NOT_READY` behavior must remain in force.
- **Next action / handoff:** Member 1: expose tenant-scoped prediction lookup/history; data owner: authorize representative longitudinal source and resolve coverage/account-level churn policy; app/job owner: provide durable scheduling, event idempotency and alert audit storage. Member 2 can then pass data/model/calibration readiness gates before any held-out TEST evaluation.
- **Reviewer / pairing:** N/A

### 2026-10-10T19:09:15Z — Member 2 AI coding assistant — Final prediction diagnostics and acceptance audit

- **Workstream:** Part 2 / ML / Integration / Docs / QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `feat(member2): audit prediction quality and harden duplicate facts`
- **Issue / task:** Member 2 Prompt 32; no ticket
- **Files changed:** `examples/member2_prompt32_diagnostics.py`, `src/retainiq_prediction/point_in_time.py`, `tests/test_point_in_time.py`, `tests/test_feature_builder.py`, `tests/test_member2_prompt32_diagnostics.py`, `docs/MEMBER2_FINAL_ACCEPTANCE_REPORT.md`, and this log.
- **What changed:**
  - Added a TRAIN/VALIDATION-only, fail-closed diagnostic runner that verifies frozen artifact identity, saved model digests, feature order, class-1 score direction, snapshot/horizon alignment, model reload reproducibility, paired baseline metrics, personalization ablation, feature missingness, SHAP additivity, bounded outlier inference and batch timing. It writes aggregate-only JSON outside Git.
  - Exact duplicate in-memory source facts are counted once; conflicting facts with the same tenant/customer/source/category/record identity are rejected. Added duplicate/conflict and deterministic large-quantity regression tests, plus imbalance/metric/ablation tests.
  - Published the full acceptance report, including weak development metrics, comparison/ablation evidence, limitations, stress-test outcomes, held-out policy and Member 3/4 safety handoff.
- **Why it changed:** Prompt 32 requires an evidence-based final Part 2 audit and fair development comparisons without opening TEST/CALIBRATION outcomes or presenting synthetic raw scores as production probabilities.
- **Contract / database / API impact:** No shared PredictionOutput, label, feature, split, database or API contract changed. In-memory adapter now deduplicates exact repeated source records and fails closed on conflicting reuse of a scoped source identity. No Member 1/3/4 implementation changed.
- **Tests / verification:**
  - Consolidated Prompt 32 focused batch across 23 relevant test modules — **initial result: 332 passed, 1 failed, 24 warnings**; the single failure was an exact floating-point equality assertion in the new imbalance test, not application behavior. Changed it to approximate comparison, then `& .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p32-fix tests\test_member2_prompt32_diagnostics.py` — **PASS, 5 passed**. The other initially passing tests were not rerun; no full repository suite was run for Prompt 32.
  - `& .\.venv\Scripts\python.exe -B -m examples.member2_prompt32_diagnostics --prepared-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v4' --prompt31-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\experiments\prompt31-standard-tenant01-demo-v1' --output-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\experiments\prompt32-diagnostics-v3'` — **PASS** — TRAIN/VALIDATION only; 9,026 raw scores reproduced; 43.9381 seconds; output aggregate SHA-256 `7fda46f721f0380aecf3def2d4fa7a4d22de53c9748864f78fdf738b31b65246`.
  - Repository-local package imports — **PASS**; AST syntax parse — **PASS, 31 files**; `git diff --check` — **PASS**. SHAP/LightGBM warnings were not suppressed; 24 warnings in the focused batch were reviewed as output-shape warnings, and actual model attribution/additivity probes passed.
- **Data / model / ROI evidence:** Synthetic-only STANDARD v1.2, seed 2026, tenant-01; immutable existing artifacts. No TEST or CALIBRATION row artifacts accessed. No source database changed and no private row-level artifacts, credentials or customer scores added to Git. Validation shows weak discrimination; constant TRAIN-prevalence Brier is better than LightGBM at both trained horizons. Personalization removal improves AP/Brier on these cohorts; this is not a general or causal claim. No real-world performance, retention, savings or ROI claim.
- **Known issues / blockers:** 7d unsupported; CALIBRATION gates fail; 14d/30d uncalibrated metrics are weak and sparse; training evidence is synthetic-only; usage coverage is partial and baseline-feature missingness shifts by about 20 percentage points between TRAIN and VALIDATION. Stored Prompt 24 reliability/freshness aggregates predate the unknown-connectivity correction. Feature baseline windows differ from the older handoff description and overlap the 30d window. TEST remains sealed. Production prediction readiness is blocked.
- **Next action / handoff:** Members 3/4 must retain `MODEL_BUNDLE_NOT_READY` and must not rank/use private raw 14d/30d scores as calibrated risk. Member 1/owners should reconcile historical coverage/freshness and the baseline window definition. Any future model work requires authorized representative data, mature horizon support, calibration support and separately authorized untouched evaluation.
- **Reviewer / pairing:** N/A

### 2026-10-10T18:50:03Z — Member 2 AI coding assistant — Fit synthetic-only STANDARD horizon demos

- **Workstream:** Part 2 / ML / Integration / Docs / QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `feat(member2): train isolated synthetic horizon demos`
- **Issue / task:** Member 2 Prompt 31; no ticket
- **Files changed:** `examples/member2_standard_synthetic_demo_training.py`, `tests/test_member2_standard_synthetic_demo_training.py`, `docs/MEMBER2_PROMPT31_SYNTHETIC_DEMO_TRAINING.md`, `docs/MEMBER2_FINAL_PREDICTION_HANDOFF.md`, `docs/MEMBER2_TRAINING_READINESS_DECISION.md`, and this log.
- **What changed:**
  - Added a reproducible, fail-closed runner that verifies the immutable tenant-01 prep manifest and four TRAIN/VALIDATION checksums, loads only those stages, re-applies the existing temporal/maturity splitter, and writes model/prediction artifacts only outside Git.
  - Actually fit and saved LightGBM 14d/30d demo models with seed 2026; reloaded each via the trusted artifact loader and produced mature VALIDATION raw scores. 7d was not fit because it fails the frozen 50-positive TRAIN/VALIDATION support gate. Calibration/TEST files were not opened; no calibration or threshold tuning was performed.
  - Documented aggregate class/feature coverage, metrics, provenance, artifact checksums, reproducible command, and Member 3/4 restrictions. Added a superseding-status notice to the Prompt 30 handoff and readiness decision; production gates remain unchanged.
- **Why it changed:** Prompt 31 requests an actual model-fitting attempt and a useful delivery while preserving frozen splits, TEST isolation, production readiness gates, and explicit synthetic provenance.
- **Contract / database / API impact:** No PredictionOutput/status, database, API, dataset, or split contract changed. Scores are explicitly uncalibrated and synthetic-demo-only; no canonical scored payload or production bundle was created. Downstream owners must not serve/rank these scores as calibrated churn forecasts.
- **Tests / verification:**
  - `& .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p31-focused tests\test_member2_standard_synthetic_demo_training.py tests\test_lightgbm_model.py tests\test_candidate_training.py tests\test_temporal_splits.py` — **PASS** — 47 passed.
  - `& .\.venv\Scripts\python.exe -B -m examples.member2_standard_synthetic_demo_training --prepared-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v4' --output-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\experiments\prompt31-standard-tenant01-demo-v1'` — **PASS** — actual 14d/30d fit, model reload, and 9,026 mature VALIDATION inferences; elapsed 39.37s; 7d skipped by gate; output manifest SHA-256 `cfbebcbc006f269121aed1fba56d7145af1425b517f2f5fd68c77f291ed6f93d`.
  - TRAIN/VALIDATION artifact and prep-manifest checksums — **PASS**; TEST and CALIBRATION customer-level files were not opened. `python -B -c "import ast, pathlib; ...; import retainiq_prediction.lightgbm_model, retainiq_prediction.temporal_splits, examples.member2_standard_synthetic_demo_training"` — **PASS**; runner `--help` — **PASS**; `git diff --check` — **PASS** after final edits.
  - No full-suite rerun; last complete suite remains Prompt 29's 463 passed, 0 failures/errors/skips, 24 known unsuppressed SHAP warnings.
- **Data / model / ROI evidence:** `SYNTHETIC_DEMO_ONLY`, tenant-01 STANDARD v1.2 seed 2026. Validation results are development-only and uncalibrated: 14d PR-AUC 0.011252, ROC-AUC 0.430971, Brier 0.011158; 30d PR-AUC 0.025993, ROC-AUC 0.498498, Brier 0.026834. These do not establish real-world or production performance; no retention, causal, saved-revenue, or ROI claim.
- **Known issues / blockers:** 7d fails frozen support; CALIBRATION fails at every horizon; all usage coverage in the prepared data is partial and no recent window is fully covered. Stored quality metadata predates the unknown-connectivity correction. No local KKBox/other authorized dataset was found. Full 7/14/30 calibration, operational scoring, independent TEST evaluation, and real-world readiness remain blocked.
- **Next action / handoff:** Members 3/4 may use the typed contract only with an explicit not-ready state; do not ingest private uncalibrated files into production flows. Member 1/data owner must address source coverage/health and missing-history semantics. Future fitting requires adequate authorized TRAIN/VALIDATION/CALIBRATION support and independent evaluation; keep TEST sealed until the separate evaluation gate.
- **Reviewer / pairing:** N/A

### 2026-10-10T18:39:45Z — Member 2 AI coding assistant — Final prediction readiness and downstream handoff

- **Workstream:** Part 2 / Integration / Docs / QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `docs(member2): publish final prediction readiness handoff`
- **Issue / task:** Member 2 Prompt 30; no ticket
- **Files changed:** `docs/MEMBER2_FINAL_PREDICTION_HANDOFF.md` and this log.
- **What changed:**
  - Published the canonical downstream payload/status/reliability semantics and the existing internal `PredictionPipeline.run(PredictionRequest)` integration seam, explicitly stating that the model bundle and scored forecasts are unavailable.
  - Recorded the aggregate 60-pair eligibility mismatch as missing subscription history (`MISSING_SUBSCRIPTION_HISTORY`), with no unsafe remapping or Member 1 worktree change.
  - Recorded frozen synthetic-only TRAIN/VALIDATION/CALIBRATION support blockers and the exact Member 1/3/4 handoffs; no TEST outcomes, data reads, training or model fitting were added.
- **Why it changed:** Prompt 30 requires a truthful final delivery state and usable downstream contract when the frozen evidence gates do not support training.
- **Contract / database / API impact:** Documentation only; no canonical schema, status, database, API, split, or feature contract changed. Member 1 must resolve the missing-versus-terminal historical subscription response; Members 3/4 should consume the existing canonical contract without assuming a scored model is available.
- **Tests / verification:**
  - `& .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p30-focused tests\test_authenticated_standard_pilot.py tests\test_eligibility.py tests\test_prediction_pipeline.py tests\test_candidate_training.py tests\test_dataset_readiness.py tests\test_retraining_readiness.py` — **PASS** — 65 passed; 15 known SHAP/LightGBM output-shape warnings, unsuppressed.
  - Repository-local imports of canonical contracts, pipeline, candidate trainer, and eligibility — **PASS**.
  - Prompt 29 one-account/one-cutoff authenticated API smoke — **PASS**, reused as recent integration evidence; not rerun because this change is documentation-only and no new API reads were needed. Prompt 29 full suite result remains 463 passed, 0 failures/errors/skips, 24 known SHAP warnings; not repeated per Prompt 30.
  - `git diff --check` — **PASS** after the final documentation edits.
- **Data / model / ROI evidence:** Synthetic-only tenant-01 STANDARD v1.2 evidence; no model fit, scored predictions, TEST-outcome use, held-out metric, real-world validation, retention effect, or ROI claim.
- **Known issues / blockers:** CALIBRATION fails frozen support at all horizons; 7d also fails TRAIN and VALIDATION positive-row support. The 60-pair missing-subscription-history mismatch is unresolved. Operational scoring remains blocked by missing model artifacts and inadequate/unknown live evidence.
- **Next action / handoff:** Member 1 to resolve historical eligibility and source-health/evidence fields. Members 3/4 can integrate the schema and explicit not-ready state; do not rank or learn from synthetic/unavailable probabilities. Any future fitting requires authorized data and all frozen maturity/support gates to pass.
- **Reviewer / pairing:** N/A

### 2026-10-10T18:30:11Z — Member 2 AI coding assistant — Execute authenticated STANDARD historical pilot

- **Workstream:** Part 2 / Part 1 integration / QA / Docs
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `feat(member2): checkpoint authenticated STANDARD pilot`
- **Issue / task:** Member 2 Prompt 29; no ticket
- **Files changed:** `examples/member2_authenticated_standard_pilot.py`, `tests/test_authenticated_standard_pilot.py`, `docs/MEMBER2_AUTHENTICATED_STANDARD_PILOT_RESULTS.md`, and this log.
- **What changed:**
  - Added a deterministic, aggregate-only pilot capped at 30 tenant-01 accounts × three frozen TRAIN/VALIDATION cutoffs, using Member 1's DPAPI wrapper, authenticated historical APIs, and Member 2's existing SQLite adapter/features/eligibility/freshness/reliability/label components. Added runtime rejection of unprivileged valuation fields.
  - Added offline structural tests and recorded the authenticated STANDARD pilot, source/working-copy integrity, stage/horizon labels, source-state and reliability outcomes, API-call counts, and readiness classifications.
  - Clarified that Prompt 28 was checkpointed locally as `853f11b60afc9d73b0e85bda61d665305de7c716`; verified Member 1 P0 HEAD `c312eb80a75c6686e16049f1e04ebe31713e403f` without modifying either Member 1 worktree.
- **Why it changed:** Verify the secured cross-member read boundary and corrected unknown-source handling on a bounded synthetic STANDARD cohort before considering any separately authorized larger experiment.
- **Contract / database / API impact:** No shared schema, API, split boundary, TEST, reliability threshold, or label policy changed. The observed 60-pair Member 1 `not_eligible` versus Member 2 `INSUFFICIENT_DATA` difference requires team agreement. Reader grants remain tenant-01 `retention_inference` only; no database writes or artifact writes.
- **Tests / verification:**
  - `.\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p29-focused-final tests\test_authenticated_standard_pilot.py` — **PASS** — 9 passed in 3.81s.
  - `.\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p29-cross-member tests\test_authenticated_standard_pilot.py tests\test_dataset_readiness.py tests\test_sqlite_data_adapter.py tests\test_data_freshness.py tests\test_reliability.py tests\test_label_builder.py tests\test_outcome_coverage_reconciliation.py tests\test_outcome_reconciliation.py tests\test_historical_dataset_preparation.py tests\test_temporal_splits.py tests\test_cross_member_policy_readiness.py tests\test_cross_member_integration.py tests\test_data_foundation.py` — **PASS** — 221 passed in 13.97s.
  - `.\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p29-full` — **PASS** — 463 passed, 0 failures/errors/skips, 24 existing SHAP warnings in 24.60s; warnings unsuppressed.
  - P0 `test_member1_p0_reader.py`, `test_member2_handoff.py`, `test_data_foundation.py`, run with Member 2's absolute local interpreter — **PASS** — 59 passed in 7.09s. An initial invocation used a nonexistent P0-relative `.venv` path and ran no tests; corrected without changing P0 files.
  - Supplemental authenticated one-account/one-cutoff contract smoke through the DPAPI wrapper — **PASS** — one read each for account snapshot, events, subscriptions, and coverage; live valuation-redaction assertions passed; excluded from pilot sample counts.
  - Nine package imports; AST parse of 67 Python files; `git diff --check` — **PASS**. Manifest artifacts 20/20; immutable source and working-copy SHA-256s matched approved values; both SQLite files returned `integrity_check=ok` opened read-only.
  - Two successful authenticated bounded executions used the same 90 deterministic account/cutoff pairs; final corrected aggregate is documented. No TEST reads, data generation/import, model training, or direct database row queries.
- **Data / model / ROI evidence:** Synthetic-only API observations. 90 candidate pairs; 28 eligible; per horizon 1 positive, 27 negative, 0 unknown, 2 excluded, 60 unsupported. No model was trained and no predictive performance, real-world readiness, or retention impact is claimed.
- **Known issues / blockers:** 60 sampled account-state disagreements (`not_eligible` vs `INSUFFICIENT_DATA`); no known-cancellation case sampled; no historical independent heartbeat/disconnection evidence; 25/28 eligible cases require abstention; only one positive account and zero TRAIN positives. Operational scoring and offline training remain blocked.
- **Next action / handoff:** Agree eligibility semantics and request an API-backed lifecycle/source-health evidence contract with Member 1. Only afterward, request separate approval for a larger bounded STANDARD development sample. Prompt 29 is checkpointed locally in this commit; no push, merge, deployment, TEST inspection, or training.
- **Reviewer / pairing:** N/A

### 2026-10-10T17:23:08Z — Member 2 AI coding assistant — Audit authorized data access and FULL readiness

- **Workstream:** Part 2 / Part 1 integration / Docs / QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `docs(member2): audit authorized synthetic dataset readiness` (Prompt 28 checkpoint `853f11b60afc9d73b0e85bda61d665305de7c716`)
- **Issue / task:** Member 2 Prompt 28; no ticket
- **Files changed:** `docs/MEMBER2_AUTHORIZED_FULL_DATASET_READINESS.md`, `docs/MEMBER2_TO_MEMBER1_CONTRACT_REQUESTS.md`, and this log.
- **What changed:**
  - Reviewed and checkpointed the exact Prompt 27 change set as `ed7493f290cb0a9732a37318ea0b2bc32a9d430b`; current branch is `integration/member2-main-sqlite`.
  - Reverified the STANDARD v1.2 manifest and all 20 listed file hashes/sizes; reverified the prior tenant-01 prepared manifest and all eight output hashes; the STANDARD SQLite file hash matches the recorded prior verified database. No private SQLite rows were queried.
  - Confirmed the documented FULL artifact/database paths remain absent and `RETAINIQ_MODEL_TOKEN` is absent. No credentials were provisioned, no authenticated calls were made, and no data pilot ran.
  - Documented current least-privilege read flow, extra `model_artifact_write`/`billing_valuation` principal grants in convenience/import paths, missing service-principal revoke/rotation, bounded FULL provisioning steps, and explicitly estimated (not measured) compute/storage.
  - Updated the Member 1 contract request with the newly confirmed principal-lifecycle/import side effects. No shared API/schema policy was changed.
- **Why it changed:** Prompt 28 requires evidence-backed STANDARD/FULL artifact status, safe reader setup, bounded-pilot decision, and a reviewed FULL provisioning plan without creating/importing data absent prerequisites.
- **Contract / database / API impact:** Documentation/request only; no API, database, source artifact, split, calibration, label, TEST, or reliability policy changed. Member 1 action requested for least-privilege principal lifecycle, import idempotency, health/completeness, and bounded reads.
- **Tests / verification:**
  - `.\.venv\Scripts\python.exe -B -m pytest -q tests\test_dataset_readiness.py tests\test_sqlite_data_adapter.py tests\test_data_freshness.py tests\test_reliability.py tests\test_label_builder.py tests\test_historical_dataset_preparation.py tests\test_cross_member_policy_readiness.py tests\test_cross_member_integration.py tests\test_data_foundation.py tests\test_temporal_splits.py --basetemp .pytest-tmp-p28-focused` — **PASS** — 181 passed in 11.06s; fixture/test evidence, not live authorization.
  - `.\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p28` — **PASS** — 454 passed, 0 failed/errors/skipped, 24 existing SHAP warnings in 19.43s; warnings unsuppressed.
  - STANDARD source manifest and 20 artifacts — **PASS**; prepared v4 manifest and 8 artifacts — **PASS**; SQLite SHA-256 matches prior verified checksum. Hash-only checks; no record reads.
  - Authenticated pilot and FULL pilot — **NOT RUN** — reader token absent; FULL artifact/database absent. Authenticated data API calls: 0.
  - CLI help/source inspection — **PASS** for documented generator/importer/provisioner options; generation/import/provisioning were not invoked.
  - 11 package imports — **PASS**; AST/syntax parse — **PASS** for 79 Python files; `git diff --check` — **PASS**. No files are staged; changed paths are documentation/log only and contain no credentials or private rows.
- **Data / model / ROI evidence:** Synthetic-only provenance. No new observations or outcomes, corrected live freshness counts, labels, model, calibration, metrics, or claims. Prior v4 reliability aggregates are explicitly pre-correction; FULL storage/runtime figures are linear estimates only.
- **Known issues / blockers:** STANDARD reader credential unavailable. FULL manifest/database absent. No supported service-principal revocation/rotation was found; import retries can add extra service-principal rows. Source operational-health/completeness evidence remains unavailable. Training and operational scoring remain blocked.
- **Next action / handoff:** Member 1 to provide safe principal lifecycle/import behavior and health/batch contracts; authorized operator to securely inject a tenant-01 read-only `RETAINIQ_MODEL_TOKEN`. Then execute the bounded STANDARD pilot before any separately approved FULL generation/import. Prompt 28 was committed locally as `853f11b60afc9d73b0e85bda61d665305de7c716`; no push or merge.
- **Reviewer / pairing:** N/A

### 2026-10-10T17:14:17Z — Member 2 AI coding assistant — Correct source-state attribution and assess FULL feasibility

- **Workstream:** Part 2 / Part 1 integration / Docs / QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `fix(member2): distinguish unknown source health from disconnection` (Prompt 27 pending; not committed)
- **Issue / task:** Member 2 Prompt 27; no ticket
- **Files changed:** `src/retainiq_prediction/data_freshness.py`, `src/retainiq_prediction/sqlite_data_adapter.py`, `tests/test_data_freshness.py`, `tests/test_sqlite_data_adapter.py`, `tests/test_reliability.py`, `docs/MEMBER2_FULL_SYNTHETIC_FEASIBILITY.md`, `docs/MEMBER2_TO_MEMBER1_CONTRACT_REQUESTS.md`, `docs/MEMBER2_TRAINING_READINESS_DECISION.md`, and this log.
- **What changed:**
  - Prompt 26 was verified as precisely its four expected files and checkpointed locally as `c0948a2b6981711559c854bd53a52e7b883f43ca` (`docs(member2): formalize source health and model readiness contracts`). No other files were staged for that checkpoint.
  - Confirmed the adapter inferred `connected=False` from missing account facts/coverage and freshness mislabeled silence `SOURCE_NOT_CONNECTED`/stale. `connected` is now tri-state with default unknown; the SQLite adapter does not infer connection from either events or coverage. Explicit `False` remains stale/blocking; absent health and absent watermark remain unknown. Complete available coverage can independently support coverage freshness. Reliability policy, status enums, thresholds, and canonical prediction schema are unchanged.
  - Added regressions for event silence, independently verified zero usage coverage, explicit disconnection, unknown/future source health, serialized reasons, and continued reliability abstention.
  - Inspected FULL profile code/config (20,000 accounts, four tenants, seed 2026 default, `[2024-10-01, 2026-10-01)`). The documented immutable FULL directory and DB are absent from the inspected private root; no FULL manifest or tenant authorization could be verified. `RETAINIQ_MODEL_TOKEN` was absent, so a bounded STANDARD authenticated pilot stopped before data API calls; no credentials were requested or created.
  - Profiled the existing STANDARD preparation's recorded aggregate metrics rather than re-reading customer data: 234,495 authenticated calls / 950.910s; point-in-time reads 572.882s, outcome reads 120.845s. Proposed an authorized Member 1 batch API; no cache or alternate reader was added. FULL compute/storage projections are explicitly linear estimates, not measurements.
  - Verified the existing STANDARD source manifest, preparation manifest, all 8 artifact hashes/sizes, and the SQLite file checksum by checksum-only reads. No SQLite records were queried or changed; private customer-level artifacts were not decompressed, parsed, or altered.
- **Why it changed:** Prompt 27 requires truthful source-health attribution, a bounded FULL feasibility decision, and efficiency analysis without weakening data-quality or temporal safeguards.
- **Contract / database / API impact:** Internal freshness evidence now permits unknown connection state. No canonical PredictionOutput fields/statuses, source database, Member 1 API/schema, frozen split, calibration threshold, or TEST policy changed. Member 1 must supply historical operational-health and completeness evidence and consider bounded authorized batch reads; shared cancellation/multi-subscription policy remains open.
- **Tests / verification:**
  - `.\.venv\Scripts\python.exe -B -m pytest -q tests\test_data_freshness.py tests\test_sqlite_data_adapter.py tests\test_reliability.py tests\test_historical_dataset_preparation.py tests\test_label_builder.py tests\test_temporal_splits.py tests\test_data_foundation.py tests\test_cross_member_integration.py tests\test_cross_member_policy_readiness.py --basetemp .pytest-tmp-p27-focused-final` — **PASS** — 173 passed.
  - `.\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p27-final` — **PASS** — 454 passed, 0 failed/errors/skipped, 24 known SHAP warnings (9 explainability, 15 prediction pipeline), unsuppressed; 20.71s.
  - Package imports — **PASS**. AST parse — **PASS**, 49 Python files. `git diff --check` — **PASS** (rerun after this log update before handoff).
  - STANDARD source/preparation manifest SHA and all 8 artifact SHA/size checks — **PASS**. SQLite file checksum-only SHA-256 matches prior manifest `71bc6c18d9266c2b0c8b8e5008f6f6633a55804b1fe90a947f8ea24ca3ee5943`.
  - Bounded authenticated pilot — **NOT RUN** — no `RETAINIQ_MODEL_TOKEN` in process environment. FULL pilot — **NOT RUN** — expected immutable dataset/database absent and tenant-01 authorization unverified.
- **Data / model / ROI evidence:** **Synthetic only.** Existing STANDARD v1.2 tenant-01 preparation; no new records, labels, metrics, model, calibration, TEST outcome analysis, or performance claim. Historical handoff FULL counts/import time are cited only as unverified prior documentation. New FULL storage/runtime projections are estimates.
- **Known issues / blockers:** Existing v4 aggregate freshness/reliability and 9,355 `SOURCE_NOT_CONNECTED` occurrences are pre-correction results and were not recomputed. STANDARD sample gates remain blocked; operational scoring remains blocked. No FULL manifest/tenant grants or usable reader credential. Member 1 historical heartbeat/completeness and batch-read interfaces remain dependencies.
- **Next action / handoff:** Project lead/Member 1 to provide or locate the immutable FULL artifact, confirm exact tenant-01 authorization, and deliver historical source-health/completeness and bounded-read contracts. Only then run a bounded tenant-01 readiness pilot; do not train or alter frozen TEST/split/calibration policy without a separately authorized prompt.

### 2026-10-10T16:59:47Z — Member 2 AI coding assistant — Audit cross-member policy and readiness

- **Workstream:** Part 2 / Part 1 integration / Docs / QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `docs(member2): audit cross-member source readiness contracts` (Prompt 26 pending; not committed)
- **Issue / task:** Member 2 Prompt 26; no ticket
- **Files changed:** `docs/MEMBER2_TO_MEMBER1_CONTRACT_REQUESTS.md`, `docs/MEMBER2_TRAINING_READINESS_DECISION.md`, `tests/test_cross_member_policy_readiness.py`, and this log.
- **What changed:**
  - Checkpointed the verified Prompt 25 reconciliation as `41041f3de6496d4dcd49676b0104d92e57e956b8` (`fix(member2): reconcile churn outcome evidence and coverage`); no other work was staged.
  - Audited Member 1's latest-state/all-active cancellation rule against Member 2's any-visible-historical-request routing. Documented ended-subscription and reversed-request cases, downstream denominator/route impact, and alternatives for a versioned shared policy. Existing implementations remain unchanged.
  - Documented current source-health and outcome-coverage APIs separately from proposed heartbeat, coverage-completeness, and late-arrival aggregate contracts. Added tenant/source authorization, as-of timing, and acceptance requirements; no Member 1 production API/schema was changed.
  - Recovered frozen tenant-01 stage support from v4 manifest/partition evidence; documented numeric and structural gates, row/unique-account deltas, distinct readiness states, synthetic dataset options, and why training/scoring remain blocked. No TEST metric analysis or model training occurred.
  - Added current-behavior regression tests and test-only types clearly marked `CONTRACT_PROPOSAL`; they do not claim a production heartbeat or diagnostics API exists.
- **Why it changed:** Prompt 26 requires cross-member contract alignment and evidence-backed readiness before any future training decision, while preserving Prompt 25 artifacts and frozen splits.
- **Contract / database / API impact:** No runtime contract or database/API was changed. Proposed versioned cancellation and health/diagnostics contracts require Member 1 and named shared policy-owner review. No Member 1/3/4 worktree was modified.
- **Tests / verification:**
  - `.\.venv\Scripts\python.exe -B -m pytest -q tests\test_cross_member_policy_readiness.py --basetemp .pytest-tmp-p26-focused` — **PASS** — 16 passed.
  - Focused Member 1/2 integration command covering policy/readiness, outcome reconciliation, historical preparation tests, label/eligibility, reliability/freshness, SQLite adapter, Data Foundation and cross-member tests — **PASS** — 175 passed.
  - `.\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p26` — **PASS** — 448 passed, 0 failed/errors/skipped; 24 existing SHAP warnings (9 explainability, 15 prediction pipeline), unsuppressed; 19.63s.
  - Package imports and AST parsing — **PASS** — 27 Python package files. `git diff --check` — **PASS**. Private v4 preparation manifest SHA and 8/8 artifact SHA/size checks — **PASS**; source SQLite SHA-256 remains `71bc6c18d9266c2b0c8b8e5008f6f6633a55804b1fe90a947f8ea24ca3ee5943`.
- **Data / model / ROI evidence:** **Synthetic only** — existing tenant-01 STANDARD v1.2 (`synthetic-saas-v1-2-standard-s2026-970a9d231e68`), immutable source manifest SHA `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`; prepared v4 manifest SHA `1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a`. No model trained, no TEST outcomes inspected for optimization, no dataset re-preparation.
- **Known issues / blockers:** All three horizons fail at least one frozen stage support gate; all are synthetic-only. Sufficient/fresh snapshots are zero; operational scoring remains blocked. Multi-subscription request aggregation/reversal policy and lifecycle/billing heartbeats/completeness remain unresolved. Existing APIs filter unavailable events without excluded-row aggregate diagnostics.
- **Next action / handoff:** Project lead to name the domain-policy approver and coordinate with Member 1 on cancellation semantics, lifecycle/billing source health, and authorized diagnostics. Only after agreement and explicit authorization, consider a separate tenant-scoped read-only preparation from the existing immutable FULL synthetic dataset. Preserve its split policy; preflight stage support and reliability, and stop if blocked. Do not train or alter TEST policy until separately authorized.

### 2026-10-10T16:32:00Z — Member 2 AI coding assistant — Reconcile labels and freeze reproducible historical data

- **Workstream:** Part 2 / Part 1 integration
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `fix(member2): reconcile churn outcome evidence and coverage` — checkpoint `41041f3de6496d4dcd49676b0104d92e57e956b8`
- **Issue / task:** Member 2 Prompt 25; no ticket
- **Files changed:** `src/retainiq_prediction/label_builder.py`, `src/retainiq_prediction/sqlite_data_adapter.py`, `src/retainiq_prediction/historical_dataset_preparation.py`, `src/retainiq_prediction/reliability.py`, `tests/test_outcome_coverage_reconciliation.py`, `tests/test_reliability.py`, `docs/MEMBER2_OUTCOME_COVERAGE_BLOCKERS.md`, `docs/MEMBER2_SYNTHETIC_HISTORICAL_DATASET_PREPARATION.md`, and this log.
- **What changed:**
  - Prompt 24 checkpoint retained at `7971828b9f1c281340806dae39c56641a57a6633`; the verified Prompt 25 changes were subsequently checkpointed as `41041f3de6496d4dcd49676b0104d92e57e956b8`.
  - Member 1's effective termination `status=ended` is now accepted by Member 2's label semantics. Outcome coverage retains source category/status/completeness/policy metadata; the label builder joins adjacent complete subscription intervals only, requires continuity for all active subscription identities, and keeps gaps/outages/usage-only coverage unknown.
  - Synthetic final-entitlement evaluation now preserves a first churn episode across later reactivation, requires no paid entitlement at the account churn time, records the final subscription-loss time and all terminal evidence refs, and leaves contradictory state unknown. Reliability reason iteration now sorts essential sources to make serialized feature artifacts deterministic.
  - Reused the existing authenticated tenant-01 STANDARD SQLite APIs. Added focused regressions and per-horizon reason/source-coverage summaries to the private preparation manifest. Re-prepared into versioned private directories; the final output is `member2-prep-v4`, with all earlier outputs preserved. No model was trained.
  - Authorized source audit observed 160 terminal lifecycle facts across 155 tenant-01 accounts (147 involuntary, 5 non-renewal, 8 voluntary); 39,824 subscription coverage rows (37,099 complete, 1,162 outage, 63 partial, 750 censored, 750 not-created). Reader access succeeded with tenant-01 retention-inference authorization; no permission bypass or access to other tenants. Existing service-principal also had `model_artifact_write`, which read-only preparation did not use.
  - End-boundary authorized API aggregate: 750 tenant-01 identities; 629 with paying entitlement (625 eligible, 4 known cancellations), 121 not eligible; 75 accounts with multiple historical subscription IDs, 23 partial-termination accounts, 137 final entitlement-loss transitions, and 154 with a later paid-active lifecycle fact after a qualifying termination.
  - Corrected full run: 26,267 lifecycle-backed snapshots; 23,415 eligible; 700 unique eligible accounts; 22,715 repeated snapshots; labels positive/negative/unknown: 7d 100/21,851/1,464, 14d 200/21,058/2,157, 30d 437/19,530/3,448. All horizons remain blocked for synthetic training under calibration-stage class/unique-account minimums. Real-world readiness remains blocked.
  - Frozen splits retained: TRAIN 7,157 (2024-12-09–2025-08-18), VALIDATION 5,859 (2025-10-06–2026-01-19), CALIBRATION 3,700 (2026-03-02–2026-04-20), TEST 6,699 (2026-06-01–2026-08-17). Stage label maturity exclusions were zero; TEST remains evaluation-only. Reliability: 0 sufficient, 654 limited, 22,761 insufficient; freshness: 0 fresh, 654 partially stale, 22,761 stale, 0 unknown. Staleness remains ambiguous between time-relative event watermarks and genuine source gaps because independent heartbeats are absent; thresholds were not weakened.
  - Final v4 preparation took 950.910 seconds; 57.576 candidate pairs/s, 24.624 eligible snapshots/s, 73.871 labels/s; peak working set unavailable. v3/v4 manifests and all eight artifact hashes match; source DB hash remained unchanged. Final private manifest SHA-256: `1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a`.
- **Why it changed:** Prompt 24 surfaced zero labels despite an existing authorized STANDARD dataset. The verified root causes were Member 1's canonical `ended` state not being accepted as terminal by Member 2, and Member 2 requiring one coverage segment to span a full horizon instead of joining contiguous complete subscription segments.
- **Contract / database / API impact:** No Member 1 schema, API, authorization, shared prediction contract, or database was changed. Adapter consumes existing authenticated APIs. Prediction-time features and post-cutoff label outcomes remain separate. Synthetic v1.2 final-paid-entitlement loss remains explicitly dataset-specific.
- **Tests / verification:**
  - `.\.venv\Scripts\python.exe -B -m pytest -q tests\test_outcome_coverage_reconciliation.py tests\test_historical_dataset_preparation.py tests\test_sqlite_data_adapter.py tests\test_feature_builder.py tests\test_label_builder.py tests\test_temporal_splits.py tests\test_reliability.py tests\test_data_freshness.py tests\test_data_foundation.py tests\test_cross_member_integration.py --basetemp .pytest-tmp-p25-integration-final2` — **PASS** — 175 passed.
  - `.\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p25-final` — **PASS** — 432 passed, 0 failed/errors/skipped, 24 existing SHAP warnings; warnings not suppressed.
  - Focused `tests\test_reliability.py tests\test_outcome_coverage_reconciliation.py tests\test_label_builder.py` — **PASS** — 50 passed.
  - Authenticated full tenant-01 preparation — **PASS** — 26,267 lifecycle-backed, 23,415 eligible, 70,245 labels; private manifest/artifact checksums verified; SQLite SHA-256 unchanged.
  - Python package imports and AST parse — **PASS** — 27 package files parsed; `git diff --check` — **PASS**; private output/hash checks — **PASS**.
- **Data / model / ROI evidence:** Synthetic STANDARD v1.2 only, tenant-01 only, seed 2026; source manifest SHA-256 `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`. No model training, model evaluation, real-world validation, causal effect, saved revenue, or ROI claim. Customer-level prepared data and credentials remain outside Git.
- **Known issues / blockers:** Every horizon remains `BLOCKED` for synthetic training because calibration partitions do not meet declared positive/unique-account support; 7-day train/validation/test support is also insufficient. 97.21% of eligible rows remain stale/insufficient, with no lifecycle/billing heartbeat to distinguish event silence from an ingestion gap. The bounded-cutoff enumerator mismatch is confirmed: Member 1 excludes a known cancellation only when all active subscriptions are pending cancellation, while Member 2 excludes when any subscription has a known request. Team decision required; conservative Member 2 routing is unchanged. Real multi-subscription churn and source correction/supersession policy remain unresolved.
- **Next action / handoff:** Member 1/team to clarify heartbeat/watermark, least-privilege read purpose, and account-level known-cancellation semantics; agree real account churn/correction policy. Do not train until all horizon/stage readiness gates are satisfied. Keep TEST sealed from selection and obtain authorized real longitudinal evidence before real-world claims.
- **Reviewer / pairing:** N/A

### 2026-10-10T15:17:20Z — Member 2 AI coding assistant — Prepare synthetic historical dataset

- **Workstream:** Part 2 / Part 1 integration
- **Branch:** integration/member2-main-sqlite
- **Commit subject:** feat(member2): prepare leakage-safe synthetic historical dataset
- **Issue / task:** Member 2 Prompt 24; no ticket
- **Files changed:** src/retainiq_prediction/historical_dataset_preparation.py, src/retainiq_prediction/feature_builder.py, src/retainiq_prediction/sqlite_data_adapter.py, src/retainiq_prediction/label_builder.py, tests/test_historical_dataset_preparation.py, docs/MEMBER2_SYNTHETIC_HISTORICAL_DATASET_PREPARATION.md, and this log.
- **What changed:**
  - Added historical preparation orchestration over the existing authenticated Member 1 reader, point-in-time features, synthetic-only final-entitlement churn policy, label maturity, existing temporal splits, and reliability/freshness assessments. Historical customer-level artifacts and manifest remain outside Git.
  - Corrected negative label maturity: a negative cannot be emitted before its full prediction horizon elapsed, even if future-dated coverage is supplied. Applied the existing dataset-specific all-active-entitlements policy without changing shared requirements.
  - Ran the existing STANDARD v1.2 dataset for tenant-01 only. Produced 26,267 lifecycle-backed snapshots, 23,415 eligible feature snapshots, and 70,245 horizon labels; all eligible labels were unknown due to missing outcome coverage. Added the audited split, metrics, and manifest findings to the new documentation.
  - Prompt 23 checkpoint: 28353fb1d0903258afdf1145ef5b6f3c9e7d2774 (feat(member2): integrate authenticated sqlite historical data adapter).
- **Why it changed:** Prompt 24 requires a reproducible point-in-time-safe dataset preparation path and honest split/label/readiness evidence before any model training.
- **Contract / database / API impact:** No database schema or shared PredictionOutput contract changed. The preparation consumes existing Member 1 authenticated APIs; feature and label behavior is additive/fixed for correct historical maturity. Synthetic account-churn semantics remain dataset-specific and are not declared as real-customer policy.
- **Tests / verification:**
  - .\.venv\Scripts\python.exe -B -m pytest -q tests\test_historical_dataset_preparation.py tests\test_sqlite_data_adapter.py tests\test_feature_builder.py tests\test_label_builder.py tests\test_temporal_splits.py tests\test_reliability.py tests\test_data_freshness.py tests\test_data_foundation.py tests\test_cross_member_integration.py --basetemp .pytest-tmp-p24-integration — PASS — 163 passed.
  - .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p24 — PASS — 420 passed, 0 failures/errors/skips, 24 known SHAP warnings.
  - Actual authenticated STANDARD tenant-01 preparation — PASS as a reproducible structural run — 54,750 candidate pairs, 26,267 lifecycle-backed, 23,415 eligible, 70,245 unknown horizon labels; 920.336 seconds; source DB SHA-256 unchanged.
  - Package import and AST syntax checks — PASS. All eight private artifact SHA-256 checks and preparation manifest SHA-256 sidecar — PASS. git diff --check — PASS.
- **Data / model / ROI evidence:** Synthetic v1.2 only; immutable dataset manifest SHA-256 7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d. Tenant-01 only. Zero mature positives and negatives were surfaced; no class prevalence, model metric, real-world validation, retention effect, or ROI claim. No model trained.
- **Known issues / blockers:** All horizons are BLOCKED for synthetic training: authorized outcome reads produced no qualifying positive evidence and no complete subscription outcome coverage, despite the four-tenant dataset manifest's 621 episode count. Freshness/reliability were stale/insufficient for 97.21% of eligible snapshots; lifecycle/billing lack independent heartbeats and usage coverage is mostly incomplete. Member 1/Member 2 must reconcile outcome event/coverage fields and watermark contract. The source database, artifacts and private records remain outside Git.
- **Next action / handoff:** Member 1 and Member 2 to investigate authorized outcome/coverage API evidence and lifecycle/billing heartbeat semantics. Do not begin model training until every horizon has adequate mature class coverage and split-level readiness.
- **Reviewer / pairing:** N/A

### 2026-10-10T14:35:16Z — Member 2 AI coding assistant — Add authenticated SQLite prediction adapter

- **Workstream:** Part 2 / Part 1 integration
- **Branch:** integration/member2-main-sqlite
- **Commit subject:** feat(member2): add read-only authenticated SQLite data adapter
- **Issue / task:** Member 2 Prompt 23; no ticket
- **Files changed:** src/retainiq_prediction/sqlite_data_adapter.py, src/retainiq_prediction/feature_builder.py, tests/test_sqlite_data_adapter.py, docs/MEMBER2_LOCAL_SQLITE_ADAPTER.md, and this log.
- **What changed:**
  - Added a typed, tenant-bound adapter over Member 1's authenticated reader APIs. It binds the database identity to the STANDARD v1.2 manifest, preserves synthetic provenance and source timestamps, reconstructs subscription facts from dated events, maps usage/billing/lifecycle and coverage evidence, and rechecks the cutoff on all returned rows.
  - Extended existing feature/coverage inputs additively for daily usage quantities, distinct active days and coverage metadata. A daily aggregate remains one fact; quantity is not expanded into duplicate sessions. Missing or invalid quantity is not counted as one session.
  - Added 13 adapter-focused tests covering authorized/unauthorized use, identity mismatch, tenant scoping, historical eligibility/cancellation, payment-failure semantics, future/late/unknown availability, aggregate quantities, zero-versus-unknown coverage, freshness limitations, outcome separation and SQLite read-only behavior.
  - Generated and validated STANDARD synthetic v1.2 seed-2026 data outside the repository, imported it into private SQLite with idempotency verification, provisioned a tenant-01 reader without billing-valuation permission, and ran both the official cross-member smoke and the new adapter against the actual database.
- **Why it changed:** Prompt 23 required a verified local synthetic integration path and a Member 2-owned adapter without duplicating Member 1 storage/authentication or asserting real-data readiness.
- **Contract / database / API impact:** No database schema, PredictionOutput, label policy, or Member 1 API was changed. Existing FeatureValues and UsageCoverage gained additive fields for active-day and coverage-quality semantics. The adapter rejects unsupported availability-policy changes because Member 1's read API currently applies source_available_at then received_at. Member 1 and the team should review the additional feature fields and source-availability limitations before production integration.
- **Tests / verification:**
  - Local generator generate --profile standard --seed 2026 — PASS — dataset ID synthetic-saas-v1-2-standard-s2026-970a9d231e68.
  - Local synthetic validator — PASS — manifest SHA-256 7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d; no warnings.
  - Local importer with --verify-idempotency — PASS — 239,721 events and 491,223 coverage records; replay accepted zero and identified 239,721 duplicates; import duration 104.768 seconds.
  - .\.venv\Scripts\python.exe -B -m examples.member2_synthetic_smoke --db [private-db] --dataset [private-dataset] — PASS — dataset identity and cross-tenant denial verified; training not performed.
  - Direct authenticated adapter smoke against private SQLite — PASS — tenant-bound historical snapshot and feature assembly; 629 eligible tenant-01 accounts at the selected cutoff; one NOT_ELIGIBLE account was also verified without printing its identifier; freshness for the inspected feature example was stale.
  - .\.venv\Scripts\python.exe -B -m pytest -q tests/test_sqlite_data_adapter.py tests/test_feature_builder.py — PASS — 26 tests.
  - .\.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p23 — PASS — 413 passed, 0 failed/errors/skipped, 24 existing SHAP/LightGBM warnings, 20.16 seconds.
  - Package import check and git diff --check — PASS.
- **Data / model / ROI evidence:** Synthetic v1.2 only; 3,000 accounts, 4 tenants, 239,721 canonical events, 491,223 coverage intervals, 3,262 subscriptions and 621 effective account-churn episodes. No real-data validation, model training, performance, retention effect, or ROI claim.
- **Known issues / blockers:** The Member 1 reader provisioner grants model_artifact_write in addition to retention_inference; a least-privilege read-only provisioner change belongs to Member 1. Member 1's event API filters unknown/late records before returning them and does not expose exclusion counts, and its current API has no independent lifecycle/billing freshness heartbeat. The synthetic final-paid-entitlement policy must not be silently reused for real multi-subscription accounts. No corrections/supersession or production backend integration was tested.
- **Next action / handoff:** Keep Prompt 23 changes uncommitted for review. Member 1 should consider least-privilege read grants and explicit excluded-event/source-watermark evidence. Prompt 24 may prepare a frozen synthetic historical training/evaluation dataset path and split readiness checks; do not claim real-world effectiveness or production readiness.
- **Reviewer / pairing:** N/A

### 2026-10-10T14:05:36Z — Member 2 AI coding assistant — Integrate Main Data Foundation and synthetic CLI

- **Workstream:** Part 1 / Part 2 integration and QA
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `merge: integrate latest main data foundation with member2`
- **Issue / task:** Member 2 Prompt 22; no ticket
- **Files changed:** Merged `origin/main` at `c2fce585d55169d51f8dcf4a0d70c41984eb488a`, including `retaniq/`, `migrations/`, synthetic tooling, examples, Member 1 tests/docs and `DATASET_CARD.md`; resolved `.gitignore` and `TEAM_LOG.md`; updated Member 2 integration/blocker/dependency docs, the synthetic handoff command, and `tests/test_cross_member_integration.py`.
- **What changed:**
  - Preserved Member 1's SQLite Data Foundation and synthetic v1.2 implementation alongside Member 2's `src/retainiq_prediction` package. The only merge conflicts were add/add conflicts in `.gitignore` and `TEAM_LOG.md`; both were resolved by retaining all legitimate protections and all Member 1/Member 2 history.
  - Verified the synthetic `generate`, `validate`, `import`, and `provision-reader` CLIs without generating a dataset. Corrected the smoke command to module execution, removed the unsupported caller-supplied tenant argument, documented manifest-authoritative Prompt 23 commands and secure one-time token handling, and added a CLI regression test.
  - Updated integration readiness to recognize the merged local SQLite/auth/coverage interfaces while keeping real-data, production PostgreSQL, Member 3/4, durable governance, multi-subscription, and Member 2 SQLite-adapter blockers explicit.
- **Why it changed:** Safely combine the latest tenant-scoped Data Foundation with the completed Member 2 package before Prompt 23 local dataset generation and adapter work, without conflating synthetic readiness with real or production readiness.
- **Contract / database / API impact:** No frozen prediction, label, churn, availability, tenant, probability-horizon, or governance contract was changed. SQLite migrations 001–004 and Main's existing API/storage contracts are now present on the isolated integration branch. Local SQLite remains separate from future Supabase/PostgreSQL production integration.
- **Tests / verification:**
  - `.venv\Scripts\python.exe -B -m unittest discover -s tests -v` — PASS — 64 Member 1 unittest-style tests in 13.745s.
  - `.venv\Scripts\python.exe -B -m pytest -q tests/test_data_foundation.py tests/test_member2_handoff.py tests/test_member2_synthetic_smoke.py tests/test_synthetic_generator.py tests/test_synthetic_integration.py --basetemp .pytest-tmp-p22-member1` — PASS — 64 tests in 12.56s.
  - `.venv\Scripts\python.exe -B -m pytest -q tests/test_cross_member_integration.py --basetemp .pytest-tmp-p22-cross` — PASS — 19 tests in 3.46s.
  - Member 2 pytest files excluding the five Member 1 files, with `--basetemp .pytest-tmp-p22-member2` — PASS — 336 tests in 5.20s; 24 known SHAP/LightGBM output-shape warnings.
  - `.venv\Scripts\python.exe -B -m pytest -q --basetemp .pytest-tmp-p22` — PASS — 400 combined tests in 19.23s; 24 known SHAP/LightGBM output-shape warnings.
  - Synthetic CLI and every subcommand `--help`, module-based smoke `--help`, STANDARD seed-2026 configuration/ID calculation, source inspection, and `git diff --check` — PASS. Direct path-based smoke invocation was corrected to the verified module form.
- **Data / model / ROI evidence:** Synthetic source code, metadata contracts and test fixtures only. Dataset/database status is `EXPECTED_LOCAL_ARTIFACT_NOT_GENERATED`; no dataset was generated, no SQLite database was imported, no reader token was issued, no model was trained, and no performance or ROI evidence was produced.
- **Known issues / blockers:** Prompt 23 must generate/validate/import the exact manifest-bound STANDARD artifact and implement the Member 2 SQLite adapter. Real historical data, Supabase/PostgreSQL, Member 3/4 interfaces, durable production governance, correction policy, and agreed real-source multi-subscription semantics remain blocked.
- **Next action / handoff:** Keep this merge on the isolated integration branch. Prompt 23 should create the private Git-ignored synthetic artifact, provision a tenant-scoped token without logging it, run the smoke, and implement/test only the SQLite-to-Member2 adapter.
- **Reviewer / pairing:** N/A

### 2026-10-10T08:32:31Z — Member 2 AI coding assistant — Cross-member integration contracts and handoff

- **Workstream:** Part 2 / Part 4 integration
- **Branch:** `feature/prediction-engine`
- **Commit subject:** `docs(member2): finalize cross-member integration handoff`
- **Issue / task:** Member 2 Prompt 20; no ticket
- **Files changed:** `docs/MEMBER2_CROSS_MEMBER_INTEGRATION.md`, `docs/MEMBER2_HANDOFF_BLOCKERS.md`, `docs/MEMBER2_INTEGRATION_DEPENDENCIES.md`, `tests/test_cross_member_integration.py`, `TEAM_LOG.md`
- **What changed:**
  - Documented the verified Member 1 input contract, current point-in-time adapter fields, Member 3 canonical prediction/feedback handoff, Member 4 dashboard/outcome semantics, ownership boundaries, security/provenance rules and concrete acceptance checklist.
  - Added a P0/P1 blocker matrix without inventing backend/API/frontend completion. P0 blockers include the absent authorized longitudinal dataset, authenticated Member 1 adapter, unresolved multi-subscription policy, source availability/correction policy, and durable production model-governance storage.
  - Added 18 deterministic synthetic cross-member contract tests covering prediction serialization, scored/non-scored states, pipeline blockers, feedback maturity/revisions, tenant isolation, source availability and `prediction_id` linkage. Reused existing contracts; no parallel serializer, API, database, decision engine or UI was added.
- **Why it changed:** Make Member 2's actual interfaces and integration blockers actionable for Members 1, 3 and 4 while distinguishing local unit-test verification from real production readiness.
- **Contract / database / API impact:** No public schema, database, endpoint or shared enum change. Existing `PredictionOutput.model_dump/model_validate`, `PipelineResult`, `PointInTimeDataAdapter` and `InMemoryOutcomeReconciliationStore` are the verified local handoff boundaries. External authentication, persistence and endpoint ownership remain with other workstreams.
- **Tests / verification:**
  - `.venv\Scripts\python.exe -m pytest -q tests/test_cross_member_integration.py --basetemp .pytest-tmp-p20` — PASS — 18 tests passed.
  - `.venv\Scripts\python.exe -m pytest -q tests/test_cross_member_integration.py tests/test_prediction_contract.py tests/test_prediction_pipeline.py tests/test_outcome_reconciliation.py --basetemp .pytest-tmp-p20` — PASS — 75 tests passed, 15 known SHAP warnings.
  - `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-p20` — PASS — 335 tests passed, 24 known SHAP warnings.
  - `.venv\Scripts\python.exe -c "import retainiq_prediction; ..."` — PASS — Python 3.14.4; canonical prediction, pipeline and reconciliation exports imported.
  - `git diff --check` — PASS — no whitespace errors; normal LF/CRLF conversion warnings only.
- **Data / model / ROI evidence:** Explicitly synthetic contract fixtures and existing local unit tests only; no authorized dataset, real score, model metric, intervention effect, saved revenue or ROI evidence.
- **Known issues / blockers:** P0 handoff blockers remain open. `IMPROVEMENT-001` through `IMPROVEMENT-005` remain pending/unresolved. Prompt 18's original 28-scenario coverage review and Prompt 19's final governance scenario review remain deferred for final regression review.
- **Next action / handoff:** Member 1 should supply the authenticated canonical adapter, DATASET_CARD, availability/correction policy and multi-subscription decision. Members 3 and 4 should confirm their prediction/feedback and dashboard query contracts against this handoff before integration.
- **Reviewer / pairing:** N/A

### 2026-10-10T08:27:02Z — Member 2 AI coding assistant — Human approval, promotion and rollback governance

- **Workstream:** Part 2 / Part 4 governance
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; Prompt 18 checkpoint is `f5872a5`
- **Issue / task:** Member 2 Prompt 19; no ticket
- **Files changed:** `src/retainiq_prediction/model_approval.py`, `src/retainiq_prediction/model_promotion.py`, `src/retainiq_prediction/model_rollback.py`, `src/retainiq_prediction/__init__.py`, `tests/test_model_approval.py`, `tests/test_model_promotion.py`, `tests/test_model_rollback.py`, `docs/MEMBER2_MODEL_APPROVAL_PROMOTION_ROLLBACK.md`, `TEAM_LOG.md`
- **What changed:**
  - Added typed, append-only approval records with request idempotency, preserved `APPROVE`/`REJECT` rationale, immutable audit events, and a replaceable external authorization verifier. Caller role strings, booleans and synthetic verifier evidence fail closed for production approval.
  - Added separate promotion consideration/technical eligibility/activation checks and a process-local compare-and-swap active bundle reference with generation checks, prior-bundle history and explicit non-production limitations. No prediction pipeline mutation or automatic deployment is performed.
  - Added rollback request validation for authorized human actions, compatible approved targets, stale active-state rejection, process-local simulation, chain preservation and audit evidence. Added 30 synthetic structural governance scenarios and documented implemented versus unavailable production controls.
- **Why it changed:** Establish an explicit human-governed release boundary after candidate training/evaluation while preventing synthetic evidence, caller claims, stale pointers, changed artifacts and metadata-only statuses from activating or rolling back a model.
- **Contract / database / API impact:** No database, API, model-training, calibration, prediction-pipeline, Part 3, or dashboard behavior changed. New interfaces consume existing `ModelBundleMetadata` and frozen candidate-evaluation manifests. Member 1/backend must later provide trusted authorization, durable append-only audit, artifact integrity, deployment compatibility and durable atomic active-bundle storage.
- **Tests / verification:**
  - `.venv\Scripts\python.exe -m pytest -q tests/test_model_approval.py tests/test_model_promotion.py tests/test_model_rollback.py --basetemp .pytest-tmp-p19` — PASS — 30 tests passed.
  - `.venv\Scripts\python.exe -m pytest -q tests/test_model_registry.py tests/test_candidate_training.py tests/test_candidate_evaluation.py tests/test_model_approval.py tests/test_model_promotion.py tests/test_model_rollback.py --basetemp .pytest-tmp-p19` — PASS — 55 tests passed.
  - `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-p19` — PASS — 317 tests passed, 24 known SHAP warnings.
  - `.venv\Scripts\python.exe -c "import retainiq_prediction; ..."` — PASS — Python 3.14.4 and new governance exports imported.
  - `git diff --check` — PASS — no whitespace errors; only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Synthetic structural fixtures and process-local simulation only; no authorized production actor, dataset, artifact, deployment, model metric, retention result or ROI evidence.
- **Known issues / blockers:** The included audit and active pointer are not durable, distributed or production-safe. Real production activation/rollback remains blocked. Prompt 18's original 28 candidate-training/evaluation scenarios still require a final scenario-to-test coverage review; that review was not performed here.
- **Next action / handoff:** Member 1/backend should provide the trusted authorization and durable deployment/audit interfaces. Member 2 should perform the deferred Prompt 18 scenario coverage review before any real release integration.
- **Reviewer / pairing:** N/A

### 2026-10-10T07:02:28Z — Member 2 AI coding assistant — Multi-horizon LightGBM candidate

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous checkpoint is `72550fa`
- **Issue / task:** Member 2 Prompt 10; no ticket
- **Files changed:** `pyproject.toml`, `src/retainiq_prediction/lightgbm_model.py`, `src/retainiq_prediction/__init__.py`, `tests/test_lightgbm_model.py`, `docs/MEMBER2_LIGHTGBM_MODELS.md`, `TEAM_LOG.md`
- **What changed:**
  - Added the optional CPU LightGBM dependency and a reusable three-horizon training component with independent 7/14/30-day classifiers, existing feature allowlist reuse, mature TRAIN-mask filtering, optional VALIDATION-only early stopping, and explicit single-class/insufficient/dependency `NOT_READY` results.
  - Added uncalibrated-probability semantics, deterministic configuration, tenant scope, feature-order/preprocessing metadata, dataset readiness/provenance metadata, trusted-root artifact save/load, malformed-artifact checks, and 21 synthetic structural tests.
  - Added LightGBM documentation; preserved `IMPROVEMENT-001`, `IMPROVEMENT-002`, and `IMPROVEMENT-003` without changing their statuses or shared prediction contracts.
- **Why it changed:** Implement the primary model-training candidate while preserving chronological label maturity, untouched CALIBRATION/TEST periods, honest probability semantics, and the current evidence blocker.
- **Contract / database / API impact:** No database, API, shared prediction enum, production `PredictionOutput`, calibration, SHAP, decision, dashboard, or retraining behavior changed. Raw LightGBM scores remain separate from calibrated production forecasts.
- **Tests / verification:**
  - `.venv\Scripts\python.exe -m pytest -q tests/test_lightgbm_model.py --basetemp .pytest-tmp` — PASS — 21 tests passed, 0 skipped in 2.21s.
  - `.venv\Scripts\python.exe -m pytest -q tests/test_lightgbm_model.py tests/test_baselines.py --basetemp .pytest-tmp` — PASS — 36 tests passed, 0 skipped in 2.40s.
  - `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 132 tests passed, 0 skipped in 2.53s.
  - Package import and dependency version check — PASS — Python 3.14.4, NumPy 2.5.3, SciPy 1.18.1, scikit-learn 1.9.1, LightGBM 4.7.0, Pydantic 2.14.0, pytest 8.4.2.
  - `git diff --check` — PASS — no whitespace errors; Git emitted only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Explicitly synthetic fixtures and temporary internal artifacts only; no authorized dataset, calibration, benchmark metric, production model, churn performance, retention result, or ROI evidence. LightGBM is a primary candidate, not a claimed winner.
- **Known issues / blockers:** No authorized longitudinal dataset exists. Account-level multi-subscription semantics remain `IMPROVEMENT-002: NEEDS_TEAM_DECISION`. Calibration, horizon coherence, SHAP, real evaluation, and promotion governance remain deferred. Pickle artifacts are trusted-internal only.
- **Next action / handoff:** Member 1 must provide authorized lifecycle/billing data, source availability and correction timestamps, tenant authorization/provenance, observation coverage, and account-level churn policy before real training or evaluation.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:56:37Z — Member 2 AI coding assistant — Isolated ML baseline verification

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** `feat(member2): verify baseline models in isolated ML environment`
- **Issue / task:** Member 2 Prompt 09; no ticket
- **Files changed:** `.gitignore`, `pyproject.toml`, `src/retainiq_prediction/baselines.py`, `src/retainiq_prediction/__init__.py`, `tests/test_baselines.py`, `docs/MEMBER2_BASELINE_MODELS.md`, `docs/MEMBER2_IMPROVEMENT_BACKLOG.md`, `TEAM_LOG.md`
- **What changed:**
  - Added the project-local `.venv/` workflow and `ml` optional dependency (`scikit-learn>=1.7,<2`), with generated environments, caches, and egg-info ignored by Git; the global Python installation was not modified.
  - Fixed the baseline vectorizer to pass ordered numeric rows to scikit-learn, then verified independent 7/14/30-day Logistic Regression fitting, train-fitted imputation/scaling, mature-label filtering, test isolation, metadata, and trusted-root artifact save/load.
  - Added `IMPROVEMENT-003` for later rule-threshold validation and documented exact setup/dependency versions plus the pickle trusted-artifact restriction.
- **Why it changed:** Remove the dependency-related baseline verification gap and validate the existing synthetic comparison pipeline in an isolated, reproducible environment without claiming real model performance.
- **Contract / database / API impact:** No database, API, shared prediction enum, label policy, calibration, LightGBM, or production `PredictionOutput` change. Baseline outputs remain ranking scores or explicitly uncalibrated probabilities.
- **Tests / verification:**
  - `.venv\Scripts\python.exe -m pytest -q tests/test_baselines.py --basetemp .pytest-tmp` — PASS — 15 tests passed, 0 skipped in 2.37s.
  - `.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 111 tests passed, 0 skipped in 2.35s.
  - Package import check with `.venv\Scripts\python.exe` — PASS — imported package and reported `SKLEARN_AVAILABLE=True`.
  - `git diff --check` — PASS — no whitespace errors; Git emitted only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Synthetic fixtures only; no authorized dataset, production artifact, calibrated probability, empirical metric, retention result, or ROI evidence. Installed versions: Python 3.14.4, NumPy 2.5.3, SciPy 1.18.1, scikit-learn 1.9.1, Pydantic 2.14.0, pytest 8.4.2.
- **Known issues / blockers:** No authorized longitudinal dataset exists. Pickle artifacts are executable serialization and are restricted to validated trusted-root paths. Rule weights and alert thresholds remain provisional and unvalidated.
- **Next action / handoff:** Member 1 must provide authorized longitudinal data, canonical billing/lifecycle mappings, source provenance and account-level churn policy. Threshold validation and LightGBM comparison require development/validation data and remain deferred.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:49:46Z — Member 2 AI coding assistant — Rule and Logistic Regression baselines

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous temporal-splitting checkpoint is `09527dc`
- **Issue / task:** Member 2 Prompt 08; no ticket
- **Files changed:** `src/retainiq_prediction/baselines.py`, `src/retainiq_prediction/__init__.py`, `tests/test_baselines.py`, `docs/MEMBER2_BASELINE_MODELS.md`, `docs/MEMBER2_IMPROVEMENT_BACKLOG.md`, `TEAM_LOG.md`
- **What changed:**
  - Added versioned, configurable rule-based ranking scores using only point-in-time feature values and optional point-in-time payment-failure counts; missing usage is not treated as zero and payment failure is not treated as churn.
  - Added a reusable optional scikit-learn Logistic Regression component with independent 7/14/30-day fitting, TRAIN-only temporal masks, explicit numeric feature allowlist, train-fitted imputation/scaling, fixed random state, one-class/insufficient-data `NOT_READY` results, uncalibrated score labeling, and trusted-local artifact persistence.
  - Recorded `IMPROVEMENT-002` as an unresolved Member 1 + Member 2 multi-subscription churn-definition decision without changing `IMPROVEMENT-001` or existing label semantics.
- **Why it changed:** Provide honest comparison baselines before the future personalized multi-horizon LightGBM implementation while preserving temporal label maturity and the canonical prediction boundary.
- **Contract / database / API impact:** No database, API, shared prediction enum, label policy, or production `PredictionOutput` change. Baseline results remain separate from calibrated production forecasts. The optional Logistic Regression backend reports `NOT_READY` when scikit-learn is unavailable.
- **Tests / verification:**
  - `& C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q` — PASS — 106 tests passed, 5 skipped in 0.59s; skips are scikit-learn-dependent fit/persistence tests because the local environment does not provide scikit-learn.
  - `PYTHONPATH=src` package import check — PASS — imported baseline classes and reported `SKLEARN_AVAILABLE=False`.
  - `git diff --check` — PASS — no whitespace errors; Git emitted only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Synthetic baseline fixtures only; no authorized dataset, fitted Logistic Regression artifact, production probability, calibration, model metric, retention result, or ROI evidence. Rule thresholds are configurable operational assumptions, not validated performance claims.
- **Known issues / blockers:** scikit-learn is not installed in the current Python 3.14.4 environment, so real Logistic Regression fitting was not executed. No authorized longitudinal dataset exists. Member 1 must finalize canonical payment feature mapping, lifecycle/account churn semantics, provenance, and authorization before model readiness can change.
- **Next action / handoff:** Provide an isolated approved scikit-learn environment and authorized data, then rerun fitting and chronological evaluation before comparing against LightGBM. Keep `IMPROVEMENT-002` unresolved until the account-level policy is agreed.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:44:28Z — Member 2 AI coding assistant — Chronological dataset splitting

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous label-builder checkpoint is `fd9ae10`
- **Issue / task:** Member 2 Prompt 07; no ticket
- **Files changed:** `src/retainiq_prediction/temporal_splits.py`, `src/retainiq_prediction/__init__.py`, `tests/test_temporal_splits.py`, `docs/MEMBER2_TEMPORAL_SPLITTING.md`, `docs/MEMBER2_IMPROVEMENT_BACKLOG.md`, `TEAM_LOG.md`
- **What changed:**
  - Added deterministic timezone-aware TRAIN, VALIDATION, CALIBRATION, and TEST partitioning by prediction `as_of` using explicit half-open boundaries; all horizons for one snapshot remain together and duplicate snapshot assignments are rejected.
  - Added per-horizon supervised/evaluation masks, label-maturity enforcement using `evaluation_as_of` and an optional maturity gap, test-label evaluation isolation, account-overlap reporting, class/sample warnings, and a reproducible split manifest.
  - Added the temporal-splitting handoff documentation and persisted `IMPROVEMENT-001` for a future personalized-baseline ablation study; no model training or performance claims were added.
- **Why it changed:** Prevent temporal assignment and label-observation leakage before future 7/14/30-day model development, while preserving unknown labels and the existing churn-label semantics.
- **Contract / database / API impact:** No database or API schema changed. The splitter consumes existing `FeatureSnapshot`/`ChurnLabel` records and requires Member 1 to provide an authorized longitudinal dataset, canonical lifecycle mappings, availability/evaluation timestamps, coverage evidence, and account-level multi-subscription semantics.
- **Tests / verification:**
  - `& C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q` — PASS — 96 tests passed in 0.60s.
  - `& C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q tests/test_temporal_splits.py` — PASS — 14 tests passed in 0.35s.
  - `PYTHONPATH=src` package import check — PASS — imported `retainiq_prediction`, `TemporalSplitter`, and `TemporalSplitManifest`.
  - `git diff --check` — PASS — no whitespace errors reported; Git emitted only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Explicitly synthetic structural fixtures only; no authorized real dataset, training, model, metric, prediction, or ROI result. The manifest keeps real training readiness `BLOCKED` without an authorized dataset.
- **Known issues / blockers:** No authorized longitudinal dataset exists in the repository. Member 1 must finalize source availability/correction semantics, canonical field mappings, account-level churn policy, and authorization/provenance evidence before real training readiness can change.
- **Next action / handoff:** Member 1 should implement the real adapter and dataset evidence mapping; Member 2 can then replay the splitter on an authorized historical dataset before model work.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:08:15Z — Member 2 AI coding assistant — Repository documentation setup

- **Workstream:** Part 2 / Integration / Docs
- **Branch:** `feature/prediction-engine`
- **Commit subject:** `docs: set up prediction-engine repository documentation`
- **Issue / task:** Repository documentation setup; no ticket
- **Files changed:** `AGENTS.md`, `RetainIQ_v2_Complete_Requirements.md`, `TEAM_LOG.md`, `docs/RetainIQ_v2_Data_Foundation.md`, `docs/RetainIQ_v2_Part2_Prediction_Engine_Requirements.md`, `docs/RetainIQ_v2_Part3_Decision_Engine_Requirements.md`, `docs/RetainIQ_v2_Part4_Closed_Loop_Learning_and_Dashboard_Requirements.md`, `docs/MEMBER2_INTEGRATION_DEPENDENCIES.md`
- **What changed:**
  - Copied the supplied canonical requirements, team guidance, and Part 1–4 specifications into the repository without content changes; created `AGENTS.md` as an exact copy of the available `AGENT.md`.
  - Added the Member 2 integration dependency note covering confirmed prediction contracts, downstream handoffs, unresolved decisions, and blockers.
- **Why it changed:** Establish the repository documentation baseline and make Member 2’s cross-part dependencies explicit before implementation.
- **Contract / database / API impact:** No implementation or API/database changes. The canonical flat prediction payload and `prediction_id`/`prediction_run_id` distinction are documented as integration requirements.
- **Tests / verification:**
  - Source/destination SHA-256 comparison — PASS — copied documents match their Downloads originals.
  - Repository audit and `git diff --check` — PASS — clean formatting check; no implementation tests exist or were needed for documentation-only setup.
- **Data / model / ROI evidence:** N/A; no dataset, model, prediction, or ROI result was created.
- **Known issues / blockers:** Repository still has no backend, database, dependency manifest, tests, dataset, or Member 1 implementation. Account-level multi-subscription churn semantics and event-availability timestamp contract remain unresolved.
- **Next action / handoff:** Member 1 should provide the canonical data/API contract and dataset evidence gate; Member 2 can then implement time-safe labels/features and prediction services.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:12:43Z — Member 2 AI coding assistant — Minimal prediction contract foundation

- **Workstream:** Part 2 / Integration
- **Branch:** `feature/prediction-engine`
- **Commit subject:** `feat: add canonical prediction contract foundation`
- **Issue / task:** Member 2 Prompt 02; no ticket
- **Files changed:** `pyproject.toml`, `src/retainiq_prediction/__init__.py`, `src/retainiq_prediction/contracts.py`, `tests/test_prediction_contract.py`, `docs/MEMBER2_PREDICTION_CONTRACT.md`, `TEAM_LOG.md`
- **What changed:**
  - Added a minimal Python package with Pydantic v2 models for the canonical flat `PredictionOutput` payload and nested reliability, freshness, and non-quantified uncertainty contracts.
  - Added validation for status-dependent probabilities, cumulative horizon ordering, non-empty/distinct IDs, timezone-aware timestamps, documented enum values, and JSON round trips.
  - Added focused contract documentation and synthetic-only fixtures; no training, feature engineering, API, or database code was added.
- **Why it changed:** Establish the shared Part 2 prediction interface before implementing feature building or model inference.
- **Contract / database / API impact:** Defines the local validation contract for the integrated `prediction_id`/`prediction_run_id` distinction and flat `p_churn_7d`/`p_churn_14d`/`p_churn_30d` fields. No database or API implementation changed; unresolved cross-part questions remain documented.
- **Tests / verification:**
  - `python -m pytest -q` — PASS — 21 tests passed in 0.31s.
  - `git diff --check` — PASS — no whitespace errors.
  - Python/Pydantic/pytest environment check — PASS — Python 3.14.4, Pydantic 2.13.5, pytest 8.4.2.
- **Data / model / ROI evidence:** Synthetic contract fixtures only; no dataset, trained model, performance metric, prediction result, or ROI claim.
- **Known issues / blockers:** Member 1’s canonical data/API contract, authorized longitudinal dataset, account-level multi-subscription churn semantics, source-availability timestamp semantics, and attribution shape remain unresolved.
- **Next action / handoff:** Coordinate the unresolved contracts with Members 1 and 4, then implement time-safe features and labels only after the dataset evidence gate is available.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:17:45Z — Member 2 AI coding assistant — Historical dataset readiness gate

- **Workstream:** Part 2 / Integration
- **Branch:** `feature/prediction-engine`
- **Commit subject:** `feat: add historical dataset readiness gate`
- **Issue / task:** Member 2 Prompt 03; no ticket
- **Files changed:** `src/retainiq_prediction/dataset_readiness.py`, `src/retainiq_prediction/__init__.py`, `tests/test_dataset_readiness.py`, `docs/MEMBER2_DATASET_READINESS.md`, `TEAM_LOG.md`
- **What changed:**
  - Added a read-only adapter-based readiness validator that checks account identity, tenant mapping, events, lifecycle history, outcome timestamps, source availability, duplicates, observation coverage, provenance, and personalized-baseline evidence.
  - Added structured `PASS`/`PARTIAL`/`BLOCKED` reports with supported horizons, blockers, missing fields, quality issues, field-state evidence, and non-PII row counts.
  - Documented the Member 1 adapter boundary and the current project status: no dataset supplied, therefore `BLOCKED`.
- **Why it changed:** Prevent genuine 7/14/30-day model work from starting without timestamped, authorized, outcome-observable historical evidence.
- **Contract / database / API impact:** No database, ingestion, or API changes. The validator consumes a documented adapter view and does not create a competing schema. The default 28-day baseline span is an explicit configurable readiness heuristic, not a finalized model contract.
- **Tests / verification:**
  - `& C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q` — PASS — 29 tests passed in 0.31s.
  - Source import with `PYTHONPATH=src` and empty-adapter check — PASS — package imported and returned `BLOCKED`.
  - Initial `python -m pytest -q` / bare source import — NOT PASS — Windows Python app-execution alias was unavailable and the uninstalled `src` layout is not on `sys.path`; explicit interpreter plus `PYTHONPATH=src` was used for final verification.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Synthetic structural fixtures only; no real dataset, trained model, accuracy metric, prediction result, or ROI claim. The actual repository readiness status remains `BLOCKED`.
- **Known issues / blockers:** No authorized longitudinal dataset or `DATASET_CARD.md`; Member 1’s canonical adapter, source-availability semantics, multi-subscription churn policy, and outcome schema remain unavailable. The package is not installed into the interpreter environment; tests use the declared `src` path configuration.
- **Next action / handoff:** Member 1 should supply the canonical mapped records and provenance/evidence gate. Only after a real dataset passes should Member 2 implement features, labels, splits, or training.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:23:21Z — Member 2 AI coding assistant — Point-in-time adapter and eligibility foundation

- **Workstream:** Part 2 / Integration
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; working tree change only
- **Issue / task:** Member 2 Prompt 04; no ticket
- **Files changed:** `src/retainiq_prediction/point_in_time.py`, `src/retainiq_prediction/eligibility.py`, `src/retainiq_prediction/__init__.py`, `tests/test_point_in_time.py`, `tests/test_eligibility.py`, `docs/MEMBER2_POINT_IN_TIME_AND_ELIGIBILITY.md`, `TEAM_LOG.md`
- **What changed:**
  - Added a typed, replaceable in-memory point-in-time adapter with exact tenant/customer scoping, timezone-aware cutoff validation, event/effective-time filtering, configurable source-availability precedence, provenance preservation, and explicit exclusion limitations.
  - Added eligibility reconstruction for eligible, known cancellation, not eligible, and insufficient data states, including machine-readable reason codes, conservative lifecycle handling, payment-failure non-churn behavior, and explicit unresolved multi-subscription policy handling.
  - Added synthetic-only focused tests and documented the Member 1 input contract. No database, ingestion API, feature engineering, labels, model training, or prediction calculations were added.
- **Why it changed:** Establish the leakage-safe storage boundary and eligibility routing foundation before feature or label implementation.
- **Contract / database / API impact:** No database or API implementation changed. The adapter expects dated subscription, usage, and billing facts with source provenance and an availability/received timestamp when available. Availability precedence remains configurable pending Member 1 agreement.
- **Tests / verification:**
  - `& C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q` — PASS — 49 tests passed in 0.43s.
  - `PYTHONPATH=src` source import check — PASS — `import retainiq_prediction`.
  - `git diff --check` — PASS — no whitespace errors reported.
- **Data / model / ROI evidence:** Synthetic fixtures only; no dataset, feature set, labels, trained model, performance metric, prediction result, or ROI claim.
- **Known issues / blockers:** Member 1 must provide the real adapter/database mapping, source availability semantics, event availability timestamps, authoritative lifecycle history, account-level multi-subscription churn policy, and authorization boundary. Unknown availability is conservatively excluded and yields an explicit limitation.
- **Next action / handoff:** Agree the availability precedence and account-level subscription policy with Member 1, then connect the real adapter without changing the eligibility business logic.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:29:51Z — Member 2 AI coding assistant — Personalized behavioral feature foundation

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; local checkpoint is `37df5de`
- **Issue / task:** Member 2 Prompt 05; no ticket
- **Files changed:** `src/retainiq_prediction/feature_builder.py`, `src/retainiq_prediction/__init__.py`, `tests/test_feature_builder.py`, `docs/MEMBER2_FEATURE_ENGINEERING.md`, `TEAM_LOG.md`
- **What changed:**
  - Added a versioned `FeatureSnapshot` with typed feature values, point-in-time cutoff metadata, coverage/missingness quality fields, and source evidence references.
  - Added configurable session-event semantics and personalized four-week baseline features: 7/30-day sessions, inactivity days, recent trend, observed weeks, averages, deviations, ratio, variability, and explicit baseline availability status.
  - Added optional explicit usage-coverage evidence so confirmed zero activity is distinct from unknown or incomplete history. No cohort baseline, labels, model training, prediction calculation, cancellation feature, or churn outcome was added.
- **Why it changed:** Establish the first leakage-safe behavioral feature layer required before label building or model work.
- **Contract / database / API impact:** No database, API, or Member 1 source contract changed. The builder consumes `PointInTimeDataAdapter`; Member 1 must later supply canonical session semantics, source coverage evidence, and availability timestamps through a replaceable adapter boundary.
- **Tests / verification:**
  - `& C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q` — PASS — 62 tests passed in 0.37s.
  - `git diff --check` — NOT RUN after this uncommitted feature edit; the checkpoint staged check reported preserved requirements-document trailing whitespace and an existing blank line at EOF. No requirement documents were rewritten to hide those source formatting issues.
- **Data / model / ROI evidence:** Synthetic usage and coverage fixtures only; no real dataset, labels, trained model, prediction, performance metric, or ROI evidence.
- **Known issues / blockers:** Member 1 must confirm session event semantics, period-level usage coverage/completeness representation, availability precedence, and production adapter mapping. Personalized baselines remain unavailable for sparse or unobserved histories; no cohort fallback is implemented.
- **Next action / handoff:** Review the feature field names and coverage contract with Member 1, then connect the canonical adapter before implementing labels or models.
- **Reviewer / pairing:** N/A

### 2026-10-10T06:38:33Z — Member 2 AI coding assistant — 7/14/30-day churn label builder

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous feature checkpoint is `f82a290`
- **Issue / task:** Member 2 Prompt 06; no ticket
- **Files changed:** `src/retainiq_prediction/label_builder.py`, `src/retainiq_prediction/__init__.py`, `tests/test_label_builder.py`, `docs/MEMBER2_LABEL_ENGINEERING.md`, `TEAM_LOG.md`
- **What changed:**
  - Added typed/versioned `ChurnLabel` records for independent 7-, 14-, and 30-day horizons with explicit positive, negative, unknown, excluded, and unsupported statuses.
  - Added a replaceable lifecycle/outcome adapter and synthetic in-memory implementation that separates prediction `as_of` from later `evaluation_as_of`, enforces source availability, preserves evidence references, and reports late/unknown coverage.
  - Implemented qualifying effective voluntary cancellation, non-renewal, and finalized involuntary termination semantics; payment failures, requests, inactivity, and missing events are not churn by themselves.
  - Added conservative known-cancellation, already-terminated, right-censoring, multi-subscription, boundary, cross-tenant, late-outcome, and conflicting-lifecycle handling. No model training, temporal splitting, prediction API, or feature mutation was added.
- **Why it changed:** Establish reproducible supervised-target generation without allowing future outcome evidence to enter prediction-time features or prospective eligibility.
- **Contract / database / API impact:** No database or API schema changed. Member 1 can implement `LifecycleOutcomeAdapter` against canonical lifecycle storage and must supply effective timestamps, availability/received timestamps, account mapping, stable IDs, and observation coverage.
- **Tests / verification:**
  - `& C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q` — PASS — 82 tests passed in 0.40s.
  - `PYTHONPATH=src` package import check — PASS — imported `retainiq_prediction` and label enums.
  - `git diff --check` — PASS — no whitespace errors reported; Git emitted only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Synthetic lifecycle and observation fixtures only; no real dataset, labels from production data, trained model, prediction, performance metric, or ROI evidence.
- **Known issues / blockers:** Member 1 must finalize canonical churn event mappings, source-availability precedence, observation-coverage semantics, account-level multi-subscription churn policy, source-correction handling, authorization boundary, and the real adapter. No authorized longitudinal dataset exists in the repository.
- **Next action / handoff:** Review label policy and lifecycle/coverage mappings with Member 1 before allowing positive/negative labels into supervised training.
- **Reviewer / pairing:** N/A

### 2026-10-10T13:44:03Z — Member 1 / Data & Backend Engineer — Complete Synthetic SaaS v1.2 remediation

- **Workstream:** Part 1 / Data Foundation, Synthetic QA, Integration & Docs
- **Branch:** `member1`
- **Commit subject:** `feat: deliver verified synthetic SaaS v1.2 handoff`
- **Issue / task:** Prompt 05C — complete generated synthetic dataset remediation and Member 2 handoff.
- **Files changed:** `retaniq/data_foundation.py`, `retaniq/synthetic/`, `migrations/004_dataset_identity_and_observation_coverage.sql`, `examples/member2_synthetic_smoke.py`, related tests, `DATASET_CARD.md`, `README.md`, `docs/SYNTHETIC_SAAS_DATASET.md`, `docs/HYBRID_DATASET_STRATEGY.md`, both Member 2 handoffs, and this log.
- **What changed:**
  - Added v1.2 daily usage aggregates, per-account observation coverage, dataset identity binding, horizon/maturity evidence, calendar billing periods, repeated risk episodes/reactivation, source-verified and proxy scenario reporting, and bounded resumable canonical imports with checkpoints.
  - Added a one-time tenant/source-scoped Member 2 reader and read-only end-to-end smoke; retained canonical normalization, source/category authorization, subscription ownership, idempotency, and as-of visibility checks.
  - Generated and audited immutable QUICK/STANDARD/FULL artifacts outside Git; documented exact IDs, hashes, counts, timings, label/split evidence, scenario coverage and synthetic limitations, while preserving real-data isolation.
- **Why it changed:** Prompt 05B identified shortcomings in daily usage evidence, source coverage, churn episode fidelity, outcome maturity, and import scalability. This completes the authorized v1.2 remediation and provides a measured synthetic-only handoff.
- **Contract / database / API impact:** Added migration 004 for isolated synthetic dataset identity, source observation coverage, and resumable import checkpoints. Added authorized dataset identity/coverage reads and batched canonical writes. Event ingestion still uses canonical validation and tenant/source/category grants; Member 2 owns production feature and label builders.
- **Tests / verification:**
  - `python -m unittest discover -s tests -v` — **PASS** — 64 tests in 13.441 seconds.
  - Fresh `validate_dataset(FULL)` — **PASS** — no errors or warnings. QUICK and STANDARD independent validators also passed with no errors or warnings.
  - QUICK, STANDARD, FULL canonical imports — **VERIFIED** — 16,351 / 239,721 / 1,547,420 events and 32,697 / 491,223 / 3,263,358 coverage rows accepted; FULL import took 478.985 seconds. Replay idempotency and cross-tenant denial passed on the prior checks.
  - Member 2 smoke — **PASS** for QUICK, STANDARD, and FULL. FULL confirmed identity and exact source/purpose grants, as-of usage features, separated future outcome oracle, churn visibility, and ineligible-account exclusion.
  - FULL SQLite read-only integrity — **PASS** — counts match manifest, one dataset identity, zero foreign-key violations; database size 3,616,260,096 bytes.
  - `python -m py_compile` on changed Python modules, synthetic CLI help, reader CLI help, and `git diff --check` — **PASS**.
- **Data / model / ROI evidence:** Synthetic SaaS v1.2 only; seed 2026; 20,000 accounts across four tenants; 24 months; 48 measured scenario categories with `SOURCE_VERIFIED` versus `SOURCE_PROXY` distinctions. No model was trained, no model metric or ROI was computed, no real customer data was read, and no KKBox file was changed.
- **Known issues / blockers:** Synthetic realism remains limited: past-due termination (4,006 accounts) is much more common than late recovery (596); nonrenewal (157) and voluntary cancellation (429) are sparse; source-history sufficiency varies by tenant; and repeated weekly cutoffs are correlated. SQLite is a local reference. None of this establishes real-world predictive performance. FULL import took about eight minutes and its SQLite file is about 3.62 GB.
- **Next action / handoff:** Member 2 may implement point-in-time feature/label pipelines and synthetic-only rule/logistic/LightGBM comparison using the exact dataset identity and chronological stages in `docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`. Keep real KKBox status `NOT_VALIDATED`; do not present synthetic evaluation as real-world evidence.
- **Reviewer / pairing:** N/A

### 2026-10-10T11:15:05Z — Member 1 / Data & Backend Engineer — Design Synthetic SaaS v1.2 remediation

- **Workstream:** Part 1 / Data Foundation & Integration
- **Branch:** `member1`
- **Commit subject:** `docs: design synthetic SaaS v1.2 remediation`
- **Issue / task:** Prompt 05C — source-backed v1.2 dataset and Member 2 handoff.
- **Files changed:** `docs/superpowers/specs/2026-10-10-synthetic-saas-v1-2-design.md`, `docs/superpowers/plans/2026-10-10-synthetic-saas-v1-2.md`, `TEAM_LOG.md`
- **What changed:** Recorded the implementation design and staged plan for daily usage semantics, interval coverage, lifecycle fidelity, dataset-bound storage, validated batch import, independent QA, and authorized handoff.
- **Why it changed:** Prompt 05B found source-history and import-readiness gaps; Prompt 05C authorizes a complete, versioned remediation.
- **Contract / database / API impact:** None in this design-only commit. Existing shared event, prediction, label, MRR, and authorization contracts remain unchanged.
- **Tests / verification:** `git diff --check` — **PASS** for tracked files; plan/spec placeholder scan — **PASS**. No code tests run because this commit contains design and planning documents only.
- **Data / model / ROI evidence:** No data generated or modified; no model, performance, or ROI evidence. Synthetic design only; KKBox remains isolated.
- **Known issues / blockers:** Part 4 requirements file is not present in the workspace; the complete requirements and Parts 1–3 contracts are available. Implementation and all data gates remain pending.
- **Next action / handoff:** Implement the approved Prompt 05C scope with test-first regressions, regenerate all profiles, import STANDARD, and verify the handoff before reporting readiness.
- **Reviewer / pairing:** N/A

### 2026-10-10T10:25:53Z — Member 1 / Data & Backend Engineer — Synthetic SaaS dataset foundation

- **Workstream:** Part 1 / Data Foundation, Integration & Docs
- **Branch:** `member1`
- **Commit subject:** `feat: add synthetic SaaS dataset foundation`
- **Issue / task:** Prompt 05 — hybrid dataset foundation and advanced synthetic SaaS generator.
- **Files changed:** `README.md`, `TEAM_LOG.md`, `configs/synthetic_saas.json`, `docs/HYBRID_DATASET_STRATEGY.md`, `docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`, `docs/SYNTHETIC_SAAS_DATASET.md`, `examples/member2_synthetic_as_of_history.py`, `retaniq/data_foundation.py`, `retaniq/synthetic/__init__.py`, `retaniq/synthetic/__main__.py`, `retaniq/synthetic/canonical_adapter.py`, `retaniq/synthetic/config.py`, `retaniq/synthetic/generator.py`, `retaniq/synthetic/validator.py`, `tests/test_synthetic_generator.py`, `tests/test_synthetic_integration.py`
- **What changed:**
  - Added deterministic QUICK/STANDARD/FULL/STRESS configurations, per-account stochastic lifecycle state, four tenant archetypes, streamed linked customer/plan/identity/usage/billing/subscription/coverage exports, effective churn and reactivation events, measured overlapping scenario coverage, chronological split guidance, isolated label-oracle and adversarial fixtures, and stable manifests with SHA-256 hashes.
  - Added a synthetic CLI and canonical adapter that provisions tenant/category-scoped integrations, maps exact source identities, imports through `ingest_event`, verifies historical snapshots and tenant denial, and can repeat every event to prove idempotency without persisting credentials.
  - Added bounded streaming validation of schema, identity, source category, timestamps, canonical allowlists, currency/money, subscription ownership, counts, hashes, target leakage and synthetic provenance. Source-outage events become available after simulated reconnection.
  - Fixed feature snapshot IDs to use the canonical ID alphabet; `token_urlsafe` could intermittently generate `_` and break a later prediction link.
- **Why it changed:** RetainIQ needed a complete isolated synthetic SaaS dataset family for end-to-end demonstration while preserving the KKBox `NOT_SUITABLE_FOR_REQUIRED_TARGET` conclusion and all current Member 1 contracts.
- **Contract / database / API impact:** No migration, HTTP endpoint, event type, attribute allowlist, target policy, prediction interface or money rule changed. New API surface is the `retaniq.synthetic` Python/CLI package. Generated data stays outside Git under the user's private directory. Member 2 receives lifecycle/coverage evidence and an authorized read example; Member 2 still owns production features, 7/14/30 labels, models, calibration and evaluation. Member 3/4 receive dated MRR-compatible subscription facts, billing/usage evidence, and source/timeline provenance, with no predictions, human decisions, causal uplift or saved-revenue claims.
- **Tests / verification:**
  - `python -m unittest discover -s tests -v` — **PASS** — 51 tests in 10.188 seconds, including deterministic generation, seed variation, identity/time/leakage validation, horizon oracle semantics, canonical import, idempotency, historical reads and cross-tenant denial.
  - `python -m compileall -q retaniq tests examples`, `python -m retaniq.synthetic --help`, `git diff --check` — **PASS**.
  - `python -m retaniq.synthetic generate/validate --profile quick --seed 2026` — **PASS** — 200 accounts, 4 tenants, 4,598 canonical events; validator returned zero errors and warnings.
  - `python -m retaniq.synthetic import --profile quick --db ...\\quick-v1.1.sqlite3 --verify-idempotency` — **PASS** — 4,598 accepted, 4,598 duplicate on repeat, 12 historical snapshots, cross-tenant denial verified, 129.698 seconds.
  - `python -m retaniq.synthetic generate/validate --profile standard --seed 2026` — **PASS** — 3,000 accounts, 4 tenants, 69,594 canonical events; validator returned zero errors and warnings. Canonical STANDARD import was **NOT RUN** because the dependency-free reference path opens a transaction per event and QUICK took 129.698 seconds for two passes; importing 69,594 rows was not needed to establish the exercised contract.
  - `python -m retaniq.synthetic generate/validate --profile full --seed 2026` — **PASS** — 20,000 accounts, 4 tenants, 465,253 canonical events, 322,924,069 bytes; generation 44.729 seconds and validation 21.249 seconds with zero errors and warnings.
- **Data / model / ROI evidence:** Explicitly synthetic data only. Final generator version `synthetic-saas-v1.1`; seed 2026; default period 2024-10-01 through 2026-09-30. No model was trained, no performance metric or causal effect was computed, and no KKBox file or real dataset was read or modified.
- **Known issues / blockers:** Member 2 label materialization, feature building, model fitting/calibration and untouched-test evaluation remain unimplemented, so synthetic model-training and end-to-end product readiness remain conditional. SQLite remains a local reference rather than production PostgreSQL. STANDARD canonical import was not executed because the current per-event transaction path is too slow for a routine local verification run.
- **Next action / handoff:** Member 2 should use the exact final manifest and `MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`, provision an exact-source analyst principal, materialize point-in-time features/labels, and run independent chronological model comparison. Member 3/4 should consume actual later predictions and decisions without presenting generated outcomes as causal retention effects.
- **Reviewer / pairing:** N/A

### 2026-10-10T08:39:07Z — Member 1 / Data & Backend Engineer — Scope model writes and source event categories

- **Workstream:** Part 1 / Data Foundation & Core Backend
- **Branch:** `member1`
- **Commit subject:** `fix: scope model artifact writes and event categories`
- **Issue / task:** Complete the Prompt 03B integration authorization remediation.
- **Files changed:** `README.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, `docs/MEMBER1_TO_MEMBER2_DATA_HANDOFF.md`, `examples/member2_as_of_history.py`, `migrations/003_integration_event_categories.sql`, `retaniq/__main__.py`, `retaniq/api.py`, `retaniq/data_foundation.py`, `tests/test_data_foundation.py`, `TEAM_LOG.md`
- **What changed:**
  - Required the explicit `model_artifact_write` purpose and `analyst` role for service-principal feature/label/prediction writes; source integration writes now require a customer mapping through that token's own source. Added tests for denied cross-source/cross-tenant writes and successful authorized multi-source history plus persistence.
  - Added migration 003 for explicit usage/billing/subscription category grants, legacy observed-category backfill, usage-only fallback for unused integrations, and trusted local category-grant replacement. Ingestion and HTTP return a safe forbidden error before canonical event persistence for ungranted categories.
  - Preserved category grants during mapping-version refresh. Categorical storage now rejects long digit-bearing identifiers after punctuation normalization and applies finite tier/event enums. Updated the synthetic example to request its required categories explicitly.
- **Why it changed:** The audit found that same-tenant source mappings did not constrain ML writers, integrations could submit event categories outside their intended source role, and punctuation could obscure card/contact identifiers in categorical strings.
- **Contract / database / API impact:** Migration 003 adds `integration_event_categories`; canonical event, feature, label, prediction fields and IDs are unchanged. New integrations default to usage-only. Migration preserves categories evidenced in legacy canonical events; any unobserved category requires a trusted operator grant. `create-integration` accepts repeated `--category`; `set-integration-categories` replaces grants; HTTP ingestion returns 403 `event_category_not_authorized`. Member 2 must provision the exact-source `analyst` principal with `retention_inference` and `model_artifact_write` for multi-source persistence. No Member 2 feature/label/model or Member 3 decision logic was changed.
- **Tests / verification:**
  - `python -m unittest discover -s tests -p test_data_foundation.py -v` — **PASS** — 44 tests, including prior Prompt 03 coverage and new authorization/category/sensitive-value regressions.
  - `python -m unittest discover -s tests -v` — **PASS** — 45 tests; all test fixtures are synthetic.
  - `python -m unittest discover -s tests -p test_member2_handoff.py -v` — **PASS** — 1 synthetic point-in-time handoff test.
  - `python -m examples.member2_as_of_history` — **PASS** — synthetic eligible account, cutoff-limited usage, no labels or probabilities.
  - `python -m compileall -q retaniq tests examples`, `python -m retaniq --help`, `git diff --check` — **PASS**. No configured linter or type checker exists.
  - Fresh-schema `PRAGMA foreign_key_check` — **PASS**, 0 violations; upgrade regression checks version-1 history through migrations 002–003, records applied versions, and checks foreign keys.
- **Data / model / ROI evidence:** Synthetic tests/example only. `DATASET_CARD.md` remains `NOT_READY`; no genuine 7/14/30 labels, model fit, or predictive evaluation is claimed.
- **Known issues / blockers:** SQLite still does not meet the PostgreSQL architecture requirement. Existing integrations whose earlier history did not evidence a needed category require a trusted local category update. Real-source authorization/acquisition and coverage remain unverified.
- **Next action / handoff:** Member 2 provisions the narrow multi-source writer with the exact existing source grants and calls the shared as-of and artifact-storage methods. Project owner must authorize a genuine longitudinal source before label feasibility or training can be evaluated.
- **Reviewer / pairing:** N/A

### 2026-10-10T08:17:17Z — Member 1 / Data & Backend Engineer — Security and temporal integrity remediation

- **Workstream:** Part 1 / Data Foundation & Core Backend
- **Branch:** `member1`
- **Commit subject:** `fix: enforce source and temporal security boundaries`
- **Issue / task:** Remediate Member 1 source authorization, sensitive storage, subscription ownership, historical eligibility, and integration-health audit findings.
- **Files changed:** `README.md`, `TEAM_LOG.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, `docs/MEMBER1_TO_MEMBER2_DATA_HANDOFF.md`, `migrations/002_authorized_services_and_subscription_owners.sql`, `retaniq/__main__.py`, `retaniq/api.py`, `retaniq/data_foundation.py`, `retaniq/importer.py`, `tests/test_data_foundation.py`
- **What changed:**
  - Limited integration reads, snapshots, eligible-account enumeration and replay to the integration source; account snapshots/enumeration now also require a canonical identity mapping from at least one authorized source. Added separately provisioned tenant/service/source/purpose/role grants for trusted internal multi-source reads.
  - Constrained feature and explanation values to numeric/boolean data and bounded categorical fields, restricted reliability reasons to stable safe codes, and added sensitive-value checks.
  - Added append-only subscription ownership claims and composite tenant/subscription/customer foreign keys. Same-tenant cross-customer claims fail before canonical event insertion; the projection no longer changes owners. Legacy conflicting owners stop migration rather than being guessed.
  - Made historical eligibility depend on dated, source-backed subscription events instead of the mutable undated `customers.account_status`. Added the role/purpose/source-scoped `GET /v1/admin/integrations` health read for operators/admins.
- **Why it changed:** The audit found cross-source customer probing, unbounded feature/explanation strings, mutable subscription ownership, retroactive account status effects, and no authorized tenant-level integration-health view.
- **Contract / database / API impact:** Migration 002 adds service-principal and subscription-owner tables and rebuilds dependent subscription/billing tables with ownership FKs. As-of read helpers accept a new service-principal type; account-specific reads require identity mappings from granted sources. `GET /v1/admin/integrations` is additive; existing integration health and prediction/label fields remain unchanged. Member 2 must use safe reason codes and an explicitly granted service principal for cross-source histories. No dashboard or Member 2/3 logic was added.
- **Tests / verification:**
  - `python -m unittest discover -s tests -v` — **PASS** — 39 tests; fixtures are synthetic.
  - Focused source-scope, customer-mapping probe, feature/explanation safety, subscription-owner collision, historical status, operator-health, and schema-upgrade regression tests — **PASS** — 1 each.
  - `python -m compileall -q retaniq tests examples` — **PASS**.
  - `python -m examples.member2_as_of_history` — **PASS** — synthetic handoff only; no labels or probabilities.
  - `python -m retaniq --help` — **PASS** — CLI includes local service-principal provisioning.
  - `git diff --check` — **PASS** — no whitespace errors; Git reported LF/CRLF conversion notices.
  - No repository linter or type-checker configuration was found.
- **Data / model / ROI evidence:** Synthetic fixtures only. `DATASET_CARD.md` remains `NOT_READY`; no real historical data, genuine 7/14/30 labels, model readiness, or ROI evidence is claimed.
- **Known issues / blockers:** SQLite remains in use and does not satisfy the integrated PostgreSQL requirement. No production TLS, managed encryption, or external identity provider was verified. Account-level suspension/closure still lacks a dated source-backed lifecycle contract. Real-data and Member 2 training readiness remain blocked.
- **Next action / handoff:** Member 2 provisions a service principal with only the required source/purpose grants, uses the as-of APIs, and maps descriptive reliability text to stable reason codes. Member 4 may use the new operator health endpoint. Project owners still need to authorize a genuine historical dataset before training work.
- **Reviewer / pairing:** N/A

### 2026-10-10T07:41:34Z — Member 1 / Data & Backend Engineer — Real dataset gate and Member 2 handoff

- **Workstream:** Part 1 / Data Foundation & Core Backend
- **Branch:** feature/data-foundation
- **Commit subject:** feat(data): add evidence-backed dataset handoff
- **Issue / task:** Investigate the unresolved real historical dataset gate and complete the Member 1 → Member 2 data handoff.
- **Files changed:** DATASET_CARD.md, docs/MEMBER1_TO_MEMBER2_DATA_HANDOFF.md, docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md, docs/superpowers/plans/2026-10-10-real-dataset-handoff.md, examples/__init__.py, examples/member2_as_of_history.py, tests/test_member2_handoff.py, TEAM_LOG.md
- **What changed:**
  - Compared publicly documented dataset candidates and their source terms. KKBox is technically closest, but terms were not accepted, project eligibility was not verified, and no participant-authorized files were obtained; static and synthetic alternatives do not satisfy the temporal subscription target.
  - Expanded the dataset card with per-candidate feasibility, acquisition results, unmeasured coverage, and the NOT_READY decision.
  - Added a temporary-SQLite synthetic example and test that use existing Member 1 APIs to load one eligible account at a point-in-time cutoff while excluding a later event.
  - Added Member 2 handoff and requirement-by-requirement compliance documents. No Member 2 implementation or canonical schema was changed.
- **Why it changed:** Member 2 cannot responsibly build or evaluate genuine 7/14/30-day outcomes until source authorization, dated lifecycle facts, source availability, and observation coverage are established.
- **Contract / database / API impact:** No schema or production API behavior change. The example exercises existing ingestion, identity mapping, eligibility and as-of query helpers. Compliance records that current storage remains SQLite and does not meet the integrated PostgreSQL requirement.
- **Tests / verification:**
  - python -m unittest discover -s tests -p test_member2_handoff.py -v — PASS — 1 synthetic handoff test.
  - python -m examples.member2_as_of_history — PASS — one synthetic eligible account; post-cutoff usage absent; no label or probability.
  - python -m unittest discover -s tests -v — PASS — 32 tests; all data fixtures synthetic.
  - python -m compileall -q retaniq tests examples — PASS.
  - python -m retaniq --help — PASS.
  - git diff --check — PASS — no whitespace errors; Git emitted line-ending conversion notices for modified Markdown files.
  - Get-Command kaggle -ErrorAction SilentlyContinue and Python find_spec('kaggle') — no executable/package present. No dataset download was attempted.
- **Data / model / ROI evidence:** Zero real records imported; no source file was available for local coverage measurement. Synthetic engineering example only. No labels, model, predictive performance, or ROI evidence generated.
- **Known issues / blockers:** Real dataset authorization/access and source coverage remain unresolved; genuine 7/14/30 labels and training readiness are blocked. The local prototype uses SQLite rather than PostgreSQL.
- **Next action / handoff:** Project owner to confirm source permission and provide an authorized longitudinal dataset. Then inspect and measure the files before implementing a reviewed canonical adapter; Member 2 owns feature/label construction and model evaluation.
- **Reviewer / pairing:** N/A


### 2026-10-10T07:28:13Z — Member 1 / Data & Backend Engineer — Enforce point-in-time and purpose data contracts

- **Workstream:** Part 1 / Data Foundation & Core Backend
- **Branch:** `feature/data-foundation`
- **Commit subject:** `fix(data): enforce point-in-time and purpose data contracts`
- **Issue / task:** Close additional findings from the read-only review of the Member 1 data foundation.
- **Files changed:** `retaniq/data_foundation.py`, `tests/test_data_foundation.py`, `README.md`, `TEAM_LOG.md`
- **What changed:**
  - Rejected predictions whose source-availability cutoff is later than the prediction's `as_of` time.
  - Required `billing_valuation` scope to store financial valuation fields in feature snapshots and prediction explanations.
  - Rejected contact and credential values, sensitive key/value fragments, control characters and overlong text in reliability reasons.
- **Why it changed:** Review identified point-in-time leakage, financial data stored by retention-only integrations, and unsafe free-text reliability reasons; follow-up checks expanded contact and credential labels covered by sanitization.
- **Contract / database / API impact:** Prediction and snapshot write contracts are stricter; retention-only consumers can still store non-financial features and explainers. No schema change.
- **Tests / verification:**
  - `python -m unittest discover -s tests -v` — PASS — 31 tests; synthetic fixtures only.
  - `python -m compileall -q retaniq tests` — PASS.
  - `python -m retaniq --help` — PASS.
  - `git diff --check` — PASS — only Git line-ending normalization notices.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only. No real dataset, model, churn, or ROI evidence was used or generated; dataset gate remains `NOT_READY`.
- **Known issues / blockers:** The local prototype still uses SQLite without production encryption/TLS/deployment controls or a PostgreSQL adapter; authorized historical data remains unavailable.
- **Next action / handoff:** Member 2 may persist valuation-bearing features only through a principal with `billing_valuation`; prediction builders must use no source data later than the declared `as_of`.
- **Reviewer / pairing:** Read-only code review; PIT, purpose-gating, and reliability-reason findings corrected.

### 2026-10-10T07:16:26Z — Member 1 / Data & Backend Engineer — Enforce purpose and valuation contracts

- **Workstream:** Part 1 / Data Foundation & Core Backend
- **Branch:** `feature/data-foundation`
- **Commit subject:** `fix(data): enforce purpose and valuation contracts`
- **Issue / task:** Follow-up to the read-only review of the Member 1 data foundation commit
- **Files changed:** `retaniq/data_foundation.py`, `retaniq/api.py`, `retaniq/currency_codes.py`, `tests/test_data_foundation.py`, `README.md`, `TEAM_LOG.md`
- **What changed:**
  - Enforced purpose scopes on data reads and feature/label/prediction writes. Retention-only views preserve usage and billing status while redacting monetary fields; MRR and pricing fields require `billing_valuation`. Purpose failures return 403.
  - Required positive churn-label observation to cover the outcome time and validated linked feature snapshots against tenant/account/cutoff/version.
  - Bundled and enforced the official ISO 4217 List One code snapshot published 2026-09-17, excluding reserved test/no-currency codes.
- **Why it changed:** A read-only code review identified purpose-scope, outcome-coverage, snapshot-linkage, and currency-validation contract gaps.
- **Contract / database / API impact:** Read helpers now apply purpose-specific filtering. Part 2 can read lifecycle and usage data under `retention_inference` without seeing prices or MRR; Part 3 valuation requires both `retention_inference` and `billing_valuation`. No schema change.
- **Tests / verification:**
  - `python -m unittest discover -s tests -v` — PASS — 31 tests; synthetic fixtures only.
  - `python -m compileall -q retaniq tests` — PASS.
  - `python -m retaniq --help` — PASS.
  - `git diff --check` — PASS — only Git line-ending normalization notices.
  - Bundled ISO code set compared with the SIX List One XML snapshot — PASS — exact match after excluding `XTS` and `XXX`.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only. No real dataset, model, churn, or ROI evidence was used or generated; dataset gate remains `NOT_READY`.
- **Known issues / blockers:** The local prototype still uses SQLite without production encryption/TLS/deployment controls or a PostgreSQL adapter; authorized historical data remains unavailable.
- **Next action / handoff:** Member 2 can use retention-only reads without valuation fields. Member 3 needs an integration granted both retention and billing valuation. Refresh the bundled ISO list when SIX publishes a new List One snapshot.
- **Reviewer / pairing:** Read-only code review; four actionable findings corrected.

### 2026-10-10T07:05:21Z — Member 1 / Data & Backend Engineer — Tenant-scoped data foundation

- **Workstream:** Part 1 / Data Foundation & Core Backend
- **Branch:** `feature/data-foundation`
- **Commit subject:** `feat(data): add tenant-scoped canonical data foundation`
- **Issue / task:** Member 1 workstream from the supplied RetainIQ v2 requirements
- **Files changed:** `retaniq/data_foundation.py`, `retaniq/api.py`, `retaniq/importer.py`, `retaniq/__main__.py`, `retaniq/__init__.py`, `migrations/001_data_foundation.sql`, `tests/test_data_foundation.py`, `DATASET_CARD.md`, `README.md`, `.gitignore`, `docs/superpowers/plans/2026-10-10-data-foundation.md`, `TEAM_LOG.md`
- **What changed:**
  - Added tenant/source/purpose-scoped bearer authentication, explicit account identity mapping, allowlisted/minimized ingestion, safe error reporting, and idempotent event storage for usage, billing, and subscriptions.
  - Added append-only subscription history and availability-aware as-of access, silent-account eligibility enumeration, versioned minor-unit MRR, CSV import/replay, integration health, and shared feature/7/14/30 label/unified prediction storage contracts.
  - Added SQLite schema, API/CLI/data handoff documentation, and a dataset card that marks evidence `NOT_READY`.
- **Why it changed:** The checkout contained only a placeholder README and no backend, tests, migrations, or data. This supplies the Part 1 contract without duplicating Part 2 label/model logic or Part 3 decision rules.
- **Contract / database / API impact:** Added the SQLite migration and authenticated `POST /v1/ingest/events` / `GET /v1/integrations`. Tenant IDs come from authenticated server context. Canonical prediction storage keeps `prediction_id` separate from `prediction_run_id` and stores all three horizons in one row. Member 2 should use the documented as-of/account helpers; Member 3 should use the dated MRR/currency/status valuation. The migration is a local SQLite implementation, not a PostgreSQL deployment migration.
- **Tests / verification:**
  - `python -m unittest discover -s tests -v` — PASS — 27 tests; synthetic fixtures only.
  - `python -m compileall -q retaniq tests` — PASS.
  - `python -m retaniq --help` — PASS.
  - `git diff --check` — PASS — no whitespace errors; Git reported only the README LF-to-CRLF normalization warning.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only. No real dataset was present; no model, churn, or ROI evidence was generated. Dataset gate remains `NOT_READY`.
- **Known issues / blockers:** No authorized historical dataset/license, managed encrypted database, TLS termination, PostgreSQL adapter, external identity provider, or scheduled daily worker exists in this checkout. Currency validation checks three-uppercase-letter syntax, not full ISO registry membership.
- **Next action / handoff:** Member 2 can consume tenant-scoped point-in-time histories and the shared feature/label/prediction contracts. Member 3 can consume as-of MRR, currency, valuation time, and factual billing/usage references. The team must verify dataset provenance and provision production storage/security before real scoring.
- **Reviewer / pairing:** N/A

## 5. Team workstream directory — fill in before parallel development

| Workstream | Member / handle | Scope | Current handoff |
|---|---|---|---|
| Part 1 — Data Foundation | _Unassigned_ | Historical import, Push API, data normalization, tenant/security, MRR | Canonical events and feature inputs |
| Part 2 — Prediction | _Unassigned_ | 7/14/30 labels, features, calibration, reliability and evaluation | Versioned `prediction_id` payload |
| Part 3 — Decisions | _Unassigned_ | Routing, action catalog, budget/capacity, human approvals | Case and human event history |
| Part 4 — Feedback & Dashboard | _Unassigned_ | Mature outcomes, evaluation, model governance, timeline, analytics | Feedback and manager dashboard |
| QA / Integration / Demo | _Unassigned_ | Cross-part contracts, replay, leakage/security tests, judge demo | Reproducible end-to-end proof |

Members may cover several workstreams. Update assignments through a logged commit.

### 2026-10-10T07:16:47Z — Member 2 AI coding assistant — Calibration and horizon coherence foundation

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous LightGBM checkpoint is `f1999f4`
- **Issue / task:** Member 2 Prompt 11; no ticket
- **Files changed:** `src/retainiq_prediction/calibration.py`, `src/retainiq_prediction/horizon_coherence.py`, `src/retainiq_prediction/__init__.py`, `tests/test_calibration.py`, `tests/test_horizon_coherence.py`, `docs/MEMBER2_CALIBRATION_AND_COHERENCE.md`, `TEAM_LOG.md`
- **What changed:**
  - Added independent sigmoid/Platt calibration for 7-, 14-, and 30-day raw LightGBM probabilities. Each horizon reads only mature, confirmed labels from the CALIBRATION partition; VALIDATION and TEST are excluded from fitting.
  - Added versioned calibration metadata, finite/bounded calibrated outputs, compatibility checks, trusted-root artifact persistence, and diagnostics for raw/calibrated/optional post-coherence Brier scores plus a calibration table.
  - Added explicit cumulative-max horizon coherence over complete compatible three-horizon outputs, preserving original probabilities and adjustment metadata. Added readiness reporting that requires all model/calibrator pairs and real `DatasetStatus.PASS` evidence.
  - Added synthetic-only tests and documented that the canonical `PredictionOutput` remains unchanged.
- **Why it changed:** Provide the post-model probability safeguards required before production prediction assembly without treating synthetic fits as calibrated performance evidence.
- **Contract / database / API impact:** No database, API, shared `PredictionOutput`, decision-engine, dashboard, SHAP, reliability, threshold, or retraining implementation changed. Calibrated outputs remain a separate internal contract.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_calibration.py tests/test_horizon_coherence.py --basetemp .pytest-tmp` — PASS — 25 tests passed in 2.26s.
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_lightgbm_model.py tests/test_baselines.py --basetemp .pytest-tmp` — PASS — 36 tests passed in 2.42s.
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 157 tests passed in 2.76s.
  - `& .venv\Scripts\python.exe -c "import sys, pydantic, sklearn, lightgbm; import retainiq_prediction"` — PASS — Python 3.14.4, Pydantic 2.14.0, scikit-learn 1.9.1, LightGBM 4.7.0, and the package import succeeded.
  - `git diff --check` — PASS — no whitespace errors; Git emitted only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Synthetic fixtures only; no authorized longitudinal dataset, production calibrator, empirical calibration metric, prediction, retention result, or ROI claim. Local environment: Python 3.14.4, NumPy 2.5.3, SciPy 1.18.1, scikit-learn 1.9.1, LightGBM 4.7.0, Pydantic 2.14.0, pytest 8.4.2.
- **Known issues / blockers:** Real readiness remains `BLOCKED` because no authorized longitudinal dataset exists. Member 1 must provide canonical lifecycle/billing mappings, source availability and correction semantics, complete observation coverage, provenance/authorization, and the account-level multi-subscription churn policy. Cumulative-max adjustment can change calibration properties and requires held-out evaluation.
- **Next action / handoff:** Connect the real Member 1 adapter and dataset evidence, then fit and evaluate each calibrator on frozen chronological cohorts before any production promotion or PredictionOutput assembly.
- **Reviewer / pairing:** N/A

### 2026-10-10T07:25:22Z — Member 2 AI coding assistant — Reliability gate and source freshness

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous calibration checkpoint is `b65a10c`
- **Issue / task:** Member 2 Prompt 12; no ticket
- **Files changed:** `src/retainiq_prediction/reliability.py`, `src/retainiq_prediction/data_freshness.py`, `src/retainiq_prediction/__init__.py`, `tests/test_reliability.py`, `tests/test_data_freshness.py`, `docs/MEMBER2_RELIABILITY_AND_FRESHNESS.md`, `docs/MEMBER2_IMPROVEMENT_BACKLOG.md`, `TEAM_LOG.md`
- **What changed:**
  - Added versioned deterministic reliability assessments with machine-readable reason codes, human-readable explanations, evidence/coverage summaries, feature compatibility checks, cold-start handling, explicit zero-usage-with-coverage handling, and no numerical confidence field.
  - Added source-level freshness assessment for subscription lifecycle, billing, usage coverage, and configured optional sources. It preserves input cutoffs, availability basis, per-source evidence, missing-source status, watermarks, tenant/account scope, and conservative future-metadata exclusion.
  - Added combined readiness routing that preserves known-cancellation and not-eligible states, abstains on insufficient eligibility/data, and requires a complete three-horizon calibrated bundle with `DatasetStatus.PASS` before scoring can be allowed.
  - Added `IMPROVEMENT-004` for held-out post-coherence calibration validation. No `PredictionOutput`, uncertainty, SHAP, API, decision engine, dashboard, benchmark, or retraining implementation changed.
- **Why it changed:** Establish the explainable data/applicability gate and source-health boundary required before future production scoring, without treating silence as churn or reliability as confidence.
- **Contract / database / API impact:** No database or API schema changed. New modules are additive internal assessments and reuse existing canonical enum values and `AvailabilityPolicy`. Member 1 must supply real source heartbeats/watermarks, lifecycle/coverage mappings, authorization-scoped evidence, and validated source thresholds.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_data_freshness.py tests/test_reliability.py --basetemp .pytest-tmp` — PASS — 29 tests passed in 2.22s.
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 186 tests passed in 2.96s.
  - `& .venv\Scripts\python.exe -c "import sys, pydantic; import retainiq_prediction"` — PASS — Python 3.14.4, Pydantic 2.14.0, package import succeeded, and uncertainty remained `not_quantified`/`none`/`null`.
  - `git diff --check` — PASS — no whitespace errors; Git emitted only normal LF/CRLF conversion warnings.
- **Data / model / ROI evidence:** Synthetic structural fixtures only; no authorized longitudinal dataset, production freshness SLA, OOD detector, confidence estimate, prediction, predictive metric, retention result, or ROI claim.
- **Known issues / blockers:** Real readiness remains `BLOCKED`. Member 1 must finalize source availability versus `received_at` precedence, source heartbeat/watermark semantics, account-level multi-subscription policy, lifecycle/coverage mappings, authorization/provenance, and production freshness thresholds. Limited/insufficient rules require validation on held-out real data.
- **Next action / handoff:** Connect the canonical Member 1 source evidence adapter, validate policy thresholds and reliability cohorts on authorized chronological replay, then integrate the gate with future inference without changing abstention semantics.
- **Reviewer / pairing:** N/A

### 2026-10-10T07:33:34Z — Member 2 AI coding assistant — SHAP explainability foundation

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; Prompt 12 checkpoint is `f58ee52`
- **Issue / task:** Member 2 Prompt 13; no ticket
- **Files changed:** `src/retainiq_prediction/explainability.py`, `src/retainiq_prediction/__init__.py`, `tests/test_explainability.py`, `docs/MEMBER2_SHAP_EXPLAINABILITY.md`, `pyproject.toml`, `TEAM_LOG.md`
- **What changed:**
  - Added an optional SHAP 0.53.x dependency and a typed, versioned `LightGBMExplainer` using real `shap.TreeExplainer` for independent 7-, 14-, and 30-day LightGBM artifacts.
  - Normalized binary SHAP output variants, retained full signed contributions, recorded base/raw margin/probability/additivity evidence, and selected deterministic top-K positive/negative associations from the locked approved feature allowlist.
  - Added fail-closed handling for missing SHAP, incompatible artifacts or feature order, version/scope mismatches, missing feature inputs, non-scored prediction statuses, unready production assessments, unsupported output shapes, and failed additivity.
  - Added neutral non-causal formatting and documented that explanations describe raw margin/log-odds, not calibrated or horizon-coherence-adjusted probabilities. The canonical `PredictionOutput` and backlog items 001–004 were not changed.
- **Why it changed:** Provide auditable model associations for future prediction records without introducing identifiers, labels, cancellation fields, causal claims, fabricated metrics, or a new API contract.
- **Contract / database / API impact:** No database, API, or canonical `PredictionOutput` schema changed. The proposed mapping into `explanations_by_horizon`, attribution retention policy, and production exposure remain team decisions. Member 1 must provide authorized point-in-time feature snapshots and source evidence references.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pip install 'shap>=0.53,<0.54'` — PASS — prebuilt wheel installed; SHAP 0.53.0.
  - Real TreeExplainer smoke invocation on a synthetically trained LightGBM model — PASS — raw output and SHAP additivity returned successfully.
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_explainability.py --basetemp .pytest-tmp` — PASS — 13 tests passed; SHAP emitted its known LightGBM binary-output compatibility warning.
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_lightgbm_model.py tests/test_calibration.py tests/test_reliability.py --basetemp .pytest-tmp` — PASS — 52 tests passed.
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 199 tests passed; 9 known SHAP/LightGBM output-shape warnings.
- **Data / model / ROI evidence:** Synthetic LightGBM training fixtures and real TreeExplainer execution only; no authorized longitudinal data, production explanation, predictive metric, retention result, causal effect, or ROI claim.
- **Known issues / blockers:** Real readiness remains `BLOCKED`. Member 1 must finalize canonical feature-source availability/correction semantics and provide authorized snapshots. The team must agree on the persisted `explanations_by_horizon` shape, attribution privacy/retention, registry identity, and calibration/coherence handoff. SHAP explanations require the caller to pass the canonical readiness gate before production exposure.
- **Next action / handoff:** Review the proposed attribution mapping with Members 1, 3, and 4, then connect explanations only after real calibrated model artifacts and readiness evidence exist.
- **Reviewer / pairing:** N/A

### 2026-10-10T07:41:02Z — Member 2 AI coding assistant — End-to-end prediction pipeline

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous SHAP checkpoint is `e79f657`
- **Issue / task:** Member 2 Prompt 14; no ticket
- **Files changed:** `src/retainiq_prediction/prediction_pipeline.py`, `src/retainiq_prediction/__init__.py`, `tests/test_prediction_pipeline.py`, `docs/MEMBER2_PREDICTION_PIPELINE.md`, `TEAM_LOG.md`
- **What changed:**
  - Added typed `PredictionRequest`, `PipelineResult`, internal pipeline statuses/reason codes, injectable clock and prediction-ID factory, and orchestration over the existing point-in-time adapter, eligibility, features, freshness, reliability, LightGBM, calibration, coherence, SHAP, and canonical prediction contracts.
  - Added strict three-horizon model/calibrator compatibility checks for readiness, versions, label policy, feature version/order/preprocessing, tenant scope, provenance, dataset status, and empirical calibration validation.
  - Added explicit known-cancellation/not-eligible bypasses, data abstention with null probabilities, technical/model-bundle error states, limited-evidence warning preservation, and no raw-score fallback.
  - Added synthetic-only end-to-end execution requiring synthetic artifact provenance and blocked dataset evidence; results are explicitly non-deployable. Production mode remains blocked by current repository evidence.
- **Why it changed:** Connect the existing time-safe prediction components into one testable inference path without training, API/database work, fabricated scores, or a new canonical status/schema.
- **Contract / database / API impact:** The existing `PredictionOutput` contract is unchanged. The pipeline proposes serializing one existing `ExplanationResult` under each `explanations_by_horizon` key while preserving raw-margin limitations; persistence/display shape remains a Member 3/4 team decision. No database, API, authentication, decision, dashboard, or retraining component changed.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_prediction_pipeline.py --basetemp .pytest-tmp` — PASS — 16 tests passed; 15 known SHAP/LightGBM output-shape warnings.
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_prediction_pipeline.py tests/test_explainability.py tests/test_calibration.py tests/test_reliability.py --basetemp .pytest-tmp` — PASS — 60 tests passed; 24 known SHAP/LightGBM output-shape warnings.
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 215 tests passed; 24 known SHAP/LightGBM output-shape warnings.
  - `& .venv\Scripts\python.exe -c "import sys, retainiq_prediction"` — PASS — Python 3.14.4, package import, canonical statuses, and non-quantified uncertainty verified.
  - `git diff --check` — PASS — only normal LF/CRLF conversion warning for the modified package export.
- **Data / model / ROI evidence:** Synthetic fitted LightGBM/calibrator fixtures and real SHAP execution only; no authorized longitudinal dataset, production prediction, predictive metric, retention result, causal effect, or ROI claim.
- **Known issues / blockers:** Production readiness remains `BLOCKED` because no authorized real longitudinal dataset or PASS-provenance model/calibration bundle exists. Member 1 must supply canonical source/freshness/coverage evidence, artifact provenance and registry mapping, and the agreed multi-subscription policy. Members 3/4 must agree on the final `explanations_by_horizon` persistence/display contract and synthetic-result exclusion.
- **Next action / handoff:** Review the orchestration and proposed explanation mapping with Members 1, 3, and 4; connect only authorized real artifacts and adapters before production exposure.
- **Reviewer / pairing:** N/A

### 2026-10-10T07:50:07Z — Member 2 AI coding assistant — Offline historical evaluation

- **Workstream:** Part 2 / Prediction Engine
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; Prompt 14 checkpoint is `e952291`
- **Issue / task:** Member 2 Prompt 15; no ticket
- **Files changed:** `src/retainiq_prediction/historical_evaluation.py`, `src/retainiq_prediction/__init__.py`, `tests/test_historical_evaluation.py`, `docs/MEMBER2_HISTORICAL_EVALUATION.md`, `TEAM_LOG.md`
- **What changed:**
  - Added a typed, offline evaluator for immutable `PredictionOutput`/candidate scores joined to `ChurnLabel` records by `(tenant_id, customer_id, as_of, horizon_days)`; duplicate and cross-tenant/customer joins are rejected.
  - Enforced chronological partition membership, frozen TEST selection, version compatibility, evaluation-cutoff maturity, horizon-specific exclusion, deterministic top-K ranking, and explicit single-class/insufficient-sample metric states without converting unknown outcomes to zero.
  - Added per-horizon PR-AUC, ROC-AUC, Brier, Precision@K, Recall@K, calibration bins, coverage/abstention, horizon-ordering audits, model-cohort comparison warnings, typed lead-time readiness, and conservative Revenue Captured@K handling requiring as-of MRR, one currency, and an explicit deduplication policy.
  - Added a Prompt 14 scenario coverage audit and documented the 24 existing SHAP/LightGBM output-shape warnings as known compatibility warnings; the existing explainer normalizes supported output shapes and verifies additivity.
  - Added the historical-evaluation documentation while preserving improvement backlog items 001–004 as pending.
- **Why it changed:** Provide reproducible offline evaluation and governance evidence without retraining, estimator/calibrator fitting, threshold selection, API/database work, or causal/revenue-saved claims.
- **Contract / database / API impact:** No database, API, canonical prediction schema, label definition, temporal-split policy, Decision Engine, or dashboard contract changed. The evaluator preserves `prediction_id` and `prediction_run_id` when present and records version/provenance metadata.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_historical_evaluation.py --basetemp .pytest-tmp` — PASS — 15 tests passed.
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 230 tests passed; 24 known SHAP/LightGBM output-shape warnings.
  - Focused evaluator/pipeline/explainability/calibration/reliability run — PASS — 75 tests passed; 24 known SHAP/LightGBM output-shape warnings.
  - `git diff --check` and package import checks — run after the final log update below.
- **Data / model / ROI evidence:** Synthetic evaluation fixtures only; no authorized longitudinal dataset, real performance metric, model-selection result, retention uplift, causal effect, saved revenue, or ROI claim. Real evaluation remains `BLOCKED` until Member 1 supplies authorized provenance and mature source-backed outcomes and the dataset readiness gate is PASS.
- **Known issues / blockers:** Member 1 must provide frozen historical prediction/source joins, lifecycle outcome availability and correction semantics, mature outcome coverage, as-of MRR/currency and deduplication policy, and authorized dataset provenance. Lead-time analysis also requires a frozen alert-policy version and historical alert records. Personalized-baseline ablation remains pending and was not implemented.
- **Next action / handoff:** Have Members 1, 3, and 4 review the typed evaluation report, coverage/abstention denominators, revenue exposure limitation, and synthetic-result exclusion before any authorized replay or dashboard integration.
- **Reviewer / pairing:** N/A

### 2026-10-10T07:58:50Z — Member 2 AI coding assistant — Prediction feedback and outcome reconciliation

- **Workstream:** Part 4 feedback foundation / Part 2 ML handoff
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; previous Prompt 15 checkpoint is `20cf1c8`
- **Issue / task:** Member 2 Prompt 16; no ticket
- **Files changed:** `src/retainiq_prediction/outcome_reconciliation.py`, `src/retainiq_prediction/__init__.py`, `tests/test_outcome_reconciliation.py`, `docs/MEMBER2_OUTCOME_RECONCILIATION.md`, `TEAM_LOG.md`
- **What changed:**
  - Added a typed append-only reconciliation boundary that links tenant-scoped immutable `PredictionOutput` snapshots by `prediction_id` to the existing `ChurnLabel` semantics; `prediction_run_id` is retained as batch metadata and is never used as the identity.
  - Added `PENDING`, `MATURE_POSITIVE`, `MATURE_NEGATIVE`, `INCOMPLETE`, and `INELIGIBLE` outcome states with explicit source availability, provenance, coverage, conflict and unresolved multi-subscription reason codes.
  - Added idempotent repeated reconciliation, conflicting duplicate rejection, append-only source-correction revisions, historical as-of revision views, and a mature-label adapter for the existing historical evaluator.
  - Added conservative future-learning admissibility checks requiring authorized real provenance, mature verified horizon-specific outcomes, compatible policy versions, sufficient coverage and evidence before the training cutoff. No training or model promotion is triggered.
  - Added a read-only Part 3 action-feedback compatibility record that explicitly cannot claim intervention causality, plus a Member 4 serialization/documentation handoff.
- **Why it changed:** Establish the Member 2 prediction-feedback foundation required by Part 4 without mutating predictions, creating a competing churn definition, adding production persistence/API infrastructure, or making retention/causal claims.
- **Contract / database / API impact:** Existing `PredictionOutput`, `ChurnLabel`, historical-evaluation metrics, label policy and temporal semantics remain unchanged. The new in-memory store is a replaceable synthetic/test boundary; no database, queue, dashboard, Decision Engine, recommendation or approval implementation was added.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_outcome_reconciliation.py --basetemp .pytest-tmp` — PASS — 20 tests passed.
  - `& .venv\Scripts\python.exe -m pytest -q tests/test_outcome_reconciliation.py tests/test_label_builder.py tests/test_historical_evaluation.py --basetemp .pytest-tmp` — PASS — 55 tests passed.
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp` — PASS — 250 tests passed; 24 known SHAP/LightGBM binary-output compatibility warnings.
  - Package import and `git diff --check` — run after the final log update below.
- **Data / model / ROI evidence:** Explicitly synthetic fixtures only; no authorized real feedback, supervised training set, model release, performance result, intervention effectiveness, saved revenue or ROI claim. Synthetic feedback is rejected by learning admissibility.
- **Known issues / blockers:** Member 1 must provide authorized lifecycle/source availability and correction evidence, mature observation coverage, stable tenant/account identity, and the unresolved account-level multi-subscription churn policy. Production persistence/API and authoritative action records remain other-member responsibilities.
- **Next action / handoff:** Review the feedback field names and revision semantics with Members 1, 3 and 4, then connect only authorized adapter records; keep candidate retraining behind the existing temporal/evaluation/release gates.
- **Reviewer / pairing:** N/A

### 2026-10-10T08:07:38Z — Member 2 AI coding assistant — Retraining readiness and model registry governance

- **Workstream:** Part 2 / Prediction Engine learning governance
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; Prompt 16 checkpoint is `9a5b6c8`
- **Issue / task:** Member 2 Prompt 17; no ticket
- **Files changed:** `src/retainiq_prediction/retraining_readiness.py`, `src/retainiq_prediction/model_registry.py`, `src/retainiq_prediction/__init__.py`, `tests/test_retraining_readiness.py`, `tests/test_model_registry.py`, `docs/MEMBER2_RETRAINING_GOVERNANCE.md`, `docs/MEMBER2_IMPROVEMENT_BACKLOG.md`, `TEAM_LOG.md`
- **What changed:**
  - Added a conservative readiness assessor that gates future candidate training on PASS authorized-real dataset evidence, complete temporal split metadata, point-in-time feature validity, mature source-backed outcomes, compatible versions/policies, horizon-specific sample/class readiness, and explicit selection/intervention warnings.
  - Added immutable metadata-only model bundle registry with one model/calibration version per 7/14/30-day horizon, provenance and artifact references, explicit lifecycle transitions, readiness/evidence gates, independent human approval, and immutable active-bundle registration.
  - Added IMPROVEMENT-005 for the historical evaluation scenario-coverage audit; the audit itself was intentionally not performed in this milestone. Existing backlog items 001–004 were preserved.
  - Added focused synthetic structural tests and governance documentation. No model was trained, retrained, promoted, deployed, scheduled, or persisted.
- **Why it changed:** Establish controlled evidence and release gates for a future retraining workflow without making synthetic fixtures appear production-ready or mutating the existing inference path.
- **Contract / database / API impact:** No database, API, prediction contract, label definition, temporal split policy, Decision Engine, dashboard, or production bundle was changed. The registry is an in-memory replaceable metadata boundary and does not load untrusted artifacts.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pytest tests/test_retraining_readiness.py -q` — PASS — 12 tests passed.
  - `& .venv\Scripts\python.exe -m pytest tests/test_model_registry.py -q` — PASS — 8 tests passed.
  - Focused readiness/registry/feedback/evaluation/label/split run — PASS — 89 tests passed.
  - `& .venv\Scripts\python.exe -m pytest -q` — 265 passed, 5 setup errors because the default Windows pytest temp root was inaccessible (`WinError 5` on `C:\Users\User\AppData\Local\Temp\pytest-of-User`).
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-p17` — PASS — 270 tests passed; 24 known SHAP/LightGBM binary-output compatibility warnings.
  - The temporary `.pytest-tmp-p17` directory was removed after verification. Package import and `git diff --check` were run after this log update.
- **Data / model / ROI evidence:** Synthetic fixtures only; no authorized longitudinal dataset, real readiness result, trained artifact, performance metric, release decision, retention uplift, causal effect, saved revenue, or ROI claim.
- **Known issues / blockers:** Real candidate training remains blocked until Member 1 supplies authorized longitudinal provenance, mature lifecycle/outcome coverage and correction semantics, stable tenant/account identity, complete source availability, and the agreed account-level multi-subscription churn policy. Independent evaluation, human approval, artifact storage/loading, deployment, rollback execution, scheduling, and population-selection coverage remain external governance/integration responsibilities.
- **Next action / handoff:** Have Members 1, 3, and 4 review the readiness reason codes, registry metadata, selection-coverage limitations, and approval/rollback ownership before any authorized candidate run. Keep Prompt 17 changes uncommitted until review.
- **Reviewer / pairing:** N/A

### 2026-10-10T08:19:22Z — Member 2 AI coding assistant — Controlled candidate training and evaluation gates

- **Workstream:** Part 2 candidate learning / Part 4 release governance
- **Branch:** `feature/prediction-engine`
- **Commit subject:** Not committed; Prompt 17 checkpoint is `3666b17`
- **Issue / task:** Member 2 Prompt 18; no ticket
- **Files changed:** `src/retainiq_prediction/candidate_training.py`, `src/retainiq_prediction/candidate_evaluation.py`, `src/retainiq_prediction/__init__.py`, `tests/test_candidate_training.py`, `tests/test_candidate_evaluation.py`, `docs/MEMBER2_CANDIDATE_TRAINING_AND_EVALUATION.md`, `TEAM_LOG.md`
- **What changed:**
  - Added typed candidate-training orchestration over the existing chronological splitter, LightGBM implementation and sigmoid calibrator. Each 7/14/30-day model and calibrator is fit independently with TRAIN/VALIDATION/CALIBRATION separation; TEST is not accessed.
  - Added real-candidate readiness/provenance/freeze/version gates and an explicit synthetic-only execution mode that runs actual fitting/calibration but remains non-production and non-approvable.
  - Added immutable TEST evaluation manifests and a one-access final evaluation gate over the existing historical evaluator, including candidate/champion same-cohort checks, horizon-specific evidence, coverage/abstention reporting, review-capacity consistency and explicit insufficient-evidence states.
  - Integrated evaluation recording with the metadata-only registry up to `EVALUATED_PENDING_APPROVAL`; no approval, promotion, active-bundle mutation, rollback, scheduling, persistence, API, or dashboard behavior was added.
  - Added the candidate training/evaluation documentation, including current blockers and the Windows pytest temporary-directory workaround. Existing improvement backlog items were preserved.
- **Why it changed:** Provide a reproducible and auditable candidate workflow without allowing synthetic data, immature labels, test reuse, or slight metric changes to create a production release claim.
- **Contract / database / API impact:** Canonical `PredictionOutput`, churn labels, temporal split contracts, feature allowlist, model/calibration implementations and active pipeline remain unchanged. New structures are internal governance boundaries; no database schema or API was created.
- **Tests / verification:**
  - `& .venv\Scripts\python.exe -m pytest tests/test_candidate_training.py tests/test_candidate_evaluation.py -q --basetemp .pytest-tmp-p18` — PASS — 17 tests passed; synthetic LightGBM and calibration fitting executed.
  - `& .venv\Scripts\python.exe -m pytest tests/test_candidate_training.py tests/test_candidate_evaluation.py tests/test_model_registry.py tests/test_retraining_readiness.py tests/test_lightgbm_model.py tests/test_calibration.py tests/test_historical_evaluation.py -q --basetemp .pytest-tmp-p18` — PASS — 86 tests passed.
  - `& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-p18` — PASS — 287 tests passed; 24 known SHAP/LightGBM binary-output compatibility warnings.
  - `& .venv\Scripts\python.exe -m pytest -q` — 282 passed, 5 setup errors; the same Windows `WinError 5` occurred while pytest scanned `C:\Users\User\AppData\Local\Temp\pytest-of-User` for `tmp_path` fixtures. The default invocation is not fixed.
  - No tests were skipped or suppressed. `.pytest-tmp/` remains Git-ignored; the repository-local basetemp was used for the passing full run and removed after verification.
- **Data / model / ROI evidence:** Synthetic fixtures only; real LightGBM and sigmoid calibration code executed in isolated tests. No authorized longitudinal dataset, real candidate, real TEST metric, improvement claim, retention uplift, causal effect, saved revenue or ROI claim exists.
- **Known issues / blockers:** Real candidate training and final TEST evaluation remain blocked by missing authorized longitudinal data and PASS provenance. Member 1 must provide canonical availability/correction evidence, mature outcomes, tenant/account identity, resolved multi-subscription semantics and readiness evidence. Members 3/4 must align on prediction/evaluation persistence, feedback coverage, human approval, artifact storage, rollback and dashboard integration. TEST authorization and a genuine champion are required for any comparative human-review gate.
- **Next action / handoff:** Review the freeze manifest, candidate/champion cohort policy, synthetic non-approvability and registry transition evidence with Members 1, 3 and 4. Keep Prompt 18 changes uncommitted.
- **Reviewer / pairing:** N/A

## 6. Shared integration agreements — verify before changing

- **Prediction anchor:** `prediction_id` = unique account forecast snapshot; `prediction_run_id` = inference batch/job ID.
- **Forecast contract:** `p_churn_7d`, `p_churn_14d`, `p_churn_30d`, plus reliability, freshness, reserved uncertainty, versions and `as_of`.
- **Decision routes:** `PRIORITY_REVIEW`, `HUMAN_REVIEW`, `OBSERVE`; nonpredictive states `KNOWN_CANCELLATION`, `NOT_ELIGIBLE`.
- **Account:** paying subscription account, not each application seat. All customer-bearing tables are tenant-scoped.
- **Time truth:** both event occurrence and original data availability must be `<= as_of` before a feature is allowed.
- **Actual prediction labels:** 7/14/30-day matured source-backed outcomes; incomplete = unknown, not retained.
- **Action eligibility:** MVP-only actions must be backed by actual Part 1 fields; support/plan/discount actions remain disabled without their real prerequisite data.
- **ROI:** one-month break-even scenario, explicitly hypothetical; never claim retention uplift or saved revenue from observation alone.
- **Human authority:** no discretionary customer outreach or financial action without authorized approval.
- **Testing:** frozen chronological replay, no fake model predictions or benchmark numbers.

A teammate who changes any of these must update the canonical requirements/contract, the relevant implementation/tests, and their **same-commit log entry**, and inform downstream owners.

## 7. PR / merge checklist

- [ ] Every included commit has a meaningful **`TEAM_LOG.md` entry in the same commit**.
- [ ] Changed behavior and file paths are accurately summarized.
- [ ] Tests run (or not run with explanation) are recorded truthfully.
- [ ] Any altered schema/API/prediction contract is documented and downstream owners informed.
- [ ] No credential, private customer data, or secret was committed to code or log.
- [ ] Synthetic/demo numbers, cost assumptions and measured results are clearly distinguished.
- [ ] End-to-end time correctness, currency and tenant isolation are preserved.
- [ ] Another teammate can reproduce the change using instructions in the repo.

**Optional enforcement:** A repository owner may configure a Git pre-commit hook or CI rule that fails if a change commit does not stage/modify `TEAM_LOG.md`. Until then, the team must follow the rule manually.
