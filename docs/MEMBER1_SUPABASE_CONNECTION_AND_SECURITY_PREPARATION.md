# Member 1 — Supabase connection and security preparation (07A)

## Scope and decision

Prompt 07A prepares local configuration, safe connectivity diagnostics, and a
reviewable Phase 07B role/RLS plan. It does **not** create a Supabase project,
apply migrations, enable RLS, provision tenant credentials, import STANDARD,
or deploy application/customer data. Milestone 06 remains
**CONDITIONALLY_ACCEPTED** with the gaps in the 06E acceptance report; this
document does not broaden that claim.

**07A classification: `CONFIGURATION_READY_REMOTE_BLOCKED`.** The local
configuration and preflight implementation is tested. No designated demo
project reference, project URL, application DSN, migration DSN, or Supabase
credential was found in the local process configuration or repository
environment-file metadata. No remote connection was attempted. An official
Supabase Dashboard project could not be independently discovered from this
checkout. Do not infer that one exists or use an unknown/production project.

`AGENT.md`, `AGENTS.md`, and `RetainIQ_v2_Complete_Requirements.md` were not
present in this checkout. No additional requirements were inferred.

## Configuration interface

Local SQLite and PostgreSQL continue through the existing
`retaniq.database_config.DatabaseConfig` and existing shared psycopg connection
layer. Supabase is never an implicit default. Select it explicitly with all
five settings below; a missing/malformed value is an error and never falls
back to SQLite.

| Setting | Required value |
|---|---|
| `RETAINIQ_DATABASE_BACKEND` | `supabase` |
| `RETAINIQ_SUPABASE_PROJECT_URL` | HTTPS project URL copied from the intended Dashboard project |
| `RETAINIQ_SUPABASE_EXPECTED_PROJECT_REF` | Expected project reference, separately confirmed in the Dashboard |
| `RETAINIQ_SUPABASE_DB_APP_DSN` | Application-role connection string copied from that project's Connect panel |
| `RETAINIQ_SUPABASE_DB_MIGRATION_DSN` | Separate migration-role **direct** connection string from the same project |
| `RETAINIQ_SUPABASE_CONNECTION_MODE` | `DIRECT`, `SESSION_POOLER`, or `TRANSACTION_POOLER` for the application DSN |

The code verifies the project URL/reference pair and checks that each DSN's
documented endpoint form/port and project identity agree with the configured
mode/reference. It validates the actual copied string; it does **not** compose
pooler hosts. The application and migration DSNs must use different database
roles. The connection role is not interchangeable with a Supabase API key.
The safe placeholder template is [`.env.supabase.example`](../.env.supabase.example);
it is not a working connection file. `.env` and `.env.*` are ignored except
the committed examples. Never commit a filled-in environment file.

Existing `RETAINIQ_DATABASE_URL` behavior remains available for explicit local
SQLite/PostgreSQL use. Supabase mode rejects mixing those generic targets or
`RETAINIQ_SQLITE_PATH` into the demo configuration.

## Create and identify the intended project

1. The project owner creates or designates a **dedicated RetainIQ synthetic
   demonstration** project. Confirm its name, project reference, region, and
   account ownership in the Supabase Dashboard. Do not point this workflow at
   an unknown or production project. No paid resource or billing setting was
   created or changed in 07A.
2. From the Dashboard, copy the project URL and independently confirm the
   project reference. Put these in the two non-secret settings above.
3. In **Connect**, copy—not reconstruct—the connection string for the chosen
   application connection mode. Copy a separate **direct** connection string
   for the future migration role. Use Dashboard-issued host, port, username,
   database name, and password. Percent-encode reserved password characters
   as directed by Supabase.
4. Phase 07B must create and grant the dedicated least-privilege roles in the
   role plan below before providing an application DSN. Do not use Supabase
   `service_role`, a schema owner, or a superuser as the tenant-facing app
   role. The current migration config intentionally requires distinct app and
   migration usernames.
