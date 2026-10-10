# Member 2 LightGBM Models

## Scope and evidence boundary

`src/retainiq_prediction/lightgbm_model.py` implements the primary LightGBM
training candidate for RetainIQ v2. It is a training and internal inference
component only. It does not implement calibration, horizon-coherence
adjustment, SHAP explanations, production serving, benchmark evaluation, or
model promotion.

The repository has no authorized longitudinal dataset. The tests use
synthetic fixtures only, and saved test artifacts are temporary. A successful
synthetic fit is an implementation check, not evidence that LightGBM is better
than Logistic Regression or that either model predicts real churn accurately.

## Architecture

The implementation trains three independent binary classifiers:

- one classifier for 7-day churn;
- one classifier for 14-day churn; and
- one classifier for 30-day churn.

Each fit receives a `TemporalSplitResult` and reads only the TRAIN partition's
horizon-specific supervised mask. Independent models avoid treating the three
horizons as one target. Raw model outputs are returned through the shared
baseline result shape with `score_kind=uncalibrated_probability`.

LightGBM is the primary candidate, not a guaranteed better model than Logistic
Regression. A future comparison must use the same chronological cohorts,
mature labels, features, and alert budget for all baselines and model
variants.

## Input features and exclusions

The model reuses the approved `FeatureVectorizer` and
`MODEL_FEATURE_ALLOWLIST` from `baselines.py`:

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

Tenant IDs, customer IDs, labels, churn-effective timestamps,
cancellation-status fields, future subscription state, post-cutoff outcomes,
and protected identity data cannot enter the vectorizer. The model's
`tenant_id` scope can optionally restrict fitting and inference to one tenant;
the identifiers themselves remain excluded from features.

Missing numeric values are represented as `NaN` and handled by LightGBM's
native missing-value behavior. No future or test-set feature is added to the
matrix dynamically.

## Label and chronology requirements

Training requires:

1. an eligible prediction snapshot at its original `as_of`;
2. a confirmed mature positive or negative label for the requested horizon;
3. the temporal splitter's horizon-specific TRAIN inclusion mask; and
4. one consistent `label_policy_version` across the selected training rows.

Unknown, excluded, unsupported, immature, and missing labels are not converted
to zero. A single-class or insufficient training set returns `NOT_READY`.

Validation is never part of fitting by default. The configuration can enable
development-only validation early stopping; when enabled, only the
VALIDATION horizon mask is supplied as the evaluation set. CALIBRATION and
TEST are never read by `fit`, early stopping, feature selection, or parameter
selection. Calibration remains a later task.

## Default configuration

The conservative CPU defaults are:

| Setting | Default |
|---|---:|
| `n_estimators` | `40` |
| `learning_rate` | `0.05` |
| `num_leaves` | `7` |
| `max_depth` | `3` |
| `min_child_samples` | `5` |
| `subsample` | `0.9` |
| `colsample_bytree` | `0.9` |
| random seed | `42` |
| device | CPU |
| threads | `1` |
| validation early stopping | disabled |

`class_weight="balanced"` is supported as an explicit configuration when
class imbalance is justified by development data. No arbitrary imbalance
weight is applied by default. Expensive hyperparameter search is not
implemented.

## Reproducibility and metadata

Every successful fit records `LightGBMModelMetadata` containing:

- `model_version` and `model_family=lightgbm`;
- prediction horizon;
- feature and label-policy versions;
- exact feature names and order;
- training configuration and CPU settings;
- training cutoff and dataset provenance/status;
- LightGBM and Python dependency versions;
- native-missing-value preprocessing metadata;
- random seed; and
- `calibration_status=not_calibrated`.

Synthetic fixtures deliberately retain `training_dataset_status=BLOCKED`.
This prevents a successful functional fit from being mistaken for authorized
production readiness.

## Training and loading commands

From the repository root on Windows PowerShell:

```powershell
& .venv\Scripts\python.exe -m pip install -e ".[test,ml]"
& .venv\Scripts\python.exe -c "import lightgbm; print(lightgbm.__version__)"
& .venv\Scripts\python.exe -m pytest -q tests\test_lightgbm_model.py --basetemp .pytest-tmp
& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp
```

The verified environment contains Python 3.14.4, NumPy 2.5.3, SciPy 1.18.1,
scikit-learn 1.9.1, LightGBM 4.7.0, Pydantic 2.14.0, and pytest 8.4.2.

Artifacts can be saved and loaded only as trusted internal `.pkl` files under a
caller-selected `trusted_root`. Loading validates the path before unpickling,
then validates the artifact type, version, model family, calibration status,
and required fit metadata. Pickle remains executable serialization and must
not be used for arbitrary user uploads or untrusted model paths. No production
artifact registry is created here.

## Limitations and dependencies

- No authorized longitudinal dataset or real performance evaluation exists.
- Account-level multi-subscription churn semantics remain
  `IMPROVEMENT-002: NEEDS_TEAM_DECISION`.
- Member 1 must provide canonical lifecycle/billing mappings, source
  availability and correction timestamps, tenant authorization boundaries,
  observation coverage, and dataset provenance.
- Calibration, horizon coherence, SHAP associations, test-set metrics, model
  comparison, and promotion governance are deferred.
- Personalized-baseline ablation remains `IMPROVEMENT-001`; provisional rule
  threshold validation remains `IMPROVEMENT-003`.

