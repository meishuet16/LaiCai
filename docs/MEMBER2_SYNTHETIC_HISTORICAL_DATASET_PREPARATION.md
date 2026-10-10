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

The initial Prompt 24 zero-label outcome was traced to two Member 2 adapter
interpretation defects and corrected: Member 1's canonical lifecycle fold uses
status `ended` for effective termination facts, and the label builder did not
join adjacent complete subscription coverage intervals. The revised builder
recognizes the terminal status and joins only continuous complete subscription
coverage; gaps and incomplete/outage segments remain unknown. A further
synthetic-only lifecycle correction preserves a churn episode through
reactivation and timestamps multi-subscription churn at final entitlement
loss. Reliability reason ordering was made deterministic. An authenticated
source audit verified outcome evidence and availability at evaluation cutoffs.
Full findings and the scenario-to-test matrix are in
[`MEMBER2_OUTCOME_COVERAGE_BLOCKERS.md`](MEMBER2_OUTCOME_COVERAGE_BLOCKERS.md).

The corrected full preparation produced mature outcomes while preserving
unknown labels and excluding non-prospective cases. Counts below use 23,415
eligible account-cutoff snapshots as the horizon denominator. Prevalence is
positive / (positive + negative), not model performance.

| Horizon | Eligible | Positive | Negative | Unknown | Confirmed-label prevalence | Synthetic training |
|---:|---:|---:|---:|---:|---:|---|
| 7 days | 23,415 | 100 | 21,851 | 1,464 | 0.456% | **BLOCKED** |
| 14 days | 23,415 | 200 | 21,058 | 2,157 | 0.941% | **BLOCKED** |
| 30 days | 23,415 | 437 | 19,530 | 3,448 | 2.189% | **BLOCKED** |

Across the lifecycle-backed population, 111 snapshots were known cancellations,
2,733 were not eligible, and 8 had insufficient eligibility evidence; these
are outside the eligible denominators. Eligible records contain 700 unique
accounts and 22,715 repeated account snapshots. Unknowns are 6.25%, 9.21%, and
14.72% by horizon; they are not reclassified as negatives. Per-horizon reason
and source-coverage status counts are recorded in the private manifest. Its
label-reason totals cover all 26,267 lifecycle-backed candidate snapshots,
including separately identified non-prospective eligibility outcomes. Coverage
record/status counts are repeated account-cutoff observations at each horizon,
not unique source-row counts. The separate authorized source audit counted
39,824 unique tenant-scoped coverage rows: 37,099 complete, 1,162 outage, 63
partial, 750 censored, and 750 not-created.

