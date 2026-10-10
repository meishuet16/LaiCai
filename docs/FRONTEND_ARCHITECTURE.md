# RetainIQ frontend architecture

The frontend keeps five primary pages and secondary detail drawers. It is currently a UI/integration shell, not a connected production retention system.

## Navigation and shared state

`src/app/routes.ts` owns the existing route parsing and URL generation for Business Overview (`/command-center`), Data Integration (`/integrations`), Churn Prediction (`/predictions`), Retention Actions (`/cases`), and Customer Insights (`/customers/:customerId/timeline`). Prediction and case detail routes remain secondary drawers. `AppContext` owns route, account-ID search, horizon, currency, role-demo control, and the explicit data mode.

The shell does not claim an authenticated tenant, model cutoff, dataset identity, or wall-clock historical snapshot. Connected mode requires authorized server context that this frontend cannot currently obtain. A browser-selected tenant or URL value is not an authorization mechanism.

## Explicit data modes

`connected` is the default. Services do not silently replace connection failures with fixtures. Customer/prediction, decision/capacity, and customer timeline reads report unavailable because this checkout has no browser-safe authenticated API adapter or corresponding read endpoints. Data Integration also stays unavailable because the health endpoints require service-principal authorization and the browser has no approved credential flow.

`demo_fixture` is opt-in from the shell. It is labeled `DEMO FIXTURE — SAMPLE DATA`; these local illustrative records are not Synthetic SaaS v1.2 records, trained model predictions, observed outcomes, or durable decisions. Fixture account IDs are display identifiers; company/contact/owner/tenant identity and prediction cutoff metadata are not invented. Case decisions remain browser-session simulations.

## Domain and formatting

`src/domain/customer.ts` holds customer, prediction, route, and money contracts. `src/domain/currency.ts` mirrors the current backend-supported currency-code snapshot, including MYR, USD, and SGD. Money is stored as integer minor units and formatted only at the display boundary. Unsupported currencies, invalid amounts, and absent values display as `N/A`. Aggregates are grouped by currency; no exchange conversion or cross-currency total is implied.

`src/domain/integration.ts` uses the backend canonical event vocabulary. Cancellation requests, payment failures, and event-level cancellations remain distinct evidence; none is relabeled as account-level churn. Usage aggregates are daily session quantities, not individual session events.

Predictions retain independent p7/p14/p30 values and explicit non-forecast states. Client code does not invent risk thresholds, repair invalid probability order, or synthesize historical score trends. Risk-band display is used only when supplied by the prediction policy. Scenario ROI is clearly hypothetical and fixture-only; it is not measured savings, causal uplift, or an authoritative backend decision result.

## Page integration status

| Page | Connected status | Demo behavior |
|---|---|---|
| Business Overview | Customer, prediction, decision, outcome, and evaluation reads unavailable | Explicit fixture summary; currency-separated MRR/exposure; no source-backed claims |
| Data Integration | Authenticated integration-health read is not connected in browser | Explicit example health/events; canonical types; safe metadata only |
| Churn Prediction | Prediction and evaluation APIs unavailable | Fixture probabilities are identified as non-model samples; no fabricated risk history |
| Retention Actions | Case, capacity, budget, and approval APIs unavailable | Session-only decisions/execution and a `SCENARIO ONLY` slider simulator for budget, review slots, action cost, margin, and assumed risk reduction |
| Customer Insights | Customer, event, provenance, and feedback APIs unavailable | Small illustrative timeline; selected historical cutoff gates event availability |

## Current backend boundary

The active backend exposes event ingestion and service-principal integration-health routes, but no browser-safe authenticated customer, subscription/MRR, prediction/evaluation, decision, timeline, or feedback read APIs. The frontend intentionally does not invent those endpoints. See [MEMBER4_INTEGRATION.md](MEMBER4_INTEGRATION.md) for the confirmed route boundary and minimum contracts needed for integration.

## Verification

The repository's `package.json` defines `npm run build`; it does not define lint, typecheck, or test scripts. Frontend tests use Node's test runner with TypeScript stripping. See the latest `TEAM_LOG.md` entry for commands actually executed and results.
