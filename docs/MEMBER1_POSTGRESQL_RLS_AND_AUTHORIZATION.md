# Member 1 — PostgreSQL RLS and authorization (07B-1)

**Status: PARTIALLY_VERIFIED.** Migrations 005–007 were tested locally against
disposable PostgreSQL with actual restricted login roles and are now
catalog-verified on the dedicated Supabase demo. The remote restricted-login
smoke passed its 13 reported scenarios. The shared tenant GUC remains
spoofable by a holder of the trusted backend database credential with arbitrary
SQL access; this is not independently authenticated database tenant identity
or production-grade isolation against credential compromise.

## Scope and inventory

Migrations 001–004 create 18 application tables. Sixteen have a direct
`tenant_id`; two are global operational state. `retaniq_schema_migrations` is
separate migration metadata. There are no application views or triggers in
the current schema. The only sequence is the identity sequence for
`canonical_events.event_id`. Migration 005 adds two SECURITY DEFINER
authentication lookup functions with a fixed `pg_catalog, public` search path,
owned by the NOLOGIN `retaniq_authenticator` role. Migration 006 adds
source-scoped authorization-record reads for the artifact writer; migration
007 restores the explicit global maintenance grants accidentally removed by
005's final deny-list. No migration adds tables.

All 16 tenant-bearing tables have ENABLE and FORCE ROW LEVEL SECURITY. Their
policies compare the direct tenant key to a non-empty
`current_setting('retaniq.tenant_id', true)`; a missing, empty, or unmatched
value returns no rows / rejects writes. Every row still has a composite tenant
foreign key where parent ownership applies; the RLS predicate is not replaced
by foreign-key enforcement.

| Table | PK / tenant key | Ownership path and allowed purpose | Exposure / test evidence |
|---|---|---|---|
| `tenants` | `tenant_id` / direct | Tenant root | Backend / maintenance only; per-table SELECT positive and cross-tenant negative |
| `integrations` | `integration_id` / direct | Tenant FK; source integration registry | Backend/maintenance; authenticator through fixed function; artifact writer reads only its authorized source list |
| `customers` | `(tenant_id, customer_id)` / direct | Tenant FK | Backend, inference, dashboard, maintenance; tenant SELECT and DML negatives tested |
| `customer_identities` | `(tenant_id, source, external_customer_id)` / direct | Composite FK to customer | Backend/inference/maintenance; artifact writer is limited to its transaction-local authorized source list |
| `canonical_events` | `event_id` / direct | Composite FK to customer; integration source/category checked by Python | Backend/inference/maintenance; per-table SELECT positive/negative; child JOIN tested |
| `usage_events` | `(tenant_id, event_id)` / direct | Composite FK to canonical event and customer | Backend/inference/maintenance; per-table SELECT positive/negative |
| `billing_events` | `(tenant_id, event_id)` / direct | Composite canonical/customer FKs and subscription-owner FK | Backend/inference/maintenance; per-table SELECT positive/negative |
| `subscriptions` | `(tenant_id, subscription_id)` / direct | Composite customer and subscription-owner FKs | Backend/inference/maintenance; per-table SELECT positive/negative |
| `subscription_events` | `(tenant_id, event_id)` / direct | Composite canonical/customer/owner FKs | Backend/inference/maintenance; per-table SELECT positive/negative |
| `feature_snapshots` | `feature_snapshot_id` / direct | Composite customer FK; predictions reference the tenant-scoped snapshot | Backend/artifact writer/maintenance; per-table SELECT positive/negative; writer input isolation tested |
| `churn_labels` | `(tenant_id, customer_id, as_of, horizon_days, label_policy_version)` / direct | Composite customer FK | Backend/artifact writer/maintenance; per-table SELECT positive/negative |
| `predictions` | `(tenant_id, prediction_id)` / direct | Composite customer and feature-snapshot FKs | Backend/artifact writer/decision/dashboard/maintenance; per-table SELECT positive/negative; cross-tenant writer rejected |
| `service_principals` | `service_principal_id` / direct | Tenant FK; bearer token digest and stored service grants | Backend and maintenance; authenticator lookup function; per-table SELECT positive/negative |
| `subscription_owners` | `(tenant_id, subscription_id)` / direct | Composite customer FK; composite owner FKs from subscription/billing history | Backend/maintenance; per-table SELECT positive/negative |
| `integration_event_categories` | `(tenant_id, source, category)` / direct | Composite FK to integration `(tenant_id, source)` | Backend/inference/maintenance; authenticator function; artifact writer source-list scoped |
| `observation_coverage` | `(tenant_id, source, coverage_id)` / direct | Composite customer and source/category-grant FKs | Backend/inference/maintenance; per-table SELECT positive/negative |
| `dataset_identity` | singleton `singleton_id=1`; **no tenant key** | Global synthetic provenance, not customer data | RLS; maintenance-only policy/grant; tenant-role denial and maintenance SELECT tested |
| `synthetic_import_checkpoints` | `(dataset_id, stream_name)`; **no tenant key** | Global operational state FK to dataset identity | RLS; maintenance-only policy/grant; tenant-role denial and maintenance INSERT/SELECT tested |
| `retaniq_schema_migrations` | `version`; **no tenant key** | Migration checksum/history metadata | No runtime grant; migration administrator/owner only; not an application table |

