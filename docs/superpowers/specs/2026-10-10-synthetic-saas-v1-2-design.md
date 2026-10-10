# Synthetic SaaS v1.2 Design

## Goal

Deliver an independently simulated, event-backed Synthetic SaaS v1.2 family whose daily usage, dated subscription lifecycle, observation coverage, and chronological outcome evidence can be reconstructed through the existing tenant-safe Member 1 interfaces.

## Architecture

The generator writes immutable QUICK, STANDARD, and FULL datasets outside Git. Usage is represented as one `usage_aggregate_updated` event per active account-day. Its quantity counts sessions in the completed UTC day window ending at `occurred_at`; only these rows contribute to session totals. Feature adoption uses the event's `feature` value. Missing or non-complete observation intervals remain unknown rather than becoming zero.

Source files carry customer/source coverage intervals with availability timestamps and an observation-policy version. Subscription events remain authoritative for eligibility, effective account-level churn, and reactivation episodes. Calendar-aware period arithmetic and explicit renewal updates preserve the existing event allowlist. The generator exports source-backed truth and coverage but no future churn flag or latent predictor values.

Canonical SQLite storage binds one immutable dataset identity to each database. A mismatch is rejected before import writes. Coverage reads use the same tenant, source, and retention-purpose checks as canonical event reads. Import uses bounded validated transactions, stable idempotency keys, and durable per-stream checkpoints; it does not bypass normalization, ownership, or authorization checks.

An independent validator recomputes counts, hashes, scenario evidence, usage density, coverage, horizon feasibility, and chronological maturity from exported files. STANDARD is imported and exercised through an authorized service principal. A smoke command keeps as-of features and later outcome-oracle evidence in separate report sections. Member 2 continues to own production feature construction, label construction, model fitting, calibration, and evaluation.

## Compatibility and constraints

- Preserve canonical event attribute allowlists and the existing `prediction_id`, `prediction_run_id`, `as_of`, horizon, churn-effective, known-cancellation, MRR, authorization, and reliability contracts.
- Keep Synthetic SaaS and KKBox in separate dataset identities, database files, target policies, model namespaces, and evaluation populations.
- Do not train models or claim real-world predictive performance.
- Keep generated datasets and SQLite databases outside Git; never include credentials in exports or logs.
- Do not push, merge, or create a pull request.

## Error handling and recovery

Invalid import records are rejected within row savepoints and cannot roll back earlier committed batches. A failed batch leaves its event and checkpoint state atomic. Re-running a completed import verifies stable source keys as duplicates. Dataset metadata mismatch aborts before provisioning or event import. Incomplete or delayed outcome coverage yields unknown labels in the independent QA calculation.

## Verification design

Tests first cover daily UTC window boundaries, no session double-counting, calendar periods, future-starting subscription eligibility, coverage availability, account-level partial termination, dataset mismatch, checkpoint resume, idempotency, and cross-tenant/source denial. QUICK provides fast contract verification. STANDARD must complete canonical import and the authorized handoff smoke test. FULL generation and manifest/source validation are required; full canonical import is bounded by measured resource cost.
