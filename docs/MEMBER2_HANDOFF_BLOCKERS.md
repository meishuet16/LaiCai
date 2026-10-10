# Member 2 Handoff Blockers

This list reports current integration blockers from repository evidence. No
external completion or team commitment is assumed.

| ID | Description | Severity | Owner | Required decision/data | Affected functionality | Evidence/status | Acceptance condition |
|---|---|---:|---|---|---|---|---|
| M2-P0-001 | No authorized timestamped longitudinal dataset or `DATASET_CARD.md` | P0 | Member 1 / team | Authorized source, license, coverage, schema mapping, provenance | Real features, labels, training, evaluation, metrics, production scoring | No authorized dataset exists in repository; synthetic fixtures only | DATASET_CARD and readiness report pass with authorized real provenance |
| M2-P0-002 | No canonical authenticated tenant-scoped backend adapter/API | P0 | Member 1 | Auth boundary, canonical IDs, durable storage and read contract | Historical replay, live scoring, feedback persistence, security | Only replaceable in-memory adapters exist | Member 1 adapter passes tenant, availability, correction and replay tests |
| M2-P0-003 | Account-level multi-subscription churn policy unresolved | P0 | Member 1 + Member 2 + team | Define last/all/contract-specific semantics and effective timestamp | Eligibility, labels, feedback maturity, evaluation and training | `IMPROVEMENT-002` remains `NEEDS_TEAM_DECISION` | Versioned policy is documented and applied to real lifecycle history |
| M2-P0-004 | Source availability/watermark/correction precedence unresolved | P0 | Member 1 + team | Precedence among source availability, received time, watermark and revisions | Point-in-time features, labels, feedback and replay | Local adapter is conservative and configurable; no external policy confirmed | Canonical availability/correction contract with replay evidence |
| M2-P0-005 | No durable model artifact, approval, active-bundle or rollback backend | P0 | Member 1/backend + Part 4 | Trusted artifact integrity, RBAC, append-only audit, atomic CAS store | Production promotion, serving and rollback | Prompt 19 governance is process-local and explicitly blocks production | Durable interfaces pass authorization, idempotency, CAS and audit acceptance tests |
| M2-P1-001 | Member 3 action/feedback schema and MRR contract not implemented in this repo | P1 | Member 3 + Member 1 | Prediction linkage, action timestamps, currency/MRR evidence and outcome fields | Decision routing, action tracking and dashboard outcome views | Member 2 documents the handoff; no Part 3 implementation exists | Member 3 consumes `prediction_id` and preserves causal/non-causal distinctions |
| M2-P1-002 | Member 4 dashboard query/display contract not implemented | P1 | Member 4 | Query shape, refresh, warning and revision presentation | Dashboard and end-to-end demonstration | No frontend is present in this repository | UI acceptance tests preserve null/status/version/provenance semantics |
| M2-P1-003 | Prompt 18 original 28 candidate scenarios lack final coverage matrix | P1 | Member 2 | Scenario-to-test mapping and missing regression tests | Final governance regression sign-off | Prompt 19 intentionally deferred review | Coverage matrix marks every scenario and missing cases are tested |
| M2-P1-004 | Prompt 19 governance scenario coverage needs final regression review | P1 | Member 2 | Review 30 governance scenarios against requirements and integration | Release governance confidence | Local 30-test suite exists; final review not performed | Independent coverage review completed and logged |
| M2-P1-005 | Improvement backlog validation studies lack real data/models | P1 | Member 2 + team | Complete authorized cohorts and evaluation policy | Personalization, thresholds, calibration, evaluation audit | `IMPROVEMENT-001`–`005` remain pending or unresolved | Each item has evidence-backed result or remains explicitly pending |

## Current readiness interpretation

Local contracts and tests are implemented. Real production readiness is
**BLOCKED** by the P0 items above. Passing synthetic unit tests does not prove
data quality, model performance, secure deployment, retention effectiveness or
ROI.
