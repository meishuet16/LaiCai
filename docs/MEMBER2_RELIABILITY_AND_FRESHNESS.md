# Member 2 Reliability Gate and Data Freshness

## Scope and evidence boundary

`reliability.py` and `data_freshness.py` provide deterministic, explainable
pre-scoring assessments. They do not calculate churn probabilities, produce
SHAP explanations, select Part 3 actions, or change the canonical
`PredictionOutput` schema.

Reliability is a data/applicability status, never an individual confidence
percentage. The implementation has no confidence score, confidence interval,
or probability-of-model-correctness field. The canonical uncertainty remains:

```json
{"status": "not_quantified", "method": "none", "intervals": null}
```

## Reliability statuses

`ReliabilityPolicy` is versioned (`reliability_v1` by default) and configurable.
Its default history thresholds are synthetic policy examples: at least 28
observed days and four observed weeks for a full personal-history signal.

- `sufficient_evidence`: identity, eligible-account evidence, required feature
  values, essential source freshness, and applicable coverage pass the policy.
- `limited_evidence`: scoring may be allowed, but sparse personal history,
  partial usage coverage, incomplete optional freshness, or another explicit
  limitation is reported. `allow_limited_scoring` is configurable.
- `insufficient_evidence`: identity, eligibility, required feature values,
  essential lifecycle freshness, or model applicability cannot be established.
  The combined readiness result requires abstention and must map to future
  `PredictionOutput` status `abstained` with null probabilities.

Machine-readable reason codes include identity and eligibility outcomes,
feature cutoff/version/missingness failures, usage coverage states, cold start,
zero-usage-with-coverage, essential/optional freshness limitations, and
`MODEL_ARTIFACT_NOT_READY`. Human-readable reasons are emitted alongside them.

## Evidence and cold starts

The gate checks tenant/account identity across `EligibilityResult`,
`FeatureSnapshot`, and `DataFreshnessAssessment`. It does not infer identity
from a customer-submitted tenant value or allow mismatched evidence to pass.

Missing personal history is not zero usage. A cold-start account is
`limited_evidence` by default and can be configured to
`insufficient_evidence` when the model requires a personal baseline. Confirmed
zero usage with complete coverage and sufficient history is allowed; it is
reported as `ZERO_USAGE_WITH_COVERAGE`, not as stale data or missing activity.
Partial or unknown usage coverage is reported explicitly. Recent silence never
proves churn and never proves connector failure.

Feature requirements are checked when supplied by model metadata or an explicit
required-feature list. Missing or non-finite required values, an incompatible
feature version, or a feature cutoff after `as_of` is blocking. Optional data
that is not required by the model is not automatically blocking.

## Source-specific freshness

`FreshnessPolicy` is versioned (`freshness_v1` by default) and accepts the
existing configurable `AvailabilityPolicy`:

- `SOURCE_THEN_RECEIVED` — prefer source-provided availability and fall back to
  `received_at` only when source availability is absent;
- `SOURCE_ONLY` — require source availability; or
- `RECEIVED_ONLY` — require receipt time.

This preserves the unresolved Member 1 precedence decision rather than silently
creating a new team policy. A source record is usable for a cutoff only when
the selected availability metadata, source watermark, and any selected sync
metadata are not after `as_of`. Future metadata is excluded and yields
`FUTURE_METADATA_EXCLUDED`.

The default sources and synthetic example limits are:

| Source | Default role | Example maximum watermark age |
|---|---|---:|
| `subscription_lifecycle` | essential | 2 days |
| `usage_coverage` | essential | 2 days |
| `billing_events` | optional | 2 days |

These are not production freshness SLAs. Member 1 must validate thresholds and
source coverage semantics. A missing essential source or stale essential source
produces aggregate `unknown` or `stale` and blocks normal scoring. An optional
missing source is visible but does not by itself block freshness; reliability
may report `limited_evidence` when that limitation matters.

Source freshness is based on availability, sync, coverage, and watermark
metadata. It is not based on the time since the last customer session. Healthy
usage coverage with no recent sessions can therefore remain `fresh`. Missing
freshness metadata is `unknown`, never silently `fresh`.

Each source assessment preserves source evidence, availability basis,
`input_data_as_of`, source references, status, and reason codes. Aggregate
output preserves per-source statuses, missing sources, the latest accepted
input cutoff, policy version, and evaluation timestamp.

## Combined readiness and abstention

`assess_prediction_readiness` combines eligibility, features, freshness, and an
optional calibrated model-bundle readiness result:

| Input condition | Result |
|---|---|
| Eligible, sufficient data, complete PASS model bundle | Scoring allowed; no probability is generated here |
| Eligible, limited data, safeguards and policy permit | Scoring may proceed with warnings preserved |
| Eligible, insufficient data or blocking freshness | `abstained`; no numeric score |
| Known cancellation | `known_cancellation`; never prospective-score |
| Not eligible | `not_eligible`; never score |
| Insufficient eligibility | `abstained`, not `not_eligible` |
| Missing/incomplete calibrated model bundle | `abstained`; data reliability cannot override artifact readiness |

Model readiness is deliberately separate from data reliability. A complete
calibrated bundle must report all 7/14/30 horizons, no missing horizons, and
`DatasetStatus.PASS` for each horizon before it can enable scoring. This gate
does not perform inference or fill any probability field.

## Member 1 integration requirements

The real adapter/backend must provide tenant-authorized, account-scoped:

- dated subscription lifecycle facts and essential historical coverage;
- source availability and `received_at` timestamps without replacing unknown
  availability with event time;
- source heartbeat/sync status and source event watermarks;
- usage coverage/completeness evidence independent of activity events;
- billing freshness evidence when billing features are enabled;
- stable feature/model/calibration/label-policy versions; and
- provenance, correction/conflict handling, and the agreed multi-subscription
  account policy.

Authentication and authorization remain Member 1/backend responsibilities. The
in-memory tests enforce tenant/account scoping but are not an authorization
service.

## Validation plan and current limitations

The thresholds and rules require validation on authorized chronological replay
data. Future evaluation must report abstention and limited-evidence shares,
prediction error/calibration by reliability cohort, source outage cases, and
false-safe/false-abstention trade-offs. It must not convert missing outcomes or
missing coverage into negative evidence.

No authorized longitudinal dataset exists in this repository. Current tests
are synthetic structural tests only. No production freshness SLA, OOD detector,
confidence estimate, predictive metric, or retention result is claimed.
