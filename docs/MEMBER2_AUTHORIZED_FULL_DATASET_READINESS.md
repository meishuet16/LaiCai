# Member 2 Authorized Dataset Readiness — Prompt 28

**Decision:** no authenticated readiness pilot ran. STANDARD artifacts are present and checksum-consistent with the prior verified import, but no usable reader token is in this process. The expected FULL dataset and database are absent. No data API reads, dataset generation/import, full preparation, or model training were performed.

## Explicit readiness statuses

| Gate | Status | Evidence |
|---|---|---|
| `STANDARD_AUTHENTICATED_PILOT` | **BLOCKED** | `RETAINIQ_MODEL_TOKEN` was absent; zero authenticated calls. |
| `FULL_ARTIFACT` | **ABSENT** | Neither the expected FULL dataset directory nor its SQLite path exists under the approved private data root. |
| `FULL_AUTHORIZATION` | **NOT_APPLICABLE** | No FULL artifact exists to bind to a principal; no matching credential was verified. |
| `FULL_PREPARATION_READINESS` | **BLOCKED** | FULL artifact, matching authorization, corrected pilot evidence, and Member 1 provisioning safeguards are missing. |

These are data-access/readiness statuses, not training or production approval.

## Checkpoint and scope

- Branch: `integration/member2-main-sqlite`
- Prompt 27 was reviewed and locally checkpointed as `ed7493f290cb0a9732a37318ea0b2bc32a9d430b` (`fix(member2): preserve unknown source state and audit full dataset feasibility`).
- Prompt 28 changes are documentation-only and remain uncommitted.
- The permitted data root was `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2`; no unrelated private folders were searched.
- All datasets described here are synthetic. None is real-world evidence.

## Artifact verification

### STANDARD

The exact source directory is:

`C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68`

The manifest identifies Synthetic SaaS v1.2.0, STANDARD, seed 2026, generator `synthetic-saas-v1.2` / build `r9`, interval `[2024-10-01, 2026-10-01)`, target policy `effective-account-churn-v1.2`, 3,000 accounts across four tenants, 239,721 canonical events, 491,223 coverage records, and 621 reported effective account-churn episodes. `no_real_customer_data` is true.

| Check | Result |
|---|---|
| Dataset ID | `synthetic-saas-v1-2-standard-s2026-970a9d231e68` — matched |
| `dataset_manifest.json` SHA-256 | `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d` — matched |
| Manifest-listed files | 20 of 20 present; all SHA-256 and listed sizes matched |
| Canonical SQLite file SHA-256 | `71bc6c18d9266c2b0c8b8e5008f6f6633a55804b1fe90a947f8ea24ca3ee5943` — matched the previously verified database checksum |
| Prior prepared v4 manifest | SHA-256 `1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a` — matched |
| Prior prepared v4 artifacts | 8 of 8 checksums matched |

The database was hashed as bytes only; no SQLite query or row access was used. Existing Member 2 handoff documentation records the earlier successful import, idempotency check, dataset-identity check, and tenant-denial smoke. Because this database's current checksum matches that recorded immutable file, its bytes have not changed. However, Prompt 28 did **not** reauthenticate or re-query the database identity, applied migration/checkpoint state, tenant inventory, or reader grants. The current source code defines schema version `1.0` and migrations `001`–`004`; that is not a fresh assertion about the database's applied migration table.

### FULL

The documented expected directory, `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\full\synthetic-saas-v1-2-full-s2026-33ac24d7f094`, and expected database, `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-full-s2026-33ac24d7f094.sqlite3`, are both absent. The approved root currently has only `db`, `prepared`, and `standard` directories. The expected ID is a prior documentation reference only: no FULL manifest, checksum, artifact hashes, database identity, import checkpoints, tenant inventory, or authorization could be verified. FULL was not regenerated or imported.

## Reader authentication and least privilege

