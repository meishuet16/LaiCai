# Member 2 — Prediction Engine Integration Dependencies

Status: Member 2 contracts and local implementations exist; real integration and
production readiness remain blocked by Member 1/backend evidence and unresolved
team policies. This document is a dependency summary, not a claim that external
systems are implemented.

The complete requirements are the preferred integrated specification. Items marked **proposed** still require team agreement before implementation.

## 1. Expected from Member 1 — Data Foundation

Member 2 requires tenant-scoped, point-in-time data through the canonical Part 1 interfaces:

- Paying account identity: `tenant_id`, stable `customer_id`, and subscription mapping.
- Subscription lifecycle history sufficient to reconstruct status, price, cancellation requests, expiry, and effective termination at any `as_of` cutoff.
- Usage and billing events with event type, `occurred_at`, and true historical availability (`received_at` or a trusted source-availability timestamp).
- Versioned feature-snapshot inputs containing `as_of`, `feature_version`, data cutoff, values, and data-quality/coverage flags.
- Churn-label inputs with horizon, outcome timestamp, observation-through timestamp, label policy version, and `1/0/unknown` semantics.
- Authenticated tenant context; Member 2 must not accept a client-supplied tenant ID.
- Historical import/replay through the same canonical event semantics as live ingestion.

Part 1 must also provide the dataset provenance, source permission/license, schema mapping, censoring limitations, and any documented availability assumptions.

## 2. Member 2 output to Member 3

Member 2 will provide one immutable account forecast snapshot per cutoff with:

```text
tenant_id, customer_id, prediction_id, prediction_run_id,
as_of, generated_at, status,
p_churn_7d, p_churn_14d, p_churn_30d,
feature_version, model_version, calibration_version,
reliability, data_freshness, uncertainty,
explanations_by_horizon
```

Confirmed status rules:

- `status`: `scored`, `abstained`, `known_cancellation`, or `not_eligible`.
- Scored probabilities are calibrated cumulative values in `[0,1]` with `p7 <= p14 <= p30`.
- Non-scored statuses have null probabilities.
- Reliability is a reasoned applicability/data-quality status, not a confidence percentage.
- Uncertainty remains `not_quantified` unless a defensible validated method is implemented.
- Explanations are model attributions and associations, not causal action evidence.

Member 3 may join this payload with Part 1 MRR, currency, and business constraints. Member 2 does not own routing, action selection, ROI, budget, or approval logic.

## 3. Member 2 output to Member 4

Member 2 will provide:

- Stable `prediction_id` linkage to the exact forecast, cutoff, versions, and original probabilities.
- Per-horizon prediction records that can be evaluated only after the relevant observation window matures.
- Prediction/model metadata needed for evaluation, candidate comparison, registry records, and rollback references.
- Reproducible evaluation artifacts including cohort definition, horizon, sample count, provenance, and metrics when evidence is sufficient.
- Retraining candidate inputs and readiness results; promotion remains an authorized Part 4 decision.

Member 4 owns feedback maturity, model-governance approval, dashboard presentation, and release/rollback decisions. Observed retention must not be interpreted as causal intervention success.

## 4. Dataset requirements for genuine forecasting

The dataset must contain, or defensibly reconstruct:

- Timestamped usage and/or billing activity.
- Dated subscription start, status, expiry/cancellation, and effective churn events.
- A defined account-level churn policy, including multi-subscription accounts.
- Sufficient history to create repeated point-in-time cutoffs per account.
- Complete follow-up coverage for valid 7-, 14-, and 30-day negative labels.
- Source availability timestamps, or a documented defensible assumption about availability.
- A reproducible mapping to the canonical Push API/event schema.
- Chronological train, development/validation, calibration, and untouched test windows.

A static final `Churn = Yes/No` table cannot support validated early-warning lead time or genuine multi-horizon labels. Synthetic data may verify pipeline mechanics only and must be labeled synthetic.

## 5. Unresolved contracts requiring team agreement

**Confirmed by the integrated requirements:**

- `prediction_id` identifies one account forecast snapshot; `prediction_run_id` identifies an inference batch.
- The canonical prediction payload uses flat `p_churn_7d`, `p_churn_14d`, and `p_churn_30d` fields.
- Known cancellations are excluded from prospective churn scoring.
- Prediction feedback is anchored at prediction `as_of`; operational action follow-up uses a separate action/follow-up anchor.

**Proposed or unresolved:**

- Exact account-level churn semantics when an account has multiple subscriptions: last paid subscription versus contract-specific churn.
- Canonical availability field and precedence between `received_at` and source-provided availability time.
- Part 1 ownership and materialization timing for `feature_snapshots` and `churn_labels`.
- Exact prediction uniqueness key and whether repeated scoring at the same cutoff is prevented or versioned by run.
- Shape and storage schema for `explanations_by_horizon` and attribution values.
- Reliability/freshness thresholds and policy versioning.
- Chronological split gaps/purging rules for overlapping 7/14/30-day labels.
- Minimum sample/evidence gates for evaluation and candidate retraining.
- Model artifact storage, serving runtime, and registry ownership.
- Feedback API naming: the detailed Part 4 document mentions `prediction_run_id` in one record example, while the integrated contract requires exact `prediction_id` linkage.

## 6. Current implementation blockers

- The repository contains no Member 1 production backend/database or authorized dataset. Member 2's local typed contracts, tests and model components are present, but they are not a production serving system.
- No authorized longitudinal dataset or `DATASET_CARD.md` exists.
- Member 1’s canonical schema, authentication boundary, replay path, and label policy are not implemented.
- No team-approved values exist for availability semantics, churn aggregation, split policy, reliability thresholds, or model-release gates.
- Part 2 cannot claim trained performance, lead time, calibration quality, or genuine replay results until the dataset and contracts are available.

## 7. Next handoff

Member 1 should provide the canonical data/API contract and dataset evidence gate. After that, Member 2 can implement time-safe features and labels first, followed by baselines, calibrated multi-horizon prediction, reliability/abstention, replay evaluation, and the Part 4 feedback/evaluation backend.
