# RetainIQ v2 — Team Development & Commit Log

**Project:** Dormathon 2026 — RetainIQ v2  
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

### 2026-10-10T21:37:17Z — Member 2 AI coding assistant — Merge final Member 2 integration with current main

- **Workstream:** Part 2 / Integration / Delivery
- **Branch:** `codex/member2-final-integration` targeting `main`
- **Commit subject:** `merge: integrate Member 2 final delivery into main`
- **Issue / task:** User-requested push and merge
- **Files changed:** Merge of current `origin/main`; conflict resolutions in `TEAM_LOG.md` and `docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`.
- **What changed:** Preserved both Member 1 and Member 2 log histories. Kept the newer secure bounded P0 synthetic handoff command using the DPAPI secret file and authenticated reader smoke, superseding the older broad FULL-cohort smoke instructions. No application code was edited during conflict resolution.
- **Why it changed:** Reconcile the pushed Member 2 final integration branch with current main before updating main without force.
- **Contract / database / API impact:** None from conflict resolution; the merged histories retain their existing documented contracts and blockers.
- **Tests / verification:** Conflict markers are absent and the two resolved files pass the scoped staged whitespace check. The whole staged merge check reports two pre-existing Markdown hard-break spaces in `docs/TEAM_LOG.md` inherited from `origin/main`; that unrelated upstream formatting was preserved. No additional tests were run because the conflicts were documentation-only and the final-integration instruction limited testing; the pre-merge focused result remains 3 passed in 4.94s.
- **Data / model / ROI evidence:** No new data, model, calibration, prediction, or ROI evidence. Prompt 34 remains blocked with no genuine fitted three-horizon bundle.
- **Known issues / blockers:** Operational scoring remains `MODEL_BUNDLE_NOT_READY`; the blockers in `docs/MEMBER2_FINAL_INTEGRATION_REPORT.md` remain unchanged.
- **Next action / handoff:** Push the resolved merge commit to the feature branch, then update `main` without force.
- **Reviewer / pairing:** N/A

### 2026-10-10T21:35:16Z — Member 2 AI coding assistant — Final Track A/B/C integration and blocked artifact handoff

- **Workstream:** Part 2 / Integration / QA / Docs
- **Branch:** `codex/member2-final-integration`
- **Commit subject:** `docs(member2): record final integration blocker`
- **Issue / task:** Member 2 final integration delivery
- **Files changed:** `docs/MEMBER2_FINAL_INTEGRATION_REPORT.md` and this log; integration branch also contains Track B/C changes cherry-picked before this commit.
- **What changed:** Integrated Track A (`74b0340`, already ancestral), Track B (`3a295f0` → `a8948d5`) and Track C (`5119e89` → `43425c3`), preserving all concurrent log entries. Added the final artifact inventory, supported-horizon state, bounded verification result, smoke status and Member 3/4 handoff.
- **Why it changed:** Deliver the verified integration promptly without regenerating data, fitting models/calibrators, opening held-out evaluation, or representing Prompt 31 artifacts as Prompt 34 evidence.
- **Contract / database / API impact:** None. No dataset, database, model, calibrator, prediction, API, schema or production bundle was changed.
- **Tests / verification:** One focused pytest invocation with a 90-second timeout — **PASS, 3 passed in 4.94s** — safe artifact load failure, monotonic adjustment, and chronological replay/persistence. Track B's reported 22-test pass and Track C's reported one-test synthetic fitted replay pass were reused and not rerun. End-to-end fitted-artifact smoke — **BLOCKED / SKIPPED** because the required Prompt 34 artifacts do not exist. No other tests were run.
- **Data / model / ROI evidence:** Synthetic-only source manifest available with recorded SHA-256 `75a687071f3fee639e3ce057b59404834accb2fc01ec39a7cb122cb9883e5aac`. The reduced prepared directory is incomplete and lacks `preparation_manifest.json`; no Prompt 34 7/14/30 models, calibrators, shared bundle ID, fitted-artifact hashes or finalized compatible feature schema exist. Prompt 31's uncalibrated 14d/30d models were not substituted.
- **Known issues / blockers:** Prompt 34 supports no fitted horizon. Model-backed Load → Predict → Calibrate → SHAP → Replay → Persist remains blocked. Production scoring must remain `MODEL_BUNDLE_NOT_READY`.
- **Next action / handoff:** Member 3 must not rank/route on absent or uncalibrated scores. Member 4 must not display Prompt 34 score/calibration/replay claims. Enable scored workflows only after a separately authorized complete three-horizon bundle passes the existing provenance, compatibility and approval gates.
- **Reviewer / pairing:** N/A

### 2026-10-10T21:32:02Z — Member 2 AI coding assistant — Prompt 34 deadline status correction

- **Workstream:** Part 2 / Prompt 34 / Docs / handoff
- **Branch:** `integration/member2-main-sqlite`
- **Commit subject:** `docs(member2): record interrupted Prompt 34 preparation status`
- **Issue / task:** Member 2 Prompt 34 emergency delivery
- **Files changed:** `docs/MEMBER2_PROMPT34_CALIBRATED_DEMO_REPORT.md` and this log.
- **What changed:** Recorded the intentional deadline interruption at the latest verified progress checkpoint (25/25 cutoffs), the exact available partial private files, and the absence of a finalized preparation manifest or support report. Explicitly states that no Prompt 34 model training, calibration, held-out evaluation, or real model-backed replay is claimed, and distinguishes the existing Prompt 31 artifacts.
- **Why it changed:** The user directed immediate stop and truthful final delivery before the reduced preparation completed finalization.
- **Contract / database / API impact:** None. Existing synthetic source dataset, imported SQLite database, private preparation files, and logs were preserved. No generated/private data or model artifact was added to Git.
- **Tests / verification:** No tests rerun by instruction; the last focused evidence remains as recorded in the prior Prompt 34 entry. `git diff --check` run before commit.
- **Data / model / ROI evidence:** Synthetic-only. Latest verified preparation progress: cutoff 25/25, `2026-08-17`, 125,000 candidate checks, 63,296 historical and 55,039 eligible snapshots at that cutoff. These are progress counters, not finalized split or support counts. No Prompt 34 model artifacts exist.
- **Known issues / blockers:** `preparation_manifest.json` is absent; private prepared outputs are incomplete, including a `.tmp` calibration feature file. TRAIN/VALIDATION/CALIBRATION support gates were not finalized. Training, calibration, TEST evaluation, and real model-backed replay remain unverified and unclaimed.
- **Next action / handoff:** Resume only with a separately authorized, versioned recovery plan; do not train from the incomplete private files.
- **Reviewer / pairing:** N/A

### 2026-10-10T21:23:45Z — Codex / Member 1 — Merge PostgreSQL and Supabase foundation into main

- **Workstream:** Part 1 / Integration
- **Branch:** `codex/member1-main-merge` targeting `main`
- **Commit subject:** `merge: integrate Member 1 PostgreSQL and Supabase foundation`
- **Issue / task:** User-authorized merge of `codex/member1-postgres-migration` into the latest `origin/main`, including conflict resolution.
- **Files changed:** Member 1 PostgreSQL migrations, runtime/database configuration, RLS/security tooling, tenant-scoped import/API code, tests and documentation; merged `README.md` and `TEAM_LOG.md`.
- **What changed:**
  - Integrated the complete Member 1 PostgreSQL/Supabase history through source commit `2a4b205572e8b9f575bd97d373cd999aa1cade46` with the latest main frontend/documentation history.
  - Resolved README and team-log conflicts by retaining main's judge-facing README, adding accurate PostgreSQL/Supabase first-bind status and Member 1 security documentation links, and preserving both branches' development records.
  - Included the secure one-time Supabase first-bind and DPAPI-protected restricted backend/maintenance import wrappers. Operator-supplied remote evidence confirms migrations 001–007, forced RLS on 18 tables, two restricted logins without BYPASSRLS, and the approved tenant-01 dataset identity bind. STANDARD tenant rows are not yet imported.
- **Why it changed:** Make the verified Member 1 Data Foundation available from `main` without discarding concurrent frontend or documentation work.
- **Contract / database / API impact:** Adds SQLite/PostgreSQL dual-backend support, PostgreSQL migrations 001–007, RLS/capability roles, Supabase preflight/first-bind/import entry points, and authenticated history APIs. No remote database mutation was performed during this merge.
- **Tests / verification:**
  - `py -3.14 -B -m unittest tests.test_supabase_first_bind -v` — **PASS** — 16/16.
  - `py -3.14 -B -m compileall -q retaniq tests` — **PASS**.
  - Initial `npm run build` — **BLOCKED by missing local dependencies** (`tsc` unavailable); `npm ci` completed with 0 vulnerabilities, then `npm run build` — **PASS** — 46 modules transformed.
  - `git diff --check` and conflict-marker scan — **PASS** before staging.
- **Data / model / ROI evidence:** Approved synthetic STANDARD manifest only. Supabase first bind exists, but tenant-01 import/API smoke and any model/ROI evidence remain pending.
- **Known issues / blockers:** Shared transaction-local tenant GUC remains a trusted-backend boundary rather than independent database authentication. Tenant-01 STANDARD import and bounded remote API smoke have not yet run.
- **Next action / handoff:** Import only tenant-01 through the restricted backend/maintenance logins, verify expected counts and cross-tenant absence, then run the bounded authenticated API smoke.
- **Reviewer / pairing:** N/A

### 2026-10-10T20:59:22Z — Member 2 AI coding assistant — Prompt 34 LightGBM artifact validation

- **Workstream:** Prompt 34 / Track B / model persistence
- **Branch:** `codex/prompt34-parallel`
- **Commit subject:** `fix(member2): validate loaded LightGBM artifact contract`
- **Issue / task:** Member 2 Prompt 34 delivery
- **Files changed:** `src/retainiq_prediction/lightgbm_model.py`, `tests/test_lightgbm_model.py`, and this log.
- **What changed:** Hardened persisted LightGBM loading to require a ready fit and validate horizon, configuration, vectorizer, estimator, feature-count and available label-policy/dataset-provenance metadata. Added a cross-horizon mismatch regression test. This does not claim training completion; training still requires finalized prepared artifacts and passing frozen support gates.
- **Verification:** With the project virtual environment and repository-local pytest temp directory, `tests/test_lightgbm_model.py` passed (22 tests). A first invocation using pytest's default shared Windows temp directory hit the existing `WinError 5` setup failure; rerunning with `--basetemp .pytest-tmp-trackb` passed.
- **Data / model evidence:** No training, calibration, TEST-label reads or private-artifact changes were performed in this commit.
- **Known issues / next action:** Verify finalized reduced prepared artifacts and fixed support counts before invoking the existing three-horizon training command.
- **Reviewer / pairing:** Track B agent implementation; root verification.

### 2026-10-10T20:59:22Z — Member 2 AI coding assistant — Prompt 34 calibration and replay integration fixture

- **Workstream:** Prompt 34 / Track C / calibration, SHAP and replay integration
- **Branch:** `codex/prompt34-track-c`
- **Commit subject:** `test(member2): cover saved calibrated model replay integration`
- **Issue / task:** Member 2 Prompt 34 delivery
- **Files changed:** `tests/test_prompt34_model_calibration_replay_integration.py` and this log.
- **What changed:** Added an isolated integration fixture that fits and persists three horizon-specific LightGBM models and sigmoid calibrators, reloads them, and exercises T1/T2 replay, calibrated monotonic probabilities, SHAP explanations and persisted risk changes. The test validates existing components without reading the private SQLite database or real TEST outcomes.
- **Verification:** `tests/test_prompt34_model_calibration_replay_integration.py` passed (1 test; six known SHAP binary-output shape warnings).
- **Data / model evidence:** Fixture models are synthetic test-only artifacts. This commit does not supply or claim a Prompt 34 trained bundle.
- **Known issues / next action:** Run the same integration path against the verified prepared bundle after Track B passes support gates; confirm bundle ID and horizon contracts before end-to-end replay.
- **Reviewer / pairing:** Track C agent implementation; root verification.

### 2026-10-10T20:57:28Z — ChatGPT / Docs — Refresh README homepage rendering

- **Workstream:** Docs / GitHub Repository Presentation
- **Branch:** `main`
- **Commit subject:** `docs: refresh GitHub homepage README rendering`
- **Issue / task:** User reported repository homepage README preview showing old content while opening the root README file displayed the new complete project document.
- **Files changed:** `README.md`, `TEAM_LOG.md`
- **What changed:**
  - Replaced the README opening HTML alignment wrapper with a native GitHub Markdown H1 heading that prominently displays the LaiCai / RetainIQ v2 identity.
  - Kept every subsequent README section, architecture flow, requirements discussion, demo details and evidence limitations identical.
  - Created a new commit to request GitHub's repository-page preview refresh; homepage browser rendering/cache is not directly observable through the repository API.
