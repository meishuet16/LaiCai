# Member 2 — Authenticated STANDARD Historical Pilot Results

**Result:** the bounded authenticated read pilot completed for tenant-01 only. It validates a narrow synthetic data path and the corrected handling of unknown source connectivity. It does not establish real-world readiness, training readiness, model performance, or operational scoring readiness.

## Provenance and authorized boundary

- Evidence type: `SYNTHETIC_ONLY`.
- Dataset: `synthetic-saas-v1-2-standard-s2026-970a9d231e68` (Synthetic SaaS v1.2, seed 2026).
- Dataset manifest SHA-256: `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- P0 reader worktree: `codex/member1-p0-reader-handoff`, HEAD `c312eb80a75c6686e16049f1e04ebe31713e403f`; clean when checked. Member 1's separate RLS worktree was not modified.
- Member 2 Prompt 28 checkpoint: `853f11b60afc9d73b0e85bda61d665305de7c716` (`docs(member2): audit authorized synthetic dataset readiness`).
- Working-copy database identity: tenant-01 reader copy, SHA-256 `68404ded8052dc3199dbe0051819f445247b65b3d16adca5af68406d54443114`.
- Immutable source DB SHA-256: `71bc6c18d9266c2b0c8b8e5008f6f6633a55804b1fe90a947f8ea24ca3ee5943`.
- Reader grant: tenant `tenant-01`, role `analyst`, purpose `retention_inference` only, and exactly the three metadata-verified usage, billing, and subscription sources. `billing_valuation` and `model_artifact_write` were not authorized. No token was printed or checked into Git; the DPAPI-protected file was used under its matching Windows identity through Member 1's wrapper and was removed from the child environment after authentication.
- The dataset manifest identity and all three source/category mappings matched. The authenticated API denied the cross-tenant account probe (`not_found`). No direct SQL data reads, schema changes, provisioning, or writes were performed by the pilot.

The immutable source DB hash, working-copy DB hash, and manifest hash matched the approved values after the pilot. All 20 manifest-listed artifact hashes matched. Read-only `PRAGMA integrity_check` returned `ok` for both SQLite files. The exact working-copy checksum was unchanged, which also rules out pilot writes to its records, principals, or grants.

## Deterministic sample and cutoff policy

The cohort was selected without consulting labels: ascending SHA-256 of `dataset_id|tenant_id|customer_id` over the dataset's identity inventory, then the first 30 tenant-01 identities. The existing frozen split schedule supplied three weekly UTC development cutoffs: first TRAIN (`2024-12-09T12:00:00Z`, freeze `2025-10-01T00:00:00Z`), last TRAIN (`2025-08-18T12:00:00Z`, same freeze), and last VALIDATION (`2026-01-19T12:00:00Z`, freeze `2026-03-01T00:00:00Z`). The existing label maturity lag is eight days. No TEST cutoff or TEST outcome was queried. Stage label-freeze dates and the `effective-account-churn-v1.2` policy were read from the existing split and dataset manifests; neither was changed.

Two successful bounded executions used the same deterministic 90 account/cutoff pairs (180 pair visits total). The first execution exposed an aggregation/mapping issue in the Member 1/Member 2 eligibility comparison; the second execution corrected that reporting and is authoritative for the tables below. This was not a full historical preparation or a new dataset import/generation.

After those runs, a separate one-account/one-cutoff authenticated contract smoke exercised the response-redaction guard added to the pilot runner. It called each of the four historical APIs once and confirmed the live responses contained no unauthorized valuation fields. This additional 4-call smoke is not included in the 90-pair pilot metrics.

## Eligibility and label outcomes

There were 30 unique accounts and 90 candidate snapshots, with 60 repeated-account snapshot rows. Eligibility over the candidate pairs:

| State | Pairs |
|---|---:|
| Eligible | 28 |
| Known cancellation | 0 |
| Not eligible (confirmed terminated) | 2 |
| Insufficient data | 60 |

There were 20 unique eligible accounts and 8 repeated eligible snapshots. The same label status counts resulted at each horizon under the synthetic effective-account-churn-v1.2 policy:

| Horizon | Candidate snapshots | Eligible labels | Positive | Negative | Unknown | Excluded | Unsupported | Usable (P+N) | Positive prevalence among usable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 days | 90 | 28 | 1 | 27 | 0 | 2 | 60 | 28 | 1/28 (3.57%) |
| 14 days | 90 | 28 | 1 | 27 | 0 | 2 | 60 | 28 | 1/28 (3.57%) |
| 30 days | 90 | 28 | 1 | 27 | 0 | 2 | 60 | 28 | 1/28 (3.57%) |

The percentages describe this tiny synthetic sample only. They are not model results or population estimates. The one observed qualifying account churn was available by label evaluation; 27 negatives had full observed, churn-free horizons. Two snapshots were already terminated and excluded; 60 lacked enough lifecycle evidence for a defensible prospective label. No payment failure was promoted to churn. No sampled known-cancellation case occurred, so the outstanding known-cancellation policy disagreement was not empirically exercised.

Stage counts were identical for all three horizons:

| Stage | Candidate pairs | Positive | Negative | Unknown | Excluded | Unsupported | Unique positive / negative accounts |
|---|---:|---:|---:|---:|---:|---:|---|
| TRAIN (two selected cutoffs) | 60 | 0 | 10 | 0 | 0 | 50 | 0 / 9 |
| VALIDATION (one selected cutoff) | 30 | 1 | 17 | 0 | 2 | 10 | 1 / 17 |

TRAIN has no positive examples in this sample; neither TRAIN nor VALIDATION comes close to the frozen minimum-support gates. Calibration and TEST were not sampled. The 621 dataset-wide reported churn episodes are not equivalent to horizon-specific mature positive labels.

## Point-in-time, source-state, freshness, and reliability

Feature facts were checked for both occurrence and source availability/receipt by the prediction cutoff. The existing adapter's source-availability-then-received-at rule was used; late or availability-unknown events were excluded, and current projections were not used to reconstruct historical state. Outcome evidence was read only at each frozen development label freeze, separate from feature snapshots. There were zero labels whose outcome evidence was unavailable by the computed evaluation cutoff. The historical API filters excluded rows before returning, so their raw counts are not observable from this authorized boundary.

| Classification | Candidate pairs / eligible denominator | Count |
|---|---:|---:|
| Connection unknown | 90 | 90 |
| Explicitly disconnected | 90 | 0 |
| `SOURCE_NOT_CONNECTED` reason occurrence | overlapping reason counter | 0 |
| Fresh | 90 | 0 |
| Partially stale | 90 | 3 |
| Stale | 90 | 27 |
| Freshness unknown | 90 | 60 |
| Reliability sufficient | 28 eligible | 0 |
| Reliability limited | 28 eligible | 3 |
| Reliability insufficient | 28 eligible | 25 |
| Reliability-based abstention required | 28 eligible | 25 (89.29%) |

Freshness reason occurrences overlap and are not mutually exclusive: `SOURCE_COVERAGE_INCOMPLETE` 30, `SOURCE_METADATA_MISSING` 73, `SOURCE_PARTIALLY_STALE` 30, `SOURCE_STALE` 27, and `SOURCE_NOT_CONNECTED` 0. Usage coverage interval results were complete 627, delayed 1, entitlement-ended 22, not-created 30, and outage 29. Subscription-outcome coverage intervals were complete 725, not-created 28, and outage 50. For the 28 eligible snapshots, usage coverage was partial in all 28; personal baseline was available in 22, insufficient-history in 4, and unavailable in 2 (6 cold-start/baseline-limited cases).

The corrected behavior is verified for this sample: missing events, missing independent heartbeat, and missing coverage do not become evidence of disconnection. No explicit disconnected evidence was exposed by these APIs, so the pilot cannot certify live source health or distinguish all historical staleness from genuinely stale upstream evidence. Incomplete coverage and missing source metadata are observed causes of degraded/unknown assessments; there is no sample evidence of a cutoff or replay-timestamp defect. Do not interpret `SOURCE_STALE` here as a production integration outage.

## Cross-member compatibility finding

The API scoping, JSON response shape, timestamp handling, source/category checks, point-in-time adapter mapping, and valuation redaction are compatible for the exercised paths. Member 1's account snapshot returned `not_eligible` for 60 sampled pairs where the Member 2 lifecycle evaluator returned `INSUFFICIENT_DATA`; the other 28 mapped to eligible and 2 to not-eligible. Member 2 intentionally treats absent dated lifecycle evidence as insufficient rather than asserting historical ineligibility. This is a genuine semantic mismatch requiring agreement before broader integration. No known cancellation appeared in this cohort, so the known-cancellation routing difference remains unresolved.

The pilot reader did not have financial valuation authorization. A supplemental live one-account API check exercised the new assertion against account snapshot, subscription, event, and coverage responses; account valuation was null/omitted and no subscription or billing/subscription event valuation fields were present. The reader also has no model-artifact write permission.

The current process identity matched the DPAPI owner and the protected credential successfully authenticated through the supported wrapper. No second Windows identity was impersonated for a negative DPAPI decrypt test; no raw token was displayed or copied.

## API calls and elapsed time

Final corrected execution counts at the high-level reader boundary:

| API | Calls |
|---|---:|
| Account snapshot | 91 (90 sampled pairs + 1 cross-tenant denial probe) |
| Dataset identity | 1 |
| Events | 118 |
| Observation coverage | 118 |
| Subscriptions | 90 |
| Candidate-associated data reads | 416 |
| Cross-tenant denial read | 1 |
| All high-level data reads including denial | 417 |

The 28 eligible cases accounted for 168 candidate-associated reads (6 per eligible pair); the mean was 4.62 candidate-associated reads per candidate pair. Nested SQL statements inside Member 1's API functions were not separately counted.

Measured final-run time: 12.427911 seconds in the pilot runner, excluding outer authentication and adapter construction; 15.710157 seconds end-to-end; authentication itself 0.002327 seconds. Throughput was 7.241764 candidate pairs/second for this run. Peak memory was not measured. These 30×3 timings do not establish FULL-scale performance. The earlier full STANDARD preparation's 234,495 calls over 950.910 seconds is a historical comparison only; do not linearly project pilot throughput. The API does repeat equivalent reads between feature and outcome stages; a tenant-derived, bounded/batched historical read interface may reduce overhead, but must preserve per-account authorization and auditability.

## Verification and limitations

Executed in the repository-local environment:

- Focused pilot tests: `9 passed`.
- Cross-member/readiness/adapter/freshness/reliability/label/outcome/preparation/split/Data Foundation tests: `221 passed`.
- Full Member 2 suite: `463 passed`, `0 failed`, `0 errors`, `0 skipped`; 24 known SHAP warnings remain unsuppressed.
- Member 1 P0 reader/handoff/Data Foundation tests: `59 passed`.
- Nine package import checks and AST parsing of 67 source/test/example Python files: passed.
- `git diff --check`: passed after final documentation edits.
- STANDARD manifest artifacts: `20/20` hashes verified; source and working DB SHA-256 values unchanged; both read-only SQLite integrity checks returned `ok`.
- Member 2 token environment variable absent after pilot; no DPAPI file/token tracked. The P0 branch remained at the verified clean checkpoint.

The first attempt to invoke P0 tests used a `.venv` path relative to Member 1's worktree, where that interpreter does not exist; no tests ran in that invocation. The same tests then passed using Member 2's absolute repository-local interpreter. No credential was exposed. Real-world source health, a larger authorized cohort, model training, and performance are not tested here.

Some pre-pilot wording in `DATASET_CARD.md` and the Prompt 28 readiness note says authenticated reads/verified outcomes were unavailable. Those statements describe the earlier checkpoint and are superseded only for this tenant-01 bounded pilot; the shared card was not rewritten as part of this task.

## Readiness decision

| Gate | Status | Reason |
|---|---|---|
| `AUTHENTICATED_STANDARD_ACCESS` | **VERIFIED** | P0 DPAPI wrapper, narrow tenant-01 reader, authenticated Member 1 API calls, manifest binding, and cross-tenant denial passed. |
| `CROSS_MEMBER_ADAPTER_COMPATIBILITY` | **PARTIAL** | Exercised read interfaces work, but the 60-case `NOT_ELIGIBLE` vs `INSUFFICIENT_DATA` mismatch remains unresolved. |
| `SOURCE_STATE_PILOT` | **VERIFIED** | In this bounded cohort, silent/unknown health was not labeled disconnected; explicit disconnect was not exposed. |
| `DATA_INTEGRITY` | **VERIFIED** | Artifact/database checksums and both read-only database integrity checks passed before/after. |
| `OFFLINE_TRAINING_READINESS` | **BLOCKED** | Synthetic-only data; 28 usable labels per horizon, one positive account, no TRAIN positives, and frozen support gates unmet. |
| `OPERATIONAL_SCORING_READINESS` | **BLOCKED** | No trained/approved model, 25/28 eligible cases require reliability abstention, and source health is unknown. |

**Next task recommendation:** first agree with Member 1 on the historical account-eligibility semantics and request an API-backed lifecycle/source-health evidence contract. Only then, with separate authorization, run a larger bounded STANDARD development-only sample to assess support and call efficiency. Do not train or inspect TEST outcomes as part of that follow-up.
