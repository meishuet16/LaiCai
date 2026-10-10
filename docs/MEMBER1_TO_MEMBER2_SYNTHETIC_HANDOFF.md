# Member 1 → Member 2 synthetic handoff

## Ready inputs

The generated manifest identifies the exact private dataset directory, seed, period, counts, scenario coverage, hashes, and target policy. `canonical_events.csv` and its category files contain source-backed occurrence, availability, and receipt times. `observation_coverage.csv` distinguishes complete, partial, and outage periods.

Use the existing authorized reads: `get_account_snapshot_as_of`, `get_events_as_of`, `get_subscriptions_as_of`, and `list_eligible_accounts_as_of`.

Potential feature families include recent sessions and active days, feature adoption, days since last observed usage, customer-relative non-overlapping baselines, usage trend and variability, billing failures and recovery, tenure, source freshness, and observation completeness. Do not use cancellation request state, generator scenario aggregates, latent state, or post-cutoff evidence as predictors.

## Outcome contract

The event ledger is authoritative. For a common eligible cutoff `t`, label horizon `h` positive only when loss of the final qualifying paid entitlement occurs in `(t,t+h]`. A negative requires complete observation through the full horizon. Censored periods remain `unknown`. Cancellation known at the cutoff uses the `known_cancellation` state and leaves the prospective scoring population. Payment failure alone is not churn. Reactivation creates a later lifecycle episode and does not erase earlier effective churn.

`label_oracle_fixtures.json` is a small independent test oracle. It is not a production label table. Member 2 still owns point-in-time feature construction and 7/14/30-day label materialization.

## Chronology

`split_manifest.json` proposes chronological training, development, calibration, and untouched test windows with 30-day maturity/embargo boundaries for the default period. Recalculate the windows when dates are overridden. Multiple cutoffs for one account are correlated observations and must not be randomly split across stages.

## Authorization and example

After import, provision an analyst principal with `retention_inference`, `model_artifact_write`, exact generated sources, and `billing_valuation` only when valuation is required. Store its token outside Git and set `RETAINIQ_MODEL_TOKEN`.

```powershell
python .\examples\member2_synthetic_as_of_history.py --db "$HOME\RetainIQ-private\synthetic_saas_v1\quick.sqlite3" --tenant-id tenant-01 --customer-id tenant-01-customer-000001 --as-of 2026-08-31T23:59:59Z
```

## Conditional work

Actual labels, training features, LightGBM/logistic/rule models, calibration, held-out metrics, explanations, and saved predictions remain conditional on Member 2 code executing successfully. No generated metric may be presented as real-world validation.
