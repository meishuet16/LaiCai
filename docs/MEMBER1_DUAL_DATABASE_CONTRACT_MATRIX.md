# Member 1 dual-database contract matrix — Prompt 06E

This matrix records behavioral evidence, not merely implementation presence.
The differential harness creates a fresh SQLite file and a fresh PostgreSQL
database, provisions the same synthetic identities and grants through public
interfaces, runs each scenario on both, normalizes only row/timestamp
representation and database-generated `event_id`, and strictly compares all
remaining fields. WSGI `last_successful_ingestion_at` and `last_failure_at`
are true processing times: each is parsed and checked for validity on each
backend; stable health fields are compared. No business identifiers,
availability times, probabilities, amounts, permission results, or error codes
are omitted from comparisons.

Test commands and test names below refer to unittest discovery under `tests/`.
`HistoricalQueryContract` and `ArtifactPersistenceContract` are the same test
mixins executed by their SQLite and live PostgreSQL subclasses.

| Contract | SQLite evidence | Live PostgreSQL evidence | Shared comparison / security outcome | Status and limitation |
|---|---|---|---|---|
| Connection/configuration and no backend fallback | `test_database_config.py`; `test_database_connection.py` | Same unit tests; live repository suites connect via guarded `DatabaseConfig` | Existing suites validate explicit backend selection; WSGI differential verifies configured database behavior | **PASS** — local reference configuration only; no managed deployment. |
| Schema init, migration integrity and fresh concurrent initialization | SQLite initialization and schema-upgrade tests in `test_data_foundation.py` | `test_postgresql_migrations.py`: fresh/repeated init, checksums, failed migration rollback, concurrent attempts | `test_concurrent_migration_attempts_serialize`; lock-before-schema-create fix remains under test | **PASS** — no migration added in 06D-3/06E. No destructive reinitialization path is exposed. |
| Tenant/source identity and canonical ingestion | `test_data_foundation.py`; `test_csv_import_counts_invalid_and_duplicate_rows_and_replay_preserves_times` | `test_postgresql_ingestion.py`: identity, subtype, owner, category, idempotency | `test_ingestion_hashes_idempotency_authorization_and_as_of_replay_match` compares source IDs, semantic hash digests, event fields and duplicate/conflict outcomes; `test_subscription_owner_race_has_equivalent_tenant_scoped_result` compares ownership race results | **PASS** — synthetic fixture identities only. |
| Identical and conflicting concurrent event retries | SQLite serialization/idempotency contracts in `test_data_foundation.py` | `test_concurrent_identical_and_conflicting_event_retries` | `test_concurrent_identical_ingestion_has_equivalent_external_result` runs 8 identical and 2 conflicting writers on each backend | **PASS** — one canonical row wins; retries/conflict outcomes match. |
| Atomic subtype and ownership rollback | SQLite transaction rollback tests | `test_subtype_failure_rolls_back_event_owner_and_projection`; batch checkpoint rollback | `test_subtype_failure_rolls_back_event_and_subscription_owner_on_both_backends` installs backend-specific DB failure triggers, invokes public ingestion, and confirms zero partial ledger/subtype/owner/projection rows | **PASS** — failure injection differs only by backend DDL. |
| Historical occurrence/availability cutoffs and replay ordering | `HistoricalQueryContract` cutoff, offset, tie, fallback and replay assertions | Same `HistoricalQueryContract` cases live; PostgreSQL importer replay suite | `test_ingestion_hashes_idempotency_authorization_and_as_of_replay_match` strictly compares `occurred_at`, `received_at`, `source_available_at`, ordering and result content | **PASS** — predicates remain `occurred_at <= as_of` and `COALESCE(source_available_at, received_at) <= as_of`; processing receipt is never substituted for source availability. |
| Tenant/source/category/purpose authorization and redaction | `test_data_foundation.py`; historical contract auth cases | `test_postgresql_ingestion.py`, `test_postgresql_historical_queries.py`, `test_postgresql_wsgi_api.py` | Differential artifact, event and WSGI scenarios compare forbidden-purpose, cross-tenant, source/category, admin-route and error outcomes | **PASS** — application-level checks are not RLS. |
| Subscription history and account eligibility | Historical contract tests plus lifecycle tests in `test_data_foundation.py` | Same historical contract live in `test_postgresql_historical_queries.py` | `test_subscription_coverage_mrr_and_source_grants_match` compares payment-failure and pending-cancellation behavior, as-of snapshot and subscription output | **PASS** — current synthetic semantics only; no universal real-world churn policy. |
| Coverage record, availability and idempotency | `test_coverage_as_of_idempotency_and_missing_is_not_zero`; `test_coverage_partial_and_tenant_source_scope` | Same two contract tests live; batch checkpoint tests | Differential scenario compares accepted/repeated/conflicting coverage, missing-before-availability and visible-at-availability behavior | **PASS** for complete/partial/missing and delayed visibility. **GAP**: outage, censored, not-created, entitlement-ended, adjacent/overlap variants are not all compared in a shared fixture; a coverage interval does not create an independent heartbeat. |
| MRR/currency and billing authorization | MRR interval/discount, missing/mixed currency, zero-decimal, redaction tests in `test_data_foundation.py` | Same historical contract MRR cases live | Differential lifecycle fixture compares annual discount calculation (900 minor units), payment failure, and billing redaction/no-valuation results | **PASS** for representative annual/discount behavior and currency/redaction cases present in shared historical mixins. **GAP**: invalid currency and every day/week/quarter/zero-decimal variant are not in the strict cross-result fixture; invalid currency has SQLite-only direct coverage. No FX is performed. |
| Feature snapshot persistence | `SQLiteArtifactPersistenceTests` | `PostgreSQLArtifactPersistenceTests` | `test_artifact_round_trips_and_contract_failures_match` compares stored tenant/customer/as-of/version/cutoff/JSON/quality and permission/conflict outcomes | **PASS** — generated feature snapshot surrogate ID is normalized only as the prediction linkage target. |
| Churn label persistence | `SQLiteArtifactPersistenceTests` | `PostgreSQLArtifactPersistenceTests` | Same artifact differential scenario compares horizon, label, outcome, observation-through, policy and validation outcomes | **PASS** for the represented schema. **GAP**: richer status/evidence references/evaluation timestamp/generation metadata are not columns in the established schema. `unknown` remains unknown; mature-negative validation remains enforced. |
| Prediction persistence | `SQLiteArtifactPersistenceTests` | `PostgreSQLArtifactPersistenceTests` | Same artifact differential scenario compares prediction ID/run ID, probabilities, versions, reliability/freshness, explanation JSON and auth failures | **PASS** for the established flat schema. **GAP**: full uncertainty object is not persisted; status remains `not_quantified`. |
| Dataset identity/provenance and mismatch rejection | `test_data_foundation.py`; SQLite side of synthetic import/replay test | PostgreSQL side of `test_postgresql_import_replay.py` | Differential lifecycle scenario compares dataset ID and manifest digest and rejects a conflicting dataset version | **PASS** — one immutable synthetic dataset identity per database; no real-data relabeling. |
| Import/checkpoint and bounded synthetic replay | `test_synthetic_integration.py`; shared SQLite side of `test_postgresql_import_replay.py` | `test_postgresql_import_replay.py` | The import test compares deterministic quick-profile counts/checkpoints and repeat-import duplicates; differential event fixture compares replay semantics | **PASS** within deterministic quick scope. **GAP**: full `STANDARD` scale/load and production resume operations are not claimed. |
| Existing WSGI routes and safe rejection | `test_data_foundation.py` | `test_postgresql_wsgi_api.py` | `test_existing_wsgi_routes_match_for_authenticated_requests` compares success, duplicate, conflict, missing auth, forged tenant, forbidden category, invalid event, integration health, admin authorization and no-partial-write counts | **PASS** — existing routes only; no prediction/decision/dashboard endpoints. |
| Token rotation/revocation and secret minimization | `test_data_foundation.py` token digest and restricted-field cases | `test_postgresql_ingestion.py` token rotation; `test_postgresql_wsgi_api.py` safe errors | Differential artifacts/API fixtures compare purpose denial, restricted-field rejection and DSN non-disclosure | **PASS** for the local token-digest contract; no external identity provider. |
| PostgreSQL RLS / database-enforced tenant isolation | N/A | N/A | Not implemented or simulated by application checks | **GAP / Phase 07 prerequisite** — every test here proves application authorization, not row-level security. |

