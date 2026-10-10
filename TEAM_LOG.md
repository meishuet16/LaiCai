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