- The Member 2 local smoke reads `RETAINIQ_MODEL_TOKEN`. It authenticates through `authenticate_service_principal`; tenant identity is taken from the authenticated principal and checked on every scoped read. The adapter separately compares the database's immutable dataset identity to the selected source manifest. A STANDARD token is not evidence of FULL authorization.
- The service principal is scoped to tenant, source IDs, purpose, and role. Event categories are granted on the backing source integrations, not as a separate service-principal field; verify the three source-to-category mappings are exactly usage, billing, and subscription. For tenant-01 the v1.2 source IDs are `tenant-01-synthetic-usage-v1-2`, `tenant-01-synthetic-billing-v1-2`, and `tenant-01-synthetic-subscription-v1-2`.
- Minimum read-only scope: role `analyst`, tenant `tenant-01`, exactly those three verified source IDs, and purpose `retention_inference` only. Do not grant `admin`, `operator`, `billing_valuation`, `operational_contact`, `identity_mapping`, `integration_health`, or `model_artifact_write` for this pilot.
- `python -m retaniq create-service-principal` supports those exact read-only grants. It does **not** itself check dataset identity or import completion, so the trusted operator must first verify the correct database through the established importer/admin workflow. The CLI prints the bearer token once to stdout; never paste/capture that output in chat, Git, a log, or a screenshot.
- `python -m retaniq.synthetic provision-reader` checks import checkpoints, creates an analyst principal with `model_artifact_write`, and only then checks the manifest identity. If that last check fails, the principal row remains even though the token is not returned. Do not use this convenience command for a least-privilege read-only pilot. The synthetic importer itself also creates per-tenant analyst principals with `retention_inference`, `billing_valuation`, and `model_artifact_write`; their generated bearer strings are not returned, but the principals are persisted. Repeated import attempts can create additional principals.
- No supported service-principal rotation/revocation function or CLI was found. Creating a replacement principal does not revoke the old one. Do not manipulate private SQLite tables directly; Member 1 must provide a supported lifecycle/revocation procedure before credentials are provisioned at scale.
- The `RETAINIQ_MODEL_TOKEN` check returned **ABSENT**. No credential was requested, created, or displayed. To restore access, an authorized local database operator should provision the exact principal only after verifying the dataset-bound database, then inject the secret into the Codex process using the approved local secret manager/process launcher. Do not use `setx`, shell history, `.env`, repository files, chat, or screenshots. If no secure injection path or revocation procedure is available, stop and request one.
- The existing `examples.member2_synthetic_smoke` requires `model_artifact_write`; it is not suitable as a least-privilege authentication test. A dedicated bounded read-only pilot/acceptance runner is still needed. Current fixture tests prove authorization logic only; they do not prove live principal grants.

## Pilot results and corrected source-state behavior

No STANDARD or FULL authenticated pilot ran. **Authenticated API calls: 0.** Pilot runtime, API-category breakdown, calls per candidate/eligible snapshot, peak memory, live eligibility counts, label counts, coverage states, actual outages, corrected reason counts, reliability/abstention distribution, and source-health findings are **not measured**. No customer IDs or event payloads were read or emitted.

For a later bounded pilot, choose at most 30 tenant-01 candidate accounts by ascending SHA-256 of `dataset_id|tenant_id|customer_id` from the authenticated tenant-scoped candidate list; do not consult churn labels or outcomes for selection, and never print the IDs. Select at most three TRAIN/VALIDATION cutoffs by a fixed index rule from the dataset's frozen split manifest. Stop at 90 account/cutoff pairs. Keep TEST cutoffs/outcomes out of selection and development. Record aggregate candidate/eligible/reason counts, labels, freshness/reliability, and per-endpoint call counts only. The current repository has no runner implementing this full bounded protocol, so a future implementation must add tests before execution.

Prompt 27 changed missing operational connection evidence from inferred `connected=False` to `connected=None` / unknown; explicit disconnected evidence remains stale/blocking, while coverage is assessed independently. Prompt 28's focused tests include the corresponding freshness, reliability, and adapter tests, but no live data was available to count how many STANDARD cases changed from false disconnection to unknown. The prior v4 counts—0 sufficient, 654 limited, 22,761 insufficient, and 9,355 `SOURCE_NOT_CONNECTED` occurrences—are **PRE-CORRECTION ONLY** and must not be used as current results. Removing a false reason code alone does not upgrade scoring eligibility.

