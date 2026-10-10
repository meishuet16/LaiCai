# Member 1 — Final Data Foundation Acceptance

**Assessment:** `PARTIALLY_VERIFIED — NOT DONE`
**Assessment date:** 2026-10-11
**Branch:** `codex/member1-postgres-migration`

This record distinguishes operator-supplied Supabase evidence, local tests, and
checks performed in this worktree. No Supabase connection, remote mutation,
STANDARD import, role cleanup, or Member 2 remote read was performed during
this task. The success criteria for Member 1 are not met.

## Evidence summary

| Area | Result | Evidence and limit |
|---|---|---|
| PostgreSQL migrations 001–007 | **VERIFIED by prior operator-supplied evidence; not rechecked here** | Prior catalog report says checksums match, no pending migrations, current version 007. No remote connection was available in this task. |
| Remote RLS catalog | **VERIFIED by prior operator-supplied evidence; not rechecked here** | Prior report: 18/18 application tables enabled and forced, 42 policies. |
| Remote restricted smoke | **PARTIALLY_VERIFIED** | Prior report says 13 temporary-login scenarios passed. It is not comprehensive proof of durable runtime credentials or tenant identity independent of the shared backend GUC. Cleanup was only reported as attempted; independent cleanup verification is absent. |
| Durable restricted LOGINs | **NOT_VERIFIED** | No restricted app, inference/dashboard, artifact, or maintenance login DSNs are configured in this environment. Capability roles alone are not runtime logins. |
| Data API / exposed schemas / anon and authenticated access | **NOT_VERIFIED** | No live read-only catalog or API check was possible. Actual project's Data API settings are unknown. |
| STANDARD tenant-01 Supabase import | **NOT DONE** | No import or remote write occurred. No tenant-01 rows are claimed in Supabase. |
| Local STANDARD working copy | **PARTIALLY_VERIFIED; not tenant-01-only at rest** | Read-only identity and count check matched the frozen manifest, but the named P0 SQLite file contains all four tenant partitions. See the correction in `MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`. |
| Member 2 authenticated local reader | **PASS, local SQLite only** | DPAPI-protected reader smoke passed: 23 events, 1 subscription, 48 coverage rows at the stated cutoff; cross-tenant request denied; no valuation fields; database unchanged during reads. The database file itself contains other tenant partitions. |
| Member 2 remote API read | **NOT_VERIFIED** | No remote credentials, deployed application URL, or remote Member 2 access path was available. |
| Member 3/4 prediction lookup | **LOCAL CONTRACT TESTS PASS; remote readiness NOT_VERIFIED** | Bounded history and ID lookup have local authenticated WSGI tests. No remote restricted read login or remote predictions were tested. |

The only environment-secret check performed here recorded presence booleans;
the RetainIQ app, maintenance, and migration DSNs were all absent. Secret
values were not printed or added to files.

## Implementation delivered locally

- Added explicit app, maintenance, and migration DSN separation. Routine
  runtime configuration no longer requires a migration DSN; maintenance
  credentials must differ from the app login and use a direct or session
  endpoint for global import state.
- Routed global synthetic identity/checkpoint operations through the
  maintenance target and tenant data writes through the backend target. Split
  batch checkpointing is replay-safe but not a distributed atomic transaction.
- Added explicit `tenant-01` scope to Supabase import, tenant-filtered manifest
  input processing, per-tenant counts, and tenant-specific checkpoints.
  Supabase import does not initialize or migrate the schema.
- Added authenticated, bounded account-history and prediction-history/ID WSGI
  routes with tenant derived from the stored RetainIQ principal, purpose checks,
  pagination limits, and label/valuation redaction.
- Added a fail-closed guard for first-time Supabase dataset identity binding.
  A maintenance login is subject to FORCE RLS on tenant tables; zero visible
  rows under no tenant context cannot prove global destination emptiness. The
  importer therefore refuses an unbound Supabase destination rather than
  misclassifying RLS-hidden data as an empty database.

These code changes are not equivalent to durable role provisioning, remote
role routing verification, or deployment. The API currently uses the configured
application database target; it does not automatically route downstream read
requests to a separate inference/dashboard LOGIN.

## Local STANDARD artifact inspection

Performed read-only against the existing private STANDARD manifest and P0
SQLite working copy. The frozen manifest identity matched the identity row:

