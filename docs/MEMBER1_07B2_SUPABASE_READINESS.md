# Member 1 — 07B-2 Supabase security deployment readiness

**Status: BLOCKED pending owner decisions and approved project credentials.**
07B-1 remains **PARTIALLY_VERIFIED**: local PostgreSQL 16.15 evidence only.
No Supabase changes or STANDARD import were made.

## Findings

| Finding | Status | Evidence and boundary |
|---|---|---|
| Shared custom-GUC spoofability | **VERIFIED** | A restricted backend login can set `retaniq.tenant_id` directly and read that tenant; the test reproduces this. GUCs are trusted-backend assertions, not database-authenticated identity. Protect only against callers who cannot execute arbitrary SQL with the shared credential. |
| Backend and artifact tenant isolation | **PARTIALLY_VERIFIED** | Local RLS and normal Python authentication/context paths pass. The artifact-writer login successfully stores feature snapshots, labels, and predictions and is denied source-event/ungranted-source reads. Neither role is protected from arbitrary SQL using its own shared credential; this is not independently authenticated tenant isolation. |
| Restricted-role successful write coverage | **PARTIALLY_VERIFIED** | Successful restricted writes cover the three artifact tables. Valid provisioning/ingestion writes for tenants, integrations, customers/identities, canonical and subtype events, subscriptions/owners, service principals, categories, and observation coverage remain untested as their intended capability login. Generic cross-tenant write denials do not fill that gap. |
| Maintenance credential routing | **NOT_VERIFIED** | The application config separates application and migration DSNs, but has no distinct maintenance DSN/selection path. Global import/checkpoint and tenant/source provisioning must not silently use a broadly privileged routine credential. |
| Runtime versus migration roles | **PARTIALLY_VERIFIED** | NOLOGIN capability roles and restricted logins were exercised locally; migration administration is separate in the migration runner. Supabase role creation, ownership, membership, default ACLs, and runtime credential routing have not been verified. The current app does not route every capability role to its own operation. |
| Supabase `service_role` bypass | **VERIFIED platform risk; NOT VERIFIED remotely** | Supabase documents that `service_role`/secret-key requests bypass RLS. It must not be used as the routine RetainIQ backend or as evidence of policy enforcement. No Supabase role catalog was inspected. |
| Transaction-pooler compatibility | **PARTIALLY_VERIFIED** | RetainIQ binds context transaction-locally, keeps it in the protected transaction, disables psycopg prepared statements for transaction mode, and passes local commit/rollback/reuse checks. The actual Supabase pooler has not been exercised; verify the real route and transaction boundaries before use. |
| Migration advisory-lock connection mode | **PARTIALLY_VERIFIED** | Local concurrent migration tests pass. The runner uses a session-level advisory lock, so use a direct or session-pooler migration connection, not transaction pooling. No remote lock/migration test has run. |
| Supabase grants, exposed schemas, and catalog state | **NOT_VERIFIED** | `public`/Data API exposure, default privileges, managed-role grants, object ownership, `BYPASSRLS`, function ownership, and the platform's ability to run the bootstrap/`ALTER FUNCTION OWNER` statements remain unknown. |

## Required before deployment

1. Owner decides whether the documented trusted-backend boundary is acceptable. If arbitrary SQL execution or compromise of a shared runtime credential must still preserve tenant isolation, approve a separate non-spoofable identity design before deployment; the current GUC scheme cannot provide that guarantee.
2. Complete local positive-write tests for the production paths that will use restricted logins, including ordinary authenticated ingestion and approved provisioning/maintenance. Route each operation to an intentional runtime role, or explicitly defer unused capability roles; do not treat role names alone as separation.
3. Confirm a separate, narrowly held maintenance credential and route global import/checkpoint and provisioning operations through it. Keep migration administration separate from both application and maintenance credentials.
4. In the approved Supabase project, verify role-creation/ownership privileges, role memberships and attributes, grants/default ACLs, `public` exposure, and the exact effect of migrations 005–007. Do not broadly revoke platform grants without a reviewed impact check.
5. Re-run positive and negative tests using actual restricted Supabase logins—never `service_role`—including application transactions through the selected pooler. Inspect catalogs after migration and exercise the approved rollback/recovery procedure.

## Required owner approval and configuration

- Designate an isolated synthetic-demo project, project reference, region, owner, and explicit authorization to make database changes. No project is currently approved or configured.
- Approve the GUC threat model or authorize the stronger identity redesign; approve which operator owns provisioning, maintenance, and break-glass procedures.
- Approve backup/recovery and rollback expectations and coordinate the permission model with the inference, decision, and dashboard owners.
- Supply credentials only through the approved secret store/environment—not chat, source control, or a browser: project URL/reference; a restricted application DSN; a distinct maintenance DSN (not currently supported by app routing); and a distinct direct/session-capable migration DSN. The migration DSN must be different from the app DSN. Do not provide a Supabase secret/service-role key to routine RetainIQ code.
- Confirm TLS and the selected connection modes from the project's Connect panel. Transaction pooling is suitable only for the application path after actual transaction-local context and prepared-statement behavior are verified. Use direct/session mode for the migration runner's session advisory lock.

No Supabase Auth replacement is implied: RetainIQ's custom bearer tokens remain the application identity. Supabase Auth JWT claims are not currently mapped to those principals.

## Work that can be completed locally

- Add restricted-role positive-write and repository-path tests for missing table families; cover the intended backend versus maintenance login and connection reuse.
- Add reviewed maintenance-credential configuration/routing and tests, or explicitly defer those operations until the route exists.
- Improve the database identity boundary if the owner rejects shared-GUC spoofability.
- Rehearse role bootstrap, migration ordering/checksum inspection, catalog assertions, and failure rollback against disposable local PostgreSQL. None of this substitutes for remote verification.

## Recommended 07B-2 sequence

1. Obtain the approvals and secret-store configuration above. Do not create a project or infer credentials.
2. Close the agreed local write/routing gaps and rerun the complete SQLite/PostgreSQL regression and restricted-role suite.
3. With approved credentials, run a **read-only** Supabase preflight: verify project identity/region, current schema and migration checksums, roles/attributes/memberships, owners, grants/default ACLs, exposed schemas, and Data API configuration. Stop on mismatch; do not auto-repair.
4. Review each statement in the bootstrap and 005–007 against the actual platform privileges. Agree who owns the protected objects and the two SECURITY DEFINER functions. If a required operation is unavailable, stop and revise via a reviewed forward migration.
5. Take/confirm the approved recovery point. Apply only the approved ordered migrations with the distinct direct/session migration DSN; do not use transaction pooling for the session advisory lock.
6. Inspect RLS flags, FORCE state, policies, table/function ownership, grants, default ACLs, role attributes, and exposed-schema/API privileges. Confirm no routine credential is `service_role`/`BYPASSRLS`.
7. Run actual restricted-role positive/negative tests remotely, then the authenticated RetainIQ backend path and transaction-pooler reuse checks. Record evidence and owner acceptance. If any check fails, stop and follow the reviewed recovery plan.
8. Stop at remote security acceptance. STANDARD import is a separate later task and requires explicit approval; it is not part of 07B-2 readiness or this checkpoint.

Official references: [Supabase API keys and `service_role`](https://supabase.com/docs/guides/getting-started/api-keys), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [exposed/custom schemas](https://supabase.com/docs/guides/api/using-custom-schemas), and [PostgreSQL connection modes and transaction-pooler limitations](https://supabase.com/docs/guides/database/connecting-to-postgres).
