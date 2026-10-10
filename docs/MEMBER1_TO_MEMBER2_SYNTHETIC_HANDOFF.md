# Member 1 → Member 2 synthetic handoff

## Verified inputs

Version 1.2 outputs are immutable and outside Git. QUICK, STANDARD, and FULL pass independent validation with zero errors or warnings. STANDARD and FULL import through the canonical data foundation was verified for accepted counts, idempotent replay, dataset identity, and cross-tenant denial. The Member 2 read-only smoke passed on both. No model training or performance evaluation was performed.

| Profile | Dataset ID | Dataset path | Import database | Account / tenant | Canonical events | Coverage rows |
|---|---|---|---|---:|---:|---:|
| QUICK | `synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3` | `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\quick\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3` | `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3.sqlite3` | 200 / 4 | 16,351 | 32,697 |
| STANDARD | `synthetic-saas-v1-2-standard-s2026-970a9d231e68` | `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68` | `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3` | 3,000 / 4 | 239,721 | 491,223 |
| FULL | `synthetic-saas-v1-2-full-s2026-33ac24d7f094` | `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\full\synthetic-saas-v1-2-full-s2026-33ac24d7f094` | `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-full-s2026-33ac24d7f094.sqlite3` | 20,000 / 4 | 1,547,420 | 3,263,358 |

FULL spans 2024-10-01 through 2026-09-30, with 1,362,045 daily usage rows, 88,615 billing events, 96,760 subscription events, 21,648 subscriptions, 4,237 final-entitlement-loss episodes, and 439 reactivations. Its 48 measured scenario categories include both event-verifiable categories and clearly marked behavioral proxies. Category and profile hashes are in each dataset's `dataset_manifest.json`.

## Import and authorization

Import/replay always names the exact immutable dataset and its own database. Example for FULL:

```powershell
python -m retaniq.synthetic import --dataset 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\full\synthetic-saas-v1-2-full-s2026-33ac24d7f094' --db 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-full-s2026-33ac24d7f094.sqlite3'
```

The importer normalizes through `ingest_event`, checks tenant/source/category authorization and subscription ownership, stores dataset identity and account-level source-coverage intervals, and uses bounded transactions with a resumable checkpoint. Measured imports took 6.719 seconds for QUICK, 60.555 seconds for STANDARD (730,944 event-plus-coverage rows), and 478.985 seconds for FULL (4,810,778 combined rows). FULL accepted all 1,547,420 event rows and 3,263,358 coverage rows, verified the identity, and denied a cross-tenant read. Its Member 2 smoke also passed.

Provision a one-time analyst credential separately for each tenant. It is restricted to the dataset's exact usage, billing, and subscription sources, with `retention_inference` and `model_artifact_write`. Add billing valuation only for a task that needs monetary amounts. Do not put the emitted token in source control or logs:

```powershell
$dataset = 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\full\synthetic-saas-v1-2-full-s2026-33ac24d7f094'
$db = 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-full-s2026-33ac24d7f094.sqlite3'
python -m retaniq.synthetic provision-reader --dataset $dataset --db $db --tenant-id tenant-01
# Store the one-time token in the local secret manager, then:
$env:RETAINIQ_MODEL_TOKEN = '<one-time tenant-scoped token>'
python .\examples\member2_synthetic_smoke.py --db $db --dataset $dataset --tenant-id tenant-01
```

The smoke reads a cutoff snapshot, usage/billing/subscription evidence and source coverage. It checks dataset identity and grants. It compares features to the isolated synthetic oracle solely to verify mechanics; it does not persist production labels or train a model. Repeat provisioning per tenant rather than granting one principal every tenant.

## Usage evidence and feature windows

`usage_aggregate_updated` represents one observed active day. Its integer quantity is that day's session count. `session_started` and `feature_used` do not coexist with the daily aggregates, preventing duplicate activity counts. Build session totals by summing quantity and active days by distinct aggregate dates. Use the authorized as-of API, not raw CSVs, for the canonical source view.

For cutoff date `d`, use `[d-7,d)`, `[d-14,d)`, `[d-30,d)`, and a non-overlapping comparison `[d-58,d-30)`. Check per-account usage coverage across each window. A complete window with no aggregate rows is observed inactivity; outage, partial, missing-backfill, delayed, censored, not-created, and entitlement-ended coverage have separate meanings. Do not impute missing telemetry as zero usage. FULL averages 5.33–5.89 active-day rows per exposure-adjusted simulated account-month by tenant (5.24–6.66 by signup cohort, across 240,996.88 cohort account-months). Including all 20,000 accounts across all 24 calendar months, including pre-creation periods, gives 2.84 rows per nominal account-month. History sufficiency varies: by stage, 30-day sufficiency is 61–90% and non-overlapping 28-day baseline sufficiency is 56–86%. Carry `short_personal_usage_history`, `missing_usage_source`, `partial_source_coverage`, or `unknown_observation_coverage` when applicable.

Example of a verified STANDARD smoke feature row at cutoff `2025-08-18T12:00Z`: 7d 2 sessions / 2 active days; 30d 7 / 7; prior 28d baseline 5 / 4; baseline non-overlapping; coverage complete. A separate positive example had final entitlement loss 2025-05-15, first visible by 7-day maturity. These examples are synthetic and only demonstrate as-of mechanics.

## Outcome policy and independent evidence

