# RetainIQ v2 — Coding Agent Instructions

**Applies to:** AI coding agents, code assistants and human contributors working in this repository.  
**Canonical spec:** `RetainIQ_v2_Complete_Requirements.md`  
**Mandatory per-commit log:** `TEAM_LOG.md`

> **Core rule:** Build an honest, traceable, tenant-safe retention product. Do not invent model performance, customer results, saved revenue, AI intervention effectiveness, or API behavior. **Every code/documentation commit must update `TEAM_LOG.md` in the same commit.**

## 1. First actions before editing

1. Read `RetainIQ_v2_Complete_Requirements.md`, especially Sections **3–4** (common definitions/contracts), the relevant part (Sections **5–8**), Section **10** (evidence), Section **13** (testing) and Section **17** (reconciled changes).
2. Read `TEAM_LOG.md` to identify what other members changed, current blockers and active integration dependencies.
3. Inspect the actual repository structure and existing code/tests. Do **not** assume a library, framework, database migration, API, deployed infrastructure, connector or trained model already exists.
4. Work in a focused change. Prefer the smallest complete implementation with tests over speculative features.
5. If an instruction conflicts with the canonical spec, report the conflict in your change explanation and log; do not silently rewrite shared contracts.

## 2. Architecture and responsibilities

| Part | Owns | Agent must not move here |
|---|---|---|
| **1 — Data Foundation** | Authenticated ingestion, historical import, canonical tenant/customer/subscription records, point-in-time sources, MRR/labels | Retention-effect claims or discretionary outreach |
| **2 — Prediction Engine** | Point-in-time features, real 7/14/30-day labels, LightGBM/baselines, calibration, reliability, predictions | Budget, action selection, ROI, artificial confidence scores |
| **3 — Decision Engine** | Routing, p30×MRR review prioritization, fact-based action catalog, top-K, budget/staff gate, human choices/outcomes, break-even scenario | Autonomous offers, unverified uplift modeling, model retraining |
| **4 — Closed Loop & Dashboard** | Mature feedback, model checks, authorized retraining release, source-backed BI and end-to-end timeline | A duplicate action engine or online self-modifying model |

Treat RetainIQ as **an extension to clients' systems**, not a replacement for a client's entire application stack. Use one canonical dataset family/schema for historical replay and live ingestion.

## 3. Non-negotiable data and security rules

- Always derive `tenant_id` from authenticated server context; never trust a user-submitted tenant ID. Enforce tenant-scoped reads, writes, joins, training and exports.
- The prediction unit is a **paying subscription account**; do not conflate it with individual users/seats.
- Retain `occurred_at`, `received_at`/true source availability and `as_of`. **Never** use events or knowledge arriving after `as_of` in earlier model features. Do not treat replay processing time as historical availability.
- A cancellation request already known at cutoff means **known cancellation**: exclude it from prospective churn scoring. A failed payment is **not** automatically churn.
- Negative training/evaluation labels require complete observation over the full horizon. Missing or censored outcomes stay **unknown**.
- Sensitive fields must be classified and minimized **before storage**; do not place card credentials, raw secrets, unnecessary emails or private notes into model features or logs.
- Store money in integer minor units plus ISO currency. Normalize MRR at the original as-of date. Never blindly sum different currencies or treat p30×MRR as exact cash loss.
- Use stable IDs, unique source event keys/idempotency, tenant-safe foreign keys and transaction-safe approval/budget enforcement.
- Keep meaningful user decisions, model releases and corrections auditable; use append-only events or explicit versioned supersession.

## 4. Canonical interfaces — do not drift

### Prediction snapshots

One immutable forecast snapshot per account/cutoff has:

```text
tenant_id, customer_id, prediction_id, prediction_run_id,
as_of, generated_at,
status: scored | abstained | known_cancellation | not_eligible,
p_churn_7d, p_churn_14d, p_churn_30d,
feature_version, model_version, calibration_version,
reliability.status: sufficient_evidence | limited_evidence | insufficient_evidence,
data_freshness.status: fresh | partially_stale | stale | unknown,
uncertainty.status: not_quantified (unless defensibly validated),
explanations_by_horizon (actual model attributions if available)
```

