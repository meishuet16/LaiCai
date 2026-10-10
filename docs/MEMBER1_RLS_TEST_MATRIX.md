# Member 1 — 07B-1 RLS test matrix

Evidence is local PostgreSQL 16.15 / psycopg 3.3.6 only. The security subject
is an actual restricted LOGIN role, not a superuser, table owner, or
BYPASSRLS role. Setup and catalog inspection use a separate administrator
connection against disposable loopback databases.

## Protected table inventory

`test_every_tenant_table_has_positive_and_cross_tenant_negative_evidence`
connects as `retaniq_backend` and verifies own-tenant rows are visible while
Tenant B rows are hidden for each of the 16 tenant-bearing tables. The
cross-tenant write test checks a copied INSERT and ownership-changing UPDATE
for each table; a `retaniq_maintenance` login attempts cross-tenant DELETE on
each table and every operation affects zero rows. These generic-policy checks
do not prove every valid application write shape.

| Table | Tenant ownership path | Positive scope evidence | Negative scope evidence | Valid restricted write evidence / gap |
|---|---|---|---|---|
| `tenants` | Direct `tenant_id` root | All-table scope test | All-table SELECT/INSERT/UPDATE/DELETE test | **GAP:** no normal backend provisioning path; maintenance SELECT/INSERT verified only for global tables |
| `integrations` | Direct `tenant_id`; source registry | All-table scope test | All-table scope/DML test | **GAP:** no restricted successful integration provisioning |
| `customers` | Direct tenant FK | All-table scope test; customer own read | Customer DML/RETURNING test; all-table DML test | **GAP:** no restricted successful customer provisioning |
| `customer_identities` | Direct tenant; composite FK to customer | All-table scope test | All-table DML test | **GAP:** no restricted successful identity-map write |
| `canonical_events` | Direct tenant; composite customer FK | All-table scope test; child JOIN test | All-table DML test; writer source read denied | **GAP:** no successful canonical event insert as backend capability role |
| `usage_events` | Direct tenant; composite canonical/customer FKs | All-table scope test | All-table DML test | **GAP:** no successful subtype write as backend capability role |
| `billing_events` | Direct tenant; composite canonical/customer/owner FKs | All-table scope test | All-table DML test | **GAP:** no successful subtype write as backend capability role |
| `subscriptions` | Direct tenant; composite customer/owner FKs | All-table scope test | All-table DML test | **GAP:** no successful projection write as backend capability role |
| `subscription_events` | Direct tenant; composite canonical/customer/owner FKs | All-table scope test | All-table DML test | **GAP:** no successful history write as backend capability role |
| `feature_snapshots` | Direct tenant; composite customer FK | All-table scope test | All-table DML test | **PASS:** actual artifact-writer repository insert; source-scope checks |
| `churn_labels` | Direct tenant; composite customer FK | All-table scope test | All-table DML test | **PASS:** actual artifact-writer repository insert |
| `predictions` | Direct tenant; composite customer and feature-snapshot FKs | All-table scope test | All-table DML test; cross-tenant artifact insert denied | **PASS:** actual artifact-writer repository insert; dashboard/decision readers are read-only |
| `service_principals` | Direct tenant FK | All-table scope test | All-table DML test; bootstrap invalid-digest case | **GAP:** no restricted successful principal provisioning |
| `subscription_owners` | Direct tenant; composite customer FK, referenced by subscription/billing history | All-table scope test | All-table DML test | **GAP:** no successful restricted ownership-registry write |
| `integration_event_categories` | Direct tenant; composite integration FK | All-table scope test | All-table DML test | **GAP:** no successful restricted category update |
| `observation_coverage` | Direct tenant; composite customer and source/category FKs | All-table scope test | All-table DML test | **GAP:** no successful restricted coverage batch write |
| `dataset_identity` | Global singleton; no `tenant_id` | Maintenance-role SELECT | Backend role is denied | **PARTIAL:** maintenance INSERT verified for checkpoints; global identity write not separately tested |
| `synthetic_import_checkpoints` | Global state keyed by dataset and stream; no `tenant_id` | Maintenance-role INSERT/SELECT | Backend role is denied | **PARTIAL:** checkpoint operation tested directly, not via configured import runtime |
| `retaniq_schema_migrations` | Global migration metadata; no `tenant_id` | Migration runner applies and rereads catalog | Runtime backend role denied | Migration owner path only; not RLS-protected |

