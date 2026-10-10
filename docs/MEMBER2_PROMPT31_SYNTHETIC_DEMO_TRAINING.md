# Prompt 31 — Synthetic-only LightGBM training report

## Outcome

Two LightGBM horizon models were genuinely fit from the existing tenant-01 STANDARD **synthetic** prepared data: 14-day and 30-day. The models were reloaded from their saved artifacts and generated 9,026 raw validation scores. They are uncalibrated, synthetic-demo-only artifacts; they are not a complete 7/14/30 bundle and are **not production-ready**. The 7-day horizon was not fit because it fails the frozen TRAIN and VALIDATION positive-class minimum. Calibration was not run because the frozen calibration support gate fails for every horizon.

No TEST label/features file was opened, no TEST outcome was used, no STANDARD manifest or split was changed, and no synthetic rows were added to the source database. Row-level scores and models remain outside Git.

## Data source and development-only audit

- Dataset: `synthetic-saas-v1-2-standard-s2026-970a9d231e68`, STANDARD v1.2, seed 2026, generator build `r9`; source manifest SHA-256 `7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d`.
- Authorized scope represented by the immutable prepared artifact: tenant-01 only. Prepared directory: `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v4`.
- Preparation manifest SHA-256: `1169164a8c3b038572a8c19f534bc519e51cbe14bde235227297238d0bb3d94a`. The training command verified this digest and each of the four TRAIN/VALIDATION feature/label artifact checksums before loading them.
- Existing frozen half-open boundaries were reused: TRAIN ends `2025-10-01T00:00:00Z`; VALIDATION ends `2026-03-01T00:00:00Z`. The splitter applies the prepared label-availability cutoffs; the training script additionally checks `evaluation_as_of`, `label_observed_through`, and `label_generated_at` against each stage end for every supervised row.
- No existing KKBox or other authorized dataset was found in the repository or the inspected private dataset root. No new dataset was downloaded or generated.

### TRAIN and VALIDATION populations

Every prepared feature row is an eligible account snapshot. Repeated snapshots are retained for time-forward evaluation of existing accounts; there are 292 unique accounts shared between TRAIN and VALIDATION, so this is not an unseen-account generalization test.

| Stage | Snapshots / eligible | Unique accounts | Repeated snapshots | 7d positive / negative / unknown | 14d positive / negative / unknown | 30d positive / negative / unknown |
|---|---:|---:|---:|---:|---:|---:|
| TRAIN | 7,157 | 324 | 6,833 | 27 / 6,389 / 741 | 55 / 6,014 / 1,088 | 131 / 5,297 / 1,729 |
| VALIDATION | 5,859 | 435 | 5,424 | 28 / 5,138 / 693 | 54 / 4,775 / 1,030 | 113 / 4,084 / 1,662 |

Unknown labels remain in the coverage denominator and were never changed to negatives. For 14d/30d the mature TRAIN and VALIDATION cohorts pass the frozen row/account support minima. For 7d, TRAIN and VALIDATION have only 27/28 positives against the 50-positive minimum, so no 7d model was fit. CALIBRATION support remains blocked under the unchanged gate: the earlier verified frozen audit reports 7d 13 positive rows/13 positive accounts, 14d 27/14, and 30d 59/17 (the last still below 20 unique positives). No calibration artifact or label file was loaded in this experiment.

### Feature coverage and limitations

| Stage | Usage coverage | Recent window fully covered | Baseline window covered | Personal baseline: available / insufficient-history / unavailable / zero |
|---|---:|---:|---:|---:|
| TRAIN | 7,157 partial | 0 | 4,148 | 3,983 / 2,460 / 549 / 165 |
| VALIDATION | 5,859 partial | 0 | 3,613 | 3,493 / 1,982 / 264 / 120 |

Observed history days (min/median/max) were TRAIN `0/94/317` and VALIDATION `0/203/470`. All snapshots have partial usage coverage and none has complete recent-window coverage; missing usage was preserved as missing rather than converted to zero. These limits make the experiment unsuitable as evidence of reliable operational scoring.

The stored reliability/freshness assessments in `member2-prep-v4` predate the Prompt 27 correction to unknown connectivity handling and were not recomputed here. They are shown only as historical stored metadata: TRAIN reliability 6,935 insufficient / 222 limited and freshness 6,935 stale / 222 partially stale; VALIDATION 5,708 / 151 and 5,708 / 151 respectively. They must not be treated as corrected source-health findings. No reliability policy was relaxed.

## Fit and validation results