- Dataset: `synthetic-saas-v1-2-standard-s2026-970a9d231e68`, version 1.2.0.
- Target policy: `effective-account-churn-v1.2`; generator: `synthetic-saas-v1.2`.
- Manifest SHA-256: `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- Source partition for tenant-01: 750 customers, 2,250 identities, 56,211
  canonical events, 119,472 observation-coverage rows.
- Corresponding tenant-01 SQLite counts: 750 customers, 2,250 identities,
  56,211 canonical events, 49,363 usage events, 3,264 billing events, 3,584
  subscription events, 825 subscriptions, and 119,472 coverage rows. The local
  file also has three integrations, three category grants, one service
  principal, and three credential-audit rows; no predictions, feature
  snapshots, or churn-label rows.
- SQLite `PRAGMA integrity_check`: `ok`; dataset identity SHA matches the
  source manifest.
- The file's import checkpoints are for the full manifest (239,721 canonical
  events and 491,223 coverage rows), and 752,669 rows across tenant-bearing
  tables belong to tenant IDs other than tenant-01. This working copy is not a
  physically tenant-01-only dataset. It was not changed or copied in this task.

The STANDARD artifact is synthetic demonstration data. Its manifest and
partition counts are provenance, not real-customer or predictive-performance
evidence. The original manifest totals are global totals; they are not
tenant-01 import totals.

## API and authorization boundary

RetainIQ's custom bearer tokens remain authoritative. API code authenticates a
stored service principal, derives tenant/source/purpose from that record, and
sets PostgreSQL tenant context transaction-locally. Callers cannot supply a
tenant ID as authorization identity. The ordinary WSGI surface has fixed
routes and does not expose arbitrary SQL execution.

**Residual threat:** PostgreSQL custom GUC context is spoofable by a holder of
the shared backend database credential who can execute arbitrary SQL. It is
not independently authenticated tenant identity and does not protect against
credential compromise or arbitrary-SQL injection. Do not expose the backend
DSN to a browser, and do not describe this as database-level isolation from a
compromised backend credential. Supabase `service_role` bypasses RLS and must
not be used as the normal application or security-test login.

The added Member 2 history response reports source freshness as `unknown`;
no deployed refresh worker or remote freshness signal is established here.
Prediction history surfaces persisted versions, reliability, freshness,
uncertainty and status; no remote Member 3/4 client contract was exercised.
Only stored prediction fields are returned. The synthetic provenance of a
future model must be supplied and reviewed by the model owner; no model or
prediction data was imported in this task.

## Requirement acceptance checklist

| Part 1 requirement | Result | Evidence / outstanding dependency |
|---|---|---|
| Dataset provenance, license and limitations | **PASS for synthetic provenance; real data NOT_READY** | Frozen STANDARD manifest hash verified locally. Dataset card says no real dataset is authorized/imported. |
| Historical import and canonical source mapping | **PARTIAL** | Local full-four-tenant SQLite import exists and source mapping/counts are readable. The requested Supabase tenant-01 import is not done; the P0 file is not tenant-01-only. |
| Authenticated Push API normalization/minimization | **LOCAL TEST PASS** | Existing ingestion/API suite plus local tests; no Supabase API deployment/read smoke. |
| Replay/idempotency and foreign-key integrity | **LOCAL TEST PASS** | Scoped QUICK importer test and existing replay tests pass. No live remote import/replay. |
| Availability-safe timestamps and point-in-time access | **LOCAL TEST PASS** | As-of history tests and protected local reader smoke; no remote data validation. |
| 7/14/30 labels, censoring, cancellation policy | **NOT COMPLETE / MEMBER 2 OWNED** | This repository stores label contracts; no production label builder, and the inspected local P0 copy has zero churn-label rows. Requires Member 2 implementation and shared evidence. |
| MRR/currency and billing normalization | **LOCAL CONTRACT TESTS PASS** | Local unit coverage only; synthetic amounts are not business evidence. |
| Tenant isolation using actual restricted remote credentials | **NOT VERIFIED IN THIS TASK** | Prior 13-case remote smoke was operator-supplied; current remote logins absent. Shared-GUC limitation remains. |
| Source freshness and ingestion failure reporting | **PARTIAL** | Local integration-health contract exists; history API reports freshness `unknown`; no scheduled refresh/deployed monitoring was tested. |
| Silent-account daily refresh | **NOT VERIFIED** | No running scheduler/worker or remote refresh job was present. |
| Prediction persistence and lookup/history | **LOCAL TEST PASS; REMOTE NOT VERIFIED** | New local WSGI lookup/history tests pass; inspected P0 database has zero predictions. Member 3/4 remote read role and client integration remain outstanding. |
| Supabase remote data integrity | **NOT VERIFIED AFTER IMPORT** | No import, remote row-count query, or remote integrity check was run. |
| Member 2/3/4 integration contracts | **PARTIAL** | Local route tests and P0 SQLite reader smoke pass. No actual remote Member 2 read, no Member 3/4 remote restricted-client smoke, and no shared prediction/action end-to-end run. |

## Verification run in this task

- `py -3.14 -B -m unittest tests.test_data_foundation.DataFoundationTests.test_supabase_first_identity_binding_fails_closed_under_tenant_rls tests.test_synthetic_integration tests.test_member1_p0_reader tests.test_member1_api_handoff tests.test_supabase_configuration -q` — **PASS**, 34 tests.
- `py -3.14 -B -m unittest discover -s tests -q` — **PASS**, 218 tests, 0 failures/errors, 57 expected PostgreSQL-guard skips. 161 tests executed and passed; **zero live PostgreSQL tests** ran because no disposable test DSN was configured.
- `py -3.14 -B -m compileall -q retaniq tests` — **PASS**.
- `py -3.14 -B -m retaniq.secret_store run --file <DPAPI-protected local reader token> -- py -3.14 -B -m examples.member1_p0_authenticated_reader_smoke --db <private P0 SQLite working copy>` — **PASS**, authenticated SQLite read-only smoke; 23 events, 1 subscription, 48 coverage rows, tenant-02 denial, no valuation fields, database unchanged during reads. Token and customer rows were not printed.
- Read-only STANDARD manifest/SQLite inspection — **PASS for identity/integrity; FAIL for physical tenant-only storage** as described above.
- `git diff --check` and staged-secret scan — results recorded in the accompanying `TEAM_LOG.md` entry; no remote database or secret file was staged.

## Exact blockers and required next sequence

1. In the approved secret store or a hidden local prompt, configure distinct
   project-validated restricted backend and maintenance LOGIN DSNs. Configure
   a separate direct/session migration DSN only for read-only catalog checks
   and approved administration. Do not use the `postgres` or `service_role`
   login for routine RetainIQ API traffic or RLS proof.
2. Obtain owner/operator confirmation of project ref, region and recoverability;
   perform a fresh read-only catalog check of migrations, role attributes,
   memberships, grants, ownership, exposed schemas, anon/authenticated access,
   and temporary smoke-role cleanup. Stop on unexpected roles or privileges.
3. Resolve the first-bind gate: the importer currently refuses an unbound
   Supabase dataset identity because maintenance RLS cannot prove global
   emptiness. A privileged read-only destination check and a reviewed,
   controlled identity-binding step must be implemented/tested; no blind
   confirmation flag should bypass this check. Keep tenant writes on backend
   and global state on maintenance. Test the exact operation using actual
   restricted logins on local PostgreSQL before remote use.
4. Confirm Data API exposure settings and make direct `anon`/`authenticated`
   access fail without an authenticated RetainIQ backend. Independently verify
   cleanup of temporary smoke LOGINs.
5. Import tenant-01 only after steps 1–4 pass and the application is offline
   from conflicting writers. Verify the source manifest hash, tenant-specific
   checkpoints/counts, all tenant-owned table counts, event/coverage integrity,
   idempotent replay, and zero tenant-02/03/04 writes using read-only
   post-import checks.
6. Run Member 2's authenticated read through the actual approved remote path;
   then run Member 3/4 prediction lookup/history with their restricted read
   credentials and contract owners. Record source freshness as unknown until
   a real refresh signal exists.
7. Do not claim Member 1 DONE until remote restricted-login checks, tenant-01
   import integrity, Member 2 remote read, and Member 3/4 remote contract
   checks are evidenced.

No import command is issued from this worktree: the required Supabase DSNs and
durable LOGINs are absent, the destination has not been freshly checked, and
the importer correctly blocks first-time Supabase identity binding until the
empty-destination question is resolved.
