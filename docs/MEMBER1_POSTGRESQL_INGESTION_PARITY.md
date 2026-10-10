# Member 1 PostgreSQL ingestion parity — Prompt 06D-1

06D-1 adds a bounded set of PostgreSQL-backed Member 1 data-foundation
operations without claiming complete PostgreSQL parity. The existing
normalization, minimization, principal validation, category/purpose policy,
event hash, and subtype decisions remain shared in
`retaniq/data_foundation.py`; only backend persistence details branch.

## Implemented PostgreSQL operations

The following existing operations accept SQLite paths or an explicit
`DatabaseConfig` for PostgreSQL:

- Tenant, integration/category grants, customer, and service-principal setup.
- Integration and service-principal token authentication and stored-grant
  revalidation; mapping-version updates and safe source-health updates/reads.
- Tenant-scoped identity mapping, including exact idempotent repeats and
  conflicting-owner rejection.
- `ingest_event()` for canonical usage, billing, and subscription events,
  including subscription-owner/projection updates.
- `ingest_events_batch()` and its synthetic import checkpoint read/write, plus
  the existing CSV importer path through `update_mapping_version()` and
  `ingest_event()`.

All other PostgreSQL repository operations remain explicitly gated by `_db()`
and raise `PostgreSQLSchemaNotReady`; there is no fallback to a SQLite file.

## Shared contracts and backend-specific behavior

The shared path validates the authenticated `IntegrationPrincipal`, binds the
tenant/source to stored integration state, checks category and purpose grants,
normalizes only allowlisted event attributes, and hashes the same canonical
envelope used by SQLite. Tenant identity is derived from the principal; an
event cannot supply a `tenant_id`. No email matching or implicit identity
creation is performed.

`DatabaseConnection` retains SQLite `sqlite3.Row` behavior and PostgreSQL
`dict_row` behavior. Its PostgreSQL qmark adapter changes `?` placeholders
only outside quoted strings, identifiers, comments, and dollar-quoted blocks;
it is not a broad SQL rewrite. PostgreSQL-specific `ON CONFLICT`, `RETURNING`,
and `FOR UPDATE` remain visible at persistence call sites. SQLite retains
`INSERT OR IGNORE`, `lastrowid`, and `BEGIN IMMEDIATE` where needed.

Normalized ISO-8601 instants are bound to PostgreSQL as aware `datetime`
values for `TIMESTAMPTZ`. Health timestamps are rendered back to the existing
UTC ISO-8601 string response contract. Event occurrence, receipt, and trusted
source-availability times remain distinct; availability is never replaced by
import time.

## Transaction, identity, and idempotency guarantees

Each operation uses one connection-owned transaction. Canonical event,
subtype row, subscription-owner claim, subscription projection, integration
success state, and—when batching—the checkpoint commit together. Any exception
rolls back all writes in that transaction.

For PostgreSQL, the unique key `(tenant_id, source, source_event_id)` is used
with `ON CONFLICT ... DO NOTHING RETURNING event_id`. A concurrent identical
retry reads the winning row and returns `duplicate`; a conflicting normalized
hash returns `idempotency_conflict`. No existing event is overwritten.
SQLite writers retain `BEGIN IMMEDIATE` and the same event hash comparison.

Identity mapping uses `(tenant_id, source, external_customer_id)` uniqueness.
PostgreSQL uses `ON CONFLICT ... DO NOTHING RETURNING` and checks the winning
customer mapping after a conflict. Subscription ownership is protected by the
unique `(tenant_id, subscription_id)` key; PostgreSQL inserts or locks the
owner row with `FOR UPDATE`. The owner lock serializes projection rebuilds by
different workers, and the composite child foreign keys remain the final
tenant/owner integrity boundary. No process-local mutex is used as a database
concurrency guarantee.

Batch import locks the singleton dataset identity row with `FOR UPDATE` on
PostgreSQL before reading/updating its checkpoint. This serializes checkpoint
advancement for that bound dataset. Checkpoint success is written only in the
same transaction as its event/subtype writes.

## Authentication and authorization

Integration and service-principal tokens are SHA-256 digests in the database;
the bearer is returned only at provisioning time and is never included in
errors or health output. Authentication checks the digest, then operations
revalidate the stored principal ID, tenant, source/role, and grants. Integration
category grants are read from `integration_event_categories`; service
principals retain their exact source and purpose sets. Rotating the stored
digest revokes the previous bearer. The schema has no expiry field or expiry
policy, so token expiry is not claimed.

These are application-level authorization checks—not PostgreSQL Row Level
Security. RLS, Supabase Auth, production database roles, and production
deployment remain out of scope.

## Event semantics and safe errors

The established `EVENT_TYPES` rules and minimized attributes are unchanged.
Payment failures create billing evidence but do not end subscriptions.
Cancellation requests remain `pending_cancel`; only effective cancellation,
non-renewal, or involuntary termination records `ended`. A future source fact
retains its trusted `source_available_at` independently of `received_at`.

Existing safe `DataFoundationError` codes are preserved: `unauthorized`,
`source_not_authorized`, `event_category_not_authorized`,
`identity_not_mapped`, `idempotency_conflict`, `contract_conflict`, and
`invalid_event`. PostgreSQL integrity errors retain only SQLSTATE and a
constraint identifier internally; messages and payloads are discarded.
Unique/FK ownership conflicts map to the existing conflict contract. Other
database failures use the safe backend-neutral `DatabaseError` path (the WSGI
API reports `internal_error`); transaction failures never return accepted.

## 30-scenario coverage map

