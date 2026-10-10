# Member 2 Prompt 34 — Emergency Delivery Report

**Overall status: INCOMPLETE — Prompt 34 did not produce a prepared dataset or a Prompt 34 model bundle.** The authenticated synthetic source and SQLite import are preserved privately. No Prompt 34 model training, calibration, TEST evaluation, or replay result is claimed.

## Source artifacts and preparation attempts

The new source cohort was generated once and imported through Member 1's canonical importer. The frozen STANDARD cohort was not regenerated or reimported.

| Item | Observed value |
|---|---|
| Evidence type | `SYNTHETIC_ONLY`; fictional SaaS records |
| Dataset ID | `synthetic-saas-v1-2-prompt34_demo-s2034-316bec2deb46` |
| Dataset manifest SHA-256 | `75a687071f3fee639e3ce057b59404834accb2fc01ec39a7cb122cb9883e5aac` |
| Generator / seed | Synthetic SaaS v1.2 / `2034` |
| Tenant scope | One authorized synthetic tenant (`tenant-01`) |
| Accounts / canonical events / coverage records | 5,000 / 363,562 / 814,446 |
| Effective account-churn episodes / late-arriving events | 1,036 / 1,425 |
| Target policy | `effective-account-churn-v1.2` (synthetic-only) |
| Imported SQLite file | 884,641,792 bytes; importer previously returned `VERIFIED` |

The first historical preparation was stopped at the user's request at **45/73** weekly cutoffs (225,000 candidate account-cutoff checks; 71,156 historical snapshots; 65,383 eligible snapshots reported at that checkpoint). Those counts were in-memory progress only. The `prepared` directory contains **zero files**; no complete feature, label, split, or preparation-manifest artifact exists from that attempt.

A separately versioned reduced experiment was then started against the same existing source cohort and import. Its cutoff policy was fixed before label reads: evenly spaced weekly cutoffs by chronological index, **TRAIN 12, VALIDATION 5, CALIBRATION 4, TEST 4** (25 total). It reached **7/25** cutoffs (35,000 candidate checks; 6,682 historical snapshots; 6,381 eligible snapshots), then ended without finalized files or a retained exit diagnostic. Its private `prepared` directory is also empty. This partial progress is not a training dataset and is not reported as complete. The reason the worker ended is unverified.

The synthetic source export includes aggregate cohort label/support summaries, including TEST-stage aggregate counts. These are generator/preparation QA summaries, not held-out model metrics. No TEST row-label artifact, model score, or TEST evaluation was used for fitting, candidate ranking, threshold selection, or model evaluation in this task.

## Model, calibration, SHAP, and replay status

No model or calibrator was fitted from the Prompt 34 cohort. Consequently:

- Prompt 34 TRAIN/VALIDATION/CALIBRATION/TEST snapshot and label distributions are **unavailable**; the full 50-positive/50-negative and 20-accounts-per-class gates were not evaluated on finalized artifacts.
- There are no Prompt 34 validation comparisons, calibration results, held-out metrics, selected thresholds, or inference throughput figures.
- There are no Prompt 34 model-backed replay snapshots, database prediction writes, outcome reveals, or lead-time results.
- Prompt 34 scoring and production readiness remain **BLOCKED**. No horizon is marked ready for synthetic training or real-world use.

The repository's pre-existing Prompt 31 synthetic STANDARD 14d/30d LightGBM artifacts were used only for a model-loading/inference/SHAP smoke check with an explicitly synthetic `FeatureSnapshot` fixture. Both models loaded and returned raw **uncalibrated** scores; SHAP returned `available`, with additivity errors `5.329070518200751e-15` (14d) and `0.0` (30d). These are compatibility smoke results, not Prompt 34 model outputs or performance evidence. An all-missing fixture correctly produced `FEATURE_INPUT_MISSING`; it was replaced by a populated synthetic fixture for the passing smoke check. No 7d model or calibrator was exercised.