The existing `LightGBMModel.fit` / `LightGBMModel.predict` implementation was used with its fixed CPU defaults, seed 2026, tenant scope `tenant-01`, `features_personalized_baseline_v1`, and label policy `effective-account-churn-v1.2`. Validation early stopping, hyperparameter search, threshold selection, and calibration were not performed. The model fit masks included only mature positive/negative TRAIN labels; inference and descriptive metrics used only mature positive/negative VALIDATION rows.

| Horizon | Result | TRAIN rows (positive / negative; unique positive accounts) | VALIDATION rows (positive / negative; unique positive accounts) | PR-AUC (average precision) | ROC-AUC | Brier, uncalibrated |
|---|---|---:|---:|---:|---:|---:|
| 7d | Not fit — frozen support blocked | 6,416 (27 / 6,389; 27) | 5,166 (28 / 5,138; 28) | N/A | N/A | N/A |
| 14d | Fit; uncalibrated demo only | 6,069 (55 / 6,014; 29) | 4,829 (54 / 4,775; 30) | 0.011252 | 0.430971 | 0.011158 |
| 30d | Fit; uncalibrated demo only | 5,428 (131 / 5,297; 36) | 4,197 (113 / 4,084; 33) | 0.025993 | 0.498498 | 0.026834 |

These are actual **synthetic development-validation** metrics, not independent TEST results or real-world churn performance. They are uncalibrated and should not be compared to production baselines. The low discrimination values do not support a claim of useful predictive performance. No canonical `PredictionOutput` was created, and these raw scores must not be served or ranked as calibrated churn probabilities.

## Artifacts and reproduction

Private experiment output (outside Git):

`C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\experiments\prompt31-standard-tenant01-demo-v1`

- `models/horizon-14d.pkl` — SHA-256 `18aa32de48584192767316772fe68388ed080717322d6571c6861b528a2fa620`
- `models/horizon-30d.pkl` — SHA-256 `b5faf7b031814efdaf2755df50fd0d66483aef24d54ac27d166b47e570a40041`
- `validation_predictions.jsonl` — 9,026 customer-level uncalibrated scores, SHA-256 `6a3d3a45221b3df1b2f69167c4b2ced8bcbb5eb4240bbeafe709f2511c1ed734`
- `training_manifest.json` — aggregate run metadata, SHA-256 `cfbebcbc006f269121aed1fba56d7145af1425b517f2f5fd68c77f291ed6f93d`

The actual run took 39.37 seconds. Model artifacts were reloaded with the existing trusted-root loader, then used to infer every mature VALIDATION row; the model-loading/inference smoke passed. The output manifest records model/feature/label versions, row counts, metrics, input/output digests, runtime versions, and the `SYNTHETIC_DEMO_ONLY` / `production_readiness=BLOCKED` status. Do not commit the private model or customer-level prediction file.

Reproduce into a **new, nonexistent** output directory (the script refuses to overwrite):

```powershell
& .\.venv\Scripts\python.exe -B -m examples.member2_standard_synthetic_demo_training `
  --prepared-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\prepared\synthetic-saas-v1-2-standard-s2026-970a9d231e68\tenant-01\member2-prep-v4' `
  --output-dir 'C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\experiments\prompt31-standard-tenant01-demo-v2'
```

Runtime used: Python 3.14.4, LightGBM 4.7.0, scikit-learn 1.9.1, NumPy 2.5.3. The script loads only the TRAIN/VALIDATION feature and label files. Its `LightGBMModel` outputs are explicitly `uncalibrated_probability` scores. The complete `PredictionPipeline.run` contract remains unavailable because the 7d model and supported calibration bundle do not exist.

## Verification and downstream handoff

- `tests/test_member2_standard_synthetic_demo_training.py`, `tests/test_lightgbm_model.py`, `tests/test_candidate_training.py`, and `tests/test_temporal_splits.py`: **47 passed**.
- Actual experiment: two horizon fits succeeded; saved-artifact reload and mature VALIDATION inference succeeded; 7d was skipped by frozen support; TEST and CALIBRATION row artifacts were not opened.
- Existing production readiness gates remain **BLOCKED**. No test-suite-wide run was repeated.

Member 3/4 may inspect the schema/versioning conventions, but must treat these artifacts as isolated synthetic demo material and must not consume the raw scores as canonical predictions. A complete authorized dataset, adequate per-horizon support including CALIBRATION, credible feature coverage, calibrated models, and independent evaluation are still required before a production bundle or forecast handoff.
