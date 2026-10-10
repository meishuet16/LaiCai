# Member 2 Retraining Governance

This document defines the evidence gates and metadata registry for a future
RetainIQ candidate-model retraining workflow. It does not train, calibrate,
promote, deploy, schedule, or persist model artifacts.

## Readiness gate

`RetrainingReadinessAssessor` accepts the existing `DatasetReadinessReport`,
`TemporalSplitResult`, reconciled prediction feedback, and an explicit
`RetrainingReadinessConfig`. It returns a frozen `RetrainingReadinessReport`
with an overall status:

- `BLOCKED`: no authorized real dataset, missing temporal split, or equivalent
  foundational evidence is available.
- `NOT_READY`: the evidence exists but one or more horizons fail maturity,
  version, class-balance, sample, coverage, or policy checks.
- `READY_FOR_CANDIDATE_TRAINING`: all configured horizon gates pass. This is
  permission to propose a candidate training run, not permission to deploy it.

The dataset must be explicitly `PASS`, eligible for genuine training, and
provenanced as authorized real data. Synthetic fixtures can exercise structure
only and cannot make a candidate trainable or approvable.

## Evidence and leakage controls

Only reconciled mature positive or negative feedback is considered. The
outcome evidence, evaluation cutoff, reconciliation timestamp, prediction
cutoff, label policy, feature version, tenant scope, and temporal split must
agree with the readiness configuration. Pending, incomplete, ineligible,
unsupported, conflicting, unresolved-policy, late, or insufficiently sourced
outcomes are excluded per horizon and recorded by reason code.

Training candidates are linked only to snapshots in the TRAIN partition. The
VALIDATION, CALIBRATION, and TEST partitions are never used for candidate
training or model-selection evidence. A final TEST label may mature later for
evaluation, but it cannot be admitted to readiness for training.

The assessor checks point-in-time feature cutoff validity and the existing
label/outcome availability policy. It does not redefine churn or create a
feature matrix. Repeated account snapshots remain time-forward observations;
the report warns that this does not establish generalization to entirely new
customers.

## Horizon and selection gates

7-, 14-, and 30-day outcomes have independent inclusion masks. Unknown labels
are never converted to zero. Each horizon must meet configured minimum total,
positive, and negative counts and contain both classes. Selection coverage,
abstained/scored representation, intervention exposure, and non-causal outcome
limitations are surfaced as warnings; a deployment policy may require complete
selection coverage before readiness.

## Model version registry

`ModelBundleMetadata` is immutable metadata for one candidate bundle. It
records:

- one model version and calibration version for each of 7/14/30 days;
- feature, label-policy, split-policy, training-configuration, and evaluation
  policy versions;
- dataset provenance reference, training freeze cutoff, artifact references,
  tenant scope, and readiness fingerprint;
- lifecycle status and explicit provenance.

`ModelRegistry` is an in-memory, replaceable metadata registry. It does not
load pickle, joblib, or other untrusted artifacts and does not create a
database. Candidate registration is idempotent only for identical metadata;
conflicting candidate or bundle identities are rejected.

The lifecycle is explicit:

`PROPOSED` -> `ELIGIBLE_FOR_TRAINING` -> `TRAINED_PENDING_EVALUATION` ->
`EVALUATED_PENDING_APPROVAL` -> `APPROVED` -> `RETIRED`.

Blocked and rejected transitions are explicit. Eligibility requires a passing
readiness report and authorized real provenance. Training/evaluation steps
require an evidence note. Approval requires a human approval record,
independent test evaluation, authorized real provenance, and artifact
references. Registering an approved active bundle is a separate explicit
operation, and an existing active bundle cannot be replaced by this module.
There is no automatic promotion, rollback execution, or production mutation.

## Required future integrations

Member 1 must provide authorized dataset provenance, complete historical
availability evidence, stable feature/label/version identifiers, authoritative
tenant scope, and the account-level churn policy. Member 4 must provide the
operational feedback/outcome coverage needed to detect selection and
intervention bias. Member 3 consumes stable model/calibration versions and
prediction contracts but is not changed here.

The real workflow remains blocked until an authorized longitudinal dataset,
complete outcome reconciliation, agreed account-level churn semantics, and
independently reviewed model/evaluation artifacts are available. No empirical
performance or retraining readiness is claimed by the synthetic tests.

See `docs/MEMBER2_IMPROVEMENT_BACKLOG.md` for pending validation work,
including the historical evaluation coverage audit and personalized-baseline
ablation study.