## Scenario-to-test evidence

| Scenario | Test evidence | Status |
|---|---|---|
| Positive own-tenant and negative cross-tenant SELECT on all 16 scoped tables | `test_every_tenant_table_has_positive_and_cross_tenant_negative_evidence` | PASS |
| Cross-tenant INSERT and ownership-changing UPDATE on all scoped tables; cross-tenant DELETE filtering on all scoped tables | `test_all_tenant_tables_reject_cross_tenant_insert_update_and_delete` | PASS |
| Missing/invalid context defaults deny; transaction-ended context denies | `test_missing_invalid_and_transaction_ended_context_fail_closed` | PASS |
| Customer INSERT/UPDATE `RETURNING`, UPSERT, cross-tenant write denial | `test_tenants_are_isolated_for_select_insert_update_delete_and_returning` | PASS for customer cases |
| Parent/child joins remain tenant-scoped | `test_child_reads_and_joins_obey_tenant_scope` | PASS for tested canonical/customer join; not every join shape |
| Inference role is read-only; artifact writer cannot read canonical source events | `test_inference_is_read_only_and_artifact_writer_cannot_read_source_events` | PASS |
| Real artifact writes as an artifact-writer login; ungranted source identities hidden | `test_restricted_artifact_writer_uses_verified_source_scope_for_real_writes` | PASS for feature, label, prediction repository paths |
| Dashboard and decision roles cannot delete customer rows | `test_dashboard_and_decision_roles_are_read_only` | PASS for tested grants |
| Schema creation, disabling RLS, granting maintenance, or assuming maintenance denied | `test_roles_cannot_escalate_or_create_schema`; `test_role_inheritance_and_global_table_denial` | PASS |
| Global operational access restricted to maintenance | `test_role_inheritance_and_global_table_denial` | PASS for backend denial and maintenance SELECT/checkpoint INSERT |
| Authentication lookup derives tenant from verified digest; invalid digest installs no context | `test_authentication_bootstrap_derives_tenant_from_verified_digest`; `test_python_authentication_and_repository_scope_use_verified_principal` | PASS locally |
| Commit/rollback and reused-connection context reset | `test_transaction_context_does_not_leak_on_reused_connection` | PASS locally |
| Caller-provided HTTP tenant does not override backend authentication | `test_postgresql_wsgi_api` forged-tenant regression and Python principal test | Application-level PASS |
| Shared custom-GUC spoofing | `test_custom_guc_spoofing_is_possible_to_a_compromised_shared_role` | Risk reproduced, not an isolation guarantee |
| Source/category/purpose grant enforcement | Existing SQLite/PostgreSQL auth, ingestion, historical, and WSGI suites | PASS at application boundary; database policies do not independently encode all custom grants |
| Migration locking, repeat/checksum, rollback and migration history | `tests/test_postgresql_migrations.py` | PASS after versions 001–007 |

## Remaining coverage gaps

- Successful restricted-role write paths for tenants, provisioning, canonical
  and subtype events, subscription projection/history, identity mapping,
  subscription ownership, event categories, and observation coverage.
- The existing generic application DSN is not automatically switched to a
  maintenance credential for trusted provisioning and global import/checkpoint
  operations. The maintenance capability is verified by direct role tests.
- The transaction-local `retaniq.*` values can be forged by a client with
  arbitrary SQL under a shared role. The backend credential must remain inside
  the trusted server; SQL injection or credential compromise crosses the
  documented tenant trust boundary.
- No Supabase schema, role catalog, Data API exposure, or connection pooler was
  modified or tested. Supabase deployment remains 07B-2.

## Aggregate evidence

The focused RLS suite has 16 live test methods, each using real restricted
login roles. Final full dual-backend run: 191 passed, 0 failed, 0 errors,
0 skipped, 0 Python warnings, 67.321 seconds; 57 unique live PostgreSQL-guarded tests
and 16 unique restricted-role/RLS tests ran. SQLite-only: 134 passed,
0 failed/errors, 57 expected live-PostgreSQL skips, 13.518 seconds. Local
evidence is not remote Supabase evidence. Cleanup details are in `TEAM_LOG.md`.
