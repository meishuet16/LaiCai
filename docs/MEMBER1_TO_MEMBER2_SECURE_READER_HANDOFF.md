# Member 1 → Member 2 secure STANDARD reader handoff

## Readiness

**READER_READY** for the bounded, tenant-01 synthetic STANDARD read pilot. A real bearer credential was provisioned into the dedicated working copy, and authenticated reads through the Member 1 historical APIs passed. This is not a production data or source-health readiness claim.

## Provenance and isolation

- P0 branch: `codex/member1-p0-reader-handoff`.
- P0 worktree: `C:\Users\User\.codex\worktrees\member1-p0-reader-handoff\LaiCai`.
- Base: 07A checkpoint `90f745392e32a52d8ac896e302b81221ec617ee0`.
- The unfinished 07B-1 RLS changes remain only in `C:\Users\User\.codex\worktrees\member1-postgres-migration\LaiCai` and were not copied or edited.
- Approved dataset: Synthetic SaaS v1.2 STANDARD, seed 2026.
- Dataset ID: `synthetic-saas-v1-2-standard-s2026-970a9d231e68`.
- Dataset manifest SHA-256: `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- Immutable source DB: `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3`.
- Expected and reverified source DB SHA-256: `71bc6c18d9266c2b0c8b8e5008f6f6633a55804b1fe90a947f8ea24ca3ee5943`.
- Approved generated data directory: `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68`.

The source DB was read-only during the SQLite online backup. The backup used `sqlite3.Connection.backup`, which takes a consistent snapshot and includes active WAL state. The original source uses DELETE journaling and had no WAL/SHM sidecars at backup time. Before provisioning, the copy matched the source identity and had all 239,721 canonical events and 491,223 coverage rows. The initial raw working-copy SHA-256 was `648b66d4da5a3d1460a8d9949de0c8a1634d71b80be65fb0077e87cfa5675000`.

The copied DB contained five pre-existing service-principal records, including broader tenant-01 purposes, and imported integration token digests. The P0 copy invalidated all five service principals and all 12 integration token digests, recording the principal revocations. It retained the four-tenant synthetic data, dataset identity, event rows, coverage rows, and per-source category grants. The post-sanitization, pre-P0-reader DB SHA-256 was `b47ea1f31c89bada483aa19d189bd3f9f5e1b09a509dd22440c0ad8227ce493f`. These operations changed only the working copy.

The exact Member 2 DB is:

`C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\working\member1-p0\synthetic-saas-v1-2-standard-s2026-970a9d231e68-tenant-01-reader.sqlite3`

Its `dataset_identity` remains bound to the approved manifest and STANDARD dataset ID. Final working-copy SHA-256 after reader provisioning is `68404ded8052dc3199dbe0051819f445247b65b3d16adca5af68406d54443114`. `PRAGMA integrity_check` returned `ok`; the final copy retains 239,721 events, 491,223 coverage rows, four tenants, and exactly one service principal. Do not select the immutable `db\...sqlite3` source or another prepared database for the bounded pilot.

## Reader grant and provisioning path

The reader is service principal `member2-standard-tenant-01-reader`, role `analyst`, tenant `tenant-01`, with purpose `retention_inference` only. Its exact source/category grants, derived from `customer_identities.csv` and verified against the imported metadata, are:

| Source | Category |
| --- | --- |
| `tenant-01-synthetic-usage-v1-2` | `usage` |
| `tenant-01-synthetic-billing-v1-2` | `billing` |
| `tenant-01-synthetic-subscription-v1-2` | `subscription` |

It has no `model_artifact_write`, `billing_valuation`, `identity_mapping`, `integration_health`, administrative purpose, or access to another tenant. Tenant scope is taken from the authenticated `ServicePrincipal`; these read APIs accept no caller-supplied tenant ID. Billing status is available with amount/currency removed, and subscription price/MRR fields are omitted.

`python -m retaniq.synthetic provision-reader` now validates the exact STANDARD dataset identity, full imported counts, and source/category metadata before provisioning. It is limited to this tenant and the dedicated working-copy path. It creates or rotates the single fixed principal ID in one DB transaction and uses the SHA-256 token-digest schema. The one-time token is passed directly to the current-user Windows DPAPI store; command output contains only grant metadata and the protected file path. The migration `005_service_principal_credential_audit.sql` records `provision`, `rotate`, and `revoke` events without token material.

## Credential storage and lifecycle

The protected token file is:

`C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard-tenant-01-reader-p0.dpapi`

It is encrypted to the Windows identity that provisioned it. It is not a portable credential file. The current file ACL is owned by `LAPTOP-P974JQL0\User`, with full control also for SYSTEM and local Administrators; DPAPI protects the contents to the current user. The receiving Member 2 process must run under that Windows user or the operator must provision/re-protect through an approved secret manager for the receiving identity. Never decrypt the token to a terminal or paste it into chat.

Provision or intentionally rotate the reader (rotation invalidates the prior token and atomically replaces the protected file):

```powershell
$python = 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$dataset = 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68'
$db = 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\working\member1-p0\synthetic-saas-v1-2-standard-s2026-970a9d231e68-tenant-01-reader.sqlite3'
$secret = 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard-tenant-01-reader-p0.dpapi'
& $python -m retaniq.synthetic provision-reader --dataset $dataset --db $db --tenant-id tenant-01 --secret-file $secret
```

Revoke the reader and make the stored token invalid:

```powershell
& $python -m retaniq revoke-member2-reader --db $db
```

The credential digest is stored in `service_principals`; plaintext token material is not. Rotation and revoke have focused tests. The general-purpose `create-service-principal` command remains a trusted local operator tool with broader grant options; do not use it for this read pilot.

## Authenticated historical smoke

Member 1 ran a deterministic, small authenticated read at `2026-10-01T00:00:00Z` through:

- `get_events_as_of()`
- `get_subscriptions_as_of()`
- `get_account_snapshot_as_of()`
- `get_observation_coverage_as_of()`

The actual token was loaded from DPAPI into the child process as `RETAINIQ_MODEL_TOKEN` without being printed:

```powershell
& $python -m retaniq.secret_store run --file $secret -- $python -m examples.member1_p0_authenticated_reader_smoke --db $db
```

The smoke authenticated the tenant-01 reader, checked all returned source/category pairs and both historical visibility predicates (`occurred_at <= as_of` and `available_at <= as_of`), serialized the results, verified that valuation fields were omitted, and rejected a tenant-02 account. Result: **PASS**, 23 events, 1 subscription, 48 coverage rows; no account identifiers or event payloads were printed. The SQLite `data_version` and modification time stayed unchanged during the historical reads.

## Bounded Member 2 pilot

1. Use the exact `working\member1-p0\...tenant-01-reader.sqlite3` path above.
2. Run the DPAPI-wrapped smoke command above. This injects `RETAINIQ_MODEL_TOKEN` only into that child process; it does not create a token-bearing shell command.
3. Run Member 2's one-account, one-cutoff pilot. It selects one authorized tenant-01 account internally, calls the same four APIs, and emits only counts and window totals:

   ```powershell
   & $python -m retaniq.secret_store run --file $secret -- $python -m examples.member2_p0_bounded_pilot --db $db --as-of 2026-10-01T00:00:00Z
   ```

4. The pilot checks tenant derivation, the three source/category grants, occurrence and availability cutoffs, serialization, valuation omission, and tenant-02 denial.
5. Do not write features, labels, predictions, or model artifacts in this handoff. Stop after this one-account/one-cutoff read. Do not run `examples/member2_synthetic_smoke.py` for this bounded task; it scans many accounts and historical cutoffs.

The bounded pilot was run with the protected token and passed: one eligible account, 22 usage events, one subscription event, 27 daily-aggregate sessions, and 48 coverage intervals (42 complete, 3 censored, 3 not-created). The output contained no account identifier or event payload and confirmed no writes.

## Negative authorization and integrity evidence

The focused P0 suite covers: authenticated narrow grant; missing and invalid token; other tenant; tampered source scope; unauthorized source filtering; unauthorized category filtering; no `model_artifact_write`; no `identity_mapping`; admin-route denial; billing valuation redaction; one-ID rotation with old-token invalidation; revoke; failed secret delivery rollback; digest-only storage; and diagnostics without token material. The real STANDARD smoke covers actual positive reads, tenant derivation, cutoff boundaries, source/category scope, serialization, no valuation, cross-tenant denial, and no SQLite writes during reads.

The original source file and manifest were SHA-256 checked before provisioning and rechecked after the read smoke: both still match the values above. The DB copy was checked with `PRAGMA integrity_check`, retained the original dataset identity and import counts, and had inherited credentials invalidated before the new reader was provisioned. The complete P0 worktree suite passed 183 tests with 41 PostgreSQL-guarded skips; no PostgreSQL test target was configured for the run.

## Source health and cancellation policy limits

This is synthetic historical data. Integration category grants and observation-coverage intervals are present, but they do not establish a live source connection or a measured freshness SLA. Source health is separate evidence; freshness remains unknown without a source-specific policy, and the repository does not provide an independent lifecycle/billing heartbeat. Missing, partial, delayed, outage, censored, and entitlement-ended coverage must remain explicit.

The supported synthetic cancellation policy is loss of the last active paid entitlement. A cancellation request, payment failure, one subscription ending while another remains active, or an undated `customers.account_status` change is not sufficient evidence of account churn. A negative outcome requires complete subscription-outcome observation through the horizon plus maturity lag. Member 2 owns label materialization and must keep known cancellation out of predictive features. No labels are produced by this P0 handoff.

## Operator actions and limits

- The protected file is usable only under the Windows identity to which DPAPI sealed it. If Member 2 runs as another identity, re-provision or transfer via an approved secret store before the pilot.
- A pre-existing `standard-tenant-01-reader.dpapi` file remains in the private dataset directory. It was not used, decrypted, or mapped to an original database principal during P0; do not use it for this pilot.
- The original immutable DB still contains its pre-existing digest-only principal records; they were not altered. The working copy revokes those principals and invalidates its imported integration credentials. Do not use a token from another file or the original DB.
- No PostgreSQL cluster was used for P0. Its guarded tests are reported separately from the SQLite reader evidence.
- This handoff establishes synthetic STANDARD read access only. Source-health, real-data, model-training, predictive-performance, and cancellation-outcome validation remain outside this task.