- `prediction_id` uniquely links an account snapshot to Part 3 cases and Part 4 outcome feedback. `prediction_run_id` groups inference jobs and is **not** a substitute for a per-account identifier.
- Probabilities are **calibrated cumulative** with `0 <= p7 <= p14 <= p30 <= 1` when scored. Abstained/known-cancellation/ineligible forecasts use null probabilities.
- A reliability status is **not** a numerical prediction-confidence percentage. Do not fabricate confidence intervals or arbitrary risk scores.
- Explanations such as SHAP are **model associations**, never sufficient evidence that an action will work.

### Decision routes and priorities

```text
PRIORITY_REVIEW | HUMAN_REVIEW | OBSERVE
KNOWN_CANCELLATION | NOT_ELIGIBLE  # separate nonpredictive states
priority_sort = calibrated_p_churn_30d * as_of_MRR
p_churn_7d = urgency indicator and tie-break, not a made-up weight
```

- Route eligibility and reliability/freshness **before** financial ranking.
- Make cooldowns explicit and suppress repeated *discretionary* contacts, not normal support or contractual notices.
- Top-K means reviewer slots; it does not mean K saved accounts. Investigation burden cannot be hidden from shared staff capacity.

### Action catalog and ROI

- Enable `ACCOUNT_CHECK_IN` with observed usage-change evidence and `PAYMENT_RECOVERY` with verified billing failures; `PRODUCT_WALKTHROUGH` only when feature-level facts support it.
- Always support `DATA_INVESTIGATION` and `NO_INTERVENTION`.
- Support-ticket escalation, plan change, pause/downgrade and discount need their real supporting data and approval policies; otherwise **disabled or clearly synthetic-demo-only**.
- Budget/capacity limits require **backend transactional checks**; a UI-only restriction is insufficient.
- ROI MVP is a **one-month assumption-based break-even card**, not causal uplift prediction:

```text
contribution_value = MRR * contribution_margin
break_even_absolute_reduction = action_cost / contribution_value
break_even_relative_risk_fraction = break_even_absolute_reduction / p30
scenario_gross_value = assumed_absolute_reduction * contribution_value
scenario_net_value = scenario_gross_value - action_cost
scenario_ROI = scenario_net_value / action_cost
```

Absolute reduction must be displayed as **percentage points**; relative risk share as a **percentage**. Handle zero/unknown denominators and impossible break-even thresholds. Always label assumptions `SCENARIO_ONLY` and never claim real retention savings without valid causal evidence.

### Learning and outcomes

- Prediction-feedback horizons anchor at **prediction `as_of`**; post-action operational follow-up anchors at the **defined action/follow-up start**. Do not mix them.
- Feedback states: `PENDING | MATURE_POSITIVE | MATURE_NEGATIVE | INCOMPLETE | INELIGIBLE`. No early negatives.
- Observed “still subscribed” is **not proof** an intervention saved that account. Human/AI suggestion changes must be preserved.
- Model retraining may create a candidate **only from eligible mature labels**, using proper chronology. Operator approval and an independent model comparison gate are required before promotion; a failed/not-ready candidate is acceptable. Support rollback.

## 5. Model/data integrity and demo rules

- Do not fabricate historical timestamps, churn effective dates, source fields, model scores, financial results, sample counts or KPI improvements.
- Distinguish **real source-backed data**, **synthetic fixtures**, **configurable cost/effectiveness assumptions**, and **held-out measured metrics** in UI, code, docs, and demo.
- Use chronological train/development/calibration/untouched-test windows with label maturity and no leakage.
- Primary model candidate: 7/14/30-day LightGBM classifiers; comparison baselines: rules and logistic regression. Personalized-baseline ablation is important.
- Report PR-AUC, Brier/calibration, Recall@K, lead time and false-alert workload **only when computed from sufficient held-out data**.
- Part 3 `RevenueCaptured@K` identifies subsequently churned MRR in the selected historic review set; it is **not** saved revenue.
- Historical replay must freeze time, generate actual predictions with then-available data and reveal future outcomes **after** saving those predictions.
- If the dataset or infrastructure cannot support a feature, implement a clean `unavailable`/`N/A`/`NOT_READY` state and document the blocker rather than fake the result.

## 6. Coding and test workflow

For **every task**:

1. Identify the relevant requirement and affected owner(s) and APIs.
2. Inspect related files and write the smallest coherent change; avoid unnecessary framework migration or adding a new LLM/tool just for the sake of AI.
3. Add/adjust tests for the touched logic and negative/edge cases. At minimum consider time leakage, identity/tenant scoping, currency/MRR, idempotency and human permissions where applicable.
4. Run applicable test/typecheck/lint/build commands that **actually exist in the repository**. Never claim a command passed without running it.
5. Document migrations, backfill, public API/contract changes and downstream impacts; update the full requirements spec if the agreement changes.
6. Update `TEAM_LOG.md` with one entry for this commit, in the same commit, including commands/results and blockers.
7. Re-check that staged files contain no secrets, private account data or fake empirical claims.
8. Provide a concise completion summary: what changed, what was verified, what could not be verified and what remains.

**Suggested tests by change type:**

| Work changed | Minimum tests/checks |
|---|---|
| Ingestion/schema | auth rejection, idempotent repeats, source mapping, field redaction, tenant separation |
| Snapshot/labels | after-cutoff/late-available event rejected, pending-cancel exclusion, 7/14/30 censoring |
| Model/calibration | real trained outputs, horizon monotonicity, baseline comparison, abstain behavior |
| Decision | route enum, p30×MRR sorting, tie-break, K/cooldown, disabled unsupported actions |
| Cost/ROI | margin units, 17.86 pp / 27.47% example, zero cost, missing MRR, impossible break-even |
| Approvals | RBAC, immutable proposal/override reason, concurrent budget caps, audit events |
| Feedback/dashboard | correct horizon maturity, action vs prediction time, reconciliation, tenant scoping |
| Model registry | reject insufficient evidence, independent test release gate, promotion authorization, rollback |

## 7. Required TEAM_LOG.md behavior for every commit

**You MUST update `TEAM_LOG.md` in the same commit as your files.** Copy the template from its Section 3 and insert a new entry at the top of Section 4. Include:

- Actual date/time in UTC, member/agent identity, branch and commit subject.
- Specific changed paths and behavior and the reason.
- Contract, migration or API effects and other workstream owners to notify.
- Actual tests/commands and honest outcomes (`PASS`, `FAIL`, `NOT RUN` with reason).
- Data/model evidence type (`real`, `synthetic`, `assumption`, `N/A`) and limitations.
- Known blockers plus the next handoff/action.

**Important:** You cannot know the new Git commit SHA before creating the commit. Do **not** invent a SHA or amend in a fake reference. An optional future entry can reference an existing SHA.

**Before committing (if Git is available):**

```bash
git status --short
git add -- path/to/changed_file TEAM_LOG.md
git diff --cached --name-only
git diff --cached --check
# Confirm TEAM_LOG.md and related tests are staged; then commit.
git commit -m "feat: meaningful summary"
```

Replace `path/to/changed_file` with the actual changed path(s). Never stage unrelated secrets or data. If not working in a Git repository, still prepare a truthful pending entry when creating deliverable files; do not claim a commit happened.

## 8. Collaboration, interface updates and priorities

- Do not change shared enum values, money semantics, label rules, `as_of`, `prediction_id` or API paths without coordinating affected owners and adjusting tests/documentation/logs.
- Keep Part 1–4 integration working end-to-end; a dashboard component with hardcoded pretend customer results is **not** finished.
- For hackathon time pressure, prioritize: (1) dataset gate, (2) secure canonical Push API/replay, (3) real time-safe prediction, (4) human review/eligible action flow, (5) customer timeline/dashboard, (6) evidence-backed feedback/retraining gate.
- Anything optional (Stripe webhook, extra connectors, support text NLP, uplift, OR-Tools global solver, interactive multi-bundle ROI) must not delay the core path.
- When blocked, state the blocker and provide a safe partial implementation or clear disabled state. Do not silently change the product claim.

## 9. What counts as finished

A task is complete only when it is (a) consistent with the canonical contract, (b) secure and testable for its scope, (c) connected to real source-backed records or explicitly labeled fixtures, (d) documented with reproducible verification evidence, and (e) **recorded in `TEAM_LOG.md` as part of the same commit**.

**Final principle:** Accuracy and traceability matter more than an impressive-looking but unverified AI demo.
