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

### 2026-10-10T17:02:46Z — Member 1 / Data & Backend Engineer — 07A Supabase configuration and security preparation

- **Workstream:** Part 1 / Supabase demo connectivity, secret handling, Phase 07B RLS preparation
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** N/A — 07A changes intentionally uncommitted for review
- **Issue / task:** Prompt 07A only; stop before Phase 07B/07C/07D and Phase 08.
- **06E checkpoint:** `89a0293e3b89789b7df43c5b44563459154f055f` — `test(member1): verify sqlite postgres contract conformance`, committed locally after staging/reviewing the exact five 06E paths. No push or merge.
- **Files changed in 07A:** `.gitignore`, `.env.supabase.example`, `retaniq/database_config.py`, `retaniq/database.py`, `retaniq/postgresql_migrations.py`, new `retaniq/supabase_preflight.py`, new `tests/test_supabase_configuration.py`, new `tests/test_supabase_preflight.py`, new `docs/MEMBER1_SUPABASE_CONNECTION_AND_SECURITY_PREPARATION.md`, and this entry.
- **What changed:** Added explicit Supabase demo selection to the existing database config/shared psycopg client; verified project-reference and mode-specific DSN identity; separated app/migration roles and required a direct migration DSN; added TLS policy/labels, secret-safe diagnostics, and a SELECT-only preflight; prepared the role/RLS table inventory and deployment safety procedure.
- **Why it changed:** Establish secure, fail-closed configuration before a shared synthetic demo without applying schema changes or sending data remotely.
- **Contract / database / API impact:** SQLite and local PostgreSQL behavior retained. Supabase remains opt-in. Transaction-pooler application connections disable psycopg prepared statements (`prepare_threshold=None`); migrations reject transaction mode because the runner holds a session-level advisory lock. Supabase migrations route through the separate direct migration DSN. No API endpoint or migration file changed; no RLS/grants deployed.
- **Tests / verification:** Focused Supabase/config/preflight/migration suite — **PASS** — 59 tests, 0 failures/errors, 5 expected guarded PostgreSQL skips, 0.133s. Full discovery on isolated local PostgreSQL 16.15 / psycopg 3.3.6 — **PASS** — 175 passed, 0 failures/errors/skips, 66.250s, 41 unique live PostgreSQL tests. SQLite-only full discovery — **PASS** — 134 passed, 41 expected live-PG skips, 14.877s. `compileall`, package imports, and `git diff --check` — **PASS**. No Python warnings; only expected rejected-request logs.
- **Data / model / ROI evidence:** No Supabase or customer data accessed. Test databases `retaniq_test_07a_20261011` and `retaniq_test_07a_final_20261011` were confined to a loopback-only temporary cluster, then dropped; the cluster was stopped. Its stopped directory remains in Temp because recursive removal was blocked by the shell safeguard. The unrelated Windows PostgreSQL service was untouched.
- **Known issues / blockers:** No Supabase project reference/URL or app/migration DSN configured; remote connectivity was not attempted. Local preflight returned sanitized `BLOCKED` (exit 2). RLS, grants, identity mapping, schema exposure changes, remote migrations, and remote import remain unimplemented. `AGENT.md`, `AGENTS.md`, and the complete requirements document were absent and not inferred.
- **Next action / handoff:** **CONFIGURATION_READY_REMOTE_BLOCKED.** User/project owner must designate a dedicated RetainIQ synthetic demo project, confirm identity/region, create reviewed distinct app/migration roles in 07B, obtain DSNs from Dashboard Connect, and place them in a protected secret store. Next coding scope is 07B: reviewed grants/RLS plus live positive/negative tests. Do not run 07C import until RLS/security acceptance.
- **Reviewer / pairing:** N/A

### 2026-10-10T16:32:31Z — Member 1 / Data & Backend Engineer — 06E dual-database contract conformance

