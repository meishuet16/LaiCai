# Member 2 Candidate Training and Evaluation

This milestone adds a controlled candidate workflow. It is not an automatic
retraining, deployment, promotion, rollback, API, or dashboard system.

## Architecture

`train_candidate` coordinates the existing `TemporalSplitResult`,
`LightGBMModel`, and `ProbabilityCalibrator` implementations. It does not
duplicate feature vectorization, model fitting, calibration, or historical
metric calculations.

The real candidate path requires:

- `DatasetReadinessReport.status == PASS` and
  `eligible_for_genuine_training == true`;
- `REAL_AUTHORIZED` dataset provenance;
- a `RetrainingReadinessReport` with
  `READY_FOR_CANDIDATE_TRAINING`;
- an explicit timezone-aware training freeze equal to the configured TRAIN
  boundary;
- compatible dataset, split, feature, label-policy, tenant and point-in-time
  evidence.

Missing, synthetic, unverified, contradictory, immature, single-class or
insufficient evidence returns `BLOCKED` or `NOT_READY` without a production
candidate.

## Chronological isolation

Each of 7, 14 and 30 days is fitted independently:

- TRAIN snapshots and the existing maturity-aware supervised mask fit the
  LightGBM classifier.
- VALIDATION may be supplied only to the existing optional early-stopping
  path. It is not TEST data.
- CALIBRATION snapshots and their horizon-specific mature masks fit the
  corresponding sigmoid calibrator only.
- TEST is never read by candidate training.

The coordinator preserves the existing feature allowlist and preprocessing
metadata. Outcome feedback, churn timestamps, cancellation requests and
prediction probabilities are not added as model features. Unknown labels are
never converted to zero. All three horizon models and calibrators must be
ready before a candidate result is returned as trained.

The candidate metadata contains one model and calibration version per horizon,
the freeze cutoff, dataset provenance, feature/label/split/evaluation policy
versions, and synthetic status. Artifacts remain in memory in this milestone;
no active bundle is changed.

## Synthetic execution

`CandidateTrainingMode.SYNTHETIC_TEST_ONLY` is a separate explicit path. It
requires synthetic provenance and a synthetic dataset reference, then runs the
actual LightGBM and sigmoid calibration code for structural tests. Its result
is `SYNTHETIC_ONLY`, `production_eligible == false`, and carries the synthetic
provenance into metadata and warnings. Synthetic artifacts cannot satisfy the
real readiness gate or become production-approved through this module.

Synthetic fitting demonstrates code execution only. It is not a real dataset,
does not establish predictive performance, and does not justify a release.

## TEST freeze and evaluation gate

`CandidateEvaluationGate.freeze_candidate` accepts only a candidate in
`TRAINED_PENDING_EVALUATION` state. It records an immutable
`FrozenTestEvaluationManifest` containing candidate identity, model/calibration
references, feature and label versions, split and evaluation policy versions,
freeze cutoffs, authorization reference and a sealed TEST status.

Final evaluation requires the unchanged candidate metadata and unchanged
evaluation configuration. A candidate mutation, configuration change,
selection-oriented TEST call, missing authorization, non-untouched TEST set,
or repeated TEST access is blocked. The gate allows one final TEST access per
gate instance; TEST is not used for fitting, tuning, calibration or selecting
among candidates.

The existing `HistoricalEvaluator` computes PR-AUC, ROC-AUC where defined,
Brier score, Recall@K, Precision@K, coverage, abstention, calibration bins,
horizon audits and model-cohort comparisons. The wrapper reports each horizon
separately and requires configured mature samples and metric definitions. It
does not merge horizon metrics or calculate causal intervention effectiveness.

`ELIGIBLE_FOR_HUMAN_REVIEW` means that evidence is sufficient for an operator
review only. It is not `APPROVED`, `PROMOTED`, or `DEPLOYED`. Synthetic reports
remain `EVALUATED_NOT_APPROVABLE`; missing champions, cohort mismatch,
undefined metrics and insufficient denominators remain explicit limitations.

Candidate and champion comparisons use the same TEST partition, evaluation
cutoff, label policy and review capacity K. Coverage differences are retained
instead of hidden. No candidate is selected solely because one metric moves
slightly, and no improvement claim is generated automatically.

## Registry lifecycle

Training may register immutable `PROPOSED` metadata. Evaluation can explicitly
record `EVALUATED_PENDING_APPROVAL` with evidence, but does not approve or
mutate the active bundle. Existing registry rules still require independent
human approval, authorized real provenance and artifact references before
approval. Synthetic candidates cannot pass those approval checks.

The registry is metadata-only and in-memory here. Artifact loading, storage,
deployment, rollback execution, scheduling and restricted approval APIs remain
future integration responsibilities.

## Feedback and selection limitations

Only mature, verified, policy-compatible outcomes may enter a future training
readiness report. Historical feedback can over-represent previously scored
customers, omit abstained customers, reflect intervention selection, have
missing follow-up, and repeat the same account across cutoffs. These are
reported limitations, not causal treatment labels. The personalized-baseline
ablation in `IMPROVEMENT-001` remains pending and is not implemented here.

## Current blockers and ownership

Real training and TEST evaluation remain blocked in this repository because no
authorized longitudinal dataset or PASS-provenance model evidence exists.
Member 1 must provide canonical source availability, mature lifecycle outcomes,
correction history, tenant/account identity, dataset authorization and the
resolved account-level multi-subscription churn policy. Member 3 consumes the
stable prediction/model versions and must not rewrite probabilities. Member 4
owns operational feedback persistence, human review evidence, approval and
dashboard integration.

No real performance, uplift, saved revenue, ROI, or production-readiness claim
is made by the synthetic tests.

## Windows pytest verification

The standard command was tested. On this workstation, five tests using
`tmp_path` failed during setup because the default Windows root
`C:\Users\User\AppData\Local\Temp\pytest-of-User` returned `WinError 5`
permission denied. This is an environment/temp-root permission issue, not a
skipped test or suppressed fixture.

The reproducible repository-local command is:

```powershell
& .venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-p18
```

`.pytest-tmp/` is ignored by Git. The Prompt 18 verification uses a unique
repository-local basetemp and removes it after the run.
