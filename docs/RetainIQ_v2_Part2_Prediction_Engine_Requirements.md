# RetainIQ v2 — Part 2: Prediction Engine Requirements

**Status:** Implementation specification (Hackathon MVP)  
**Track:** Predictive Model — Predict Early, Decide Better  
**Owner:** Part 2  
**Dependencies:** Part 1 Data Foundation  
**Downstream consumer:** Part 3 Decision Engine

## 1. Purpose and Scope

Predict **whether and how soon an eligible active subscription account will churn**, using only information available at the prediction cutoff. The engine must provide calibrated cumulative probabilities for **7, 14, and 30 days**, customer-relative behavioral evidence, horizon-specific explanations, and a transparent prediction-reliability status. It must be evaluated for earlier useful warning versus conventional baselines.

**Signature capability:** Personalized Multi-Horizon Churn Foresight — customer-specific behavioral deviations combined with time-horizon forecasts and evidence-aware warnings.

**Not in Part 2:** pricing or discount selection, next-best action, budget optimization, retained-revenue claims, intervention effectiveness, or post-intervention learning. These belong to Part 3.

## 2. Definitions and Prediction Population

- **Unit of prediction:** a subscription account, not an individual app user. Multiple end users may belong to one account.
- **Prediction cutoff (`as_of`):** timestamp at which all allowed input evidence is frozen.
- **7/14/30-day probability:** cumulative probability that a qualifying churn event occurs by the end of that horizon, conditional on being eligible at `as_of`.
- **Churn event:** effective loss of subscription service due to voluntary cancellation, non-renewal at expiry, or finalized involuntary termination after failed collections. A payment failure alone is a feature, **not** churn.
- **Known/pending cancellation:** if a cancellation request or scheduled termination is known at `as_of`, exclude the account from prospective churn scoring; route to a distinct `known_cancellation` status. Do not use pending-cancellation status as a predictive feature.
- **Eligible:** currently active subscription, no known cancellation pending at cutoff, and sufficient identity and subscription evidence to establish status.
- **Unobservable outcome:** if the full future horizon is not observable, label that horizon `unknown` rather than negative. Account for right censoring.

Prediction thresholds and exclusions must be versioned and consistent between training, replay, and live inference.

## 3. Part 1 Input Contract

Consume canonical, tenant-scoped historical and incremental data:

| Entity | Required fields | Usage |
|---|---|---|
| Account/subscription | `tenant_id`, `customer_id`, `subscription_id`, status, start/end/effective cancellation timestamps | Eligibility and labels |
| Usage events | account mapping, event type, `occurred_at`, ingestion/availability timestamp | Engagement features |
| Billing events | event type/status, event timestamp, availability timestamp | Payment-history features |
| Optional support | ticket status/severity and timestamps | Support features only if present in historical and live data |
| Feature snapshot | `tenant_id`, `customer_id`, `as_of`, `feature_version`, feature values, data-quality flags | Reproducible model input |

Use **event-time plus data-availability time**: no feature can include events that happened **or became available** after `as_of`. Store data-source coverage and missingness. The financial fields (`amount`, `currency`, `billing_interval`, normalized `mrr`) belong to Part 1 and are available to Part 3; MRR is not required as an input to the primary churn model.

### Dataset acceptance gate

Before building the multi-horizon model, verify that the selected authorized historical dataset has reliable dated account events, churn-effective dates, and sufficient observation history to create multiple cutoffs per account. A static customer table with only a final `Churn=Yes/No` cannot support validated early-warning lead time or genuine multi-horizon labels. Stripe Test Mode is for integration testing, **not** a substitute for historical labeled training data.

If the dataset does not meet the gate, explicitly mark unsupported features as unvalidated and do not fabricate timestamps, outcomes, support events, or model metrics.

## 4. Prediction Pipeline

### 4.1 Point-in-Time Feature Builder

For each eligible `(tenant_id, customer_id, as_of)` snapshot calculate, where supported:

| Feature family | Examples |
|---|---|
| Current usage | Sessions in the previous 7/30 days, days since last activity |
| Customer-relative usage | Prior baseline (e.g., earlier 4–8 complete weeks), recent-to-baseline ratio, absolute and percentage deviation |
| Usage stability | Prior-week variability; change relative to expected periodic behavior |
| Billing | Payment failures in prior 30 days, days overdue, earlier recovery events |
| Subscription | Tenure, billing interval, plan tenure |
| Support, optional | Prior unresolved tickets and recent ticket count |
| Data sufficiency | Observed history length, data gaps, missing source flags, last available data time |

**Personalized baseline rules:** calculate baseline strictly from an earlier, non-overlapping window; exclude the recent comparison window. Avoid division by zero. For new or sparse customers use a cohort baseline or mark insufficient personal history, and include a corresponding missingness indicator. Never treat missing history as zero usage. Define event semantics (login is not automatically a session).