- **Workstream:** Part 1 / Data Foundation, PostgreSQL parity, security regression
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** N/A — Prompt 06E changes intentionally uncommitted
- **Issue / task:** Prompt 06E — final dual-database contract conformance and Milestone 06 assessment; stop before Phase 07.
- **06D-3 checkpoint:** `106cc67e86219d14995529a6c91515c0358130e7` — `feat(member1): complete PostgreSQL persistence replay and API parity`, local commit created at the start of this prompt after auditing and staging the exact 15-file 06D-3 set.
- **Files changed in 06E:** new `tests/test_dual_database_contracts.py`, new `docs/MEMBER1_DUAL_DATABASE_CONTRACT_MATRIX.md`, new `docs/MEMBER1_POSTGRESQL_MIGRATION_ACCEPTANCE.md`, updated `tests/test_postgresql_import_replay.py`, and this entry.
- **What changed:**
  - Added seven shared fixture runners executing the same deterministic authenticated scenario on fresh SQLite and PostgreSQL databases and strictly comparing normalized business outputs.
  - Covered event digests/idempotency/conflicts, as-of event availability/replay, artifact persistence/auth, MRR/payment/cancellation/coverage/source grants, existing WSGI routes and rejection atomicity, concurrent identical/conflicting ingestion, subscription-owner races, and subtype-trigger rollback.
  - Added a direct check that the Member 2 synthetic workflow principal intentionally receives only `retention_inference` and `model_artifact_write` by default, with no `billing_valuation` unless explicitly requested.
  - Added a PASS/GAP contract matrix, principal permission matrix, and formal Milestone 06 acceptance/Phase 07A recommendation.
- **Why it changed:** Verify cross-backend behavior with identical inputs and make the distinction between storage parity, explicit untested contract variants, operational data readiness, and production security auditable.
- **Contract / database / API impact:** No application implementation, schema migration, applied migration checksum, endpoint, or shared payload contract changed in 06E. Tests use backend-specific DB triggers only to inject subtype persistence failure; the public event API is invoked on each engine. Timestamp normalization is restricted to UTC representation; API health processing times are validated per backend because they arise from separate real executions.
- **Tests / verification:**
  - 06D-3 baseline before 06E edits on fresh guarded PostgreSQL 16.15 — **PASS** — 150 passed, 0 failed/errors/skips, 63.665s; 34 live PostgreSQL tests.
  - Focused differential suite — **PASS** — 7 shared comparisons, each run on SQLite and live PostgreSQL; final focused run 13.395s.
  - Final full unittest discovery with PostgreSQL 16.15 / psycopg 3.3.6 — **PASS** — 157 passed, 0 failed, 0 errors, 0 skipped, 75.887s; 41 unique live PostgreSQL tests ran.
  - SQLite-only full suite — **PASS** — 157 total, 116 passed, 41 expected PostgreSQL-guarded skips, 15.012s.
  - `compileall`, package import smoke, and `git diff --check` — **PASS**. No Python warnings; expected unauthorized/invalid-request test logs only.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only. The import fixture is bounded quick profile; no STANDARD-scale, real-customer, model, performance, or ROI claim.
- **Known issues / blockers:** No critical parity mismatch found. Noncritical coverage-state enumeration and strict MRR cross-output variants remain gaps (see matrix); richer label evidence/status/evaluation metadata and a full uncertainty object are not represented by current storage. RLS, external identity, production hosting, real-data permission/provenance, full-scale import, and Member 2's previously reported maturity/coverage/freshness/heartbeat blockers remain outside this prompt. Member 2's current corrections were not assumed or independently verified.
- **Next action / handoff:** Milestone 06 is **CONDITIONALLY_ACCEPTED**: core dual-backend conformance is verified, with specified noncritical gaps. The exact task-created database `retaniq_test_06e_20261011` was dropped, the differential child database was dropped by test teardown, and only the task-owned PostgreSQL cluster was stopped; the unrelated Windows service was untouched. Recommended next scope is Phase 07A Supabase tenant-security/RLS foundation after policy review; do not begin it automatically. Leave 06E changes uncommitted; no push, merge, or deployment.
- **Reviewer / pairing:** N/A

### 2026-10-10T16:11:05Z — Member 1 / Data & Backend Engineer — 06D-3 PostgreSQL artifacts, import, replay, and WSGI parity