5. Store values in an approved server-side secret manager or protected local
   environment file with restrictive ACLs. Do not put them in source control,
   frontend variables, a browser bundle, command-line arguments, logs, or
   reports. Rotate the app and migration credentials independently and update
   the corresponding secret-store entry. The repository does not persist
   secrets or implement a production secret manager.

## Connection-mode decision

This checkout was built around a persistent Python backend with short-lived
database connections. Supabase's current guidance distinguishes these paths:

| Mode | 07A handling | Intended use / constraint |
|---|---|---|
| `DIRECT` | Supported; preferred for migration and administration | Direct database endpoint; Supabase documents IPv6 unless an IPv4 add-on is enabled. The future migration DSN must be DIRECT. |
| `SESSION_POOLER` | Supported for app connectivity | Candidate for a persistent Python process on IPv4-only networks. Session features and prepared statements are preserved. |
| `TRANSACTION_POOLER` | Supported for app connection only, with psycopg `prepare_threshold=None` | Candidate for short-lived/serverless requests. Supabase documents that prepared statements and session state do not survive between transactions. RetainIQ's database layer does not invoke query-pipeline mode. |
| `TRANSACTION_POOLER` for migrations | **Rejected before connection** | The migration runner takes a session-level PostgreSQL advisory lock across migration transactions; transaction pooling can move the session between transactions and invalidate that lock. Use the separately configured DIRECT migration DSN via `DatabaseConfig.for_migrations()`. |