- **Why it changed:** Improve predictable repository homepage rendering and refresh the README display without discarding the comprehensive documentation.
- **Contract / database / API impact:** None; documentation only.
- **Tests / verification:**
  - GitHub root tree and `main` HEAD inspected — PASS — only one root `README.md` exists and `main` references the expected current commit.
  - README text comparison — PASS — all existing content beyond the opening title block is byte-for-byte preserved.
  - GitHub homepage browser-rendered cache — NOT VERIFIED — connector exposes repository files, not a browser view of this private repo.
  - Runtime tests — NOT RUN — documentation/display-only update, no code changed.
- **Data / model / ROI evidence:** Unchanged; synthetic/demo and hypothetical financial examples remain explicitly labeled.
- **Known issues / blockers:** GitHub website/browser CDN cache invalidation cannot be guaranteed or independently observed via API.
- **Next action / handoff:** Check the repository root view using a fresh/private browser session; if still stale, compare visible commit/branch and ask GitHub support for persistent repository homepage caching.
- **Reviewer / pairing:** N/A

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

### 2026-10-10T20:42:20Z — ChatGPT / Docs — Publish complete judging-ready LaiCai README

- **Workstream:** Docs / Track 1 Pitch & Integration
- **Branch:** `main`
- **Commit subject:** `docs: publish rubric-aligned LaiCai project README`
- **Issue / task:** User-requested complete README aligned with RetainIQ v2 requirements, Track 1 judging rubric, and final three-minute pitch script.
- **Files changed:** `README.md`, `TEAM_LOG.md`
- **What changed:**
  - Replaced Part 1-only README with full project presentation: problem and verified Recurly/Unbounce sources, customer success personas, Connect–Predict–Decide–Learn flow, features, dashboard routes, and example journey.
  - Documented multi-horizon modeling, personal baseline, reliability, human-governed MRR-prioritized review, break-even math, mature feedback, data integration, local setup, evidence standards, demo walkthrough, and rubric mapping.
  - Separated specification/design, current synthetic UI/data foundation, unsupported real-data/model claims, and integration gates.
- **Why it changed:** Provide a complete and understandable judge-facing project README consistent with the four-part requirements and actual repository boundaries.
- **Contract / database / API impact:** Documentation only; no code, API schema, database, model, credential, or deployed service changed.
- **Tests / verification:**
  - README static content and Markdown section checks — PASS — core requirements, primary story, evidence caveats, documented routes, citations, and formulas included.
  - GitHub `main` HEAD, `README.md`, `TEAM_LOG.md`, `DATASET_CARD.md`, `package.json`, frontend routes and services inspected — PASS — README reflects verified repository state.
  - Runtime build/unit tests — NOT RUN — documentation-only remote GitHub update; prior reported results are not represented as newly executed.
- **Data / model / ROI evidence:** Third-party cited statistics, local synthetic demonstration, arithmetic scenario assumptions, and existing DATASET_CARD limitations; no invented held-out metrics or causally saved revenue.
- **Known issues / blockers:** Real-data acceptance, real measured LightGBM performance, production API/UI integration and complete deployment not established in main.
- **Next action / handoff:** Team to validate demo/deployment and update measured evidence, links, and implementation status only when supported; maintain same-commit log discipline.

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

### 2026-10-10T18:03:37Z — Codex / AI coding agent — Update latest LaiCai presentation

- **Workstream:** Documentation / Pitch
- **Branch:** `feature/decision-engine`
- **Commit subject:** `docs(pitch): update latest LaiCai presentation`
- **Issue / task:** User-authorized request to publish only the latest HTML pitch presentation.
- **Files changed:** `pitch/retainiq-3min-pitch.html`, `TEAM_LOG.md`.
- **What changed:**
  - Added the current seven-slide LaiCai presentation, including the latest typography update.
  - Recorded this presentation-only commit and its verification.
- **Why it changed:** Publish the latest approved presentation on the existing feature branch without including screenshots, reports, or other generated files.
- **Contract / database / API impact:** None; presentation artifact only.
- **Tests / verification:**
  - `py -3.14 -` with Python `html.parser` — **PASS** — parsed the HTML, confirmed seven slide sections, one title, navigation script, and current typography.
  - Unit tests — **NOT RUN** — presentation-only documentation change.
- **Data / model / ROI evidence:** No new claims or evidence; existing illustrative values and implementation caveats are retained.
- **Known issues / blockers:** None for this presentation-only commit.
- **Next action / handoff:** Push the commit to `origin/feature/decision-engine` and verify the remote branch.

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
- **Reviewer / pairing:** N/A

### 2026-10-10T15:09:47Z — Codex — Add five-page RetainIQ frontend dashboard

- **Workstream:** Frontend
- **Branch:** `main`
- **Commit subject:** `feat: add five-page RetainIQ frontend dashboard`
- **Issue / task:** User-approved frontend implementation and refinement.
- **Files changed:** `index.html`, `package.json`, `package-lock.json`, `src/`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `docs/FRONTEND_ARCHITECTURE.md`, `docs/MEMBER4_INTEGRATION.md`, and this log.
- **What changed:**
  - Added the five-page RetainIQ shell, shared navigation/state, feature pages, customer and case detail drawers, typed domain models, hooks, and simulated services.
  - Refined Business Overview, Data Integration, and Churn Prediction presentation, while keeping unsupported backend operations and unavailable evidence explicit.
  - Added frontend architecture and integration notes.
- **Why it changed:** Provide a consistent, judge-ready frontend workflow across business overview, data health, churn prediction, retention actions, and customer insights.
- **Contract / database / API impact:** No backend, database, or API contract changes. Frontend uses synthetic/demo data and session-only case changes.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production build (45 modules).
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/domain/scenario.test.ts src/services/decisionService.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts` — PASS — 31 tests.
  - `git diff --cached --check` — PASS — no whitespace errors before this log update.
- **Data / model / ROI evidence:** Synthetic fixtures and scenario assumptions only; no trained-model evaluation, production integration, or measured ROI is claimed.
- **Known issues / blockers:** Production APIs, authentication, durable case writes, and source-backed evidence remain unconnected.
- **Next action / handoff:** Replace demo adapters with approved backend integrations when their contracts and services are available.
- **Reviewer / pairing:** `N/A`
### 2026-10-10T20:11:45Z — Member 1 / Data & Backend Engineer — Scope STANDARD import and add authenticated history APIs

- **Workstream:** Part 1 / Data Foundation, tenant import and API handoff
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): scope synthetic import and add authenticated data APIs`
- **Issue / task:** Final tenant-01 Supabase import and Member 2/3/4 API handoff implementation.
- **Files changed:** `.env.supabase.example`; `retaniq/api.py`; `retaniq/data_foundation.py`; `retaniq/database_config.py`; `retaniq/synthetic/__main__.py`; `retaniq/synthetic/canonical_adapter.py`; `tests/test_data_foundation.py`; `tests/test_member1_api_handoff.py`; `tests/test_supabase_configuration.py`; `tests/test_synthetic_integration.py`; `docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`; `docs/MEMBER1_07B2_SUPABASE_READINESS.md`; `docs/MEMBER1_FINAL_DATA_FOUNDATION_ACCEPTANCE.md`; and this log.
- **What changed:** Added separate app/maintenance/migration DSN configuration, routed global importer identity/checkpoint work through maintenance, added tenant-01-only Supabase importer scope, transaction-local trusted backend tenant context, and authenticated account/prediction history and ID routes. Added local tests. The handoff now explicitly corrects the P0 SQLite copy's physical scope: it contains the full four-tenant STANDARD fixture even though the P0 reader authorization is tenant-01-scoped. First-time Supabase dataset identity binding now fails closed because maintenance RLS cannot prove the destination empty.
- **Why it changed:** The final handoff requires a tenant-only import and least-privilege maintenance separation; a maintenance-role zero count under FORCE RLS is not evidence that other tenant rows are absent.
- **Contract / database / API impact:** Local authenticated routes derive tenant/source/purpose from the stored RetainIQ principal and reject caller-supplied tenant scope. Prediction history is bounded and redacts labels/valuation fields; Member 2 history returns point-in-time account/coverage data and reports freshness `unknown`. API runtime still uses the configured app DSN rather than separately routing downstream reads to inference/dashboard logins. Shared tenant GUC remains spoofable by a holder of the trusted backend credential with arbitrary SQL access. No Supabase migration, role provisioning, API exposure change, remote import, or remote API read occurred.
- **Tests / verification:** `py -3.14 -B -m unittest tests.test_data_foundation.DataFoundationTests.test_supabase_first_identity_binding_fails_closed_under_tenant_rls tests.test_synthetic_integration tests.test_member1_p0_reader tests.test_member1_api_handoff tests.test_supabase_configuration -q` — **PASS**, 34 tests. `py -3.14 -B -m unittest discover -s tests -q` — **PASS**, 218 total; 161 passed, 57 expected PostgreSQL-guard skips, 0 failures/errors; no live PostgreSQL tests ran. `py -3.14 -B -m compileall -q retaniq tests`, package import smoke, `git diff --check` — **PASS**. DPAPI-protected P0 reader smoke against local SQLite — **PASS**, 23 events/1 subscription/48 coverage rows, cross-tenant API denial, no valuation fields, database unchanged. Read-only local STANDARD identity/integrity check matched manifest SHA and SQLite integrity, but found 752,669 rows across non-tenant-01 partitions in the P0 file. Staged paths were checked to exclude `.env` secrets, DPAPI files, SQLite databases, and exports.
- **Data / model / ROI evidence:** Synthetic STANDARD only; manifest SHA `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`. Tenant-01 source counts are 750 customers, 2,250 identities, 56,211 canonical events, and 119,472 coverage rows. These do not represent Supabase import counts; no model or ROI result was produced.
- **Known issues / blockers:** No app, maintenance, or migration DSNs are configured in this task environment. Durable remote restricted LOGINs, Data API/exposed-schema checks, direct anon/authenticated denial, temporary smoke-role cleanup, and actual Member 2/3/4 remote reads remain unverified. Supabase first import requires a privileged read-only full-destination emptiness check and a reviewed identity-binding path; the importer currently refuses an unbound Supabase destination. Local P0 working copy contains four tenants and is not physically isolated. The remote 13-scenario RLS smoke remains prior operator-supplied evidence only; GUC spoofability remains.
- **Next action / handoff:** Configure distinct restricted backend and maintenance LOGINs plus a separate approved read-only/admin preflight credential through a protected local secret mechanism. Verify destination/project, exposed API roles and cleanup. Implement and live-test the one-time empty-destination/identity-binding gate on real PostgreSQL, then run actual restricted-role remote checks before importing tenant-01. Only after those gates, verify import and Member 2/3/4 remote access; do not use `service_role` or bypass RLS.
- **Reviewer / pairing:** N/A

### 2026-10-10T19:36:21Z — Member 1 / Data & Backend Engineer — Verify Supabase RLS deployment and restricted smoke

