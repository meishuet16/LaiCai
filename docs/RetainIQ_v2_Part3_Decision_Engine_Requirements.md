# RetainIQ v2 — Part 3: Decision Engine Requirements

**Track:** Predictive Model — Predict Early, Decide Better  
**Document type:** Standalone implementation specification  
**Status:** Proposed hackathon MVP; formulas and rules are design requirements, not measured results  
**Component name:** RetainIQ Decision Engine  
**Signature experience:** Human-Governed Retention Strategy Lab

## 1. Purpose and Product Promise

Part 3 turns Part 2's personalized churn forecasts into a **feasible, explainable, human-approved retention plan**. It answers five business questions:

1. **Who needs attention now?** Consider time-to-churn, reliability and observed revenue exposure.
2. **Which action is appropriate?** Match actions to verified customer facts, not guesses about causes.
3. **What can the team afford to do?** Respect available review slots, estimated costs, staff time and contact cooldowns.
4. **Would the action be worth its cost?** Show transparent break-even requirements and scenario ROI, never invented intervention effectiveness.
5. **What actually happened?** Record the original proposal, the final human choice, execution and later observed outcomes.

**One-sentence pitch:** RetainIQ helps subscription teams decide who to review, which fact-supported action to consider and what it would need to achieve to justify the cost—while keeping the final decision with a person.

### Boundaries between the three parts

| Component | Owns | Does not claim |
|---|---|---|
| Part 1 — Data Foundation | Secure event intake, identity mapping, historical facts, subscription prices, currency and normalized MRR | Predictive accuracy or action effectiveness |
| Part 2 — Prediction Engine | Calibrated cumulative 7/14/30-day churn forecasts, reliability/freshness, horizon explanations | The causal effect of a retention action |
| **Part 3 — Decision Engine** | Routing, exposure proxy, fact-matched candidate actions, review capacity, break-even scenarios, human decisions, observed outcomes | Proven revenue saved without a valid causal comparison |

## 2. Scope: What Must Ship

### MVP — required

- Read versioned Part 2 predictions and Part 1 subscription/usage/billing facts at a common `as_of` cutoff.
- Route cases into `PRIORITY_REVIEW`, `HUMAN_REVIEW` or `OBSERVE`; respect Part 2 non-eligible/known-cancellation states.
- Compute a **30-day MRR-weighted churn exposure proxy** when data are sufficient and money is comparable.
- Select up to **K priority-review accounts** using a deterministic, auditable sort with cooldown controls.
- Propose only actions supported by data actually present in Part 1; include `NO_INTERVENTION` and `DATA_INVESTIGATION`.
- Display configured action cost and estimated staff minutes; enforce budget/time limits **before approval or execution**.
- Provide **one interactive break-even / scenario ROI card** for a selected eligible action.
- Require human approval, modification, rejection or explicit no-intervention; preserve reasons and execution records.
- Track observed 7/14/30-day outcomes and run a frozen, time-correct historical ranking evaluation.

### Later enhancements — not required for MVP

- An independent budget-allocation simulator covering multiple alternative action bundles.
- OR-Tools / knapsack / global optimizer for mixed-cost action portfolios.
- Live CRM or support-ticket workflows not connected in Part 1.
- Automatic discounts, plan changes or customer messaging without manager authorization.
- AI-generated retention text, BERT, LLM routing, uplift or causal treatment-effect prediction.
- Live randomized holdouts or a production experimentation service.

**Naming rule:** The MVP is a **budget-aware review planner**, not a proven optimizer of retention gains. Its top-K review selection can be exact for a fixed number of slots, but does not prove optimal allocation among heterogeneous interventions.

## 3. End-to-End Decision Flow

```text
Part 1: timestamped customer facts + subscription/MRR
                    │
Part 2: p7 / p14 / p30 + reliability + freshness + versions
                    │
                    ▼
          Eligibility & Reliability Gate
             ├── not eligible / known cancellation → separate workflow
             ├── insufficient / stale / conflicting → HUMAN_REVIEW
             └── eligible + sufficient evidence → policy routing
                                         ├── OBSERVE
                                         └── PRIORITY_REVIEW
                                                    │
                                                    ▼
                                  p30 × MRR ranking + p7 urgency tie-break
                                                    │
                                                    ▼
                                     K review slots + cooldown controls
                                                    │
                                                    ▼
                                      Verified-fact action candidates
                                                    │
                                                    ▼
                             Cost / staff-time checks + Break-even ROI card
                                                    │
                                                    ▼
                               Human: approve / modify / reject / no action
                                                    │
                                                    ▼
                            Assigned → executed → observed follow-up outcomes
```