- **Workstream:** Part 1 / Data Foundation & PostgreSQL parity
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** N/A — intentionally uncommitted per task instruction
- **Issue / task:** Prompt 06D-3 — PostgreSQL artifact persistence, historical replay, import/checkpoint compatibility, and existing WSGI API parity; stop before 06E.
- **Files changed:** `retaniq/api.py`, `retaniq/data_foundation.py`, `retaniq/importer.py`, `retaniq/postgresql_migrations.py`, `retaniq/synthetic/canonical_adapter.py`, `tests/test_data_foundation.py`, new `tests/test_postgresql_artifact_persistence.py`, new `tests/test_postgresql_import_replay.py`, new `tests/test_postgresql_wsgi_api.py`, `README.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, new `docs/MEMBER1_POSTGRESQL_PERSISTENCE_AND_REPLAY_PARITY.md`, and `TEAM_LOG.md`.
- **What changed:**
  - Ported existing feature snapshot, churn-label, and prediction writers to PostgreSQL with timezone-aware timestamp binding, duplicate/conflict normalization, unchanged payload validation and immutable keys, and least-privilege service-principal authorization.
  - Enabled PostgreSQL dataset identity/provenance, synthetic identity provisioning, coverage batch checkpointing, bounded quick-profile import, and existing authorized historical replay without SQLite fallback.
  - Enabled the existing WSGI routes on PostgreSQL. Startup verifies migration history/checksums read-only and refuses an uninitialized schema; it does not auto-migrate or add endpoints.
  - Fixed a confirmed first-initialization concurrency race by acquiring the advisory lock before PostgreSQL schema creation.
  - Added shared SQLite/live PostgreSQL artifact-contract tests, PostgreSQL WSGI tests, and bounded dual-backend import/checkpoint/replay tests; documented the capability matrix and contract limitations.
- **Why it changed:** Complete the scoped 06D-3 repository parity requested for Member 1 without changing Member 2/3 worktrees, inventing new artifact shapes, or implying production readiness.
- **Contract / database / API impact:** No new migration, endpoint, SQLite schema, or feature/label/prediction payload shape. Artifact service writers require role `analyst` and explicit `model_artifact_write`; source/customer scope is enforced. PostgreSQL startup performs read-only migration verification. Labels still lack a richer status/evidence-reference/evaluation-time schema; predictions retain `uncertainty_status=not_quantified` rather than a full uncertainty object. Application authorization is not RLS.
- **Tests / verification:**
  - Baseline before edits — **PASS** — 138 tests, 0 failures/errors/skips.
  - Focused feature/label/prediction fixtures — **PASS** — shared SQLite and live PostgreSQL contract tests; focused import/replay (1), WSGI (3), and schema-initialization concurrency tests passed.
  - Full suite with disposable loopback PostgreSQL 16.15 and psycopg 3.3.6 — **PASS** — 150 tests, 150 passed, 0 failures/errors/skips; 34 live PostgreSQL integration tests ran (64.205s). Initial run exposed the schema-creation race; the corrected rerun passed.
  - Full suite without PostgreSQL test target — **PASS** — 150 total, 116 passed, 34 expected live-PostgreSQL tests skipped (17.112s), confirming SQLite/unit regressions.
  - `compileall` — **PASS**; `git diff --check` — **PASS** (only expected Windows LF/CRLF notices).
- **Data / model / ROI evidence:** Deterministic synthetic quick fixture only (12 accounts, 4 tenants, 2025-01-01 through 2025-05-31); no real customer rows, model training, model performance, or ROI evidence.
- **Known issues / blockers:** Full `STANDARD` PostgreSQL import/load is intentionally untested. Member 2's zero mature 7/14/30-day labels, insufficient verified outcome coverage, 97.21% stale/insufficient snapshots, and missing independent lifecycle/billing heartbeat remain unresolved. RLS, production identity/deployment, encryption-at-rest, scheduled workers, and Supabase remain out of scope. Complete requirements and `AGENT.md`/`AGENTS.md` were unavailable in this checkout.
- **Next action / handoff:** Stop at 06D-3; do not begin 06E. Keep all task changes uncommitted; no push, merge, or deployment. The exact task-created disposable database `retaniq_test_06d3_20261010` was dropped, and only the task-owned PostgreSQL cluster under the temporary runtime directory was stopped; the separate Windows PostgreSQL service was left untouched.
- **Reviewer / pairing:** N/A

### 2026-10-10T15:44:36Z — Member 1 / Data & Backend Engineer — 06D-2 live historical query verification

- **Workstream:** Part 1 / Data Foundation & PostgreSQL parity
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): verify PostgreSQL historical query and coverage parity`
- **Issue / task:** Prompt 06D-2V; preceding 06D-1 checkpoint: `9f0442b4d52594b65c70bf9486e9375cc24c243d`
- **Files changed:** `retaniq/data_foundation.py`, `retaniq/database.py`, `tests/test_postgresql_ingestion.py`, `tests/test_postgresql_historical_queries.py`, `docs/MEMBER1_POSTGRESQL_HISTORICAL_QUERY_PARITY.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `README.md`, `TEAM_LOG.md`
- **What changed:**
  - Enabled existing historical event, subscription, account snapshot, and coverage read APIs on PostgreSQL with source/category-aware grants, UTC-aware cutoff binding, and the existing output timestamp shape.
  - Enabled idempotent PostgreSQL single coverage writes using the existing contract and unique key; reused existing historical subscription fold and valuation policy.
  - Added shared SQLite/live-PostgreSQL fixtures for cutoff, authorization, lifecycle, MRR, coverage, and read-only behaviors; updated the earlier explicit-unsupported test.
- **Why it changed:** Prompt 06D-2 requires historical Data Foundation inputs for Member 2/3 without changing their worktrees or inventing service contracts.
- **Contract / database / API impact:** Existing Python function signatures and result shapes remain. Historical reads now enforce the existing source/category grants against stored rows, including after grant narrowing. Availability remains `source_available_at` with `received_at` fallback; both time predicates are inclusive. Application authorization is not RLS. No schema migration was added.
- **Tests / verification:**
  - Task-owned PostgreSQL 16.15 cluster startup initially failed to bind loopback; explicit IPv4-only `-h 127.0.0.1 -p 62534` recovered it. psycopg 3.3.6 smoke — PASS — real `SELECT 1`, server/database identity, commit, rollback, and connection cleanup.
  - `python -B -m unittest discover -s tests -p 'test_postgresql_migrations.py' -v` — PASS — 20 total including 5 live migration integration tests, 1.912s.
  - `python -B -m unittest discover -s tests -p 'test_postgresql_ingestion.py' -v` — PASS — 11 live ingestion/concurrency tests, 13.590s.
  - `python -B -m unittest discover -s tests -p 'test_postgresql_historical_queries.py' -v` — PASS — 22 total, including 11 live PostgreSQL and 11 shared SQLite fixtures, 13.654s.
  - Full `python -B -m unittest discover -s tests` — PASS — 138 tests, 138 passed, 0 failed, 0 errors, 0 skipped, 42.118s. All 27 unique PostgreSQL integration tests executed live; no Python warnings (expected unauthorized-request log messages only).
  - `compileall`, package imports, and `git diff --check` — PASS. Test target `retaniq_test_06d2v_20261010` was confirmed absent before creation, then dropped after tests; only the task-owned cluster was stopped. No code defect was confirmed; SQLite historical contracts matched PostgreSQL expectations.
- **Data / model / ROI evidence:** Synthetic engineering fixtures only; no model or ROI claims.
- **Known issues / blockers:** Member 2's reported zero mature 7/14/30-day labels, insufficient authorized outcome coverage, 97.21% stale/insufficient snapshots, and missing independent lifecycle/billing heartbeat remain unresolved and outside this task. Complete requirements and `AGENT.md`/`AGENTS.md` remain unavailable (`D:\dunno\dormathon` absent).
- **Next action / handoff:** 06D-2 historical-query parity is live-verified. 06D-3 remains a separate task for feature/label/prediction persistence and any scoped import/checkpoint/replay work. No push or merge.
- **Reviewer / pairing:** N/A

### 2026-10-10T15:14:20Z — Member 1 / Data & Backend Engineer — PostgreSQL ingestion, identity and auth parity

- **Workstream:** Part 1 / Data Foundation, PostgreSQL Ingestion Parity
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): add PostgreSQL ingestion and identity parity` (06D-1 remains uncommitted)
- **Issue / task:** Prompt 06D-1 — PostgreSQL ingestion, identity, authorization and transaction parity; stop before 06D-2.
- **Files changed:** `retaniq/database.py`, `retaniq/data_foundation.py`, `tests/test_database_connection.py`, new `tests/test_postgresql_ingestion.py`, new `docs/MEMBER1_POSTGRESQL_INGESTION_PARITY.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `docs/MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, `README.md`, and `TEAM_LOG.md`.
- **What changed:**
  - **06C checkpoint:** Prompt 06C was locally checkpointed at `4eeb2b303701f63b0d246aeca4a357b16ad0c55b` with subject `feat(member1): implement PostgreSQL schema and migration runner`; its staged-path audit included only the 06C files and this log. No push/merge.
  - Added a quote/comment-aware PostgreSQL placeholder adapter and safe integrity metadata; enabled the existing shared setup/authz/authentication, tenant identity mapping, mapping-version/source health, canonical `ingest_event`, bounded batch/checkpoint, subtype, and CSV importer paths for PostgreSQL.
  - Added PostgreSQL `ON CONFLICT ... RETURNING` for identity/event writes and database-enforced owner/event conflict handling; `FOR UPDATE` serializes subscription-owner claims/projection rebuilds and the batch dataset checkpoint. Normalization, minimization, event hashing, tenant binding, and grants stay shared with SQLite.
  - Updated README/backend/compliance/schema notes and added a 30-scenario test coverage map. Historical queries, observation coverage, valuation, feature/label/prediction persistence, complete synthetic provisioning, and WSGI API startup remain explicitly unsupported on PostgreSQL.