For all 16 direct-tenant tables, the live test checks positive own-tenant and
zero cross-tenant SELECT results, rejects a copied cross-tenant INSERT and
ownership-changing UPDATE, and verifies a maintenance-role cross-tenant
DELETE affects zero rows. This checks the shared policy shape on each table;
it is not proof of every valid application write shape on every table. The
test matrix distinguishes tested policy denials from successful writes.

## Roles and grants

`security/postgresql/role_bootstrap.sql` is a separate reviewed bootstrap. It
creates only NOLOGIN capability/group roles, without passwords, LOGIN,
SUPERUSER, CREATEROLE, or BYPASSRLS. The normal migration runner does not
silently create roles. Runtime login roles must be separately provisioned and
granted only the required capability role.

| Capability role | Actual grants / policy | Not granted |
|---|---|---|
| `retaniq_backend` | SELECT/INSERT/UPDATE on the 16 tenant tables; canonical-event sequence USAGE/SELECT; EXECUTE on the two narrow authentication functions; tenant-scoped ALL policy | DELETE/TRUNCATE/REFERENCES, global operational tables, migration metadata, schema CREATE, BYPASSRLS |
| `retaniq_inference_reader` | SELECT on customer identity, canonical/subtype events, subscriptions/history, category grants, and observation coverage; tenant SELECT policies | Writes, artifacts, global state, migration metadata |
| `retaniq_artifact_writer` | SELECT/INSERT on feature snapshots, labels, predictions; SELECT on its own principal and configured-source integration/category/customer-identity records; tenant/artifact/source policies | Canonical and subtype event data, ungranted-source identity records, UPDATE/DELETE, global state |
| `retaniq_decision_service` | SELECT on prediction artifacts only | All writes and source data |
| `retaniq_dashboard_reader` | SELECT on customers and predictions only | All writes and event/source tables |
| `retaniq_maintenance` | SELECT/INSERT/UPDATE/DELETE on tenant tables and global dataset/checkpoint tables; sequence access; tenant policy for tenant tables and explicit maintenance-membership policy for global tables | Migration metadata, schema CREATE, BYPASSRLS |
| `retaniq_authenticator` | NOLOGIN; SELECT only on integration/category/service-principal lookup data under its own restrictive role policy; owns only the two fixed authentication functions | No login, no persistent membership for the migration login, no writes, no bypass |
| Migration administrator | Runs schema migrations and owns migration objects in the configured schema | Must not be the application login; credentials are not represented in SQL |

PUBLIC table privileges and CREATE on `public` are revoked. If Supabase roles
`anon`, `authenticated`, or `service_role` exist, table privileges and
`public` CREATE are revoked from them as well. Sequence grants are explicit.
No TRUNCATE or REFERENCES grants are made. Role inheritance and membership
must be reviewed for each environment; the test login is not a member of the
migration administrator role. `retaniq_artifact_writer` receives its authorized
source list and service-principal ID only from trusted Python code as
transaction-local GUCs; these are subject to the same spoofing limitation as
tenant context.

Supabase's `postgres` role can have `CREATEROLE` without `SUPERUSER`. PostgreSQL
17 creates a non-superuser creator membership with ADMIN TRUE but SET FALSE.
Migration 005 uses ADMIN to add a distinct temporary self-membership with
`SET TRUE, INHERIT FALSE` (without ADMIN), grants the function owner CREATE on
the function schema, transfers ownership, then revokes both temporary grants
before commit. This avoids trying to grant ADMIN back to its grantor while
providing the SET privilege required by `ALTER FUNCTION ... OWNER`. A failure
rolls back the complete migration transaction. The ordering and exact
membership options are asserted by the migration unit test; catalog state still
requires live PostgreSQL verification.