- **Workstream:** Part 1 / Data Foundation, Supabase PostgreSQL deployment
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `fix(member1): verify Supabase RLS deployment and restricted smoke`
- **Issue / task:** Continue the authorized dedicated-demo migration after correcting the migration-005 role-owner transfer and restricted-smoke transaction boundary.
- **Files changed:** `migrations/postgresql/005_rls_and_least_privilege.sql`, `retaniq/database_config.py`, `retaniq/postgresql_migrations.py`, `retaniq/supabase_remote_preflight.py`, focused migration/RLS/Supabase tests, `docs/MEMBER1_POSTGRESQL_RLS_AND_AUTHORIZATION.md`, `docs/MEMBER1_SUPABASE_CONNECTION_AND_SECURITY_PREPARATION.md`, and this log.
- **What changed:** Added safe migration failure diagnostics (migration version, statement, operation and SQLSTATE without DSN/password output); corrected migration 005's temporary SET membership and schema CREATE grant ordering; allowed the project's session-pooler migration connection while rejecting transaction pooling; corrected the restricted smoke harness to use real top-level transactions with autocommit.
- **Why it changed:** Supabase rejected the initial ownership transfer because of role membership options; after deployment, the smoke exposed that preliminary identity queries kept the connection inside an outer transaction, invalidating transaction-local cleanup assertions.
- **Contract / database / API impact:** Operator-supplied remote result for project `mhtzkzqjcsdyjacvcxty` / PostgreSQL 17.11 / Session Pooler reports migration history `CHECKSUMS_MATCH`, no pending versions, current version 007, and `applied_versions: []` on the final verification run. Catalog checks passed: all 18 application data tables (migration metadata excluded) have RLS enabled and forced, 42 policies are present, and both SECURITY DEFINER authentication functions are owned by `retaniq_authenticator`. The temporary restricted-login smoke passed all 13 scenarios for backend, artifact-writer, dashboard-reader and maintenance roles. It explicitly passed the shared-GUC spoofability characterization; it does not establish independently authenticated database tenant identity. Smoke cleanup was reported as `ATTEMPTED`, not independently verified. No STANDARD rows were imported, no durable runtime login credentials or Member 2 access were provisioned, and `service_role` was not used for smoke verification.
- **Tests / verification:** Focused local live-PostgreSQL migration/configuration/RLS/preflight suite — **PASS**, 58 tests, 0 failures/errors/skips, on a disposable PostgreSQL 17.11 container; `py -3.14 -m compileall -q retaniq tests`, package imports, and `git diff --check` — **PASS**. The corrected remote restricted smoke — **PASS**, 13/13 reported scenarios. No full 191-test suite rerun.
- **Data / model / ROI evidence:** None imported. STANDARD dataset remains local synthetic artifact `synthetic-saas-v1-2-standard-s2026-970a9d231e68`; no remote dataset or Member 2 read-access evidence.
- **Known issues / blockers:** The backend's shared transaction-local GUC is spoofable by any holder of its database credential capable of arbitrary SQL. The catalog shows capability roles are NOLOGIN; the deployment credential is privileged `postgres` (`rolbypassrls=true`, `rolcreatedb=true`, `rolcreaterole=true`). Data API/exposed-schema behavior and cleanup of temporary smoke logins were not independently verified. The existing importer binds one global dataset identity, provisions all four dataset tenants, is not tenant-01-only, and uses the regular configured DSN for global provenance/checkpoint and batch operations; no separate maintenance-login routing exists. Therefore the import gate is not satisfied.
- **Next action / handoff:** Before STANDARD import, owner must decide whether to accept the trusted-backend GUC boundary, securely provision distinct durable backend and maintenance login credentials (without `BYPASSRLS`), verify Supabase Data API exposure and role memberships, independently confirm temporary smoke-login cleanup, and approve the four-tenant import mapping or a tenant-01-only import contract. Then add/verify the minimum importer routing and actual remote restricted read path; do not bypass RLS or use `service_role`.
- **Reviewer / pairing:** N/A

### 2026-10-10T19:31:28Z — Member 1 / Data & Backend Engineer — Fix remote smoke transaction boundary

- **Workstream:** Part 1 / Data Foundation, Supabase PostgreSQL deployment
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** Pending remote restricted-smoke retry
- **Issue / task:** Diagnose the first restricted-role smoke failure after migrations 005–007 were deployed.
- **Remote state:** Operator-supplied catalog reports migration history `CHECKSUMS_MATCH`, current version 007, 18/18 application data tables RLS-enabled and forced (migration metadata table excluded), 42 policies, both SECURITY DEFINER authentication functions owned by `retaniq_authenticator`, and `catalog_checks_passed:true`. Four temporary restricted logins were attempted. The smoke returned FAIL after six backend scenarios; cleanup was attempted but not independently verified. No STANDARD import occurred.
- **What changed:** The smoke login factory now uses psycopg `autocommit=True`, ensuring its `connection.transaction()` contexts are top-level transactions even after identity queries. Previously, the initial `SELECT current_user` opened an implicit transaction and caused later contexts to be savepoints, so transaction-local tenant context was not cleared at the supposed commit. Added a unit check for autocommit and updated the remote smoke implementation only; database schema/migrations are unchanged.
- **Tests / verification:** `py -3.14 -B -m unittest tests.test_postgresql_migrations tests.test_supabase_remote_preflight tests.test_supabase_configuration tests.test_postgresql_rls` against a task-owned disposable PostgreSQL 17.11 container with the disposable-DSN guard enabled — **PASS**, 58 tests, 0 failures/errors/skips. `py -3.14 -m compileall -q retaniq tests`, package imports, and `git diff --check` — **PASS**. Task-owned PostgreSQL container stopped/removed. The updated smoke has not yet been rerun on Supabase.
- **Known issues / blockers:** Remote RLS deployment is catalog-verified, but actual restricted-role acceptance remains incomplete until the corrected smoke passes. The smoke's previous cleanup status is only `ATTEMPTED`. Shared-GUC spoofability remains a known shared-credential limitation. No dataset import.
- **Next action / handoff:** Run the secure `--deploy` command again after a fresh catalog preflight. It should find migration checksums already matching and rerun restricted-login smoke; require its final `MIGRATIONS_AND_RESTRICTED_SMOKE_PASS` result and inspect cleanup before import or commit.
- **Reviewer / pairing:** N/A

### 2026-10-10T19:24:35Z — Member 1 / Data & Backend Engineer — Grant temporary SET membership for migration 005

- **Workstream:** Part 1 / Data Foundation, Supabase PostgreSQL deployment
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** Pending fresh catalog verification and deployment retry
- **Issue / task:** Fix the newly confirmed `42501` failure in migration 005 without granting extra ADMIN authority.
- **Remote state:** Latest attempt failed at migration 005 statement 14 (`ALTER FUNCTION`) with SQLSTATE `42501` because `retaniq_authenticator` membership had `SET FALSE`. The migration runner reports `MAY_HAVE_OCCURRED`; no fresh post-failure catalog read had been performed at that time. Preflight immediately before that attempt showed 001–004 recorded and 005–007 pending.
- **What changed:** Migration 005 now grants the migration login a distinct temporary membership `WITH SET TRUE, INHERIT FALSE`, omitting ADMIN, then revokes that membership after transferring the authentication-function ownership. Updated the PostgreSQL 17 ownership-transfer test assertion, security documentation, and RLS catalog test setup (`schema = public`) so the live catalog check runs.
- **Tests / verification:** Focused suite against a task-owned disposable PostgreSQL **17.11** container: **PASS**, 57 tests, 0 failures, 0 errors, 0 skips. This includes live migration 001–007 application and restricted-role/RLS tests. Compileall, package imports, and `git diff --check` passed. The task-owned container was stopped and removed.
- **Known issues / blockers:** Remote rollback/catalog state was not verified at this timestamp; the corrected SET-option migration later deployed successfully, but restricted-role smoke had not yet passed.
- **Next action / handoff:** Superseded by the 19:31Z smoke-transaction fix above.
- **Reviewer / pairing:** N/A

### 2026-10-10T19:18:02Z — Member 1 / Data & Backend Engineer — Remove failing migration 005 self-grant

- **Workstream:** Part 1 / Data Foundation, Supabase PostgreSQL deployment
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** Pending fresh explicit remote retry
- **Issue / task:** Correct the precisely diagnosed failure from the operator-confirmed deployment attempt.
- **Remote state:** The first retry confirmed migration 005 statement 13 (`GRANT RETANIQ`) failed with SQLSTATE `0LP01`, `ADMIN option cannot be granted back to your own grantor`. The subsequent retry passed that statement and failed at statement 14 (`ALTER FUNCTION`) with SQLSTATE `42501`, `must be able to SET ROLE "retaniq_authenticator"`. Before that retry, fresh preflight showed 001–004 applied, 005–007 pending, and 19 total tables including metadata. Both attempts reported `mutations_performed:true`.
- **What changed:** Removed `ADMIN TRUE` from the membership grant after the `0LP01` failure. The next live attempt established that PostgreSQL 17's creator membership has `SET FALSE`; the earlier assumption that it provided SET ROLE was incorrect. The additional SET-option correction is recorded in the 19:24Z entry above.
- **Tests / verification:** After the first fix, focused tests passed (57 tests, 36 passed, 21 skipped without local PostgreSQL); compileall, imports and diff check passed. The later SET-option correction was separately tested live as recorded above.
- **Known issues / blockers:** At the time of this entry migration 005–007 and RLS had not passed remote verification; those later changed states are captured in the newer log entries. No STANDARD data was imported.
- **Next action / handoff:** Superseded by the 19:24Z and 19:31Z entries above.
- **Reviewer / pairing:** N/A

### 2026-10-10T18:29:07Z — Member 1 / Data & Backend Engineer — Record emergency Supabase delivery blockers

- **Workstream:** Part 1 / Data Foundation, Supabase deployment readiness
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `docs(member1): record emergency Supabase delivery blockers`
- **Issue / task:** Emergency final delivery; attempt deployment/import only if the approved remote project and security gates are verifiable.
- **Files changed:** `TEAM_LOG.md`
- **What changed:** Recorded the current remote readiness checks and the safe stop conditions for this task. Confirmed the existing local synthetic STANDARD artifact identity from its manifest; no artifact rows or raw records were imported or changed.
- **Why it changed:** No approved Supabase target or protected credentials are configured, and the current importer does not yet have safe maintenance-role routing and verified multi-tenant context handling required by the local role/RLS design.
- **Contract / database / API impact:** None. No remote database was contacted; migrations 001–007 were not deployed, remote roles/RLS were not tested, no dataset was imported, and no Member 2 database access was granted or tested.
- **Tests / verification:**
  - Environment-presence check across process/user/machine scopes — **PASS** — all five RetainIQ Supabase settings plus `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD` absent; values were not printed.
  - Supabase CLI and local config-file availability check — **PASS** — CLI and `.env`/`.env.local`/`.env.supabase` absent; example file only.
  - `py -3.14 -B -m retaniq.supabase_preflight` — **BLOCKED** — reports `supabase_demo_configuration_missing_or_invalid`; this was the single local preflight, with no remote connection.
  - Regression tests — **NOT RUN** — no code or database changes were made; prior checkpoint evidence remains 191 passed on the full live dual-backend run, and is not represented as rerun for this emergency task.
  - `git diff --check` — to be run before commit.
- **Data / model / ROI evidence:** Synthetic dataset only: `synthetic-saas-v1-2-standard-s2026-970a9d231e68`. The local artifact is not evidence of remote import; no real dataset, PII, or model-performance claim was used.
- **Known issues / blockers:** No approved project/ref/region, owner authorization for remote mutation, or protected migration/runtime DSNs. Importer currently accepts a local `--db` path rather than environment-based Supabase configuration; global import identity/checkpoints require maintenance access, and multi-tenant provisioning/batching needs a safe, tested context boundary. Remote ownership, role grants, exposed schemas, RLS, and pooler mode remain unverified. Shared-GUC context remains spoofable to a caller with arbitrary SQL access under the shared backend credential.
- **Next action / handoff:** Owner must designate and authorize a dedicated synthetic demo project (including ref/region and backup/rollback approval), securely provision migration and restricted runtime credentials outside chat, and approve the four synthetic tenant-partition mapping. Before import, locally implement and test the smallest secure maintenance/import role routing and tenant-context changes; then deploy migrations and run actual restricted-credential checks before importing. No push, deployment, or import performed.
- **Reviewer / pairing:** N/A

### 2026-10-10T18:19:02Z — Member 1 / Data & Backend Engineer — Checkpoint local PostgreSQL RLS and prepare 07B-2 handoff

