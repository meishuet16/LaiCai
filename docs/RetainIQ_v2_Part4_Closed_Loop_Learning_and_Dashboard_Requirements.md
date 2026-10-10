# RetainIQ v2 — Part 4: Closed-Loop Learning & Business Command Center

**Track:** Predictive Model — Predict Early, Decide Better  
**Document type:** Part 4 implementation requirements  
**Status:** Proposed MVP specification, aligned with Parts 1–3  
**Core promise:** Connect real customer outcomes back to earlier forecasts and human decisions, monitor whether the prediction system still works, and make the results useful in a business dashboard.

## 1. Purpose

Part 4 closes the loop across the existing RetainIQ system:

- **Part 1 — Data Foundation:** Capture, validate, protect, normalize and time-stamp subscription, billing and usage data.
- **Part 2 — Prediction Engine:** Forecast eligible customers' cumulative churn probability within 7, 14 and 30 days, with personalized behavior features, explanations and a reliability gate.
- **Part 3 — Decision Engine:** Route cases, prioritize limited review slots, propose evidence-supported actions, present a break-even financial scenario, let humans decide, and record execution/outcomes.
- **Part 4 — Learn & Understand:** Reconcile those predictions and decisions with *subsequently observed* outcomes, evaluate/retrain models under safeguards, and give managers an end-to-end operational view.

**One-line pitch:** *RetainIQ does not stop at a risk score: it tracks what actually happened, checks its forecasts, and helps teams make the next decision with better evidence.*

### Part 4 owns

1. Outcome-to-prediction reconciliation and feedback maturity tracking.
2. Model performance monitoring, controlled candidate retraining and version governance.
3. Company-facing analytics and an auditable customer journey/timeline.

### Part 4 does not own

- New ingestion connectors or raw data validation (Part 1).
- Original point-in-time features or live churn model inference (Part 2).
- Action eligibility, budget allocation, approvals or execution recording (Part 3).
- A causal uplift model, real-time online learning, autonomous customer contact, or a general-purpose drag-and-drop BI builder (outside MVP).

## 2. End-to-End Architecture

```text
 [Part 1: Data Foundation]
 Historical + live usage / billing / subscription events
                |
                v
 [Part 2: Prediction Engine]
 Versioned 7/14/30-day forecasts + reliability + reasons
                |
                v
 [Part 3: Decision Engine]
 Review queue -> evidence-matched options -> human decision
                |                              |
                |                              v
                |                   Approved action / execution
                |                              |
                +------------------------------+
                                               |
                         Actual subsequent customer events
                                               |
                                               v
 [Part 4: Closed-Loop Learning & Dashboard]
   1. Match outcomes to earlier predictions at their own horizons
   2. Measure performance and feedback-data quality
   3. Create/test candidate model; promote only if verified
   4. Show risk, decisions, outcomes and traceable customer timelines
                                               |
                                               v
                         Next Part 2 prediction cycle
                         (only after model approval)
```

**Core distinction:** A *customer's observed subscription status* can be used as a prediction label after the relevant window matures. It is **not** proof that a prior intervention caused the customer to stay.

## 3. MVP Scope and Deliverables

| Component | Required MVP behavior | Outside MVP |
|---|---|---|
| Outcome feedback | Link each stored forecast to valid 7/14/30-day actual outcome labels when mature; preserve unknown/incomplete states | Treat all still-active customers as negative labels immediately |
| Performance monitoring | Show horizon-specific results for sufficiently observed historical cohorts, model versions and data-quality segments | Unsupported instantaneous accuracy claims |
| Controlled learning | Build and evaluate a candidate retrained model using eligible mature observations; keep the current model unless it passes the release gate | Retrain/deploy after every single customer outcome |
| Business dashboard | Risk overview, decision workload, action execution, observed churn and basic model quality | Unlimited custom widget builder |
| Customer timeline | Trace source evidence -> feature/prediction -> routing -> human choice -> action -> actual outcome -> feedback status | Invented events or cause-and-effect claims |
| Historical replay demo | Advance a historical clock to show predictions before revealing future outcomes | Fake model-improvement percentages |

**MVP completion does not require showing that the new model is better.** A valid result can be “candidate failed the release gate; incumbent remains in production.”

## 4. Cross-Part Inputs and Ownership

Part 4 **reads** authoritative records from the preceding parts rather than duplicating their business logic.

