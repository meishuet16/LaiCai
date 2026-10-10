# Member 2 — FULL Synthetic Feasibility and Read Efficiency (Prompt 27)

## Decision summary

- **FULL tenant-01 preparation: BLOCKED.** The handoff documentation describes a FULL dataset, but its documented immutable dataset directory and database are absent from the inspected private data root. No FULL manifest could be verified and no FULL records were read.
- **Bounded STANDARD reader pilot: BLOCKED.** `RETAINIQ_MODEL_TOKEN` was not present in the process environment. No credential was requested, exposed, or created, and no account-level STANDARD API calls were made in this prompt.
- **Member 2 source-state correction: implemented and focused-tested.** Event/coverage silence is no longer translated into explicit disconnection. Missing operational health remains unknown; explicit disconnect remains stale/blocking.
- **No training, calibration, TEST access, split changes, dataset generation/import, or full preparation occurred.**

## Confirmed profile and available artifacts

Source inspection of `configs/synthetic_saas.json`, `retaniq/synthetic/config.py`, and `tests/test_synthetic_generator.py` confirms the FULL profile is 20,000 synthetic accounts across four tenants, seed default 2026, using the same exclusive 24-month configuration as the other profiles: `[2024-10-01, 2026-10-01)`. The target policy is `effective-account-churn-v1.2`. The profile code creates deterministic tenant/account-specific streams; profile populations are independent, not a continuation of STANDARD.

The Member 1 handoff says the expected FULL ID is `synthetic-saas-v1-2-full-s2026-33ac24d7f094`, and records 20,000 accounts, four tenants, 1,547,420 events, 3,263,358 coverage rows, and a 478.985-second import. Those are **previously documented handoff measurements**, not independently verified in this task. The expected FULL dataset directory and corresponding database are absent. A bounded directory inventory of the private v1.2 root found the STANDARD source and its prepared output, but no FULL profile directory. Therefore no FULL manifest hash, source DB hash, or tenant-01 credential/grants are confirmed here. The handoff's prior FULL authorization does not prove current access.

STANDARD remains the only locally present dataset checked for this task:

- Dataset ID: `synthetic-saas-v1-2-standard-s2026-970a9d231e68`.
- Source manifest SHA-256: `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- Existing tenant-01 preparation: `member2-prep-v4`, 23,415 eligible snapshots / 700 unique accounts, 70,245 horizon labels.
- Frozen partition boundaries and artifacts were not modified. The prior frozen test window remains June–August 2026.
- Historical readiness remains synthetic-only; all horizons remain blocked by the frozen per-stage sample/account gates. Operational scoring remains blocked: no model/calibrator is trained, and source-health/completeness evidence is unresolved.

## Source-state reliability correction

Before the correction, `SQLiteDataAdapter.freshness_evidence_from` assigned `connected=False` when it found no account lifecycle/billing events or usage coverage. `_source_assessment` interpreted every false value as verified disconnection and emitted `SOURCE_NOT_CONNECTED` with `STALE` status. Event silence is not source-level health evidence.

The internal field is now tri-state. The SQLite adapter emits `connected=None` because Member 1 supplies no historical operational health fact to this adapter; neither account events nor coverage records are treated as a connectivity heartbeat. Freshness returns `UNKNOWN` when availability/watermark evidence is absent. It does not infer healthy or disconnected from silence. Explicit `connected=False` continues to return `STALE` with `SOURCE_NOT_CONNECTED`. A complete, tenant/account-scoped coverage interval with an as-of watermark can still establish freshness of that coverage evidence while the separate connection field remains unknown. Missing activity remains distinct from complete zero-activity coverage. Reliability rules and thresholds are unchanged; unknown essential freshness remains conservative and does not become sufficient evidence.

The v4 manifest's 9,355 `SOURCE_NOT_CONNECTED` reason occurrences are now understood as **misattributed by the prior adapter**, not measured outages. The persisted v4 aggregate reliability/freshness statuses have **not** been recomputed under the correction. Do not present those totals as post-fix findings. The Member 1 health API currently exposes current operational telemetry and `freshness_status=unknown`; it does not supply historical as-of health/coverage watermarks. Current health must not be projected backward.

## Bounded pilot and source quality

The planned small STANDARD pilot would read at most four tenant-01 accounts at three TRAIN-period cutoffs using `SQLiteDataAdapter`, then build features and assess reliability/freshness without reading labels or TEST outcomes. It stopped before any data API call because the existing tenant-scoped `RETAINIQ_MODEL_TOKEN` was absent. This is **BLOCKED**, not a zero-result or failed customer sample. No full/sample reliability distribution is claimed for the corrected logic.

Previous authorized STANDARD preparation evidence remains the only aggregate baseline: 23,415 snapshots, reliability sufficient 0 / limited 654 / insufficient 22,761; freshness fresh 0 / partially stale 654 / stale 22,761 / unknown 0; abstention-eligible 22,761 (97.21%). These figures reflect the **pre-correction preparation**, with incomplete usage coverage on every snapshot and the source-state attribution defect described above. They are not corrected aggregate counts. The training support gate remains at least 50 positive and 50 negative rows and 20 distinct positive and negative accounts per stage/horizon. No FULL tenant-specific sample support or calibration feasibility can be inferred from documented all-tenant totals.

## Read efficiency and scale estimate

The prior STANDARD preparation measured 950.910 seconds for 54,750 candidate account/cutoff pairs and 23,415 eligible snapshots. It made 234,495 authenticated reader calls:

| Read | Calls | Approx. calls per candidate pair |
|---|---:|---:|
| Account snapshot | 54,750 | 1.000 |
| Subscription fold | 54,750 | 1.000 |
| Event read | 78,165 | 1.427 |
| Coverage read | 46,830 | 0.855 |
| **Total** | **234,495** | **4.283** |

Measured phases were point-in-time snapshot reads 572.882 seconds (60.25% of run) and outcome reads 120.845 seconds (12.71%). Feature building was 79.857 seconds. The new bounded pilot could not measure a per-account/current-run delta. No optimization is claimed as implemented or benchmarked. The largest actionable cost is repeated authenticated data access. Do not add a Member 2 cache or direct SQL reader; ask Member 1 for a tenant-derived, bounded batch read that retains per-record authorization, occurrence and availability filters, and response limits. Cache reuse is only safe for immutable metadata or identical source identity and cutoff/evaluation context, with no cross-tenant keys.

For capacity planning only, 20,000 / 3,000 = 6.67× the STANDARD population. If work and storage scaled linearly and scope/weekly-cutoff count remained comparable, the prior 950.910-second tenant-01 preparation suggests roughly **6,340 seconds (~1.76 hours)** and the 234,495-call pattern suggests roughly **1.56 million calls** for a five-thousand-account tenant. The eight verified compressed v4 artifacts total 104,510,654 bytes (99.67 MiB); linear scaling suggests about **664.46 MiB** for the corresponding FULL tenant preparation. The present 550,723,584-byte (525.21 MiB) all-tenant STANDARD SQLite file linearly scales to about **3.42 GiB** for FULL. These are **estimates, not FULL benchmarks**; uneven eligibility/event density, storage, SQLite/query behavior, coverage, and API batching could change them. Existing handoff documentation's 478.985-second FULL import is historical evidence only. Do not start generation, import, or preparation in this prompt.

## Preserved safeguards and next controlled experiment

- Do not pool tenants or infer tenant-01 support from all-tenant counts.
- Do not alter the synthetic seed, target policy, label maturity, reliability policy, split boundaries, calibration requirements, or TEST use.
- Keep account features point-in-time and outcome labels separately observed after maturity; unknown coverage is never recoded as retention.
- Synthetic class sufficiency is separate from label maturity, feature correctness, calibration feasibility, operational scoring reliability, and real-world validation.
- The existing split design remains chronological with TRAIN, VALIDATION, CALIBRATION, and untouched TEST. No outcome-based tuning was performed.
- To proceed later, the owner must locate/authorize the immutable FULL artifact and obtain an exact tenant-01 read principal with only that tenant's approved source grants. Verify dataset ID + manifest against its imported database before any reads. Then run a bounded tenant-01 readiness pilot, report horizon/stage support and corrected reliability, and stop if gates fail. A separate full preparation requires explicit approval and a new versioned prep manifest; keep the STANDARD artifact immutable.

Required Member 1 decisions/interfaces remain: historical operational source health with true as-of availability and observed-through semantics; account-scoped lifecycle/billing completeness and coverage; authorized aggregate late-arrival diagnostics; bounded batch reads; and a shared known-cancellation/multi-subscription policy. Proposed APIs in `MEMBER2_TO_MEMBER1_CONTRACT_REQUESTS.md` are requests, not implemented endpoints.