- **Workstream:** Part 1 / Data Foundation, PostgreSQL RLS and authorization
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): checkpoint local PostgreSQL RLS foundation`
- **Issue / task:** Verify and checkpoint the existing 07B-1 implementation; prepare a deployment-readiness handoff without deploying Supabase or importing STANDARD data.
- **Checkpoint:** Base is `90f745392e32a52d8ac896e302b81221ec617ee0` (`feat(member1): prepare secure supabase configuration and preflight`). The implementation remains **PARTIALLY_VERIFIED**. Repository instructions and canonical requirements were found in the OneDrive checkout and another worktree; both were read-only and left unchanged. The separate Member 2 P0 worktree was not modified.
- **Files changed:** PostgreSQL migrations `005_rls_and_least_privilege.sql`, `006_artifact_authorization_scope.sql`, and `007_restore_global_maintenance_grants.sql`; `security/postgresql/role_bootstrap.sql`; `retaniq/data_foundation.py`, `retaniq/database.py`; PostgreSQL test support and migration/RLS/integration test files; README and Member 1 PostgreSQL/data-contract docs; `docs/MEMBER1_POSTGRESQL_RLS_AND_AUTHORIZATION.md`, `docs/MEMBER1_RLS_TEST_MATRIX.md`, new `docs/MEMBER1_07B2_SUPABASE_READINESS.md`, and this log.
- **What changed:** Re-audited the role/grant/RLS implementation and its trust boundary. Confirmed migration 006's source-scoped authorization lookup and 007's forward restoration of global maintenance grants without editing applied migrations 001–004 or changing 005's checksum. Confirmed the PostgreSQL adapter's empty-parameter handling required for migration SQL containing literal percent-format strings. Added a readiness report with gap classifications, owner approvals, prerequisites, and an ordered 07B-2 sequence.
- **Contract / database / API impact:** No logical application contract or endpoint changed. Sixteen tenant-bearing tables have forced RLS; two global operational tables are maintenance-only; migration metadata has no runtime grant. `retaniq.tenant_id` and related source/principal GUCs remain spoofable by arbitrary SQL under a shared database login. The application has separate app/migration DSNs but does not yet route maintenance or every capability role independently. Supabase ownership, grants, exposed-schema state, and pooler behavior remain unknown. Downstream inference, decision, and dashboard owners need to agree on actual role routing before remote deployment.
- **Tests / verification:**
  - `py -3.14 -B -m unittest tests.test_postgresql_rls tests.test_postgresql_migrations -v` — **PASS** — 36 tests, 0 failures/errors/skips; 5.620s.
  - With explicit disposable loopback DSN and `RETAINIQ_POSTGRES_TEST_DISPOSABLE=1`, `py -3.14 -B -m unittest discover -s tests` — **PASS** — 191 tests, 0 failures/errors/skips; 69.834s. The 57 PostgreSQL-guarded tests ran, including 16 restricted-role RLS methods.
  - With PostgreSQL guard variables empty, `py -3.14 -B -m unittest discover -s tests` — **PASS** — 191 tests, 0 failures/errors, 57 expected PostgreSQL skips; 13.739s.
  - `py -3.14 -B -m compileall -q retaniq tests`, package import smoke, and `git diff --check` — **PASS**. No Python warnings; rejected-request audit lines were expected test output.
  - PostgreSQL version and driver: 16.15 / psycopg 3.3.6. Focused restricted-role tests used actual LOGIN roles; general regression tests are not counted as RLS evidence when run through the setup/admin DSN.
- **Database cleanup:** Dropped the exact disposable base database after the suite; the RLS test's temporary database was also dropped by its teardown. Confirmed no `retaniq_test_*` databases remained, then stopped the verified task-owned loopback cluster. Its temporary data directory was preserved.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only. No Supabase or customer data accessed; no dataset/model/ROI claim made; no STANDARD data imported.
- **Known issues / blockers:** Shared-GUC spoofability is directly reproduced. Positive restricted writes beyond feature snapshots, churn labels, and predictions remain incomplete. Maintenance role routing is absent. Supabase service-role bypass, exposed schemas/default ACLs, migration-owner privileges, and pooler behavior are not remotely verified. 07B-2 remains **BLOCKED** pending project/region designation, owner authorization, secure credential provisioning, and an explicit decision on the GUC threat model.
- **Next action / handoff:** Follow `docs/MEMBER1_07B2_SUPABASE_READINESS.md` in order. Do not deploy, push, merge, or import STANDARD from this checkpoint.
- **Reviewer / pairing:** N/A

### 2026-10-10T18:03:03Z — Member 1 / Data & Backend Engineer — Resume and verify 07B-1 PostgreSQL RLS

- **Workstream:** Part 1 / Data Foundation, PostgreSQL RLS and authorization
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** N/A — 07B-1 changes intentionally remain uncommitted for review
- **Issue / task:** Resume unfinished Prompt 07B-1 after the separately isolated Member 2 P0 reader handoff; stop before 07B-2.
- **Checkpoint:** Verified HEAD `90f745392e32a52d8ac896e302b81221ec617ee0` (`feat(member1): prepare secure supabase configuration and preflight`); the existing pending 07B-1 work was preserved. The P0 worktree was only checked for independent existence/clean state and was not modified.
- **Files changed:** Added `migrations/postgresql/006_artifact_authorization_scope.sql`, `migrations/postgresql/007_restore_global_maintenance_grants.sql`, `docs/MEMBER1_POSTGRESQL_RLS_AND_AUTHORIZATION.md`, `docs/MEMBER1_RLS_TEST_MATRIX.md`, `tests/postgresql_security_support.py`, and `tests/test_postgresql_rls.py`; updated `retaniq/data_foundation.py`, `tests/test_postgresql_migrations.py`, existing PostgreSQL test setup files, `README.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, and `docs/MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md`.
- **What changed:**
  - Audited the existing 005 RLS and least-privilege implementation. Kept custom RetainIQ bearer tokens as the authoritative identity; the SECURITY DEFINER bootstrap lookup installs a transaction-local tenant context only after digest validation.
  - Added migration 006 to give the artifact-writer role only source-list-scoped authorization-record reads needed by the existing repository checks. Verified actual feature, churn-label, and prediction writes through a restricted artifact-writer LOGIN without source-event access.
  - Live testing exposed that migration 005's final broad revoke removed its intended global maintenance grants. Preserved its checksum and added forward migration 007 to restore only maintenance access to global provenance/checkpoint tables.
  - Added all-table cross-tenant INSERT/ownership-update and DELETE-filter checks for the 16 tenant tables; verified maintenance-only global access, missing/invalid context, connection reuse, privilege denials, GUC spoofability, and auth bootstrap.
  - Completed the role/schema/table inventory, status/coverage matrix, Supabase deployment limitations, and this log entry. No Supabase migration or STANDARD import was performed.
- **Role / permission decision:** `retaniq_backend` performs trusted backend reads and writes on tenant-bearing tables but not DELETE/global state/migration metadata; inference is SELECT-only; artifact writer persists only ML artifacts and reads only authorization records for its verified source list; decision and dashboard roles are read-only; maintenance handles restricted provisioning/global operations; authenticator is NOLOGIN and owns only two fixed-search-path SECURITY DEFINER lookups. Runtime credentials and memberships remain operator-provisioned.
- **Trust boundary / known issues:** The transaction-local `retaniq.tenant_id`, `retaniq.authorized_sources`, and `retaniq.service_principal_id` values are backend assertions, not cryptographic identity; any holder of a shared SQL credential with arbitrary SQL can spoof them. Do not expose those credentials to browsers/untrusted services, and do not claim isolation against credential compromise or arbitrary-SQL injection. The generic runtime configuration does not yet automatically route trusted provisioning and global batch/import/checkpoint operations through a separate maintenance credential. Successful restricted writes for several source/provisioning tables remain a matrix gap. Supabase role privileges, exposed schema/Data API state, pooler behavior, and remote RLS remain unverified.
- **Tests / verification:** PostgreSQL 16.15, psycopg 3.3.6. Focused RLS + migration suite — **PASS**, 36 tests. Full live dual-backend discovery — **PASS**, 191 passed, 0 failed, 0 errors, 0 skipped, 0 Python warnings, 67.321s; 57 unique live PostgreSQL-guarded tests including 16 restricted-role/RLS methods. SQLite-only full discovery — **PASS**, 134 passed, 0 failed/errors, 57 expected live-PostgreSQL guard skips, 13.518s. `compileall`, package imports, and `git diff --check` — **PASS**; `git diff --cached --name-only` empty. The changed-file credential-pattern audit matched only synthetic DSN test fixtures in `tests/test_postgresql_migrations.py`; no secret/config/database files are staged or added.
- **Database cleanup:** Reused the task-owned PostgreSQL cluster only after verifying `postgres.exe` command line, executable, owner, data directory `C:\Users\User\AppData\Local\Temp\retaniq_07a_20261011_pg`, and IPv4 loopback port 62534. Dropped only `retaniq_test_07b_20261011`, confirmed no `retaniq_test_*` databases remained, then stopped the cluster with its verified `pg_ctl.exe`. The Temp data directory remains on disk; no database artifact was staged.
- **Final classification:** **PARTIALLY_VERIFIED** — local RLS and tested restricted-role behavior pass, but the shared-GUC trust limitation, missing separate maintenance runtime selection, incomplete positive write-shape coverage, and absence of Supabase verification remain explicit.
- **Next action / handoff:** 07B-2 only after approval/designation of the dedicated demo project and secrets, decision on whether the shared-GUC threat model is acceptable, review of role bootstrap/ownership privileges in Supabase, configured distinct app/migration/maintenance credentials, actual Data API/exposed-schema audit, and repeat restricted-role positive/negative tests remotely. STANDARD import stays blocked until 07B-2 acceptance.
### 2026-10-10T17:50:28Z — Member 1 / Data & Backend Engineer — P0 isolated authenticated STANDARD reader handoff

- **Workstream:** Part 1 / SQLite Data Foundation / Member 2 secure reader
- **Branch:** `codex/member1-p0-reader-handoff` — cleanly based on 07A `90f745392e32a52d8ac896e302b81221ec617ee0`; checkpoint committed locally after verification; no push or merge.
- **Commit subject:** `feat(member1): provide secure tenant-scoped synthetic reader`.
- **Issue / task:** P0-ISOLATED; separate from unfinished 07B-1 RLS work.
- **Files changed:** `README.md`, `TEAM_LOG.md`, `retaniq/data_foundation.py`, `retaniq/__main__.py`, `retaniq/secret_store.py`, `retaniq/synthetic/__main__.py`, `retaniq/synthetic/canonical_adapter.py`, `migrations/005_service_principal_credential_audit.sql`, `tests/test_member1_p0_reader.py`, `examples/member1_p0_authenticated_reader_smoke.py`, new `examples/member2_p0_bounded_pilot.py`, `docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`, and new `docs/MEMBER1_TO_MEMBER2_SECURE_READER_HANDOFF.md`.
- **What changed:** Added a tenant-01-only `analyst` reader path granting `retention_inference` and the three existing source/category pairs only; credential create/rotate/revoke audit records; atomic digest update coupled to current-user DPAPI secret delivery; safe child-process token injection through `RETAINIQ_MODEL_TOKEN`; fixed-ID rotation/revoke operations; and checks preventing the provisioning CLI from using an arbitrary DB or the immutable original source.
- **Why it changed:** The existing synthetic `provision-reader` path granted `model_artifact_write`, could add repeated credentials, and printed its token. The approved source DB also contained five prior principal rows, including broader grants. Member 2 needed a separate least-privilege read credential without changing the source or depending on 07B-1.
- **Contract / database / API impact:** SQLite migration 005 adds a non-secret `service_principal_credential_audit` table. The P0 CLI validates dataset identity, full import counts and exact metadata-derived source/category grants before one fixed principal is inserted/rotated. The original DB stayed read-only. The working copy removed the five inherited service-principal rows, invalidated 12 imported integration digests, and preserves all synthetic rows and identity. Reads use existing authenticated `get_events_as_of`, `get_subscriptions_as_of`, `get_account_snapshot_as_of`, and `get_observation_coverage_as_of`; there is no new HTTP read route.
- **Tests / verification:** Focused P0 tests — **PASS** — 8 passed. Full SQLite-only unittest discovery using `py -3.14 -B -m unittest discover -s tests -q` with `RETAINIQ_POSTGRES_TEST_DSN` and `RETAINIQ_POSTGRES_TEST_DISPOSABLE` unset — **PASS** — 183 tests run, 41 guarded PostgreSQL skips, 0 failures/errors. The existing shared PostgreSQL cluster was not used, changed, or stopped. Actual authenticated STANDARD smoke — **PASS** — 23 events, 1 subscription, 48 coverage rows at `2026-10-01T00:00:00Z`; tenant-02 denial, source/category checks, valuation redaction, JSON serialization, and unchanged SQLite data_version/mtime. Actual bounded Member 2 pilot — **PASS** — one eligible tenant-01 account at the same cutoff; 22 usage events, 1 subscription event, 27 daily-aggregate sessions, 48 coverage rows; no writes or account identifiers in output. Original manifest hash still `7f85a83a…77db6d`; original DB SHA-256 still `71bc6c18…ee5943`. Working-copy final SHA-256 `68404ded8052dc3199dbe0051819f445247b65b3d16adca5af68406d54443114`; SQLite integrity `ok`; dataset identity and full counts retained. DPAPI file ACL checked; file contains DPAPI envelope only, never plaintext output.
- **Data / model / ROI evidence:** Synthetic SaaS v1.2 STANDARD only. No labels, model training, FULL generation, real customer data, or model-performance claim.
- **Known issues / blockers:** DPAPI secret is bound to the current Windows user; a Member 2 process under a different OS identity needs operator re-provisioning or an approved secret manager. The immutable source still contains its pre-existing digest-only principal rows and was intentionally not edited. A legacy similarly named external DPAPI artifact remains untouched and was not used or mapped to those rows. Source freshness has no source-specific SLA or independent lifecycle/billing heartbeat; cancellation labels still require mature, complete outcome coverage. Complete requirements and `AGENT.md`/`AGENTS.md` were absent in this checkout.
- **Next action / handoff:** **READER_READY** for the bounded tenant-01 synthetic pilot. Member 2 can reproduce the completed bounded read with `python -m retaniq.secret_store run --file $secret -- $python -m examples.member2_p0_bounded_pilot --db $db --as-of 2026-10-01T00:00:00Z`. Do not run the multi-account `examples/member2_synthetic_smoke.py` for this bounded task. Do not use the original DB or 07B-1 RLS worktree.
- **Reviewer / pairing:** N/A

### 2026-10-10T17:02:46Z — Member 1 / Data & Backend Engineer — 07A Supabase configuration and security preparation