The demonstration code now provides a reduced predeclared preparation path, three-horizon training/calibration, development comparisons, TEST-prediction persistence-before-label-read, SHAP checks, and T1/T2 replay. VALIDATION comparisons use raw model scores only; parameters fitted on the later CALIBRATION partition are not applied backward to VALIDATION. The reduced preparation command was not completed, so the end-to-end code path remains unverified on Prompt 34 data.

Replay code clones the imported SQLite file into a private replay database before writing predictions, so a successful replay can leave the imported source copy's event data untouched. The Member 1 writer currently stores a restricted prediction projection; full SHAP attributions and free-form reliability reasons remain in the private immutable prediction snapshot artifact. Replay history/read-after-write in this demo uses a tenant-scoped process mirror because Member 1 does not yet expose the required authenticated prediction history reader. Neither the clone nor replay writer was exercised in this attempt.

## Verification actually completed

Repository-local environment: Python `3.14.4`, LightGBM `4.7.0`, scikit-learn `1.9.1`, SHAP `0.53.0`, NumPy `2.5.3`, Pydantic `2.14.0`.

| Command/check | Result |
|---|---|
| `python -B -m py_compile examples/member2_prompt34_demo.py src/retainiq_prediction/historical_dataset_preparation.py tests/test_member2_prompt34_demo.py` | PASS |
| Focused pytest batch: Prompt 34, calibration, explainability, prediction pipeline, operational inference, historical evaluation | PASS — 79 passed, 0 failed, 0 errors, 0 skipped; 24 existing SHAP output-shape warnings, unsuppressed |
| Prompt 34 focused module (`tests/test_member2_prompt34_demo.py`) | PASS — 9 passed |
| Repository-local imports for the preparation and Prompt 34 modules | PASS |
| Existing model load + synthetic-fixture inference/SHAP smoke | PASS — two pre-existing uncalibrated models; additivity results above |
| `git diff --check` | PASS (line-ending conversion warning only) |
| Full repository pytest suite | NOT RUN — emergency scope requested one focused batch; the incomplete preparation also blocks end-to-end model tests |

No private customer-level records, model artifacts, or prediction outputs were added to Git. Peak preparation memory and reader-call count for the interrupted runs were not finalized/captured. No Prompt 34 preparation duration or throughput is claimed.

## Remaining blockers and safe next step

1. A completed authenticated preparation run is required before any Prompt 34 fit. The interrupted reduced root is preserved and must not be treated as resumable. If another attempt is authorized, use a new versioned private root (for example `prompt34-three-horizon-reduced-v2`); do not regenerate or reimport the source cohort.
2. Keep the fixed support gates unchanged. If any horizon/stage fails them, mark that horizon blocked rather than lowering thresholds or selecting cutoff dates by outcomes.
3. Member 1 still needs an authenticated prediction lookup/history API for durable replay idempotency/readback. The current writer rejects full SHAP/reliability-reason details, and the historical Push API does not accept trusted source-availability timestamps; the implemented replay uses the authenticated source reader and existing canonical writer instead.
4. Evidence is synthetic-only. A real authorized longitudinal dataset, verified outcome coverage, and approved account-level churn policy are still required before production readiness or any real-world claim.

Reproduction entry points in a fresh private output root:

```powershell
.\.venv\Scripts\python.exe -B -m examples.member2_prompt34_demo prepare-reduced --root "$env:USERPROFILE\RetainIQ-private\prompt34-three-horizon-reduced-v2"
.\.venv\Scripts\python.exe -B -m examples.member2_prompt34_demo train --root "$env:USERPROFILE\RetainIQ-private\prompt34-three-horizon-reduced-v2"
.\.venv\Scripts\python.exe -B -m examples.member2_prompt34_demo replay --root "$env:USERPROFILE\RetainIQ-private\prompt34-three-horizon-reduced-v2"
```

These are future commands, not completed results. The preparation command reuses the existing Prompt 34 dataset and imported database; it does not generate or import STANDARD data.