**Important:** A high churn score does not automatically trigger a discount, customer message or contract change.

## 4. Required Contracts with Parts 1 and 2

### 4.1 Part 1 facts needed by Part 3

| Source | Required fields | Decision use |
|---|---|---|
| `customers` | `tenant_id`, `customer_id`, `account_status` | Eligibility and case identity |
| `subscriptions` | `tenant_id`, `customer_id`, `status`, `started_at`, `ended_at?`, `cancellation_requested_at?`, `plan_id`, `billing_interval`, `billing_interval_count`, `amount_minor`, `currency`, `discount_minor?` | Eligible subscription and as-of MRR |
| `billing_events` | `tenant_id`, `customer_id`, `event_type`, `payment_status`, `occurred_at` | Verified payment-recovery eligibility |
| `usage_events` / features | `tenant_id`, `customer_id`, `event_type`, `occurred_at`, measured recent usage, personal/cohort reference | Check-in; optional training if feature-level gap exists |
| Identity / freshness data | Verified account mapping, `input_data_as_of`, source freshness | Prevent mistaken or stale decisions |
| Pricing policy | MRR normalization method, currency, contribution margin configuration | Comparable exposure and scenario calculation |

Every fact must be tenant-scoped, source-identifiable and available **at the decision cutoff**. For B2B cases, the prediction/customer key refers to the paying **account**, not each seat or employee.

Part 1's hackathon MVP does **not** guarantee support-ticket text, support resolution status, plan entitlements, customer price objections or historical treatment effects. Actions requiring those facts remain disabled or clearly marked as simulation-only.

### 4.2 Part 2 prediction contract

Part 3 consumes:

```json
{
  "tenant_id": "tenant_abc",
  "customer_id": "cust_001",
  "prediction_run_id": "run_001",
  "as_of": "2026-10-10T00:00:00Z",
  "status": "scored",
  "p_churn_7d": 0.12,
  "p_churn_14d": 0.38,
  "p_churn_30d": 0.81,
  "model_version": "mh_v1",
  "calibration_version": "cal_v1",
  "feature_version": "feat_v1",
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
  }
}
```

This is a **contract illustration**, not actual model output. The numbers above must not appear as pre-programmed demo predictions.

Required semantics:

- `status`: `scored | abstained | known_cancellation | not_eligible`.
- `reliability.status`: `sufficient_evidence | limited_evidence | insufficient_evidence`.
- `data_freshness.status`: `fresh | partially_stale | stale | unknown`, using documented source-specific freshness limits.
- `uncertainty`: **reserved** for statistically validated uncertainty estimates. `not_quantified` is legitimate; Part 3 **must not invent numerical confidence intervals**.
- Probabilities must be calibrated cumulative probabilities on `[0, 1]`, with `p7 <= p14 <= p30` where populated; an `abstained` case has null probabilities.
- Part 2 supplies SHAP-based model associations for display only; these **are not facts that establish an action's cause or effectiveness**.

## 5. Case Eligibility, Routing and Urgency

There are **three review routes** plus two nonpredictive states. Do not introduce undocumented routes such as `FINANCIAL_PRIORITY_REVIEW`.

| State/route | Trigger | Next step |
|---|---|---|
| `KNOWN_CANCELLATION` | Cancellation already requested/known by cutoff | Separate cancellation-recovery workflow; no prospective first-churn score |
| `NOT_ELIGIBLE` | Not in applicable paying-account prediction population | Exclude from prospective review ranking |
| `HUMAN_REVIEW` | Abstained, limited/insufficient evidence, material staleness, conflicting identity, or missing critical amount | Investigate data/account; do not propose discretionary offers as certain |
| `PRIORITY_REVIEW` | Eligible, sufficiently evidenced and fresh; meets validation-selected action-review policy | Competes for K review slots |
| `OBSERVE` | Eligible reliable account below review policy, or nonurgent case under discretionary-contact cooldown | Continue daily monitoring; record exclusions |