### 4.2 Horizon Labels

Create **three target labels** at each cutoff: qualifying churn within 7, 14, and 30 days. For an observed churn date within a horizon set `1`; for fully observed churn-free horizons set `0`; otherwise `unknown` and exclude from supervised loss for that horizon. Do not generate examples after known cancellation or after churn.

### 4.3 Baselines and Primary Model

- **Rule baseline:** transparent inactivity/payment heuristic. Thresholds selected on development data only.
- **ML baseline:** logistic regression with consistent preprocessing.
- **Primary candidate:** LightGBM binary classifiers trained separately for 7, 14, and 30 days on point-in-time features.
- **Selection criterion:** out-of-time test performance, calibration, lead-time/alert-budget utility, model stability, and operational cost. LightGBM is a candidate, not a guaranteed winner.

Train preprocessing only on training data. Account for class imbalance; do not select a model by accuracy alone. Tune hyperparameters on a development time window, not the final test period.

### 4.4 Calibration and Horizon Coherence

Use a distinct chronological calibration period to calibrate each horizon (e.g., sigmoid or isotonic with sufficient samples). Enforce cumulative consistency:

`0 <= P(churn by 7d) <= P(churn by 14d) <= P(churn by 30d) <= 1`.

If independent calibrated models violate ordering, apply an explicit monotonic adjustment or evaluate a discrete-time survival alternative; **reassess calibration and discrimination after adjustment**. Do not derive 7/14-day probabilities by arbitrarily scaling a 30-day score.

### 4.5 Horizon-Specific Explanations

Use LightGBM feature-attribution tooling (e.g., TreeSHAP) to identify the leading contributors to each horizon's model output. Present top positive and negative drivers, feature values and relevant personal baseline evidence. Attributions describe **model associations**, not proven causes or intervention effects. If a different model is selected, use compatible explanation tooling.

### 4.6 Prediction Reliability Gate

Report a clear reason-based status:

- `sufficient_evidence`: required sources available, reasonable historical coverage, no blocking validation issue.
- `limited_evidence`: scoring allowed, but short history, stale/missing optional source, or out-of-distribution features are flagged.
- `insufficient_evidence`: eligibility, key data, or model applicability cannot be established; **abstain** from displaying a numeric forecast.

This is a **data/applicability quality status, not a statistically calibrated confidence percentage**. Validate the reliability policy on held-out data, including performance by coverage group. Show model-wide calibration in technical metrics, not an invented individual certainty score.

### 4.7 Early Warning and Historical Risk Evolution

Persist dated predictions. At each replay or production cutoff, calculate forecast changes from previous **real model-generated predictions**, and flag emerging risk only under a versioned alert policy (threshold, upward movement, minimum data quality, cooldown). Full-account refresh must still occur daily to capture customers with **no new usage events**. Event-triggered reprediction is additional, not a substitute.

A curve of historical predictions must not be labeled a forecast of future risk trajectory. Forecast horizons describe cumulative event probabilities from the current cutoff.

## 5. Evaluation: Prove Predictive Value

### Split protocol

Use chronological train, tuning/validation, calibration, and **untouched final test** periods. Respect label maturation: a cutoff in a preceding split whose 30-day outcome overlaps the next split cannot be treated as if it was known at training time. Document temporal gaps/purging rules, repeated account observations, and any cross-tenant generalization assumptions.

### Required reporting

| Evaluation | Requirement |
|---|---|
| Per-horizon prediction | PR-AUC, ROC-AUC, Brier score, calibration plot or table, sample size and churn prevalence for 7/14/30d |
| Operational ranking | Recall@Top-K or recall at a fixed weekly alert budget |
| Early warning | First-alert lead time before observed churn, warning coverage, false alerts, and alerts per period |
| Personalization ablation | Primary model with vs. without customer-relative baseline features |
| Fair comparison | Identical held-out replay data, cutoffs, alert budget, eligibility, and outcome definitions for rule, logistic, and full engine |
| Reliability | Abstention/limited-evidence share and performance by reliability group |
| Engineering | Inference latency, run reproducibility, data leakage checks |

**Critical:** longer lead time alone is not proof of superiority. Report alert volume and false-positive trade-offs. Pick alert thresholds on development data; freeze them before final testing. Do not report an example such as "Day 19 versus Day 34" unless computed by the actual replay pipeline with verifiable prediction and event timestamps.

## 6. Historical Replay Demo — One Dataset, One Schema

Use a held-out chronological segment from the **same dataset family and canonical schema** used in training. Stream its historical events in timestamp order through the Part 1 Push API (replay mode), preserving the original `occurred_at` and recorded data availability. This demonstrates the ingestion-to-prediction pipeline without pretending Stripe Test Mode's generated data shares the training distribution.

Demo flow:

