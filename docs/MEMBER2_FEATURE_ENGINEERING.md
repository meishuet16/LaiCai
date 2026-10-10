# Member 2 — Point-in-Time Feature Engineering

Status: first personalized behavioral baseline implementation. This module
computes synthetic/testable usage features only. It does not generate churn
labels, train a model, calibrate probabilities, or produce predictions.

## Feature snapshot

`FeatureBuilder.build(...)` returns a versioned `FeatureSnapshot` containing:

- `tenant_id`, `customer_id`, and timezone-aware `as_of`;
- `feature_version` and `data_cutoff_at`;
- typed `feature_values`;
- typed `data_quality` and coverage/missingness metadata; and
- `source_evidence_refs` containing source record and coverage references used
  by the snapshot.

The current version is `features_personalized_baseline_v1`. `data_cutoff_at`
is the requested point-in-time cutoff, not a claim that every source was
fresh or complete. The `features` and `quality` properties are read-only
convenience aliases for `feature_values` and `data_quality`.

## Usage event semantics

The builder never counts every usage event as a session. The configurable
`FeatureBuilderConfig.session_event_types` mapping defaults to
`session_started`. Member 1 must confirm the canonical allowlisted event types
that represent one customer session. Events such as `login` are ignored unless
the mapping explicitly includes them.

The in-memory adapter returns only facts whose applicable event/effective time
and trusted availability time are both at or before `as_of`. The builder does
not bypass that adapter boundary. Future events and late-arriving events are
therefore absent from the feature input and are not counted.

## Window boundaries

The current version uses explicit UTC/timezone-aware intervals:

- recent usage: `[as_of - 7 days, as_of]`, inclusive at both ends;
- 30-day usage: `[as_of - 30 days, as_of]`, inclusive at both ends;
- personal baseline: four complete seven-day weeks ending immediately before
  the recent window, `[as_of - 35 days, as_of - 7 days)`.

The baseline length is configurable from 4 through 8 complete weeks. The
recent window remains seven days for this feature version. A fact at the
baseline/recent boundary belongs to the recent window only, so the windows do
not overlap.

## Implemented feature definitions

The typed `FeatureValues` fields are:

- `sessions_prev_7d`: mapped session events in the recent seven-day window;
- `sessions_prev_30d`: mapped session events in the recent 30-day window;
- `days_since_last_observed_session`: whole days from the latest mapped
  session to `as_of`;
- `recent_usage_trend`: recent weekly session rate minus the last complete
  baseline-week session count;
- `observed_weeks`: complete baseline weeks supported by coverage evidence;
- `valid_usage_history`: true only when usage coverage is complete for the
  recent and baseline periods and the baseline is usable;
- `historical_avg_sessions_per_week`: mean session count over complete baseline
  weeks;
- `recent_avg_sessions_per_week`: session count per week in the recent window;
- `absolute_usage_deviation`: recent average minus historical average;
- `percentage_usage_deviation`: `(recent - baseline) / baseline`, represented
  as a fraction (`-0.75` means `-75%`);
- `recent_to_baseline_usage_ratio`: recent average divided by baseline
  average; and
- `historical_weekly_usage_variability`: population standard deviation of
  complete baseline-week counts.

`personal_baseline_availability_status` is one of `available`,
`zero_baseline`, `insufficient_history`, or `unavailable`.

## Missingness, zero activity, and cold starts

An empty usage event list is not automatically zero activity. The optional
`UsageCoverage` input is explicit evidence that a source period was observed,
complete, and available by `as_of`. A covered period with no session events
produces a confirmed zero. No coverage produces a null count and an
`unknown`/`partial` quality status instead.

Short histories and incomplete coverage preserve observed event counts where
possible but set `valid_usage_history` false and make the personal baseline
unavailable or insufficient. A zero historical baseline exposes the valid
absolute deviation but leaves percentage deviation and ratio null to avoid
division by zero.

No cohort baseline is implemented. A future extension point is the
`UsageCoverageProvider`/feature-builder boundary and the baseline status
field; a cohort fallback must be separately versioned and approved rather than
silently replacing a missing personal baseline.

## Data-quality metadata

`FeatureQuality` records:

- usage coverage status (`complete`, `partial`, or `unknown`);
- personal baseline status;
- observed history days and complete baseline weeks;
- requested and available baseline weeks;
- whether recent and baseline windows are covered;
- per-feature missingness flags; and
- adapter or coverage limitations.

This lets downstream reliability logic distinguish confirmed zero usage,
partially observed activity, and unavailable personal history.

## Required Member 1 inputs and blockers

The real adapter must provide, without changing this feature interface:

- tenant/account-scoped usage records with stable source event IDs;
- canonical event type and occurrence/effective timestamps;
- source availability and/or received timestamps with the agreed precedence;
- a documented definition of what constitutes one session;
- source completeness/coverage evidence for periods with zero activity;
- authorization-scoped tenant reads; and
- enough historical coverage to support repeated cutoffs and complete
  4–8-week personal baselines.

Member 1 still needs to finalize availability semantics, coverage metadata,
session/event mapping, and the account-level subscription policy. The current
in-memory adapter and synthetic coverage fixtures are not production data and
do not establish model performance.

No cancellation request, churn outcome, future payment, protected email, or
sensitive identity field is included in the feature values.
