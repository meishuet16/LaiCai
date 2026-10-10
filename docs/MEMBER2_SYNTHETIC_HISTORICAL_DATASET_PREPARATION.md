# Member 2 — Synthetic Historical Dataset Preparation

## Scope and provenance

This preparation used the already-existing immutable STANDARD v1.2 dataset
(synthetic-saas-v1-2-standard-s2026-970a9d231e68, seed 2026, generator
synthetic-saas-v1.2 build r9). Its source manifest SHA-256 is
7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d.
All evidence is **SYNTHETIC_ONLY**. No model was trained or evaluated.

Only tenant-01 was read, through Member 1's authenticated, tenant-scoped
reader API. The other three tenants were not accessed. The dataset and SQLite
database remain outside Git. The before/after SQLite SHA-256 matched
(71bc6c18d9266c2b0c8b8e5008f6f6633a55804b1fe90a947f8ea24ca3ee5943),
and the adapter's identity check matched the dataset manifest.

## Historical snapshots and features

Cutoffs are deterministic weekly Mondays at 12:00 UTC, with a 63-day history
warmup. Source stage windows are half-open. The Member 2 package reconstructs
eligibility and features from dated events and availability known at each
cutoff; it does not use current subscription projections as historical state.
Known cancellations are excluded, inactive accounts are retained in the
historical population assessment, and payment failures are evidence rather
than churn labels. Usage quantity sums daily session counts; active days are
distinct observed dates. Coverage gaps remain missing/partial rather than
being imputed as zero. The personal baseline window is non-overlapping with
the recent usage window.

| Population measure | Count |
|---|---:|
| Candidate account-cutoff pairs | 54,750 |
| With subscription lifecycle evidence | 26,267 |
| Without lifecycle evidence | 28,483 |
| Eligible feature snapshots | 23,415 |
| Known-cancellation snapshots | 111 |
| Not-eligible snapshots | 2,733 |
| Insufficient eligibility evidence | 8 |
| Unique eligible accounts | 700 |
| Repeat snapshots after each account's first eligible snapshot | 22,715 |

Feature/source evidence references, missingness, reliability and freshness
are carried into the private records. Across eligible snapshots, personal
baseline status was available for 16,385, insufficient-history for 5,172,
unavailable for 1,167, and observed-zero-baseline for 691. Usage coverage was
partial for all 23,415 snapshots.

## Labels and observed coverage

The synthetic-only account churn policy is
effective-account-churn-v1.2: final paid-entitlement loss is account churn;
ending only one of multiple active subscriptions is not. Prediction features
are frozen at as_of; future lifecycle data is read separately for labels.
Label evaluation cutoffs are min(stage freeze, as_of + horizon + 8 days).
Positive labels require a qualifying effective termination available by that
evaluation cutoff. Negative labels require the entire horizon to have elapsed
and complete subscription outcome coverage through the horizon. Otherwise
the label remains unknown. No unknown is converted to zero.

The actual authorized read produced **zero mature positives and zero mature
negatives**. All 23,415 eligible snapshots are unknown at each horizon, with
missing_outcome_coverage; known-cancellation, not-eligible and insufficient
eligibility cases are separately excluded. This is a material reconciliation
blocker: the dataset's aggregate manifest reports 621 effective churn
episodes across four tenants, but the Member 2 authorized historical outcome
path surfaced no usable positive evidence and no complete outcome coverage
for this tenant. Do not infer labels from the episode count or missing events.
Member 1/Member 2 must reconcile the outcome event and coverage API contract
before training.

| Horizon | Eligible | Positive | Negative | Unknown | Class prevalence | Readiness |
|---:|---:|---:|---:|---:|---:|---|
| 7 days | 23,415 | 0 | 0 | 23,415 | N/A | **BLOCKED** |
| 14 days | 23,415 | 0 | 0 | 23,415 | N/A | **BLOCKED** |
| 30 days | 23,415 | 0 | 0 | 23,415 | N/A | **BLOCKED** |

This is not READY_FOR_SYNTHETIC_TRAINING, and is not real-world validation.
The dataset-declared minimums (50 positives, 50 negatives, 20 unique accounts
per class) are unmet for every horizon.

## Frozen chronological partitions

The splitter uses the existing chronological infrastructure. Prediction
snapshots are assigned by as_of; all horizons remain attached to their
snapshot. Labels are eligible for a stage only if confirmed and available by
that stage's freeze. TEST labels are evaluation-only and are never made
available to supervised fitting or model selection. No model-selection or
performance analysis was performed.

| Partition | Cutoffs | UTC cutoff dates (inclusive) | Label freeze (exclusive) | Snapshots | Unique accounts | Positive / negative / unknown per horizon |
|---|---:|---|---|---:|---:|---|
| TRAIN | 37 | 2024-12-09 – 2025-08-18 | 2025-10-01 | 7,157 | 324 | 0 / 0 / 7,157 |
| VALIDATION | 16 | 2025-10-06 – 2026-01-19 | 2026-03-01 | 5,859 | 435 | 0 / 0 / 5,859 |
| CALIBRATION | 8 | 2026-03-02 – 2026-04-20 | 2026-06-01 | 3,700 | 501 | 0 / 0 / 3,700 |
| TEST | 12 | 2026-06-01 – 2026-08-17 | 2026-10-01 | 6,699 | 617 | 0 / 0 / 6,699 |