| Data | Source / owner | Required fields or guarantees | Part 4 usage |
|---|---|---|---|
| Canonical events and subscription lifecycle | Part 1 | `tenant_id`, `customer_id`, `occurred_at`, `received_at`, event/source IDs, subscription status and effective churn timestamp | Establish observable truth and data coverage |
| Monetary details | Part 1 | normalized MRR, `currency`, source timestamp and definition | Segment analysis; correctly labeled risk exposure |
| Historical labels | Part 1 label builder / Part 2 training pipeline | `tenant_id`, `customer_id`, `as_of`, `horizon_days`, `label`, `outcome_at`, `label_observed_through` | Reconcile mature prediction outcomes; training/evaluation only |
| Versioned forecast | Part 2 | `prediction_run_id`, `as_of`, `model_version`, `feature_version`, `calibration_version`, `status`, `p_churn_7d`, `p_churn_14d`, `p_churn_30d` | Evaluate the exact forecast made at the time |
| Prediction trust metadata | Part 2 | `reliability.status`, reasons, `data_freshness.status`, source cutoff, reserved `uncertainty` | Stratify errors and show trustworthy UI warnings |
| Human decision trace | Part 3 | `case_id`, `prediction_run_id`, route, proposal, `APPROVE`/`MODIFY`/`REJECT`/`NO_INTERVENTION`, reason, actor, timestamps | Display the original proposal and actual choice |
| Execution and follow-up | Part 3 | executed action, owner, actual cost if known, timestamps, `outcome_observations`, completeness | Operational metrics and a customer timeline |

**Compatibility rules**

- Every join includes authenticated `tenant_id`; never connect customers across tenants by similar names or emails.
- Prediction labels are anchored to **prediction `as_of`**, whereas operational follow-up periods may be anchored to **action execution time**. Do not mix these windows.
- `reliability.status` stays `sufficient_evidence | limited_evidence | insufficient_evidence`; `data_freshness.status` stays `fresh | partially_stale | stale | unknown`.
- The reserved `uncertainty` object may say `not_quantified`. Do not manufacture numeric uncertainty intervals in the dashboard.
- Part 3 routes remain `PRIORITY_REVIEW`, `HUMAN_REVIEW`, `OBSERVE`, and nonpredictive `NOT_ELIGIBLE`/`KNOWN_CANCELLATION` states.
- Churn labels and future outcomes **must never appear in a live model's input features at the earlier `as_of` time**.

## 5. Feature 1 — Outcome-Based Prediction Feedback

### 5.1 What the system learns from

For each **eligible historical forecast** made at time `t`, Part 4 checks the subsequent customer/subscription lifecycle through `t + h`, where `h` is 7, 14 or 30 days.

| Feedback state | Meaning | Include in horizon-specific supervised evaluation/training? |
|---|---|---|
| `PENDING` | Outcome horizon has not finished | No |
| `MATURE_POSITIVE` | A qualifying actual churn occurred inside `(t, t+h]` | Yes: label `1` |
| `MATURE_NEGATIVE` | Entire horizon is adequately observed and qualifying churn did not occur | Yes: label `0` |
| `INCOMPLETE` | Horizon passed, but source coverage/identity/outcome proof is insufficient | No |
| `INELIGIBLE` | Customer was not eligible for prospective churn prediction at `t` | No |

A **failed payment is not churn by itself**. A pending cancellation already known by `t` is handled as a separate known-cancellation state, not an undisclosed predictive target. Apply the same voluntary/non-renewal/involuntary churn definitions agreed in Part 1.

The label comes from authoritative time-stamped lifecycle data, not a salesperson's “probably retained” note. If records are corrected later, regenerate affected feedback with an audit trail and an explicit label-policy version.

### 5.2 Data availability and observation maturity

- Evaluate only snapshots with source coverage sufficient to establish the outcome for the full horizon; an account still active today is not automatically a valid negative for a forecast made yesterday.
- Preserve both the business event time (`occurred_at`) and the time the event became available to the system (`received_at`). Historical replay must not let late-arriving future information leak backward.
- Store outcome source/provenance, observation cutoff, prediction version and feedback computation time.
- Keep evaluation cohorts separated by horizon, model version, tenant/segment where permitted, and enough observation time.
- Mark source outages, uncertain identity and incomplete billing coverage rather than silently treating missing data as retention.

### 5.3 Observation is not intervention effectiveness

Example:

```text
Day 0:  Bob receives P(churn within 30 days) = 0.80.
Day 2:  Human approves and completes an account check-in.
Day 30: Bob remains subscribed, with full observation coverage.
Result: 30-day observed churn label = 0.
```