**Order of operations:** eligibility → reliability/freshness → policy threshold → cooldown → review ranking.

**Urgency is a separate attribute, not a fourth route.** For eligible accounts, `p_churn_7d` supplies an urgency indicator and sorting tie-breaker, while `p_churn_30d` supplies the main financial risk horizon. Urgency bands and review cutoffs are selected on validation data and stored under `policy_version`, not invented from a pitch example.

Treat `partially_stale` according to source importance and documented policy; stale critical subscription/billing facts block automated financial ranking. Limited evidence is not converted into a made-up numerical penalty.

**Cooldown:** after an executed discretionary outreach, suppress repeated discretionary proposals for a configurable period, but continue monitoring. Cooldowns must not block required billing notices, standard customer support or contractual obligations. Human overrides need a recorded reason.

## 6. Financial Risk Assessment and Ranking

### 6.1 Exposure proxy

For an eligible, sufficiently supported account:

```text
exposure_proxy_30d = calibrated_p_churn_30d × as_of_MRR
```

Interpretation: **MRR-weighted 30-day churn exposure proxy**. It is *not* an estimate of the exact next 30 days' cash loss, customer lifetime value or proven recoverable revenue.

- Normalize annual/quarterly/monthly contracted recurring amounts into MRR at the proper `as_of` date.
- Store original prices as minor units with an ISO currency code; normalize discounts consistently.
- Compare/rank accounts within **one currency** unless there is an explicit dated FX conversion policy.
- If MRR is missing or stale, expose `null` and route to `HUMAN_REVIEW`; do not substitute zero.
- Use Part 2's calibrated 30-day probability; do not replace it with arbitrary rule scores.

### 6.2 Review priority

Among eligible `PRIORITY_REVIEW` accounts within the same currency and cutoff:

1. Sort by descending `exposure_proxy_30d`.
2. Tie-break by descending `p_churn_7d` (near-term urgency).
3. Tie-break by oldest pending `case_created_at`, then stable account ID.
4. Select up to K accounts with available review slots; respect contact cooldown.

**K** means number of human **review slots** for the selected period, not a prediction of how many customers will be saved. `HUMAN_REVIEW` data investigations have a separately disclosed queue and staffing allocation. When staff time is shared across both queues, state the combined capacity explicitly rather than hiding extra human workload.

### 6.3 Arithmetic example (illustrative only)

| Account | `p30` | MRR (MYR) | Exposure proxy | Reliability | Handling |
|---|---:|---:|---:|---|---|
| Alice | 0.85 | RM100 | RM85 | Sufficient | Eligible review ranking |
| Bob | 0.65 | RM1,200 | RM780 | Sufficient | Eligible review ranking |
| Charlie | 0.78 | RM500 | RM390 | Sufficient | Eligible review ranking |
| Dana | 0.45 | RM900 | RM405 | Limited | Separate `HUMAN_REVIEW` investigation |

If all four had sufficient evidence, financial sorting would be **Bob → Dana → Charlie → Alice**. With Dana separated for investigation and **K = 2**, the financial queue picks **Bob and Charlie**, assuming both meet the validation-selected review policy and are not in cooldown.

The example demonstrates arithmetic and routing only. It is not a recorded RetainIQ prediction or measured customer result.

## 7. Personalized Next Best Action

### 7.1 Principle

The Decision Engine proposes **candidate actions**, never an unverified guaranteed best treatment. Matching is based on **observable, time-valid customer facts** and business policies, not on SHAP attribution or an LLM's guess.

The action catalogue must store: `action_code`, display name, `required_fields`, eligibility conditions, contraindications, estimated monetary cost with currency and source, estimated staff minutes, cooldown duration, approval level, version and enabled mode (`operational | simulation_only | disabled`).

### 7.2 Action catalogue and data availability

