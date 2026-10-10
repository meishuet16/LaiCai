# RetainIQ v2 — Team Development & Commit Log

**Project:** Dormathon 2026 — RetainIQ v2<br>
**Purpose:** Give every team member a shared, truthful record of what changed in **every Git commit**.<br>
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

### 2026-10-10T21:55:25Z — Codex — Refine and reconcile frontend workflow views

- **Workstream:** Frontend / Integration / QA
- **Branch:** `member4`
- **Commit subject:** `fix: refine frontend workflow and navigation views`
- **Issue / task:** Review the remaining local frontend changes before aligning them with the latest main branch.
- **Files changed:** `index.html`, `src/app/AppShell.tsx`, `src/components/CustomerSwitcher.tsx`, `src/components/CustomerTable.tsx`, `src/components/StatusPills.tsx`, `src/domain/decision.ts`, affected page components in `src/features/`, `src/hooks/useCustomers.ts`, `src/index.css`, `src/services/decisionService.ts`, and this log.
- **What changed:** Added a customer switcher and collapsible navigation, centered prediction details, compacted queue/status presentation, removed unsupported owner display/requirement, simplified Integration page sections, and wired the Retention Actions simulator as a slider-driven view. Corrected prediction evidence wording to match the frontend domain and retained the requirement that timeline facts are hidden until an explicit cutoff is selected.
- **Why it changed:** Consolidate the reviewed frontend refinements while preserving the five-page shell, fixture workflow, and point-in-time timeline behavior.
- **Contract / database / API impact:** None; connected service adapters and backend contracts are unchanged. Demo decisions remain browser-session-only.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production build.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Illustrative fixture data only; no trained predictions, connected outcomes, or measured ROI are claimed.
- **Known issues / blockers:** Decision and timeline data remain fixture-backed in demo mode; no browser-safe connected read or approval adapter is implemented.
- **Next action / handoff:** Reconcile this frontend commit with current `main`, keeping main-branch data/backend work and unrelated untracked files intact.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T18:08:07Z — Codex — Center and emphasize Retention Actions tabs

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `style: center and emphasize retention action tabs`
- **Issue / task:** Center the Work Queue and Strategy & ROI Simulator view selectors and make the selected view easier to identify.
- **Files changed:** `src/index.css` and this log.
- **What changed:** Centered the two tab buttons, gave them equal visual weight, increased their size, added a clear selected-state treatment and hover feedback, and centered the labels on narrow screens.
- **Why it changed:** The existing tabs were left-aligned and visually understated in a full-width strip.
- **Contract / database / API impact:** None.
- **Tests / verification:**
  - `git diff --check` — PASS — no whitespace errors.
  - Automated tests/build — NOT RUN — CSS-only visual change; no behavior or data contracts changed.
