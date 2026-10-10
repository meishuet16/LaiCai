# Member 2 Baseline Models

## Scope and evidence boundary

This milestone adds a transparent rule baseline and an optional
scikit-learn Logistic Regression baseline. They are comparison components for
future 7/14/30-day model evaluation. They do not populate the canonical
`PredictionOutput`, perform calibration, create SHAP explanations, or claim
production forecast quality.

The repository currently has no authorized longitudinal dataset. All tests use
synthetic fixtures and demonstrate structural behavior only. No accuracy,
PR-AUC, Brier score, Recall@K, warning lead time, false-alert, retention, or
ROI claim is made.

## Common result interface

`BaselinePrediction` identifies:

- the horizon (`7`, `14`, or `30`);
- `READY`, `NOT_READY`, or `UNFITTED` status;
- a score and its explicit kind;
- baseline, feature, and model versions; and
- machine-readable explanatory reasons.

Rule results use `ranking_score`. Logistic results use
`uncalibrated_probability`. Neither is a calibrated production churn
probability. A future serving layer must apply the approved calibration and
then construct the canonical `PredictionOutput` only after its release gate.

## Rule baseline

`RuleBasedBaseline` is deterministic and configurable through
`RuleBaselineConfig`. The default version is `rule_baseline_v1`; its defaults
are operational assumptions, not validated scientific thresholds:

| Signal | Default condition | Score contribution |
|---|---:|---:|
| Days since last observed session | `>= 14` | `40` |
| Recent-to-personal-baseline usage ratio | `<= 0.5` | `35` |
| Point-in-time payment failures | `>= 1` | `15` |

The default alert threshold is a ranking score of `50`, and an alert also
requires at least one known usage signal. Payment failure is a risk signal,
not proof of churn. The caller may supply a point-in-time payment-failure
count from the canonical billing adapter; `None` means unknown, not zero.

Missing sessions, missing personal baseline, and incomplete usage history do
not contribute an inactivity or decline score. When no risk signal is known,
the result is `NOT_READY` with no score. Thus missing usage is not silently
treated as zero usage or confirmed inactivity.

The rule baseline has no fitted parameters. Its `fit` method returns versioned
ready metadata and does not inspect labels or historical partitions.

## Logistic Regression baseline

`LogisticRegressionBaseline` trains one independent binary classifier per
horizon. It accepts a `TemporalSplitResult` and reads only the TRAIN
partition's horizon-specific supervised mask. The existing temporal splitter
has already excluded ineligible, unknown, excluded, unsupported, and immature
labels. The implementation refuses training when there are insufficient
samples or only one class.

Preprocessing is part of the training pipeline:

1. median imputation with missingness indicators;
2. standard scaling; and
3. Logistic Regression with a fixed random seed and configurable `max_iter`.

All imputation and scaling parameters are learned from TRAIN only. Validation,
calibration, and TEST snapshots are not used by `fit`. TEST labels remain
evaluation-only under the temporal splitting contract.

The raw output is explicitly marked `uncalibrated_probability`. Threshold
selection, calibration, and production model release are outside this task.

## Feature allowlist

The model vectorizer allows only these numeric or boolean fields from
`FeatureValues`:

- `sessions_prev_7d`
- `sessions_prev_30d`
- `days_since_last_observed_session`
- `recent_usage_trend`
- `observed_weeks`
- `valid_usage_history`
- `historical_avg_sessions_per_week`
- `recent_avg_sessions_per_week`
- `absolute_usage_deviation`
- `percentage_usage_deviation`
- `recent_to_baseline_usage_ratio`
- `historical_weekly_usage_variability`

Tenant/customer identifiers, churn labels, churn-effective timestamps,
known-cancellation indicators, future subscription state, post-cutoff
interventions, and protected personal information are not vectorized. The
allowlist is versioned through the feature and baseline configuration.

## Dependency and setup status

The verified project-local environment uses prebuilt Windows wheels with these
versions:

| Dependency | Version |
|---|---:|
| Python | 3.14.4 |
| NumPy | 2.5.3 |
| SciPy | 1.18.1 |
| scikit-learn | 1.9.1 |
| Pydantic | 2.14.0 |
| pytest | 8.4.2 |

The dependency declaration is the `ml` optional extra in `pyproject.toml`.
Windows setup from the repository root is:

```powershell
& C:\Path\To\Python3.14\python.exe -m venv .venv
& .venv\Scripts\python.exe -m pip install -e ".[test,ml]"
& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp
```

`.venv/` and pytest caches are ignored by Git. The verified run used the
project-local `.venv\Scripts\python.exe`; the global Python installation was
not modified.

Fitted artifacts can be saved and loaded for trusted local use. The artifact
uses executable Python pickle serialization, so `load` requires a validated
`trusted_root` and a `.pkl` file inside that directory. It must never be used
for an untrusted upload or arbitrary user-controlled path. Model registry
approval, digest verification, and promotion governance remain
Member 4/integration responsibilities.

## Multi-horizon and temporal dependencies

Each horizon is fit independently using its own mature labels. A valid 7-day
training row does not imply a valid 14- or 30-day row. The model depends on:

- the canonical `FeatureSnapshot` feature version;
- the existing `ChurnLabel` statuses and `evaluation_as_of` metadata;
- the temporal splitter's TRAIN-only supervised masks; and
- the unresolved account-level multi-subscription churn policy.

`IMPROVEMENT-002` remains `NEEDS_TEAM_DECISION`. No `any_subscription_end`
default was introduced and no existing label policy was changed.

## Future comparison with LightGBM

The rule and Logistic Regression baselines are intended for a later
same-cohort comparison against personalized multi-horizon LightGBM. That
comparison requires an authorized dataset, mature outcomes, untouched
chronological TEST evaluation, approved calibration, and sufficient samples.
LightGBM is not implemented or installed in this milestone.