This is a valid **negative outcome label**. It does **not** imply that the model was “wrong” merely because a probabilistic 80% event did not occur, nor that the check-in saved Bob. Action assignment is not random: intervention-exposed customers can systematically differ from uncontacted customers.

**MVP safeguard:** Keep intervention exposure (`none / known / unknown`) and relevant action timing for cohort reporting. Monitor performance overall and by exposure where sample sizes allow. Do not use future action events as features for a prediction already made. Interpret retraining on intervention-affected labels as learning from outcomes under the observed operating policy, **not learning causal action uplift**. If exposure bias is material, restrict or defer model promotion until evaluation is credible.

## 6. Feature 2 — Controlled Model Improvement

### 6.1 Feedback cycle

1. **Collect:** New subscription and billing outcomes arrive through the existing Part 1 process.
2. **Reconcile:** Match the appropriate mature outcomes to immutable Part 2 predictions and record the feedback state.
3. **Monitor:** Calculate prediction error/calibration and data-quality indicators on eligible mature cohorts.
4. **Decide whether retraining is justified:** Require sufficient new, valid labels, reasonable coverage and a documented evaluation plan. If not, keep monitoring.
5. **Train a candidate:** Run the same Part 2 feature definitions and modeling pipeline on valid, authorized history, with a new model/calibration version. Maintain time-order and tenant privacy rules.
6. **Evaluate against incumbent:** Compare on a suitable *untouched* later chronological holdout (or prospective shadow window), using matched alert budgets. A customer/outcome used to fit or tune a candidate must not also be used as its final held-out proof.
7. **Promote or reject:** An authorized operator approves promotion only if quality, calibration, safety and regression gates pass. Otherwise retain the current model.
8. **Audit and roll back:** Record versions, metrics, approvals and deployment time; allow a prior known-good model to be restored.

### 6.2 Minimum model checks

Evaluate **7, 14 and 30 days separately** where labels are mature:

- **PR-AUC:** Ability to rank churners in an imbalanced population; show prevalence/context.
- **Brier score / calibration:** Whether predicted probabilities align with observed event frequencies.
- **Recall@K and false-alert workload:** Comparisons at the same review or alert budget.
- **Time-to-warning / warning lead time:** Only for qualifying detected churn events during chronological replay; report missed events too.
- **Reliability and freshness cohorts:** Missingness, abstention fraction, model performance in `sufficient_evidence` vs `limited_evidence` groups, and source staleness.
- **Segment stability:** Only show customer cohorts with adequate support; suppress misleading tiny-sample estimates.
- **Horizon coherence:** Check cumulative probabilities satisfy `P(7d) <= P(14d) <= P(30d)` when all are present.

Make model comparison conditional on enough independent cases and a predefined release policy. **Do not automatically promote merely because one aggregate metric improved slightly.** A release may be blocked by degraded calibration, unstable subgroup performance, incomplete labels or leakage concerns.

### 6.3 Operational cadence

- **Daily or scheduled:** Refresh feedback maturity and dashboard aggregates as source data permits.
- **Periodic / on demand:** Evaluate model drift/performance on sufficiently mature cohorts.
- **Candidate retraining:** Trigger only with adequate new information or documented degradation; no per-event online training requirement.
- **Production deployment:** Explicit operator approval, not a background self-modifying production model.

No guarantee of automatic improvement is implied. The honest promise is **controlled learning with measurable evaluation**.

## 7. Feature 3 — Company Business Dashboard

The dashboard answers business questions without requiring managers to interpret a full ML research report. Build on the same source tables, prediction versions and Part 3 cases.

### 7.1 Overview — “What needs attention now?”

Show, filtered to the authorized tenant and chosen date:

- Eligible customers monitored and prediction coverage, separated from abstained/ineligible accounts.
- Current `PRIORITY_REVIEW`, `HUMAN_REVIEW` and `OBSERVE` counts.
- 7/14/30-day risk distribution and change over time **with clear forecast dates and model versions**.
- **MRR-weighted 30-day churn exposure proxy** for comparable eligible accounts, with currency and missing-MRR coverage visible. Never label it guaranteed loss.
- Open actions, overdue follow-ups, human-review backlog and owner workload.
- A compact source freshness/integration health summary linked to Part 1.

### 7.2 Decision & Outcome Analytics — “What did the team do?”