| Candidate action | Observable eligibility evidence | MVP status | Notes |
|---|---|---|---|
| `ACCOUNT_CHECK_IN` | Meaningful measured usage decline vs valid personal/cohort baseline | **Enabled** | Ask about usage changes; never assume dissatisfaction |
| `PAYMENT_RECOVERY` | Confirmed failed or past-due billing event | **Enabled** | Follow standard billing policy; no payment credentials in model |
| `PRODUCT_WALKTHROUGH` | Usage evidence **and** observed feature/onboarding gap | **Conditional** | If no feature-level telemetry, propose check-in instead |
| `DATA_INVESTIGATION` | Missing, inconsistent, old or limited evidence | **Enabled** | Investigate data before discretionary offer |
| `NO_INTERVENTION` | Any eligible case, subject to essential service duties | **Enabled** | Record reason and monitoring plan |
| `TECH_SUPPORT_ESCALATION` | Actual unresolved relevant support ticket/issue | **Future / simulation-only** | No support source in minimal Part 1 |
| `PLAN_REVIEW` / `PAUSE` / `DOWNGRADE` | Plan entitlement + actual usage/needs evidence + permission to change | **Future / simulation-only** | Must account for reduced recurring revenue |
| `CONDITIONAL_DISCOUNT` | Documented price objection + offer eligibility + approval | **Future / simulation-only** | High churn risk alone does not justify a discount |

A simulation-only action may appear in a clearly separate **demo sandbox**, but never as a real executable recommendation for an account without the required evidence.

### 7.3 Candidate generation procedure

1. Read up-to-date Part 1 facts at the case `as_of` cutoff.
2. Apply the action catalogue's required-data and eligibility rules.
3. Remove options violating cooldown, business policy, prior unresolved actions or approval permissions.
4. Present allowed options with **supporting fact IDs, explanatory reason, cost estimate and staff minutes**.
5. Offer `NO_INTERVENTION`; require a reason where action is rejected/overridden.
6. Let the human approve, modify, reject or defer within controlled states.

If the facts do not justify a specific intervention, the system proposes `DATA_INVESTIGATION`, not a generic discount.

## 8. Budget and Capacity Planning

### MVP behavior

- Admin configures review capacity **K** for the day/week, optional staff-minute cap and available discretionary retention budget by currency.
- Engine creates the **top-K human-review shortlist**, using Section 6 rules. This is not automatic action execution.
- Each candidate intervention shows estimated cost and employee time from an administrator-maintained action catalogue; actuals are entered after execution.
- At approval, the backend must reject or request explicit authorized override if a proposed set of approved actions would exceed the remaining budget/time cap. Simultaneous approvals must be handled atomically to prevent overspending.
- If a customer has a pending/open action, repeated proposals are suppressed according to the case policy; standard customer care is never suppressed.
- A manager may manually reprioritize, with reason and audit trail.

**MVP allocation guarantee:** the top-K review list respects slot limits; approved interventions respect separately configured spending/time limits. It does **not** solve a global multi-action cost-benefit optimization problem.

**Optional enhancement:** feasible greedy allocation across action-cost/time bundles or a constrained solver (e.g., OR-Tools), with objective and infeasibility handling documented. Without measured uplift, any objective is **risk-exposure coverage**, not expected saved revenue.

## 9. What-If and ROI: One Break-Even Scenario Card

### 9.1 Goal and inputs

For one eligible candidate action, let a manager ask: **"How much would this action need to reduce churn to break even?"**

Required inputs:

- Actual current `MRR` and its currency/as-of timestamp from Part 1.
- Administrator-configured `contribution_margin` in `[0,1]` (default explicitly labeled a business assumption).
- Estimated `action_cost > 0` from the catalogue, with editable scenario override.
- **Calibrated 30-day churn probability** `p30` from Part 2.
- User-selected **assumed absolute reduction in 30-day churn probability**, from 0 to `p30`.
- Fixed **one-month** contribution-value comparison for MVP. Longer horizons need a separately validated retention-duration assumption/model and are not treated as equivalent to p30.

### 9.2 Formulas

All probabilities and margin values are numeric fractions (e.g., `0.65` and `0.70`).

```text
one_month_contribution_value = MRR × contribution_margin
break_even_abs_reduction = action_cost / one_month_contribution_value
break_even_fraction_of_baseline_risk = break_even_abs_reduction / p30
scenario_gross_incremental_value = assumed_abs_reduction × one_month_contribution_value
scenario_net_value = scenario_gross_incremental_value - action_cost
scenario_ROI = scenario_net_value / action_cost
```

Show `break_even_abs_reduction` as **percentage points (pp)**. Show the risk fraction as a **relative share of the baseline churn risk**. These units must never be conflated.