- **Data / model / ROI evidence:** N/A; presentation-only change.
- **Known issues / blockers:** None known.
- **Next action / handoff:** Review the updated tabs in the local Retention Actions page.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T18:01:53Z — Codex — Show only useful page controls in the header

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `fix: simplify contextual dashboard controls`
- **Issue / task:** Make the shared filter bar intuitive and remove fields that do not change the current view.
- **Files changed:** `src/app/AppShell.tsx`, `src/index.css`, and this log.
- **What changed:** Removed the noninteractive Tenant and As-of/model chips and the duplicate global account search. Search remains in the Churn Prediction and Retention Actions tables. The Data source selector remains available on every page; Currency appears only in Churn Prediction and Retention Actions; Horizon only in Churn Prediction and Customer Insights; Role preview only in Retention Actions and Customer Insights. Removed obsolete header styles.
- **Why it changed:** Several header controls were static or had no effect on the page showing them, while account search duplicated table filters.
- **Contract / database / API impact:** None; source mode, currency, horizon, and role state remain unchanged.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (all five primary pages on port 5180) — PASS — each page shows only relevant controls; Customer Insights header layout was visually checked.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Data source still says `Sample data`; no backend or model outputs changed.
- **Known issues / blockers:** No connected tenant/as-of context is available yet; those static placeholders were removed rather than presented as filters.
- **Next action / handoff:** Review on `member4`; do not push or merge without approval.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:54:55Z — Codex — Remove repeated demo indicators across pages

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `fix: remove repeated demo indicators from dashboard`
- **Issue / task:** Remove prominent demo badges and banners from all five primary pages.
- **Files changed:** `src/app/AppShell.tsx`, `src/features/IntegrationHealthPage.tsx`, `src/features/PredictionRadarPage.tsx`, `src/features/PredictionDetailPage.tsx`, `src/features/StrategyRoiSimulator.tsx`, `src/features/TimelinePage.tsx`, and this log.
- **What changed:** Removed the global notice and sidebar footer; removed per-page fixture badges from Data Integration, Churn Prediction, Customer Insights, prediction details, and the ROI simulator. The functional Data source selector now says `Sample data` for fixture mode, and the non-authenticated role control says `Role preview`. Scenario-only and unavailable-state labels remain where they describe real limitations.
- **Why it changed:** Repeated visual indicators cluttered the five-page dashboard.
- **Contract / database / API impact:** None; fixture/connected separation and unavailable states are unchanged.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (all five primary pages on port 5180) — PASS — repeated demo badges absent; Sample data selector visible.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Fixtures remain selected by default and are labelled Sample data in the selector; no real model or backend integration is implied. Scenario-only calculations remain labelled.
- **Known issues / blockers:** Connected prediction and decision APIs remain unavailable as previously logged.
- **Next action / handoff:** Review on `member4`; do not push or merge without approval.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:50:10Z — Codex — Remove duplicate Customer Insights fixture notices

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `fix: remove duplicate customer fixture notices`
- **Issue / task:** Remove the two long fixture banners shown above Customer Insights.
- **Files changed:** `src/app/AppShell.tsx`, `src/features/TimelinePage.tsx`, and this log.
- **What changed:** Suppressed the global notice on Customer Insights and removed that page's duplicate local notice. The Data mode selector, sidebar fixture marker, and customer-card fixture badge still identify demo-only data.
- **Why it changed:** The repeated warnings pushed customer information below the fold without adding distinct information.
- **Contract / database / API impact:** None; connected-mode unavailable states and historical cutoff behavior are unchanged.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (`/customers/c01/timeline` on port 5180) — PASS — both top notices absent; fixture indicators remain.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Demo fixture remains explicitly identified; no source, prediction, decision, or outcome values changed.
- **Known issues / blockers:** Connected timeline APIs remain unavailable as previously logged.
- **Next action / handoff:** Review on `member4`; do not push or merge without approval.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:37:04Z — Codex — Remove ownership from Customer Insights

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `fix: remove owner from customer insights`
- **Issue / task:** Remove the demo staff-owner field shown on the Customer Insights page.
- **Files changed:** `src/features/TimelinePage.tsx` and this log.
- **What changed:** Removed Owner from the customer summary and removed the assignee name from the decision-context summary, retaining the case due date. Retention Actions still owns assignment controls.
- **Why it changed:** Synthetic SaaS v1.2 customer source data has no staff-owner field; the displayed name was fixture-only and distracting in the customer profile.
- **Contract / database / API impact:** None.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (`/customers/c01/timeline` on port 5180) — PASS — no Owner in the customer summary or current decision context; Case due remains.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Demo fixture only; no source or prediction values changed.
- **Known issues / blockers:** Staff assignment remains browser-session-only in Retention Actions; connected decision APIs are unavailable.
- **Next action / handoff:** Review on `member4`; do not push or merge without approval.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:28:52Z — Codex — Center and simplify Retention case details

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `fix: center and simplify retention case details`
- **Issue / task:** Open Retention case details in the center and reduce initial copy density.
- **Files changed:** `src/app/AppShell.tsx`, `src/features/DecisionCaseDetailPage.tsx`, `src/index.css`, and this log.
- **What changed:** The case detail route now uses a centered, responsive modal while prediction details retain their side drawer. The case summary is shorter; evidence, proposals, ROI, audit history, and outcome feedback are expandable sections. Decision and execution controls remain available.
- **Why it changed:** The side drawer was too dense for the case workflow.
- **Contract / database / API impact:** None. Demo decisions remain browser-session-only.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (`/cases/demo_case_c02` on port 5180) — PASS — case opens centered from the queue; close button and Escape return to the queue.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Demo fixture only; no prediction, outcome, or ROI claims changed.
- **Known issues / blockers:** Connected decision APIs remain unavailable as previously logged.
- **Next action / handoff:** Review on `member4`; do not push or merge without approval.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:23:15Z — Codex — Keep the Retention Actions workload strip to five cards

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `fix: show five retention workload cards`
- **Issue / task:** Remove the lone sixth workload card from the Retention Actions Work Queue.
- **Files changed:** `src/features/DecisionCasesPage.tsx` and this log.
- **What changed:** Removed the standalone Investigation queue card and retained its count in the Awaiting review card subtitle. The strip now has five cards at all viewport sizes.
- **Why it changed:** The sixth card wrapped onto its own row on the reference desktop layout.
- **Contract / database / API impact:** None; all counts still come from the existing demo capacity record.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (`/cases` on port 5180) — PASS — five capacity/workload cards rendered, with the investigation count inside Awaiting review.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** Demo fixture values only; no backend integration or business metric was changed.
- **Known issues / blockers:** Connected decision APIs remain unavailable as previously logged.
- **Next action / handoff:** Continue layout review on `member4`; do not push or merge without approval.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:19:22Z — Codex — Soften Retention Actions case-button hover

