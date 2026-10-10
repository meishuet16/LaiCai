# LaiCai frontend architecture

The frontend exposes six primary views plus prediction and case detail drawers. The default path is an end-to-end local workspace backed by the authenticated, tenant-scoped SQLite adapter.

## Navigation and shared state

`src/app/routes.ts` owns Business Overview (`/command-center`), Data Integration (`/integrations`), Churn Prediction (`/predictions`), Retention Actions (`/cases`), Customer Insights (`/customers/:customerId/timeline`), and Learning & Model Health (`/learning`). `AppContext` owns route, horizon, currency and workspace-role display state.

## Connected data path

The Vite frontend calls the FastAPI adapter through `/api`. The adapter reads the generated SQLite workspace with a DPAPI-protected service-principal token. The source database is never edited; `scripts/seed_dashboard_demo.py` creates a separate working copy and adds versioned predictions, persisted retention cases, horizon feedback state and model-release governance records.

The connected path covers:

- account, subscription/MRR and prediction reads;
- source health, event counts, freshness and observation coverage;
- persisted cases, capacity, decision, execution and follow-up audit changes;
- customer prediction/case timelines;
- outcome maturity and governed model-release state.

The repository retains isolated fixture adapters for unit tests and offline development, but the product UI does not expose a data-source switch or silently fall back when the backend is unavailable.

## Evidence boundaries

`src/domain/customer.ts` holds customer, prediction, route and money contracts. Money remains integer minor units and is always grouped by currency. Cancellation requests, payment failures and effective cancellations are distinct facts. Predictions keep independent p7/p14/p30 values and explicit non-forecast states; the client never repairs invalid probabilities or invents historical trends.

The working dataset is an explicitly identified synthetic evaluation cohort. Product copy avoids repeated prototype language, while Learning & Model Health preserves the material provenance boundary. No real-world uplift, saved revenue or production model performance is claimed. Scenario ROI remains assumption-based and separate from measured outcomes.

## Page integration status

| Page | Connected capability |
|---|---|
| Business Overview | Cohort, forecast, workload, freshness, MRR and exposure summaries |
| Data Integration | Three source records, canonical events, sync timestamps, coverage and alerts |
| Churn Prediction | Persisted multi-horizon forecasts, reliability, freshness and explanations |
| Retention Actions | Persisted cases, budget/capacity, human decisions, execution and follow-up audit |
| Customer Insights | Account, forecast and case history with occurrence/availability timestamps |
| Learning & Model Health | Feedback maturity, coverage/abstention/coherence checks and release gates |

## Verification

Use `npm run test:frontend`, `npm run build`, and `py -3.14 -m pytest tests/decision -q`. The local walkthrough additionally verifies browser → API → SQLite reads on every primary route.