The decision-service capability currently has only a prediction SELECT
contract because the repository has no decision/action tables. Maintenance
does not receive migration-history access. Login creation, passwords, role
membership, schema-owner ownership, and managed-platform privileges remain
environment-specific and must be verified before 07B-2.

## Authentication and tenant context

Custom RetainIQ bearer tokens remain authoritative; Supabase Auth is not
substituted. The WSGI service validates the bearer token by SHA-256 digest and
loads the stored tenant, source, categories/purposes, or service-principal
grants. In PostgreSQL, the narrow SECURITY DEFINER lookup functions validate
the digest and install the verified tenant with transaction-local
`set_config(..., true)`. The definer role is NOLOGIN, has no granted members,
can only select the small authentication lookup set, and the routines pin
their search path and accept only a digest parameter.

For subsequent repository operations, the API passes the returned principal;
the Python database boundary starts the transaction, sets the tenant GUC with
a parameter, and then revalidates the principal against stored grants before
protected queries/writes. HTTP payload/query tenant IDs are not accepted as
authorization identity. On commit, rollback, or connection close, the
transaction-local value does not carry into the next transaction. This
behavior was live-tested on one reused psycopg connection and via the Python
authentication + repository path.

**Threat boundary:** a PostgreSQL custom GUC is not an unforgeable identity.
The test suite intentionally connects with the same backend capability and
sets `retaniq.tenant_id` to Tenant B; RLS then returns Tenant B. Therefore this
design is safe only when the login and arbitrary SQL execution are confined
to the trusted RetainIQ backend. It is not safe against a browser, untrusted
service, SQL injection with arbitrary SQL execution, or compromise of that
shared credential. Do not expose this DSN. Do not claim database identity
isolation against compromised backend credentials. A separately approved
per-tenant database identity or signed/unforgeable context design is needed
if that threat is in scope.

The bootstrap function prevents an authentication query from being trapped
behind tenant RLS: it checks the token digest before setting context. Invalid
digests return no row and install no tenant value. The two Python authentication
functions use it only on PostgreSQL; SQLite behavior remains the existing
digest lookup. Custom database contexts are assertions created by trusted
backend code, not JWT claims. Custom RetainIQ tokens do not automatically
become Supabase JWT claims.

## Local verification

Verified on a disposable local PostgreSQL 16.15 instance with psycopg 3.3.6.
Sixteen tests connected as actual restricted LOGIN roles; no test used a
superuser connection as the security subject. The setup/admin connection was
used only to create the disposable database, seed fixtures, bootstrap roles,
and inspect catalogs. Tests cover catalog state, all 16 tenant-table SELECT
scopes, cross-tenant SELECT/INSERT/UPDATE/DELETE attempts on each of the 16
tenant tables, INSERT/UPDATE RETURNING, UPSERT, child JOIN visibility,
successful feature/label/prediction persistence as the artifact-writer login,
artifact-writer source/event read limits, maintenance global-table access,
role-specific privileges, schema creation, RLS disable, BYPASSRLS escalation,
role membership, authentication bootstrap, invalid/missing context, transaction
cleanup/reuse, Python authentication context, and the GUC-spoofing limitation.

SQLite compatibility is verified by running the complete suite without the
PostgreSQL guard: 134 passed, 0 failures/errors, and 57 expected live-PostgreSQL
guard skips. The live dual-backend full suite ran 191 tests with 191 passed,
0 failures/errors/skips, including 57 unique live PostgreSQL-guarded tests and all 16
restricted-role RLS methods. Existing PostgreSQL migration, ingestion,
historical-query, artifact, bounded import/replay, WSGI, and differential
contracts are rerun after migrations 005–007.

## Migration and rollback

Deployment order is: (1) review and run the no-login role bootstrap as an
approved database administrator; (2) inspect current migration checksums and
schema state read-only; (3) use a direct/session-capable privileged migration
connection to apply versions 001–007 transactionally; (4) inspect `pg_class`,
`pg_policies`, `pg_roles`, `pg_proc`, table ownership, and grants; (5) connect
as each actual restricted login and repeat positive/negative tests; (6) verify
Data API grants and project role attributes; (7) obtain explicit security
acceptance. Never run 005–007 in Supabase before their role prerequisites and
`ALTER FUNCTION ... OWNER` privilege have been approved.

