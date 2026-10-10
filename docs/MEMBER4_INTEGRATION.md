# Member 4 frontend integration boundary

## Confirmed implementation state

The five-page React frontend has two explicit modes:

- `connected` is the default and fails visibly to `Not connected` / `Unavailable`; it never falls back to fixture records.
- `demo_fixture` is selected explicitly and globally labeled `DEMO FIXTURE — SAMPLE DATA`. It contains isolated illustrative accounts, predictions, cases, and timeline events. Those records are not Synthetic SaaS v1.2 source rows, trained predictions, durable decisions, or observed retention outcomes.

The domain uses backend-supported currency codes, stores money in integer minor units, formats according to the code's minor-unit exponent, and groups amounts by currency. It does not convert or add MYR, USD, SGD, or other currencies together. Canonical event types are defined in `src/domain/integration.ts`; `subscription_started` is not used as a canonical event.

The frontend does not select a tenant or historical cutoff by default. It cannot authorize a tenant based on URL or browser state. Fixture account and prediction tenant/cutoff metadata remain absent when not supplied.

## Backend routes confirmed in this checkout

The active Python API currently provides:

| Route | Current purpose | Frontend status |
|---|---|---|
| `POST /v1/ingest/events` | Authorized event ingestion | Not called by this read-oriented UI |
| `GET /v1/integrations` | Integration health for an authorized integration principal | Not connected; no browser-safe auth adapter |
| `GET /v1/admin/integrations` | Admin/operator integration health | Not connected; requires privileged service authorization |

These health responses do not supply the customer/business read models required by the five pages. No active HTTP routes were found for customer/subscription/MRR queries, prediction records/evaluation, decision cases/capacity/approval, customer timelines, or mature feedback/model governance. The frontend does not infer endpoints from Python service helpers or from unmerged branches.

## Minimum backend work needed for full integration

All future reads and writes need an authenticated browser-safe boundary (for example, an approved same-origin BFF), with the server deriving and enforcing tenant access. Required contracts include:

1. **Business/data:** tenant-scoped customer, subscription state, dated MRR and currency, source health, event counts, coverage, quality alerts, and authorized as-of context. Pagination and server-side aggregation are needed for the FULL dataset.
2. **Prediction:** persisted prediction IDs and run IDs, p7/p14/p30/status, reliability/freshness, policy risk bands if defined, feature evidence/explanations when available, model version, historical issued scores, and measured evaluation artifacts with provenance/sample sizes.
3. **Decisions:** cases/routes/proposals, backend rank, capacity/budget/staff limits, and transactional approve/modify/reject/no-intervention, assignment, execution, and audit APIs. Writes must return confirmed authoritative records; frontend state cannot enforce concurrency or budget limits.
4. **Customer learning:** tenant-scoped chronological source events with occurred and available/ingested times, immutable provenance, point-in-time features, linked prediction and case IDs, action follow-up, mature feedback states, and model-governance/evaluation records where implemented.

Every response should expose the tenant and dataset identity/provenance, selected historical cutoff, relevant generation/import/availability timestamps as separate fields, and pagination metadata. Historical queries must exclude records not available by the requested cutoff. Missing coverage must not be interpreted as zero activity.

## Local run and verification

```bash
npm install
npm run dev
```

`package.json` currently provides `dev`, `build`, and `preview`; there are no configured npm lint, typecheck, or test scripts. Node's built-in test runner can execute the TypeScript tests with `node --experimental-strip-types --test ...`.

Do not claim live integration, predictive performance, saved revenue, causal action effect, or measured ROI until the corresponding authenticated backend contracts and evidence are implemented and verified.
