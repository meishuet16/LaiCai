# Member 2 Temporal Splitting

## Scope

This module prepares historical feature snapshots and churn labels for later
model development. It does not train models, fit preprocessing, select
thresholds, calibrate probabilities, or expose an API.

The implementation is in
`src/retainiq_prediction/temporal_splits.py`. It consumes a
`SnapshotRecord`, which couples one `FeatureSnapshot` at an `as_of` cutoff
with its available 7-, 14-, and 30-day `ChurnLabel` records.

## Chronological partitions

`TemporalSplitBoundaries` supplies explicit timezone-aware boundaries. The
splitter uses half-open intervals:

- TRAIN: `[train_start, train_end)`
- VALIDATION: `[train_end, validation_end)`
- CALIBRATION: `[validation_end, calibration_end)`
- TEST: `[calibration_end, test_end)` (or through the supplied data when
  `test_end` is omitted)

Each snapshot is assigned once using its prediction `as_of`. The three horizon
labels attached to a snapshot cannot be split apart. Input order does not
affect the result; output snapshots are sorted by `as_of`, account key, and a
stable snapshot identifier. Duplicate snapshot identifiers are rejected.

No split dates are invented by the implementation. The current repository has
no authorized longitudinal dataset, so real training readiness remains
`BLOCKED` even when synthetic records exercise the structure.

## Label maturity and leakage prevention

For TRAIN, VALIDATION, and CALIBRATION, a label enters that partition's
horizon-specific supervised mask only when all of the following hold:

1. The snapshot was eligible at its original `as_of`.
2. The label is explicitly `POSITIVE` or `NEGATIVE` with a value of `1` or
   `0`.
3. `label.evaluation_as_of` is no later than that partition's model-development
   freeze (`train_end`, `validation_end`, or `calibration_end`) minus the
   configured `maturity_gap`.

This maturity rule is an availability gate, not a new churn definition. It
prevents a late-completing 30-day negative label from entering training merely
because its prediction snapshot was in the training period. Unknown,
excluded, unsupported, missing, or immature labels are never converted to
zero. Counts for each exclusion class are retained in the split manifest.

The optional `maturity_gap` is an explicit purging/embargo control. It can
reserve time between outcome observation and a partition freeze when the team
needs additional protection from delayed corrections or operational lag.

TEST has no supervised fitting mask. Confirmed test labels are exposed only in
the evaluation mask, including labels revealed after the test period; deferred
test labels are counted in the manifest. They must not be used for training,
preprocessing fitting, hyperparameter tuning, threshold selection, or
calibration.

## Horizon-specific behavior

The splitter evaluates 7-, 14-, and 30-day labels independently. A mature
7-day label does not make the 14- or 30-day label usable. Each horizon gets
separate supervised and evaluation identifiers, usable counts, unknown/
excluded/unsupported counts, and maturity exclusions. The manifest reports
warnings when a partition has too few usable labels or only one usable class.

## Repeated accounts

The same tenant/customer may have multiple historical snapshots. These are
allowed because the intended task is time-forward forecasting for existing
accounts. They remain in their chronological partitions and are not randomly
split. The manifest reports pairwise account overlap between partitions.

Overlap means the temporal evaluation does not establish generalization to
completely unseen customers. Feature construction and the point-in-time
adapter remain responsible for preventing future feature values from flowing
back into an earlier snapshot.

## Reproducibility and readiness

`TemporalSplitManifest` records the dataset identifier, policy version,
serialized boundaries, maturity gap, minimum sample configuration,
horizon-specific counts, overlap summary, warnings, and readiness status. The
same records and configuration produce the same ordered partitions and
manifest.

The readiness status is `BLOCKED` unless the caller explicitly declares an
authorized dataset. Declaring authorization only removes this module's
missing-dataset block; it does not claim that coverage, lifecycle evidence,
label quality, or sample sufficiency has passed the broader readiness review.

## Member 1 dependencies

The real adapter and dataset pipeline must provide:

- tenant and customer identity for every snapshot;
- a timezone-aware prediction `as_of` and the point-in-time-safe
  `FeatureSnapshot`;
- one explicit label record per supported horizon, or an explicit missing/
  unknown result;
- `label_status`, `label`, `evaluation_as_of`, observation/availability
  evidence, and source evidence references;
- canonical lifecycle and account-level churn semantics, including the
  multiple-subscription policy;
- correction/late-arrival handling sufficient to establish when outcome
  evidence was actually available.

`prediction_eligible` must be derived from the existing eligibility component.
The splitter does not create a database schema or replace Member 1's storage,
authorization, or ingestion contracts.