- Original AI action proposal vs final human choice (`APPROVE`/`MODIFY`/`REJECT`/`NO_INTERVENTION`).
- Action case counts by state: proposed, assigned, executed, pending follow-up and closed.
- Review response time and overdue action count.
- Estimated versus **recorded actual** costs, clearly indicating when costs are assumptions or missing.
- Observed subscription outcomes after action, with status and follow-up completeness.
- Basic grouping by customer segment/action type **only when the supporting facts exist**; otherwise display unavailable rather than inventing dimensions.

**Forbidden KPI:** “Revenue saved by AI” or “retention uplift” computed merely by counting active accounts after an intervention. Such figures require appropriate causal evidence, not just observed follow-up.

### 7.3 Prediction Quality — “Can we trust the model?”

Use **mature labeled cohorts**, not the current live population, for performance metrics:

- Number of valid 7/14/30-day labels and observation coverage.
- Current production model version and candidate/approval status.
- Horizon-specific PR-AUC, Brier/calibration and Recall@K against named baselines where measurable.
- Breakdown by evidence reliability, freshness and major documented segment.
- Trend in missing/outdated input data and abstention rate.
- Latest evaluation date, sample sizes, and warnings when insufficient for a reliable conclusion.

The UI must distinguish **live forecast totals** from **historically evaluated results**. It must not compute a “today's 30-day accuracy” from forecasts that have not yet had 30 days to mature.

### 7.4 Practical configuration, not a BI builder

MVP supports standard filters for date/as-of period, forecast horizon, customer segment (if in data), action/route state and owner; currency-specific reporting unless a documented conversion policy exists. Saved default filters are optional.

Role-based views can be simple:

- **Manager:** risk, open decisions, budget/action workload, actual outcomes.
- **Customer Success team:** assigned cases, due actions and relevant customer history.
- **Admin / ML operator:** data freshness, feedback coverage, model health and candidate release status.

Dashboard must not duplicate Part 3's approval engine: actionable customer links open the authoritative Part 3 case/workspace.

## 8. Feature 4 — End-to-End Customer Timeline

A customer detail view makes every step traceable. Events remain ordered by **event time** while also preserving **recorded/available time**.

Example, with clearly hypothetical values:

```text
Customer: Bob                 Example only

2026-08-01  Product usage events recorded
2026-08-08  Sessions/week fell below Bob's own baseline
2026-08-09  Part 2 made a 30-day forecast; version + reliability stored
2026-08-09  Part 3 routed Bob to a human review case
2026-08-10  AI proposed an account check-in; manager approved
2026-08-11  Team marked the check-in completed; actual cost logged
2026-09-08  The 30-day observation horizon became mature
2026-09-08  Source-backed outcome recorded; feedback linked to forecast
Next review  Feedback enters model evaluation / eligible training dataset
```

Show links to the underlying event IDs or authorized record summaries, and retain the original AI proposal even if a human modifies it. For a future-dated horizon, show **“Outcome pending”**, not an assumed success/failure.

**The timeline must not imply that an executed intervention caused the observed outcome.** For each prediction, display its data cutoff, version, actual risk values if scored, reliability explanation and what was known at that moment.

## 9. Data Storage and API Boundaries

### 9.1 Reuse rather than duplicate

Existing core tables remain owned by Parts 1–3:

- Part 1: `subscriptions`, `billing_events`, `usage_events`, `churn_labels` and customer identity mapping.
- Part 2: `feature_snapshots`, `predictions` and model-versioned forecast metadata.
- Part 3: `decision_cases`, `action_proposals`, `human_decisions`, `outcome_observations`.

### 9.2 Minimum Part 4 records

| Table / record | Main fields | Why it exists |
|---|---|---|
| `prediction_feedback` | `tenant_id`, `feedback_id`, `prediction_run_id`, `customer_id`, `horizon_days`, `feedback_status`, `label?`, `outcome_at?`, `label_observed_through`, `label_policy_version`, `outcome_source_ref?`, `intervention_exposure_status`, `evaluated_at` | Immutable/versioned outcome linkage and maturity evidence |
| `evaluation_runs` | `evaluation_run_id`, `model_version`, `calibration_version`, `feature_version`, `evaluation_window`, `horizon_days`, `cohort_definition`, `label_policy_version`, `sample_count`, `metrics_json`, `created_at`, `data_provenance` | Reproducible model-performance results |
| `model_registry` | `model_version`, `calibration_version`, `feature_version`, `training_cutoff`, `scope`, `evaluation_run_id?`, `status`, `approval_actor?`, `promoted_at?`, `artifact_digest?` | Approved version, deployment and rollback audit |
| `retraining_runs` | `retraining_run_id`, `source_window`, `training_dataset_digest`, `candidate_model_version`, `split_policy`, `evaluation_run_id?`, `decision`, `decision_reason`, `operator_id?`, timestamps | Track retraining attempts and decisions |