If `one_month_contribution_value <= 0`, or the scenario lacks reliable MRR/forecast, do not compute a usable financial conclusion. If `p30 = 0`, the relative share is undefined. If `break_even_abs_reduction > p30`, display **"Break-even not achievable within this simplified scenario"**. If action cost is zero, show a zero-cost calculation and ROI as `N/A` rather than dividing by zero.

### 9.3 Verified arithmetic example (not measured ROI)

```text
MRR = RM 1,200
Contribution margin = 70%
30-day baseline churn probability = 65%
Intervention cost = RM 150
One-month contribution value = 1,200 × 0.70 = RM 840
Break-even absolute reduction = 150 / 840 = 0.178571 = 17.86 pp
Required share of baseline risk = 0.178571 / 0.65 = 27.47%
Assumed absolute reduction = 10 pp (unverified input)
Scenario gross incremental value = 0.10 × 840 = RM 84
Scenario net value = 84 - 150 = -RM 66
Scenario ROI = -66 / 150 = -44%
```

**Interpretation:** under these simplified assumptions, the action needs to eliminate approximately **27.5% of the customer's baseline churn probability** to break even. The example does **not** establish that the action actually achieves a 10 pp reduction or saves the stated revenue.

### 9.4 Required labeling

The UI/API must label outputs as:

- `SCENARIO_ONLY` — assumption-based, no treatment-effect model.
- `OBSERVED_OUTCOME` — actual costs/customer outcomes, not proof of causation.
- `VALIDATED_INCREMENTAL_ROI` — **not available in MVP**; require credible randomized or causally defensible comparative evidence.

Changing action cost, margin or assumed effectiveness must genuinely recompute the break-even and ROI figures. Do not hardcode ROI, effectiveness, revenue saved or improvement percentages.

## 10. Human Decision and Outcome Tracking

### 10.1 Human choices and permissions

A person, not the model, must finalize each discretionary retention action:

- `APPROVE` — confirm a proposed eligible action.
- `MODIFY` — choose a different eligible action/plan, with a reason.
- `REJECT` — reject the proposal, with a reason.
- `NO_INTERVENTION` — deliberately take no discretionary action, with a reason and follow-up policy.
- `DEFER` — optional; set an owner and re-review time.

Capture actor identity, decision time, original proposed action, final chosen action, reason code/free text, assigned owner/team and role permissions. Require manager approval for financial offers or contract modifications in any future expansion.

### 10.2 Execution workflow

```text
PROPOSED -> HUMAN_REVIEWED -> ASSIGNED -> EXECUTED -> FOLLOW_UP_DUE -> CLOSED
                       \-> CLOSED_NO_ACTION
                       \-> REJECTED
```

Each lifecycle transition must preserve immutable history, who initiated it and when. Record proposed estimate vs actual spend, staff minutes, first-response latency, execution time and any failure/cancellation.

### 10.3 Observed follow-up outcomes

At **7, 14 and 30 days** after the defined follow-up start, record subscription state and any verifiable payment/usage changes, using time-stamped source events. Record `unknown` where observation is incomplete. Distinguish pending cancellation, active, churned, downgraded and not-yet-observed.

**Observed retention is not proven retention caused by the intervention.** No field should automatically label a retained account as "saved by RetainIQ" without a valid causal estimate.

### 10.4 Experiment readiness — metadata only in MVP

Optionally record `experiment_id`, `assignment_strategy`, `assignment_group`, `assignment_at`, eligibility and business-as-usual status. In the MVP, any experimental allocation demonstration must use clearly identified **synthetic data** unless a reviewed, authorized real experiment exists.

Future holdouts may compare **additional discretionary outreach** with business-as-usual. Do not withhold essential support, contractual services, urgent billing remedies or legally required communications from a control group.

## 11. Minimal Storage and API Design

Reuse Part 1's `tenant_id`/customer identity and Part 2's immutable prediction records. Minimum Part 3 persistence:

| Table | Essential fields |
|---|---|
| `decision_cases` | `tenant_id`, `case_id`, `customer_id`, `prediction_run_id`, `as_of`, `route`, `route_reasons`, `urgency`, `policy_version`, `mrr_minor`, `currency`, `exposure_proxy_minor?`, `cooldown_until?`, `case_created_at`, `case_status` |
| `action_proposals` | `tenant_id`, `proposal_id`, `case_id`, `action_code`, `catalogue_version`, `supporting_fact_refs`, `eligible`, `ineligible_reasons`, `estimated_cost_minor`, `currency`, `estimated_staff_minutes`, `created_at` |
| `human_decisions` | `tenant_id`, `decision_event_id`, `case_id`, `proposal_id?`, `event_type`, `decision_type?`, `original_action?`, `chosen_action?`, `actor_id`, `reason?`, `assigned_owner?`, `estimated_cost_minor?`, `actual_cost_minor?`, `at` |
| `outcome_observations` | `tenant_id`, `observation_id`, `case_id`, `observed_at`, `horizon_days`, `outcome_status`, `source_event_ref?`, `mrr_minor?`, `currency?`, `followup_completeness`, `experiment_metadata?` |

`human_decisions` must be **append-only for meaningful decisions and lifecycle events**; do not overwrite the original model proposal. Ensure case IDs, prediction run IDs and customer IDs are tenant-compatible and enforceable by foreign keys/authorization.

Suggested endpoints:

```text
GET  /v1/decision-cases?route=PRIORITY_REVIEW
GET  /v1/decision-cases/{case_id}
GET  /v1/decision-plan?capacity_k=10
GET  /v1/action-catalogue?case_id={case_id}
POST /v1/decision-cases/{case_id}/decisions
POST /v1/decision-cases/{case_id}/assign
POST /v1/decision-cases/{case_id}/execution
GET  /v1/decision-cases/{case_id}/outcomes
POST /v1/scenarios/break-even
GET  /v1/evaluation/decision?metric=revenue-captured-at-k
```

Security requirements: API-authenticated tenant identity (never trust `tenant_id` from user input), customer/account authorization, least-privilege user roles, idempotency keys for mutations, optimistic locking/transaction constraints for concurrent approvals, monetary limits enforced on the server and audit-safe logging.

## 12. Evaluation: Prove the Planning Policy, Not Imaginary Savings

Use the **same held-out chronological historical event replay** as Part 2. At each weekly decision cutoff, reconstruct only facts and predictions available at that moment. Keep thresholds, policies, model parameters and calibration frozen before final testing.

### 12.1 Primary retrospective metric

**Revenue Captured@K** (better described on a chart as **Subsequently Churned MRR Identified@K**):

```text
RevenueCapturedAtK(t) =
    sum(MRR_at_t for selected eligible accounts that actually churn within 30 days)
    /
    sum(MRR_at_t for all evaluation-eligible accounts that actually churn within 30 days)
```

This is **historical identification coverage**, not retention revenue generated or saved. Compute per currency and cutoff; `N/A` if no churned-MRR denominator. For repeated weekly cutoffs, show per-week results and avoid presenting repeatedly selected accounts as independent retained accounts.

### 12.2 Strategy comparisons

| Strategy | Selection rule | What it establishes |
|---|---|---|
| A — Risk only | Rank by calibrated `p30` | Traditional highest-risk-first baseline |
| B — Risk × MRR | Rank by calibrated `p30 × MRR` | Incremental value of financial weighting |
| C — RetainIQ routing + planning | Eligibility/reliability routing, cooldown, K, then `p30 × MRR` and `p7` tie-break | Operational tradeoffs of safer, implementable review |

Keep the same cohort, cutoff and available reviewer effort. For C, **show the investigation workload separately** and include it in total capacity accounting if reviewers are shared. A route that abstains may yield lower revenue capture; report that honestly.

### 12.3 Ablation and complementary checks

- C minus reliability gate: how much do data investigation and abstention change coverage and review burden?
- C minus cooldown: how many repeated contact proposals are prevented, and at what identification tradeoff?
- C minus urgency tie-break: does 7-day urgency meaningfully change selected cases?
- `Recall@K` and alert/review load alongside financial capture.
- Among cases with observed outcomes, compare absolute prediction error/calibration between reliability categories; report abstention fraction and data defect incidence instead of calling it ungrounded "routing accuracy".
- Budget/time cap compliance, proposal eligibility violations, human override reasons and follow-up completion.

**Not evaluable without intervention data:** incremental customers retained, intervention causal effectiveness, validated ROI or actual budget savings attributable to decisions. Configured action/staff costs are cost assumptions; do not report them as measured savings.

## 13. MVP Demo Script and Evidence Standard

