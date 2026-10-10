# RetainIQ v2 — Complete Product & Engineering Requirements

**Track:** Dormathon 2026 — Track 1: Predictive Model / Predict Early, Decide Better  
**Status:** Proposed implementation specification; not evidence of completed features, model performance, or retention uplift  
**Version:** 1.0 (integrated from the four supplied Part 1–4 specifications)  
**Primary audience:** Product, data engineering, ML, backend, frontend, and hackathon demo teams  
**System:** RetainIQ — subscription churn prediction and human-governed retention decisions

> **Product promise:** Predict early, plan realistically, let humans decide, and learn responsibly from what actually happens.

## Contents

1. [Product goal and boundaries](#1-product-goal-and-boundaries)
2. [System architecture and component ownership](#2-system-architecture-and-component-ownership)
3. [Common business and time definitions](#3-common-business-and-time-definitions)
4. [Unified data model and contracts](#4-unified-data-model-and-contracts)
5. [Part 1 — Data Foundation](#5-part-1--data-foundation)
6. [Part 2 — Prediction Engine](#6-part-2--prediction-engine)
7. [Part 3 — Decision Engine](#7-part-3--decision-engine)
8. [Part 4 — Closed-Loop Learning & Business Dashboard](#8-part-4--closed-loop-learning--business-dashboard)
9. [APIs and integration flow](#9-apis-and-integration-flow)
10. [Evaluation and evidence standards](#10-evaluation-and-evidence-standards)
11. [Security, operations, and data governance](#11-security-operations-and-data-governance)
12. [User experience and dashboard requirements](#12-user-experience-and-dashboard-requirements)
13. [End-to-end demo and test plan](#13-end-to-end-demo-and-test-plan)
14. [Delivery sequence, roles, and definition of done](#14-delivery-sequence-roles-and-definition-of-done)
15. [Risks, dependencies, and deferred features](#15-risks-dependencies-and-deferred-features)
16. [Cross-part acceptance checklist](#16-cross-part-acceptance-checklist)
17. [Source alignment and integration decisions](#17-source-alignment-and-integration-decisions)

---

## 1. Product goal and boundaries

### 1.1 Problem

Subscription businesses may observe usage declines, failed payments, and subscription changes before an account churns, but converting these signals into timely, justified action is difficult. Standard churn dashboards can show a risk score without showing whether the warning is early enough, reliable, actionable, affordable, or linked to a later outcome. RetainIQ addresses that **prediction-to-decision gap**.

### 1.2 Four-part product

| Layer | One-line pitch | Primary deliverable |
|---|---|---|
| **Part 1 — Connect** | Turn timestamped business data into secure, reproducible customer evidence. | Canonical events, identities, subscriptions, point-in-time history, integration health |
| **Part 2 — Predict** | Forecast who may churn within 7/14/30 days, what changed, and whether the warning is trustworthy. | Versioned calibrated forecasts, behavior baselines, reliability status, evaluation |
| **Part 3 — Decide** | Prioritize human attention and fact-supported actions within real resource constraints. | Routes, revenue-risk proxy, action proposals, review plan, break-even scenario, human decision history |
| **Part 4 — Learn & Understand** | Connect predictions and decisions to observed outcomes and safely assess future model improvements. | Mature feedback, model governance, business dashboard, customer timeline |

**Primary prediction object:** a paying subscription **account**, not every individual seat/user. An account may have several user identities and/or subscriptions. The organization must document whether churn means the **last paying subscription ends** or a particular contract ends; use the same definition everywhere.

### 1.3 The complete operating loop

```text
Timestamped historical / incremental subscription, usage, billing events
                               |
                               v
      PART 1: Auth -> classify -> minimize -> normalize -> store
                               |
             point-in-time features + eligible outcomes
                               |
                               v
      PART 2: Personalized features + 7/14/30-day models
               + calibration + reliability/freshness
                               |
                       immutable prediction
                               |
                               v
      PART 3: Eligibility/reliability routing -> p30 x MRR
               -> top-K review -> factual action options
               -> cost/break-even -> HUMAN DECISION -> execute
                               |
                  later actual lifecycle events
                               |
                               v
      PART 4: Outcome maturity -> evaluation -> dashboard
               -> controlled retraining / operator approval
                               |
                               +----> next Part 2 release (if valid)
```

A forecast does **not** authorize a discretionary message, voucher, price change, or contract change. Humans approve the final decision. Future outcomes must never leak into earlier predictions.

### 1.4 Must-have MVP versus later enhancements

**Must-have product path:** authorized historical dataset + one Push API; tenant-aware canonical storage; leakage-safe 7/14/30-day prediction and baseline comparison; three review routes; MRR-weighted ranking; supported action options; top-K review slots; approval and follow-up tracking; one one-month break-even ROI card; a traceable customer timeline; mature-outcome feedback and basic dashboard; one honest historical replay.

**Conditional on valid data:** complete three-horizon accuracy/lead-time claims, personalized-baseline performance claims, action types requiring unavailable facts, and candidate retraining. Deliver a truthful blocked/unavailable state rather than fabricating evidence.

**Not MVP:** connector marketplace; large LLM agents; automatic offers; an uplift/treatment-effect model; a claim that observed retention equals saved revenue; global heterogeneous-intervention optimization; production randomized holdout service; online model updates after each event; arbitrary drag-and-drop dashboard builder.

---

## 2. System architecture and component ownership

| Concern | System of record / owner | Downstream responsibility |
|---|---|---|
| Source authorization, provenance, raw-data minimization, account identity | **Part 1** | Parts 2–4 consume only authorized tenant-scoped records |
| Canonical usage/billing/subscription history and as-of contract value | **Part 1** | Part 2 builds inputs; Part 3 values account exposure; Part 4 reconstructs outcomes |
| Churn event definition and historical label materialization | **Part 1 + Part 2** | One label policy/version, reused for evaluation and feedback |
| Point-in-time features, model training, calibration, prediction, SHAP associations | **Part 2** | Part 3 must not rewrite model probabilities or infer treatment effects |
| Case routes, contact cooldown, action catalog, slots/budget enforcement | **Part 3** | Part 4 shows the authoritative states rather than cloning rules |
| AI suggestion, human override, assignment, execution, actual cost | **Part 3** | Part 4 reads events for analytics and timelines |
| Mature label linkage, prediction quality, release governance | **Part 4** | Approved models flow back to Part 2 serving |
| Company dashboard, risk-to-action navigation, customer timeline | **Part 4 UI** | Case approval opens Part 3's authoritative decision workflow |

**Shared conventions:** server-derived `tenant_id`; stable account `customer_id`; ISO-8601 UTC timestamps; source event `occurred_at` and availability time; durable IDs; versioned policy/feature/model/calibration/action catalog; database money in integer minor units and an ISO-4217 `currency`.

**No duplicated business logic:** the dashboard does not reimplement forecasts, action rules or ledger totals in frontend JavaScript. APIs provide computed, versioned, explainable outputs.

---

## 3. Common business and time definitions

### 3.1 Churn and eligibility

- **Qualifying churn:** paid subscription entitlement **actually ends** due to voluntary cancellation, non-renewal, or finalized involuntary termination after collections. The effective event time is `churn_effective_at`.
- **Payment failure:** a billing feature, **not** churn unless paid entitlement later terminates.
- **Known/pending cancellation:** a cancellation request known at/before the prediction cutoff. Exclude from prospective first-churn scoring and use `known_cancellation`/`KNOWN_CANCELLATION` separate process; do not use pending-cancel status as a churn feature.
- **Eligible population:** active at the cutoff, no known pending cancellation, valid mapped account and observable subscription state. Eligibility rules and label policy have versions.
- **Horizon label:** for cutoff `t` and horizon `h` in `{7,14,30}`, label `1` if qualifying churn takes effect in `(t,t+h]`; label `0` only with full observed churn-free follow-up; otherwise `unknown`/censored.
- **Right censoring:** do not convert incomplete future coverage or disconnected data sources into negatives.
- **Multi-subscription accounts:** define account churn consistently and test partial-plan termination separately from total churn.

### 3.2 Point-in-time correctness

`as_of` is the precise snapshot/prediction cutoff. A fact is allowed as a feature only if **both** its event time and its actual historical availability time were at or before `as_of`. Model training, evaluation, historical replay and live scoring use the same rule. Future cancellations, future customer actions, outcomes, later data corrections and after-cutoff availability are excluded from earlier features.

For replay, preserve the historical source availability timestamp when it exists. **Replay ingestion time is not equivalent to historical first availability.** If the dataset lacks arrival timestamps, document a defensible availability assumption and do not claim tested robustness to late-arriving data.

Prediction outcome windows begin at **prediction `as_of`**; operational action follow-up may begin at **action execution**. Store the anchors separately.

### 3.3 Probability and financial semantics

- `p_churn_7d`, `p_churn_14d`, `p_churn_30d` are **calibrated cumulative probabilities** by the specified horizon, not three unrelated labels or exact churn dates.
- When populated, `0 <= p7 <= p14 <= p30 <= 1`. Each horizon needs its own training label and validation.
- `MRR` is normalized recurring contract amount after applicable recurring discounts and excluding one-off items/tax according to a versioned policy. It is not automatically customer lifetime value.
- **Exposure proxy:** `p30 × as_of_MRR`, per currency. This is MRR-weighted churn exposure for ranking, **not** exact next-month loss or provably recoverable revenue.
- **Scenario ROI:** assumed effectiveness + configured costs/margin, not observed incremental results. **Validated incremental ROI** requires an appropriate controlled comparison.

---

## 4. Unified data model and contracts

### 4.1 Canonical event intake

The Push API accepts an authenticated, versioned, allowlisted envelope for subscription, billing and usage events. `tenant_id` is derived from authentication, never from a client's body.

```json
{
  "source": "product_app",
  "source_event_id": "evt_1029",
  "external_customer_id": "acct_102",
  "event_type": "session_started",
  "occurred_at": "2026-10-10T09:00:00Z",
  "attributes": { "feature": "analytics" },
  "schema_version": "1.0"
}
```

The ingestion service records `received_at` on arrival and separately preserves `source_available_at` if a trusted historical source supplies it. Source and event semantics must be documented. Do not confuse a login with a session without a defined event contract.

**Identity:** `(tenant_id, source, external_customer_id) -> customer_id`. Prefer explicit account mappings; do not fuzzy-merge by email. Store minimal protected contact identity separately from model features.

### 4.2 Logical PostgreSQL schema

This is a **logical, integrated contract**, not a claim that all tables already exist. Part 1's earlier eight-table list is expanded to support reliable state history and Parts 2–4. The migration implementation may split/normalize records differently as long as the stated keys, time semantics and interfaces are preserved.

| Owner | Table | Required core information |
|---|---|---|
| P1 | `customers` | `tenant_id`, `customer_id`, `account_status`, `created_at` |
| P1 | `customer_identities` | `tenant_id`, `customer_id`, `source`, `external_customer_id`, protected contact fields only if needed |
| P1 | `subscriptions` | account/subscription IDs, plan/status, start/end/current period, cancel-request time, billing interval/count, amount/discount minor, currency |
| P1 | `subscription_events` **(integration clarification)** | `tenant_id`, subscription/account IDs, source/event IDs, event type, `occurred_at`, `received_at`, state/price changes sufficient to reconstruct `as_of` subscription truth |
| P1 | `billing_events` | tenant/account/event IDs, type, payment status, amount/currency if applicable, `occurred_at`, `received_at` |
| P1 | `usage_events` | tenant/account/event IDs, typed activity, approved attributes, `occurred_at`, `received_at` |
| P1/P2 | `feature_snapshots` | `feature_snapshot_id`, tenant/account, `as_of`, `feature_version`, feature values, source availability cutoff and coverage/quality flags |
| P1/P2 | `churn_labels` | tenant/account, `as_of`, `horizon_days`, label `1/0/unknown`, `outcome_at?`, `label_observed_through`, `label_policy_version` |
| P2 | `predictions` | `prediction_id`, `prediction_run_id`, tenant/account, `as_of`, statuses, p7/p14/p30, versions, reliability/freshness/uncertainty, `generated_at`, feature snapshot ref |
| P3 | `decision_cases` | `case_id`, tenant/account, `prediction_id`, `as_of`, `route`, urgency, exposure/MRR/currency, policy version, cooldown, status |
| P3 | `action_proposals` | `proposal_id`, `case_id`, action/catalog version, supporting fact refs, eligibility, cost/currency/staff estimate |
| P3 | `human_decisions` | append-only actor, proposal, original/final action, decision/transition, reason, owner, time, cost/actuals |
| P3 | `outcome_observations` | `observation_id`, `case_id`, follow-up anchor, horizon, observed status/source, completeness, dated actual cost/financial status |
| P4 | `prediction_feedback` | `feedback_id`, `prediction_id`, horizon, maturity status, label/source, observation coverage, exposure indicator, policy version |
| P4 | `evaluation_runs` | ID, model/feature/calibration versions, window, cohort/labels, metrics, sample size, provenance |
| P4 | `model_registry` | scope/tenant (as appropriate), model/calibration/feature versions, status, artifact digest, approval/promotion/rollback audit |
| P4 | `retraining_runs` | ID, source window, dataset digest, split, candidate version, evaluated run, decision/reason/operator/time |

**Migration notes:**

1. The original Part 1 stored predictions as **one `(horizon_days, churn_probability)` row per horizon**. The integrated output standard is **one immutable `prediction_id` per account/cutoff with three probability columns**. A long-form view may be produced for metric computation, but do not mix the two as canonical APIs.
2. `prediction_run_id` identifies a batch/inference run, potentially shared by many accounts; **`prediction_id` identifies one account forecast snapshot** and is the foreign key used by Parts 3–4. Preserve both identifiers.
3. The additional append-only subscription history is an **integration design clarification** to reconstruct historical status/price reliably; it was not a separate mandatory table in the original eight-table Part 1 outline.
4. Enforce tenant-aware unique/foreign keys and source-event idempotency `(tenant_id,source,source_event_id)`; use server-side row scopes on every operation.
5. Separate `observed outcome` from `human action outcome`: they may have different cutoff anchors and cannot be interchanged.

### 4.3 Unified Part 2 -> Part 3 / Part 4 prediction payload

The following is a **schema illustration only**; displayed numbers are not trained model outputs.

```json
{
  "tenant_id": "tenant_abc",
  "customer_id": "cust_001",
  "prediction_id": "pred_001",
  "prediction_run_id": "run_001",
  "as_of": "2026-10-10T00:00:00Z",
  "generated_at": "2026-10-10T00:00:10Z",
  "status": "scored",
  "p_churn_7d": 0.12,
  "p_churn_14d": 0.38,
  "p_churn_30d": 0.81,
  "feature_version": "features_v1",
  "model_version": "multihorizon_v1",
  "calibration_version": "calibration_v1",
  "label_policy_version": "churn_policy_v1",
  "reliability": {
    "status": "sufficient_evidence",
    "reasons": []
  },
  "data_freshness": {
    "status": "fresh",
    "input_data_as_of": "2026-10-10T00:00:00Z",
    "stale_sources": []
  },
  "uncertainty": {
    "status": "not_quantified",
    "method": "none",
    "intervals": null
  },
  "explanations_by_horizon": {}
}
```

**Field/status contract:**

| Field | Values / interpretation |
|---|---|
| `status` | `scored`, `abstained`, `known_cancellation`, `not_eligible` |
| `reliability.status` | `sufficient_evidence`, `limited_evidence`, `insufficient_evidence` |
| `data_freshness.status` | `fresh`, `partially_stale`, `stale`, `unknown`; thresholds documented per source |
| `uncertainty.status` | `not_quantified` until defensible statistically validated uncertainty is implemented; never synthesize confidence intervals |
| `p_churn_*` | float in `[0,1]` only when scored; otherwise `null`; cumulative horizon ordering |
| `explanations_by_horizon` | computed fitted-model attributions, signed with actual feature values and horizon; model associations, not causes |
| `input_data_as_of` | latest source-availability cutoff actually used, not a claim of 100% fresh coverage |

**Key reconciliation:** Part 2's original nested `cumulative_churn_probability` shape and Part 3's original flat `p_churn_*` shape are mapped to the **flat API/database contract above**. Parts 3–4 consume the same structure; no client should depend on the older nested sample.

### 4.4 Part 3 -> Part 4 decision / outcome contract

Part 4 receives (or queries) the **authoritative Part 3 case and append-only decision events**, not a synthetic summary:

- `case_id`, `prediction_id`, account and tenant IDs, route/reason, cutoff, policy version and MRR exposure proxy.
- `proposal_id`, `action_code`, `catalogue_version`, supporting fact references, action eligibility, estimate and staff minutes.
- original AI suggestion, final human choice, `APPROVE | MODIFY | REJECT | NO_INTERVENTION` (optional `DEFER`), reason, actor, timestamps, assigned owner.
- execution events, actual/estimated cost, follow-up anchor and 7/14/30-day source-backed observations with completeness.
- Optional experimental metadata (`experiment_id`, assignment group and strategy) is **metadata only**; no production randomized allocation required for MVP.

---

## 5. Part 1 — Data Foundation

### 5.1 Objective

Provide a small, secure, repeatable pathway from historical and incremental business events to normalized **point-in-time-correct** customer facts, subscription valuation and versioned feature/label inputs. It is an **extension to a company's existing system**, not a requirement that the company rebuild its product inside RetainIQ.

### 5.2 Sources and dataset gate

**Required:** a legitimately usable longitudinal dataset with timestamped account activity and/or billing, dated subscription lifecycle and actual churn-effective outcomes, sufficient follow-up coverage, and a reproducible mapping to the Push API. Document source, permission/license, record coverage, schema and limitations in `DATASET_CARD.md`.

- Import CSV/Parquet history using a versioned source-to-canonical mapping.
- Build chronological training, tuning/validation, calibration and untouched test windows.
- A static final `Churn = Yes/No` snapshot does **not** validate early warning, true 7/14/30-day labels, or personal historical deviation.
- If data do not meet the gate, use synthetic fixtures only to verify pipeline behavior; label every such evaluation/demo as synthetic, not real predictive performance.
- Stripe Test Mode is an **optional connectivity demo**, not independent model-validation data.

### 5.3 API ingestion and normalization

- Implement `POST /v1/ingest/events`, authenticated using properly scoped secrets and server-derived tenant identity.
- Authenticate and authorize source; check schema; classify origin, sensitivity and allowed purpose; remove/reject unauthorized or unnecessary restricted fields **before persistent storage**; normalize and deduplicate.
- Field-allowlist event types for usage, billing and subscriptions; record schema/mapping versions, reject reasons and redacted operational errors.
- Persist idempotent events using `(tenant_id,source,source_event_id)`; source event IDs are stable.
- Map source account IDs to canonical paying accounts; reject or quarantine unmatched identities rather than silently misjoining.
- Persist source event time and availability/received time, normalized subscription state and currency/value history.
- Expose last-successful sync, mapping/version and error state to authorized UI.

**Optional connector:** signed Stripe Test Mode webhook adapter; it uses the same normalization and account identity path. No connector marketplace or arbitrary user-provided pull-URL support in MVP.

### 5.4 Security/data classification

Classify independently:

1. **Origin:** internal, authorized external, unverified.
2. **Sensitivity:** public, internal, confidential, restricted.
3. **Permitted purpose:** identity mapping, retention inference, billing valuation, customer contact.

Reject unnecessary restricted fields, keep payment-card/secrets out of analytics and feature JSON, protect contact identity separately, redact errors and audit logs. Require HTTPS, secrets outside source code/frontend, encryption at rest from managed storage, scoped database access, role separation and negative cross-tenant tests.

### 5.5 Canonical valuations and churn labels

- Store money as integer minor units plus ISO currency and billing interval/count; use a documented dated MRR normalization policy.
- Do not mix currencies. If cross-currency aggregates are essential, use a documented dated FX source/rate or report separately.
- Determine effective churn (voluntary, non-renewal, involuntary) only when entitlement truly ends; known pending cancellation is not a pre-churn predictor sample.
- Materialize **7-, 14-, and 30-day** point-in-time labels for Part 2. This intentionally **supersedes the 30-day-only wording** in the uploaded Part 1 specification.
- For right-censored/incomplete coverage, persist `unknown`; do not fabricate negative examples.

### 5.6 Refresh strategy

- Ingest events upon arrival; daily reconciliation where supported.
- **Daily scoring refresh for all eligible accounts**, including those without activity/events.
- Optionally trigger additional affected-account scoring for failed payments or materially changed usage after aggregation.
- Track source freshness with business-relevant rules; no unsupported 5-minute prediction SLA.
- Nonurgent staff notifications follow configured business hours; ingestion and mandatory billing obligations are not blocked.

### 5.7 Part 1 acceptance tests

- [ ] Historical dataset provenance/licensing and event/label coverage are documented, including gaps.
- [ ] Historical import, replay and Push API share a versioned canonical event contract.
- [ ] Ingestion handles authentication, minimization, explicit identity mapping, invalid events and duplicate event IDs.
- [ ] Subscription, usage and billing sources preserve event/availability timing and source references.
- [ ] All customer-bearing data and reads enforce `tenant_id`; contact/payment credentials stay out of modeling inputs.
- [ ] MRR/currency/discount normalization handles annual/monthly contracts, missing prices and multiple subscriptions.
- [ ] Known pending cancellations, payment failure and right censoring follow agreed labeling semantics.
- [ ] 7/14/30-day snapshots/labels can be reconstructed without lookahead; daily refresh finds silent accounts.
- [ ] Source freshness and ingestion failures are visible to authorized operators.

---

## 6. Part 2 — Prediction Engine

### 6.1 Objective and output

**Personalized Multi-Horizon Churn Foresight:** estimate calibrated cumulative churn probabilities over 7, 14 and 30 days, explain model-associated patterns, identify meaningful deviations from each account's own behavior, and say when evidence is too weak for a trustworthy numeric forecast.

Part 2 answers **who may churn, how soon, what evidence changed, and how reliable the warning is**. It does **not** calculate action effects, offer discounts or set business budgets.

### 6.2 Point-in-time features

At each eligible `(tenant_id, customer_id, as_of)` compute feature families where available:

| Family | Examples | Safeguard |
|---|---|---|
| Usage intensity | sessions in prior 7/30d, inactivity days | event semantics explicit; missing != zero |
| Personal baseline | earlier 4–8 complete weeks, usage ratio, deviation/percentage change | baseline window strictly **before and non-overlapping** with comparison window |
| Usage rhythm | prior variability/weekly patterns, changes vs expected rhythm | avoid leakage from later periods |
| Billing | failures in prior 30d, overdue duration, successful recovery | failure alone is not churn |
| Subscription | tenure, billing cadence, plan tenure | no pending-cancel flag as feature |
| Optional support | dated ticket severity/count/status | only if both historical and live source exists |
| Quality | days of observed history, missingness, source freshness, applicable cohort | sparse/new accounts flagged; safe cohort fallback |

For zero-baseline or cold-start accounts, safely handle denominators and mark missing personal history. The baseline is a feature **shared across a trained population**, not a separate model trained per customer.

### 6.3 Horizon training labels and split protocol

For each cutoff create three independent horizon labels (7/14/30) with positive, observed negative, and unknown states. Do not train a horizon on unknown outcomes. Train/rank models using chronological **train -> tuning/validation -> calibration -> untouched test** splits. Purge or separate overlapping label windows as needed so a training label is genuinely observable before the next period starts. Do not fit preprocessing, thresholds, calibration or model hyperparameters on final test outcomes.

### 6.4 Baselines and primary candidate

- **Rule baseline:** documented inactivity/payment heuristic.
- **ML baseline:** logistic regression with consistent preprocessing.
- **Primary candidate:** three horizon-specific LightGBM classifiers using the same point-in-time feature contract.
- **Optional research comparison:** discrete-time survival model if the dataset justifies it; not a hackathon dependency.
- Select a final model by **held-out** discrimination, calibration, fixed-alert-budget usefulness, lead time, inference cost and stability. Do not assume LightGBM automatically wins.
- Handle imbalanced classes without relying on classification accuracy alone.

### 6.5 Calibration and coherent cumulative forecasts

Calibrate each horizon using a separate chronological calibration period (e.g., sigmoid; isotonic with enough data). Verify `p7 <= p14 <= p30`; if independently calibrated models violate this, perform a documented monotonic correction and **reassess calibration and discrimination afterward**. Never derive p7/p14 by arbitrarily scaling p30.

### 6.6 Explainability and early warning

- Use actual fitted-model horizon-specific attributions (e.g., TreeSHAP) with feature values/signs, not generated generic explanations.
- Explain *associations*, not causes or treatment effectiveness.
- Persist real dated predictions. A historical sequence of previously issued scores forms a **risk history**, not a forecast curve of future risk.
- Early-warning trigger policies (probability threshold, increasing trend, data quality, cooldown) are versioned and selected on development data.
- Score inactive accounts daily; do not require a new event to notice silence.

### 6.7 Reliability, freshness and uncertainty

| State | Interpretation | Decision consequence |
|---|---|---|
| `sufficient_evidence` | Required sources and history pass policy | Suitable for policy-based review ranking |
| `limited_evidence` | Prediction possible but data history/optional inputs/coverage limited | Route for human investigation if Part 3 policy requires; do not silently treat as certain |
| `insufficient_evidence` | Eligibility or critical input/model applicability cannot be established | `abstained`; null probabilities |

`reliability` is a **quality/applicability gate**, not a statistically calibrated per-customer “certainty 91%.” `data_freshness` flags material outages/late source coverage. `uncertainty` exists in the payload but remains `not_quantified` unless validated estimation is implemented; do not manufacture intervals.

### 6.8 Evidence-based predictive evaluation

| Area | Required result if sufficient held-out data exist |
|---|---|
| Each horizon | PR-AUC, ROC-AUC, Brier score, calibration table/plot, sample sizes, prevalence |
| Ranking at fixed capacity | Recall@Top-K or same weekly alert budget across baselines |
| Warning utility | first-alert lead time among detected churn cases, missed cases, false alerts and alert load |
| Personalization ablation | with versus without customer-relative features using the same model/time split |
| Reliability | abstention rate and errors/calibration by reliability/coverage cohort |
| Engineering | point-in-time checks, runtime, reproducible model/feature/calibration versions |

Longer warning lead time alone is not proof of a better model. Compare with false-positive and alert-workload controls. If evidence is insufficient, report `N/A` and reason instead of manufactured wins.

### 6.9 Part 2 acceptance tests

- [ ] Dataset can support genuine dated churn labels; otherwise limitations visibly documented.
- [ ] All model inputs were available by `as_of` and exclude known-cancel information.
- [ ] Personal baselines use strictly earlier independent windows and handle cold starts.
- [ ] Rule/logistic/full candidates use the same fair held-out population and cutoffs.
- [ ] Per-horizon calibrated probabilities and monotonic checks are tested.
- [ ] Explanations come from the fitted model and contain no unjustified causal attribution.
- [ ] Reliability/freshness/abstention statuses map to the shared prediction contract.
- [ ] Daily refresh, immutable prediction IDs and versioned alert policies function.
- [ ] Evaluation includes alert budget, false positives, sample sizes and real historical timing.

---

## 7. Part 3 — Decision Engine

### 7.1 Objective

Build a **Human-Governed Retention Strategy Lab** that turns calibrated forecasts and verified source facts into a feasible **human review plan**. Core promise: prioritize a limited number of accounts, offer context-appropriate **candidate** actions, show what effectiveness would be needed to justify their cost, and record what employees actually chose and did.

**MVP is budget-aware review planning, not validated optimal retention ROI.** No new paid LLM/model inference is required for this part.

### 7.2 Eligibility and three authoritative routes

Apply in order: **eligibility -> reliability/freshness -> review policy threshold -> cooldown -> financial ranking**.

| Route/state | Trigger | Behavior |
|---|---|---|
| `KNOWN_CANCELLATION` | cancellation request already known at cutoff | separate cancellation-recovery workflow; no prospective churn score |
| `NOT_ELIGIBLE` | no valid active paying-account population | excluded from prospective review |
| `HUMAN_REVIEW` | abstention, limited/insufficient evidence, materially stale data, identity conflict, missing critical valuation | verify source/account facts first; do not make unsupported offers |
| `PRIORITY_REVIEW` | eligible, sufficiently evidenced/fresh and qualifies under validation-selected policy | ranked against K reviewer slots |
| `OBSERVE` | below review policy or deferred under permissible discretionary contact cooldown | monitor; record why no outreach was proposed |

These are **three operational routes plus two nonpredictive states**. “Urgent,” “scheduled,” and “financial priority” may be UI descriptors/attributes but **must not be separate undocumented route enum values**. `p7` is urgency information/tie-break, `p30` is the main financial ranking horizon. Policy/thresholds are selected on development data, never taken from the example table.

Limited data do not mean safe data. Handle `partially_stale` according to source importance; critical subscription/billing staleness prevents ranked financial recommendations. Discretionary outreach cooldowns do **not** block mandatory notices or normal support.

### 7.3 Exposure proxy, priority and correctly defined K

```text
exposure_proxy_30d = calibrated_p_churn_30d × as_of_MRR

Review shortlist order:
  (1) descending exposure_proxy_30d
  (2) descending p_churn_7d on ties
  (3) oldest pending case on ties
  (4) stable account ID on ties

Top K = available HUMAN REVIEW SLOTS in a defined period, not "customers saved".
```

- Compare accounts within one currency or apply an explicit dated FX rule; never add unlike currencies.
- If MRR missing/stale, return null and route to investigation, not `0`.
- Deduct investigative workload from shared staffing capacity if those staff are the same people; report investigation queue separately.
- A customer with an open action or applicable cooldown should not repeatedly receive the same discretionary contact proposal.

**Illustrative arithmetic (not measured data):**

| Account | 30d risk | MRR | Proxy | Reliability | Handling |
|---|---:|---:|---:|---|---|
| Alice | 85% | RM100 | RM85 | sufficient | rankable |
| Bob | 65% | RM1,200 | RM780 | sufficient | rankable |
| Charlie | 78% | RM500 | RM390 | sufficient | rankable |
| Dana | 45% | RM900 | RM405 | limited | `HUMAN_REVIEW` investigation |

If all reliable: **Bob, Dana, Charlie, Alice**. As shown with Dana separated and `K=2`, rankable accounts **Bob and Charlie** are selected, assuming thresholds/cooldowns allow both.

### 7.4 Fact-based Next Best Action catalog

The engine proposes **eligible options**, not a scientifically proven best intervention. Use actual customer facts available by cutoff, never SHAP as a causal action trigger.

| Action code | Necessary observed facts | MVP mode |
|---|---|---|
| `ACCOUNT_CHECK_IN` | valid measured usage change/deviation; no contradictory account status | **operational** |
| `PAYMENT_RECOVERY` | confirmed failed/past-due billing event under business policy | **operational** |
| `PRODUCT_WALKTHROUGH` | usage evidence plus actual feature/onboarding gap | **conditional** if feature-level events exist |
| `DATA_INVESTIGATION` | stale, missing, conflicting or limited source evidence | **operational** |
| `NO_INTERVENTION` | human chooses no discretionary action, with documented reason | **operational** |
| `TECH_SUPPORT_ESCALATION` | relevant unresolved ticket/status, currently outside minimal Part 1 | **disabled/simulation-only** |
| `PLAN_REVIEW`, `PAUSE`, `DOWNGRADE` | entitlements, account needs, plan policy, cost/revenue impact | **disabled/simulation-only** |
| `CONDITIONAL_DISCOUNT` | documented price objection and authorization | **disabled/simulation-only** |

Every catalog entry records `required_fields`, eligibility conditions, contraindications, estimate source/date/currency, `estimated_staff_minutes`, cooldown, approval role, `catalogue_version`, and `operational | simulation_only | disabled` mode.

**Candidate generation:** read tenant/time-valid facts -> test required data -> apply eligibility and cooldown/permission -> attach supporting source fact IDs and reasons -> show estimated cost/time -> let a human choose an allowed action or `NO_INTERVENTION`. If evidence is missing, route to investigation instead of pretending to know the right incentive.

**No unsupported auto-execution.** No automatic vouchers, plan changes, outreach, or legally necessary service denial. Simulation-only actions must not enter live executable proposals.

### 7.5 Budget, reviewer capacity and approval safeguards

- Admin configures `K` review slots per day/week and, optionally, a staff-minute cap plus monetary discretionary action budget **per currency**.
- Generate deterministic top-K **review cases**. Top-K is exact for slots, **not** a global optimal bundle across different treatments/costs.
- Show estimated staff minutes and configured action cost per proposal; actual costs are logged after execution.
- Enforce remaining budget and staff-minute caps **transactionally at human approval**, including concurrent approvals/idempotency. Require authorized override with reason when policy allows.
- A manager may modify priority or choose `NO_INTERVENTION`, with audit metadata.
- **Deferred:** second bundle-planning simulator and global knapsack/OR-Tools optimizer; without measured action uplift these cannot claim to maximize revenue saved.

### 7.6 One-month What-If / break-even ROI card

**Question:** “How much would this proposed action need to reduce 30-day churn risk to cover its estimated cost?” This is a **sensitivity analysis**, not an effect prediction.

Inputs: actual `as_of_MRR`, `p30`, action estimated cost (`>0` unless special handling), admin-configured **contribution margin**, user-set assumed **absolute 30-day churn reduction** within `[0,p30]`, one-month valuation window.

```text
contribution_value = MRR × contribution_margin
break_even_absolute_reduction = action_cost / contribution_value
break_even_share_of_baseline_risk = break_even_absolute_reduction / p30
scenario_gross_incremental_value = assumed_absolute_reduction × contribution_value
scenario_net_value = scenario_gross_incremental_value - action_cost
scenario_ROI = scenario_net_value / action_cost
```

Display the absolute reduction in **percentage points** (e.g. `17.86 pp`), and separately the relative fraction of baseline risk (`27.47%`). Do not interchange them. If denominator <= 0 or baseline unknown, show `N/A`; zero cost produces ROI `N/A`; if break-even reduction exceeds p30, mark **not achievable in this simplified scenario**. No multi-month retained value without an explicit separately justified duration assumption.

**Verified arithmetic example — hypothetical, not impact evidence:**

```text
MRR = RM1,200; contribution margin = 70%; p30 = 65%; cost = RM150
one_month_contribution = RM840
break_even_abs_reduction = 150 / 840 = 0.178571 = 17.86 pp
break_even_share = 0.178571 / 0.65 = 27.47% of baseline risk
assumed_abs_reduction = 10 pp (NOT measured)
scenario_gross = 0.10 × 840 = RM84
scenario_net = RM84 - RM150 = -RM66
scenario_ROI = -66 / 150 = -44%
```

UI labels: `SCENARIO_ONLY`, `OBSERVED_OUTCOME`, or `VALIDATED_INCREMENTAL_ROI` (**unavailable in MVP**). Configured costs are assumptions until actual expenses are recorded. Actual observation alone cannot prove causal savings.

### 7.7 Human authority and execution history

Supported human decisions: `APPROVE`, `MODIFY`, `REJECT`, `NO_INTERVENTION`; optional `DEFER`. Preserve both **original system proposal** and **final human choice**, reason code/text, actor, timestamp, owner, policy and catalog versions. Require role restrictions for any future financial offer or contract modification.

Suggested states:

```text
PROPOSED -> HUMAN_REVIEWED -> ASSIGNED -> EXECUTED -> FOLLOW_UP_DUE -> CLOSED
                       \-> CLOSED_NO_ACTION
                       \-> REJECTED
```

Every meaningful lifecycle change is an append-only audited event; do not overwrite proposal history. Record predicted action cost and **actual** monetary/staff effort separately; date of first response, completion/failure and source-backed customer follow-up.

At **7/14/30 days after a defined follow-up anchor**, observe active, churned, pending cancellation, downgraded, or unknown states. Unknown/incomplete observation is **not** a successful retention outcome. These operational follow-ups do **not** redefine the prediction-as-of labels in Part 2/4.

**Experiment readiness:** optional treatment/control assignment fields may be stored, but no live RCT infrastructure is required. Synthetic group demos must be labeled synthetic. Never withhold essential customer care or lawful notices for a control group.

### 7.8 Decision-quality evaluation

Use the same frozen, held-out historical replay as Part 2, with each weekly cutoff reconstructed from then-available evidence. Primary metric:

```text
RevenueCaptured@K(t) =
  sum(as_of_MRR of selected eligible accounts that actually churn in next 30d)
  / sum(as_of_MRR of all evaluation-eligible accounts that actually churn in next 30d)
```

Also label the measure **Subsequently Churned MRR Identified@K**; it is historical **identification coverage**, not money saved. Compute per currency/cutoff, and `N/A` for zero denominator. Avoid treating repeated weekly observations of the same account as independent customers.

| Strategy | Mechanics | Meaning |
|---|---|---|
| **A — Risk only** | Descending calibrated `p30` | Basic churn priority baseline |
| **B — Risk × MRR** | Descending calibrated `p30 × MRR` | Value of exposure weighting |
| **C — RetainIQ planning** | Reliability/eligibility, cooldown, K, p30×MRR, p7 tie-break | Operational effect of gated resource planning |

Fair comparison: same historical population, source-availability cutoffs, currency, reviewer slots and counted effort. For C report investigation queue labor as real capacity consumption if staff are shared; risk coverage can fall due to reliability gating, and that is not automatically a failure. Ablate reliability gate, cooldown and urgency tie-break separately. Report Recall@K, missing-data investigations, abstention fraction, false proposals, action eligibility violations and constraint compliance.

**Not measurable without intervention data:** causal uplift, validated intervention ROI, actual saved customers and actual financial savings attributable to the system.

### 7.9 Part 3 acceptance tests

- [ ] Route enums/eligibility cases and reason codes exactly match the shared contract; high risk alone never overrides data inadequacy.
- [ ] `p30 × MRR` and `p7` tie-break, fixed K, cooldown and stable ordering are deterministic/tested.
- [ ] All proposed actions have supporting observed fact IDs and pass enabled-mode/required-data checks.
- [ ] Approval/changes are human-authorized; cost/staff caps resist concurrent double-spend.
- [ ] One-month ROI card recalculates assumptions and handles pp, fraction, zero/undefined cases.
- [ ] Proposed vs actual action/cost history is immutable and reconstructable.
- [ ] Follow-ups differentiate observed outcomes, pending states and unknown source coverage.
- [ ] Frozen A/B/C evaluation reports tradeoffs; no causal saved-revenue claims.

---

## 8. Part 4 — Closed-Loop Learning & Business Dashboard

### 8.1 Objective and ownership

**Close the evidence loop:** link earlier versioned forecasts and human decisions to actual, adequately observed subscription outcomes; monitor predictive quality; evaluate retrained candidates before any model change; give companies an actionable end-to-end dashboard.

Part 4 is **not** a second decision engine and does not automatically learn which retention action caused a customer to stay. Its learning target is **churn forecasting under observed operating conditions**; causal action learning is future research.

### 8.2 Mature outcome feedback

For each stored `prediction_id` at `as_of=t`, evaluate **each** `h ∈ {7,14,30}` after its outcome window. Preserve source provenance, observation coverage and label version.

| Feedback state | Definition | Can train/evaluate? |
|---|---|---|
| `PENDING` | Horizon not finished | No |
| `MATURE_POSITIVE` | Qualifying observed churn in `(t,t+h]` | Yes, label 1 |
| `MATURE_NEGATIVE` | Entire interval observed and no qualifying churn | Yes, label 0 |
| `INCOMPLETE` | Interval elapsed but trustworthy observation missing | No |
| `INELIGIBLE` | Prospectively ineligible at original cutoff | No |

- Do not infer retention from absence of a churn event if ingestion or account state coverage is incomplete.
- Account for late source corrections by superseding/versioning feedback with audit history; do not silently overwrite prior results.
- Record intervention exposure (`none | known | unknown`) and its timestamp for performance breakdowns where sample size supports it.
- **A retained customer after outreach is not proof of outreach effectiveness.** A predicted 80% risk followed by no churn is a possible outcome of a probabilistic model, not by itself an error.

### 8.3 Controlled retraining (not online self-modification)

1. Collect new eligible maturity-confirmed feedback.
2. Monitor per-horizon error/calibration, coverage and missingness; show label/sample counts.
3. Require enough **new valid information** and an auditable split/retraining plan.
4. Train a **candidate** using the same Part 2 time-safe feature/label pipeline and versioned calibration.
5. Compare candidate against current model on a **separate untouched later time period or genuinely prospective shadow sample**; fit/tune outcomes are not reused as final proof.
6. Check PR-AUC/prevalence, Brier/calibration, Recall@K at matched alert budget, warnings/false alerts, reliability cohorts, horizon monotonicity and data leakage.
7. Authorized operator reviews. `PROMOTED` only if predefined gates pass; `REJECTED`/`NOT_READY` is legitimate.
8. Record dataset digest, model artifact/version, evaluation evidence, approval and rollback target. Keep the previous model available.

**Operating cadence:** scheduled feedback maturity and dashboard refresh as data arrives; periodic/on-demand performance checks; candidate retraining only when justified; **never** deploy a new production model in response to every individual outcome.

**Bias caveat:** if an intervention influences future churn outcomes, new labels reflect the actual operating policy. Retraining does **not** isolate treatment effects. Monitor treated/untreated cohorts and withhold promotion where selection bias makes evidence unreliable.

### 8.4 Company-facing dashboard

**Overview — What needs attention?**

- Tenant-scoped active/eligible monitored accounts and scored vs abstained/ineligible coverage.
- Count of `PRIORITY_REVIEW`, `HUMAN_REVIEW`, `OBSERVE`, and pending/overdue cases.
- Dated 7/14/30-day risk distributions and trend history with model version/time displayed.
- MRR-weighted exposure proxy by currency with valuation coverage/missingness.
- Owner workload, open actions, follow-ups, connection freshness and ingestion error hints.

**Decision and outcome analytics — What did the team do?**

- AI proposal versus human approval/modification/rejection/no action.
- Proposal/assignment/execution/closure counts, first-response latency, overdue items.
- Configured estimated costs versus recorded **actual** costs with missing-state indicators.
- Source-backed observed outcomes after action, with completeness and proper action anchor.
- Optional grouping by available segment/action type. Never invent unsupported categories.

**Model health — Can the team trust it?**

- 7/14/30-day valid-label counts, maturation coverage and observation windows.
- Current model/calibration/feature version and candidate release status.
- Mature-cohort PR-AUC, Brier/calibration, Recall@K versus documented baseline when available.
- Reliability, freshness, source coverage and alert/abstention trends.
- `N/A` and caveats for small sample sizes, incomplete horizons or unsupported comparisons.

**Business constraints:** filters by authorized tenant, date/as-of range, horizon, available segment, route/action status, owner and currency. No need for arbitrary custom widgets. Manager sees prioritization/work; CSM sees assigned cases; admin/operator sees source/model quality. Action buttons open authoritative Part 3 cases.

### 8.5 End-to-end customer timeline

Authorized account detail shows traceable, ordered and linked events:

```text
Source event / availability and normalized account facts (Part 1)
    -> point-in-time feature + personal baseline
    -> prediction_id, as_of, p7/p14/p30, model/reliability (Part 2)
    -> route, exposure proxy, eligible actions (Part 3)
    -> original AI proposal, actual human choice, actor and timestamp
    -> action assigned/executed or explicit no intervention
    -> observed source-backed subscription state when follow-up matures
    -> per-horizon feedback + model evaluation/retraining status (Part 4)
```

Each timeline item links to its permitted source record and preserves actual event time **and** availability/record time. Before horizon maturity show **Outcome pending**. An account retained after an action is presented as an **observed association**, not automatic attribution of saved revenue.

### 8.6 Part 4 acceptance tests

- [ ] Feedback has correct per-horizon maturation/unknown/source-coverage behavior and immutable forecast linkage.
- [ ] Part 2 prediction feedback and Part 3 post-action follow-up use separate, explicit time anchors.
- [ ] Prediction metrics use mature cohorts and show sample counts/versions, not today's unmatured predictions.
- [ ] Model releases require independently evaluated evidence, explicit approval and rollback; rejected candidate is supported.
- [ ] Dashboard cost/risk/actuals reconcile with authoritative Parts 1–3 records; no invented ROI.
- [ ] Customer timeline traces every step to source/audit IDs and never leaks future outcomes into past screens.
- [ ] Tenant/role restrictions apply to dashboards, histories and model administration.

---

## 9. APIs and integration flow

These are **suggested stable interfaces**, subject to implementation naming, with request/response behavior constrained by the earlier contracts. Document any deviation in the API schema and `TEAM_LOG.md` before modifying downstream consumers.

| Method | Endpoint | Owner | Behavior |
|---|---|---|---|
| `POST` | `/v1/ingest/events` | P1 | Validated, authenticated, idempotent canonical event intake |
| `GET` | `/v1/integrations` | P1 | Source health / last-success / mapping version for authorized user |
| `GET` | `/v1/predictions/{prediction_id}` | P2 | Immutable unified 7/14/30-day snapshot / reliability/version |
| `GET` | `/v1/predictions?customer_id=...` | P2 | Tenant-scoped dated risk history |
| `GET` | `/v1/decision-cases?route=...` | P3 | Authoritative routed work queue |
| `GET` | `/v1/decision-cases/{case_id}` | P3 | Route reasons, provenance, proposals, human case state |
| `GET` | `/v1/decision-plan?capacity_k=...` | P3 | Policy-bounded shortlist; server validates allowed capacity |
| `GET` | `/v1/action-catalogue?case_id=...` | P3 | Data-eligible options, explanations, costs |
| `POST` | `/v1/decision-cases/{case_id}/decisions` | P3 | Role-checked accept/modify/reject/no-action + audit |
| `POST` | `/v1/decision-cases/{case_id}/assign` | P3 | Assigned person/team and due time |
| `POST` | `/v1/decision-cases/{case_id}/execution` | P3 | Executed/cancelled/failed event + actuals |
| `GET` | `/v1/decision-cases/{case_id}/outcomes` | P3 | Operational follow-up truth / completeness |
| `POST` | `/v1/scenarios/break-even` | P3 | Server-verified assumption-only ROI calculation |
| `GET` | `/v1/evaluation/decision` | P3 | Frozen retrospective strategy metrics |
| `GET` | `/v1/dashboard/overview` | P4 | Tenant-scoped risk/work/exposure/health aggregate |
| `GET` | `/v1/dashboard/decisions` | P4 | Human work and execution analytics |
| `GET` | `/v1/dashboard/outcomes` | P4 | Mature follow-up and actual churn summaries |
| `GET` | `/v1/dashboard/model-health` | P4 | Mature-cohort model quality and coverage |
| `GET` | `/v1/customers/{customer_id}/timeline` | P4 | Full source-to-outcome authorized trace |
| `GET` | `/v1/predictions/{prediction_id}/feedback` | P4 | Per-horizon maturity and label proof |
| `GET` | `/v1/model-registry/current` | P4 | Current approved model |
| `GET` | `/v1/model-registry/candidates` | P4 | Candidate evaluation, readiness and status |
| `POST` | `/v1/model-registry/{model_version}/review-decision` | P4 | Restricted approve/reject promotion and audit |

**Operational APIs:** training, label maturity refresh, import and replay jobs may be internal commands rather than public endpoints. Avoid exposed unauthenticated `POST /train`. Request `tenant_id` is always derived from authenticated context; state-changing endpoints require authorization, idempotency and transaction-safe budget checks.

---

## 10. Evaluation and evidence standards

### 10.1 One historical dataset family, one frozen test procedure

1. Select/source-authorize timestamped histories with churn-effective outcomes and observation coverage.
2. Convert training/evaluation/replay events to the **same canonical event semantics and identity scheme**.
3. Split chronologically, with label-maturation controls; tune on train/development/calibration only.
4. Freeze model artifacts, calibration, routing thresholds, costs/policies and alert budget before final evaluation.
5. Replay the held-out event stream chronologically, applying `occurred_at` and availability rules.
6. Generate actual snapshots and predictions using the production path; persist versions and outcomes separately.
7. Reveal future outcome only after earlier forecasts and case decisions are recorded.
8. Compute all reported metrics from test outputs; report failures and `N/A` fairly.

**Never** replay unrelated synthetic Stripe transactions as evidence of model accuracy on historical customers. Synthetic fixtures are allowed for integration UI/tests with unmistakable labeling.

### 10.2 Metrics by layer

| Owner | Metric or evidence | Interpretation / limitation |
|---|---|---|
| P1 | timestamp/identity coverage, schema rejects, duplicate suppression, freshness, failed source events | Data readiness, not model quality |
| P2 | 7/14/30-day PR-AUC, ROC-AUC, Brier/calibration, prevalence, sample sizes | Historical predictive skill by mature horizon |
| P2 | recall@fixed K, warning lead time, false alerts/workload, personalization ablation | Operational warning quality at matched alert volume |
| P2 | abstention/limited shares; error by reliability and availability | Whether warning trust metadata is meaningful |
| P3 | RevenueCaptured@K, Recall@K, investigation load, cooldown/eligibility/slot compliance | Retrospective identification and operational feasibility, **not actual saved revenue** |
| P3 | A risk-only / B p30×MRR / C reliability+cooldown+K ranking with ablations | Component tradeoffs when capacity is matched |
| P3 | budget vs actual costs, decision override reasons and lag | Observed workflow performance, not measured causal ROI |
| P4 | feedback maturity/completeness, evaluation version and sample size | Source-backed label quality |
| P4 | candidate vs incumbent under untouched test, gated approval outcome | Controlled model governance, no guarantee of improvement |

### 10.3 Forbidden claims and display hygiene

Do not label any of these as empirical results without their supporting data:

- “X% churn reduction,” “RM X saved,” “Y% action effectiveness,” “ROI improved,” or “customer was saved by the AI.”
- Churn risk values copied from a hypothetical example rather than model inference.
- Lead-time improvements derived from a static dataset without historical timestamps.
- “Model is 90% confident” inferred from the reliability gate.
- Cost savings inferred from merely configured staff/action cost parameters.
- Action causal effectiveness inferred from a treated customer's subsequent continued subscription.
- Retraining improvement inferred from training accuracy or test leakage.

Source-backed production values, **synthetic demo values**, **configured assumptions**, and **validated holdout measures** must be distinctly labeled.

---

## 11. Security, operations, and data governance

**Privacy / tenant boundaries**

- Tenant identity must be server-derived and consistently enforced for feature jobs, labels, forecasts, review lists, dashboards and exports.
- Store credentials only in secret management/environment configuration, never source/frontend or commit logs. Avoid raw payment-card fields and unnecessary PII.
- Use source allowlists, data minimization *before storage*, redacted logs, explicit account identity and basic user RBAC (`ADMIN/ML_OPERATOR`, `MANAGER`, `CSM`, `VIEWER` as appropriate).
- Require role checks for model release, financial/contract changes, overrides and action approval. Preserve audit actors and timestamps.
- An intervention trial must never remove legally or contractually required service, security notices or ordinary support.

**Correctness / resilience**

- UTC event, availability, decision and observation times; preserve source timezone when needed for display.
- Stable IDs and idempotent event/decision ingestion; atomic quota/budget enforcement under concurrent users.
- Append-only history for meaningful decisions, model releases and corrected outcomes (or explicitly versioned supersession).
- Source freshness / delayed ingestion visible; no silent `unknown -> negative` conversion.
- When source/model/maturity jobs fail, retain the prior approved model and keep existing cases/workflows usable.
- Keep generated artifacts and schema/model/policy versions reproducible; log run parameters and provenance.

**Testing minimum**

1. Cross-tenant read/write denial for every endpoint.
2. Event idempotency, invalid input, missing IDs, restricted fields and redacted failure logs.
3. Leakage cases: after-`as_of` events, late-arriving facts, known pending cancellation, train/test overlap.
4. Subscription valuation: annual/monthly, recurring discounts, zero-decimal and mixed currencies, multi-subscriptions.
5. Prediction: null/abstain, cold start, horizon ordering and calibration test.
6. Decision: correct routes, p30×MRR/K, cooldown, unavailable actions, concurrent approval quota.
7. ROI: absolute pp versus percentage, break-even infeasibility, zero denominator and no fabricated uplift.
8. Feedback: horizons not mature, incomplete observation, late corrections, action versus prediction anchor.
9. Model release: insufficient evidence -> NOT_READY, failing candidate -> REJECTED, authorized promotion/rollback.

---

## 12. User experience and dashboard requirements

### 12.1 Minimum pages/navigation

| Screen | Purpose | Main interaction |
|---|---|---|
| **Integration & Data Health** (P1 view) | Data source state, mapping, coverage, freshness and rejects | Inspect integration; correct config with permission |
| **Prediction Radar** (P2 + P4 view) | Risk distribution, 7/14/30 forecasts, baseline deviations, warning age/reliability | Open forecast/account evidence |
| **Decision Cases & Strategy Lab** (P3 view) | Reliable priority queue, investigation queue, eligible options, costs, slots, one-month scenario | Approve/modify/reject/no-intervention as authorized |
| **Business Command Center** (P4 view) | Overview, decision/action analytics, source-backed outcomes and model-health summaries | Filter/inspect, navigate to authoritative case |
| **Customer Timeline** (P4 view) | Explain the entire record from source events to mature feedback | Trace IDs, review time/version and known-at-the-time data |

Product should feel like **one application with linked records**, not four disconnected dashboards. Simple filters and role-specific layouts suffice; no drag/drop BI editor.

### 12.2 Required UI semantics

- Clearly show horizon, cutoff and model version next to every risk number.
- Use three route names only (`PRIORITY_REVIEW`, `HUMAN_REVIEW`, `OBSERVE`) plus the explicit nonpredictive states; show reasons and time urgency separately.
- Distinguish **data insufficient**, **no action selected**, **outcome pending**, and **observed retention**.
- Any missing MRR/exposure or low-sample model metric displays `N/A`/reason, not fabricated `0`.
- Label ROI `SCENARIO_ONLY`, show assumptions and separate absolute pp from relative baseline-risk percentage.
- Never display an unsupported action as executable; disable or move to a synthetic demonstration section.
- Human decision flows show owner, cost, pending status and auditable reason.
- A timeline must not reveal future outcomes in a historical pre-cutoff view.

---

## 13. End-to-end demo and test plan

### 13.1 Primary judge demo: one account, real data path

1. **Connect:** Show the selected authorized historical dataset, source contract and live Push API receiving a held-out timestamped event.
2. **Process:** Show canonical account identity, normalized activity/billing and as-of data-availability proof.
3. **Predict at T1:** Generate and save actual model p7/p14/p30 plus personal baseline, reliability/freshness and version.
4. **Advance to T2:** Replay later real events (not future outcomes yet), rescore with the frozen model and show whether warning emerges or changes.
5. **Route and value:** Show correct Part 3 route reason, `p30 × MRR`, K review priority, and investigation handling if data are weak.
6. **Recommend:** Show **only data-supported** candidate action(s), supporting observed fact ID and `NO_INTERVENTION`.
7. **Plan and simulate:** Show case/approval budget, staff minutes, and recalculate one break-even/ROI card after a user changes an assumption.
8. **Human decides:** Approve/modify/reject, preserve original suggestion and final actor/time/owner; label any mock human action as synthetic.
9. **Reveal the outcome:** Move replay clock forward, reveal source-backed churn/retention and per-horizon mature feedback separately from action follow-up.
10. **Command Center:** Show sourced dashboard totals, the full customer timeline and mature evaluation evidence.
11. **Learning governance:** Show a real evaluated candidate model and justified promote/reject decision **if eligible training/test evidence exists**; otherwise demonstrate the honest NOT_READY gate and why.

**No preprogrammed results:** example churn probabilities, lead-time gains, retained revenue and model-improvement statistics cannot be silently substituted for measured replay outputs. A hypothetical financial card can use explicitly user-configured assumptions.

### 13.2 Minimum integration tests

| Test | Expected result |
|---|---|
| Push identical event twice | One normalized source event, repeat request safely idempotent |
| Insert event `occurred_at <= T` but available after T | Feature snapshot at T excludes it |
| Known cancellation requested before T | No prospective scored p7/p14/p30; separate cancellation state |
| Missing required customer/account data | Explicit abstention/investigation, not made-up 0% risk |
| `p30=0.65, MRR=1200` | Exposure proxy RM780 with same-currency comparison |
| Alice/Bob/Charlie reliable; Dana limited; K=2 | Bob and Charlie selected if eligible, Dana investigates |
| Action needing unavailable support ticket | Disabled in production (or clearly sandbox-only) |
| Parallel manager approvals exceed budget | Atomic rejection/authorized override, no silent overspend |
| `MRR=1200, margin=.7, cost=150, p30=.65, assumed effect=.1` | Break-even 17.86 pp; 27.47% baseline share; RM-66 net; ROI -44% |
| Unmatured 30-day horizon | `PENDING`, not negative or “saved” |
| No source coverage for a matured horizon | `INCOMPLETE`, not negative |
| Candidate has worse calibrated holdout performance | `REJECTED` or operator-blocked; incumbent remains serving |
| Cross-tenant account/case access | Denied; no leaked identifiers or values |

---

## 14. Delivery sequence, roles, and definition of done

### 14.1 Recommended delivery order

| Milestone | Deliverable | Why first |
|---|---|---|
| **M0 — Evidence gate** | `DATASET_CARD.md`, churn policy, dated feature/label feasibility, chronological splits | Multi-horizon predictions impossible to validate without it |
| **M1 — Core contracts** | Identity, canonical events, subscription history, stable prediction ID, versioned API schemas | Separate teammates can integrate without guessing |
| **M2 — Part 1 ingestion** | Historical importer, Push API, tenant auth/minimization, event+MRR integrity | Live foundation and replay share path |
| **M3 — Part 2 baseline and model** | Labels, personalized features, rule/logistic/LightGBM, calibration, reliability, real predictions | Predictive track's scientific core |
| **M4 — Part 3 decision flow** | Routing, exposure sorting, K, narrow actions, approval, tracking, break-even card | Turn prediction into human-governed decision |
| **M5 — Part 4 visibility** | Mature feedback, account timeline, business dashboard and model-health | Complete product with result trace |
| **M6 — Closed-loop governance** | Evaluation run, candidate comparison if valid, model registry release decision | Safe learning rather than unverified online updates |
| **M7 — Final judge replay** | One held-out coherent dataset, real end-to-end demo + evidence report | Shows integration and honest differentiation |

### 14.2 Suggested team ownership (assign actual names in repo)

| Workstream | Responsibility | Primary contract handoff |
|---|---|---|
| Data/backend | Part 1 ingestion, schema, source/identity/security, MRR | Feature and event contract to ML; factual inputs to decisions |
| ML | Part 2 features/labels/model/calibration/reliability/eval | Immutable `prediction_id` and probability payload |
| Backend/decision | Part 3 routes/action catalog/budget/approval | `case_id` and append-only human/outcome history |
| Frontend/product | Dashboards, case actions, timeline, ROI UI | Consumes authoritative APIs, no fabricated metrics |
| QA/integration owner | Replay harness, cross-tenant tests, model gate, Part 4 feedback | Reproducible full trace and acceptance checks |

If team is small, people can own multiple workstreams; the **interfaces and tests** still need explicit owners. Change the shared contract only with coordinated updates and log entry.

### 14.3 Every commit must be documented

Every team member updates **`TEAM_LOG.md` in the same Git commit as their code/docs change**. Include timestamp (UTC), author, workstream, commit subject, changed files, concrete changes, test commands and results, remaining risks/blockers, and next action. Never invent a Git hash before making the commit. Coding agents must obey `AGENT.md`; if the repository's agent tooling recognizes only `AGENTS.md`, copy the same rules there.

**Ready to merge** means: correct tenant/time/currency contracts; relevant tests run (or explicit reasons they could not); no leaked secret/PII; APIs/types/docs updated; `TEAM_LOG.md` staged in the same commit; no unmeasured metrics or false ROI claims; another member can reproduce the relevant workflow.

---

## 15. Risks, dependencies, and deferred features

| Risk | Consequence | Mitigation / decision |
|---|---|---|
| No timestamped labeled historical dataset | Cannot validate multi-horizon early warnings | Dataset gate first; honest synthetic-only demonstration if needed |
| Subscription status recorded only as latest snapshot | Historical cutoff leakage or missing as-of eligibility | Keep minimal append-only subscription state changes/time-aware reconstruction |
| Part 1 originally assumes only 30d prediction | P2 7/14/30 labels and P3 urgency break | Canonicalize all three labels/probabilities before coding consumers |
| Part 2 and Part 3 prediction JSON shapes differ | Frontend/backend integration fails | Single flat probability payload + stable `prediction_id` |
| `reliability` mistaken for calibrated confidence | False certainty | Status+reasons only; `uncertainty=not_quantified` until validated |
| A support/plan recommendation lacks source data | Unsupported action | Enabled-mode/required-fields catalog, disabled/simulation-only until wired |
| Large-budget simulator implies optimal action uplift | Misleading ROI | Top-K review planner plus one transparent break-even scenario |
| Human team lacks capacity for investigation | Queue looks feasible but is not | Show investigation burden; account for common staff capacity |
| Interventions bias observed labels | Misinterpret action effect and retraining | Log exposure, separate observation from causality, require independent test |
| Retraining silently deploys degraded model | Operational regression | Release gate, operator authorization, rollback |
| Multiple customers/tenant privacy leakage | Data protection failure | Server-derived tenant, scoped authorization, negative tests |
| Demo uses fabricated “saved revenue” | Judge credibility failure | Distinct provenance labels and reproducible actual replay metrics |

**Deferred with rationale:** extra connectors, raw support/CRM integrations, autonomous outreach, deep text models, multi-arm uplift, causal experiment platform, multi-bundle optimization, self-modifying online models and unrestricted BI builder. They should not block the core predictive demonstration.

---

## 16. Cross-part acceptance checklist

The following are the **integrated product-level gates**, in addition to per-part checklists.

### Data and predictive validity

- [ ] Dataset provenance/permission, scope, event timestamps, label coverage and censoring documented.
- [ ] The same canonical schema supports import, replay, Push API and inference.
- [ ] Account identity, subscriptions and monetary values are tenant-scoped and time-correct.
- [ ] Multi-horizon labels and probabilities are genuine or explicitly marked unvalidated/synthetic.
- [ ] No label/event after `as_of` is used for earlier feature computation.
- [ ] Rule/logistic/full model fair comparisons and personalized-feature ablation are reproducible.
- [ ] Calibration, horizon monotonicity, abstention/reliability and model versioning work.

### Decisions and human control

- [ ] `prediction_id` joins to exactly the decision context and eventual feedback.
- [ ] Three routes and two nonpredictive states are used consistently across API, DB and UI.
- [ ] Ranked K and p30×MRR use comparable currency, reliable evidence and cooldown policy.
- [ ] Action library enforces available facts; unsupported support/plan/discount paths are disabled.
- [ ] Backend enforces human authorization plus staff/budget caps under concurrency.
- [ ] Break-even scenario is reproducible and always labeled assumption-based.
- [ ] Original proposal, human decision, action execution and observed outcome are distinguishable and auditable.

### Feedback, dashboard, demo and teamwork

- [ ] Per-horizon prediction feedback matures only with valid source-backed follow-up.
- [ ] Actual outcome is not automatically labeled as a causal save.
- [ ] Model re-release requires independent evaluation, authorization and rollback; NOT_READY is permitted.
- [ ] Dashboard values reconcile to authoritative source tables with model/date/missingness labels.
- [ ] Customer timeline traces a real account from event to forecast to decision to outcome feedback.
- [ ] Historical demo reveals future outcomes only after saving original predictions.
- [ ] Cross-tenant access/security and ingestion/decision idempotency tests pass.
- [ ] `TEAM_LOG.md` entry accompanies **every Git commit** and tests/blockers are reported truthfully.
- [ ] Team follows `AGENT.md` (and optional `AGENTS.md` alias) for implementation safety.

---

## 17. Source alignment and integration decisions

This document is integrated from the following **user-provided** specifications, without pretending that any item has been implemented or empirically validated:

- `RetainIQ_v2_Data_Foundation.md` — Part 1
- `RetainIQ_v2_Part2_Prediction_Engine_Requirements.md` — Part 2
- `RetainIQ_v2_Part3_Decision_Engine_Requirements.md` — Part 3
- `RetainIQ_v2_Part4_Closed_Loop_Learning_and_Dashboard_Requirements.md` — Part 4

**Explicit decisions made to reconcile conflicting/underspecified original contracts:**

1. **7/14/30 days becomes canonical:** Part 1's 30-day-only objective/schema is amended to supply per-horizon labels, while Part 2 keeps all three real classifiers/labels. This is a coordination decision, not a claim the existing implementation already supports it.
2. **Stable `prediction_id` plus `prediction_run_id`:** use one account snapshot row with p7/p14/p30; preserve run ID separately. Earlier long-form and nested JSON examples require adapters/migrations.
3. **Time-aware subscription history:** introduce an append-only subscription change representation for accurate historical as-of reconstruction; this is an integration design addition beyond Part 1's original eight logical tables.
4. **Route names standardized:** `PRIORITY_REVIEW`, `HUMAN_REVIEW`, `OBSERVE` with `KNOWN_CANCELLATION` and `NOT_ELIGIBLE` states. Urgency is an attribute, not a fourth route.
5. **Reliability vs uncertainty:** only reliability/freshness statuses are operational in MVP; numerical uncertainty is reserved, never fabricated.
6. **Actions gated by sources:** check-in/payment recovery are MVP-operational; training conditional; support/plan/discount features are inactive without corresponding observed facts/policies.
7. **Resource optimization claim narrowed:** MVP does exact top-K review selection and transactional budget/staff enforcement, **not** a global mathematically optimal intervention portfolio or proven uplift.
8. **One-month ROI card only:** break-even and relative baseline-risk requirement are scenario inputs, not effect predictions.
9. **Distinct outcome time anchors:** prediction-quality feedback uses prediction cutoff; action follow-up uses execution/follow-up start.
10. **Controlled improvement:** Part 4 monitors mature feedback and gates candidate training/release; candidate failure or insufficient evidence is a valid outcome.

### Decisions still requiring real implementation/data evidence

- Dataset availability, licensing, historical coverage, subscription churn policy for multi-subscription accounts, and observed intervention-exposure completeness.
- Operational source-specific staleness limits, daily job schedule, routing thresholds and discretionary contact cooldown duration. Select thresholds using development data and documented business policy, not fictional examples.
- Action costs, staff minutes, contribution margin and budget/currency policy provided by real tenant configuration; no invented customer ROI claims.
- Exact storage migrations, chosen model/calibration artifacts, deployment stack, actual team owner names and future retention study design.

**Final product line:** **RetainIQ connects evidence -> personalized multi-horizon forecasts -> human-governed resource decisions -> observed outcomes -> verified prediction feedback.**
