# Member 2 Cross-Member Integration Contracts

This document is the Part 2 handoff contract for the current repository. It
describes verified local interfaces and explicitly separates them from
external functionality that is not implemented. All examples in this
document and in `tests/test_cross_member_integration.py` are synthetic
fixtures; they are not production scores, customer records, or performance
evidence.

## 1. Architecture and ownership

```text
Member 1 canonical source + auth
        -> PointInTimeDataAdapter / lifecycle outcome adapter
        -> Member 2 FeatureSnapshot + eligibility + PredictionOutput
        -> Member 3 routing, MRR exposure, actions and human decisions
        -> Member 4 presentation, timelines and feedback views
        -> Member 2 outcome reconciliation / evaluation / learning gates
```

Member 2 owns time-safe features, labels, eligibility, model/calibration
metadata, prediction contracts, historical evaluation, outcome reconciliation,
and candidate/release evidence gates. Member 2 does not own database
ingestion, authentication, decision routing, action execution, frontend code,
causal intervention effects, or ROI claims.

## 2. Member 1 input contract

The replaceable `PointInTimeDataAdapter.snapshot_for(tenant_id, customer_id,
as_of)` currently accepts `HistoricalFact` records. The in-memory adapter
already supports:

| Contract field | Current local type | Local behavior |
|---|---|---|
| Stable source record ID | `record_id` | Included and used for exclusion/evidence references |
| Tenant/account scope | `tenant_id`, `customer_id` | Filters both before returning facts |
| Event/effective time | `occurred_at` or `effective_at` | Future event/effective time is excluded |
| Availability | `source_available_at`, `received_at` | Configurable source-then-received, source-only or received-only policy |
| Category/source | `category`, `source`, event type | Preserved on subscription, usage and billing facts |
| Subscription identity | `subscription_id`, status, payment flag | Preserved for eligibility/lifecycle reconstruction |
| Billing identity/status | `record_id`, event type, payment status | Payment failure is not independently churn |
| Limitations | excluded counts and limitation text | Unknown availability is explicit, not substituted with occurred time |

Member 1 must implement the same replaceable boundary against canonical storage
and provide the following authoritative inputs:

1. Authenticated tenant-scoped access. `tenant_id` must come from server auth;
   Member 2 will not trust a client-submitted tenant scope.
2. Stable customer/account IDs, subscription IDs and source-ID mappings.
3. Dated lifecycle history with occurrence and effective timestamps.
4. Source availability and received timestamps, plus documented precedence.
5. Source watermark, heartbeat, sync status and backfill/replay evidence.
6. Explicit usage-period coverage and completeness, including configurable
   session-event type mapping.
7. Billing events and confirmed payment failures, separately from termination.
8. Verified churn-effective outcomes, cancellation-request and scheduled-
   cancellation timestamps.
9. Correction/revision history and source event IDs.
10. Authorized dataset provenance, permission/license evidence and
    `DATASET_CARD.md`.
11. Reproducible historical replay through the canonical event semantics.
12. An agreed account-level multi-subscription churn definition.
13. As-of MRR, amount minor units, currency, billing interval and valuation
    evidence when Part 3 needs financial exposure.

Member 1 also owns authentication, authorization, storage transactions,
tenant isolation and durable audit persistence. No endpoint URL, database
schema migration, or backend completion is assumed here.

### Contract status

- `AVAILABLE_IN_MEMBER2_CONTRACT`: typed facts, cutoff, availability policy,
  tenant/account scoping, eligibility states, labels and prediction contracts.
- `IMPLEMENTED_BY_MEMBER1`: local SQLite migrations and storage, authenticated
  tenant/source/purpose-scoped principals, canonical ingestion, identity
  mapping, availability-aware as-of reads, lifecycle reconstruction,
  observation coverage, MRR/currency valuation, synthetic generation,
  validation/import, dataset identity, and tenant-reader provisioning.
- `AWAITING_INTEGRATION`: a SQLite-to-Member2 typed adapter, correction mapping,
  persisted Member 2 evidence fields, and end-to-end feature/label/prediction
  materialization against the generated local artifact.
- `BLOCKED_FOR_PRODUCTION`: authorized real data, Supabase/PostgreSQL storage,
  production authentication/deployment controls, durable governance storage,
  and agreed real-source multi-subscription semantics.

## 3. Member 3 prediction and feedback handoff

Member 3 consumes one immutable `PredictionOutput` per account/cutoff:

```text
tenant_id, customer_id, prediction_id, prediction_run_id,
as_of, generated_at, status,
p_churn_7d, p_churn_14d, p_churn_30d,
feature_version, model_version, calibration_version,
label_policy_version, reliability, data_freshness,
uncertainty, explanations_by_horizon
```