The 005–007 migrations do not change checksums for 001–004. The migration
runner records each version/checksum in the same transaction as its DDL; a
failure rolls back the entire pending migration. Do not edit any applied
migration: create a reviewed forward migration instead. Migration 007 is the
forward correction for the maintenance grants removed by migration 005's
final revocation. Policy rollback would
restore access if RLS is disabled, so no automatic rollback is supplied. Use a
reviewed recovery migration, backup, and restricted-role verification; do not
simply disable RLS to make an application request pass.

Supabase migration-role privileges may differ from local PostgreSQL. In
particular, do not assume it can create/alter roles, change function owners,
revoke managed-role grants, or alter all default ACLs. Validate those exact
operations in the approved project and stop if the platform denies them.
`service_role` bypasses RLS when it has table privileges, so it must not be a
routine RetainIQ login. Data API exposed-schema grants must be explicitly
checked. Use a direct migration DSN when available; the runner also accepts a
separately configured shared session-pooler migration DSN for IPv4-only
environments. Transaction pooling does not preserve session state and is
incompatible with the session advisory lock, so it is never used for migrations.
The application transaction-local GUC is set and consumed within a single
transaction, and psycopg automatic preparation is disabled for transaction
pooling; verify this behavior with the actual pooler before use.

## Required before STANDARD import / 07B-2

- Approved dedicated synthetic-demo Supabase project, project reference,
  region, owner, backup/recovery plan, and protected secrets.
- Separate backend, migration, and any capability login credentials; verified
  role memberships, ownership, `rolsuper`, `rolbypassrls`, default ACLs, and
  actual Data API exposure. No frontend/untrusted service receives a database
  credential.
- Approved decision whether the shared-GUC threat model is acceptable or
  whether per-tenant/non-spoofable DB identity is required.
- Configure and verify a separate maintenance login for tenant/source
  provisioning and global dataset/checkpoint operations. The current generic
  application configuration does not select that capability automatically.
- Verify batch ingest/coverage multi-principal operations, migration history,
  all policy combinations, Supabase catalog state, session-pooler/application
  behavior, backups, and rollback/recovery against the designated project.
- Run actual-restricted-role positive/negative tests remotely without using
  service_role; do not treat local tests or mocked Supabase JWT claims as
  deployment proof.
- Only after 07B-2 acceptance may anyone begin 07C import review. No STANDARD
  data was imported by 07B-1.

## Remaining blockers

The 13-scenario remote smoke covers selected operations, not every table or
write shape. Remaining gaps are durable restricted runtime login provisioning
and routing (including a separate maintenance login), tenant-01-only versus
four-tenant import semantics, successful batch import under actual runtime
roles, Supabase Data API/exposed-schema verification, independent confirmation
that temporary smoke logins were removed, and the documented GUC spoofing
risk if a database credential is compromised. See
`MEMBER1_RLS_TEST_MATRIX.md` for per-table evidence and coverage gaps.

## Current Supabase verification (2026-10-11)

The operator-supplied final `retaniq.supabase_remote_preflight --deploy`
result reported project `mhtzkzqjcsdyjacvcxty`, PostgreSQL 17.11 through the
Session Pooler, migration history `CHECKSUMS_MATCH`, no pending migrations,
and current version 007. No migration was newly applied by that final run
(`applied_versions: []`); migrations 001–007 were already recorded. Catalog
checks passed for 18/18 application data tables with both RLS enabled and
forced, 42 policies, and the two fixed-search-path SECURITY DEFINER
authentication functions owned by `retaniq_authenticator`. The separate
migration metadata table is intentionally outside RLS.

The restricted-login smoke reported PASS for 13 scenarios using temporary
backend, artifact-writer, dashboard-reader, and maintenance logins. It
verified selected default-deny, tenant filtering, denied cross-tenant writes,
transaction-local context clearing, capability-specific artifact/dashboard
permissions, and maintenance cross-tenant delete denial. It also explicitly
confirmed that arbitrary SQL under the shared backend login can spoof the
tenant GUC. The output says temporary-role cleanup was `ATTEMPTED`; absence was
not independently verified. The catalog's `postgres` migration role has
`BYPASSRLS`, `CREATEROLE`, and `CREATEDB`; the runtime capability roles remain
NOLOGIN. No routine `service_role` test was used, and no dataset was imported.

These results verify selected remote catalog and restricted-role behavior,
not complete Data API exposure, durable application credential routing,
complete table/write coverage, or database-enforced identity isolation.

## Supabase references reviewed (2026-10-11)

- [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Postgres roles](https://supabase.com/docs/guides/database/postgres/roles)
- [Connect to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Connection pooling and limits](https://supabase.com/docs/guides/database/connecting-to-postgres/pooling-and-limits)