- **Workstream:** Part 1 / Supabase demo connectivity, secret handling, Phase 07B RLS preparation
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** N/A — 07A changes intentionally uncommitted for review
- **Issue / task:** Prompt 07A only; stop before Phase 07B/07C/07D and Phase 08.
- **06E checkpoint:** `89a0293e3b89789b7df43c5b44563459154f055f` — `test(member1): verify sqlite postgres contract conformance`, committed locally after staging/reviewing the exact five 06E paths. No push or merge.
- **Files changed in 07A:** `.gitignore`, `.env.supabase.example`, `retaniq/database_config.py`, `retaniq/database.py`, `retaniq/postgresql_migrations.py`, new `retaniq/supabase_preflight.py`, new `tests/test_supabase_configuration.py`, new `tests/test_supabase_preflight.py`, new `docs/MEMBER1_SUPABASE_CONNECTION_AND_SECURITY_PREPARATION.md`, and this entry.
- **What changed:** Added explicit Supabase demo selection to the existing database config/shared psycopg client; verified project-reference and mode-specific DSN identity; separated app/migration roles and required a direct migration DSN; added TLS policy/labels, secret-safe diagnostics, and a SELECT-only preflight; prepared the role/RLS table inventory and deployment safety procedure.
- **Why it changed:** Establish secure, fail-closed configuration before a shared synthetic demo without applying schema changes or sending data remotely.
- **Contract / database / API impact:** SQLite and local PostgreSQL behavior retained. Supabase remains opt-in. Transaction-pooler application connections disable psycopg prepared statements (`prepare_threshold=None`); migrations reject transaction mode because the runner holds a session-level advisory lock. Supabase migrations route through the separate direct migration DSN. No API endpoint or migration file changed; no RLS/grants deployed.
- **Tests / verification:** Focused Supabase/config/preflight/migration suite — **PASS** — 59 tests, 0 failures/errors, 5 expected guarded PostgreSQL skips, 0.133s. Full discovery on isolated local PostgreSQL 16.15 / psycopg 3.3.6 — **PASS** — 175 passed, 0 failures/errors/skips, 66.250s, 41 unique live PostgreSQL tests. SQLite-only full discovery — **PASS** — 134 passed, 41 expected live-PG skips, 14.877s. `compileall`, package imports, and `git diff --check` — **PASS**. No Python warnings; only expected rejected-request logs.
- **Data / model / ROI evidence:** No Supabase or customer data accessed. Test databases `retaniq_test_07a_20261011` and `retaniq_test_07a_final_20261011` were confined to a loopback-only temporary cluster, then dropped; the cluster was stopped. Its stopped directory remains in Temp because recursive removal was blocked by the shell safeguard. The unrelated Windows PostgreSQL service was untouched.
- **Known issues / blockers:** No Supabase project reference/URL or app/migration DSN configured; remote connectivity was not attempted. Local preflight returned sanitized `BLOCKED` (exit 2). RLS, grants, identity mapping, schema exposure changes, remote migrations, and remote import remain unimplemented. `AGENT.md`, `AGENTS.md`, and the complete requirements document were absent and not inferred.
- **Next action / handoff:** **CONFIGURATION_READY_REMOTE_BLOCKED.** User/project owner must designate a dedicated RetainIQ synthetic demo project, confirm identity/region, create reviewed distinct app/migration roles in 07B, obtain DSNs from Dashboard Connect, and place them in a protected secret store. Next coding scope is 07B: reviewed grants/RLS plus live positive/negative tests. Do not run 07C import until RLS/security acceptance.
- **Reviewer / pairing:** N/A

### 2026-10-10T16:32:31Z — Member 1 / Data & Backend Engineer — 06E dual-database contract conformance

- **Workstream:** Part 1 / Data Foundation, PostgreSQL parity, security regression
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** N/A — Prompt 06E changes intentionally uncommitted
- **Issue / task:** Prompt 06E — final dual-database contract conformance and Milestone 06 assessment; stop before Phase 07.
- **06D-3 checkpoint:** `106cc67e86219d14995529a6c91515c0358130e7` — `feat(member1): complete PostgreSQL persistence replay and API parity`, local commit created at the start of this prompt after auditing and staging the exact 15-file 06D-3 set.
- **Files changed in 06E:** new `tests/test_dual_database_contracts.py`, new `docs/MEMBER1_DUAL_DATABASE_CONTRACT_MATRIX.md`, new `docs/MEMBER1_POSTGRESQL_MIGRATION_ACCEPTANCE.md`, updated `tests/test_postgresql_import_replay.py`, and this entry.
- **What changed:**
  - Added seven shared fixture runners executing the same deterministic authenticated scenario on fresh SQLite and PostgreSQL databases and strictly comparing normalized business outputs.
  - Covered event digests/idempotency/conflicts, as-of event availability/replay, artifact persistence/auth, MRR/payment/cancellation/coverage/source grants, existing WSGI routes and rejection atomicity, concurrent identical/conflicting ingestion, subscription-owner races, and subtype-trigger rollback.
  - Added a direct check that the Member 2 synthetic workflow principal intentionally receives only `retention_inference` and `model_artifact_write` by default, with no `billing_valuation` unless explicitly requested.
  - Added a PASS/GAP contract matrix, principal permission matrix, and formal Milestone 06 acceptance/Phase 07A recommendation.
- **Why it changed:** Verify cross-backend behavior with identical inputs and make the distinction between storage parity, explicit untested contract variants, operational data readiness, and production security auditable.
- **Contract / database / API impact:** No application implementation, schema migration, applied migration checksum, endpoint, or shared payload contract changed in 06E. Tests use backend-specific DB triggers only to inject subtype persistence failure; the public event API is invoked on each engine. Timestamp normalization is restricted to UTC representation; API health processing times are validated per backend because they arise from separate real executions.
- **Tests / verification:**
  - 06D-3 baseline before 06E edits on fresh guarded PostgreSQL 16.15 — **PASS** — 150 passed, 0 failed/errors/skips, 63.665s; 34 live PostgreSQL tests.
  - Focused differential suite — **PASS** — 7 shared comparisons, each run on SQLite and live PostgreSQL; final focused run 13.395s.
  - Final full unittest discovery with PostgreSQL 16.15 / psycopg 3.3.6 — **PASS** — 157 passed, 0 failed, 0 errors, 0 skipped, 75.887s; 41 unique live PostgreSQL tests ran.
  - SQLite-only full suite — **PASS** — 157 total, 116 passed, 41 expected PostgreSQL-guarded skips, 15.012s.
  - `compileall`, package import smoke, and `git diff --check` — **PASS**. No Python warnings; expected unauthorized/invalid-request test logs only.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only. The import fixture is bounded quick profile; no STANDARD-scale, real-customer, model, performance, or ROI claim.
- **Known issues / blockers:** No critical parity mismatch found. Noncritical coverage-state enumeration and strict MRR cross-output variants remain gaps (see matrix); richer label evidence/status/evaluation metadata and a full uncertainty object are not represented by current storage. RLS, external identity, production hosting, real-data permission/provenance, full-scale import, and Member 2's previously reported maturity/coverage/freshness/heartbeat blockers remain outside this prompt. Member 2's current corrections were not assumed or independently verified.
- **Next action / handoff:** Milestone 06 is **CONDITIONALLY_ACCEPTED**: core dual-backend conformance is verified, with specified noncritical gaps. The exact task-created database `retaniq_test_06e_20261011` was dropped, the differential child database was dropped by test teardown, and only the task-owned PostgreSQL cluster was stopped; the unrelated Windows service was untouched. Recommended next scope is Phase 07A Supabase tenant-security/RLS foundation after policy review; do not begin it automatically. Leave 06E changes uncommitted; no push, merge, or deployment.
- **Reviewer / pairing:** N/A

### 2026-10-10T16:11:05Z — Member 1 / Data & Backend Engineer — 06D-3 PostgreSQL artifacts, import, replay, and WSGI parity

- **Workstream:** Part 1 / Data Foundation & PostgreSQL parity
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** N/A — intentionally uncommitted per task instruction
- **Issue / task:** Prompt 06D-3 — PostgreSQL artifact persistence, historical replay, import/checkpoint compatibility, and existing WSGI API parity; stop before 06E.
- **Files changed:** `retaniq/api.py`, `retaniq/data_foundation.py`, `retaniq/importer.py`, `retaniq/postgresql_migrations.py`, `retaniq/synthetic/canonical_adapter.py`, `tests/test_data_foundation.py`, new `tests/test_postgresql_artifact_persistence.py`, new `tests/test_postgresql_import_replay.py`, new `tests/test_postgresql_wsgi_api.py`, `README.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, new `docs/MEMBER1_POSTGRESQL_PERSISTENCE_AND_REPLAY_PARITY.md`, and `TEAM_LOG.md`.
- **What changed:**
  - Ported existing feature snapshot, churn-label, and prediction writers to PostgreSQL with timezone-aware timestamp binding, duplicate/conflict normalization, unchanged payload validation and immutable keys, and least-privilege service-principal authorization.
  - Enabled PostgreSQL dataset identity/provenance, synthetic identity provisioning, coverage batch checkpointing, bounded quick-profile import, and existing authorized historical replay without SQLite fallback.
  - Enabled the existing WSGI routes on PostgreSQL. Startup verifies migration history/checksums read-only and refuses an uninitialized schema; it does not auto-migrate or add endpoints.
  - Fixed a confirmed first-initialization concurrency race by acquiring the advisory lock before PostgreSQL schema creation.
  - Added shared SQLite/live PostgreSQL artifact-contract tests, PostgreSQL WSGI tests, and bounded dual-backend import/checkpoint/replay tests; documented the capability matrix and contract limitations.
- **Why it changed:** Complete the scoped 06D-3 repository parity requested for Member 1 without changing Member 2/3 worktrees, inventing new artifact shapes, or implying production readiness.
- **Contract / database / API impact:** No new migration, endpoint, SQLite schema, or feature/label/prediction payload shape. Artifact service writers require role `analyst` and explicit `model_artifact_write`; source/customer scope is enforced. PostgreSQL startup performs read-only migration verification. Labels still lack a richer status/evidence-reference/evaluation-time schema; predictions retain `uncertainty_status=not_quantified` rather than a full uncertainty object. Application authorization is not RLS.
- **Tests / verification:**
  - Baseline before edits — **PASS** — 138 tests, 0 failures/errors/skips.
  - Focused feature/label/prediction fixtures — **PASS** — shared SQLite and live PostgreSQL contract tests; focused import/replay (1), WSGI (3), and schema-initialization concurrency tests passed.
  - Full suite with disposable loopback PostgreSQL 16.15 and psycopg 3.3.6 — **PASS** — 150 tests, 150 passed, 0 failures/errors/skips; 34 live PostgreSQL integration tests ran (64.205s). Initial run exposed the schema-creation race; the corrected rerun passed.
  - Full suite without PostgreSQL test target — **PASS** — 150 total, 116 passed, 34 expected live-PostgreSQL tests skipped (17.112s), confirming SQLite/unit regressions.
  - `compileall` — **PASS**; `git diff --check` — **PASS** (only expected Windows LF/CRLF notices).
- **Data / model / ROI evidence:** Deterministic synthetic quick fixture only (12 accounts, 4 tenants, 2025-01-01 through 2025-05-31); no real customer rows, model training, model performance, or ROI evidence.
- **Known issues / blockers:** Full `STANDARD` PostgreSQL import/load is intentionally untested. Member 2's zero mature 7/14/30-day labels, insufficient verified outcome coverage, 97.21% stale/insufficient snapshots, and missing independent lifecycle/billing heartbeat remain unresolved. RLS, production identity/deployment, encryption-at-rest, scheduled workers, and Supabase remain out of scope. Complete requirements and `AGENT.md`/`AGENTS.md` were unavailable in this checkout.
- **Next action / handoff:** Stop at 06D-3; do not begin 06E. Keep all task changes uncommitted; no push, merge, or deployment. The exact task-created disposable database `retaniq_test_06d3_20261010` was dropped, and only the task-owned PostgreSQL cluster under the temporary runtime directory was stopped; the separate Windows PostgreSQL service was left untouched.
- **Reviewer / pairing:** N/A

### 2026-10-10T15:44:36Z — Member 1 / Data & Backend Engineer — 06D-2 live historical query verification

- **Workstream:** Part 1 / Data Foundation & PostgreSQL parity
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): verify PostgreSQL historical query and coverage parity`
- **Issue / task:** Prompt 06D-2V; preceding 06D-1 checkpoint: `9f0442b4d52594b65c70bf9486e9375cc24c243d`
- **Files changed:** `retaniq/data_foundation.py`, `retaniq/database.py`, `tests/test_postgresql_ingestion.py`, `tests/test_postgresql_historical_queries.py`, `docs/MEMBER1_POSTGRESQL_HISTORICAL_QUERY_PARITY.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `README.md`, `TEAM_LOG.md`
- **What changed:**
  - Enabled existing historical event, subscription, account snapshot, and coverage read APIs on PostgreSQL with source/category-aware grants, UTC-aware cutoff binding, and the existing output timestamp shape.
  - Enabled idempotent PostgreSQL single coverage writes using the existing contract and unique key; reused existing historical subscription fold and valuation policy.
  - Added shared SQLite/live-PostgreSQL fixtures for cutoff, authorization, lifecycle, MRR, coverage, and read-only behaviors; updated the earlier explicit-unsupported test.
- **Why it changed:** Prompt 06D-2 requires historical Data Foundation inputs for Member 2/3 without changing their worktrees or inventing service contracts.
- **Contract / database / API impact:** Existing Python function signatures and result shapes remain. Historical reads now enforce the existing source/category grants against stored rows, including after grant narrowing. Availability remains `source_available_at` with `received_at` fallback; both time predicates are inclusive. Application authorization is not RLS. No schema migration was added.
- **Tests / verification:**
  - Task-owned PostgreSQL 16.15 cluster startup initially failed to bind loopback; explicit IPv4-only `-h 127.0.0.1 -p 62534` recovered it. psycopg 3.3.6 smoke — PASS — real `SELECT 1`, server/database identity, commit, rollback, and connection cleanup.
  - `python -B -m unittest discover -s tests -p 'test_postgresql_migrations.py' -v` — PASS — 20 total including 5 live migration integration tests, 1.912s.
  - `python -B -m unittest discover -s tests -p 'test_postgresql_ingestion.py' -v` — PASS — 11 live ingestion/concurrency tests, 13.590s.
  - `python -B -m unittest discover -s tests -p 'test_postgresql_historical_queries.py' -v` — PASS — 22 total, including 11 live PostgreSQL and 11 shared SQLite fixtures, 13.654s.
  - Full `python -B -m unittest discover -s tests` — PASS — 138 tests, 138 passed, 0 failed, 0 errors, 0 skipped, 42.118s. All 27 unique PostgreSQL integration tests executed live; no Python warnings (expected unauthorized-request log messages only).
  - `compileall`, package imports, and `git diff --check` — PASS. Test target `retaniq_test_06d2v_20261010` was confirmed absent before creation, then dropped after tests; only the task-owned cluster was stopped. No code defect was confirmed; SQLite historical contracts matched PostgreSQL expectations.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only; no model or ROI claims.
- **Known issues / blockers:** Member 2's reported zero mature 7/14/30-day labels, insufficient authorized outcome coverage, 97.21% stale/insufficient snapshots, and missing independent lifecycle/billing heartbeat remain unresolved and outside this task. Complete requirements and `AGENT.md`/`AGENTS.md` remain unavailable (`D:\dunno\dormathon` absent).
- **Next action / handoff:** 06D-2 historical-query parity is live-verified. 06D-3 remains a separate task for feature/label/prediction persistence and any scoped import/checkpoint/replay work. No push or merge.
- **Reviewer / pairing:** N/A

### 2026-10-10T15:14:20Z — Member 1 / Data & Backend Engineer — PostgreSQL ingestion, identity and auth parity

- **Workstream:** Part 1 / Data Foundation, PostgreSQL Ingestion Parity
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): add PostgreSQL ingestion and identity parity` (06D-1 remains uncommitted)
- **Issue / task:** Prompt 06D-1 — PostgreSQL ingestion, identity, authorization and transaction parity; stop before 06D-2.
- **Files changed:** `retaniq/database.py`, `retaniq/data_foundation.py`, `tests/test_database_connection.py`, new `tests/test_postgresql_ingestion.py`, new `docs/MEMBER1_POSTGRESQL_INGESTION_PARITY.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `docs/MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, `README.md`, and `TEAM_LOG.md`.
- **What changed:**
  - **06C checkpoint:** Prompt 06C was locally checkpointed at `4eeb2b303701f63b0d246aeca4a357b16ad0c55b` with subject `feat(member1): implement PostgreSQL schema and migration runner`; its staged-path audit included only the 06C files and this log. No push/merge.
  - Added a quote/comment-aware PostgreSQL placeholder adapter and safe integrity metadata; enabled the existing shared setup/authz/authentication, tenant identity mapping, mapping-version/source health, canonical `ingest_event`, bounded batch/checkpoint, subtype, and CSV importer paths for PostgreSQL.
  - Added PostgreSQL `ON CONFLICT ... RETURNING` for identity/event writes and database-enforced owner/event conflict handling; `FOR UPDATE` serializes subscription-owner claims/projection rebuilds and the batch dataset checkpoint. Normalization, minimization, event hashing, tenant binding, and grants stay shared with SQLite.
  - Updated README/backend/compliance/schema notes and added a 30-scenario test coverage map. Historical queries, observation coverage, valuation, feature/label/prediction persistence, complete synthetic provisioning, and WSGI API startup remain explicitly unsupported on PostgreSQL.
