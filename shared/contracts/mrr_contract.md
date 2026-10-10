# Part 1 → Part 3 — MRR Contract (Frozen)

**Owner:** Member 1 (Data Foundation)
**Consumer:** Member 3 (Decision Engine)
**Status:** FROZEN — v1.0
**Last updated:** 2026-10-10

---

## 1. Purpose

Provide an **`as_of`-dated, normalized MRR per paying account**, so Part 3 can compute
`exposure_proxy_30d = calibrated_p_churn_30d × mrr_minor` without reimplementing
money normalization.

MRR is a **derived** value, not a raw column. It is normalized from subscription
state at a specific `as_of`, not read from a live subscription row.

---

## 2. Delivery Interface

Member 1 delivers MRR via **one** of the following (agreed: Option A).

### Option A — SQL view (chosen)
`account_mrr_as_of`

### Option B — API endpoint (fallback)
`GET /v1/accounts/{customer_id}/valuation?as_of=<ISO-8601>`

### Option C — Bundled decision-context payload (fallback)
Returned inside a Part 1 payload consumed by Part 3.

**Chosen:** Option A.

---

## 3. Field Contract

| Field | Type | Nullable | Unit / Format | Description |
|---|---|---|---|---|
| `tenant_id` | string | No | — | Server-derived. Never client-submitted. |
| `customer_id` | string | No | — | Paying subscription account. Not a seat/user. |
| `mrr_as_of` | timestamptz | No | ISO-8601 UTC | Must equal the prediction `as_of`. |
| `mrr_minor` | integer | **Yes** | Integer minor units | Normalized monthly recurring amount. Null if missing. |
| `currency` | string | No | ISO-4217 | e.g. `"MYR"`, `"USD"`, `"JPY"`. |
| `mrr_basis_version` | string | No | — | Versioned normalization policy, e.g. `"mrr_policy_v1"`. |
| `subscription_count` | integer | No | — | Number of active subscriptions summed into `mrr_minor`. |
| `mrr_completeness` | enum | No | `complete` \| `partial` \| `missing` | Quality flag. |
| `mrr_components` | jsonb | Yes | — | Optional breakdown for the decision brief. |

**Forbidden in this contract:**
- `mrr_major` (float major units) — must be integer minor units only
- Any client-supplied `tenant_id`
- Mixed-currency aggregate without explicit FX metadata

---

## 4. Enum Values

### `mrr_completeness`
- `complete` — all required source fields present, normalization succeeded
- `partial` — some fields missing; value returned but may understate MRR
- `missing` — cannot compute MRR; `mrr_minor` MUST be `null`

**Rule:** `mrr_completeness = "missing"` ⇒ `mrr_minor = null`. Never `0`.

---

## 5. Normalization Policy (`mrr_basis_version = "mrr_policy_v1"`)

```text
mrr_minor = normalized recurring contract amount per month,
            after applicable recurring discounts,
            excluding one-off charges, taxes, and credits.

Normalization:
  weekly    → amount × 52 / 12
  monthly   → amount
  quarterly → amount / 3
  annual    → amount / 12

Currency:
  Stored as integer minor units per ISO-4217 exponent.
  Zero-decimal currencies (JPY, KRW) use exponent 0.
  Never silently sum different currencies.

Multi-subscription:
  Sum across active subscriptions for the account.
  `subscription_count` reflects how many were summed.
  Churn definition = last paying subscription ends (per Part 1 policy).

Discounts:
  Recurring discounts applied before storing `mrr_minor`.
  One-time discounts excluded.
  Discount recurrence must be recorded in source data.