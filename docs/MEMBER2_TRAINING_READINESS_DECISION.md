# Member 2 Training Readiness Decision

> **Prompt 31 update:** This document records the frozen readiness decision before exploratory fitting. Prompt 31 has since fit separate uncalibrated synthetic-demo models for 14d and 30d using TRAIN and VALIDATION only. The original class-support/calibration gates remain unchanged; production and full-bundle readiness remain **BLOCKED**. See [the Prompt 31 training report](MEMBER2_PROMPT31_SYNTHETIC_DEMO_TRAINING.md).

## Decision

The preserved tenant-01 STANDARD v1.2 preparation is not ready for synthetic
model fitting under its frozen per-stage support minimums; operational scoring
is separately blocked by reliability/freshness and absence of a trained,
calibrated model. Do not use these findings as real-world performance claims.
No model was trained and no TEST metrics were computed or inspected for model
selection.

**Evidence identity:** Synthetic SaaS v1.2 STANDARD, seed 2026, tenant-01;
dataset `synthetic-saas-v1-2-standard-s2026-970a9d231e68`, source manifest
SHA-256 `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
Prepared artifact `member2-prep-v4`, manifest SHA-256
`1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a`.
Private artifacts are outside Git. Verified unique staged counts were
recovered from the checksummed partition labels; no IDs or raw rows are
included here.

## Readiness gates actually found

| Gate | Existing threshold / rule | Audit interpretation |
|---|---|---|
| Prepared synthetic stage/horizon class support | Dataset split manifest declares at least **50 positive rows, 50 negative rows, 20 unique positive accounts, and 20 unique negative accounts** in each TRAIN, VALIDATION, CALIBRATION, and untouched TEST cohort/horizon. | This is the predeclared readiness gate used for the reported `BLOCKED` decisions. It is not a universal statistical sufficiency claim. |
| Generic temporal splitter | `minimum_samples_per_horizon=2` default; the preparation explicitly sets 2. | Structural floor only; not the dataset class-support gate. |
| Calibration fitter | Default total 4, at least **2 positive + 2 negative** per horizon. | Optimizer minimum only; not strong evidence of useful calibration. CALIBRATION also fails the dataset's declared 50/20 gate. |
| Generic retraining assessor | Defaults: 2 total, at least 1 positive and 1 negative per horizon; requires all 7/14/30 horizons and reports provenance, maturity, selection warnings, and policy blockers. | Does not override dataset support/freshness requirements. No extra per-tenant numeric minimum is declared in this implementation. |
| Final TEST evaluator | Default at least **2 mature labeled rows/horizon**, required metrics `pr_auc`, `brier_score`, `recall_at_k`, frozen/untouched TEST, authorization reference, champion comparison, same-cohort option. | Structural minimum only. A real independent-test evidence floor beyond this is not specified; do not interpret 2 as adequate. TEST remains sealed in this audit. |
| Outcome coverage | No percentage threshold. Positive requires an available qualifying outcome; negative requires full horizon coverage by complete subscription-outcome evidence. Partial/gap/outage/censored/missing remains unknown. | Source evidence rule, not a class-count substitute. Usage-only coverage cannot mature a negative. |
| Label maturity / split | Dataset-specific 8-day outcome maturity lag; maximum 30-day horizon plus lag = **38 days**. Frozen gaps are **49, 42, 42 days**; label maturity exclusions are zero. | Timing checks pass for prepared artifact; timing does not cure missing coverage. |
| Reliability/freshness | Reliability defaults require **28 observed days and 4 observed weeks** for sufficient personal history. Freshness defaults require essential source watermark age ≤ **2 days**; these are synthetic configuration examples, not validated production SLAs. | All 23,415 rows have partial usage coverage; 0 sufficient reliability and 0 fresh aggregate freshness. Do not relax. |
| Dataset provenance / authorization | Real candidate path requires PASS, authorized real provenance, ready retraining evidence, version and temporal policy match. Synthetic mode is clearly synthetic-only. Tenant scope is explicit; no pooling is implied. | Current data are synthetic-only and tenant-01 authorized. No tenant-level minimum beyond scoped authorization was found. |

## Actual support by frozen stage and horizon

Each cell below gives positive / negative / unknown rows; unique positive /
unique negative accounts; mature-label prevalence `positive/(positive+negative)`;
then row deficit vs 50 positive and 50 negative, and unique-account deficit
vs 20 positive and 20 negative. Unknowns remain in the stage coverage
denominator but are not supervised samples. All stages have the listed total
unique accounts / repeated snapshots: TRAIN **324 / 6,833**, VALIDATION
**435 / 5,424**, CALIBRATION **501 / 3,199**, TEST **617 / 6,082**.

| Stage | Horizon | Pos / neg / unknown | Unique pos / neg | Mature prevalence | Row delta P / N | Unique delta P / N |
|---|---:|---:|---:|---:|---:|---:|
| TRAIN | 7d | 27 / 6,389 / 741 | 27 / 323 | 0.421% | -23 / +6,339 | +7 / +303 |
| TRAIN | 14d | 55 / 6,014 / 1,088 | 29 / 323 | 0.906% | +5 / +5,964 | +9 / +303 |
| TRAIN | 30d | 131 / 5,297 / 1,729 | 36 / 320 | 2.413% | +81 / +5,247 | +16 / +300 |
| VALIDATION | 7d | 28 / 5,138 / 693 | 28 / 431 | 0.542% | -22 / +5,088 | +8 / +411 |
| VALIDATION | 14d | 54 / 4,775 / 1,030 | 30 / 428 | 1.118% | +4 / +4,725 | +10 / +408 |
| VALIDATION | 30d | 113 / 4,084 / 1,662 | 33 / 415 | 2.692% | +63 / +4,034 | +13 / +395 |
| CALIBRATION | 7d | 13 / 3,673 / 14 | 13 / 501 | 0.353% | -37 / +3,623 | -7 / +481 |
| CALIBRATION | 14d | 27 / 3,655 / 18 | 14 / 499 | 0.733% | -23 / +3,605 | -6 / +479 |
| CALIBRATION | 30d | 59 / 3,614 / 27 | 17 / 498 | 1.606% | +9 / +3,564 | -3 / +478 |
| TEST | 7d | 32 / 6,651 / 16 | 32 / 614 | 0.479% | -18 / +6,601 | +12 / +594 |
| TEST | 14d | 64 / 6,614 / 21 | 32 / 611 | 0.958% | +14 / +6,564 | +12 / +591 |
| TEST | 30d | 134 / 6,535 / 30 | 37 / 603 | 2.009% | +84 / +6,485 | +17 / +583 |

All 7/14/30 horizons fail at least one stage's predeclared support minimum:
CALIBRATION misses unique positive account support (and row positives at 7d
and 14d); 7d also misses positive row support in TRAIN, VALIDATION, and TEST.
The actual frozen TEST boundaries remain 2026-06-01 through 2026-08-17,
freeze 2026-10-01; no boundaries were changed. The 30-day TEST has 134/6,535
positive/negative rows and 37/603 unique positive/negative accounts, but this
is not an invitation to tune against TEST.

## Separate readiness decisions

- **DATA_LABEL_READINESS:** mature positives and negatives exist at every
  horizon. Unknown labels remain **1,464 (7d), 2,157 (14d), 3,448 (30d)**;
  support is not uniformly complete. For each negative, complete subscription
  outcome coverage spans the full horizon and is available at label evaluation.
  Label evidence is synthetic policy `effective-account-churn-v1.2` only.
- **MODEL_FITTING_READINESS:** **BLOCKED** by frozen stage class/unique-account
  minima and synthetic-only provenance. Repeated cutoffs are correlated
  observations, not independent accounts.
- **CALIBRATION_READINESS:** **BLOCKED** at all horizons by 50 positive-row /
  20 unique-positive-account cohort rules, even though 30d reaches 59 positive
  rows; it has only 17 distinct positive accounts.
- **INDEPENDENT_TEST_READINESS:** the partition is chronologically frozen and
  label-mature (0 maturity exclusions), but independent evaluation is not
  authorized/performed here, no model/champion exists, and this audit does not
  inspect outcomes to optimize a candidate. The implementation's 2-row
  evaluator floor is not a sufficiency claim.
- **OPERATIONAL_SCORING_READINESS:** **BLOCKED**. No model/calibrator exists;
  reliability is sufficient 0 / limited 654 / insufficient 22,761; aggregate
  freshness is fresh 0 / partially stale 654 / stale 22,761 / unknown 0.
  Abstention-eligible is 22,761 (97.21%).
- **REAL-WORLD READINESS:** **BLOCKED_SYNTHETIC_ONLY** for all uses. Synthetic
  tests establish mechanics, not real predictive performance or SaaS
  distribution validity.

## Freshness and reliability evidence

Per-source assessments overlap and must not be summed as disjoint customers.
Across 54,750 candidate account/cutoff pairs, 28,483 had no subscription
lifecycle facts returned and 8 were explicitly `INSUFFICIENT_DATA` (3 TRAIN,
5 VALIDATION); those are not among the 23,415 eligible feature snapshots and
have no reliability assessment in these counts.
For 23,415 eligible snapshots, subscription lifecycle is stale for 22,737 and
partially stale for 678; billing is stale for 22,784 and partially stale for
631; usage coverage is partially stale/incomplete for 22,592 and stale for
823. `SOURCE_COVERAGE_INCOMPLETE` appears 22,592 times and
`SOURCE_NOT_CONNECTED` 9,355 times (reason counts may overlap). Personal
baseline status is available 16,385, insufficient history 5,172, unavailable
1,167, zero baseline 691; cold-start-history reason appears 6,538 times.
Missing personal baseline and stale/coverage reasons overlap.

Confirmed causes: every feature snapshot has partial usage coverage; the
adapter builds lifecycle/billing watermarks from latest visible customer
events, not a completeness heartbeat; and the health API's `freshness_status`
is explicitly `unknown`. The v4 manifest records 9,355
`SOURCE_NOT_CONNECTED` reason occurrences. Prompt 27 traced these to
`connected=False` being synthesized from no account-scoped event/coverage;
they are not measured outages. The adapter now represents absent operational
health as `connected=None` and returns unknown when no independent source
availability/watermark exists. Explicit disconnected evidence remains stale;
available complete coverage may establish freshness of that coverage without
claiming connectivity. Reliability rules and thresholds are unchanged. This
code-level correction has not been propagated through the private prepared
outputs, so their aggregate freshness/reliability distributions remain the
pre-correction results and must not be presented as corrected counts. Unknown
cause remains whether stale historical watermarks reflect expected
time-relative event silence, missing sync, outage, or an account coverage
defect. Do not promote freshness without source-backed cadence and completeness
evidence.

## Future data options (not executed)

| Option | Permissions / independence | Statistical and calibration limits | Cost / provenance / remaining block |
|---|---|---|---|
| **A. Keep tenant-01 STANDARD** | Existing exact tenant-01 source grants; keep current immutable TEST and manifest. | Observed support above fails the predeclared stage rules. No calibration-ready cohort. | Lowest incremental cost; no new source dataset ID, but any altered preparation config needs a new prep manifest. Does not address synthetic-only evidence, heartbeat, or account-policy gaps. |
| **B. Existing immutable FULL synthetic profile** | Explicit approval to use the already-generated FULL profile; one least-privilege credential/source grant per selected tenant. No cross-tenant principal by default. Use its immutable dataset ID and existing split manifest unchanged. | FULL's source-level manifest reports support at every stage, but tenant-01-only Member 2 labels, eligibility, reliability and calibration have not been re-prepared/verified. Larger synthetic counts do not validate generator realism or fix heartbeat absence. | Highest plausible compute/storage; FULL is ~20,000 accounts, 1,547,420 events, 3,263,358 coverage rows across four tenants. Exact Member 2 prep cost unknown; no new generated dataset ID if reusing immutable FULL, but a new scoped preparation needs its own manifest/artifact hashes. Frozen independent test can be retained only by honoring its existing split manifest. Remains synthetic demonstration only. |
| **C. Additional authorized tenant cohorts** | Requires each tenant's own grant and explicit approval for cross-tenant modeling, pooling, and evaluation; tenant-derived authorization remains enforced. | Domain/tenant heterogeneity and leakage/correlation must be evaluated. More rows do not automatically yield independent evidence; calibration needs appropriate later calibration cohorts. | More read/storage cost, roughly proportional to chosen scope but not measured. Combined cohort is a new prepared artifact/provenance manifest; preserve the existing holdout or define a separately approved, frozen cohort before access. Still synthetic-only if synthetic sources. |
| **D. Development-only pipeline smoke** | A small authorized, synthetic-only fixture/source scope; no real or cross-tenant permission implied. | Can verify optimizer/API wiring only; tiny/imbalanced samples cannot support calibrated probabilities or independent metrics. No TEST access for selection. | Lowest compute, but still produce explicit run provenance and do not call results model performance. Does not clear fitting, calibration, test, operational, or real-world readiness. |

**Recommended next experiment path:** first obtain the shared policy decision
and Member 1 source-health/coverage contract in
[`MEMBER2_TO_MEMBER1_CONTRACT_REQUESTS.md`](MEMBER2_TO_MEMBER1_CONTRACT_REQUESTS.md).
Then, if the project owner authorizes it, run a separately scoped,
read-only preparation on the existing FULL synthetic dataset for one tenant
first, honoring its immutable split manifest and producing a new prep manifest
with checksum-verified artifacts. Preflight support by horizon/stage and
reliability before any candidate fit; if any gate remains blocked, stop at
readiness. This tests engineering scale only. Do not pool tenants, alter seed,
prevalence, labels, horizon, reliability policy, or TEST boundaries to chase
counts. Do not make real-world claims.

No FULL preparation, new imports, model fitting, calibration, TEST evaluation,
or split changes were performed for this audit.