`PredictionOutput.model_dump(mode="json")` and
`PredictionOutput.model_validate(payload)` are the verified local handoff
serialization boundary. `PipelineResult` wraps this output with orchestration
status, safe diagnostics, version references and a `synthetic_test_only` flag;
it is not a replacement for the canonical prediction payload.

Status semantics:

- `scored`: all three calibrated cumulative probabilities are present and
  satisfy `0 <= p7 <= p14 <= p30 <= 1`. These are the only records eligible
  for normal risk ranking.
- `abstained`: probabilities are null because evidence or applicability is
  insufficient. Route to data investigation, not zero risk.
- `known_cancellation`: a cancellation request or scheduled termination was
  already known at `as_of`; use a separate cancellation-recovery workflow.
- `not_eligible`: outside the active paying-account prediction population.

Null probabilities are never zero. Reliability and freshness warnings must be
preserved. SHAP/explanation values are model associations over eligible known
features; raw margins are not probability contributions, and explanations are
not causal evidence. No model output proves intervention effectiveness.

Member 3 owns routing, prioritization, review capacity, as-of MRR/currency
exposure, next-best-action evidence, action approval and execution. Member 2
does not implement those behaviors.

Minimum feedback linkage:

- use `prediction_id` to identify the exact immutable forecast snapshot;
- carry `tenant_id`, `customer_id`, `prediction_run_id`, `prediction_as_of`,
  and horizon as consistency checks;
- keep action/execution time separate from prediction `as_of`;
- preserve `action_id`, approval state, execution time and evidence refs in the
  Part 3 action record without treating action outcome as churn truth.

`prediction_run_id` groups an inference job. It must not replace
`prediction_id` for case or feedback linkage.

## 4. Member 4 dashboard and outcome handoff

Member 4 may display scored probabilities, cumulative horizon labels, model and
calibration versions, reliability/freshness states, warnings, abstention
reasons, known cancellations, not-eligible reasons, missing explanations,
horizon-specific attributions, historical timestamps and synthetic provenance.

Member 4 may display `PredictionFeedback` states:

`PENDING`, `MATURE_POSITIVE`, `MATURE_NEGATIVE`, `INCOMPLETE`, and
`INELIGIBLE`, together with observation/evaluation cutoffs, evidence refs,
revision history, candidate evaluation, approval and rollback metadata.

Display rules:

- never render null probability as 0%;
- do not label raw SHAP margins as probability contributions;
- label synthetic scores and process-local simulations as synthetic/test-only;
- do not call ranking metrics saved revenue;
- do not imply that evaluation or approval deployed a candidate;
- preserve original `as_of`, `generated_at`, `prediction_id`, model version and
  calibration version for historical predictions;
- show pending/incomplete outcomes as unresolved, not negative retention.

Member 4 owns all frontend components, dashboard queries and display behavior.
No UI component is added by this task.

## 5. Versions, errors and provenance

Prediction, feedback and evaluation records must agree on feature version,
label policy version, model version, calibration version, tenant, customer,
prediction cutoff and horizon. Mismatches are rejected or marked unavailable;
they are not silently coerced. Model-bundle unavailability is represented by
`PipelineStatus.MODEL_BUNDLE_NOT_READY`, with machine-readable reason codes,
not fabricated probabilities.

Known source-freshness values are `fresh`, `partially_stale`, `stale` and
`unknown`. Stale or unknown essential data can lead to abstention. A missing
subscription history or unresolved multi-subscription policy is insufficient
evidence, not proof of retention.

Production status requires authorized real provenance. Synthetic fixtures may
exercise serialization, rejection paths, reconciliation and local governance
simulation only. No synthetic-to-production shortcut exists.

## 6. Synthetic integration examples

The integration tests cover these labeled structural examples:

1. A scored snapshot round-trips all canonical fields and nested metadata.
2. A limited-evidence scored snapshot preserves warning reasons.
3. Abstained, known-cancellation and not-eligible snapshots retain null
   probabilities.
4. `PipelineResult` reports model-unavailable and synthetic-only states without
   creating a prediction score.
5. Pending, mature positive, mature negative and incomplete outcome feedback
   remains linked by `prediction_id`, while a different tenant is rejected.
6. A source correction creates an append-only revision and leaves the original
   prediction snapshot unchanged.

The values are deterministic fixture values and are not calibrated production
outputs or empirical performance metrics.

## 7. Security and authorization boundary