Add `tenant_id` to run/version records wherever they are scoped to a tenant, or restrict global version metadata to authorized administrators. Do not join or expose one customer's raw record to a different tenant. Use keyed/versioned feedback updates or superseding records to handle corrected lifecycle events; never silently overwrite an evaluated outcome without provenance.

### 9.3 Suggested API surface

```text
GET  /v1/dashboard/overview?horizon=30d
GET  /v1/dashboard/decisions
GET  /v1/dashboard/outcomes
GET  /v1/dashboard/model-health
GET  /v1/customers/{customer_id}/timeline
GET  /v1/predictions/{prediction_run_id}/feedback
GET  /v1/model-registry/current
GET  /v1/model-registry/candidates
POST /v1/model-registry/{model_version}/review-decision  [admin only]
```

Feedback jobs and candidate retraining can be internal scheduled commands in MVP; a public `POST /train` endpoint is not necessary. Mutations require idempotency, operator authorization and an audit record. All read APIs enforce tenant and role access.

## 10. Security, Correctness and Product Guardrails

1. **Tenant isolation:** Enforce server-derived tenant identity and row-level access boundaries across forecasts, action history, analytics and model records.
2. **Data minimization:** Do not place protected email, payment-card information or free-form sensitive customer notes into dashboard exports or model features without a defined need and authorization.
3. **Point-in-time truth:** Historical model inputs use only data available by the forecast cutoff; outcome labels only join after the forecast for assessment/training.
4. **Non-leaking replay:** Use both `occurred_at` and `received_at` as appropriate to reconstruct availability; future subscription cancellations must never become earlier features.
5. **Observability:** Show freshness, missingness, insufficient observation and failed/late jobs rather than hiding them.
6. **Auditability:** Record who modified/published a model and when, with version, metrics and rollback path.
7. **Financial integrity:** Risk-weighted MRR, costs, observed revenue and hypothetical ROI must have different labels; never present hypothetical intervention effects as achieved financial returns.
8. **Causal honesty:** Recorded “retained” outcomes are observational. No causal savings claim without a valid comparison design.
9. **Fallback:** A failed feedback/retraining job must not erase predictions or disrupt the Part 3 human approval workflow.
10. **Permissions:** Staff can review their assigned cases; model promotion is a separate restricted privilege.

## 11. MVP Demo — One Customer, the Full Loop

Use a held-out historical stream with timestamped customer events and outcomes; document whether the dataset is real/authorized or synthetic.

1. **Part 1:** Ingest/replay dated usage, billing and subscription events through the same canonical processing path used by the live system.
2. **Part 2:** Freeze the replay clock at an earlier date; compute/store a real model prediction using only then-available input data. Show 7/14/30-day risk, baseline behavior and reliability.
3. **Part 3:** Generate the appropriate review route, risk-exposure rank, evidence-supported option and break-even scenario; show a human accepting/modifying/rejecting it. If this interaction is simulated, label it as such.
4. **Part 4, before maturity:** Show the customer timeline with `PENDING` outcome feedback; no future churn information on the earlier screen.
5. **Part 4, after advancing the clock:** Reveal the actual source-backed churn/retention outcome when the required horizon and observation coverage are complete. Reconcile feedback for each mature 7/14/30-day label.
6. **Part 4 dashboard:** Refresh the relevant observed outcome metrics and model evaluation with correct sample counts.
7. **Part 4 learning:** Demonstrate a candidate retraining/evaluation run with separate training and evaluation periods, then show either `PROMOTED` (only if predefined gates actually pass) or `REJECTED/NOT_READY` with reasons. Do not report an invented improvement.
8. **Traceability:** Open the case timeline and show original source events, prediction/model version, human decision, execution status, observed outcome and feedback status.

**Demonstration constraint:** Replay outcomes can support retrospective prediction evaluation. A replayed or hypothetical action does not prove the action saved the customer. Model gains require a genuinely independent test period or future validation.

## 12. Evaluation and Success Criteria

### Prediction-learning quality

- Feedback maturity correctness: no premature negative labels and no unknowns relabeled as retention.
- Completeness: percentage of due forecasts with source-backed, mature labels, separately for 7/14/30 days.
- Forecast quality: horizon-specific PR-AUC, Brier/calibration, Recall@K and alert lead-time where evaluation samples permit.
- Data-health breakdown: performance or abstention across `sufficient_evidence` and `limited_evidence`, freshness and observed intervention-exposure cohorts.
- Candidate governance: candidate/production versions, test boundaries, promotion decision and rollback history recorded.