For historical cost context only, the prior STANDARD tenant-01 preparation recorded 54,750 candidate account/cutoff pairs, 23,415 eligible snapshots, 234,495 authenticated calls, and 950.910 seconds. Its recorded reads were 54,750 account snapshots, 54,750 subscription reads, 78,165 event reads, and 46,830 coverage reads. These are prior full-preparation measurements, not Prompt 28 pilot measurements. No local cache or unauthenticated reader was added; a tenant-derived bounded batch API remains a Member 1 efficiency request.

## FULL provisioning plan (not executed)

This is a reviewed procedure, **not approval to run it**. Obtain separate authorization and resolve the principal over-grant/revocation issue first.

1. Keep all outputs outside Git. Verify that the FULL destination and its staging path do not already exist; if either exists, stop and inspect rather than overwrite/delete. Use a new private output root if there is any ambiguity. The v1.2 generator refuses an existing destination or staging directory and does not overwrite an existing destination.
2. The verified CLI is `python -m retaniq.synthetic generate`. For the documented config, an operator-approved invocation is:

   ```powershell
   .\.venv\Scripts\python.exe -B -m retaniq.synthetic generate --profile full --seed 2026 --accounts 20000 --tenants 4 --start-date 2024-10-01 --end-date 2026-10-01 --output C:\Users\User\RetainIQ-private\synthetic_saas_v1_2
   ```

   The end date is exclusive. Generator defaults not overridden above (including event/outage/billing settings, generator version/build, and target policy) must be recorded from the generated manifest. The returned `dataset_id` and path, not a guessed filename, become the candidate identity. Compare against the previously documented expected ID; any mismatch is a stop-and-investigate condition, not a reason to relabel.
3. Run `python -m retaniq.synthetic validate --dataset <returned-dataset-path>`. The validator checks synthetic provenance, manifest identity, all listed file hashes, and aggregate counts. Independently record SHA-256 for the manifest and its listed files; preserve the generated source immutably. Do not change manifest fields to fix validation.
4. Only after the importer principal side effects have an approved mitigation, import to a **new, FULL-specific** private DB path, never the immutable STANDARD DB:

   ```powershell
   .\.venv\Scripts\python.exe -B -m retaniq.synthetic import --dataset <returned-dataset-path> --db C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\<verified-dataset-id>.sqlite3 --verify-idempotency
   ```

   Accept only `VERIFIED` output with matching dataset ID, event/coverage counts, completed checkpoints, cross-tenant denial, and zero replay inserts/all replay rows counted duplicate. This command initializes/applies migrations and writes canonical records; it is not a dry run or one all-or-nothing transaction.
5. Import writes event/coverage batches with transactional checkpoints, and the same dataset identity is required on a subsequent call. However, a retry re-enters principal provisioning and creates additional per-tenant service-principal rows; there is no global rollback or supported principal cleanup. Therefore **do not automatically resume a failed/partial import** until Member 1 fixes or explicitly approves that side effect and provides revocation. Preserve the partial DB and logs, do not delete it, and resume only against the exact same manifest and DB after review. A dataset identity mismatch fails closed. `--verify-idempotency` is a write/replay check and is for a new, isolated FULL DB only.
6. After a verified import, use the least-privilege `create-service-principal` CLI with tenant-01, the exact three source IDs and `retention_inference` only; do not use `provision-reader`. The actual CLI is:

   ```powershell
   .\.venv\Scripts\python.exe -B -m retaniq create-service-principal --db <verified-full-db-path> --tenant-id tenant-01 --role analyst --source tenant-01-synthetic-usage-v1-2 --source tenant-01-synthetic-billing-v1-2 --source tenant-01-synthetic-subscription-v1-2 --purpose retention_inference
   ```

   First confirm those source IDs/categories against the validated dataset; this CLI prints the one-time bearer value to stdout, so use only a trusted terminal with a secure local handoff and never copy the output into a task, shell transcript, file, or screenshot. Securely inject the value as `RETAINIQ_MODEL_TOKEN` into the Codex process. Before any customer reads, the first API call must be `get_dataset_identity` and its result must match the manifest. Verify exact principal grants and backing category grants, then test allowed event/subscription/coverage/snapshot reads plus cross-tenant/category denials with aggregate-only output. The current example smoke's extra write-purpose requirement and lack of a 30×3 cap make it unsuitable; a dedicated bounded read-only runner must replace it before this pilot can run.

   A test-only metadata check can call `authenticate_service_principal(db, os.environ.get("RETAINIQ_MODEL_TOKEN"))` followed by `get_dataset_identity(db, principal)`, assert tenant `tenant-01`, role `analyst`, exact sources, and only `retention_inference`, then print only those grants and `dataset_id`. It must not print the token. These are authenticated library APIs, not direct SQLite queries. Do not proceed to account/event reads unless the returned dataset identity exactly matches the validated manifest.

