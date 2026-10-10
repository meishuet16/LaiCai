# Member 2 Operational Inference Integration

## Scope

`retainiq_prediction.operational_inference` composes the existing point-in-time
adapter, feature/reliability gates, calibrated prediction pipeline and Part 1
prediction writer. It adds orchestration only; it does not add an API server,
scheduler, database schema, source-ingestion path, or model. It never accepts
churn outcomes or labels as inference inputs.

## Batch scoring and persistence

`DailyPredictionBatch.run(as_of, prediction_run_id)` obtains the tenant from
the configured source/principal, asks the source for eligible accounts at the
cutoff, and evaluates every returned account—including accounts with no recent
usage events. The existing `PredictionPipeline` remains responsible for
historical eligibility, point-in-time facts, feature construction, freshness,
reliability, abstention, calibrated horizon outputs and explanations.

The storage protocol is append-only and unique by `(tenant_id, customer_id,
as_of)`, consistent with the repository's canonical Part 1 prediction table.
Exact retries are idempotent; a different payload for the same snapshot is a
conflict. `DataFoundationPredictionSnapshotStore` maps the flat canonical
fields to the existing `retaniq.data_foundation.store_prediction` writer and
never issues direct SQL. It requires an authenticated, tenant-scoped
read-before-write callback for idempotent retries. The existing Member 1
surface does not currently expose a prediction reader/history reader, so the
real adapter cannot be fully wired until Member 1 supplies these callbacks (or
equivalent authenticated APIs). The database writer persists the supported
`not_quantified` uncertainty status; no numeric uncertainty is produced.

Batch item outcomes distinguish stored, already present, model not ready,
pipeline failure, input-evidence failure and persistence failure. They include
safe exception type codes, not exception messages or customer data. A
`synthetic_test_only` marker is propagated from the pipeline result.

## Event triggers and alert policy

`EventTriggeredPrediction` rejects a tenant mismatch and rejects an event if
either its occurrence or availability time is after the requested cutoff.
Duplicate source/event identities are suppressed in-process; conflicting reuse
of an event identity is rejected. This in-memory suppression is suitable for
structural tests only. Production needs durable event idempotency owned by the
ingestion/job system.

`apply_alert_policy` evaluates already-persisted canonical predictions under an
explicit `policy_version`: scored status, reliability floor, freshness
allowlist, p30 threshold, comparable/rising-risk history, cooldown and a
period-level alert budget. It returns decisions but does not persist them or
send contacts. Thresholds, cooldowns and budgets are caller-supplied policy,
not empirically selected values. This is a risk-warning gate, not Part 3
review ranking, discretionary-contact cooldown, action selection or resource
optimization.

`risk_evolution` compares chronological snapshots only when status and model,
calibration and feature versions match. Its output is a change between prior
predictions—not a forecast trajectory.

## Historical replay

`PointInTimeReplayRunner` accepts strictly increasing, timezone-aware cutoffs
and sends each through the same point-in-time scoring path. It retrieves the
persisted outputs after each call and computes risk changes only from those
outputs. It has no label/outcome argument, so it cannot reveal future outcomes
while building predictions. Full replay through Member 1's timestamp-ordered
Push API is still an integration dependency; this runner reuses the existing
historical adapter and does not mutate/re-ingest source events.

## Readiness and Member 1 handoff

- No deployable 7/14/30-day model bundle is currently available. The frozen
  synthetic STANDARD evidence is not production-ready; 7-day fitting and
  calibration gates fail, and the 14/30-day synthetic validation comparisons
  do not establish useful predictive skill.
- Member 1 should expose tenant-authorized `get_prediction(tenant principal,
  customer_id, as_of)` and prediction-history reads with canonical fields and
  immutable identity checks. A history reader should support bounded account
  reads for replay/risk evolution.
- The app/job owner should provide durable event-trigger idempotency and
  append-only alert-decision persistence, plus its deployment scheduler and
  retry policy.
- Do not serve the uncalibrated Prompt 31 demo files through this integration.
  The pipeline's existing `MODEL_BUNDLE_NOT_READY` state remains the safe
  production behavior until all data/model gates pass.

All tests added for this module use explicitly synthetic in-memory fixtures.
They verify interface behavior only and are not predictive-performance or
production-readiness evidence.
