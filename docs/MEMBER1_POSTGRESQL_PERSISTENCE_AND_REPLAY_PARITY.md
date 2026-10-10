# Member 1 PostgreSQL artifact, import, replay, and WSGI parity — Prompt 06D-3

## Scope and result

This checkpoint ports the existing Data Foundation feature-snapshot, churn-label,
and prediction write contracts to PostgreSQL; enables dataset identity and
provenance operations needed by the existing bounded synthetic importer; makes
observation-coverage batch checkpointing and historical event replay usable on
PostgreSQL; and allows the existing WSGI API to verify and use an already
migrated PostgreSQL schema. No SQLite schema or artifact contract was changed,
and no new PostgreSQL migration was required.

The live tests use PostgreSQL 16.15 and psycopg 3.3.6. The database target is
guarded by an explicit disposable marker, loopback host, and `retaniq_test_*`
database prefix. Import/replay parity was verified using the deterministic
`quick` profile (12 accounts, 4 tenants, 2025-01-01 through 2025-05-31), not a
full `STANDARD` dataset. No model training, customer data, or performance claim
is part of this work.

## Capability matrix

| Capability | SQLite status | PostgreSQL status | Contract / limit |
|---|---|---|---|
| Connection/configuration | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Explicit backend configuration; no fallback. PostgreSQL test used loopback with an explicit disposable guard. |
| Schema initialization | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | SQLite uses existing initialization; PostgreSQL uses explicit migrations. Concurrent first-time PostgreSQL schema creation is serialized. |
| Tenant/auth setup and canonical ingestion | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Existing 06D-1 auth, identity, category, event/subtype, batch/checkpoint, and idempotency contracts. |
| Historical reads, coverage, and valuation | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Existing 06D-2 cutoff, source scope, coverage, subscription and MRR contracts. |
| Feature snapshots | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Tenant/customer/as-of/version uniqueness; minimized typed JSON and quality status; matching repeat idempotent, conflicting duplicate rejected. |
| Churn labels | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | 7/14/30 horizons; `0`, `1`, and `unknown`; outcome and observation-through times; unknown stays unknown; mature negative validation. |
| Predictions | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | One snapshot ID per tenant/account/cutoff; independent shared run ID; three horizon values; versions, explanation/reliability fields, nullable non-scored statuses, and feature snapshot linkage. |
| Dataset identity/provenance | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Immutable dataset ID/version/type, target policy, generator version, manifest digest, and idempotent identity behavior. |
| CSV import | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Existing canonical event path and trusted availability option; bounded integration tests. |
| Synthetic batch import/checkpoints | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Existing event normalizer and identity setup. PostgreSQL verified with deterministic quick profile only; not full STANDARD scale. |
| Historical replay | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | Existing tenant/source/purpose authorization and occurrence + effective-availability cutoffs; stable order by availability, occurrence, event ID. Receipt time is processing time and differs across two separate imports. |
| Existing WSGI endpoints | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | `POST /v1/ingest/events`, `GET /v1/integrations`, `GET /v1/admin/integrations`; no route or response contract added. Rejections remain atomic. |
| API database startup | **IMPLEMENTED_AND_TESTED** | **IMPLEMENTED_AND_TESTED** | PostgreSQL migration history/checksums are verified read-only; missing/incomplete schema fails startup, with no automatic migration. |

Artifact writes use explicit least-privilege checks. A service principal must
have the `analyst` role and `model_artifact_write` purpose, and source/customer
scope must match. `retention_inference` alone is insufficient. Integration
principals remain source-bound and cannot persist artifacts for customer IDs
only mapped through another source. This work does not make a new credential
provisioning route or allow artifact grants to be assigned through the
integration-token CLI flow.

The migration runner now acquires its PostgreSQL advisory lock before creating
the target schema, so simultaneous first-time initializers serialize schema
creation as well as migration application.

## Artifact contract boundaries

The implementation preserves the pre-existing storage shapes rather than
inventing richer contracts:

- Labels have one row per tenant/customer/as-of/horizon/policy and store the
  label, outcome time, observed-through time, and policy version. A negative
  label requires a mature, fully observed horizon. The current schema does not
  persist a richer label status, evidence-reference list, or label-evaluation
  timestamp. Member 2 still owns label construction and evidence policy.
- Predictions store the existing three horizon probabilities and reliability
  status/reason codes. Uncertainty remains `not_quantified`; a full uncertainty
  object is not persisted. The run ID can be shared across account predictions
  while each account/cutoff keeps its prediction snapshot ID.
- Feature payloads remain minimized typed JSON under the existing approved
  fields; free text and restricted attributes are rejected. Data cutoff and
  feature version remain explicit.

PostgreSQL binds contract timestamps as timezone-aware values against
`TIMESTAMPTZ` and returns the established normalized UTC string shape. Database
uniqueness plus existing content digests preserve immutable/idempotent writes;
there is no SQLite fallback.

## Verification

Focused checks passed for the shared SQLite and live PostgreSQL artifact
contract fixtures, WSGI integration, bounded import/checkpoint/replay, and
concurrent first-time migrations. The full-suite result and exact disposable
database cleanup are recorded in the 06D-3 `TEAM_LOG.md` entry. Test fixtures
cover artifact round trips and conflicting duplicates, unknown/mature label
semantics, prediction-to-snapshot/version linkage, auth/source/tenant scope,
API startup on uninitialized schemas, endpoint rejection atomicity, dataset
identity mismatch, checkpoint idempotency, replay cutoffs, and SQLite parity.

## Readiness and remaining work

This is scoped backend parity, not production readiness or complete feature
parity. The existing Python artifact stores persist validated contracts; this
does not add a feature pipeline, label builder, model registry, trainer,
calibration/evaluation lifecycle, or an independent data-freshness worker.
Full synthetic `STANDARD` import, real-data import and permissions, large-scale
load/performance tests, RLS, production identity/TLS deployment, encryption at
rest, scheduled workers, and Supabase remain out of scope. Existing Member 2
readiness blockers (zero mature labeled positives/negatives, insufficient
verified outcome coverage, 97.21% stale/insufficient snapshots, and no
independent lifecycle/billing freshness heartbeat) remain unchanged.

Prompt 06D-3 stops here. 06E and any deployment, production database, RLS, or
cross-member integration work require their own explicit scope and verification.

## Cross-member handoff and recommended 06E scope

Storage parity does not clear Member 2's reported blockers: zero mature
positive/negative 7/14/30 labels, incomplete authorized outcome observation,
97.21% stale/insufficient snapshots, no independent lifecycle/billing
freshness heartbeat, and synthetic-only provenance. Later investigation should
ask Member 2 to specify the source-backed outcome stream, authorized source
mapping, outcome-effective time, observation-through semantics, and complete /
partial / unknown / delayed coverage states needed to prove label maturity.
The existing coverage API records source-attributed intervals but does not
itself create an independent heartbeat or establish that a missing outcome is
a negative. The teams should also decide whether richer label `status`,
evidence references, `evaluation_as_of`, and generation timestamps require a
reviewed additive migration or remain outside the canonical table.

Recommended Prompt 06E is a dual-database contract-conformance phase: extract
shared SQLite/PostgreSQL fixtures for all public Data Foundation read/write
contracts, compare normalized results and error codes, cover transaction
rollback and idempotency/conflict semantics, exercise migration upgrade and
startup verification, and document intentional backend-specific differences.
It should run against a disposable PostgreSQL instance and SQLite, without
adding inference, new API routes, production deployment, or RLS; any required
schema changes need cross-member contract review first.
