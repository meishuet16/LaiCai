# Member 2 Local SQLite Adapter (Synthetic v1.2)

## Scope and provenance

SQLiteDataAdapter is a read-only bridge from Member 1's authenticated Data
Foundation functions to Member 2's existing point-in-time, eligibility,
feature, freshness, and lifecycle-outcome types. It does not query SQLite
tables directly, create a database, persist snapshots, train a model, or expose
an HTTP endpoint.

The local input is synthetic only:

- Dataset: synthetic-saas-v1-2-standard-s2026-970a9d231e68
- Version: 1.2.0; profile STANDARD; seed 2026; generator build r9
- Manifest SHA-256: 7f85a83a1697efaaeebe1a5534b075ef6c7a99fa5ad3a1e9514b3eb8ae77db6d
- Dataset period: 2024-10-01 through 2026-10-01 (end exclusive)
- Aggregate counts: 3,000 accounts, 4 tenants, 239,721 canonical events,
  491,223 coverage intervals, 14,848 subscription lifecycle events, 13,658
  billing events, and 621 effective account-churn episodes.
- Validation: PASS; no validation warnings. Imported event and coverage counts
  matched the manifest; idempotency replay accepted zero and classified all
  239,721 event rows as duplicates.
- Private dataset root:
  C:\Users\User\RetainIQ-private\synthetic_saas_v1_2
- SQLite file:
  C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3

These data are synthetic fixtures, not authorized real customer data. They
support mathematical and software-path execution only. Model training was not
performed in this task; no real-world effectiveness or model metric is claimed.

## Reproducing the local dataset and smoke checks

Use the repository-local Python environment. Dataset files and the database
remain outside the repository. Run these PowerShell commands:

- .\.venv\Scripts\python.exe -B -m retaniq.synthetic generate --profile standard --seed 2026 --output C:\Users\User\RetainIQ-private\synthetic_saas_v1_2
- .\.venv\Scripts\python.exe -B -m retaniq.synthetic validate --dataset C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68
- .\.venv\Scripts\python.exe -B -m retaniq.synthetic import --dataset C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68 --db C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3 --verify-idempotency
- .\.venv\Scripts\python.exe -B -m retaniq.synthetic provision-reader --dataset C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68 --db C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3 --tenant-id tenant-01
- .\.venv\Scripts\python.exe -B -m examples.member2_synthetic_smoke --db C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\db\synthetic-saas-v1-2-standard-s2026-970a9d231e68.sqlite3 --dataset C:\Users\User\RetainIQ-private\synthetic_saas_v1_2\standard\synthetic-saas-v1-2-standard-s2026-970a9d231e68
- .\.venv\Scripts\python.exe -B -m pytest -q tests\test_sqlite_data_adapter.py

The smoke command obtains its token from RETAINIQ_MODEL_TOKEN; it must not
receive a caller-supplied tenant ID. For this local run the token was protected
with Windows CurrentUser DPAPI outside the repository and only placed in the
child process environment for the command. The environment variable and
transient plaintext buffers were cleared afterward. Do not copy a token into
this document, a command transcript, a fixture, or Git.

## Adapter setup and Member 1 API use

Authenticate using Member 1's authenticate_service_principal(database, token)
and pass that authenticated ServicePrincipal to the adapter. Example:

    adapter = SQLiteDataAdapter(database_path, dataset_path, principal)
    snapshot = adapter.snapshot_for(principal.tenant_id, customer_id, as_of)
    coverage = adapter.coverage_for(principal.tenant_id, customer_id, as_of)
    features = FeatureBuilder(
        adapter,
        config=adapter.feature_builder_config(),
        coverage_provider=adapter,
    ).build(principal.tenant_id, customer_id, as_of)
    eligibility = adapter.eligibility_for(principal.tenant_id, customer_id, as_of)

Construction checks the manifest bytes against Member 1's immutable database
identity, including dataset ID/version, target policy, generator version and
manifest hash. Every read is made through get_dataset_identity,
get_account_snapshot_as_of, get_events_as_of, get_subscriptions_as_of,
get_observation_coverage_as_of, or list_eligible_accounts_as_of. Member 1
revalidates the principal and limits results to its tenant and authorized
source grants. The request tenant must match the principal tenant. Canonical
account identity is required; there is no fuzzy join. customer_id is the
canonical account key, while source_event_id remains provenance and record_id
retains Member 1's internal event identifier.

The APIs do not return a tenant ID on each canonical event row. The adapter
binds those facts to the authenticated principal tenant and verifies the
customer scope. It uses Member 1's as-of subscription fold only as a
consistency check; eligibility facts are reconstructed from timestamped event
history and are never populated from a current-state projection.

## Field mapping and historical availability