Member 2 owns the production label builder. For account cutoff `t`, horizon `h` is positive if the last qualifying paid entitlement is effectively lost in `(t,t+h]`; it is negative only with complete subscription-outcome observation through the full horizon and maturity lag. Otherwise label is unknown. Exclude accounts whose cancellation is already known at `t`. Payment failure, a request to cancel, and one subscription ending while another remains entitled are not account churn. Reappearance after final loss starts a later episode. Do not expose generator latent factors or scenario labels as model features.

The isolated label evidence below independently reconciles the lifecycle stream and account coverage. Counts are cutoff rows (`positive / negative / unknown`); repeated weekly cutoffs are correlated. “Unique positive” is distinct accounts with a positive at that horizon; “episodes” is distinct positive risk episodes. Eligibility exclusions for known cancellation are omitted from the denominators shown. FULL stage totals:

| Stage | Cutoffs / dates | Candidate cutoffs | Known-cancellation exclusions | Outcome rows after exclusion | Horizon | Positive / negative / unknown | Unique positive accounts / episodes |
|---|---:|---:|---:|---:|---:|---:|
| Train | 37 | 189,227 | 298 | 188,929 | 7d | 827 / 178,467 / 9,635 | 822 / 827 |
| Train |  |  |  |  | 14d | 1,704 / 173,119 / 14,106 | 880 / 885 |
| Train |  |  |  |  | 30d | 3,854 / 160,745 / 24,330 | 981 / 987 |
| Development | 16 | 163,700 | 221 | 163,479 | 7d | 745 / 147,636 / 15,098 | 745 / 745 |
| Development |  |  |  |  | 14d | 1,497 / 139,677 / 22,305 | 794 / 795 |
| Development |  |  |  |  | 30d | 3,295 / 132,791 / 27,393 | 930 / 932 |
| Calibration | 8 | 100,824 | 165 | 100,659 | 7d | 477 / 99,921 / 261 | 477 / 477 |
| Calibration |  |  |  |  | 14d | 946 / 99,390 / 323 | 545 / 545 |
| Calibration |  |  |  |  | 30d | 2,044 / 98,158 / 457 | 694 / 694 |
| Untouched test | 12 | 175,538 | 243 | 175,295 | 7d | 694 / 151,922 / 22,679 | 694 / 694 |
| Untouched test |  |  |  |  | 14d | 1,412 / 140,341 / 33,542 | 769 / 769 |
| Untouched test |  |  |  |  | 30d | 3,085 / 117,660 / 54,550 | 922 / 922 |

All cutoff rows have enough elapsed calendar time for the longest horizon plus the 8-day maturity lag. Unknown labels arise from incomplete outcome-source coverage, not immature dates. The frozen chronological cutoff windows are train `2024-10-01`–`2025-08-24`, development `2025-10-01`–`2026-01-25`, calibration `2026-03-01`–`2026-04-26`, and untouched test `2026-06-01`–`2026-08-24`; maturity boundaries are in `split_manifest.json`. It provides positive and negative variation in each stage/horizon, including the later test, but many accounts recur at weekly cutoffs across stages. Use temporal stage boundaries, account-clustered uncertainty, and report cutoff rows alongside unique accounts and episodes. Do not random-split rows. Rule/logistic/LightGBM comparison has enough synthetic counts to run as a development experiment, but repeated cutoffs and simulated feature relationships preclude interpreting standard errors or metrics as real-world evidence.

## Scenario coverage and realism limitations

The 48 categories have measured account/event counts in `scenario_coverage.json`; categories overlap. Examples: low usage without churn 9,866 accounts and low usage before churn 815; high usage without churn 3,882 and before churn 297; temporary decline/recovery 9,541 and sudden churn 1,780 are `SOURCE_PROXY` behavioral classifications; 15,020 stable-renewal accounts; 1,199 multiple-active-subscription accounts; 479 partial cancellations; 4,880 accounts with payment failure without churn; 448 reactivations. Treat proxies as generated behavior measurements rather than direct source event proof.

Scientifically material limitations: past-due recovery (596 accounts) is still much rarer than termination (4,006); nonrenewal (157) and voluntary cancellation (429) are sparse; tenant history and personal baselines differ; recent source-coverage scenarios can reveal data quality regimes; and weekly cutoff samples are dependent. Validate event-time visibility and leakage before training. Keep scenario fixtures and oracle separate from the ordinary population. Do not claim the synthetic distribution is calibrated to SaaS customers.

## Chronology, ownership, and work remaining

Feature inputs must come only from records visible at the cutoff by both occurrence and verified source availability (or actual receipt fallback). Outcomes are consulted only after maturity by the label-building process. The dataset also has isolated oracle outcomes; use them to test a label builder, never as features. Keep each model artifact, calibration, and report bound to this exact `dataset_id`, target policy, split, feature version, and profile. Synthetic and KKBox remain isolated as documented in [`HYBRID_DATASET_STRATEGY.md`](HYBRID_DATASET_STRATEGY.md).

The inputs are ready for Member 2 to implement and compare point-in-time feature and label pipelines, then train on synthetic data only. Member 2 still owns label materialization, feature versioning, model comparison, calibration, evaluation, and saved model artifacts. Member 3/4 can use the same dated MRR, billing and subscription facts for integration exercises; simulated amounts and outcomes must remain labeled synthetic. No synthetic metric demonstrates real-world predictive performance.
