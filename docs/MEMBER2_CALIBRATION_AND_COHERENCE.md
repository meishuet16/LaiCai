# Member 2 Calibration and Horizon Coherence

## Scope and evidence boundary

This document describes the post-model probability layer in
`src/retainiq_prediction/calibration.py` and
`src/retainiq_prediction/horizon_coherence.py`. It is an internal training and
evaluation foundation. It does not change the canonical `PredictionOutput`,
serve an API, produce SHAP explanations, select alert thresholds, or claim
predictive performance.

The repository still has no authorized longitudinal dataset. All current tests
use synthetic fixtures, so a successful fit or coherence adjustment is only a
structural implementation check.

## Independent calibration

Each horizon has its own calibrator. `ProbabilityCalibrator.fit` accepts one
fitted LightGBM model and one `TemporalSplitResult`, then reads only that
horizon's supervised mask in the `CALIBRATION` partition. The mask must already
exclude unknown, excluded, unsupported, ineligible, and immature labels. The
`VALIDATION` and `TEST` partitions are never read for fitting.

The current method is sigmoid/Platt calibration implemented as logistic
regression over the model probability's logit. The input convention is recorded
as `raw_probability_logit_once`: raw LightGBM probabilities are clipped only at
the configured numerical epsilon, transformed to a logit once for fitting and
once for application, and are never logit-transformed twice. Each successful
artifact records:

- calibration and model versions;
- horizon, feature version, and label-policy version;
- calibration cutoff and mature sample/class counts;
- configuration, dependency versions, dataset provenance/status; and
- empirical-validation status, which remains `BLOCKED` until real evaluation is
  performed.

Fitting requires minimum total, positive, and negative sample counts. A
single-class or insufficient horizon returns `NOT_READY`; no labels are
converted from unknown to zero. Calibrated values are finite and bounded in
`[0, 1]`.

## Artifact safety and compatibility

Calibration artifacts are versioned internal pickle files. Loading requires a
caller-supplied trusted root, the `.pkl` extension, the expected artifact type
and version, a compatible `CalibrationConfig`, fitted state, and metadata. This
is not an arbitrary-upload mechanism: pickle remains executable serialization
and must only be loaded from a trusted internal artifact location.

The model and calibrator must agree on model version, horizon, feature version,
and label-policy version. The real dataset status must be `PASS` before an
artifact can participate in production readiness. Synthetic fixtures retain
`BLOCKED` status even when the numerical fit succeeds.

## Diagnostics

`evaluate_probability_diagnostics` is a read-only comparison hook. It ignores
labels that are not confirmed mature positive or negative outcomes and reports
raw and calibrated Brier scores, plus an optional post-coherence adjusted Brier
score. It also returns a five-bin calibration table for calibrated
probabilities. The hook does not tune a model, recalibrate an artifact, inspect
the TEST partition during fitting, or turn diagnostics into performance claims.

The future evaluation protocol must reserve TEST until all model fitting,
preprocessing fitting, hyperparameter selection, calibration, and coherence
policy decisions are complete. Post-adjustment diagnostics should be reported
on the same frozen chronological cohorts for raw, calibrated, and adjusted
values.

## Horizon coherence

Independent calibration can produce values that violate the cumulative
relationship `p_churn_7d <= p_churn_14d <= p_churn_30d`. The coherence layer
requires all three finite, bounded values and preserves the originals. Its
current explicit policy is cumulative maximum:

```text
adjusted_7  = original_7
adjusted_14 = max(original_7, original_14)
adjusted_30 = max(original_7, original_14, original_30)
```

The result records whether an adjustment occurred, the method version, all
compatible model/calibration/feature/label metadata, and the limitation that
ordering correction can change calibration properties. A missing horizon,
invalid probability, duplicate horizon, or incompatible metadata is rejected;
the layer never silently fills a missing forecast.

The readiness helper requires all three model/calibrator pairs, compatible
metadata, and `DatasetStatus.PASS` for the training evidence. It is a readiness
signal, not a promotion decision, and it does not alter `PredictionOutput`.

## Member 1 integration dependencies and blockers

Member 1 must provide the real historical adapter and dataset evidence needed
by the existing temporal splitter and label builder:

- tenant/account-scoped feature snapshots with point-in-time availability;
- canonical lifecycle and billing outcome mappings;
- event occurrence and source availability/received timestamps;
- complete observation coverage for negative labels;
- stable feature and label-policy versions;
- source provenance, authorization, and correction/conflict handling; and
- the agreed account-level policy for multiple subscriptions.

Until those inputs and an authorized longitudinal dataset are available, real
calibration readiness remains `BLOCKED`. No production artifact, empirical
calibration metric, or model comparison should be inferred from the synthetic
tests.