| Member 1 record | Member 2 mapping |
|---|---|
| Canonical event ID | HistoricalFact.record_id |
| Authenticated tenant + canonical customer | tenant_id, customer_id |
| Canonical source/category/event type | source, category, event_type |
| occurred_at | occurred_at; retained unchanged |
| source_available_at, received_at | Retained separately; basis noted in availability_basis_by_record |
| Usage quantity, feature, unit | UsageFact.attributes; quantity remains on one daily aggregate row |
| Billing event type and payment status | BillingFact.event_type and payment_status; no amount/currency without valuation authority |
| Subscription event changes | Dated SubscriptionFact lifecycle state, including cancellation and effective dates |
| Coverage interval/status/completeness/availability | UsageCoverage with interval, status, completeness, source category, policy version and availability |
| Manifest and database identity | Immutable adapter.provenance, explicitly SYNTHETIC_ONLY |

Member 1 currently filters events using occurred_at <= as_of and
COALESCE(source_available_at, received_at) <= as_of. The adapter fixes
AvailabilityPolicy.SOURCE_THEN_RECEIVED to match that API; selecting another
policy is rejected rather than silently applying it after Member 1 has already
filtered records. The adapter rechecks timestamps on returned rows. Unknown
availability and late-arriving evidence are excluded and surfaced as
limitations when returned by the API; Member 1's current SQL API normally
filters such rows before returning them, so it does not report counts of all
excluded source records. Neither occurrence time nor processing time is used
as a fallback availability timestamp.

All input datetimes must be timezone-aware. No account customers.account_status
or live subscription projection is used to infer historical eligibility.
Known cancellation is an eligibility route only. Payment failures remain
billing evidence and do not become churn by themselves.

## Usage coverage, aggregates, billing and freshness

v1.2 emits usage_aggregate_updated rows where one row represents a completed
UTC day and its integer quantity is the number of sessions in that day. The
adapter does not expand the quantity into duplicate events. Its feature
configuration counts that quantity as sessions and counts a positive daily
aggregate once toward distinct active days. Invalid aggregate quantities are
not counted and are reported as a feature limitation.

Only coverage with status complete and completeness exactly 1.0 proves a
complete interval. Partial, delayed, outage, censored, not-created, and other
statuses remain incomplete. No coverage records means unknown observation, not
zero activity. Complete coverage with no aggregate events is the only route to
a verified zero-activity feature.

Member 1 redacts billing valuation fields unless specifically authorized.
The adapter does not request valuation authority; payment status is available
for permitted billing events. Freshness evidence uses source events and
coverage intervals, but the current API has no independent sync heartbeat or
source-completeness watermark for lifecycle/billing. Those fields remain
unknown/incomplete rather than being invented. Default freshness age limits
are synthetic examples, not validated SLAs.

The adapter's eligibility helper uses the dataset's explicit v1.2 policy label
only for synthetic data. It must not be copied to a real-data adapter or used
to settle the still-open shared account-level policy. With real data, the
multi-subscription policy must be explicitly agreed and supplied by the team.
The label adapter can return historical events and coverage separately from
prediction-time facts, but a training run still needs approved policy,
complete lifecycle observation, and maturity controls.

## Verification results and limitations

- Dataset generation: PASS, STANDARD / seed 2026; generated in 151.613 seconds.
- Manifest validation: PASS, no validation warnings; identity and hash matched.
- Import: VERIFIED in 104.768 seconds; 239,721 events and 491,223 coverage rows;
  idempotency replay inserted no duplicates.
- Reader: tenant-01 analyst principal; retention inference scope; no
  billing-valuation grant. The Member 1 provisioner also grants
  model_artifact_write; removing that unnecessary permission requires a
  Member 1 provisioning-contract change.
- Official Member 1-to-Member 2 smoke: PASS; tenant denial and dataset identity
  verified; no model training or real-world validation performed.
- Direct adapter smoke: PASS at a historical cutoff; 629 eligible tenant-01
  accounts were enumerated, and a tenant-scoped point-in-time feature snapshot
  and freshness assessment were assembled. A second tenant-scoped check found
  and verified a historical NOT_ELIGIBLE account through the adapter, without
  printing its identifier. The feature sample's freshness assessment was
  stale; this is a quality result, not a failed read or model result.
- Focused adapter and feature tests: 26 passed.

No real authorized longitudinal data, deployed backend/API, source heartbeat,
source-correction/supersession semantics, or production authorization was
verified. The STANDARD synthetic dataset supports execution of the existing
mathematical software path, not evidence of model quality or real-world
predictive effectiveness.

## Future PostgreSQL boundary

Do not port SQLite access or create a competing storage schema. A future
PostgreSQL adapter should implement the existing point-in-time reader boundary
using Member 1's authenticated service context and the same canonical event,
availability, lifecycle and observation-coverage semantics. It must bind
tenant identity from authorization, preserve all timestamps, fail closed on
unknown availability, and carry the canonical dataset/provenance identity.
Snapshot/label/prediction persistence contracts remain separate team decisions.
