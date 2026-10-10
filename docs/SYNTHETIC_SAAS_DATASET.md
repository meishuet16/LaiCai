# Synthetic SaaS dataset v1.2

## Purpose and boundary

This is an explicitly synthetic, tenant-isolated longitudinal SaaS dataset for engineering and synthetic model-development work. It contains no KKBox records and no real customer evidence. No model has been trained. Its results cannot establish real-world predictive performance, causal uplift, or saved revenue. The real-data gate remains separate in [`DATASET_CARD.md`](../DATASET_CARD.md).

## Generated immutable datasets

All profiles use seed 2026 and the 24-month period 2024-10-01 through 2026-09-30. Outputs are outside Git under `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2`.

| Profile | Dataset ID | Accounts / tenants | Canonical events | Usage daily rows | Coverage intervals | Total files | Generation | Canonical import | Manifest SHA-256 |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| QUICK | `synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3` | 200 / 4 | 16,351 | 14,403 | 32,697 | 11,277,564 B | 8.921 s | VERIFIED, 6.719 s | `a6b581a13abbd22ff50ba9d6300bab4946aaf144ad524fa9545e735640282d62` |
| STANDARD | `synthetic-saas-v1-2-standard-s2026-970a9d231e68` | 3,000 / 4 | 239,721 | 211,215 | 491,223 | 162,648,430 B | 113.069 s | VERIFIED, 60.555 s | `aa78180d3e5f49e0bc668b459e296616a16ee5ca97aa50c68bc28c8285c984e0` |
| FULL | `synthetic-saas-v1-2-full-s2026-33ac24d7f094` | 20,000 / 4 | 1,547,420 | 1,362,045 | 3,263,358 | 1,050,207,262 B | 748.09 s | VERIFIED, 478.985 s | `8f7110960b1adc11b9a7d6635d5a26298e820c42b8c26ebbd932c33f522fc17a` |

The FULL canonical ledger also contains 88,615 billing events and 96,760 subscription events. Across the dataset it records 21,648 subscriptions, 4,237 account-level final-entitlement-loss episodes, and 439 reactivations. Each profile is immutable and has a separate SQLite import database named `<dataset_id>.sqlite3` in the `db` directory.

## Artifacts and semantics

Each versioned dataset contains a manifest, generator configuration, data dictionary, customers and identity mappings, plan catalog, canonical/category event files, observation coverage, scenario coverage, quality and label-evidence reports, split proposal, and isolated label-oracle/adversarial fixtures. FULL has 21 output files. Generator latent state is discarded and excluded from canonical payloads, features, and the label oracle.

In v1.2, one `usage_aggregate_updated` record means one observed account-active day; its quantity records sessions for that day. `session_started` and `feature_used` are absent from those same daily rows, so Member 2 cannot count daily aggregates and session events as duplicate activity. Source coverage is represented independently per account and time interval. Complete observation, low activity, telemetry outage, delayed delivery, historical backfill gaps, entitlement ending, and right censoring have distinct states. A zero in a complete window means observed inactivity; an outage does not.

The account label target is final paid-entitlement loss, not payment failure, cancellation request, or loss of one of several subscriptions. Reactivation starts another risk episode. Weekly cutoff labels use `[t-7,t)`, `[t-30,t)`, and a non-overlapping earlier `[t-58,t-30)` baseline. Prediction cutoffs are Mondays at 12:00 UTC and labels mature after an 8-day operational lag plus the 30-day target horizon. Incomplete negative observation is unknown.

## Validation and readiness evidence

The independent validator returned PASS with no errors or warnings for QUICK, STANDARD, and FULL. STANDARD and FULL label evidence is marked READY for synthetic development. QUICK proves mechanics only. On exposure-adjusted `simulated_account_months`, FULL usage density ranges from 5.33 to 5.89 observed active-day rows per account-month by tenant and 5.24–6.66 by signup cohort. The cohort exposure denominator totals 240,996.88 simulated account-months; if one instead divides by all 20,000 accounts times 24 calendar months (including pre-creation periods), the average is 2.84 rows/account-calendar-month. Tenants have about 64.5–71.6 active days per account across the simulation. Sufficient history is not universal: FULL 30-day windows have 61–90% sufficiency across stages, while a non-overlapping 28-day baseline has 56–86%; tenant-level baseline coverage varies from about 63% to 80%. Member 2 should use coverage and quality flags and retain insufficient-history cases as such.

The measured scenario report has 48 categories, with source-verifiable counts and explicitly marked behavioral proxies. Examples include 9,866 accounts with low usage and no churn, 815 with low usage before churn, 3,882 with high usage and no churn, 297 with high usage before churn, 9,541 temporary decline/recovery proxies, 1,780 sudden-churn proxies, 15,020 stable-renewal accounts, 1,199 multiple-subscription accounts, 479 partial cancellations, 448 reactivations, and 4,880 accounts with payment failures but no churn. These categories overlap. Proxy categories are not direct proof from a single source event. Nonrenewal (157 accounts) and voluntary effective cancellation (429) are relatively sparse. Past-due late recovery (596 accounts) remains much less common than termination (4,006), so billing outcomes remain unusually predictive in this simulation.

FULL has positive examples for each horizon in every chronological stage. Weekly cutoffs repeat accounts and episodes: they are correlated observations, not independent samples. Keep the supplied chronological stages, report unique accounts and episodes, cluster uncertainty by account, and do not randomly split cutoffs. The generated manifest and scenario report are the reproducible sources for label counts, coverage rates, and split definitions.

## Generate, validate, and import

```powershell
python -m retaniq.synthetic generate --profile quick --seed 2026 --output 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2'
python -m retaniq.synthetic validate --dataset 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\quick\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3'
python -m retaniq.synthetic import --dataset 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\quick\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3' --db 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-quick-s2026-3d3b2b710cf3.sqlite3'
```

To use the immutable outputs already generated, pass their exact dataset paths shown above. The CLI imports each canonical row and coverage interval through the authorized tenant/source path, with per-batch transactions and a resumable import checkpoint. It preserves normalization, identity/ownership checks, source/category authorization, dataset identity, historical availability, and idempotency. It does not skip validation to gain speed. See the handoff for the restricted Member 2 smoke credential flow and actual import timings.

## Operational and scientific limits

The 48 measured scenario categories include underrepresented and proxy-only cases. Past-due recovery/termination, sudden-churn, nonrenewal, and voluntary cancellation are not population-calibrated. Some tenant history and personalized baselines are sparse. Scenario fixtures and label-oracle examples are separated from the ordinary population and must not be added to model inputs. Repeated weekly cutoffs require temporal controls. SQLite is a local reference integration, not the production PostgreSQL deployment. The synthetic dataset is suitable for engineering and comparative model development only; any metric must be explicitly labeled synthetic and cannot clear the real-data or real-world validation gates.