1. Replay a **held-out timestamped customer event** through Part 1's existing ingestion path.
2. Show the normalized customer fact, the stored Part 2 7/14/30-day prediction, `reliability` and freshness.
3. Open the decision case and show its exact route and reason (`PRIORITY_REVIEW`, `HUMAN_REVIEW` or `OBSERVE`).
4. Show the MRR-weighted exposure proxy, review capacity K and correctly recomputed priority shortlist.
5. Show one real **data-eligible** candidate action plus `NO_INTERVENTION`; clearly distinguish unavailable actions.
6. Change an assumption on the one-month break-even card; recalculate pp, fraction of baseline risk, scenario net value and ROI.
7. Let the manager approve/modify/reject; record who decided, why, ownership, timestamp and execution status.
8. Advance the **historical replay clock** to reveal the subsequent recorded customer outcome. Never expose future data to earlier decisions.
9. Show `Revenue Captured@K` and A/B/C backtest results, computed from the frozen test period rather than scripted percentages.

Do not show simulated costs/benefits, example churn probabilities or day-of-warning differences as real empirical metrics. If any scenario uses synthetic data, label its status clearly.

## 14. Build Order

1. Validate the Part 1/Part 2 fields and freeze routing names, money definitions and case policy schema.
2. Implement deterministic eligibility, reliability/freshness routing, `p30 × MRR` ranking and K/cooldown enforcement.
3. Implement the narrow, fact-supported action catalogue and approval-time budget/staff checks.
4. Implement immutable human decisions, assignments, execution and 7/14/30-day follow-up records.
5. Implement the one-month break-even and assumption-based ROI card.
6. Implement frozen historical replay evaluation: A/B/C, `Revenue Captured@K`, reliability/cooldown ablations.
7. Demonstrate one complete traceable case from source event to signed-off human decision and observed outcome.

## 15. Acceptance Criteria

- [ ] Part 3 consumes Part 2's stored predictions, reliability/freshness fields and versions without requesting or using future labels.
- [ ] Cases have exactly the documented routes plus explicit `KNOWN_CANCELLATION`/`NOT_ELIGIBLE` nonpredictive states.
- [ ] Unreliable, stale or financially incomplete cases are investigated instead of being silently ranked or falsely treated as safe.
- [ ] Review K, p30 × MRR ordering, p7 tie-break, cooldown and stable tie ordering work in deterministic tests.
- [ ] As-of MRR and currencies are normalized; exposure is null rather than zero if unavailable.
- [ ] Every executable action passes a required-facts eligibility check; SHAP alone cannot authorize an action.
- [ ] `NO_INTERVENTION` and `DATA_INVESTIGATION` are supported and logged.
- [ ] Budget and staff-minute limits cannot be bypassed by normal approval requests or concurrent approvals.
- [ ] Break-even math passes unit tests including percentage-point/relative-risk interpretation and zero/undefined cases.
- [ ] Scenario outputs are visibly marked as assumptions, not achieved or validated intervention ROI.
- [ ] Human actions retain the original proposal, final choice, reason, actor, timestamps and subsequent execution history.
- [ ] Outcome observations distinguish actual source-backed status from unknown and never automatically credit retention to the intervention.
- [ ] Frozen chronological evaluation reports matched-capacity A/B/C comparisons and relevant ablations.
- [ ] Cross-tenant access, unauthorized approvals and duplicate requests fail safely.
- [ ] No extra paid LLM/model inference is needed for the Part 3 MVP.

## 16. Model and Running-Cost Decision

| Task | MVP implementation | Additional paid AI model? |
|---|---|---|
| Churn probability | Reuse Part 2 LightGBM outputs | No additional model in Part 3 |
| Reliability/freshness routing | Deterministic versioned policy rules | No |
| Exposure / queue selection | Python / SQL | No |
| Fact-to-action matching | Versioned action-catalogue rules | No |
| Budget and staff limits | Backend transactional checks | No |
| ROI scenarios | Transparent arithmetic | No |
| Human review and outcome recording | API + PostgreSQL | No |
| Later causal effectiveness | Controlled experimentation + uplift/causal methods | Future research only |

Software infrastructure, database and engineering costs still exist; "no additional paid AI model" does not mean the platform costs nothing to run.

---

**Final product line:** **Predict early. Plan realistically. Let humans decide. Measure what actually happened.**