An additional end-boundary authorized API audit at 2026-09-30T23:59:59Z found
750 tenant-01 identities: 629 with a paying entitlement (625 eligible and 4
known cancellations under Member 2's conservative routing), and 121 not
eligible. It observed 155 accounts with qualifying termination evidence across
160 facts, 137 active-to-no-paying-entitlement transitions, 75 accounts with
multiple historical subscription IDs, 23 with a partial termination while
another entitlement remained active, and 154 with a later paid-active
lifecycle fact after a qualifying termination. These are source-history
aggregates, not labels or generator scenario claims.

All horizons remain **BLOCKED** under the dataset's declared per-stage support
rules (at least 50 positive and negative snapshots and 20 unique accounts per
class in every stage). CALIBRATION is below the positive support minimum for
all horizons; 7-day TRAIN and VALIDATION also lack positive support, and 7-day
TEST has only 32 positive snapshots. Weekly snapshots repeat accounts, so row
counts are not independent customers. This is synthetic-only evidence, not
real-world validation.

## Frozen chronological partitions

The splitter uses the existing chronological infrastructure. Prediction
snapshots are assigned by as_of; all horizons remain attached to their
snapshot. Labels are eligible for a stage only if confirmed and available by
that stage's freeze. TEST labels are evaluation-only and are never made
available to supervised fitting or model selection. No model-selection or
performance analysis was performed.

| Partition | Cutoffs | UTC cutoff dates (inclusive) | Label freeze (exclusive) | Snapshots | Unique accounts | Positive / negative / unknown per horizon |
|---|---:|---|---|---:|---:|---|
| TRAIN | 37 | 2024-12-09 – 2025-08-18 | 2025-10-01 | 7,157 | 324 | 7d 27/6,389/741; 14d 55/6,014/1,088; 30d 131/5,297/1,729 |
| VALIDATION | 16 | 2025-10-06 – 2026-01-19 | 2026-03-01 | 5,859 | 435 | 7d 28/5,138/693; 14d 54/4,775/1,030; 30d 113/4,084/1,662 |
| CALIBRATION | 8 | 2026-03-02 – 2026-04-20 | 2026-06-01 | 3,700 | 501 | 7d 13/3,673/14; 14d 27/3,655/18; 30d 59/3,614/27 |
| TEST | 12 | 2026-06-01 – 2026-08-17 | 2026-10-01 | 6,699 | 617 | 7d 32/6,651/16; 14d 64/6,614/21; 30d 134/6,535/30 |

Each triple is positive / negative / unknown. TEST is evaluation-only and was
not used for fitting or selection. Label maturity exclusions were zero in all
stages: stage freezes and 42–49 day inter-stage gaps exceed the 30-day horizon
plus 8-day maturity lag. This establishes label timing, not account independence.

Unique positive / unique negative accounts by stage (per horizon):

| Stage | 7d | 14d | 30d |
|---|---:|---:|---:|
| TRAIN | 27 / 323 | 29 / 323 | 36 / 320 |
| VALIDATION | 28 / 431 | 30 / 428 | 33 / 415 |
| CALIBRATION | 13 / 501 | 14 / 499 | 17 / 498 |
| TEST | 32 / 614 | 32 / 611 | 37 / 603 |

Stage quality and usage-history distributions from the manifest:

| Stage | Reliability limited / insufficient | Freshness partial / stale | Usage coverage partial | Personal baseline available / insufficient-history / unavailable / zero |
|---|---:|---:|---:|---:|
| TRAIN | 222 / 6,935 | 222 / 6,935 | 7,157 | 3,983 / 2,460 / 549 / 165 |
| VALIDATION | 151 / 5,708 | 151 / 5,708 | 5,859 | 3,493 / 1,982 / 264 / 120 |
| CALIBRATION | 105 / 3,595 | 105 / 3,595 | 3,700 | 3,159 / 291 / 140 / 110 |
| TEST | 176 / 6,523 | 176 / 6,523 | 6,699 | 5,750 / 439 / 214 / 296 |

All observed usage coverage rows are partial; this is not interpreted as zero
activity. Freshness/reliability had no sufficient/fresh rows in any stage.

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
partially stale/incomplete and 823 stale. Lifecycle was stale/partially stale
in 22,737/678 source assessments; billing was stale/partially stale in
22,784/631 assessments. The aggregate reason
SOURCE_NOT_CONNECTED occurred 9,355 times. Thus much of the stale result is
time-relative historical watermark age and missing heartbeat/coverage
evidence; the current contract cannot establish whether all such cases are
genuine source failures. No freshness or reliability thresholds were weakened.

Readiness is separated by use:

- **LABEL_READINESS: BLOCKED_FOR_SYNTHETIC_TRAINING_SUPPORT.** Mature labels
  now exist at all horizons, but the predeclared per-stage class and unique
  account minimums are not met (see the CALIBRATION and 7-day support above).
- **SCORING_RELIABILITY_READINESS: BLOCKED.** No model was trained, there are
  zero sufficient-evidence/fresh snapshots, and 97.21% are
  insufficient-evidence/stale. No meaningful scored prediction population is
  established.
- **REAL_WORLD_READINESS: BLOCKED_SYNTHETIC_ONLY.** These data do not establish
  real-world performance or outcome effectiveness.

## Artifacts, reproducibility, and performance

Final Prompt 25 private output directory (earlier v1–v3 outputs are preserved):

C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v4

Customer-level features and labels are private, compressed JSONL artifacts;
none are committed. preparation_manifest.json contains the policy/config,
cutoffs, splits, per-horizon and source-quality counts, software versions, and
SHA-256/byte/record checksums for all eight partition artifacts. Manifest
SHA-256:
1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a.
Artifacts use deterministic ordering and gzip mtime=0. The v3 and v4 manifest
hashes and all eight partition artifact hashes match exactly, verifying
equivalent output across repeated preparations with identical data and config.

Preparation software: Python 3.14.4, Pydantic 2.14.0, SQLite 3.50.4, and
retainiq_prediction package 0.1.0 on Windows 11. The manifest stores each
artifact's record count, byte length, and SHA-256.

Measured final preparation duration was 950.910 seconds (15m 50.910s):
57.576 candidate account-cutoff pairs/second, 24.624 eligible feature
snapshots/second, and 73.871 labels/second. It made 234,495 Member 1 reader
calls: 54,750 account snapshots, 54,750 subscription reads, 78,165 event
reads, and 46,830 coverage reads. Peak working set was not available from the
runner. The source database SHA-256 matched before and after
(71bc6c18d9266c2b0c8b8e5008f6f6633a55804b1fe90a947f8ea24ca3ee5943).
These are dataset-preparation throughput measurements, not model performance.

## Verification and blockers

Executed with the repository-local environment:

- Prompt 25 focused outcome reconciliation, label builder, preparation,
  SQLite adapter, features, temporal splits, reliability/freshness, Member 1
  Data Foundation and cross-member tests: **175 passed**.
- Full Prompt 25 suite: **432 passed**, 0 failed/errors/skipped, 24 known SHAP
  warnings (9 explainability, 15 prediction-pipeline warnings); warnings were
  not suppressed.
- Source database before/after checksum: **unchanged**.

Remaining blockers:

1. All horizons remain blocked for synthetic training under the frozen
   per-stage class and unique-account minimums. Do not train or inspect test
   performance to work around this gate.
2. Member 1 needs an independent lifecycle/billing heartbeat or equivalent
   trusted completeness watermark, and explicit coverage/read diagnostics.
3. Keep effective-account-churn-v1.2 explicitly synthetic-only; the real
   account-level multi-subscription policy remains a team decision.
4. Investigate the single bounded-cutoff discrepancy between the Member 1
   eligible-account enumerator and Member 2's known-cancellation routing.
5. Obtain authorized, source-backed longitudinal data before any real-world
   readiness or effectiveness claim.

Reproduction (without dataset generation or re-import):

    .\.venv\Scripts\python.exe -B -m retainiq_prediction.historical_dataset_preparation --dataset C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68 --db C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3 --output-dir C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v4

Set RETAINIQ_MODEL_TOKEN from the authorized tenant-01 secret store for the
process only, then clear it. Do not print, commit, or place the token in the
command history. A future synthetic model-training task must first resolve
label coverage; if resolved, train each horizon only on mature TRAIN labels,
use VALIDATION for model/threshold decisions, CALIBRATION only for calibration,
and retain TEST untouched until the authorized final evaluation.