Scheduled cutoffs are Monday 12:00Z. The boundary windows omit six weekly
cutoffs between TRAIN/VALIDATION and five between each later stage. The gaps
are 49, 42, and 42 days respectively, exceeding the maximum 30-day horizon
plus 8-day maturity lag (38 days). Account overlap is reported in the
preparation manifest; this is temporal evaluation of existing accounts, not
evidence of generalization to unseen accounts.

## Freshness, reliability, and abstention

| Assessment | Count | Share of eligible snapshots |
|---|---:|---:|
| Reliability: sufficient evidence | 0 | 0% |
| Reliability: limited evidence | 654 | 2.79% |
| Reliability: insufficient evidence | 22,761 | 97.21% |
| Freshness: fresh | 0 | 0% |
| Freshness: partially stale | 654 | 2.79% |
| Freshness: stale | 22,761 | 97.21% |
| Freshness: unknown | 0 | 0% |
| Abstention-eligible | 22,761 | 97.21% |

The applied freshness policy has a conservative two-day watermark threshold.
The adapter uses the latest available lifecycle/billing event as a watermark
and reports that no independent completeness heartbeat is exposed; event
silence therefore cannot distinguish an idle source from an ingestion outage.
Usage coverage has explicit gaps: 22,592 usage-source assessments were
partially stale/incomplete and 823 stale. Lifecycle and billing were stale in
22,737 and 22,784 source assessments respectively. The aggregate reason
SOURCE_NOT_CONNECTED occurred 9,355 times. Thus much of the stale result is
time-relative historical watermark age and missing heartbeat/coverage
evidence; the current contract cannot establish whether all such cases are
genuine source failures. No freshness or reliability thresholds were weakened.

Downstream scoring readiness is **BLOCKED**: no model was trained, and the
reliability/coverage evidence is insufficient for meaningful scored
predictions.

## Artifacts, reproducibility, and performance

Private output directory:

C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v1

Customer-level features and labels are private, compressed JSONL artifacts;
none are committed. preparation_manifest.json contains the policy/config,
cutoffs, splits, per-horizon and source-quality counts, software versions, and
SHA-256/byte/record checksums for all eight partition artifacts. Manifest
SHA-256:
c2a5465991ce1fd2dcbd537e888368a9557f0c06513484079fea342994de163b.
Artifacts use deterministic ordering and gzip mtime=0. This run records
deterministic output for identical inputs/code/configuration; a second full
run was not performed as an equivalence check.

Preparation software: Python 3.14.4, Pydantic 2.14.0, SQLite 3.50.4, and
retainiq_prediction package 0.1.0 on Windows 11. The manifest stores each
artifact's record count, byte length, and SHA-256.

Measured preparation duration was 920.336 seconds (15m 20.336s): 59.489
candidate account-cutoff pairs/second, 25.442 eligible feature snapshots/
second, and 76.325 labels/second. It made 234,495 Member 1 reader calls:
54,750 account snapshots, 54,750 subscription reads, 78,165 event reads, and
46,830 coverage reads. Peak working set was not available from the runner.
These are dataset-preparation throughput measurements, not model performance.

## Verification and blockers

Executed with the repository-local environment:

- Focused preparation, SQLite adapter, feature, label, temporal split,
  reliability/freshness, Member 1 Data Foundation and cross-member tests:
  **163 passed**.
- Full suite: **420 passed**, 0 failures/errors/skips, 24 known SHAP warnings
  (9 explainability, 15 prediction-pipeline warnings).
- Source database before/after checksum: **unchanged**.

Remaining blockers:

1. Reconcile why authorized outcome reads expose no qualifying termination
   facts and no complete subscription outcome coverage, despite the dataset's
   aggregate episode count. Until then all horizons remain blocked.
2. Member 1 needs an independent lifecycle/billing heartbeat or equivalent
   trusted completeness watermark, and explicit coverage/read diagnostics.
3. Keep effective-account-churn-v1.2 explicitly synthetic-only; the real
   account-level multi-subscription policy remains a team decision.
4. Obtain authorized, source-backed longitudinal data before any real-world
   readiness or effectiveness claim.

Reproduction (without dataset generation or re-import):

    .\.venv\Scripts\python.exe -B -m retainiq_prediction.historical_dataset_preparation --dataset C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68 --db C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3 --output-dir C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v1

Set RETAINIQ_MODEL_TOKEN from the authorized tenant-01 secret store for the
process only, then clear it. Do not print, commit, or place the token in the
command history. A future synthetic model-training task must first resolve
label coverage; if resolved, train each horizon only on mature TRAIN labels,
use VALIDATION for model/threshold decisions, CALIBRATION only for calibration,
and retain TEST untouched until the authorized final evaluation.