Supabase documents direct connections for persistent IPv6 backends and
migrations; the shared session pooler for IPv4-only persistent backends; and
the transaction pooler for short-lived/serverless workloads. The shared pooler
is IPv4 reachable. Its host and username include Dashboard-specific values;
the application must copy them from **Connect**, not derive them from a
region or project reference. See the official
[connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

The application-level transaction-pooler support is deliberately narrow:
psycopg prepared statements are disabled, operations remain transaction-bound,
and no migration/advisory-lock path is permitted. A successful configuration
parse is not evidence of a successful remote connection or of full production
compatibility.

Connection sizing remains an operator decision after the target plan/compute
limits and expected concurrency are known. The current client opens and closes
short-lived connections and has no application pool. Do not enable extra pool
layers or raise Supabase pool limits without a connection budget. Count direct
connections plus each pooler's backend connections against the database max,
leaving headroom for Supabase-managed services; monitor Dashboard connection
usage before a shared demo. See [Supabase pooling and limits](https://supabase.com/docs/guides/database/connecting-to-postgres/pooling-and-limits).

## TLS and credential handling

Every remote PostgreSQL target, including Supabase, must use SSL. `disable`,
`allow`, and `prefer` are rejected; only `require`, `verify-ca`, and
`verify-full` pass the remote encrypted-transport check. The diagnostic labels
these distinctly:

- `require`: encrypted, but the server certificate/hostname identity is **not
  verified**.
- `verify-ca`: the configured certificate authority is verified, but hostname
  identity is **not** verified. The configuration requires an explicit
  `sslrootcert` path.
- `verify-full`: CA trust and server hostname are verified. The configuration
  requires an explicit `sslrootcert` path; install/download the current root
  certificate from the project's Dashboard and protect/update it as directed.

Prefer `verify-full` when the deployed trust configuration supports it.
Supabase notes that `sslmode=require` encrypts but does not prevent a
man-in-the-middle attack. A certificate file without a driver option does not
establish verification. Do not describe `require` as identity verification;
see [Supabase SSL guidance](https://supabase.com/docs/guides/database/connecting-to-postgres#ssl).

Configuration objects hide DSNs from `repr`; driver failures are translated
to static safe errors; the preflight output never prints a DSN, password,
API/JWT key, or exception text. Never put credentials in a CLI `--db`
argument. The DSNs are server-side database credentials, not frontend
configuration.

## Read-only preflight

Run from the repository root after setting all required variables in the
process's protected environment:

```powershell
python -m retaniq.supabase_preflight
```

The command requires explicit `RETAINIQ_DATABASE_BACKEND=supabase`; otherwise
it exits with a sanitized `BLOCKED` JSON result. With valid configuration it
checks psycopg availability, connects once using the app DSN and once using
the separate DIRECT migration DSN, executes only read-only probes, reports
the current database/role and superuser/BYPASSRLS status, and compares the
existing public-schema migration history/checksums with local migration files.
It closes both connections on success and failure. No schema, role, row, or
migration is created or altered. If app-role privileges do not allow a
read-only check, the result is a readiness gap, not a reason to elevate the
routine app role.

An expected report may say `BLOCKED` or
`CONNECTED_WITH_READINESS_GAPS`. Even
`PREFLIGHT_PASSED_NOT_DEPLOYMENT_APPROVAL` would only establish sanitized
read-only connectivity, non-bypass app role, and matching migration
checksums. It does not prove RLS, end-user authorization, backups, deployment
security, production readiness, or permission to import data.

### Actual connection evidence

**Remote result: `REMOTE_SUPABASE_CONNECTIVITY_BLOCKED` — not attempted.**
There was no explicit project designation or configured secret metadata.
No URL/reference/region/credentials have been invented. Local mocked preflight
unit tests are not remote connectivity evidence.

## 07B database-role architecture (proposed; not provisioned)

All tenant-facing roles must be `NOBYPASSRLS`; no browser receives a database
DSN. Supabase's `service_role` (and its secret API key path) bypasses RLS and
must never be used as evidence that tenant policies work. An owner/migrator
can also bypass policies through ownership or elevated role attributes. Keep
those credentials server-side, separate from the routine application role,
and out of customer request paths. Supabase's official
[RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security)
and [Postgres roles guide](https://supabase.com/docs/guides/database/postgres/roles)
describe these behaviors.

| Logical role | Existing Member 1 purpose mapping | Allowed actions / data | Tenant and source/category boundary | Authentication and RLS bypass |
|---|---|---|---|---|
| Schema migration | None; operator/deployment credential, not a service principal | Reviewed DDL and migration-history access only; apply checksum-verified migrations | No routine tenant data access; schema-scoped, controlled operator | Protected deployment secret + approved change; preferably non-login owner plus short-lived migration login. Schema owner/elevated migration role is never routine; may bypass unless tables force RLS. |
| Backend application | Implements the existing authenticated `IntegrationPrincipal` / `ServicePrincipal`; purpose checks remain authoritative | Calls existing ingestion/read/write repositories. Exact SQL table grants to be least-privilege per operation | Backend derives tenant from validated opaque token; source and category grants remain separate checks | Trusted server only; `NOBYPASSRLS`. No frontend DB credential. |
| Tenant-scoped inference reader | `retention_inference`; add `billing_valuation` only for monetary values | SELECT authorized customer/event/subscription/coverage/artifact facts; billing amounts only with the separate valuation purpose | Tenant plus authorized source; category policy for usage/subscription/billing. Same-tenant unauthorized source is not automatically allowed. | Trusted backend principal or verified Supabase Auth subject mapped to tenant; `NOBYPASSRLS`. |
| Model artifact writer | `model_artifact_write` **and** `retention_inference` as required by current artifact APIs | INSERT feature snapshots, churn labels, and predictions for authorized mapped customer/source; no arbitrary schema or tenant writes | Tenant plus customer identity through an authorized source. Billing-valued features additionally require `billing_valuation`. | Trusted Member 2 service credential through backend; `NOBYPASSRLS`. |
| Decision Engine service | Existing `retention_inference`; optional `billing_valuation` if an approved contract requires it | Current schema has no decision/action/outcome table or dedicated Decision Engine purpose. 07B must define its contract before granting writes; presently read inputs only. | Tenant/source scopes remain mandatory. Source/category grants are not tenant isolation. | Trusted server identity only; `NOBYPASSRLS`. No inferred permission to write absent tables. |
| Read-only dashboard | `retention_inference`; `billing_valuation` only for approved monetary display | SELECT only through a trusted backend/API projection; no direct frontend database connection | Tenant and user membership/source scope, plus field-level billing purpose at API boundary | Verified user session through approved identity provider; backend maps user to tenant. `NOBYPASSRLS`. |
| Administrative maintenance | Operational operator/admin workflow, possibly `integration_health`; no broad purpose implies DB superuser | Audited operational maintenance, retention/export, recovery tasks as separately approved; no routine model/customer browsing | Explicit approved tenant/operation scope; emergency break-glass has independent approval and audit | Separate short-lived operator identity and protected credential; prefer `NOBYPASSRLS`; if a break-glass role must bypass, it is never tenant-facing and requires independent control. |

Required-table inventory per logical role (the actual grants must still be
minimized to each endpoint/job):

| Logical role | Required table set |
|---|---|
| Schema migration | Schema objects and `retaniq_schema_migrations`; no routine tenant-row reads. |
| Backend application | `tenants`, `integrations`, `customers`, `customer_identities`, `canonical_events`, `usage_events`, `billing_events`, `subscriptions`, `subscription_events`, `subscription_owners`, `integration_event_categories`, `observation_coverage`, `feature_snapshots`, `churn_labels`, `predictions`, and narrowly scoped `service_principals`; synthetic importer additionally needs `dataset_identity` and `synthetic_import_checkpoints`. |
| Tenant-scoped inference reader | `customers`, `customer_identities`, canonical/subtype events, `subscriptions`, `observation_coverage`, and approved `feature_snapshots`, `churn_labels`, `predictions`. |
| Model artifact writer | `customers`/`customer_identities` for scoped linkage; INSERT into `feature_snapshots`, `churn_labels`, `predictions`. |
| Decision Engine service | Read-only access to scoped customer/event/subscription/coverage/prediction inputs; no decision/action table exists yet, so no write target is approved. |
| Read-only dashboard | No direct SQL requirement; if a reviewed backend projection exists, its limited source tables are `customers`, `subscriptions`, `feature_snapshots`, and `predictions`. |
| Administrative maintenance | No standing grant. Per-operation allowlist and audit record determine required tables. |

These are logical separation requirements, not a claim that PostgreSQL roles or
RLS are already implemented. Existing purposes are application-level
permissions, not database grants. Existing WSGI service authentication uses
opaque token digests in `service_principals`; Supabase Auth user identity and
tenant membership are not implemented. Phase 07B must settle that mapping
before granting access.

## RLS trust boundary and planned table coverage

RLS must be enabled and forced where appropriate, and grants must independently
limit operations. `USING` governs visible/target rows; `WITH CHECK` governs
new/updated rows. A policy must require authenticated tenant membership or a
server-authenticated tenant claim, **and** source/category/purpose where the
operation requires it. Source/category authorization never substitutes for
tenant isolation. Do not create permissive placeholder policies.

The only acceptable tenant context is derived after authenticating a signed
Supabase Auth identity or the existing integration/service credential at a
trusted backend. Never trust a request-body `tenant_id`, an arbitrary caller
JWT claim, or a caller-controlled custom session setting. If 07B selects a
backend-bound tenant context, it must be transaction-local, derived from the
authenticated principal in trusted server code, inaccessible to frontend
clients, and cleared by transaction/connection reset; tests must prove forged
tenant fields/settings and connection reuse cannot cross tenants. Prefer a
database-verifiable signed identity or tenant-membership lookup over a naked
`set_config('tenant_id', caller_value, ...)`. Policy helper/security-definer
functions need pinned empty `search_path`, schema-qualified names, audited
ownership, restricted EXECUTE grants, and tests for recursive-policy behavior.

Planned coverage of all tables in the canonical PostgreSQL migrations (and
the runner metadata table):

| Table | Tenant ownership key / exception | Planned SELECT | Planned INSERT | Planned UPDATE | Planned DELETE | Admin exception and required negative tests |
|---|---|---|---|---|---|---|
| `tenants` | `tenant_id` | Same authenticated tenant only | Trusted tenant-provisioning backend only | Trusted admin provisioning only | No routine delete; audited tenant-retention process | Cross-tenant read/write denied; forged tenant denied; no tenant-facing delete. |
| `integrations` | `tenant_id`; `source` is a narrower app scope | Same tenant and source-grant metadata for trusted backend | Trusted integration provisioning only | Trusted integration/category operator only | Audited maintenance only | Other-tenant and ungranted-source reads denied; ordinary app cannot provision or delete. |
| `customers` | `(tenant_id, customer_id)` | Same tenant; identity/source eligibility also enforced in app/API | Trusted identity/customer service only | Trusted identity/customer service only | Audited retention only | Cross-tenant, unmapped identity, forged customer/tenant denied. |
| `customer_identities` | `tenant_id`; composite identity `(tenant_id, source, external_customer_id)` | Same tenant and authorized source | Identity-mapping backend with `identity_mapping` purpose | Same scoped identity-mapping backend | Audited identity-correction process only | Cross-tenant and ungranted source denied; duplicate/forged identity cannot rebind. |
| `canonical_events` | `tenant_id`; source and category are additional scopes | Same tenant + authorized source + event category | Trusted ingestion path only | None (append-only) | No routine delete; retention admin only | Cross-tenant/source/category denied; direct tenant-facing insert/update/delete denied. |
| `usage_events` | `tenant_id` via canonical event/customer composite FKs | Same tenant + source + `usage` category + inference purpose | Trusted ingestion path only | None | Retention admin only | Parent/event tenant mismatch, unauthorized source/category, direct mutation denied. |
| `billing_events` | `tenant_id` via event/subscription/customer composite FKs | Same tenant + authorized billing source/category; monetary columns additionally require `billing_valuation` | Trusted ingestion only | None | Audited retention only | No cross-tenant/source access; amount/currency unavailable without valuation grant; mutation denied. |
| `subscriptions` | `(tenant_id, subscription_id)` | Same tenant and authorized source/history scope | Trusted canonical subscription ingestion only | Trusted projection updater only | Audited retention only | Cross-tenant owner and unauthorized source denied; payment-only events cannot mutate entitlement. |
| `subscription_events` | `tenant_id` via canonical event/subscription/customer | Same tenant + authorized source + subscription category | Trusted ingestion only | None (append-only) | Audited retention only | Cross-tenant/category denied; direct update/delete denied. |
| `feature_snapshots` | `(tenant_id, customer_id)` | Tenant inference/dashboard reader, authorized mapped customer | Artifact writer after inference + artifact purpose checks | None (immutable snapshot contract) | Audited retention only | Other tenant/customer/source denied; inference-only writer and arbitrary fields denied. |
| `churn_labels` | `(tenant_id, customer_id)` | Approved inference/evaluation backend only | Trusted label/outcome pipeline after maturity validation | None (versioned evidence) | Audited retention only | Cross-tenant, premature label, and unauthorized writer denied; unknown remains explicit. |
| `predictions` | `(tenant_id, customer_id)` | Tenant inference reader/dashboard projection | Decision/model service with artifact-write contract | None (immutable prediction/run contract) | Audited retention only | Cross-tenant/customer denied; reader cannot write; privileged roles are not used to claim policy enforcement. |
| `service_principals` | `tenant_id` | No user/API direct reads; narrow backend authentication lookup/function only | Trusted operator provisioning only | Trusted rotation/revocation only | Audited revoke/retention only | Token plaintext never stored; cross-tenant token lookup and raw-table access denied. |
| `subscription_owners` | `tenant_id`; no source column, ownership derived from subscription FK | Trusted backend consistency check only, joined to tenant-filtered subscription/source facts | Subscription ingestion/ownership trigger only | None; ownership immutable | Audited correction only | Cross-tenant and conflicting-owner claim denied; no source authorization inferred from this table. |
| `integration_event_categories` | `tenant_id`; source/category pair | Trusted backend category authorization lookup | Trusted integration operator only | Trusted operator replaces explicit grants only | Trusted operator only | Other tenant/source and ungranted categories denied; category is not a replacement for tenant policy. |
| `observation_coverage` | `tenant_id`; `source`, `source_category`, `customer_id` | Same tenant + authorized source/category and inference purpose | Trusted coverage/import service only | Prefer immutable versioned replacement; explicit trusted updater if contract allows | Audited retention only | Cross-tenant/customer/source/category denied; missing is not verified zero; lifecycle heartbeat is separate evidence. |
| `dataset_identity` | Global singleton synthetic provenance; **no `tenant_id`** | Trusted operator/model pipeline only; keep out of API exposure | Migration/import administrator only | No routine update; immutable dataset binding | No routine delete | Not tenant data. Restrict schema/table grants; reject public API access and attempt to rebind the singleton. |
| `synthetic_import_checkpoints` | `dataset_id` -> global `dataset_identity`; **no `tenant_id`** | Import operator only | Trusted synthetic importer only | Same import operator, atomic checkpoint update | Audited reset/replay operator only | Operational progress is not tenant scope; restrict to private schema/grants, reject API/customer access and wrong dataset. |
| `retaniq_schema_migrations` | Migration schema/version metadata; **no tenant key** | Migration/deployment verifier only | Migration runner only | Migration runner only | No routine delete | Keep inaccessible to app/API roles; test missing SELECT privilege and checksum/history mismatch. |

Negative-test minimum for every tenant-owned row family: same-tenant allowed
case where intended; cross-tenant SELECT/INSERT/UPDATE/DELETE denial; forged
tenant/customer/source/category denial; and role-specific disallowed write.
Test with actual non-bypass database roles, not only Python principal checks.
For tables without `tenant_id`, tests prove that no public API role can reach
them and that global operational state cannot be used to infer another
tenant's data. Migration metadata is not an application table.

## Schema exposure and migration safety

Current migrations and queries target the default `public` schema. Supabase
Data API exposure/grants make this a material risk even before a frontend
exists. RLS and least-privilege grants must be applied before data import.
Consider placing RetainIQ data in a dedicated, non-API-exposed schema. This
reduces accidental Data API reachability, but the current repositories issue
unqualified table names; safe adoption therefore requires reviewed schema
qualification/connection search-path behavior, migration-runner updates, and
integration tests. Do not silently move the schema in 07A. A plain session
`search_path` setting is also unsuitable as a transaction-pooler assumption.

Phase 07B migration workflow, before any demo import:

1. Confirm the dedicated project reference, owner approval, region, network
   connectivity, and recovery/backup expectations.
2. Confirm the app and migration database roles are separate; inspect role
   attributes and grants using a privileged audit path without exposing
   credentials. App role must not own tables or have `BYPASSRLS`.
3. Verify local migration checksums and the target's current migration history
   read-only. Resolve drift by review; never edit an already-applied file.
4. Use the DIRECT migration connection only. Review the exact migration and
   rollback/recovery plan. No blind or automatic production migration.
5. Apply grants, RLS enable/force, and policies as one controlled reviewed
   security change. Keep policy helpers out of exposed schemas or prove
   restrictive invocation/ownership.
6. Run positive and negative live tests using the actual app/inference/artifact
   roles, including cross-tenant attempts, source/category boundaries, app-role
   `BYPASSRLS` status, connection reuse/context reset, and direct Data API
   exposure checks.
7. Verify backup/restore/recovery expectations and read-only preflight again.
   Only after explicit acceptance of those checks may Phase 07C consider a
   synthetic STANDARD import. Never import real/customer data in this demo
   milestone.

No migrations were applied in 07A.

## Tests and evidence

Local tests added for environment parsing and target selection, malformed and
wrong-project DSNs, TLS enforcement and verification labels, distinct roles,
secret redaction, DIRECT/SESSION/TRANSACTION mode classification, transaction
pooler migration rejection and prepared-statement disablement, preflight
BLOCKED behavior, read-only SQL, cleanup after connection errors, safe output,
role-plan completeness, and exact coverage of every canonical migration table.
The preflight tests use fake connections strictly as unit-test evidence; they
are **not** Supabase connectivity evidence.

Verification on 2026-10-11 (Singapore local date; test host UTC date 2026-10-10):

| Run | Result |
|---|---|
| Supabase config + preflight + database config/connection/migration focused suite | **59 run; 0 failures/errors; 5 expected live-PG skips**, 0.133s. Guarded migration integration cases also ran in the full live suite below. |
| Full unittest discovery with a disposable loopback PostgreSQL 16.15 cluster and psycopg 3.3.6 | **175 passed; 0 failures; 0 errors; 0 skipped**, 66.250s; all **41 unique live PostgreSQL integration tests** ran. |
| Full SQLite-only unittest discovery | **134 passed; 0 failures; 0 errors; 41 expected PostgreSQL-guarded skips**, 14.877s. |
| `compileall`, package import smoke, and `git diff --check` | **PASS**. No Python warnings; expected unauthorized/invalid-request test log entries only. |
| Actual Supabase preflight | `BLOCKED` (exit 2), sanitized reason `supabase_demo_configuration_missing_or_invalid`; no remote attempt. |

The temporary test databases `retaniq_test_07a_20261011` and
`retaniq_test_07a_final_20261011` were dropped and their shared task-owned
PostgreSQL cluster was stopped after verification. The exact
stopped cluster data directory remains under the current user's Temp path;
the shell's recursive-removal safeguard rejected deleting that directory.
The unrelated Windows PostgreSQL service was not used or modified. The
isolated test run is not evidence of Supabase connectivity. The existing synthetic handoff
contains local STANDARD/FULL import evidence, but PostgreSQL/Supabase + RLS
STANDARD deployment readiness and scale remain unverified. Supabase has not
been contacted.

## Known limits and phase dependencies

- No designated Supabase project, credentials, or remote connectivity evidence.
- No RLS policies or database grants have been applied; this is a plan, not a
  security boundary.
- The WSGI service currently uses opaque service-principal records and
  application checks. Supabase Auth identity and tenant membership are not
  mapped.
- The current migration runner creates schemas/tables and uses a session lock;
  migrations require a direct connection.
- A non-exposed schema is recommended for review but not implemented; current
  SQL assumes `public`/default search path.
- Decision Engine write purposes/tables are not present in the Member 1
  schema; 07B must define its contract before grants are designed.
- Supabase/PostgreSQL + RLS STANDARD import readiness and scale, real-data
  permissions, customer data, and Member 2's maturity/outcome-coverage/
  freshness/heartbeat questions remain unresolved. Existing local synthetic
  STANDARD/FULL handoff evidence is not remote deployment evidence. Any Phase
  07C import depends on 07B RLS, least-privilege grants, verified import
  provenance, and Member 2's independent outcome/freshness readiness evidence.

## Official guidance reviewed

- [Supabase: Connect to your database](https://supabase.com/docs/guides/database/connecting-to-postgres) — current connection-mode selection, Dashboard connection strings, IP versions, pooler usernames/ports, prepared statements, transaction-mode session-state limitations, and SSL verification distinctions.
- [Supabase: Connection pooling and limits](https://supabase.com/docs/guides/database/connecting-to-postgres/pooling-and-limits) — client/backend connection limits, shared vs dedicated poolers, and capacity headroom.
- [Supabase: Disabling prepared statements](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL) — psycopg `prepare_threshold=None` for transaction-mode poolers.
- [Psycopg 3 connection API](https://www.psycopg.org/psycopg3/docs/api/connections.html) — `prepare_threshold=None` disables automatic prepared statements.
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security) — API grants, `service_role`/secret-key bypass behavior, role policies, and security-definer/search-path cautions.
- [Supabase: Postgres roles](https://supabase.com/docs/guides/database/postgres/roles) — built-in `authenticated` and `service_role` behavior and managed roles.

Supabase guidance accessed 2026-10-11. Dashboard availability, project
configuration, credentials, and connection results were not inferred from
documentation.