- **Workstream:** Frontend / QA
- **Branch:** `member4`
- **Commit subject:** `fix: use light-green hover for retention case buttons`
- **Issue / task:** Change the Retention Actions work-queue case button hover from dark green to light green.
- **Files changed:** `src/index.css` and this log.
- **What changed:** Scoped a pale-green hover and keyboard-focus style to the outlined work-queue case buttons, retaining dark-green readable text and border.
- **Why it changed:** The shared `.btn:hover` rule turned these outlined buttons dark even though their normal treatment is light.
- **Contract / database / API impact:** None.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - Safari local Vite check (`/cases` on port 5180) — PASS — the work-queue case button displayed the light-green hover and still opened/closed its case drawer.
  - `git diff --check` — PASS — no whitespace errors.
- **Data / model / ROI evidence:** N/A; presentation-only change to the explicitly labelled demo view.
- **Known issues / blockers:** None for this hover change. Connected decision APIs remain unavailable as previously logged.
- **Next action / handoff:** Continue frontend visual review on the `member4` branch; do not merge or push without approval.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:11:19Z — Codex — Keep demo fixtures as the initial frontend view

- **Workstream:** Frontend / QA / Docs
- **Branch:** `member4`
- **Commit subject:** `fix: keep demo fixtures visible until integrations exist`
- **Issue / task:** Preserve the existing mock customer and case data while Members 2 and 3 integrations are unavailable.
- **Files changed:** `src/app/AppContext.tsx`, `src/services/retainIQService.ts`, `src/services/decisionService.ts`, `src/features/DecisionCasesPage.tsx`, `src/features/StrategyRoiSimulator.tsx`, related service tests, `docs/FRONTEND_ARCHITECTURE.md`, and this log.
- **What changed:**
  - Made explicitly labelled `demo_fixture` the initial view; selecting Connected mode still shows its real unavailable state and never falls back silently.
  - Restored the original illustrative company names and seeded owners in demo records, and displayed names with stable IDs in the work queue and slider simulator.
- **Why it changed:** The backend customer/prediction and decision workflows are not yet integrated, and defaulting to unavailable pages hid the useful mock UI during frontend development.
- **Contract / database / API impact:** None. No production identity, tenant, prediction cutoff, API response, or shared backend schema was changed.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (`/cases` on port 5180) — PASS — a fresh load selected Demo fixture, showed Northwind Logistics/Janice and Meridian Foods/Jasmine, and displayed named cases with five sliders in Strategy & ROI Simulator.
- **Data / model / ROI evidence:** Illustrative local fixtures and scenario assumptions only; no trained model output, authenticated tenant, production decision, measured outcome, or causal ROI.
- **Known issues / blockers:** Member 2/3 browser-safe prediction and decision APIs are not connected. Demo case changes remain browser-session-only; Connected mode remains unavailable.
- **Next action / handoff:** Replace the sample adapters only after authoritative tenant-scoped APIs and authentication are supplied; preserve the explicit demo/connected separation.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T17:01:33Z — Codex — Add slider-driven Strategy & ROI simulator

- **Workstream:** Frontend / QA / Docs
- **Branch:** `member4`
- **Commit subject:** `feat: add slider-driven strategy and ROI simulator`
- **Issue / task:** Convert the Retention Actions Strategy & ROI tab into an interactive slider simulator.
- **Files changed:** `src/features/DecisionCasesPage.tsx`, `src/features/StrategyRoiSimulator.tsx`, `src/index.css`, `docs/FRONTEND_ARCHITECTURE.md`, and this log.
- **What changed:**
  - Replaced number-field what-ifs with sliders for same-currency scenario budget, review slots, assumed action cost, contribution margin, and assumed absolute churn reduction.
  - Added live allocation and one-month break-even previews, including budget/slot meters, a candidate list, threshold marker, and explicit scenario-only labels.
