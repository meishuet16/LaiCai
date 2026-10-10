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

### 2026-10-10T19:23:22Z — Florence / Member 4 — simplify data integration and strengthen LaiCai branding
- Workstream: Part 4 / Frontend
- Branch: main
- Commit subject: `feat: simplify data integration and strengthen LaiCai branding`
- Issue/task: N/A
- Files changed: `src/features/IntegrationHealthPage.tsx`, `src/index.css`
- What changed:
  - Increased the LaiCai sidebar wordmark to a prominent semibold Inter treatment.
  - Removed duplicate per-source summary cards from Data Integration because the source health table already provides the same inspectable status and freshness data.
  - Removed unavailable historical import, sync, and report cards that added no actionable capability to the read-only demo.
- Why: Reduce visual noise while keeping source health, coverage, quality alerts, rejected-event counts, and detail inspection available.
- Contract/API: None.
- Tests: `npm run build` — PASS.
- Data/model: Synthetic fixture data unchanged.
- Known issues: None introduced.
- Next: Review the simplified Data Integration layout in the running app.
- Reviewer: Pending.

### 2026-10-10T19:22:00Z — Florence / Member 4 — rename frontend product branding

- **Workstream:** Part 4 / Frontend
- **Branch:** `main`
- **Commit subject:** `chore: rename frontend branding to LaiCai`
- **Issue / task:** `N/A`
- **Files changed:** `index.html`, `src/app/AppShell.tsx`
- **What changed:**
  - Replaced the visible RetainIQ product name and mark with LaiCai in the sidebar and document metadata.
  - Updated the accessible product label and browser title/description to match the new name.
- **Why it changed:** The product should be presented as LaiCai throughout the user-facing frontend.
- **Contract / database / API impact:** None.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript compilation and Vite production build completed successfully.
  - `rg -n "RetainIQ|LaiCai" src/app/AppShell.tsx index.html` — PASS — visible frontend branding is LaiCai.
- **Data / model / ROI evidence:** N/A.
- **Known issues / blockers:** Internal service/type names and historical documentation retain RetainIQ identifiers for compatibility and traceability.
- **Next action / handoff:** None.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T19:17:08Z — Florence / Member 4 — consolidate RetainIQ frontend UX

- **Workstream:** Part 4 / Frontend
- **Branch:** `main`
- **Commit subject:** `feat: refine RetainIQ frontend workflow and visual system`
- **Issue / task:** `N/A`
- **Files changed:** `src/app/AppShell.tsx`, `src/components/CustomerTable.tsx`, `src/components/CustomerSwitcher.tsx`, `src/components/StatusPills.tsx`, `src/domain/decision.ts`, `src/features/CommandCenterPage.tsx`, `src/features/DecisionCaseDetailPage.tsx`, `src/features/DecisionCasesPage.tsx`, `src/features/PredictionDetailPage.tsx`, `src/features/PredictionRadarPage.tsx`, `src/features/TimelinePage.tsx`, `src/hooks/useCustomers.ts`, `src/index.css`, `src/services/decisionService.ts`
- **What changed:**
  - Refined the five-page dashboard flow: centered prediction details, compact timeline context, customer switching, all-case queue access, and lighter status/chart colors.
  - Removed visible owner fields and owner filters from the frontend workflow while preserving case status and due-date information.
  - Added collapsible icon-only navigation, consistent light-green button hover states, and shared typography tokens using Inter/system-ui with tabular numerals.
- **Why it changed:** The frontend needed a tighter review workflow, less verbose decision context, more usable navigation, and a consistent visual language across all five pages.
- **Contract / database / API impact:** No database or external API contract changes. Decision input owner is optional for the browser-only simulation; fixture data remains synthetic.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript compilation and Vite production build completed successfully.
  - Manual browser checks — PASS — prediction filters, retention case detail, compact navigation, and owner-free approval controls rendered in the local app.
- **Data / model / ROI evidence:** Synthetic demo fixtures and assumption-only ROI values; no live model or customer data added.
- **Known issues / blockers:** None known for the local frontend. Generated build/cache files remain untracked and are intentionally excluded.
- **Next action / handoff:** Connect the frontend reads and decision writes to the verified backend contracts when available.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T15:00:00Z — Florence / Member 4 — initialize frontend dashboard

- **Workstream:** Part 4 / Frontend
- **Branch:** `main`
- **Commit subject:** `feat: scaffold member4 dashboard and integration docs`
- **Issue / task:** `N/A`
- **Files changed:** `src/App.tsx`, `src/index.css`, `src/data/mockData.ts`, `src/main.tsx`, `src/vite-env.d.ts`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `docs/MEMBER4_INTEGRATION.md`, `.gitignore`
- **What changed:**
  - Scaffolded a Vite + React + TypeScript dashboard foundation for the RetainIQ Member 4 workstream.
  - Added a business-facing review UI with summary metrics, risk distribution, recommendation cards and an account queue table.
  - Added the initial Member 4 integration documentation describing the module boundaries, mock-mode behavior, and next implementation steps.
- **Why it changed:** The repo started as documentation-only and needed a runnable front-end shell that matches the dashboard responsibilities and the repo rules for honest demo data labeling.
- **Contract / database / API impact:** None yet; this is a mock demo layer only, with the UI explicitly flagged as `synthetic` / `assumption` and not presented as real model output.
- **Tests / verification:**
  - `npm run build` — PASS — Vite production build completed successfully in the repo.
- **Data / model / ROI evidence:** Synthetic demo fixtures and assumption-only labels; no live prediction, decision, or financial data was fabricated as real evidence.
- **Known issues / blockers:** The prediction and decision engine contracts are not connected yet, so the dashboard remains a frontend scaffold with mock data until the backend integration is added.
- **Next action / handoff:** Connect this dashboard to the real ingestion/prediction/decision APIs, swap in real data contracts, and then replace the demo-mode labels with verified live results.
- **Reviewer / pairing:** `N/A`

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
