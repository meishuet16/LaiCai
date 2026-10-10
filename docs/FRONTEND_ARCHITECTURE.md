# RetainIQ frontend architecture — Five primary pages

This is a local, synthetic frontend foundation. No API, trained model, authenticated tenant, or persistent decision workflow is connected.

## Navigation

`src/app/routes.ts` owns route parsing and URL generation. `AppContext` synchronizes route state with browser history, including Back/Forward and drawer closing. The five primary pages are Business Overview (`/command-center`), Data Integration (`/integrations`), Churn Prediction (`/predictions`), Retention Actions (`/cases`), and Customer Insights (`/customers/:customerId/timeline`). Existing prediction and case detail URLs (`/predictions/:predictionId`, `/cases/:caseId`) are secondary drawers over their parent pages, not primary navigation pages. All five page components stay mounted to preserve filters and scroll when switching between related drawers/pages.

## State and data

`AppContext` holds route, search, horizon, currency, and the simulated demo role. The displayed tenant and role are fixture controls, not authorization. A future backend must derive tenant identity and enforce permissions server-side.

`src/domain/customer.ts` defines the shared account, money, route, reliability, freshness, and prediction types. Money uses integer minor units plus currency. A scored prediction has distinct 7/14/30-day values and an immutable prediction ID. `src/services/retainIQService.ts` defines `RetainIQDataSource`; the current implementation supplies synthetic records. Later API adapters can implement the same interface without making pages own transport logic.

`useCustomers` and `useAccount` handle asynchronous loading and failure states. They cancel obsolete requests when unmounted or when an account changes. Pages show explicit loading, empty, error, and missing-record states.

## Data Integration and Churn Prediction

`src/domain/integration.ts` and `src/services/integrationService.ts` define the source health, coverage, alert, and rejected-event read model. Data Integration keeps event occurrence and availability/ingestion timestamps distinct, links actionable checks to safe source details, and shows rejected-event metadata only in a redacted inspector. Missing source-level schema, separate quarantine counts, sensitivity, and provenance remain unavailable rather than inferred. The page omits Push API and Historical Replay panels; import, synchronization, replay, resolution, and report operations are not presented as available without a real authorized backend.

Churn Prediction reads shared account records through `useCustomers`, with account search, currency, horizon, risk-band, route, reliability, freshness, segment, owner, sort, and pagination controls. Unknown-MRR accounts stay visible under a currency filter. The account table displays supplied p7/p14/p30 outputs directly, flags missing, out-of-range, or non-monotonic values without rewriting them, and keeps known cancellations and ineligible records in separate non-forecast sections. A URL such as `/predictions/demo_pred_c02` opens an accessible prediction detail drawer through `getPrediction`, preserving the parent table state. Baselines and model attributions are shown as unavailable unless supplied; uncertainty is explicitly not quantified. The app has no per-account risk-history stream or held-out evaluation results, so those states remain unavailable rather than becoming fabricated trends or metrics. Risk bands are display-only, consistently colored, and are not decision-policy thresholds.

## Retention Actions

`src/domain/decision.ts` defines the case, proposal, audit, decision, execution, and capacity contracts. `src/services/decisionService.ts` holds a synthetic in-memory case fixture and implements guarded demo decisions and execution records. Work Queue exposes all five routes, workload/capacity/budget indicators, ranked risk, evidence status, and case drawers. Case details include related timeline evidence, eligible proposals, required reason/owner inputs, confirmation, execution actuals, follow-up, outcome maturity gaps, and audit history. Strategy & ROI provides explicitly labeled budget/capacity what-if arithmetic, an assumption-only break-even calculator, and an unavailable historical-replay comparison state.

The demo role selector is not authentication. Decisions are not persisted after reload and do not send messages or payment requests. Checks for slots, minutes, budget, cooldown, eligibility, and tenant/role permissions must move to a transactional, authenticated server before real use. The current service checks slot, staff-minute, and budget availability only in browser memory and does **not** claim concurrency safety. Synthetic fact IDs do not link to real source records.

`src/domain/scenario.ts` is a pure one-month, assumption-only break-even calculator. It keeps absolute churn reduction in percentage points distinct from its share of baseline p30, marks mathematically impossible break-even, and returns `N/A` for invalid or missing inputs. It does not estimate causal treatment effect.

## Business Overview

`src/services/dashboardService.ts` joins the current account/case fixture read models and includes the separate Data Integration example for alert display. `src/domain/dashboard.ts` applies filters and derives coverage, route/workload, risk bands, currency-separated at-risk exposure, selected actions, recorded decisions, cost/effort, missingness, and available response latency. Business Overview exposes shared search/currency/horizon controls plus route, action status/type, owner, and segment filters. A visible workflow strip and chart selections link to customer, prediction, and case context.

The account/case cohort has nine synthetic rows. Data Integration's larger source aggregate fixture is a **different example population**; its alert count is labeled separately and is not combined with account totals. There is only one prediction cutoff and no complete historical decision-event stream, source-backed outcome/feedback table, measured model metrics, or approved model registry. Trend, full lifecycle funnel/rates, outcome breakdown, maturity, PR-AUC/Brier/calibration/Recall@K, and candidate comparison therefore show `N/A` / `NOT_READY`, never fabricated evidence. Budget/effort actuals remain distinct from estimates, and absent actuals are not displayed as zero.

## Customer Insights

`src/domain/timeline.ts` defines read-only timeline events and a pure historical visibility gate. An event appears at a selected cutoff only when both its occurrence time and record availability time are no later than that cutoff. Prediction feedback uses the prediction's `as_of` anchor: an unfinished horizon is `PENDING`; once the window ends, the UI shows `NOT_CONNECTED` until a source-backed feedback record exists, never an inferred negative. `NOT_CONNECTED` is a display availability marker, not a canonical feedback label. Known cancellations and ineligible predictions are `INELIGIBLE`.

`src/services/timelineService.ts` combines the account/prediction fixture, case audit snapshot, and a small set of redacted synthetic source events. `useTimeline` handles loading, missing records, and cancellation. Customer Insights offers UTC date-range, category, event-type, decision/source-only, horizon, and historical-cutoff filters; chronological events; timestamp/provenance detail; and links to the related Churn Prediction and Retention Actions drawers. Restricted payloads are absent, not client-side hidden behind the simulated role selector.

The case fixture includes workflow history older than the single displayed prediction. Timeline case events therefore **do not claim** a `prediction_id` association. An action reconstructed from the case snapshot is labelled as such, not presented as an authoritative immutable execution record. Numeric feature/baseline snapshots, raw source links, source-backed outcomes, complete prediction-feedback records, and model-evaluation links remain `N/A`. A real API must supply immutable tenant-authorized events, true availability timestamps, historical account state, source permissions, explicit case/prediction linkage, and mature coverage evidence before production use.

## Current limits and next handoff

Business Overview, Customer Insights, and Data Integration/Churn Prediction figures are synthetic examples. Live integrations, predictions, role enforcement, durable decisions, authoritative audit history, and mature outcomes require their owning backend contracts. The five-page experience is a demo architecture, not a production-integrated retention system.
