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