- **Why it changed:** Make resource and ROI assumptions easier to explore while keeping hypothetical results distinct from actual decision-engine allocations or measured outcomes.
- **Contract / database / API impact:** None. The simulator uses explicit local demo fixtures and existing scenario arithmetic; no backend writes or new endpoints.
- **Tests / verification:**
  - `npm run build` — PASS — TypeScript and Vite production bundle.
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - Safari local Vite check (`/cases`, explicit demo fixture mode) — PASS — Strategy & ROI simulator rendered; a zero budget removed the candidate from the allocation, and changing assumed reduction from 10.0 to 25.2 pp recalculated hypothetical net value from -RM 66.00 to RM 61.68.
- **Data / model / ROI evidence:** Illustrative fixture records and editable scenario assumptions only; no source-backed budget allocation, causal uplift, observed savings, or measured ROI.
- **Known issues / blockers:** Connected decision-case and budget/capacity APIs remain unavailable; the simulator does not commit decisions or evaluate strategy performance.
- **Next action / handoff:** Integrate authorized decision and budget contracts when supplied by Member 3; retain scenario-only labeling until then.
- **Reviewer / pairing:** `N/A`

### 2026-10-10T16:43:30Z — Codex — Align frontend data contracts and unavailable states

- **Workstream:** Frontend / Integration / QA / Docs
- **Branch:** `member4`
- **Commit subject:** `fix: align frontend with canonical synthetic contracts`
- **Issue / task:** Correct RetainIQ frontend content and align the five-page UI with current Synthetic SaaS v1.2/backend contracts.
- **Files changed:** `src/`, `docs/FRONTEND_ARCHITECTURE.md`, `docs/MEMBER4_INTEGRATION.md`, and this log.
- **What changed:**
  - Added backend-supported currency-code validation and currency-aware minor-unit formatting; retained separate currency aggregates and corrected scenario amount conversion.
  - Replaced the legacy subscription event alias with the current canonical event vocabulary; distinguished event time, availability, and source semantics.
  - Added explicit `connected` and opt-in `demo_fixture` data modes. Connected pages now report missing authenticated reads instead of silently substituting sample accounts, predictions, cases, or timelines.
  - Removed the hardcoded tenant/cutoff shell assumptions and fixture CRM names/owners; made identity search account-ID based and applied it to the prediction table.
  - Updated prediction/status, historical cutoff, freshness, MRR exposure, timeline, and workflow UI states; preserved the five routes and existing drawers.
- **Why it changed:** The previous UI represented a hand-written fixture as source/model data, used outdated money/event assumptions, and displayed tenant/cutoff context unsupported by the active backend.
- **Contract / database / API impact:** Frontend-only domain/service adapter changes; no shared Python contracts or database schema changed. Confirmed active API routes are `POST /v1/ingest/events`, `GET /v1/integrations`, and `GET /v1/admin/integrations`. The frontend does not call them: service-principal authentication has no approved browser-safe adapter, and no customer, prediction/evaluation, decision, timeline, or feedback read route is present.
- **Tests / verification:**
  - `node --experimental-strip-types --test src/app/routes.test.ts src/services/retainIQService.test.ts src/services/integrationService.test.ts src/services/decisionService.test.ts src/domain/scenario.test.ts src/domain/dashboard.test.ts src/domain/overview.test.ts src/domain/timeline.test.ts src/domain/predictionPresentation.test.ts src/domain/customerFilters.test.ts src/domain/format.test.ts` — PASS — 38 tests.
  - `npm run build` — PASS — TypeScript project build and Vite production bundle (47 modules).
  - `git diff --check` — PASS — no whitespace errors.
  - `npm run lint`, `npm run typecheck`, and `npm test` — NOT RUN — these scripts are not defined in `package.json`.
- **Data / model / ROI evidence:** Demo fixture records and user-entered ROI assumptions only. No trained model output, source-backed business result, historical evaluation, causal uplift, or saved revenue is claimed.
- **Known issues / blockers:** Connected customer, prediction, decision, timeline, evaluation, outcome, and browser-safe integration-health APIs remain unimplemented/unavailable. Retention decisions remain session-only in explicit demo mode; scenario arithmetic is illustrative, not backend-authoritative ROI.
- **Next action / handoff:** Backend owners should provide tenant-authorized paginated read contracts and transactional decision endpoints behind an approved browser-safe auth boundary before connected mode can be enabled.
- **Reviewer / pairing:** `N/A`

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