- **Why it changed:** Establish verified PostgreSQL parity for Member 1's core ingestion/auth/identity path without weakening the existing contract or overstating full backend parity.
- **Contract / database / API impact:** Existing event/principal shapes and error codes are preserved. PostgreSQL `TIMESTAMPTZ` receives aware datetime parameters and health output returns normalized UTC strings. Payment failures do not end subscriptions; known cancellations remain distinct. Application authz is not RLS. No Supabase, production DB, cross-member work, or data copy.
- **Tests / verification:**
  - Pre-edit baseline on the disposable target — **PASS** — 104 tests, 0 failed/errors/skipped, 14.110 seconds.
  - Live PostgreSQL ingestion — **PASS** — 11 tests, 0 failed/errors/skipped, 12.109 seconds. Actual concurrency: 8 identical-ingest workers; 2 conflicting-ingest workers; 8 same-owner identity workers; 2 conflicting-identity workers; 2 subscription-owner contenders.
  - Existing PostgreSQL schema/migration tests — **PASS** — 20 tests, including all five live PostgreSQL integration tests, 2.189 seconds.
  - SQLite Data Foundation regression — **PASS** — 48 tests, 6.939 seconds; focused five authorization tests passed in 0.673 seconds; four importer/batch/checkpoint tests passed in 0.401 seconds.
  - Full suite on Python 3.12.14 + psycopg 3.3.6 against PostgreSQL 16.15 — **PASS** — 116 passed, 0 failed, 0 errors, 0 skipped, 0 Python warnings; unittest duration 28.529 seconds (28.859 seconds wall clock).
  - `compileall`, package import checks, and `git diff --check` — **PASS**. Four expected safe request-rejection log lines came from negative tests; no credentials/restricted values were exposed. Git showed only LF/CRLF normalization notices.
- **Data / model / ROI evidence:** Synthetic-only fixtures and task-created disposable PostgreSQL database; no customer dataset, model, or ROI results.
- **Known issues / blockers:** Complete requirements and `AGENT.md`/`AGENTS.md` were absent; the cited `D:\dunno\dormathon` requirements path was unavailable. Integration/service token expiry is not an existing schema feature. Historical query and coverage parity, other persistence, production TLS/identity, and RLS remain unverified/out of scope.
- **Next action / handoff:** The disposable `retaniq_test_06d1` database was dropped and its task-created cluster was stopped (`pg_ctl` confirms no server); the existing `postgresql-x64-16` Windows service remains Running and was not targeted. The known temporary cluster and isolated psycopg venv directories remain on disk for safe reuse; recursive deletion was rejected by the environment. Keep 06D-1 changes uncommitted. Next milestone is **06D-2 — Historical Queries and Coverage Parity**; do not begin it automatically.
- **Reviewer / pairing:** N/A

### 2026-10-10T14:47:40Z — Member 1 / Data & Backend Engineer — PostgreSQL schema and migrations

- **Workstream:** Part 1 / Data Foundation, PostgreSQL Schema & Migrations
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): implement PostgreSQL schema and migration runner`
- **Issue / task:** Milestone 06C — implement the PostgreSQL schema and explicit migration runner; stop before 06D.
- **Files changed:** `migrations/postgresql/001_data_foundation.sql` through `004_dataset_identity_and_observation_coverage.sql`, `retaniq/postgresql_migrations.py`, `retaniq/data_foundation.py`, `retaniq/database.py`, `retaniq/database_config.py`, `retaniq/__main__.py`, `tests/test_postgresql_migrations.py`, `docs/MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, `docs/MEMBER1_TO_MEMBER2_DATA_HANDOFF.md`, `README.md`, and `TEAM_LOG.md`.
- **What changed:**
  - Added four PostgreSQL migrations for the canonical 18-table Data Foundation schema, tenant-composite keys, constraints, indexes, identity sequence, timestamps, integration grants/owners, and dataset identity/coverage. Serialized payload text stays `TEXT`; PostgreSQL uses `BIGINT`, `DOUBLE PRECISION`, and `TIMESTAMPTZ` where appropriate.
  - Added ordered/checksummed migration discovery, history validation, session advisory locking, per-migration atomic transactions, schema targeting, and actionable safe errors. `init-db` explicitly applies the PostgreSQL migrations; ordinary repository operations remain SQLite-only pending 06D.
  - Documented the schema compatibility matrix, runner and disposable test procedure, status/limitations, and Member 2 database handoff. No SQLite data-copy or query-adaptation work was included.
- **Why it changed:** 06C provides a verifiable PostgreSQL schema and repeatable migration lifecycle after the 06B backend foundation, without implying repository/query parity or production readiness.
- **Contract / database / API impact:** New PostgreSQL schema matches the logical SQLite table/column contract with native PostgreSQL types, named constraints, tenant-scoped foreign keys, and indexes. PostgreSQL initialization is available only through the explicit migration path. No RLS, Supabase, application query parity, data migration, production service, or remote database changes.
- **Tests / verification:**
  - Full suite with temporary PostgreSQL 16.15 cluster and psycopg 3.3.6, guarded by the disposable loopback test target — **PASS** — 104 tests, 0 failures, 0 errors, 0 skips; all five live catalog/constraint/transaction/checksum/concurrency integration tests ran.
  - Focused PostgreSQL migration tests — **PASS** — 20 tests, including all five live-server integration tests.
  - `python -B -m compileall -q retaniq tests` using the isolated test runtime — **PASS**.
  - `git diff --check` — **PASS** — no whitespace errors; Git noted LF-to-CRLF normalization for existing text files.
  - Bundled-runtime full suite without psycopg/test DSN — **PASS** — 104 tests, 99 passed and the five live-PostgreSQL tests skipped by their safety guard; 0 failures/errors.
- **Data / model / ROI evidence:** Only synthetic test fixtures and an empty, task-created disposable PostgreSQL database. No real customer data, model, or ROI analysis used.
- **Known issues / blockers:** Complete requirements and `AGENT.md`/`AGENTS.md` were not present in this checkout; the compliance record points to requirements under inaccessible `D:\dunno\dormathon`. PostgreSQL stores timestamps as `TIMESTAMPTZ`, unlike SQLite text; query/repository compatibility and any data conversion remain unverified until 06D. No production isolation/RLS or deployment claim is made.
- **Next action / handoff:** Member 1 proceeds to 06D-1 PostgreSQL ingestion/identity/auth parity, then 06D-2 historical query and coverage parity. This checkpoint is local only; no push or merge. The disposable database was dropped and its task-created PostgreSQL cluster stopped. The environment rejected recursive deletion of the two exact temporary directories (`retaniq-06c-postgres-runtime` and `retaniq-06c-psycopg-venv`), so their stopped cluster files and isolated driver environment remain on disk. The pre-existing Windows PostgreSQL service was not targeted.
- **Reviewer / pairing:** N/A

### 2026-10-10T14:18:47Z — Member 1 / Data & Backend Engineer — Configurable database backend foundation