1. Show the selected account's eligible status and the last available data timestamp.
2. Replay events until cutoff T1; build a real feature snapshot and score it.
3. Replay later events until T2; generate a second real prediction and explain the changed features.
4. Show 7/14/30-day forecasts, personal baseline deviation, horizon drivers, and reliability status.
5. Reveal the held-out outcome only **after** forecasts are saved; calculate actual alert lead time if churn occurred.
6. Show comparison with the baseline using the same replay and alert policy.

**Demo integrity:** replayed test outcomes must not be used for model fitting, threshold tuning, or scripted risk probabilities. Numeric screenshots/claims must be generated from real runs. Never promise a fixed improvement before evaluation.

## 7. Part 2 Output Contract

Persist one record per `(tenant_id, customer_id, as_of, prediction_run_id)` in `predictions`, including:

```json
{
  "tenant_id": "tenant_abc",
  "customer_id": "cust_001",
  "prediction_run_id": "run_20261010_001",
  "as_of": "2026-10-10T00:00:00Z",
  "status": "scored",
  "prediction_horizon_days": [7, 14, 30],
  "cumulative_churn_probability": {
    "7": 0.12,
    "14": 0.38,
    "30": 0.81
  },
  "model_version": "lightgbm_multihorizon_v1",
  "calibration_version": "calibration_v1",
  "feature_version": "features_v1",
  "reliability": {
    "status": "limited_evidence",
    "reasons": ["Short personal usage history"]
  },
  "explanations": {
    "7": ["Recent payment failures"],
    "30": ["Usage below personal baseline"]
  },
  "input_data_as_of": "2026-10-10T00:00:00Z"
}
```

**Schema example only:** example probabilities and drivers above are synthetic; they are **not** expected demo values or validated metrics. For `insufficient_evidence`, return status `abstained` and `null` probability fields. For known cancellation, return status `known_cancellation` and no prospective forecast. Explanation output in production must contain actual model-backed feature attributions and their sign/magnitude, not only prewritten phrases.

Part 3 may join this record with Part 1 normalized MRR, currency, billing interval, and business constraints to calculate financial exposure and support human decisions. Part 2 must **not** embed expected intervention ROI or recommendation claims.

## 8. Implementation Deliverables

1. `feature_builder`: time-safe normalized and personalized features, plus `feature_version`.
2. `label_builder`: reproducible 7/14/30-day labels, censoring and eligibility handling.
3. `train`: rule and logistic baselines, LightGBM candidates, chronological model-selection pipeline.
4. `calibrate`: probability calibration and horizon monotonicity checks.
5. `explain`: model-backed, horizon-specific risk drivers.
6. `reliability`: data/applicability checks and abstention policy.
7. `predict`: tenant-scoped batch/event-driven inference and persisted versioned results.
8. `replay_evaluate`: held-out event replay, operational lead-time and false-alert comparison.
9. `report`: reproducible metrics, calibration visuals, dataset provenance, limitations, and run configuration.

## 9. Acceptance Criteria

- [ ] Dataset provenance, event-time coverage, effective churn dates and observation windows are documented.
- [ ] All training/evaluation snapshots exclude future-known information and known pending cancellations.
- [ ] Each horizon label correctly handles positives, observed negatives and unknown outcomes.
- [ ] Personal baseline uses an earlier non-overlapping window and handles sparse/new accounts.
- [ ] Rule/logistic baselines and LightGBM use the same eligible temporal evaluation data.
- [ ] Reported 7/14/30-day forecasts are calibrated, monotonic, and versioned.
- [ ] Top drivers are generated from the fitted model; unsupported causal language is absent.
- [ ] Missing or stale essential input causes clear abstention; limited evidence is identified.
- [ ] Daily batch evaluates silent accounts; important events may trigger additional refresh.
- [ ] Predictions persist with model, calibration, feature and cutoff versions.
- [ ] Replay API uses timestamp-ordered, held-out events and produces genuine forecast changes.
- [ ] Lead-time claims are calculated from real alert and churn timestamps, with alert-volume/false-alert comparison.
- [ ] Part 3 can consume the output without depending on Part 2 for prices, decisions, or ROI.

## 10. Scope Boundaries and Fallback

**Required MVP:** validated historical dataset; time-safe snapshots and labels; personalized usage features; three-horizon forecasting; baseline comparison; calibrated probabilities; clear reliability status; saved predictions; replay evaluation.

**If time permits:** horizon-specific SHAP visualizations and fuller alert-policy sensitivity studies.

**Not required:** deep-learning text models, causal uplift, churn-type competing-risk model, model retraining from intervention results, dynamic action optimization, automatic discounts, arbitrary external API connectors.

**Fallback rule:** when timestamps, churn-effective dates, or longitudinal behavior are insufficient, do **not** claim multi-horizon lead-time validation. Deliver the supported subset, disclose the evidence gap, and avoid fabricated benchmark results.