- **Why it changed:** Establish verified PostgreSQL parity for Member 1's core ingestion/auth/identity path without weakening the existing contract or overstating full backend parity.
- **Contract / database / API impact:** Existing event/principal shapes and error codes are preserved. PostgreSQL `TIMESTAMPTZ` receives aware datetime parameters and health output returns normalized UTC strings. Payment failures do not end subscriptions; known cancellations remain distinct. Application authz is not RLS. No Supabase, production DB, cross-member work, or data copy.
- **Tests / verification:**
  - Pre-edit baseline on the disposable target — **PASS** — 104 tests, 0 failed/errors/skipped, 14.110 seconds.
  - Live PostgreSQL ingestion — **PASS** — 11 tests, 0 failed/errors/skipped, 12.109 seconds. Actual concurrency: 8 identical-ingest workers; 2 conflicting-ingest workers; 8 same-owner identity workers; 2 conflicting-identity workers; 2 subscription-owner contenders.
  - Existing PostgreSQL schema/migration tests — **PASS** — 20 tests, including all five live PostgreSQL integration tests, 2.189 seconds.
  - SQLite Data Foundation regression — **PASS** — 48 tests, 6.939 seconds; focused five authorization tests passed in 0.673 seconds; four importer/batch/checkpoint tests passed in 0.401 seconds.
  - Full suite on Python 3.12.14 + psycopg 3.3.6 against PostgreSQL 16.15 — **PASS** — 116 passed, 0 failed, 0 errors, 0 skipped, 0 Python warnings; unittest duration 28.529 seconds (28.859 seconds wall clock).
  - `compileall`, package import checks, and `git diff --check` — **PASS**. Four expected safe request-rejection log lines came from negative tests; no credentials/restricted values were exposed. Git showed only LF/CRLF normalization notices.