## Permission matrix

| Principal | Read/ingest scope | Artifact writes | Billing valuation | Administrative health |
|---|---|---|---|---|
| Integration principal | One tenant, one source, granted categories and purposes; canonical ingestion derives tenant from token | Denied unless a separately supported grant path exists; inference alone is not write authority | Only when explicitly granted | Denied |
| Retention service principal | One tenant and exact authorized sources; retention-purpose reads | Denied when `model_artifact_write` is absent | Redacted/omitted without `billing_valuation` | Denied for analyst role |
| Model artifact writer | Same exact tenant/source scope, analyst role, explicit `model_artifact_write` | Allowed only for customers mapped through an authorized source | Only with separate `billing_valuation` | Denied for analyst role |
| Admin/operator service principal | Exact tenant/source scope and role-specific operations | Denied by artifact writer role check | Purpose-gated | Requires `integration_health` and admin/operator role |

`provision_member2_reader()` deliberately provisions the multi-source analyst
used by the Member 2 synthetic workflow with both `retention_inference` and
`model_artifact_write`, because that workflow consumes authorized inputs and
persists feature/label/prediction artifacts. It omits `billing_valuation` by
default; the optional flag adds it. This explicit combination is tested by the
bounded dual-backend import fixture. It is a workflow-specific principal, not
a general inference token. Standalone integration principals with only
`retention_inference` cannot write artifacts. There is no scope expansion to
unlisted sources/customers.

## Overall assessment

The seven strict differential scenario runners pass on both backends. The
existing backend-specific suites add broader expected-contract assertions and
live PostgreSQL migration, ingestion, historical, artifact, import and WSGI
coverage. The enumerated coverage-state variants and larger-than-quick import
remain explicit noncritical gaps. See
[`MEMBER1_POSTGRESQL_MIGRATION_ACCEPTANCE.md`](MEMBER1_POSTGRESQL_MIGRATION_ACCEPTANCE.md)
for the Milestone 06 classification and Phase 07A prerequisites.