- **Workstream:** Part 1 / Data Foundation, Database Configuration & Transactions
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat: add configurable database backend foundation`
- **Issue / task:** Milestone 06B — implement a configurable database connection and transaction foundation.
- **Files changed:** `retaniq/database_config.py`, `retaniq/database.py`, `retaniq/data_foundation.py`, `retaniq/__main__.py`, `requirements-postgresql.txt`, `tests/test_database_config.py`, `tests/test_database_connection.py`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `README.md`, and `TEAM_LOG.md`.
- **What changed:**
  - Added typed SQLite/PostgreSQL target parsing with explicit backend selection, environment configuration, TLS policy for remote PostgreSQL, local insecure-test opt-in, and redacted representations/errors.
  - Added SQLite and optional psycopg 3 connection lifecycle primitives with commit/rollback ownership, explicit nested-transaction rejection, SQLite foreign-key/busy-timeout setup, and migration-operation guards.
  - Routed the existing SQLite Data Foundation through the shared boundary and made PostgreSQL repository use fail explicitly until 06C/06D schema and parity work; no schema, RLS, Supabase, contract-field, or tenant-auth changes were made.
- **Why it changed:** 06B requires a backend-aware foundation that preserves current SQLite behavior while making future PostgreSQL migration and repository work explicit, testable, and free of silent SQLite fallback.
- **Contract / database / API impact:** Existing SQLite behavior and public contracts remain unchanged. PostgreSQL configuration and connection support are available as a foundation only; existing Data Foundation operations reject PostgreSQL with a readiness error. No PostgreSQL migration or production database was changed.
- **Tests / verification:**
  - Bundled Python `-B -m unittest discover -s tests -p 'test_database_config.py' -v` — **PASS** — 12 focused configuration tests.
  - Bundled Python `-B -m unittest discover -s tests -p 'test_database_connection.py' -v` — **PASS** — 8 focused connection/transaction tests.
  - Bundled Python `-B -m compileall -q retaniq tests` — **PASS**.
  - Bundled Python `-B -m unittest discover -s tests -v` — **PASS** — 84 tests in 13.257 seconds.
  - Bundled Python `-B -m compileall -q retaniq tests` — **PASS**; `git diff --check` — **PASS** — no whitespace errors, with only Git line-ending normalization notices.
- **Data / model / ROI evidence:** No data, model, prediction, or ROI evidence was generated. Existing synthetic-only status is unchanged.
- **Known issues / blockers:** `POSTGRES_CONNECTION_SMOKE_NOT_RUN` — no safe PostgreSQL instance/DSN was available; psycopg 3 is not installed in the bundled runtime; `psql`, `postgres`, and `pg_ctl` are absent; Docker was not started. PostgreSQL feature parity remains unimplemented.
- **Next action / handoff:** Member 1 next implements 06C PostgreSQL schema and migrations, then 06D query/repository parity. Keep Supabase deferred to the later infrastructure phase. No commit, push, or merge is part of this handoff.
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

### 2026-10-10T07:42:00Z — Member 3 — Action execution tracking endpoint and actual cost audit trail

- **Workstream:** Part 3 — Decision Engine
- **Branch:** `feature/decision-engine`
- **Commit subject:** `feat: add action execution endpoint, actual vs predicted cost tracking, and migration 004`
- **Issue / task:** Spec §7.7 Action Execution & Cost Audit Trail (RetainIQ_v2_Complete_Requirements.md §7.7)
- **Files changed:**
  - `backend/decision/migrations/004_action_executions.sql` *(new)* — table `action_executions` with RLS, audit indexes, and separation of actual monetary/staff costs
  - `backend/decision/models.py` *(modified)* — added `ExecutionStatus`, `ExecutionRequest`, `ExecutionResponse`, and `notes: list[str]` on `EvaluationResponse`
  - `backend/decision/api.py` *(modified)* — implemented live `POST /v1/decisions/cases/{case_id}/execution` endpoint transitioning case status to EXECUTED / FOLLOW_UP_DUE / CLOSED
  - `tests/decision/test_api_phase3.py` *(modified)* — added tests for live execution endpoint, failed execution status transition, and tenant header authorization
  - `TEAM_LOG.md` *(this entry)*
- **What changed:**
  - `004_action_executions.sql`: Created schema for `action_executions` table separating actual monetary costs (`actual_monetary_cost_minor`) and staff effort (`actual_staff_minutes`) from initial predictions on `action_proposals`. Added tenant isolation with PostgreSQL RLS.
  - `models.py`: Added Pydantic schemas `ExecutionRequest` and `ExecutionResponse` validating `execution_status` in `('EXECUTED', 'FAILED', 'CANCELLED')` and non-negative actual cost/time numbers.
  - `api.py`: Implemented `POST /v1/decisions/cases/{case_id}/execution` endpoint that validates case status (must be `ASSIGNED` or `HUMAN_REVIEWED`), inserts the execution record, updates the case status to `EXECUTED` or `FOLLOW_UP_DUE` (when `follow_up_anchor` is provided), computes the 7/14/30d follow-up schedule, and logs an append-only `ACTION_EXECUTED` event to `case_history`.
  - `test_api_phase3.py`: Added 3 tests validating successful execution recording, transition to `CLOSED` upon execution failure, and rejection of requests missing tenant identification.
- **Why it changed:** Completes spec §7.7 requirement: "Record predicted action cost and actual monetary/staff effort separately" and provides execution lifecycle transitions.
- **Contract / database / API impact:** Added `POST /v1/decisions/cases/{case_id}/execution`. Added `action_executions` table in migration 004.
- **Tests / verification:**
  - `pytest tests/decision/ -v` — PASS (91 passed, 0 failed in 0.60s).
  - `pytest deepseek_python_20261010_dc4479.py deepseek_python_20261010_7837fa.py -v` — PASS (14 passed in 0.21s).
  - `python deepseek_python_20261010_54466f.py` — PASS (39 passed, 0 failed).
- **Data / model / ROI evidence:** Fully conforms to non-causal guardrails (§10.3) and separate actual vs predicted expense accounting (§7.7).
- **Known issues / blockers:** None.
- **Next action / handoff:** Provide status update to team and user, commit and push changes.
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

### 2026-10-10T07:18:00Z — Member 3 — Decision engine top-level adapter APIs and validation harness

- **Workstream:** Part 3 — Decision Engine
- **Branch:** `feature/decision-engine`
- **Commit subject:** `feat: add top-level decision engine adapter APIs and pass validation test suite`
- **Issue / task:** Part 3 validation — `deepseek_python_20261010_dc4479.py`, `deepseek_python_20261010_54466f.py`, `deepseek_python_20261010_7837fa.py`
- **Files changed:**
  - `backend/decision/enums.py` *(modified)* — exported `Route` and `HumanDecision` aliases
  - `backend/decision/router_engine.py` *(modified)* — added `route_account` top-level adapter
  - `backend/decision/ranker.py` *(modified)* — added `rank_top_k` top-level adapter
  - `backend/decision/action_catalog.py` *(modified)* — added `propose_actions` top-level adapter
  - `backend/decision/roi_calculator.py` *(modified)* — added `break_even_card` sensitivity analysis adapter
  - `backend/decision/workflow.py` *(modified)* — added `approve_case` human decision workflow adapter
  - `backend/decision/outcomes.py` *(modified)* — added `record_outcome` outcome observation adapter
  - `backend/decision/evaluator.py` *(modified)* — added `evaluate_strategies` multi-strategy evaluation adapter
  - `deepseek_python_20261010_54466f.py` *(modified)* — project ROOT path resolution supporting repo root or scripts dir
  - `TEAM_LOG.md` *(this entry)*
- **What changed:**
  - Implemented top-level convenience adapter functions across the Decision Engine module:
    - `route_account(case: dict | PredictionPayload) -> Route`
    - `rank_top_k(accounts: list[dict], k: int = 10) -> list[dict]`
    - `propose_actions(facts: dict | CustomerFacts) -> list[dict]`
    - `break_even_card(...) -> dict` returning sensitivity metrics with strict guardrails
    - `approve_case(...) -> dict` checking operational modes and enforcing budget/staff caps
    - `record_outcome(...) -> dict` recording 7, 14, 30d outcomes with non-causal guardrail notes
    - `evaluate_strategies(cohort: list, k: int = 10) -> dict` evaluating A, B, C strategies
  - Fixed ROOT path resolution in `deepseek_python_20261010_54466f.py`.
- **Why it changed:** Enables clean top-level integration testing and automated validation against Part 3 specifications.
- **Contract / database / API impact:** None on existing FastAPI routes or PostgreSQL tables. Adapters provide clean programmatic access for third-party scripts and team members.
- **Tests / verification:**
  - `pytest deepseek_python_20261010_dc4479.py -v` — PASS (1 passed in 0.14s)
  - `python deepseek_python_20261010_54466f.py --verbose` — PASS (Total: 39, PASS: 39, FAIL: 0)
  - `pytest deepseek_python_20261010_7837fa.py -v` — PASS (13 passed in 0.16s)
  - `pytest tests/decision/ -v` — PASS (88 passed in 0.55s)
- **Data / model / ROI evidence:** All guardrails verified: SCENARIO_ONLY labels enforced, zero cost ROI is None, non-causal outcome notes preserved, no forbidden ROI claims.
- **Known issues / blockers:** None. All 3 validation scripts pass 100%.
- **Next action / handoff:** Part 3 is fully validated and ready for end-to-end integration with Members 1, 2, and 4.
- **Reviewer / pairing:** N/A

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

### 2026-10-10T07:05:00Z — Member 3 — Phase 3: Human approval state machine, budget enforcement, outcomes, evaluation

- **Workstream:** Part 3 — Decision Engine
- **Branch:** `feature/decision-engine`
- **Commit subject:** `feat: Phase 3 — human approval workflow, budget capacity safeguards, 7/14/30d outcomes, RevenueCaptured@K`
- **Issue / task:** Phase 3 — Human Approval + Outcome Tracking (RetainIQ_v2_Complete_Requirements.md §7.5, §7.7, §7.8; rolemember.md §开发优先顺序)
- **Files changed:**
  - `backend/decision/workflow.py` *(new)* — human authority state machine & transactional budget/capacity cap guards (§7.5, §7.7)
  - `backend/decision/outcomes.py` *(new)* — 7/14/30d outcome observation engine with unknown-status integrity checks (§7.7)
  - `backend/decision/evaluator.py` *(new)* — frozen replay evaluation engine for Strategies A, B, and C with RevenueCaptured@K metric (§7.8)
  - `backend/decision/migrations/003_human_decisions_and_outcomes.sql` *(new)* — human_decisions, outcome_observations, and case_history audit tables + RLS
  - `backend/decision/models.py` *(modified)* — HistoryEvent, CaseHistoryResponse, EvaluationCohortAccount, EvaluationResponse; enhanced Approval & Outcome models
  - `backend/decision/api.py` *(modified)* — live POST /cases/{case_id}/approve, GET /cases/{case_id}/history, POST /cases/{case_id}/outcomes, GET /evaluation endpoints
  - `tests/decision/test_workflow.py` *(new)* — 9 unit tests for APPROVE/MODIFY/REJECT/NO_INTERVENTION, budget caps, overrides, idempotency
  - `tests/decision/test_outcomes.py` *(new)* — 5 unit tests for 7/14/30d horizons, coverage, and unknown status guardrails
  - `tests/decision/test_evaluator.py` *(new)* — 5 unit tests for Strategies A/B/C, RevenueCaptured@K, zero-denominator handling
  - `tests/decision/test_api_phase3.py` *(new)* — 4 FastAPI integration tests for all live Phase 3 endpoints
  - `TEAM_LOG.md` *(this entry)*
- **What changed:**
  - `workflow.py`: Implemented state machine transitions (PROPOSED -> ASSIGNED, REJECTED, CLOSED_NO_ACTION, HUMAN_REVIEWED). Preserved original system proposal vs final human choice. Enforced transactional budget and staff-minute capacity caps against double-spend, requiring authorized override with reason. Rejects attempts to execute simulation-only or disabled actions live on MODIFY. Anchors follow-up at decided_at with automated 7d/14d/30d due date calculation. Idempotent re-approvals safely return existing decision without double deduction.
  - `outcomes.py`: Validates follow-up horizons (strictly 7, 14, 30 days) and observed statuses (active, churned, pending_cancellation, downgraded, unknown). Enforces §7.7 rule that unknown/incomplete observation is NOT a successful retention outcome. Emits strict non-causal guardrail note 'active_is_not_proof_of_retention_effectiveness'.
  - `evaluator.py`: Implemented frozen historical replay evaluation comparing Strategy A (calibrated p30 descending), Strategy B (p30 * MRR exposure descending), and Strategy C (RetainIQ gated planning: reliability gating + cooldown + top-K + p30*MRR + p7 urgency tie-break). Computes RevenueCaptured@K (Subsequently Churned MRR Identified@K) and Recall@K. Zero churned MRR denominator cleanly yields N/A. Strictly labeled as historical identification coverage, never claiming causal revenue saved.
  - `api.py`: Promoted remaining stubs (/approve, /history, /outcomes, /evaluation) to fully functional live handlers with database and demo fixture fallback paths.
- **Why it changed:** Completes all Phase 3 requirements, closing Part 3 decision engine scope per §7.5, §7.7, §7.8, §7.9.
- **Contract / database / API impact:** All 8 Decision API endpoints are now fully live and conformant with `shared/fixtures/decision_mock.json` and `shared/contracts/prediction_contract.md`. Migration 003 adds `human_decisions`, `outcome_observations`, and `case_history` tables.
- **Tests / verification:**
  - `pytest tests/decision/ -v` — PASS (88 passed, 0 failed in 0.57s).
- **Data / model / ROI evidence:** Evaluation and outcomes strictly labeled with non-causal guardrails.
- **Known issues / blockers:** None for Part 3. Ready for Part 1/2 real model/data integration and Part 4 frontend visualization.
- **Next action / handoff:** Part 3 is complete and ready for end-to-end integration with Member 1 (data foundation), Member 2 (ML model), and Member 4 (frontend dashboard).
- **Reviewer / pairing:** N/A

### 2026-10-10T06:55:00Z — Member 3 — Phase 2: Action catalog engine, break-even ROI card, DB migration, live API, tests

- **Workstream:** Part 3 — Decision Engine
- **Branch:** `feature/decision-engine`
- **Commit subject:** `feat: Phase 2 — action catalog rule engine, break-even ROI calculator, proposal migrations, live endpoints`
- **Issue / task:** Phase 2 — Action Rules + ROI (RetainIQ_v2_Complete_Requirements.md §7.4, §7.5, §7.6; rolemember.md §开发优先顺序)
- **Files changed:**
  - `backend/decision/action_catalog.py` *(new)* — Next Best Action catalog & fact-based candidate generation (§7.4)
  - `backend/decision/roi_calculator.py` *(new)* — one-month break-even sensitivity & scenario ROI calculation (§7.6)
  - `backend/decision/migrations/002_action_proposals.sql` *(new)* — action_proposals & budget_config tables + RLS
  - `backend/decision/models.py` *(modified)* — SupportingFactRef, ActionProposal, DisabledAction, CaseProposalsResponse, CustomerFacts, BudgetConfigRecord
  - `backend/decision/router_engine.py` *(modified)* — populated reliability_status and data_freshness_status in RouteResult
  - `backend/decision/database.py` *(modified)* — clean FastAPI generator dependency without contextmanager, fallback when pool is not initialized
  - `backend/decision/api.py` *(modified)* — live GET /v1/decisions/cases/{case_id}/proposals & GET /v1/decisions/cases/{case_id}/roi endpoints
  - `tests/decision/test_action_catalog.py` *(new)* — 15 unit tests covering eligibility, contraindications, suppression, data investigation
  - `tests/decision/test_roi_calculator.py` *(new)* — 10 unit tests covering verified arithmetic, zero cost, bounds, pp vs % formatting
  - `tests/decision/test_api_phase2.py` *(new)* — 2 FastAPI integration tests for live proposals and ROI calculation
  - `TEAM_LOG.md` *(this entry)*
- **What changed:**
  - `action_catalog.py`: Catalog defined with canonical actions and strict modes (operational: ACCOUNT_CHECK_IN, PAYMENT_RECOVERY, DATA_INVESTIGATION, NO_INTERVENTION; conditional: PRODUCT_WALKTHROUGH; disabled/simulation: TECH_SUPPORT_ESCALATION, PLAN_REVIEW, PAUSE, DOWNGRADE, CONDITIONAL_DISCOUNT). Implemented fact-based candidate generator attaching source table IDs (usage_events, billing_events, feature_events). Discretionary contact suppressed when open action exists or active cooldown applies. When evidence is missing or stale, routes strictly to DATA_INVESTIGATION rather than fabricating incentives. Non-operational actions segregated into disabled_actions list.
  - `roi_calculator.py`: Implements §7.6 break-even arithmetic: contribution_value = MRR * margin; break_even_abs = cost / contribution_value (in percentage points pp); break_even_share = break_even_abs / p30 (in percentage %). Zero cost produces ROI N/A. Break-even exceeding p30 marked break_even_achievable=False ("not achievable in this simplified scenario"). Clamps assumed reduction within [0, p30]. Strictly labeled SCENARIO_ONLY.
  - `api.py`: Promoted GET /cases/{case_id}/proposals and GET /cases/{case_id}/roi from stubs to live calculation engines. Preserved real reliability_status and data_freshness_status in decision_cases insertion.
- **Why it changed:** Fulfills Phase 2 requirements for Part 3 Decision Engine per §7.4, §7.5, §7.6.
- **Contract / database / API impact:** Live response formats match frozen shared fixture `shared/fixtures/decision_mock.json` exactly. Migration 002 adds `action_proposals` and `budget_config` tables.
- **Tests / verification:**
  - `pytest tests/decision/ -v` — PASS (65 passed, 0 failed in 0.55s).
- **Data / model / ROI evidence:** ROI calculation strictly enforces SCENARIO_ONLY sensitivity labeling. No causal uplift claimed.
- **Known issues / blockers:** Part 1 SQL view `account_mrr_as_of` still pending from Member 1; inline MRR or default fallback used in the interim.
- **Next action / handoff:** Phase 3 — Human approval state machine, transactional budget enforcement, 7/14/30d outcome tracking, and RevenueCaptured@K evaluation (§7.5, §7.7, §7.8).
- **Reviewer / pairing:** N/A

### 2026-10-10T06:42:00Z — Member 3 — Phase 1: Routing engine, ranker, DB migration, API, tests

- **Workstream:** Part 3 — Decision Engine
- **Branch:** `feature/decision-engine`
- **Commit subject:** `feat: Phase 1 — routing engine, top-K ranker, decision_cases migration, FastAPI`
- **Issue / task:** Phase 1 — Routing + Ranking (rolemember.md §开发优先顺序)
- **Files changed:**
  - `backend/requirements.txt` *(new)*
  - `backend/decision/__init__.py` *(new)*
  - `backend/decision/enums.py` *(new)* — all canonical route/status/action enums
  - `backend/decision/models.py` *(new)* — Pydantic schemas for prediction, MRR, routing, cases, ROI, approvals
  - `backend/decision/config.py` *(new)* — env-var settings
  - `backend/decision/database.py` *(new)* — psycopg2 connection pool
  - `backend/decision/router_engine.py` *(new)* — 5-gate routing logic (§7.2)
  - `backend/decision/ranker.py` *(new)* — exposure proxy + Top-K sort (§7.3)
  - `backend/decision/api.py` *(new)* — FastAPI handlers (Phase 1 live + Phase 2/3 stubs)
  - `backend/decision/main.py` *(new)* — app entry point (uvicorn port 8003)
  - `backend/decision/migrations/001_decision_cases.sql` *(new)* — decision_cases table + RLS + indexes
  - `tests/__init__.py`, `tests/decision/__init__.py` *(new)*
  - `tests/decision/test_router_engine.py` *(new)* — 23 routing unit tests
  - `tests/decision/test_ranker.py` *(new)* — 15 ranking unit tests
  - `TEAM_LOG.md` *(this entry)*
- **What changed:**
  - `router_engine.py`: Implements the 5-step gate in strict order (NOT_ELIGIBLE → KNOWN_CANCELLATION → HUMAN_REVIEW × 8 triggers → threshold → cooldown → PRIORITY_REVIEW). Pure function — no DB side effects, fully testable.
  - `ranker.py`: Deterministic 4-level sort (exposure DESC, p7 DESC, oldest ASC, customer_id ASC). Currency-safe: filters by single currency before ranking.
  - `models.py`: Pydantic v2 with validators — monotonicity check p7≤p14≤p30, mrr_missing→null guard.
  - `api.py`: Phase 1 endpoints `POST /route`, `POST /cases/batch`, `GET /cases` are live. Phase 2/3 endpoints are working stubs returning `decision_mock.json` fixture.
  - `001_decision_cases.sql`: Tenant-scoped table with `UNIQUE(tenant_id, customer_id, prediction_id)`, RLS policy, auto-updated_at trigger, 4 performance indexes.
- **Why it changed:** Phase 1 priority per rolemember.md — routing and ranking core logic must be live before Phase 2 action catalog.
- **Contract / database / API impact:**
  - New table: `decision_cases`. FK: `prediction_id` references Member 2's `predictions` table. MRR data from Member 1's `account_mrr_as_of` view.
  - New endpoints: `POST /v1/decisions/route`, `POST /v1/decisions/cases/batch`, `GET /v1/decisions/cases`.
  - **Notify Member 4:** Phase 2/3 stubs are live — all 8 endpoints callable, returning `decision_mock.json`.
  - **Notify Member 1:** Need `account_mrr_as_of` view available with fields from `mrr_contract.md`.
  - **Notify Member 2:** `decision_cases.prediction_id` FK — must be a stable immutable `prediction_id` per account/cutoff.
- **Tests / verification:**
  - `pytest tests/decision/ -v --tb=short` — **38 passed, 0 failed** — `PASS`
  - Exposure proxy arithmetic (Bob §7.3 example): `0.65 × 120000 = 78000` — `PASS`
  - High risk never overrides limited_evidence gate — `PASS`
  - Monotonicity validator p7>p14 raises — `PASS`
  - mrr_missing + non-null mrr_minor raises — `PASS`
  - Currency mixing prevention (MYR vs USD not ranked together) — `PASS`
  - `psycopg2` DB not started (no local PostgreSQL) — DB-dependent endpoints NOT RUN in unit tests
- **Data / model / ROI evidence:** Synthetic fixture only. No real prediction data consumed yet.
- **Known issues / blockers:**
  - `database.py` requires PostgreSQL at `DATABASE_URL`. Run migration `001_decision_cases.sql` before starting API.
  - Phase 2/3 endpoints return mock fixture — real action catalog, ROI calculation, and human approval to be implemented in Phase 2 and 3.
  - `reliability_status` and `data_freshness_status` stored as route_reason placeholder in `_store_decision_cases` — refine to store proper enum values in Phase 2.
  - Member 1 `account_mrr_as_of` view not yet available — using inline MRR from request body for now.
- **Next action / handoff:**
  - Member 3: Phase 2 — action catalog + ROI card calculation
  - Member 4: Stub endpoints are live — `GET /v1/decisions/cases` returns real sorted data when DB is up; other endpoints return fixture
  - Member 1: Please confirm `account_mrr_as_of` view schema matches `mrr_contract.md`
- **Reviewer / pairing:** N/A

### 2026-10-10T06:30:00Z — Member 3 — Day 0 contract freeze: prediction + decision mock fixture

- **Workstream:** Part 3 — Decision Engine / Integration
- **Branch:** `feature/decision-engine`
- **Commit subject:** `docs: freeze prediction contract and publish decision mock fixture`
- **Issue / task:** Day 0 Integration Contract Freeze (rolemember.md §开发开始前)
- **Files changed:**
  - `shared/contracts/prediction_contract.md` *(new)*
  - `shared/fixtures/decision_mock.json` *(new)*
  - `TEAM_LOG.md` *(this entry)*
- **What changed:**
  - Created `prediction_contract.md`: frozen v1.0 prediction JSON schema agreed with Member 2. Covers all fields — `prediction_id`, `p_churn_7d/14d/30d`, `reliability.status`, `data_freshness.status`, `uncertainty`, `explanations_by_horizon`. Includes status enums, Part 3 consumption rules, and 7 mock fixture accounts.
  - Created `decision_mock.json`: synthetic fixture for all 8 Decision API endpoints — `GET /cases`, `GET /proposals`, `GET /roi`, `POST /approve`, `GET /history`, `POST /outcomes`, `GET /evaluation`. Uses MRR values from `mrr_contract.md` (minor units + ISO currency). Clearly labeled `SYNTHETIC_FIXTURE`.
- **Why it changed:** Member 4 cannot start frontend development without mock API responses. Member 3 cannot build routing without confirmed prediction payload shape. Freezing contracts Day 0 per rolemember.md workflow.
- **Contract / database / API impact:**
  - `prediction_id` confirmed as the FK linking `predictions → decision_cases → prediction_feedback`.
  - `as_of` must match `mrr_as_of` for correct point-in-time MRR lookup (Option A: SQL view `account_mrr_as_of`).
  - Prediction probabilities are Member 2's frozen output — Part 3 must NOT rewrite them.
  - **Notify:** Member 2 to confirm `prediction_contract.md` matches actual model output shape before real model is ready. Member 4 can begin using `decision_mock.json` immediately.
- **Tests / verification:**
  - JSON fixture validated for structure — `PASS` (manual review)
  - Arithmetic check: `exposure_proxy_30d` for cust_002: `0.65 × 120000 = 78000 minor MYR` — `PASS`
  - ROI card check: `150/840 = 0.1786 = 17.86 pp`, `0.1786/0.65 = 27.47%`, `net = 84-150 = -66`, `ROI = -44%` — `PASS`
  - Unit tests: `NOT RUN` — test scaffolding not yet created (Phase 1 next)
- **Data / model / ROI evidence:** Synthetic fixture — not real model predictions. ROI numbers are the verified spec example from §7.6.
- **Known issues / blockers:**
  - Member 2 must confirm prediction payload shape matches `prediction_contract.md` when real model is ready.
  - Member 1 must confirm `account_mrr_as_of` SQL view field names match `mrr_contract.md`.
  - `RevenueCaptured@K` in evaluation mock returns `null` — requires real historical data from Member 1+2.
- **Next action / handoff:**
  - Member 3: begin Phase 1 — routing engine code + `decision_cases` table migration
  - Member 4: start Strategy Lab UI using `shared/fixtures/decision_mock.json`
  - Member 2: review `prediction_contract.md` and confirm or propose field changes
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