Member 1/backend authenticates callers, derives tenant scope, authorizes reads
and writes, redacts sensitive fields, and provides durable audit/provenance.
Member 2 enforces scope and identity consistency inside its replaceable local
adapters and typed contracts. These local checks do not replace backend
authorization. Credentials, raw secrets and unnecessary PII must not enter
prediction payloads, explanations, logs or dashboard fixtures.

## 8. Ownership and acceptance checklist

- [x] Member 1 supplies local authenticated SQLite reads, a synthetic
      `DATASET_CARD.md`, availability-aware replay, and observation coverage.
- [ ] Member 2 implements the typed SQLite adapter and verifies it against the
      generated artifact without weakening tenant/source grants.
- [ ] The team supplies an authorized real dataset and confirms real-source
      availability, watermarks, corrections, and replay semantics.
- [ ] Member 1 + Member 2 agree account-level multi-subscription churn.
- [ ] Member 2 verifies real feature/label/prediction replay before claiming
      production readiness.
- [ ] Member 3 consumes `prediction_id`, not only `prediction_run_id`, and
      preserves status/reliability/freshness/null semantics.
- [ ] Member 3 keeps action approval/execution and intervention outcomes
      separate from source-backed churn truth.
- [ ] Member 4 preserves historical timestamps, versions, warnings,
      pending/mature states and synthetic labels.
- [ ] Member 4 does not display null as zero or evaluation/approval as deploy.
- [ ] Team supplies durable prediction, feedback, audit, model registry and
      active-bundle persistence before production operation.
- [ ] Prompt 18 and Prompt 19 scenario coverage reviews are completed before
      final regression sign-off.

## 9. Unresolved decisions

The following remain open and are not silently resolved here:

- account-level multi-subscription churn semantics;
- source availability precedence and correction visibility;
- exact feature/label materialization ownership and API/storage schema;
- prediction uniqueness at repeated account/cutoff/run combinations;
- explanation payload detail and attribution display policy;
- reliability/freshness thresholds and release evidence minimums;
- durable audit, artifact integrity, serving and active-bundle ownership;
- Member 3 action and feedback record endpoint/schema;
- Member 4 dashboard query and refresh contracts.

## 10. Prompt 23 local synthetic workflow

The merged CLI supports `generate`, `validate`, `import`, and
`provision-reader`. Prompt 23 should run the following from the repository root
with the project-local Python. These commands are documented here but were not
executed during the merge task:

```powershell
$privateRoot = Join-Path $HOME 'RetainIQ-private\synthetic_saas_v1_2'
$generated = (& .\.venv\Scripts\python.exe -m retaniq.synthetic generate `
  --profile standard --seed 2026 --output $privateRoot) | ConvertFrom-Json
$dataset = [string]$generated.dataset_path
$manifest = Get-Content -Raw -LiteralPath (Join-Path $dataset 'dataset_manifest.json') | ConvertFrom-Json
$datasetId = [string]$manifest.dataset_id
$db = Join-Path $privateRoot ("db\{0}.sqlite3" -f $datasetId)

.\.venv\Scripts\python.exe -m retaniq.synthetic validate --dataset $dataset
.\.venv\Scripts\python.exe -m retaniq.synthetic import --dataset $dataset --db $db
$reader = (& .\.venv\Scripts\python.exe -m retaniq.synthetic provision-reader `
  --dataset $dataset --db $db --tenant-id tenant-01) | ConvertFrom-Json
$env:RETAINIQ_MODEL_TOKEN = [string]$reader.token
$reader.token = $null
.\.venv\Scripts\python.exe -m examples.member2_synthetic_smoke `
  --db $db --dataset $dataset
Remove-Item Env:\RETAINIQ_MODEL_TOKEN
```

For the merged v1.2 STANDARD configuration and seed 2026, source inspection
computes the expected ID
`synthetic-saas-v1-2-standard-s2026-970a9d231e68`. The generated
`dataset_manifest.json` is authoritative: validation checks its per-file
SHA-256 hashes and counts, import binds the database to the manifest SHA-256,
and provisioning/smoke reject a dataset/database identity mismatch. Do not
hardcode the expected ID instead of reading the generated manifest.

`provision-reader` emits the one-time credential in its JSON result. Capture
that output rather than echoing it, do not write it to Git or a transcript, and
remove `RETAINIQ_MODEL_TOKEN` after the smoke. The token is tenant-bound,
analyst-role, exact-source scoped, and grants `retention_inference` plus
`model_artifact_write`; billing valuation is opt-in.

The local SQLite database and generated files remain private, Git-ignored
development artifacts for synthetic historical integration. They do not
depend on Supabase and do not establish real-world model performance. Future
Supabase/PostgreSQL work remains backend-owned and requires separate migrations,
tenant authentication, prediction/decision persistence, and production tests.