### Business dashboard usefulness

- Cases awaiting review, action execution and overdue follow-up can be reconciled to the underlying Part 3 records.
- Predicted financial exposure is separated from actual churned MRR and observed costs.
- Every customer timeline entry resolves to a real, authorized timestamped record or is explicitly marked simulation/example.
- Manager can move from an aggregate risk insight to the corresponding Part 3 human decision case.
- All missing/insufficient metrics show `N/A`, low sample support or a reason; never a fabricated zero.

### What the MVP does **not** validate

- The causal effectiveness of training, discounts or account check-ins.
- Actual saved revenue or verified intervention ROI.
- That every retraining run will improve the model.
- A guaranteed “earlier alert” improvement unless measured against a baseline at a matched alert budget.

## 13. Suggested Build Order

1. Align Part 4 feedback keys (`prediction_run_id`, `customer_id`, `as_of`, `horizon_days`) with stored Part 1 labels and Part 2 forecasts.
2. Implement outcome maturation, source coverage checks and feedback status recording.
3. Build customer timeline from existing event, prediction and Part 3 decision history.
4. Implement dashboard overview and action/outcome counts from real database queries.
5. Add evaluation job and horizon-specific quality panels on mature cohorts.
6. Add model registry, candidate retrain procedure, independent comparison, approval and rollback.
7. Connect the chronological replay demo across all four Parts and test non-leakage.

**Hackathon fallback if time is tight:** Prioritize (1) correct feedback maturity, (2) the complete customer timeline, (3) a manager overview and (4) an honest before/after historical replay. A model-registry demonstration is more valuable than a rushed auto-retraining claim; candidate retraining should remain disabled until it can be evaluated properly.

## 14. Acceptance Criteria

- [ ] Part 4 uses the existing Parts 1–3 data/contracts; no duplicate action decision engine is introduced.
- [ ] Each prediction has a stable identity, model/calibration/feature versions, `as_of` and original stored probabilities.
- [ ] Each 7/14/30-day feedback label is derived from the correct horizon and qualifying actual lifecycle event.
- [ ] Pending/incomplete/known-cancellation cases are excluded from incorrect binary label assignment.
- [ ] Outcome feedback preserves source provenance, observation cutoff, label policy and late-correction history.
- [ ] Predictions are assessed using outcomes only **after** the prediction cutoff; no replay leakage.
- [ ] Human interventions and observed outcomes are linked but never interpreted automatically as proven causal savings.
- [ ] Current/live dashboard forecasts are clearly separated from mature historical model-evaluation cohorts.
- [ ] Dashboard counts, expenses and observed statuses reconcile with Part 3 authoritative records.
- [ ] No unsupported Technical Support or Plan Review recommendations are activated by Part 4; action eligibility remains in Part 3.
- [ ] MRR-weighted financial exposure is labeled as a proxy and kept separate from actual revenue/ROI.
- [ ] Model evaluation includes sample sizes, horizon-specific metrics, versions and missing/abstained cases.
- [ ] Candidate training uses chronological separation and a truly held-out evaluation window.
- [ ] Model promotion requires documented acceptance criteria and authorized approval; rejection is a valid outcome.
- [ ] The production model can remain unchanged or be rolled back without interrupting customer-case work.
- [ ] Tenant and role boundaries protect customer timelines, dashboards and model administration.
- [ ] A single end-to-end historical replay shows evidence -> forecast -> human decision -> outcome -> feedback without future-data leakage.
- [ ] Real, synthetic and scenario-only data are conspicuously differentiated in demos and analytics.

## 15. Final Product Positioning

| Layer | Product promise |
|---|---|
| **Part 1 — Connect** | Turn timestamped business data into secure, reliable customer evidence. |
| **Part 2 — Predict** | Forecast who may churn, how soon, what behavior has changed and how reliable the warning is. |
| **Part 3 — Decide** | Prioritize limited resources, match evidence-supported options, test financial assumptions and let humans choose. |
| **Part 4 — Learn & Understand** | Observe real outcomes, monitor and safely update predictive models, and give companies a traceable end-to-end decision dashboard. |

> **RetainIQ connects the full retention loop: evidence -> prediction -> human decision -> observed outcome -> verified model feedback.**

Part 4's distinctive value is **traceable, measured improvement**, not a promise that the system automatically improves after every customer event.