### Resource estimates (not measurements)

| Item | Estimate and basis |
|---|---|
| FULL source files | ~1.01 GiB; STANDARD manifest-listed 162,643,747 bytes scaled by 20,000 / 3,000 |
| FULL canonical SQLite | ~3.42 GiB; STANDARD 550,723,584-byte DB scaled by the same account ratio |
| FULL tenant-01 prepared artifacts | ~0.65 GiB; prior eight v4 artifacts (104,510,654 bytes) scaled linearly |
| Combined steady-state artifacts | ~5.08 GiB; no temporary/WAL overhead included |
| Suggested free-space reserve | At least ~10.2 GiB (about 2× the linear estimate); conservative planning allowance, not a measured requirement |
| Tenant-01 preparation runtime/calls | ~6,340 seconds (~1.76 h) and ~1.56 million calls, linearly scaled from prior STANDARD preparation; high uncertainty, not a benchmark |

The prior handoff's 478.985-second FULL import is historical documentation only, not a current measurement. No FULL generation/import/runtime is claimed. Current C: free space was not used as authorization and does not change the missing artifact/security gates.

## Readiness, blockers, and next handoff

- Prior STANDARD v4 per-stage/per-horizon support gates (50 positive, 50 negative, 20 unique positive accounts, 20 unique negative accounts) were documented as blocked. Prompt 28 did not recalculate them. FULL support cannot be inferred from 621 synthetic generator-wide churn episodes or linear scaling.
- All three horizons remain **BLOCKED for training readiness** pending current mature-label support, stage-level unique-account support, corrected feature/reliability assessment, and authorized pilot evidence. No calibration or TEST inspection occurred; the frozen split and TEST policy were not changed.
- Operational scoring readiness is also **BLOCKED** until source health/completeness is independently evidenced; no reason-code cleanup can replace that evidence.
- Member 1 handoff: provide a supported service-principal revocation/rotation workflow; stop importer from creating unnecessary broad/dormant principals or make it safe/idempotent; preserve explicit source/category grants; verify dataset identity, schema/checkpoints and tenant scope via authorized metadata; add historical source-health/completeness evidence and bounded tenant-derived reads.
- Recommended next milestone: first establish that least-privilege credential lifecycle and safe import retry are supported; implement/use a read-only pilot runner capped at 30 accounts × 3 development cutoffs, then run the STANDARD pilot after secure token injection. Only review FULL generation/import after those results and explicit resource approval. Do not train from the pilot.

## Verification performed for this report

- Focused existing suite: **181 passed** in 11.06s across dataset readiness, SQLite adapter/auth, freshness/reliability, labels, historical preparation, temporal splits, Data Foundation, and cross-member contract tests.
- Full regression: **454 passed, 0 failed, 0 errors, 0 skipped** in 19.43s; 24 existing SHAP warnings were left unsuppressed (9 explainability, 15 prediction pipeline).
- Manifest/artifact checks: STANDARD source 20/20 hashes and sizes; prepared v4 8/8 hashes; SQLite SHA-256 matched. Hashing only; no source rows were read.
- Generator/importer/provision-reader CLI help and source were inspected. No generation, import, credential provisioning, authenticated data read, model fitting, or private database query was run.
