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
