# Member 1 PostgreSQL migration acceptance — Milestone 06 / Prompt 06E

## Decision

**CONDITIONALLY_ACCEPTED — core SQLite/PostgreSQL Data Foundation contract
conformance is verified for the exercised operations.** The seven new shared
differential scenarios passed against a fresh SQLite database and a live,
task-owned PostgreSQL 16.15 database. Existing migration, ingestion,
historical-query, artifact, import/replay, WSGI, and SQLite regression suites
also passed. No production deployment, Supabase, or RLS claim is made.

Conditions are explicit, noncritical test-scope gaps: not every coverage enum
state and every MRR interval/currency combination has a strict normalized
cross-output comparison; the synthetic STANDARD import and scale were not
tested; and rich Member 2 label/uncertainty metadata is not represented by the
current schema. These do not mask a found behavioral mismatch; they constrain
the acceptance claim. The detailed evidence and named cases are in the
[contract matrix](MEMBER1_DUAL_DATABASE_CONTRACT_MATRIX.md).

## Checkpoint and worktree

- Branch: `codex/member1-postgres-migration`
- Worktree: `C:\Users\User\.codex\worktrees\member1-postgres-migration\LaiCai`
- 06D-3 checkpoint: `106cc67` — `feat(member1): complete PostgreSQL persistence replay and API parity`
- 06D-3 was committed locally after reviewing the exact 15-file staged set,
  staged names, staged whitespace, and secret/data-file exclusions. No push or
  merge was performed.
- Prompt 06E changes remain uncommitted for review.
- `AGENT.md`, `AGENTS.md`, and `RetainIQ_v2_Complete_Requirements.md` were not
  present in this checkout; their contents were not inferred.
- No other worktree was modified. The worktree list showed separate Member 2
  OneDrive and detached checkouts; neither was used for this work.

## Live test environment and results

A task-owned PostgreSQL cluster was started explicitly on `127.0.0.1:62534`.
The server identified itself as PostgreSQL **16.15**. Tests used psycopg
**3.3.6** and the isolated task runtime. The target database
`retaniq_test_06e_20261011` was confirmed absent before creation; its loopback
server/database identity was checked before running tests. The differential
suite created a second uniquely named `retaniq_test_contract_*` database,
refused reuse if it already existed, and dropped that child database in its
teardown.

| Run | Result |
|---|---|
| Pre-06E baseline, full suite with real PostgreSQL | **150 passed; 0 failed; 0 errors; 0 skipped**, 63.665 seconds. The 34 live PostgreSQL integration tests ran. |
| Focused new differential suite | **7 passed**, 13.395 seconds. Each scenario ran against both fresh SQLite and PostgreSQL databases. |
| Final full suite with live PostgreSQL | **157 passed; 0 failed; 0 errors; 0 skipped**, 75.887 seconds. **41 unique live PostgreSQL integration tests** ran: 34 existing plus 7 differential scenarios. |
| Full SQLite-only suite | **116 passed; 0 failed; 0 errors; 41 expected skips**, 15.012 seconds. Skips are only live-PostgreSQL-guarded tests; this is not the dual-backend acceptance run. |
| `compileall` | **PASS** — `retaniq` and `tests`. |
| Package import smoke | **PASS** — API, data foundation, database/config, importer, migrations, and synthetic adapter imported. |
| `git diff --check` | **PASS** — only Windows line-ending normalization notices. |
| Python warnings | **0**. Expected unauthorized/invalid request log records were emitted by security-negative tests. |

The seven differential scenario methods compare normalized outputs for
ingestion/idempotency/auth/as-of replay; subscription/coverage/MRR/source
grants; feature/label/prediction persistence; existing WSGI behavior;
concurrent identical and conflicting ingestion; subtype-failure rollback; and
subscription-owner races. Total strict scenario comparisons: **7**, each
executed on both engines. JSON mapping order and row representation are
normalized; UTC timestamp encodings are normalized; generated canonical
`event_id` and generated feature snapshot linkage are handled only as
documented in the matrix. Source IDs, canonical digests, occurred/received/
source-available times, values, probabilities, prediction IDs/run IDs,
permissions, error codes, and statuses are compared. API health processing
timestamps cannot be identical across sequential executions; they are parsed
and validated individually while stable health fields are compared.

Initial differential-test iterations exposed test-harness issues only: SQLite
row objects needed explicit mapping conversion, API health processing times
needed per-run validity checks instead of impossible equality across sequential
runs, and the duplicate-event expectation was corrected to the established
`idempotency_conflict` code. No application/backend defect was found by the
differential scenarios.

## What is verified

The verified interface includes configurable SQLite/PostgreSQL connections;
explicit migrations and schema checks; tenant, identity, principal, source,
category, and purpose authorization; canonical event/subtype ingestion;
database-enforced subscription ownership; historical event/subscription/
account queries; coverage reads/writes and import checkpoints; MRR valuation;
feature, label, and prediction writes; immutable dataset identity; bounded
synthetic import/replay; and the existing WSGI endpoints:

- `POST /v1/ingest/events`
- `GET /v1/integrations`
- `GET /v1/admin/integrations`

No API endpoints or migrations were added in 06E. The migration lock remains
acquired before schema creation, preserving the 06D-3 concurrent-initializer
fix. Live tests verify migration checksums, repeated initialization, concurrent
first initialization, failed-migration rollback, and no partial migration
history entry. The differential rollback test injects a database-side subtype
failure on both engines and confirms no canonical event, subtype, subscription
owner, or projection survives.

Historical visibility remains:

```text
occurred_at <= as_of
AND COALESCE(source_available_at, received_at) <= as_of
```

Payment failure does not terminate entitlement; a cancellation request is not
an effective end; partial subscription termination preserves eligibility when
another qualifying subscription remains; missing coverage is not verified
zero; and unknown outcome remains unknown. The current synthetic policy is not
declared a universal real-world churn definition.

## Authorization and security

Integration principals remain scoped to their authenticated tenant, source,
configured event categories, and purposes. Service principals are bound to a
tenant and exact source list. Artifact writes require analyst role,
`model_artifact_write`, and a customer identity through an authorized source;
inference-only principals cannot write. Billing fields and MRR remain gated by
`billing_valuation`. Administrative health requires admin/operator role and
`integration_health`. Negative tests cover wrong tenant/body context,
unauthorized category, restricted fields, source/tenant scope, invalid/missing
tokens, and DSN redaction. Application authorization is **not** PostgreSQL
RLS.

`provision_member2_reader()` intentionally grants the imported Member 2
multi-source analyst both `retention_inference` and `model_artifact_write`,
because this workflow reads inputs and persists modeling artifacts. It omits
`billing_valuation` by default; its explicit option adds that purpose. This is
a workflow-scoped, tested combination, not an expansion of integration-token
rights.

## Contract and remaining-gap assessment

No applied migration checksum was changed. Existing schema constraints and
API/payload shapes remain in force. The current label table does not store the
richer `status`, evidence references, evaluation-as-of, or generation fields
that a downstream label object might carry. Prediction storage persists
flattened reliability/freshness and `uncertainty_status=not_quantified`, not a
full uncertainty object. No unsupported metadata is claimed as losslessly
stored.

Coverage behavior is tested for complete/partial intervals, missing-versus-
zero, delayed availability, repeat/conflict, and tenant/source scoping. The
full set of accepted states—outage, censored, not-created, entitlement-ended,
and missing historical backfill—does not yet have strict shared cross-result
fixtures. The canonical coverage record cannot prove an independent
lifecycle/billing heartbeat or establish mature outcome coverage by itself.
Invalid currency and every billing interval/zero-decimal variant are not all
in the strict cross-result fixture; there is no FX conversion. Full synthetic
STANDARD load/performance, external data permission, and production scale were
not tested; performance was not measured.

Prior Member 2 handoff materials report missing/incomplete mature 7/14/30
outcomes, outcome-coverage mapping issues, stale/insufficient historical
evidence, and a missing independent lifecycle/billing heartbeat. Those reports
are dependencies, not findings revalidated in this 06E run. No Member 2
worktree was changed, and no coverage, freshness, or real-data evidence was
fabricated.

The synthetic fixture/provenance suite remains synthetic-only. The bounded
quick import verified canonical event/checkpoint/replay behavior, not
STANDARD-scale readiness or real-data provenance. Dataset files were not
modified by import tests.

After verification, the exact task-created parent database
`retaniq_test_06e_20261011` was dropped. The differential child database was
already dropped by its test teardown. Only the task-owned temporary PostgreSQL
cluster was stopped; the unrelated Windows PostgreSQL service was not used or
modified. No PostgreSQL data directory, database file, bearer token, password,
or generated dataset was staged.

## Phase 07 prerequisites and recommended Phase 07A

Before production use, Phase 07 must establish a managed database boundary,
database roles/credentials, transport and secret handling, backup/retention,
operational monitoring, and explicit PostgreSQL RLS policies. RLS tests must
run with application credentials that cannot bypass row policies and must
prove tenant isolation independently of Python principal checks. External
identity, source-owner permission, lawful data use, and real outcome/coverage
provenance must be verified separately.

Recommended **Phase 07A — Supabase tenant security and RLS foundation**:

1. Review the canonical tenant/source access model and map each app role to a
   least-privilege Supabase database role; identify trusted service operations.
2. Design and review RLS policies for every tenant-owned table, including
   artifact, identity, event/subtype, coverage, checkpoint, and health data.
3. Apply the policy migration in an isolated Supabase project only after the
   reviewed design; preserve version/checksum discipline and avoid schema drift.
4. Add live authenticated integration tests proving same-tenant access,
   cross-tenant denial, service-role limits, and migration rollback under RLS.
5. Keep application authorization as defense in depth; do not expose service
   secrets or add new prediction/decision routes in this phase.

This is a recommended scope, not an assertion that Phase 07A has started or
that Supabase is configured. Keep the coverage-state and currency differential
gaps visible for a follow-up contract-test prompt.