- **Data / model / ROI evidence:** Synthetic-only fixtures and task-created disposable PostgreSQL database; no customer dataset, model, or ROI results.
- **Known issues / blockers:** Complete requirements and `AGENT.md`/`AGENTS.md` were absent; the cited `D:\dunno\dormathon` requirements path was unavailable. Integration/service token expiry is not an existing schema feature. Historical query and coverage parity, other persistence, production TLS/identity, and RLS remain unverified/out of scope.
- **Next action / handoff:** The disposable `retaniq_test_06d1` database was dropped and its task-created cluster was stopped (`pg_ctl` confirms no server); the existing `postgresql-x64-16` Windows service remains Running and was not targeted. The known temporary cluster and isolated psycopg venv directories remain on disk for safe reuse; recursive deletion was rejected by the environment. Keep 06D-1 changes uncommitted. Next milestone is **06D-2 — Historical Queries and Coverage Parity**; do not begin it automatically.
- **Reviewer / pairing:** N/A

### 2026-10-10T14:47:40Z — Member 1 / Data & Backend Engineer — PostgreSQL schema and migrations

- **Workstream:** Part 1 / Data Foundation, PostgreSQL Schema & Migrations
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat(member1): implement PostgreSQL schema and migration runner`
- **Issue / task:** Milestone 06C — implement the PostgreSQL schema and explicit migration runner; stop before 06D.
- **Files changed:** `migrations/postgresql/001_data_foundation.sql` through `004_dataset_identity_and_observation_coverage.sql`, `retaniq/postgresql_migrations.py`, `retaniq/data_foundation.py`, `retaniq/database.py`, `retaniq/database_config.py`, `retaniq/__main__.py`, `tests/test_postgresql_migrations.py`, `docs/MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`, `docs/MEMBER1_TO_MEMBER2_DATA_HANDOFF.md`, `README.md`, and `TEAM_LOG.md`.
- **What changed:**
  - Added four PostgreSQL migrations for the canonical 18-table Data Foundation schema, tenant-composite keys, constraints, indexes, identity sequence, timestamps, integration grants/owners, and dataset identity/coverage. Serialized payload text stays `TEXT`; PostgreSQL uses `BIGINT`, `DOUBLE PRECISION`, and `TIMESTAMPTZ` where appropriate.
  - Added ordered/checksummed migration discovery, history validation, session advisory locking, per-migration atomic transactions, schema targeting, and actionable safe errors. `init-db` explicitly applies the PostgreSQL migrations; ordinary repository operations remain SQLite-only pending 06D.
  - Documented the schema compatibility matrix, runner and disposable test procedure, status/limitations, and Member 2 database handoff. No SQLite data-copy or query-adaptation work was included.
- **Why it changed:** 06C provides a verifiable PostgreSQL schema and repeatable migration lifecycle after the 06B backend foundation, without implying repository/query parity or production readiness.
- **Contract / database / API impact:** New PostgreSQL schema matches the logical SQLite table/column contract with native PostgreSQL types, named constraints, tenant-scoped foreign keys, and indexes. PostgreSQL initialization is available only through the explicit migration path. No RLS, Supabase, application query parity, data migration, production service, or remote database changes.
- **Tests / verification:**
  - Full suite with temporary PostgreSQL 16.15 cluster and psycopg 3.3.6, guarded by the disposable loopback test target — **PASS** — 104 tests, 0 failures, 0 errors, 0 skips; all five live catalog/constraint/transaction/checksum/concurrency integration tests ran.
  - Focused PostgreSQL migration tests — **PASS** — 20 tests, including all five live-server integration tests.
  - `python -B -m compileall -q retaniq tests` using the isolated test runtime — **PASS**.
  - `git diff --check` — **PASS** — no whitespace errors; Git noted LF-to-CRLF normalization for existing text files.
  - Bundled-runtime full suite without psycopg/test DSN — **PASS** — 104 tests, 99 passed and the five live-PostgreSQL tests skipped by their safety guard; 0 failures/errors.
- **Data / model / ROI evidence:** Only synthetic test fixtures and an empty, task-created disposable PostgreSQL database. No real customer data, model, or ROI analysis used.
- **Known issues / blockers:** Complete requirements and `AGENT.md`/`AGENTS.md` were not present in this checkout; the compliance record points to requirements under inaccessible `D:\dunno\dormathon`. PostgreSQL stores timestamps as `TIMESTAMPTZ`, unlike SQLite text; query/repository compatibility and any data conversion remain unverified until 06D. No production isolation/RLS or deployment claim is made.
- **Next action / handoff:** Member 1 proceeds to 06D-1 PostgreSQL ingestion/identity/auth parity, then 06D-2 historical query and coverage parity. This checkpoint is local only; no push or merge. The disposable database was dropped and its task-created PostgreSQL cluster stopped. The environment rejected recursive deletion of the two exact temporary directories (`retaniq-06c-postgres-runtime` and `retaniq-06c-psycopg-venv`), so their stopped cluster files and isolated driver environment remain on disk. The pre-existing Windows PostgreSQL service was not targeted.
- **Reviewer / pairing:** N/A

### 2026-10-10T14:18:47Z — Member 1 / Data & Backend Engineer — Configurable database backend foundation

- **Workstream:** Part 1 / Data Foundation, Database Configuration & Transactions
- **Branch:** `codex/member1-postgres-migration`
- **Commit subject:** `feat: add configurable database backend foundation`
- **Issue / task:** Milestone 06B — implement a configurable database connection and transaction foundation.
- **Files changed:** `retaniq/database_config.py`, `retaniq/database.py`, `retaniq/data_foundation.py`, `retaniq/__main__.py`, `requirements-postgresql.txt`, `tests/test_database_config.py`, `tests/test_database_connection.py`, `docs/MEMBER1_DATABASE_BACKEND_CONFIGURATION.md`, `README.md`, and `TEAM_LOG.md`.
- **What changed:**
  - Added typed SQLite/PostgreSQL target parsing with explicit backend selection, environment configuration, TLS policy for remote PostgreSQL, local insecure-test opt-in, and redacted representations/errors.
  - Added SQLite and optional psycopg 3 connection lifecycle primitives with commit/rollback ownership, explicit nested-transaction rejection, SQLite foreign-key/busy-timeout setup, and migration-operation guards.
  - Routed the existing SQLite Data Foundation through the shared boundary and made PostgreSQL repository use fail explicitly until 06C/06D schema and parity work; no schema, RLS, Supabase, contract-field, or tenant-auth changes were made.
- **Why it changed:** 06B requires a backend-aware foundation that preserves current SQLite behavior while making future PostgreSQL migration and repository work explicit, testable, and free of silent SQLite fallback.
- **Contract / database / API impact:** Existing SQLite behavior and public contracts remain unchanged. PostgreSQL configuration and connection support are available as a foundation only; existing Data Foundation operations reject PostgreSQL with a readiness error. No PostgreSQL migration or production database was changed.
- **Tests / verification:**
  - Bundled Python `-B -m unittest discover -s tests -p 'test_database_config.py' -v` — **PASS** — 12 focused configuration tests.
  - Bundled Python `-B -m unittest discover -s tests -p 'test_database_connection.py' -v` — **PASS** — 8 focused connection/transaction tests.
  - Bundled Python `-B -m compileall -q retaniq tests` — **PASS**.
  - Bundled Python `-B -m unittest discover -s tests -v` — **PASS** — 84 tests in 13.257 seconds.
  - Bundled Python `-B -m compileall -q retaniq tests` — **PASS**; `git diff --check` — **PASS** — no whitespace errors, with only Git line-ending normalization notices.
- **Data / model / ROI evidence:** No data, model, prediction, or ROI evidence was generated. Existing synthetic-only status is unchanged.
- **Known issues / blockers:** `POSTGRES_CONNECTION_SMOKE_NOT_RUN` — no safe PostgreSQL instance/DSN was available; psycopg 3 is not installed in the bundled runtime; `psql`, `postgres`, and `pg_ctl` are absent; Docker was not started. PostgreSQL feature parity remains unimplemented.
- **Next action / handoff:** Member 1 next implements 06C PostgreSQL schema and migrations, then 06D query/repository parity. Keep Supabase deferred to the later infrastructure phase. No commit, push, or merge is part of this handoff.
- **Reviewer / pairing:** N/A

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
