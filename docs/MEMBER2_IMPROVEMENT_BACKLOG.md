# Member 2 Improvement Backlog

## IMPROVEMENT-001: Personalized Baseline Ablation Study

Status: PENDING — requires an authorized longitudinal dataset and trained models.

Current MVP:

- Four complete historical baseline weeks.
- Recent seven-day usage comparison.

Future verification:

- Compare a model using ordinary usage features against the same model with personalized baseline features.
- Use the same chronological test cohorts, prediction horizons and alert budget.
- Report PR-AUC, Brier Score, Recall@K, warning lead time and false alerts.
- Do not claim personalization improves performance unless empirical evidence supports it.

This backlog is for later improvement work. The ablation study is not implemented.

## IMPROVEMENT-002: Multi-Subscription Churn Definition

Status: NEEDS_TEAM_DECISION

Issue:

RetainIQ predicts churn at the paying-account level.

An account may own multiple active subscriptions. Ending one subscription does
not necessarily mean the entire paying account has churned.

Existing policies:

- `any_subscription_end`
- `all_subscriptions_end`

Requirements:

- Do not enable `any_subscription_end` as the default account-level churn definition.
- Preserve unsupported or unresolved status when the required business policy is not confirmed.
- Member 1 and Member 2 must agree on authoritative account-level churn semantics and effective churn timestamp.
- Confirm the handling of simultaneous subscriptions, partial cancellations, renewals, and account termination.
- Do not silently change existing label-builder policy or historical labels.
- Revisit affected labels and evaluation if the policy changes.

Owner: Member 1 + Member 2.

This issue is not resolved by the baseline implementation.

## IMPROVEMENT-003: Rule-Based Alert Threshold Validation

Status: PENDING_VALIDATION_DATA

Description:

The current inactivity, usage-decline, payment-failure weights, and alert
threshold are provisional heuristics. Select or tune thresholds using
development/validation data only, and compare against the final models under
the same alert budget.

Threshold tuning is not implemented in the current milestone.
