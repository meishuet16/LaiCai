# Part 2 → Part 3/4 — Prediction Contract (Frozen)

**Owner:** Member 2 (Prediction Engine)  
**Consumers:** Member 3 (Decision Engine), Member 4 (Frontend Dashboard)  
**Status:** FROZEN — v1.0 (temp mock; adjust once real model is ready)  
**Last updated:** 2026-10-10  

---

## 1. Purpose

One **immutable prediction snapshot per account per cutoff** (`as_of`).
`prediction_id` uniquely links a forecast to Part 3 cases and Part 4 feedback.
`prediction_run_id` groups an inference batch — it is **not** a substitute for `prediction_id`.

---

## 2. Canonical Payload

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

---

## 3. Field Contract

| Field | Type | Nullable | Values / Notes |
|---|---|---|---|
| `tenant_id` | string | No | Server-derived from auth; never from request body |
| `customer_id` | string | No | Paying subscription account (not individual seat/user) |
| `prediction_id` | string | No | Unique per account + `as_of`. FK used by Part 3 `decision_cases` and Part 4 `prediction_feedback` |
| `prediction_run_id` | string | No | Groups inference batch. NOT a per-account identifier |
| `as_of` | timestamptz | No | Prediction cutoff. ISO-8601 UTC. Part 3 uses this for MRR lookup (`mrr_as_of`) |
| `generated_at` | timestamptz | No | Actual generation timestamp |
| `status` | enum | No | See §4 |
| `p_churn_7d` | float | Yes | `[0,1]` when scored; `null` otherwise. Cumulative |
| `p_churn_14d` | float | Yes | `[0,1]`. Must satisfy `p7 ≤ p14` |
| `p_churn_30d` | float | Yes | `[0,1]`. Must satisfy `p14 ≤ p30`. Used for `exposure_proxy_30d` |
| `feature_version` | string | No | Versioned feature pipeline |
| `model_version` | string | No | Model artifact version |
| `calibration_version` | string | No | Calibration artifact version |
| `label_policy_version` | string | No | Churn label policy version |
| `reliability.status` | enum | No | See §5 — used by Part 3 routing |
| `reliability.reasons` | array | No | Empty array when no issues |
| `data_freshness.status` | enum | No | See §6 — used by Part 3 cooldown/staleness check |
| `data_freshness.input_data_as_of` | timestamptz | No | Latest source availability cutoff actually used |
| `data_freshness.stale_sources` | array | No | Empty array when fresh |
| `uncertainty.status` | enum | No | Always `"not_quantified"` in MVP |
| `uncertainty.method` | string | No | `"none"` in MVP |
| `uncertainty.intervals` | null | Yes | Always `null` in MVP |
| `explanations_by_horizon` | object | No | SHAP associations per horizon (empty `{}` in MVP). Model associations only — NOT causal triggers |

---

## 4. `status` Enum

| Value | Meaning | `p_churn_*` |
|---|---|---|
| `scored` | Normal eligible scored account | float `[0,1]` |
| `abstained` | Insufficient evidence to score | `null` |
| `known_cancellation` | Cancel already known at cutoff → separate workflow | `null` |
| `not_eligible` | No valid active paying account | `null` |

---

## 5. `reliability.status` Enum

| Value | Meaning | Part 3 routing effect |
|---|---|---|
| `sufficient_evidence` | Required sources and history pass policy | Eligible for `PRIORITY_REVIEW` ranking |
| `limited_evidence` | Prediction possible but data history limited | Route to `HUMAN_REVIEW` investigation |
| `insufficient_evidence` | Critical input missing; model cannot apply | `status = abstained`; probabilities null |

> **Rule for Part 3:** `reliability.status` is a quality gate, NOT a numeric confidence score. Never fabricate confidence percentages from it.

---

## 6. `data_freshness.status` Enum

| Value | Meaning | Part 3 behaviour |
|---|---|---|
| `fresh` | All sources within freshness policy | Normal routing |
| `partially_stale` | Some sources stale | Check which sources; critical billing/subscription staleness → `HUMAN_REVIEW` |
| `stale` | Material outage or late coverage | Route to `HUMAN_REVIEW` |
| `unknown` | Cannot determine freshness | Treat conservatively |

---

## 7. Part 3 Consumption Rules

1. **Never rewrite or re-derive `p_churn_*`** — these are Member 2's frozen outputs.
2. Use `p_churn_30d` as the main financial ranking horizon → `exposure_proxy_30d = p_churn_30d × mrr_minor`.
3. Use `p_churn_7d` as urgency/tie-break only — not for financial ranking.
4. `explanations_by_horizon` SHAP values are **model associations** — never use them as causal action justifications.
5. Match `as_of` to `mrr_as_of` in the MRR contract for correct point-in-time valuation.
6. `prediction_id` is the foreign key for all `decision_cases` records.

---

## 8. Mock Fixture Accounts for Dev

| `prediction_id` | `customer_id` | `p_churn_30d` | `reliability.status` | `status` | Notes |
|---|---|---|---|---|---|
| `pred_001` | `cust_001` | 0.81 | `sufficient_evidence` | `scored` | High risk — rankable |
| `pred_002` | `cust_002` | 0.65 | `sufficient_evidence` | `scored` | Med-high risk — rankable |
| `pred_003` | `cust_003` | 0.78 | `sufficient_evidence` | `scored` | High risk — rankable |
| `pred_004` | `cust_004` | 0.45 | `limited_evidence` | `scored` | → `HUMAN_REVIEW` |
| `pred_005` | `cust_005` | null | `insufficient_evidence` | `abstained` | → `HUMAN_REVIEW` |
| `pred_006` | `cust_006` | null | — | `known_cancellation` | Separate workflow |
| `pred_007` | `cust_007` | null | — | `not_eligible` | Excluded |

---

## 9. Change Policy

Any change to this contract must:
1. Notify Member 3 (Decision Engine) and Member 4 (Frontend) **before** merging.
2. Update version fields (`feature_version`, `model_version`, etc.).
3. Be recorded in `TEAM_LOG.md` in the same commit.
4. Preserve backward-compatible `prediction_id` linkage.