| # | Scenario | Coverage |
|---:|---|---|
| 1 | Valid authenticated ingestion | PG `test_usage_persistence...`; SQLite authenticated push and ingestion tests |
| 2 | Invalid token | PG `test_integration_and_service_authentication...`; SQLite auth/WSGI tests |
| 3 | Revoked/rotated token | PG auth/token-rotation test; SQLite digest-backed auth contract |
| 4 | Expiry behavior | Not supported: no expiry column or policy exists |
| 5 | Wrong tenant | PG authorization test rejects body tenant; SQLite `test_tenant_is_derived...` |
| 6 | Unauthorized source | PG authorization test; SQLite source authorization tests |
| 7 | Unauthorized purpose | PG narrow billing grant test; SQLite `test_source_authorization...` |
| 8 | Unauthorized category | PG authorization test; SQLite multicategory and usage-only tests |
| 9 | Restricted attributes | PG authorization test; SQLite allowlist/redaction tests |
| 10 | Valid identity mapping | PG identity concurrency test; SQLite mapping/ingestion setup |
| 11 | Duplicate identity mapping | PG identity concurrency test; SQLite identity tests |
| 12 | Conflicting identity ownership | PG sequential and concurrent identity conflict test; SQLite mapping tests |
| 13 | Usage subtype persistence | PG usage persistence test; SQLite event/subtype tests |
| 14 | Billing subtype persistence | PG lifecycle test; SQLite payment failure and billing tests |
| 15 | Subscription subtype persistence | PG lifecycle/owner-race tests; SQLite subscription history tests |
| 16 | Cancellation semantics | PG lifecycle test; SQLite pending/effective cancellation tests |
| 17 | Payment failure is not churn | PG lifecycle test; SQLite `test_payment_failure_is_billing_risk...` |
| 18 | Occurrence time preserved | PG usage persistence test; SQLite temporal tests |
| 19 | Receipt/availability preserved | PG usage and CSV-import tests; SQLite late-availability/import tests |
| 20 | Identical retry | PG sequential and concurrent retry tests; SQLite idempotency tests |
| 21 | Conflicting retry | PG concurrent conflicting retry; SQLite conflicting duplicate test |
| 22 | Concurrent identical ingestion | PG 8-worker idempotency test |
| 23 | Concurrent conflicting ingestion | PG 2-worker conflicting retry test |
| 24 | Subscription-owner race | PG 2-customer owner race; SQLite owner conflict tests |
| 25 | Canonical/subtype atomicity | PG injected subtype-failure rollback test; SQLite transaction suite |
| 26 | Rollback on injected persistence failure | PG subtype and batch rollback tests; SQLite batch rollback coverage |
| 27 | Rejected event has no partial row | PG authorization and rollback tests; SQLite rejected-event tests |
| 28 | Source health consistency | PG ingestion timestamps and safe health read; SQLite health/failure tests |
| 29 | No SQLite fallback | `_db()` backend gate and explicit unsupported historical-read test; SQLite connection tests |
| 30 | Secret/payload redaction | PG auth and restricted-field tests; SQLite API/error/log redaction tests |

## Verification and known limits

The guarded live suite is `tests/test_postgresql_ingestion.py`; it requires an
explicit disposable marker, loopback host, and database name prefixed
`retaniq_test_`. It exercises actual PostgreSQL writes, rollback, retries,
row locks, and concurrent workers. Existing SQLite tests remain the
authoritative regression suite for the unchanged backend.

Verification on Python 3.12.14, psycopg 3.3.6, and a task-created disposable
PostgreSQL 16.15 cluster:

- Live PostgreSQL ingestion suite: **11 passed**, 0 failed/errors/skipped, in
  12.109 seconds. Five PostgreSQL catalog/constraint/migration integration
  tests also ran live within the 20-test migration suite (**20 passed** in
  2.189 seconds).
- Matching SQLite Data Foundation suite: **48 passed** in 6.939 seconds;
  five focused source/category/purpose authorization tests passed in 0.673
  seconds, and four importer/batch/checkpoint regressions passed in 0.401
  seconds.
- Full suite with the disposable PostgreSQL target enabled: **116 passed**,
  0 failed, 0 errors, 0 skipped, 0 Python warnings, in 28.529 seconds as
  reported by unittest (28.859 seconds wall clock). Expected safe rejection
  log lines were emitted by authorization tests; no rejected payload values
  or credentials were logged.
- `compileall`, package import checks, and `git diff --check` passed. Git
  emitted only its configured LF-to-CRLF working-copy notices.
- Actual PostgreSQL concurrency cases: 8 workers replaying one identical
  event (one insert/seven duplicates); 2 workers racing conflicting payloads
  (one accepted/one conflict); 8 workers claiming the same identity/customer;
  2 workers racing a conflicting identity mapping; and 2 customers racing for
  one subscription owner (one accepted/one rejected). All passed.

The full requirements document and `AGENT.md`/`AGENTS.md` were not available
in this checkout; the compliance documentation references a requirements
location on `D:\dunno\dormathon`, which was absent. Existing frozen contracts
and migrations were therefore used without inventing additional fields or
policies.

The 06D-1 boundary does **not** include `get_events_as_of`, historical
subscription replay, observation coverage reads/writes, MRR/account
valuation, feature snapshots, churn labels, predictions, complete synthetic
dataset provisioning, or the WSGI API startup path. These continue to reject
PostgreSQL explicitly. The next scope is **06D-2 — Historical Queries and
Coverage Parity**; no work from that milestone is included here.
